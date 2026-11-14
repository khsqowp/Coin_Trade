import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from run_gen11_a2 import ALL_SYMBOLS, SECTORS, _load_prices_a2, align_common_calendar, run_a2


class CommonCalendarTests(unittest.TestCase):
    def make_frames(self):
        dates = pd.date_range("2025-01-01", periods=5, freq="D")
        frames = {symbol: pd.DataFrame({"close": range(1, 6)}, index=dates) for symbol in ALL_SYMBOLS}
        # SPY begins earlier and continues later than the nine sector inputs.
        frames["SPY"] = pd.DataFrame({"close": [10, 11, 12, 13, 14, 15]}, index=pd.date_range("2024-12-31", periods=6, freq="D"))
        return frames

    def test_aligns_every_instrument_to_ten_way_intersection(self):
        frames = self.make_frames()
        common, aligned = align_common_calendar(frames)
        expected = pd.date_range("2025-01-01", periods=5, freq="D")
        self.assertTrue(common.equals(expected))
        for symbol in ALL_SYMBOLS:
            self.assertTrue(aligned[symbol].index.equals(common), symbol)
        self.assertEqual(aligned["SPY"]["close"].tolist(), [11, 12, 13, 14, 15])

    def test_only_intersection_rows_are_retained_without_forward_fill(self):
        frames = self.make_frames()
        frames["XLB"] = frames["XLB"].drop(pd.Timestamp("2025-01-03"))
        common, aligned = align_common_calendar(frames)
        self.assertNotIn(pd.Timestamp("2025-01-03"), common)
        self.assertEqual(len(common), 4)
        for symbol in ALL_SYMBOLS:
            self.assertTrue(aligned[symbol].index.equals(common), symbol)
        self.assertFalse(aligned["XLB"]["close"].isna().any())

    def test_invalid_source_indexes_fail_before_alignment(self):
        frames = self.make_frames()
        frames["XLK"] = frames["XLK"].set_axis(["a", "b", "c", "d", "e"])
        with self.assertRaisesRegex(ValueError, "DatetimeIndex"):
            align_common_calendar(frames)

    def test_duplicate_or_descending_source_dates_fail_closed(self):
        for replacement, expected in (
            ([pd.Timestamp("2025-01-01")] * 5, "unique"),
            (list(reversed(pd.date_range("2025-01-01", periods=5, freq="D"))), "ascending"),
        ):
            with self.subTest(expected=expected):
                frames = self.make_frames()
                frames["XLY"] = frames["XLY"].set_axis(replacement)
                with self.assertRaisesRegex(ValueError, expected):
                    align_common_calendar(frames)

    def test_empty_intersection_fails_closed(self):
        frames = self.make_frames()
        frames["SPY"] = frames["SPY"].set_axis(pd.date_range("2030-01-01", periods=6, freq="D"))
        with self.assertRaisesRegex(ValueError, "empty common calendar"):
            align_common_calendar(frames)

    def test_requires_exact_frozen_instrument_set(self):
        frames = self.make_frames()
        del frames[SECTORS[0]]
        with self.assertRaisesRegex(ValueError, "exactly"):
            align_common_calendar(frames)

    def test_source_price_integrity_is_checked_even_outside_common_calendar(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dates = pd.date_range("2025-01-01", periods=3, freq="D")
            for symbol in ALL_SYMBOLS:
                frame = pd.DataFrame({
                    "open": [10.0, 10.0, 10.0],
                    "high": [11.0, 11.0, 11.0],
                    "low": [9.0, 9.0, 9.0],
                    "close": [10.0, 10.0, 10.0],
                    "adjclose": [10.0, 10.0, 10.0],
                }, index=dates)
                if symbol == "SPY":
                    frame = frame.drop(dates[-1])
                frame.to_parquet(root / f"{symbol}.parquet")
            # Corrupt a price row that is not on the ten-way intersection.
            xlb = pd.read_parquet(root / "XLB.parquet")
            xlb.loc[dates[-1], "high"] = float("nan")
            xlb.to_parquet(root / "XLB.parquet")
            with self.assertRaisesRegex(ValueError, "source data"):
                _load_prices_a2(root)

    def test_pending_go_is_durable_and_blocks_parquet_read(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            run_id = "TEST-A2-PENDING-GO"
            with patch("run_gen11_a2.pd.read_parquet") as read_parquet:
                with self.assertRaisesRegex(RuntimeError, "reviewer GO"):
                    run_a2(Path(temp) / "no-market-data", out, run_id)
                read_parquet.assert_not_called()
            events = [json.loads(line) for line in (out / f"attempts_{run_id}.jsonl").read_text().splitlines()]
            self.assertEqual([event["event"] for event in events], ["STARTED", "FAILED"])
            manifest = json.loads((out / f"manifest_{run_id}.json").read_text())
            self.assertEqual(manifest["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
