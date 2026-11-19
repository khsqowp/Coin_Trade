import unittest
import sqlite3
import tempfile
from pathlib import Path

import numpy as np

from chart_predictor.hourly_talib_feasibility import (
    BULLISH,
    BEARISH,
    HOUR_MS,
    MINUTE_MS,
    assert_prefix_invariant,
    calculate_signal_arrays,
    flush_hour,
    scan_database,
    _record_signal,
    validate_pattern_contract,
    START_MS,
)


class HourlyTalibFeasibilityTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(20261119)
        n = 700
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.008, n)))
        op = close * (1 + rng.normal(0, 0.003, n))
        hi = np.maximum(op, close) * (1 + rng.uniform(0, 0.006, n))
        lo = np.minimum(op, close) * (1 - rng.uniform(0, 0.006, n))
        self.arrays = tuple(np.asarray(x, dtype=np.float64) for x in (op, hi, lo, close))

    def test_frozen_paper_pattern_mapping_exists_in_pinned_talib(self):
        validate_pattern_contract()
        self.assertEqual(len(BULLISH), 30)
        self.assertEqual(len(BEARISH), 25)
        self.assertEqual(len(set(BULLISH.values()) & set(BEARISH.values())), 15)
        self.assertEqual(len(set(BULLISH.values()) | set(BEARISH.values())), 40)

    def test_claims_are_prefix_invariant(self):
        assert_prefix_invariant(calculate_signal_arrays, self.arrays, (150, 151, 250, 500, 699))

    def test_prefix_check_rejects_deliberate_future_peek(self):
        def leaky(_op, _hi, _lo, close):
            result = np.zeros(len(close), dtype=bool)
            result[:-1] = close[1:] != close[:-1]
            return {("leaky", "long"): result}

        with self.assertRaisesRegex(AssertionError, "future-sensitive"):
            assert_prefix_invariant(leaky, self.arrays, (250,))

    def test_hour_aggregation_rejects_gaps_and_accepts_exact_hour(self):
        start = 1_700_000_000_000 // HOUR_MS * HOUR_MS
        rows = [(start + i * MINUTE_MS, 10.0, 12.0 + i, 9.0 - i, 11.0 + i) for i in range(60)]
        self.assertEqual(flush_hour(start, rows), (start, 10.0, 71.0, -50.0, 70.0))
        self.assertIsNone(flush_hour(start, rows[:-1]))
        rows[30] = (rows[30][0] + MINUTE_MS, *rows[30][1:])
        self.assertIsNone(flush_hour(start, rows))

    def test_nonoverlap_deadline_includes_exact_expiry(self):
        counters = {}
        _record_signal(counters, "BTCUSDT", 0, "Hammer", "long")
        _record_signal(counters, "BTCUSDT", 9 * HOUR_MS, "Hammer", "long")
        _record_signal(counters, "BTCUSDT", 10 * HOUR_MS, "Hammer", "long")
        item = counters[("Hammer", "long")]
        self.assertEqual(item["count"], 3)
        self.assertEqual(item["nonoverlap"][10], 2)
        self.assertEqual(item["nonoverlap"][20], 1)

    def test_read_only_scan_reports_manifest_and_hour_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.sqlite"
            db = sqlite3.connect(path)
            db.executescript(
                "CREATE TABLE archive_manifest(symbol TEXT, month TEXT, sha256 TEXT, rows INTEGER, archive_bytes INTEGER, retrieved_utc TEXT);"
                "CREATE TABLE candles(symbol TEXT, open_ms INTEGER, open REAL, high REAL, low REAL, close REAL, "
                "volume REAL, close_ms INTEGER, quote_volume REAL, trade_count INTEGER, taker_buy_base REAL, "
                "taker_buy_quote REAL, PRIMARY KEY(symbol, open_ms));"
            )
            rows = []
            for index in range(150 * 60):
                minute = START_MS + index * MINUTE_MS
                rows.append(("BTCUSDT", minute, 100.0, 101.0, 99.0, 100.0, 1.0, minute + MINUTE_MS - 1, 100.0, 1, 0.5, 50.0))
            db.execute("INSERT INTO archive_manifest VALUES(?,?,?,?,?,?)", ("BTCUSDT", "2021-01", "test", len(rows), 1, "2026-11-19T00:00:00Z"))
            db.execute("INSERT INTO archive_manifest VALUES(?,?,?,?,?,?)", ("BTCUSDT", "2020-12", "outside-range", 20, 1, "2026-11-19T00:00:00Z"))
            db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            db.commit()
            db.close()

            with self.assertRaisesRegex(RuntimeError, "manifest SHA-256 mismatch"):
                scan_database(path, expected_manifest_sha256="wrong-digest")
            with self.assertRaisesRegex(RuntimeError, "cohort size mismatch"):
                scan_database(path, expected_symbol_count=2)
            result = scan_database(path)
            self.assertTrue(result["manifest_month_row_counts_match"])
            self.assertEqual(result["expected_minute_rows"], 9000)
            self.assertEqual(result["observed_minute_rows"], 9000)
            self.assertEqual(result["manifest_rows"], 2)
            self.assertEqual(result["manifest_research_month_rows"], 1)
            self.assertEqual(result["manifest_absent_scheduled_symbol_months"], 69)
            self.assertEqual(result["symbols"], ["BTCUSDT"])
            self.assertEqual(result["complete_hours"], 150)
            self.assertEqual(result["feature_eligible_anchors"], 1)
            self.assertEqual(len(result["claims"]), 116)

            db = sqlite3.connect(path)
            db.execute("UPDATE archive_manifest SET rows=8999 WHERE month='2021-01'")
            db.commit()
            db.close()
            mismatched = scan_database(path)
            self.assertFalse(mismatched["manifest_month_row_counts_match"])
            self.assertFalse(any(row["eligible"] for row in mismatched["claims"]))

    def test_duplicate_manifest_month_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.sqlite"
            db = sqlite3.connect(path)
            db.executescript(
                "CREATE TABLE archive_manifest(symbol TEXT, month TEXT, sha256 TEXT, rows INTEGER, archive_bytes INTEGER, retrieved_utc TEXT);"
                "CREATE TABLE candles(symbol TEXT, open_ms INTEGER, open REAL, high REAL, low REAL, close REAL, "
                "volume REAL, close_ms INTEGER, quote_volume REAL, trade_count INTEGER, taker_buy_base REAL, taker_buy_quote REAL, "
                "PRIMARY KEY(symbol, open_ms));"
            )
            manifest = ("BTCUSDT", "2021-01", "same", 1, 1, "2026-11-19T00:00:00Z")
            db.execute("INSERT INTO archive_manifest VALUES(?,?,?,?,?,?)", manifest)
            db.execute("INSERT INTO archive_manifest VALUES(?,?,?,?,?,?)", manifest)
            db.commit()
            db.close()
            with self.assertRaisesRegex(RuntimeError, "duplicate archive manifest"):
                scan_database(path)


if __name__ == "__main__":
    unittest.main()
