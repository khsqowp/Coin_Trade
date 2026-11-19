from __future__ import annotations

import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from scripts.research.kr_kodex200_vol_target import (
    BASE_COST,
    CUTOFF,
    load_prefix,
    simulate,
    target_weight,
)


class KODEXVolTargetTests(unittest.TestCase):
    def _flat_rows(self, n=400):
        start = dt.datetime(2010, 8, 9, tzinfo=dt.timezone.utc)
        return [
            (start + dt.timedelta(days=i), 100.0, 100.0, 100.0, 100.0, 1.0)
            for i in range(n)
        ]

    def test_flat_price_selects_full_exposure(self):
        self.assertEqual(target_weight([100.0] * 30, 20, 20, 0.10), 1.0)

    def test_simulation_charges_entry_and_terminal_cost_and_reconciles(self):
        result = simulate(self._flat_rows(), lookback=20, target_vol=0.10, cost=BASE_COST)
        self.assertAlmostEqual(result["terminal_nav"], (1 - BASE_COST) ** 2, places=10)
        self.assertEqual(result["rebalance_events"], 1)
        self.assertAlmostEqual(result["one_way_turnover_x"], 2.0, places=10)
        self.assertTrue(all(x == 0.0 for x in result["returns"][1:-1]))

    def test_cutoff_row_numeric_payload_is_not_parsed(self):
        start = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("timestamp", "Open", "High", "Low", "Close", "Volume"))
                for i in range(320):
                    stamp = start + dt.timedelta(days=i)
                    writer.writerow((stamp.isoformat(), 100, 100, 100, 100, 1))
                writer.writerow((CUTOFF.isoformat(), "not-a-number", "x", "x", "x", "x"))
            rows, _ = load_prefix(path)
        self.assertEqual(len(rows), 320)
        self.assertLess(rows[-1][0], CUTOFF)

    def test_duplicate_timestamps_fail_closed(self):
        start = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(("timestamp", "Open", "High", "Low", "Close", "Volume"))
                for i in range(320):
                    stamp = start if i == 1 else start + dt.timedelta(days=i)
                    writer.writerow((stamp.isoformat(), 100, 100, 100, 100, 1))
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                load_prefix(path)


if __name__ == "__main__":
    unittest.main()
