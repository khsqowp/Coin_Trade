"""Independent synthetic-only implementation of frozen Gen17 skew screen.

The market-data loader is permanently disabled in this runner.  This module
exists solely to test the registered mechanics against in-memory synthetic
series; it must not be used to open the local market cache.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Mapping, Sequence

PREREG_SHA256 = "ecd75ddbae7b59813bbc4837aba2f58d139adb8ec117c89087d07e7334e6cc58"
MANIFEST_SHA256 = "395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4"
COHORTS: dict[str, tuple[str, ...]] = {
    "US": ("AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"),
    "KR": ("000270", "000660", "000810", "005380", "005490", "005930",
           "006400", "009150", "012330", "017670", "028260", "032830",
           "034730", "035420", "055550", "068270", "086790", "105560",
           "316140", "373220", "402340"),
}
K = {"US": 2, "KR": 5}
COSTS = {
    ("US", "base"): (0.0008, 0.0008),
    ("US", "stress"): (0.0036, 0.0036),
    ("KR", "base"): (0.00065, 0.00245),
    ("KR", "stress"): (0.00115, 0.00295),
}
LOOKBACK_CLOSES = 64
LOOKBACK_RETURNS = 63
CADENCE = 21
OOS_START = date(2023, 1, 1)


class DataGateError(RuntimeError):
    pass


@dataclass
class Position:
    ticker: str
    shares: float
    last_close: float
    entry_day: date
    entry_index: int
    scheduled_exit_index: int


@dataclass
class Fill:
    day: date
    ticker: str
    side: str
    close: float
    shares: float
    gross: float
    fee: float
    cash_before: float
    cash_after: float
    reason: str
    rank: int | None = None
    nav_batch: float | None = None


@dataclass
class DayRecord:
    day: date
    cash: float
    nav: float
    holdings: tuple[str, ...]
    marked_nav_pretrade: float
    gross_buys: float
    gross_sells: float
    fees: float
    events: tuple[str, ...]
    stale_marks: tuple[str, ...]


@dataclass
class Simulation:
    candidate: str
    market: str
    scenario: str
    dates: list[date] = field(default_factory=list)
    nav: list[float] = field(default_factory=list)
    cash: list[float] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    daily: list[DayRecord] = field(default_factory=list)
    eligibility_by_decision: dict[date, int] = field(default_factory=dict)
    ranking_by_decision: dict[date, tuple[str, ...]] = field(default_factory=dict)
    filled_by_execution: dict[date, tuple[str, ...]] = field(default_factory=dict)
    skipped_by_execution: dict[date, tuple[str, ...]] = field(default_factory=dict)
    skipped_terminal_decisions: list[date] = field(default_factory=list)


def parse_utc_day(value: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise DataGateError("timestamp_missing")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise DataGateError("timestamp_invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise DataGateError("timestamp_offset_required")
    return stamp.astimezone(timezone.utc).date()


def _valid_close(value: object) -> bool:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(x) and x > 0


def validate_memory_data(data: Mapping[str, Mapping[date, float]], market: str) -> None:
    if market not in COHORTS:
        raise ValueError("unknown market")
    if set(data) != set(COHORTS[market]):
        raise DataGateError("cohort_mismatch")
    for ticker, series in data.items():
        days = list(series)
        if days != sorted(days) or any(type(d) is not date for d in days):
            raise DataGateError(f"invalid_or_unsorted_dates:{ticker}")
        for day, close in series.items():
            if not _valid_close(close):
                raise DataGateError(f"invalid_close:{ticker}:{day}")


def union_calendar(data: Mapping[str, Mapping[date, float]]) -> list[date]:
    days = sorted({d for series in data.values() for d in series})
    if not days:
        raise DataGateError("empty_union_calendar")
    return days


def sample_skewness(returns: Sequence[float]) -> float | None:
    n = len(returns)
    if n != LOOKBACK_RETURNS or any(not math.isfinite(float(x)) for x in returns):
        return None
    mu = mean(returns)
    s = math.sqrt(sum((x - mu) ** 2 for x in returns) / (n - 1))
    if s == 0.0 or not math.isfinite(s):
        return None
    g1 = n / ((n - 1) * (n - 2)) * sum(((x - mu) / s) ** 3 for x in returns)
    return g1 if math.isfinite(g1) else None


def decision_schedule(oos_dates: Sequence[date]) -> list[int]:
    return list(range(0, len(oos_dates), CADENCE))


def _ticker_returns_on_window(
    series: Mapping[date, float], window_dates: Sequence[date]
) -> list[float] | None:
    closes = [series.get(d) for d in window_dates]
    if any(not _valid_close(c) for c in closes):
        return None
    return [float(closes[j]) / float(closes[j - 1]) - 1.0
            for j in range(1, len(closes))]


def score_cross_section(
    data: Mapping[str, Mapping[date, float]], calendar: Sequence[date], index: int
) -> tuple[list[tuple[str, float]], dict[str, tuple[float, ...]]]:
    """Return ascending G1 rank and eligible return vectors at decision index."""
    if index < LOOKBACK_CLOSES - 1 or index >= len(calendar):
        return [], {}
    window = calendar[index - (LOOKBACK_CLOSES - 1): index + 1]
    if len(window) != LOOKBACK_CLOSES:
        return [], {}
    ranked: list[tuple[str, float]] = []
    vectors: dict[str, tuple[float, ...]] = {}
    for ticker, series in data.items():
        returns = _ticker_returns_on_window(series, window)
        if returns is None:
            continue
        score = sample_skewness(returns)
        if score is None:
            continue
        ranked.append((ticker, score))
        vectors[ticker] = tuple(returns)
    ranked.sort(key=lambda item: (item[1], item[0]))
    return ranked, vectors


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for pos in range(start, end):
            ranks[order[pos]] = rank
        start = end
    return ranks


def _pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    mx, my = mean(x), mean(y)
    dx = [a - mx for a in x]
    dy = [b - my for b in y]
    denom = math.sqrt(sum(a * a for a in dx) * sum(b * b for b in dy))
    if denom == 0 or not math.isfinite(denom):
        return None
    rho = sum(a * b for a, b in zip(dx, dy)) / denom
    return rho if math.isfinite(rho) else None


def overlap_diagnostic(vectors: Mapping[str, Sequence[float]]) -> dict[str, float | None]:
    """Descriptive only: G1 rank vs sigma, compound return, signed max return."""
    names = sorted(vectors)
    if len(names) < 4:
        return {"volatility": None, "cumulative_return": None, "max_return": None}
    gs = [sample_skewness(vectors[name]) for name in names]
    if any(x is None for x in gs) or len(set(gs)) <= 1:
        return {"volatility": None, "cumulative_return": None, "max_return": None}
    comparator_values = {
        "volatility": [pstdev(vectors[name]) for name in names],
        "cumulative_return": [math.prod(1.0 + x for x in vectors[name]) - 1.0
                              for name in names],
        "max_return": [max(vectors[name]) for name in names],
    }
    granks = _average_ranks([float(x) for x in gs])
    out: dict[str, float | None] = {}
    for label, values in comparator_values.items():
        if not all(math.isfinite(x) for x in values) or len(set(values)) <= 1:
            out[label] = None
        else:
            out[label] = _pearson(granks, _average_ranks(values))
    return out


def _fees(market: str, scenario: str) -> tuple[float, float]:
    try:
        return COSTS[(market, scenario)]
    except KeyError as exc:
        raise ValueError("unknown market/cost scenario") from exc


def _mark(positions: Mapping[str, Position], data: Mapping[str, Mapping[date, float]],
          day: date) -> tuple[float, tuple[str, ...]]:
    stale: list[str] = []
    gross = 0.0
    for ticker, pos in positions.items():
        close = data[ticker].get(day)
        if close is None:
            stale.append(ticker)
        elif not _valid_close(close):
            raise DataGateError(f"invalid_close:{ticker}:{day}")
        else:
            pos.last_close = float(close)
        gross += pos.shares * pos.last_close
    return gross, tuple(sorted(stale))


def _sell(result: Simulation, positions: dict[str, Position], ticker: str, day: date,
          data: Mapping[str, Mapping[date, float]], cash: float, sell_fee: float,
          reason: str) -> tuple[float, float, float]:
    close = data[ticker].get(day)
    if not _valid_close(close):
        raise DataGateError(f"required_exit_close_missing:{ticker}:{day}")
    pos = positions.pop(ticker)
    gross = pos.shares * float(close)
    fee = gross * sell_fee
    before = cash
    cash += gross - fee
    result.fills.append(Fill(day, ticker, "sell", float(close), pos.shares,
                             gross, fee, before, cash, reason))
    return cash, gross, fee


def _buy(result: Simulation, positions: dict[str, Position], ticker: str, day: date,
         index: int, exit_index: int, data: Mapping[str, Mapping[date, float]],
         cash: float, slot_spend: float, buy_fee: float, nav_batch: float,
         rank: int) -> tuple[float, float, float, bool]:
    close = data[ticker].get(day)
    if not _valid_close(close):
        return cash, 0.0, 0.0, False
    gross = slot_spend / (1.0 + buy_fee)
    fee = gross * buy_fee
    total_spend = gross + fee
    if cash + 1e-12 < total_spend:
        return cash, 0.0, 0.0, False
    shares = gross / float(close)
    before = cash
    cash -= total_spend
    positions[ticker] = Position(ticker, shares, float(close), day, index, exit_index)
    result.fills.append(Fill(day, ticker, "buy", float(close), shares, gross, fee,
                             before, cash, "G1_low_skew", rank, nav_batch))
    return cash, gross, fee, True


def simulate_candidate(
    data: Mapping[str, Mapping[date, float]], market: str, scenario: str,
    start: date = OOS_START, end: date | None = None,
) -> Simulation:
    """Synthetic/in-memory only; no loader or filesystem dependency."""
    validate_memory_data(data, market)
    full_calendar = union_calendar(data)
    final_available = full_calendar[-1]
    end = end or final_available
    oos = [d for d in full_calendar if start <= d <= end]
    if not oos:
        raise DataGateError("empty_oos_segment")
    if end > final_available:
        raise DataGateError("end_after_available_data")
    n, k = len(COHORTS[market]), K[market]
    buy_fee, sell_fee = _fees(market, scenario)
    result = Simulation("G1_low_skew", market, scenario)
    schedule = set(decision_schedule(oos))
    positions: dict[str, Position] = {}
    cash = 1.0
    pending: dict[int, list[tuple[str, float]]] = {}
    exits_at: dict[int, list[str]] = {}
    for signal_idx in sorted(schedule):
        if signal_idx + 1 >= len(oos):
            result.skipped_terminal_decisions.append(oos[signal_idx])
            continue
        if signal_idx + 1 == len(oos) - 1:
            result.skipped_terminal_decisions.append(oos[signal_idx])
            continue
        rank, _ = score_cross_section(data, full_calendar,
                                      full_calendar.index(oos[signal_idx]))
        result.eligibility_by_decision[oos[signal_idx]] = len(rank)
        result.ranking_by_decision[oos[signal_idx]] = tuple(t for t, _ in rank)
        pending[signal_idx + 1] = rank
        if rank:
            exits_at.setdefault(signal_idx + 22, [])

    for idx, day in enumerate(oos):
        marked, stale = _mark(positions, data, day)
        pretrade_nav = cash + marked
        gross_buys = gross_sells = fees = 0.0
        events: list[str] = []

        for ticker in sorted(exits_at.get(idx, [])):
            if ticker in positions:
                cash, gross, fee = _sell(result, positions, ticker, day, data,
                                         cash, sell_fee, "scheduled_21_interval_exit")
                gross_sells += gross
                fees += fee
                events.append(f"exit:{ticker}")

        # Final union date is terminal-only: no new entries are permitted.
        if idx in pending and idx != len(oos) - 1:
            ranked = pending[idx]
            nav_batch = cash + sum(p.shares * p.last_close for p in positions.values())
            slot_spend = nav_batch / k
            filled: list[str] = []
            skipped: list[str] = []
            scheduled_exit = min(idx + 21, len(oos) - 1)
            for rank_number, (ticker, _score) in enumerate(ranked, start=1):
                if len(filled) >= k:
                    break
                cash, gross, fee, did_fill = _buy(
                    result, positions, ticker, day, idx, scheduled_exit, data,
                    cash, slot_spend, buy_fee, nav_batch, rank_number,
                )
                if did_fill:
                    gross_buys += gross
                    fees += fee
                    filled.append(ticker)
                    events.append(f"entry:{ticker}:rank{rank_number}")
                    # A lot from decision s is due at s+22; execution index is s+1.
                    signal_idx = idx - 1
                    exit_idx = min(signal_idx + 22, len(oos) - 1)
                    exits_at.setdefault(exit_idx, []).append(ticker)
                else:
                    skipped.append(ticker)
                    events.append(f"skip:{ticker}:rank{rank_number}")
            result.filled_by_execution[day] = tuple(filled)
            result.skipped_by_execution[day] = tuple(skipped)

        if idx == len(oos) - 1:
            for ticker in sorted(list(positions)):
                cash, gross, fee = _sell(result, positions, ticker, day, data,
                                         cash, sell_fee, "terminal_liquidation")
                gross_sells += gross
                fees += fee
                events.append(f"terminal_exit:{ticker}")

        hold_value = sum(p.shares * p.last_close for p in positions.values())
        nav = cash + hold_value
        if not math.isfinite(nav) or nav <= 0.0 or cash < -1e-10:
            raise DataGateError(f"invalid_account_state:{day}")
        result.dates.append(day)
        result.nav.append(nav)
        result.cash.append(cash)
        result.daily.append(DayRecord(day, cash, nav, tuple(sorted(positions)),
                                      pretrade_nav, gross_buys, gross_sells, fees,
                                      tuple(events), stale))
    if positions or abs(result.nav[-1] - cash) > 1e-10:
        raise DataGateError("terminal_reconciliation_failed")
    return result


def simulate_benchmark(data: Mapping[str, Mapping[date, float]], market: str,
                       scenario: str, start: date, end: date) -> Simulation:
    validate_memory_data(data, market)
    calendar = [d for d in union_calendar(data) if start <= d <= end]
    if not calendar:
        raise DataGateError("empty_benchmark_segment")
    buy_fee, sell_fee = _fees(market, scenario)
    n = len(COHORTS[market])
    result = Simulation("B&H", market, scenario)
    cash = 1.0
    positions: dict[str, Position] = {}
    unbought = set(COHORTS[market])
    total_spend = 1.0 / n
    gross_target = total_spend / (1.0 + buy_fee)
    for idx, day in enumerate(calendar):
        marked, stale = _mark(positions, data, day)
        pretrade_nav = cash + marked
        gross_buys = gross_sells = fees = 0.0
        events: list[str] = []
        if idx != len(calendar) - 1:
            for ticker in sorted(list(unbought)):
                close = data[ticker].get(day)
                if not _valid_close(close):
                    continue
                fee = gross_target * buy_fee
                spend = gross_target + fee
                if cash + 1e-12 < spend:
                    raise DataGateError("benchmark_reserved_cash_short")
                before = cash
                cash -= spend
                shares = gross_target / float(close)
                positions[ticker] = Position(ticker, shares, float(close), day, idx,
                                             len(calendar) - 1)
                result.fills.append(Fill(day, ticker, "buy", float(close), shares,
                                         gross_target, fee, before, cash,
                                         "benchmark_initial_or_delayed"))
                unbought.remove(ticker)
                gross_buys += gross_target
                fees += fee
                events.append(f"benchmark_entry:{ticker}")
        if idx == len(calendar) - 1:
            for ticker in sorted(list(positions)):
                cash, gross, fee = _sell(result, positions, ticker, day, data,
                                         cash, sell_fee, "benchmark_terminal_liquidation")
                gross_sells += gross
                fees += fee
                events.append(f"benchmark_exit:{ticker}")
        nav = cash + sum(p.shares * p.last_close for p in positions.values())
        if nav <= 0 or not math.isfinite(nav) or cash < -1e-10:
            raise DataGateError("benchmark_invalid_account_state")
        result.dates.append(day)
        result.nav.append(nav)
        result.cash.append(cash)
        result.daily.append(DayRecord(day, cash, nav, tuple(sorted(positions)),
                                      pretrade_nav, gross_buys, gross_sells, fees,
                                      tuple(events), stale))
    if positions or abs(result.nav[-1] - cash) > 1e-10:
        raise DataGateError("benchmark_terminal_reconciliation")
    return result


def summarize(result: Simulation) -> dict[str, float | int | None]:
    if not result.nav or len(result.nav) != len(result.dates):
        raise DataGateError("empty_or_misaligned_path")
    if any(not math.isfinite(x) or x <= 0 for x in result.nav):
        raise DataGateError("invalid_nav")
    initial_day = result.dates[0] - timedelta(days=1)
    elapsed = (result.dates[-1] - initial_day).days
    if elapsed <= 0:
        raise DataGateError("invalid_elapsed_days")
    returns = [result.nav[0] - 1.0]
    returns.extend(result.nav[i] / result.nav[i - 1] - 1.0
                   for i in range(1, len(result.nav)))
    sd = pstdev(returns) if len(returns) > 1 else 0.0
    sharpe = mean(returns) / sd * math.sqrt(252.0) if sd > 0 else None
    peak, mdd = 1.0, 0.0
    for nav in result.nav:
        peak = max(peak, nav)
        mdd = max(mdd, 1.0 - nav / peak)
    turnover = sum((d.gross_buys + d.gross_sells) / d.marked_nav_pretrade
                   for d in result.daily if d.marked_nav_pretrade > 0)
    total_costs = sum(f.fee for f in result.fills)
    return {
        "cagr": result.nav[-1] ** (365.2425 / elapsed) - 1.0,
        "sharpe": sharpe,
        "mdd": mdd,
        "terminal_nav": result.nav[-1],
        "turnover": turnover,
        "total_costs": total_costs,
        "fill_count": len(result.fills),
        "average_cash_share": mean(d.cash / d.nav for d in result.daily),
    }


def screen_pass(candidate: Mapping[str, object], benchmark: Mapping[str, object]) -> bool:
    if candidate.get("sharpe") is None or benchmark.get("sharpe") is None:
        return False
    return (float(candidate["cagr"]) > float(benchmark["cagr"])
            and float(candidate["sharpe"]) > float(benchmark["sharpe"])
            and float(candidate["mdd"]) <= float(benchmark["mdd"]))


def load_market_data(*_args: object, **_kwargs: object) -> None:
    """Permanent safety latch: intentionally contains no file-read operation."""
    raise RuntimeError("BLOCKED: Gen17 runner C has no market-data loader")


def run_market_performance(*_args: object, **_kwargs: object) -> None:
    """Market-performance entry point is intentionally unreachable."""
    raise RuntimeError("BLOCKED: synthetic-only runner; market performance forbidden")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--market-performance", action="store_true")
    args = parser.parse_args(argv)
    if args.market_performance:
        print("BLOCKED: synthetic-only runner; market performance forbidden")
        return 3
    print(f"SYNTHETIC_ONLY prereg={PREREG_SHA256} manifest={MANIFEST_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
