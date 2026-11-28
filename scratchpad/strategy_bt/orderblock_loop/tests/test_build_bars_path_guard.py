import os
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "build_bars.py"
CANONICAL_DATA_ROOT = "/Users/user/CODE/Coin_Trade/trading_data"


class BuildBarsPathGuardTests(unittest.TestCase):
    def test_missing_environment_is_rejected_before_data_libraries_import(self):
        env = os.environ.copy()
        env.pop("TRADING_DATA_DIR", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TRADING_DATA_DIR must exactly equal", result.stderr)
        self.assertNotIn("No module named 'pandas'", result.stderr)

    def test_environment_must_match_the_repository_data_root(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            "BASE = require_trading_data_dir(os.environ.get(\"TRADING_DATA_DIR\"))",
            source,
        )
        self.assertNotIn("Path.home()", source)
        env = os.environ.copy()
        env["TRADING_DATA_DIR"] = CANONICAL_DATA_ROOT
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = os.pathsep.join(
            filter(None, (str(SCRIPT.parent), env.get("PYTHONPATH", "")))
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", "import build_bars; print(build_bars.BASE)"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), CANONICAL_DATA_ROOT)


if __name__ == "__main__":
    unittest.main()
