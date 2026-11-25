from __future__ import annotations

import hashlib
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import data_access
import search_crypto_r14 as r14
import search_crypto_r27_bos_fvg_confluence as r27
import search_crypto_r29_bos_taker_flow as r29
from crypto import Bar, Zone, r4_zones


def minute_fixture(start=0, count=240, taker_share=0.6):
    rows = []
    for index in range(count):
        price = 100.0
        quote = 10.0
        rows.append({
            "open_time": start + index * r29.MINUTE_MS,
            "open": price, "high": price + 1, "low": price - 1,
            "close": price, "volume": 1.0, "quote_volume": quote,
            "taker_buy_quote_volume": quote * taker_share,
        })
    return pd.DataFrame(rows)


class R29TakerFlowTests(unittest.TestCase):
    def bar(self, timestamp=0):
        return Bar(timestamp, 100.0, 101.0, 99.0, 100.0, 240.0)

    def test_directional_threshold_and_neutral_tie_are_fixed(self):
        self.assertTrue(r29._flow_passes(0.500001, "long"))
        self.assertFalse(r29._flow_passes(0.5, "long"))
        self.assertTrue(r29._flow_passes(0.499999, "short"))
        self.assertFalse(r29._flow_passes(0.5, "short"))
        self.assertFalse(r29._flow_passes(0.8, "flat"))

    def test_invalid_ratio_fails_closed(self):
        for value in (-0.01, 1.01, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                r29._flow_passes(value, "long")

    def test_complete_240_minutes_reaggregate_and_fingerprint_deterministically(self):
        frame = minute_fixture()
        first = r29._aggregate_4h_group(frame, self.bar())
        second = r29._aggregate_4h_group(frame, self.bar())
        self.assertEqual(first["buy_share"], 0.6)
        self.assertEqual(first, second)
        self.assertEqual(len(frame), 240)

    def test_missing_duplicate_or_out_of_order_minutes_fail_closed(self):
        frame = minute_fixture()
        with self.assertRaisesRegex(ValueError, "240 ordered consecutive"):
            r29._aggregate_4h_group(frame.iloc[:-1], self.bar())
        duplicate = pd.concat([frame, frame.iloc[[10]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "240 ordered consecutive"):
            r29._aggregate_4h_group(duplicate, self.bar())
        reversed_frame = frame.iloc[::-1].reset_index(drop=True)
        with self.assertRaisesRegex(ValueError, "240 ordered consecutive"):
            r29._aggregate_4h_group(reversed_frame, self.bar())

    def test_fractional_nan_and_boolean_timestamps_fail_closed(self):
        fractional = minute_fixture()
        fractional["open_time"] = fractional["open_time"].astype(float)
        fractional.loc[1, "open_time"] = 60_000.5
        with self.assertRaisesRegex(ValueError, "finite integer millisecond"):
            r29._aggregate_4h_group(fractional, self.bar())
        with self.assertRaisesRegex(ValueError, "finite integer millisecond"):
            r29._minute_timestamp(float("nan"))
        with self.assertRaisesRegex(ValueError, "finite integer millisecond"):
            r29._minute_timestamp(True)

    def test_cutoff_and_future_rows_cannot_change_closed_bos_flow(self):
        frame = minute_fixture()
        future = minute_fixture(start=r29.BAR_MS, count=240, taker_share=0.99)
        expected = r29._aggregate_4h_group(frame, self.bar())
        changed = pd.concat([frame, future], ignore_index=True)
        actual = r29._aggregate_4h_group(changed, self.bar())
        self.assertEqual(expected["buy_share"], actual["buy_share"])
        cutoff_before_close = pd.Timestamp("1970-01-01T03:59:00Z").value // 1_000_000
        with self.assertRaisesRegex(ValueError, "after the preregistered TRAIN cutoff"):
            r29._aggregate_4h_group(
                frame, Bar(0, 100, 101, 99, 100, 240), cutoff_ms=cutoff_before_close)

    def test_price_and_volume_reaggregation_mismatch_fails_closed(self):
        frame = minute_fixture()
        wrong_price = Bar(0, 100.0, 101.0, 99.0, 101.0, 240.0)
        with self.assertRaisesRegex(ValueError, "disagrees with cached 4h close"):
            r29._aggregate_4h_group(frame, wrong_price)
        wrong_volume = Bar(0, 100.0, 101.0, 99.0, 100.0, 241.0)
        with self.assertRaisesRegex(ValueError, "disagrees with cached 4h volume"):
            r29._aggregate_4h_group(frame, wrong_volume)

    def test_invalid_taker_quote_and_zero_quote_fail_closed(self):
        over = minute_fixture()
        over.loc[0, "taker_buy_quote_volume"] = 11.0
        with self.assertRaisesRegex(ValueError, "outside total quote"):
            r29._aggregate_4h_group(over, self.bar())
        zero = minute_fixture()
        zero["quote_volume"] = 0.0
        zero["taker_buy_quote_volume"] = 0.0
        with self.assertRaisesRegex(ValueError, "total quote volume must be positive"):
            r29._aggregate_4h_group(zero, self.bar())

    def test_prereg_hash_and_single_fixed_configuration(self):
        self.assertEqual(r29._PREREG_SHA,
                         "065c152b5898d691f0278c37b2ee5ecc9a54a43dc88716afb717c39bcf5773ab")
        self.assertEqual(hashlib.sha256(r29.PREREG_PATH.read_bytes()).hexdigest(), r29._PREREG_SHA)
        self.assertEqual(r29._MASTER_SHA,
                         "fa77fa8fa539ddf6880b53cdfbdf9365937579ea1eb603024322b1166f2cb46a")
        self.assertIn("R29는 R14", r29.MASTER_PATH.read_text(encoding="utf-8"))
        self.assertEqual(r29.CONFIG["long_buy_share_min_exclusive"], 0.5)
        self.assertEqual(r29.CONFIG["short_buy_share_max_exclusive"], 0.5)
        self.assertIn("search_crypto_r29_bos_taker_flow.py", r29.CODE_FILES)

    def test_month_picker_uses_only_months_with_train_bars(self):
        bars = [self.bar(0), self.bar(31 * 24 * 60 * 60_000)]
        self.assertEqual(r29._months_for_bars(bars), ["1970-01", "1970-02"])

    def test_flow_loader_reads_only_required_month_and_fingerprints_aggregates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external/crypto/binance/um_klines_1m/BTCUSDT"
            source.mkdir(parents=True)
            minute_fixture().to_parquet(source / "1970-01.parquet", index=False)
            bar = self.bar()
            mapping, fingerprint, stats = r29._build_flow_map(
                root, [("BTCUSDT", [bar], {}, 0)])
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(mapping[id(bar)], 0.6)
        self.assertEqual(stats["symbols"], 1)
        self.assertEqual(stats["four_hour_bars"], 1)
        self.assertEqual(stats["matched_flow_bars"], 1)
        self.assertEqual(stats["minutes_read"], 240)

    def test_flow_loader_reads_both_files_for_month_boundary_bars(self):
        january = pd.Timestamp("1970-01-31T20:00:00Z").value // 1_000_000
        bars = [self.bar(january), self.bar(january + r29.BAR_MS)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external/crypto/binance/um_klines_1m/BTCUSDT"
            source.mkdir(parents=True)
            minute_fixture(start=bars[0].timestamp).to_parquet(
                source / "1970-01.parquet", index=False)
            minute_fixture(start=bars[1].timestamp).to_parquet(
                source / "1970-02.parquet", index=False)
            mapping, _fingerprint, stats = r29._build_flow_map(
                root, [("BTCUSDT", bars, {}, 0)])
        self.assertEqual(mapping[id(bars[0])], 0.6)
        self.assertEqual(mapping[id(bars[1])], 0.6)
        self.assertEqual(stats["source_files"], 2)
        self.assertEqual(stats["matched_flow_bars"], 2)

    def test_flow_loader_missing_month_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "one-minute source missing"):
                r29._build_flow_map(Path(directory), [("BTCUSDT", [self.bar()], {}, 0)])

    def test_flow_loader_filters_after_cutoff_rows_before_returning_them(self):
        cutoff_bar = 1_699_272_000_000  # 2023-11-06 12:00 UTC; closes at cutoff.
        bar = Bar(cutoff_bar, 100.0, 101.0, 99.0, 100.0, 240.0)
        before = minute_fixture(start=cutoff_bar)
        after = minute_fixture(start=r29.CUTOFF_MS, count=2, taker_share=0.99)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external/crypto/binance/um_klines_1m/BTCUSDT"
            source.mkdir(parents=True)
            pd.concat([before, after], ignore_index=True).to_parquet(
                source / "2023-11.parquet", index=False)
            mapping, _fingerprint, stats = r29._build_flow_map(
                root, [("BTCUSDT", [bar], {}, 0)])
        self.assertEqual(mapping[id(bar)], 0.6)
        self.assertEqual(stats["minutes_read"], 240)

    def test_rejected_later_zone_does_not_replace_earlier_flow_qualified_zone(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(42)]
        four_hour[27] = Bar(27 * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
        four_hour[28] = Bar(28 * r14.ZONE_DURATION_MS, 103, 104, 102, 103.5, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 110, 111, 109, 110, 1000)
                  for i in range(len(four_hour) * 4)]
        zones = [Zone(27, 24, "long", 98, 99, 1),
                 Zone(28, 25, "long", 98, 99, 1)]
        flow = {id(four_hour[27]): 0.6, id(four_hour[28]): 0.4}
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=zones):
            result = r29._trial_with_flow(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)], flow)
        self.assertEqual(result["flow_evaluated_zones"], 2)
        self.assertEqual(result["flow_qualified_zones"], 1)
        self.assertEqual(result["flow_rejected_zones"], 1)
        self.assertEqual(result["zones"], 1)
        self.assertEqual(result["superseding_zones_dropped"], 0)

    def test_filter_is_restored_after_detector_exception(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(4)]
        hourly = [Bar(i * r14.DURATION_MS, 100, 101, 99, 100, 1000)
                  for i in range(16)]
        original = r27._has_directional_fvg
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", side_effect=RuntimeError("synthetic detector error")):
            with self.assertRaisesRegex(RuntimeError, "synthetic detector error"):
                r29._trial_with_flow([("BTCUSDT", hourly, {}, 0)],
                                     [("BTCUSDT", four_hour, {}, 0)],
                                     {id(four_hour[0]): 0.6})
        self.assertIs(r27._has_directional_fvg, original)

    def test_ledger_counts_rows_and_refuses_duplicate_round(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=r29.common.FIELDS)
                writer.writeheader()
                writer.writerow({field: "" for field in r29.common.FIELDS})
            with patch.object(r29.common, "CSV_PATH", path):
                self.assertEqual(r29._ledger_state(), 1)
                with path.open("a", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=r29.common.FIELDS)
                    row = {field: "" for field in r29.common.FIELDS}
                    row["round"] = r29.ROUND
                    writer.writerow(row)
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    r29._ledger_state()

    def test_append_writes_one_complete_row_and_never_truncates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r29.common.FIELDS)
            with patch.object(r29.common, "CSV_PATH", path):
                r29._append({"status": "completed", "trades": 1}, "grid", "code", "fp",
                            r29.EXPECTED_N, r29.CONFIG)
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["round"], r29.ROUND)
            self.assertEqual(rows[0]["parameter_grid_hash"], "grid")

    def test_uncertain_append_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r29.common.FIELDS)
            original_size = path.stat().st_size
            with patch.object(r29.common, "CSV_PATH", path), \
                    patch.object(r29.os, "write", side_effect=OSError("synthetic denied write")):
                with self.assertRaises(r29.AppendUncertainError):
                    r29._append({"status": "completed"}, "grid", "code", "fp",
                                r29.EXPECTED_N, r29.CONFIG)
            self.assertEqual(path.stat().st_size, original_size)

    def test_both_run_locks_are_exclusive_and_partial_lock_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_dir = root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            opened = r29._acquire_run_locks(root)
            self.assertEqual(len(opened), 2)
            with self.assertRaises(FileExistsError):
                r29._acquire_run_locks(root)
            r29._release_run_locks(opened)
            sentinel = lock_dir / ".ob_attrition_train_trials.lock"
            sentinel.write_text("owned elsewhere", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                r29._acquire_run_locks(root)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "owned elsewhere")

    def test_split_preflight_requires_every_fixed_bar_file_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            symbols = frozenset({"BTCUSDT"})
            expected_split = data_access.CRYPTO_COMMON_SPLIT_MS + max(
                data_access.TIMEFRAME_MS.values())
            records = {}
            for timeframe in ("1h", "4h"):
                folder = root / "cache/orderblock/bars" / timeframe
                folder.mkdir(parents=True)
                path = folder / "BTCUSDT.parquet"
                path.touch()
                records[str(path.resolve())] = {
                    "fixed": True, "split_timestamp": expected_split,
                }
            split_path = root / "cache/orderblock/crypto_splits_close_boundary.json"
            split_path.write_text(json.dumps(records), encoding="utf-8")
            before = split_path.stat().st_mtime_ns
            with patch.object(r29.r14, "_expected_symbols", return_value=symbols):
                digest, mtime = r29._split_cache_state(root, data_access)
            self.assertEqual(len(digest), 64)
            self.assertEqual(mtime, before)
            self.assertEqual(split_path.stat().st_mtime_ns, before)

    def test_actual_r14_bos_detection_and_trade_simulator_receive_flow_filter(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(40)]
        four_hour[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1000)
        four_hour[22] = Bar(22 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1000)
        four_hour[24] = Bar(24 * r14.ZONE_DURATION_MS, 100, 112, 100, 111, 1000)
        self.assertEqual(len(r4_zones(four_hour, "bos_origin")), 1)
        hourly = [Bar(i * r14.DURATION_MS, 120, 121, 119, 120, 1000)
                  for i in range(len(four_hour) * 4)]
        hourly[100] = Bar(100 * r14.DURATION_MS, 100.7, 101.3, 100.6, 101.1, 1000)
        hourly[101] = Bar(101 * r14.DURATION_MS, 101.1, 101.2, 100.9, 101.0, 1000)
        hourly[102] = Bar(102 * r14.DURATION_MS, 101.0, 104.0, 100.9, 103.5, 1000)
        flow = {id(four_hour[24]): 0.6}
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r29._trial_with_flow(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)], flow)
        self.assertEqual(result["raw_bos_events"], 1)
        self.assertEqual(result["flow_qualified_zones"], 1)
        self.assertEqual(result["flow_rejected_zones"], 0)
        self.assertEqual(result["zones"], 1)
        self.assertEqual(result["total_trades"], 1)

    def test_missing_feature_for_a_bos_zone_is_not_silently_dropped(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(40)]
        zone = Zone(24, 20, "long", 98, 99, 1)
        hourly = [Bar(i * r14.DURATION_MS, 120, 121, 119, 120, 1000)
                  for i in range(len(four_hour) * 4)]
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[zone]):
            with self.assertRaisesRegex(ValueError, "no validated taker-flow"):
                r29._trial_with_flow(
                    [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)], {})


if __name__ == "__main__":
    unittest.main()
