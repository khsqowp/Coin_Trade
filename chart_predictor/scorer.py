"""Deterministic candle-only prediction scoring."""
import numpy as np
import pandas as pd
import math
from . import indicators
from .schema import HORIZON

WIDTH = {"1m": 60_000, "5m": 300_000, "30m": 1_800_000, "60m": 3_600_000}
SCORING_VERSION = "target-first-v3"


def score_prediction(prediction, candles, taker_fee=0.0005, slippage=0.0002,
                     entry_delay_candles=1, flat_mult=0.25):
    """Score complete candles; delay trade entry while M1-M3 remain anchor-based."""
    if isinstance(flat_mult, bool) or not isinstance(flat_mult, (int, float)) or not math.isfinite(flat_mult) or flat_mult <= 0:
        raise ValueError("flat_mult must be a finite positive number")
    frame = candles.sort_values("t_open_ms").reset_index(drop=True)
    raw_anchor = prediction.get("anchor_time_ms", prediction["anchor_time"])
    anchor_ms = int(raw_anchor) if isinstance(raw_anchor, (int, float)) else int(pd.Timestamp(raw_anchor).timestamp() * 1000)
    tf, width = prediction["timeframe"], WIDTH[prediction["timeframe"]]
    past = frame[frame.t_open_ms + width <= anchor_ms]
    horizon_candles = HORIZON[tf] // (width // 60_000)
    future = frame[frame.t_open_ms >= anchor_ms].head(horizon_candles)
    if past.empty or len(future) < horizon_candles or not np.all(np.diff(future.t_open_ms) == width):
        return {"status": "UNSCORABLE", "scoring_version": SCORING_VERSION}
    return _score_complete(prediction, past, future, taker_fee, slippage, entry_delay_candles, flat_mult)


def _score_complete(p, past, future, fee, slip, entry_delay_candles, flat_mult):
    """Compute direction, target touch, path error, stop and return metrics."""
    if isinstance(entry_delay_candles, bool) or not isinstance(entry_delay_candles, int):
        raise ValueError("entry_delay_candles must be a nonnegative integer")
    if entry_delay_candles < 0 or entry_delay_candles > len(future):
        raise ValueError("entry delay exceeds available horizon")
    anchor = float(past.c.iloc[-1])
    atr = float(indicators.atr(past.h, past.l, past.c)[-1])
    if not np.isfinite(atr):
        return {"status": "UNSCORABLE"}
    horizon = len(future)
    final_move = float(future.c.iloc[-1]) - anchor
    band = flat_mult * atr * math.sqrt(horizon)
    actual = "flat" if abs(final_move) <= band else "up" if final_move > 0 else "down"
    target, target_reason = _target_first(p, future, anchor, entry_delay_candles)
    if target_reason == "INVALID_LEVELS":
        return {"status": "UNSCORABLE", "scoring_version": SCORING_VERSION,
                "m2_hit": False, "m2_exit_reason": target_reason}
    width = WIDTH[p["timeframe"]]
    path = _path_errors(p, future, width)
    trade = _trade(p, future, anchor, fee, slip, entry_delay_candles)
    return {"status": "SCORED", "scoring_version": SCORING_VERSION,
            "m1_actual": actual, "m1_hit": p["direction"] == actual,
            "flat_band": band, "m2_hit": target, "m2_exit_reason": target_reason,
            "m3_mae_usdt": float(np.mean(path)),
            "m3_mae_atr": float(np.mean(path) / atr) if atr else None, **trade}


def _target_first(p, future, anchor, entry_delay_candles=1):
    """Resolve target-first outcome only for an executable delayed-entry signal.

    OHLC bars do not reveal which barrier was crossed first when both barriers
    lie inside one candle. Such ties are deliberately scored as invalidation.
    Bars before the configured entry are not credited as a win/loss on a trade
    that was never entered; barrier touches there make the signal non-executable.
    Forecasts with no actionable long/short side have no target-first outcome.
    """
    side = p["side"]
    if side not in {"long", "short"}:
        return False, "NO_TRADE"

    target = float(p["target_low"] if side == "long" else p["target_high"])
    invalidation = float(p["invalidation"])
    if (side == "long" and not invalidation < anchor < target) or (
            side == "short" and not target < anchor < invalidation):
        return False, "INVALID_LEVELS"
    entry_index = max(0, entry_delay_candles - 1)
    for row in future.iloc[:entry_index].itertuples():
        stop_hit, target_hit = _barriers(row, side, target, invalidation)
        if stop_hit and target_hit:
            return False, "AMBIGUOUS_BEFORE_ENTRY"
        if stop_hit:
            return False, "INVALIDATION_BEFORE_ENTRY"
        if target_hit:
            return False, "TARGET_MISSED_BEFORE_ENTRY"

    entry_open = float(anchor if entry_delay_candles == 0 else future.iloc[entry_index].o)
    if (side == "long" and entry_open <= invalidation) or (
            side == "short" and entry_open >= invalidation):
        return False, "INVALIDATION_BEFORE_ENTRY"
    if (side == "long" and entry_open >= target) or (side == "short" and entry_open <= target):
        return False, "TARGET_MISSED_BEFORE_ENTRY"

    for row in future.iloc[entry_index:].itertuples():
        stop_hit, target_hit = _barriers(row, side, target, invalidation)

        # If both barriers occur in one OHLC candle, their ordering is unknown;
        # take the adverse outcome instead of granting the target optimistically.
        if stop_hit:
            return False, "INVALIDATION"
        if target_hit:
            return True, "TARGET"
    return False, "TIMEOUT"


def _barriers(row, side, target, invalidation):
    """Return stop/target touches for one OHLC bar, including open gaps."""
    if side == "long":
        return (row.o <= invalidation or row.l <= invalidation,
                row.o >= target or row.h >= target)
    return (row.o >= invalidation or row.h >= invalidation,
            row.o <= target or row.l <= target)


def _path_errors(p, future, width):
    """Absolute errors at the four schema-defined horizons."""
    prices = future.c.to_numpy(float)
    return [abs(float(point["price"]) - prices[int(point["minutes"]) * 60_000 // width - 1])
            for point in p["path"]]


def _trade(p, future, anchor, fee, slip, entry_delay_candles=1):
    """Enter at delayed candle open and resolve adverse stops without optimistic fills."""
    side, lev = p["side"], int(p["leverage_suggestion"])
    if side == "none":
        return {"invalidation_hit_time": None, "exit_reason": "NO_TRADE", "entry_price": None,
                "exit_price": None, "net_return": 0.0, "r_multiple": None}
    if isinstance(entry_delay_candles, bool) or not isinstance(entry_delay_candles, int):
        raise ValueError("entry_delay_candles must be a nonnegative integer")
    if entry_delay_candles < 0 or entry_delay_candles > len(future):
        raise ValueError("entry delay exceeds available horizon")
    entry_index = max(0, entry_delay_candles - 1)
    entry = float(anchor if entry_delay_candles == 0 else future.iloc[entry_index].o)
    scan = future.iloc[0 if entry_delay_candles == 0 else entry_index:]
    sign = 1 if side == "long" else -1
    target = float(p["target_low"] if side == "long" else p["target_high"])
    inv = float(p["invalidation"])
    if (side == "long" and not inv < anchor < target) or (
            side == "short" and not target < anchor < inv):
        return {"invalidation_hit_time": None, "exit_reason": "INVALID_LEVELS",
                "entry_price": entry, "exit_price": entry, "net_return": None,
                "r_multiple": None}
    if (side == "long" and entry >= target) or (side == "short" and entry <= target):
        return {"invalidation_hit_time": None, "exit_reason": "TARGET_MISSED_BEFORE_ENTRY",
                "entry_price": None, "exit_price": None, "net_return": 0.0,
                "r_multiple": None}
    liq = entry * (1 - sign * max(0, 1 / lev - .005))
    for row in scan.itertuples():
        stop = _first_stop(row, side, entry, inv, liq)
        if stop:
            reason, exit_price = stop
            hit = int(row.t_open_ms) if reason == "INVALIDATION" else None
            return _trade_result(reason, entry, exit_price, hit, inv, lev, sign, fee, slip)
        target_hit = ((row.o >= target or row.h >= target) if side == "long"
                      else (row.o <= target or row.l <= target))
        if target_hit:
            return _trade_result("TARGET", entry, target, None, inv, lev, sign, fee, slip)
    exit_price = float(future.c.iloc[-1])
    return _trade_result("HORIZON", entry, exit_price, None, inv, lev, sign, fee, slip)


def _first_stop(row, side, entry, invalidation, liquidation):
    """Choose the nearer triggered stop, filling at candle open after a gap."""
    levels = [("INVALIDATION", invalidation), ("LIQUIDATION", liquidation)]
    long_side = side == "long"
    gap = [(name, level) for name, level in levels if row.o <= level] if long_side else [
        (name, level) for name, level in levels if row.o >= level]
    touched = [(name, level) for name, level in levels if row.l <= level] if long_side else [
        (name, level) for name, level in levels if row.h >= level]
    triggered = gap or touched
    if not triggered:
        return None
    reason, level = min(triggered, key=lambda item: abs(entry - item[1]))
    return reason, float(row.o if gap else level)


def _trade_result(reason, entry, exit_price, hit_time, invalidation, lev, sign, fee, slip):
    """Calculate leverage return and R using the actual entry and fill prices."""
    gross = sign * (exit_price / entry - 1) * lev
    net = gross - 2 * (fee + slip) * lev
    risk = abs(entry - invalidation) / entry * lev
    return {"invalidation_hit_time": hit_time, "exit_reason": reason, "entry_price": entry,
            "exit_price": exit_price, "net_return": net, "r_multiple": net / risk if risk else None}
