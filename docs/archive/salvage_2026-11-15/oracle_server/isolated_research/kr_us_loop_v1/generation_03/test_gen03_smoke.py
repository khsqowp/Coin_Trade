"""Synthetic mechanics/causality checks; no market data or network access."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

RUNNER = Path(__file__).with_name("run_gen03.py")
spec = importlib.util.spec_from_file_location("run_gen03", RUNNER)
g = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(g)


def panel() -> dict:
    idx = pd.bdate_range("2018-01-01", periods=520)
    t = np.arange(len(idx), dtype=float)
    base = np.column_stack([
        100 * np.exp(0.0005 * t + 0.03 * np.sin(t / 11)),
        80 * np.exp(0.0002 * t + 0.04 * np.sin(t / 7)),
        120 * np.exp(-0.0001 * t + 0.05 * np.sin(t / 17)),
    ])
    c = pd.DataFrame(base, index=idx, columns=["AAA", "BBB", "CCC"])
    o = c * (1 + 0.002 * np.sin(t[:, None] / 3))
    h = pd.DataFrame(np.maximum(o.to_numpy(), c.to_numpy()) * 1.01, index=idx, columns=c.columns)
    l = pd.DataFrame(np.minimum(o.to_numpy(), c.to_numpy()) * 0.99, index=idx, columns=c.columns)
    return {"market": "US", "cal": idx, "O": o, "H": h, "L": l, "C": c,
            "V": c * 1000, "eligible": pd.DataFrame(True, index=idx, columns=c.columns),
            "benchmark": pd.Series(1 + t / 10000, index=idx), "k": 2,
            "fee_buy": .001, "fee_sell": .001}


def main() -> None:
    d = panel()
    days = g.g1.month_ends(d["cal"])
    names = ("FRAMA16_SLOPE5", "VORTEX14_SMA100", "ICHIMOKU_CURRENT_CLOUD",
             "DCTC_GAP_INTRADAY63", "VOL_COMPRESSION_RELEASE55")
    cut = pd.Timestamp(d["cal"][390])
    for name in names:
        w = g.candidate_targets(d, name, days)
        assert w.shape == d["C"].shape and np.isfinite(w).all(), f"{name}: nonfinite weights"
        assert (w >= 0).all() and (w.sum(axis=1) <= 1.00001).all(), f"{name}: constraint failure"
        r, tv, ex = g.simulate_strict(d, w)
        assert np.isfinite(r).all() and np.isfinite(tv).all() and np.isfinite(ex).all(), f"{name}: simulator failure"
        changed = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in d.items()}
        future = changed["C"].index > cut
        rng = np.random.default_rng(20261106)
        factor = pd.DataFrame(rng.uniform(.6, 1.7, size=changed["C"].loc[future].shape),
                              index=changed["C"].index[future], columns=changed["C"].columns)
        for key in ("O", "H", "L", "C"):
            changed[key].loc[future] *= factor
        wc = g.candidate_targets(changed, name, days)
        np.testing.assert_allclose(w[d["cal"] <= cut], wc[d["cal"] <= cut], atol=0, rtol=0,
                                   err_msg=f"{name}: future perturbation affected past target")

    frama_weights = g.candidate_targets(d, "FRAMA16_SLOPE5", days)
    assert (frama_weights.sum(axis=1) > 0).any(), "FRAMA must produce a nonzero portfolio on the synthetic persistent-trend panel"
    gap_data = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in d.items()}
    gap_at = 250
    for key in ("O", "H", "L", "C"):
        gap_data[key].iloc[gap_at, :] = np.nan
    recovered = g.candidate_targets(gap_data, "FRAMA16_SLOPE5", days)
    assert (recovered[gap_at + 220:].sum(axis=1) > 0).any(), "FRAMA must recover after its post-gap warm-up"

    bad_bar = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in d.items()}
    bad_bar["O"].iloc[300, 0] = np.nan
    held = np.zeros(d["C"].shape, dtype=np.float32)
    held[299:, 0] = 1.0
    try:
        g.simulate_strict(bad_bar, held)
    except ValueError as exc:
        assert "strict execution data gap" in str(exc)
    else:
        raise AssertionError("strict simulator must reject a held security with a missing bar")

    entry_bad_close = {k: v.copy() if isinstance(v, pd.DataFrame) else v for k, v in d.items()}
    entry_bad_close["C"].iloc[300, 0] = np.nan
    entry_target = np.zeros(d["C"].shape, dtype=np.float32)
    entry_target[299, 0] = 1.0  # next open entry would occur on row 300
    try:
        g.simulate_strict(entry_bad_close, entry_target)
    except ValueError as exc:
        assert "complete executable OHLC bar" in str(exc)
    else:
        raise AssertionError("strict simulator must reject a new entry whose close is missing")

    entry = pd.DataFrame(False, index=d["cal"], columns=["X"])
    exit_ = entry.copy()
    entry.iloc[days[0] + 1, 0] = True
    assert not g.monthly_stateful(entry, exit_, days).iloc[days[1], 0]
    print("PASS: five candidate paths, portfolio bounds, next-open simulation, randomized future perturbation, month-end-only state")


if __name__ == "__main__":
    main()
