import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("run_gen09", HERE / "run_gen09.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(mod)


class Generation09Tests(unittest.TestCase):
    def test_first_three_session_window_resets_each_month(self):
        dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02",
                                "2024-02-05", "2024-02-06", "2024-03-01"])
        got = mod.first_three_session_mask(pd.DatetimeIndex(dates))
        np.testing.assert_array_equal(got, [False, False, True, True, True, False, False])

    def test_open_to_open_applies_entry_and_exit_costs(self):
        idx = pd.date_range("2024-01-02", periods=4, freq="B")
        prices = pd.Series([100.0, 110.0, 110.0, 121.0], index=idx)
        # Exposure starts on the first open and ends on the second open.
        target = np.array([1.0, 0.0, 0.0, 0.0])
        returns, turnover, exposure = mod.simulate_open_to_open(prices, target, fee=0.001)
        self.assertAlmostEqual(float(returns.iloc[1]), 1.1 * 0.999 - 1.0, places=12)
        self.assertAlmostEqual(float(returns.iloc[2]), 0.999 - 1.0, places=12)
        self.assertAlmostEqual(float(turnover.iloc[1]), 1.0, places=12)
        self.assertAlmostEqual(float(turnover.iloc[2]), 1.0, places=12)
        self.assertAlmostEqual(float(exposure.iloc[1]), 1.0, places=12)

    def test_terminal_liquidation_charges_position_held_through_last_open(self):
        idx = pd.date_range("2024-01-02", periods=4, freq="B")
        prices = pd.Series([100.0, 100.0, 100.0, 110.0], index=idx)
        # The position remains open through the last priced open, so terminal
        # liquidation (rather than a prior scheduled exit) must pay the final fee.
        returns, turnover, _ = mod.simulate_open_to_open(prices, np.array([0.0, 1.0, 1.0, 1.0]))
        self.assertAlmostEqual(float(returns.iloc[-1]), 1.1 * 0.999 - 1.0, places=12)
        self.assertAlmostEqual(float(turnover.iloc[-1]), 1.0, places=12)

    def test_invalid_prices_fail_closed(self):
        idx = pd.date_range("2024-01-02", periods=3, freq="B")
        prices = pd.Series([100.0, np.nan, 102.0], index=idx)
        with self.assertRaisesRegex(ValueError, "invalid adjusted open"):
            mod.simulate_open_to_open(prices, np.array([1.0, 0.0, 0.0]), fee=0.001)

    def test_metrics_are_finite_and_include_trade_count(self):
        idx = pd.date_range("2024-01-02", periods=110, freq="B")
        r = pd.Series(np.full(110, 0.001), index=idx)
        turnover = pd.Series(np.zeros(110), index=idx)
        turnover.iloc[1:3] = 1.0
        exposure = pd.Series(np.zeros(110), index=idx)
        exposure.iloc[1] = 1.0
        result = mod.summarize(r, turnover, exposure)
        self.assertEqual(result["observations"], 109)
        self.assertEqual(result["exposure_sessions"], 1)
        self.assertTrue(np.isfinite(result["total_return"]))

    def test_later_metric_window_keeps_its_first_return_and_trade(self):
        idx = pd.date_range("2024-01-02", periods=240, freq="B")
        r = pd.Series(np.full(240, 0.001), index=idx)
        turnover = pd.Series(np.zeros(240), index=idx)
        exposure = pd.Series(np.zeros(240), index=idx)
        first_later = idx[120]
        turnover.loc[first_later] = 1.0
        exposure.loc[first_later] = 1.0
        result = mod.summarize(r, turnover, exposure, first_later.date().isoformat(), None)
        self.assertEqual(result["start"], first_later.date().isoformat())
        self.assertEqual(result["observations"], 120)
        self.assertAlmostEqual(result["annual_turnover"], 1.0 / (120 / 252), places=10)
        self.assertAlmostEqual(result["mean_exposure"], 1.0 / 120, places=10)


if __name__ == "__main__":
    unittest.main()
