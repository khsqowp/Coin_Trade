import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd

from run_gen12_volatility import (
    DataBlockedError,
    FEE,
    build_targets,
    downside_rms,
    execute_attempt,
    metrics,
    sha256,
    simulate,
)


def synthetic_bars(adj_close: list[float], open_values: list[float] | None = None) -> pd.DataFrame:
    close = np.asarray(adj_close, dtype=float)
    opens = close.copy() if open_values is None else np.asarray(open_values, dtype=float)
    dates = pd.date_range("2020-01-01", periods=len(close), freq="B")
    return pd.DataFrame(
        {
            "open": opens,
            "high": np.maximum(opens, close) * 1.01,
            "low": np.minimum(opens, close) * 0.99,
            "close": close,
            "adjclose": close,
        },
        index=dates,
    )


def write_synthetic_calendar(path: Path, index: pd.DatetimeIndex) -> None:
    pd.DataFrame({"session_date": index.strftime("%Y-%m-%d")}).to_csv(path, index=False)


class DownsideForecastTests(unittest.TestCase):
    def test_warmup_and_formula_are_exact_at_63_completed_returns(self):
        returns = np.r_[0.0, np.full(62, 0.01), -0.02]
        result = downside_rms(returns)
        self.assertTrue(np.isnan(result[62]))
        self.assertAlmostEqual(result[63], np.sqrt((0.02**2) / 63))

    def test_positive_and_flat_intervals_contribute_zero_downside(self):
        returns = np.r_[0.0, np.full(63, 0.01)]
        result = downside_rms(returns)
        self.assertEqual(result[63], 0.0)

    def test_targets_are_cash_until_warmup_then_capped_at_one(self):
        close = np.full(65, 100.0)
        close[1:] *= np.cumprod(np.r_[np.full(62, 1.01), 0.98, 1.01])
        series = pd.Series(close, index=pd.date_range("2020-01-01", periods=len(close), freq="B"))
        targets, forecast = build_targets(series)
        self.assertTrue(np.isnan(targets.iloc[:63]).all())
        self.assertTrue(np.isfinite(targets.iloc[63:]).all())
        self.assertTrue(((targets.dropna() > 0) & (targets.dropna() <= 1)).all())
        self.assertEqual(len(forecast), len(close))

    def test_zero_downside_forecast_fails_closed(self):
        close = np.full(64, 100.0)
        series = pd.Series(close, index=pd.date_range("2020-01-01", periods=len(close), freq="B"))
        with self.assertRaisesRegex(ValueError, "zero downside"):
            build_targets(series)

    def test_price_index_and_values_are_validated(self):
        frame = synthetic_bars([100, 101, 102])
        frame.index = pd.DatetimeIndex(["2020-01-01", "2020-01-01", "2020-01-03"])
        with self.assertRaisesRegex(ValueError, "unique"):
            build_targets(frame["adjclose"])

    def test_unsorted_dates_fail_closed_before_forecast_calculation(self):
        frame = synthetic_bars([100, 101, 102, 103]).iloc[[0, 2, 1, 3]]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            build_targets(frame["adjclose"])

    def test_calendar_mismatch_is_data_block_not_strategy_rejection(self):
        from run_gen12_volatility import validate_session_calendar

        frame = synthetic_bars([100, 101, 102, 103])
        with tempfile.TemporaryDirectory() as temp:
            calendar_path = Path(temp) / "calendar.csv"
            write_synthetic_calendar(calendar_path, frame.index.delete(1))
            with self.assertRaisesRegex(DataBlockedError, "do not exactly match"):
                validate_session_calendar(frame.index, calendar_path)

    def test_calendar_rejects_multiple_timestamps_normalizing_to_same_session(self):
        from run_gen12_volatility import validate_session_calendar

        index = pd.DatetimeIndex(
            ["2020-01-02 09:30", "2020-01-02 16:00", "2020-01-03 16:00"]
        )
        with tempfile.TemporaryDirectory() as temp:
            calendar_path = Path(temp) / "calendar.csv"
            write_synthetic_calendar(calendar_path, pd.DatetimeIndex(["2020-01-02", "2020-01-03"]))
            with self.assertRaisesRegex(DataBlockedError, "multiple timestamps for one session date"):
                validate_session_calendar(index, calendar_path)


class CausalityTests(unittest.TestCase):
    def test_future_perturbation_does_not_change_prior_forecasts_or_targets(self):
        rng = np.random.default_rng(1206)
        close = 100 * np.cumprod(1 + rng.normal(0.0002, 0.008, 180))
        dates = pd.date_range("2020-01-01", periods=len(close), freq="B")
        original = pd.Series(close, index=dates)
        baseline, baseline_sigma = build_targets(original)
        changed = original.copy()
        changed.iloc[140:] *= np.cumprod(np.r_[1.0, np.full(39, 1.03)])
        revised, revised_sigma = build_targets(changed)
        pd.testing.assert_series_equal(baseline.iloc[:140], revised.iloc[:140])
        pd.testing.assert_series_equal(baseline_sigma.iloc[:140], revised_sigma.iloc[:140])

    def test_close_signal_first_changes_target_at_next_open(self):
        close = np.r_[100.0, np.full(63, 99.0)]
        series = pd.Series(close, index=pd.date_range("2020-01-01", periods=len(close), freq="B"))
        targets, _ = build_targets(series)
        first_valid_close = targets.index.get_loc(targets.first_valid_index())
        self.assertEqual(first_valid_close, 63)
        first_target_open = first_valid_close + 1
        self.assertEqual(first_target_open, 64)


class AccountingTests(unittest.TestCase):
    def test_drift_turnover_cost_and_terminal_liquidation_hand_calculation(self):
        frame = synthetic_bars(
            [100.0, 90.0, 99.0, 108.9],
            open_values=[100.0, 100.0, 110.0, 121.0],
        )
        targets = pd.Series([0.5, 0.5, 1.0, 0.0], index=frame.index)
        run = simulate(frame, targets, fee=0.01)
        # At open[2], prior exposure earned +10%; its drifted weight is
        # .5*1.1/(1+.5*.1), then it is rebalanced to .5 and pays turnover cost.
        drifted = 0.5 * 1.1 / (1 + 0.5 * 0.1)
        expected_rebalance_cost = 0.01 * abs(0.5 - drifted)
        self.assertAlmostEqual(run["turnover"][1], abs(0.5 - drifted))
        self.assertAlmostEqual(run["returns"].iloc[1], (1 + 0.5 * 0.1) * (1 - expected_rebalance_cost) - 1)
        # The final open liquidates the carried 50% exposure; it does not
        # apply the 100% target calculated at the preceding close.
        terminal_drift = 0.5 * 1.1 / (1 + 0.5 * 0.1)
        self.assertAlmostEqual(run["turnover"][-1], terminal_drift)
        self.assertAlmostEqual(run["returns"].iloc[-1], (1 + 0.5 * 0.1) * (1 - 0.01 * terminal_drift) - 1)
        self.assertEqual(run["terminal_target_ignored"], 1.0)
        self.assertAlmostEqual(run["benchmark_returns"].iloc[0], -0.01)
        self.assertAlmostEqual(run["returns"].iloc[0], -0.005)
        self.assertAlmostEqual(run["benchmark_returns"].iloc[-1], 1.1 * 0.99 - 1.0)

    def test_cash_warmup_and_matched_buy_and_hold_benchmark_are_finite(self):
        rng = np.random.default_rng(5)
        close = 100 * np.cumprod(1 + rng.normal(0.0002, 0.01, 90))
        frame = synthetic_bars(close.tolist())
        targets, _ = build_targets(frame["adjclose"])
        run = simulate(frame, targets, fee=FEE)
        self.assertEqual(len(run["returns"]), len(frame) - 1)
        self.assertEqual(len(run["benchmark_returns"]), len(frame) - 1)
        self.assertTrue(run["returns"].index.equals(run["benchmark_returns"].index))
        self.assertTrue(np.isfinite(run["returns"]).all())
        self.assertTrue(np.isfinite(run["benchmark_returns"]).all())
        self.assertTrue((run["exposure"] <= 1).all())
        first_close = targets.index.get_loc(targets.first_valid_index())
        entry_open = run["first_entry_open_index"]
        entry_row = entry_open - 1
        self.assertEqual(entry_open, first_close + 1)
        np.testing.assert_array_equal(run["exposure"].iloc[: entry_row + 1], 0.0)
        np.testing.assert_array_equal(run["benchmark_exposure"].iloc[: entry_row + 1], 0.0)
        self.assertEqual(run["benchmark_exposure"].iloc[entry_row + 1], 1.0)
        self.assertEqual(run["first_entry_open_date"], str(frame.index[entry_open].date()))

    def test_metrics_json_serialization_rejects_nonfinite_results(self):
        summary = metrics(pd.Series([0.01, -0.02, 0.03]))
        encoded = json.dumps(summary, allow_nan=False)
        self.assertEqual(json.loads(encoded), summary)
        with self.assertRaises(ValueError):
            metrics(pd.Series([0.0, np.inf]))


class AttemptLifecycleTests(unittest.TestCase):
    def test_blocked_data_gate_records_data_blocked_without_reading_prices(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prereg, addendum, addendum_a2 = root / "p", root / "a1", root / "a2"
            runner, tests, freeze = root / "runner.py", root / "tests.py", root / "FREEZE.json"
            attempts, manifest = root / "attempts.jsonl", root / "manifest.json"
            for path in (prereg, addendum, addendum_a2, runner, tests):
                path.write_text("synthetic-only")
            freeze.write_text(json.dumps({
                "review_status": "PENDING_ROOT_REVIEW",
                "data_gate_status": "DATA_BLOCKED",
                "data_gate_reason": "authoritative NYSE Arca calendar unavailable",
            }))
            reader = Mock(side_effect=AssertionError("blocked data must not be opened"))
            with self.assertRaisesRegex(DataBlockedError, "calendar unavailable"):
                execute_attempt(
                    prereg=prereg, addendum=addendum, addendum_a2=addendum_a2,
                    runner_path=runner, tests_path=tests, freeze_path=freeze,
                    data_path=root / "market.parquet", attempts_path=attempts,
                    manifest_path=manifest, reader=reader,
                )
            reader.assert_not_called()
            events = [json.loads(line) for line in attempts.read_text().splitlines()]
            self.assertEqual([event["status"] for event in events], ["STARTED", "DATA_BLOCKED"])
            self.assertEqual(events[-1]["stage"], "input_calendar_or_data")
            self.assertFalse(events[-1]["strategy_result"])
            self.assertFalse(events[-1]["market_values_opened"])

    def test_pending_freeze_logs_started_then_failed_without_opening_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prereg = root / "PREREG.md"
            addendum = root / "ADDENDUM_A1.md"
            addendum_a2 = root / "ADDENDUM_A2.md"
            runner = root / "runner.py"
            tests = root / "tests.py"
            freeze = root / "FREEZE.json"
            data = root / "market.parquet"
            attempts = root / "attempts.jsonl"
            manifest = root / "manifest.json"
            prereg.write_text("frozen rule")
            addendum.write_text("benchmark timing clarification")
            addendum_a2.write_text("calendar and reporting gates")
            runner.write_text("runner")
            tests.write_text("tests")
            freeze.write_text(json.dumps({"review_status": "PENDING_ROOT_REVIEW", "data_gate_status": "READY"}))
            reader = Mock(side_effect=AssertionError("market data must not be opened"))
            with self.assertRaisesRegex(RuntimeError, "root GO"):
                execute_attempt(
                    prereg=prereg,
                    addendum=addendum,
                    addendum_a2=addendum_a2,
                    runner_path=runner,
                    tests_path=tests,
                    freeze_path=freeze,
                    data_path=data,
                    attempts_path=attempts,
                    manifest_path=manifest,
                    reader=reader,
                )
            reader.assert_not_called()
            events = [json.loads(line) for line in attempts.read_text().splitlines()]
            self.assertEqual([event["status"] for event in events], ["STARTED", "FAILED"])
            self.assertEqual(json.loads(manifest.read_text())["status"], "FAILED")

    def test_authorized_synthetic_attempt_serializes_and_finishes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prereg = root / "PREREG.md"
            addendum = root / "ADDENDUM_A1.md"
            addendum_a2 = root / "ADDENDUM_A2.md"
            runner = root / "runner.py"
            tests = root / "tests.py"
            freeze = root / "FREEZE.json"
            data = root / "market.parquet"
            calendar = root / "calendar.csv"
            attempts = root / "attempts.jsonl"
            manifest = root / "manifest.json"
            prereg.write_text("frozen rule")
            addendum.write_text("benchmark timing clarification")
            addendum_a2.write_text("calendar and reporting gates")
            runner.write_text("runner")
            tests.write_text("tests")
            data.write_bytes(b"synthetic test fixture only")
            frozen = {
                "review_status": "GO",
                "data_gate_status": "READY",
                "prereg_sha256": sha256(prereg),
                "addendum_sha256": sha256(addendum),
                "addendum_a2_sha256": sha256(addendum_a2),
                "runner_sha256": sha256(runner),
                "test_sha256": sha256(tests),
                "data_sha256": sha256(data),
                "calendar_path": str(calendar),
                "calendar_source": "synthetic fixture only",
            }
            returns = np.resize(np.array([0.001, -0.002, 0.001, -0.001]), 9999)
            close = 100.0 * np.cumprod(np.r_[1.0, 1.0 + returns])
            fixture = synthetic_bars(close.tolist())
            fixture.index = pd.bdate_range("1980-01-01", periods=len(fixture))
            write_synthetic_calendar(calendar, fixture.index)
            frozen["calendar_sha256"] = sha256(calendar)
            freeze.write_text(json.dumps(frozen))

            report = execute_attempt(
                prereg=prereg,
                addendum=addendum,
                addendum_a2=addendum_a2,
                runner_path=runner,
                tests_path=tests,
                freeze_path=freeze,
                data_path=data,
                attempts_path=attempts,
                manifest_path=manifest,
                reader=Mock(return_value=fixture),
            )
            events = [json.loads(line) for line in attempts.read_text().splitlines()]
            self.assertEqual(
                [event["status"] for event in events],
                ["STARTED", "DATA_READ_STARTED", "FINISHED_EXPLORATORY"],
            )
            self.assertEqual(json.loads(manifest.read_text())["status"], "FINISHED_EXPLORATORY")
            self.assertTrue((root / "results.json").exists())
            self.assertTrue((root / "curve.csv.gz").exists())
            self.assertEqual(report["full"]["strategy"]["observations"], len(fixture) - 1)
            self.assertEqual(
                report["full"]["completed_open_to_open_holding_intervals"],
                report["activity"]["completed_open_to_open_holding_intervals"],
            )
            self.assertIn("net_minus_gross_total_return", report["full"]["cost_drag"])
            self.assertGreaterEqual(report["full"]["total_traded_notional_as_fraction_of_wealth"], 0)
            json.dumps(report, allow_nan=False)

    def test_data_hash_mismatch_fails_before_reader_opens_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prereg, addendum = root / "PREREG.md", root / "ADDENDUM_A1.md"
            addendum_a2 = root / "ADDENDUM_A2.md"
            runner, tests = root / "runner.py", root / "tests.py"
            freeze, data = root / "FREEZE.json", root / "market.parquet"
            calendar = root / "calendar.csv"
            attempts, manifest = root / "attempts.jsonl", root / "manifest.json"
            for path, content in ((prereg, "rule"), (addendum, "accounting"), (addendum_a2, "calendar"), (runner, "runner"), (tests, "tests")):
                path.write_text(content)
            data.write_bytes(b"market bytes whose hash is intentionally not the frozen digest")
            write_synthetic_calendar(calendar, pd.date_range("2020-01-01", periods=3, freq="B"))
            freeze.write_text(json.dumps({
                "review_status": "GO",
                "data_gate_status": "READY",
                "prereg_sha256": sha256(prereg),
                "addendum_sha256": sha256(addendum),
                "addendum_a2_sha256": sha256(addendum_a2),
                "runner_sha256": sha256(runner),
                "test_sha256": sha256(tests),
                "data_sha256": "0" * 64,
                "calendar_path": str(calendar),
                "calendar_source": "synthetic fixture only",
                "calendar_sha256": sha256(calendar),
            }))
            reader = Mock(side_effect=AssertionError("reader must not run on hash mismatch"))
            with self.assertRaisesRegex(RuntimeError, "data_sha256"):
                execute_attempt(
                    prereg=prereg, addendum=addendum, addendum_a2=addendum_a2,
                    runner_path=runner, tests_path=tests,
                    freeze_path=freeze, data_path=data, attempts_path=attempts,
                    manifest_path=manifest, reader=reader,
                )
            reader.assert_not_called()
            events = [json.loads(line) for line in attempts.read_text().splitlines()]
            self.assertEqual([event["status"] for event in events], ["STARTED", "FAILED"])
            self.assertFalse(events[-1]["market_values_opened"])

    def test_existing_attempt_cannot_be_overwritten_or_rerun(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempts = root / "attempts.jsonl"
            attempts.write_text('{"status":"STARTED"}\n')
            reader = Mock()
            with self.assertRaisesRegex(RuntimeError, "one-attempt"):
                execute_attempt(
                    prereg=root / "p", runner_path=root / "r", tests_path=root / "t",
                    addendum=root / "a",
                    addendum_a2=root / "a2",
                    freeze_path=root / "f", data_path=root / "d", attempts_path=attempts,
                    manifest_path=root / "m", reader=reader,
                )
            reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
