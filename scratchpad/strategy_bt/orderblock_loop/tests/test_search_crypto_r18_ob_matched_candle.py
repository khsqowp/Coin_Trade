from __future__ import annotations

import unittest
import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from crypto import Bar
import search_crypto_r18_ob_matched_candle as r18
import search_crypto as common


def bars(count: int = 300) -> list[Bar]:
    rows = []
    price = 100.0
    for i in range(count):
        change = 0.08 + (0.015 if i % 3 else -0.025)
        open_price = price
        price += change
        rows.append(Bar(i * r18.BAR_MS, open_price, max(open_price, price) + 0.4,
                        min(open_price, price) - 0.4, price, 1000 + (i % 7) * 10))
    return rows


class R18MatchedCandleTests(unittest.TestCase):
    def test_gap_splits_segments_without_compressing_time(self):
        source = bars(5)
        for i in range(3, len(source)):
            row = source[i]
            source[i] = Bar(row.timestamp + r18.BAR_MS, row.open, row.high,
                            row.low, row.close, row.volume)
        segments, gaps = r18._split_segments(source)
        self.assertEqual([len(part) for part in segments], [3, 2])
        self.assertEqual(gaps, 1)

    def test_non_monotone_or_off_grid_time_rejected(self):
        source = bars(3)
        source[2] = Bar(source[1].timestamp + 1, 100, 101, 99, 100, 10)
        with self.assertRaises(ValueError):
            r18._split_segments(source)

    def test_features_use_current_and_prior_bars_only(self):
        source = bars()
        before = r18._feature(source, 220)
        source[221:] = [Bar(row.timestamp, row.open, row.high + 500, row.low,
                            row.close + 200, row.volume * 50) for row in source[221:]]
        self.assertEqual(before, r18._feature(source, 220))

    def test_bos_signal_prefix_is_unchanged_when_future_bars_change(self):
        source = bars(500)
        baseline = [(zone.signal_index, zone.direction, zone.low, zone.high)
                    for zone in r18.r4_zones(source, "bos_origin")
                    if zone.signal_index <= 300]
        mutated = list(source)
        for i in range(301, len(mutated)):
            row = mutated[i]
            mutated[i] = Bar(row.timestamp, row.open, row.high + i * 3,
                             row.low - i * 2, row.close * 1.5, row.volume * 7)
        after = [(zone.signal_index, zone.direction, zone.low, zone.high)
                 for zone in r18.r4_zones(mutated, "bos_origin")
                 if zone.signal_index <= 300]
        self.assertEqual(baseline, after)

    def test_feature_requires_twenty_prior_bars_and_positive_volume_median(self):
        self.assertIsNone(r18._feature(bars(20), 19))
        source = bars()
        for i in range(200, 220):
            source[i] = Bar(source[i].timestamp, source[i].open, source[i].high,
                            source[i].low, source[i].close, 0)
        self.assertIsNone(r18._feature(source, 220))

    def test_caliper_includes_exact_boundary_but_rejects_beyond(self):
        base = (0.01, 0.02, 1.0, 0.5)
        edge = (0.0125, 0.025, 1.25, 0.75)
        outside = (0.012501, 0.02, 1.0, 0.5)
        self.assertIsNotNone(r18._distance(base, edge))
        self.assertIsNone(r18._distance(base, outside))

    def test_outcome_uses_next_open_and_24th_close_direction(self):
        source = bars(40)
        result = r18._outcome(source, 5, "long")
        self.assertIsNotNone(result)
        self.assertEqual(result[0], int(source[29].close > source[6].open))
        self.assertEqual(r18._outcome(source, 5, "short")[0], int(source[29].close < source[6].open))

    def test_equal_exit_is_not_a_direction_hit(self):
        source = bars(30)
        entry = source[6].open
        source[29] = Bar(source[29].timestamp, entry, entry, entry, entry, 10)
        self.assertEqual(r18._outcome(source, 5, "long"), (0, 0.0))

    def test_short_or_incomplete_result_window_is_censored(self):
        source = bars(29)
        self.assertIsNone(r18._outcome(source, 5, "long"))
        source = bars(30)
        source[18] = Bar(source[18].timestamp, source[18].open, source[18].high,
                         source[18].low, source[18].close, source[18].volume, False)
        self.assertIsNone(r18._outcome(source, 5, "long"))

    def test_30_day_block_bootstrap_is_deterministic_and_one_sided(self):
        matched = [{"bos_ts": i * r18.BLOCK_MS, "delta": 1 if i % 2 == 0 else 0}
                   for i in range(8)]
        first = r18._block_stats(matched)
        second = r18._block_stats(matched)
        self.assertEqual(first, second)
        self.assertEqual(first["blocks"], 8)
        self.assertEqual(first["delta"], 0.5)
        self.assertGreaterEqual(first["p_one_sided"], 0)

    def test_match_is_prehorizon_and_control_windows_do_not_overlap(self):
        source = bars(400)
        states = ["long"] * len(source)
        events = [r18.Event("AAA", i, source[i].timestamp, "long",
                            r18._feature(source, i), "long") for i in (300, 310)]
        # All bars are bullish; two close treatment events must not receive
        # overlapping 24-bar placebo outcomes.
        zone = object()
        pairs, rows, counts = r18._match_segment("AAA", source, events,
                                                 {300: zone, 310: zone}, states)
        self.assertEqual(counts["matched"], 1)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["bos_index"], 300)
        self.assertGreaterEqual(300 - pairs[0]["control_index"], 25)
        self.assertLessEqual(300 - pairs[0]["control_index"], 180)
        self.assertEqual(sum(row["pair_status"] == "unmatched" for row in rows), 1)

    def test_shared_timestamp_guard_blocks_overlap_across_segments(self):
        source = bars(400)
        states = ["long"] * len(source)
        occupied = set()
        first = r18.Event("AAA", 300, source[300].timestamp, "long",
                          r18._feature(source, 300), "long")
        first_pairs, _, _ = r18._match_segment(
            "AAA", source, [first], {300: object()}, states, occupied)
        self.assertEqual(len(first_pairs), 1)
        second = r18.Event("AAA", 310, source[310].timestamp, "long",
                           r18._feature(source, 310), "long")
        second_pairs, _, second_counts = r18._match_segment(
            "AAA", source, [second], {310: object()}, states, occupied)
        self.assertEqual(second_pairs, [])
        self.assertEqual(second_counts["unmatched_no_control"], 1)

    def test_control_with_bos_in_prior_48_bars_is_excluded(self):
        source = bars(400)
        states = ["long"] * len(source)
        event = r18.Event("AAA", 300, source[300].timestamp, "long",
                          r18._feature(source, 300), "long")
        _, _, counts = r18._match_segment("AAA", source, [event],
                                          {250: object(), 300: object()}, states)
        self.assertEqual(counts["matched"], 0)
        self.assertEqual(counts["unmatched_no_control"], 1)

    def test_control_direction_and_trend_state_must_match(self):
        source = bars(400)
        states = ["short"] * len(source)
        states[300] = "long"
        event = r18.Event("AAA", 300, source[300].timestamp, "long",
                          r18._feature(source, 300), "long")
        _, rows, counts = r18._match_segment("AAA", source, [event], {300: object()}, states)
        self.assertEqual(counts["matched"], 0)
        self.assertEqual(rows[0]["exclusion_reason"], "no_eligible_control")

    def test_matching_distance_tie_selects_earlier_control(self):
        source = bars(400)
        states = ["long"] * len(source)
        event = r18.Event("AAA", 300, source[300].timestamp, "long",
                          r18._feature(source, 300), "long")
        with patch.object(r18, "_distance", return_value=0.25):
            pairs, _, _ = r18._match_segment("AAA", source, [event], {300: object()}, states)
        self.assertEqual(pairs[0]["control_index"], 252)

    def test_matched_but_censored_pair_is_kept_in_audit_rows(self):
        source = bars(400)
        states = ["long"] * len(source)
        event = r18.Event("AAA", 390, source[390].timestamp, "long",
                          r18._feature(source, 390), "long")
        pairs, audit_rows, counts = r18._match_segment(
            "AAA", source, [event], {390: object()}, states)
        self.assertEqual(counts["matched"], 1)
        self.assertEqual(counts["right_censored_pairs"], 1)
        self.assertEqual(pairs, [])
        self.assertEqual(audit_rows[0]["pair_status"], "right_censored")
        self.assertIn("24_bar_window_outside_segment", audit_rows[0]["exclusion_reason"])

    def test_exact_252_bar_prehistory_is_distinguished_from_missing_history(self):
        source = bars(300)
        states = ["long"] * len(source)
        event = r18.Event("AAA", 252, source[252].timestamp, "long",
                          r18._feature(source, 252), "long")
        _, _, counts = r18._match_segment("AAA", source, [event], {252: object()}, states)
        self.assertEqual(counts["eligible_bos"], 1)
        self.assertEqual(counts["unmatched_missing_prehistory"], 0)
        self.assertEqual(counts["unmatched_no_control"], 1)

    def test_train_cutoff_allows_last_train_close_but_rejects_later_bar(self):
        last_open = r18.TRAIN_CLOSE_CUTOFF_MS - r18.BAR_MS
        last_train = Bar(last_open, 100, 101, 99, 100, 10)
        r18._assert_train_cutoff([("AAA", [last_train], 0)])
        post = Bar(last_open + 1, 100, 101, 99, 100, 10)
        with self.assertRaisesRegex(ValueError, "cutoff"):
            r18._assert_train_cutoff([("AAA", [post], 0)])

    def test_event_csv_keeps_unmatched_reason_and_censored_pair_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.csv"
            rows = [
                {"symbol": "AAA", "bos_index": 251, "bos_ts": 1,
                 "pair_status": "unmatched", "exclusion_reason": "insufficient_252_bar_prehistory",
                 "bos_feature": None, "control_feature": None},
                {"symbol": "BBB", "bos_index": 390, "bos_ts": 2,
                 "control_index": 275, "control_ts": 3,
                 "pair_status": "right_censored", "exclusion_reason": "24_bar_window_outside_segment",
                 "bos_feature": (0.01, 0.02, 1.0, 0.5), "control_feature": (0.01, 0.02, 1.0, 0.5)},
            ]
            r18._write_event_csv(path, rows)
            with path.open(newline="", encoding="utf-8") as stream:
                saved = list(csv.DictReader(stream))
            self.assertEqual(len(saved), 2)
            self.assertIn("insufficient_252_bar_prehistory", saved[0]["exclusion_reason"])
            self.assertEqual(saved[1]["pair_status"], "right_censored")
            self.assertEqual(json.loads(saved[1]["bos_feature"]), [0.01, 0.02, 1.0, 0.5])

    def test_append_writes_one_failure_attempt_row_to_an_isolated_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trials.csv"
            path.write_text(",".join(common.FIELDS) + "\n", encoding="utf-8")
            original = common.CSV_PATH
            common.CSV_PATH = path
            try:
                r18._append({"status": "failed"}, 1, "grid", "code", "prereg", "fingerprint")
                with path.open(newline="", encoding="utf-8") as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["round"], "R18-coin")
                self.assertEqual(json.loads(rows[0]["metric"])["status"], "failed")
            finally:
                common.CSV_PATH = original

    def test_short_append_is_rolled_back_without_corrupting_shared_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trials.csv"
            initial = (",".join(common.FIELDS) + "\nexisting-row\n").encode()
            path.write_bytes(initial)
            original = common.CSV_PATH
            common.CSV_PATH = path
            try:
                with patch.object(r18.os, "write", return_value=1):
                    with self.assertRaisesRegex(OSError, "short append"):
                        r18._append({"status": "failed"}, 2, "grid", "code", "prereg", "fingerprint")
                self.assertEqual(path.read_bytes(), initial)
            finally:
                common.CSV_PATH = original

    def test_raw_bos_without_252_bars_remains_in_match_rate_denominator(self):
        source = bars(280)
        event = r18.Event("AAA", 251, source[251].timestamp, "long", None, None)
        _, _, counts = r18._match_segment("AAA", source, [event], {251: object()},
                                          [None] * len(source))
        self.assertEqual(counts["eligible_bos"], 1)
        self.assertEqual(counts["unmatched_missing_prehistory"], 1)
        self.assertEqual(counts["matched"], 0)

    def test_summarize_requires_both_pair_count_and_match_rate(self):
        pairs = [{"bos_ts": i * r18.BLOCK_MS, "delta": 1,
                  "bos_hit": 1, "control_hit": 0,
                  "bos_signed_return": 0.02, "control_signed_return": 0.0}
                 for i in range(100)]
        audit = {"symbols": 32, "eligible_bos": 100, "matched": 100,
                 "complete_pairs": 100, "unmatched_missing_prehistory": 0,
                 "unmatched_no_control": 0, "right_censored_pairs": 0,
                 "incomplete_bars_excluded": 0, "gap_bars": 0, "raw_bos_events": 100}
        self.assertEqual(r18._summarize(pairs, audit, 1675)["status"], "unscorable")
        audit["eligible_bos"] = 300
        self.assertEqual(r18._summarize(pairs, audit, 1675)["status"], "unscorable")


if __name__ == "__main__":
    unittest.main()
