import unittest
from datetime import datetime, timedelta, timezone

from search_wonyotti_flow_bitmex_2018_2019_v1 import (
    build_trades,
    funding_avoid,
    inverse_return,
    signals_for_hour,
)


UTC = timezone.utc


class WonyottiBitmexFlowTests(unittest.TestCase):
    def test_flow_signal_uses_only_closed_lookback_hours(self):
        hour = datetime(2018, 3, 5, 10, tzinfo=UTC)
        flow = {hour: 10, hour.replace(hour=9): -2, hour.replace(hour=11): -900}
        self.assertEqual(signals_for_hour(flow, hour, 2), (8, 12))

    def test_flow_prefix_result_is_unchanged_by_future_flow(self):
        hour = datetime(2018, 3, 5, 10, tzinfo=UTC)
        prefix = {hour: 8, hour.replace(hour=9): 2}
        before = signals_for_hour(prefix, hour, 2)
        prefix[hour.replace(hour=11)] = -100000
        self.assertEqual(signals_for_hour(prefix, hour, 2), before)

    def test_funding_exclusion_covers_each_settlement_and_neighbors(self):
        day = datetime(2018, 3, 5, tzinfo=UTC)
        for hour in (3, 4, 5, 11, 12, 13, 19, 20, 21):
            self.assertTrue(funding_avoid(day.replace(hour=hour)), hour)
        for hour in (2, 6, 10, 14, 18, 22, 23, 0):
            self.assertFalse(funding_avoid(day.replace(hour=hour)), hour)

    def test_inverse_long_and_short_have_correct_direction(self):
        long = inverse_return(1, 100.0, 110.0, 0.0, 0.0)
        short = inverse_return(-1, 100.0, 90.0, 0.0, 0.0)
        self.assertAlmostEqual(long["gross_return"], 1 - 100 / 110)
        self.assertAlmostEqual(short["gross_return"], 100 / 90 - 1)
        self.assertTrue(long["direction_correct"])
        self.assertTrue(short["direction_correct"])

    def test_costs_reduce_return_and_allocation_caps_trade_loss(self):
        result = inverse_return(1, 100.0, 50.0, 0.001, 0.0002)
        self.assertLess(result["net_return"], result["gross_return"])
        self.assertEqual(result["account_return"], -0.10)

    def test_trade_enters_next_bar_and_ignores_later_prices(self):
        signal = datetime(2018, 3, 5, 1, tzinfo=UTC)
        next_hour = datetime(2018, 3, 5, 2, tzinfo=UTC)
        later = datetime(2018, 3, 5, 3, tzinfo=UTC)
        flow = {signal: 100}
        bars = {
            signal: {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5},
            next_hour: {"open": 101.0, "high": 104.0, "low": 100.0, "close": 103.0},
        }
        first, _ = build_trades(flow, bars, 1, 0.0, signal, later)
        self.assertEqual(first[0]["entry"], 101.0)
        bars[later] = {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}
        second, _ = build_trades(flow, bars, 1, 0.0, signal, later)
        self.assertEqual(first, second)

    def test_zero_flow_and_threshold_are_not_signals(self):
        signal = datetime(2018, 3, 5, 1, tzinfo=UTC)
        next_hour = datetime(2018, 3, 5, 2, tzinfo=UTC)
        end = next_hour
        bars = {signal: {"open": 1, "high": 1, "low": 1, "close": 1},
                next_hour: {"open": 1, "high": 1, "low": 1, "close": 1}}
        trades, stats = build_trades({signal: 0}, bars, 1, 0.0, signal, end)
        self.assertEqual(trades, [])
        self.assertEqual(stats["no_flow"], 1)
        previous = signal - timedelta(hours=1)
        bars[previous] = {"open": 100, "high": 102, "low": 99, "close": 101}
        trades, stats = build_trades({signal: 9, previous: -7}, bars, 2, 0.25, signal, end)
        self.assertEqual(trades, [])
        self.assertEqual(stats["threshold_filtered"], 1)

    def test_missing_market_bar_in_signal_lookback_skips_signal(self):
        signal = datetime(2018, 3, 5, 2, tzinfo=UTC)
        next_hour = datetime(2018, 3, 5, 3, tzinfo=UTC)
        bars = {signal: {"open": 100, "high": 102, "low": 99, "close": 101},
                next_hour: {"open": 101, "high": 103, "low": 100, "close": 102}}
        trades, stats = build_trades({signal: 10}, bars, 2, 0.0, signal, next_hour)
        self.assertEqual(trades, [])
        self.assertEqual(stats["invalid_price_window"], 1)


if __name__ == "__main__":
    unittest.main()
