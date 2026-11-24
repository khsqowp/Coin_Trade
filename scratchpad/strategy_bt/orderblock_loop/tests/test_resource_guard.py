import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from resource_guard import heavy_task


class HeavyTaskGuardTests(unittest.TestCase):
    def test_guard_allows_concurrent_entries_and_ignores_lock_path(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / ".heavy.lock"
            lock.write_text("owned by other run")

            def enter(role):
                with heavy_task(role, lock):
                    return role

            with patch("resource_guard.shutil.disk_usage") as disk_usage:
                disk_usage.return_value.free = 41 * 1024**3
                with ThreadPoolExecutor(max_workers=2) as pool:
                    self.assertEqual(set(pool.map(enter, ["one", "two"])), {"one", "two"})

            self.assertEqual(lock.read_text(), "owned by other run")

    def test_guard_refuses_start_below_40_gib(self):
        with patch("resource_guard.shutil.disk_usage") as disk_usage:
            disk_usage.return_value.free = 39 * 1024**3
            with self.assertRaisesRegex(RuntimeError, "less than 40 GiB"):
                with heavy_task("test"):
                    self.fail("guard entered below disk-space threshold")


if __name__ == "__main__":
    unittest.main()
