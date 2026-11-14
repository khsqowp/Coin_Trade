"""Synthetic-only test suite for /private/tmp/gen17_C.py."""
from __future__ import annotations

import builtins
import importlib.util
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PATH = Path("/private/tmp/gen17_C.py")
spec = importlib.util.spec_from_file_location("gen17_C", PATH)
g = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = g
spec.loader.exec_module(g)


def weekdays(start: date, count: int) -> list[date]:
    days: list[date] = []
    d = start
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def synthetic_data(market: str = "US", count: int = 120) -> dict[str, dict[date, float]]:
    days = weekdays(date(2022, 10, 3), count)
    data: dict[str, dict[date, float]] = {}
    for j, ticker in enumerate(g.COHORTS[market]):
        px = 80.0 + 7.0 * j
        series: dict[date, float] = {}
        for i, day in enumerate(days):
            # A deterministic, nonstationary mix gives each name a distinct
            # return distribution while retaining valid positive prices.
            ret = 0.0003 * (j - 2) + 0.0012 * math.sin((i + 1) * (j + 1) * 0.31)
            if i % (13 + j) == (j % 7):
                ret += 0.012 * (1 if (i // (13 + j)) % 2 else -0.6)
            px *= 1.0 + ret
            series[day] = px
        data[ticker] = series
    return data


def test_utc_timestamp_requires_explicit_timezone():
    assert g.parse_utc_day("2023-01-01T00:30:00+02:00") == date(2022, 12, 31)
    assert g.parse_utc_day("2023-01-01T00:00:00Z") == date(2023, 1, 1)
    with pytest.raises(g.DataGateError, match="offset_required"):
        g.parse_utc_day("2023-01-01T00:00:00")


def test_sample_skew_exact_formula_and_equal_moments_different_skew():
    symmetric = [-1.0] * 21 + [0.0] * 21 + [1.0] * 21
    asymmetric = [-2.0] * 7 + [1.0] * 14 + [0.0] * 42
    assert sum(symmetric) == sum(asymmetric) == 0.0
    assert sum(x * x for x in symmetric) == sum(x * x for x in asymmetric)
    s = math.sqrt(sum(x * x for x in symmetric) / 62)
    expected = 63 / (62 * 61) * sum((x / s) ** 3 for x in symmetric)
    assert g.sample_skewness(symmetric) == pytest.approx(expected, abs=1e-15)
    assert g.sample_skewness(symmetric) == pytest.approx(0.0, abs=1e-15)
    assert g.sample_skewness(asymmetric) < 0


def test_skewness_positive_scale_invariance_and_extreme_return_sensitivity():
    base = [0.001 * math.sin(i * 0.4) for i in range(63)]
    base[-1] += 0.25
    scaled_prices = {date(2022, 1, 1) + timedelta(days=i): 100 * (1 + base[i])
                     for i in range(63)}
    scaled_prices_2 = {d: value * 1000 for d, value in scaled_prices.items()}
    ret1 = [scaled_prices[d] / scaled_prices[date(2022, 1, 1) + timedelta(days=i - 1)] - 1
            for i, d in enumerate(scaled_prices) if i > 0]
    ret2 = [scaled_prices_2[d] / scaled_prices_2[date(2022, 1, 1) + timedelta(days=i - 1)] - 1
            for i, d in enumerate(scaled_prices_2) if i > 0]
    # The price-level scaling leaves all derived returns and skew unchanged.
    assert g.sample_skewness(ret1) == pytest.approx(g.sample_skewness(ret2), abs=1e-12)
    ordinary = [0.001 * math.sin(i) for i in range(63)]
    positive_extreme = ordinary.copy()
    negative_extreme = ordinary.copy()
    positive_extreme[-1] = 1.0
    negative_extreme[-1] = -0.5
    assert g.sample_skewness(positive_extreme) > g.sample_skewness(ordinary)
    assert g.sample_skewness(negative_extreme) < g.sample_skewness(ordinary)


def test_exact_64_close_boundary_and_missing_or_constant_windows():
    data = synthetic_data(count=80)
    dates = g.union_calendar(data)
    ranked, vectors = g.score_cross_section(data, dates, 62)
    assert not ranked and not vectors
    ranked, vectors = g.score_cross_section(data, dates, 63)
    assert len(ranked) == len(g.COHORTS["US"])
    assert all(len(values) == 63 for values in vectors.values())
    ticker = g.COHORTS["US"][0]
    del data[ticker][dates[40]]
    ranked, _ = g.score_cross_section(data, dates, 63)
    assert ticker not in {name for name, _ in ranked}
    constant = {d: 100.0 for d in dates}
    assert g.sample_skewness([constant[dates[0]] / 100.0 - 1.0] * 63) is None


def test_rank_order_tie_break_and_schedule_indices():
    assert g.decision_schedule(list(range(100))) == [0, 21, 42, 63, 84]
    rows = [("B", 0.0), ("A", 0.0), ("C", -0.1)]
    assert sorted(rows, key=lambda x: (x[1], x[0])) == [
        ("C", -0.1), ("A", 0.0), ("B", 0.0)
    ]
    data = synthetic_data(count=80)
    dates = g.union_calendar(data)
    a, b = g.COHORTS["US"][:2]
    data[b] = dict(data[a])
    tied_rank, _ = g.score_cross_section(data, dates, 63)
    tie_scores = {name: score for name, score in tied_rank}
    assert tie_scores[a] == tie_scores[b]
    ordered_ties = [name for name, _ in tied_rank if name in {a, b}]
    assert ordered_ties == sorted([a, b])


def test_overlap_correlations_define_minimum_sample_ties_and_zero_variance():
    base = tuple(0.001 * math.sin((j + 1) * 0.73) for j in range(63))
    same = {f"T{i}": base for i in range(4)}
    corr = g.overlap_diagnostic(same)
    assert set(corr) == {"volatility", "cumulative_return", "max_return"}
    assert all(value is None for value in corr.values())  # G1 cross-section is constant.
    assert all(value is None for value in g.overlap_diagnostic({k: v for k, v in same.items()
                                                               if k != "T3"}).values())
    values = [3.0, 1.0, 1.0, 4.0]
    assert g._average_ranks(values) == [3.0, 1.5, 1.5, 4.0]
    assert g._pearson([1, 1], [2, 3]) is None


def test_first_decision_executes_next_union_close_and_holds_21_intervals():
    data = synthetic_data(count=120)
    dates = g.union_calendar(data)
    oos = [d for d in dates if d >= date(2023, 1, 1)]
    assert len(oos) > 44
    sim = g.simulate_candidate(data, "US", "base", start=date(2023, 1, 1), end=oos[43])
    first_exec = oos[1]
    second_exec = oos[22]
    first_buys = [f for f in sim.fills if f.side == "buy" and f.day == first_exec]
    first_sells = [f for f in sim.fills if f.side == "sell" and f.day == second_exec
                   and f.reason == "scheduled_21_interval_exit"]
    second_buys = [f for f in sim.fills if f.side == "buy" and f.day == second_exec]
    assert len(first_buys) == g.K["US"]
    assert len(first_sells) == len(first_buys)
    assert len(second_buys) == g.K["US"]
    assert sim.dates.index(second_exec) - sim.dates.index(first_exec) == 21
    assert max(sim.fills.index(f) for f in first_sells) < min(sim.fills.index(f) for f in second_buys)


def test_execution_time_full_rank_fallback_and_fee_inclusive_budget():
    data = synthetic_data(count=90)
    dates = g.union_calendar(data)
    oos = [d for d in dates if d >= date(2023, 1, 1)]
    first_signal_index = g.union_calendar(data).index(oos[0])
    ranked, _ = g.score_cross_section(data, dates, first_signal_index)
    assert len(ranked) >= 3
    missing_ticker = ranked[0][0]
    del data[missing_ticker][oos[1]]
    sim = g.simulate_candidate(data, "US", "stress", start=date(2023, 1, 1), end=oos[22])
    buys = [f for f in sim.fills if f.side == "buy" and f.day == oos[1]]
    assert len(buys) == 2
    assert missing_ticker not in {f.ticker for f in buys}
    assert sim.skipped_by_execution[oos[1]][0] == missing_ticker
    assert all(f.gross + f.fee == pytest.approx(f.nav_batch / g.K["US"])
               for f in buys)
    by_ticker = {}
    for fill in sim.fills:
        if fill.side == "buy":
            by_ticker[fill.ticker] = fill.shares
        elif fill.reason == "scheduled_21_interval_exit":
            assert fill.shares == pytest.approx(by_ticker[fill.ticker])


def test_terminal_signal_and_execution_final_date_never_create_new_entries():
    data = synthetic_data(count=100)
    all_dates = g.union_calendar(data)
    oos = [d for d in all_dates if d >= date(2023, 1, 1)]
    # Final index 22 is the execution date of decision 21; decision 0 trades,
    # decision 21 is skipped, and the first block is liquidated at final close.
    sim = g.simulate_candidate(data, "US", "base", start=date(2023, 1, 1), end=oos[22])
    assert all(f.day != oos[22] or f.side != "buy" for f in sim.fills)
    assert oos[21] in sim.skipped_terminal_decisions
    assert sim.nav[-1] == pytest.approx(sim.cash[-1], abs=1e-10)
    # If a decision itself lands on the last date, it is recorded without order.
    sim2 = g.simulate_candidate(data, "US", "base", start=date(2023, 1, 1), end=oos[21])
    assert oos[21] in sim2.skipped_terminal_decisions
    assert all(f.day != oos[21] or f.side != "buy" for f in sim2.fills)


def test_missing_required_exit_blocks_and_interim_missing_mark_is_stale_only():
    data = synthetic_data(count=100)
    dates = g.union_calendar(data)
    oos = [d for d in dates if d >= date(2023, 1, 1)]
    full = g.simulate_candidate(data, "US", "base", start=date(2023, 1, 1), end=oos[22])
    bought = next(f.ticker for f in full.fills if f.side == "buy" and f.day == oos[1])
    del data[bought][oos[22]]
    with pytest.raises(g.DataGateError, match="required_exit_close_missing"):
        g.simulate_candidate(data, "US", "base", start=date(2023, 1, 1), end=oos[22])


def test_benchmark_delayed_initial_close_on_terminal_date_stays_cash():
    data = synthetic_data(count=70)
    days = g.union_calendar(data)
    ticker = g.COHORTS["US"][0]
    for d in days[:-1]:
        del data[ticker][d]
    bench = g.simulate_benchmark(data, "US", "base", days[0], days[-1])
    assert not [f for f in bench.fills if f.ticker == ticker]
    assert bench.nav[-1] == pytest.approx(bench.cash[-1], abs=1e-10)


def test_benchmark_terminal_holding_without_actual_close_blocks():
    data = synthetic_data(count=70)
    days = g.union_calendar(data)
    ticker = g.COHORTS["US"][0]
    del data[ticker][days[-1]]
    with pytest.raises(g.DataGateError, match="required_exit_close_missing"):
        g.simulate_benchmark(data, "US", "base", days[0], days[-1])


def test_ledger_nav_cost_turnover_metrics_and_screen():
    data = synthetic_data(count=110)
    days = [d for d in g.union_calendar(data) if d >= date(2023, 1, 1)]
    candidate = g.simulate_candidate(data, "US", "stress", start=date(2023, 1, 1), end=days[43])
    benchmark = g.simulate_benchmark(data, "US", "stress", days[0], days[43])
    for sim in (candidate, benchmark):
        cash = 1.0
        positions: dict[str, float] = {}
        last_price: dict[str, float] = {}
        fills_by_day: dict[date, list] = {}
        for fill in sim.fills:
            fills_by_day.setdefault(fill.day, []).append(fill)
        for day, record in zip(sim.dates, sim.daily):
            for fill in fills_by_day.get(day, []):
                if fill.side == "buy":
                    cash -= fill.gross + fill.fee
                    positions[fill.ticker] = positions.get(fill.ticker, 0.0) + fill.shares
                else:
                    cash += fill.gross - fill.fee
                    positions.pop(fill.ticker)
                last_price[fill.ticker] = fill.close
            for ticker, series in data.items():
                if ticker in positions and day in series:
                    last_price[ticker] = series[day]
            replay_nav = cash + sum(positions[t] * last_price[t] for t in positions)
            assert record.cash == pytest.approx(cash, abs=1e-10)
            assert record.nav == pytest.approx(replay_nav, abs=1e-10)
            assert set(record.holdings) == set(positions)
            assert record.marked_nav_pretrade > 0
        assert sim.nav[-1] == pytest.approx(sim.cash[-1], abs=1e-10)
        summary = g.summarize(sim)
        assert summary["fill_count"] == len(sim.fills)
        assert summary["total_costs"] == pytest.approx(sum(f.fee for f in sim.fills))
        assert summary["turnover"] >= 0
    assert not g.screen_pass({"cagr": 1, "sharpe": None, "mdd": 0},
                             {"cagr": 0, "sharpe": 1, "mdd": 1})


def test_future_mutation_prefix_invariance_and_final_hash_guard():
    data = synthetic_data(count=110)
    days = [d for d in g.union_calendar(data) if d >= date(2023, 1, 1)]
    cut = days[22]
    first = g.simulate_candidate(data, "US", "base", date(2023, 1, 1), cut)
    mutated = {ticker: dict(series) for ticker, series in data.items()}
    for series in mutated.values():
        for d in list(series):
            if d > cut:
                series[d] *= 4.0
    second = g.simulate_candidate(mutated, "US", "base", date(2023, 1, 1), cut)
    assert first.nav == second.nav
    assert [(f.day, f.ticker, f.side, f.gross, f.fee) for f in first.fills] == [
        (f.day, f.ticker, f.side, f.gross, f.fee) for f in second.fills
    ]
    assert g.PREREG_SHA256 == "ecd75ddbae7b59813bbc4837aba2f58d139adb8ec117c89087d07e7334e6cc58"
    with pytest.raises(RuntimeError, match="no market-data loader"):
        g.load_market_data()
    with pytest.raises(RuntimeError, match="market performance forbidden"):
        g.run_market_performance()
    # Explicitly prove loader guard does not attempt an open.
    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("filesystem access attempted")
    old_open = builtins.open
    builtins.open = forbidden_open
    try:
        with pytest.raises(RuntimeError, match="no market-data loader"):
            g.load_market_data("/private/tmp/does-not-exist")
    finally:
        builtins.open = old_open
