from __future__ import annotations

import unittest
from unittest.mock import patch

import search_crypto_r14 as r14
import search_crypto_r24_bos_impulse_target as r24
from crypto import Bar, Zone


class R24EndToEndIntegrationTests(unittest.TestCase):
    def test_r21_filter_to_r14_mapping_setup_and_real_simulator(self):
        hour = r24.HOUR_MS
        four_hour = [Bar(i * 4 * hour, 100, 101, 99, 100.5, 1000)
                     for i in range(42)]
        four_hour[25] = Bar(25 * 4 * hour, 100, 101, 98.9, 100.1, 1000)
        hourly = [Bar(i * hour, 100, 101, 99, 100.5, 1000)
                  for i in range(len(four_hour) * 4)]
        # The structural target must come from the completed BOS candle at 112..115.
        hourly[114] = Bar(114 * hour, 100, 150, 99, 100, 1000)
        hourly[117] = Bar(117 * hour, 99, 99.2, 98.2, 98.8, 1000)
        hourly[118] = Bar(118 * hour, 98.9, 99.2, 98.5, 99.0, 1000)
        hourly[119] = Bar(119 * hour, 99.0, 150, 98.0, 149, 1000)
        zone = Zone(28, 24, "long", 98, 99, 1.0)
        original_simulate = r14.simulate_trade
        captured = []

        def capture_trade(*args, **kwargs):
            trade = original_simulate(*args, **kwargs)
            captured.append((args[1], trade))
            return trade

        stats = {"structure_target_unavailable": 0,
                 "structure_target_not_ahead": 0}
        target_distances = []
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[zone]), \
                patch.object(r14, "simulate_trade", side_effect=capture_trade):
            result = r24._trial_with_structure_target(
                [("BTCUSDT", hourly, {}, 0)],
                [("BTCUSDT", four_hour, {}, 0)],
                stats, target_distances)

        self.assertEqual(result["pre_bos_sweep_zones"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 1)
        self.assertEqual(len(captured), 1)
        setup, trade = captured[0]
        self.assertEqual(setup.entry_index, 118)
        self.assertEqual(setup.target, 150)
        self.assertEqual(trade.exit_reason, "target")
        self.assertEqual(trade.exit_index, 119)
        self.assertAlmostEqual(trade.cost_bps, 12)
        self.assertEqual(stats["structure_target_unavailable"], 0)
        self.assertEqual(stats["structure_target_not_ahead"], 0)


if __name__ == "__main__":
    unittest.main()
