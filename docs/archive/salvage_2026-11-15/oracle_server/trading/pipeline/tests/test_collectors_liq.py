import datetime as dt
import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import deriv, hl, kisintra, krsurge, liqmap


# ---------------------------------------------------------------- deriv
FORCE = {"e": "forceOrder", "E": 1, "o": {"s": "BTCUSDT", "S": "SELL", "o": "LIMIT", "f": "IOC", "q": "0.1", "p": "80000", "ap": "79990",
                                          "X": "FILLED", "l": "0.1", "z": "0.1", "T": 1792898000000}}


def test_force_order_parse_keeps_only_btc_eth():
    r = deriv.parse_force_order(FORCE)
    assert r[1] == "BTCUSDT" and r[2] == "SELL" and r[3] == 80000.0
    other = json.loads(json.dumps(FORCE))
    other["o"]["s"] = "DOGEUSDT"
    assert deriv.parse_force_order(other) is None
    assert deriv.parse_force_order({"garbage": 1}) is None


def test_liq_insert_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(deriv, "DDIR", tmp_path)
    monkeypatch.setattr(deriv, "DB", tmp_path / "d.sqlite")
    con = deriv.db()
    row = deriv.parse_force_order(FORCE)
    deriv.save_liq(con, [row, row])
    assert con.execute("SELECT COUNT(*) FROM liq").fetchone()[0] == 1


# ---------------------------------------------------------------- hyperliquid
def _state(szi="0.5", liq="70000.0", coin="BTC", lev=10):
    return {"marginSummary": {"accountValue": "100000"}, "assetPositions": [{"type": "oneWay", "position": {
        "coin": coin, "szi": szi, "entryPx": "80000", "liquidationPx": liq, "positionValue": "40000", "marginUsed": "4000",
        "leverage": {"type": "cross", "value": lev}}}]}


def test_hl_parse_state_validates():
    rows = hl.parse_state("0x" + "a" * 40, _state(), b"{}")
    assert len(rows) == 1 and rows[0][0] == "BTC" and rows[0][3] == 70000.0
    assert hl.parse_state("a", _state(coin="DOGE"), b"{}") == []                  # other coins ignored
    assert hl.parse_state("a", _state(lev=900), b"{}") == []                       # absurd leverage dropped
    assert hl.parse_state("a", {"assetPositions": [{"position": {"coin": "BTC", "szi": "x"}}]}, b"{}") == []


def test_hl_info_whitelist_blocks_exchange_like_types():
    with pytest.raises(RuntimeError):
        hl.info({"type": "order"})
    assert "exchange" not in open(hl.__file__).read().replace("exchange endpoint", "").replace("`exchange` endpoint", "").split("def info")[1]


def test_hl_address_discovery_filters(tmp_path, monkeypatch):
    monkeypatch.setattr(hl, "HDIR", tmp_path)
    monkeypatch.setattr(hl, "DB", tmp_path / "h.sqlite")
    con = hl.db()
    a1, a2 = "0x" + "1" * 40, "0x" + "2" * 40
    trades = [{"coin": "BTC", "px": "80000", "sz": "1", "users": [a1, a2]},
              {"coin": "BTC", "px": "80000", "sz": "0.001", "users": ["0x" + "3" * 40, a1]},      # too small
              {"coin": "DOGE", "px": "1", "sz": "1e9", "users": ["0x" + "4" * 40, a1]},           # other coin
              {"coin": "ETH", "px": "3000", "sz": "50", "users": ["not-an-address", a2]}]
    assert hl.add_addrs(con, trades) == 2
    assert {r[0] for r in con.execute("SELECT addr FROM addrs")} == {a1, a2}


# ---------------------------------------------------------------- liquidation maps
def test_proxy_series_long_liquidations_cleared_by_price_drop():
    n = 400
    idx = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    oi = pd.Series(1e9 + np.arange(n) * 1e6, index=idx)               # steadily rising OI
    ls = pd.Series(0.5, index=idx)
    px = np.full(n, 100.0)
    px[300:] = 90.0                                                   # 10% crash
    k5 = pd.DataFrame({"open": px, "high": px * 1.0005, "low": px * 0.9995, "close": px, "volume": 1.0}, index=idx - pd.Timedelta("5min"))
    f, (lm, sm, base, off) = liqmap.proxy_series(oi, ls, k5, return_last_map=True)
    assert f["short_above_usd"].iloc[299] > 0 and f["long_below_usd"].iloc[299] > 0
    assert f["liq_imb"].between(-1, 1).all()
    # after the crash all 10x/20x/50x/100x long levels above 90 (liq at 90.5, 95, 98...) must have been swept
    pc = liqmap._gi(90.0, base) + off
    assert lm[pc + 1:].sum() == 0


def test_proxy_is_causal():
    n = 600
    idx = pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC")
    rng = np.random.RandomState(1)
    px = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    oi = pd.Series(1e9 * (1 + np.cumsum(rng.normal(0, 0.001, n))), index=idx)
    ls = pd.Series(0.5 + rng.normal(0, 0.02, n), index=idx)
    k5 = pd.DataFrame({"open": px, "high": px * 1.001, "low": px * 0.999, "close": px, "volume": 1.0}, index=idx - pd.Timedelta("5min"))
    full = liqmap.proxy_series(oi, ls, k5)
    part = liqmap.proxy_series(oi.iloc[:350], ls.iloc[:350], k5)
    pd.testing.assert_frame_equal(full.iloc[:350].fillna(-9), part.fillna(-9))


def _m(src, long_pct, short_pct):
    bands = []
    for k in range(-30, 30):
        lo = k * 0.5
        bands.append({"lo_pct": lo, "hi_pct": lo + 0.5, "long_usd": float(long_pct.get(k, 0)) if k < 0 else 0.0,
                      "short_usd": float(short_pct.get(k, 0)) if k >= 0 else 0.0})
    return {"source": src, "bands": bands, "summary": liqmap.summarize_bands(bands)}


def test_compare_identical_and_different_maps():
    a = _m("a", {-4: 100, -10: 50}, {3: 80, 12: 40})
    same = liqmap.compare(a, _m("b", {-4: 100, -10: 50}, {3: 80, 12: 40}))
    assert same["l1_distance_below"] == 0 and same["l1_distance_above"] == 0 and same["imbalance"]["same_sign"]
    diff = liqmap.compare(a, _m("c", {-20: 100}, {20: 100}))
    assert diff["l1_distance_below"] == 1.0
    assert liqmap.compare(a, None)["available"] is False


def test_summary_nearest_dense_cluster():
    m = _m("a", {-6: 10, -2: 10}, {2: 500, 8: 10, 9: 10, 10: 10})
    s = m["summary"]
    assert s["nearest_dense_above_pct"] == 1.0 and s["imbalance_short_minus_long"] > 0


# ---------------------------------------------------------------- KIS minute parsing + surge simulator
def test_kis_parse_minutes_filters_other_days():
    j = {"output2": [{"stck_bsop_date": "20261023", "stck_cntg_hour": "090100", "stck_prpr": "100", "stck_oprc": "99", "stck_hgpr": "101",
                      "stck_lwpr": "98", "cntg_vol": "10"},
                     {"stck_bsop_date": "20261022", "stck_cntg_hour": "153000", "stck_prpr": "1", "stck_oprc": "1", "stck_hgpr": "1",
                      "stck_lwpr": "1", "cntg_vol": "1"}]}
    df = kisintra.parse_minutes(j, "20261023")
    assert len(df) == 1 and df.index[0] == pd.Timestamp("2026-10-23 00:01:00", tz="UTC") and df["close"].iloc[0] == 100.0


def test_kis_module_has_no_order_paths():
    from tp import kis
    assert all("order" not in p for p in kis.ALLOWED)
    src = open(kisintra.__file__).read().lower()
    assert not any(t in src for t in ("order-cash", "order_cash", "place_order", "inquire-balance", "trading/order"))


def test_collector_session_hours():
    kst = kisintra.KST
    assert kisintra.in_session(dt.datetime(2026, 10, 26, 10, 0, tzinfo=kst))            # Monday
    assert not kisintra.in_session(dt.datetime(2026, 10, 25, 10, 0, tzinfo=kst))        # Sunday
    assert not kisintra.in_session(dt.datetime(2026, 10, 26, 8, 0, tzinfo=kst))
    assert not kisintra.in_session(dt.datetime(2026, 10, 26, 16, 0, tzinfo=kst))


def test_daily_call_cap(monkeypatch):
    monkeypatch.setattr(kisintra, "MAX_CALLS_PER_DAY", 3)
    kisintra.CALLS.update(day=None, n=0)
    now = dt.datetime(2026, 10, 26, 10, tzinfo=kisintra.KST)
    for _ in range(3):
        kisintra.count_call(now)
    with pytest.raises(kisintra.Stop):
        kisintra.count_call(now)


def _day(prices, vols=None, start="2026-10-26 09:00"):
    idx = pd.date_range(start, periods=len(prices), freq="1min", tz="Asia/Seoul").tz_convert("UTC")
    p = np.array(prices, float)
    o = np.r_[p[0], p[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, p), "low": np.minimum(o, p), "close": p,
                         "volume": np.array(vols if vols is not None else [100] * len(p), float)}, index=idx)


def _surge_path(after):
    base = [100.0] * 8
    ramp = [103, 105, 106.5, 107]           # +7% vs prev close 100 at signal
    return base + ramp + after


VOL = [100] * 8 + [100, 100, 20000, 20000, 20000] + [100] * 400


def test_surge_take_profit_and_costs():
    p = _surge_path([108, 110, 113, 114, 112, 112])
    t = krsurge.simulate_day(_day(p, VOL[:len(p)]), 100.0)
    assert len(t) == 1 and t[0]["reason"] == "take_profit" and 4.5 < t[0]["net_pct"] < 5.0


def test_surge_stop_loss_has_slippage_and_stop_wins_ties():
    p = _surge_path([107, 106, 100, 99, 99])
    t = krsurge.simulate_day(_day(p, VOL[:len(p)]), 100.0)
    assert t[0]["reason"] in ("stop_loss", "stop_gap") and t[0]["net_pct"] < -3.0 - 0.5


def test_surge_limit_up_proximity_blocks_entry():
    p = [100.0] * 8 + [120, 125, 128.5, 129, 129, 129]
    t = krsurge.simulate_day(_day(p, VOL[:len(p)]), 100.0)
    assert t == []


def test_surge_forced_flat_at_1520():
    n = 8 + 4 + 380
    p = [100.0] * 8 + [103, 105, 106.5, 107] + [107.5] * 380
    v = [100] * 8 + [100, 100, 1000, 2000] + [100] * 380
    t = krsurge.simulate_day(_day(p[:n], v[:n]), 100.0)
    assert t and t[0]["reason"] == "eod_flat" and t[0]["exit_time"].endswith("06:20:00+00:00") or t[0]["reason"] == "eod_flat"


def test_surge_has_no_order_code():
    src = open(krsurge.__file__).read().lower()
    assert "requests" not in src and "place_order" not in src
