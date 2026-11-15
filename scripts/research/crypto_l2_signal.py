"""Causal candidate construction for the frozen R005 L2 hypothesis.

This module emits unfilled research candidates only. It does not derive
thresholds, estimate execution, label outcomes, or place orders.
"""
from __future__ import annotations

import math
from typing import Any

from scripts.research.crypto_l2_windows import eligible_windows_for_completed_bar

AGGRESSION_LOOKBACK_MS = 30 * 24 * 60 * 60 * 1000
AGGRESSION_PERCENTILES = {0.80, 0.90, 0.95}
REPLENISHMENT_THRESHOLDS = {0.5, 1.0, 1.5}


def _finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def prior_aggression_threshold(
    observations: list[dict[str, Any]], *, symbol: str, direction: str,
    anchor_event_ms: int, percentile: float, lookback_ms: int,
    minimum_history_n: int,
) -> tuple[float | None, int]:
    """Return a linear-interpolated quantile using only same-symbol prior rows.

    The window includes observations at `anchor_event_ms-lookback_ms` and
    excludes observations at or after the anchor. The minimum history count is
    explicit so the caller cannot silently treat a tiny sample as a threshold.
    """
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("symbol must be a non-empty string")
    if not isinstance(direction, str) or direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")
    if isinstance(anchor_event_ms, bool) or not isinstance(anchor_event_ms, int):
        raise ValueError("anchor must be integer event-time milliseconds")
    if not _finite_number(percentile) or not 0 < percentile < 1:
        raise ValueError("percentile must be between zero and one")
    if isinstance(lookback_ms, bool) or not isinstance(lookback_ms, int) or lookback_ms <= 0:
        raise ValueError("lookback must be a positive integer number of milliseconds")
    if (isinstance(minimum_history_n, bool) or not isinstance(minimum_history_n, int)
            or minimum_history_n < 1):
        raise ValueError("minimum history count must be a positive integer")

    cutoff_ms = anchor_event_ms - lookback_ms
    values: list[float] = []
    for row in observations:
        if row.get("symbol") != symbol or row.get("direction") != direction:
            continue
        event_ms = row.get("event_ms")
        if isinstance(event_ms, bool) or not isinstance(event_ms, int):
            raise ValueError("matching prior observations require integer event_ms")
        if not cutoff_ms <= event_ms < anchor_event_ms:
            continue
        quote_volume = row.get("aggression_quote_volume")
        if not _finite_number(quote_volume) or quote_volume < 0:
            raise ValueError("matching prior aggression quote volume must be finite and non-negative")
        values.append(float(quote_volume))

    count = len(values)
    if count < minimum_history_n:
        return None, count
    values.sort()
    position = (count - 1) * percentile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    threshold = values[lower] + (values[upper] - values[lower]) * fraction
    return threshold, count


def _completed_feature_available(bar: dict[str, Any], *, decision_event_ms: int,
                                 decision_receive_monotonic_s: float) -> bool:
    close_ms = bar.get("bar_close_ms")
    available = bar.get("feature_available_receive_monotonic_s")
    return (
        bar.get("completed") is True
        and isinstance(close_ms, int) and not isinstance(close_ms, bool)
        and close_ms <= decision_event_ms
        and _finite_number(available)
        and available < decision_receive_monotonic_s
    )


def build_candidates_for_completed_bar(
    windows: list[dict[str, Any]], *,
    t_bar: dict[str, Any],
    btc_h_bar: dict[str, Any],
    decision_event_ms: int,
    decision_receive_monotonic_s: float,
    prior_aggression_observations: list[dict[str, Any]],
    aggression_percentile: float,
    minimum_aggression_history_n: int,
    minimum_replenishment_ratio: float,
    tick_size: float,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build at most one earliest qualifying R005 candidate for a T bar.

    The aggression quantile is computed separately at each event's start using
    only same-symbol, same-direction observations in the preceding 30 days.
    T/H bars must carry their actual close and receive-time. The decision event-
    time anchor represents when both bars and the replenishment observation
    are complete; the monotonic anchor represents local knowledge. Candidate
    stop levels are indicative only; entry/target/R remain unresolved until an
    executable post-signal quote is replayed.
    """
    required_ints = (decision_event_ms, t_bar.get("bar_open_ms"),
                     t_bar.get("bar_close_ms"))
    if any(isinstance(value, bool) or not isinstance(value, int) for value in required_ints):
        raise ValueError("decision and T-bar event-time bounds must be integer milliseconds")
    t_open, t_close = t_bar["bar_open_ms"], t_bar["bar_close_ms"]
    if t_open < 0 or t_close <= t_open or decision_event_ms < t_close:
        raise ValueError("T bar must be valid and completed by the decision event time")
    timeframe_min = t_bar.get("timeframe_minutes")
    macro_timeframe_min = btc_h_bar.get("timeframe_minutes")
    if (isinstance(timeframe_min, bool) or not isinstance(timeframe_min, int)
            or timeframe_min not in {1, 3, 5, 10, 15, 30, 60, 120, 240, 360, 720, 1440}):
        raise ValueError("T bar timeframe is not in the frozen R005 timeframe set")
    expected_macro_min = max(240, 4 * timeframe_min)
    if (isinstance(macro_timeframe_min, bool) or not isinstance(macro_timeframe_min, int)
            or macro_timeframe_min != expected_macro_min):
        raise ValueError("BTC macro timeframe must equal max(240m, 4 x T)")
    if t_close % (timeframe_min * 60_000) != 0:
        raise ValueError("T bar close must align to its UTC timeframe boundary")
    if t_open != t_close - timeframe_min * 60_000:
        raise ValueError("T bar open/close bounds must describe exactly one full bar")
    macro_close_ms = btc_h_bar.get("bar_close_ms")
    macro_open_ms = btc_h_bar.get("bar_open_ms")
    if (isinstance(macro_close_ms, bool) or not isinstance(macro_close_ms, int)
            or isinstance(macro_open_ms, bool) or not isinstance(macro_open_ms, int)
            or macro_close_ms % (macro_timeframe_min * 60_000) != 0
            or macro_close_ms > decision_event_ms
            or macro_open_ms != macro_close_ms - macro_timeframe_min * 60_000):
        raise ValueError("BTC macro close must be a completed UTC timeframe boundary")
    symbol = t_bar.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("T bar requires a symbol")
    if btc_h_bar.get("symbol") != "BTCUSDT":
        raise ValueError("macro bar must be BTCUSDT")
    if not _finite_number(decision_receive_monotonic_s):
        raise ValueError("decision receive-time anchor must be finite")
    if (not _finite_number(aggression_percentile)
            or aggression_percentile not in AGGRESSION_PERCENTILES):
        raise ValueError("aggression percentile must be one of the frozen 80/90/95 thresholds")
    if (isinstance(minimum_aggression_history_n, bool)
            or not isinstance(minimum_aggression_history_n, int)
            or minimum_aggression_history_n < 1):
        raise ValueError("minimum aggression history count must be a positive integer")
    if (not _finite_number(minimum_replenishment_ratio)
            or minimum_replenishment_ratio not in REPLENISHMENT_THRESHOLDS):
        raise ValueError("replenishment threshold must be one of the frozen 0.5/1.0/1.5 values")
    if not isinstance(prior_aggression_observations, list):
        raise ValueError("prior aggression observations must be a list")
    if not _finite_number(tick_size) or tick_size <= 0:
        raise ValueError("tick size must be finite and positive")

    rejects = {
        "t_bar_unavailable": 0,
        "higher_timeframe_unavailable": 0,
        "no_directional_macro_regime": 0,
        "window_not_eligible": 0,
        "wrong_symbol": 0,
        "insufficient_prior_aggression_history": 0,
        "no_qualifying_event": 0,
    }
    if not _completed_feature_available(
        t_bar, decision_event_ms=decision_event_ms,
        decision_receive_monotonic_s=decision_receive_monotonic_s,
    ):
        rejects["t_bar_unavailable"] = len(windows) or 1
        return [], rejects
    if not _completed_feature_available(
        btc_h_bar, decision_event_ms=decision_event_ms,
        decision_receive_monotonic_s=decision_receive_monotonic_s,
    ):
        rejects["higher_timeframe_unavailable"] = len(windows) or 1
        return [], rejects

    close = btc_h_bar.get("close")
    ema50 = btc_h_bar.get("ema50")
    ema50_5_bars_ago = btc_h_bar.get("ema50_5_bars_ago")
    if not all(_finite_number(x) for x in (close, ema50, ema50_5_bars_ago)):
        rejects["higher_timeframe_unavailable"] = len(windows) or 1
        return [], rejects
    long_regime = close > ema50 and ema50 > ema50_5_bars_ago
    short_regime = close < ema50 and ema50 < ema50_5_bars_ago
    if not long_regime and not short_regime:
        rejects["no_directional_macro_regime"] = len(windows) or 1
        return [], rejects

    eligible, eligibility_rejects = eligible_windows_for_completed_bar(
        windows, bar_open_ms=t_open, bar_close_ms=t_close,
        decision_receive_monotonic_s=decision_receive_monotonic_s,
    )
    rejects["window_not_eligible"] = sum(eligibility_rejects.values())
    matching_symbol = []
    for window in eligible:
        if window.get("symbol") == symbol:
            matching_symbol.append(window)
        else:
            rejects["wrong_symbol"] += 1
    eligible = matching_symbol
    eligible.sort(key=lambda row: row["window_start_ms"])
    for window in eligible:
        # The endpoint used in the feature must already exist by event time too.
        refill = window.get("d_plus_2s")
        if not isinstance(refill, dict) or not _finite_number(refill.get("event_ms")):
            rejects["no_qualifying_event"] += 1
            continue
        if refill["event_ms"] > decision_event_ms:
            rejects["no_qualifying_event"] += 1
            continue
        side = "long" if long_regime else "short"
        if side == "long":
            aggression = window.get("sell_aggressor_quote_volume")
            replenishment = window.get("bid_replenishment_ratio")
            adverse_price = window.get("trade_low")
            stop_price = (adverse_price - tick_size) if _finite_number(adverse_price) else None
        else:
            aggression = window.get("buy_aggressor_quote_volume")
            replenishment = window.get("ask_replenishment_ratio")
            adverse_price = window.get("trade_high")
            stop_price = (adverse_price + tick_size) if _finite_number(adverse_price) else None
        aggression_quote_threshold, history_n = prior_aggression_threshold(
            prior_aggression_observations,
            symbol=symbol,
            direction=side,
            anchor_event_ms=window["window_start_ms"],
            percentile=aggression_percentile,
            lookback_ms=AGGRESSION_LOOKBACK_MS,
            minimum_history_n=minimum_aggression_history_n,
        )
        if aggression_quote_threshold is None:
            rejects["insufficient_prior_aggression_history"] += 1
            continue
        if (not _finite_number(aggression) or aggression < aggression_quote_threshold
                or not _finite_number(replenishment)
                or replenishment < minimum_replenishment_ratio
                or not _finite_number(stop_price) or stop_price <= 0):
            rejects["no_qualifying_event"] += 1
            continue
        return [{
            "symbol": window.get("symbol"),
            "side": side,
            "timeframe_bar_open_ms": t_open,
            "timeframe_bar_close_ms": t_close,
            "window_start_ms": window["window_start_ms"],
            "window_end_ms": window["window_end_ms"],
            "signal_event_ms": decision_event_ms,
            "signal_receive_monotonic_s": decision_receive_monotonic_s,
            "macro_bar_close_ms": btc_h_bar["bar_close_ms"],
            "macro_regime": "long" if long_regime else "short",
            "aggression_quote_volume": aggression,
            "aggression_quote_threshold": aggression_quote_threshold,
            "aggression_percentile": aggression_percentile,
            "aggression_lookback_ms": AGGRESSION_LOOKBACK_MS,
            "aggression_history_n": history_n,
            "replenishment_ratio": replenishment,
            "minimum_replenishment_ratio": minimum_replenishment_ratio,
            "stop_price_pre_entry": stop_price,
            "entry_price": None,
            "target_price": None,
            "candidate_status": "awaiting_executable_post_signal_quote",
        }], rejects
    return [], rejects
