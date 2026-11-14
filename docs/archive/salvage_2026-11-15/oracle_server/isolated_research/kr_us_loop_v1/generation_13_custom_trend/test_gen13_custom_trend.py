from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_gen13_custom_trend as gen13  # noqa: E402


def ohlc_frame() -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=80, freq="B")
    close = 100.0 + np.arange(len(index), dtype=float) * 0.5
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "adjclose": close,
        },
        index=index,
    )


class WilderSmoothingTests(unittest.TestCase):
    def test_seed_is_mean_of_first_fourteen_consecutive_values(self) -> None:
        values = np.arange(1.0, 17.0)
        result = gen13.wilder_smooth(values, period=14)
        self.assertTrue(np.isnan(result[:13]).all())
        self.assertAlmostEqual(result[13], 7.5)
        self.assertAlmostEqual(result[14], (13.0 * 7.5 + 15.0) / 14.0)
        self.assertAlmostEqual(result[15], (13.0 * result[14] + 16.0) / 14.0)

    def test_gap_restarts_seed_and_requires_fourteen_consecutive_values(self) -> None:
        values = np.r_[np.arange(1.0, 15.0), np.nan, np.arange(20.0, 34.0)]
        result = gen13.wilder_smooth(values, period=14)
        self.assertEqual(result[13], 7.5)
        self.assertTrue(np.isnan(result[14:27]).all())
        self.assertAlmostEqual(result[28], 26.5)


class IndicatorTests(unittest.TestCase):
    def test_linear_rising_bars_produce_positive_directional_index(self) -> None:
        frame = ohlc_frame()
        adjusted = gen13.adjust_ohlc(frame)
        features = gen13.calculate_features(adjusted)
        self.assertTrue(features.loc[features.index[14]:, "di_plus"].gt(0).all())
        self.assertTrue(features.loc[features.index[14]:, "di_minus"].eq(0).all())
        self.assertTrue(np.isfinite(features.loc[features.index[14]:, "chop14"]).all())
        self.assertTrue(features.loc[features.index[14]:, "di_plus"].gt(
            features.loc[features.index[14]:, "di_minus"]
        ).all())

    def test_choppiness_matches_hand_computed_window(self) -> None:
        frame = ohlc_frame()
        adjusted = gen13.adjust_ohlc(frame)
        features = gen13.calculate_features(adjusted)
        tr = features["tr"]
        i = 20
        expected = 100.0 * np.log10(tr.iloc[i - 13:i + 1].sum() / (
            adjusted["high"].iloc[i - 13:i + 1].max()
            - adjusted["low"].iloc[i - 13:i + 1].min()
        )) / np.log10(14.0)
        self.assertAlmostEqual(features["chop14"].iloc[i], expected, places=12)

    def test_adjusted_ohlc_uses_row_adjustment_factor(self) -> None:
        raw = ohlc_frame()
        raw.loc[raw.index[10], ["open", "high", "low", "close", "adjclose"]] = [
            50.0, 52.0, 48.0, 51.0, 102.0
        ]
        adjusted = gen13.adjust_ohlc(raw)
        self.assertEqual(adjusted.loc[raw.index[10], "open"], 100.0)
        self.assertEqual(adjusted.loc[raw.index[10], "high"], 104.0)
        self.assertEqual(adjusted.loc[raw.index[10], "low"], 96.0)
        self.assertEqual(adjusted.loc[raw.index[10], "close"], 102.0)

    def test_invalid_dates_or_ohlc_fail_closed(self) -> None:
        raw = ohlc_frame()
        duplicate = pd.concat([raw, raw.iloc[[-1]]])
        with self.assertRaises(gen13.DataBlockedError):
            gen13.validate_prices(duplicate)
        bad = raw.copy()
        bad.iloc[20, bad.columns.get_loc("high")] = bad.iloc[20]["low"] - 1.0
        with self.assertRaises(gen13.DataBlockedError):
            gen13.validate_prices(bad)


class StateMachineTests(unittest.TestCase):
    def test_entry_exit_thresholds_and_hysteresis_are_exact(self) -> None:
        index = pd.date_range("2024-01-01", periods=7, freq="B")
        features = pd.DataFrame(
            {
                "di_plus": [2, 2, 2, 2, 2, 1, 2],
                "di_minus": [1, 1, 1, 1, 1, 1, 1],
                "chop14": [40, 38.19, 38.2, 50, 61.8, 30, 30],
            },
            index=index,
        )
        valid = pd.Series([False, True, True, True, True, True, True], index=index)
        state = gen13.build_state(features, valid)
        self.assertEqual(state.tolist(), [0, 1, 1, 1, 0, 0, 1])

    def test_missing_indicator_after_warmup_fails(self) -> None:
        index = pd.date_range("2024-01-01", periods=3, freq="B")
        features = pd.DataFrame({"di_plus": [2.0, np.nan, 2.0],
                                 "di_minus": [1.0, 1.0, 1.0],
                                 "chop14": [30.0, 30.0, 30.0]}, index=index)
        valid = pd.Series([True, True, True], index=index)
        with self.assertRaises(ValueError):
            gen13.build_state(features, valid)


class SimulatorTests(unittest.TestCase):
    def test_next_open_entry_exit_cost_and_curve_dates(self) -> None:
        index = pd.date_range("2024-01-01", periods=5, freq="B")
        opens = [100.0, 100.0, 110.0, 100.0, 100.0]
        raw = pd.DataFrame(
            {"open": opens, "high": [x + 1 for x in opens], "low": [x - 1 for x in opens],
             "close": opens, "adjclose": opens}, index=index
        )
        states = pd.Series([1, 1, 0, 0, 0], index=index, dtype=float)
        valid = pd.Series([True] * 5, index=index)
        run = gen13.simulate_open_to_open(raw, states, valid)
        self.assertEqual(run["returns"].index.tolist(), list(index[2:]))
        self.assertAlmostEqual(run["returns"].iloc[0], 0.999 * 1.1 - 1.0, places=10)
        self.assertAlmostEqual(run["returns"].iloc[1], (100.0 / 110.0) * 0.999 - 1.0, places=10)
        self.assertAlmostEqual(run["returns"].iloc[2], 0.0, places=12)
        self.assertEqual(run["exposure"].tolist(), [1.0, 1.0, 0.0])
        self.assertEqual(run["benchmark_returns"].index.tolist(), run["returns"].index.tolist())
        self.assertAlmostEqual(run["benchmark_returns"].iloc[0], 0.999 * 1.1 - 1.0, places=10)
        self.assertAlmostEqual(run["benchmark_returns"].iloc[-1], 0.999 - 1.0, places=10)
        self.assertEqual(run["terminal_close_state_ignored"], states.iloc[-1])

    def test_no_valid_indicator_or_terminal_entry_fails(self) -> None:
        raw = ohlc_frame().iloc[:3]
        states = pd.Series([0.0, 0.0, 0.0], index=raw.index)
        valid = pd.Series([False, False, True], index=raw.index)
        with self.assertRaises(ValueError):
            gen13.simulate_open_to_open(raw, states, valid)


class CausalityAndAuthorizationTests(unittest.TestCase):
    def test_future_perturbation_does_not_change_prior_features_or_states(self) -> None:
        raw = ohlc_frame()
        adjusted = gen13.adjust_ohlc(raw)
        base_features = gen13.calculate_features(adjusted)
        base_valid = gen13.indicator_validity(base_features)
        base_state = gen13.build_state(base_features, base_valid)
        cutoff = 50
        changed = adjusted.copy()
        changed.iloc[cutoff + 1:, :] *= np.array([1.4, 1.5, 1.3, 1.4])
        changed_features = gen13.calculate_features(changed)
        changed_valid = gen13.indicator_validity(changed_features)
        changed_state = gen13.build_state(changed_features, changed_valid)
        pd.testing.assert_frame_equal(base_features.iloc[:cutoff + 1], changed_features.iloc[:cutoff + 1])
        pd.testing.assert_series_equal(base_state.iloc[:cutoff + 1], changed_state.iloc[:cutoff + 1])

    def test_session_calendar_requires_exact_dates_without_repair(self) -> None:
        index = pd.date_range("2024-01-01", periods=5, freq="B")
        with tempfile.TemporaryDirectory() as directory:
            calendar_path = Path(directory) / "synthetic_sessions.csv"
            pd.DataFrame({"session_date": index.strftime("%Y-%m-%d")}).to_csv(calendar_path, index=False)
            gen13.validate_session_calendar(index, calendar_path)
            missing = index.delete(2)
            with self.assertRaises(gen13.DataBlockedError):
                gen13.validate_session_calendar(missing, calendar_path)
            duplicated = pd.DatetimeIndex([index[0], index[1], index[1], index[3], index[4]])
            with self.assertRaises(gen13.DataBlockedError):
                gen13.validate_session_calendar(duplicated, calendar_path)
            same_session_different_times = pd.DatetimeIndex([
                index[0] + pd.Timedelta(hours=9),
                index[0] + pd.Timedelta(hours=16),
                *index[1:].tolist(),
            ])
            with self.assertRaisesRegex(gen13.DataBlockedError, "after normalization"):
                gen13.validate_session_calendar(same_session_different_times, calendar_path)

    def test_pending_freeze_blocks_before_reader_and_attempt_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            freeze = root / "FREEZE.json"
            freeze.write_text(json.dumps({"status": "PENDING_ROOT_REVIEW_NO_MARKET_RUN_AUTHORIZED"}))
            def forbidden_reader(_path: Path) -> pd.DataFrame:
                raise AssertionError("market data reader must not be called before GO")
            with self.assertRaisesRegex(RuntimeError, "root GO"):
                gen13.execute_attempt(
                    freeze_path=freeze,
                    data_path=root / "not-read.parquet",
                    attempts_path=root / "attempts.jsonl",
                    manifest_path=root / "manifest.json",
                    reader=forbidden_reader,
                )
            self.assertFalse((root / "attempts.jsonl").exists())
            self.assertFalse((root / "manifest.json").exists())

    def test_missing_authoritative_calendar_blocks_before_reader_and_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            freeze = root / "FREEZE.json"
            freeze.write_text(json.dumps({
                "status": "DATA_BLOCKED",
                "data_gate_reason": "authoritative NYSE Arca session calendar is unavailable",
            }))
            def forbidden_reader(_path: Path) -> pd.DataFrame:
                raise AssertionError("market data reader must not be called while calendar gate is blocked")
            with self.assertRaisesRegex(gen13.DataBlockedError, "calendar is unavailable"):
                gen13.execute_attempt(
                    freeze_path=freeze,
                    data_path=root / "not-read.parquet",
                    attempts_path=root / "attempts.jsonl",
                    manifest_path=root / "manifest.json",
                    reader=forbidden_reader,
                )
            self.assertFalse((root / "attempts.jsonl").exists())
            self.assertFalse((root / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
