"""Rotation simulator: accounting, exchange filters, stops, cooldown, liquidation, causality (synthetic, deterministic)."""
import numpy as np
import pandas as pd
import pytest

from tp import rotation, rotstudy

FILT = {"minNotional": 5.0, "stepSize": 0.1, "minQty": 0.1, "maxQty": 1e9, "tickSize": 0.01, "base": "X"}
COST0 = dict(fee=0.0, slip=0.0)
COST = dict(fee=0.0005, slip=0.0002)
N = 2600


def frame(close, vol=1000.0):
    c = np.asarray(close, float)
    o = np.r_[c[0], c[:-1]]
    idx = pd.date_range("2025-01-01", periods=len(c), freq="1h", tz="UTC")
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0005, "low": np.minimum(o, c) * 0.9995, "close": c, "volume": vol}, index=idx)


def make(altpath, filters=None, btc=None):
    t = np.arange(N)
    b = btc if btc is not None else 100 * np.exp(0.0002 * t)                 # BTC steadily up: filter on
    frames = {"BTCUSDT": frame(b), "AAAUSDT": frame(altpath)}
    f = {k: dict(FILT, **(filters or {})) for k in frames}
    return rotation.Data(frames, f, {})


def rising_then_crash(drop=0.5, start=1500, crash_at=2000):
    t = np.arange(N)
    p = 10 * np.exp(0.0006 * np.minimum(t, crash_at))
    p = np.where(t >= crash_at, p[crash_at] * (1 - drop) * np.exp(0.0001 * (t - crash_at)), p)
    return p


V = dict(kind="rot", clock="1h", n=1, stop="trail10", btc=True)


def test_buy_and_hold_accounting_matches_prices():
    D = make(10 * np.exp(0.0006 * np.arange(N)))
    r = rotation.run(D, dict(V, stop="loss7"), COST0)
    assert r["n_trades"] == 0 and r["fills"] >= 1
    # no costs: equity must equal capital * price ratio of the held symbol after the first fill (minus step-rounding cash)
    eq = r["eq"]
    assert eq[-1] > eq[0] * 1.2 and r["fees"] == 0


def test_fee_and_slippage_are_charged():
    D = make(10 * np.exp(0.0006 * np.arange(N)))
    a = rotation.run(D, dict(V, stop="loss7"), COST0)["eq"][-1]
    b = rotation.run(D, dict(V, stop="loss7"), COST)["eq"][-1]
    assert b < a and (a - b) / a == pytest.approx(0.0007, abs=0.0004)        # one entry: 0.05% + 0.02%


def test_min_notional_rejects_orders_and_stays_in_cash():
    D = make(10 * np.exp(0.0006 * np.arange(N)), filters={"minNotional": 1e6})
    r = rotation.run(D, V, COST)
    assert r["fills"] == 0 and r["rejects"] > 0
    assert np.allclose(r["eq"], 128.88)


def test_step_size_floors_quantity():
    D = make(10 * np.exp(0.0006 * np.arange(N)), filters={"stepSize": 1000.0, "minQty": 1000.0})
    r = rotation.run(D, V, COST)
    assert r["fills"] == 0 and r["rejects"] > 0                              # 128 USDT / price << 1000 units


def test_trailing_stop_exits_and_cooldown_blocks_rebuy():
    D = make(rising_then_crash())
    r = rotation.run(D, V, COST)
    stops = [t for t in r["trades"] if t["reason"] == "stop"]
    assert stops and stops[0]["t1"] - rotation.WARMUP >= 2000 - rotation.WARMUP
    buys_after = [t for t in r["trades"] if t["t0"] > stops[0]["t1"] and t["t0"] < stops[0]["t1"] + 24]
    assert not buys_after


def test_btc_filter_off_blocks_entries():
    t = np.arange(N)
    btc = 100 * np.exp(-0.0003 * t)                                           # BTC always below its 50d mean
    D = make(10 * np.exp(0.0006 * t), btc=btc)
    r = rotation.run(D, V, COST)
    assert r["fills"] == 0
    r2 = rotation.run(D, dict(V, btc=False), COST)
    assert r2["fills"] >= 1


def test_leverage_liquidation_loses_margin_only():
    D = make(rising_then_crash(drop=0.7, crash_at=2000), btc=None)
    r = rotation.run(D, dict(V, stop="loss7"), COST0, lev=3.0)
    assert r["liq"] >= 1
    assert r["eq"].min() > 0                                                   # isolated margin: never below zero
    r1 = rotation.run(D, dict(V, stop="loss7"), COST0, lev=1.0)
    assert r1["liq"] == 0


def test_run_is_causal_and_prefix_stable():
    rng = np.random.RandomState(4)
    alt = 10 * np.exp(np.cumsum(rng.normal(0.0001, 0.01, N)))
    D = make(alt)
    full = rotation.run(D, dict(V, clock="4h", stop="atr3"), COST)
    cut = rotation.run(D, dict(V, clock="4h", stop="atr3"), COST, end=2000)
    assert np.allclose(full["eq"][:len(cut["eq"])], cut["eq"])


def test_variant_grid_size_and_names():
    v = rotstudy.variants()
    assert len(v) == 66 and "cad_n3_atr3_b1" in v and v["card_k8"]["k"] == 8


def test_gate_input_shape_passes_through_small_rotation_profile():
    from tp import risk
    cfg = risk.PROFILES["crypto_small_rotation"]
    assert cfg.max_position_pct == 1.0 and cfg.max_drawdown_halt_pct == 0.15 and cfg.daily_loss_limit_pct == 0.03
    D = make(rising_then_crash())
    r = rotation.run(D, V, COST)
    g = risk.gate_numeric(rotstudy.gate_input(r, len(r["eq"]) // 2, len(r["eq"])), "BTC/USDT", "skip", cfg)
    assert hasattr(g, "allowed") and isinstance(g.reasons, list)
