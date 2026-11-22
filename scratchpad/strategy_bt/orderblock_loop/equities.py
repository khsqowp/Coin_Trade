"""Pure daily/weekly C1/C2 stock signals and deterministic trade simulation.

Input bars must already be formed and chronologically ordered.  No data access,
resampling, portfolio sizing, or external side effects are performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, MutableMapping, Sequence

Timeframe = Literal["daily", "weekly"]
Market = Literal["US", "KR"]


@dataclass(frozen=True)
class Bar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    complete: bool = True


@dataclass(frozen=True)
class Costs:
    commission_bps_per_side: float
    slippage_bps_per_side: float
    sell_tax_bps: float = 0.0


@dataclass(frozen=True)
class Trade:
    strategy: Literal["C1", "C2", "C3", "C4"]
    signal_index: int
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    exit_reason: Literal["stop", "target", "time"]
    gross_return: float
    cost_bps: float
    net_return: float


AUDIT_KEYS = (
    "signals", "invalidated", "retest_failed", "expired", "right_censored",
    "entries_skipped", "time_exit_censored", "completed_trades",
    "ignored_while_busy",
)


def _reset_audit(audit: MutableMapping[str, int] | None, signals: int) -> None:
    if audit is not None:
        audit.clear()
        audit.update({key: 0 for key in AUDIT_KEYS})
        audit["signals"] = signals


def _count(audit: MutableMapping[str, int] | None, key: str) -> None:
    if audit is not None:
        audit[key] += 1


def preregistered_costs(market: Market) -> Costs:
    """Exact per-side costs in PREREG.md v0.4, expressed in basis points."""
    if market == "US":
        return Costs(commission_bps_per_side=5.0, slippage_bps_per_side=5.0)
    if market == "KR":
        return Costs(
            commission_bps_per_side=1.5,
            slippage_bps_per_side=5.0,
            sell_tax_bps=18.0,
        )
    raise ValueError(f"unsupported market: {market!r}")


def _eligible(bars: Sequence[Bar], timeframe: Timeframe) -> list[int]:
    if timeframe not in ("daily", "weekly"):
        raise ValueError(f"unsupported timeframe: {timeframe!r}")
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError("bars must be strictly chronological")
    incomplete = [i for i, bar in enumerate(bars) if not bar.complete]
    if incomplete and incomplete != list(range(incomplete[0], len(bars))):
        raise ValueError("incomplete bars may only be a trailing suffix")
    indices = [i for i, bar in enumerate(bars) if bar.complete]
    return indices


def _validate(bars: Sequence[Bar]) -> None:
    for bar in bars:
        if not all(isfinite(value) for value in (bar.open, bar.high, bar.low, bar.close)):
            raise ValueError("OHLC values must be finite")
        if not (bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            raise ValueError("bar OHLC values are inconsistent")


def atr(bars: Sequence[Bar], end_index: int, period: int = 14) -> float | None:
    """Simple mean true range ending at end_index; all included bars are prior/current completed bars."""
    if period <= 0 or end_index + 1 < period:
        return None
    start = end_index - period + 1
    ranges = []
    for i in range(start, end_index + 1):
        previous_close = bars[i - 1].close if i > 0 else bars[i].open
        ranges.append(max(bars[i].high - bars[i].low,
                          abs(bars[i].high - previous_close),
                          abs(bars[i].low - previous_close)))
    return sum(ranges) / period


def c1_signals(bars: Sequence[Bar], timeframe: Timeframe = "daily", *,
               lookback: int | None = None) -> list[tuple[int, float, float]]:
    """Return (signal index, OB low, OB high) for C1, using completed bars only."""
    _validate(bars)
    eligible = _eligible(bars, timeframe)
    position = {bar_index: n for n, bar_index in enumerate(eligible)}
    signals = []
    for i in eligible:
        n = position[i]
        if n < 10:
            continue
        for window in ((lookback,) if lookback is not None else (10, 20)):
            if window not in (10, 20):
                raise ValueError("C1 lookback must be 10 or 20")
            if n < window:
                continue
            prior = eligible[n - window:n]
            if bars[i].close <= max(bars[j].high for j in prior):
                continue
            # PREREG: search at most L completed bars backward from t-1.
            candidates = [j for j in eligible[max(0, n - window):n]
                          if bars[j].close < bars[j].open]
            if candidates:
                ob = candidates[-1]
                signals.append((i, bars[ob].low, bars[ob].high))
                break
    return signals


def c2_signals(bars: Sequence[Bar], timeframe: Timeframe = "daily", *,
               gap_atr: float = 1.0) -> list[tuple[int, float, float]]:
    """Return (signal index, prior close target, signal low stop) for C2."""
    if timeframe != "daily":
        raise ValueError("C2 is preregistered for daily bars only")
    _validate(bars)
    eligible = _eligible(bars, timeframe)
    signals = []
    for i in eligible:
        if i == 0 or not bars[i - 1].complete:
            continue
        value = atr(bars, i - 1, 14)
        if value is not None and bars[i].open - bars[i - 1].close <= -gap_atr * value and bars[i].close > bars[i].open:
            signals.append((i, bars[i - 1].close, bars[i].low))
    return signals


def _trade(strategy: Literal["C1", "C2"], signal_i: int, entry_i: int,
           exit_i: int, entry: float, exit_: float, reason: Literal["stop", "target", "time"],
           costs: Costs) -> Trade:
    gross = exit_ / entry - 1.0
    entry_cost = (costs.commission_bps_per_side + costs.slippage_bps_per_side) / 10_000
    exit_cost = (costs.commission_bps_per_side + costs.slippage_bps_per_side + costs.sell_tax_bps) / 10_000
    total_bps = (entry_cost + exit_cost) * 10_000
    net = gross - total_bps / 10_000
    return Trade(strategy, signal_i, entry_i, exit_i, entry, exit_, reason, gross, total_bps, net)


def simulate_c1(bars: Sequence[Bar], *, timeframe: Timeframe = "daily", lookback: int = 10,
                retest_bars: int = 10, reward_r: int = 2, holding_bars: int = 20,
                market: Market = "US", costs: Costs | None = None,
                execution_bars: Sequence[Bar] | None = None,
                audit: MutableMapping[str, int] | None = None) -> list[Trade]:
    """Simulate one non-overlapping long per C1 setup; only preregistered grid values allowed."""
    if lookback not in (10, 20) or retest_bars not in (10, 20) or reward_r not in (2, 3) or holding_bars not in (20, 40):
        raise ValueError("C1 parameters must be from the preregistered grid")
    costs = costs or preregistered_costs(market)
    _validate(bars)
    if timeframe == "weekly":
        if execution_bars is None:
            raise ValueError("weekly C1 requires daily execution_bars for next-trading-day fills and OHLC exits")
        _validate(execution_bars)
        weekly = _eligible(bars, "weekly")
        daily = _eligible(execution_bars, "daily")
        signals = {i: (lo, hi) for i, lo, hi in c1_signals(bars, "weekly", lookback=lookback)}
        _reset_audit(audit, len(signals))
        weekly_position = {i: n for n, i in enumerate(weekly)}
        trades: list[Trade] = []
        busy_until = -1
        for signal_i in weekly:
            if signal_i not in signals or signal_i <= busy_until:
                if signal_i in signals:
                    _count(audit, "ignored_while_busy")
                continue
            lo, hi = signals[signal_i]
            start = weekly_position[signal_i] + 1
            stop_scan = min(len(weekly), start + retest_bars)
            touch_pos = None
            invalid_pos = None
            for p in range(start, stop_scan):
                bar = bars[weekly[p]]
                if bar.close <= lo:
                    invalid_pos = p
                    break
                if bar.low <= hi and bar.high >= lo:
                    touch_pos = p
                    break
            if touch_pos is None:
                if invalid_pos is not None:
                    busy_until = weekly[invalid_pos]
                    _count(audit, "invalidated")
                elif stop_scan > start:
                    busy_until = weekly[stop_scan - 1]
                    _count(audit, "right_censored" if stop_scan - start < retest_bars else "expired")
                else:
                    # The signal is the final completed weekly bar; its retest
                    # window has no observable follow-up bars at the cutoff.
                    _count(audit, "right_censored")
                continue
            retest_i = weekly[touch_pos]
            if bars[retest_i].close <= hi:
                busy_until = retest_i
                _count(audit, "invalidated" if bars[retest_i].close <= lo else "retest_failed")
                continue
            entry_pos = next((p for p, i in enumerate(daily)
                              if execution_bars[i].timestamp > bars[retest_i].timestamp), None)
            if entry_pos is None:
                _count(audit, "right_censored")
                continue
            entry_i = daily[entry_pos]
            entry = execution_bars[entry_i].open
            risk = entry - lo
            if entry <= lo or risk <= 0:
                busy_until = retest_i
                _count(audit, "entries_skipped")
                continue
            stop, target = lo, entry + reward_r * risk
            horizon_complete = touch_pos + holding_bars < len(weekly)
            deadline_pos = min(len(weekly) - 1, touch_pos + holding_bars)
            deadline = bars[weekly[deadline_pos]].timestamp
            daily_until = [p for p in range(entry_pos, len(daily))
                           if execution_bars[daily[p]].timestamp <= deadline]
            if not daily_until:
                continue
            last_pos = daily_until[-1]
            exit_i, exit_price, reason = daily[last_pos], execution_bars[daily[last_pos]].close, "time"
            for p in daily_until:
                i = daily[p]
                bar = execution_bars[i]
                if bar.open <= stop:
                    exit_i, exit_price, reason = i, bar.open, "stop"
                    break
                if bar.low <= stop:
                    exit_i, exit_price, reason = i, stop, "stop"
                    break
                if bar.high >= target:
                    exit_i, exit_price, reason = i, target, "target"
                    break
            else:
                next_pos = last_pos + 1
                if not horizon_complete or next_pos >= len(daily):
                    _count(audit, "time_exit_censored")
                    continue
                exit_i = daily[next_pos]
                exit_price = execution_bars[exit_i].open
            trades.append(_trade("C1", signal_i, entry_i, exit_i, entry, exit_price, reason, costs))
            _count(audit, "completed_trades")
            completed_before_exit = [w for w in weekly
                                     if bars[w].timestamp < execution_bars[exit_i].timestamp]
            busy_until = completed_before_exit[-1] if completed_before_exit else -1
        return trades
    eligible = _eligible(bars, timeframe)
    signals = c1_signals(bars, timeframe, lookback=lookback)
    _reset_audit(audit, len(signals))
    sig_by_i = {i: (lo, hi) for i, lo, hi in signals}
    result: list[Trade] = []
    visited_signals: set[int] = set()
    cursor = 0
    while cursor < len(eligible):
        signal_i = eligible[cursor]
        if signal_i not in sig_by_i:
            cursor += 1
            continue
        visited_signals.add(signal_i)
        lo, hi = sig_by_i[signal_i]
        after = cursor + 1
        end = min(len(eligible), after + retest_bars)
        touch_pos = None
        invalid_pos = None
        for p in range(after, end):
            bar = bars[eligible[p]]
            if bar.close <= lo:
                invalid_pos = p
                break
            if bar.low <= hi and bar.high >= lo:
                touch_pos = p
                break
        if touch_pos is None:
            _count(audit, "invalidated" if invalid_pos is not None else
                   "right_censored" if end - after < retest_bars else "expired")
            cursor = invalid_pos + 1 if invalid_pos is not None else end
            continue
        retest_i = eligible[touch_pos]
        # Treat the first contact as the preregistered retest; a failed close consumes this OB.
        if bars[retest_i].close <= hi or touch_pos + 1 >= len(eligible):
            if bars[retest_i].close <= hi:
                _count(audit, "invalidated" if bars[retest_i].close <= lo else "retest_failed")
            else:
                _count(audit, "right_censored")
            cursor = touch_pos + 1
            continue
        entry_i = eligible[touch_pos + 1]
        entry = bars[entry_i].open
        risk = entry - lo
        if entry <= lo or risk <= 0:
            _count(audit, "entries_skipped")
            cursor = touch_pos + 2
            continue
        stop, target = lo, entry + reward_r * risk
        last_pos = min(len(eligible) - 1, touch_pos + holding_bars)
        exit_i = entry_i
        exit_price = entry
        reason: Literal["stop", "target", "time"] = "time"
        for p in range(touch_pos + 1, last_pos + 1):
            i = eligible[p]
            bar = bars[i]
            if bar.open <= stop:
                exit_i, exit_price, reason = i, bar.open, "stop"
                break
            stop_hit, target_hit = bar.low <= stop, bar.high >= target
            if stop_hit:  # same-bar ambiguity is resolved stop first
                exit_i, exit_price, reason = i, stop, "stop"
                break
            if target_hit:
                exit_i, exit_price, reason = i, target, "target"
                break
            if p == last_pos:
                next_pos = p + 1
                if next_pos < len(eligible):
                    exit_i = eligible[next_pos]
                    exit_price = bars[exit_i].open
                    reason = "time"
                else:
                    reason = "time"
                    exit_i = i
                    exit_price = bar.close
        if reason == "time" and exit_i == eligible[-1] and last_pos == len(eligible) - 1:
            # No next open exists to implement the preregistered time exit.
            _count(audit, "time_exit_censored")
            cursor = len(eligible)
            continue
        result.append(_trade("C1", signal_i, entry_i, exit_i, entry, exit_price, reason, costs))
        _count(audit, "completed_trades")
        cursor = (eligible.index(exit_i, cursor + 1)
                  if exit_i in eligible[cursor + 1:] else cursor + 1)
    if audit is not None:
        audit["ignored_while_busy"] += len(signals) - len(visited_signals)
    return result


def simulate_c2(bars: Sequence[Bar], *, gap_atr: float = 1.0, holding_bars: int = 5,
                market: Market = "US", costs: Costs | None = None,
                audit: MutableMapping[str, int] | None = None) -> list[Trade]:
    """Simulate C2 daily gap-reversion longs with impossible-gap/stop entries skipped."""
    if gap_atr not in (1.0, 1.5) or holding_bars not in (5, 10):
        raise ValueError("C2 parameters must be from the preregistered grid")
    costs = costs or preregistered_costs(market)
    _validate(bars)
    eligible = _eligible(bars, "daily")
    positions = {bar_i: n for n, bar_i in enumerate(eligible)}
    signals = c2_signals(bars, gap_atr=gap_atr)
    _reset_audit(audit, len(signals))
    result = []
    blocked_until = -1
    for signal_i, target, stop in signals:
        n = positions[signal_i]
        entry_pos = n + 1
        if entry_pos >= len(eligible):
            _count(audit, "right_censored")
            continue
        if n < blocked_until:
            _count(audit, "ignored_while_busy")
            continue
        entry_i = eligible[entry_pos]
        entry = bars[entry_i].open
        if entry >= target or entry <= stop or target <= stop:
            _count(audit, "entries_skipped")
            continue
        end_pos = min(len(eligible) - 1, entry_pos + holding_bars - 1)
        exit_i, exit_price, reason = entry_i, entry, "time"
        for p in range(entry_pos, end_pos + 1):
            i = eligible[p]
            bar = bars[i]
            if bar.open <= stop:
                exit_i, exit_price, reason = i, bar.open, "stop"
                break
            stop_hit, target_hit = bar.low <= stop, bar.high >= target
            if stop_hit:
                exit_i, exit_price, reason = i, stop, "stop"
                break
            if target_hit:
                exit_i, exit_price, reason = i, target, "target"
                break
            if p == end_pos:
                next_pos = p + 1
                if next_pos < len(eligible):
                    exit_i, exit_price, reason = eligible[next_pos], bars[eligible[next_pos]].open, "time"
                else:
                    exit_i, exit_price, reason = i, bar.close, "time"
        if reason == "time" and exit_i == eligible[-1] and end_pos == len(eligible) - 1:
            _count(audit, "time_exit_censored")
            continue
        result.append(_trade("C2", signal_i, entry_i, exit_i, entry, exit_price, reason, costs))
        _count(audit, "completed_trades")
        blocked_until = positions[exit_i]
    return result


def _simulate_breakout_family(bars: Sequence[Bar], *, family: Literal["C3", "C4"],
                              market: Market, lookback: int = 0, stop_atr: float = 0,
                              distance_atr: float = 0, stop_buffer: float = 0,
                              reward_r: int, holding_bars: int,
                              audit: MutableMapping[str, int] | None) -> list[Trade]:
    _validate(bars)
    eligible = _eligible(bars, "daily")
    allowed = ((lookback in (126, 252) and stop_atr in (2, 3)
                and reward_r in (2, 3) and holding_bars in (20, 40)) if family == "C3"
                else (distance_atr in (0.5, 1.0) and stop_buffer in (0, 0.5)
                      and reward_r in (2, 3) and holding_bars in (10, 20)))
    if not allowed:
        raise ValueError(f"{family} parameters must be from preregistered grid")
    costs = preregistered_costs(market)
    _reset_audit(audit, 0)
    result: list[Trade] = []
    signals = 0
    cursor = 0
    while cursor < len(eligible):
        i = eligible[cursor]
        n = cursor
        value = atr(bars, i, 14)
        signal = False
        stop = 0.0
        if value is not None and n + 1 < len(eligible):
            if family == "C3" and n >= lookback:
                prior = eligible[n - lookback:n]
                signal = bars[i].close > max(bars[j].high for j in prior)
            elif family == "C4" and n >= 200:
                recent = eligible[n - 49:n + 1]
                trend = eligible[n - 199:n + 1]
                sma50 = sum(bars[j].close for j in recent) / 50
                sma200 = sum(bars[j].close for j in trend) / 200
                signal = (bars[i].close > sma200
                          and 0 <= bars[i].close - sma50 <= distance_atr * value
                          and bars[i].close > bars[i].open)
                stop = bars[i].low - stop_buffer * value
        if not signal:
            cursor += 1
            continue
        signals += 1
        entry_i = eligible[n + 1]
        entry = bars[entry_i].open
        if family == "C3":
            stop = entry - stop_atr * value
        risk = entry - stop
        if risk <= 0:
            _count(audit, "entries_skipped")
            cursor += 1
            continue
        target = entry + reward_r * risk
        last = min(len(eligible) - 1, n + holding_bars)
        exit_i, exit_price, reason = entry_i, entry, "time"
        hit = False
        for p in range(n + 1, last + 1):
            j = eligible[p]
            bar = bars[j]
            if bar.open <= stop:
                exit_i, exit_price, reason, hit = j, bar.open, "stop", True
                break
            if bar.low <= stop:
                exit_i, exit_price, reason, hit = j, stop, "stop", True
                break
            if bar.high >= target:
                exit_i, exit_price, reason, hit = j, target, "target", True
                break
        if not hit:
            if last + 1 >= len(eligible):
                _count(audit, "time_exit_censored")
                break
            exit_i = eligible[last + 1]
            exit_price = bars[exit_i].open
        result.append(_trade(family, i, entry_i, exit_i, entry, exit_price,
                             reason, costs))
        _count(audit, "completed_trades")
        cursor = eligible.index(exit_i) + 1
    if audit is not None:
        audit["signals"] = signals
        audit["completed_trades"] = len(result)
    return result


def simulate_c3(bars: Sequence[Bar], *, lookback: int = 126, stop_atr: int = 2,
                reward_r: int = 2, holding_bars: int = 20, market: Market = "US",
                audit: MutableMapping[str, int] | None = None) -> list[Trade]:
    """Simulate preregistered long-only rolling-high breakouts."""
    return _simulate_breakout_family(bars, family="C3", market=market,
                                     lookback=lookback, stop_atr=stop_atr,
                                     reward_r=reward_r, holding_bars=holding_bars,
                                     audit=audit)


def simulate_c4(bars: Sequence[Bar], *, distance_atr: float = 0.5,
                stop_buffer: float = 0, reward_r: int = 2, holding_bars: int = 10,
                market: Market = "US",
                audit: MutableMapping[str, int] | None = None) -> list[Trade]:
    """Simulate preregistered 200-day trend / 50-day pullback longs."""
    return _simulate_breakout_family(bars, family="C4", market=market,
                                     distance_atr=distance_atr,
                                     stop_buffer=stop_buffer, reward_r=reward_r,
                                     holding_bars=holding_bars, audit=audit)
