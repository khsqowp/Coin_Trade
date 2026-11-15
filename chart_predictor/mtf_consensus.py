"""Causal multi-timeframe consensus construction and triple-barrier scoring."""
from collections import defaultdict
import math
from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd


TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "10m": 10, "15m": 15,
    "30m": 30, "60m": 60, "120m": 120, "240m": 240,
}
TIMEFRAME_MS = {name: minutes * 60_000 for name, minutes in TIMEFRAME_MINUTES.items()}
BASE_SETUPS = frozenset({
    "bb_squeeze_breakout", "orb_funding_session", "vwap_band_fade",
    "volume_climax_exhaustion",
})
ROUND_TRIP_TAKER_FEE = 0.001
TARGET_R_MULTIPLE = 2.0
CHECKPOINT_BARS = (10, 20)
LEVERAGES = (4, 5)
MAINTENANCE_BUFFER = 0.005
REQUIRED_CANDLE_COLUMNS = ("t_open_ms", "o", "h", "l", "c")


def build_consensus(signals: Iterable[Mapping], *, symbol: str, entry_ms: int,
                    entry_price: float, min_timeframes: int = 2) -> dict | None:
    """Build one strict-unanimity event from fresh, closed-bar setup votes.

    `entry_ms` is the next 1m candle open after the latest completed 1m candle.
    Votes are known only when their complete setup candle closed no later than
    that timestamp. Each timeframe gets one vote; conflicting votes abstain.
    """
    _require_timestamp(entry_ms, "entry_ms")
    if entry_ms % 60_000:
        raise ValueError("entry_ms must align to a 1m UTC candle boundary")
    _require_positive(entry_price, "entry_price")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("symbol must be a non-empty string")
    if isinstance(min_timeframes, bool) or not isinstance(min_timeframes, int):
        raise ValueError("min_timeframes must be an integer")
    if not 2 <= min_timeframes <= len(TIMEFRAME_MINUTES):
        raise ValueError("min_timeframes is outside the supported timeframe count")

    grouped = _eligible_signals(signals, symbol, entry_ms)
    votes = {}
    has_timeframe_conflict = False
    for timeframe, rows in grouped.items():
        latest_close = max(row["signal_close_ms"] for row in rows)
        latest = [row for row in rows if row["signal_close_ms"] == latest_close]
        sides = {row["side"] for row in latest}
        if len(sides) != 1:
            has_timeframe_conflict = True
            continue
        side = next(iter(sides))
        stops = [row["stop"] for row in latest]
        if not all(_stop_is_adverse(side, entry_price, stop) for stop in stops):
            continue
        # If same-timeframe rules agree, use the closest valid stop, a fixed
        # conservative tie rule that does not create an extra timeframe vote.
        stop = max(stops) if side == "long" else min(stops)
        risk = abs(entry_price - stop)
        sign = 1 if side == "long" else -1
        target = float(entry_price + sign * TARGET_R_MULTIPLE * risk)
        if target <= 0:
            continue
        votes[timeframe] = {
            "timeframe": timeframe,
            "signal_close_ms": latest_close,
            "setups": sorted({row["setup"] for row in latest}),
            "side": side,
            "entry_ms": entry_ms,
            "entry_price": float(entry_price),
            "stop": stop,
            "risk": risk,
            "target": target,
            "risk_fraction": risk / float(entry_price),
        }

    if has_timeframe_conflict or len(votes) < min_timeframes:
        return None
    if len({vote["side"] for vote in votes.values()}) != 1:
        return None
    side = next(iter(votes.values()))["side"]
    return {"event_id": f"{symbol}:{entry_ms}:{side}", "symbol": symbol,
            "entry_ms": entry_ms, "entry_price": float(entry_price), "side": side,
            "votes": votes, "forecasts": votes.copy()}


def _eligible_signals(signals, symbol, entry_ms):
    grouped = defaultdict(list)
    for row in signals:
        if not isinstance(row, Mapping):
            raise ValueError("each signal must be a mapping")
        if row.get("symbol") != symbol:
            continue
        signal_close_ms = row.get("signal_close_ms")
        _require_timestamp(signal_close_ms, "signal_close_ms")
        # Ignore future and stale records before inspecting their signal fields.
        # This makes later outcomes unable to invalidate an earlier decision.
        if signal_close_ms > entry_ms:
            continue
        timeframe = row.get("timeframe")
        if timeframe not in TIMEFRAME_MS:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        age_ms = entry_ms - signal_close_ms
        if age_ms > TIMEFRAME_MS[timeframe]:
            continue
        side = row.get("side")
        if side not in {"long", "short"}:
            raise ValueError("signal side must be long or short")
        setup = row.get("setup")
        if setup not in BASE_SETUPS:
            raise ValueError(f"unsupported base setup: {setup}")
        stop = _require_positive(row.get("stop"), "stop")
        if signal_close_ms % TIMEFRAME_MS[timeframe]:
            raise ValueError("signal close must align to its UTC timeframe boundary")
        grouped[timeframe].append({"signal_close_ms": signal_close_ms,
                                   "side": side, "setup": setup, "stop": stop})
    return grouped


def score_forecast(forecast: Mapping, minute_candles: pd.DataFrame, *,
                   include_leverage: bool = True) -> dict:
    """Score 10/20-bar target-first outcomes using complete 1m candles.

    The stop wins same-candle barrier ties. A missing/incomplete path is
    unscorable, not a timeout. Leverage paths are optional for matched
    unleveraged baselines. Fees follow SPEC §14.1; slippage and depth are not
    modeled in this phase.
    """
    _validate_forecast(forecast)
    _validate_candle_frame(minute_candles)
    timeframe = forecast["timeframe"]
    width_ms = TIMEFRAME_MS[timeframe]
    max_end_ms = forecast["entry_ms"] + CHECKPOINT_BARS[-1] * width_ms
    future = minute_candles.loc[
        (minute_candles["t_open_ms"] >= forecast["entry_ms"])
        & (minute_candles["t_open_ms"] < max_end_ms),
        list(REQUIRED_CANDLE_COLUMNS),
    ].sort_values("t_open_ms", kind="stable").reset_index(drop=True)
    results = {
        f"{bars}_bars": _score_horizon(forecast, future, bars * width_ms)
        for bars in CHECKPOINT_BARS
    }
    leveraged = {
        f"{leverage}x": {
            "liquidation_price": _liquidation_price(forecast, leverage),
            "stop_beyond_liquidation": _stop_beyond_liquidation(forecast, leverage),
            **{f"{bars}_bars": _score_horizon(
                forecast, future, bars * width_ms, leverage=leverage
            ) for bars in CHECKPOINT_BARS},
        }
        for leverage in LEVERAGES
    } if include_leverage else {}
    scored = {"TARGET", "STOP", "TIMEOUT"}
    any_scored = any(value["outcome"] in scored for value in results.values())
    any_scored |= any(lev_result[f"{bars}_bars"]["outcome"] in scored
                      for lev_result in leveraged.values() for bars in CHECKPOINT_BARS)
    return {"status": "SCORED" if any_scored else "UNSCORABLE",
            "event_id": forecast.get("event_id"), "symbol": forecast["symbol"],
            "timeframe": timeframe, "side": forecast["side"],
            "entry_ms": forecast["entry_ms"], "leverage": leveraged, **results}


def _score_horizon(forecast, future, horizon_ms, leverage=None):
    entry_ms = forecast["entry_ms"]
    width_ms = TIMEFRAME_MS[forecast["timeframe"]]
    minute_ms = 60_000
    required = horizon_ms // minute_ms
    horizon_end = entry_ms + horizon_ms
    window = future.loc[future["t_open_ms"] < horizon_end].reset_index(drop=True)
    for index in range(required):
        if index >= len(window):
            return {"outcome": "UNSCORABLE_INCOMPLETE", "target_first": None,
                    "observed_minutes": index}
        row = window.iloc[index]
        expected_ms = entry_ms + index * minute_ms
        actual_ms = int(row["t_open_ms"])
        if actual_ms != expected_ms:
            return {"outcome": "UNSCORABLE_GAP", "target_first": None,
                    "expected_ms": expected_ms, "observed_ms": actual_ms}
        values = [float(row[key]) for key in ("o", "h", "l", "c")]
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("candle prices must be finite and positive")
        open_price, high, low, close = values
        if high < max(open_price, close) or low > min(open_price, close) or high < low:
            raise ValueError("invalid OHLC candle")
        exit_result = _barrier_exit(forecast, open_price, high, low, leverage)
        if exit_result is not None:
            return _trade_metrics(forecast, exit_result[0], exit_result[1], actual_ms,
                                  index + 1, width_ms, leverage)
    exit_price = float(window.iloc[required - 1]["c"])
    return _trade_metrics(forecast, "TIMEOUT", exit_price, horizon_end - minute_ms,
                          required, width_ms, leverage)


def _barrier_exit(forecast, open_price, high, low, leverage):
    side = forecast["side"]
    stop, target = float(forecast["stop"]), float(forecast["target"])
    adverse_reason = "STOP"
    if leverage is not None:
        liquidation = _liquidation_price(forecast, leverage)
        if side == "long" and liquidation >= stop:
            stop, adverse_reason = liquidation, "LIQUIDATION"
        elif side == "short" and liquidation <= stop:
            stop, adverse_reason = liquidation, "LIQUIDATION"
    if side == "long":
        stop_hit, target_hit = low <= stop, high >= target
        gap_stop, gap_target = open_price <= stop, open_price >= target
    else:
        stop_hit, target_hit = high >= stop, low <= target
        gap_stop, gap_target = open_price >= stop, open_price <= target
    if stop_hit and target_hit:
        return adverse_reason, open_price if gap_stop else stop
    if gap_stop:
        return adverse_reason, open_price
    if gap_target:
        return "TARGET", target
    if stop_hit:
        return adverse_reason, stop
    if target_hit:
        return "TARGET", target
    return None


def _trade_metrics(forecast, outcome, exit_price, exit_ms, observed_minutes, width_ms,
                   leverage=None):
    sign = 1 if forecast["side"] == "long" else -1
    entry = float(forecast["entry_price"])
    gross_return = sign * (float(exit_price) / entry - 1)
    underlying_net_return = gross_return - ROUND_TRIP_TAKER_FEE
    net_return = underlying_net_return * leverage if leverage else underlying_net_return
    risk_fraction = abs(entry - float(forecast["stop"])) / entry
    risk_scale = leverage if leverage else 1
    return {"outcome": outcome, "target_first": outcome == "TARGET",
            "exit_ms": exit_ms, "exit_price": float(exit_price),
            "observed_minutes": observed_minutes,
            "horizon_bars": math.ceil(observed_minutes / (width_ms / 60_000)),
            "gross_return": gross_return, "net_return": net_return,
            "net_r": net_return / (risk_fraction * risk_scale) if risk_fraction else None,
            "underlying_net_return": underlying_net_return,
            "round_trip_fee": ROUND_TRIP_TAKER_FEE,
            "leverage": leverage}


def _liquidation_price(forecast, leverage):
    sign = 1 if forecast["side"] == "long" else -1
    loss_fraction = 1 / leverage - MAINTENANCE_BUFFER
    return float(forecast["entry_price"] * (1 - sign * loss_fraction))


def _stop_beyond_liquidation(forecast, leverage):
    liquidation = _liquidation_price(forecast, leverage)
    if forecast["side"] == "long":
        return float(forecast["stop"]) <= liquidation
    return float(forecast["stop"]) >= liquidation


def _validate_forecast(forecast):
    if not isinstance(forecast, Mapping):
        raise ValueError("forecast must be a mapping")
    if forecast.get("timeframe") not in TIMEFRAME_MS:
        raise ValueError("unsupported forecast timeframe")
    if forecast.get("side") not in {"long", "short"}:
        raise ValueError("forecast side must be long or short")
    if not isinstance(forecast.get("symbol"), str) or not forecast["symbol"]:
        raise ValueError("forecast symbol must be non-empty")
    _require_timestamp(forecast.get("entry_ms"), "entry_ms")
    if forecast["entry_ms"] % 60_000:
        raise ValueError("entry_ms must align to a 1m UTC candle boundary")
    entry = _require_positive(forecast.get("entry_price"), "entry_price")
    stop = _require_positive(forecast.get("stop"), "stop")
    target = _require_positive(forecast.get("target"), "target")
    side = forecast["side"]
    if not _stop_is_adverse(side, entry, stop):
        raise ValueError("stop must be adverse to entry")
    expected_target = entry + (1 if side == "long" else -1) * TARGET_R_MULTIPLE * abs(entry - stop)
    if not math.isclose(target, expected_target, rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError("target must be exactly 2R from entry")


def _validate_candle_frame(frame):
    if not isinstance(frame, pd.DataFrame) or not set(REQUIRED_CANDLE_COLUMNS).issubset(frame.columns):
        raise ValueError("minute candles require t_open_ms and OHLC columns")


def _stop_is_adverse(side, entry, stop):
    return stop < entry if side == "long" else stop > entry


def _require_timestamp(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer millisecond timestamp")
    return int(value)


def _require_positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value
