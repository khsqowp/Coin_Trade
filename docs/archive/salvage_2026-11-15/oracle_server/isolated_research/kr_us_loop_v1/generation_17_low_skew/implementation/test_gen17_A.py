"""Synthetic-only tests for the independently implemented Gen17 runner A."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path


MODULE_PATH = Path("/private/tmp/gen17_A.py")
SPEC = importlib.util.spec_from_file_location("gen17_A", MODULE_PATH)
gen = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gen
SPEC.loader.exec_module(gen)


def fixture_dates(oos_days: int = 50) -> list[date]:
    start = date(2022, 10, 29)
    return [start + timedelta(days=i) for i in range(64 + oos_days)]


def make_series(dates: list[date], missing: set[tuple[str, date]] | None = None):
    missing = missing or set()
    output: dict[str, dict[date, float]] = {}
    for ticker_idx, ticker in enumerate(gen.COHORTS["US"]):
        price = 100.0 + ticker_idx
        rows: dict[date, float] = {}
        for idx, day in enumerate(dates):
            if idx:
                residue = ((idx * 7 + ticker_idx * 11) % 19) - 9
                ret = residue * 0.0007 + (0.0001 if ticker_idx % 2 else -0.0002)
                price *= 1 + ret
            if (ticker, day) not in missing:
                rows[day] = price
        output[ticker] = rows
    return output


class TimestampAndInputTests(unittest.TestCase):
    def test_01_utc_offsets_are_normalized(self):
        self.assertEqual(gen.parse_utc_date("2023-01-01T01:00:00+01:00"), date(2023, 1, 1))
        self.assertEqual(gen.parse_utc_date("2023-01-01T00:00:00Z"), date(2023, 1, 1))

    def test_02_naive_and_malformed_timestamps_are_rejected(self):
        for value in ("2023-01-01T00:00:00", "not-a-timestampZ"):
            with self.subTest(value=value), self.assertRaises(gen.DataBlocked):
                gen.parse_utc_date(value)

    def test_03_bad_close_is_rejected(self):
        for value in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(gen.DataBlocked):
                gen.normalize_series({"AAPL": {date(2023, 1, 1): value}}, "US")

    def test_04_wrong_cohort_is_rejected(self):
        with self.assertRaisesRegex(gen.DataBlocked, "cohort"):
            gen.normalize_series({"AAPL": {}}, "US")

    def test_05_duplicate_utc_day_from_distinct_offsets_is_rejected(self):
        rows = {"2023-01-01T00:00:00Z": 10.0, "2023-01-01T01:00:00+01:00": 11.0}
        full = {ticker: {} for ticker in gen.COHORTS["US"]}
        full["AAPL"] = rows
        with self.assertRaisesRegex(gen.DataBlocked, "duplicate"):
            gen.normalize_series(full, "US")

    def test_06_loader_refuses_before_any_path_access(self):
        with self.assertRaisesRegex(gen.DataBlocked, "PERFORMANCE_GATE_CLOSED"):
            gen.load_market_data(Path("/path/that/must/not/be/opened"), "US")

    def test_06b_performance_entry_point_refuses_before_any_path_access(self):
        with self.assertRaisesRegex(gen.DataBlocked, "PERFORMANCE_GATE_CLOSED"):
            gen.run_performance(Path("/path/that/must/not/be/opened"), "US", "base")


class SkewSignalTests(unittest.TestCase):
    def test_07_skew_matches_bias_corrected_fisher_pearson_definition(self):
        values = [-0.2, 0.0, 0.2] * 21
        mean = sum(values) / len(values)
        sample_sd = (sum((x - mean) ** 2 for x in values) / (len(values) - 1)) ** 0.5
        expected = len(values) / ((len(values) - 1) * (len(values) - 2)) * sum(((x - mean) / sample_sd) ** 3 for x in values)
        self.assertAlmostEqual(gen.fisher_pearson_skew(values), expected, places=14)

    def test_08_equal_mean_variance_can_have_different_skew(self):
        symmetric = [-0.2, 0.0, 0.2] * 21
        asymmetric = [-0.4, 0.2, 0.2] * 7 + [0.0] * 42
        self.assertAlmostEqual(sum(symmetric), sum(asymmetric), places=14)
        self.assertAlmostEqual(sum(x * x for x in symmetric), sum(x * x for x in asymmetric), places=14)
        self.assertAlmostEqual(gen.fisher_pearson_skew(symmetric), 0.0, places=12)
        self.assertLess(gen.fisher_pearson_skew(asymmetric), 0.0)

    def test_09_positive_price_scale_does_not_change_window_score(self):
        dates = fixture_dates()
        base = make_series(dates)
        scaled = {ticker: {day: close * 37.5 for day, close in rows.items()} for ticker, rows in base.items()}
        for ticker in gen.COHORTS["US"]:
            before = gen.skew_for_ticker(base[ticker], dates, 64)
            after = gen.skew_for_ticker(scaled[ticker], dates, 64)
            self.assertAlmostEqual(before, after, places=12)

    def test_10_constant_return_window_is_ineligible(self):
        prices = {}
        value = 100.0
        dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(64)]
        for day in dates:
            prices[day] = value
        self.assertIsNone(gen.skew_for_ticker(prices, dates, 63))

    def test_11_requires_64_consecutive_union_closes_for_63_returns(self):
        dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(64)]
        prices = {day: 100.0 + i for i, day in enumerate(dates)}
        self.assertIsNotNone(gen.skew_for_ticker(prices, dates, 63))
        self.assertIsNone(gen.skew_for_ticker(prices, dates[:-1], 62))
        del prices[dates[20]]
        self.assertIsNone(gen.skew_for_ticker(prices, dates, 63))

    def test_12_ranks_lowest_skew_first_then_ticker(self):
        ranked = gen.rank_scores({"BBB": -0.1, "AAA": -0.1, "CCC": 0.2})
        self.assertEqual(ranked, [("AAA", -0.1), ("BBB", -0.1), ("CCC", 0.2)])

    def test_13_extreme_positive_return_increases_skewness(self):
        baseline = [-0.01] * 31 + [0.01] * 31 + [0.0]
        extreme = list(baseline)
        extreme[-1] = 0.5
        self.assertGreater(gen.fisher_pearson_skew(extreme), gen.fisher_pearson_skew(baseline))

    def test_14_missing_row_in_window_makes_ticker_ineligible(self):
        dates = fixture_dates()
        series = make_series(dates)
        oos_dates = [d for d in dates if d >= date(2023, 1, 1)]
        ticker = gen.COHORTS["US"][0]
        del series[ticker][oos_dates[0] - timedelta(days=1)]
        self.assertIsNone(gen.skew_for_ticker(series[ticker], dates, dates.index(oos_dates[0])))


class OverlapDiagnosticTests(unittest.TestCase):
    def test_15_perfect_rank_correlation_and_average_ties(self):
        scores = {"A": 1.0, "B": 2.0, "C": 2.0, "D": 4.0}
        returns = {"A": [-0.2, 0.0, 0.1], "B": [-0.1, 0.0, 0.1], "C": [0.0, 0.0, 0.1], "D": [0.1, 0.0, 0.1]}
        diagnostics = gen.overlap_diagnostics(scores, returns)
        self.assertAlmostEqual(diagnostics["cumulative_return"], 0.9486832980505138, places=12)

    def test_16_minimum_cross_section_and_zero_variance_return_na(self):
        scores = {"A": -1.0, "B": 0.0, "C": 1.0}
        returns = {ticker: [0.0, 0.01, -0.01] for ticker in scores}
        diag = gen.overlap_diagnostics(scores, returns)
        self.assertTrue(all(value is None for value in diag.values()))
        tied_scores = {ticker: 0.0 for ticker in "ABCD"}
        tied_returns = {ticker: [i * 0.01, 0.02, -0.01] for i, ticker in enumerate("ABCD")}
        diag = gen.overlap_diagnostics(tied_scores, tied_returns)
        self.assertTrue(all(value is None for value in diag.values()))


class ExecutionAndAccountingTests(unittest.TestCase):
    def test_17_signal_schedule_and_next_union_session_execution(self):
        dates = fixture_dates(50)
        series = make_series(dates)
        result = gen.simulate_candidate(series, "US", "base")
        oos = result.oos_dates
        self.assertEqual([r.decision_index for r in result.signals], [0, 21, 42])
        self.assertEqual([r.execution_date for r in result.signals], [oos[1], oos[22], oos[43]])

    def test_18_holding_interval_is_21_union_sessions_and_exit_before_reentry(self):
        dates = fixture_dates(50)
        result = gen.simulate_candidate(make_series(dates), "US", "base")
        oos = result.oos_dates
        event_day = oos[22]
        day_events = [fill for fill in result.ledger if fill.day == event_day]
        self.assertEqual([fill.side for fill in day_events[:4]], ["sell", "sell", "buy", "buy"])
        for sell, buy in zip(day_events[:2], day_events[2:4]):
            self.assertEqual(sell.side, "sell")
            self.assertEqual(buy.side, "buy")
        first_buys = [f for f in result.ledger if f.side == "buy" and f.day == oos[1]]
        next_sells = [f for f in result.ledger if f.side == "sell" and f.day == oos[22]]
        self.assertEqual(len(first_buys), 2)
        self.assertEqual(len(next_sells), 2)
        for fill in first_buys:
            sold = next(x for x in next_sells if x.ticker == fill.ticker)
            self.assertEqual(fill.shares, sold.shares)
            self.assertEqual((sold.day - fill.day).days, 21)

    def test_19_missing_execution_close_uses_full_rank_fallback(self):
        dates = fixture_dates(50)
        baseline = make_series(dates)
        oos = [d for d in dates if d >= date(2023, 1, 1)]
        signal = gen.build_signal(baseline, "US", oos, 0)
        missing_ticker = signal.ranking[0][0]
        series = make_series(dates, missing={(missing_ticker, oos[1])})
        result = gen.simulate_candidate(series, "US", "base")
        buys = [f for f in result.ledger if f.side == "buy" and f.day == oos[1]]
        self.assertEqual(len(buys), 2)
        self.assertNotIn(missing_ticker, [f.ticker for f in buys])
        self.assertTrue(all(f.rank is not None for f in buys))
        self.assertGreaterEqual(result.canceled_entries, 1)

    def test_20_fee_inclusive_slot_sizing_and_registered_costs(self):
        dates = fixture_dates(50)
        for market, expected_buy in (("US", 0.0008), ("KR", 0.00065)):
            series = make_series_for_market(dates, market)
            result = gen.simulate_candidate(series, market, "base")
            buys = [f for f in result.ledger if f.side == "buy" and f.day == result.oos_dates[1]]
            self.assertEqual(len(buys), gen.SLOTS[market])
            for fill in buys:
                self.assertAlmostEqual(fill.gross + fill.fee, fill.nav_batch / gen.SLOTS[market], places=11)
                self.assertAlmostEqual(fill.fee, fill.gross * expected_buy, places=12)

    def test_21_segment_final_order_and_final_decision_are_skipped(self):
        dates = fixture_dates(1)
        result = gen.simulate_candidate(make_series(dates), "US", "base")
        self.assertFalse(any(fill.side == "buy" and fill.day == result.oos_dates[-1] for fill in result.ledger))
        self.assertTrue(result.skipped_terminal_decisions >= 1)
        self.assertEqual(result.daily[-1].cash, result.daily[-1].nav)

    def test_22_terminal_holding_liquidates_at_actual_close(self):
        dates = fixture_dates(5)
        result = gen.simulate_candidate(make_series(dates), "US", "base")
        terminal_sells = [f for f in result.ledger if f.side == "sell" and f.reason == "terminal_liquidation"]
        self.assertTrue(terminal_sells)
        self.assertTrue(all(f.day == result.oos_dates[-1] for f in terminal_sells))
        self.assertFalse(result.daily[-1].holdings)

    def test_23_missing_required_terminal_price_blocks(self):
        dates = fixture_dates(5)
        oos = [d for d in dates if d >= date(2023, 1, 1)]
        initial = make_series(dates)
        result = gen.simulate_candidate(initial, "US", "base")
        held = result.signals[0].ranking[0][0]
        series = make_series(dates, missing={(held, oos[-1])})
        with self.assertRaisesRegex(gen.DataBlocked, "terminal"):
            gen.simulate_candidate(series, "US", "base")

    def test_24_interim_missing_mark_is_stale_but_does_not_change_shares(self):
        dates = fixture_dates(50)
        base = make_series(dates)
        oos = [d for d in dates if d >= date(2023, 1, 1)]
        result0 = gen.simulate_candidate(base, "US", "base")
        ticker = next(f.ticker for f in result0.ledger if f.side == "buy" and f.day == oos[1])
        series = make_series(dates, missing={(ticker, oos[2])})
        result = gen.simulate_candidate(series, "US", "base")
        row = next(r for r in result.daily if r.day == oos[2])
        self.assertIn(ticker, row.stale_marks)
        prior = next(f for f in result.ledger if f.side == "buy" and f.ticker == ticker)
        later = next(f for f in result.ledger if f.side == "sell" and f.ticker == ticker)
        self.assertEqual(prior.shares, later.shares)

    def test_25_nav_ledger_reconciliation_and_nonnegative_cash(self):
        result = gen.simulate_candidate(make_series(fixture_dates(50)), "US", "stress")
        self.assertTrue(all(row.cash >= -gen.TOL for row in result.daily))
        self.assertTrue(all(row.reconciliation_error <= gen.TOL for row in result.daily))
        self.assertEqual(result.daily[-1].nav, result.daily[-1].cash)

    def test_26_benchmark_delayed_first_close_on_terminal_date_stays_cash(self):
        dates = fixture_dates(1)
        oos = [d for d in dates if d >= date(2023, 1, 1)]
        missing = {(ticker, oos[0]) for ticker in gen.COHORTS["US"][:-1]}
        result = gen.simulate_benchmark(make_series(dates, missing=missing), "US", "base")
        self.assertEqual(result.ledger, [])
        self.assertEqual(result.daily[-1].cash, 1.0)

    def test_27_benchmark_fixed_gross_delayed_entry_and_terminal_exit(self):
        dates = fixture_dates(5)
        oos = [d for d in dates if d >= date(2023, 1, 1)]
        ticker = gen.COHORTS["US"][0]
        result = gen.simulate_benchmark(make_series(dates, missing={(ticker, oos[0])}), "US", "base")
        buy = next(f for f in result.ledger if f.side == "buy" and f.ticker == ticker)
        self.assertEqual(buy.day, oos[1])
        sell = next(f for f in result.ledger if f.side == "sell" and f.ticker == ticker)
        self.assertEqual(buy.shares, sell.shares)
        self.assertEqual(sell.day, oos[-1])

    def test_28_prefix_future_mutation_does_not_change_past_signal_or_nav(self):
        dates = fixture_dates(50)
        base = make_series(dates)
        altered = {ticker: dict(rows) for ticker, rows in base.items()}
        oos = [d for d in dates if d >= date(2023, 1, 1)]
        future_start = oos[10]
        for rows in altered.values():
            for day in list(rows):
                if day >= future_start:
                    rows[day] *= 50.0
        left = gen.simulate_candidate(base, "US", "base")
        right = gen.simulate_candidate(altered, "US", "base")
        self.assertEqual(left.signals[:1], right.signals[:1])
        self.assertEqual(left.daily[:10], right.daily[:10])


def make_series_for_market(dates, market):
    missing = set()
    output = {}
    for ticker_idx, ticker in enumerate(gen.COHORTS[market]):
        price = 100.0 + ticker_idx
        rows = {}
        for idx, day in enumerate(dates):
            if idx:
                residue = ((idx * 7 + ticker_idx * 11) % 19) - 9
                ret = residue * 0.0007 + (0.0001 if ticker_idx % 2 else -0.0002)
                price *= 1 + ret
            rows[day] = price
        output[ticker] = rows
    return output


if __name__ == "__main__":
    unittest.main(verbosity=2)
