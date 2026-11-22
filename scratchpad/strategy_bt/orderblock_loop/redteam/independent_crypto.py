"""Frozen independent crypto oracle derived only from PREREG.md.

Pass 2 freeze: this file was completed from the v0.6 wording before inspecting
crypto.py. Cost settlement is deliberately expressed as a simple deduction
because the preregistration does not specify compounding.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Sequence


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
    direction: str
    low: float
    high: float
    atr: float
    kind: str


@dataclass(frozen=True)
class Fill:
    entry_index: int
    exit_index: int
    direction: str
    entry: float
    exit: float
    gross_return: float
    net_return: float
    reason: str
    funding: float = 0.0


def atr(bars: Sequence[Bar], end: int, period: int = 14) -> float:
    """SMA of the last period completed TRs; the first series TR is H-L."""
    if period <= 0 or end < 0 or end >= len(bars) or end + 1 < period:
        return float("nan")
    tr = []
    for i in range(end - period + 1, end + 1):
        if i == 0:
            tr.append(bars[i].high - bars[i].low)
        else:
            prev = bars[i - 1].close
            tr.append(max(bars[i].high - bars[i].low,
                          abs(bars[i].high - prev), abs(bars[i].low - prev)))
    return sum(tr) / period


def _pivots(bars: Sequence[Bar], i: int, side: str) -> list[int]:
    """Return already-confirmed pivots available at signal close i."""
    found = []
    for p in range(3, i - 2):
        window = bars[p - 3:p + 4]
        value = bars[p].high if side == "high" else bars[p].low
        others = [b.high if side == "high" else b.low for j, b in enumerate(window) if j != 3]
        if all(value > x for x in others) if side == "high" else all(value < x for x in others):
            if p + 3 <= i:
                found.append(p)
    return found


def signals(bars: Sequence[Bar], kind: str = "body") -> list[Signal]:
    """Generate independent OB signals using only completed data at each index."""
    if kind not in {"body", "bos", "volume"}:
        raise ValueError("kind must be body, bos, or volume")
    out: list[Signal] = []
    active_until = {"long": -1, "short": -1}
    for i in range(20, len(bars)):
        a = atr(bars, i)
        if isnan(a) or a <= 0:
            continue
        highs, lows = _pivots(bars, i, "high"), _pivots(bars, i, "low")
        last_high = bars[highs[-1]].high if highs else float("inf")
        last_low = bars[lows[-1]].low if lows else float("-inf")
        up, down = bars[i].close > last_high, bars[i].close < last_low
        if up == down:
            continue
        direction = "long" if up else "short"
        if active_until[direction] >= i:
            continue
        b = bars[i]
        if kind != "bos":
            same_way = b.close > b.open if up else b.close < b.open
            if not same_way or abs(b.close - b.open) < 1.5 * a:
                continue
        if kind == "volume":
            prev_vol = sorted(x.volume for x in bars[i - 20:i])
            median = (prev_vol[9] + prev_vol[10]) / 2
            if b.volume < 1.5 * median:
                continue
        opposite = [j for j in range(max(0, i - 20), i)
                    if (bars[j].close < bars[j].open if up else bars[j].close > bars[j].open)]
        if not opposite:
            continue
        ob = bars[opposite[-1]]
        out.append(Signal(i, direction, ob.low, ob.high, a, kind))
        # H is a setup parameter; 48 is the maximum registered revisit horizon.
        active_until[direction] = i + 48
    return out


def trade(bars: Sequence[Bar], setup: Signal, *, revisit: int = 24,
          reward: float = 1.5, holding: int = 48, fee: float = .0004,
          slip: float = .0002,
          funding_events: Sequence[tuple[int, float, float]] = (),
          bar_duration_ms: int | None = None) -> Fill | None:
    """First-revisit entry, OB-boundary invalidation, padded stop, and exits."""
    if revisit <= 0 or holding <= 0:
        raise ValueError("revisit and holding must be positive")
    side = 1 if setup.direction == "long" else -1
    boundary = setup.low if side == 1 else setup.high
    stop = boundary - side * .1 * setup.atr
    entry_i = None
    for i in range(setup.index + 1, min(len(bars), setup.index + revisit + 1)):
        b = bars[i]
        invalid = b.low <= boundary if side == 1 else b.high >= boundary
        if invalid:
            return None
        if b.low <= setup.high and b.high >= setup.low:
            entry_i = i + 1
            break
    if entry_i is None or entry_i >= len(bars):
        return None
    entry_bar = bars[entry_i]
    if entry_bar.open <= boundary if side == 1 else entry_bar.open >= boundary:
        return None
    entry = entry_bar.open
    risk = (entry - stop) * side
    if risk <= 0:
        return None
    target = entry + side * risk * reward
    exit_i = None
    raw = None
    reason = ""
    for i in range(entry_i, min(len(bars), entry_i + holding)):
        b = bars[i]
        stop_hit = b.low <= stop if side == 1 else b.high >= stop
        target_hit = b.high >= target if side == 1 else b.low <= target
        if stop_hit:
            raw = b.open if (b.open < stop if side == 1 else b.open > stop) else stop
            exit_i, reason = i, "stop"
            break
        if target_hit:
            raw, exit_i, reason = target, i, "target"
            break
    if exit_i is None:
        # 48th holding-bar close, then next bar open; incomplete exits are censored.
        exit_i = entry_i + holding
        if exit_i >= len(bars):
            return None
        raw, reason = bars[exit_i].open, "time"
    settled = 0.0
    for ts, rate, mark_price in funding_events:
        exit_ts = bars[exit_i].timestamp
        entry_ts = bars[entry_i].timestamp
        entry_tie = bar_duration_ms is not None and ts == entry_ts
        time_exit_tie = reason == "time" and bar_duration_ms is not None and ts == exit_ts
        event_in_exit_candle = (
            reason != "time" and bar_duration_ms is not None
            and exit_ts <= ts <= exit_ts + bar_duration_ms
        )
        if entry_tie or time_exit_tie or event_in_exit_candle:
            raise ValueError("unscorable: funding order at entry/exit boundary is unknown")
        if entry_ts < ts <= exit_ts:
            settled += -side * rate * mark_price / entry
    gross = side * (raw - entry) / entry
    net = gross - 2 * (fee + slip)
    net += settled
    return Fill(entry_i, exit_i, setup.direction, entry, raw, gross, net, reason, settled)
