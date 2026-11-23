import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crypto import Bar
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


if __name__ == "__main__":
    unittest.main()
