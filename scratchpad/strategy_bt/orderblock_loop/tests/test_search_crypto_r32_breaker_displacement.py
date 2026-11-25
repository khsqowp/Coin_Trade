from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, FundingEvent, Zone, r4_zones, trade_daily_pnl
import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r31_breaker_flip_retest as r31
import search_crypto_r32_breaker_displacement as r32


class BreakerDisplacementTests(unittest.TestCase):
    def bar(self, close, index=1, *, complete=True):
        return Bar(index * r31.HOUR_MS, 100.0, max(101.0, close),
                   min(98.0, close), close, 1.0, complete)

    def state(self, direction="long", atr=4.0):
        zone = Zone(0, 19, direction, 99.0, 102.0, atr)
        return {"zone": zone, "phase": "ob_wait", "break_index": None}

    def test_shallow_close_breach_is_rejected_and_wait_continues(self):
        state = self.state("long", atr=4.0)
        rejected = {"shallow_close_break_rejected": 0}
        result = r32._advance_with_depth(state, self.bar(98.5), 1, rejected)
        self.assertEqual(result, "wait")
        self.assertEqual(rejected["shallow_close_break_rejected"], 1)
        self.assertEqual(state["phase"], "ob_wait")

    def test_exact_quarter_atr_and_deeper_close_confirm_break(self):
        state = self.state("long", atr=4.0)
        rejected = {"shallow_close_break_rejected": 0}
        result = r32._advance_with_depth(state, self.bar(98.0), 1, rejected)
        self.assertEqual(result, "broken")
        self.assertEqual(state["phase"], "breaker_wait")
        self.assertEqual(rejected["shallow_close_break_rejected"], 0)

    def test_shallow_break_keeps_original_expiry_boundary(self):
        state = self.state("long", atr=4.0)
        rejected = {"shallow_close_break_rejected": 0}
        last_valid = self.bar(98.5, index=r31.BREAK_DEADLINE)
        self.assertEqual(r32._advance_with_depth(
            state, last_valid, r31.BREAK_DEADLINE, rejected), "wait")
        beyond = self.bar(98.5, index=r31.BREAK_DEADLINE + 1)
        self.assertEqual(r32._advance_with_depth(
            state, beyond, r31.BREAK_DEADLINE + 1, rejected), "expire_break")
        self.assertEqual(rejected["shallow_close_break_rejected"], 1)

    def test_short_direction_uses_symmetric_zone_atr_overshoot(self):
        rejected = {"shallow_close_break_rejected": 0}
        shallow = self.state("short", atr=4.0)
        self.assertEqual(r32._advance_with_depth(shallow, self.bar(102.5), 1, rejected), "wait")
        exact = self.state("short", atr=4.0)
        self.assertEqual(r32._advance_with_depth(exact, self.bar(103.0), 1, rejected), "broken")

    def test_no_breach_is_not_counted_as_shallow(self):
        state = self.state("long")
        rejected = {"shallow_close_break_rejected": 0}
        self.assertEqual(r32._advance_with_depth(state, self.bar(99.2), 1, rejected), "wait")
        self.assertEqual(rejected["shallow_close_break_rejected"], 0)

    def test_invalid_zone_atr_fails_closed(self):
        for atr in (0, -1, float("nan"), float("inf")):
            with self.subTest(atr=atr), self.assertRaisesRegex(ValueError, "ATR"):
                r32._advance_with_depth(
                    self.state("long", atr), self.bar(98.0), 1,
                    {"shallow_close_break_rejected": 0})

    def test_activation_bar_does_not_count_as_a_break(self):
        state = self.state("long")
        rejected = {"shallow_close_break_rejected": 0}
        self.assertEqual(r32._advance_with_depth(state, self.bar(90, 0), 0, rejected), "wait")
        self.assertEqual(rejected["shallow_close_break_rejected"], 0)

    def test_base_state_function_restored_after_wrapped_trial_raises(self):
        original = r31._advance
        with patch.object(r31, "_trial", side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r32._trial_with_depth([], [])
        self.assertIs(r31._advance, original)

    def test_depth_filter_flows_through_base_state_and_common_trade_engine(self):
        zone = self.state("long")["zone"]
        bars = [
            Bar(i * r31.HOUR_MS, 100, 101, 99, 100, 1.0)
            for i in range(6)
        ]
        bars[1] = Bar(r31.HOUR_MS, 100, 100.5, 98.2, 98.5, 1.0)
        bars[2] = Bar(2 * r31.HOUR_MS, 98.5, 99.0, 97.5, 98.0, 1.0)
        bars[3] = Bar(3 * r31.HOUR_MS, 98.0, 99.5, 97.5, 98.5, 1.0)
        bars[4] = Bar(4 * r31.HOUR_MS, 98.5, 98.7, 97.0, 98.2, 1.0)
        bars[5] = Bar(5 * r31.HOUR_MS, 98.2, 98.5, 96.0, 96.2, 1.0)
        rejected = {"shallow_close_break_rejected": 0}
        original = r31._advance
        r31._advance = lambda state, bar, index: r32._advance_with_depth(
            state, bar, index, rejected, base_advance=original)
        try:
            trades, audit = r31._simulate_segment(bars, {}, {0: zone})
        finally:
            r31._advance = original
        self.assertEqual(rejected["shallow_close_break_rejected"], 1)
        self.assertEqual(audit["breaks"], 1)
        self.assertEqual(audit["confirmed_retests"], 1)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].exit_reason, "target")

    def test_real_zone_mapper_depth_filter_trade_cost_and_funding_end_to_end(self):
        four = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1.0)
                for i in range(40)]
        four[10] = Bar(10 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1.0)
        four[19] = Bar(19 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1.0)
        four[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 112, 99, 111, 1.0)
        self.assertEqual(len(r4_zones(four, "bos_origin")), 1)

        hourly = [Bar(i * r31.HOUR_MS, 103, 103.5, 102.5, 103, 1.0)
                  for i in range(90)]
        hourly[85] = Bar(85 * r31.HOUR_MS, 100, 100.5, 98.2, 98.5, 1.0)
        hourly[86] = Bar(86 * r31.HOUR_MS, 98.5, 99.0, 97.5, 98.125, 1.0)
        hourly[87] = Bar(87 * r31.HOUR_MS, 98.125, 99.5, 97.5, 98.5, 1.0)
        hourly[88] = Bar(88 * r31.HOUR_MS, 98.5, 98.7, 97.0, 98.2, 1.0)
        hourly[89] = Bar(89 * r31.HOUR_MS, 98.2, 98.5, 96.0, 96.2, 1.0)
        mapped, unaligned = r14._zones_on_confirmation_segments([hourly], [four])
        self.assertEqual(unaligned, 0)
        self.assertIn(84, mapped[0])

        timestamp = 89 * r31.HOUR_MS
        funding = {timestamp: FundingEvent(timestamp, -0.001, 98.0)}
        rejected = {"shallow_close_break_rejected": 0}
        original = r31._advance
        r31._advance = lambda state, bar, index: r32._advance_with_depth(
            state, bar, index, rejected, base_advance=original)
        try:
            trades, audit = r31._simulate_segment(hourly, funding, mapped[0])
        finally:
            r31._advance = original
        self.assertEqual(rejected["shallow_close_break_rejected"], 1)
        self.assertEqual(audit["breaks"], 1)
        self.assertEqual(audit["confirmed_retests"], 1)
        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade.setup.zone.direction, "short")
        self.assertEqual(trade.exit_reason, "target")
        self.assertAlmostEqual(trade.cost_bps, 12.0)
        self.assertLess(trade.funding_return, 0)
        daily = trade_daily_pnl(hourly, trade, funding=funding,
                                bar_duration_ms=r31.HOUR_MS)
        self.assertAlmostEqual(sum(daily.values()), trade.net_return)

    def test_future_bar_mutation_does_not_change_prior_depth_decision(self):
        prefix = [self.bar(98.5, index=1), self.bar(98.0, index=2)]
        state_a, state_b = self.state("long"), self.state("long")
        rejected_a = {"shallow_close_break_rejected": 0}
        rejected_b = {"shallow_close_break_rejected": 0}
        events_a = [r32._advance_with_depth(state_a, bar, i + 1, rejected_a)
                    for i, bar in enumerate(prefix)]
        changed = prefix + [self.bar(150.0, index=3)]
        events_b = [r32._advance_with_depth(state_b, bar, i + 1, rejected_b)
                    for i, bar in enumerate(changed[:2])]
        self.assertEqual(events_a, events_b)
        self.assertEqual(state_a, state_b)
        self.assertEqual(rejected_a, rejected_b)

    def test_round_and_threshold_are_fixed_in_both_preregs(self):
        self.assertEqual(r32.DEPTH_ATR, 0.25)
        self.assertEqual(r32.EXPECTED_ROWS + 1, r32.EXPECTED_N)
        self.assertIn("R32-coin", r32.MASTER_PATH.read_text(encoding="utf-8"))
        detail = r32.PREREG_PATH.read_text(encoding="utf-8")
        self.assertIn("overshoot >= 0.25", detail)
        self.assertIn("N≥200", detail)

    def test_snapshot_gate_rejects_code_change(self):
        with patch.object(r32, "_code_hash", return_value="changed"):
            with self.assertRaisesRegex(RuntimeError, "changed during run"):
                r32._assert_snapshot("original", r32._PREREG_SHA, r32._MASTER_SHA)

    def test_snapshot_gate_rejects_detail_and_master_prereg_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            detail = Path(directory) / "detail.md"
            master = Path(directory) / "master.md"
            detail.write_text("detail", encoding="utf-8")
            master.write_text("master", encoding="utf-8")
            detail_sha = r32.hashlib.sha256(detail.read_bytes()).hexdigest()
            master_sha = r32.hashlib.sha256(master.read_bytes()).hexdigest()
            detail.write_text("changed detail", encoding="utf-8")
            with patch.object(r32, "_code_hash", return_value="same"), \
                    patch.object(r32, "PREREG_PATH", detail), \
                    patch.object(r32, "MASTER_PATH", master):
                with self.assertRaisesRegex(RuntimeError, "changed during run"):
                    r32._assert_snapshot("same", detail_sha, master_sha)
            detail.write_text("detail", encoding="utf-8")
            master.write_text("changed master", encoding="utf-8")
            with patch.object(r32, "_code_hash", return_value="same"), \
                    patch.object(r32, "PREREG_PATH", detail), \
                    patch.object(r32, "MASTER_PATH", master):
                with self.assertRaisesRegex(RuntimeError, "changed during run"):
                    r32._assert_snapshot("same", detail_sha, master_sha)

    def test_append_once_preserves_prior_rows_and_duplicate_round_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "prior"})
            before = path.read_bytes()
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r32.r19, "_assert_no_ledger_writer"):
                r32._append({"status": "completed"}, "grid", "code", "fingerprint", r32.CONFIG)
                with path.open(newline="", encoding="utf-8") as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))), 2)
                with path.open("a", newline="", encoding="utf-8") as stream:
                    csv.DictWriter(stream, fieldnames=common.FIELDS).writerow({"round": "R32-coin"})
                with self.assertRaisesRegex(RuntimeError, "R32 already exists"):
                    r32._ledger_state()
            self.assertTrue(path.read_bytes().startswith(before))

    def test_writer_conflict_rejects_r32_append_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            path.write_text("existing\n", encoding="utf-8")
            before = path.read_bytes()
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r32.r19, "_assert_no_ledger_writer",
                                 side_effect=RuntimeError("writer active")):
                with self.assertRaisesRegex(RuntimeError, "writer active"):
                    r32._append({"status": "completed"}, "grid", "code", "fp", r32.CONFIG)
            self.assertEqual(path.read_bytes(), before)

    def test_partial_r32_append_is_uncertain_and_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            path.write_text("existing\n", encoding="utf-8")
            before = path.read_bytes()
            real_write = os.write
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r32.r19, "_assert_no_ledger_writer"), \
                    patch.object(r32.os, "write",
                                 side_effect=lambda fd, payload: real_write(fd, payload[:3])) as write:
                with self.assertRaisesRegex(r32.AppendUncertainError, "short append"):
                    r32._append({"status": "completed"}, "grid", "code", "fp", r32.CONFIG)
            self.assertEqual(write.call_count, 1)
            self.assertTrue(path.read_bytes().startswith(before))
            self.assertGreater(len(path.read_bytes()), len(before))

    def test_locks_are_exclusive_and_removed_after_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_dir = root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            opened = r32._acquire_run_locks(root)
            with self.assertRaises(FileExistsError):
                r32._acquire_run_locks(root)
            r32._release_run_locks(opened)
            self.assertEqual(list(lock_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
