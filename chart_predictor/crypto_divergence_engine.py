"""Method-only building blocks for the preregistered divergence backtest.

All inputs are historical public OHLCV. This module performs no network or
exchange-order calls. Missing data is never interpolated or forward-filled.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np

MINUTE_MS = 60_000
FOUR_HOUR_MS = 240 * MINUTE_MS


@dataclass(frozen=True)
class Bars:
    open_ms: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray


def matched_baseline_sides(previous_close, close, *, symbol, timeframe_minutes,
                           anchor_ms, seed=20261117):
    """Momentum and SHA-256 fair-direction baselines for one common anchor."""
    if not np.isfinite([previous_close, close]).all() or previous_close <= 0 or close <= 0:
        raise ValueError("baseline closes must be positive and finite")
    momentum = "long" if close > previous_close else "short" if close < previous_close else None

    def random_side(label):
        payload = f"{seed}|{label}|{symbol}|{timeframe_minutes}|{anchor_ms}".encode()
        bit = hashlib.sha256(payload).digest()[0] & 1
        return "long" if bit == 0 else "short"

    if momentum is None:
        momentum = random_side("momentum-zero-fallback")
    random_direction = random_side("random-baseline")
    return {"momentum": momentum, "random": random_direction}


def aggregate_complete_minutes(open_ms, opens, highs, lows, closes, volumes, tf_minutes):
    """UTC-aligned OHLCV bars; discard any bucket lacking every minute exactly once."""
    ts = np.asarray(open_ms)
    values = [np.asarray(x, dtype=float) for x in (opens, highs, lows, closes, volumes)]
    if (not isinstance(tf_minutes, (int, np.integer)) or isinstance(tf_minutes, bool)
            or tf_minutes < 1):
        raise ValueError("tf_minutes must be a positive integer")
    if ts.dtype.kind not in "iu" or ts.ndim != 1:
        raise ValueError("open_ms must be an integer one-dimensional array")
    if any(x.ndim != 1 or len(x) != len(ts) for x in values):
        raise ValueError("OHLCV arrays must be one-dimensional and aligned")
    if ts.size == 0:
        return Bars(*(np.asarray([], dtype=np.int64 if i == 0 else float)
                      for i in range(6)))
    ts = ts.astype(np.int64, copy=False)
    if np.any(ts % MINUTE_MS) or np.any(np.diff(ts) <= 0):
        raise ValueError("minute timestamps must be aligned, unique, and strictly increasing")
    o, h, l, c, v = values
    if (not all(np.isfinite(x).all() for x in values)
            or (v < 0).any() or (h < np.maximum(o, c)).any()
            or (l > np.minimum(o, c)).any() or (l > h).any()):
        raise ValueError("minute OHLCV contains nonfinite or malformed values")
    width = int(tf_minutes) * MINUTE_MS
    bucket = ts // width * width
    starts = np.r_[0, np.flatnonzero(np.diff(bucket)) + 1]
    ends = np.r_[starts[1:], len(ts)]
    counts = ends - starts
    valid = ((counts == tf_minutes)
             & (ts[starts] == bucket[starts])
             & (ts[ends - 1] == bucket[starts] + width - MINUTE_MS))
    s, e, b = starts[valid], ends[valid], bucket[starts[valid]]
    return Bars(b.astype(np.int64), o[s].copy(),
                np.maximum.reduceat(h, starts)[valid], np.minimum.reduceat(l, starts)[valid],
                c[e - 1].copy(), np.add.reduceat(v, starts)[valid])


def contiguous_slices(open_ms, tf_minutes):
    """Split native bars at every missing interval; indicators must not bridge gaps."""
    ts = np.asarray(open_ms)
    if ts.dtype.kind not in "iu" or ts.ndim != 1:
        raise ValueError("open_ms must be integer timestamps")
    if not isinstance(tf_minutes, (int, np.integer)) or isinstance(tf_minutes, bool) or tf_minutes < 1:
        raise ValueError("tf_minutes must be a positive integer")
    if not len(ts):
        return []
    cut = np.flatnonzero(np.diff(ts.astype(np.int64, copy=False)) != int(tf_minutes) * MINUTE_MS) + 1
    edges = np.r_[0, cut, len(ts)]
    return [slice(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:])]


def closed_4h_features(minute_open_ms, minute_close):
    """Return 4h close-availability timestamps and reset-safe EMA regime states.

    Invalid/missing 4h intervals reset the EMA history. A fresh sequence of 200
    valid 4h closes is required before either macro direction is available.
    """
    c = np.asarray(minute_close, dtype=float)
    raw_ts = np.asarray(minute_open_ms)
    if raw_ts.dtype.kind not in "iu" or raw_ts.ndim != 1 or len(raw_ts) != len(c):
        raise ValueError("minute timestamps and close values must align")
    four = aggregate_complete_minutes(raw_ts, c, c, c, c, np.zeros(len(c)), 240)
    close_ms = four.open_ms + FOUR_HOUR_MS
    direction = np.zeros(len(four.close), dtype=np.int8)
    alpha50, alpha200 = 2.0 / 51.0, 2.0 / 201.0
    ema50 = ema200 = None
    streak = 0
    previous_end = None
    for i, (end_ms, value) in enumerate(zip(close_ms, four.close)):
        if previous_end is None or end_ms != previous_end + FOUR_HOUR_MS:
            ema50 = ema200 = None
            streak = 0
        ema50 = value if ema50 is None else alpha50 * value + (1 - alpha50) * ema50
        ema200 = value if ema200 is None else alpha200 * value + (1 - alpha200) * ema200
        streak += 1
        if streak >= 200:
            if value > ema50 > ema200:
                direction[i] = 1
            elif value < ema50 < ema200:
                direction[i] = -1
        previous_end = int(end_ms)
    return close_ms.astype(np.int64), direction


def align_closed_4h_regime(close_ms, direction, native_open_ms, native_tf_minutes):
    """Align already-closed 4h states to native bars without lookahead/fill."""
    if not isinstance(native_tf_minutes, (int, np.integer)) or isinstance(native_tf_minutes, bool) or native_tf_minutes < 1:
        raise ValueError("native_tf_minutes must be positive")
    ends, states = np.asarray(close_ms), np.asarray(direction)
    native = np.asarray(native_open_ms)
    if (ends.dtype.kind not in "iu" or states.ndim != 1 or len(states) != len(ends)
            or native.dtype.kind not in "iu" or native.ndim != 1):
        raise ValueError("4h availability states and native timestamps must be aligned integers")
    native_close_ms = native.astype(np.int64, copy=False) + int(native_tf_minutes) * MINUTE_MS
    ix = np.searchsorted(ends, native_close_ms, side="right") - 1
    out = np.zeros(len(native), dtype=np.int8)
    valid = (ix >= 0) & (ix < len(direction))
    out[valid] = states[ix[valid]]
    return out


def closed_4h_regime(minute_open_ms, minute_close, native_open_ms, native_tf_minutes):
    """Return {-1,0,+1} macro direction using only available closed 4h bars."""
    ends, direction = closed_4h_features(minute_open_ms, minute_close)
    return align_closed_4h_regime(ends, direction, native_open_ms, native_tf_minutes)


def _net_r(entry, exit_price, side, stop, *, fee_per_side=0.0005, slippage_per_side=0.00025):
    risk = abs(entry - stop)
    if not np.isfinite([entry, exit_price, stop]).all() or entry <= 0 or risk <= 0:
        raise ValueError("entry, exit, and stop must define a positive finite risk")
    cost = fee_per_side + slippage_per_side
    if side == "long":
        net_pnl_fraction = (exit_price * (1 - cost) - entry * (1 + cost)) / entry
    else:
        net_pnl_fraction = (entry * (1 - cost) - exit_price * (1 + cost)) / entry
    return float(net_pnl_fraction * entry / risk)


def evaluate_divergence_event(*, minute_open_ms, minute_opens, minute_highs,
                              minute_lows, minute_closes, native_bars: Bars,
                              native_tf_minutes, signal_index, side, pivot_stop, atr_at_signal,
                              stop_buffer_atr, target_r, horizon_bars,
                              entry_mode, fee_per_side=0.0005,
                              slippage_per_side=0.00025):
    """Evaluate one emitted signal on the complete 1m path; fail closed on gaps.

    No-fill/expiry/invalid-before-entry is a resolved signal failure without a
    realized trade P&L. `trade_net_r` is present only when a position actually
    filled, keeping M2's signal denominator separate from trade-order Monte Carlo.
    """
    if side not in ("long", "short") or entry_mode not in ("next_open", "stop_entry"):
        raise ValueError("invalid side or entry_mode")
    if not 0 <= signal_index < len(native_bars.open_ms):
        raise ValueError("signal_index outside native bars")
    if horizon_bars not in (10, 20) or target_r not in (1.0, 1.5, 2.0, 3.0):
        raise ValueError("horizon or target outside frozen grid")
    raw_ts = np.asarray(minute_open_ms)
    mo, mh, ml, mc = [np.asarray(x, dtype=float) for x in
                       (minute_opens, minute_highs, minute_lows, minute_closes)]
    if raw_ts.dtype.kind not in "iu" or any(x.ndim != 1 or len(x) != len(raw_ts)
                                             for x in (mo, mh, ml, mc)):
        raise ValueError("minute path must contain aligned integer timestamps and OHLC")
    if (not isinstance(native_tf_minutes, (int, np.integer))
            or isinstance(native_tf_minutes, bool) or native_tf_minutes < 1):
        raise ValueError("native_tf_minutes must be a positive integer")
    tf_minutes = int(native_tf_minutes)
    signal_open = int(native_bars.open_ms[signal_index])
    signal_end = signal_open + tf_minutes * MINUTE_MS
    trigger = (native_bars.high[signal_index] if side == "long"
               else native_bars.low[signal_index])
    stop = pivot_stop - stop_buffer_atr * atr_at_signal if side == "long" else pivot_stop + stop_buffer_atr * atr_at_signal
    signal_close = native_bars.close[signal_index]
    if (not np.isfinite([trigger, stop, signal_close, atr_at_signal]).all()
            or atr_at_signal <= 0 or stop <= 0
            or (side == "long" and stop >= signal_close)
            or (side == "short" and stop <= signal_close)):
        return {"status": "invalid", "target_first": False, "entry_ms": None,
                "entry_price": None, "exit_price": None, "trade_net_r": None}
    raw_ts = raw_ts.astype(np.int64, copy=False)
    minute_start = int(np.searchsorted(raw_ts, signal_end))
    if minute_start >= len(raw_ts) or raw_ts[minute_start] != signal_end:
        return {"status": "unresolved", "target_first": None, "entry_ms": None,
                "entry_price": None, "exit_price": None, "trade_net_r": None}

    entry_i = signal_index + 1
    if entry_i >= len(native_bars.open_ms):
        return {"status": "unresolved", "target_first": None, "entry_ms": None,
                "entry_price": None, "exit_price": None, "trade_net_r": None}
    if int(native_bars.open_ms[entry_i]) != signal_end:
        return {"status": "unresolved", "target_first": None, "entry_ms": None,
                "entry_price": None, "exit_price": None, "trade_net_r": None}
    entry_ms = None
    entry_price = None
    entry_native_index = entry_i
    if entry_mode == "next_open":
        entry_ms = int(native_bars.open_ms[entry_i])
        entry_price = float(native_bars.open[entry_i])
        minute_start = int(np.searchsorted(raw_ts, entry_ms))
        # The native entry and its underlying 1m execution path must describe
        # the same observed open. Fail closed if callers pass mismatched bars.
        if (minute_start >= len(raw_ts) or raw_ts[minute_start] != entry_ms
                or not np.isclose(mo[minute_start], entry_price, rtol=0, atol=0)):
            return {"status": "unresolved", "target_first": None, "entry_ms": entry_ms,
                    "entry_price": entry_price, "exit_price": None, "trade_net_r": None}
    else:
        for k in range(3):
            native_i = entry_i + k
            if native_i >= len(native_bars.open_ms):
                return {"status": "unresolved", "target_first": None, "entry_ms": None,
                        "entry_price": None, "exit_price": None, "trade_net_r": None}
            bar_start = int(native_bars.open_ms[native_i])
            first = int(np.searchsorted(raw_ts, bar_start))
            nminutes = tf_minutes
            if first + nminutes > len(raw_ts) or not np.array_equal(
                    raw_ts[first:first+nminutes], bar_start + np.arange(nminutes, dtype=np.int64) * MINUTE_MS):
                return {"status": "unresolved", "target_first": None, "entry_ms": None,
                        "entry_price": None, "exit_price": None, "trade_net_r": None}
            for mi in range(first, first+nminutes):
                if (not np.isfinite([mo[mi], mh[mi], ml[mi], mc[mi]]).all()
                        or mh[mi] < max(mo[mi], mc[mi])
                        or ml[mi] > min(mo[mi], mc[mi])
                        or mh[mi] < ml[mi]):
                    return {"status": "unresolved", "target_first": None,
                            "entry_ms": None, "entry_price": None,
                            "exit_price": None, "trade_net_r": None}
                if side == "long":
                    if mo[mi] >= trigger:
                        entry_ms, entry_price = int(raw_ts[mi]), float(mo[mi]); entry_native_index = native_i; break
                    if mo[mi] <= stop or ml[mi] <= stop:
                        return {"status": "no_fill_invalidated", "target_first": False,
                                "entry_ms": None, "entry_price": None, "exit_price": None,
                                "trade_net_r": None}
                    if mh[mi] >= trigger:
                        entry_ms, entry_price = int(raw_ts[mi]), float(trigger); entry_native_index = native_i; break
                else:
                    if mo[mi] <= trigger:
                        entry_ms, entry_price = int(raw_ts[mi]), float(mo[mi]); entry_native_index = native_i; break
                    if mo[mi] >= stop or mh[mi] >= stop:
                        return {"status": "no_fill_invalidated", "target_first": False,
                                "entry_ms": None, "entry_price": None, "exit_price": None,
                                "trade_net_r": None}
                    if ml[mi] <= trigger:
                        entry_ms, entry_price = int(raw_ts[mi]), float(trigger); entry_native_index = native_i; break
            if entry_price is not None:
                minute_start = first
                break
        if entry_price is None:
            return {"status": "expired", "target_first": False, "entry_ms": None,
                    "entry_price": None, "exit_price": None, "trade_net_r": None}

    path_start = int(native_bars.open_ms[entry_native_index])
    if (minute_start >= len(raw_ts)
            or raw_ts[minute_start] != path_start):
        return {"status": "unresolved", "target_first": None, "entry_ms": entry_ms,
                "entry_price": entry_price, "exit_price": None, "trade_net_r": None}
    if (side == "long" and stop >= entry_price) or (side == "short" and stop <= entry_price):
        return {"status": "no_fill_invalidated", "target_first": False, "entry_ms": None,
                "entry_price": None, "exit_price": None, "trade_net_r": None}
    risk = abs(entry_price - stop)
    target = entry_price + (1 if side == "long" else -1) * risk * target_r
    expected_count = tf_minutes * horizon_bars
    path_ix = int(np.searchsorted(raw_ts, path_start))
    expected_times = path_start + np.arange(expected_count, dtype=np.int64) * MINUTE_MS
    if (path_ix + expected_count > len(raw_ts)
            or not np.array_equal(raw_ts[path_ix:path_ix+expected_count], expected_times)):
        return {"status": "unresolved", "target_first": None, "entry_ms": entry_ms,
                "entry_price": entry_price, "exit_price": None, "trade_net_r": None}
    resolved = _resolve_path(mo[path_ix:path_ix+expected_count],
                             mh[path_ix:path_ix+expected_count],
                             ml[path_ix:path_ix+expected_count],
                             mc[path_ix:path_ix+expected_count], side, stop, target)
    status, exit_price, exit_minute = resolved
    if status == "unresolved" or exit_price is None:
        return {"status": "unresolved", "target_first": None, "entry_ms": entry_ms,
                "entry_price": entry_price, "exit_price": None, "trade_net_r": None}
    net_r = _net_r(entry_price, exit_price, side, stop,
                   fee_per_side=fee_per_side, slippage_per_side=slippage_per_side)
    return {"status": status, "target_first": status == "target", "entry_ms": entry_ms,
            "entry_price": entry_price, "exit_price": exit_price,
            "exit_ms": int(raw_ts[path_ix + exit_minute]), "trade_net_r": net_r}


def _resolve_path(opens, highs, lows, closes, side, stop, target):
    for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
        if not np.isfinite([o, h, l, c]).all() or h < max(o, c) or l > min(o, c) or h < l:
            return "unresolved", None, i
        if side == "long":
            if o <= stop:
                return "stop", float(o), i
            if o >= target:
                return "target", float(target), i
            if l <= stop:
                return "stop", float(stop), i
            if h >= target:
                return "target", float(target), i
        else:
            if o >= stop:
                return "stop", float(o), i
            if o <= target:
                return "target", float(target), i
            if h >= stop:
                return "stop", float(stop), i
            if l <= target:
                return "target", float(target), i
    return "timeout", float(closes[-1]), len(closes) - 1
