import unittest

import pandas as pd

from data_quality import SymbolQualityError, filter_equity_bars


def bars(count=100):
    return pd.DataFrame({
        "open_time": range(count), "open": [10.0] * count,
        "high": [11.0] * count, "low": [9.0] * count,
        "close": [10.5] * count, "volume": [100.0] * count,
    })


class EquityDataQualityTests(unittest.TestCase):
    def test_drops_single_nonpositive_ohlc_row(self):
        frame = bars()
        frame.loc[3, "close"] = 0
        filtered, stats = filter_equity_bars(frame, "TEST")
        self.assertEqual(len(filtered), 99)
        self.assertEqual(stats["invalid_ohlc"], 1)
        self.assertNotIn(3, filtered["open_time"].tolist())

    def test_drops_invalid_range_and_close_outside_range(self):
        frame = bars()
        frame.loc[1, "high"] = 8
        frame.loc[4, "close"] = 12
        filtered, stats = filter_equity_bars(frame, "TEST")
        self.assertEqual(len(filtered), 98)
        self.assertEqual(stats["invalid_ohlc"], 2)

    def test_drops_nonfinite_and_open_outside_range(self):
        frame = bars()
        frame.loc[1, "open"] = float("inf")
        frame.loc[4, "open"] = 12
        filtered, stats = filter_equity_bars(frame, "TEST")
        self.assertEqual(len(filtered), 98)
        self.assertEqual(stats["invalid_ohlc"], 2)

    def test_rejects_symbol_when_bad_rows_are_concentrated(self):
        frame = bars()
        frame.loc[2:4, "close"] = 0
        with self.assertRaises(SymbolQualityError):
            filter_equity_bars(frame, "BAD")

    def test_drops_five_day_zero_volume_halt_run(self):
        frame = bars()
        frame.loc[1:5, "volume"] = 0
        filtered, stats = filter_equity_bars(frame, "HALTED")
        self.assertEqual(filtered["open_time"].tolist(), [0, *range(6, 100)])
        self.assertEqual(stats["halt_bars"], 5)

    def test_keeps_isolated_zero_volume_rows(self):
        frame = bars()
        frame.loc[2, "volume"] = 0
        filtered, stats = filter_equity_bars(frame, "THIN")
        self.assertEqual(len(filtered), 100)
        self.assertEqual(stats["halt_bars"], 0)


if __name__ == "__main__":
    unittest.main()
