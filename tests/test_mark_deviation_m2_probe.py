import unittest
import csv
from pathlib import Path
import tempfile

import numpy as np

from scripts.research.mark_deviation_m2_probe import (
    SCORE_START,
    SYMBOLS,
    _atr,
    _circular_day_sample,
    _funding_minute_indices,
    _manifest_snapshot,
    _per_symbol_metrics,
    _rolling_z,
    _wilson,
    barrier_outcome,
    signal_events,
)


class MarkDeviationProbeTests(unittest.TestCase):
    @staticmethod
    def _data(opens, highs, lows, closes, mark_closes=None, start=0):
        n = len(opens)
        if mark_closes is None:
            mark_closes = closes
        return {
            "times": start + np.arange(n, dtype=np.int64) * 60_000,
            "open": np.asarray(opens, dtype=float),
            "high": np.asarray(highs, dtype=float),
            "low": np.asarray(lows, dtype=float),
            "close": np.asarray(closes, dtype=float),
            "mark_open": np.asarray(mark_closes, dtype=float),
            "mark_close": np.asarray(mark_closes, dtype=float),
            "funding_times": np.asarray([], dtype=np.int64),
            "funding_rates": np.asarray([], dtype=float),
            "funding_intervals": np.asarray([], dtype=np.int64),
            "funding_mark_opens": np.asarray([], dtype=float),
        }

    def test_rolling_z_excludes_current_observation(self):
        values = np.asarray([1.0, 2.0, 3.0, 100.0])
        z = _rolling_z(values, 3)
        expected_sd = np.std(values[:3], ddof=1)
        self.assertAlmostEqual(z[3], (100.0 - np.mean(values[:3])) / expected_sd)
        self.assertTrue(np.isnan(z[2]))

    def test_atr_uses_closed_bar_window_including_current(self):
        high = np.asarray([11.0, 12.0, 13.0])
        low = np.asarray([9.0, 10.0, 11.0])
        close = np.asarray([10.0, 11.0, 12.0])
        atr = _atr(high, low, close, 2)
        self.assertTrue(np.isnan(atr[1]))
        self.assertAlmostEqual(atr[2], 2.0)

    def test_signal_requires_inside_to_outside_cross_and_lockout(self):
        n = 160
        opens = np.full(n, 100.0)
        highs = np.full(n, 101.0)
        lows = np.full(n, 99.0)
        closes = np.full(n, 100.0)
        basis = 0.0005 * np.sin(np.arange(n) * 2 * np.pi / 17)
        basis[[70, 90]] = 0.02
        basis[80] = -0.02
        marks = closes / np.exp(basis)
        data = self._data(opens, highs, lows, closes, marks, start=SCORE_START)
        events, raw, suppressed, invalid = signal_events(data, "BTCUSDT")
        self.assertEqual(raw, 3)
        self.assertEqual(len(events), 2)
        self.assertEqual(suppressed, 1)
        self.assertEqual(invalid, 0)
        self.assertTrue(all(event["side"] == -1 for event in events))
        self.assertTrue(all(b["entry_ms"] - a["entry_ms"] >= 20 * 60_000
                            for a, b in zip(events, events[1:])))

    def test_stop_first_when_both_barriers_touch_same_bar(self):
        data = self._data([100] * 12, [101, 103] + [101] * 10,
                          [99, 97] + [99] * 10, [100] * 12)
        event = {"entry_index": 1, "entry_price": 100.0, "risk": 2.0,
                 "entry_ms": 60_000, "signal_close": 100.0, "symbol": "BTCUSDT"}
        result = barrier_outcome(data, event, 1, 10)
        self.assertEqual(result["exit_reason"], "STOP")
        self.assertEqual(result["m2_success"], 0)
        self.assertEqual(result["exit_price"], 98.0)

    def test_gap_through_stop_fills_at_adverse_open(self):
        data = self._data([100, 100, 95] + [95] * 9,
                          [101, 101, 96] + [96] * 9,
                          [99, 99, 94] + [94] * 9,
                          [100, 100, 95] + [95] * 9)
        event = {"entry_index": 1, "entry_price": 100.0, "risk": 2.0,
                 "entry_ms": 60_000, "signal_close": 100.0, "symbol": "BTCUSDT"}
        result = barrier_outcome(data, event, 1, 10)
        self.assertEqual(result["exit_reason"], "STOP")
        self.assertEqual(result["exit_price"], 95.0)

    def test_funding_at_entry_excluded_and_at_exit_minute_included(self):
        data = self._data([100] * 12, [101, 103] + [101] * 10,
                          [99] * 12, [100] * 12)
        data["funding_times"] = np.asarray([60_000, 120_000], dtype=np.int64)
        data["funding_rates"] = np.asarray([0.01, 0.02])
        data["funding_mark_opens"] = np.asarray([100.0, 100.0])
        event = {"entry_index": 1, "entry_price": 100.0, "risk": 2.0,
                 "entry_ms": 60_000, "signal_close": 100.0, "symbol": "BTCUSDT"}
        result = barrier_outcome(data, event, 1, 10)
        self.assertAlmostEqual(result["funding_return"], -0.02)

    def test_wilson_empty_sample_is_null(self):
        self.assertEqual(_wilson(0, 0), [None, None])

    def test_funding_millisecond_jitter_maps_to_containing_mark_minute(self):
        mark_times = np.asarray([0, 60_000, 120_000], dtype=np.int64)
        indices = _funding_minute_indices(mark_times, np.asarray([60_007, 120_999]))
        self.assertEqual(indices.tolist(), [1, 2])
        with self.assertRaisesRegex(ValueError, "more than 1 second"):
            _funding_minute_indices(mark_times, np.asarray([61_001]))

    def test_circular_bootstrap_uses_consecutive_calendar_days(self):
        rng = np.random.default_rng(7)
        sampled = _circular_day_sample(30, rng, 7)
        for offset in range(0, len(sampled), 7):
            block = sampled[offset:offset + 7]
            self.assertTrue(np.all((np.diff(block) % 30) == 1))

    def test_per_symbol_summary_contains_m2_and_net_results(self):
        row = {
            "symbol": "BTCUSDT", "horizon_min": 10,
            "candidate_m2_success": 1, "candidate_m1_correct": 1,
            "candidate_gross_return": 0.01, "candidate_funding_return": 0.0,
            "candidate_net_base": 0.009, "candidate_net_stress": 0.007,
            "momentum_m2_success": 0, "random_m2_success": 1,
        }
        audit = {symbol: {"raw_triggers": 0, "lockout_suppressed": 0,
                          "invalid_triggers": 0} for symbol in SYMBOLS}
        opportunities = {symbol: 100 for symbol in SYMBOLS}
        result = _per_symbol_metrics([row], opportunities, audit)
        btc = next(item for item in result if item["symbol"] == "BTCUSDT"
                   and item["horizon_min"] == 10)
        self.assertEqual(btc["m2_rate"], 1.0)
        self.assertEqual(btc["mean_net_stress_fee_proxy"], 0.007)

    def test_manifest_snapshot_ignores_unrelated_appended_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "MANIFEST.csv"
            target = root / "binance" / "target.parquet"
            target.parent.mkdir()
            target.touch()
            fields = ["path", "bytes", "sha256", "source_url", "src_zip_bytes"]
            rows = [{"path": "binance/target.parquet", "bytes": "0", "sha256": "abc",
                     "source_url": "https://data.binance.vision/target.zip", "src_zip_bytes": "1"}]
            with manifest.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            before = _manifest_snapshot(manifest, [target], root)
            rows.append({"path": "unrelated/new.parquet", "bytes": "10", "sha256": "def",
                         "source_url": "https://data.binance.vision/new.zip", "src_zip_bytes": "2"})
            with manifest.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            after = _manifest_snapshot(manifest, [target], root)
            self.assertEqual(before[0], after[0])
            self.assertNotEqual(before[2], after[2])
            self.assertEqual(after[1], 2)


if __name__ == "__main__":
    unittest.main()
