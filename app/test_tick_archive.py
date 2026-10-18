"""Tests for durable, hour-partitioned tick archive batches."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import tick_archive


class TickArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.archive_dir = Path(self.temp_dir.name) / "archive"
        self.archive_patch = patch.object(tick_archive, "ARCHIVE_DIR", self.archive_dir)
        self.archive_patch.start()

    def tearDown(self) -> None:
        self.archive_patch.stop()
        self.temp_dir.cleanup()

    def test_records_are_split_by_utc_hour_and_category(self) -> None:
        tick_archive.append_batches({
            "crypto_perp": [
                {"symbol": "BTC", "ts": "2026-10-18T01:59:59+00:00", "price": 1},
                {"symbol": "BTC", "ts": "2026-10-18T02:00:00+00:00", "price": 2},
            ],
            "crypto_funding": [
                {"symbol": "BTC", "ts": "2026-10-18T02:00:01+00:00", "mark_price": 2},
            ],
        })

        first_hour = self.archive_dir / "2026/10/18/01/crypto_perp.jsonl"
        second_hour = self.archive_dir / "2026/10/18/02/crypto_perp.jsonl"
        funding = self.archive_dir / "2026/10/18/02/crypto_funding.jsonl"
        self.assertEqual(json.loads(first_hour.read_text())["price"], 1)
        self.assertEqual(json.loads(second_hour.read_text())["price"], 2)
        self.assertEqual(json.loads(funding.read_text())["mark_price"], 2)

    def test_failed_multi_file_append_rolls_back_all_files(self) -> None:
        original = {"symbol": "BTC", "ts": "2026-10-18T02:00:00+00:00", "price": 1}
        tick_archive.append_batch("crypto_perp", [original])
        original_path = self.archive_dir / "2026/10/18/02/crypto_perp.jsonl"
        original_bytes = original_path.read_bytes()

        real_fsync = tick_archive.os.fsync
        fsync_calls = 0

        def fail_second_fsync(fd: int) -> None:
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 2:
                raise OSError("injected disk failure")
            real_fsync(fd)

        with patch.object(tick_archive.os, "fsync", side_effect=fail_second_fsync):
            with self.assertRaisesRegex(OSError, "injected disk failure"):
                tick_archive.append_batches({
                    "crypto_perp": [{"symbol": "BTC", "ts": "2026-10-18T02:00:01+00:00", "price": 2}],
                    "crypto_funding": [{"symbol": "BTC", "ts": "2026-10-18T02:00:01+00:00", "mark_price": 2}],
                })

        self.assertEqual(original_path.read_bytes(), original_bytes)
        self.assertFalse((self.archive_dir / "2026/10/18/02/crypto_funding.jsonl").exists())

    def test_invalid_timestamp_writes_nothing(self) -> None:
        with self.assertRaises(ValueError):
            tick_archive.append_batch("crypto_perp", [{"symbol": "BTC", "ts": "bad"}])
        self.assertEqual(list(self.archive_dir.rglob("*.jsonl")), [])

    def test_path_like_categories_are_rejected_before_writing(self) -> None:
        record = {"symbol": "BTC", "ts": "2026-10-18T02:00:00+00:00", "price": 1}
        for category in ("../escape", "../../../../tmp/escape", "bad/category", ""):
            with self.subTest(category=category), self.assertRaises(ValueError):
                tick_archive.append_batch(category, [record])
        self.assertEqual(list(Path(self.temp_dir.name).rglob("*.jsonl")), [])


if __name__ == "__main__":
    unittest.main()
