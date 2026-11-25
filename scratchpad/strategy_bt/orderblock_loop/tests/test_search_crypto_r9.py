import csv
import io
import json
import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from crypto import Bar, Zone
import search_crypto_r9 as r9
from search_crypto_r9 import (
    _already_recorded, _append, _nonoverlap_events, _segments, _trial, first_sweep_recovery,
    simulate_symbol,
)

BAR_MS = 14_400_000


def bar(index, *, open_=105.0, high=108.0, low=102.0, close=105.0):
    return Bar(index * BAR_MS, open_, high, low, close, 100.0)


def no_contact(index):
    return bar(index, open_=113.0, high=115.0, low=112.0, close=114.0)


def long_zone():
    return Zone(0, 0, "long", 100.0, 110.0, 2.0)


class R9SweepRecoveryTests(unittest.TestCase):
    def test_ordinary_first_retest_consumes_zone_without_trade(self):
        result = first_sweep_recovery([
            bar(0), bar(1, high=111, low=100, close=106), bar(2),
        ], long_zone())
        self.assertEqual(result.status, "ordinary_retest_consumed")
        self.assertEqual(result.consumed_index, 1)


    def test_same_bar_distal_sweep_and_full_reclaim(self):
        result = first_sweep_recovery([
            bar(0), bar(1, high=112, low=99, close=111),
        ], long_zone())
        self.assertEqual(result.status, "reclaimed_same_bar")
        self.assertEqual(result.sweep_index, 1)
        self.assertEqual(result.confirmation_index, 1)

    def test_next_bar_full_reclaim_allows_another_wick_sweep(self):
        result = first_sweep_recovery([
            bar(0), bar(1, high=108, low=99, close=105),
            bar(2, high=112, low=98, close=111),
        ], long_zone())
        self.assertEqual(result.status, "reclaimed_next_bar")
        self.assertEqual(result.sweep_index, 1)
        self.assertEqual(result.confirmation_index, 2)

    def test_recovery_decision_is_unchanged_by_later_bars(self):
        prefix = [
            bar(0), bar(1, high=108, low=99, close=105),
            bar(2, high=112, low=98, close=111),
        ]
        future = prefix + [
            bar(3, high=140, low=60, close=80),
            bar(4, high=150, low=50, close=145),
        ]
        self.assertEqual(
            first_sweep_recovery(prefix, long_zone()),
            first_sweep_recovery(future, long_zone()),
        )

    def test_distal_close_failure_prevents_later_recovery(self):
        result = first_sweep_recovery([
            bar(0), bar(1, high=108, low=99, close=100),
            bar(2, high=112, low=98, close=111),
        ], long_zone())
        self.assertEqual(result.status, "distal_close_failed")
        self.assertEqual(result.consumed_index, 1)

    def test_gap_entirely_beyond_distal_is_failure_not_a_synthetic_sweep(self):
        result = first_sweep_recovery([
            bar(0), bar(1, open_=98, high=99, low=95, close=96),
            bar(2, high=112, low=98, close=111),
        ], long_zone())
        self.assertEqual(result.status, "distal_gap_failed")
        self.assertEqual(result.consumed_index, 1)

    def test_confirmation_bar_must_reclaim_before_distal_close_failure(self):
        result = first_sweep_recovery([
            bar(0), bar(1, high=108, low=99, close=105),
            bar(2, high=108, low=98, close=100),
        ], long_zone())
        self.assertEqual(result.status, "confirmation_distal_close_failed")
        self.assertEqual(result.confirmation_index, 2)

    def test_sweep_on_final_deadline_bar_expires_without_reading_bar_49(self):
        bars = [no_contact(i) for i in range(49)]
        bars[0] = bar(0)
        bars[48] = bar(48, high=108, low=99, close=105)
        result = first_sweep_recovery(bars, long_zone())
        self.assertEqual(result.status, "expired_confirmation_outside_deadline")
        self.assertEqual(result.sweep_index, 48)
        self.assertIsNone(result.confirmation_index)

    def test_confirmation_at_bar_49_is_expired_not_censored(self):
        bars = [no_contact(i) for i in range(50)]
        bars[0] = bar(0)
        bars[48] = bar(48, high=108, low=99, close=105)
        bars[49] = bar(49, high=112, low=100, close=111)
        result = first_sweep_recovery(bars, long_zone())
        self.assertEqual(result.status, "expired_confirmation_outside_deadline")
        self.assertIsNone(result.confirmation_index)

    def test_confirmation_missing_inside_deadline_is_right_censored(self):
        bars = [bar(0), no_contact(1), no_contact(2),
                bar(3, high=108, low=99, close=105)]
        result = first_sweep_recovery(bars, long_zone())
        self.assertEqual(result.status, "confirmation_right_censored")
        self.assertEqual(result.sweep_index, 3)
        self.assertEqual(result.consumed_index, 3)

    def test_missing_confirmation_is_logged_as_gap_or_cutoff_censoring(self):
        first_segment = [bar(0), no_contact(1), no_contact(2),
                         bar(3, high=108, low=99, close=105)]
        gap_bars = first_segment + [bar(5), bar(6)]
        for bars, zones, expected in (
            (first_segment, [[long_zone()]], "cutoff_confirmation_censored"),
            (gap_bars, [[long_zone()], []], "gap_confirmation_blocked"),
        ):
            with self.subTest(expected=expected):
                writer = io.StringIO()
                with patch("search_crypto_r9.r4_zones", side_effect=zones):
                    *_, audit, _, _, _, _, _ = simulate_symbol(
                        "BTCUSDT", bars, {}, event_writer=writer,
                    )
                self.assertEqual(audit["right_censored"], 1)
                self.assertIn(expected, writer.getvalue())

    def test_first_contact_after_deadline_is_not_used(self):
        bars = [no_contact(i) for i in range(50)]
        bars[0] = bar(0)
        bars[49] = bar(49, high=112, low=99, close=111)
        result = first_sweep_recovery(bars, long_zone())
        self.assertEqual(result.status, "expired_no_contact")
        self.assertEqual(result.consumed_index, 48)

    def test_short_side_is_mirrored(self):
        zone = Zone(0, 0, "short", 100.0, 110.0, 2.0)
        result = first_sweep_recovery([
            bar(0), bar(1, open_=105, high=111, low=98, close=99),
        ], zone)
        self.assertEqual(result.status, "reclaimed_same_bar")

    def test_gaps_split_segments_without_compressing_time(self):
        bars = [bar(0), bar(1), bar(3), bar(4)]
        self.assertEqual(_segments(bars), [(0, 2), (2, 4)])

    def test_unaligned_timestamps_are_rejected(self):
        bars = [bar(0), Bar(BAR_MS + 1, 105, 108, 102, 105, 100)]
        with self.assertRaisesRegex(ValueError, "UTC boundaries"):
            _segments(bars)

    def test_duplicate_timestamps_are_rejected(self):
        bars = [bar(0), bar(0)]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            _segments(bars)

    def test_failed_next_bar_confirmation_never_enters(self):
        bars = [no_contact(i) for i in range(55)]
        bars[0] = bar(0)
        bars[1] = bar(1, high=109, low=99, close=105)
        bars[2] = bar(2, high=109, low=101, close=105)
        with patch("search_crypto_r9.r4_zones", return_value=[long_zone()]), \
                patch("search_crypto_r9.simulate_trade") as simulate:
            trades, _, _, audit, _, _, _, _, _ = simulate_symbol("BTCUSDT", bars, {})
        self.assertEqual(trades, [])
        self.assertEqual(audit["sweep_failed"], 1)
        simulate.assert_not_called()

    def test_entry_open_equal_to_stop_is_skipped(self):
        bars = [no_contact(i) for i in range(55)]
        bars[0] = bar(0)
        bars[1] = bar(1, high=109, low=99, close=105)
        bars[2] = bar(2, high=112, low=103, close=111)
        bars[3] = bar(3, open_=98.9, high=101, low=98.9, close=100)
        zone = long_zone()
        with patch("search_crypto_r9.r4_zones", return_value=[zone]), \
                patch("search_crypto_r9._atr", return_value=1.0), \
                patch("search_crypto_r9.simulate_trade") as simulate:
            trades, _, _, audit, _, _, _, _, _ = simulate_symbol("BTCUSDT", bars, {})
        self.assertEqual(trades, [])
        self.assertEqual(audit["entry_skipped"], 1)
        simulate.assert_not_called()

    def test_entry_after_data_gap_is_not_mislabeled_as_cutoff(self):
        bars = [
            bar(0), bar(1, high=112, low=99, close=111),
            bar(3), bar(4),
        ]
        with patch("search_crypto_r9.r4_zones", side_effect=[[long_zone()], []]):
            trades, _, _, audit, _, _, _, _, _ = simulate_symbol("BTCUSDT", bars, {})
        self.assertEqual(trades, [])
        self.assertEqual(audit["gap_entry_blocked"], 1)
        self.assertEqual(audit["cutoff_entry_censored"], 0)

    def test_missing_entry_at_final_train_bar_is_cutoff_censored(self):
        bars = [bar(0), bar(1, high=112, low=99, close=111)]
        with patch("search_crypto_r9.r4_zones", return_value=[long_zone()]):
            trades, _, _, audit, _, _, _, _, _ = simulate_symbol("BTCUSDT", bars, {})
        self.assertEqual(trades, [])
        self.assertEqual(audit["gap_entry_blocked"], 0)
        self.assertEqual(audit["cutoff_entry_censored"], 1)

    def test_open_trade_censor_uses_segment_boundary_not_stop_price(self):
        first_segment = [bar(0), bar(1, high=112, low=99, close=111)]
        first_segment.extend(no_contact(i) for i in range(2, 20))
        gap_bars = first_segment + [no_contact(i) for i in range(21, 25)]
        cutoff_bars = first_segment
        for bars, expected in (
            (gap_bars, (1, 0)),
            (cutoff_bars, (0, 1)),
        ):
            with self.subTest(expected=expected):
                writer = io.StringIO()
                with patch("search_crypto_r9.r4_zones", side_effect=[[long_zone()], []]), \
                        patch("search_crypto_r9._atr", return_value=1.0), \
                        patch("search_crypto_r9.simulate_trade", return_value=None):
                    *_, audit, _, _, _, _, _ = simulate_symbol(
                        "BTCUSDT", bars, {}, event_writer=writer,
                    )
                self.assertEqual(
                    (audit["gap_exit_censored"], audit["cutoff_exit_censored"]),
                    expected,
                )
                event = writer.getvalue().splitlines()[0]
                self.assertIn("gap_exit_censored" if expected[0] else "cutoff_exit_censored", event)

    def test_m2_includes_complete_price_path_even_if_funding_is_unscorable(self):
        empty_audit = {
            "zones": 1, "ordinary_retest_consumed": 0, "sweep_failed": 0,
            "reclaimed": 1, "expired": 0, "right_censored": 0,
            "gap_segments": 0, "entry_skipped": 0,
            "exit_path_censored": 0, "completed_trades": 1,
            "ignored_zones": 0, "funding_unscorable_trades": 1,
            "gap_entry_blocked": 0, "cutoff_entry_censored": 0,
            "gap_exit_censored": 0, "cutoff_exit_censored": 0,
        }
        incomplete_trade = SimpleNamespace(net_return=None, ambiguous_funding_events=0)
        result_row = (
            [incomplete_trade], [], [], empty_audit,
            [("BTCUSDT", BAR_MS, 2 * BAR_MS, 0, True, "long")], {}, {},
            {"long": {0: 0.01}, "short": {}},
            {"long": {0: 0.01}, "short": {}},
        )
        bars = [bar(0), bar(1)]
        barsets = [(f"S{i}", bars, {}, 0) for i in range(30)]
        with patch("search_crypto_r9.simulate_symbol", return_value=result_row):
            result = _trial(barsets)
        self.assertEqual(result["status"], "unscorable")
        self.assertEqual(result["m2_signal_count"], 30)
        self.assertEqual(result["m2_target_hits"], 30)
        self.assertEqual(result["m2_target_first_rate"], 1.0)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["total_trades"], 30)
        self.assertEqual(result["by_direction"]["long"]["m2_signal_count"], 30)
        self.assertEqual(result["by_direction"]["short"]["m2_signal_count"], 0)
        self.assertAlmostEqual(result["by_direction"]["long"]["cumulative_return"], 0.01)
        self.assertEqual(result["by_direction"]["short"]["cumulative_return"], 0.0)

    def test_all_entries_link_to_m2_windows_and_survive_future_extension(self):
        bars = [no_contact(index) for index in range(10)]
        bars[0] = bar(0)
        bars[1] = bar(1, high=109, low=99, close=105)
        bars[2] = bar(2, high=112, low=103, close=111)
        bars[3] = bar(3, open_=111, high=112, low=110, close=111)
        bars[4] = bar(4, open_=111, high=136, low=110, close=135)
        bars[5] = bar(5)
        bars[6] = bar(6, high=109, low=99, close=105)
        bars[7] = bar(7, high=112, low=103, close=111)
        bars[8] = bar(8, open_=111, high=112, low=110, close=111)
        bars[9] = bar(9, open_=111, high=136, low=110, close=135)
        zones = [long_zone(), Zone(5, 4, "long", 100.0, 110.0, 2.0)]

        def run_with(series):
            writer = io.StringIO()
            with patch("search_crypto_r9.r4_zones", return_value=zones), \
                    patch("search_crypto_r9._atr", return_value=1.0):
                result = simulate_symbol(
                    "BTCUSDT", series, {}, event_writer=writer,
                )
            entered = [
                row for row in map(json.loads, writer.getvalue().splitlines())
                if row.get("status") == "entered"
            ]
            return result, entered

        prefix_result, prefix_entered = run_with(bars)
        extended_result, extended_entered = run_with(
            bars + [bar(10, high=150, low=50, close=80),
                    bar(11, high=160, low=40, close=150)],
        )
        prefix_events = prefix_result[4]
        extended_events = extended_result[4]
        self.assertEqual(prefix_events, extended_events)
        self.assertEqual(len(prefix_events), 2)
        self.assertEqual(len(prefix_entered), len(prefix_events))
        self.assertEqual(prefix_entered, extended_entered)

        matched_windows = []
        for event in prefix_events:
            matches = [row for row in prefix_entered
                       if row["entry_timestamp"] == event[1]
                       and row["exit_timestamp"] + BAR_MS == event[2]]
            self.assertEqual(len(matches), 1)
            entered = matches[0]
            self.assertEqual(entered["signal_id"], r9._event_id(
                "BTCUSDT", entered["signal_timestamp"],
                entered["origin_timestamp"], entered["direction"],
            ))
            self.assertTrue(entered["m2_included"])
            matched_windows.append((event[1], event[2]))
        self.assertEqual(len(set(matched_windows)), len(prefix_events))


class R9TrialLedgerTests(unittest.TestCase):
    def test_nonoverlap_schedule_maximizes_count_by_earliest_exit(self):
        events = [
            ("BTCUSDT", 100, 1000, 1, True, "long"),
            ("BTCUSDT", 200, 500, 2, False, "short"),
            ("BTCUSDT", 1000, 1200, 3, False, "short"),
            ("ETHUSDT", 150, 400, 1, False, "short"),
        ]
        selected = _nonoverlap_events(events)
        self.assertEqual(
            [(event[0], event[3]) for event in selected],
            [("BTCUSDT", 2), ("BTCUSDT", 3), ("ETHUSDT", 1)],
        )

    def test_nonoverlap_schedule_keeps_maximum_cardinality(self):
        events = [
            ("BTCUSDT", 0, 10, 1, False, "long"),
            ("BTCUSDT", 1, 2, 2, True, "short"),
            ("BTCUSDT", 3, 4, 3, False, "long"),
        ]
        selected = _nonoverlap_events(events)
        self.assertEqual([event[3] for event in selected], [2, 3])

    def test_loader_universe_must_match_frozen_symbols_exactly(self):
        self.assertEqual(len(r9._expected_symbols()), 35)
        expected = frozenset({"BTCUSDT", "ETHUSDT"})
        r9._validate_universe(["BTCUSDT", "ETHUSDT"], expected)
        for actual in (["BTCUSDT"], ["BTCUSDT", "ETHUSDT", "XRPUSDT"],
                       ["BTCUSDT", "BTCUSDT"]):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                r9._validate_universe(actual, expected)

    def test_failed_trial_can_be_retried_but_completed_trial_cannot(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "trials.csv"
            with patch.object(r9.common, "CSV_PATH", ledger):
                _append({"status": "failed"}, "fingerprint", "",
                        "captured-code", "captured-prereg")
                grid_hash = r9.hashlib.sha256(r9.json.dumps(
                    r9.CONFIG, sort_keys=True, separators=(",", ":")
                ).encode()).hexdigest()
                self.assertFalse(_already_recorded(
                    "captured-code", grid_hash, "fingerprint", "captured-prereg",
                ))
                _append({"status": "unknown"}, "fingerprint", "",
                        "captured-code", "captured-prereg")
                self.assertFalse(_already_recorded(
                    "captured-code", grid_hash, "fingerprint", "captured-prereg",
                ))
                _append({"status": "completed"}, "fingerprint", "events.jsonl",
                        "captured-code", "captured-prereg")
                self.assertTrue(_already_recorded(
                    "captured-code", grid_hash, "fingerprint", "captured-prereg",
                ))
                self.assertFalse(_already_recorded(
                    "captured-code", grid_hash, "fingerprint", "other-prereg",
                ))

    def test_append_uses_the_code_hash_captured_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "trials.csv"
            with patch.object(r9.common, "CSV_PATH", ledger):
                with patch.object(r9, "_code_hash", return_value="later-code"):
                    _append({"status": "completed"}, "fingerprint", "events.jsonl",
                            "run-code", "run-prereg")
                with ledger.open(newline="", encoding="utf-8") as stream:
                    row = next(csv.DictReader(stream))
                self.assertEqual(row["code_sha256"], "run-code")

    def test_loaded_code_hash_rejects_source_drift_before_run(self):
        with patch.object(r9, "_LOADED_CODE_SHA", "loaded-code"), \
                patch.object(r9, "_code_hash", return_value="changed-code"):
            with self.assertRaisesRegex(RuntimeError, "changed after import"):
                r9._verified_loaded_code_hash()

    def test_loaded_code_hash_returns_the_verified_import_fingerprint(self):
        with patch.object(r9, "_LOADED_CODE_SHA", "loaded-code"), \
                patch.object(r9, "_code_hash", return_value="loaded-code"):
            self.assertEqual(r9._verified_loaded_code_hash(), "loaded-code")

    def test_loaded_prereg_hash_rejects_document_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PREREG.md"
            path.write_text("new prereg", encoding="utf-8")
            with patch.object(r9, "PREREG_PATH", path), \
                    patch.object(r9, "_LOADED_PREREG_SHA", "old-prereg"):
                with self.assertRaisesRegex(RuntimeError, "preregistration changed"):
                    r9._verified_loaded_prereg_hash()

    def test_source_drift_during_loader_is_recorded_and_stops_before_trial(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "trials.csv"
            with patch("resource_guard.heavy_task", return_value=nullcontext()), \
                    patch.object(r9, "_verified_loaded_code_hash", return_value="loaded-code"), \
                    patch.object(r9, "_load", return_value=[]), \
                    patch.object(r9, "_code_hash", return_value="changed-code"), \
                    patch.object(r9.common, "CSV_PATH", ledger):
                with self.assertRaisesRegex(RuntimeError, "source/prereg changed while TRAIN"):
                    r9.run()
            with ledger.open(newline="", encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["code_sha256"], "loaded-code")
            self.assertIn('"status":"failed"', row["metric"])

    def test_output_setup_failure_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            not_directory = root / "not-directory"
            not_directory.write_text("file", encoding="utf-8")
            ledger = root / "trials.csv"
            with patch("resource_guard.heavy_task", return_value=nullcontext()), \
                    patch.object(r9, "_load", return_value=[]), \
                    patch.object(r9, "_LOADED_CODE_SHA", "run-code"), \
                    patch.object(r9, "_code_hash", return_value="run-code"), \
                    patch.object(r9.common, "_train_input_fingerprint", return_value="fingerprint"), \
                    patch.object(r9.common, "CSV_PATH", ledger), \
                    patch.dict(os.environ, {"TRADING_DATA_DIR": str(not_directory)}):
                with self.assertRaises(NotADirectoryError):
                    r9.run()
            with ledger.open(newline="", encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["code_sha256"], "run-code")
            self.assertIn('"status":"failed"', row["metric"])

    def test_event_sync_failure_is_recorded_as_failed_trial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "trials.csv"
            with patch("resource_guard.heavy_task", return_value=nullcontext()), \
                    patch.object(r9, "_load", return_value=[]), \
                    patch.object(r9, "_LOADED_CODE_SHA", "run-code"), \
                    patch.object(r9, "_code_hash", return_value="run-code"), \
                    patch.object(r9, "_trial", return_value={"status": "completed"}), \
                    patch.object(r9.common, "_train_input_fingerprint", return_value="fingerprint"), \
                    patch.object(r9.common, "CSV_PATH", ledger), \
                    patch.object(r9.os, "fsync", side_effect=OSError("disk sync failed")), \
                    patch.dict(os.environ, {"TRADING_DATA_DIR": str(root)}):
                with self.assertRaisesRegex(OSError, "disk sync failed"):
                    r9.run()
            with ledger.open(newline="", encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["code_sha256"], "run-code")
            self.assertIn('"status":"failed"', row["metric"])


if __name__ == "__main__":
    unittest.main()
