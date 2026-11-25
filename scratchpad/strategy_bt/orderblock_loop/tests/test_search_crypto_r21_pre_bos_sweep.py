from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, Zone
import search_crypto_r21_pre_bos_sweep as r21


def flat_bars(count=60):
    return [Bar(i * r21.BAR_MS, 100, 101, 99, 100.5, 1000)
            for i in range(count)]


class R21PreBosSweepTests(unittest.TestCase):
    def test_long_external_sweep_requires_wick_below_and_close_back_above(self):
        bars = flat_bars()
        row = bars[25]
        bars[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
        self.assertTrue(r21._external_sweep(bars, 25, "long"))
        bars[25] = Bar(row.timestamp, 100, 101, 98.9, 99.0, 1000)
        self.assertFalse(r21._external_sweep(bars, 25, "long"))

    def test_short_external_sweep_mirrors_long(self):
        bars = flat_bars()
        row = bars[25]
        bars[25] = Bar(row.timestamp, 100, 101.1, 99, 100.9, 1000)
        self.assertTrue(r21._external_sweep(bars, 25, "short"))
        bars[25] = Bar(row.timestamp, 100, 101.1, 99, 101.0, 1000)
        self.assertFalse(r21._external_sweep(bars, 25, "short"))

    def test_20_bar_lookback_is_exact_and_includes_strict_break(self):
        bars = flat_bars()
        row = bars[25]
        bars[5] = Bar(bars[5].timestamp, 100, 101, 98.8, 100.5, 1000)
        bars[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
        self.assertFalse(r21._external_sweep(bars, 25, "long"))
        bars[5] = Bar(bars[5].timestamp, 100, 101, 99, 100.5, 1000)
        bars[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
        self.assertTrue(r21._external_sweep(bars, 25, "long"))

    def test_sweep_must_precede_bos_by_one_to_three_bars(self):
        for distance in (1, 2, 3):
            with self.subTest(distance=distance):
                bars = flat_bars()
                sweep_index = 25
                row = bars[sweep_index]
                bars[sweep_index] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
                self.assertTrue(r21._pre_bos_sweep(
                    bars, sweep_index + distance, "long"))
        bars = flat_bars()
        row = bars[25]
        bars[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
        self.assertFalse(r21._pre_bos_sweep(bars, 29, "long"))

    def test_original_zone_builder_is_restored_when_trial_raises(self):
        original_builder = r21.r14.r4_zones
        with patch.object(r21.r14, "_trial", side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r21._trial_with_filtered_zones([], [], {
                    "raw_bos_zones": 0, "pre_bos_sweep_zones": 0})
        self.assertIs(r21.r14.r4_zones, original_builder)

    def test_short_ledger_append_rolls_back_before_reporting_failure(self):
        import search_crypto_r19_match_attrition_audit as r19

        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(r21.common.FIELDS) + "\n", encoding="utf-8")
            before = ledger.read_bytes()
            with patch.object(r21.common, "CSV_PATH", ledger), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r21.os, "write", return_value=0):
                with self.assertRaisesRegex(OSError, "short append rolled back"):
                    r21._append({"status": "completed"}, "grid", "code", "data")
            self.assertEqual(ledger.read_bytes(), before)

    def test_failed_ledger_rollback_is_marked_unsafe(self):
        import search_crypto_r19_match_attrition_audit as r19

        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(r21.common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(r21.common, "CSV_PATH", ledger), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r21.os, "write", return_value=0), \
                    patch.object(r21.os, "ftruncate", side_effect=OSError("synthetic")):
                with self.assertRaises(r21.AppendRollbackError):
                    r21._append({"status": "completed"}, "grid", "code", "data")

    def test_future_bars_cannot_change_prior_sweep_classification(self):
        bars = flat_bars()
        row = bars[25]
        bars[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
        baseline = r21._pre_bos_sweep(bars, 28, "long")
        future_changed = list(bars)
        for i in range(29, len(future_changed)):
            old = future_changed[i]
            future_changed[i] = Bar(old.timestamp, old.open, old.high + 100,
                                    old.low - 100, old.close * 3, old.volume * 10)
        self.assertEqual(baseline, r21._pre_bos_sweep(future_changed, 28, "long"))

    def test_zone_filter_keeps_only_bos_with_prior_sweep(self):
        bars = flat_bars()
        row = bars[25]
        bars[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
        zones = [Zone(28, 24, "long", 99, 100, 1),
                 Zone(40, 36, "long", 99, 100, 1)]
        stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
        with patch.object(r21.r14, "r4_zones", return_value=zones):
            _, build = r21._filtered_zone_builder(stats)
            selected = build(bars, "bos_origin")
        self.assertEqual([zone.signal_index for zone in selected], [28])
        self.assertEqual(stats, {"raw_bos_zones": 2, "pre_bos_sweep_zones": 1})

    def test_non_bos_definitions_are_not_filtered_or_counted(self):
        zone = Zone(30, 26, "long", 99, 100, 1)
        stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
        with patch.object(r21.r14, "r4_zones", return_value=[zone]):
            _, build = r21._filtered_zone_builder(stats)
            selected = build(flat_bars(), "displacement")
        self.assertEqual(selected, [zone])
        self.assertEqual(stats, {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0})


if __name__ == "__main__":
    unittest.main()
