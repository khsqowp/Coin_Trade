import unittest
from datetime import datetime, timezone

from crypto import Bar, FundingEvent
from search_crypto import _funding_by_timestamp, _run_trial
from equities import Bar as EquityBar, Trade
from search_equities import _configs, _daily_trade_pnl, _max_drawdown, _weekly_bars


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

    def test_equity_daily_curve_includes_unrealized_interim_drawdown(self):
        bars = [EquityBar(1 * 86_400_000, 100, 101, 99, 100),
                EquityBar(2 * 86_400_000, 100, 101, 79, 80),
                EquityBar(3 * 86_400_000, 80, 111, 79, 110)]
        trade = Trade("C1", 0, 0, 2, 100, 110, "target", .1, 20, .098)
        marks = _daily_trade_pnl(bars, trade, "US")
        self.assertAlmostEqual(sum(marks.values()), trade.net_return)
        self.assertLess(marks[2], -.19)

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

    def test_crypto_runner_preserves_exact_funding_timestamp(self):
        bars = [Bar(1000, 100, 101, 99, 100, 10),
                Bar(2000, 100, 101, 99, 100, 10)]
        event = FundingEvent(2000, 0.001, 100)
        self.assertEqual(_funding_by_timestamp(bars, {2000: event}), {2000: event})

    def test_crypto_runner_preserves_funding_inside_bar_interval(self):
        bars = [Bar(1000, 100, 101, 99, 100, 10),
                Bar(2000, 100, 101, 99, 100, 10)]
        event = FundingEvent(1500, 0.001, 100)
        self.assertEqual(_funding_by_timestamp(bars, {1500: event}), {1500: event})

    def test_crypto_runner_excludes_only_missing_mark_symbols_and_enforces_30_valid(self):
        bars = [Bar(0, 100, 101, 99, 100, 10), Bar(900_000, 100, 101, 99, 100, 10)]
        missing = FundingEvent(0, 0.001, None)
        valid = [(f"S{i}", bars, {}, 0) for i in range(30)]
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            [*valid, ("MISSING", bars, {0: missing}, 0)], {},
        )
        self.assertEqual(result["symbols"], 30)
        self.assertEqual(result["symbols_excluded_missing_funding_marks"], 1)
        self.assertEqual(result["status"], "completed")
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            valid[:29], {},
        )
        self.assertEqual(result["status"], "unscorable")

    def test_crypto_runner_excludes_symbols_with_funding_cadence_gaps(self):
        bars = [Bar(0, 100, 101, 99, 100, 10), Bar(900_000, 100, 101, 99, 100, 10)]
        gap = FundingEvent(0, 0.0, None, coverage_gap=True)
        valid = [(f"S{i}", bars, {}, 0) for i in range(30)]
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            [*valid, ("GAP", bars, {0: gap}, 0)], {},
        )
        self.assertEqual(result["symbols_excluded_funding_gap"], 1)
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
