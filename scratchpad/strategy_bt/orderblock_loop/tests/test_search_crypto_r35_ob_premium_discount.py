from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r35_ob_premium_discount as r35
from crypto import Bar, FundingEvent, Zone

BAR = r14.ZONE_DURATION_MS
HOUR = r14.DURATION_MS


def bar(index, *, high=110.0, low=90.0, complete=True, timestamp=None):
    return Bar(index * BAR if timestamp is None else timestamp,
               100.0, high, low, 100.5, 1000.0, complete)


def range_bars(count=25):
    return [bar(i) for i in range(count)]


class PremiumDiscountTests(unittest.TestCase):
    def test_long_discount_and_short_premium_are_symmetric(self):
        bars = range_bars()
        self.assertEqual(r35._zone_location(bars, Zone(20, 18, "long", 89, 91, 1)),
                         (True, "accepted"))
        self.assertEqual(r35._zone_location(bars, Zone(20, 18, "short", 109, 111, 1)),
                         (True, "accepted"))
        self.assertEqual(r35._zone_location(bars, Zone(20, 18, "long", 109, 111, 1)),
                         (False, "not_discount"))
        self.assertEqual(r35._zone_location(bars, Zone(20, 18, "short", 89, 91, 1)),
                         (False, "not_premium"))

    def test_exact_range_midpoint_is_rejected_for_both_sides(self):
        bars = range_bars()
        for direction in ("long", "short"):
            self.assertFalse(r35._zone_location(
                bars, Zone(20, 18, direction, 99, 101, 1))[0])

    def test_exact_twenty_bar_window_excludes_bos_bar(self):
        bars = range_bars(24)
        bars[20] = bar(20, high=1000, low=1)
        zone = Zone(20, 18, "long", 89, 91, 1)
        expected = r35._zone_location(bars, zone)
        bars[20] = bar(20, high=20, low=10)
        self.assertEqual(r35._zone_location(bars, zone), expected)
        self.assertEqual(expected, (True, "accepted"))

    def test_future_bars_do_not_change_location_at_bos_close(self):
        bars = range_bars(30)
        zone = Zone(20, 18, "short", 109, 111, 1)
        baseline = r35._zone_location(bars, zone)
        for i in range(21, len(bars)):
            bars[i] = bar(i, high=1_000_000, low=0.01)
        self.assertEqual(r35._zone_location(bars, zone), baseline)

    def test_twenty_bar_history_is_required(self):
        bars = range_bars(20)
        self.assertEqual(r35._zone_location(
            bars, Zone(19, 18, "long", 89, 91, 1)), (False, "insufficient_history"))

    def test_incomplete_and_gap_windows_fail_closed(self):
        bars = range_bars()
        bars[12] = bar(12, complete=False)
        self.assertEqual(r35._zone_location(
            bars, Zone(20, 18, "long", 89, 91, 1)), (False, "incomplete_window"))
        bars = range_bars()
        bars[12] = bar(12, timestamp=12 * BAR + 1)
        self.assertEqual(r35._zone_location(
            bars, Zone(20, 18, "long", 89, 91, 1)), (False, "gap_window"))
        bars = range_bars()
        bars[20] = bar(20, timestamp=21 * BAR)
        self.assertEqual(r35._zone_location(
            bars, Zone(20, 18, "long", 89, 91, 1)), (False, "gap_window"))

    def test_real_bos_generation_is_filtered_before_one_hour_mapping(self):
        bars4 = [Bar(i * BAR, 100, 101, 99, 100, 1000) for i in range(25)]
        bars4[10] = Bar(10 * BAR, 100, 110, 99, 100, 1000)
        bars4[19] = Bar(19 * BAR, 101, 102, 99, 100, 1000)
        bars4[20] = Bar(20 * BAR, 100, 112, 99, 111, 1000)
        bars1 = [Bar(i * HOUR, 100, 100.5, 99.5, 100, 1000)
                 for i in range(25 * 4)]
        stats = {"raw_bos_zones": 0, "qualified_zones": 0, "rejected_zones": 0}
        _original, builder = r35._filtered_zone_builder(stats)
        with patch.object(r14, "r4_zones", side_effect=builder):
            mapped, unaligned = r14._zones_on_confirmation_segments(
                [bars1], [bars4]
            )
        self.assertEqual(unaligned, 0)
        self.assertEqual(stats["raw_bos_zones"], 1)
        self.assertEqual(stats["qualified_zones"], 1)
        self.assertEqual(stats["rejected_zones"], 0)
        self.assertEqual(list(mapped[0]), [21 * 4])

    def test_invalid_zone_and_direction_fail_closed(self):
        bars = range_bars()
        self.assertEqual(r35._zone_location(
            bars, Zone(20, 18, "long", 91, 89, 1)), (False, "invalid_zone"))
        self.assertEqual(r35._zone_location(
            bars, Zone(20, 18, "flat", 89, 91, 1)), (False, "invalid_direction"))

    def test_filter_only_changes_bos_origin_zones(self):
        bars = range_bars()
        long_zone = Zone(20, 18, "long", 89, 91, 1)
        short_zone = Zone(20, 18, "short", 109, 111, 1)
        stats = {"raw_bos_zones": 0, "qualified_zones": 0, "rejected_zones": 0}
        with patch.object(r14, "r4_zones", return_value=[long_zone, short_zone]):
            _original, builder = r35._filtered_zone_builder(stats)
            self.assertEqual(builder(bars, "displacement"), [long_zone, short_zone])
            self.assertEqual(builder(bars, "bos_origin"), [long_zone, short_zone])
        self.assertEqual(stats["raw_bos_zones"], 2)
        self.assertEqual(stats["qualified_zones"], 2)
        self.assertEqual(stats["rejected_zones"], 0)

    def test_filter_passes_through_real_r14_simulator_and_restores_patch(self):
        bars1 = [Bar(i * HOUR, 100, 100.5, 99.5, 100, 1000) for i in range(140)]
        bars1[29] = Bar(29 * HOUR, 99, 99.2, 98.2, 98.8, 1000)
        bars1[30] = Bar(30 * HOUR, 98.9, 99.2, 98.5, 99.0, 1000)
        bars1[31] = Bar(31 * HOUR, 99, 99.2, 98.5, 99.0, 1000)
        bars1[32] = Bar(32 * HOUR, 99, 100, 97.5, 99.8, 1000)
        bars1[101] = Bar(101 * HOUR, 90.8, 91.0, 90.5, 90.8, 1000)
        bars1[102] = Bar(102 * HOUR, 92.0, 94.0, 91.5, 93.5, 1000)
        bars4 = [Bar(i * BAR, 100, 110, 90, 100, 4000) for i in range(32)]
        zone = Zone(24, 22, "long", 89, 91, 1)
        funding = {102 * HOUR: FundingEvent(102 * HOUR, 0.0001, 100)}
        original = r14.r4_zones
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[zone]):
            result = r35._trial_with_filter(
                [("BTCUSDT", bars1, funding, 0)], [("BTCUSDT", bars4, {}, 0)])
        self.assertEqual(r14.r4_zones, original)
        self.assertEqual(result["raw_bos_zones"], 1)
        self.assertEqual(result["qualified_zones"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 1)

    def test_r14_patch_is_restored_after_exception(self):
        original = r14.r4_zones
        with patch.object(r14, "_trial", side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r35._trial_with_filter([], [])
        self.assertIs(r14.r4_zones, original)

    def test_duplicate_round_is_rejected_before_price_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "R35-coin"})
            with patch.object(common, "CSV_PATH", path):
                with self.assertRaisesRegex(RuntimeError, "R35 already exists"):
                    r35._ledger_state()

    def test_append_adds_one_row_with_denominator_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r35.r19, "_assert_no_ledger_writer"):
                r35._append({"status": "completed"}, "grid", "code", "fingerprint",
                            r35.EXPECTED_N, {**r35.CONFIG, "bonferroni_n": r35.EXPECTED_N})
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["round"], "R35-coin")
            self.assertEqual(json.loads(rows[0]["metric"])["bonferroni_denominator"],
                             r35.EXPECTED_N)
            self.assertEqual(json.loads(rows[0]["metric"])["train_input_fingerprint"],
                             "fingerprint")

    def test_locks_are_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cache/orderblock/runs").mkdir(parents=True)
            first = r35._acquire_locks(root)
            try:
                with self.assertRaises(FileExistsError):
                    r35._acquire_locks(root)
            finally:
                r35._release_locks(first)
            self.assertEqual(list((root / "cache/orderblock/runs").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
