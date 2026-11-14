import unittest

import numpy as np
import pandas as pd

from run_gen11 import _validate_adjusted_ordering, build_signal, simulate


def bars(opens, highs=None, lows=None, closes=None):
    idx = pd.date_range("2020-01-01", periods=len(opens), freq="B")
    opens = np.asarray(opens, dtype=float)
    closes = opens.copy() if closes is None else np.asarray(closes, dtype=float)
    highs = np.maximum(opens, closes) + 1 if highs is None else np.asarray(highs, dtype=float)
    lows = np.minimum(opens, closes) - 1 if lows is None else np.asarray(lows, dtype=float)
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes,
                         "adjclose": closes, "volume": 1.0}, index=idx)


class Gen11SignalTests(unittest.TestCase):
    def test_signal_is_causal_and_uses_previous_100_volatility_values(self):
        n = 150
        close = np.linspace(100, 110, n)
        frame = bars(close, highs=close + 0.5, lows=close - 0.5, closes=close)
        first, _ = build_signal(frame)
        changed = frame.copy()
        changed.iloc[140:, changed.columns.get_loc("high")] += 100
        changed.iloc[140:, changed.columns.get_loc("low")] -= 100
        second, _ = build_signal(changed)
        pd.testing.assert_series_equal(first.iloc[:140], second.iloc[:140])
        self.assertFalse(first.iloc[:120].any())

    def test_signal_requires_strict_threshold_and_positive_five_session_momentum(self):
        # A constant-range series cannot create a strict > percentile signal.
        close = np.linspace(100, 130, 150)
        frame = bars(close, highs=close + 1, lows=close - 1, closes=close)
        signal, features = build_signal(frame)
        valid = features["threshold"].notna() & features["momentum"].notna()
        self.assertTrue(valid.any())
        self.assertFalse(signal.any())
        self.assertTrue(features["atr20_over_close"].iloc[19:].notna().all())
        expected = ((features["atr20_over_close"] > features["threshold"])
                    & (features["momentum"] > 0)).fillna(False)
        pd.testing.assert_series_equal(signal, expected.astype(bool))

    def test_invalid_ohlc_fails_closed(self):
        frame = bars(np.arange(1, 151, dtype=float))
        frame.iloc[80, frame.columns.get_loc("high")] = 0
        with self.assertRaises(ValueError):
            build_signal(frame)

    def test_adjusted_ohlc_roundoff_tolerance_is_narrow_and_relative(self):
        tiny = pd.DataFrame({"open": [100.0], "high": [100.0], "low": [100.0 + 1e-13], "close": [100.0]})
        _validate_adjusted_ordering(tiny)
        bad = tiny.copy()
        bad.loc[bad.index[0], "low"] = 100.0 + 1e-6
        with self.assertRaises(ValueError):
            _validate_adjusted_ordering(bad)


class Gen11ExecutionTests(unittest.TestCase):
    def test_next_open_five_intervals_entry_exit_costs_and_benchmark(self):
        frame = bars([100, 100, 110, 110, 110, 110, 110, 110, 110])
        signal = pd.Series(False, index=frame.index)
        signal.iloc[1] = True  # close day 1, enter open day 2, exit open day 7
        result = simulate(frame, signal, hold_intervals=5, cost=0.01)
        self.assertEqual(result["trades"], 1)
        # First interval includes entry cost; last interval includes exit cost.
        strategy = result["strategy_returns"]
        self.assertAlmostEqual(strategy.iloc[2], (110 / 110) * (1 - 0.01) - 1)
        self.assertAlmostEqual(strategy.iloc[6], (110 / 110) * (1 - 0.01) - 1)
        self.assertAlmostEqual(strategy.iloc[3:6].sum(), 0.0)

    def test_overlapping_signals_suppressed_until_exit_date_close(self):
        frame = bars(np.linspace(100, 120, 30))
        signal = pd.Series(False, index=frame.index)
        signal.iloc[[2, 5, 8, 9, 16]] = True
        result = simulate(frame, signal, hold_intervals=5, cost=0.001)
        # Signal 2 opens at 3, exits at 8; 5 and 9 are suppressed. Signal 8 is
        # evaluated after the exit-day close and may enter at open 9; 16 is later.
        self.assertEqual(result["trades"], 3)
        self.assertEqual(result["suppressed"], 2)

    def test_terminal_censored_signal_is_not_entered(self):
        frame = bars(np.linspace(100, 110, 12))
        signal = pd.Series(False, index=frame.index)
        signal.iloc[7] = True  # needs exit open at index 13, outside data
        result = simulate(frame, signal, hold_intervals=5, cost=0.001)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["censored"], 1)


if __name__ == "__main__":
    unittest.main()
