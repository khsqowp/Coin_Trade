import importlib.util
import unittest
from unittest.mock import patch

from metrics import ROBUSTNESS_REQUIRED_KEYS
from stats import (bonferroni, circular_shift_null, concentration_by_year, deflated_sharpe,
                   circular_shift_evidence, gate_decision, hansen_spa, matched_random_entry_evidence,
                   null_percentile_pass,
                   data_integrity_evidence, monte_carlo_reorder_evidence,
                   plateau_evidence, random_entry_null, reality_check,
                   stdlib_bootstrap_family_p, walk_forward_evidence, ROBUST,
                   wilson_interval)
from crypto import Bar


class StatisticalGateTests(unittest.TestCase):
    def test_statistical_and_general_robustness_gate_keys_match_prereg(self):
        self.assertEqual(set(ROBUST) | {"bonferroni", "reality_check", "spa", "deflated_sharpe"},
                         ROBUSTNESS_REQUIRED_KEYS)

    def test_missing_arch_blocks_official_reality_check_and_spa(self):
        with patch("stats._arch_comparison", return_value=None):
            with self.assertRaises(RuntimeError):
                reality_check([[0.01, -0.01, 0.02]], block_length=2, reps=10)
            with self.assertRaises(RuntimeError):
                hansen_spa([[0.01, -0.01, 0.02]], block_length=2, reps=10)

    def test_walk_forward_requires_five_folds_four_positive_and_positive_pool(self):
        self.assertTrue(walk_forward_evidence([[0.1]] * 5).passed)
        self.assertFalse(walk_forward_evidence([[0.1], [0.1], [0.1], [-0.5], [0.1]]).passed)
        self.assertFalse(walk_forward_evidence([[0.1]] * 4).passed)

    def test_monte_carlo_requires_1000_reorders_and_uses_p95_drawdown(self):
        stable = monte_carlo_reorder_evidence([0.001] * 100)
        self.assertTrue(stable.passed)
        self.assertEqual(stable.diagnostics["permutations"], 1000)
        self.assertFalse(monte_carlo_reorder_evidence([0.10, -0.15, 0.10]).passed)
        with self.assertRaises(ValueError):
            monte_carlo_reorder_evidence([0.01, -0.01], repetitions=999)

    def test_plateau_requires_complete_neighbor_shell_and_70_percent(self):
        configs = [{"lookback": x, "stop": y}
                   for x in (1, 2, 3) for y in (1, 2, 3)]
        returns = [0.10 if config == {"lookback": 2, "stop": 2}
                   else (0.06 if index % 2 else 0.01)
                   for index, config in enumerate(configs)]
        passed = plateau_evidence({"lookback": 2, "stop": 2}, configs, returns)
        self.assertTrue(passed.passed)
        incomplete = list(returns)
        incomplete[1] = None
        self.assertFalse(plateau_evidence({"lookback": 2, "stop": 2},
                                          configs, incomplete).passed)
        with self.assertRaises(ValueError):
            plateau_evidence({"lookback": 5}, configs, returns)

    def test_data_integrity_checks_real_bar_fields_and_cutoff(self):
        bars = [Bar(1, 10, 11, 9, 10, 4), Bar(2, 10, 12, 9, 11, 5)]
        good = data_integrity_evidence(
            bars, cutoff_ms=2, source_fingerprint="a" * 64,
            funding_complete=True, source_unchanged=True)
        self.assertTrue(good.passed)
        future = data_integrity_evidence(
            bars + [Bar(3, 10, 12, 9, 11, 5)], cutoff_ms=2,
            source_fingerprint="a" * 64, funding_complete=True,
            source_unchanged=True)
        self.assertFalse(future.passed)

    def test_wilson_interval_bounds_and_empty_input(self):
        self.assertIsNone(wilson_interval(0, 0))
        low, high = wilson_interval(8, 10)
        self.assertAlmostEqual(low, 0.490162, places=5)
        self.assertGreater(high, low)

    def test_bonferroni_uses_supplied_cumulative_denominator(self):
        result = bonferroni(0.001, 100)
        self.assertAlmostEqual(result["threshold"], 0.0005)
        self.assertFalse(result["pass"])

    @unittest.skipUnless(importlib.util.find_spec("arch") is not None,
                         "preregistered Reality Check/SPA requires arch")
    def test_null_returns_do_not_pass_family_comparison(self):
        returns = [[0.001, -0.001, 0.002, -0.002] * 25 for _ in range(3)]
        rc = reality_check(returns, block_length=2, reps=199)
        spa = hansen_spa(returns, block_length=2, reps=199)
        rc_cross = stdlib_bootstrap_family_p(returns, block_length=2, reps=199, method="rc")
        spa_cross = stdlib_bootstrap_family_p(returns, block_length=2, reps=199, method="spa")
        self.assertGreater(rc["p_value"], 0.05)
        self.assertGreater(spa["p_value"], 0.05)
        self.assertLess(abs(rc["p_value"] - rc_cross), 0.02)
        self.assertLess(abs(spa["p_value"] - spa_cross), 0.02)
        self.assertEqual(rc["method"], "arch.bootstrap.RealityCheck upper")
        self.assertEqual(spa["method"], "arch.bootstrap.SPA consistent")

    @unittest.skipUnless(importlib.util.find_spec("arch") is not None,
                         "preregistered Reality Check/SPA requires arch")
    def test_known_edge_is_detected_by_rc_and_spa(self):
        edge = [[0.02 + (i % 2) * 0.001 for i in range(100)],
                [0.015 + (i % 2) * 0.001 for i in range(100)]]
        rc = reality_check(edge, block_length=5, reps=199)
        spa = hansen_spa(edge, block_length=5, reps=199)
        self.assertLessEqual(rc["p_value"], 0.05)
        self.assertLessEqual(spa["p_value"], 0.05)
        rc_cross = stdlib_bootstrap_family_p(edge, block_length=5, reps=199, method="rc")
        spa_cross = stdlib_bootstrap_family_p(edge, block_length=5, reps=199, method="spa")
        self.assertLess(abs(rc["p_value"] - rc_cross), 0.02)
        self.assertLess(abs(spa["p_value"] - spa_cross), 0.02)

    def test_deflated_sharpe_uses_train_trial_count_and_rejects_flat_series(self):
        returns = [0.01 + (i % 2) * 0.001 for i in range(100)]
        self.assertGreater(deflated_sharpe(returns, 5), 0.99)
        self.assertIsNone(deflated_sharpe([0.01] * 20, 5))

    def test_concentration_aggregates_daily_pnl_by_calendar_year(self):
        result = concentration_by_year({2025: 2.0, 2026: 3.0})
        self.assertEqual(result["max_year_share"], 0.6)
        self.assertEqual(result["shares"], {2025: 0.4, 2026: 0.6})

    def test_null_helpers_are_seeded_and_enforce_95th_percentile(self):
        first = random_entry_null([1, 2, 3, 4], repetitions=5, trades_per_draw=2)
        second = random_entry_null([1, 2, 3, 4], repetitions=5, trades_per_draw=2)
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            random_entry_null([1, 2, 3, 4])
        with self.assertRaises(ValueError):
            random_entry_null([1, 2, 3, 4], trades_per_draw=4)
        shifted = circular_shift_null({"A": [0, 1, 2]}, repetitions=3)
        self.assertEqual(len(shifted), 3)
        with self.assertRaisesRegex(ValueError, "same aligned observation dates"):
            circular_shift_null({"A": [0, 1, 2], "B": [0, 1]})
        self.assertTrue(null_percentile_pass(10, [1, 2, 3, 4]))
        self.assertFalse(null_percentile_pass(3, [1, 2, 3, 4]))

    def test_matched_random_entries_preserve_symbol_counts_and_replay_callback(self):
        seen = []

        def simulate(entries):
            seen.append({symbol: tuple(values) for symbol, values in entries.items()})
            return sum(sum(values) for values in entries.values()) / 1000

        evidence = matched_random_entry_evidence(
            1.0, {"A": [1, 2, 3, 4], "B": [10, 11, 12]},
            {"A": [1, 2], "B": [10]}, simulate)
        self.assertTrue(evidence.passed)
        self.assertEqual(len(seen), 200)
        self.assertTrue(all(len(row["A"]) == 2 and len(row["B"]) == 1 for row in seen))
        self.assertEqual(evidence.diagnostics["candidate_entries"], 3)
        with self.assertRaises(ValueError):
            matched_random_entry_evidence(1.0, {"A": [1]}, {"B": [1]}, simulate)

    def test_circular_shift_evidence_runs_full_pipeline_callback_1000_times(self):
        calls = []

        def evaluate(signals):
            calls.append(signals)
            return sum(map(sum, signals.values()))

        evidence = circular_shift_evidence(100.0,
                                           {"A": [1, 0, 1, 0], "B": [0, 1, 0, 0]},
                                           evaluate)
        self.assertTrue(evidence.passed)
        self.assertEqual(len(calls), 1000)
        with self.assertRaises(ValueError):
            circular_shift_evidence(1.0, {"A": [1]}, evaluate, repetitions=10)

    def test_gate_decision_is_fail_closed_on_null_and_unknown_evidence(self):
        metric = {key: True for key in ("sample", "net_return", "profit_factor", "expectancy",
                  "wilson_vs_breakeven", "drawdown", "sharpe", "solvency", "walk_forward",
                  "monte_carlo", "random_entry", "circular_shift",
                  "plateau", "regime_2018", "regime_2022", "cost_stress_2x", "delay_1_bar",
                  "untouched_symbols", "profit_concentration", "independent_reimplementation",
                  "data_integrity")}
        metric.update(bonferroni_p=0.001, reality_check_p=0.001, spa_p=0.001,
                      deflated_sharpe_probability=0.999)
        counts = {"frozen_test_candidates": 10, "train_trials": 1000}
        result = gate_decision(metric, counts)
        self.assertEqual(result["bonferroni"], "pass")
        self.assertEqual(result["deflated_sharpe"], "fail")
        metric["reality_check_p"] = 0.5
        self.assertEqual(gate_decision(metric, counts)["reality_check"], "fail")
        self.assertEqual(gate_decision({}, {})["sample"], "undetermined")
        self.assertEqual(gate_decision(metric, {})["spa"], "undetermined")


if __name__ == "__main__":
    unittest.main()
