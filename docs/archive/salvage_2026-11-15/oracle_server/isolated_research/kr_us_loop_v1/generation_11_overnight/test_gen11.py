import unittest

import numpy as np
import pandas as pd

from run_gen11 import adjusted_prices, simulate_overnight, validate_market_frame


def frame(opens, highs=None, lows=None, closes=None, adjcloses=None):
    n = len(opens)
    closes = closes or [100.0] * n
    highs = highs or [max(o, c) + 1.0 for o, c in zip(opens, closes)]
    lows = lows or [min(o, c) - 1.0 for o, c in zip(opens, closes)]
    adjcloses = adjcloses or closes
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes,
         "adjclose": adjcloses},
        index=pd.date_range("2020-01-02", periods=n, freq="B"),
    )


class Gen11Tests(unittest.TestCase):
    def test_validation_requires_sorted_unique_dates_and_valid_ohlc(self):
        good = frame([100, 101, 102])
        self.assertEqual(len(validate_market_frame(good)), 3)
        with self.assertRaisesRegex(ValueError, "unique and increasing"):
            validate_market_frame(good.iloc[::-1])
        duplicate = good.copy()
        duplicate.index = pd.DatetimeIndex(["2020-01-02", "2020-01-03", "2020-01-03"])
        with self.assertRaisesRegex(ValueError, "unique and increasing"):
            validate_market_frame(duplicate)
        invalid = good.copy()
        invalid.loc[invalid.index[1], "high"] = 99
        with self.assertRaisesRegex(ValueError, "OHLC bounds"):
            validate_market_frame(invalid)

    def test_adjusted_open_and_close_are_consistent_with_vendor_factor(self):
        raw = frame([100, 49], highs=[101, 50], lows=[99, 48], closes=[100, 50], adjcloses=[100, 49])
        prices = adjusted_prices(raw)
        self.assertAlmostEqual(prices.loc[raw.index[1], "open"], 48.02)
        self.assertAlmostEqual(prices.loc[raw.index[1], "close"], 49.0)

    def test_dividend_adjustment_is_included_in_overnight_factor(self):
        # A $2 distribution on the ex-date is reflected by a .98 factor on the
        # prior close. Raw prior close=100 and ex-date open=99 imply +1.0204%
        # total-return-adjusted overnight performance, not the raw -1% price gap.
        raw = frame([100, 99], highs=[101, 100], lows=[99, 98], closes=[100, 99], adjcloses=[98, 99])
        result = simulate_overnight(raw, fee_per_side=0.0)
        self.assertAlmostEqual(result["overnight_gross_returns"].iloc[0], 0.0)
        self.assertAlmostEqual(result["overnight_gross_returns"].iloc[1], 99 / 98 - 1)

    def test_overnight_series_uses_two_costs_per_night_and_no_daytime_return(self):
        raw = frame([100, 120, 90], highs=[101, 121, 131], lows=[99, 99, 89], closes=[100, 100, 130])
        result = simulate_overnight(raw, fee_per_side=0.001)
        # Overnight: close100->open120; close100->open90. Costs applied per side.
        self.assertAlmostEqual(result["strategy_returns"].iloc[1], 1.2 * 0.999**2 - 1)
        self.assertAlmostEqual(result["strategy_returns"].iloc[2], (90 / 100) * 0.999**2 - 1)
        self.assertEqual(result["strategy_returns"].iloc[0], 0.0)

    def test_matched_benchmark_endpoint_is_final_open(self):
        raw = frame([100, 110, 90], highs=[111, 111, 101], lows=[99, 99, 89], closes=[105, 100, 95])
        result = simulate_overnight(raw, fee_per_side=0.0)
        expected = (100 / 105) * (90 / 100)  # close0 -> close1 -> final open2
        self.assertAlmostEqual(np.prod(1 + result["benchmark_returns"].iloc[1:]), expected)

    def test_benchmark_costs_only_at_matching_start_and_end_boundaries(self):
        raw = frame([100, 101, 102, 103], highs=[101, 102, 103, 104], lows=[99, 100, 101, 102],
                    closes=[100, 101, 102, 103])
        result = simulate_overnight(raw, fee_per_side=0.001)
        self.assertEqual(result["strategy_cost_sides"].tolist(), [0, 2, 2, 2])
        self.assertEqual(result["benchmark_cost_sides"].tolist(), [0, 1, 0, 1])
        gross_matched_benchmark = (102 / 100) * (103 / 102)  # close0->close2->open3
        expected_net = gross_matched_benchmark * 0.999**2
        self.assertAlmostEqual(np.prod(1 + result["benchmark_returns"].iloc[1:]), expected_net)

    def test_invalid_fee_or_adjustment_fails_closed(self):
        raw = frame([100, 101, 102])
        with self.assertRaisesRegex(ValueError, "fee"):
            simulate_overnight(raw, fee_per_side=-0.01)
        invalid = raw.copy()
        invalid.loc[invalid.index[1], "adjclose"] = np.nan
        with self.assertRaisesRegex(ValueError, "finite and positive"):
            simulate_overnight(invalid)


if __name__ == "__main__":
    unittest.main()
