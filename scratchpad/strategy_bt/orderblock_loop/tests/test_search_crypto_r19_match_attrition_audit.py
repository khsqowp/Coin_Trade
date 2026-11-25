from __future__ import annotations

import unittest
from unittest.mock import patch

from crypto import Bar
import search_crypto_r18_ob_matched_candle as r18
import search_crypto_r19_match_attrition_audit as r19


def bars(count=400):
    result = []
    price = 100.0
    for i in range(count):
        close = price + (0.08 if i % 2 else 0.04)
        result.append(Bar(i * r18.BAR_MS, price, close + 0.5, price - 0.5,
                          close, 1000.0))
        price = close
    return result


class R19AttritionTests(unittest.TestCase):
    def fixture(self):
        source = bars()
        i = 330
        event = r18.Event("AAA", i, source[i].timestamp, "long",
                          r18._feature(source, i), "long")
        return source, event, {i: object()}, ["long"] * len(source)

    def test_funnel_reports_candidate_pairs_and_events_at_each_stage(self):
        source, event, zones, states = self.fixture()
        result = r19._funnel(source, [event], zones, states)
        names = list(result["candidate_pairs_by_stage"])
        self.assertEqual(names, ["time_and_history", "same_candle_direction",
                                 "same_ema_state", "no_bos_last_48",
                                 "feature_available", "calipers", "greedy_nonoverlap"])
        self.assertEqual(result["raw_bos_events"], 1)
        self.assertGreater(result["candidate_pairs_by_stage"][names[0]], 0)
        for left, right in zip(names, names[1:]):
            self.assertLessEqual(result["candidate_pairs_by_stage"][right],
                                 result["candidate_pairs_by_stage"][left])
        self.assertLessEqual(result["greedy_selected"], 1)

    def test_exact_252_boundary_is_eligible_but_251_is_not(self):
        source = bars(300)
        event_ok = r18.Event("AAA", 252, source[252].timestamp, "long",
                             r18._feature(source, 252), "long")
        event_bad = r18.Event("AAA", 251, source[251].timestamp, "long",
                              r18._feature(source, 251), "long")
        result_ok = r19._funnel(source, [event_ok], {252: object()}, ["long"] * len(source))
        result_bad = r19._funnel(source, [event_bad], {251: object()}, ["long"] * len(source))
        self.assertEqual(result_ok["events_with_252_prehistory"], 1)
        self.assertEqual(result_bad["events_with_252_prehistory"], 0)

    def test_same_direction_and_ema_filters_are_not_relaxed(self):
        source, event, zones, states = self.fixture()
        source = [Bar(row.timestamp, row.open, row.high, row.low,
                      row.open - 0.1, row.volume) for row in source]
        # Every candidate is a down candle and thus cannot match a long event.
        result = r19._funnel(source, [event], zones, states)
        self.assertGreater(result["candidate_pairs_by_stage"]["time_and_history"], 0)
        self.assertEqual(result["candidate_pairs_by_stage"]["same_candle_direction"], 0)
        source, event, zones, states = self.fixture()
        states = ["short"] * len(states)
        result = r19._funnel(source, [event], zones, states)
        self.assertEqual(result["candidate_pairs_by_stage"]["same_ema_state"], 0)

    def test_recent_bos_exclusion_removes_candidate_without_relaxation(self):
        source, event, _, states = self.fixture()
        bos = {event.index, 270}
        result = r19._funnel(source, [event], bos, states)
        self.assertGreater(result["candidate_pairs_by_stage"]["same_ema_state"], 0)
        self.assertLess(result["candidate_pairs_by_stage"]["no_bos_last_48"],
                        result["candidate_pairs_by_stage"]["same_ema_state"])

    def test_missing_event_feature_is_attributed_at_feature_stage_only(self):
        source, event, zones, states = self.fixture()
        event = r18.Event(event.symbol, event.index, event.timestamp, event.direction,
                          None, event.trend)
        result = r19._funnel(source, [event], zones, states)
        self.assertGreater(result["candidate_pairs_by_stage"]["no_bos_last_48"], 0)
        self.assertEqual(result["candidate_pairs_by_stage"]["feature_available"], 0)

    def test_occupied_outcomes_persist_across_segments_for_symbol(self):
        source, event, zones, states = self.fixture()
        occupied = {row.timestamp for row in source[150:330]}
        result = r19._funnel(source, [event], zones, states, occupied)
        self.assertEqual(result["greedy_selected"], 0)
        self.assertGreater(result["candidate_pairs_by_stage"]["calipers"], 0)
        self.assertEqual(result["candidate_pairs_by_stage"]["greedy_nonoverlap"], 0)

    def test_symbol_segment_driver_shares_occupied_windows(self):
        source, event, zones, states = self.fixture()
        segments = [(source, [event], zones, states), (source, [event], zones, states)]
        first, second = r19._funnel_symbol_segments(segments)
        self.assertEqual(first["greedy_selected"], 1)
        self.assertEqual(second["greedy_selected"], 0)

    def test_duplicate_event_index_is_rejected(self):
        source, event, zones, states = self.fixture()
        with self.assertRaisesRegex(ValueError, "duplicate BOS"):
            r19._funnel(source, [event, event], zones, states)

    def test_writer_detector_only_flags_external_write_descriptors(self):
        sample = "p100\nf3w\nn/path/TRAIN_TRIALS.csv\np200\nftxt\nn/path/TRAIN_TRIALS.csv\np300\nf4r\nn/path/TRAIN_TRIALS.csv\np400\nf5u\nn/path/TRAIN_TRIALS.csv\n"
        self.assertEqual(r19._writable_ledger_pids(sample, 100), {400})

    def test_caliper_is_exactly_r18_caliper(self):
        source, event, zones, states = self.fixture()
        with patch.object(r18, "_distance", return_value=None):
            result = r19._funnel(source, [event], zones, states)
        self.assertGreater(result["candidate_pairs_by_stage"]["feature_available"], 0)
        self.assertEqual(result["candidate_pairs_by_stage"]["calipers"], 0)

    def test_greedy_stage_prevents_control_reuse_and_overlapping_windows(self):
        source = bars(500)
        events = [r18.Event("AAA", i, source[i].timestamp, "long",
                            r18._feature(source, i), "long") for i in (330, 340)]
        with patch.object(r18, "_distance", return_value=0.1):
            result = r19._funnel(source, events, {330: object(), 340: object()},
                                 ["long"] * len(source))
        self.assertGreaterEqual(result["events_with_candidate_by_stage"]["calipers"], 1)
        chosen = result["selected_controls"]
        self.assertEqual(result["greedy_selected"], len(chosen))
        controls = [control for _event, control in chosen]
        self.assertEqual(len(controls), len(set(controls)))
        windows = [set(r18._observed_window_timestamps(source, index))
                   for pair in chosen for index in pair]
        self.assertTrue(all(not left & right for i, left in enumerate(windows)
                            for right in windows[i + 1:]))
        with patch.object(r18, "_distance", return_value=0.1):
            reversed_result = r19._funnel(source, list(reversed(events)),
                                          {330: object(), 340: object()}, ["long"] * len(source))
        self.assertEqual(chosen, reversed_result["selected_controls"])

    def test_future_mutation_does_not_change_prefix_funnel(self):
        source, event, zones, states = self.fixture()
        with patch.object(r18, "_outcome_with_reason",
                          side_effect=AssertionError("outcome path must not be called")):
            before = r19._funnel(source, [event], zones, states)
        mutated = list(source)
        for index in range(event.index + 1, len(mutated)):
            row = mutated[index]
            mutated[index] = Bar(row.timestamp, row.open, row.high + 100,
                                 row.low - 100, row.close * 2, row.volume * 10)
        with patch.object(r18, "_outcome_with_reason",
                          side_effect=AssertionError("outcome path must not be called")):
            after = r19._funnel(mutated, [event], zones, states)
        self.assertEqual(before, after)

    def test_cutoff_bar_close_guard(self):
        last_open = r18.TRAIN_CLOSE_CUTOFF_MS - r18.BAR_MS
        r18._assert_train_cutoff([("AAA", [Bar(last_open, 1, 2, 0.5, 1.5, 10)], 0)])
        with self.assertRaisesRegex(ValueError, "cutoff"):
            r18._assert_train_cutoff([("AAA", [Bar(last_open + 1, 1, 2, 0.5, 1.5, 10)], 0)])


if __name__ == "__main__":
    unittest.main()
