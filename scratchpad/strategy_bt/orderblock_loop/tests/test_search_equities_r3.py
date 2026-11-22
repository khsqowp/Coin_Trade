import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from equities import Bar
from search_equities_r3 import (DataQualityError, GRID, _bars, _configs, _metrics,
                               _default_split_path,
                               _frame_sha256, _signal, _simulate, run)


class SearchEquitiesR3Tests(unittest.TestCase):
    def test_r3_split_default_uses_separate_external_cache_and_environment(self):
        with patch.dict(os.environ, {"TRADING_DATA_DIR": "/tmp/trading-data"}):
            self.assertEqual(_default_split_path(),
                             Path("/tmp/trading-data/cache/orderblock/equity_splits_r3.json"))
        with patch.dict(os.environ):
            os.environ.pop("TRADING_DATA_DIR", None)
            self.assertEqual(_default_split_path(),
                             Path.home() / "CODE/trading_data/cache/orderblock/equity_splits_r3.json")

    def test_preregistered_grid_has_24_trials_per_market(self):
        self.assertEqual(len(_configs("US")), 24)
        self.assertEqual(len(_configs("KR")), 24)
        self.assertEqual(set(GRID), {"US", "KR"})
        for market in GRID:
            self.assertEqual({c["family"] for c in _configs(market)}, {"A", "B", "C"})

    def test_us_gap_is_up_gap_continuation_and_kr_is_down_gap_rebound(self):
        config = {"family": "B", "gap_pct": 2, "close_strength": 0.25, "holding_days": 5}
        up_gap = [Bar(0, 100, 101, 99, 100), Bar(1, 103, 108, 102, 107)]
        down_gap = [Bar(0, 100, 101, 99, 100), Bar(1, 97, 101, 96, 100)]
        self.assertIsNotNone(_signal(up_gap, 1, config, "US"))
        self.assertIsNone(_signal(up_gap, 1, config, "KR"))
        self.assertIsNotNone(_signal(down_gap, 1, config, "KR"))
        self.assertIsNone(_signal(down_gap, 1, config, "US"))

    def test_round_trip_costs_are_exactly_20_and_31_basis_points(self):
        bars = [Bar(i, 100, 101, 99, 100) for i in range(4)]
        trade = {"family": "B", "gap_pct": 2, "close_strength": 0.25, "holding_days": 1}
        bars[1] = Bar(1, 103, 108, 102, 107)
        bars[2] = Bar(2, 107, 110, 106, 109)
        us = _simulate(bars, "US", trade)[0]
        # KR uses a down-gap setup and pays the registered 31 bp round trip.
        bars[1] = Bar(1, 97, 101, 96, 100)
        bars[2] = Bar(2, 100, 103, 99, 102)
        kr = _simulate(bars, "KR", trade)[0]
        self.assertAlmostEqual((109 / 107 - 1 - us["net_return"]) * 10_000, 20)
        self.assertAlmostEqual((102 / 100 - 1 - kr["net_return"]) * 10_000, 31)

    def test_metrics_keep_empty_sample_unscored(self):
        metrics = _metrics([])
        self.assertEqual(metrics["trades"], 0)
        self.assertIsNone(metrics["win_rate_pct"])
        self.assertIsNone(metrics["expectancy_net_bps"])

    def test_time_exit_beyond_available_train_bars_is_right_censored(self):
        bars = [Bar(0, 100, 101, 99, 100), Bar(1, 103, 108, 102, 107),
                Bar(2, 107, 111, 106, 109), Bar(3, 109, 112, 108, 110)]
        audit = {}
        trades = _simulate(bars, "US", {"family": "B", "gap_pct": 2,
                                        "close_strength": 0.25, "holding_days": 3},
                           audit=audit)
        self.assertEqual(trades, [])
        self.assertEqual(audit["right_censored"], 1)

    def test_last_train_signal_without_next_open_is_counted_not_entered(self):
        bars = [Bar(0, 100, 101, 99, 100), Bar(1, 103, 108, 102, 107)]
        audit = {}
        trades = _simulate(bars, "US", {"family": "B", "gap_pct": 2,
                                        "close_strength": 0.25, "holding_days": 5},
                           audit=audit)
        self.assertEqual(trades, [])
        self.assertEqual(audit["unfilled_signal_censored"], 1)

    def test_last_signal_censor_count_is_written_to_trial_metrics(self):
        frame = pd.DataFrame([
            {"open_time": 0, "open": 100, "high": 101, "low": 99, "close": 100},
            {"open_time": 1, "open": 103, "high": 108, "low": 102, "close": 107},
        ])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            universe = root / "universe.csv"
            trials = root / "trials.csv"
            universe.write_text("market,symbol,daily_path\nUS,AAA,fake.parquet\n")
            with patch("search_equities_r3._load_train", return_value=frame):
                output = run(universe, trials, root / "splits.json")
            row = next(item for item in output if item["market"] == "US"
                       and item["family"] == "B" and item["parameters"] == {
                           "family": "B", "gap_pct": 2, "close_strength": 0.25,
                           "holding_days": 5,
                       })
            self.assertEqual(row["unfilled_signal_censored"], 1)

    def test_incomplete_bars_are_rejected_before_signal_or_trade(self):
        frame = pd.DataFrame([{"open_time": 0, "open": 100, "high": 101,
                               "low": 99, "close": 100, "complete": True},
                              {"open_time": 1, "open": 103, "high": 108,
                               "low": 102, "close": 107, "complete": False}])
        with self.assertRaisesRegex(DataQualityError, "incomplete.*timestamp=1"):
            _bars(frame)
        with self.assertRaisesRegex(DataQualityError, "incomplete.*timestamp=1"):
            _simulate([Bar(0, 100, 101, 99, 100),
                       Bar(1, 103, 108, 102, 107, complete=False)], "US",
                      {"family": "B", "gap_pct": 2, "close_strength": 0.25,
                       "holding_days": 5})

    def test_entry_at_or_below_stop_is_counted_as_skipped(self):
        bars = [Bar(0, 100, 101, 99, 100), Bar(1, 103, 108, 102, 107),
                Bar(2, 101, 104, 100, 103)]
        audit = {}
        trades = _simulate(bars, "US", {"family": "B", "gap_pct": 2,
                                        "close_strength": 0.25, "holding_days": 5},
                           audit=audit)
        self.assertEqual(trades, [])
        self.assertEqual(audit["entries_skipped_at_or_below_stop"], 1)

    def test_duplicate_market_symbol_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            universe = root / "universe.csv"
            universe.write_text("market,symbol,daily_path\nUS,AAA,a.parquet\nUS,AAA,b.parquet\n")
            with patch("search_equities_r3._load_train") as load_train:
                with self.assertRaisesRegex(ValueError, "duplicate.*US.*AAA"):
                    run(universe, root / "trials.csv", root / "splits.json")
            load_train.assert_not_called()

    def test_barrier_exit_before_cutoff_remains_a_completed_trade(self):
        bars = [Bar(0, 100, 101, 99, 100), Bar(1, 103, 108, 102, 107),
                Bar(2, 107, 118, 106, 117)]
        audit = {}
        trades = _simulate(bars, "US", {"family": "B", "gap_pct": 2,
                                        "close_strength": 0.25, "holding_days": 5},
                           audit=audit)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["reason"], "target")
        self.assertEqual(audit.get("right_censored", 0), 0)

    def test_bars_reject_malformed_ohlc_instead_of_repairing(self):
        frame = pd.DataFrame([{"open_time": 1, "open": 100, "high": 99,
                               "low": 98, "close": 100}])
        with self.assertRaisesRegex(DataQualityError, "inconsistent OHLC.*timestamp=1"):
            _bars(frame)

    def test_train_frame_fingerprint_includes_completion_eligibility(self):
        frame = pd.DataFrame([{"open_time": 1, "open": 100, "high": 101,
                               "low": 99, "close": 100, "complete": True}])
        incomplete = frame.copy()
        incomplete.loc[0, "complete"] = False
        self.assertNotEqual(_frame_sha256(frame), _frame_sha256(incomplete))

    def test_run_records_bad_symbol_by_name_and_keeps_valid_count_zero(self):
        bad_frame = pd.DataFrame([{"open_time": 1, "open": 100, "high": 99,
                                   "low": 98, "close": 100}])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            universe = root / "universe.csv"
            trials = root / "trials.csv"
            splits = root / "splits.json"
            universe.write_text("market,symbol,daily_path\nKR,000001,fake.parquet\n")
            with patch("search_equities_r3._load_train", return_value=bad_frame):
                output = run(universe, trials, splits)
            kr_rows = [row for row in output if row["market"] == "KR"]
            self.assertEqual(len(kr_rows), 24)
            self.assertTrue(all(row["symbols"] == 0 for row in kr_rows))
            self.assertTrue(all(row["symbols_invalid_ohlc_or_time"] == 1 for row in kr_rows))
            self.assertTrue(all("000001" in row["symbol_failures"] for row in kr_rows))


if __name__ == "__main__":
    unittest.main()
