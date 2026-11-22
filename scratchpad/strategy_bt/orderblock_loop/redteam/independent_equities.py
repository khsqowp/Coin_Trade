"""Literal independent C1/C2 rules from PREREG.md; weekly signals map to daily bars."""
from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import MutableMapping, Sequence


@dataclass(frozen=True)
class Bar:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class Signal:
    index: int
    kind: str
    low: float
    high: float
    target: float = 0.0


@dataclass(frozen=True)
class Fill:
    entry_index: int
    exit_index: int
    entry: float
    exit: float
    net_return: float
    reason: str


def atr(bars: Sequence[Bar], end: int, period: int = 14) -> float:
    if period <= 0 or end < 0 or end >= len(bars) or end + 1 < period:
        return float("nan")
    values = []
    for i in range(end - period + 1, end + 1):
        if i == 0:
            values.append(bars[i].high - bars[i].low)
        else:
            prev = bars[i - 1].close
            values.append(max(bars[i].high - bars[i].low,
                              abs(bars[i].high - prev), abs(bars[i].low - prev)))
    return sum(values) / period


def c1_signals(bars: Sequence[Bar], lookback: int = 10) -> list[Signal]:
    if lookback <= 0:
        raise ValueError("lookback must be positive")
    out: list[Signal] = []
    for i in range(lookback, len(bars)):
        if bars[i].close <= max(b.high for b in bars[i - lookback:i]):
            continue
        candidates = [j for j in range(max(0, i - lookback), i)
                      if bars[j].close < bars[j].open]
        if candidates:
            ob = bars[candidates[-1]]
            out.append(Signal(i, "c1", ob.low, ob.high))
    return out


def c2_signals(bars: Sequence[Bar], gap_atr: float = 1.0) -> list[Signal]:
    out = []
    for i in range(1, len(bars)):
        a = atr(bars, i - 1)
        if not isnan(a) and bars[i].open - bars[i - 1].close <= -gap_atr * a and bars[i].close > bars[i].open:
            out.append(Signal(i, "c2", bars[i].low, bars[i].high, bars[i - 1].close))
    return out


def simulate_c1(bars: Sequence[Bar], setup: Signal, *, holding: int = 20,
                reward: float = 2.0, fee: float = .0005, slip: float = .0005,
                tax: float = 0.0, audit: MutableMapping[str, int] | None = None) -> Fill | None:
    def count(name: str) -> None:
        if audit is not None:
            audit[name] = audit.get(name, 0) + 1

    count("signals")
    for i in range(setup.index + 1, min(len(bars), setup.index + holding + 1)):
        b = bars[i]
        overlap = b.low <= setup.high and b.high >= setup.low
        if overlap:
            if b.close <= setup.high or b.close <= setup.low:
                count("first_revisit_failed")
                return None
            entry_i = i + 1
            if entry_i >= len(bars):
                count("right_censored")
                return None
            if bars[entry_i].open <= setup.low:
                count("entry_skipped")
                return None
            entry = bars[entry_i].open
            risk = entry - setup.low
            if risk <= 0:
                count("entry_skipped")
                return None
            target = entry + reward * risk
            for j in range(entry_i, min(len(bars), entry_i + holding)):
                x = bars[j]
                if x.low <= setup.low:
                    raw = x.open if x.open < setup.low else setup.low
                    exit_i, reason = j, "stop"
                    break
                if x.high >= target:
                    raw, exit_i, reason = target, j, "target"
                    break
            else:
                exit_i = entry_i + holding
                if exit_i >= len(bars):
                    count("incomplete_time_exit")
                    return None
                raw, reason = bars[exit_i].open, "time"
            # US/KR cost arguments are explicit; exact net-cost math is unresolved in PREREG.
            net = (raw - entry) / entry - (2 * (fee + slip) + tax)
            count("completed")
            return Fill(entry_i, exit_i, entry, raw, net, reason)
    if len(bars) <= setup.index + holding:
        count("right_censored")
    else:
        count("expired")
    return None


def simulate_c2(bars: Sequence[Bar], setup: Signal, *, holding: int = 5,
                fee: float = .0005, slip: float = .0005, tax: float = 0.0,
                audit: MutableMapping[str, int] | None = None) -> Fill | None:
    if audit is not None:
        audit["signals"] = audit.get("signals", 0) + 1
    entry_i = setup.index + 1
    if entry_i >= len(bars):
        if audit is not None: audit["right_censored"] = audit.get("right_censored", 0) + 1
        return None
    entry = bars[entry_i].open
    stop, target = setup.low, setup.target
    if entry >= target or entry <= stop:
        if audit is not None: audit["entry_skipped"] = audit.get("entry_skipped", 0) + 1
        return None
    last_hold = entry_i + holding - 1
    for j in range(entry_i, min(len(bars), entry_i + holding)):
        b = bars[j]
        if b.low <= stop:
            raw, exit_i, reason = (b.open if b.open < stop else stop), j, "stop"
            break
        if b.high >= target:
            raw, exit_i, reason = target, j, "target"
            break
    else:
        # Last holding-day close, then next actual trading-day open.
        exit_i = last_hold + 1
        if last_hold >= len(bars) or exit_i >= len(bars):
            if audit is not None: audit["incomplete_time_exit"] = audit.get("incomplete_time_exit", 0) + 1
            return None
        raw, reason = bars[exit_i].open, "time"
    net = (raw - entry) / entry - (2 * (fee + slip) + tax)
    if audit is not None: audit["completed"] = audit.get("completed", 0) + 1
    return Fill(entry_i, exit_i, entry, raw, net, reason)


def weekly_signals_to_daily(weekly: Sequence[Signal], week_end_timestamps: Sequence[int],
                            daily: Sequence[Bar]) -> list[Signal]:
    """Map completed weekly signal index to its first later daily bar index."""
    if len(weekly) != len(week_end_timestamps):
        raise ValueError("weekly signals and timestamps differ in length")
    converted = []
    for signal, end_ts in zip(weekly, week_end_timestamps):
        daily_i = next((i for i, bar in enumerate(daily) if bar.timestamp > end_ts), None)
        if daily_i is not None:
            converted.append(Signal(daily_i, signal.kind, signal.low, signal.high, signal.target))
    return converted
