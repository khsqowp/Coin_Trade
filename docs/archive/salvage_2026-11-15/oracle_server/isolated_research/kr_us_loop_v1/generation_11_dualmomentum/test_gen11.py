"""Pure rule tests; no market-data reads or performance calculations."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from run_gen11 import (apply_open_interval, choose_target, momentum_score,
                       rebalance_cost, validate_ordered_dates,
                       assert_single_run_unstarted)


class DualMomentumRuleTests(unittest.TestCase):
    def test_12_1_score_uses_t_minus_21_over_t_minus_252(self):
        closes = [100.0] * 254
        closes[1] = 80.0
        closes[232] = 120.0
        # t=253 -> numerator index 232 and denominator index 1.
        self.assertAlmostEqual(momentum_score(closes, 253), 0.5)

    def test_target_is_single_top_asset_when_best_absolute_momentum_positive(self):
        self.assertEqual(choose_target({"SPY": 0.05, "QQQ": 0.12, "IWM": -0.02, "DIA": 0.03}), "QQQ")

    def test_target_is_cash_when_all_assets_have_nonpositive_momentum(self):
        self.assertIsNone(choose_target({"SPY": -0.01, "QQQ": 0.0, "IWM": -0.2, "DIA": -0.03}))

    def test_tie_break_is_deterministic_and_alphabetical(self):
        self.assertEqual(choose_target({"SPY": 0.1, "QQQ": 0.1, "IWM": -0.1, "DIA": 0.0}), "QQQ")

    def test_missing_momentum_rejects_month_instead_of_silently_shrinking_universe(self):
        with self.assertRaises(ValueError):
            choose_target({"SPY": 0.1, "QQQ": None, "IWM": 0.2, "DIA": 0.1})

    def test_rebalance_cost_uses_one_way_turnover(self):
        self.assertAlmostEqual(rebalance_cost("SPY", "QQQ", 0.001), 0.002)
        self.assertAlmostEqual(rebalance_cost("SPY", "SPY", 0.001), 0.0)
        self.assertAlmostEqual(rebalance_cost(None, "SPY", 0.001), 0.001)

    def test_entry_fee_reduces_the_same_interval_return_from_pre_rebalance_nav(self):
        next_nav, interval_return = apply_open_interval(1.0, None, "SPY", 1.10, 0.001)
        self.assertAlmostEqual(next_nav, 1.0989)
        self.assertAlmostEqual(interval_return, 0.0989)

    def test_switch_charges_sell_and_buy_before_new_asset_return(self):
        next_nav, interval_return = apply_open_interval(1.0, "SPY", "QQQ", 1.0, 0.001)
        self.assertAlmostEqual(next_nav, 0.998)
        self.assertAlmostEqual(interval_return, -0.002)

    def test_exit_to_cash_charges_sell_fee_and_cash_has_zero_gross_return(self):
        next_nav, interval_return = apply_open_interval(1.0, "SPY", None, 1.0, 0.001)
        self.assertAlmostEqual(next_nav, 0.999)
        self.assertAlmostEqual(interval_return, -0.001)

    def test_unchanged_target_charges_no_fee_but_keeps_market_return(self):
        next_nav, interval_return = apply_open_interval(2.0, "SPY", "SPY", 1.05, 0.001)
        self.assertAlmostEqual(next_nav, 2.10)
        self.assertAlmostEqual(interval_return, 0.05)

    def test_unsorted_or_duplicate_dates_are_rejected_not_repaired(self):
        validate_ordered_dates([1, 2, 3])
        for dates in ([1, 3, 2], [1, 2, 2]):
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                validate_ordered_dates(dates)

    def test_single_run_guard_allows_prepared_only_and_rejects_started_or_output(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "attempts.jsonl"
            output = root / "result.json"
            ledger.write_text('{"state":"PREPARED_AWAITING_INDEPENDENT_REVIEW"}\n', encoding="utf-8")
            assert_single_run_unstarted(ledger, (output,))
            ledger.write_text(ledger.read_text(encoding="utf-8") + '{"state":"STARTED"}\n', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                assert_single_run_unstarted(ledger, (output,))
            ledger.write_text('{"state":"PREPARED_AWAITING_INDEPENDENT_REVIEW"}\n', encoding="utf-8")
            output.write_text("{}", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                assert_single_run_unstarted(ledger, (output,))


if __name__ == "__main__":
    unittest.main()
