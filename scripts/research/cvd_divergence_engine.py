"""Frozen 1h price/CVD divergence signal and triple-barrier mechanics."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

HOUR_MS = 3_600_000
DAY_MS = 86_400_000


@dataclass(frozen=True)
class MarketSeries:
    times: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    taker_buy_volume: np.ndarray


def signed_delta(volume: np.ndarray, taker_buy_volume: np.ndarray) -> np.ndarray:
    volume = np.asarray(volume, dtype=float)
    taker = np.asarray(taker_buy_volume, dtype=float)
    if volume.shape != taker.shape:
        raise ValueError("volume arrays must have identical shape")
    return 2.0 * taker - volume


def utc_daily_cvd(times: np.ndarray, delta: np.ndarray) -> np.ndarray:
    times = np.asarray(times, dtype=np.int64)
    delta = np.asarray(delta, dtype=float)
    if times.shape != delta.shape:
        raise ValueError("time and delta arrays must have identical shape")
    result = np.empty(len(times), dtype=float)
    running = 0.0
    previous_day = None
    previous_time = None
    for index, (stamp, value) in enumerate(zip(times, delta)):
        day = int(stamp) // DAY_MS
        if previous_day is not None and day < previous_day:
            raise ValueError("timestamps must be sorted")
        if day != previous_day or (previous_time is not None and int(stamp) - previous_time != HOUR_MS):
            running = 0.0
        running += float(value)
        result[index] = running
        previous_day = day
        previous_time = int(stamp)
    return result


def wilder_atr_reset_on_gaps(times: np.ndarray, high: np.ndarray, low: np.ndarray,
                             close: np.ndarray, period: int = 14) -> np.ndarray:
    times = np.asarray(times, dtype=np.int64)
    high, low, close = (np.asarray(value, dtype=float) for value in (high, low, close))
    out = np.full(len(times), np.nan, dtype=float)
    segment_true_ranges = []
    previous_atr = np.nan
    previous_close = np.nan
    for index in range(len(times)):
        contiguous = index > 0 and int(times[index]) - int(times[index - 1]) == HOUR_MS
        if not contiguous:
            segment_true_ranges = []
            previous_atr = np.nan
            tr = high[index] - low[index]
        else:
            tr = max(high[index] - low[index], abs(high[index] - previous_close),
                     abs(low[index] - previous_close))
        segment_true_ranges.append(float(tr))
        if len(segment_true_ranges) == period:
            previous_atr = float(np.mean(segment_true_ranges))
            out[index] = previous_atr
        elif len(segment_true_ranges) > period:
            previous_atr = (previous_atr * (period - 1) + float(tr)) / period
            out[index] = previous_atr
        previous_close = close[index]
    return out


def atr_available_at_open(times: np.ndarray, atr_values: np.ndarray) -> np.ndarray:
    """At a bar open, only the previous contiguous bar's completed ATR is known."""
    times = np.asarray(times, dtype=np.int64)
    atr_values = np.asarray(atr_values, dtype=float)
    if times.shape != atr_values.shape:
        raise ValueError("time and ATR arrays must have identical shape")
    result = np.full(len(times), np.nan, dtype=float)
    for index in range(1, len(times)):
        if (int(times[index]) - int(times[index - 1]) == HOUR_MS
                and np.isfinite(atr_values[index - 1]) and atr_values[index - 1] > 0):
            result[index] = atr_values[index - 1]
    return result


def _strict_pivot(values: np.ndarray, index: int, low: bool, wing: int = 3,
                  times: np.ndarray | None = None) -> bool:
    if index < wing or index + wing >= len(values):
        return False
    left = values[index - wing:index]
    right = values[index + 1:index + wing + 1]
    if times is not None and np.any(np.diff(times[index - wing:index + wing + 1]) != HOUR_MS):
        return False
    if low:
        return bool(np.all(values[index] < left) and np.all(values[index] < right))
    return bool(np.all(values[index] > left) and np.all(values[index] > right))


def replace_pending_for_new_pair(pending: dict, side: str, *,
                                 price_divergence: bool, cvd_divergence: bool,
                                 arm: str, new_setup: dict) -> None:
    """Every newly confirmed same-day pair supersedes the older same-side pending setup."""
    pending[side] = None
    if price_divergence and (arm == "price_only" or cvd_divergence):
        pending[side] = new_setup


def pending_confirmation_step(setup: dict, current_idx: int) -> int:
    return current_idx - int(setup["available_idx"])


def next_hour_entry_anchor(times: np.ndarray, signal_idx: int) -> tuple[int, int | None]:
    """Return the scheduled next-open timestamp and its observed index, if present."""
    scheduled = int(times[signal_idx]) + HOUR_MS
    observed_index = signal_idx + 1
    if observed_index < len(times) and int(times[observed_index]) == scheduled:
        return scheduled, observed_index
    return scheduled, None


def generate_events(symbol: str, data: MarketSeries, *, arm: str,
                    eligible_start_ms: int, eligible_end_ms: int) -> tuple[list[dict], int]:
    """Generate one frozen arm: `price_only` or `cvd`; no outcomes are read."""
    if arm not in {"price_only", "cvd"}:
        raise ValueError("arm must be price_only or cvd")
    arrays = [np.asarray(value) for value in (
        data.times, data.open, data.high, data.low, data.close,
        data.volume, data.taker_buy_volume,
    )]
    n = len(arrays[0])
    if any(len(array) != n for array in arrays):
        raise ValueError("market arrays have unequal lengths")
    times, opens, highs, lows, closes, volumes, taker = arrays
    times = times.astype(np.int64, copy=False)
    if n < 20 or np.any(np.diff(times) <= 0):
        raise ValueError("series must have at least 20 strictly increasing hourly bars")
    cvd = utc_daily_cvd(times, signed_delta(volumes, taker))
    atr_values = wilder_atr_reset_on_gaps(times, highs, lows, closes, 14)
    atr_at_open = atr_available_at_open(times, atr_values)
    day_ids = times // DAY_MS
    previous_pivot = {"long": None, "short": None}
    pending = {"long": None, "short": None}
    events = []
    eligible_bars = 0

    eligible_entry_mask = ((times >= eligible_start_ms)
                           & (times + 20 * HOUR_MS - 1 < eligible_end_ms)
                           & np.isfinite(atr_at_open) & (atr_at_open > 0))
    eligible_bars = int(np.sum(eligible_entry_mask))

    for confirmation_idx in range(n):
        if confirmation_idx > 0 and times[confirmation_idx] - times[confirmation_idx - 1] != HOUR_MS:
            # A data discontinuity invalidates pivot continuity and all pending setups.
            previous_pivot = {"long": None, "short": None}
            pending = {"long": None, "short": None}

        # Resolve newly known same-close pivot pairs before checking an older setup's breakout.
        # A new same-side pair supersedes the old setup at this close; its own confirmation
        # window starts on the next bar because its available_idx equals confirmation_idx.
        pivot_idx = confirmation_idx - 3
        if pivot_idx >= 3:
            for side, is_pivot, price in (
                ("long", _strict_pivot(lows, pivot_idx, low=True, times=times), float(lows[pivot_idx])),
                ("short", _strict_pivot(highs, pivot_idx, low=False, times=times), float(highs[pivot_idx])),
            ):
                if not is_pivot:
                    continue
                previous = previous_pivot[side]
                if previous is not None and day_ids[previous["idx"]] == day_ids[pivot_idx]:
                    price_divergence = price < previous["price"] if side == "long" else price > previous["price"]
                    cvd_divergence = cvd[pivot_idx] > previous["cvd"] if side == "long" else cvd[pivot_idx] < previous["cvd"]
                    momentum_change = closes[confirmation_idx] / closes[confirmation_idx - 1] - 1.0
                    momentum_side = "long" if momentum_change > 0 else "short" if momentum_change < 0 else None
                    new_setup = {
                        "available_idx": confirmation_idx, "day_id": int(day_ids[pivot_idx]),
                        "pivot1_idx": previous["idx"], "pivot2_idx": pivot_idx,
                        "pivot2_price": price, "pivot2_cvd": float(cvd[pivot_idx]),
                        "momentum_side": momentum_side,
                    }
                    replace_pending_for_new_pair(pending, side, price_divergence=price_divergence,
                                                 cvd_divergence=cvd_divergence, arm=arm, new_setup=new_setup)
                previous_pivot[side] = {"idx": pivot_idx, "price": price, "cvd": float(cvd[pivot_idx]),
                                        "available_idx": confirmation_idx}

        confirmations = []
        for side, setup in list(pending.items()):
            if setup is None:
                continue
            step = pending_confirmation_step(setup, confirmation_idx)
            if step < 1:
                continue
            if (step > 3 or day_ids[confirmation_idx] != setup["day_id"]
                    or times[confirmation_idx] - times[confirmation_idx - 1] != HOUR_MS):
                pending[side] = None
                continue
            broken = (closes[confirmation_idx] > highs[confirmation_idx - 1]
                      if side == "long" else closes[confirmation_idx] < lows[confirmation_idx - 1])
            if broken:
                confirmations.append((side, setup))
                pending[side] = None
            elif step == 3:
                pending[side] = None

        if len(confirmations) == 2:
            confirmations = []
        elif len(confirmations) > 2:
            confirmations.sort(key=lambda item: item[1]["pivot2_idx"], reverse=True)
            confirmations = confirmations[:1]

        if confirmations:
            side, setup = confirmations[0]
            entry_time, entry_idx = next_hour_entry_anchor(times, confirmation_idx)
            scheduled_expiry_close = entry_time + 20 * HOUR_MS - 1
            atr_at_price_turn = float(atr_values[confirmation_idx])
            if (eligible_start_ms <= entry_time and scheduled_expiry_close < eligible_end_ms
                    and np.isfinite(atr_at_price_turn) and atr_at_price_turn > 0):
                events.append({
                    "symbol": symbol, "arm": arm, "side": side,
                    "signal_idx": confirmation_idx, "signal_time_ms": int(times[confirmation_idx]) + HOUR_MS - 1,
                    "entry_idx": entry_idx, "entry_open_ms": entry_time,
                    "pivot1_idx": setup["pivot1_idx"], "pivot2_idx": setup["pivot2_idx"],
                    "pivot2_price": setup["pivot2_price"], "pivot2_cvd": setup["pivot2_cvd"],
                    "atr_at_confirmation": atr_at_price_turn,
                    "scheduled_expiry_close_ms": scheduled_expiry_close,
                    "baseline_momentum_side": setup["momentum_side"],
                })

    return events, eligible_bars


def resolve_barrier(side: str, entry: float, stop: float, opens: np.ndarray,
                    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                    times: np.ndarray, funding_times: np.ndarray,
                    funding_rates: np.ndarray, horizon: int) -> dict:
    """Resolve a fixed stop/1R target with stop-first intrabar ambiguity."""
    if horizon not in (10, 20):
        raise ValueError("horizon must be 10 or 20")
    sign = 1 if side == "long" else -1
    if (sign == 1 and stop >= entry) or (sign == -1 and stop <= entry):
        return {"reason": "INVALID_ENTRY", "m2_hit": False, "exit_price": entry,
                "exit_idx": None, "exit_time_ms": None, "funding_signed": 0.0}
    risk = abs(entry - stop)
    target = entry + sign * risk
    reason, exit_price, exit_idx = "TIMEOUT", float(closes[horizon - 1]), horizon - 1
    for index in range(horizon):
        adverse_gap = opens[index] <= stop if sign == 1 else opens[index] >= stop
        target_gap = opens[index] >= target if sign == 1 else opens[index] <= target
        stop_hit = adverse_gap or (lows[index] <= stop if sign == 1 else highs[index] >= stop)
        target_hit = target_gap or (highs[index] >= target if sign == 1 else lows[index] <= target)
        if stop_hit:
            reason = "STOP"
            exit_price = float(opens[index] if adverse_gap else stop)
            exit_idx = index
            break
        if target_hit:
            reason = "TARGET"
            exit_price = float(target)
            exit_idx = index
            break
    exit_open_time = int(times[exit_idx])
    exit_close_time = exit_open_time + HOUR_MS - 1
    entry_time = int(times[0])
    lo = int(np.searchsorted(funding_times, entry_time, side="right"))
    hi = int(np.searchsorted(funding_times, exit_close_time, side="right"))
    signed_funding = 0.0
    actual_signed_funding = 0.0
    exit_candle_actual_funding = 0.0
    exit_candle_charged_funding = 0.0
    for stamp, rate in zip(funding_times[lo:hi], funding_rates[lo:hi]):
        charge = sign * float(rate)
        actual_signed_funding += charge
        if int(stamp) >= exit_open_time:
            exit_candle_actual_funding += charge
            exit_candle_charged_funding += max(charge, 0.0)
            signed_funding += max(charge, 0.0)
        else:
            signed_funding += charge
    return {"reason": reason, "m2_hit": reason == "TARGET", "exit_price": exit_price,
            "exit_idx": exit_idx, "exit_time_ms": exit_close_time,
            "gross_return": sign * (exit_price / entry - 1.0),
            "funding_signed": signed_funding, "funding_actual_signed": actual_signed_funding,
            "funding_exit_candle_actual": exit_candle_actual_funding,
            "funding_exit_candle_charged": exit_candle_charged_funding,
            "target": target, "risk": risk}


def causal_prefix_check(symbol: str, data: MarketSeries, *, arm: str,
                        eligible_start_ms: int, eligible_end_ms: int) -> dict:
    if len(data.times) < 200:
        raise ValueError("causal check requires at least 200 hourly bars")
    cut = len(data.times) // 2
    prefix_data = MarketSeries(*(np.asarray(value)[:cut] for value in (
        data.times, data.open, data.high, data.low, data.close, data.volume, data.taker_buy_volume)))
    mutated = [np.asarray(value).copy() for value in (
        data.times, data.open, data.high, data.low, data.close, data.volume, data.taker_buy_volume)]
    for array in mutated[1:5]:
        array[cut:] *= 1.7
    mutated[5][cut:] *= 2.0
    mutated[6][cut:] *= 0.5
    mutated_data = MarketSeries(*mutated)
    full, _ = generate_events(symbol, data, arm=arm, eligible_start_ms=eligible_start_ms,
                              eligible_end_ms=eligible_end_ms)
    prefix, _ = generate_events(symbol, prefix_data, arm=arm, eligible_start_ms=eligible_start_ms,
                                eligible_end_ms=eligible_end_ms)
    changed, _ = generate_events(symbol, mutated_data, arm=arm, eligible_start_ms=eligible_start_ms,
                                 eligible_end_ms=eligible_end_ms)
    cut_time = int(data.times[cut])
    key = lambda rows: [(row["entry_open_ms"], row["side"], row["pivot2_idx"], row["pivot2_price"])
                        for row in rows if row["entry_open_ms"] < cut_time]
    a, b, c = key(full), key(prefix), key(changed)
    return {"status": "PASS" if a == b == c else "FAIL", "cut_index": cut,
            "prefix_signal_count": len(a), "full_prefix_match": a == b,
            "future_mutation_match": a == c}
