from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from run_gen07 import monthly_nr, abnormal_nr, month_end_targets, completed_month_ends


class Gen07SignalTests(unittest.TestCase):
    def test_monthly_nr_uses_exact_positive_overnight_negative_daytime_condition(self):
        idx = pd.date_range("2024-01-02", periods=16, freq="B")
        daytime = pd.DataFrame({"A": [-0.01] * 8 + [0.01] * 8}, index=idx)
        overnight = pd.DataFrame({"A": [0.01] * 8 + [-0.01] * 8}, index=idx)
        result, counts = monthly_nr(daytime, overnight)
        key = pd.Period("2024-01", freq="M")
        self.assertEqual(counts.loc[key, "A"], 16)
        self.assertEqual(result.loc[key, "A"], 0.5)

    def test_monthly_nr_rejects_month_with_fewer_than_15_valid_sessions(self):
        idx = pd.date_range("2024-01-02", periods=16, freq="B")
        daytime = pd.DataFrame({"A": [-0.01] * 16}, index=idx)
        overnight = pd.DataFrame({"A": [0.01] * 16}, index=idx)
        daytime.iloc[:2, 0] = np.nan
        nr, counts = monthly_nr(daytime, overnight)
        key = pd.Period("2024-01", freq="M")
        self.assertEqual(counts.loc[key, "A"], 14)
        self.assertTrue(np.isnan(nr.loc[key, "A"]))

    def test_abnormal_nr_denominator_is_trailing_only(self):
        months = pd.period_range("2023-01", periods=14, freq="M")
        nr = pd.DataFrame({"A": [0.1] * 12 + [0.8, 0.9]}, index=months)
        score = abnormal_nr(nr)
        self.assertAlmostEqual(score.loc[months[12], "A"], 8.0)
        self.assertAlmostEqual(score.loc[months[13], "A"], 0.9 / ((11 * 0.1 + 0.8) / 12))

    def test_abnormal_nr_needs_ten_prior_values_and_positive_mean(self):
        months = pd.period_range("2023-01", periods=13, freq="M")
        nr = pd.DataFrame({"A": [0.2] * 9 + [np.nan, 0.2, np.nan, 0.8]}, index=months)
        score = abnormal_nr(nr)
        self.assertTrue(np.isnan(score.loc[months[9], "A"]))
        self.assertAlmostEqual(score.loc[months[12], "A"], 4.0)
        nr.loc[months[0:12], "A"] = 0.0
        self.assertTrue(np.isnan(abnormal_nr(nr).loc[months[12], "A"]))

    def test_targets_require_coverage_and_break_ties_by_ticker(self):
        idx = pd.date_range("2024-01-02", periods=1)
        cols = ["C", "A", "B", "D"]
        score = pd.DataFrame([[1.0, 2.0, 2.0, 0.0]], index=idx, columns=cols)
        eligible = pd.DataFrame([[True] * 4], index=idx, columns=cols)
        # ceil(10% * 4) = 1; the tied score picks A, independent of input order.
        weights, coverage = month_end_targets(score, eligible, np.array([0]), coverage_min=0.75,
                                               full_member_counts=np.array([4]))
        self.assertEqual(coverage[0]["coverage"], 1.0)
        self.assertEqual(weights[0, cols.index("A")], 1.0)
        # Two finite scores out of four fail an 85% coverage gate and become cash.
        score.iloc[0, 2:] = np.nan
        weights, coverage = month_end_targets(score, eligible, np.array([0]), coverage_min=0.85,
                                               full_member_counts=np.array([4]))
        self.assertEqual(coverage[0]["coverage"], 0.5)
        self.assertEqual(weights[0].sum(), 0.0)

    def test_coverage_denominator_includes_missing_pit_members(self):
        idx = pd.date_range("2024-01-31", periods=1)
        score = pd.DataFrame([[1.0, 2.0]], index=idx, columns=["A", "B"])
        eligible = pd.DataFrame([[True, True]], index=idx, columns=["A", "B"])
        weights, audit = month_end_targets(score, eligible, np.array([0]),
                                           coverage_min=0.85, full_member_counts=np.array([4]))
        self.assertEqual(audit[0]["coverage"], 0.5)
        self.assertEqual(audit[0]["available_eligible_count"], 2)
        self.assertEqual(audit[0]["eligible_count"], 4)
        self.assertEqual(weights[0].sum(), 0.0)

    def test_last_incomplete_calendar_month_is_not_a_decision(self):
        idx = pd.bdate_range("2024-01-01", "2024-02-20")
        month_ends = completed_month_ends(idx)
        dates = [idx[i].date().isoformat() for i in month_ends]
        self.assertEqual(dates, ["2024-01-31"])


if __name__ == "__main__":
    unittest.main()
