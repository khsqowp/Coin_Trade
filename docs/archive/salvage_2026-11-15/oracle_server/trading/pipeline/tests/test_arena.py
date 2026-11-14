import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import arena, risk


def _px(n, kind):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = {"flat": np.full(n, 100.0), "crash": 100 * 0.995 ** np.arange(n), "up": 100 * 1.001 ** np.arange(n)}[kind]
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c), "low": np.minimum(o, c), "close": c, "volume": 1.0}, index=idx)


def _sig(px, v=1.0):
    return pd.Series(v, index=px.index)


def test_inference_cost_is_deducted_exactly():
    px = _px(25, "flat")
    ar = arena.Arena([arena.Policy("p", 0.1, 0.0, {"s": 1.0}), arena.Policy("q", 0.1, 0.0, {"s": 1.0})], px, signals={"s": _sig(px, 0.0)},
                     base_inference_cost=7.0, cost_multiplier=3.0, bars_per_epoch=24, review_every=99)
    res = ar.run()
    for a in res["accounts"]:
        assert a["equity"] == pytest.approx(arena.INITIAL - 21.0) and a["inference_cost_paid"] == pytest.approx(21.0)


def test_real_ledger_cost_overrides_multiplier():
    assert arena.epoch_cost(5, 2, real_cost=0.0123) == 0.0123 and arena.epoch_cost(5, 2) == 10


def test_trading_costs_and_pnl_accounting():
    px = _px(25, "up")
    ar = arena.Arena([arena.Policy("p", 0.1, 0.0, {"s": 1.0}), arena.Policy("q", 0.1, 0.0, {"s": 0.0})], px, signals={"s": _sig(px)},
                     base_inference_cost=0.0, bars_per_epoch=24, review_every=99)
    res = ar.run()
    a = next(x for x in res["accounts"] if x["policy"] == "p")
    # position 0.1 from bar 2 on; 1 entry cost, price compounding 0.1% per bar
    growth = np.prod([1 + 0.1 * 0.001 for _ in range(23)])
    expected = arena.INITIAL * (1 - 0.1 * (bt_cost())) * growth
    assert a["equity"] == pytest.approx(expected, rel=2e-3) and a["trading_cost_paid"] > 0


def bt_cost():
    from tp import bt
    return bt.FEE + bt.SLIP


def test_bankruptcy_deactivates_account_and_flattens():
    px = _px(24 * 40, "crash")
    big = arena.Policy("yolo", 0.25, 0.0, {"s": 1.0})
    ar = arena.Arena([big, arena.Policy("cash", 0.1, 0.0, {"s": 1.0})], px, signals={"s": _sig(px)}, base_inference_cost=3000.0,
                     bankruptcy_frac=0.2, review_every=999, bars_per_epoch=24)
    res = ar.run()
    dead = [a for a in res["accounts"] if not a["alive"]]
    assert dead and all(a["equity"] <= res["bankruptcy_line"] for a in dead)
    assert any(e["event"] == "bankrupt" for e in res["events"])
    acct = next(a for a in ar.accounts if not a.alive)
    assert acct.position == 0.0


def test_risk_engine_cap_cannot_be_exceeded_by_agent_request():
    px = _px(100, "up")
    greedy = arena.Policy("greedy", 0.9, 5.0, {"s": 1.0})          # asks for 90% of equity
    ar = arena.Arena([greedy, arena.Policy("tame", 0.1, 0.0, {"s": 1.0})], px, signals={"s": _sig(px)}, base_inference_cost=0.0, review_every=999)
    ar.run()
    g = next(a for a in ar.accounts if a.policy.name == "greedy")
    assert g.position <= risk.RiskConfig().max_position_pct + 1e-12
    assert any(e.get("event") == "order_rejected" and "MAX_POSITION_PCT" in e["reasons"] for e in ar.events)
    with pytest.raises(Exception):
        ar.cfg.max_position_pct = 1.0


def test_selection_retires_worst_and_clones_best():
    px = _px(24 * 12, "up")
    good = arena.Policy("good", 0.2, 0.0, {"s": 1.0})
    bad = arena.Policy("bad", 0.2, 0.0, {"s": 0.0})
    ar = arena.Arena([good, bad], px, signals={"s": _sig(px)}, base_inference_cost=1.0, review_every=5, bars_per_epoch=24)
    res = ar.run()
    ev = [e["event"] for e in res["events"]]
    assert "retired_worst" in ev and "cloned_best" in ev
    clones = [a for a in res["accounts"] if a["parent"]]
    assert clones and all(c["policy"] == "good" for c in clones)
    assert res["virtual_capital_created"] == arena.INITIAL * (2 + len(clones))


def test_pressure_metrics_recorded(tmp_path):
    px = make_ohlcv(24 * 30, seed=9)
    ar = arena.Arena([arena.Policy("a", 0.1, 3.0, {"s": 1.0}), arena.Policy("b", 0.1, 0.0, {"s": 1.0})], px,
                     signals={"s": pd.Series(1.0, index=px.index)}, base_inference_cost=20.0, review_every=999)
    res = ar.run()
    m = ar.metrics[0]
    assert {"pressure", "distance_to_bankruptcy", "avg_position_fraction", "position_changes"} <= set(m)
    assert "corr_pressure_size" in res["pressure_risk"]
    assert ar.save(tmp_path / "a.sqlite")


def test_agents_count_limits():
    px = _px(30, "flat")
    with pytest.raises(ValueError):
        arena.Arena([arena.Policy("a")], px)
    with pytest.raises(ValueError):
        arena.Arena([arena.Policy(str(i)) for i in range(5)], px)
