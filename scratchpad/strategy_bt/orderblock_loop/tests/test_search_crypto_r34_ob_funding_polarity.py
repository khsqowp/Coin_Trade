from __future__ import annotations

import csv
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa

from crypto import Bar, FundingEvent, Zone
import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r34_ob_funding_polarity as r34

HOUR = 3_600_000
CLOSE = 100 * HOUR


def event(timestamp, rate=-0.001, mark=100.0, *, gap=False, fallback=False):
    return FundingEvent(timestamp, rate, mark, coverage_gap=gap,
                        used_candle_close_fallback=fallback)


def confirmation(timestamp=CLOSE - HOUR):
    return Bar(timestamp, 100, 101, 99, 100.5, 1000)


def zone(direction="long"):
    return Zone(0, 0, direction, 99.0, 101.0, 1.0)


class FundingPolarityTests(unittest.TestCase):
    def test_event_at_one_hour_buffer_boundary_is_eligible(self):
        ok, reason = r34._funding_filter(
            zone(), confirmation(), {CLOSE - HOUR: event(CLOSE - HOUR)})
        self.assertTrue(ok)
        self.assertEqual(reason, "accepted")

    def test_event_less_than_one_hour_before_close_is_not_used(self):
        for timestamp in (CLOSE - HOUR + 1, CLOSE - 1, CLOSE, CLOSE + 1):
            with self.subTest(timestamp=timestamp):
                ok, reason = r34._funding_filter(
                    zone(), confirmation(), {timestamp: event(timestamp)})
                self.assertFalse(ok)
                self.assertEqual(reason, "no_prior_event")

    def test_event_at_close_or_after_close_is_not_used(self):
        for timestamp in (CLOSE, CLOSE + 1):
            with self.subTest(timestamp=timestamp):
                ok, reason = r34._funding_filter(
                    zone(), confirmation(), {timestamp: event(timestamp)})
                self.assertFalse(ok)
                self.assertEqual(reason, "no_prior_event")

    def test_latest_gap_rejects_without_falling_back_to_older_valid_event(self):
        old_ts, gap_ts = CLOSE - 2 * HOUR, CLOSE - HOUR
        ok, reason = r34._funding_filter(
            zone(), confirmation(),
            {old_ts: event(old_ts), gap_ts: event(gap_ts, gap=True, mark=None)})
        self.assertFalse(ok)
        self.assertEqual(reason, "coverage_gap")

    def test_gap_after_confirmation_does_not_affect_past_decision(self):
        valid_ts, future_gap = CLOSE - HOUR, CLOSE + 1
        ok, reason = r34._funding_filter(
            zone(), confirmation(),
            {valid_ts: event(valid_ts), future_gap: event(future_gap, gap=True, mark=None)})
        self.assertTrue(ok)
        self.assertEqual(reason, "accepted")

    def test_new_valid_event_after_gap_is_used(self):
        old_ts, gap_ts, new_ts = CLOSE - 5 * HOUR, CLOSE - 4 * HOUR, CLOSE - HOUR
        ok, reason = r34._funding_filter(
            zone(), confirmation(),
            {old_ts: event(old_ts), gap_ts: event(gap_ts, gap=True, mark=None),
             new_ts: event(new_ts)})
        self.assertTrue(ok)
        self.assertEqual(reason, "accepted")

    def test_twelve_hour_age_is_inclusive_and_one_millisecond_older_is_stale(self):
        for age, expected in ((HOUR, "accepted"), (12 * HOUR, "accepted"),
                              (12 * HOUR + 1, "stale")):
            ts = CLOSE - age
            ok, reason = r34._funding_filter(
                zone(), confirmation(), {ts: event(ts)})
            self.assertEqual(ok, expected == "accepted")
            self.assertEqual(reason, expected)

    def test_long_short_opposite_polarity_is_symmetric(self):
        long_ok = r34._funding_filter(
            zone("long"), confirmation(), {CLOSE - HOUR: event(CLOSE - HOUR, -0.001)})
        long_bad = r34._funding_filter(
            zone("long"), confirmation(), {CLOSE - HOUR: event(CLOSE - HOUR, +0.001)})
        short_ok = r34._funding_filter(
            zone("short"), confirmation(), {CLOSE - HOUR: event(CLOSE - HOUR, +0.001)})
        short_bad = r34._funding_filter(
            zone("short"), confirmation(), {CLOSE - HOUR: event(CLOSE - HOUR, -0.001)})
        self.assertTrue(long_ok[0])
        self.assertFalse(long_bad[0])
        self.assertTrue(short_ok[0])
        self.assertFalse(short_bad[0])

    def test_neutral_nonfinite_and_out_of_range_rates_are_rejected(self):
        cases = ((0.0, "neutral_rate"), (math.nan, "invalid_rate"),
                 (math.inf, "invalid_rate"), (-math.inf, "invalid_rate"),
                 (1.0, "invalid_rate"), (-1.0, "invalid_rate"))
        for rate, expected in cases:
            with self.subTest(rate=rate):
                ok, reason = r34._funding_filter(
                    zone(), confirmation(), {CLOSE - HOUR: event(CLOSE - HOUR, rate)})
                self.assertFalse(ok)
                self.assertEqual(reason, expected)

    def test_missing_invalid_or_close_fallback_mark_is_rejected(self):
        cases = ((None, False), (math.nan, False), (math.inf, False),
                 (0.0, False), (-1.0, False), (100.0, True))
        for mark, fallback in cases:
            with self.subTest(mark=mark, fallback=fallback):
                ok, reason = r34._funding_filter(
                    zone(), confirmation(),
                    {CLOSE - HOUR: event(CLOSE - HOUR, mark=mark, fallback=fallback)})
                self.assertFalse(ok)
                self.assertEqual(reason, "invalid_or_fallback_mark")

    def test_funding_key_must_match_event_timestamp(self):
        with self.assertRaisesRegex(ValueError, "key and event timestamp"):
            r34._funding_filter(
                zone(), confirmation(), {CLOSE - HOUR: event(CLOSE - 2)})

    def _barsets(self):
        bars = [Bar(i * HOUR, 100, 100.5, 99.5, 100, 1000) for i in range(32)]
        bars[5] = Bar(5 * HOUR, 100, 100.9, 99.5, 100.7, 1000)
        bars[6] = Bar(6 * HOUR, 100.7, 101.8, 100.6, 101.7, 1000)
        four_hour = []
        for start in range(0, 32, 4):
            group = bars[start:start + 4]
            four_hour.append(Bar(group[0].timestamp, group[0].open,
                                 max(item.high for item in group),
                                 min(item.low for item in group),
                                 group[-1].close, sum(item.volume for item in group)))
        funding = {
            5 * HOUR: event(5 * HOUR, -0.001),
            8 * HOUR: event(8 * HOUR, 0.0002),
        }
        return ([ ("BTCUSDT", bars, funding, 0) ],
                [("BTCUSDT", four_hour, {}, 0)], funding)

    def test_real_r14_mapper_setup_and_simulator_keep_full_funding_path(self):
        bars1, bars4, funding = self._barsets()
        generated_zone = zone("long")
        generated_zone = Zone(0, 0, "long", 99.0, 101.0, 1.0)
        observed = []
        original_simulate = r14.simulate_trade

        def capture(*args, **kwargs):
            observed.append(kwargs["funding"])
            return original_simulate(*args, **kwargs)

        with patch.object(r14, "r4_zones", return_value=[generated_zone]), \
                patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "simulate_trade", side_effect=capture):
            result = r34._trial_with_funding_filter(bars1, bars4)
        self.assertEqual(result["funding_filter_candidates"], 1)
        self.assertEqual(result["funding_filter_accepted"], 1)
        self.assertEqual(result["m2_signal_count"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(len(observed), 1)
        self.assertEqual(set(observed[0]), set(funding))
        self.assertEqual(result["funding_filter_candidates"],
                         result["funding_filter_accepted"] +
                         sum(result[f"funding_filter_{name}"] for name in (
                             "no_prior_event", "stale", "coverage_gap", "invalid_rate",
                             "neutral_rate", "invalid_or_fallback_mark", "polarity_mismatch")))

    def test_filter_uses_valid_event_before_segment_start_but_simulator_map_is_unchanged(self):
        bars = [Bar(8 * HOUR + i * HOUR, 100, 100.5, 99.5, 100, 1000)
                for i in range(32)]
        bars[1] = Bar(9 * HOUR, 100, 100.9, 99.5, 100.7, 1000)
        bars[2] = Bar(10 * HOUR, 100.7, 101.8, 100.6, 101.7, 1000)
        four_hour = [Bar(i * 4 * HOUR, 100, 100.5, 99.5, 100, 4000)
                     for i in range(8)]
        funding = {7 * HOUR + HOUR // 2: event(7 * HOUR + HOUR // 2, -0.001)}
        barsets_1h = [("BTCUSDT", bars, funding, 0)]
        barsets_4h = [("BTCUSDT", four_hour, {}, 0)]
        observed = []
        original_simulate = r14.simulate_trade
        generated_zone = Zone(1, 1, "long", 99.0, 101.0, 1.0)

        def capture(*args, **kwargs):
            observed.append(kwargs["funding"])
            return original_simulate(*args, **kwargs)

        with patch.object(r14, "r4_zones", return_value=[generated_zone]), \
                patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "simulate_trade", side_effect=capture):
            result = r34._trial_with_funding_filter(barsets_1h, barsets_4h)
        self.assertEqual(result["funding_filter_accepted"], 1)
        self.assertEqual(result["m2_signal_count"], 1)
        self.assertEqual(observed, [{}])

    def test_rejected_first_touch_is_consumed_and_not_reentered(self):
        bars1, bars4, _funding = self._barsets()
        rejected = {5 * HOUR: event(5 * HOUR, +0.001)}
        bars1[0] = (bars1[0][0], bars1[0][1], rejected, bars1[0][3])
        generated_zone = Zone(0, 0, "long", 99.0, 101.0, 1.0)
        with patch.object(r14, "r4_zones", return_value=[generated_zone]), \
                patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})):
            result = r34._trial_with_funding_filter(bars1, bars4)
        self.assertEqual(result["funding_filter_candidates"], 1)
        self.assertEqual(result["funding_filter_polarity_mismatch"], 1)
        self.assertEqual(result["m2_signal_count"], 0)
        self.assertEqual(result["total_trades"], 0)

    def test_r14_monkeypatches_are_restored_after_exception(self):
        original_make, original_sim = r14._make_setup, r14._simulate_segment
        with patch.object(r14, "_trial", side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r34._trial_with_funding_filter([], [])
        self.assertIs(r14._make_setup, original_make)
        self.assertIs(r14._simulate_segment, original_sim)

    def test_duplicate_round_is_rejected_before_data_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "R34-coin"})
            with patch.object(common, "CSV_PATH", path):
                with self.assertRaisesRegex(RuntimeError, "R34 already exists"):
                    r34._ledger_state()

    def test_denominator_mismatch_fails_before_data_module_import(self):
        with patch.object(r19, "_assert_no_ledger_writer"), \
                patch.object(r34, "_ledger_state", return_value=r34.EXPECTED_ROWS - 1):
            with self.assertRaisesRegex(RuntimeError, "before market data access"):
                r34._run_locked(Path("/unused/data-root"))

    def test_funding_contract_requires_schema_and_timestamp_documentation(self):
        schema = pa.schema([
            ("calc_time", pa.int64()),
            ("last_funding_rate", pa.float64()),
            ("funding_interval_hours", pa.int64()),
        ])
        catalog = "dataset um_fundingRate"
        prereg = "rate becomes eligible only at its recorded settlement timestamp"
        r34._validate_funding_schema(schema, catalog, prereg)
        with self.assertRaisesRegex(RuntimeError, "schema contract"):
            r34._validate_funding_schema(pa.schema([("calc_time", pa.string())]),
                                         catalog, prereg)
        with self.assertRaisesRegex(RuntimeError, "timestamp contract"):
            r34._validate_funding_schema(schema, catalog, "no timing guarantee")

    def test_append_writes_one_R34_row_with_frozen_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"):
                r34._append({"status": "completed"}, "grid", "code", "fingerprint",
                            {**r34.CONFIG, "bonferroni_n": r34.EXPECTED_N})
            with path.open(newline="", encoding="utf-8") as stream:
                records = list(csv.DictReader(stream))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["round"], "R34-coin")
            self.assertEqual(records[0]["parameter_grid_hash"], "grid")
            import json
            self.assertEqual(json.loads(records[0]["metric"])["bonferroni_denominator"],
                             r34.EXPECTED_N)

    def test_uncertain_append_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r19, "_assert_no_ledger_writer"), \
                    patch.object(r34.os, "write", return_value=0):
                with self.assertRaises(r34.AppendUncertainError):
                    r34._append({}, "grid", "code", "fingerprint", {})

    def test_run_locks_are_exclusive_and_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_dir = root / "cache/orderblock/runs"
            lock_dir.mkdir(parents=True)
            first = r34._acquire_locks(root)
            try:
                with self.assertRaises(FileExistsError):
                    r34._acquire_locks(root)
            finally:
                r34._release_locks(first)
            self.assertEqual(list(lock_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
