"""모킹으로 OpenDART 재시도·이어받기·호출 한도를 검증한다."""
import json
import tempfile
import unittest
from pathlib import Path

from opendart_fetch import DAILY_LIMIT, OpenDartFetcher


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.body).encode()


class OpenDartFetcherTests(unittest.TestCase):
    def test_fetch_writes_and_resume_skips_completed_key(self):
        calls = []

        def opener(url, timeout):
            calls.append(url)
            return Response({"status": "000", "list": [{"rcept_no": "x"}]})

        with tempfile.TemporaryDirectory() as td:
            fetcher = OpenDartFetcher("test-only", Path(td), opener=opener, sleeper=lambda _: None)
            self.assertEqual(fetcher.fetch_one("elestock", "00126380"), "ok")
            self.assertEqual(fetcher.fetch_one("elestock", "00126380"), "already_done")
            self.assertEqual(len(calls), 1)
            self.assertIn('"rcept_no": "x"', (Path(td) / "elestock.jsonl").read_text())

    def test_retries_then_succeeds_without_logging_api_key(self):
        attempts = []

        def opener(url, timeout):
            attempts.append(url)
            if len(attempts) == 1:
                raise OSError("temporary")
            return Response({"status": "000", "list": []})

        with tempfile.TemporaryDirectory() as td:
            f = OpenDartFetcher("secret-test-value", Path(td), opener=opener, sleeper=lambda _: None)
            self.assertEqual(f.fetch_one("majorstock", "00126380"), "ok")
            self.assertEqual(len(attempts), 2)
            self.assertNotIn("secret-test-value", (Path(td) / "majorstock.jsonl").read_text())

    def test_daily_quota_and_invalid_endpoint(self):
        with tempfile.TemporaryDirectory() as td:
            f = OpenDartFetcher("test", Path(td), opener=lambda *a, **k: self.fail("should not call"))
            f.daily_count = DAILY_LIMIT
            self.assertEqual(f.fetch_one("elestock", "00126380"), "daily_limit")
            with self.assertRaises(ValueError):
                f.fetch_one("unknown", "00126380")

    def test_api_error_is_not_marked_done(self):
        with tempfile.TemporaryDirectory() as td:
            f = OpenDartFetcher("test", Path(td), opener=lambda *a, **k: Response({"status": "010"}), sleeper=lambda _: None)
            self.assertEqual(f.fetch_one("elestock", "00126380"), "api_error")
            self.assertEqual(f.fetch_one("elestock", "00126380"), "api_error")


if __name__ == "__main__":
    unittest.main()
