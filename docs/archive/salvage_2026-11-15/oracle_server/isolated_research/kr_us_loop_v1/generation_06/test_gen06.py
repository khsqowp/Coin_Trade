import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

PATH = Path(__file__).with_name("run_gen06.py")
spec = importlib.util.spec_from_file_location("gen06", PATH)
gen06 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen06)


def test_beta_uses_only_paired_trailing_observations():
    market = pd.Series([0.01, -0.02, 0.03, 0.01, -0.01, 0.02])
    asset = pd.DataFrame({"A": 2 * market + 0.001, "B": -market + 0.002})
    asset.loc[2, "A"] = np.nan
    beta = gen06.rolling_market_beta(asset, market, window=4, min_periods=3)
    # At index 4, only the last four paired observations participate.
    paired = pd.concat([asset["A"].iloc[1:5], market.iloc[1:5]], axis=1).dropna()
    expected = paired.iloc[:, 0].cov(paired.iloc[:, 1]) / paired.iloc[:, 1].var()
    assert np.isclose(beta.iloc[4]["A"], expected)
    assert np.isclose(beta.iloc[4]["B"], -1.0)


def test_beta_waits_for_minimum_paired_observation_count():
    market = pd.Series([0.01, 0.02, -0.01, 0.03])
    asset = pd.DataFrame({"A": [0.02, np.nan, -0.02, 0.06]})
    beta = gen06.rolling_market_beta(asset, market, window=4, min_periods=4)
    assert np.isnan(beta.iloc[-1, 0])


def test_beta_requires_current_session_paired_return():
    market = pd.Series([0.01, 0.02, -0.01, 0.03])
    asset = pd.DataFrame({"A": [0.02, 0.04, -0.02, np.nan]})
    beta = gen06.rolling_market_beta(asset, market, window=4, min_periods=3)
    assert np.isnan(beta.iloc[-1, 0])


def test_kr_market_factor_excludes_the_evaluated_name():
    dates = pd.date_range("2020-01-01", periods=2)
    returns = pd.DataFrame({"A": [0.10, 0.20], "B": [0.00, 0.10], "C": [-0.10, 0.00]}, index=dates)
    eligible = pd.DataFrame(True, index=dates, columns=returns.columns)
    factors = gen06.market_factor_returns({"eligible": eligible}, returns, "KR")
    assert np.isclose(factors.loc[dates[0], "A"], -0.05)
    assert np.isclose(factors.loc[dates[0], "B"], 0.0)


def test_kr_beta_pairs_ineligible_stock_history_with_market_proxy():
    dates = pd.date_range("2020-01-01", periods=4)
    returns = pd.DataFrame({"A": [0.01, 0.02, 0.03, 0.04], "B": [0.02, 0.03, 0.04, 0.05]}, index=dates)
    eligible = pd.DataFrame({"A": [True, False, False, True], "B": [True, True, True, True]}, index=dates)
    factors = gen06.market_factor_returns({"eligible": eligible}, returns, "KR")
    counts = gen06.rolling_paired_count(returns, factors, window=4)
    assert factors.loc[dates[1], "A"] == returns.loc[dates[1], "B"]
    assert counts.loc[dates[3], "A"] == 4  # own historical return pairs even when A was not eligible


def test_month_end_target_selects_lowest_beta_and_emits_sparse_orders():
    dates = pd.date_range("2020-01-30", periods=4, freq="D")
    beta = pd.DataFrame([[0.2, 0.1, 0.3], [0.2, 0.1, 0.3], [0.4, 0.1, 0.2], [0.4, 0.1, 0.2]],
                        index=dates, columns=["A", "B", "C"])
    eligible = pd.DataFrame(True, index=dates, columns=beta.columns)
    target = gen06.month_end_targets(beta, eligible, np.array([1, 3]), 2)
    np.testing.assert_allclose(target[1], [0.5, 0.5, 0.0])
    assert np.isnan(target[2]).all()
    np.testing.assert_allclose(target[3], [0.0, 0.5, 0.5])


def test_month_end_targets_are_long_only_and_capped():
    beta = pd.DataFrame([[0.1, 0.2, 0.3]], columns=["A", "B", "C"])
    eligible = pd.DataFrame(True, columns=beta.columns, index=beta.index)
    target = gen06.month_end_targets(beta, eligible, np.array([0]), 2)
    assert np.isfinite(target).all()
    assert np.all(target >= 0)
    assert target.sum() <= 1.0
