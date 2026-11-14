import unittest

import numpy as np
import pandas as pd

from run_gen10 import build_signal, simulate, adjusted_ohlc, descriptive_metrics


def bars(high, low, close=None, open_=None):
    idx = pd.date_range("2024-01-01", periods=len(high), freq="D")
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close if close is not None else (high + low) / 2, dtype=float)
    open_ = np.asarray(open_ if open_ is not None else close, dtype=float)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "adjclose": close}, index=idx)


class Gen10Tests(unittest.TestCase):
    def test_nr7_uses_exact_seven_prior_ranges_and_ties_qualify(self):
        frame = bars([12, 11, 10, 10, 10, 10, 10, 10, 12],
                     [10, 10, 9, 9, 9, 9, 9, 9, 10],
                     close=[11, 10.5, 9.5, 9.5, 9.5, 9.5, 9.5, 9.5, 11.5])
        signal = build_signal(frame)
        # At t=8, range at t-1 ties the smallest in the seven preceding ranges;
        # close[t] breaks the previous high.
        self.assertTrue(signal.iloc[8])
        self.assertFalse(signal.iloc[7])

    def test_prior_window_excludes_current_bar_and_requires_prior_break(self):
        frame = bars([12, 11, 10, 10, 10, 10, 10, 10, 10],
                     [10, 10, 9, 9, 9, 9, 9, 9, 9],
                     close=[11, 10.5, 9.5, 9.5, 9.5, 9.5, 9.5, 9.5, 9.5])
        self.assertFalse(build_signal(frame).iloc[8])

    def test_entry_is_next_open_and_exit_is_ten_open_intervals_later(self):
        frame = bars([200] * 20, [1] * 20, close=[11] * 20,
                     open_=[100 + i for i in range(20)])
        signal = pd.Series(False, index=frame.index)
        signal.iloc[7] = True
        result = simulate(frame, signal, fee=0.0)
        # Close signal at 7, entry O8, exit O18. Exactly intervals 8->9 ... 17->18.
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["entry_indices"], [8])
        self.assertEqual(result["exit_indices"], [18])
        self.assertEqual(result["exposure"].sum(), 10)
        self.assertTrue(np.all(result["returns"].iloc[9:19].to_numpy() != 0))
        self.assertEqual(float(result["returns"].iloc[8]), 0.0)

    def test_overlap_suppression_and_reentry_at_exit_open(self):
        frame = bars([200] * 30, [1] * 30, close=[11] * 30,
                     open_=[100 + i for i in range(30)])
        signal = pd.Series(False, index=frame.index)
        signal.iloc[[7, 10, 17]] = True  # entries 8,11 (blocked),18 (at prior exit)
        result = simulate(frame, signal, fee=0.0)
        self.assertEqual(result["entry_indices"], [8, 18])
        self.assertEqual(result["overlap_suppressed"], 1)

    def test_entry_and_exit_fees_are_each_applied_once(self):
        frame = bars([120] * 20, [90] * 20, close=[100] * 20,
                     open_=[100.0] * 20)
        signal = pd.Series(False, index=frame.index)
        signal.iloc[7] = True
        result = simulate(frame, signal, fee=0.001)
        invested = result["returns"].iloc[9:19].to_numpy()
        self.assertAlmostEqual(float(np.prod(1 + invested)), (1 - 0.001) ** 2)

    def test_terminal_signal_is_censored_not_traded(self):
        frame = bars([200] * 15, [1] * 15, close=[11] * 15,
                     open_=[100 + i for i in range(15)])
        signal = pd.Series(False, index=frame.index)
        signal.iloc[12] = True  # entry index 13; scheduled exit 23 is outside
        result = simulate(frame, signal, fee=0.0)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["terminal_censored"], 1)

    def test_adjusted_ohlc_scales_consistently(self):
        frame = bars([12, 12], [10, 10], close=[11, 11], open_=[10, 10])
        frame.loc[frame.index[1], "adjclose"] = 5.5
        adjusted = adjusted_ohlc(frame)
        self.assertAlmostEqual(adjusted.iloc[1]["open"], 5.0)
        self.assertAlmostEqual(adjusted.iloc[1]["high"], 6.0)
        self.assertAlmostEqual(adjusted.iloc[1]["low"], 5.0)

    def test_invalid_ohlc_fails_closed(self):
        frame = bars([12] * 10, [10] * 10)
        frame.iloc[4, frame.columns.get_loc("high")] = 1
        with self.assertRaises(ValueError):
            adjusted_ohlc(frame)

    def test_metrics_window_retains_first_in_window_observation(self):
        idx = pd.date_range("2020-01-01", periods=300, freq="D")
        returns = pd.Series(0.001, index=idx)
        turns = pd.Series(0.0, index=idx)
        exposure = pd.Series(1.0, index=idx)
        result = descriptive_metrics(returns, turns, exposure, "2020-02-01", "2020-11-01")
        self.assertEqual(result["start"], "2020-02-01")
        self.assertGreater(result["observations"], 100)


if __name__ == "__main__":
    unittest.main()
