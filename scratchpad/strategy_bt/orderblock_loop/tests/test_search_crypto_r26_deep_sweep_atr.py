from __future__ import annotations

import unittest
from unittest.mock import patch

import search_crypto_r14 as r14
import search_crypto_r26_deep_sweep_atr as r26
from crypto import Bar, FundingEvent, Zone


class R26DeepSweepTests(unittest.TestCase):
    def test_long_depth_threshold_below_equal_and_above(self):
        bars = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100, 1)
                for i in range(21)]
        bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 101, 98.1, 100.5, 1)
        with patch.object(r26, "_atr", return_value=4):
            self.assertFalse(r26._deep_sweep(bars, 20, "long"))
            bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 101, 98, 100.5, 1)
            self.assertTrue(r26._deep_sweep(bars, 20, "long"))
            bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 101, 97.9, 100.5, 1)
            self.assertTrue(r26._deep_sweep(bars, 20, "long"))

    def test_short_depth_threshold_is_symmetric(self):
        bars = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100, 1)
                for i in range(21)]
        bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 101.9, 99, 99.5, 1)
        with patch.object(r26, "_atr", return_value=4):
            self.assertFalse(r26._deep_sweep(bars, 20, "short"))
            bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 102, 99, 99.5, 1)
            self.assertTrue(r26._deep_sweep(bars, 20, "short"))
            bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 102.1, 99, 99.5, 1)
            self.assertTrue(r26._deep_sweep(bars, 20, "short"))

    def test_atr_warmup_or_invalid_atr_rejects_sweep(self):
        bars = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100, 1)
                for i in range(21)]
        bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 101, 98, 100.5, 1)
        with patch.object(r26, "_atr", return_value=None):
            self.assertFalse(r26._deep_sweep(bars, 20, "long"))
        with patch.object(r26, "_atr", return_value=0):
            self.assertFalse(r26._deep_sweep(bars, 20, "long"))
        with patch.object(r26, "_atr", return_value=None):
            self.assertEqual(r26._pre_bos_sweep_funnel(bars, 21, "long"),
                             (True, False, True, False))
        with patch.object(r26, "_atr", return_value=5):
            self.assertEqual(r26._pre_bos_sweep_funnel(bars, 21, "long"),
                             (True, False, False, True))

    def test_zone_funnel_counts_atr_warmup_and_shallow_rejections(self):
        bars = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100, 1)
                for i in range(21)]
        bars[20] = Bar(20 * r26.BAR_4H_MS, 100, 101.2, 98.8, 100, 1)
        zones = [Zone(21, 18, "long", 98, 99, 1),
                 Zone(21, 18, "short", 101, 102, 1)]
        stats = {"raw_bos_zones": 0, "basic_sweep_zones": 0,
                 "deep_sweep_zones": 0, "atr_warmup_rejected_zones": 0,
                 "shallow_rejected_zones": 0}
        with patch.object(r26.r14, "r4_zones", return_value=zones), \
                patch.object(r26, "_atr", return_value=4):
            _original, builder = r26._filtered_zone_builder(stats)
            self.assertEqual(builder(bars, "bos_origin"), [])
        self.assertEqual(stats["raw_bos_zones"], 2)
        self.assertEqual(stats["basic_sweep_zones"], 2)
        self.assertEqual(stats["atr_warmup_rejected_zones"], 0)
        self.assertEqual(stats["shallow_rejected_zones"], 2)
        stats = {"raw_bos_zones": 0, "basic_sweep_zones": 0,
                 "deep_sweep_zones": 0, "atr_warmup_rejected_zones": 0,
                 "shallow_rejected_zones": 0}
        with patch.object(r26.r14, "r4_zones", return_value=zones), \
                patch.object(r26, "_atr", return_value=None):
            _original, builder = r26._filtered_zone_builder(stats)
            self.assertEqual(builder(bars, "bos_origin"), [])
        self.assertEqual(stats["atr_warmup_rejected_zones"], 2)
        self.assertEqual(stats["shallow_rejected_zones"], 0)

    def test_sweep_must_precede_bos_by_one_to_three_bars(self):
        bars = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100, 1)
                for i in range(30)]
        bars[25] = Bar(25 * r26.BAR_4H_MS, 100, 101, 98.4, 100.5, 1)
        with patch.object(r26, "_atr", return_value=2):
            self.assertTrue(r26._pre_bos_deep_sweep(bars, 26, "long"))
            self.assertTrue(r26._pre_bos_deep_sweep(bars, 28, "long"))
            self.assertFalse(r26._pre_bos_deep_sweep(bars, 29, "long"))

    def test_bos_bar_excluded_and_post_sweep_pre_bos_mutation_is_invariant(self):
        bars = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100, 1)
                for i in range(34)]
        bars[28] = Bar(28 * r26.BAR_4H_MS, 100, 101, 98.4, 100.5, 1)
        self.assertFalse(r26._pre_bos_deep_sweep(bars, 28, "long"))
        bars[25] = Bar(25 * r26.BAR_4H_MS, 100, 101, 98.4, 100.5, 1)
        baseline_candidate = r26._deep_sweep(bars, 25, "long")
        baseline = r26._pre_bos_deep_sweep(bars, 28, "long")
        changed = list(bars)
        for i in (26, 27):
            old = changed[i]
            changed[i] = Bar(old.timestamp, old.open, 300, 99,
                             old.close, old.volume)
        for i in range(28, len(changed)):
            old = changed[i]
            changed[i] = Bar(old.timestamp, old.open, old.high + 100,
                             old.low - 100, old.close, old.volume)
        self.assertTrue(baseline_candidate)
        self.assertTrue(baseline)
        self.assertEqual(r26._deep_sweep(changed, 25, "long"), baseline_candidate)
        self.assertEqual(r26._pre_bos_deep_sweep(changed, 28, "long"), baseline)

    def test_r21_deep_filter_calls_real_r14_trial_and_restores_builder(self):
        four_hour = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100.5, 1000)
                     for i in range(42)]
        four_hour[25] = Bar(25 * r26.BAR_4H_MS, 100, 101, 98.4, 100.1, 1000)
        hourly_ms = 3_600_000
        hourly = [Bar(i * hourly_ms, 100, 101, 99, 100.5, 1000)
                  for i in range(len(four_hour) * 4)]
        hourly[117] = Bar(117 * hourly_ms, 99, 99.2, 98.2, 98.8, 1000)
        hourly[118] = Bar(118 * hourly_ms, 98.9, 99.2, 98.5, 99, 1000)
        hourly[119] = Bar(119 * hourly_ms, 99, 100, 98.5, 99.8, 1000)
        funding = {hourly[119].timestamp: FundingEvent(
            hourly[119].timestamp, 0.001, 98.9)}
        accepted = Zone(28, 24, "long", 98, 99, 1)
        shallow = Zone(33, 30, "long", 98, 99, 1)
        original_builder = r14.r4_zones
        original_simulator = r14.simulate_trade
        observed = []

        def capture_trade(*args, **kwargs):
            trade = original_simulator(*args, **kwargs)
            observed.append((args[1], trade))
            return trade

        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[accepted, shallow]), \
                patch.object(r14, "simulate_trade", side_effect=capture_trade), \
                patch.object(r26, "_atr", return_value=2):
            result = r26._trial_with_deep_sweep(
                [("BTCUSDT", hourly, funding, 0)],
                [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(r14.r4_zones, original_builder)
        self.assertEqual(result["raw_bos_zones"], 2)
        self.assertEqual(result["basic_sweep_zones"], 1)
        self.assertEqual(result["deep_sweep_zones"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 1)
        self.assertEqual(result["trades"], 1)
        self.assertEqual(len(observed), 1)
        _setup, trade = observed[0]
        self.assertEqual(trade.exit_reason, "target")
        self.assertAlmostEqual(trade.cost_bps, 12)
        self.assertLess(trade.funding_return, 0)

    def test_r26_end_to_end_same_bar_stop_first(self):
        four_hour = [Bar(i * r26.BAR_4H_MS, 100, 101, 99, 100.5, 1000)
                     for i in range(42)]
        four_hour[25] = Bar(25 * r26.BAR_4H_MS, 100, 101, 98.4, 100.1, 1000)
        hourly_ms = 3_600_000
        hourly = [Bar(i * hourly_ms, 100, 101, 99, 100.5, 1000)
                  for i in range(len(four_hour) * 4)]
        hourly[117] = Bar(117 * hourly_ms, 99, 99.2, 98.2, 98.8, 1000)
        hourly[118] = Bar(118 * hourly_ms, 98.9, 99.2, 98.5, 99, 1000)
        hourly[119] = Bar(119 * hourly_ms, 99, 100, 97.5, 99.8, 1000)
        accepted = Zone(28, 24, "long", 98, 99, 1)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[accepted]), \
                patch.object(r26, "_atr", return_value=2):
            result = r26._trial_with_deep_sweep(
                [("BTCUSDT", hourly, {}, 0)],
                [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 0)
        self.assertEqual(result["trades"], 1)
        self.assertLess(result["expectancy_bps"], 0)


if __name__ == "__main__":
    unittest.main()
