"""Synthetic feature/simulator checks for Generation 02; no network or market data."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

RUNNER = Path(__file__).with_name("run_gen02.py")
spec = importlib.util.spec_from_file_location("run_gen02", RUNNER)
g = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(g)


def panel() -> dict:
    idx = pd.bdate_range("2019-01-01", periods=420)
    t = np.arange(len(idx), dtype=float)
    values = [100 * np.exp(0.0005 * t + 0.02 * np.sin(t / 13)),
              80 * np.exp(0.0002 * t + 0.03 * np.sin(t / 9)),
              120 * np.exp(-0.0001 * t + 0.04 * np.sin(t / 15))]
    C = pd.DataFrame(np.column_stack(values), index=idx, columns=["AAA", "BBB", "CCC"])
    return {"market": "US", "cal": idx, "O": C * .999, "H": C * 1.01, "L": C * .99,
            "C": C, "V": C * 1000, "eligible": pd.DataFrame(True, index=idx, columns=C.columns),
            "benchmark": pd.Series(1 + t / 10000, index=idx), "k": 2, "fee_buy": .001, "fee_sell": .001}


def main() -> None:
    data = panel()
    month_days = g.g1.month_ends(data["cal"])
    names = ("TS63_KENDALL", "OLS_MULTI_3OF4", "SIGN_FLIP63", "KALMAN_DRIFT63",
             "EHLERS_SSF40_SLOPE5", "BREADTH_60_40_BASKET")
    cutoff = pd.Timestamp(data["cal"][300])
    for name in names:
        w = g.candidate_targets(data, name, month_days)
        assert w.shape == data["C"].shape and np.isfinite(w).all(), name
        assert (w >= 0).all() and (w.sum(axis=1) <= 1.00001).all(), name
        r, turnover, exposure = g.g1.simulate(data, w)
        assert np.isfinite(r).all() and np.isfinite(turnover).all() and np.isfinite(exposure).all(), name
        changed = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in data.items()}
        future_idx = changed["C"].index > cutoff
        rng = np.random.default_rng(20261106)
        factor = pd.DataFrame(rng.uniform(.55, 1.8, size=changed["C"].loc[future_idx].shape),
                              index=changed["C"].index[future_idx], columns=changed["C"].columns)
        for key in ("C", "O", "H", "L"):
            changed[key].loc[future_idx] *= factor
        wc = g.candidate_targets(changed, name, month_days)
        np.testing.assert_allclose(w[data["cal"] <= cutoff], wc[data["cal"] <= cutoff], atol=0, rtol=0,
                                   err_msg=f"{name} depends on future prices")
    idx = data["cal"]
    days = g.g1.month_ends(idx)
    entry = pd.DataFrame(False, index=idx, columns=["X"])
    exit_ = entry.copy()
    entry.iloc[days[0] + 1, 0] = True  # deliberately between registered decision dates
    daily_state = g.g1.stateful(entry, exit_)
    monthly_state = g.monthly_stateful(entry, exit_, days)
    assert daily_state.iloc[days[1], 0] and not monthly_state.iloc[days[1], 0]
    print("PASS: six candidate paths, constraints, simulation, and no post-cutoff lookahead")


if __name__ == "__main__":
    main()
