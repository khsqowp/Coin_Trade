import unittest
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from run_gen11 import (
    SECTORS,
    _activity_counts,
    _finite_positive_frame,
    _metrics,
    _load_prices,
    breadth_from_closes,
    net_open_interval_returns,
    next_open_targets,
    run,
    write_manifest_atomic,
)


def sector_panel(last_values):
    return {symbol: [1.0] * 199 + [last_values[i]] for i, symbol in enumerate(SECTORS)}


class SectorBreadthTests(unittest.TestCase):
    def test_sma200_includes_current_close_and_strictly_compares(self):
        closes = sector_panel([2.0] * 9)
        self.assertEqual(breadth_from_closes(closes, window=200), 9)
        tied = {symbol: [1.0] * 200 for symbol in SECTORS}
        self.assertEqual(breadth_from_closes(tied, window=200), 0)

    def test_strict_majority_threshold_is_five_of_nine(self):
        up = sector_panel([2.0 if i < 5 else 0.5 for i in range(9)])
        down = sector_panel([2.0 if i < 4 else 0.5 for i in range(9)])
        self.assertEqual(breadth_from_closes(up, window=200), 5)
        self.assertEqual(breadth_from_closes(down, window=200), 4)

    def test_incomplete_or_mismatched_sector_panel_fails_closed(self):
        with self.assertRaises(ValueError):
            breadth_from_closes({SECTORS[0]: [1.0] * 200}, window=200)
        panel = {symbol: [1.0] * 200 for symbol in SECTORS}
        panel[SECTORS[-1]][-1] = float("nan")
        with self.assertRaises(ValueError):
            breadth_from_closes(panel, window=200)
        with self.assertRaises(ValueError):
            breadth_from_closes({symbol: [1.0] * (200 if i < 8 else 199) for i, symbol in enumerate(SECTORS)}, window=200)

    def test_open_execution_lags_close_signal_and_charges_boundaries(self):
        # Close signals [risk-off, risk-on, risk-on] map to [None, 0, 1, 1]
        # at opens; each signal applies only from the next session's open.
        targets = next_open_targets([0, 1, 1, 0])
        self.assertEqual(targets, [None, 0, 1, 1])
        opens = [100.0, 100.0, 110.0, 121.0]
        net = net_open_interval_returns(opens, targets, cost_bps=10)
        self.assertEqual(len(net), 2)
        self.assertAlmostEqual(net[0], 0.0)
        self.assertAlmostEqual(net[1], (1.0 - 0.001) ** 2 * 1.1 - 1.0)

    def test_terminal_exit_cost_applies_only_if_last_target_is_invested(self):
        invested = net_open_interval_returns([100, 110, 110], [1, 1, 1], cost_bps=10)
        cash = net_open_interval_returns([100, 110, 110], [0, 0, 0], cost_bps=10)
        self.assertAlmostEqual(invested[0], (1.0 - 0.001) * 1.1 - 1.0)
        self.assertAlmostEqual(invested[-1], 1.0 - 0.001 - 1.0)
        self.assertAlmostEqual(cash[0], 0.0)

    def test_activity_counts_separate_entries_exits_terminal_and_turnover(self):
        counts = _activity_counts([1, 1, 0, 1])
        self.assertEqual(counts["entries_including_initial_if_invested"], 2)
        self.assertEqual(counts["signal_driven_exits"], 1)
        self.assertEqual(counts["terminal_liquidations"], 1)
        self.assertEqual(counts["turnover_units_including_entry_and_terminal_exit"], 4.0)
        self.assertEqual(counts["measured_open_to_open_intervals"], 4)

    def test_metrics_use_sample_standard_deviation_and_handle_single_interval(self):
        import math

        returns = [0.01, -0.02, 0.03]
        mean = sum(returns) / 3
        sample_sd = math.sqrt(sum((r - mean) ** 2 for r in returns) / 2)
        expected = mean / sample_sd * math.sqrt(252)
        self.assertAlmostEqual(_metrics(returns)["sharpe"], expected)
        self.assertEqual(_metrics([0.01])["sharpe"], 0.0)

    def test_run_persists_started_then_failed_before_market_read_when_no_go(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            run_id = "TEST-PENDING-GO"
            with self.assertRaisesRegex(RuntimeError, "reviewer GO"):
                run(Path(temp) / "nonexistent-market-data", out, run_id)
            ledger = [json.loads(line) for line in (out / f"attempts_{run_id}.jsonl").read_text().splitlines()]
            self.assertEqual([event["event"] for event in ledger], ["STARTED", "FAILED"])
            manifest = json.loads((out / f"manifest_{run_id}.json").read_text())
            self.assertEqual(manifest["status"], "FAILED")
            self.assertIn("independent reviewer GO", manifest["error"])

    def test_run_id_collision_is_rejected_without_overwriting_first_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            run_id = "TEST-DUPLICATE"
            with self.assertRaisesRegex(RuntimeError, "reviewer GO"):
                run(Path(temp) / "none", out, run_id)
            original = (out / f"attempts_{run_id}.jsonl").read_text()
            with self.assertRaises(FileExistsError):
                run(Path(temp) / "none", out, run_id)
            self.assertEqual((out / f"attempts_{run_id}.jsonl").read_text(), original)
            rejected = [json.loads(line) for line in (out / "attempts_rejected.jsonl").read_text().splitlines()]
            self.assertEqual(rejected[0]["event"], "REJECTED_DUPLICATE_RUN_ID")

    def test_start_manifest_write_failure_still_appends_failed_and_preserves_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            run_id = "TEST-MANIFEST-FAIL"
            calls = {"count": 0}

            def fail_first_manifest(path, manifest):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise OSError("disk-full")
                return write_manifest_atomic(path, manifest)

            with patch("run_gen11.write_manifest_atomic", side_effect=fail_first_manifest):
                with self.assertRaisesRegex(OSError, "disk-full"):
                    run(Path(temp) / "not-read", out, run_id)
            ledger = [json.loads(line) for line in (out / f"attempts_{run_id}.jsonl").read_text().splitlines()]
            self.assertEqual([event["event"] for event in ledger], ["STARTED", "FAILED"])
            manifest = json.loads((out / f"manifest_{run_id}.json").read_text())
            self.assertEqual(manifest["status"], "FAILED")
            self.assertEqual(manifest["error"], "disk-full")

    def test_price_loader_rejects_non_datetime_index_before_values_or_metrics(self):
        class ExpectedDateTimeIndex:
            pass

        malformed_frame = SimpleNamespace(index=["2026-01-01"])
        fake_pandas = SimpleNamespace(
            DatetimeIndex=ExpectedDateTimeIndex,
            read_parquet=lambda _path: malformed_frame,
        )
        with patch.dict(sys.modules, {"pandas": fake_pandas}):
            with self.assertRaisesRegex(ValueError, "DatetimeIndex"):
                _load_prices(Path("/not-a-real-data-folder"))

    def test_finite_positive_check_uses_pandas3_compatible_to_numpy_api(self):
        class FrameWithoutApplymap:
            def __init__(self, matrix):
                self.matrix = matrix

            def to_numpy(self, dtype):
                self.asserted_dtype = dtype
                return self.matrix

        valid = FrameWithoutApplymap([[1.0, 2.0], [3.0, 4.0]])
        invalid = FrameWithoutApplymap([[1.0, float("nan")]])
        non_positive = FrameWithoutApplymap([[1.0, 0.0]])
        self.assertTrue(_finite_positive_frame(valid))
        self.assertIs(valid.asserted_dtype, float)
        self.assertFalse(_finite_positive_frame(invalid))
        self.assertFalse(_finite_positive_frame(non_positive))


if __name__ == "__main__":
    unittest.main()
