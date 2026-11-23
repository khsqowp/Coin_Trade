import unittest
from unittest.mock import patch

from crypto import Bar, Setup, Zone, simulate_trade
import search_crypto_r6 as r6


class SearchCryptoR6Tests(unittest.TestCase):
    def test_grid_is_exactly_eight_a_and_four_b_trials(self):
        a = [config for config in r6.CONFIGS if config["experiment"] == "R6-A"]
        b = [config for config in r6.CONFIGS if config["experiment"] == "R6-B"]
        self.assertEqual(len(a), 8)
        self.assertEqual(len(b), 4)
        self.assertEqual({config["funding_order_policy"] for config in r6.CONFIGS},
                         {"adverse_only"})
        self.assertEqual({config["minimum_symbols"] for config in r6.CONFIGS}, {30})
        self.assertEqual(len({str(config) for config in r6.CONFIGS}), 12)
        self.assertEqual(len(r6.configs_for("R6-A")), 8)
        self.assertEqual(len(r6.configs_for("R6-B")), 4)
        with self.assertRaises(ValueError):
            r6.configs_for("R6-C")

    def test_atr_bin_uses_only_preceding_history_and_median_ties_are_low(self):
        bars = [Bar(index, 100, 101, 99, 100, 1) for index in range(32)]

        def atr_fraction(_bars, index):
            if index == 31:
                return 2.0
            return 1.0

        with patch("search_crypto_r6._atr_fraction", side_effect=atr_fraction) as calc:
            self.assertEqual(r6._atr_bin(bars, 31), "high")
            calls = [call.args[1] for call in calc.call_args_list]
            self.assertEqual(calls[0], 31)
            self.assertTrue(all(index < 31 for index in calls[1:]))
        with patch("search_crypto_r6._atr_fraction", return_value=1.0):
            self.assertEqual(r6._atr_bin(bars, 31), "low")

    def test_r6a_stop_buffer_and_two_r_target_are_exact(self):
        bars = [
            Bar(0, 100, 101, 99, 100, 1),
            Bar(1, 100, 100.5, 99.5, 100, 1),
            Bar(2, 100, 101, 99, 100, 1),
        ]
        zone = Zone(0, 0, "long", 99, 101, 2)
        config = next(row for row in r6.CONFIGS if row["experiment"] == "R6-A"
                      and row["stop_buffer_atr"] == 0.05)
        setup = r6._setup_for_zone(bars, zone, config)
        self.assertIsNotNone(setup)
        self.assertAlmostEqual(setup.stop, 98.9)
        self.assertAlmostEqual(setup.target, 102.2)
        self.assertEqual(setup.entry_index, 2)

    def test_r6b_requires_confirmation_close_position_then_next_open(self):
        bars = [
            Bar(0, 100, 101, 99, 100, 1),
            Bar(1, 100, 100.5, 99.5, 100, 1),
            Bar(2, 100, 102, 99, 101.7, 1),
            Bar(3, 101, 102, 100, 101, 1),
        ]
        zone = Zone(0, 0, "long", 99, 101, 2)
        config = next(row for row in r6.CONFIGS if row["experiment"] == "R6-B"
                      and row["close_location_threshold"] == 0.80)
        setup = r6._setup_for_zone(bars, zone, config)
        self.assertIsNotNone(setup)
        self.assertEqual(setup.entry_index, 3)
        bars[2] = Bar(2, 100, 102, 99, 101, 1)
        self.assertIsNone(r6._setup_for_zone(bars, zone, config))

    def test_confirmation_rejects_zero_range_and_missing_confirm_bar(self):
        zone = Zone(0, 0, "long", 99, 101, 2)
        config = next(row for row in r6.CONFIGS if row["experiment"] == "R6-B")
        flat_confirm = [Bar(0, 100, 101, 99, 100, 1),
                        Bar(1, 100, 100.5, 99.5, 100, 1),
                        Bar(2, 100, 101, 101, 101, 1)]
        self.assertIsNone(r6._setup_for_zone(flat_confirm, zone, config))
        missing_confirm = flat_confirm[:2]
        self.assertIsNone(r6._setup_for_zone(missing_confirm, zone, config))

    def test_r6a_counts_insufficient_atr_history_and_right_censor(self):
        bars = [Bar(i * r6.DURATION_MS, 100, 101, 99, 100, 1)
                for i in range(40)]
        zone = Zone(0, 0, "long", 90, 95, 1)
        barsets = [(f"S{i}", bars, {}, 0) for i in range(30)]
        prepared = {f"S{i}": ([zone], {0: None}) for i in range(30)}
        result = r6._trial(r6.CONFIGS[0], barsets, prepared)
        self.assertEqual(result["atr_history_insufficient_signals"], 30)
        trades, audit = r6._trades_for_symbol(bars, {}, r6.CONFIGS[0], [zone], {0: "low"})
        self.assertEqual(trades, [])
        self.assertEqual(audit["right_censored_setups"], 1)

    def test_minimum_symbol_floor_is_30(self):
        bars = [Bar(i * r6.DURATION_MS, 100, 101, 99, 100, 1) for i in range(40)]
        barsets = [(f"S{i}", bars, {}, 0) for i in range(29)]
        with patch("search_crypto_r6.r4_zones", return_value=[]):
            result = r6._trial(r6.CONFIGS[0], barsets)
        self.assertEqual(result["status"], "unscorable")
        self.assertEqual(result["symbols"], 29)
        self.assertIn("symbols 29 < 30", result["detail"])

    def test_symbol_floor_passes_at_30_without_signals(self):
        bars = [Bar(i * r6.DURATION_MS, 100, 101, 99, 100, 1) for i in range(40)]
        barsets = [(f"S{i}", bars, {}, 0) for i in range(30)]
        with patch("search_crypto_r6.r4_zones", return_value=[]):
            result = r6._trial(r6.CONFIGS[0], barsets)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["symbols"], 30)
        self.assertEqual(result["trades"], 0)

    def test_registered_24_bar_horizon_exits_at_next_open(self):
        bars = [Bar(i * r6.DURATION_MS, 100, 101, 99, 100, 1)
                for i in range(27)]
        zone = Zone(0, 0, "long", 90, 95, 1)
        setup = Setup(zone, 1, 100, 90, 120)
        trade = simulate_trade(
            bars, setup, funding={}, max_holding_bars=24,
            bar_duration_ms=r6.DURATION_MS,
            funding_order_policy="adverse_only",
        )
        self.assertIsNotNone(trade)
        self.assertEqual(trade.exit_reason, "time")
        self.assertEqual(trade.exit_index, 25)


if __name__ == "__main__":
    unittest.main()
