import unittest

import pandas as pd

from search_wonyotti_flow_v1 import aggregate_hourly_bars, build_trades, signed_hour_flow, wilson


class WonyottiFlowTests(unittest.TestCase):
    def test_flow_is_utc_hourly_signed_and_zero_is_preserved(self):
        events = [
            (pd.Timestamp("2020-01-01T00:01:00Z"), 7),
            (pd.Timestamp("2020-01-01T00:58:00Z"), -2),
            (pd.Timestamp("2020-01-01T01:00:00Z"), -5),
        ]
        got = signed_hour_flow(events)
        self.assertEqual(got[pd.Timestamp("2020-01-01T00:00:00Z")], 5)
        self.assertEqual(got[pd.Timestamp("2020-01-01T01:00:00Z")], -5)

    def test_hourly_bar_requires_complete_minute_sequence(self):
        times = pd.date_range("2020-01-01T00:00:00Z", periods=60, freq="min")
        frame = pd.DataFrame({"open_time": times.as_unit("ns").view("int64") // 1_000_000, "open": range(100, 160), "high": range(101, 161), "low": range(99, 159), "close": range(100, 160)})
        bars = aggregate_hourly_bars(frame)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[times[0].floor("h")]["open"], 100)
        self.assertEqual(bars[times[0].floor("h")]["close"], 159)
        self.assertEqual(aggregate_hourly_bars(frame.iloc[:-1]), {})

    def test_signal_enters_next_hour_not_same_hour_and_applies_cost(self):
        h0 = pd.Timestamp("2020-01-01T00:00:00Z")
        bars = {h0 + pd.Timedelta(hours=1): {"open": 100.0, "high": 103.0, "low": 99.0, "close": 102.0}}
        trades = build_trades({h0: 10}, bars, {})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["entry_hour"], "2020-01-01T01:00:00+00:00")
        self.assertAlmostEqual(trades[0]["net_return"], 0.02 - 0.0012)

    def test_wilson_returns_95_percent_interval(self):
        lo, hi = wilson(80, 100)
        self.assertLess(lo, 0.8)
        self.assertGreater(hi, 0.8)


if __name__ == "__main__":
    unittest.main()
