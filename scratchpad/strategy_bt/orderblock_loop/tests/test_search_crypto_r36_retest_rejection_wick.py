from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r36_retest_rejection_wick as r36
from crypto import Bar, FundingEvent, Zone

HOUR = r14.DURATION_MS
FOUR_HOURS = r14.ZONE_DURATION_MS


def bar(i, open_=100, high=100.5, low=99.5, close=100):
    return Bar(i * HOUR, open_, high, low, close, 1000)


class RetestWickTests(unittest.TestCase):
    def test_long_lower_wick_equal_to_body_passes(self):
        candle = Bar(0, 10, 12, 8, 11, 1)  # body=1, lower wick=2
        self.assertEqual(r36._wick_pass(candle, "long"), (True, "accepted"))

    def test_short_upper_wick_equal_to_body_passes(self):
        candle = Bar(0, 10, 12, 9, 11, 1)  # body=1, upper wick=1
        self.assertEqual(r36._wick_pass(candle, "short"), (True, "accepted"))

    def test_wick_shorter_than_body_fails(self):
        candle = Bar(0, 10, 11.2, 9.2, 11, 1)
        self.assertEqual(r36._wick_pass(candle, "long"),
                         (False, "wick_shorter_than_body"))

    def test_doji_requires_positive_directional_wick(self):
        self.assertEqual(r36._wick_pass(Bar(0, 10, 11, 9, 10, 1), "long"),
                         (True, "accepted"))
        self.assertEqual(r36._wick_pass(Bar(0, 10, 11, 10, 10, 1), "long"),
                         (False, "wick_shorter_than_body"))

    def test_flat_bad_ohlc_nonfinite_and_direction_fail_closed(self):
        self.assertEqual(r36._wick_pass(Bar(0, 10, 10, 10, 10, 1), "long"),
                         (False, "flat_range"))
        self.assertEqual(r36._wick_pass(Bar(0, 10, 9, 11, 10, 1), "long"),
                         (False, "invalid_ohlc"))
        self.assertEqual(r36._wick_pass(Bar(0, 10, float("nan"), 9, 10, 1), "long"),
                         (False, "invalid_ohlc"))
        self.assertEqual(r36._wick_pass(Bar(0, 10, 12, 9, 11, 1), "flat"),
                         (False, "invalid_direction_or_wick"))

    def test_real_bos_mapping_and_R14_simulator_accept_wick(self):
        bars4 = [Bar(i * FOUR_HOURS, 100, 101, 99, 100, 1000) for i in range(25)]
        bars4[10] = Bar(10 * FOUR_HOURS, 100, 110, 99, 100, 1000)
        bars4[19] = Bar(19 * FOUR_HOURS, 101, 102, 99, 100, 1000)
        bars4[20] = Bar(20 * FOUR_HOURS, 100, 112, 99, 111, 1000)
        bars1 = [bar(i) for i in range(25 * 4)]
        bars1[85] = bar(85, 101, 101.5, 100.6, 101.4)
        for i in range(86, 94):
            bars1[i] = bar(i, 102, 103, 101.5, 102.5)
        bars1[94] = bar(94, 102.5, 110, 102, 109)
        funding_event = FundingEvent(88 * HOUR, 0.001, 102.5)
        captured = []
        simulate = r14.simulate_trade

        def capture(*args, **kwargs):
            trade = simulate(*args, **kwargs)
            captured.append(trade)
            return trade

        stats = {"valid_r14_setups": 0, "wick_accepted_setups": 0,
                 "wick_rejected_setups": 0}
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "simulate_trade", side_effect=capture):
            result = r36._trial_with_filter(
                [("BTCUSDT", bars1, {funding_event.timestamp: funding_event}, 0)],
                [("BTCUSDT", bars4, {}, 0)])
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 1)
        self.assertEqual(result["valid_r14_setups"], 1)
        self.assertEqual(result["wick_accepted_setups"], 1)
        self.assertEqual(result["wick_rejected_setups"], 0)
        self.assertEqual(len(captured), 1)
        self.assertAlmostEqual(captured[0].cost_bps, 12)
        self.assertEqual(captured[0].funding_order_policy, "adverse_only")
        self.assertLess(captured[0].funding_return, 0)

    def test_real_R14_setup_is_rejected_when_wick_is_too_short(self):
        bars1 = [bar(i) for i in range(140)]
        bars1[101] = bar(101, 90.5, 91.0, 90.3, 90.8)
        bars1[102] = bar(102, 92.0, 94.0, 91.5, 93.5)
        bars4 = [Bar(i * FOUR_HOURS, 100, 110, 90, 100, 4000) for i in range(32)]
        zone = Zone(24, 22, "long", 89, 91, 1)
        original = r14.r4_zones
        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[zone]):
            result = r36._trial_with_filter(
                [("BTCUSDT", bars1, {}, 0)], [("BTCUSDT", bars4, {}, 0)])
        self.assertIs(r14.r4_zones, original)
        self.assertEqual(result["valid_r14_setups"], 1)
        self.assertEqual(result["wick_rejected_setups"], 1)
        self.assertEqual(result["total_trades"], 0)

    def test_future_price_mutation_cannot_change_confirmed_wick_decision(self):
        bars1 = [bar(i) for i in range(140)]
        bars1[101] = bar(101, 90.5, 91.0, 89.8, 90.8)
        bars1[102] = bar(102, 92.0, 92.5, 91.5, 92.2)
        bars4 = [Bar(i * FOUR_HOURS, 100, 110, 90, 100, 4000) for i in range(32)]
        zone = Zone(24, 22, "long", 89, 91, 1)

        def run(one_hour):
            with patch.object(r14, "_expected_symbols",
                              return_value=frozenset({"BTCUSDT"})), \
                    patch.object(r14, "r4_zones", return_value=[zone]):
                return r36._trial_with_filter(
                    [("BTCUSDT", one_hour, {}, 0)], [("BTCUSDT", bars4, {}, 0)])

        before = run(bars1)
        changed = list(bars1)
        for i in range(103, len(changed)):
            changed[i] = bar(i, 80, 200 + i, 20, 150 + i)
        after = run(changed)
        keys = ("valid_r14_setups", "wick_accepted_setups", "wick_rejected_setups")
        self.assertEqual(tuple(before[k] for k in keys), tuple(after[k] for k in keys))
        self.assertEqual(before["wick_accepted_setups"], 1)

    def test_filter_patch_is_restored_after_exception(self):
        original = r14._make_setup
        with patch.object(r14, "_trial", side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                r36._trial_with_filter([], [])
        self.assertIs(r14._make_setup, original)

    def test_duplicate_round_rejected_before_price_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
                writer.writeheader()
                writer.writerow({"round": "R36-coin"})
            with patch.object(common, "CSV_PATH", path):
                with self.assertRaisesRegex(RuntimeError, "R36 already exists"):
                    r36._ledger_state()

    def test_append_writes_single_row_with_frozen_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "TRAIN_TRIALS.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            with patch.object(common, "CSV_PATH", path), \
                    patch.object(r36.r19, "_assert_no_ledger_writer"):
                r36._append({"status": "completed"}, "grid", "code", "fingerprint",
                            r36.EXPECTED_N,
                            {**r36.CONFIG, "bonferroni_n": r36.EXPECTED_N})
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["round"], "R36-coin")
            metric = json.loads(rows[0]["metric"])
            self.assertEqual(metric["bonferroni_denominator"], r36.EXPECTED_N)
            self.assertEqual(metric["train_input_fingerprint"], "fingerprint")

    def test_duplicate_locks_fail_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cache/orderblock/runs").mkdir(parents=True)
            first = r36._acquire_locks(root)
            try:
                with self.assertRaises(FileExistsError):
                    r36._acquire_locks(root)
            finally:
                r36._release_locks(first)
            self.assertEqual(list((root / "cache/orderblock/runs").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
