import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib import splits, costs, eventstudy as es, portfolio as pf, baseline as bl, data, report, features


def synth_panel(T=60, N=4, seed=0, drift=0.0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=T)
    c = 100 * np.cumprod(1 + drift + 0.01 * rng.standard_normal((T, N)), axis=0)
    o = c * (1 + 0.002 * rng.standard_normal((T, N)))
    h, l = np.maximum(o, c) * 1.005, np.minimum(o, c) * 0.995
    v = np.full((T, N), 1e7)
    return data.Panel(dates, [f"{i:06d}" for i in range(N)], list("abcd")[:N], np.array(["KOSPI"] * N, dtype=object), o, h, l, c, v)


def test_kr_costs():
    b = costs.KRCost("B"); a = costs.KRCost("A")
    assert b.roundtrip(1e11) == pytest.approx(0.0020 + 0.0003 + 0.0010)
    assert a.roundtrip(1e11) == pytest.approx(0.0020 + 0.0010)
    assert b.roundtrip(1e9) == pytest.approx(0.0020 + 0.0003 + 0.0020)       # illiquid slippage
    assert b.with_(mult=2).roundtrip(1e11) == pytest.approx(2 * b.roundtrip(1e11))
    assert b.with_(sell_tax=0.0018).roundtrip(1e11) < b.roundtrip(1e11)
    assert a.fixed_monthly_return(1.3e6) == pytest.approx(5900 / 1.3e6) and b.fixed_monthly_return(1.3e6) == 0
    assert a.excess_commission(2e8) == pytest.approx(1e8 * 0.00015)
    assert a.excess_commission(5e7) == 0


def test_us_costs():
    u = costs.USCost()
    assert u.roundtrip() == pytest.approx(0.002 + 0.0000278 + 0.001 + 0.001)
    assert u.with_(mult=2).roundtrip() == pytest.approx(2 * u.roundtrip())


def test_holdout_guard(tmp_path):
    splits.relock_holdout()
    d = pd.bdate_range("2024-01-01", "2026-11-12")
    df = pd.DataFrame({"x": 1.0}, index=d)
    assert splits.dev_view(df).index.max() < splits.HOLDOUT_START
    with pytest.raises(splits.HoldoutLockedError):
        splits.holdout_view(df)
    with pytest.raises(splits.HoldoutLockedError):
        splits.guard_dev(d, "t")
    splits.guard_dev(d[d < splits.HOLDOUT_START])
    log = tmp_path / "u.log"
    line = splits.unlock_holdout("unit test", log)
    assert "UNLOCK" in log.read_text() and line[:4] == "2026" or line[:2] == "20"
    assert splits.holdout_view(df).index.min() >= splits.HOLDOUT_START
    splits.guard_dev(d)
    splits.relock_holdout()
    with pytest.raises(ValueError):
        splits.unlock_holdout("  ")


def test_fwd_returns_alignment():
    p = synth_panel()
    g = es.fwd_returns(p, ("open", 1), ("close", 3))
    assert g[5, 2] == pytest.approx(p.close[8, 2] / p.open[6, 2] - 1)
    assert np.isnan(g[-1, 0])
    with pytest.raises(ValueError):
        es.fwd_returns(p, ("close", 2), ("open", 2))


def test_events_and_tstat():
    p = synth_panel(T=40)
    mask = np.zeros(p.close.shape, bool); mask[5, :] = True; mask[10, 1] = True
    ev = es.make_events(p, mask, ("open", 1), ("close", 2), cost_frac=0.001)
    assert len(ev) == 5 and np.allclose(ev.cost, 0.001)
    assert ev.dates[0] == p.dates[6] and ev.xdates[0] == p.dates[7]
    m, t = es.cluster_t(np.array([0.01] * 50 + [0.012] * 50), np.arange(100))
    assert m == pytest.approx(0.011) and t > 5
    s = es.summarize(ev, p.dates[8])
    assert s["n"] == 5 and s["break_even"] == pytest.approx(ev.gross.mean())


def test_make_events_blocks_locked_holdout():
    splits.relock_holdout()
    dates = pd.bdate_range("2024-10-01", periods=60)
    T = len(dates)
    c = np.full((T, 1), 100.0)
    p = data.Panel(dates, ["a"], ["a"], np.array(["K"], dtype=object), c, c, c, c, c)
    mask = np.zeros((T, 1), bool); mask[-5, 0] = True
    with pytest.raises(splits.HoldoutLockedError):
        es.make_events(p, mask, ("open", 1), ("close", 2))


def test_bh():
    q = es.bh_qvalues([0.001, 0.01, 0.04, 0.5])
    assert q[0] == pytest.approx(0.004) and all(0 <= x <= 1 for x in q) and q[3] == pytest.approx(0.5)
    assert q == sorted(q)


def test_portfolio_max_n_first_come():
    p = synth_panel(T=40)
    mask = np.zeros(p.close.shape, bool); mask[5, :] = True; mask[6, :] = True   # 8 signals, 3-day holds
    ev = es.make_events(p, mask, ("open", 1), ("close", 3), cost_frac=0.0)
    acc = pf.select_trades(ev, N=2, seed=1)
    assert acc.sum() == 2 and (ev.ti[acc] == 5).all()                   # first-come: bar-5 signals fill slots
    assert pf.max_concurrent(ev.subset(acc)) <= 2
    r = pf.simulate(ev, p.dates, N=2, capital=1e6)
    assert r["max_conc"] <= 2 and r["n"] == 2 and r["turnover_month"] > 0


def test_portfolio_reuses_slot_after_exit():
    p = synth_panel(T=40, N=1)
    mask = np.zeros(p.close.shape, bool); mask[5, 0] = True; mask[8, 0] = True
    ev = es.make_events(p, mask, ("open", 1), ("close", 2))             # occupies open6..close7 ; open9..close10
    assert pf.select_trades(ev, N=1).sum() == 2


def test_baseline_no_edge_vs_edge():
    p = synth_panel(T=300, N=30, seed=3)
    net = es.fwd_returns(p, ("open", 1), ("close", 3)) - 0.001
    elig = np.ones_like(net, bool)
    rng = np.random.default_rng(5)
    ti = rng.integers(10, 280, 200)
    # no edge: events random -> actual mean percentile near the middle
    cols = rng.integers(0, 30, 200)
    act = np.nanmean(net[ti, cols])
    r = bl.random_entry_baseline(net, elig, ti, act, draws=400, seed=1)
    assert 0.02 < r["pct"] < 0.98
    # planted edge: pick the best stock each date
    best = np.nanargmax(net[ti], axis=1)
    r2 = bl.random_entry_baseline(net, elig, ti, np.nanmean(net[ti, best]), draws=400, seed=1)
    assert r2["pct"] >= 0.99


def test_loader_cache(tmp_path):
    cache = tmp_path / "c"; (cache / "kr").mkdir(parents=True)
    d = pd.bdate_range("2023-01-02", "2026-01-30")
    df = pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0}, index=d)
    df.to_parquet(cache / "kr" / "000001.parquet")
    splits.relock_holdout()
    r = data.load_ohlcv("kr", "000001", cache=cache, legacy=[], download=False)
    assert r.index.max() < splits.HOLDOUT_START
    with pytest.raises(splits.HoldoutLockedError):
        data.load_ohlcv("kr", "000001", cache=cache, legacy=[], download=False, include_holdout=True)
    assert data.load_ohlcv("kr", "999999", cache=cache, legacy=[], download=False) is None


def test_panel_masks_and_features():
    d = pd.bdate_range("2021-01-04", periods=30)
    f = pd.DataFrame({"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.0, "volume": 1e6}, index=d)
    f.iloc[3, f.columns.get_loc("volume")] = 0
    p = data.build_panel({"A": f}, d)
    assert np.isnan(p.close[3, 0]) and p.value20.shape == p.close.shape
    assert features.ibs(p.high, p.low, p.close)[5, 0] == pytest.approx(0.5)
    c = np.array([[5.], [4.], [3.], [4.], [3.], [2.], [1.]])
    assert features.down_streak(c)[:, 0].tolist() == [0, 1, 2, 0, 1, 2, 3]
    r = features.rsi(np.array([[1.], [2.], [3.], [4.], [5.]]), 2)
    assert r[-1, 0] > 90


def test_report(tmp_path):
    led = tmp_path / "L.md"
    report.append_ledger(report.ledger_row("KR-00", "KR", "x", "S1", 0.001, 3.2, 1.1, verdict="noise"), led)
    txt = led.read_text()
    assert "| id | market | idea | stage |" in txt and "KR-00" in txt
