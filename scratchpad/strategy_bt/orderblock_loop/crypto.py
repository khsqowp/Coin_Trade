"""Causal crypto order-block definitions and first-retest event simulation.

This module has no data loading or network side effects. Inputs must be ordered,
closed OHLCV bars. A signal can only use information available at its close.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Literal, Mapping, Sequence

Definition = Literal["displacement", "bos_origin", "volume_displacement"]
Direction = Literal["long", "short"]
SUPPORTED_REWARD_R = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0)


@dataclass(frozen=True)
class Bar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    complete: bool = True


@dataclass(frozen=True)
class Zone:
    signal_index: int
    origin_index: int
    direction: Direction
    low: float
    high: float
    atr_at_signal: float


@dataclass(frozen=True)
class Setup:
    zone: Zone
    entry_index: int
    entry_price: float
    stop: float
    target: float


@dataclass(frozen=True)
class FundingEvent:
    timestamp: int
    rate: float
    mark_price: float | None
    coverage_gap: bool = False
    used_candle_close_fallback: bool = False


@dataclass(frozen=True)
class Trade:
    setup: Setup
    exit_index: int
    exit_price: float
    exit_reason: Literal["stop", "target", "time"]
    gross_return: float
    funding_return: float | None
    cost_bps: float
    net_return: float | None
    funding_order_policy: Literal["fail_closed", "adverse_only"] = "fail_closed"
    ambiguous_funding_events: int = 0


def funding_price_available(event: FundingEvent) -> bool:
    """A finite positive observed mark or registered close proxy is usable."""
    return (event.mark_price is not None and isfinite(event.mark_price)
            and event.mark_price > 0)


def _count(audit: dict[str, int] | None, key: str) -> None:
    if audit is not None:
        audit[key] += 1


def _validate(bars: Sequence[Bar]) -> list[int]:
    for bar in bars:
        if not all(isfinite(value) for value in
                   (bar.open, bar.high, bar.low, bar.close, bar.volume)):
            raise ValueError("OHLCV values must be finite")
        if not (bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            raise ValueError("inconsistent OHLC")
        if bar.volume < 0:
            raise ValueError("volume cannot be negative")
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError("bars must be strictly chronological")
    incomplete = [i for i, bar in enumerate(bars) if not bar.complete]
    if incomplete and incomplete != list(range(incomplete[0], len(bars))):
        raise ValueError("incomplete bars may only be a trailing suffix")
    indices = [i for i, bar in enumerate(bars) if bar.complete]
    return indices


def _funding_order(entry_ts: int, exit_ts: int, event_ts: int,
                   exit_reason: str, bar_duration_ms: int) -> tuple[bool, bool]:
    """Return (charge, unknown_order) using exact settlement timestamps."""
    if bar_duration_ms > 0 and event_ts == entry_ts:
        return False, True
    if exit_reason == "time":
        if bar_duration_ms > 0 and event_ts == exit_ts:
            return False, True
        return entry_ts < event_ts <= exit_ts, False
    if exit_ts <= event_ts <= exit_ts + bar_duration_ms:
        return False, True
    return entry_ts < event_ts < exit_ts, False


def _atr(bars: Sequence[Bar], index: int, period: int = 14) -> float | None:
    if index < period - 1:
        return None
    ranges = []
    for i in range(index - period + 1, index + 1):
        previous_close = bars[i - 1].close if i else bars[i].open
        ranges.append(max(bars[i].high - bars[i].low,
                          abs(bars[i].high - previous_close),
                          abs(bars[i].low - previous_close)))
    result = sum(ranges) / period
    return result if result > 0 else None


def _confirmed_pivots(bars: Sequence[Bar], index: int, left: int = 3,
                       right: int = 3) -> tuple[float | None, float | None]:
    """Latest pivots confirmed no later than index; ties are not pivots."""
    highs: list[float] = []
    lows: list[float] = []
    for pivot in range(left, index - right + 1):
        window = bars[pivot - left:pivot + right + 1]
        if all(bars[pivot].high > b.high for j, b in enumerate(window) if j != left):
            highs.append(bars[pivot].high)
        if all(bars[pivot].low < b.low for j, b in enumerate(window) if j != left):
            lows.append(bars[pivot].low)
    return (highs[-1] if highs else None, lows[-1] if lows else None)


def _confirmed_pivot_levels(bars: Sequence[Bar], indices: Sequence[int],
                            left: int = 3, right: int = 3
                            ) -> dict[int, tuple[float | None, float | None]]:
    """Track the latest confirmed pivot in one pass instead of rescanning history."""
    levels: dict[int, tuple[float | None, float | None]] = {}
    latest_high = latest_low = None
    for index in indices:
        pivot = index - right
        if pivot >= left:
            window = bars[pivot - left:pivot + right + 1]
            center = bars[pivot]
            if all(center.high > bar.high for j, bar in enumerate(window) if j != left):
                latest_high = center.high
            if all(center.low < bar.low for j, bar in enumerate(window) if j != left):
                latest_low = center.low
        levels[index] = (latest_high, latest_low)
    return levels


def zones(bars: Sequence[Bar], definition: Definition, *, displacement_atr: float = 1.5,
          volume_multiple: float = 1.5) -> list[Zone]:
    """Return causal OB candidates; callers must apply one-active-zone lifecycle."""
    if definition not in ("displacement", "bos_origin", "volume_displacement"):
        raise ValueError(f"unsupported definition: {definition!r}")
    eligible = _validate(bars)
    pivot_levels = _confirmed_pivot_levels(bars, eligible)
    found: list[Zone] = []
    for i in eligible:
        if i < 20:
            continue
        atr_value = _atr(bars, i)
        if atr_value is None:
            continue
        pivot_high, pivot_low = pivot_levels[i]
        up = pivot_high is not None and bars[i].close > pivot_high
        down = pivot_low is not None and bars[i].close < pivot_low
        if up and down:  # ambiguous external candle
            continue
        if not (up or down):
            continue
        direction: Direction = "long" if up else "short"
        body = abs(bars[i].close - bars[i].open)
        if definition != "bos_origin" and body < displacement_atr * atr_value:
            continue
        if definition != "bos_origin" and (
            (direction == "long" and bars[i].close <= bars[i].open)
            or (direction == "short" and bars[i].close >= bars[i].open)
        ):
            continue
        if definition == "volume_displacement":
            previous_volumes = sorted(bars[j].volume for j in range(i - 20, i))
            median = (previous_volumes[9] + previous_volumes[10]) / 2
            if bars[i].volume < volume_multiple * median:
                continue
        opposite = [j for j in range(max(0, i - 20), i)
                    if (bars[j].close < bars[j].open if direction == "long"
                        else bars[j].close > bars[j].open)]
        if not opposite:
            continue
        origin = opposite[-1]
        found.append(Zone(i, origin, direction, bars[origin].low,
                          bars[origin].high, atr_value))
    return found


def enforce_single_active_zone(bars: Sequence[Bar], candidates: Sequence[Zone], *,
                               deadline: int) -> list[Zone]:
    """Apply one active zone per direction; ignore new same-direction signals.

    An active zone is consumed on the first retest, invalidation, or expiry.
    Invalidation wins over a same-bar retest. New candidates encountered while
    the previous zone remains active are discarded, not queued for later.
    """
    if deadline not in (24, 48):
        raise ValueError("deadline outside preregistered grid")
    eligible = _validate(bars)
    positions = {bar_i: n for n, bar_i in enumerate(eligible)}
    ordered = sorted(candidates, key=lambda zone: zone.signal_index)
    if any(zone.signal_index not in positions for zone in ordered):
        raise ValueError("zone signal must point to a completed bar")
    accepted: list[Zone] = []
    active: dict[Direction, tuple[Zone, int, int]] = {}
    for zone in ordered:
        signal_pos = positions[zone.signal_index]
        current = active.get(zone.direction)
        if current is not None:
            old_zone, old_signal_pos, checked_pos = current
            consumed = False
            for pos in range(checked_pos + 1, signal_pos + 1):
                age = pos - old_signal_pos
                if age > deadline:
                    consumed = True
                    break
                if age < 1:
                    continue
                bar = bars[eligible[pos]]
                invalid = (bar.low <= old_zone.low if zone.direction == "long"
                           else bar.high >= old_zone.high)
                overlap = bar.low <= old_zone.high and bar.high >= old_zone.low
                if invalid or overlap:
                    consumed = True
                    break
            if consumed:
                active.pop(zone.direction, None)
            else:
                active[zone.direction] = (old_zone, old_signal_pos, signal_pos)
                continue
        accepted.append(zone)
        active[zone.direction] = (zone, signal_pos, signal_pos)
    return accepted


def active_zones(bars: Sequence[Bar], definition: Definition, *, deadline: int,
                 displacement_atr: float = 1.5,
                 volume_multiple: float = 1.5) -> list[Zone]:
    """Detect candidates and apply the preregistered active-zone lifecycle."""
    return enforce_single_active_zone(
        bars,
        zones(bars, definition, displacement_atr=displacement_atr,
              volume_multiple=volume_multiple),
        deadline=deadline,
    )


def r4_zones(bars: Sequence[Bar], definition: Definition) -> list[Zone]:
    """Detect the separately preregistered R4 definitions without future bars."""
    if definition not in ("displacement", "bos_origin", "volume_displacement"):
        raise ValueError(f"unsupported R4 definition: {definition!r}")
    eligible = _validate(bars)
    pivots = _confirmed_pivot_levels(bars, eligible)
    found = []
    for i in eligible:
        if i < 20:
            continue
        atr_value = _atr(bars, i)
        if atr_value is None:
            continue
        if definition == "bos_origin":
            pivot_high, pivot_low = pivots[i]
            up = pivot_high is not None and bars[i].close > pivot_high
            down = pivot_low is not None and bars[i].close < pivot_low
            if up == down:
                continue
            direction: Direction = "long" if up else "short"
        else:
            direction = "long" if bars[i].close > bars[i].open else "short"
            if bars[i].close == bars[i].open:
                continue
            if abs(bars[i].close - bars[i].open) < 1.5 * atr_value:
                continue
        if definition == "volume_displacement":
            previous = sorted(bars[j].volume for j in range(i - 20, i))
            median = (previous[9] + previous[10]) / 2
            if bars[i].volume < 1.5 * median:
                continue
        opposite = [j for j in range(i - 20, i)
                    if (bars[j].close < bars[j].open if direction == "long"
                        else bars[j].close > bars[j].open)]
        if opposite:
            origin = opposite[-1]
            found.append(Zone(i, origin, direction, bars[origin].low,
                              bars[origin].high, atr_value))
    return found


def first_retest(bars: Sequence[Bar], zone: Zone, *, deadline: int,
                 reward_r: float, validated: bool = False) -> Setup | None:
    """Enter next open after first overlapping retest, unless invalidated first.

    Deadline is inclusive in bars after registration. An invalidation touch on
    the retest bar wins over entry because intrabar ordering is unknowable.
    """
    if deadline not in (24, 48) or reward_r not in SUPPORTED_REWARD_R:
        raise ValueError("parameters outside preregistered grid")
    eligible = range(len(bars)) if validated else _validate(bars)
    if validated:
        signal_pos = zone.signal_index if 0 <= zone.signal_index < len(bars) else None
        if signal_pos is not None and not bars[signal_pos].complete:
            signal_pos = None
    else:
        positions = {bar_i: n for n, bar_i in enumerate(eligible)}
        signal_pos = positions.get(zone.signal_index)
    if signal_pos is None:
        return None
    stop = (zone.low - 0.1 * zone.atr_at_signal if zone.direction == "long"
            else zone.high + 0.1 * zone.atr_at_signal)
    for pos in range(signal_pos + 1, min(len(eligible), signal_pos + deadline + 1)):
        i = eligible[pos]
        bar = bars[i]
        invalid = (bar.low <= zone.low if zone.direction == "long"
                   else bar.high >= zone.high)
        overlap = bar.low <= zone.high and bar.high >= zone.low
        if invalid:
            return None
        if overlap:
            if pos + 1 >= len(eligible):
                return None
            entry_i = eligible[pos + 1]
            entry = bars[entry_i].open
            beyond_zone = (entry <= zone.low if zone.direction == "long"
                           else entry >= zone.high)
            if beyond_zone:
                return None
            risk = entry - stop if zone.direction == "long" else stop - entry
            if risk <= 0:
                return None
            target = entry + reward_r * risk if zone.direction == "long" else entry - reward_r * risk
            return Setup(zone, entry_i, entry, stop, target)
    return None


def simulate_trade(bars: Sequence[Bar], setup: Setup, *, funding: Mapping[int, FundingEvent],
                   max_holding_bars: int = 48, fee_bps_per_side: float = 4.0,
                   slippage_bps_per_side: float = 2.0,
                   bar_duration_ms: int | None = None,
                   validated: bool = False,
                   funding_order_policy: Literal["fail_closed", "adverse_only"] = "fail_closed") -> Trade | None:
    """Simulate stop/target/time exit and signed funding for a single setup.

    Funding mapping keys are exact UTC settlement timestamps, including events
    inside a candle. An event at the entry timestamp is excluded because the
    position was not held just before settlement. If a stop/target exit occurs
    inside the same candle as a funding event, event order is unknowable and
    the trade is marked unscorable.
    Returns None when a required next-open time exit is outside the supplied
    series; it never fabricates a close fill.
    """
    if max_holding_bars not in (24, 48):
        raise ValueError("holding horizon must be a preregistered 24 or 48 bars")
    if fee_bps_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("costs cannot be negative")
    if bar_duration_ms is not None and bar_duration_ms <= 0:
        raise ValueError("bar_duration_ms must be positive")
    if funding_order_policy not in ("fail_closed", "adverse_only"):
        raise ValueError("unknown funding-order policy")
    if validated:
        eligible = range(len(bars))
        start = (setup.entry_index if 0 <= setup.entry_index < len(bars)
                 and bars[setup.entry_index].complete else None)
    else:
        eligible = _validate(bars)
        positions = {bar_i: n for n, bar_i in enumerate(eligible)}
        start = positions.get(setup.entry_index)
    if start is None or setup.entry_price <= 0:
        return None
    if setup.entry_price != bars[setup.entry_index].open:
        raise ValueError("setup entry price must equal the actual next-bar open")
    stop_gap = setup.entry_price <= setup.stop if setup.zone.direction == "long" else setup.entry_price >= setup.stop
    if stop_gap:
        return None
    horizon_last = start + max_holding_bars - 1
    last = min(len(eligible) - 1, horizon_last)
    exit_index = -1
    exit_price = 0.0
    reason: Literal["stop", "target", "time"] = "time"
    for pos in range(start, last + 1):
        i = eligible[pos]
        bar = bars[i]
        long = setup.zone.direction == "long"
        stop_gap = bar.open <= setup.stop if long else bar.open >= setup.stop
        stop_hit = bar.low <= setup.stop if long else bar.high >= setup.stop
        target_hit = bar.high >= setup.target if long else bar.low <= setup.target
        if stop_gap:
            exit_index, exit_price, reason = i, bar.open, "stop"
            break
        if stop_hit:  # conservative when both barriers fall within one OHLC bar
            exit_index, exit_price, reason = i, setup.stop, "stop"
            break
        if target_hit:
            exit_index, exit_price, reason = i, setup.target, "target"
            break
        if pos == horizon_last:
            next_index = i + 1
            if next_index >= len(bars) or not bars[next_index].complete:
                return None
            exit_index = next_index
            exit_price = bars[exit_index].open
            reason = "time"
        elif pos == last:
            return None
    if exit_index < 0:
        return None
    long_sign = 1 if setup.zone.direction == "long" else -1
    gross = (exit_price / setup.entry_price - 1) * long_sign
    funding_return = 0.0
    funding_covered = True
    ambiguous_funding_events = 0
    entry_timestamp = bars[setup.entry_index].timestamp
    exit_timestamp = bars[exit_index].timestamp
    for timestamp, event in funding.items():
        if timestamp != event.timestamp:
            raise ValueError("funding key must equal its exact settlement timestamp")
        series_end = bars[-1].timestamp + (bar_duration_ms or 0) + 1_000
        if timestamp < bars[0].timestamp or timestamp > series_end:
            raise ValueError("funding event lies outside the simulated candle range")
        should_charge, order_unknown = _funding_order(
            entry_timestamp, exit_timestamp, timestamp, reason, bar_duration_ms or 0)
        if order_unknown:
            if (funding_order_policy == "adverse_only" and not event.coverage_gap
                    and isfinite(event.rate) and -1 < event.rate < 1
                    and funding_price_available(event)):
                ambiguous_funding_events += 1
                if long_sign * event.rate > 0:
                    funding_return -= long_sign * event.rate * event.mark_price / setup.entry_price
            else:
                funding_covered = False
            continue
        if should_charge:
            if event.coverage_gap:
                funding_covered = False
                continue
            if not isfinite(event.rate) or not (-1 < event.rate < 1):
                raise ValueError("invalid funding event")
            if event.mark_price is None:
                funding_covered = False
                continue
            if not isfinite(event.mark_price) or event.mark_price <= 0:
                raise ValueError("invalid funding event")
            funding_return -= long_sign * event.rate * event.mark_price / setup.entry_price
    side_cost = (fee_bps_per_side + slippage_bps_per_side) / 10_000
    # Match PREREG's fixed-capital arithmetic: subtract two one-way costs
    # from price return, then add signed funding cash flow.
    net = gross + funding_return - 2 * side_cost if funding_covered else None
    cost_bps = 2 * side_cost * 10_000
    return Trade(setup, exit_index, exit_price, reason, gross,
                 funding_return if funding_covered else None, cost_bps, net,
                 funding_order_policy, ambiguous_funding_events)


def trade_daily_pnl(bars: Sequence[Bar], trade: Trade, *,
                    funding: Mapping[int, FundingEvent],
                    bar_duration_ms: int) -> dict[int, float] | None:
    """Return UTC-day fixed-capital mark-to-market contributions for a scored trade."""
    if trade.net_return is None or bar_duration_ms <= 0:
        return None
    entry_i, exit_i = trade.setup.entry_index, trade.exit_index
    entry = trade.setup.entry_price
    sign = 1 if trade.setup.zone.direction == "long" else -1
    daily: dict[int, float] = {}
    previous_mark = entry
    side_cost = trade.cost_bps / 20_000
    for index in range(entry_i, exit_i + 1):
        bar = bars[index]
        mark = trade.exit_price if index == exit_i else bar.close
        day = bar.timestamp // 86_400_000
        daily[day] = daily.get(day, 0.0) + sign * (mark - previous_mark) / entry
        previous_mark = mark
    entry_day = bars[entry_i].timestamp // 86_400_000
    exit_day = bars[exit_i].timestamp // 86_400_000
    daily[entry_day] = daily.get(entry_day, 0.0) - side_cost
    daily[exit_day] = daily.get(exit_day, 0.0) - side_cost
    for timestamp, event in funding.items():
        exit_ts = bars[exit_i].timestamp
        should_charge, order_unknown = _funding_order(
            bars[entry_i].timestamp, exit_ts, timestamp,
            trade.exit_reason, bar_duration_ms)
        if order_unknown:
            if (trade.funding_order_policy != "adverse_only" or event.coverage_gap
                    or not isfinite(event.rate) or not (-1 < event.rate < 1)
                    or not funding_price_available(event)):
                return None
            if sign * event.rate > 0:
                daily[timestamp // 86_400_000] = (
                    daily.get(timestamp // 86_400_000, 0.0)
                    - sign * event.rate * event.mark_price / entry
                )
            continue
        if should_charge:
            if (event.coverage_gap or event.mark_price is None
                    or not isfinite(event.mark_price) or event.mark_price <= 0):
                return None
            daily[timestamp // 86_400_000] = (
                daily.get(timestamp // 86_400_000, 0.0)
                - sign * event.rate * event.mark_price / entry
            )
    if not isclose(sum(daily.values()), trade.net_return, rel_tol=1e-9, abs_tol=1e-10):
        raise ValueError("daily mark-to-market contributions do not reconcile to trade net return")
    return daily


def simulate_orderblock(bars: Sequence[Bar], definition: Definition, direction: Direction, *,
                        deadline: int, reward_r: float,
                        funding: Mapping[int, FundingEvent],
                        fee_bps_per_side: float = 4.0,
                        slippage_bps_per_side: float = 2.0,
                        bar_duration_ms: int | None = None,
                        r4_definition: bool = False,
                        funding_order_policy: Literal["fail_closed", "adverse_only"] = "fail_closed",
                        candidate_zones: Sequence[Zone] | None = None,
                        audit: dict[str, int] | None = None) -> list[Trade]:
    """Run one fixed OB candidate end-to-end without overlapping positions."""
    if deadline not in (24, 48) or reward_r not in SUPPORTED_REWARD_R:
        raise ValueError("parameters outside preregistered grid")
    if bar_duration_ms is not None and bar_duration_ms <= 0:
        raise ValueError("bar_duration_ms must be positive")
    eligible = _validate(bars)
    detected = candidate_zones
    if detected is None:
        detected = (r4_zones(bars, definition) if r4_definition
                    else zones(bars, definition))
    candidates = [zone for zone in detected if zone.direction == direction]
    by_index: dict[int, Zone] = {}
    for zone in candidates:
        if zone.signal_index in by_index:
            raise ValueError("multiple same-direction zones on one signal bar")
        by_index[zone.signal_index] = zone
    if audit is not None:
        audit.clear()
        audit.update({key: 0 for key in (
            "signals", "ignored_while_busy", "invalidated", "expired",
            "right_censored", "entries_skipped", "time_exit_censored",
            "completed_trades",
        )})
        audit["signals"] = len(candidates)

    trades: list[Trade] = []
    active: Zone | None = None
    positions = {bar_index: pos for pos, bar_index in enumerate(eligible)}
    pos = 0
    while pos < len(eligible):
        i = eligible[pos]
        candidate = by_index.get(i)
        if active is not None:
            age = i - active.signal_index
            if candidate is not None and candidate.signal_index != active.signal_index:
                _count(audit, "ignored_while_busy")
            if age > deadline:
                _count(audit, "expired")
                active = None
            elif age > 0:
                invalid = (bars[i].low <= active.low if direction == "long"
                           else bars[i].high >= active.high)
                if invalid:
                    _count(audit, "invalidated")
                    active = None
                    pos += 1
                    continue
                overlap = bars[i].low <= active.high and bars[i].high >= active.low
                if overlap:
                    entry_index = i + 1
                    if (entry_index >= len(bars) or not bars[entry_index].complete):
                        _count(audit, "right_censored")
                        active = None
                        break
                    entry_price = bars[entry_index].open
                    beyond_zone = (entry_price <= active.low if direction == "long"
                                   else entry_price >= active.high)
                    stop = (active.low - 0.1 * active.atr_at_signal if direction == "long"
                            else active.high + 0.1 * active.atr_at_signal)
                    risk = entry_price - stop if direction == "long" else stop - entry_price
                    if beyond_zone or risk <= 0:
                        _count(audit, "entries_skipped")
                        active = None
                        pos += 1
                        continue
                    target = (entry_price + reward_r * risk if direction == "long"
                              else entry_price - reward_r * risk)
                    setup = Setup(active, entry_index, entry_price, stop, target)
                    trade = simulate_trade(
                        bars, setup, funding=funding,
                        fee_bps_per_side=fee_bps_per_side,
                        slippage_bps_per_side=slippage_bps_per_side,
                        bar_duration_ms=bar_duration_ms,
                        funding_order_policy=funding_order_policy,
                    )
                    if trade is None:
                        _count(audit, "time_exit_censored")
                        active = None
                        break
                    trades.append(trade)
                    _count(audit, "completed_trades")
                    active = None
                    # Ignore all signal bars while the position is open, then
                    # process a possible signal confirmed at the exit candle close.
                    for skipped_index in by_index:
                        if entry_index <= skipped_index < trade.exit_index:
                            _count(audit, "ignored_while_busy")
                    pos = positions[trade.exit_index]
                    continue
                else:
                    pos += 1
                    continue
            else:
                pos += 1
                continue

        if active is None and candidate is not None:
            active = candidate
        pos += 1
    if active is not None and eligible and eligible[-1] - active.signal_index <= deadline:
        _count(audit, "right_censored")
    return trades
