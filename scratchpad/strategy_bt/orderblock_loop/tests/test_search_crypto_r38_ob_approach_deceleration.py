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
import search_crypto_r38_ob_approach_deceleration as r38
from crypto import Bar, Zone

H = r14.DURATION_MS
H4 = r14.ZONE_DURATION_MS


def bar(i, open_, high, low, close, *, complete=True, timestamp=None):
    return Bar(i * H if timestamp is None else timestamp, open_, high, low,
               close, 1000, complete)


def direct_fixture(direction="long"):
    zone = Zone(10, 8, direction, 99, 101, 1)
    if direction == "long":
        seq = [bar(i, c + 0.5, c + 0.75, c - 0.25, c)
               for i, c in zip((17, 18, 19), (110, 108, 106))]
    else:
        seq = [bar(i, c - 0.5, c + 0.25, c - 0.75, c)
               for i, c in zip((17, 18, 19), (90, 92, 94))]
    touch = bar(20, 101, 102, 100.1, 101.5)
    bars = [*([bar(i, 105, 106, 104, 105) for i in range(17)]), *seq, touch]
    return zone, bars


def eligible_r14_fixture(touch_index=88):
    bars4 = [Bar(i * H4, 100, 101, 99, 100, 1000) for i in range(30)]
    bars4[10] = Bar(10 * H4, 100, 110, 99, 100, 1000)
    bars4[19] = Bar(19 * H4, 101, 102, 99, 100, 1000)
    bars4[20] = Bar(20 * H4, 100, 112, 99, 111, 1000)
    bars1 = [bar(i, 105, 106, 104, 105) for i in range(30 * 4)]
    for i in range(84, touch_index):
        bars1[i] = bar(i, 103.5, 104, 103, 103.5)
    # Approach candles stay fully above the mapped long zone, descend,
    # and have nonincreasing absolute bodies.
    for i, close in zip(range(touch_index - 3, touch_index), (108, 106, 104)):
        bars1[i] = bar(i, close + 0.5, close + 0.75, close - 0.25, close)
    bars1[touch_index] = bar(touch_index, 101, 102, 100.1, 101.5)
    bars1[touch_index + 1] = bar(touch_index + 1, 101.5, 102, 101, 101.7)
    return bars1, bars4


class ApproachFilterTests(unittest.TestCase):
    def test_long_and_short_directional_patterns_pass(self):
        for direction in ("long", "short"):
            zone, bars = direct_fixture(direction)
            self.assertEqual(r38._approach_pass(zone, bars, 20), (True, "accepted"))

    def test_equal_bodies_are_allowed(self):
        zone, bars = direct_fixture()
        for i, close in zip((17, 18, 19), (110, 108, 106)):
            bars[i] = bar(i, close + 1, close + 1.25, close - 0.25, close)
        self.assertTrue(r38._approach_pass(zone, bars, 20)[0])

    def test_close_tie_is_rejected(self):
        zone, bars = direct_fixture()
        bars[18] = bar(18, 110.5, 111, 109.5, 110)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1],
                         "approach_not_strictly_descending")

    def test_increasing_body_is_rejected(self):
        zone, bars = direct_fixture()
        bars[19] = bar(19, 108, 108.5, 105, 106)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1],
                         "approach_body_increased")

    def test_approach_contact_or_overlap_is_rejected(self):
        zone, bars = direct_fixture()
        bars[18] = bar(18, 108.5, 109, 100.9, 108)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1],
                         "approach_touched_or_entered_zone")

    def test_activation_boundary_requires_three_post_activation_bars(self):
        zone, bars = direct_fixture()
        zone = Zone(18, 8, "long", 99, 101, 1)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1],
                         "insufficient_post_activation_history")

    def test_incomplete_approach_and_incomplete_touch_are_rejected(self):
        zone, bars = direct_fixture()
        bars[18] = Bar(bars[18].timestamp, bars[18].open, bars[18].high,
                       bars[18].low, bars[18].close, bars[18].volume, False)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1],
                         "incomplete_or_invalid_approach")
        zone, bars = direct_fixture()
        bars[20] = Bar(bars[20].timestamp, bars[20].open, bars[20].high,
                       bars[20].low, bars[20].close, bars[20].volume, False)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1],
                         "incomplete_or_invalid_approach")

    def test_invalid_ohlc_is_rejected(self):
        zone, bars = direct_fixture()
        bars[19] = Bar(19 * H, 106, 105, 104, 106, 1000)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1],
                         "incomplete_or_invalid_approach")

    def test_gap_between_approach_bars_is_rejected(self):
        zone, bars = direct_fixture()
        source = bars[18]
        bars[18] = Bar(source.timestamp + 2 * H, source.open, source.high,
                       source.low, source.close, source.volume)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1], "approach_gap")

    def test_gap_between_last_approach_and_touch_is_rejected(self):
        zone, bars = direct_fixture()
        source = bars[20]
        bars[20] = Bar(source.timestamp + H, source.open, source.high,
                       source.low, source.close, source.volume)
        self.assertEqual(r38._approach_pass(zone, bars, 20)[1], "approach_gap")

    def test_future_bar_mutations_do_not_change_filter_decision(self):
        zone, bars = direct_fixture()
        before = r38._approach_pass(zone, bars, 20)
        mutated = list(bars) + [bar(21, 1, 2, 0, 1)]
        self.assertEqual(r38._approach_pass(zone, mutated, 20), before)

    def test_real_r14_mapper_setup_and_simulator_accept_approach(self):
        bars1, bars4 = eligible_r14_fixture()
        captured = []
        simulate = r14.simulate_trade

        def capture(*args, **kwargs):
            result = simulate(*args, **kwargs)
            captured.append(result)
            return result

        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "simulate_trade", side_effect=capture):
            result = r38._trial_with_filter(
                [("BTCUSDT", bars1, {}, 0)], [("BTCUSDT", bars4, {}, 0)])
        self.assertEqual(result["valid_r14_setups"], 1)
        self.assertEqual(result["approach_accepted_setups"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].setup.entry_index, 89)
        self.assertEqual(captured[0].setup.entry_price, bars1[89].open)
        self.assertAlmostEqual(captured[0].cost_bps, 12)
        self.assertEqual(captured[0].funding_order_policy, "adverse_only")

    def test_unscorable_funding_stays_in_m2_but_not_scoreable_trade_count(self):
        bars1, bars4 = eligible_r14_fixture()
        missing = r14.FundingEvent(90 * H, 0.001, None, coverage_gap=True)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r38._trial_with_filter(
                [("BTCUSDT", bars1, {missing.timestamp: missing}, 0)],
                [("BTCUSDT", bars4, {}, 0)])
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["unscorable_funding_trades"], 1)
        self.assertEqual(result["m2_signal_count"], 1)
        self.assertEqual(result["m2_target_hits"], 1)

    def test_filter_rejection_consumes_first_zone_touch(self):
        bars1, bars4 = eligible_r14_fixture()
        # Break monotonicity at the first valid R14 setup; a later touch must
        # not reactivate the same parent zone.
        bars1[86] = bar(86, 106, 107, 105, 106)
        bars1[95] = bar(95, 101, 102, 100.1, 101.5)
        bars1[96] = bar(96, 101.5, 102, 101, 101.7)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r38._trial_with_filter(
                [("BTCUSDT", bars1, {}, 0)], [("BTCUSDT", bars4, {}, 0)])
        self.assertEqual(result["valid_r14_setups"], 1)
        self.assertEqual(result["approach_rejected_setups"], 1)
        self.assertEqual(result["total_trades"], 0)
        self.assertEqual(result["first_touches"], 1)

    def test_future_four_hour_changes_do_not_change_pre_touch_filter(self):
        bars1, bars4 = eligible_r14_fixture()

        def evaluate(four_hourly):
            with patch.object(r14, "_expected_symbols",
                              return_value=frozenset({"BTCUSDT"})):
                return r38._trial_with_filter(
                    [("BTCUSDT", bars1, {}, 0)],
                    [("BTCUSDT", four_hourly, {}, 0)])

        before = evaluate(bars4)
        mutated = list(bars4)
        for i in range(22, len(mutated)):
            old = mutated[i]
            mutated[i] = Bar(old.timestamp, 70, 250 + i, 20, 180 + i, old.volume)
        after = evaluate(mutated)
        for key in ("valid_r14_setups", "approach_accepted_setups",
                    "approach_rejected_setups", "m2_signal_count"):
            self.assertEqual(before[key], after[key])

    def test_first_touch_without_complete_exit_path_is_right_censored_not_m2(self):
        bars1, bars4 = eligible_r14_fixture(touch_index=108)
        for i in range(110, len(bars1)):
            bars1[i] = bar(i, 101.5, 102, 101, 101.5)
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r38._trial_with_filter(
                [("BTCUSDT", bars1, {}, 0)], [("BTCUSDT", bars4, {}, 0)])
        self.assertEqual(result["right_censored_setups"], 1)
        self.assertEqual(result["total_trades"], 0)
        self.assertEqual(result["m2_signal_count"], 0)
        self.assertEqual(result["scoreable_trade_count"], 0)

    def test_result_contract_rejects_inconsistent_m2_denominator(self):
        bad = {"total_trades": 2, "trades": 2,
               "unscorable_funding_trades": 0,
               "m2_signal_count": 1, "m2_target_hits": 1}
        with self.assertRaisesRegex(ValueError, "denominators do not reconcile"):
            r38._validate_result_contract(bad)

    def test_bar_close_cutoff_rejects_later_completed_candle(self):
        late = Bar(r38.CUTOFF_MS - H + 1, 100, 101, 99, 100, 1000)
        with self.assertRaisesRegex(ValueError, "post-cutoff bar"):
            r38._assert_cutoff_bars([("BTCUSDT", [late], {}, 0)], "1h")

    def test_cutoff_metadata_reader_requests_only_non_price_columns(self):
        calls = []

        class MetadataTable:
            schema = SimpleNamespace(names=["open_time", "complete"])

            def __init__(self, complete):
                self.complete = complete

            def column(self, name):
                return SimpleNamespace(to_pylist=lambda: self.complete)

        def reader(path, *, columns, filters):
            calls.append((path, columns, filters))
            return MetadataTable([True, False])

        self.assertTrue(r38._metadata_has_complete_cutoff_bar(
            "fake.parquet", "1h", reader))
        self.assertEqual(calls, [("fake.parquet", ["open_time", "complete"],
                                  [("open_time", "<=", r38.CUTOFF_MS - H)])])

    def test_cutoff_metadata_reader_rejects_only_incomplete_prefix_rows(self):
        class MetadataTable:
            schema = SimpleNamespace(names=["open_time", "complete"])

            def column(self, _name):
                return SimpleNamespace(to_pylist=lambda: [False, False])

        self.assertFalse(r38._metadata_has_complete_cutoff_bar(
            "fake.parquet", "4h", lambda *_a, **_kw: MetadataTable()))


class RunnerSafetyTests(unittest.TestCase):
    def test_duplicate_round_rejected_before_market_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": r38.ROUND})
            with patch.object(common, "CSV_PATH", ledger):
                with self.assertRaisesRegex(RuntimeError, "R38 already exists"):
                    r38._ledger_state()

    def test_row_count_mismatch_fails_before_data_or_append(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r38.r19, "_assert_no_ledger_writer"), \
                patch.object(r38, "_ledger_state", return_value=r38.EXPECTED_ROWS - 1), \
                patch.object(r38, "_append") as append, \
                patch.dict("sys.modules", {"data_access": SimpleNamespace(
                    iter_train_bars=lambda **_kwargs: self.fail("loader must not run")
                )}):
            with self.assertRaisesRegex(RuntimeError, "before price data"):
                r38._run_locked(Path(tmp))
        append.assert_not_called()

    def test_prereg_hash_mismatch_fails_before_data_or_append(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r38.r19, "_assert_no_ledger_writer"), \
                patch.object(r38, "_ledger_state", return_value=r38.EXPECTED_ROWS), \
                patch.object(r38, "_MASTER_SHA", "wrong"), \
                patch.object(r38, "_append") as append, \
                patch.dict("sys.modules", {"data_access": SimpleNamespace(
                    iter_train_bars=lambda **_kwargs: self.fail("loader must not run")
                )}):
            with self.assertRaisesRegex(RuntimeError, "before price data"):
                r38._run_locked(Path(tmp))
        append.assert_not_called()

    def test_imported_source_hash_mismatch_fails_before_data_or_append(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r38.r19, "_assert_no_ledger_writer"), \
                patch.object(r38, "_ledger_state", return_value=r38.EXPECTED_ROWS), \
                patch.object(r38, "_IMPORT_CODE_SHA", "wrong-source-hash"), \
                patch.object(r38, "_append") as append, \
                patch.dict("sys.modules", {"data_access": SimpleNamespace(
                    iter_train_bars=lambda **_kwargs: self.fail("loader must not run")
                )}):
            with self.assertRaisesRegex(RuntimeError, "source changed after import"):
                r38._run_locked(Path(tmp))
        append.assert_not_called()

    def test_split_fingerprint_mismatch_fails_before_market_loader_or_append(self):
        fake_data_access = SimpleNamespace(iter_train_bars=lambda **_kw: self.fail("loader ran"))
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r38.r19, "_assert_no_ledger_writer"), \
                patch.object(r38, "_ledger_state", return_value=r38.EXPECTED_ROWS), \
                patch.object(r38, "_code_hash", return_value="fixed"), \
                patch.object(r38.r29, "_split_cache_state", return_value=("wrong", 1)), \
                patch.object(r38, "_append") as append, \
                patch.dict("sys.modules", {"data_access": fake_data_access}):
            with self.assertRaisesRegex(RuntimeError, "split fingerprint differs"):
                r38._run_locked(Path(tmp))
        append.assert_not_called()

    def test_minimum_metadata_symbol_gate_fails_before_candle_loader(self):
        fake_data_access = SimpleNamespace(iter_train_bars=lambda **_kw: self.fail("loader ran"))
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r38.r19, "_assert_no_ledger_writer"), \
                patch.object(r38, "_ledger_state", return_value=r38.EXPECTED_ROWS), \
                patch.object(r38, "_code_hash", return_value="fixed"), \
                patch.object(r38.r29, "_split_cache_state",
                             return_value=(r38.EXPECTED_SPLIT_SHA, 7)), \
                patch.object(r38, "_metadata_usable_symbols", return_value=set(range(29))), \
                patch.object(r38.r14, "_load_barsets") as loader, \
                patch.object(r38, "_append") as append, \
                patch.dict("sys.modules", {"data_access": fake_data_access}):
            with self.assertRaisesRegex(RuntimeError, "fewer than 30 metadata-verified"):
                r38._run_locked(Path(tmp))
        loader.assert_not_called()
        append.assert_not_called()

    def test_loaded_symbol_shortfall_is_unscorable_not_a_strategy_result(self):
        fake_data_access = SimpleNamespace(iter_train_bars=lambda **_kw: None)
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r38.r19, "_assert_no_ledger_writer"), \
                patch.object(r38, "_ledger_state", return_value=r38.EXPECTED_ROWS), \
                patch.object(r38.r29, "_split_cache_state",
                             side_effect=[(r38.EXPECTED_SPLIT_SHA, 7),
                                          (r38.EXPECTED_SPLIT_SHA, 7)]), \
                patch.object(r38, "_metadata_usable_symbols",
                             return_value=set(range(30))), \
                patch.object(r38.r14, "_load_barsets", return_value=[]), \
                patch.object(r38.r27, "_usable_symbols", return_value=set(range(29))), \
                patch.object(r38, "_trial_with_filter") as trial, \
                patch.object(r38, "heavy_task", return_value=__import__("contextlib").nullcontext()), \
                patch.object(r38, "_append") as append, \
                patch.dict("sys.modules", {"data_access": fake_data_access}):
            r38._run_locked(Path(tmp))
        trial.assert_not_called()
        self.assertEqual(append.call_args.args[0]["status"], "unscorable")
        self.assertEqual(append.call_args.args[0]["cutoff_safe_symbols"], 29)

    def test_active_writer_fails_before_ledger_row_scan_or_data(self):
        with patch.object(r38.r19, "_assert_no_ledger_writer",
                          side_effect=RuntimeError("writer active")), \
                patch.object(r38, "_ledger_state") as state, \
                patch.object(r38, "_append") as append:
            with self.assertRaisesRegex(RuntimeError, "writer active"):
                r38._run_locked(Path("/unused"))
        state.assert_not_called()
        append.assert_not_called()

    def test_low_disk_fails_before_split_or_data_access(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r38.r19, "_assert_no_ledger_writer"), \
                patch.object(r38, "_ledger_state", return_value=r38.EXPECTED_ROWS), \
                patch.object(r38, "_code_hash", return_value="fixed"), \
                patch.object(r38.shutil, "disk_usage",
                             return_value=SimpleNamespace(free=r38.MIN_FREE_BYTES - 1)), \
                patch.object(r38.r29, "_split_cache_state") as split, \
                patch.object(r38, "_append") as append:
            with self.assertRaisesRegex(RuntimeError, "40 GiB free"):
                r38._run_locked(Path(tmp))
        split.assert_not_called()
        append.assert_not_called()

    def test_shared_locks_exclude_second_runner_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cache/orderblock/runs").mkdir(parents=True)
            held = r38._acquire_locks(root)
            try:
                self.assertEqual(len(held), 2)
                with self.assertRaises(FileExistsError):
                    r38._acquire_locks(root)
            finally:
                r38._release_locks(held)
            self.assertEqual(list((root / "cache/orderblock/runs").iterdir()), [])

    def test_temp_ledger_append_records_source_manifest_and_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            config = {**r38.CONFIG, "bonferroni_n": r38.EXPECTED_N}
            manifest = {"runner.py": "abc"}
            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r38.r19, "_assert_no_ledger_writer"):
                r38._append({"status": "completed"}, "grid", "code", manifest,
                            "fingerprint", r38.EXPECTED_N, config)
            with ledger.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            metric = json.loads(rows[0]["metric"])
            self.assertEqual(rows[0]["round"], r38.ROUND)
            self.assertEqual(metric["bonferroni_denominator"], r38.EXPECTED_N)
            self.assertEqual(metric["code_file_sha256"], manifest)

    def test_short_append_is_uncertain_and_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r38.r19, "_assert_no_ledger_writer"), \
                    patch.object(r38.os, "write", return_value=1):
                with self.assertRaises(r38.AppendUncertainError):
                    r38._append({"status": "completed"}, "grid", "code", {},
                                "fingerprint", r38.EXPECTED_N,
                                {**r38.CONFIG, "bonferroni_n": r38.EXPECTED_N})

    def test_fsync_failure_is_uncertain_after_single_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r38.r19, "_assert_no_ledger_writer"), \
                    patch.object(r38.os, "fsync", side_effect=OSError("synthetic fsync")), \
                    patch.object(r38.os, "write", wraps=r38.os.write) as write_mock:
                with self.assertRaises(r38.AppendUncertainError):
                    r38._append({"status": "completed"}, "grid", "code", {},
                                "fingerprint", r38.EXPECTED_N,
                                {**r38.CONFIG, "bonferroni_n": r38.EXPECTED_N})
            self.assertEqual(write_mock.call_count, 1)

    def test_close_failure_is_uncertain_after_single_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            ledger.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            close = r38.os.close

            def close_then_raise(fd):
                close(fd)
                raise OSError("synthetic close")

            with patch.object(common, "CSV_PATH", ledger), \
                    patch.object(r38.r19, "_assert_no_ledger_writer"), \
                    patch.object(r38.os, "close", side_effect=close_then_raise), \
                    patch.object(r38.os, "write", wraps=r38.os.write) as write_mock:
                with self.assertRaises(r38.AppendUncertainError):
                    r38._append({"status": "completed"}, "grid", "code", {},
                                "fingerprint", r38.EXPECTED_N,
                                {**r38.CONFIG, "bonferroni_n": r38.EXPECTED_N})
            self.assertEqual(write_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
