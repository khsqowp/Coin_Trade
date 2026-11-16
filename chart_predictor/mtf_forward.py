"""Causal MTF forecast construction for prospective, live-fed evaluations.

This module has no network or persistence side effects. Callers must supply
only public 1m candles and the first observed entry-minute price. Outcomes are
deliberately not read here; the caller must append forecasts before scoring.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

from .mtf_consensus import TIMEFRAME_MINUTES, build_consensus
from .resample import resample_frame
from .setups import SETUPS, Signal, generate_signals


MINUTE_MS = 60_000
MIN_HISTORY_BARS = 30
MTF_SETUPS = (
    "bb_squeeze_breakout",
    "orb_funding_session",
    "vwap_band_fade",
    "volume_climax_exhaustion",
)
REQUIRED_COLUMNS = ("t_open_ms", "o", "h", "l", "c", "v", "quote_v", "trades")
WIDTH_MS = {tf: minutes * MINUTE_MS for tf, minutes in TIMEFRAME_MINUTES.items()}


def _validate_anchor(entry_ms: int, symbol: str, entry_price: float) -> None:
    if isinstance(entry_ms, bool) or not isinstance(entry_ms, (int, np.integer)):
        raise ValueError("entry_ms must be an integer UTC millisecond timestamp")
    if entry_ms <= 0 or entry_ms % MINUTE_MS:
        raise ValueError("entry_ms must be a positive 1m UTC boundary")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    if isinstance(entry_price, bool) or not isinstance(entry_price, (int, float, np.number)):
        raise ValueError("entry_price must be numeric")
    if not math.isfinite(float(entry_price)) or float(entry_price) <= 0:
        raise ValueError("entry_price must be finite and positive")


def _prefix_frame(minute_candles: pd.DataFrame, entry_ms: int) -> pd.DataFrame:
    if not isinstance(minute_candles, pd.DataFrame):
        raise ValueError("minute_candles must be a pandas DataFrame")
    missing = set(REQUIRED_COLUMNS) - set(minute_candles.columns)
    if missing:
        raise ValueError(f"minute candle columns missing: {sorted(missing)}")
    numeric_stamps = pd.to_numeric(minute_candles["t_open_ms"], errors="coerce").to_numpy(float)
    if (not np.isfinite(numeric_stamps).all()
            or np.any(numeric_stamps != np.floor(numeric_stamps))
            or np.any(numeric_stamps < 0)
            or np.any(numeric_stamps > np.iinfo(np.int64).max)):
        raise ValueError("minute candle timestamps must be finite integer milliseconds")
    stamps = numeric_stamps.astype(np.int64)
    # Select by time before validating OHLCV: unfinished/future payload values
    # must not influence a forecast anchored at entry_ms.
    eligible = stamps < entry_ms
    prefix = minute_candles.loc[eligible, list(REQUIRED_COLUMNS)].copy()
    prefix["t_open_ms"] = stamps[eligible]
    if prefix.empty:
        return prefix
    stamps = prefix["t_open_ms"].to_numpy(np.int64)
    if np.any(stamps % MINUTE_MS):
        raise ValueError("minute candle timestamps must align to UTC minute boundaries")
    if np.any(np.diff(stamps) <= 0):
        raise ValueError("minute candles must be strictly ordered and unique")
    if int(stamps[-1]) != entry_ms - MINUTE_MS:
        expected = entry_ms - MINUTE_MS
        missing = prefix.iloc[0:0].copy()
        missing.attrs["_missing_open_ms"] = expected
        return missing
    gaps = np.flatnonzero(np.diff(stamps) != MINUTE_MS)
    if len(gaps):
        missing_open = int(stamps[gaps[0]] + MINUTE_MS)
        missing = prefix.iloc[0:0].copy()
        missing.attrs["_missing_open_ms"] = missing_open
        return missing

    values = prefix[["o", "h", "l", "c", "v", "quote_v", "trades"]].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("completed candle values must be finite")
    if np.any(values[:, :4] <= 0) or np.any(values[:, 4:] < 0):
        raise ValueError("prices must be positive and volumes/trades non-negative")
    if np.any(values[:, 6] != np.floor(values[:, 6])):
        raise ValueError("trade counts must be integers")
    opened, high, low, close = (prefix[key].to_numpy(float) for key in ("o", "h", "l", "c"))
    if np.any(high < np.maximum(opened, close)) or np.any(low > np.minimum(opened, close)):
        raise ValueError("invalid OHLC relationship")
    if np.any(high < low):
        raise ValueError("candle high is below low")
    return prefix.reset_index(drop=True)


def _fingerprint(prefix: pd.DataFrame) -> str:
    canonical = prefix.to_csv(index=False, float_format="%.12g", lineterminator="\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _with_incomplete_sentinel(frame: pd.DataFrame, timeframe: str,
                               entry_ms: int, entry_price: float) -> pd.DataFrame:
    """Permit the last completed bar to emit without exposing a partial bar."""
    width = WIDTH_MS[timeframe]
    sentinel_open = (entry_ms // width) * width
    if frame.empty:
        return frame
    if int(frame.t_open_ms.iloc[-1]) >= sentinel_open:
        # A complete bar cannot start at or after the current partial bucket.
        raise ValueError("completed timeframe bars overlap the incomplete entry bucket")
    sentinel = {column: 0 for column in frame.columns}
    sentinel.update({
        "t_open_ms": sentinel_open,
        "o": float(entry_price), "h": float(entry_price),
        "l": float(entry_price), "c": float(entry_price),
    })
    return pd.concat([frame, pd.DataFrame([sentinel])], ignore_index=True)


def forecast_at(minute_candles: pd.DataFrame, *, symbol: str, entry_ms: int,
                entry_price: float, blocked_until: Mapping[str, int] | None = None,
                min_timeframes: int = 2) -> dict:
    """Build one causal MTF event at the start of a new 1m candle.

    `entry_price` must be the first observed executable-price reference for the
    new minute. The candle at `entry_ms` and every later candle are excluded
    from features and the input fingerprint. If any minute is missing before
    the anchor, the function abstains rather than bridging the gap.

    For efficiency this first implementation recomputes setup histories from
    the supplied full prefix. It is an evaluation adapter, not a production
    latency-optimized service; callers should benchmark it before 24/7 use.
    """
    _validate_anchor(entry_ms, symbol, entry_price)
    if min_timeframes != 2:
        raise ValueError("the frozen MTF protocol requires exactly two minimum timeframe votes")
    blocked_until = blocked_until or {}
    for timeframe, deadline in blocked_until.items():
        if timeframe not in WIDTH_MS:
            raise ValueError(f"unsupported overlap timeframe: {timeframe}")
        if isinstance(deadline, bool) or not isinstance(deadline, (int, np.integer)):
            raise ValueError("overlap deadlines must be integer UTC millisecond timestamps")
        if deadline % MINUTE_MS:
            raise ValueError("overlap deadlines must align to UTC minute boundaries")

    prefix = _prefix_frame(minute_candles, entry_ms)
    if prefix.empty:
        expected = entry_ms - MINUTE_MS
        marker = prefix.attrs.get("_missing_open_ms")
        # `_prefix_frame` stores the first missing boundary in attrs below;
        # absent history is a distinct state from an observed gap.
        if marker is not None:
            return {"status": "ABSTAIN_DATA_GAP", "event": None,
                    "missing_open_ms": int(marker), "entry_ms": int(entry_ms)}
        return {"status": "ABSTAIN_INSUFFICIENT_HISTORY", "event": None,
                "missing_open_ms": expected, "entry_ms": int(entry_ms)}

    prefix_hash = _fingerprint(prefix)
    all_signals = []
    for timeframe in TIMEFRAME_MINUTES:
        width = WIDTH_MS[timeframe]
        bars = prefix.copy() if timeframe == "1m" else resample_frame(
            prefix, timeframe, now_ms=entry_ms)
        bars = bars.loc[bars.t_open_ms + width <= entry_ms].reset_index(drop=True)
        if len(bars) < MIN_HISTORY_BARS:
            continue
        bars = _with_incomplete_sentinel(bars, timeframe, entry_ms, float(entry_price))
        for setup in MTF_SETUPS:
            if setup not in SETUPS:
                raise RuntimeError(f"registered MTF setup is missing from catalog: {setup}")
            for signal in generate_signals(bars, setup):
                index = int(signal.index)
                if not 0 <= index < len(bars):
                    raise ValueError("setup emitted an invalid bar index")
                signal_close_ms = int(bars.t_open_ms.iloc[index]) + width
                if signal_close_ms > entry_ms:
                    continue
                if entry_ms - signal_close_ms > width:
                    continue
                if not isinstance(signal, Signal):
                    raise ValueError("setup returned an unsupported signal type")
                all_signals.append({
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "signal_close_ms": signal_close_ms,
                    "setup": setup,
                    "side": signal.side,
                    "stop": float(signal.stop),
                })

    active_signals = [
        signal for signal in all_signals
        if int(entry_ms) >= int(blocked_until.get(signal["timeframe"], 0))
    ]
    all_timeframes = {signal["timeframe"] for signal in all_signals}
    active_timeframes = {signal["timeframe"] for signal in active_signals}
    if len(active_timeframes) < min_timeframes and len(all_timeframes) >= min_timeframes:
        return {"status": "ABSTAIN_OVERLAP", "event": None,
                "signal_count": len(all_signals), "entry_ms": int(entry_ms),
                "input_prefix_end_ms": int(prefix.t_open_ms.iloc[-1]),
                "input_prefix_sha256": prefix_hash}

    candidate = build_consensus(
        active_signals, symbol=symbol, entry_ms=int(entry_ms),
        entry_price=float(entry_price), min_timeframes=min_timeframes,
    )
    if candidate is None:
        return {"status": "ABSTAIN_NO_CONSENSUS", "event": None,
                "signal_count": len(all_signals), "entry_ms": int(entry_ms),
                "input_prefix_end_ms": int(prefix.t_open_ms.iloc[-1]),
                "input_prefix_sha256": prefix_hash}

    event = candidate
    return {"status": "EMITTED", "event": event,
            "signal_count": len(all_signals), "entry_ms": int(entry_ms),
            "input_prefix_end_ms": int(prefix.t_open_ms.iloc[-1]),
            "input_prefix_sha256": prefix_hash}
