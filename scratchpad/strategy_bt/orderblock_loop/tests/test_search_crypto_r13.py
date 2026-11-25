import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, FundingEvent
import search_crypto_r13 as r13


def make_bars(rows):
    return [Bar(i * r13.DURATION_MS, *row, 1.0) for i, row in enumerate(rows)]


def baseline_rows(count=24):
    return [(100, 101, 99, 100) for _ in range(count)]


def hot_funding(bars, rates=(0.0003, 0.0003, 0.0003)):
    return {bars[i].timestamp + r13.DURATION_MS: FundingEvent(
        bars[i].timestamp + r13.DURATION_MS, rate, 100.0
    ) for i, rate in zip((17, 18, 19), rates)}


class SearchCryptoR13Tests(unittest.TestCase):
    def test_fixed_grid_and_close_based_support_break(self):
        rows = baseline_rows()
        rows[20] = (100, 100, 97, 98)
        bars = make_bars(rows)
        setup, reason = r13._setup_at(bars, 20, hot_funding(bars))
        self.assertEqual(reason, "setup")
        self.assertEqual(setup.entry_index, 21)
        rows[20] = (100, 102, 98, 100)  # wick under support, close above it
        bars = make_bars(rows)
        self.assertEqual(r13._setup_at(bars, 20, hot_funding(bars))[1], "no_close_break")
        self.assertEqual(len(r13.CONFIGS), 1)

    def test_exact_frozen_universe_is_required(self):
        r13._validate_symbols(["A", "B"], ["A", "B"])
        with self.assertRaisesRegex(ValueError, "exact frozen universe"):
            r13._validate_symbols(["A"], ["A", "B"])
        with self.assertRaisesRegex(ValueError, "exact frozen universe"):
            r13._validate_symbols(["A", "A"], ["A"])
        with self.assertRaisesRegex(ValueError, "exact frozen universe"):
            r13._validate_symbols(["A", "C"], ["A", "B"])

    def test_requires_twenty_previous_contiguous_bars(self):
        rows = baseline_rows(20) + [(100, 100, 97, 98), (98, 99, 97, 98)]
        bars = make_bars(rows)
        self.assertEqual(r13._setup_at(bars, 19, hot_funding(bars))[1], "insufficient_history")
        segmented, gaps = r13._continuous_segments(
            bars[:10] + [Bar(11 * r13.DURATION_MS, 100, 101, 99, 100, 1)]
        )
        self.assertEqual([len(item) for item in segmented], [10, 1])
        self.assertEqual(gaps, 1)

    def test_funding_requires_three_positive_events_and_inclusive_mean(self):
        rows = baseline_rows(22)
        rows[20] = (100, 100, 97, 98)
        bars = make_bars(rows)
        self.assertEqual(r13._setup_at(bars, 20, hot_funding(bars))[1], "setup")
        self.assertEqual(r13._setup_at(
            bars, 20, hot_funding(bars, (0.0005, 0.0004, 0.0))
        )[1], "funding_filter")
        self.assertEqual(r13._setup_at(
            bars, 20, hot_funding(bars, (0.0002, 0.0003, 0.0003))
        )[1], "funding_filter")

    def test_next_bar_open_and_same_bar_stop_precedence(self):
        rows = baseline_rows(24)
        rows[20] = (100, 100, 97, 98)
        rows[21] = (98, 102, 80, 90)
        bars = make_bars(rows)
        setup, reason = r13._setup_at(bars, 20, hot_funding(bars))
        self.assertEqual(reason, "setup")
        self.assertEqual(setup.entry_index, 21)
        self.assertEqual(setup.entry_price, bars[21].open)
        trades, audit = r13._trades_for_segment(bars, hot_funding(bars))
        self.assertEqual(audit["setup_count"], 1)
        self.assertEqual(trades[0].exit_reason, "stop")

    def test_prefix_invariance_and_future_settlements_are_ignored(self):
        rows = baseline_rows(24)
        rows[20] = (100, 100, 97, 98)
        prefix = make_bars(rows[:22])
        full = make_bars(rows + [(98, 99, 97, 98), (98, 99, 97, 98)])
        known = hot_funding(prefix)
        future_ts = full[22].timestamp + 1
        known[future_ts] = FundingEvent(future_ts, 0.5, 100)
        with patch.object(r13, "_atr", return_value=2.0):
            self.assertEqual(r13._setup_at(prefix, 20, known),
                             r13._setup_at(full, 20, known))

    def test_right_edge_cutoff_and_funding_coverage_censoring(self):
        rows = baseline_rows(21)
        rows[20] = (100, 100, 97, 98)
        bars = make_bars(rows)
        self.assertEqual(r13._setup_at(bars, 20, hot_funding(bars))[1],
                         "cutoff_entry_censored")

        rows = baseline_rows(70)
        rows[20] = (100, 100, 97, 98)
        rows[21] = (98, 99, 96, 97)
        bars = make_bars(rows)
        funding = hot_funding(bars)
        gap_ts = bars[22].timestamp + r13.DURATION_MS // 2
        funding[gap_ts] = FundingEvent(gap_ts, 0.0, None, coverage_gap=True)
        trades, audit = r13._trades_for_segment(bars, funding)
        self.assertEqual(audit["funding_coverage_censored_trades"], 1)
        self.assertEqual(len(trades), 1)
        self.assertIsNone(trades[0].net_return)

    def test_signal_at_gap_edge_is_gap_censored_not_cutoff_censored(self):
        rows = baseline_rows(21)
        rows[20] = (100, 100, 97, 98)
        first = make_bars(rows)
        after_gap = Bar(22 * r13.DURATION_MS, 100, 101, 99, 100, 1)
        combined = first + [after_gap]
        funding = hot_funding(combined)
        segments, missing = r13._continuous_segments(combined)
        scoped = r13.common._funding_by_timestamp(segments[0], funding, r13.DURATION_MS)
        _trades, audit = r13._trades_for_segment(
            segments[0], scoped, right_edge_reason="gap"
        )
        self.assertEqual(missing, 1)
        self.assertEqual(audit["gap_censored_setups"], 1)
        self.assertEqual(audit["cutoff_entry_censored"], 0)

    def test_resume_fingerprint_and_prereg_hash_are_required(self):
        fields = ("round", "parameter_grid_hash", "code_sha256", "metric")
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow({"round": "R13-coin", "parameter_grid_hash": "g",
                                 "code_sha256": "c", "metric": json.dumps({
                                     "train_input_fingerprint": "f",
                                     "prereg_sha256": "p", "status": "completed"})})
            with patch.object(r13.common, "CSV_PATH", ledger):
                self.assertTrue(r13._already_recorded("g", "c", "f", "p"))
                self.assertFalse(r13._already_recorded("g", "c", "f", "q"))
                self.assertFalse(r13._already_recorded("g", "c", "x", "p"))

    def test_bonferroni_denominator_counts_existing_rows_and_current_trial(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.csv"
            ledger.write_text("round,metric\nR1,{}\nR2,{}\n", encoding="utf-8")
            self.assertEqual(r13._ledger_denominator(ledger) + 1, 3)

    def test_m2_tracks_all_and_nonoverlapping_signals(self):
        scored = r13._m2_metrics([
            ("X", 0, 20, True), ("X", 10, 30, False), ("X", 25, 40, True)
        ])
        self.assertEqual(scored["m2_signal_count"], 3)
        self.assertEqual(scored["m2_target_hits"], 2)
        self.assertEqual(scored["m2_nonoverlap_signal_count"], 2)


if __name__ == "__main__":
    unittest.main()
