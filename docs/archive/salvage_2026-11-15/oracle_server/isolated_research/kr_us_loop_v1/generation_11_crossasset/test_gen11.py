import unittest

import numpy as np
import pandas as pd

from run_gen11 import (
    build_monthly_targets,
    calculate_metrics,
    drift_weights,
    rank_bottom,
    simulate_open_to_open,
    validate_ohlc_frame,
)


class Gen11RuleTests(unittest.TestCase):
    def test_bottom_three_uses_lowest_return_and_symbol_tie_break(self):
        returns = {"XLY": -0.2, "XLB": -0.2, "XLK": -0.2, "XLE": 0.1}
        self.assertEqual(rank_bottom(returns, slots=3), {"XLB": 1 / 3, "XLK": 1 / 3, "XLY": 1 / 3})

    def test_signal_is_scheduled_at_next_observed_open_and_latest_partial_month_is_skipped(self):
        symbols = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
        dates = pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-02", "2020-03-31", "2020-04-01"])
        prices = pd.DataFrame(index=dates, columns=symbols, dtype=float)
        prices.loc["2020-01-31"] = 100.0
        prices.loc["2020-02-28"] = [90, 91, 92, 100, 101, 102, 103, 104, 105]
        prices.loc["2020-03-02"] = prices.loc["2020-02-28"]
        prices.loc["2020-03-31"] = [80, 82, 84, 100, 101, 102, 103, 104, 105]
        prices.loc["2020-04-01"] = prices.loc["2020-03-31"]

        targets, diagnostics = build_monthly_targets(prices, slots=3)

        self.assertEqual(list(targets), [pd.Timestamp("2020-03-02")])
        self.assertEqual(set(targets[pd.Timestamp("2020-03-02")]), {"XLB", "XLE", "XLF"})
        self.assertAlmostEqual(sum(targets[pd.Timestamp("2020-03-02")].values()), 1.0)
        self.assertEqual(diagnostics["terminal_censored"], 1)

    def test_monthly_signal_does_not_use_current_or_future_price(self):
        symbols = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
        dates = pd.to_datetime(["2021-01-29", "2021-02-26", "2021-03-01", "2021-03-31", "2021-04-01"])
        prices = pd.DataFrame(100.0, index=dates, columns=symbols)
        prices.loc["2021-02-26"] = [90, 91, 92, 100, 101, 102, 103, 104, 105]
        prices.loc["2021-03-31"] = [99, 99, 99, 100, 101, 102, 103, 104, 105]
        targets, _ = build_monthly_targets(prices, slots=3)
        self.assertEqual(set(targets[pd.Timestamp("2021-03-01")]), {"XLB", "XLE", "XLF"})

    def test_weight_drift_reflects_relative_asset_returns(self):
        drifted = drift_weights({"A": 0.5, "B": 0.5}, {"A": 0.10, "B": 0.0})
        self.assertAlmostEqual(drifted["A"], 0.55 / 1.05)
        self.assertAlmostEqual(drifted["B"], 0.50 / 1.05)
        self.assertAlmostEqual(sum(drifted.values()), 1.0)

    def test_turnover_cost_and_terminal_liquidation_are_in_daily_returns(self):
        dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
        opens = pd.DataFrame({"A": [100.0, 110.0, 110.0], "B": [100.0, 100.0, 110.0]}, index=dates)
        targets = {dates[0]: {"A": 0.5, "B": 0.5}}
        net_returns, diagnostics = simulate_open_to_open(opens, targets, cost_rate=0.001)
        # The two assets each finish 10% higher and the portfolio reweights through drift.
        expected_gross = 1.10
        expected_net = (1 - 0.001) * expected_gross * (1 - 0.001)
        self.assertAlmostEqual(float(np.prod(1 + net_returns)), expected_net)
        self.assertEqual(diagnostics["rebalance_count"], 1)
        self.assertAlmostEqual(diagnostics["turnover"], 1.0)
        self.assertAlmostEqual(diagnostics["terminal_liquidation_turnover"], 1.0)

    def test_invalid_ohlc_fails_closed(self):
        good = pd.DataFrame(
            {"open": [10.0], "high": [11.0], "low": [9.0], "close": [10.0], "adjclose": [10.0]},
            index=pd.to_datetime(["2020-01-02"]),
        )
        validate_ohlc_frame(good, "A")
        bad = good.copy()
        bad.loc[0, "low"] = 10.5
        with self.assertRaises(ValueError):
            validate_ohlc_frame(bad, "A")

    def test_raw_valid_bar_is_not_rejected_for_adjusted_float_rounding(self):
        rounded = pd.DataFrame(
            {"open": [11.59375], "high": [11.609375], "low": [11.5], "close": [11.609375], "adjclose": [6.321516]},
            index=pd.to_datetime(["1999-01-11"]),
        )
        validate_ohlc_frame(rounded, "XLB")

    def test_metric_definition_is_stable_and_finite(self):
        dates = pd.date_range("2020-01-02", periods=4, freq="B")
        returns = pd.Series([0.01, -0.005, 0.002, 0.0], index=dates)
        result = calculate_metrics(returns)
        self.assertAlmostEqual(result["sharpe"], returns.mean() / returns.std(ddof=1) * np.sqrt(252))
        self.assertAlmostEqual(result["cagr"], np.prod(1 + returns) ** (252 / len(returns)) - 1)
        self.assertTrue(np.isfinite(result["cagr"]))


if __name__ == "__main__":
    unittest.main()
