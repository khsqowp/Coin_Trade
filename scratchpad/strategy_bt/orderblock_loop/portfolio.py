"""Fixed-initial-capital portfolio aggregation with explicit missing-data checks."""

from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Hashable, Mapping, Sequence


def equal_weight_daily_returns(
    universe: Sequence[str],
    pnl_fraction_of_symbol_capital: Mapping[Hashable, Mapping[str, float]],
) -> list[tuple[Hashable, float]]:
    """Aggregate per-symbol PnL fractions over fixed equal initial allocations.

    Each row must explicitly contain every symbol. A zero means no position or
    zero PnL; an absent symbol is treated as missing market data and rejected.
    The returned values are fractions of total fixed initial portfolio capital.
    """
    if not universe or len(set(universe)) != len(universe):
        raise ValueError("universe must contain unique symbols")
    expected = set(universe)
    ordered_dates = sorted(pnl_fraction_of_symbol_capital)
    result = []
    for date in ordered_dates:
        row = pnl_fraction_of_symbol_capital[date]
        if set(row) != expected:
            missing = sorted(expected - set(row))
            extra = sorted(set(row) - expected)
            raise ValueError(f"symbol row mismatch at {date!r}: missing={missing}, extra={extra}")
        if any(not isfinite(value) for value in row.values()):
            raise ValueError(f"non-finite symbol PnL at {date!r}")
        result.append((date, sum(row.values()) / len(universe)))
    return result


def daily_pearson_correlation(
    returns_a: Mapping[Hashable, float], sessions_a: Sequence[Hashable],
    returns_b: Mapping[Hashable, float], sessions_b: Sequence[Hashable],
) -> float | None:
    """Correlate UTC daily portfolio returns with explicit trading calendars.

    Dates when both markets are closed are excluded. A closed-market date is
    zero for that candidate; an omitted return on an open session is an error.
    """
    def utc_day(value: Hashable) -> date:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("correlation timestamps must be timezone-aware UTC")
            return value.astimezone(timezone.utc).date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("correlation string keys must be ISO UTC calendar dates") from exc
            if parsed.isoformat() != value:
                raise ValueError("correlation string keys must be YYYY-MM-DD UTC dates")
            return parsed
        raise ValueError("correlation keys must be UTC dates or aware timestamps")

    def normalize(values: Mapping[Hashable, float], sessions: Sequence[Hashable]):
        normalized_sessions = [utc_day(value) for value in sessions]
        normalized_returns = {utc_day(key): value for key, value in values.items()}
        if len(set(normalized_sessions)) != len(normalized_sessions):
            raise ValueError("duplicate UTC dates after normalization")
        if set(normalized_returns) != set(normalized_sessions):
            raise ValueError("each trading session requires one explicit daily return")
        return set(normalized_sessions), normalized_returns

    session_a, daily_a = normalize(returns_a, sessions_a)
    session_b, daily_b = normalize(returns_b, sessions_b)
    if not session_a or not session_b:
        return None
    if any(not isfinite(value) for value in (*daily_a.values(), *daily_b.values())):
        raise ValueError("daily returns must be finite")
    dates = sorted(session_a | session_b)
    paired = [
        (daily_a.get(date, 0.0), daily_b.get(date, 0.0))
        for date in dates
    ]
    if len(paired) < 2:
        return None
    values_a = [item[0] for item in paired]
    values_b = [item[1] for item in paired]
    mean_a = sum(values_a) / len(values_a)
    mean_b = sum(values_b) / len(values_b)
    centered_a = [value - mean_a for value in values_a]
    centered_b = [value - mean_b for value in values_b]
    sum_sq_a = sum(value * value for value in centered_a)
    sum_sq_b = sum(value * value for value in centered_b)
    if sum_sq_a == 0 or sum_sq_b == 0:
        return None
    covariance = sum(a * b for a, b in zip(centered_a, centered_b))
    return covariance / (sum_sq_a * sum_sq_b) ** 0.5
