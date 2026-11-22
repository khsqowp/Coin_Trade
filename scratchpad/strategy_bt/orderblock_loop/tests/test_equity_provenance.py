import csv
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import search_equities
from equities import Bar


class EquityProvenanceTests(unittest.TestCase):
    def test_r2_split_default_uses_external_cache_and_trading_data_dir(self):
        with patch.dict(os.environ, {"TRADING_DATA_DIR": "/tmp/trading-data"}):
            self.assertEqual(search_equities._default_split_path(),
                             Path("/tmp/trading-data/cache/orderblock/equity_splits_r2.json"))
        with patch.dict(os.environ):
            os.environ.pop("TRADING_DATA_DIR", None)
            self.assertEqual(search_equities._default_split_path(),
                             Path.home() / "CODE/trading_data/cache/orderblock/equity_splits_r2.json")

    def test_train_frame_hash_is_stable_and_completion_sensitive(self):
        frame = pd.DataFrame([{"open_time": 1, "open": 10.0, "high": 11.0,
                               "low": 9.0, "close": 10.5, "complete": True}])
        self.assertEqual(search_equities._train_frame_sha256(frame),
                         search_equities._train_frame_sha256(frame.copy()))
        changed = frame.copy()
        changed.loc[0, "complete"] = False
        self.assertNotEqual(search_equities._train_frame_sha256(frame),
                            search_equities._train_frame_sha256(changed))

    def test_trailing_incomplete_daily_bar_is_excluded_before_weekly_aggregation(self):
        monday = int(pd.Timestamp("2018-10-22", tz="UTC").timestamp() * 1000)
        frame = pd.DataFrame({
            "open_time": [monday + day * 86_400_000 for day in range(5)],
            "open": [10.0] * 5, "high": [11.0] * 5, "low": [9.0] * 5,
            "close": [10.5] * 5, "complete": [True, True, True, True, False],
        })
        daily, quality = search_equities._prepare_train(frame, "AAA")
        self.assertEqual(len(daily), 4)
        self.assertEqual(quality["incomplete_bars_excluded"], 1)
        self.assertEqual(search_equities._weekly_bars(daily), [])

    def test_nontrailing_incomplete_bar_is_rejected(self):
        frame = pd.DataFrame({
            "open_time": [1, 2, 3], "open": [10.0] * 3, "high": [11.0] * 3,
            "low": [9.0] * 3, "close": [10.5] * 3,
            "complete": [True, False, True],
        })
        with self.assertRaisesRegex(search_equities.SymbolQualityError,
                                    "incomplete bar is not a trailing suffix"):
            search_equities._prepare_train(frame, "AAA")

    def test_run_records_market_fingerprint_accounting_and_preserves_old_rows(self):
        columns = ["open_time", "open", "high", "low", "close", "complete"]
        valid = pd.DataFrame([[1, 10.0, 11.0, 9.0, 10.5, True]], columns=columns)
        empty = pd.DataFrame(columns=columns)
        malformed = pd.DataFrame([[1, 10.0, 8.0, 9.0, 10.5, True]], columns=columns)
        frames = {"AAA": valid, "EMPTY": empty, "BAD": malformed}
        fields = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
                  "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]
        config = {"family": "C1", "timeframe": "daily", "lookback": 10,
                  "retest_bars": 10, "reward_r": 2, "holding_bars": 20}

        def load_train(path, split_file, symbol, market):
            if symbol == "MISSING":
                raise FileNotFoundError("synthetic missing source")
            return frames[symbol].copy()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            universe = root / "universe.csv"
            ledger = root / "trials.csv"
            universe.write_text(
                "market,symbol,daily_path\n"
                "US,AAA,a.parquet\nUS,EMPTY,b.parquet\n"
                "US,BAD,c.parquet\nUS,MISSING,d.parquet\n"
            )
            with ledger.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({field: ("legacy-row" if field == "trial_id" else "")
                                 for field in fields})

            with (patch.object(search_equities, "_configs", return_value=[config]),
                  patch.object(search_equities, "_load_train", side_effect=load_train),
                  patch.object(search_equities, "_simulate", return_value=[]),
                  patch.object(search_equities, "_check_memory_limit")):
                self.assertEqual(search_equities.run(universe, ledger, root / "splits.json"), 1)
                self.assertEqual(search_equities.run(universe, ledger, root / "splits.json"), 1)

            with ledger.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["trial_id"], "legacy-row")
            metrics = [json.loads(row["metric"]) for row in rows[1:]]
            self.assertEqual(len(metrics), 2)
            self.assertEqual(metrics[0]["train_data_sha256"], metrics[1]["train_data_sha256"])
            self.assertEqual(len(metrics[0]["train_data_sha256"]), 64)
            accounting = metrics[0]["train_symbol_accounting"]
            self.assertEqual(accounting["AAA"]["status"], "valid")
            self.assertEqual(accounting["EMPTY"]["status"], "empty_train")
            self.assertEqual(accounting["BAD"]["status"], "quality_excluded")
            self.assertEqual(accounting["MISSING"]["status"], "loader_error")

    def test_r2_code_hash_bundle_includes_quality_filter(self):
        digest = hashlib.sha256()
        for name in ("search_equities.py", "equities.py", "data_access.py",
                     "data_quality.py", "metrics.py", "resource_guard.py"):
            digest.update((search_equities.ROOT / name).read_bytes())
        self.assertEqual(search_equities._source_code_sha256(), digest.hexdigest())


if __name__ == "__main__":
    unittest.main()
