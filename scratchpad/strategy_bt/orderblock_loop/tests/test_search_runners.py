import unittest
from datetime import datetime, timezone

from crypto import Bar, FundingEvent
from search_crypto import _funding_by_bar_index
from search_equities import _configs, _max_drawdown, _weekly_bars


class SearchRunnerTests(unittest.TestCase):
    def test_equity_round_one_search_grid_matches_preregistered_count(self):
        configs = _configs()
        self.assertEqual(len(configs), 68)
        self.assertEqual(sum(config["family"] == "C1" for config in configs), 32)
        self.assertEqual(sum(config["family"] == "C2" for config in configs), 4)
        self.assertEqual(sum(config["family"] == "C3" for config in configs), 16)
        self.assertEqual(sum(config["family"] == "C4" for config in configs), 16)
        self.assertEqual({config["family"] for config in configs}, {"C1", "C2", "C3", "C4"})

    def test_equity_mdd_aggregates_simultaneous_portfolio_exits(self):
        result = _max_drawdown([(1, 0.10), (1, -0.10), (2, -0.10)])
        self.assertAlmostEqual(result, 10.0)

    def test_equity_weekly_bars_require_full_weekdays_and_mark_close_time(self):
        monday = int(datetime(2025, 10, 6, tzinfo=timezone.utc).timestamp() * 1000)
        complete = [Bar(monday + day * 86_400_000, 10, 11, 9, 10 + day, 1)
                    for day in range(5)]
        short_holiday_week = [Bar(monday + 7 * 86_400_000 + day * 86_400_000,
                                  10, 11, 9, 10, 1)
                              for day in (0, 1, 3, 4)]
        weekly = _weekly_bars(complete + short_holiday_week)
        self.assertEqual(len(weekly), 1)
        self.assertEqual(datetime.fromtimestamp(weekly[0].timestamp / 1000, timezone.utc),
                         datetime(2025, 10, 10, 23, 59, tzinfo=timezone.utc))

    def test_crypto_runner_maps_funding_timestamps_to_bar_indices(self):
        bars = [Bar(1000, 100, 101, 99, 100, 10),
                Bar(2000, 100, 101, 99, 100, 10)]
        event = FundingEvent(2000, 0.001, 100)
        self.assertEqual(_funding_by_bar_index(bars, {2000: event}), {1: event})

    def test_crypto_runner_rejects_unaligned_funding_within_bar_range(self):
        bars = [Bar(1000, 100, 101, 99, 100, 10),
                Bar(2000, 100, 101, 99, 100, 10)]
        event = FundingEvent(1500, 0.001, 100)
        with self.assertRaisesRegex(ValueError, "do not align to candle opens"):
            _funding_by_bar_index(bars, {1500: event})


if __name__ == "__main__":
    unittest.main()
