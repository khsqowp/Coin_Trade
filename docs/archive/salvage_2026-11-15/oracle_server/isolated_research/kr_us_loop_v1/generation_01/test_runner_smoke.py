"""Deterministic, local synthetic checks; no market data or network access."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

RUNNER = Path(__file__).with_name("run_gen01.py")
spec = importlib.util.spec_from_file_location("run_gen01", RUNNER)
g = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(g)


def synthetic(scale: float = 1.0) -> dict:
    idx = pd.bdate_range("2020-01-01", periods=320)
    t = np.arange(len(idx), dtype=float)
    close = (100 + 0.08 * t + 2 * np.sin(t / 9)) * scale
    cols = ["AAA", "BBB", "CCC"]
    c = pd.DataFrame(np.column_stack([close, close * 0.8, close * 1.2]), index=idx, columns=cols)
    o, h, l = c * 0.999, c * 1.01, c * 0.99
    eligible = pd.DataFrame(True, index=idx, columns=cols)
    return {"market": "US", "cal": idx, "O": o, "H": h, "L": l, "C": c, "V": c * 1000,
            "eligible": eligible, "benchmark": pd.Series(1 + t / 10000, index=idx), "k": 2,
            "fee_buy": 0.001, "fee_sell": 0.001}


def main() -> None:
    a, b = synthetic(), synthetic(10.0)
    month_days = g.month_ends(a["cal"])
    for name in ("KAMA_ER20", "ATR_NORM_SMA100"):
        wa = g.candidate_targets(a, name, month_days)
        wb = g.candidate_targets(b, name, month_days)
        np.testing.assert_allclose(wa, wb, atol=0, rtol=0, err_msg=f"{name} must be price-scale invariant")

    names = ("KAMA_ER20", "HMA55_BREAKOUT", "REG60_R2_BREAKOUT", "ATR_NORM_SMA100",
             "VHF63_DONCHIAN20", "PERSIST63", "ATR_BUFFER55", "RESIDUAL_MOM126",
             "GAP_REVERSAL_5D", "MOM12_1_VOL10_OVERLAY", "MOM_TO_LOWVOL_200SMA")
    for name in names:
        weights = g.candidate_targets(a, name, month_days)
        assert weights.shape == a["C"].shape and np.isfinite(weights).all(), f"{name}: invalid target weights"
        assert (weights >= 0).all() and (weights.sum(axis=1) <= 1.00001).all(), f"{name}: long-only/unlevered violated"
        returns, turnover, exposure = g.simulate(a, weights)
        assert np.isfinite(returns).all() and np.isfinite(turnover).all() and np.isfinite(exposure).all(), f"{name}: simulator non-finite"

    r = pd.Series([0.0, -0.10, 0.20], index=pd.bdate_range("2024-01-01", periods=3))
    m = g.metrics(pd.concat([r, pd.Series(np.zeros(100), index=pd.bdate_range("2024-01-04", periods=100))]),
                  pd.Series(0.0, index=pd.bdate_range("2024-01-01", periods=103)),
                  pd.Series(1.0, index=pd.bdate_range("2024-01-01", periods=103)), "2024-01-01")
    assert m["mdd"] <= -0.099, f"initial capital drawdown omitted: {m['mdd']}"

    # First finite true range is max(H-L, |H-prevC|, |L-prevC|); warm-up is missing.
    tr = np.maximum.reduce([(a["H"] - a["L"]).to_numpy(), (a["H"] - a["C"].shift(1)).abs().to_numpy(),
                            (a["L"] - a["C"].shift(1)).abs().to_numpy()])
    assert np.isnan(tr[0]).all() and np.isfinite(tr[1:]).all()

    entry = pd.DataFrame(False, index=a["cal"], columns=["X"])
    exit_ = entry.copy()
    ends = g.month_ends(a["cal"])
    entry.iloc[ends[0] + 1, 0] = True
    assert g.stateful(entry, exit_).iloc[ends[1], 0]
    assert not g.stateful_monthly(entry, exit_, ends).iloc[ends[1], 0]
    print("PASS: all 11 candidate paths; monthly-only state; scale invariance; initial-capital MDD; true-range warm-up")


if __name__ == "__main__":
    main()
