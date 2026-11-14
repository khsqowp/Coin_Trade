from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from run_gen08 import (residual_skew_at, completed_month_ends, month_end_targets,
                       validate_membership_intervals)


class Gen08Tests(unittest.TestCase):
    def test_residual_skew_requires_minimum_paired_rows(self):
        rng = np.random.default_rng(18)
        market = rng.normal(0.0002, 0.01, 252)
        stock = 0.0003 + 1.2 * market + rng.normal(0.0, 0.005, 252)
        dates = pd.date_range("2024-01-01", periods=252, freq="B")
        frame = pd.DataFrame({"A": stock}, index=dates)
        market_series = pd.Series(market, index=dates)
        frame.iloc[:53, 0] = np.nan  # 199 paired observations
        self.assertTrue(np.isnan(residual_skew_at(frame, market_series, 251, min_obs=200)[0]))
        frame.iloc[52, 0] = stock[52]  # exactly 200 paired observations
        self.assertTrue(np.isfinite(residual_skew_at(frame, market_series, 251, min_obs=200)[0]))

    def test_residual_skew_is_causal_at_decision_row(self):
        rng = np.random.default_rng(7)
        dates = pd.date_range("2023-01-01", periods=300, freq="B")
        market = pd.Series(rng.normal(0.0, 0.01, len(dates)), index=dates)
        stock = pd.DataFrame({"A": 0.4 * market.to_numpy() + rng.normal(0.0, 0.02, len(dates))}, index=dates)
        baseline = residual_skew_at(stock, market, 260, window=252, min_obs=200)
        changed = stock.copy()
        changed.iloc[261:, 0] = 1.0  # arbitrary future shock cannot change the earlier score
        market_changed = market.copy()
        market_changed.iloc[261:] = -1.0
        actual = residual_skew_at(changed, market_changed, 260, window=252, min_obs=200)
        self.assertEqual(baseline[0], actual[0])

    def test_residual_skew_matches_independent_ols_population_moment(self):
        rng = np.random.default_rng(91)
        x = rng.normal(0.0001, 0.012, 252)
        noise = rng.lognormal(mean=-7.0, sigma=0.7, size=252) - np.exp(-7.0 + 0.7**2 / 2)
        y = 0.0004 + 0.85 * x + noise
        idx = pd.date_range("2024-01-01", periods=252, freq="B")
        actual = residual_skew_at(pd.DataFrame({"A": y}, index=idx),
                                  pd.Series(x, index=idx), 251)[0]
        design = np.column_stack([np.ones(len(x)), x])
        residual = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
        expected = np.mean((residual - residual.mean())**3) / np.mean((residual - residual.mean())**2)**1.5
        self.assertAlmostEqual(actual, expected, places=10)

    def test_constant_residuals_have_no_defined_skew(self):
        idx = pd.date_range("2024-01-01", periods=252, freq="B")
        market = pd.Series(np.linspace(-0.01, 0.01, 252), index=idx)
        stock = pd.DataFrame({"A": 0.001 + 1.5 * market.to_numpy()}, index=idx)
        self.assertTrue(np.isnan(residual_skew_at(stock, market, 251, min_obs=200)[0]))

    def test_targets_use_full_pit_denominator_and_deterministic_ties(self):
        idx = pd.DatetimeIndex(["2024-01-31"])
        cols = ["B", "A", "C"]
        scores = pd.DataFrame([[0.1, 0.1, 0.5]], index=idx, columns=cols)
        members = pd.DataFrame([[True, True, True]], index=idx, columns=cols)
        weights, audit = month_end_targets(scores, members, np.array([0]),
                                           full_member_counts=np.array([4]), min_coverage=0.7, k=2)
        self.assertEqual(audit[0]["coverage"], 0.75)
        self.assertEqual(audit[0]["selected"], ["A", "B"])
        self.assertAlmostEqual(weights[0].sum(), 1.0)
        weights, audit = month_end_targets(scores, members, np.array([0]),
                                           full_member_counts=np.array([4]), min_coverage=0.85, k=2)
        self.assertEqual(audit[0]["coverage"], 0.75)
        self.assertEqual(weights[0].sum(), 0.0)

    def test_trailing_incomplete_month_is_not_a_decision(self):
        idx = pd.bdate_range("2024-01-01", "2024-02-20")
        self.assertEqual([idx[i].date().isoformat() for i in completed_month_ends(idx)], ["2024-01-31"])

    def test_overlapping_pit_membership_intervals_fail_closed(self):
        intervals = pd.DataFrame({"ticker": ["A", "A"],
                                  "start_date": pd.to_datetime(["2020-01-01", "2020-06-01"]),
                                  "end_date": pd.to_datetime(["2020-12-31", "2021-06-01"])})
        with self.assertRaisesRegex(ValueError, "overlapping"):
            validate_membership_intervals(intervals)


if __name__ == "__main__":
    unittest.main()
