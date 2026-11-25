from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import search_crypto_r14 as r14
import search_crypto_r27_bos_fvg_confluence as r27
from crypto import Bar, FundingEvent, Zone


class R27FvgTests(unittest.TestCase):
    def bars(self, count=8):
        return [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1)
                for i in range(count)]

    def test_long_and_short_fvg_are_direction_symmetric_and_strict(self):
        bars = self.bars()
        bars[2] = Bar(bars[2].timestamp, 100, 101, 99, 100, 1)
        bars[4] = Bar(bars[4].timestamp, 103, 105, 102, 104, 1)
        self.assertTrue(r27._has_directional_fvg(bars, 4, "long"))
        self.assertFalse(r27._has_directional_fvg(bars, 4, "short"))
        bars[4] = Bar(bars[4].timestamp, 97, 98, 95, 96, 1)
        self.assertTrue(r27._has_directional_fvg(bars, 4, "short"))
        self.assertFalse(r27._has_directional_fvg(bars, 4, "long"))

    def test_equal_boundaries_are_rejected(self):
        bars = self.bars()
        bars[4] = Bar(bars[4].timestamp, 101, 104, 101, 103, 1)
        self.assertFalse(r27._has_directional_fvg(bars, 4, "long"))
        bars[4] = Bar(bars[4].timestamp, 98, 99, 96, 97, 1)
        self.assertFalse(r27._has_directional_fvg(bars, 4, "short"))

    def test_invalid_index_or_direction_fails_closed(self):
        bars = self.bars()
        self.assertFalse(r27._has_directional_fvg(bars, -1, "long"))
        self.assertFalse(r27._has_directional_fvg(bars, 1, "long"))
        self.assertFalse(r27._has_directional_fvg(bars, len(bars), "long"))
        self.assertFalse(r27._has_directional_fvg(bars, 4, "flat"))

    def test_fvg_requires_completed_contiguous_bos_segment(self):
        bars = self.bars()
        bars[2] = Bar(bars[2].timestamp, 100, 101, 99, 100, 1, complete=False)
        bars[4] = Bar(bars[4].timestamp, 103, 105, 102, 104, 1)
        self.assertFalse(r27._has_directional_fvg(bars, 4, "long"))
        bars = self.bars()
        bars[3] = Bar(bars[3].timestamp, 100, 101, 99, 100, 1, complete=False)
        bars[4] = Bar(bars[4].timestamp, 103, 105, 102, 104, 1)
        self.assertFalse(r27._has_directional_fvg(bars, 4, "long"))
        bars = self.bars()
        bars[2] = Bar(bars[2].timestamp, 100, 101, 99, 100, 1)
        bars[4] = Bar(bars[4].timestamp, 103, 105, 102, 104, 1)
        bars[3] = Bar(bars[3].timestamp + 1, 100, 101, 99, 100, 1)
        self.assertFalse(r27._has_directional_fvg(bars, 4, "long"))
        bars = self.bars()
        bars[4] = Bar(bars[4].timestamp, 103, 105, 102, 104, 1, complete=False)
        self.assertFalse(r27._has_directional_fvg(bars, 4, "long"))
        bars = self.bars()
        bars[2] = Bar(bars[2].timestamp, 100, 101, 99, 100, 1)
        bars[4] = Bar(4 * r14.ZONE_DURATION_MS + 1, 103, 105, 102, 104, 1)
        self.assertFalse(r27._has_directional_fvg(bars, 4, "long"))

    def test_future_bars_do_not_change_fvg_at_bos_close(self):
        bars = self.bars(12)
        bars[2] = Bar(bars[2].timestamp, 100, 101, 99, 100, 1)
        bars[5] = Bar(bars[5].timestamp, 103, 106, 102, 105, 1)
        baseline = r27._has_directional_fvg(bars, 5, "long")
        for index in range(6, len(bars)):
            bars[index] = Bar(bars[index].timestamp, 1, 10_000, 0.1, 9_000, 1)
        self.assertEqual(r27._has_directional_fvg(bars, 5, "long"), baseline)

    def test_filter_is_applied_before_activation_and_preserves_eligible_order(self):
        bars = self.bars()
        bars[2] = Bar(bars[2].timestamp, 100, 101, 99, 100, 1)
        bars[4] = Bar(bars[4].timestamp, 103, 105, 102, 104, 1)
        rejected = Zone(3, 1, "short", 99, 101, 2)
        accepted = Zone(4, 2, "long", 98, 99, 2)
        stats = {"raw_bos_events": 0, "bos_origin_zones": 0,
                 "fvg_qualified_zones": 0, "fvg_rejected_zones": 0}
        with patch.object(r14, "r4_zones", return_value=[rejected, accepted]):
            _original, builder = r27._filtered_zone_builder(stats)
            self.assertEqual(builder(bars, "bos_origin"), [accepted])
        self.assertEqual(stats, {"raw_bos_events": 0, "bos_origin_zones": 2,
                                 "fvg_qualified_zones": 1,
                                 "fvg_rejected_zones": 1})

    def test_raw_bos_event_count_is_separate_from_origin_zone_count(self):
        bars = self.bars(40)
        bars[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1)
        bars[22] = Bar(22 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1)
        bars[24] = Bar(24 * r14.ZONE_DURATION_MS, 100, 112, 100, 111, 1)
        self.assertEqual(r27._raw_bos_events(bars), 1)
        self.assertEqual(len(r14.r4_zones(bars, "bos_origin")), 1)

    def test_r14_real_mapper_simulator_cost_funding_and_stop_first_path(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100.5, 1000)
                     for i in range(42)]
        four_hour[26] = Bar(26 * r14.ZONE_DURATION_MS, 100, 101, 99, 100.5, 1000)
        four_hour[28] = Bar(28 * r14.ZONE_DURATION_MS, 103, 104, 102, 103.5, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 100, 101, 99, 100.5, 1000)
                  for i in range(len(four_hour) * 4)]
        hourly[117] = Bar(117 * r14.DURATION_MS, 99, 99.2, 98.2, 98.8, 1000)
        hourly[118] = Bar(118 * r14.DURATION_MS, 98.9, 99.2, 98.5, 99.0, 1000)
        hourly[119] = Bar(119 * r14.DURATION_MS, 99, 99.2, 98.5, 99.0, 1000)
        hourly[120] = Bar(120 * r14.DURATION_MS, 99, 100, 97.5, 99.8, 1000)
        zone = Zone(28, 24, "long", 98, 99, 1)
        funding = {hourly[119].timestamp: FundingEvent(
            hourly[119].timestamp, 0.001, hourly[119].open)}
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[zone]):
            result = r27._trial_with_fvg(
                [("BTCUSDT", hourly, funding, 0)],
                [("BTCUSDT", four_hour, {}, 0)],
            )
            without_funding = r27._trial_with_fvg(
                [("BTCUSDT", hourly, {}, 0)],
                [("BTCUSDT", four_hour, {}, 0)],
            )
        self.assertEqual(result["raw_bos_events"], 0)
        self.assertEqual(result["bos_origin_zones"], 1)
        self.assertEqual(result["fvg_qualified_zones"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 0)
        self.assertEqual(result["trades"], 1)
        self.assertLess(result["expectancy_bps"], 0)
        self.assertLess(result["expectancy_bps"], without_funding["expectancy_bps"])
        self.assertEqual(result["direction_attribution"]["long"]["trades"], 1)
        self.assertEqual(sum(v["trades"] for v in result["entry_year_attribution"].values()), 1)

    def test_nongap_zone_never_reaches_r14_lifecycle(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
                     for i in range(42)]
        hourly = [Bar(i * r14.DURATION_MS, 100, 101, 99, 100, 1000)
                  for i in range(len(four_hour) * 4)]
        rejected = Zone(28, 24, "long", 98, 99, 1)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[rejected]):
            result = r27._trial_with_fvg(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["raw_bos_events"], 0)
        self.assertEqual(result["bos_origin_zones"], 1)
        self.assertEqual(result["fvg_rejected_zones"], 1)
        self.assertEqual(result["zones"], 0)
        self.assertEqual(result["total_trades"], 0)

    def test_rejected_zone_does_not_supersede_an_eligible_later_zone(self):
        four_hour = self.bars(42)
        four_hour[25] = Bar(25 * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1000)
        four_hour[27] = Bar(27 * r14.ZONE_DURATION_MS, 100, 101, 100, 100.5, 1000)
        four_hour[28] = Bar(28 * r14.ZONE_DURATION_MS, 103, 104, 102, 103.5, 1000)
        hourly = [Bar(i * r14.DURATION_MS, 110, 111, 109, 110, 1000)
                  for i in range(len(four_hour) * 4)]
        zones = [Zone(27, 24, "long", 98, 99, 1),
                 Zone(28, 25, "long", 98, 99, 1)]
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=zones):
            result = r27._trial_with_fvg(
                [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", four_hour, {}, 0)])
        self.assertEqual(result["fvg_rejected_zones"], 1)
        self.assertEqual(result["fvg_qualified_zones"], 1)
        self.assertEqual(result["zones"], 1)
        self.assertEqual(result["superseding_zones_dropped"], 0)

    def test_activation_count_matches_r14_expiry_bar_reprocessing(self):
        bars = [Bar(i * r14.DURATION_MS, 110, 111, 109, 110, 1000)
                for i in range(60)]
        zones = {0: Zone(0, 0, "long", 98, 99, 1),
                 r14.DEADLINE + 1: Zone(r14.DEADLINE + 1, 1, "long", 97, 98, 1)}
        activated = r27._count_activated_zones(bars, {}, zones)
        _trades, audit = r14._simulate_segment(bars, {}, zones)
        self.assertEqual(activated, 2)
        self.assertEqual(audit["zones"], 2)
        self.assertEqual(audit["superseding_zones_dropped"], 1)

    def test_ledger_state_counts_rows_and_refuses_duplicate_r27(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=r27.common.FIELDS)
                writer.writeheader()
                writer.writerow({field: "" for field in r27.common.FIELDS})
            with patch.object(r27.common, "CSV_PATH", path):
                self.assertEqual(r27._ledger_state(), 1)
                with path.open("a", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=r27.common.FIELDS)
                    row = {field: "" for field in r27.common.FIELDS}
                    row["round"] = r27.ROUND
                    writer.writerow(row)
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    r27._ledger_state()

    def test_append_writes_one_complete_synthetic_row_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r27.common.FIELDS)
            with patch.object(r27.common, "CSV_PATH", path):
                r27._append({"status": "completed", "trades": 1}, "grid", "code", "fp")
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["round"], r27.ROUND)
        self.assertEqual(rows[0]["parameter_grid_hash"], "grid")
        self.assertEqual(rows[0]["code_sha256"], "code")

    def test_write_oserror_is_uncertain_and_does_not_retry_or_truncate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r27.common.FIELDS)
            original_size = path.stat().st_size
            with patch.object(r27.common, "CSV_PATH", path), \
                    patch.object(r27.os, "write", side_effect=OSError("simulated write failure")):
                with self.assertRaises(r27.AppendUncertainError):
                    r27._append({"status": "completed"}, "grid", "code", "fp")
            self.assertEqual(path.stat().st_size, original_size)

    def test_close_oserror_after_write_is_uncertain_and_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r27.common.FIELDS)
            original_close = r27.os.close

            def close_then_raise(fd):
                original_close(fd)
                raise OSError("simulated close failure")

            with patch.object(r27.common, "CSV_PATH", path), \
                    patch("search_crypto_r19_match_attrition_audit._assert_no_ledger_writer"), \
                    patch.object(r27.os, "close", side_effect=close_then_raise):
                with self.assertRaises(r27.AppendUncertainError):
                    r27._append({"status": "completed"}, "grid", "code", "fp")
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["round"], r27.ROUND)

    def test_denominator_mismatch_records_sentinel_without_loading_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(r27.common.FIELDS)
            data_access = type("DataAccessSentinel", (), {
                "iter_train_bars": staticmethod(
                    lambda **_kwargs: (_ for _ in ()).throw(AssertionError("market data accessed")))
            })()
            with patch.object(r27.common, "CSV_PATH", path), \
                    patch.object(r27, "_ledger_state", return_value=0), \
                    patch("search_crypto_r19_match_attrition_audit._assert_no_ledger_writer"), \
                    patch.dict(sys.modules, {"data_access": data_access}):
                with self.assertRaisesRegex(RuntimeError, "denominator mismatch"):
                    r27._run_locked()
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        metric = json.loads(rows[0]["metric"])
        self.assertEqual(metric["status"], "failed_before_data_access")
        self.assertEqual(metric["bonferroni_denominator"], 1)

    def test_both_shared_writer_lock_families_are_held_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_dir = root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            opened = r27._acquire_run_locks(root)
            paths = [path for path, _fd in opened]
            self.assertEqual({path.name for path in paths}, {
                ".cointrade_train_trials.lock", ".ob_attrition_train_trials.lock"})
            with self.assertRaises(FileExistsError):
                r27._acquire_run_locks(root)
            self.assertTrue(all(path.exists() for path in paths))
            r27._release_run_locks(opened)
            self.assertTrue(all(not path.exists() for path in paths))


if __name__ == "__main__":
    unittest.main()
