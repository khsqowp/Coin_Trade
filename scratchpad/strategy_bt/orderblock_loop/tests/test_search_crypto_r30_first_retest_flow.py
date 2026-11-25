from __future__ import annotations

import hashlib
import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import search_crypto_r14 as r14
import search_crypto_r30_first_retest_flow as r30
import search_crypto_r29_bos_taker_flow as r29
import search_crypto as common
from crypto import Bar, Zone


def minute_fixture(start=0, count=60, taker_share=0.6):
    rows = []
    for i in range(count):
        rows.append({
            "open_time": start + i * r30.MINUTE_MS,
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
            "volume": 1.0, "quote_volume": 10.0,
            "taker_buy_quote_volume": 10.0 * taker_share,
        })
    return pd.DataFrame(rows)


class R30FirstRetestFlowTests(unittest.TestCase):
    def bar(self, timestamp=0):
        return Bar(timestamp, 100.0, 101.0, 99.0, 100.0, 60.0)

    def test_direction_thresholds_are_fixed_and_ties_reject(self):
        self.assertTrue(r30._flow_passes(0.500001, "long"))
        self.assertFalse(r30._flow_passes(0.5, "long"))
        self.assertTrue(r30._flow_passes(0.499999, "short"))
        self.assertFalse(r30._flow_passes(0.5, "short"))
        self.assertFalse(r30._flow_passes(0.8, "flat"))

    def test_invalid_flow_ratio_fails_closed(self):
        for value in (-0.01, 1.01, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                r30._flow_passes(value, "long")

    def test_sixty_minutes_reaggregate_and_fingerprint_values(self):
        frame = minute_fixture()
        first = r30._aggregate_hour_group(frame, self.bar())
        self.assertEqual(first["buy_share"], 0.6)
        self.assertEqual(first["volume"], 60.0)
        self.assertEqual(first["quote_volume"], 600.0)

    def test_missing_duplicate_reversed_and_misaligned_minutes_fail(self):
        incomplete = minute_fixture().iloc[:-1]
        with self.assertRaisesRegex(ValueError, "60 ordered consecutive"):
            r30._aggregate_hour_group(incomplete, self.bar())
        duplicate = pd.concat([minute_fixture(), minute_fixture().iloc[[4]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "60 ordered consecutive"):
            r30._aggregate_hour_group(duplicate, self.bar())
        reversed_frame = minute_fixture().iloc[::-1].reset_index(drop=True)
        with self.assertRaisesRegex(ValueError, "60 ordered consecutive"):
            r30._aggregate_hour_group(reversed_frame, self.bar())
        shifted = minute_fixture(start=1)
        with self.assertRaisesRegex(ValueError, "60 ordered consecutive"):
            r30._aggregate_hour_group(shifted, self.bar())

    def test_fractional_boolean_and_nan_timestamps_fail(self):
        for value in (60_000.5, True, float("nan")):
            frame = minute_fixture()
            frame["open_time"] = frame["open_time"].astype(object)
            frame.loc[0, "open_time"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                r30._aggregate_hour_group(frame, self.bar())

    def test_cutoff_excludes_later_minutes_and_rejects_unclosed_confirmation(self):
        frame = pd.concat([minute_fixture(), minute_fixture(start=r30.HOUR_MS,
                             taker_share=0.99)], ignore_index=True)
        first = r30._aggregate_hour_group(frame, self.bar())
        self.assertEqual(first["buy_share"], 0.6)
        with self.assertRaisesRegex(ValueError, "after the preregistered cutoff"):
            r30._aggregate_hour_group(frame, self.bar(), cutoff_ms=r30.HOUR_MS - 1)

    def test_ohlc_base_volume_mismatch_and_invalid_volume_fail_closed(self):
        wrong_close = Bar(0, 100.0, 101.0, 99.0, 101.0, 60.0)
        with self.assertRaisesRegex(ValueError, "disagrees with cached 1h close"):
            r30._aggregate_hour_group(minute_fixture(), wrong_close)
        wrong_volume = Bar(0, 100.0, 101.0, 99.0, 100.0, 61.0)
        with self.assertRaisesRegex(ValueError, "disagrees with cached 1h volume"):
            r30._aggregate_hour_group(minute_fixture(), wrong_volume)
        invalid = minute_fixture()
        invalid.loc[0, "taker_buy_quote_volume"] = 11.0
        with self.assertRaisesRegex(ValueError, "outside total"):
            r30._aggregate_hour_group(invalid, self.bar())

    def test_zero_quote_and_negative_or_nonfinite_volume_fail_closed(self):
        zero = minute_fixture()
        zero["quote_volume"] = 0.0
        zero["taker_buy_quote_volume"] = 0.0
        with self.assertRaisesRegex(ValueError, "quote volume must be positive"):
            r30._aggregate_hour_group(zero, self.bar())
        for value in (-1.0, float("inf"), float("nan")):
            broken = minute_fixture()
            broken.loc[2, "volume"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                r30._aggregate_hour_group(broken, self.bar())

    def test_future_mutation_does_not_change_closed_hour_feature(self):
        before = minute_fixture()
        after = pd.concat([before, minute_fixture(start=r30.HOUR_MS,
                               taker_share=0.99)], ignore_index=True)
        self.assertEqual(r30._aggregate_hour_group(before, self.bar()),
                         r30._aggregate_hour_group(after, self.bar()))

    def test_hour_loader_reads_only_requested_month_and_hashes_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external/crypto/binance/um_klines_1m/BTCUSDT"
            source.mkdir(parents=True)
            path = source / "1970-01.parquet"
            path.touch()
            frame = minute_fixture()
            with patch.object(pd, "read_parquet", return_value=frame) as read:
                first, digest1, stats1 = r30._build_flow_map(
                    root, [("BTCUSDT", [self.bar()], {}, 0)])
                second, digest2, stats2 = r30._build_flow_map(
                    root, [("BTCUSDT", [self.bar()], {}, 0)])
            self.assertEqual(read.call_count, 2)
            self.assertEqual(list(first.values()), [0.6])
            self.assertEqual(digest1, digest2)
            self.assertEqual(stats1, stats2)

    def test_hour_loader_does_not_repair_unsorted_source_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external/crypto/binance/um_klines_1m/BTCUSDT"
            source.mkdir(parents=True)
            (source / "1970-01.parquet").touch()
            reversed_frame = minute_fixture().iloc[::-1].reset_index(drop=True)
            with patch.object(pd, "read_parquet", return_value=reversed_frame):
                with self.assertRaisesRegex(ValueError, "ordered consecutive"):
                    r30._build_flow_map(root, [("BTCUSDT", [self.bar()], {}, 0)])

    def test_hour_loader_missing_month_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, "one-minute source missing"):
                r30._build_flow_map(root, [("BTCUSDT", [self.bar()], {}, 0)])

    def test_hour_loader_rejects_post_cutoff_rows_even_if_reader_returns_them(self):
        bar = self.bar(r30.CUTOFF_MS - r30.HOUR_MS)
        frame = pd.concat([
            minute_fixture(start=bar.timestamp),
            minute_fixture(start=r30.CUTOFF_MS, count=1),
        ], ignore_index=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external/crypto/binance/um_klines_1m/BTCUSDT"
            source.mkdir(parents=True)
            month = datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc).strftime("%Y-%m")
            (source / f"{month}.parquet").touch()
            with patch.object(pd, "read_parquet", return_value=frame):
                with self.assertRaisesRegex(ValueError, "post-cutoff minute"):
                    r30._build_flow_map(root, [("BTCUSDT", [bar], {}, 0)])

    def test_month_boundary_uses_both_archives_without_cross_month_fill(self):
        first_ts = int(datetime(2020, 1, 31, 23, tzinfo=timezone.utc).timestamp() * 1000)
        second_ts = first_ts + r30.HOUR_MS
        january = minute_fixture(start=first_ts)
        february = minute_fixture(start=second_ts, taker_share=0.4)
        bars = [self.bar(first_ts), self.bar(second_ts)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "external/crypto/binance/um_klines_1m/BTCUSDT"
            folder.mkdir(parents=True)
            (folder / "2020-01.parquet").touch()
            (folder / "2020-02.parquet").touch()

            def read_parquet(path, **_kwargs):
                return january if path.name == "2020-01.parquet" else february

            with patch.object(pd, "read_parquet", side_effect=read_parquet) as read:
                features, _digest, stats = r30._build_flow_map(
                    root, [("BTCUSDT", bars, {}, 0)])
            self.assertEqual(read.call_count, 2)
            self.assertEqual(features[id(bars[0])], 0.6)
            self.assertEqual(features[id(bars[1])], 0.4)
            self.assertEqual(stats["flow_source_files"], 2)

    def test_actual_r14_first_touch_flow_filter_and_consumption(self):
        bars = [
            Bar(i * r14.DURATION_MS, 100.0, 101.0, 99.0, 100.0, 1.0)
            for i in range(5)
        ]
        bars[1] = Bar(r14.DURATION_MS, 100.0, 101.0, 99.5, 100.5, 1.0)
        bars[2] = Bar(2 * r14.DURATION_MS, 100.5, 102.0, 100.4, 101.5, 1.0)
        bars[3] = Bar(3 * r14.DURATION_MS, 101.5, 101.6, 100.2, 100.5, 1.0)
        bars[4] = Bar(4 * r14.DURATION_MS, 100.5, 101.0, 100.4, 100.8, 1.0)
        zone = Zone(0, 0, "long", 99.0, 101.0, 1.0)
        four_hour = [Bar(0, 100.0, 101.0, 99.0, 100.0, 4.0)]
        mapper = lambda _s1, _s4: ([{0: zone}], 0)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "_zones_on_confirmation_segments", side_effect=mapper):
            accepted = r30._trial_with_flow(
                [("BTCUSDT", bars, {}, 0)], [("BTCUSDT", four_hour, {}, 0)],
                {id(bars[1]): 0.6})
            rejected = r30._trial_with_flow(
                [("BTCUSDT", bars, {}, 0)], [("BTCUSDT", four_hour, {}, 0)],
                {id(bars[1]): 0.4})
        self.assertEqual(accepted["flow_qualified_setups"], 1)
        self.assertEqual(accepted["total_trades"], 1)
        self.assertEqual(rejected["flow_rejected_setups"], 1)
        self.assertEqual(rejected["first_touches"], 1)
        self.assertEqual(rejected["total_trades"], 0)

    def test_monkeypatches_restore_after_failure(self):
        original_setup, original_segment = r14._make_setup, r14._simulate_segment
        with patch.object(r14, "_trial", side_effect=RuntimeError("synthetic")), \
                self.assertRaisesRegex(RuntimeError, "synthetic"):
            r30._trial_with_flow([], [], {})
        self.assertIs(r14._make_setup, original_setup)
        self.assertIs(r14._simulate_segment, original_segment)

    def test_prereg_hashes_and_single_fixed_threshold_are_explicit(self):
        self.assertEqual(r30.CONFIG["long_buy_share_min_exclusive"], 0.5)
        self.assertEqual(r30.CONFIG["short_buy_share_max_exclusive"], 0.5)
        self.assertEqual(r30.EXPECTED_ROWS + 1, r30.EXPECTED_N)
        self.assertIn("R30-coin", r30.MASTER_PATH.read_text(encoding="utf-8"))
        self.assertIn("search_crypto_r30_first_retest_flow.py", r30.CODE_FILES)
        self.assertEqual(hashlib.sha256(r30.PREREG_PATH.read_bytes()).hexdigest(),
                         r30._PREREG_SHA)
        # The master prereg grows as later rounds are appended. Preserve R30's
        # execution-time snapshot hash instead of comparing it to today's master.
        self.assertEqual(r30._MASTER_SHA,
                         "57a921ec273a619bfd065ed9892dc8b5185ba3c8e7f79d7f3c1f1d585477c5a4")
        self.assertIn("R31-coin", r30.MASTER_PATH.read_text(encoding="utf-8"))

    def test_ledger_state_counts_and_refuses_duplicate_round(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "R29-coin"})
            with patch.object(common, "CSV_PATH", path):
                self.assertEqual(r30._ledger_state(), 1)
                with path.open("a", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                    writer.writerow({"round": "R30-coin"})
                with self.assertRaisesRegex(RuntimeError, "R30 already exists"):
                    r30._ledger_state()

    def test_append_is_single_row_and_does_not_truncate_prior_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(common.FIELDS)
                csv.DictWriter(stream, fieldnames=common.FIELDS).writerow({"round": "prior"})
            before = path.read_bytes()
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r30.r19, "_assert_no_ledger_writer"):
                r30._append({"status": "completed"}, "grid", "code", "fingerprint",
                            r30.EXPECTED_N, r30.CONFIG)
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["round"], "prior")
            self.assertEqual(rows[1]["round"], "R30-coin")
            self.assertTrue(path.read_bytes().startswith(before))

    def test_uncertain_append_raises_without_automatic_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(common.FIELDS)
            original_size = path.stat().st_size
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r30.r19, "_assert_no_ledger_writer"), \
                    patch.object(r30.os, "write", side_effect=OSError("synthetic denied write")):
                with self.assertRaises(r30.AppendUncertainError):
                    r30._append({"status": "completed"}, "grid", "code", "fingerprint",
                                r30.EXPECTED_N, r30.CONFIG)
            self.assertEqual(path.stat().st_size, original_size)

    def test_close_failure_after_fsync_is_uncertain_and_never_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(common.FIELDS)
            real_close = r30.os.close

            def close_then_fail(fd):
                real_close(fd)
                raise OSError("synthetic close failure")

            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r30.r19, "_assert_no_ledger_writer"), \
                    patch.object(r30.os, "close", side_effect=close_then_fail):
                with self.assertRaises(r30.AppendUncertainError):
                    r30._append({"status": "completed"}, "grid", "code", "fingerprint",
                                r30.EXPECTED_N, r30.CONFIG)
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["round"], "R30-coin")

    def test_run_locks_are_exclusive_and_partial_foreign_lock_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_dir = root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            opened = r30._acquire_run_locks(root)
            with self.assertRaises(FileExistsError):
                r30._acquire_run_locks(root)
            r30._release_run_locks(opened)
            foreign = lock_dir / ".ob_attrition_train_trials.lock"
            foreign.write_text("foreign owner", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                r30._acquire_run_locks(root)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "foreign owner")

    def test_existing_r29_and_r30_are_not_reused_as_same_round(self):
        self.assertNotEqual(r29.ROUND, r30.ROUND)
        self.assertNotEqual(r29.CONFIG["experiment"], r30.CONFIG["experiment"])


if __name__ == "__main__":
    unittest.main()
