"""Synthetic causality and execution tests; never reads market files."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

RUNNER = Path(__file__).with_name("run_gen04.py")
spec = importlib.util.spec_from_file_location("run_gen04", RUNNER)
g = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(g)


def panel() -> dict:
    idx = pd.bdate_range("2018-01-01", periods=520)
    t = np.arange(len(idx), dtype=float)
    close = np.column_stack([
        100 * np.exp(0.0007 * t + 0.02 * np.sin(t / 13)),
        80 * np.exp(0.0002 * t + 0.03 * np.sin(t / 7)),
        120 * np.exp(-0.0001 * t + 0.04 * np.sin(t / 17)),
    ])
    c = pd.DataFrame(close, index=idx, columns=["AAA", "BBB", "CCC"])
    o = c * (1 + 0.002 * np.sin(t[:, None] / 3))
    h = pd.DataFrame(np.maximum(o.to_numpy(), close) * 1.01, index=idx, columns=c.columns)
    l = pd.DataFrame(np.minimum(o.to_numpy(), close) * 0.99, index=idx, columns=c.columns)
    return {"market": "US", "cal": idx, "O": o, "H": h, "L": l, "C": c,
            "eligible": pd.DataFrame(True, index=idx, columns=c.columns), "k": 2,
            "fee_buy": .001, "fee_sell": .001}


def test_tema_formula_and_segment_reset():
    x = pd.Series([1., 2., 3., np.nan, 10., 11., 12.])
    e1, e2, e3, tema = g.tema_series(x, 2)
    assert e1.iloc[0] == 1 and e1.iloc[1] == 1 + (2 / 3)
    assert e1.iloc[3] != e1.iloc[3] and e1.iloc[4] == 10
    np.testing.assert_allclose(tema.dropna(), (3 * e1 - 3 * e2 + e3).dropna())


def test_clv_events_have_five_sessions_no_same_symbol_overlap():
    d = panel()
    d["k"] = 1
    event = pd.DataFrame(False, index=d["cal"], columns=d["C"].columns)
    rank = pd.DataFrame(0.0, index=d["cal"], columns=d["C"].columns)
    event.iloc[100, 0] = True
    event.iloc[100, 1] = True  # same-day overflow must be discarded, not queued
    event.iloc[101, 1] = True  # full portfolio; must not enter late when AAA expires
    rank.iloc[100, 0], rank.iloc[100, 1], rank.iloc[101, 1] = .9, .8, 1.0
    w = g.clv_event_targets(d, event, rank)
    # Signal at close 100 is represented in target rows 100..104, filled on 101..105.
    assert np.all(w[100:105, 0] == 1.0)
    assert np.all(w[:, 1] == 0), "a rejected signal must not be queued for a late, short-duration entry"
    assert np.all(w.sum(axis=1) <= 1.000001)


def test_strict_simulator_rejects_inconsistent_held_high_low():
    d = panel()
    weights = np.zeros(d["C"].shape, dtype=np.float32)
    weights[100:, 0] = 1.0
    d["H"].iloc[102, 0] = d["O"].iloc[102, 0] * .5
    try:
        g.simulate_gen04_strict(d, weights)
    except ValueError as exc:
        assert "OHLC integrity" in str(exc)
    else:
        raise AssertionError("strict simulation must reject an invalid high/low for a held position")


def test_strict_simulator_ignores_missing_unheld_symbol_but_stays_finite():
    d = panel()
    weights = np.zeros(d["C"].shape, dtype=np.float32)
    weights[100:, 0] = 1.0
    for key in ("O", "H", "L", "C"):
        d[key].iloc[101, 2] = np.nan  # CCC is not held and has no target weight.
    returns, turnover, exposure = g.simulate_gen04_strict(d, weights)
    assert np.isfinite(returns).all() and np.isfinite(turnover).all() and np.isfinite(exposure).all()


def test_candidates_finite_bounded_and_no_future_leakage():
    d = panel()
    months = g.g1.month_ends(d["cal"])
    for name in g.NAMES:
        w = g.candidate_targets(d, name, months)
        assert w.shape == d["C"].shape and np.isfinite(w).all()
        assert (w >= 0).all() and (w.sum(axis=1) <= 1.00001).all()
        returns, turnover, exposure = g.simulate_gen04_strict(d, w)
        assert np.isfinite(returns).all() and np.isfinite(turnover).all() and np.isfinite(exposure).all()
        cut = d["cal"][350]
        altered = {k: (v.copy() if isinstance(v, (pd.DataFrame, pd.Series)) else v) for k, v in d.items()}
        factor = pd.DataFrame(0.7 + np.random.default_rng(7).random(d["C"].loc[d["cal"] > cut].shape),
                              index=d["C"].index[d["cal"] > cut], columns=d["C"].columns)
        for key in ("O", "H", "L", "C"):
            altered[key].loc[factor.index] *= factor
        w2 = g.candidate_targets(altered, name, months)
        np.testing.assert_allclose(w[d["cal"] <= cut], w2[d["cal"] <= cut], atol=0, rtol=0)


if __name__ == "__main__":
    test_tema_formula_and_segment_reset()
    test_clv_events_have_five_sessions_no_same_symbol_overlap()
    test_strict_simulator_rejects_inconsistent_held_high_low()
    test_strict_simulator_ignores_missing_unheld_symbol_but_stays_finite()
    test_candidates_finite_bounded_and_no_future_leakage()
    print("PASS: TEMA recurrence, missing-data reset, CLV fixed holding, portfolio bounds, strict execution, future perturbation")
