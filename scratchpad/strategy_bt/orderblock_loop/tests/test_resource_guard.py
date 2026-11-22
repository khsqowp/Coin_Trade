import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from resource_guard import heavy_task


class HeavyTaskGuardTests(unittest.TestCase):
    def test_guard_creates_and_removes_its_own_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / ".heavy.lock"
            with patch("resource_guard.os.nice", return_value=10):
                with heavy_task("test", lock):
                    self.assertTrue(lock.exists())
                    self.assertIn('"role": "test"', lock.read_text())
                self.assertFalse(lock.exists())

    def test_guard_refuses_to_replace_another_runs_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / ".heavy.lock"
            lock.write_text("owned by other run")
            with patch("resource_guard.os.nice", return_value=10):
                with self.assertRaises(FileExistsError):
                    with heavy_task("test", lock):
                        self.fail("guard entered despite an existing lock")
            self.assertEqual(lock.read_text(), "owned by other run")

    def test_guard_fails_closed_when_priority_cannot_be_lowered(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / ".heavy.lock"
            with patch("resource_guard.os.nice", side_effect=OSError("denied")):
                with self.assertRaisesRegex(RuntimeError, "cannot lower"):
                    with heavy_task("test", lock):
                        self.fail("guard entered without the required priority")
            self.assertFalse(lock.exists())


if __name__ == "__main__":
    unittest.main()
