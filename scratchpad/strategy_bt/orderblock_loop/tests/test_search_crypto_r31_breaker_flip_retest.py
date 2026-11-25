from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, FundingEvent, Zone, r4_zones
import search_crypto_r14 as r14
import search_crypto_r31_breaker_flip_retest as r31
import search_crypto as common


class BreakerFlipRetestTests(unittest.TestCase):
    def zone(self, direction="long"):
        return Zone(0, 19, direction, 99.0, 102.0, 3.5)

    def bar(self, index, open_, high, low, close, complete=True):
        return Bar(index * r31.HOUR_MS, open_, high, low, close, 1.0, complete)

    def state(self, direction="long"):
        return {"zone": self.zone(direction), "phase": "ob_wait", "break_index": None}

    def test_wick_beyond_edge_does_not_break_but_close_does(self):
        state = self.state("long")
        self.assertEqual(r31._advance(state, self.bar(0, 100, 101, 98, 100), 0), "wait")
        self.assertEqual(r31._advance(state, self.bar(1, 100, 101, 98, 99.2), 1), "wait")
        self.assertEqual(r31._advance(state, self.bar(2, 99.2, 100, 97, 98.9), 2), "broken")
        self.assertEqual(state["break_index"], 2)

    def test_long_short_break_and_retest_are_directionally_symmetric(self):
        long_state = self.state("long")
        r31._advance(long_state, self.bar(0, 100, 101, 99, 100), 0)
        self.assertEqual(r31._advance(long_state, self.bar(1, 100, 101, 98, 98.5), 1), "broken")
        self.assertEqual(r31._advance(long_state, self.bar(2, 98.5, 99.5, 97, 98.8), 2), "confirm_short")

        short_state = self.state("short")
        r31._advance(short_state, self.bar(0, 100, 101, 99, 100), 0)
        self.assertEqual(r31._advance(short_state, self.bar(1, 100, 103, 99, 102.5), 1), "broken")
        self.assertEqual(r31._advance(short_state, self.bar(2, 102.5, 104, 101.5, 102.2), 2), "confirm_long")

    def test_break_bar_cannot_also_be_retest_and_retest_requires_close_outside(self):
        state = self.state("long")
        r31._advance(state, self.bar(0, 100, 101, 99, 100), 0)
        self.assertEqual(r31._advance(state, self.bar(1, 100, 103, 97, 98), 1), "broken")
        self.assertEqual(r31._advance(state, self.bar(1, 98, 100, 97, 98), 1), "wait")
        self.assertEqual(r31._advance(state, self.bar(2, 98, 100, 98, 99.5), 2), "cancel_reentered")

    def test_full_zone_penetration_cancels_before_retest_confirmation(self):
        short_state = self.state("long")
        r31._advance(short_state, self.bar(0, 100, 101, 99, 100), 0)
        r31._advance(short_state, self.bar(1, 100, 101, 98, 98.5), 1)
        self.assertEqual(r31._advance(short_state, self.bar(2, 98, 103, 97, 98.5), 2),
                         "cancel_reentered")

        long_state = self.state("short")
        r31._advance(long_state, self.bar(0, 100, 101, 99, 100), 0)
        r31._advance(long_state, self.bar(1, 100, 103, 99, 102.5), 1)
        self.assertEqual(r31._advance(long_state, self.bar(2, 102.5, 104, 98, 102.5), 2),
                         "cancel_reentered")

    def test_wick_retest_with_close_outside_is_valid_not_cancellation(self):
        state = self.state("long")
        r31._advance(state, self.bar(0, 100, 101, 99, 100), 0)
        r31._advance(state, self.bar(1, 100, 101, 98, 98.5), 1)
        self.assertEqual(r31._advance(state, self.bar(2, 98, 99.5, 97, 98.5), 2), "confirm_short")
        self.assertEqual(state["phase"], "breaker_wait")

    def test_break_and_retest_expiry_boundaries(self):
        state = self.state("long")
        r31._advance(state, self.bar(0, 100, 101, 99, 100), 0)
        self.assertEqual(r31._advance(state, self.bar(24, 100, 101, 98, 98), 24), "broken")
        self.assertEqual(r31._advance(state, self.bar(48, 98, 99.5, 97, 98.5), 48), "confirm_short")
        state = self.state("long")
        r31._advance(state, self.bar(0, 100, 101, 99, 100), 0)
        self.assertEqual(r31._advance(state, self.bar(25, 100, 101, 98, 98), 25), "expire_break")
        state = self.state("long")
        r31._advance(state, self.bar(0, 100, 101, 99, 100), 0)
        r31._advance(state, self.bar(1, 100, 101, 98, 98), 1)
        self.assertEqual(r31._advance(state, self.bar(26, 98, 99.5, 97, 98.5), 26), "expire_retest")

    def test_incomplete_bar_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "completed bars only"):
            r31._advance(self.state(), self.bar(1, 100, 101, 99, 100, False), 1)

    def test_setup_reverses_direction_uses_next_open_and_fixed_risk(self):
        bars = [self.bar(0, 98.5, 98.7, 97.0, 98.4), self.bar(1, 98.4, 98.6, 98.0, 98.2)]
        short, reason = r31._make_setup(self.zone("long"), bars, 0)
        self.assertEqual(reason, "setup")
        self.assertEqual(short.zone.direction, "short")
        self.assertEqual(short.entry_price, bars[1].open)
        self.assertAlmostEqual(short.stop, 102.35)
        self.assertAlmostEqual(short.target, 96.425)

        long_bars = [self.bar(0, 102.5, 103, 102, 102.8), self.bar(1, 102.8, 103, 102.5, 102.9)]
        long, reason = r31._make_setup(self.zone("short"), long_bars, 0)
        self.assertEqual(reason, "setup")
        self.assertEqual(long.zone.direction, "long")
        self.assertAlmostEqual(long.stop, 98.65)
        self.assertAlmostEqual(long.target, 104.875)

    def test_entry_gap_back_into_zone_is_cancelled(self):
        bars = [self.bar(0, 99.5, 100, 99, 99.5), self.bar(1, 100, 101, 99, 100)]
        self.assertEqual(r31._make_setup(self.zone("long"), bars, 0)[1], "entry_gapped_into_zone")
        bars = [self.bar(0, 102.5, 103, 102, 102.5), self.bar(1, 101, 102, 100, 101)]
        self.assertEqual(r31._make_setup(self.zone("short"), bars, 0)[1], "entry_gapped_into_zone")

    def test_stop_first_simulation_and_cost_funding_use_common_engine(self):
        zone = self.zone("long")
        bars = [self.bar(0, 98.5, 98.7, 97, 98.4), self.bar(1, 98.4, 103, 95, 98)]
        setup, _ = r31._make_setup(zone, bars, 0)
        trade = r31.r14.simulate_trade(
            bars, setup, funding={}, max_holding_bars=r31.MAX_HOLDING_BARS,
            bar_duration_ms=r31.HOUR_MS, funding_order_policy=r31.FUNDING_ORDER_POLICY)
        self.assertEqual(trade.exit_reason, "stop")
        self.assertAlmostEqual(trade.cost_bps, 12.0)

    def test_adverse_funding_is_charged_by_shared_simulator(self):
        bars = [self.bar(0, 98.5, 98.7, 97, 98.4), self.bar(1, 98.4, 98.6, 97.5, 98.2),
                self.bar(2, 98.2, 98.3, 96.0, 96.2)]
        setup, _ = r31._make_setup(self.zone("long"), bars, 0)
        funding = {2 * r31.HOUR_MS: FundingEvent(2 * r31.HOUR_MS, -0.001, 98.0)}
        trade = r31.r14.simulate_trade(
            bars, setup, funding=funding, max_holding_bars=r31.MAX_HOLDING_BARS,
            bar_duration_ms=r31.HOUR_MS, funding_order_policy=r31.FUNDING_ORDER_POLICY)
        self.assertEqual(trade.exit_reason, "target")
        self.assertLess(trade.funding_return, 0)

    def test_full_real_zone_mapper_state_machine_and_trade_path(self):
        four = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1) for i in range(40)]
        four[10] = Bar(10 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1)
        four[19] = Bar(19 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1)
        four[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 112, 99, 111, 1)
        zones = r4_zones(four, "bos_origin")
        self.assertEqual(len(zones), 1)
        hourly = [self.bar(i, 103, 103.5, 102.5, 103) for i in range(89)]
        hourly[85] = self.bar(85, 100, 101, 97, 98)
        hourly[86] = self.bar(86, 98, 99.5, 97, 98.5)
        hourly[87] = self.bar(87, 98.5, 98.8, 97, 98.2)
        hourly[88] = self.bar(88, 98.2, 98.5, 96, 96.2)
        mapped, unaligned = r14._zones_on_confirmation_segments([hourly], [four])
        self.assertEqual(unaligned, 0)
        self.assertIn(84, mapped[0])
        trades, audit = r31._simulate_segment(hourly, {}, mapped[0])
        self.assertEqual(audit["breaks"], 1)
        self.assertEqual(audit["confirmed_retests"], 1)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].setup.zone.direction, "short")
        self.assertEqual(trades[0].exit_reason, "target")

    def test_future_prefix_does_not_change_prior_breaker_decision(self):
        prefix = [self.bar(0, 100, 101, 99, 100), self.bar(1, 100, 101, 98, 98.5),
                  self.bar(2, 98.5, 99.5, 97, 98.8)]
        original = self.state("long")
        mutated = self.state("long")
        original_events = [r31._advance(original, bar, i) for i, bar in enumerate(prefix)]
        altered = prefix + [self.bar(3, 97, 120, 80, 110)]
        mutated_events = [r31._advance(mutated, bar, i) for i, bar in enumerate(altered[:3])]
        self.assertEqual(original_events, mutated_events)
        self.assertEqual(original, mutated)

    def test_ledger_counter_is_append_only_and_duplicate_round_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "prior"})
            original = path.read_bytes()
            with patch.object(common, "CSV_PATH", path):
                self.assertEqual(r31._ledger_state(), 1)
                with path.open("a", newline="", encoding="utf-8") as stream:
                    csv.DictWriter(stream, fieldnames=common.FIELDS).writerow({"round": "R31-coin"})
                with self.assertRaisesRegex(RuntimeError, "R31 already exists"):
                    r31._ledger_state()
            self.assertTrue(path.read_bytes().startswith(original))

    def test_append_writes_exactly_one_row_and_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "prior"})
            before = path.read_bytes()
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r31.r19, "_assert_no_ledger_writer"):
                r31._append({"status": "completed"}, "grid", "code", "fingerprint", r31.CONFIG)
            self.assertTrue(path.read_bytes().startswith(before))
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["round"] for row in rows], ["prior", "R31-coin"])

    def test_run_locks_are_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock_dir = root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            opened = r31._acquire_run_locks(root)
            self.assertEqual(len(opened), 2)
            with self.assertRaises(FileExistsError):
                r31._acquire_run_locks(root)
            r31._release_run_locks(opened)
            self.assertFalse(any(lock_dir.iterdir()))

    def test_prereg_registry_and_fixed_thresholds_are_explicit(self):
        self.assertEqual(r31.EXPECTED_ROWS + 1, r31.EXPECTED_N)
        self.assertIn("R31-coin", r31.MASTER_PATH.read_text(encoding="utf-8"))
        self.assertIn("N≥200", r31.PREREG_PATH.read_text(encoding="utf-8"))

    def test_changed_code_snapshot_is_rejected(self):
        with patch.object(r31, "_code_hash", return_value="changed"):
            with self.assertRaisesRegex(RuntimeError, "changed during run"):
                r31._assert_snapshot("original", r31._PREREG_SHA, r31._MASTER_SHA)

    def test_changed_detail_or_master_prereg_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            detail = Path(directory) / "detail.md"
            master = Path(directory) / "master.md"
            detail.write_text("registered detail", encoding="utf-8")
            master.write_text("registered master", encoding="utf-8")
            detail_sha = r31.hashlib.sha256(detail.read_bytes()).hexdigest()
            master_sha = r31.hashlib.sha256(master.read_bytes()).hexdigest()
            detail.write_text("changed detail", encoding="utf-8")
            with patch.object(r31, "_code_hash", return_value="same"), \
                    patch.object(r31, "PREREG_PATH", detail), \
                    patch.object(r31, "MASTER_PATH", master):
                with self.assertRaisesRegex(RuntimeError, "changed during run"):
                    r31._assert_snapshot("same", detail_sha, master_sha)
            detail.write_text("registered detail", encoding="utf-8")
            master.write_text("changed master", encoding="utf-8")
            with patch.object(r31, "_code_hash", return_value="same"), \
                    patch.object(r31, "PREREG_PATH", detail), \
                    patch.object(r31, "MASTER_PATH", master):
                with self.assertRaisesRegex(RuntimeError, "changed during run"):
                    r31._assert_snapshot("same", detail_sha, master_sha)

    def test_writer_conflict_is_rejected_before_ledger_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            path.write_text("existing\n", encoding="utf-8")
            before = path.read_bytes()
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r31.r19, "_assert_no_ledger_writer",
                                 side_effect=RuntimeError("writer active")):
                with self.assertRaisesRegex(RuntimeError, "writer active"):
                    r31._append({"status": "completed"}, "grid", "code", "fp", r31.CONFIG)
            self.assertEqual(path.read_bytes(), before)

    def test_partial_append_is_uncertain_and_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            path.write_text("existing\n", encoding="utf-8")
            before = path.read_bytes()
            real_write = os.write
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r31.r19, "_assert_no_ledger_writer"), \
                    patch.object(r31.os, "write",
                                 side_effect=lambda fd, payload: real_write(fd, payload[:3])) as write:
                with self.assertRaisesRegex(r31.AppendUncertainError, "short append"):
                    r31._append({"status": "completed"}, "grid", "code", "fp", r31.CONFIG)
            self.assertEqual(write.call_count, 1)
            self.assertTrue(path.read_bytes().startswith(before))
            self.assertGreater(len(path.read_bytes()), len(before))

    def test_gap_segments_do_not_carry_a_breaker_state(self):
        bars = [self.bar(0, 100, 101, 99, 100), self.bar(1, 100, 101, 98, 98.5),
                self.bar(4, 98, 99.5, 97, 98.5)]
        segments, _gaps = r14._segments(bars, r31.HOUR_MS)
        self.assertEqual([len(segment) for segment in segments], [2, 1])
        zone = self.zone("long")
        first, _ = r31._simulate_segment(segments[0], {}, {0: zone})
        second, audit = r31._simulate_segment(segments[1], {}, {})
        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertEqual(audit["breaks"], 0)


if __name__ == "__main__":
    unittest.main()
