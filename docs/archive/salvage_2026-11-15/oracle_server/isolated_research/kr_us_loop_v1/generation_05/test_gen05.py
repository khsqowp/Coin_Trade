import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

PATH = Path(__file__).with_name("run_gen05.py")
spec = importlib.util.spec_from_file_location("gen05", PATH)
gen05 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen05)


def test_max21_uses_only_trailing_returns_and_requires_18():
    idx = pd.date_range("2020-01-01", periods=23, freq="D")
    c = pd.DataFrame({"A": np.arange(100, 123, dtype=float), "B": np.arange(200, 223, dtype=float)}, index=idx)
    c.loc[idx[21], "A"] = np.nan
    c.loc[idx[22], "A"] = np.nan
    c.loc[idx[22], "B"] = 500
    signal = gen05.max21(c)
    assert np.isfinite(signal.iloc[20]["A"])
    assert np.isfinite(signal.iloc[21]["A"])
    assert signal.iloc[21]["B"] < 1.0
    assert np.isclose(signal.iloc[22]["B"], 500 / 221 - 1)  # current close is included, no future rows


def test_low_max_selects_lowest_score_with_stable_ticker_tie_break():
    scores = pd.DataFrame([[0.3, 0.1, 0.2]], columns=["C", "A", "B"])
    eligible = pd.DataFrame([[True, True, True]], columns=scores.columns)
    selected = gen05.select_low_max(scores, eligible, k=2)
    assert selected == ["A", "B"]


def test_targets_are_sparse_month_end_orders_only():
    dates = pd.to_datetime(["2020-01-30", "2020-01-31", "2020-02-03", "2020-02-28"])
    score = pd.DataFrame([[0.2, 0.1], [0.2, 0.1], [0.05, 0.4], [0.05, 0.4]], index=dates, columns=["A", "B"])
    eligible = pd.DataFrame(True, index=dates, columns=score.columns)
    weights = gen05.targets(score, eligible, np.array([1, 3]), 2)
    np.testing.assert_allclose(weights[1], [0.5, 0.5])
    assert np.isnan(weights[2]).all()
    np.testing.assert_allclose(weights[3], [0.5, 0.5])
    finite_rows = np.isfinite(weights).all(axis=1)
    assert np.all(weights[finite_rows] >= 0) and np.all(weights[finite_rows].sum(axis=1) <= 1.0 + 1e-12)


def test_simulator_does_not_rebalance_daily_between_month_end_orders():
    dates = pd.date_range("2020-01-30", periods=4, freq="D")
    columns = ["A", "B"]
    data = {"O": pd.DataFrame([[100, 100], [100, 100], [110, 100], [110, 100]], index=dates, columns=columns),
            "H": pd.DataFrame([[100, 100], [110, 100], [121, 100], [121, 100]], index=dates, columns=columns),
            "L": pd.DataFrame([[100, 100], [100, 100], [110, 100], [110, 100]], index=dates, columns=columns),
            "C": pd.DataFrame([[100, 100], [110, 100], [121, 100], [121, 100]], index=dates, columns=columns),
            "cal": dates, "fee_buy": 0.0, "fee_sell": 0.0}
    desired = np.full((4, 2), np.nan)
    desired[0] = [0.5, 0.5]
    desired[2] = [0.5, 0.5]
    _, turnover, exposure = gen05.simulate_monthly_strict(data, desired)
    assert turnover.iloc[1] > 0.0  # first target executes at next open
    assert turnover.iloc[2] == 0.0  # weights drift; no daily reset/rebalance
    assert turnover.iloc[3] > 0.0  # next sparse month-end order causes a rebalance
    assert np.allclose(exposure.iloc[1:], 1.0)
