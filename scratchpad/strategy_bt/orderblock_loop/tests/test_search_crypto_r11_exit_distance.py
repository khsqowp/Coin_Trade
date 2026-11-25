import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import search_crypto as common
import search_crypto_r11_exit_distance as r11


class SearchCryptoR11ExitDistanceTests(unittest.TestCase):
    def test_grid_has_48_unique_preregistered_cells(self):
        self.assertEqual(len(r11.CONFIGS), 48)
        self.assertEqual(len({json.dumps(c, sort_keys=True) for c in r11.CONFIGS}), 48)
        self.assertEqual({c["timeframe"] for c in r11.CONFIGS}, {"4h"})
        self.assertEqual({c["minimum_symbols"] for c in r11.CONFIGS}, {30})
        self.assertEqual({c["reward_r"] for c in r11.CONFIGS}, {0.25, 0.5, 0.75, 1.0})

    def test_preregistration_digest_is_pinned(self):
        digest = hashlib.sha256(r11.PREREG_PATH.read_bytes()).hexdigest()
        self.assertEqual(digest, r11.PREREG_SHA256)

    def test_run_fails_closed_when_preregistration_hash_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            altered = Path(directory) / "prereg.md"
            altered.write_text("modified preregistration", encoding="utf-8")
            with patch.object(r11, "PREREG_PATH", altered):
                with self.assertRaisesRegex(RuntimeError, "preregistration hash changed"):
                    r11.run()

    def test_append_writes_one_r11_trial_using_standard_ledger_schema(self):
        config = r11.CONFIGS[0]
        result = {"status": "completed", "trades": 123, "expectancy_bps": 16.0}
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.csv"
            with patch.object(common, "CSV_PATH", ledger):
                r11._append(config, result, "fingerprint", "grid", "code")
            with ledger.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(tuple(rows[0]), common.FIELDS)
            self.assertEqual(rows[0]["round"], r11.ROUND)
            metric = json.loads(rows[0]["metric"])
            self.assertEqual(metric["train_input_fingerprint"], "fingerprint")
            self.assertEqual(metric["preregistration_sha256"], r11.PREREG_SHA256)

    def test_registered_trials_require_exact_grid_code_fingerprint_and_prereg(self):
        config = r11.CONFIGS[0]
        definition = json.dumps(config, sort_keys=True, separators=(",", ":"))
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({
                    "trial_id": "r11-test", "round": r11.ROUND,
                    "market_group": "crypto", "utc_timestamp": "now",
                    "definition": definition, "parameter_grid_hash": "grid",
                    "code_sha256": "code", "train_period": "train",
                    "metric": json.dumps({
                        "train_input_fingerprint": "fingerprint",
                        "preregistration_sha256": r11.PREREG_SHA256,
                    }),
                    "rank": "", "notes": "test",
                })
            with patch.object(common, "CSV_PATH", ledger):
                self.assertEqual(
                    r11._registered("grid", "code", "fingerprint"), {definition}
                )
                self.assertEqual(r11._registered("other-grid", "code", "fingerprint"), set())
                self.assertEqual(r11._registered("grid", "other-code", "fingerprint"), set())
                self.assertEqual(r11._registered("grid", "code", "other-fingerprint"), set())


if __name__ == "__main__":
    unittest.main()
