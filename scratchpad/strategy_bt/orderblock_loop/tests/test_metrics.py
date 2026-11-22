import unittest

from metrics import (CORE_REQUIRED_KEYS, ROBUSTNESS_REQUIRED_KEYS, GateEvidence, core_gate,
                     curve_metrics, full_gate, release_gate, trade_metrics,
                     wilson_lower, _issue_gate_evidence)


class MetricsTests(unittest.TestCase):
    def test_wilson_bound_empty_and_boundary_values(self):
        self.assertIsNone(wilson_lower(0, 0))
        self.assertAlmostEqual(wilson_lower(10, 10), 0.7224672001, places=8)
        self.assertLess(wilson_lower(0, 10), 0.01)
        with self.assertRaises(ValueError):
            wilson_lower(11, 10)

    def test_trade_metrics_use_post_cost_returns_and_keep_zero_as_nonwin(self):
        result = trade_metrics([0.02, -0.01, 0.0, 0.03, -0.02])
        self.assertEqual(result.count, 5)
        self.assertEqual(result.win_rate, 0.4)
        self.assertAlmostEqual(result.profit_factor, 5 / 3)
        self.assertAlmostEqual(result.expectancy_bps, 40.0)
        self.assertAlmostEqual(result.breakeven_win_rate, 0.375)
        self.assertLess(result.wilson_lower_95, result.breakeven_win_rate)

    def test_equity_curve_uses_fixed_capital_and_drawdown_is_peak_relative(self):
        result = curve_metrics([0.10, -0.10, 0.05], 365)
        self.assertAlmostEqual(result.cumulative_return, 0.05)
        self.assertAlmostEqual(result.max_drawdown, 10 / 110)
        self.assertIsNotNone(result.annualized_sharpe)

    def test_zero_variance_or_short_series_sharpe_is_unavailable(self):
        self.assertIsNone(curve_metrics([0.01], 252).annualized_sharpe)
        self.assertIsNone(curve_metrics([0.01, 0.01], 252).annualized_sharpe)

    def test_core_gate_does_not_pass_unknown_win_or_sharpe_tests(self):
        trades = trade_metrics([0.01, 0.02, 0.03])
        gates = core_gate(trades, [0.01, 0.02, 0.03], market="crypto")
        self.assertFalse(gates["wilson_vs_breakeven"])
        self.assertTrue(gates["profit_factor"])
        self.assertFalse(gates["sample"])

    def test_market_thresholds_cannot_be_relaxed_by_callers(self):
        metrics = trade_metrics([0.01] * 98 + [-0.001])
        self.assertFalse(core_gate(metrics, [0.001, 0.002], market="crypto")["sample"])
        with self.assertRaises(ValueError):
            core_gate(metrics, [0.001, 0.002], market="other")

    def test_bankrupt_fixed_capital_curve_cannot_recover_on_later_returns(self):
        result = curve_metrics([-0.6, -0.6, 2.0], 365)
        self.assertFalse(result.solvent)
        self.assertEqual(result.cumulative_return, -1.0)
        self.assertEqual(result.max_drawdown, 1.0)
        self.assertIsNone(result.annualized_sharpe)

    def test_invalid_curve_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            curve_metrics([float("nan")], 365)
        with self.assertRaises(ValueError):
            curve_metrics([0.01], 0)

    def test_full_gate_fails_closed_for_missing_or_failed_robustness(self):
        core = dict.fromkeys(CORE_REQUIRED_KEYS, True)
        all_robust = {key: _issue_gate_evidence(True, "synthetic test fixture", 1,
                                                {"fixture": True})
                      for key in ROBUSTNESS_REQUIRED_KEYS}
        self.assertFalse(full_gate(core, {}))
        self.assertFalse(full_gate({"sample": True}, all_robust))
        self.assertFalse(full_gate(core, dict.fromkeys(ROBUSTNESS_REQUIRED_KEYS, True)))
        forged = {key: GateEvidence(True, "synthetic test fixture", 1, {"fixture": True})
                  for key in ROBUSTNESS_REQUIRED_KEYS}
        self.assertFalse(full_gate(core, forged))
        self.assertFalse(full_gate(core, {key: True for key in ROBUSTNESS_REQUIRED_KEYS
                                          if key != "spa"}))
        failed = dict(all_robust)
        failed["cost_stress_2x"] = _issue_gate_evidence(False, "synthetic test fixture", 1,
                                                         {"fixture": False})
        self.assertFalse(full_gate(core, failed))
        self.assertTrue(full_gate(core, all_robust))

    def test_release_gate_requires_two_uncorrelated_frozen_positive_candidates(self):
        self.assertFalse(release_gate([True], {}, {0: 0.1}))
        self.assertFalse(release_gate([True, True], {(0, 1): 0.5}, {0: 0.1, 1: 0.1}))
        self.assertFalse(release_gate([True, True], {(0, 1): -2.0}, {0: 0.1, 1: 0.1}))
        self.assertFalse(release_gate([True, True], {(0, 1): 0.2}, {0: 0.1, 1: -0.01}))
        self.assertTrue(release_gate([True, True, False], {(0, 1): 0.2},
                                     {0: 0.1, 1: 0.0}))


if __name__ == "__main__":
    unittest.main()
