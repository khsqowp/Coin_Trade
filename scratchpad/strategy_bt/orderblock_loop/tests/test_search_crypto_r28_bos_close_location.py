from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import search_crypto_r14 as r14
import search_crypto_r28_bos_close_location as r28
import search_crypto_r19_match_attrition_audit as r19
from crypto import Bar, Zone, r4_zones


class R28CloseLocationTests(unittest.TestCase):
    @staticmethod
    def bar(low=90.0, high=110.0, close=105.0, complete=True, open_=100.0):
        return Bar(0, open_, high, low, close, 1_000.0, complete)

    def test_long_and_short_extreme_close_are_directional(self):
        self.assertTrue(r28._close_location_passes([self.bar(close=105)], 0, "long"))
        self.assertFalse(r28._close_location_passes([self.bar(close=105)], 0, "short"))
        self.assertTrue(r28._close_location_passes([self.bar(close=95)], 0, "short"))
        self.assertFalse(r28._close_location_passes([self.bar(close=95)], 0, "long"))

    def test_inclusive_quartile_boundaries_and_values_just_outside(self):
        self.assertTrue(r28._close_location_passes([self.bar(close=105)], 0, "long"))
        self.assertFalse(r28._close_location_passes([self.bar(close=104.99)], 0, "long"))
        self.assertTrue(r28._close_location_passes([self.bar(close=95)], 0, "short"))
        self.assertFalse(r28._close_location_passes([self.bar(close=95.01)], 0, "short"))

    def test_zero_range_bad_ohlc_and_incomplete_bars_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "range must be positive"):
            r28._close_location_passes([self.bar(100, 100, 100)], 0, "long")
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            r28._close_location_passes([self.bar(100, 110, 99)], 0, "long")
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            r28._close_location_passes([self.bar(100, 110, 108, open_=99)], 0, "long")
        with self.assertRaisesRegex(ValueError, "finite numeric"):
            r28._close_location_passes([self.bar(close=float("nan"))], 0, "long")
        self.assertFalse(r28._close_location_passes([self.bar(close=108, complete=False)], 0, "long"))

    def test_invalid_index_and_direction_fail_closed(self):
        bars = [self.bar()]
        for index, direction in ((-1, "long"), (1, "long"), (0, "flat")):
            self.assertFalse(r28._close_location_passes(bars, index, direction))

    def test_preregistration_hashes_are_pinned_and_r14_contract_is_a_hashed_dependency(self):
        self.assertEqual(hashlib.sha256(r28.PREREG_PATH.read_bytes()).hexdigest(), r28._PREREG_SHA)
        self.assertEqual(r28._MASTER_SHA,
                         "34de50d5dc0b4ba5c12766f678ef6286e0b43d5fa844177513ba67f8623712b7")
        self.assertNotEqual(hashlib.sha256(r28.MASTER_PATH.read_bytes()).hexdigest(), r28._MASTER_SHA)
        self.assertIn("R29는 R14", r28.MASTER_PATH.read_text(encoding="utf-8"))
        self.assertIn("PREREG_R14_FIRST_RETEST_MIDPOINT_CONFIRM.md", r28.CODE_FILES)

    def test_denominator_mismatch_config_and_grid_use_actual_prior_row_count(self):
        config = r28._config_for_prior_rows(1689)
        self.assertEqual(config["bonferroni_n"], 1690)
        self.assertNotEqual(r28._grid_hash(config), r28._grid_hash(r28.CONFIG))

    def test_future_bars_cannot_change_closed_bos_classification(self):
        bars = [self.bar(close=106), self.bar(close=92)]
        expected = r28._close_location_passes(bars, 0, "long")
        bars[1] = self.bar(low=70, high=130, close=70)
        self.assertEqual(r28._close_location_passes(bars, 0, "long"), expected)

    def test_r14_real_mapper_lifecycle_and_simulator_use_filtered_zone(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100.5, 1000)
                     for i in range(42)]
        four_hour[28] = Bar(28 * r14.ZONE_DURATION_MS, 103, 104, 102, 103.5, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 100, 101, 99, 100.5, 1000)
                  for i in range(len(four_hour) * 4)]
        hourly[117] = Bar(117 * r14.DURATION_MS, 99, 99.2, 98.2, 98.8, 1000)
        hourly[118] = Bar(118 * r14.DURATION_MS, 98.9, 99.2, 98.5, 99.0, 1000)
        hourly[119] = Bar(119 * r14.DURATION_MS, 99, 99.2, 98.5, 99.0, 1000)
        hourly[120] = Bar(120 * r14.DURATION_MS, 99, 100, 97.5, 99.8, 1000)
        zone = Zone(28, 24, "long", 98, 99, 1)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[zone]):
            result = r28._trial_with_close_location(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["close_location_qualified_zones"], 1)
        self.assertEqual(result["close_location_rejected_zones"], 0)
        self.assertEqual(result["zones"], 1)
        self.assertEqual(result["total_trades"], 1)

    def test_non_extreme_bos_zone_is_rejected_before_r14_lifecycle(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(42)]
        four_hour[28] = Bar(28 * r14.ZONE_DURATION_MS, 103, 104, 102, 102.5, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 100, 101, 99, 100, 1000)
                  for i in range(len(four_hour) * 4)]
        zone = Zone(28, 24, "long", 98, 99, 1)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[zone]):
            result = r28._trial_with_close_location(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["close_location_qualified_zones"], 0)
        self.assertEqual(result["close_location_rejected_zones"], 1)
        self.assertEqual(result["zones"], 0)
        self.assertEqual(result["total_trades"], 0)

    def test_actual_r4_bos_detector_feeds_the_close_location_filter(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(40)]
        four_hour[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1000)
        four_hour[22] = Bar(22 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1000)
        four_hour[24] = Bar(24 * r14.ZONE_DURATION_MS, 100, 112, 100, 111, 1000)
        self.assertEqual(len(r4_zones(four_hour, "bos_origin")), 1)
        hourly = [Bar(i * r14.DURATION_MS, 120, 121, 119, 120, 1000)
                  for i in range(len(four_hour) * 4)]
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r28._trial_with_close_location(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["raw_bos_events"], 1)
        self.assertEqual(result["bos_origin_zones"], 1)
        self.assertEqual(result["close_location_qualified_zones"], 1)

    def test_real_bos_detection_flows_through_mapping_lifecycle_and_trade_simulator(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(40)]
        four_hour[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1000)
        four_hour[22] = Bar(22 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1000)
        four_hour[24] = Bar(24 * r14.ZONE_DURATION_MS, 100, 112, 100, 111, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 120, 121, 119, 120, 1000)
                  for i in range(len(four_hour) * 4)]
        hourly[100] = Bar(100 * r14.DURATION_MS, 100.7, 101.3, 100.6, 101.1, 1000)
        hourly[101] = Bar(101 * r14.DURATION_MS, 101.1, 101.2, 100.9, 101.0, 1000)
        hourly[102] = Bar(102 * r14.DURATION_MS, 101.0, 104.0, 100.9, 103.5, 1000)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r28._trial_with_close_location(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["raw_bos_events"], 1)
        self.assertEqual(result["close_location_qualified_zones"], 1)
        self.assertEqual(result["zones"], 1)
        self.assertEqual(result["first_touches"], 1)
        self.assertEqual(result["total_trades"], 1)

    def test_invalid_ohlc_in_input_fails_closed_before_r28_filtering(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(40)]
        four_hour[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1000)
        four_hour[22] = Bar(22 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1000)
        four_hour[24] = Bar(24 * r14.ZONE_DURATION_MS, 100, 112, 100, 111, 1000)
        four_hour[25] = Bar(25 * r14.ZONE_DURATION_MS, 102, 101, 99, 100, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 120, 121, 119, 120, 1000)
                  for i in range(len(four_hour) * 4)]
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            with self.assertRaisesRegex(ValueError, "inconsistent OHLC"):
                r28._trial_with_close_location(
                    [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])

    def test_zero_range_bos_candle_fails_closed_in_real_detector_pipeline(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(40)]
        four_hour[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1000)
        four_hour[22] = Bar(22 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1000)
        four_hour[24] = Bar(24 * r14.ZONE_DURATION_MS, 111, 111, 111, 111, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 120, 121, 119, 120, 1000)
                  for i in range(len(four_hour) * 4)]
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            with self.assertRaisesRegex(ValueError, "range must be positive"):
                r28._trial_with_close_location(
                    [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])

    def test_rejected_later_zone_does_not_displace_active_qualified_zone(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(42)]
        four_hour[27] = Bar(27 * r14.ZONE_DURATION_MS, 100, 101, 99, 100.75, 1000)
        four_hour[28] = Bar(28 * r14.ZONE_DURATION_MS, 103, 104, 102, 102.5, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 110, 111, 109, 110, 1000)
                  for i in range(len(four_hour) * 4)]
        zones = [Zone(27, 24, "long", 98, 99, 1),
                 Zone(28, 25, "long", 98, 99, 1)]
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=zones):
            result = r28._trial_with_close_location(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["close_location_qualified_zones"], 1)
        self.assertEqual(result["close_location_rejected_zones"], 1)
        self.assertEqual(result["zones"], 1)
        self.assertEqual(result["superseding_zones_dropped"], 0)

    def test_ledger_count_uses_data_rows_and_refuses_duplicate_round(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=r28.common.FIELDS)
                writer.writeheader()
                row = {field: "" for field in r28.common.FIELDS}
                row["round"] = "R27-coin"
                writer.writerow(row)
            with patch.object(r28.common, "CSV_PATH", path):
                self.assertEqual(r28._ledger_state(), 1)
                with path.open("a", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=r28.common.FIELDS)
                    row["round"] = r28.ROUND
                    writer.writerow(row)
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    r28._ledger_state()

    def test_append_writes_one_row_without_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r28.common.FIELDS)
            with patch.object(r28.common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"):
                r28._append({"status": "completed"}, "grid", "code", "fingerprint", 1685, r28.CONFIG)
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["round"], r28.ROUND)
            self.assertEqual(rows[0]["parameter_grid_hash"], "grid")

    def test_uncertain_append_error_does_not_retry_or_truncate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r28.common.FIELDS)
            with patch.object(r28.common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r28.os, "write", side_effect=OSError("simulated")) as write:
                with self.assertRaises(r28.AppendUncertainError):
                    r28._append({"status": "completed"}, "grid", "code", "fingerprint", 1685, r28.CONFIG)
                self.assertEqual(write.call_count, 1)
            with path.open(newline="", encoding="utf-8") as stream:
                self.assertEqual(sum(1 for _ in csv.reader(stream)), 1)

    def test_both_run_locks_are_exclusive_and_partial_acquire_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as directory:
            data_root = Path(directory)
            lock_dir = data_root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            opened = r28._acquire_run_locks(data_root)
            self.assertEqual(len(opened), 2)
            with self.assertRaises(FileExistsError):
                r28._acquire_run_locks(data_root)
            r28._release_run_locks(opened)
            self.assertFalse((lock_dir / ".cointrade_train_trials.lock").exists())
            self.assertFalse((lock_dir / ".ob_attrition_train_trials.lock").exists())

    def test_lock_acquire_failure_preserves_preexisting_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            data_root = Path(directory)
            lock_dir = data_root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            second = lock_dir / ".ob_attrition_train_trials.lock"
            second.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                r28._acquire_run_locks(data_root)
            self.assertFalse((lock_dir / ".cointrade_train_trials.lock").exists())
            self.assertEqual(second.read_text(encoding="utf-8"), "existing")

    def test_split_manifest_preflight_requires_all_fixed_1h_4h_keys_without_writing(self):
        class SplitSpec:
            CRYPTO_COMMON_SPLIT_MS = 1_000
            TIMEFRAME_MS = {"1h": 3_600_000, "4h": 14_400_000}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = {}
            expected = SplitSpec.CRYPTO_COMMON_SPLIT_MS + max(SplitSpec.TIMEFRAME_MS.values())
            for timeframe in ("1h", "4h"):
                bars_dir = root / "cache/orderblock/bars" / timeframe
                bars_dir.mkdir(parents=True)
                for symbol in r14._expected_symbols():
                    data_file = bars_dir / f"{symbol}.parquet"
                    data_file.touch()
                    records[str(data_file.resolve())] = {
                        "split_timestamp": expected, "fixed": True,
                    }
            manifest = root / "cache/orderblock/crypto_splits_close_boundary.json"
            original = json.dumps(records, sort_keys=True).encode()
            manifest.write_bytes(original)
            before = manifest.stat().st_mtime_ns
            sha, mtime = r28._split_cache_state(root, SplitSpec)
            self.assertEqual(sha, hashlib.sha256(original).hexdigest())
            self.assertEqual(mtime, before)
            self.assertEqual(manifest.read_bytes(), original)
            records.pop(next(iter(records)))
            manifest.write_text(json.dumps(records), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing or inconsistent"):
                r28._split_cache_state(root, SplitSpec)


if __name__ == "__main__":
    unittest.main()
