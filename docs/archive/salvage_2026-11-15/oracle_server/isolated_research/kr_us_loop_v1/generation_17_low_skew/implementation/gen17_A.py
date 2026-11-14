"""Independent synthetic-first implementation of Gen17's low-skew hypothesis.

Only in-memory fixtures are enabled. The market loader is deliberately closed
and raises before touching the filesystem unless a future owner-reviewed change
explicitly opens the gate.
"""
from __future__ import annotations

import csv
import hashlib
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PREREG_SHA256 = "ecd75ddbae7b59813bbc4837aba2f58d139adb8ec117c89087d07e7334e6cc58"
INPUT_MANIFEST_SHA256 = "395e3acc608493164700e2fcdfebebe9bca541bfa6e952a3cebdb15ab81a85b4"
PERFORMANCE_GATE_OPEN = False
TOL = 1e-10
OOS_START = date(2023, 1, 1)
REBALANCE_INTERVAL = 21
RETURN_WINDOW = 63

COHORTS = {
    "US": ("AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"),
    "KR": ("000270", "000660", "000810", "005380", "005490", "005930", "006400", "009150", "012330", "017670", "028260", "032830", "034730", "035420", "055550", "068270", "086790", "105560", "316140", "373220", "402340"),
}
SLOTS = {"US": 2, "KR": 5}
COSTS = {
    "US": {"base": (0.0008, 0.0008), "stress": (0.0036, 0.0036)},
    "KR": {"base": (0.00065, 0.00245), "stress": (0.00115, 0.00295)},
}


class DataBlocked(RuntimeError):
    """The frozen in-memory data or required observation is invalid."""


@dataclass(frozen=True)
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
    rank: int | None
    reason: str
    nav_batch: float | None = None


@dataclass
class Position:
    ticker: str
    shares: float
    last_close: float
    entry_day: date
    exit_index: int
    rank: int | None = None


@dataclass(frozen=True)
class SignalRecord:
    decision_index: int
    decision_date: date
    execution_date: date | None
    ranking: tuple[tuple[str, float], ...]
    eligible_count: int
    overlap: Mapping[str, float | None]
    skipped_terminal: bool = False


@dataclass(frozen=True)
class DailyRecord:
    day: date
    nav: float
    cash: float
    holdings: Mapping[str, float]
    held_value: float
    stale_marks: tuple[str, ...]
    event: tuple[str, ...]
    pre_trade_nav: float
    gross_buys: float
    gross_sells: float
    total_fees: float
    turnover: float
    reconciliation_error: float


@dataclass
class SimulationResult:
    candidate: str
    market: str
    cost_case: str
    oos_dates: list[date] = field(default_factory=list)
    signals: list[SignalRecord] = field(default_factory=list)
    ledger: list[Fill] = field(default_factory=list)
    daily: list[DailyRecord] = field(default_factory=list)
    canceled_entries: int = 0
    skipped_slots: int = 0
    skipped_terminal_decisions: int = 0
    skipped_terminal_orders: int = 0
    terminal_cash: float = 1.0


def parse_utc_date(value: str) -> date:
    """Parse ISO-8601 with explicit offset and convert to UTC date."""
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DataBlocked(f"invalid_timestamp:{value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataBlocked(f"timezone_offset_required:{value!r}")
    return parsed.astimezone(timezone.utc).date()


def _normalize_day(raw_day: date | str) -> date:
    if isinstance(raw_day, datetime):
        if raw_day.tzinfo is None or raw_day.utcoffset() is None:
            raise DataBlocked(f"timezone_offset_required:{raw_day!r}")
        return raw_day.astimezone(timezone.utc).date()
    if isinstance(raw_day, date):
        return raw_day
    if isinstance(raw_day, str):
        return parse_utc_date(raw_day)
    raise DataBlocked(f"invalid_date:{raw_day!r}")


def normalize_series(
    raw: Mapping[str, Mapping[date | str, Any]], market: str
) -> dict[str, dict[date, float]]:
    """Validate exact frozen cohort, close values, duplicates, and date order."""
    if market not in COHORTS:
        raise ValueError(f"unknown market: {market}")
    expected = set(COHORTS[market])
    if set(raw) != expected:
        raise DataBlocked(f"cohort_mismatch:{market}:missing={sorted(expected-set(raw))}:extra={sorted(set(raw)-expected)}")
    normalized: dict[str, dict[date, float]] = {}
    for ticker, rows in raw.items():
        out: dict[date, float] = {}
        prior: date | None = None
        for raw_day, raw_close in rows.items():
            day = _normalize_day(raw_day)
            if day in out:
                raise DataBlocked(f"duplicate_utc_date:{ticker}:{day}")
            if prior is not None and day <= prior:
                raise DataBlocked(f"nonincreasing_date:{ticker}:{day}")
            try:
                close = float(raw_close)
            except (TypeError, ValueError) as exc:
                raise DataBlocked(f"invalid_close:{ticker}:{day}") from exc
            if not math.isfinite(close) or close <= 0.0:
                raise DataBlocked(f"invalid_close:{ticker}:{day}")
            out[day] = close
            prior = day
        normalized[ticker] = out
    return normalized


def union_calendar(series: Mapping[str, Mapping[date, float]]) -> list[date]:
    dates = sorted({day for rows in series.values() for day in rows})
    if not dates:
        raise DataBlocked("empty_union_calendar")
    return dates


def fisher_pearson_skew(returns: Sequence[float]) -> float | None:
    """Bias-corrected Fisher-Pearson G1 as frozen in the preregistration."""
    n = len(returns)
    if n != RETURN_WINDOW:
        return None
    if any(not math.isfinite(float(value)) for value in returns):
        return None
    mean = sum(returns) / n
    sample_sd = math.sqrt(sum((value - mean) ** 2 for value in returns) / (n - 1))
    if sample_sd == 0.0:
        return None
    score = n / ((n - 1) * (n - 2)) * sum(((value - mean) / sample_sd) ** 3 for value in returns)
    return score if math.isfinite(score) else None


def skew_for_ticker(
    prices: Mapping[date | str, float], calendar: Sequence[date], decision_index: int
) -> float | None:
    """Score a ticker only when all 64 ending union dates have actual closes."""
    if decision_index < RETURN_WINDOW or decision_index >= len(calendar):
        return None
    window_dates = calendar[decision_index - RETURN_WINDOW : decision_index + 1]
    closes: list[float] = []
    for day in window_dates:
        raw_close = prices.get(day)
        if raw_close is None:
            raw_close = prices.get(day.isoformat())
        if raw_close is None:
            return None
        close = float(raw_close)
        if not math.isfinite(close) or close <= 0.0:
            raise DataBlocked(f"invalid_signal_close:{day}")
        closes.append(close)
    returns = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    return fisher_pearson_skew(returns)


def rank_scores(scores: Mapping[str, float]) -> list[tuple[str, float]]:
    """Rank ascending score then ticker-string ascending for exact ties."""
    return sorted(scores.items(), key=lambda item: (item[1], item[0]))


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    first = 0
    while first < len(indexed):
        end = first + 1
        while end < len(indexed) and indexed[end][1] == indexed[first][1]:
            end += 1
        average_rank = ((first + 1) + end) / 2.0
        for k in range(first, end):
            ranks[indexed[k][0]] = average_rank
        first = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    delta_left = [x - mean_left for x in left]
    delta_right = [x - mean_right for x in right]
    sum_left = sum(x * x for x in delta_left)
    sum_right = sum(x * x for x in delta_right)
    if sum_left == 0.0 or sum_right == 0.0:
        return None
    return sum(x * y for x, y in zip(delta_left, delta_right)) / math.sqrt(sum_left * sum_right)


def overlap_diagnostics(
    scores: Mapping[str, float], returns_by_ticker: Mapping[str, Sequence[float]]
) -> dict[str, float | None]:
    """Descriptive Spearman diagnostics on one identical eligible cross-section."""
    names = sorted(set(scores) & set(returns_by_ticker))
    if len(names) < 4:
        return {"realized_volatility": None, "cumulative_return": None, "maximum_session_return": None}
    score_values = [float(scores[name]) for name in names]
    comparators: dict[str, list[float]] = {
        "realized_volatility": [],
        "cumulative_return": [],
        "maximum_session_return": [],
    }
    for name in names:
        values = [float(x) for x in returns_by_ticker[name]]
        if not values or any(not math.isfinite(x) for x in values):
            raise DataBlocked(f"invalid_overlap_returns:{name}")
        if len({len(returns_by_ticker[name]) for name in names}) != 1:
            raise DataBlocked("overlap_return_length_mismatch")
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        comparators["realized_volatility"].append(math.sqrt(variance))
        comparators["cumulative_return"].append(math.prod(1.0 + x for x in values) - 1.0)
        comparators["maximum_session_return"].append(max(values))
    score_ranks = _average_ranks(score_values)
    result: dict[str, float | None] = {}
    if len(set(score_values)) == 1:
        return {key: None for key in comparators}
    for key, values in comparators.items():
        if len(set(values)) == 1:
            result[key] = None
            continue
        result[key] = _pearson(score_ranks, _average_ranks(values))
    return result


def summarize_overlap(signals: Sequence[SignalRecord]) -> dict[str, dict[str, float | int | None]]:
    """Aggregate descriptive date-level overlap only for caller-supplied records."""
    keys = ("realized_volatility", "cumulative_return", "maximum_session_return")
    summary: dict[str, dict[str, float | int | None]] = {}
    for key in keys:
        values = [abs(float(signal.overlap[key])) for signal in signals if signal.overlap.get(key) is not None]
        summary[key] = {
            "median_abs_rho": statistics.median(values) if values else None,
            "valid_date_denominator": len(values),
        }
    return summary


def _decision_returns(
    prices: Mapping[str, Mapping[date, float]], ticker: str,
    calendar: Sequence[date], decision_index: int,
) -> list[float] | None:
    if decision_index < RETURN_WINDOW:
        return None
    dates = calendar[decision_index - RETURN_WINDOW : decision_index + 1]
    closes: list[float] = []
    for day in dates:
        close = prices[ticker].get(day)
        if close is None:
            return None
        closes.append(close)
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def build_signal(
    series: Mapping[str, Mapping[date, float]], market: str,
    oos_dates: Sequence[date], decision_index: int,
) -> SignalRecord:
    """Build one decision from only the 64 closes ending on its date."""
    if not 0 <= decision_index < len(oos_dates):
        raise IndexError("decision index outside OOS calendar")
    all_dates = union_calendar(series)
    date_to_index = {day: i for i, day in enumerate(all_dates)}
    day = oos_dates[decision_index]
    global_index = date_to_index[day]
    scores: dict[str, float] = {}
    windows: dict[str, list[float]] = {}
    for ticker in COHORTS[market]:
        returns = _decision_returns(series, ticker, all_dates, global_index)
        if returns is None:
            continue
        score = fisher_pearson_skew(returns)
        if score is not None:
            scores[ticker] = score
            windows[ticker] = returns
    ranking = tuple(rank_scores(scores))
    diagnostics = overlap_diagnostics(scores, windows) if scores else {
        "realized_volatility": None,
        "cumulative_return": None,
        "maximum_session_return": None,
    }
    terminal = decision_index == len(oos_dates) - 1
    execution_date = oos_dates[decision_index + 1] if decision_index + 1 < len(oos_dates) else None
    return SignalRecord(
        decision_index=decision_index,
        decision_date=day,
        execution_date=execution_date,
        ranking=ranking,
        eligible_count=len(ranking),
        overlap=diagnostics,
        skipped_terminal=terminal,
    )


def _fee(market: str, cost_case: str, side: str) -> float:
    try:
        return COSTS[market][cost_case][0 if side == "buy" else 1]
    except KeyError as exc:
        raise ValueError(f"unknown cost schedule: {market}/{cost_case}/{side}") from exc


def _nav(cash: float, positions: Mapping[str, Position]) -> float:
    nav = cash + sum(position.shares * position.last_close for position in positions.values())
    if not math.isfinite(nav) or nav <= 0.0:
        raise DataBlocked("nonpositive_nav")
    return nav


def _mark_positions(
    positions: Mapping[str, Position], prices: Mapping[str, Mapping[date, float]], day: date,
) -> tuple[float, tuple[str, ...]]:
    stale: list[str] = []
    value = 0.0
    for ticker, position in positions.items():
        close = prices[ticker].get(day)
        if close is None:
            stale.append(ticker)
        else:
            position.last_close = close
        value += position.shares * position.last_close
    return value, tuple(sorted(stale))


def _buy(
    result: SimulationResult, ticker: str, day: date, close: float, rank: int,
    cash: float, nav_batch: float, market: str, cost_case: str,
) -> tuple[float, float, float]:
    budget = nav_batch / SLOTS[market]
    buy_fee = _fee(market, cost_case, "buy")
    gross = budget / (1.0 + buy_fee)
    fee = gross * buy_fee
    spend = gross + fee
    if cash + TOL < spend:
        raise DataBlocked(f"insufficient_cash_for_fixed_slot:{ticker}:{day}")
    shares = gross / close
    cash_before = cash
    cash -= spend
    if cash < -TOL:
        raise DataBlocked(f"negative_cash:{ticker}:{day}")
    cash = max(0.0, cash)
    result.ledger.append(Fill(day, ticker, "buy", close, shares, gross, fee, cash_before, cash, rank, "low_skew_rank", nav_batch))
    return cash, gross, fee


def _sell(
    result: SimulationResult, ticker: str, day: date, positions: dict[str, Position],
    cash: float, market: str, cost_case: str, reason: str,
) -> tuple[float, float, float]:
    close = positions[ticker].last_close
    if ticker not in positions or ticker not in result._prices or day not in result._prices[ticker]:
        raise DataBlocked(f"required_exit_terminal_close_missing:{ticker}:{day}")
    position = positions.pop(ticker)
    close = result._prices[ticker][day]
    gross = position.shares * close
    fee = gross * _fee(market, cost_case, "sell")
    cash_before = cash
    cash += gross - fee
    result.ledger.append(Fill(day, ticker, "sell", close, position.shares, gross, fee, cash_before, cash, position.rank, reason))
    return cash, gross, fee


def simulate_candidate(
    raw_series: Mapping[str, Mapping[date | str, Any]], market: str, cost_case: str,
) -> SimulationResult:
    """Run one OOS candidate path on supplied synthetic/in-memory closes only."""
    if market not in COHORTS or cost_case not in {"base", "stress"}:
        raise ValueError("invalid market or cost case")
    series = normalize_series(raw_series, market)
    all_dates = union_calendar(series)
    oos_dates = [day for day in all_dates if day >= OOS_START]
    if not oos_dates:
        raise DataBlocked("empty_oos_calendar")
    result = SimulationResult("LOW_SKEW_63", market, cost_case, oos_dates=oos_dates)
    # Private in-memory reference used only to enforce actual-close exits.
    result._prices = series
    full_index = {day: index for index, day in enumerate(all_dates)}
    oos_index = {day: index for index, day in enumerate(oos_dates)}
    decision_indices = list(range(0, len(oos_dates), REBALANCE_INTERVAL))
    order_by_execution: dict[int, SignalRecord] = {}
    signal_by_index: dict[int, SignalRecord] = {}
    positions: dict[str, Position] = {}
    cash = 1.0
    ledger_cash = 1.0
    ledger_shares: dict[str, float] = {}
    previous_nav = 1.0

    for decision_index in decision_indices:
        record = build_signal(series, market, oos_dates, decision_index)
        signal_by_index[decision_index] = record
        result.signals.append(record)
        if record.execution_date is None:
            result.skipped_terminal_decisions += 1
        else:
            order_by_execution[oos_index[record.execution_date]] = record

    for oos_i, day in enumerate(oos_dates):
        holdings_before = set(positions)
        held_value_before, stale_before = _mark_positions(positions, series, day)
        pre_trade_nav = _nav(cash, positions)
        gross_buys = gross_sells = total_fees = 0.0
        event_labels: list[str] = []
        record = order_by_execution.get(oos_i)
        is_terminal = oos_i == len(oos_dates) - 1

        # Each scheduled execution closes the previous holding block before the
        # replacement batch. A terminal execution closes the block but never
        # opens the new one.
        if record is not None or is_terminal:
            for ticker in sorted(list(positions)):
                if day not in series[ticker]:
                    raise DataBlocked(f"required_scheduled_or_terminal_close_missing:{ticker}:{day}")
                reason = "terminal_liquidation" if is_terminal else "scheduled_block_exit"
                cash, gross, fee = _sell(result, ticker, day, positions, cash, market, cost_case, reason)
                gross_sells += gross
                total_fees += fee
                event_labels.append(f"sell:{ticker}:{reason}")

        if record is not None and not is_terminal:
            nav_batch = _nav(cash, positions)
            filled = 0
            next_signal = next((idx for idx in decision_indices if idx > record.decision_index), None)
            if next_signal is None or next_signal + 1 >= len(oos_dates):
                scheduled_exit_index = len(oos_dates) - 1
            else:
                scheduled_exit_index = next_signal + 1
            for rank, (ticker, _score) in enumerate(record.ranking, start=1):
                if filled >= SLOTS[market]:
                    break
                close = series[ticker].get(day)
                if close is None:
                    result.canceled_entries += 1
                    event_labels.append(f"skip_missing_entry:{ticker}")
                    continue
                before_count = len(result.ledger)
                cash, gross, fee = _buy(result, ticker, day, close, rank, cash, nav_batch, market, cost_case)
                fill = result.ledger[-1]
                positions[ticker] = Position(ticker, fill.shares, close, day, scheduled_exit_index, rank)
                gross_buys += gross
                total_fees += fee
                filled += 1
                event_labels.append(f"buy:{ticker}:rank{rank}")
            result.skipped_slots += max(0, SLOTS[market] - filled)
        elif record is not None and is_terminal:
            result.skipped_terminal_orders += 1
            result.skipped_slots += SLOTS[market]
            event_labels.append("skip_terminal_execution_batch")

        # Enforce any lot's scheduled exit even if its corresponding next order
        # was empty; terminal liquidation takes precedence at the segment end.
        due = [ticker for ticker, position in positions.items() if position.exit_index <= oos_i]
        for ticker in sorted(due):
            if day not in series[ticker]:
                raise DataBlocked(f"required_scheduled_exit_close_missing:{ticker}:{day}")
            cash, gross, fee = _sell(result, ticker, day, positions, cash, market, cost_case, "scheduled_holding_exit")
            gross_sells += gross
            total_fees += fee
            event_labels.append(f"sell:{ticker}:scheduled_holding_exit")

        held_value, stale_after = _mark_positions(positions, series, day)
        nav = _nav(cash, positions)
        day_fills = [fill for fill in result.ledger if fill.day == day]
        for fill in day_fills:
            if abs(fill.cash_before - ledger_cash) > TOL:
                raise DataBlocked(f"ledger_cash_before_mismatch:{day}:{fill.ticker}")
            if fill.side == "buy":
                ledger_cash -= fill.gross + fill.fee
                ledger_shares[fill.ticker] = ledger_shares.get(fill.ticker, 0.0) + fill.shares
            else:
                ledger_cash += fill.gross - fill.fee
                remaining = ledger_shares.get(fill.ticker, 0.0) - fill.shares
                if remaining < -TOL:
                    raise DataBlocked(f"ledger_oversold:{day}:{fill.ticker}")
                if remaining <= TOL:
                    ledger_shares.pop(fill.ticker, None)
                else:
                    ledger_shares[fill.ticker] = remaining
            if abs(fill.cash_after - ledger_cash) > TOL:
                raise DataBlocked(f"ledger_cash_after_mismatch:{day}:{fill.ticker}")
        cash_residual = abs(cash - ledger_cash)
        names = set(positions) | set(ledger_shares)
        shares_residual = max((abs(positions.get(name, Position(name, 0.0, 0.0, day, oos_i)).shares - ledger_shares.get(name, 0.0)) for name in names), default=0.0)
        ledger_nav = ledger_cash + sum(ledger_shares[name] * positions[name].last_close for name in positions)
        reconciliation_error = max(cash_residual, shares_residual, abs(nav - ledger_nav))
        if reconciliation_error > TOL:
            raise DataBlocked(f"ledger_nav_reconciliation:{day}:{reconciliation_error}")
        turnover = (gross_buys + gross_sells) / pre_trade_nav
        result.daily.append(DailyRecord(
            day=day,
            nav=nav,
            cash=cash,
            holdings={ticker: position.shares for ticker, position in positions.items()},
            held_value=held_value,
            stale_marks=tuple(sorted(set(stale_before) | set(stale_after))),
            event=tuple(event_labels),
            pre_trade_nav=pre_trade_nav,
            gross_buys=gross_buys,
            gross_sells=gross_sells,
            total_fees=total_fees,
            turnover=turnover,
            reconciliation_error=reconciliation_error,
        ))
        previous_nav = nav

    if positions:
        raise DataBlocked("open_terminal_positions")
    if abs(previous_nav - cash) > TOL:
        raise DataBlocked("terminal_nav_cash_mismatch")
    result.terminal_cash = cash
    return result


def simulate_benchmark(
    raw_series: Mapping[str, Mapping[date | str, Any]], market: str, cost_case: str,
) -> SimulationResult:
    """Same-cohort fixed-gross buy-and-hold; no market I/O is performed."""
    if market not in COHORTS or cost_case not in {"base", "stress"}:
        raise ValueError("invalid market or cost case")
    series = normalize_series(raw_series, market)
    dates = [day for day in union_calendar(series) if day >= OOS_START]
    if not dates:
        raise DataBlocked("empty_oos_calendar")
    result = SimulationResult("BH", market, cost_case, oos_dates=dates)
    result._prices = series
    positions: dict[str, Position] = {}
    attempted: set[str] = set()
    cash = 1.0
    ledger_cash = 1.0
    ledger_shares: dict[str, float] = {}
    gross_each = 1.0 / (len(COHORTS[market]) * (1.0 + _fee(market, cost_case, "buy")))
    all_in_budget = gross_each * (1.0 + _fee(market, cost_case, "buy"))
    for idx, day in enumerate(dates):
        held_before, stale = _mark_positions(positions, series, day)
        pre_trade_nav = _nav(cash, positions)
        terminal = idx == len(dates) - 1
        gross_buys = gross_sells = fees = 0.0
        event: list[str] = []
        if not terminal:
            for ticker in COHORTS[market]:
                if ticker in attempted:
                    continue
                close = series[ticker].get(day)
                if close is None:
                    continue
                if cash + TOL < all_in_budget:
                    raise DataBlocked(f"benchmark_budget_unfunded:{ticker}:{day}")
                fee = gross_each * _fee(market, cost_case, "buy")
                before = cash
                cash -= all_in_budget
                shares = gross_each / close
                positions[ticker] = Position(ticker, shares, close, day, len(dates) - 1)
                attempted.add(ticker)
                result.ledger.append(Fill(day, ticker, "buy", close, shares, gross_each, fee, before, cash, None, "benchmark_delayed_or_initial"))
                gross_buys += gross_each
                fees += fee
                event.append(f"buy:{ticker}")
        if terminal:
            for ticker in sorted(list(positions)):
                if day not in series[ticker]:
                    raise DataBlocked(f"benchmark_terminal_close_missing:{ticker}:{day}")
                close = series[ticker][day]
                position = positions.pop(ticker)
                gross = position.shares * close
                fee = gross * _fee(market, cost_case, "sell")
                before = cash
                cash += gross - fee
                result.ledger.append(Fill(day, ticker, "sell", close, position.shares, gross, fee, before, cash, None, "benchmark_terminal_liquidation"))
                gross_sells += gross
                fees += fee
                event.append(f"sell:{ticker}:terminal")
        held_value, stale_after = _mark_positions(positions, series, day)
        nav = _nav(cash, positions)
        day_fills = [fill for fill in result.ledger if fill.day == day]
        for fill in day_fills:
            if abs(fill.cash_before - ledger_cash) > TOL:
                raise DataBlocked(f"benchmark_ledger_cash_before_mismatch:{day}:{fill.ticker}")
            if fill.side == "buy":
                ledger_cash -= fill.gross + fill.fee
                ledger_shares[fill.ticker] = ledger_shares.get(fill.ticker, 0.0) + fill.shares
            else:
                ledger_cash += fill.gross - fill.fee
                remaining = ledger_shares.get(fill.ticker, 0.0) - fill.shares
                if remaining < -TOL:
                    raise DataBlocked(f"benchmark_ledger_oversold:{day}:{fill.ticker}")
                ledger_shares.pop(fill.ticker, None)
            if abs(fill.cash_after - ledger_cash) > TOL:
                raise DataBlocked(f"benchmark_ledger_cash_after_mismatch:{day}:{fill.ticker}")
        shares_error = max(
            (
                abs(
                    positions.get(name, Position(name, 0.0, 0.0, day, idx)).shares
                    - ledger_shares.get(name, 0.0)
                )
                for name in set(positions) | set(ledger_shares)
            ),
            default=0.0,
        )
        reconciliation_error = max(abs(cash - ledger_cash), shares_error, abs(nav - (ledger_cash + sum(ledger_shares[name] * positions[name].last_close for name in positions))))
        if reconciliation_error > TOL:
            raise DataBlocked(f"benchmark_ledger_nav_reconciliation:{day}:{reconciliation_error}")
        result.daily.append(DailyRecord(
            day, nav, cash, {ticker: position.shares for ticker, position in positions.items()},
            held_value, tuple(sorted(set(stale) | set(stale_after))), tuple(event),
            pre_trade_nav, gross_buys, gross_sells, fees,
            (gross_buys + gross_sells) / pre_trade_nav, reconciliation_error,
        ))
    if positions or abs(result.daily[-1].nav - cash) > TOL:
        raise DataBlocked("benchmark_terminal_reconciliation")
    result.terminal_cash = cash
    return result


def manifest_digest(files: Mapping[str, bytes]) -> str:
    """Compute frozen canonical manifest from caller-provided bytes only."""
    payload = b"".join(
        relative_path.encode("utf-8") + b"\t" + hashlib.sha256(content).hexdigest().encode("ascii") + b"\n"
        for relative_path, content in sorted(files.items(), key=lambda item: item[0].encode("utf-8"))
    )
    return hashlib.sha256(payload).hexdigest()


def load_market_data(root: Path, market: str) -> dict[str, dict[date, float]]:
    """Market loader refuses before Path access; synthetic-only gate is closed."""
    if not PERFORMANCE_GATE_OPEN:
        raise DataBlocked("PERFORMANCE_GATE_CLOSED: no market cache access is authorized")
    # Keep all market file reads strictly after the gate check.
    cache = root / ".kis-cache"
    loaded: dict[str, dict[date, float]] = {}
    manifest_files: dict[str, bytes] = {}
    for data_market in ("US", "KR"):
        for ticker in COHORTS[data_market]:
            path = cache / f"{data_market}_{ticker}.csv"
            raw = path.read_bytes()
            relative = f".kis-cache/{path.name}"
            manifest_files[relative] = raw
            if data_market != market:
                continue
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or not {"timestamp", "Close"}.issubset(reader.fieldnames):
                    raise DataBlocked(f"schema_mismatch:{path.name}")
                rows: dict[date, float] = {}
                prior: date | None = None
                for row in reader:
                    day = parse_utc_date(row["timestamp"])
                    if prior is not None and day <= prior:
                        raise DataBlocked(f"nonincreasing_or_duplicate_date:{ticker}:{day}")
                    close = float(row["Close"])
                    if not math.isfinite(close) or close <= 0:
                        raise DataBlocked(f"invalid_close:{ticker}:{day}")
                    rows[day] = close
                    prior = day
            loaded[ticker] = rows
    if manifest_digest(manifest_files) != INPUT_MANIFEST_SHA256:
        raise DataBlocked("input_manifest_mismatch")
    return normalize_series(loaded, market)


def run_performance(root: Path, market: str, cost_case: str) -> tuple[SimulationResult, SimulationResult]:
    """Unavailable market-performance entry point; refuses before any I/O."""
    if not PERFORMANCE_GATE_OPEN:
        raise DataBlocked("PERFORMANCE_GATE_CLOSED: synthetic-only work is authorized")
    series = load_market_data(root, market)
    return simulate_candidate(series, market, cost_case), simulate_benchmark(series, market, cost_case)

