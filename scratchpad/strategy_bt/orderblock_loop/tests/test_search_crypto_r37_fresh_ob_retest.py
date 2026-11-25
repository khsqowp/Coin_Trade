from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r37_fresh_ob_retest as r37
from crypto import Bar, FundingEvent, Zone

H = r14.DURATION_MS
H4 = r14.ZONE_DURATION_MS


def hour(i, open_=100, high=100.5, low=99.5, close=100):
    return Bar(i * H, open_, high, low, close, 1000)


def setup_fixture(touch_index):
    bars4 = [Bar(i * H4, 100, 101, 99, 100, 1000) for i in range(30)]
    bars4[10] = Bar(10 * H4, 100, 110, 99, 100, 1000)
    bars4[19] = Bar(19 * H4, 101, 102, 99, 100, 1000)
    bars4[20] = Bar(20 * H4, 100, 112, 99, 111, 1000)
    bars1 = [hour(i, 105, 106, 104, 105) for i in range(30 * 4)]
    # The BOS closes at 21*4h, activating the mapped zone at 1h index 84.
    for i in range(84, touch_index):
        bars1[i] = hour(i, 103.5, 104, 103, 103.5)
    bars1[touch_index] = hour(touch_index, 101, 102, 100.1, 101.5)
    bars1[touch_index + 1] = hour(touch_index + 1, 101.5, 102, 101, 101.7)
    return bars1, bars4


class FreshRetestTests(unittest.TestCase):
    def test_age_window_is_inclusive_and_rejects_zero_or_stale(self):
        zone = Zone(10, 8, "long", 99, 101, 1)
        self.assertEqual(r37._age_pass(zone, 10), (False, 0))
        self.assertEqual(r37._age_pass(zone, 11), (True, 1))
        self.assertEqual(r37._age_pass(zone, 14), (True, 4))
        self.assertEqual(r37._age_pass(zone, 15), (False, 5))

    def test_first_retest_ages_one_and_four_reach_real_r14_simulator(self):
        for touch_index, expected_age in ((85, 1), (88, 4)):
            with self.subTest(age=expected_age):
                bars1, bars4 = setup_fixture(touch_index)
                captured = []
                simulate = r14.simulate_trade

                def capture(*args, **kwargs):
                    trade = simulate(*args, **kwargs)
                    captured.append(trade)
                    return trade

                funding = FundingEvent(90 * H, 0.001, 102.5)
                with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                        patch.object(r14, "simulate_trade", side_effect=capture):
                    result = r37._trial_with_filter(
                        [("BTCUSDT", bars1, {funding.timestamp: funding}, 0)],
                        [("BTCUSDT", bars4, {}, 0)],
                    )
                self.assertEqual(result["valid_r14_setups"], 1)
                self.assertEqual(result["age_counts"].get(str(expected_age)), 1)
                self.assertEqual(result["age_accepted_setups"], 1)
                self.assertEqual(result["age_rejected_setups"], 0)
                self.assertEqual(result["total_trades"], 1)
                self.assertEqual(len(captured), 1)
                self.assertEqual(captured[0].setup.entry_index, touch_index + 1)
                self.assertEqual(captured[0].setup.entry_price,
                                 bars1[touch_index + 1].open)
                self.assertAlmostEqual(captured[0].cost_bps, 12)
                self.assertEqual(captured[0].funding_order_policy, "adverse_only")
                if expected_age == 4:
                    self.assertLess(captured[0].funding_return, 0)

    def test_age_five_first_touch_is_consumed_without_later_reentry(self):
        bars1, bars4 = setup_fixture(89)
        # Index 88 is not a touch; index 89 is the first touch at age five.
        bars1[95] = hour(95, 101, 102, 100.1, 101.5)
        bars1[96] = hour(96, 101.5, 102, 101, 101.7)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r37._trial_with_filter(
                [("BTCUSDT", bars1, {}, 0)], [("BTCUSDT", bars4, {}, 0)]
            )
        self.assertEqual(result["age_counts"].get("5"), 1)
        self.assertEqual(result["age_rejected_setups"], 1)
        self.assertEqual(result["total_trades"], 0)
        self.assertEqual(result["first_touches"], 1)

    def test_future_bars_after_first_touch_do_not_change_age_decision(self):
        bars1, bars4 = setup_fixture(88)

        def evaluate(hourly):
            with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
                return r37._trial_with_filter(
                    [("BTCUSDT", hourly, {}, 0)], [("BTCUSDT", bars4, {}, 0)]
                )

        before = evaluate(bars1)
        changed = list(bars1)
        for i in range(90, len(changed)):
            changed[i] = hour(i, 80, 200 + i, 20, 150 + i)
        after = evaluate(changed)
        fields = ("valid_r14_setups", "age_accepted_setups", "age_rejected_setups", "age_counts")
        self.assertEqual(tuple(before[field] for field in fields),
                         tuple(after[field] for field in fields))
        self.assertEqual(before["age_accepted_setups"], 1)

    def test_future_four_hour_bars_do_not_change_first_retest_decision(self):
        bars1, bars4 = setup_fixture(88)

        def evaluate(four_hourly):
            with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
                return r37._trial_with_filter(
                    [("BTCUSDT", bars1, {}, 0)], [("BTCUSDT", four_hourly, {}, 0)]
                )

        before = evaluate(bars4)
        changed = list(bars4)
        for i in range(22, len(changed)):
            changed[i] = Bar(changed[i].timestamp, 80, 250 + i, 20, 180 + i, 1000)
        after = evaluate(changed)
        keys = ("valid_r14_setups", "age_accepted_setups", "age_rejected_setups",
                "age_counts", "m2_signal_count", "m2_target_hits")
        self.assertEqual(tuple(before[key] for key in keys), tuple(after[key] for key in keys))
        self.assertEqual(before["age_accepted_setups"], 1)

    def test_r14_monkeypatch_is_restored_after_exception(self):
        original = r14._make_setup
        with patch.object(r14, "_trial", side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r37._trial_with_filter([], [])
        self.assertIs(r14._make_setup, original)

    def test_duplicate_round_rejected_before_any_market_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "R37-coin"})
            with patch.object(common, "CSV_PATH", ledger):
                with self.assertRaisesRegex(RuntimeError, "R37 already exists"):
                    r37._ledger_state()

    def test_row_count_prereg_gate_fails_before_data_or_append(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r37.r19, "_assert_no_ledger_writer"), \
                patch.object(r37, "_ledger_state", return_value=r37.EXPECTED_ROWS - 1), \
                patch.object(r37, "_append") as append, \
                patch.dict("sys.modules", {"data_access": SimpleNamespace(
                    iter_train_bars=lambda **_kwargs: self.fail("data access must not run")
                )}):
            with self.assertRaisesRegex(RuntimeError, "before price data"):
                r37._run_locked(Path(tmp))
        append.assert_not_called()

    def test_prereg_hash_gate_fails_before_data_or_append(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r37.r19, "_assert_no_ledger_writer"), \
                patch.object(r37, "_ledger_state", return_value=r37.EXPECTED_ROWS), \
                patch.object(r37, "_PREREG_SHA", "wrong-prereg-hash"), \
                patch.object(r37, "_append") as append, \
                patch.dict("sys.modules", {"data_access": SimpleNamespace(
                    iter_train_bars=lambda **_kwargs: self.fail("data access must not run")
                )}):
            with self.assertRaisesRegex(RuntimeError, "before price data"):
                r37._run_locked(Path(tmp))
        append.assert_not_called()

    def test_low_disk_gate_fails_before_heavy_task_or_append(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r37.r19, "_assert_no_ledger_writer"), \
                patch.object(r37, "_ledger_state", return_value=r37.EXPECTED_ROWS), \
                patch.object(r37, "_code_hash", return_value="fixed-code"), \
                patch.object(r37, "shutil") as shutil_mock, \
                patch.object(r37, "_append") as append, \
                patch.object(r37, "heavy_task") as heavy:
            shutil_mock.disk_usage.return_value = SimpleNamespace(free=r37.MIN_FREE_BYTES - 1)
            with self.assertRaisesRegex(RuntimeError, "40 GiB free"):
                r37._run_locked(Path(tmp))
        append.assert_not_called()
        heavy.assert_not_called()

    def test_shared_locks_exclude_second_r37_runner_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cache/orderblock/runs").mkdir(parents=True)
            first = r37._acquire_locks(root)
            try:
                self.assertEqual(len(first), 2)
                with self.assertRaises(FileExistsError):
                    r37._acquire_locks(root)
            finally:
                r37._release_locks(first)
            self.assertEqual(list((root / "cache/orderblock/runs").iterdir()), [])

    def test_temp_ledger_append_is_single_and_contains_frozen_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            config = {**r37.CONFIG, "bonferroni_n": r37.EXPECTED_N}
            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r37.r19, "_assert_no_ledger_writer"):
                r37._append({"status": "completed"}, "grid", "code", "fingerprint",
                            r37.EXPECTED_N, config)
            with ledger.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["round"], "R37-coin")
            self.assertEqual(json.loads(rows[0]["metric"])["bonferroni_denominator"],
                             r37.EXPECTED_N)

    def test_short_append_is_marked_uncertain_and_not_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            config = {**r37.CONFIG, "bonferroni_n": r37.EXPECTED_N}
            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r37.r19, "_assert_no_ledger_writer"), \
                    patch.object(r37.os, "write", return_value=1):
                with self.assertRaises(r37.AppendUncertainError):
                    r37._append({"status": "completed"}, "grid", "code", "fingerprint",
                                r37.EXPECTED_N, config)

    def test_fsync_failure_is_uncertain_after_single_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            config = {**r37.CONFIG, "bonferroni_n": r37.EXPECTED_N}
            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r37.r19, "_assert_no_ledger_writer"), \
                    patch.object(r37.os, "fsync", side_effect=OSError("synthetic fsync")), \
                    patch.object(r37.os, "write", wraps=r37.os.write) as write_mock:
                with self.assertRaises(r37.AppendUncertainError):
                    r37._append({"status": "completed"}, "grid", "code", "fingerprint",
                                r37.EXPECTED_N, config)
            self.assertEqual(write_mock.call_count, 1)
            with ledger.open(newline="", encoding="utf-8") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 1)

    def test_close_failure_is_uncertain_after_single_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            config = {**r37.CONFIG, "bonferroni_n": r37.EXPECTED_N}
            real_close = r37.os.close

            def close_then_raise(fd):
                real_close(fd)
                raise OSError("synthetic close")

            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r37.r19, "_assert_no_ledger_writer"), \
                    patch.object(r37.os, "close", side_effect=close_then_raise), \
                    patch.object(r37.os, "write", wraps=r37.os.write) as write_mock:
                with self.assertRaises(r37.AppendUncertainError):
                    r37._append({"status": "completed"}, "grid", "code", "fingerprint",
                                r37.EXPECTED_N, config)
            self.assertEqual(write_mock.call_count, 1)
            with ledger.open(newline="", encoding="utf-8") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 1)


if __name__ == "__main__":
    unittest.main()
