"""Causal candidate construction for the frozen R005 L2 hypothesis.

This module emits unfilled research candidates only. It does not derive
thresholds, estimate execution, label outcomes, or place orders.
"""
from __future__ import annotations

import math
import hashlib
import json
from typing import Any

from scripts.research.crypto_l2_windows import (
    aggregation_code_sha256,
    aggregation_run_id_for,
    eligible_windows_for_completed_bar,
    manifest_integrity_sha256,
)

AGGRESSION_LOOKBACK_MS = 30 * 24 * 60 * 60 * 1000
AGGRESSION_PERCENTILES = {0.80, 0.90, 0.95}
REPLENISHMENT_THRESHOLDS = {0.5, 1.0, 1.5}


def _finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _window_rows_sha256(windows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for window in windows:
        line = json.dumps(window, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode() + b"\n"
        digest.update(line)
    return digest.hexdigest()


def prior_aggression_threshold(
    observations: list[dict[str, Any]], *, symbol: str, direction: str,
    anchor_event_ms: int, anchor_received_at_ms: int,
    anchor_receive_monotonic_s: float, anchor_receive_clock_domain: str,
    percentile: float, lookback_ms: int,
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
    if (isinstance(anchor_received_at_ms, bool) or not isinstance(anchor_received_at_ms, int)
            or anchor_received_at_ms < 0):
        raise ValueError("anchor receive time must be non-negative integer wall-clock milliseconds")
    if not _finite_number(anchor_receive_monotonic_s) or anchor_receive_monotonic_s < 0:
        raise ValueError("anchor monotonic receive time must be finite and non-negative")
    if not isinstance(anchor_receive_clock_domain, str) or not anchor_receive_clock_domain:
        raise ValueError("anchor receive clock domain must be a non-empty string")
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
        received_at_ms = row.get("feature_available_received_at_ms")
        if (isinstance(received_at_ms, bool) or not isinstance(received_at_ms, int)
                or received_at_ms < 0):
            raise ValueError("matching prior observations require receive-time availability")
        if received_at_ms >= anchor_received_at_ms:
            continue
        if row.get("feature_receive_clock_domain") != anchor_receive_clock_domain:
            # Monotonic clocks are only comparable within an explicitly shared domain.
            # Cross-domain wall-clock use remains disabled until clock-sync evidence is supplied.
            continue
        available_mono = row.get("feature_available_receive_monotonic_s")
        if not _finite_number(available_mono):
            raise ValueError("same-domain prior observations require monotonic availability")
        if available_mono >= anchor_receive_monotonic_s:
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
                                 decision_receive_monotonic_s: float,
                                 decision_received_at_ms: int,
                                 decision_receive_clock_domain: str) -> bool:
    close_ms = bar.get("bar_close_ms")
    available = bar.get("feature_available_receive_monotonic_s")
    available_wall = bar.get("feature_available_received_at_ms")
    return (
        bar.get("completed") is True
        and isinstance(close_ms, int) and not isinstance(close_ms, bool)
        and close_ms <= decision_event_ms
        and _finite_number(available)
        and available < decision_receive_monotonic_s
        and isinstance(available_wall, int) and not isinstance(available_wall, bool)
        and available_wall < decision_received_at_ms
        and bar.get("feature_receive_clock_domain") == decision_receive_clock_domain
    )


def build_candidates_for_completed_bar(
    windows: list[dict[str, Any]], *,
    t_bar: dict[str, Any],
    btc_h_bar: dict[str, Any],
    decision_event_ms: int,
    decision_receive_monotonic_s: float,
    decision_received_at_ms: int,
    decision_receive_clock_domain: str,
    aggregation_manifest: dict[str, Any],
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
    executable post-signal quote is replayed. `windows` must be the complete,
    ordered JSONL output represented by `aggregation_manifest`; chunked/sharded
    candidate replay is not implemented by this prototype.
    """
    required_ints = (decision_event_ms, decision_received_at_ms, t_bar.get("bar_open_ms"),
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
    if not isinstance(decision_receive_clock_domain, str) or not decision_receive_clock_domain:
        raise ValueError("decision receive clock domain must be a non-empty string")
    if not isinstance(windows, list) or any(not isinstance(row, dict) for row in windows):
        raise ValueError("windows must be a complete list of aggregation rows")
    if not isinstance(aggregation_manifest, dict):
        raise ValueError("aggregation manifest is required for candidate gating")
    claimed_manifest_hash = aggregation_manifest.get("manifest_integrity_sha256")
    if (not isinstance(claimed_manifest_hash, str) or len(claimed_manifest_hash) != 64
            or any(char not in "0123456789abcdef" for char in claimed_manifest_hash)
            or claimed_manifest_hash != manifest_integrity_sha256(aggregation_manifest)):
        raise ValueError("aggregation manifest integrity hash does not match its contents")
    raw_invalidations = aggregation_manifest.get("late_invalidated_windows")
    if not isinstance(raw_invalidations, list):
        raise ValueError("aggregation manifest requires late_invalidated_windows")
    invalidated_window_keys: set[tuple[str, int]] = set()
    for invalidation in raw_invalidations:
        if (not isinstance(invalidation, dict)
                or not isinstance(invalidation.get("symbol"), str)
                or isinstance(invalidation.get("window_start_ms"), bool)
                or not isinstance(invalidation.get("window_start_ms"), int)):
            raise ValueError("aggregation manifest contains malformed invalidation")
        invalidated_window_keys.add((invalidation["symbol"], invalidation["window_start_ms"]))
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
        "aggregation_quality_failure": 0,
    }
    quality_counters = {}
    for field in ("late_input_rows", "global_disconnect_events", "unknown_time_feed_events"):
        value = aggregation_manifest.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"aggregation manifest requires valid {field}")
        quality_counters[field] = value
    computed_quality_pass = all(value == 0 for value in quality_counters.values())
    quality_pass = aggregation_manifest.get("quality_pass")
    if not isinstance(quality_pass, bool) or quality_pass is not computed_quality_pass:
        raise ValueError("aggregation manifest quality flag contradicts quality counters")
    if not computed_quality_pass:
        rejects["aggregation_quality_failure"] = len(windows) or 1
        return [], rejects
    aggregation_run_id = aggregation_manifest.get("aggregation_run_id")
    if not isinstance(aggregation_run_id, str) or not aggregation_run_id:
        raise ValueError("aggregation manifest requires a run identity")
    for hash_field in ("source_sha256", "output_sha256", "aggregator_code_sha256"):
        digest = aggregation_manifest.get(hash_field)
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise ValueError(f"aggregation manifest requires valid {hash_field}")
    if aggregation_manifest["aggregator_code_sha256"] != aggregation_code_sha256():
        raise ValueError("aggregation manifest code hash does not match current aggregator")
    run_settings = {
        "allowed_lateness_ms": aggregation_manifest.get("allowed_lateness_ms"),
        "window_ms": aggregation_manifest.get("window_ms"),
        "refill_observation_ms": aggregation_manifest.get("refill_observation_ms"),
        "max_depth_endpoint_age_ms": aggregation_manifest.get("max_depth_endpoint_age_ms"),
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in run_settings.values()):
        raise ValueError("aggregation manifest requires valid run settings")
    expected_run_id = aggregation_run_id_for(
        source_sha256=aggregation_manifest["source_sha256"],
        aggregator_code_sha256=aggregation_manifest["aggregator_code_sha256"],
        **run_settings,
    )
    if aggregation_run_id != expected_run_id:
        raise ValueError("aggregation run identity does not match manifest provenance")
    if _window_rows_sha256(windows) != aggregation_manifest["output_sha256"]:
        raise ValueError("window rows do not match aggregation manifest output hash")
    for window in windows:
        claimed_hash = window.get("aggregation_row_sha256")
        if window.get("aggregation_run_id") != aggregation_run_id or not isinstance(claimed_hash, str):
            raise ValueError("window provenance does not match aggregation manifest")
        unhashed = {key: value for key, value in window.items()
                    if key != "aggregation_row_sha256"}
        actual_hash = hashlib.sha256(json.dumps(
            unhashed, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest()
        if claimed_hash != actual_hash:
            raise ValueError("window row hash does not match aggregation output")
    if not _completed_feature_available(
        t_bar, decision_event_ms=decision_event_ms,
        decision_receive_monotonic_s=decision_receive_monotonic_s,
        decision_received_at_ms=decision_received_at_ms,
        decision_receive_clock_domain=decision_receive_clock_domain,
    ):
        rejects["t_bar_unavailable"] = len(windows) or 1
        return [], rejects
    if not _completed_feature_available(
        btc_h_bar, decision_event_ms=decision_event_ms,
        decision_receive_monotonic_s=decision_receive_monotonic_s,
        decision_received_at_ms=decision_received_at_ms,
        decision_receive_clock_domain=decision_receive_clock_domain,
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
        decision_received_at_ms=decision_received_at_ms,
        decision_receive_clock_domain=decision_receive_clock_domain,
        invalidated_window_keys=invalidated_window_keys,
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
            anchor_received_at_ms=decision_received_at_ms,
            anchor_receive_monotonic_s=decision_receive_monotonic_s,
            anchor_receive_clock_domain=decision_receive_clock_domain,
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
            "signal_received_at_ms": decision_received_at_ms,
            "signal_receive_clock_domain": decision_receive_clock_domain,
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
