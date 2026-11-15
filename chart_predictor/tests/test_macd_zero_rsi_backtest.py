import unittest

import numpy as np

from chart_predictor.macd_zero_rsi_backtest import (
    entry_signal_mask,
    exit_signal_mask,
    resolve_barrier,
    trade_net_return,
    _simulate,
)
from chart_predictor.indicators import atr, macd, rsi


class MacdZeroRsiRuleTests(unittest.TestCase):
    @staticmethod
    def synthetic_trade(exit_type):
        from chart_predictor.macd_zero_rsi_backtest import BAR, MINUTE
        n = 24
        stamps = np.arange(n, dtype=np.int64) * BAR
        bars = __import__("pandas").DataFrame({
            "t_open_ms": stamps, "o": np.full(n, 100.), "h": np.full(n, 100.5),
            "l": np.full(n, 99.5), "c": np.full(n, 100.), "atr": np.full(n, 0.5),
            "entry_signal": np.zeros(n, dtype=bool), "macd_exit": np.zeros(n, dtype=bool),
            "rsi_exit": np.zeros(n, dtype=bool)})
        bars.loc[1, "entry_signal"] = True
        raw_rows = []
        for stamp in stamps:
            for minute in range(int(stamp), int(stamp + BAR), MINUTE):
                raw_rows.append((minute, 100., 100.5, 99.5, 100., 1., 1., 1))
        raw = __import__("pandas").DataFrame(raw_rows, columns=["t_open_ms", "o", "h", "l", "c", "v", "quote_v", "trades"])
        if exit_type in ("macd_zero_down", "rsi_below_50"):
            bars.loc[2, "macd_exit" if exit_type == "macd_zero_down" else "rsi_exit"] = True
            bars.loc[3, "o"] = 100.5
        elif exit_type == "fixed_2R":
            raw.loc[raw.index[10], "h"] = 102.1
        elif exit_type == "chandelier_3ATR":
            bars.loc[2, "h"] = 103.
            bars.loc[3, "o"] = 102.
            raw.loc[15:19, "o"] = 102.
            raw.loc[15:19, "l"] = 101.4
        return _simulate(raw, bars, "TEST", None, 0.0005, exit_type)[0]

    def test_entry_requires_zero_cross_and_rsi_above_50_on_same_closed_bar(self):
        macd = np.array([-0.2, 0.0, 0.1, 0.3, -0.1, 0.2])
        rsi = np.array([49.0, 51.0, 50.0, 50.01, 60.0, 49.0])
        np.testing.assert_array_equal(
            entry_signal_mask(macd, rsi),
            np.array([False, False, False, False, False, False]),
        )

    def test_entry_emits_only_on_nonpositive_to_positive_cross(self):
        macd = np.array([-0.2, 0.0, 0.1, 0.3, -0.1, 0.2])
        rsi = np.array([49.0, 51.0, 51.0, 60.0, 60.0, 55.0])
        np.testing.assert_array_equal(
            entry_signal_mask(macd, rsi),
            np.array([False, False, True, False, False, True]),
        )

    def test_exit_signals_are_completed_bar_crosses_not_levels(self):
        macd = np.array([0.1, 0.0, -0.1, -0.2, 0.1])
        rsi = np.array([55.0, 50.0, 49.0, 48.0, 52.0])
        got = exit_signal_mask(macd, rsi)
        np.testing.assert_array_equal(got["macd_zero_down"], [False, False, True, False, False])
        np.testing.assert_array_equal(got["rsi_below_50"], [False, False, True, False, False])

    def test_same_one_minute_stop_target_tie_is_stop_first(self):
        result = resolve_barrier(open_price=100.0, high=105.0, low=97.0,
                                 stop=98.0, target=104.0)
        self.assertEqual(result, ("stop", 98.0))

    def test_stop_gap_fills_at_worse_open(self):
        result = resolve_barrier(open_price=96.0, high=99.0, low=95.0,
                                 stop=98.0, target=None)
        self.assertEqual(result, ("stop_gap", 96.0))

    def test_target_gap_is_capped_at_limit_price(self):
        result = resolve_barrier(open_price=105.0, high=106.0, low=104.5,
                                 stop=98.0, target=104.0)
        self.assertEqual(result, ("target", 104.0))

    def test_round_trip_fee_uses_entry_and_exit_notionals(self):
        gross, net = trade_net_return(100.0, 110.0, fee_per_side=0.0005)
        self.assertAlmostEqual(gross, 0.1)
        self.assertAlmostEqual(net, 0.1 - 0.0005 * (1.0 + 1.1))

    def test_indicators_and_signals_are_prefix_invariant(self):
        close = np.array([100 + i * 0.2 + np.sin(i / 3) for i in range(180)])
        high, low = close + 0.8, close - 0.7
        full = (macd(close)[0], rsi(close), atr(high, low, close))
        prefix = (macd(close[:120])[0], rsi(close[:120]), atr(high[:120], low[:120], close[:120]))
        for a, b in zip(full, prefix):
            np.testing.assert_allclose(a[:120], b, equal_nan=True)
        full_entries = entry_signal_mask(full[0], full[1])
        prefix_entries = entry_signal_mask(prefix[0], prefix[1])
        np.testing.assert_array_equal(full_entries[:120], prefix_entries)

    def test_future_mutation_cannot_change_past_entry_signals(self):
        macd = np.array([-1., -0.2, 0.1, 0.2, -0.2, 0.1, 0.4])
        rsi = np.array([40., 51., 55., 56., 49., 53., 60.])
        before = entry_signal_mask(macd, rsi)
        macd[4:] = [-99., 200., -100.]
        rsi[4:] = [0., 100., 0.]
        after = entry_signal_mask(macd, rsi)
        np.testing.assert_array_equal(before[:4], after[:4])

    def test_synthetic_exit_paths_and_exact_timeout(self):
        self.assertEqual(self.synthetic_trade("macd_zero_down")["reason"], "signal")
        self.assertEqual(self.synthetic_trade("rsi_below_50")["reason"], "signal")
        self.assertEqual(self.synthetic_trade("fixed_2R")["reason"], "target")
        self.assertEqual(self.synthetic_trade("chandelier_3ATR")["reason"], "stop")
        timeout = self.synthetic_trade("time")
        self.assertEqual(timeout["reason"], "time")
        self.assertEqual(timeout["bars_held"], 20)
        self.assertEqual(timeout["exit_ms"], 22 * 5 * 60_000)


if __name__ == "__main__":
    unittest.main()
