from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crypto import Bar
import search_crypto as common
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r21_pre_bos_sweep as r21
import search_crypto_r33_delayed_sweep_bos as r33


def bars(count=60):
    return [Bar(i * r33.BAR_MS, 100, 101, 99, 100.5, 1000)
            for i in range(count)]


def set_long_sweep(series, index):
    old = series[index]
    series[index] = Bar(old.timestamp, 100, 101, 98.8, 100.1, 1000)


def set_short_sweep(series, index):
    old = series[index]
    series[index] = Bar(old.timestamp, 101, 101.2, 99, 99.9, 1000)


class DelayedSweepBosTests(unittest.TestCase):
    def test_exact_delay_boundaries_four_five_six_pass(self):
        for delay in (4, 5, 6):
            with self.subTest(delay=delay):
                series = bars()
                set_long_sweep(series, 25)
                self.assertTrue(r33._pre_bos_sweep(series, 25 + delay, "long"))

    def test_three_and_seven_bar_delays_are_excluded(self):
        series = bars()
        set_long_sweep(series, 25)
        self.assertFalse(r33._pre_bos_sweep(series, 28, "long"))
        self.assertFalse(r33._pre_bos_sweep(series, 32, "long"))

    def test_long_short_sweep_rules_are_symmetric(self):
        long_bars = bars()
        set_long_sweep(long_bars, 25)
        short_bars = bars()
        set_short_sweep(short_bars, 25)
        self.assertEqual(r33._latest_qualifying_sweep(long_bars, 30, "long"), 25)
        self.assertEqual(r33._latest_qualifying_sweep(short_bars, 30, "short"), 25)

    def test_latest_of_multiple_qualifying_sweeps_is_selected(self):
        series = bars()
        set_long_sweep(series, 24)
        old = series[26]
        series[26] = Bar(old.timestamp, 100, 101, 97.8, 99.0, 1000)
        self.assertEqual(r33._latest_qualifying_sweep(series, 30, "long"), 26)

    def test_future_bars_cannot_change_prior_sweep_decision(self):
        series = bars()
        set_long_sweep(series, 25)
        baseline = r33._latest_qualifying_sweep(series, 30, "long")
        mutated = list(series)
        for i in range(30, len(mutated)):
            row = mutated[i]
            mutated[i] = Bar(row.timestamp, row.open, row.high + 200,
                             row.low - 200, row.close * 2, row.volume * 9)
        self.assertEqual(baseline, r33._latest_qualifying_sweep(mutated, 30, "long"))

    def test_bos_sweep_window_has_no_lookahead_or_bos_bar_overlap(self):
        series = bars()
        set_long_sweep(series, 30)
        self.assertFalse(r33._pre_bos_sweep(series, 30, "long"))
        self.assertFalse(r33._pre_bos_sweep(series, 33, "long"))

    def test_r21_filter_is_restored_if_trial_raises(self):
        original = r21._pre_bos_sweep
        with patch.object(r21, "_trial_with_filtered_zones",
                          side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r33._trial_with_filtered_zones([], [], {
                    "raw_bos_zones": 0, "pre_bos_sweep_zones": 0})
        self.assertIs(r21._pre_bos_sweep, original)

    def test_append_writes_one_R33_row_and_preserves_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"):
                r33._append({"status": "completed"}, "grid", "code", "fingerprint",
                            {**r33.CONFIG, "bonferroni_n": r33.EXPECTED_N})
            with path.open(newline="", encoding="utf-8") as stream:
                records = list(csv.DictReader(stream))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["round"], "R33-coin")
            self.assertEqual(records[0]["parameter_grid_hash"], "grid")

    def test_duplicate_R33_round_blocks_single_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "R33-coin"})
            with patch.object(common, "CSV_PATH", path):
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    r33._ledger_state()


if __name__ == "__main__":
    unittest.main()
