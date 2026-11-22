import unittest
from datetime import date, datetime, timezone

from portfolio import daily_pearson_correlation, equal_weight_daily_returns


class PortfolioTests(unittest.TestCase):
    def test_equal_weight_uses_fixed_initial_capital_and_explicit_flat_days(self):
        rows = {
            "2020-01-02": {"AAA": 0.02, "BBB": 0.0},
            "2020-01-03": {"AAA": -0.01, "BBB": 0.03},
        }
        result = equal_weight_daily_returns(["AAA", "BBB"], rows)
        self.assertEqual([date for date, _ in result], ["2020-01-02", "2020-01-03"])
        for _, value in result:
            self.assertAlmostEqual(value, 0.01)

    def test_symbol_order_and_date_input_order_do_not_change_results(self):
        rows = {
            2: {"BBB": 0.03, "AAA": -0.01},
            1: {"AAA": 0.02, "BBB": 0.0},
        }
        result = equal_weight_daily_returns(["AAA", "BBB"], rows)
        self.assertEqual([date for date, _ in result], [1, 2])
        for _, value in result:
            self.assertAlmostEqual(value, 0.01)

    def test_missing_or_extra_symbols_are_rejected_not_assumed_flat(self):
        with self.assertRaises(ValueError):
            equal_weight_daily_returns(["AAA", "BBB"], {1: {"AAA": 0.0}})
        with self.assertRaises(ValueError):
            equal_weight_daily_returns(["AAA"], {1: {"AAA": 0.0, "CCC": 0.0}})

    def test_non_finite_values_and_duplicate_universe_are_rejected(self):
        with self.assertRaises(ValueError):
            equal_weight_daily_returns(["AAA"], {1: {"AAA": float("nan")}})
        with self.assertRaises(ValueError):
            equal_weight_daily_returns(["AAA", "AAA"], {})

    def test_daily_correlation_aligns_different_market_calendars(self):
        dates_a = ["2026-01-02", "2026-01-05", "2026-01-06"]
        dates_b = ["2026-01-02", "2026-01-06", "2026-01-07"]
        correlation = daily_pearson_correlation(
            {dates_a[0]: 0.01, dates_a[1]: -0.01, dates_a[2]: 0.02}, dates_a,
            {dates_b[0]: 0.02, dates_b[1]: 0.04, dates_b[2]: 0.0}, dates_b,
        )
        self.assertAlmostEqual(correlation, 0.9438798074485389)

    def test_daily_correlation_normalizes_utc_dates_and_rejects_mixed_aliases(self):
        correlation = daily_pearson_correlation(
            {"2026-01-02": 0.01, "2026-01-05": 0.02},
            [date(2026, 1, 2), date(2026, 1, 5)],
            {datetime(2026, 1, 2, tzinfo=timezone.utc): 0.02,
             datetime(2026, 1, 5, tzinfo=timezone.utc): 0.03},
            ["2026-01-02", "2026-01-05"],
        )
        self.assertAlmostEqual(correlation, 1.0)
        with self.assertRaisesRegex(ValueError, "duplicate UTC dates"):
            daily_pearson_correlation(
                {"2026-01-02": 0.01},
                ["2026-01-02", date(2026, 1, 2)],
                {"2026-01-02": 0.03}, ["2026-01-02"],
            )

    def test_daily_correlation_rejects_missing_open_session_and_bad_values(self):
        with self.assertRaises(ValueError):
            daily_pearson_correlation({1: 0.1}, [1, 2], {1: 0.2, 2: 0.3}, [1, 2])
        with self.assertRaises(ValueError):
            daily_pearson_correlation({1: float("nan")}, [1], {1: 0.2}, [1])


if __name__ == "__main__":
    unittest.main()
