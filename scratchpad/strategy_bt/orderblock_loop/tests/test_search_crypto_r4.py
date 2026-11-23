import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from crypto import Bar
import search_crypto_r4 as r4
from search_crypto_r4 import CONFIGS, _registered_trials, _trial


class SearchCryptoR4Tests(unittest.TestCase):
    def test_grid_has_72_unique_preregistered_settings(self):
        keys = [(
            row["definition"], row["timeframe"], row["direction"],
            row["deadline"], row["reward_r"],
        ) for row in CONFIGS]
        self.assertEqual(len(keys), 72)
        self.assertEqual(len(set(keys)), 72)
        self.assertEqual({row["minimum_symbols"] for row in CONFIGS}, {30})
        self.assertEqual({row["funding_order_policy"] for row in CONFIGS}, {"adverse_only"})

    def test_symbol_floor_uses_30_and_does_not_infer_trades(self):
        bars = [Bar(i, 100, 101, 99, 100, 10) for i in range(32)]
        config = CONFIGS[0]
        result = _trial(config, [(f"S{i}", bars, {}, 0) for i in range(29)], {})
        self.assertEqual(result["status"], "unscorable")
        self.assertEqual(result["symbols"], 29)
        self.assertEqual(result["total_trades"], 0)

    def test_complete_symbol_floor_can_be_scored_without_signals(self):
        bars = [Bar(i, 100, 101, 99, 100, 10) for i in range(32)]
        result = _trial(CONFIGS[0], [(f"S{i}", bars, {}, 0) for i in range(30)], {})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["symbols"], 30)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["cumulative_return"], 0.0)

    def test_resume_reader_handles_large_existing_metric_fields(self):
        fields = ("trial_id", "round", "parameter_grid_hash", "code_sha256", "definition", "metric")
        config = '{"definition":"displacement"}'
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "trial_id": "old", "round": "R4-coin", "parameter_grid_hash": "grid",
                    "code_sha256": "code", "definition": config, "metric": "x" * 150_000,
                })
            with patch("search_crypto_r4.common.CSV_PATH", ledger):
                self.assertEqual(_registered_trials("grid", "code"), {config})

    def test_m2_reports_all_signals_and_symbol_nonoverlap_separately(self):
        events = [
            ("BTCUSDT", 100, 200, 1, True),
            ("BTCUSDT", 150, 250, 2, False),
            ("ETHUSDT", 120, 240, 3, True),
            ("BTCUSDT", 200, 300, 4, True),
        ]
        result = r4._m2_metrics(events)
        self.assertEqual(result["m2_signal_count"], 4)
        self.assertEqual(result["m2_target_hits"], 3)
        self.assertEqual(result["m2_target_first_rate"], 0.75)
        self.assertEqual(result["m2_nonoverlap_signal_count"], 3)
        self.assertEqual(result["m2_nonoverlap_target_hits"], 3)
        self.assertEqual(result["m2_nonoverlap_target_first_rate"], 1.0)
        self.assertIsNotNone(result["m2_wilson_lower_95"])
        self.assertIsNotNone(result["m2_nonoverlap_wilson_lower_95"])

    def test_m2_empty_sample_is_unknown_not_zero_accuracy(self):
        result = r4._m2_metrics([])
        self.assertEqual(result["m2_signal_count"], 0)
        self.assertIsNone(result["m2_target_first_rate"])
        self.assertIsNone(result["m2_wilson_lower_95"])
        self.assertEqual(result["m2_nonoverlap_signal_count"], 0)
        self.assertIsNone(result["m2_nonoverlap_target_first_rate"])

    def test_trial_keeps_primary_and_strict_metrics_separate_and_counts_m2(self):
        bars = [Bar(i * 900_000, 100, 101, 99, 100, 10) for i in range(32)]
        trades = [
            SimpleNamespace(
                setup=SimpleNamespace(entry_index=1, zone=SimpleNamespace(signal_index=0)),
                exit_index=2, exit_reason="target", net_return=0.01,
                ambiguous_funding_events=1,
            ),
            SimpleNamespace(
                setup=SimpleNamespace(entry_index=3, zone=SimpleNamespace(signal_index=2)),
                exit_index=4, exit_reason="stop", net_return=-0.01,
                ambiguous_funding_events=0,
            ),
            SimpleNamespace(
                setup=SimpleNamespace(entry_index=5, zone=SimpleNamespace(signal_index=4)),
                exit_index=6, exit_reason="time", net_return=None,
                ambiguous_funding_events=0,
            ),
            SimpleNamespace(
                setup=SimpleNamespace(entry_index=7, zone=SimpleNamespace(signal_index=6)),
                exit_index=8, exit_reason="target", net_return=0.02,
                ambiguous_funding_events=1,
            ),
        ]
        with patch("search_crypto_r4.r4_zones", return_value=[]), \
                patch("search_crypto_r4.simulate_orderblock", side_effect=[trades] + [[]] * 29), \
                patch("search_crypto_r4.trade_daily_pnl",
                      side_effect=[{0: 0.01}, {0: -0.01}, None]) as daily_pnl:
            result = _trial(CONFIGS[0], [(f"S{i}", bars, {}, 0) for i in range(30)], {})

        self.assertEqual(result["trades"], 2)
        self.assertEqual(result["strict_scored_trades"], 1)
        self.assertEqual(result["strict_unscorable_funding_trades"], 3)
        self.assertEqual(result["strict_scoreable_trades"], 1)
        self.assertEqual(result["expectancy_bps"], 0.0)
        self.assertEqual(result["strict_expectancy_bps"], -100.0)
        self.assertEqual(result["m2_signal_count"], 4)
        self.assertEqual(result["m2_target_hits"], 2)
        self.assertEqual(result["m2_target_first_rate"], 0.5)
        self.assertEqual(daily_pnl.call_count, 3)


if __name__ == "__main__":
    unittest.main()
