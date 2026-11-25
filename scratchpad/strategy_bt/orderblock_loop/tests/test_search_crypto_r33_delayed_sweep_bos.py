from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from crypto import Bar, FundingEvent, Zone
import search_crypto as common
import search_crypto_r14 as r14
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

    def test_gap_cannot_be_counted_as_a_completed_bar_delay(self):
        series = bars()
        set_long_sweep(series, 25)
        row = series[28]
        series[28] = Bar(row.timestamp + r33.BAR_MS, row.open, row.high,
                         row.low, row.close, row.volume)
        self.assertIsNone(r33._latest_qualifying_sweep(series, 30, "long"))

    def test_r21_filter_is_restored_if_trial_raises(self):
        original = r21._pre_bos_sweep
        with patch.object(r21, "_trial_with_filtered_zones",
                          side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r33._trial_with_filtered_zones([], [], {
                    "raw_bos_zones": 0, "pre_bos_sweep_zones": 0})
        self.assertIs(r21._pre_bos_sweep, original)

    def test_delayed_sweep_flows_through_real_R14_mapper_and_trade_simulator(self):
        hour_ms = r33.BAR_MS // 4
        hourly = [Bar(i * hour_ms, 102, 102.8, 101.7, 102.2, 1000)
                  for i in range(42 * 4)]
        hourly[24 * 4 + 1] = Bar(24 * 4 * hour_ms + hour_ms, 102, 103.5,
                                  101.7, 102.2, 1000)
        hourly[25 * 4 + 1] = Bar(25 * 4 * hour_ms + hour_ms, 102, 102.8,
                                  98.8, 102.1, 1000)
        hourly[25 * 4 + 3] = Bar(25 * 4 * hour_ms + 3 * hour_ms, 102, 102.8,
                                  101.7, 102.0, 1000)
        hourly[30 * 4] = Bar(30 * 4 * hour_ms, 102, 102.8, 100.0, 102.0, 1000)
        hourly[30 * 4 + 3] = Bar(30 * 4 * hour_ms + 3 * hour_ms, 102, 102.8,
                                  100.0, 100.5, 1000)
        hourly[31 * 4] = Bar(31 * 4 * hour_ms, 100.5, 102.8, 100.2, 101.0, 1000)
        hourly[31 * 4 + 3] = Bar(31 * 4 * hour_ms + 3 * hour_ms, 101.0, 104.3,
                                  100.2, 104.1, 1000)
        hourly[129] = Bar(129 * hour_ms, 102, 102.8, 101.7, 102.2, 1000)
        hourly[130] = Bar(130 * hour_ms, 102, 102.8, 101.7, 102.1, 1000)
        for i in range(131, 136):
            hourly[i] = Bar(i * hour_ms, 102.1, 102.8, 101.7, 102.2, 1000)
        hourly[136] = Bar(136 * hour_ms, 102.2, 104.0, 101.7, 103.5, 1000)
        four_hour = []
        for i in range(42):
            group = hourly[i * 4:(i + 1) * 4]
            four_hour.append(Bar(group[0].timestamp, group[0].open,
                                 max(b.high for b in group), min(b.low for b in group),
                                 group[-1].close, sum(b.volume for b in group)))
        generated = r14.r4_zones(four_hour, "bos_origin")
        zones = [z for z in generated if z.signal_index == 31 and z.direction == "long"]
        self.assertEqual(len(zones), 1)
        self.assertTrue(r33._pre_bos_sweep(four_hour, 31, "long"))
        simulated = []
        real_simulate = r14.simulate_trade

        def capture(*args, **kwargs):
            trade = real_simulate(*args, **kwargs)
            simulated.append(trade)
            return trade

        stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
        funding_event = FundingEvent(132 * hour_ms, 0.001, 102.0)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "simulate_trade", side_effect=capture):
            result = r33._trial_with_filtered_zones(
                [("BTCUSDT", hourly, {funding_event.timestamp: funding_event}, 0)],
                [("BTCUSDT", four_hour, {}, 0)], stats)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 1)
        self.assertEqual(stats["pre_bos_sweep_zones"], 1)
        self.assertEqual(len(simulated), 1)
        self.assertEqual(simulated[0].exit_reason, "target")
        self.assertAlmostEqual(simulated[0].cost_bps, 12)
        self.assertEqual(simulated[0].funding_order_policy, "adverse_only")
        self.assertLess(simulated[0].funding_return, 0)
        self.assertIsNotNone(simulated[0].net_return)

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

    def test_writer_conflict_prevents_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            before = path.read_bytes()
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer",
                                 side_effect=RuntimeError("writer present")):
                with self.assertRaisesRegex(RuntimeError, "writer present"):
                    r33._append({}, "grid", "code", "fingerprint", {})
            self.assertEqual(path.read_bytes(), before)

    def test_partial_append_is_uncertain_and_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r33.os, "write", return_value=0):
                with self.assertRaises(r33.AppendUncertainError):
                    r33._append({}, "grid", "code", "fingerprint", {})

    def test_run_locks_are_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cache/orderblock/runs").mkdir(parents=True)
            first = r33._acquire_locks(root)
            try:
                with self.assertRaises(FileExistsError):
                    r33._acquire_locks(root)
            finally:
                r33._release_locks(first)
            self.assertEqual(list((root / "cache/orderblock/runs").iterdir()), [])

    def test_wrong_denominator_fails_before_split_or_train_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r33, "EXPECTED_ROWS", 0), \
                    patch.object(r33, "EXPECTED_N", 2), \
                    patch.object(r33.r29, "_split_cache_state") as split, \
                    patch.object(r33.r14, "_load_barsets") as load:
                with patch.dict(sys.modules, {"data_access": object()}):
                    with self.assertRaisesRegex(RuntimeError, "preflight mismatch"):
                        r33._run_locked(Path(tmp))
            split.assert_not_called()
            load.assert_not_called()

    def test_prereg_hash_mismatch_fails_before_train_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            changed = Path(tmp) / "changed_prereg.md"
            changed.write_text("different", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r33, "EXPECTED_ROWS", 0), \
                    patch.object(r33, "EXPECTED_N", 1), \
                    patch.object(r33, "PREREG_PATH", changed), \
                    patch.object(r33, "_PREREG_SHA", "wrong"), \
                    patch.object(r33.r14, "_load_barsets") as load:
                with patch.dict(sys.modules, {"data_access": object()}):
                    with self.assertRaisesRegex(RuntimeError, "preflight mismatch"):
                        r33._run_locked(Path(tmp))
            load.assert_not_called()

    def test_runtime_code_hash_mismatch_fails_before_split_or_train_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r33, "EXPECTED_ROWS", 0), \
                    patch.object(r33, "EXPECTED_N", 1), \
                    patch.object(r33, "_code_hash", return_value="changed"), \
                    patch.object(r33.r29, "_split_cache_state") as split:
                with self.assertRaisesRegex(RuntimeError, "changed after import"):
                    r33._run_locked(Path(tmp))
            split.assert_not_called()

    def test_low_disk_space_fails_before_split_or_train_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            usage = SimpleNamespace(free=r33.MIN_FREE_BYTES - 1)
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r33, "EXPECTED_ROWS", 0), \
                    patch.object(r33, "EXPECTED_N", 1), \
                    patch.object(r33.shutil, "disk_usage", return_value=usage), \
                    patch.object(r33.r29, "_split_cache_state") as split:
                with self.assertRaisesRegex(RuntimeError, "40 GiB"):
                    r33._run_locked(Path(tmp))
            split.assert_not_called()

    def test_split_manifest_change_after_train_load_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            data_access = SimpleNamespace(iter_train_bars=object())
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r33, "EXPECTED_ROWS", 0), \
                    patch.object(r33, "EXPECTED_N", 1), \
                    patch.object(r33.r29, "_split_cache_state",
                                 side_effect=[("before", 1), ("after", 2)]), \
                    patch.object(r33.r14, "_load_barsets", side_effect=[[], []]), \
                    patch.object(common, "_train_input_fingerprint", return_value="synthetic"), \
                    patch.object(r33.r27, "_usable_symbols", return_value=[]), \
                    patch.object(r33, "heavy_task", return_value=nullcontext()), \
                    patch.object(r33, "_append") as append:
                with patch.dict(sys.modules, {"data_access": data_access}):
                    with self.assertRaisesRegex(RuntimeError, "split cache changed"):
                        r33._run_locked(Path(tmp))
            append.assert_called_once()


if __name__ == "__main__":
    unittest.main()
