"""Gen17 independent runner B: synthetic mechanics only, market execution disabled.

The frozen specification and data manifest hashes are embedded for audit. This
module deliberately has no enabled path that reads market files or calculates
market/overlap outputs. Synthetic mappings may be supplied directly to the
simulation functions for contract tests only.
"""
from __future__ import annotations

import argparse
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence


PREREG_SHA256 = "ecd75ddbae7b59813bbc4837aba2f58d139adb8ec117c89087d07e7334e6cc58"
INPUT_MANIFEST_SHA256 = "395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4"
US_COHORT = ("AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA")
KR_COHORT = (
    "000270", "000660", "000810", "005380", "005490", "005930", "006400",
    "009150", "012330", "017670", "028260", "032830", "034730", "035420",
    "055550", "068270", "086790", "105560", "316140", "373220", "402340",
)
SLOTS = {"US": 2, "KR": 5}
FEES = {
    ("US", "base"): (0.0008, 0.0008),
    ("US", "stress"): (0.0036, 0.0036),
    ("KR", "base"): (0.00065, 0.00245),
    ("KR", "stress"): (0.00115, 0.00295),
}
LOOKBACK_RETURNS = 63
LOOKBACK_CLOSES = LOOKBACK_RETURNS + 1
REBALANCE_INTERVAL = 21
NAV_TOL = 1e-10


class DataBlocked(RuntimeError):
    """Input or required observation blocks a valid synthetic cell."""


class ImplementationError(RuntimeError):
    """Internal cash/share/NAV ledger invariant failed."""


@dataclass(frozen=True)
class RankedName:
    symbol: str
    score: float


@dataclass(frozen=True)
class SignalRanking:
    day: date
    ranked: tuple[RankedName, ...]
    eligible_count: int


@dataclass(frozen=True)
class Fill:
    day: date
    symbol: str
    side: str
    price: float
    shares: float
    gross: float
    fee: float
    cash_before: float
    cash_after: float
    reason: str
    rank: int | None = None


@dataclass
class Position:
    symbol: str
    shares: float
    last_close: float
    entry_day: date


@dataclass
class Run:
    strategy: str
    market: str
    cost_case: str
    nav: list[tuple[date, float]] = field(default_factory=list)
    cash_path: list[tuple[date, float]] = field(default_factory=list)
    holdings_path: list[tuple[date, tuple[tuple[str, float, float], ...]]] = field(default_factory=list)
    event_path: list[tuple[date, tuple[str, ...]]] = field(default_factory=list)
    stale_mark_path: list[tuple[date, int]] = field(default_factory=list)
    decision_dates: list[date] = field(default_factory=list)
    rank_by_decision: dict[date, tuple[str, ...]] = field(default_factory=dict)
    selected_by_decision: dict[date, tuple[str, ...]] = field(default_factory=dict)
    eligible_by_decision: dict[date, int] = field(default_factory=dict)
    filled_by_execution: dict[date, tuple[str, ...]] = field(default_factory=dict)
    unused_slots_by_execution: dict[date, int] = field(default_factory=dict)
    skipped_decisions: list[tuple[date, str]] = field(default_factory=list)
    unbought_terminal: tuple[str, ...] = ()
    canceled_entries: int = 0
    stale_marks: int = 0
    windows: int = 0
    skipped_windows: int = 0
    cash: float = 1.0
    positions: dict[str, Position] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    daily_turnover: list[tuple[date, float]] = field(default_factory=list)
    oos_dates: list[date] = field(default_factory=list)


def parse_utc_date(timestamp: str) -> date:
    raw = timestamp.strip()
    if not raw:
        raise DataBlocked("empty_timestamp")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise DataBlocked(f"invalid_timestamp:{timestamp}") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise DataBlocked(f"naive_timestamp:{timestamp}")
    return value.astimezone(timezone.utc).date()


def valid_close(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0.0


def normalize_bars(
    raw_bars: Mapping[str, Mapping[date | str | datetime, object]],
) -> dict[str, dict[date, float]]:
    """Validate ordered in-memory closes; never loads or repairs observations."""
    if not raw_bars:
        raise DataBlocked("empty_cohort")
    normalized: dict[str, dict[date, float]] = {}
    for symbol, rows in raw_bars.items():
        if not symbol or not rows:
            raise DataBlocked(f"empty_symbol_series:{symbol}")
        output: dict[date, float] = {}
        previous: date | None = None
        for raw_day, raw_close in rows.items():
            if isinstance(raw_day, datetime):
                if raw_day.tzinfo is None or raw_day.utcoffset() is None:
                    raise DataBlocked(f"naive_timestamp:{symbol}:{raw_day}")
                day = raw_day.astimezone(timezone.utc).date()
            elif isinstance(raw_day, str):
                day = parse_utc_date(raw_day)
            elif isinstance(raw_day, date):
                day = raw_day
            else:
                raise DataBlocked(f"invalid_date:{symbol}:{raw_day}")
            if day in output:
                raise DataBlocked(f"duplicate_date:{symbol}:{day}")
            if previous is not None and day <= previous:
                raise DataBlocked(f"non_increasing_dates:{symbol}:{day}")
            if not valid_close(raw_close):
                raise DataBlocked(f"invalid_close:{symbol}:{day}")
            output[day] = float(raw_close)
            previous = day
        normalized[symbol] = output
    return normalized


def union_calendar(bars: Mapping[str, Mapping[date, float]]) -> list[date]:
    calendar = sorted({day for rows in bars.values() for day in rows})
    if not calendar:
        raise DataBlocked("empty_calendar")
    return calendar


def fisher_pearson_skew(returns: Sequence[float]) -> float:
    """Bias-corrected Fisher-Pearson sample skewness, exactly as preregistered."""
    n = len(returns)
    if n < 3:
        raise ValueError("skew_requires_at_least_three_returns")
    if any(not math.isfinite(float(value)) for value in returns):
        raise ValueError("non_finite_return")
    mean = sum(returns) / n
    variance = sum((value - mean) ** 2 for value in returns) / (n - 1)
    if variance == 0.0:
        raise ValueError("zero_variance")
    sample_sd = math.sqrt(variance)
    result = n / ((n - 1) * (n - 2)) * sum(
        ((value - mean) / sample_sd) ** 3 for value in returns
    )
    if not math.isfinite(result):
        raise ValueError("non_finite_skew")
    return result


def _window_returns(
    bars: Mapping[str, Mapping[date, float]],
    symbol: str,
    day: date,
    calendar: Sequence[date],
) -> list[float] | None:
    try:
        end_index = calendar.index(day)
    except ValueError:
        raise DataBlocked(f"signal_day_not_in_union_calendar:{day}")
    if end_index + 1 < LOOKBACK_CLOSES:
        return None
    dates = calendar[end_index - LOOKBACK_RETURNS:end_index + 1]
    rows = bars.get(symbol, {})
    closes = [rows.get(window_day) for window_day in dates]
    if any(close is None or not valid_close(close) for close in closes):
        return None
    return [float(closes[i]) / float(closes[i - 1]) - 1.0 for i in range(1, len(closes))]


def score_at(
    raw_bars: Mapping[str, Mapping[date | str | datetime, object]],
    symbol: str,
    day: date,
) -> float | None:
    bars = normalize_bars(raw_bars)
    returns = _window_returns(bars, symbol, day, union_calendar(bars))
    if returns is None:
        return None
    try:
        return fisher_pearson_skew(returns)
    except ValueError as exc:
        if str(exc) == "zero_variance":
            return None
        raise


def signal_ranking(
    raw_bars: Mapping[str, Mapping[date | str | datetime, object]],
    day: date,
    symbols: Sequence[str] | None = None,
) -> SignalRanking:
    bars = normalize_bars(raw_bars)
    calendar = union_calendar(bars)
    ranked: list[RankedName] = []
    for symbol in (list(symbols) if symbols is not None else sorted(bars)):
        returns = _window_returns(bars, symbol, day, calendar)
        if returns is None:
            continue
        try:
            score = fisher_pearson_skew(returns)
        except ValueError as exc:
            if str(exc) == "zero_variance":
                continue
            raise
        ranked.append(RankedName(symbol, score))
    ranked.sort(key=lambda item: (item.score, item.symbol))
    return SignalRanking(day, tuple(ranked), len(ranked))


def decision_indices(length: int) -> list[int]:
    if length < 0:
        raise ValueError("negative_length")
    return list(range(0, length, REBALANCE_INTERVAL))


def _average_ranks(values: Sequence[float]) -> list[float]:
    """One-based average ranks for exact ties, ascending."""
    ordered = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    begin = 0
    while begin < len(ordered):
        end = begin + 1
        while end < len(ordered) and ordered[end][1] == ordered[begin][1]:
            end += 1
        average_rank = ((begin + 1) + end) / 2.0
        for offset in range(begin, end):
            ranks[ordered[offset][0]] = average_rank
        begin = end
    return ranks


def _rank_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Spearman correlation using average ranks; None for zero rank variance."""
    if len(left) != len(right) or len(left) < 2:
        return None
    x = _average_ranks(left)
    y = _average_ranks(right)
    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    covariance = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y))
    x_ss = sum((a - x_mean) ** 2 for a in x)
    y_ss = sum((b - y_mean) ** 2 for b in y)
    if x_ss == 0.0 or y_ss == 0.0:
        return None
    return covariance / math.sqrt(x_ss * y_ss)


def overlap_diagnostic(
    scores: Mapping[str, float],
    returns_by_symbol: Mapping[str, Sequence[float]],
) -> dict[str, float | None]:
    """Per-decision synthetic Spearman diagnostics from the frozen prereg.

    Callers must provide the exact same eligible cross-section and 63 returns
    per name. This function is never called by the synthetic-only runner CLI or
    by any market-data path.
    """
    if set(scores) != set(returns_by_symbol):
        raise ImplementationError("overlap_cross_section_mismatch")
    symbols = sorted(scores)
    g1 = [float(scores[symbol]) for symbol in symbols]
    if any(not math.isfinite(value) for value in g1):
        raise ImplementationError("overlap_non_finite_g1")
    validated_returns: dict[str, list[float]] = {}
    for symbol in symbols:
        values = [float(value) for value in returns_by_symbol[symbol]]
        if len(values) != LOOKBACK_RETURNS or any(not math.isfinite(value) or value <= -1.0 for value in values):
            raise ImplementationError(f"overlap_invalid_return_window:{symbol}")
        validated_returns[symbol] = values
    if len(symbols) < 4 or len(set(g1)) == 1:
        return {"realized_std": None, "compound_return": None, "max_return": None}

    vol_values: list[float] = []
    compound_values: list[float] = []
    max_values: list[float] = []
    for symbol in symbols:
        values = validated_returns[symbol]
        mean = sum(values) / LOOKBACK_RETURNS
        vol_values.append(math.sqrt(sum((value - mean) ** 2 for value in values) / LOOKBACK_RETURNS))
        compound = 1.0
        for value in values:
            compound *= 1.0 + value
        compound_values.append(compound - 1.0)
        max_values.append(max(values))

    if any(not math.isfinite(value) for values in (vol_values, compound_values, max_values) for value in values):
        raise ImplementationError("overlap_non_finite_comparator")

    return {
        "realized_std": _rank_correlation(g1, vol_values),
        "compound_return": _rank_correlation(g1, compound_values),
        "max_return": _rank_correlation(g1, max_values),
    }


def cost_rates(market: str, cost_case: str) -> tuple[float, float]:
    try:
        return FEES[(market, cost_case)]
    except KeyError as exc:
        raise ValueError(f"unsupported market/cost:{market}/{cost_case}") from exc


def _nav(cash: float, positions: Mapping[str, Position]) -> float:
    return cash + sum(position.shares * position.last_close for position in positions.values())


def _mark(
    run: Run,
    bars: Mapping[str, Mapping[date, float]],
    day: date,
) -> None:
    for symbol, position in run.positions.items():
        close = bars.get(symbol, {}).get(day)
        if close is None:
            run.stale_marks += 1
        elif not valid_close(close):
            raise DataBlocked(f"invalid_mark_close:{run.market}:{symbol}:{day}")
        else:
            position.last_close = float(close)


def _sell(run: Run, day: date, symbol: str, price: float | None, fee_rate: float, reason: str) -> None:
    if not valid_close(price):
        gate = "terminal_price_missing" if reason == "terminal_liquidation" else "scheduled_exit_price_missing"
        raise DataBlocked(f"{gate}:{run.market}:{symbol}:{day}")
    position = run.positions.pop(symbol)
    gross = position.shares * float(price)
    fee = gross * fee_rate
    before = run.cash
    run.cash += gross - fee
    run.fills.append(Fill(day, symbol, "sell", float(price), position.shares, gross, fee,
                          before, run.cash, reason))


def _buy(
    run: Run,
    day: date,
    symbol: str,
    price: float | None,
    gross: float,
    fee_rate: float,
    reason: str,
    rank: int | None = None,
) -> bool:
    if not valid_close(price):
        run.canceled_entries += 1
        return False
    debit = gross * (1.0 + fee_rate)
    if run.cash + NAV_TOL < debit:
        run.canceled_entries += 1
        return False
    before = run.cash
    fee = gross * fee_rate
    shares = gross / float(price)
    run.cash -= debit
    if run.cash < 0.0 and run.cash > -NAV_TOL:
        run.cash = 0.0
    run.positions[symbol] = Position(symbol, shares, float(price), day)
    run.fills.append(Fill(day, symbol, "buy", float(price), shares, gross, fee,
                          before, run.cash, reason, rank))
    return True


def _append_day(run: Run, day: date, pre_trade_nav: float, fill_start: int) -> None:
    nav = _nav(run.cash, run.positions)
    if not math.isfinite(nav) or nav <= 0.0:
        raise ImplementationError(f"invalid_nav:{day}:{nav}")
    if run.cash < -NAV_TOL:
        raise ImplementationError(f"negative_cash:{day}:{run.cash}")
    run.nav.append((day, nav))
    run.cash_path.append((day, run.cash))
    turnover_gross = sum(fill.gross for fill in run.fills[fill_start:])
    run.daily_turnover.append((day, turnover_gross / pre_trade_nav if pre_trade_nav > 0 else 0.0))
    run.holdings_path.append((day, tuple(sorted(
        (p.symbol, p.shares, p.last_close) for p in run.positions.values()
    ))))
    run.event_path.append((day, tuple(
        f"{fill.side}:{fill.symbol}:{fill.reason}" for fill in run.fills[fill_start:]
    )))
    run.stale_mark_path.append((day, run.stale_marks))


def _oos_dates(calendar: Sequence[date], start: date, end: date) -> list[date]:
    dates = [day for day in calendar if start <= day <= end]
    if not dates:
        raise DataBlocked("empty_oos_segment")
    return dates


def simulate_candidate(
    raw_bars: Mapping[str, Mapping[date | str | datetime, object]],
    market: str,
    cost_case: str,
    start: date,
    end: date,
) -> Run:
    """Run only a caller-supplied synthetic mapping using frozen Gen17 rules."""
    bars = normalize_bars(raw_bars)
    symbols = sorted(bars)
    calendar = union_calendar(bars)
    dates = _oos_dates(calendar, start, end)
    oos_index = {day: i for i, day in enumerate(dates)}
    buy_fee, sell_fee = cost_rates(market, cost_case)
    slots = SLOTS[market]
    run = Run("GEN17_LOW_SKEW", market, cost_case, oos_dates=dates)
    decision_set = set(decision_indices(len(dates)))
    pending: dict[int, SignalRanking] = {}

    for i, day in enumerate(dates):
        terminal = i == len(dates) - 1
        _mark(run, bars, day)
        pre_trade_nav = _nav(run.cash, run.positions)
        if not math.isfinite(pre_trade_nav) or pre_trade_nav <= 0.0:
            raise ImplementationError(f"invalid_pre_trade_nav:{day}")
        fill_start = len(run.fills)

        # Due block exits precede same-close replacement entries. At the
        # segment terminal, all remaining positions are liquidated and no
        # pending/new entry is executed.
        if terminal and run.positions:
            for symbol in sorted(list(run.positions)):
                _sell(run, day, symbol, bars.get(symbol, {}).get(day), sell_fee, "terminal_liquidation")
        elif i in pending:
            for symbol in sorted(list(run.positions)):
                _sell(run, day, symbol, bars.get(symbol, {}).get(day), sell_fee, "scheduled_block_exit")
            ranking = pending.pop(i)
            batch_nav = _nav(run.cash, run.positions)
            gross_per_slot = (batch_nav / slots) / (1.0 + buy_fee)
            filled: list[str] = []
            for rank, candidate in enumerate(ranking.ranked, start=1):
                if len(filled) >= slots:
                    break
                close = bars.get(candidate.symbol, {}).get(day)
                if _buy(run, day, candidate.symbol, close, gross_per_slot,
                        buy_fee, "low_skew_rank", rank):
                    filled.append(candidate.symbol)
            run.filled_by_execution[day] = tuple(filled)
            run.unused_slots_by_execution[day] = slots - len(filled)

        _append_day(run, day, pre_trade_nav, fill_start)

        if i in decision_set:
            run.windows += 1
            run.decision_dates.append(day)
            if terminal:
                run.skipped_decisions.append((day, "no_next_in_segment"))
                run.skipped_windows += 1
                continue
            if i + 1 == len(dates) - 1:
                run.skipped_decisions.append((day, "execution_is_final"))
                run.skipped_windows += 1
                continue
            # Ranks are fixed at signal close and stored for the following
            # union-date execution; they are never recomputed at execution.
            signal = signal_ranking(bars, day, symbols)
            pending[i + 1] = signal
            names = tuple(item.symbol for item in signal.ranked)
            run.rank_by_decision[day] = names
            run.eligible_by_decision[day] = signal.eligible_count
            run.selected_by_decision[day] = names[:slots]

    if pending:
        raise ImplementationError("pending_orders_after_segment")
    return run


def simulate_benchmark(
    raw_bars: Mapping[str, Mapping[date | str | datetime, object]],
    market: str,
    cost_case: str,
    start: date,
    end: date,
) -> Run:
    """Same-cohort fixed-gross B&H comparator, including delayed starts."""
    bars = normalize_bars(raw_bars)
    symbols = sorted(bars)
    dates = _oos_dates(union_calendar(bars), start, end)
    buy_fee, sell_fee = cost_rates(market, cost_case)
    gross_per_name = (1.0 / len(symbols)) / (1.0 + buy_fee)
    run = Run("BH", market, cost_case, oos_dates=dates)
    unbought = set(symbols)

    for i, day in enumerate(dates):
        terminal = i == len(dates) - 1
        _mark(run, bars, day)
        pre_trade_nav = _nav(run.cash, run.positions)
        fill_start = len(run.fills)
        if not terminal:
            for symbol in sorted(list(unbought)):
                close = bars.get(symbol, {}).get(day)
                if close is not None and _buy(
                    run, day, symbol, close, gross_per_name, buy_fee,
                    "benchmark_initial_or_delayed",
                ):
                    unbought.remove(symbol)
        if terminal:
            run.unbought_terminal = tuple(sorted(unbought))
            for symbol in sorted(list(run.positions)):
                _sell(run, day, symbol, bars.get(symbol, {}).get(day), sell_fee, "terminal_liquidation")
        _append_day(run, day, pre_trade_nav, fill_start)
    return run


def summarize(run: Run) -> dict[str, float | int | None]:
    """Summarize a caller-provided run; synthetic tests only, no market output."""
    if not run.nav:
        raise ValueError("empty_nav")
    path = [1.0] + [value for _, value in run.nav]
    if any(not math.isfinite(value) or value <= 0.0 for value in path):
        raise ValueError("nonpositive_nav")
    returns = [path[i] / path[i - 1] - 1.0 for i in range(1, len(path))]
    stdev = statistics.pstdev(returns) if returns else 0.0
    sharpe = statistics.mean(returns) / stdev * math.sqrt(252.0) if stdev > 0.0 else None
    peak = 1.0
    mdd = 0.0
    for value in path:
        peak = max(peak, value)
        mdd = max(mdd, 1.0 - value / peak)
    first_day, last_day = run.nav[0][0], run.nav[-1][0]
    elapsed = (last_day - (first_day - timedelta(days=1))).days
    cagr = path[-1] ** (365.2425 / elapsed) - 1.0 if elapsed > 0 else None
    average_cash_share = sum(
        cash / nav for (_, cash), (_, nav) in zip(run.cash_path, run.nav)
    ) / len(run.nav)
    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "mdd": mdd,
        "terminal_nav": path[-1],
        "turnover": sum(value for _, value in run.daily_turnover),
        "total_costs": sum(fill.fee for fill in run.fills),
        "fill_count": len(run.fills),
        "average_cash_share": average_cash_share,
    }


def load_close_csv(_path: Path) -> dict[date, float]:
    """Permanently disabled in runner B; this function performs no file access."""
    raise PermissionError("market data access disabled in synthetic-only runner B")


def run_market_performance(_root: Path) -> None:
    """Permanently disabled in runner B; no file read or market calculation."""
    raise PermissionError("performance execution disabled in synthetic-only runner B")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gen17 synthetic-only runner B")
    parser.add_argument("--market-performance", action="store_true")
    args = parser.parse_args(argv)
    if args.market_performance:
        raise PermissionError("performance execution disabled in synthetic-only runner B")
    print("Synthetic-only Gen17 runner B; market files and performance were not accessed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
