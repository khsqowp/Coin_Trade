"""Synthetic contract tests only; fixtures are not market observations."""
from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path("/private/tmp/gen17_B.py")
SPEC = importlib.util.spec_from_file_location("gen17_B", MODULE_PATH)
g = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = g
SPEC.loader.exec_module(g)


def day_series(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def synthetic_cohort(n_days: int = 125) -> dict[str, dict[date, float]]:
    start = date(2022, 8, 1)
    days = day_series(start, n_days)
    result = {symbol: {} for symbol in ("AAA", "BBB", "CCC")}
    for j, symbol in enumerate(result):
        price = 100.0 + j * 10
        for i, day in enumerate(days):
            ret = 0.001 * (j + 1) + 0.002 * math.sin((i + 1) * (j + 1) * 0.37) + 0.0007 * math.cos(i * 0.17 + j)
            price *= 1.0 + ret
            result[symbol][day] = price
    return result


def skew_pair(n: int = 63) -> tuple[list[float], list[float]]:
    values = [0.01] * (n - 1) + [0.05]
    mean = sum(values) / n
    centered = [value - mean for value in values]
    return ([value + 0.002 for value in centered], [-value + 0.002 for value in centered])


def closes_from_returns(returns: list[float], start: date, symbol: str) -> dict[str, dict[date, float]]:
    price = 100.0
    rows = {}
    dates = day_series(start, len(returns) + 1)
    for day, ret in zip(dates, [0.0, *returns]):
        price *= 1.0 + ret
        rows[day] = price
    return {symbol: rows}


class InputSignalTests(unittest.TestCase):
    def test_utc_and_offset_parsing(self):
        self.assertEqual(g.parse_utc_date("2025-01-01T00:30:00Z"), date(2025, 1, 1))
        self.assertEqual(g.parse_utc_date("2025-01-01T00:30:00+09:00"), date(2024, 12, 31))

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(g.DataBlocked, "naive_timestamp"):
            g.parse_utc_date("2025-01-01T00:00:00")

    def test_duplicate_utc_date_rejected(self):
        with self.assertRaisesRegex(g.DataBlocked, "duplicate_date"):
            g.normalize_bars({"AAA": {"2025-01-01T00:00:00Z": 1, "2025-01-01T09:00:00+09:00": 2}})

    def test_nonincreasing_dates_rejected(self):
        with self.assertRaisesRegex(g.DataBlocked, "non_increasing"):
            g.normalize_bars({"AAA": {date(2025, 1, 2): 10, date(2025, 1, 1): 9}})

    def test_invalid_closes_rejected(self):
        for bad in (0, -1, float("nan"), float("inf"), "bad"):
            with self.subTest(bad=bad), self.assertRaisesRegex(g.DataBlocked, "invalid_close"):
                g.normalize_bars({"AAA": {date(2025, 1, 1): bad}})

    def test_exact_fisher_pearson_formula(self):
        values, _ = skew_pair()
        mean = sum(values) / len(values)
        s = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
        n = len(values)
        expected = n / ((n - 1) * (n - 2)) * sum(((v - mean) / s) ** 3 for v in values)
        self.assertAlmostEqual(g.fisher_pearson_skew(values), expected, delta=1e-14)

    def test_equal_mean_variance_different_skew(self):
        positive, negative = skew_pair()
        self.assertAlmostEqual(sum(positive) / len(positive), sum(negative) / len(negative), delta=1e-14)
        var_positive = sum((x - sum(positive) / len(positive)) ** 2 for x in positive)
        var_negative = sum((x - sum(negative) / len(negative)) ** 2 for x in negative)
        self.assertAlmostEqual(var_positive, var_negative, delta=1e-14)
        self.assertLess(g.fisher_pearson_skew(negative), g.fisher_pearson_skew(positive))

    def test_extreme_positive_return_increases_positive_skew(self):
        values, _ = skew_pair()
        more_extreme = values[:-1] + [0.50]
        self.assertGreater(g.fisher_pearson_skew(more_extreme), g.fisher_pearson_skew(values))

    def test_positive_price_scale_invariance(self):
        bars = closes_from_returns(skew_pair()[0], date(2025, 1, 1), "AAA")
        scaled = {"AAA": {day: close * 17.25 for day, close in bars["AAA"].items()}}
        day = max(bars["AAA"])
        self.assertAlmostEqual(g.score_at(bars, "AAA", day), g.score_at(scaled, "AAA", day), delta=1e-13)

    def test_64_close_boundary_and_missing_window(self):
        returns, _ = skew_pair()
        bars = closes_from_returns(returns, date(2025, 1, 1), "AAA")
        end = max(bars["AAA"])
        dates = sorted(bars["AAA"])
        bars["BBB"] = {day: 50.0 + i for i, day in enumerate(dates)}
        self.assertEqual(g.signal_ranking(bars, end, ["AAA"]).eligible_count, 1)
        del bars["AAA"][min(bars["AAA"])]
        self.assertEqual(g.signal_ranking(bars, end, ["AAA"]).eligible_count, 0)

    def test_single_missing_close_and_constant_window_ineligible(self):
        returns, _ = skew_pair()
        bars = closes_from_returns(returns, date(2025, 1, 1), "AAA")
        end = max(bars["AAA"])
        dates = sorted(bars["AAA"])
        bars["BBB"] = {day: 50.0 + i for i, day in enumerate(dates)}
        del bars["AAA"][dates[12]]
        self.assertEqual(g.signal_ranking(bars, end, ["AAA"]).eligible_count, 0)
        constant = closes_from_returns([0.01] * 63, date(2025, 1, 1), "AAA")
        self.assertEqual(g.signal_ranking(constant, max(constant["AAA"]), ["AAA"]).eligible_count, 0)

    def test_ties_are_resolved_by_symbol(self):
        values, _ = skew_pair()
        a = closes_from_returns(values, date(2025, 1, 1), "AAA")["AAA"]
        ranking = g.signal_ranking({"BBB": dict(a), "AAA": dict(a)}, max(a), ["BBB", "AAA"])
        self.assertEqual([item.symbol for item in ranking.ranked], ["AAA", "BBB"])

    def test_future_mutation_does_not_change_past_signal(self):
        bars = synthetic_cohort()
        days = sorted(set.union(*(set(x) for x in bars.values())))
        day = days[80]
        before = g.signal_ranking(bars, day, list(bars)).ranked
        changed = {symbol: dict(rows) for symbol, rows in bars.items()}
        for rows in changed.values():
            for future in [d for d in rows if d > day]:
                rows[future] *= 11.0
        self.assertEqual(before, g.signal_ranking(changed, day, list(changed)).ranked)


class CandidateTests(unittest.TestCase):
    def test_fixed_decision_schedule(self):
        self.assertEqual(g.decision_indices(64), [0, 21, 42, 63])

    def test_next_day_entry_and_21_union_interval_exit(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        start, end = days[70], days[110]
        run = g.simulate_candidate(bars, "US", "base", start, end)
        buys = [fill for fill in run.fills if fill.side == "buy"]
        sells = [fill for fill in run.fills if fill.side == "sell"]
        self.assertTrue(buys)
        self.assertTrue(all(fill.day != start for fill in buys))
        first_buy = min(fill.day for fill in buys)
        self.assertEqual(first_buy, days[71])
        exit_fill = next(fill for fill in sells if fill.reason == "scheduled_block_exit")
        self.assertEqual(run.oos_dates.index(exit_fill.day) - run.oos_dates.index(first_buy), 21)
        self.assertEqual(run.eligible_by_decision[start], 3)
        self.assertEqual(run.unused_slots_by_execution[first_buy], 0)

    def test_same_date_exit_precedes_replacement_entry(self):
        bars = synthetic_cohort(130)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        run = g.simulate_candidate(bars, "US", "base", days[70], days[115])
        due = [fill for fill in run.fills if fill.day == days[92]]
        exit_i = max(i for i, fill in enumerate(due) if fill.side == "sell")
        buy_i = min(i for i, fill in enumerate(due) if fill.side == "buy")
        self.assertLess(exit_i, buy_i)

    def test_missing_execution_close_uses_full_rank_fallback(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        signal_day, execution_day = days[70], days[71]
        ranking = g.signal_ranking(bars, signal_day, list(bars)).ranked
        missing = ranking[0].symbol
        del bars[missing][execution_day]
        run = g.simulate_candidate(bars, "US", "base", signal_day, days[100])
        entered = [f.symbol for f in run.fills if f.side == "buy" and f.day == execution_day]
        self.assertNotIn(missing, entered)
        self.assertEqual(len(entered), 2)
        self.assertGreaterEqual(run.canceled_entries, 1)

    def test_signal_ranking_is_frozen_before_execution(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        signal_day, execution_day = days[70], days[71]
        ranking = g.signal_ranking(bars, signal_day, list(bars)).ranked
        changed = {symbol: dict(rows) for symbol, rows in bars.items()}
        for rows in changed.values():
            rows[execution_day] *= 2.0
        run = g.simulate_candidate(changed, "US", "base", signal_day, days[100])
        self.assertEqual(run.rank_by_decision[signal_day], tuple(item.symbol for item in ranking))

    def test_execution_on_final_date_is_skipped(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        run = g.simulate_candidate(bars, "US", "base", days[70], days[71])
        self.assertEqual(run.fills, [])
        self.assertIn((days[70], "execution_is_final"), run.skipped_decisions)

    def test_final_date_signal_is_discarded_and_open_holdings_liquidated(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        run = g.simulate_candidate(bars, "US", "base", days[70], days[91])
        self.assertIn((days[91], "no_next_in_segment"), run.skipped_decisions)
        terminal = [f for f in run.fills if f.reason == "terminal_liquidation"]
        self.assertTrue(all(fill.day == days[91] for fill in terminal))
        self.assertFalse(run.positions)

    def test_missing_terminal_close_blocks_cell(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        start, terminal = days[70], days[75]
        seeded = g.simulate_candidate(bars, "US", "base", start, terminal)
        symbol = next(fill.symbol for fill in seeded.fills if fill.side == "buy")
        del bars[symbol][terminal]
        with self.assertRaisesRegex(g.DataBlocked, "terminal_price_missing"):
            g.simulate_candidate(bars, "US", "base", start, terminal)


class OverlapDiagnosticTests(unittest.TestCase):
    def test_average_tie_ranks_are_one_based_midranks(self):
        self.assertEqual(g._average_ranks([4.0, 1.0, 1.0, 3.0]), [4.0, 1.5, 1.5, 3.0])

    def test_minimum_cross_section_four(self):
        scores = {symbol: float(i) for i, symbol in enumerate("ABC")}
        returns = {symbol: [0.001 * (i + 1)] * 63 for i, symbol in enumerate("ABC")}
        self.assertEqual(
            g.overlap_diagnostic(scores, returns),
            {"realized_std": None, "compound_return": None, "max_return": None},
        )

    def test_zero_g1_cross_sectional_variance_returns_na(self):
        symbols = "ABCD"
        scores = {symbol: 0.5 for symbol in symbols}
        returns = {symbol: [0.001 * (i + 1)] * 63 for i, symbol in enumerate(symbols)}
        self.assertTrue(all(value is None for value in g.overlap_diagnostic(scores, returns).values()))

    def test_invalid_window_is_not_hidden_by_zero_g1_variance(self):
        symbols = "ABCD"
        scores = {symbol: 0.5 for symbol in symbols}
        returns = {symbol: [0.001] * (62 if symbol == "A" else 63) for symbol in symbols}
        with self.assertRaisesRegex(g.ImplementationError, "invalid_return_window"):
            g.overlap_diagnostic(scores, returns)

    def test_same_eligible_cross_section_is_required(self):
        scores = {symbol: float(i) for i, symbol in enumerate("ABCD")}
        returns = {symbol: [0.001] * 63 for symbol in "ABC"}
        with self.assertRaisesRegex(g.ImplementationError, "cross_section_mismatch"):
            g.overlap_diagnostic(scores, returns)

    def test_exactly_63_returns_per_eligible_name_required(self):
        scores = {symbol: float(i) for i, symbol in enumerate("ABCD")}
        returns = {symbol: [0.001] * (62 if symbol == "A" else 63) for symbol in scores}
        with self.assertRaisesRegex(g.ImplementationError, "invalid_return_window"):
            g.overlap_diagnostic(scores, returns)

    def test_zero_comparator_variance_only_marks_that_metric_na(self):
        symbols = "ABCD"
        scores = {symbol: float(i) for i, symbol in enumerate(symbols)}
        returns = {}
        for i, symbol in enumerate(symbols):
            # Identical max return; differing lower observations alter vol and compound.
            returns[symbol] = [0.03] + [-0.001 * (i + 1)] * 62
        result = g.overlap_diagnostic(scores, returns)
        self.assertIsNone(result["max_return"])
        self.assertIsNotNone(result["realized_std"])
        self.assertIsNotNone(result["compound_return"])

    def test_spearman_matches_hand_ranked_monotonic_fixture(self):
        symbols = "ABCD"
        scores = {symbol: float(i) for i, symbol in enumerate(symbols)}
        returns = {}
        for i, symbol in enumerate(symbols, start=1):
            amplitude = i * 0.001
            returns[symbol] = [amplitude if j % 2 == 0 else -amplitude for j in range(63)]
        result = g.overlap_diagnostic(scores, returns)
        self.assertAlmostEqual(result["realized_std"], 1.0, delta=1e-14)

    def test_tie_adjusted_spearman_value(self):
        left = [1.0, 1.0, 2.0, 3.0]
        right = [10.0, 20.0, 20.0, 40.0]
        left_ranks = g._average_ranks(left)
        right_ranks = g._average_ranks(right)
        xbar = sum(left_ranks) / 4
        ybar = sum(right_ranks) / 4
        expected = sum((x - xbar) * (y - ybar) for x, y in zip(left_ranks, right_ranks)) / math.sqrt(
            sum((x - xbar) ** 2 for x in left_ranks) * sum((y - ybar) ** 2 for y in right_ranks)
        )
        self.assertAlmostEqual(g._rank_correlation(left, right), expected, delta=1e-14)


class AccountingBenchmarkAndGuardsTests(unittest.TestCase):
    def test_cost_cases_and_fee_per_fill(self):
        self.assertEqual(g.cost_rates("US", "base"), (0.0008, 0.0008))
        self.assertEqual(g.cost_rates("KR", "stress"), (0.00115, 0.00295))
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        run = g.simulate_candidate(bars, "US", "stress", days[70], days[100])
        buy, sell = g.cost_rates("US", "stress")
        for fill in run.fills:
            self.assertAlmostEqual(fill.fee, fill.gross * (buy if fill.side == "buy" else sell), delta=1e-12)

    def test_fixed_slot_budget_and_cash_nonnegative(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        run = g.simulate_candidate(bars, "US", "base", days[70], days[100])
        buys = [f for f in run.fills if f.side == "buy" and f.day == days[71]]
        self.assertEqual(len(buys), 2)
        for fill in buys:
            self.assertAlmostEqual(fill.gross + fill.fee, 0.5, delta=1e-12)
            self.assertGreaterEqual(fill.cash_after, -g.NAV_TOL)

    def test_kr_slot_count_uses_frozen_k_and_leaves_unused_slots_cash(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        run = g.simulate_candidate(bars, "KR", "base", days[70], days[90])
        buys = [f for f in run.fills if f.side == "buy" and f.day == days[71]]
        self.assertEqual(len(buys), 3)
        for fill in buys:
            self.assertAlmostEqual(fill.gross + fill.fee, 1.0 / 5, delta=1e-12)
        self.assertEqual(run.unused_slots_by_execution[days[71]], 2)

    def test_daily_nav_cash_and_holding_ledger_reconcile(self):
        bars = synthetic_cohort(125)
        days = sorted(set.union(*(set(rows) for rows in bars.values())))
        run = g.simulate_candidate(bars, "US", "base", days[70], days[100])
        cash_by_day = dict(run.cash_path)
        holdings_by_day = dict(run.holdings_path)
        for day, nav in run.nav:
            cash = cash_by_day[day]
            positions = holdings_by_day[day]
            marked = sum(shares * close for _, shares, close in positions)
            self.assertAlmostEqual(nav, cash + marked, delta=g.NAV_TOL)

    def test_benchmark_delayed_start_and_final_date_entry_stays_cash(self):
        days = [date(2025, 1, 1) + timedelta(days=i) for i in range(3)]
        bars = {
            "AAA": {days[0]: 100, days[1]: 101, days[2]: 102},
            "BBB": {days[1]: 50, days[2]: 51},
            "CCC": {days[2]: 30},
        }
        run = g.simulate_benchmark(bars, "US", "base", days[0], days[-1])
        self.assertFalse([f for f in run.fills if f.side == "buy" and f.day == days[-1]])
        self.assertEqual(run.unbought_terminal, ("CCC",))
        self.assertFalse(run.positions)

    def test_metrics_use_initial_point_day_before_oos(self):
        days = [date(2025, 1, 1), date(2025, 1, 2)]
        run = g.simulate_benchmark({"AAA": {days[0]: 100, days[1]: 110}}, "US", "base", *days)
        metrics = g.summarize(run)
        elapsed = (days[-1] - (days[0] - timedelta(days=1))).days
        expected = run.nav[-1][1] ** (365.2425 / elapsed) - 1
        self.assertAlmostEqual(metrics["cagr"], expected, delta=1e-12)
        self.assertGreaterEqual(metrics["mdd"], 0)

    def test_terminal_benchmark_exit_requires_actual_close(self):
        days = [date(2025, 1, 1), date(2025, 1, 2)]
        bars = {"AAA": {days[0]: 100}, "BBB": {days[0]: 50, days[1]: 51}}
        with self.assertRaisesRegex(g.DataBlocked, "terminal_price_missing"):
            g.simulate_benchmark(bars, "US", "base", *days)

    def test_market_data_loader_is_disabled_before_any_file_io(self):
        with patch.object(Path, "open", side_effect=AssertionError("unexpected file I/O")):
            with self.assertRaisesRegex(PermissionError, "market data access disabled"):
                g.load_close_csv(Path("/not/read/.kis-cache/US_AAPL.csv"))

    def test_performance_entry_point_is_disabled(self):
        with patch.object(Path, "open", side_effect=AssertionError("unexpected file I/O")):
            with self.assertRaisesRegex(PermissionError, "performance execution disabled"):
                g.run_market_performance(Path("/not/read"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
