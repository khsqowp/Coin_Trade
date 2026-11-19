"""Independent scalar oracle for synthetic crypto OHLC execution-path tests.

This module intentionally imports no production trading or path-resolution code.
It is a method-validation reference, not a trading signal or market-data tool.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import math


MINUTE_MS = 60_000


@dataclass(frozen=True)
class ScalarBars:
    open_ms: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]


def aggregate_minutes(times, opens, highs, lows, closes, tf_minutes):
    """Build complete UTC-aligned native OHLC buckets without production helpers."""
    if not isinstance(tf_minutes, int) or isinstance(tf_minutes, bool) or tf_minutes < 1:
        raise ValueError("tf_minutes must be a positive integer")
    arrays = (times, opens, highs, lows, closes)
    if any(len(x) != len(times) for x in arrays[1:]):
        raise ValueError("minute arrays must align")
    width = tf_minutes * MINUTE_MS
    by_time = {}
    for i, raw in enumerate(times):
        stamp = int(raw)
        if stamp % MINUTE_MS:
            raise ValueError("minute timestamps must align to UTC minute boundaries")
        if stamp in by_time:
            raise ValueError("duplicate minute timestamp")
        by_time[stamp] = i
    bucket_starts = sorted({stamp // width * width for stamp in by_time})
    result = [[], [], [], [], []]
    for start in bucket_starts:
        indices = [by_time.get(start + offset * MINUTE_MS) for offset in range(tf_minutes)]
        if any(index is None for index in indices):
            continue
        oi = indices[0]
        ci = indices[-1]
        result[0].append(start)
        result[1].append(float(opens[oi]))
        result[2].append(max(float(highs[i]) for i in indices))
        result[3].append(min(float(lows[i]) for i in indices))
        result[4].append(float(closes[ci]))
    return ScalarBars(*result)


def _unresolved(entry_ms=None, entry_price=None):
    return {"status": "unresolved", "target_first": None,
            "entry_ms": entry_ms, "entry_price": entry_price,
            "exit_ms": None, "exit_price": None, "trade_net_r": None}


def _resolve_scalar(opens, highs, lows, closes, side, stop, target):
    for i in range(len(opens)):
        o, h, l, c = map(float, (opens[i], highs[i], lows[i], closes[i]))
        if (not all(map(math.isfinite, (o, h, l, c))) or h < max(o, c)
                or l > min(o, c) or h < l):
            return "unresolved", None, i
        if side == "long":
            if o <= stop:
                return "stop", o, i
            if o >= target:
                return "target", target, i
            if l <= stop:
                return "stop", stop, i
            if h >= target:
                return "target", target, i
        else:
            if o >= stop:
                return "stop", o, i
            if o <= target:
                return "target", target, i
            if h >= stop:
                return "stop", stop, i
            if l <= target:
                return "target", target, i
    return "timeout", float(closes[-1]), len(closes) - 1


def evaluate_scalar(*, minute_open_ms, minute_opens, minute_highs, minute_lows,
                    minute_closes, native_bars, native_tf_minutes, signal_index,
                    side, pivot_stop, atr_at_signal, stop_buffer_atr, target_r,
                    horizon_bars, entry_mode, fee_per_side=0.0005,
                    slippage_per_side=0.00025):
    """Resolve one signal using independent scalar loops and explicit arithmetic."""
    if side not in ("long", "short") or entry_mode not in ("next_open", "stop_entry"):
        raise ValueError("invalid side or entry_mode")
    if horizon_bars not in (10, 20) or target_r not in (1.0, 1.5, 2.0, 3.0):
        raise ValueError("horizon or target outside frozen grid")
    if not isinstance(native_tf_minutes, int) or isinstance(native_tf_minutes, bool) or native_tf_minutes < 1:
        raise ValueError("native_tf_minutes must be a positive integer")
    if signal_index < 0 or signal_index >= len(native_bars.open_ms):
        raise ValueError("signal_index outside native bars")
    arrays = (minute_open_ms, minute_opens, minute_highs, minute_lows, minute_closes)
    if any(len(x) != len(minute_open_ms) for x in arrays[1:]):
        raise ValueError("minute path arrays must align")
    times = [int(x) for x in minute_open_ms]
    tf_ms = native_tf_minutes * MINUTE_MS
    signal_open = int(native_bars.open_ms[signal_index])
    signal_end = signal_open + tf_ms
    trigger = (float(native_bars.high[signal_index]) if side == "long"
               else float(native_bars.low[signal_index]))
    atr = float(atr_at_signal)
    close = float(native_bars.close[signal_index])
    stop = (float(pivot_stop) - float(stop_buffer_atr) * atr if side == "long"
            else float(pivot_stop) + float(stop_buffer_atr) * atr)
    if (not all(map(math.isfinite, (trigger, stop, close, atr))) or atr <= 0
            or stop <= 0 or close <= 0
            or (side == "long" and stop >= close)
            or (side == "short" and stop <= close)):
        return {"status": "invalid", "target_first": False, "entry_ms": None,
                "entry_price": None, "exit_ms": None, "exit_price": None,
                "trade_net_r": None}

    minute_start = bisect_left(times, signal_end)
    if minute_start >= len(times) or times[minute_start] != signal_end:
        return _unresolved()
    entry_i = signal_index + 1
    if entry_i >= len(native_bars.open_ms):
        return _unresolved()
    if int(native_bars.open_ms[entry_i]) != signal_end:
        return _unresolved()

    entry_ms = None
    entry_price = None
    entry_native_index = entry_i
    if entry_mode == "next_open":
        entry_ms = int(native_bars.open_ms[entry_i])
        entry_price = float(native_bars.open[entry_i])
        minute_start = bisect_left(times, entry_ms)
        if (minute_start >= len(times) or times[minute_start] != entry_ms
                or float(minute_opens[minute_start]) != entry_price):
            return _unresolved(entry_ms, entry_price)
    else:
        for offset in range(3):
            native_i = entry_i + offset
            if native_i >= len(native_bars.open_ms):
                return _unresolved()
            bar_start = int(native_bars.open_ms[native_i])
            first = bisect_left(times, bar_start)
            expected = [bar_start + k * MINUTE_MS for k in range(native_tf_minutes)]
            if first + native_tf_minutes > len(times) or times[first:first + native_tf_minutes] != expected:
                return _unresolved()
            for mi in range(first, first + native_tf_minutes):
                o, h, l = float(minute_opens[mi]), float(minute_highs[mi]), float(minute_lows[mi])
                c = float(minute_closes[mi])
                if (not all(map(math.isfinite, (o, h, l, c))) or h < max(o, c)
                        or l > min(o, c) or h < l):
                    return _unresolved()
                if side == "long":
                    if o >= trigger:
                        entry_ms, entry_price, entry_native_index = times[mi], o, native_i
                        break
                    if o <= stop or l <= stop:
                        return {"status": "no_fill_invalidated", "target_first": False,
                                "entry_ms": None, "entry_price": None, "exit_ms": None,
                                "exit_price": None, "trade_net_r": None}
                    if h >= trigger:
                        entry_ms, entry_price, entry_native_index = times[mi], trigger, native_i
                        break
                else:
                    if o <= trigger:
                        entry_ms, entry_price, entry_native_index = times[mi], o, native_i
                        break
                    if o >= stop or h >= stop:
                        return {"status": "no_fill_invalidated", "target_first": False,
                                "entry_ms": None, "entry_price": None, "exit_ms": None,
                                "exit_price": None, "trade_net_r": None}
                    if l <= trigger:
                        entry_ms, entry_price, entry_native_index = times[mi], trigger, native_i
                        break
            if entry_price is not None:
                minute_start = first
                break
        if entry_price is None:
            return {"status": "expired", "target_first": False, "entry_ms": None,
                    "entry_price": None, "exit_ms": None, "exit_price": None,
                    "trade_net_r": None}

    path_start = int(native_bars.open_ms[entry_native_index])
    if minute_start >= len(times) or times[minute_start] != path_start:
        return _unresolved(entry_ms, entry_price)
    if (side == "long" and stop >= entry_price) or (side == "short" and stop <= entry_price):
        return {"status": "no_fill_invalidated", "target_first": False,
                "entry_ms": None, "entry_price": None, "exit_ms": None,
                "exit_price": None, "trade_net_r": None}
    risk = abs(entry_price - stop)
    target = entry_price + (1 if side == "long" else -1) * risk * target_r
    count = native_tf_minutes * horizon_bars
    path_ix = bisect_left(times, path_start)
    expected = [path_start + k * MINUTE_MS for k in range(count)]
    if path_ix + count > len(times) or times[path_ix:path_ix + count] != expected:
        return _unresolved(entry_ms, entry_price)
    status, exit_price, exit_minute = _resolve_scalar(
        minute_opens[path_ix:path_ix + count], minute_highs[path_ix:path_ix + count],
        minute_lows[path_ix:path_ix + count], minute_closes[path_ix:path_ix + count],
        side, stop, target)
    if status == "unresolved" or exit_price is None:
        return _unresolved(entry_ms, entry_price)
    cost = float(fee_per_side) + float(slippage_per_side)
    if side == "long":
        net_r = (float(exit_price) * (1 - cost) - entry_price * (1 + cost)) / risk
    else:
        net_r = (entry_price * (1 - cost) - float(exit_price) * (1 + cost)) / risk
    return {"status": status, "target_first": status == "target",
            "entry_ms": int(entry_ms), "entry_price": float(entry_price),
            "exit_ms": int(times[path_ix + exit_minute]),
            "exit_price": float(exit_price), "trade_net_r": float(net_r)}
