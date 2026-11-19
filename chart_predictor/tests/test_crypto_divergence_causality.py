"""Synthetic future-injection coverage for the registered divergence grid."""
import numpy as np
import pytest

from chart_predictor import indicators
from chart_predictor.crypto_divergence_backtest import (
    HORIZONS, LAGS, OSCILLATORS, TIMEFRAMES, _bars_for_tf, _event_bars,
    _events_by_lag, _label,
)
from chart_predictor.crypto_divergence_engine import (
    MINUTE_MS, aggregate_complete_minutes, closed_4h_regime,
)


def _signal_signature(events, before_index):
    return [(
        row["index"], row["local_index"], row["lag"], row["side"],
        row["pivot_stop"], row["atr"], row["signal_ms"],
        row["signal_close"], row["oscillator"],
    ) for row in events if row["index"] < before_index]


def _synthetic_native(tf, count=1500):
    i = np.arange(count)
    close = 100 + 0.006 * i + 5 * np.sin(i * 0.11) + 0.6 * np.sin(i * 0.71)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.4 + 0.2 * np.sin(i)
    low = np.minimum(open_, close) - 0.4 - 0.2 * np.cos(i)
    minute_in_bar = np.tile(np.arange(tf, dtype=float), count)
    repeated_open = np.repeat(open_, tf)
    repeated_close = np.repeat(close, tf)
    minute_open = repeated_open + (repeated_close - repeated_open) * minute_in_bar / tf
    minute_close = repeated_open + (repeated_close - repeated_open) * (minute_in_bar + 1) / tf
    minute_high = np.maximum(minute_open, minute_close) + np.repeat(
        high - np.maximum(open_, close), tf)
    minute_low = np.minimum(minute_open, minute_close) - np.repeat(
        np.minimum(open_, close) - low, tf)
    minute_ts = np.arange(count * tf, dtype=np.int64) * MINUTE_MS
    return (minute_ts, minute_open, minute_high, minute_low, minute_close,
            np.ones(count * tf, dtype=float))


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_aggregation_prefix_is_invariant_at_partial_and_closed_bar_boundaries(tf):
    count = 12 * tf
    minute_ts = np.arange(count, dtype=np.int64) * MINUTE_MS
    close = 100 + np.arange(count, dtype=float) * 0.01
    open_ = close.copy()
    high, low = close + 0.1, close - 0.1
    volume = np.ones(count)

    for cutoff in (6 * tf - 1, 6 * tf, 6 * tf + 1):
        changed = close.copy()
        changed[cutoff:] += 500
        first = aggregate_complete_minutes(minute_ts, open_, high, low, close, volume, tf)
        second = aggregate_complete_minutes(minute_ts, open_ + (changed-close), high + (changed-close),
                                             low + (changed-close), changed, volume, tf)
        complete = first.open_ms + tf * MINUTE_MS <= cutoff * MINUTE_MS
        for field in ("open_ms", "open", "high", "low", "close", "volume"):
            np.testing.assert_array_equal(getattr(second, field)[complete],
                                          getattr(first, field)[complete])


@pytest.mark.parametrize("tf", TIMEFRAMES)
@pytest.mark.parametrize("horizon", HORIZONS)
@pytest.mark.parametrize("oscillator", OSCILLATORS)
@pytest.mark.parametrize("lag", (2, 3, 4))
def test_registered_signal_prefix_is_invariant_to_future_ohlcv(
        tf, horizon, oscillator, lag):
    """Signal generation is horizon-independent and cannot read post-anchor bars."""
    del horizon  # It is part of the registered claim grid, not signal generation.
    raw = _synthetic_native(tf)
    original = _bars_for_tf(raw, tf)
    cutoff = 1000

    changed_raw = [x.copy() for x in raw]
    cutoff_minute = cutoff * tf
    future = np.arange(len(changed_raw[4]) - cutoff_minute, dtype=float)
    shift = 40 + future * 0.03
    for field in (1, 2, 3, 4):
        changed_raw[field][cutoff_minute:] += shift
    changed = _bars_for_tf(tuple(changed_raw), tf)

    macro = np.ones(len(original.open_ms), dtype=np.int8)
    changed_macro = macro.copy()
    changed_macro[cutoff:] = -1
    before = list(_events_by_lag(original, macro, oscillator, tf))
    after = list(_events_by_lag(changed, changed_macro, oscillator, tf))

    expected = _signal_signature([row for row in before if row["lag"] == lag], cutoff)
    assert expected, "synthetic fixture must exercise emitted signals"
    assert _signal_signature([row for row in after if row["lag"] == lag], cutoff) == expected


@pytest.mark.parametrize("tf", TIMEFRAMES)
def test_closed_four_hour_regime_prefix_is_future_invariant_for_every_native_tf(tf):
    minute_count = 230 * 240
    minute_ts = np.arange(minute_count, dtype=np.int64) * MINUTE_MS
    close = np.repeat(1000.0 + np.arange(230), 240)
    cutoff = 205 * 240
    mutated_close = close.copy()
    mutated_close[cutoff:] = np.linspace(10_000, 1, len(close) - cutoff)
    native_ts = np.arange(0, minute_count - tf + 1, tf, dtype=np.int64) * MINUTE_MS

    before = closed_4h_regime(minute_ts, close, native_ts, tf)
    after = closed_4h_regime(minute_ts, mutated_close, native_ts, tf)
    prefix = native_ts + tf * MINUTE_MS <= cutoff * MINUTE_MS
    assert np.any(before[prefix] != 0)
    np.testing.assert_array_equal(after[prefix], before[prefix])


def _raw_execution_path(tf, horizon, *, target_touch=False, change_after_deadline=False):
    count = (horizon + 2) * tf
    ts = np.arange(count, dtype=np.int64) * MINUTE_MS
    opens = np.full(count, 100.0)
    highs = np.full(count, 101.0)
    lows = np.full(count, 99.0)
    closes = np.full(count, 100.0)
    if target_touch:
        highs[tf] = 111.0
    if change_after_deadline:
        deadline = (horizon + 1) * tf
        opens[deadline:] = 150.0
        highs[deadline:] = 160.0
        lows[deadline:] = 140.0
        closes[deadline:] = 155.0
    return ts, opens, highs, lows, closes, np.ones(count)


@pytest.mark.parametrize("tf", TIMEFRAMES)
@pytest.mark.parametrize("horizon", HORIZONS)
def test_registered_execution_horizons_keep_entry_causal_and_ignore_post_deadline(
        tf, horizon):
    raw = _raw_execution_path(tf, horizon)
    native = aggregate_complete_minutes(*raw, tf)
    event = {"side": "long", "local_index": 0, "pivot_stop": 90.0, "atr": 1.0}
    params = {"entry": "next_open", "stop_buffer_atr": 0.0, "target_r": 1.0}

    timeout = _label(raw, native, tf, event, horizon=horizon, params=params)
    path_hit = _raw_execution_path(tf, horizon, target_touch=True)
    hit_native = aggregate_complete_minutes(*path_hit, tf)
    hit = _label(path_hit, hit_native, tf, event, horizon=horizon, params=params)
    assert timeout["status"] == "timeout"
    assert hit["status"] == "target"
    assert (hit["entry_ms"], hit["entry_price"]) == (
        timeout["entry_ms"], timeout["entry_price"])

    tail_changed = _raw_execution_path(tf, horizon, change_after_deadline=True)
    tail_native = aggregate_complete_minutes(*tail_changed, tf)
    tail = _label(tail_changed, tail_native, tf, event, horizon=horizon, params=params)
    assert tail == timeout


@pytest.mark.parametrize("tf", TIMEFRAMES)
@pytest.mark.parametrize("horizon", HORIZONS)
@pytest.mark.parametrize("oscillator", OSCILLATORS)
@pytest.mark.parametrize("lag", LAGS)
@pytest.mark.parametrize("side", ("long", "short"))
def test_connected_signal_entry_and_target_path_is_causal(
        tf, horizon, oscillator, lag, side):
    raw = _synthetic_native(tf)
    bars = _bars_for_tf(raw, tf)
    direction = 1 if side == "long" else -1
    macro = np.full(len(bars.open_ms), direction, dtype=np.int8)
    events = list(_events_by_lag(bars, macro, oscillator, tf))
    candidates = [event for event in events
                  if event["lag"] == lag
                  and event["side"] == side
                  and event["local_index"] + horizon + 1 < len(bars.open_ms)]
    event = next((item for item in candidates
                  if ((bars.open[item["local_index"] + 1] > item["pivot_stop"])
                      if side == "long" else
                      (bars.open[item["local_index"] + 1] < item["pivot_stop"]))), None)
    assert event is not None, "synthetic path must contain an executable registered signal"

    stop = event["pivot_stop"]
    entry_index = event["local_index"] + 1
    entry = float(bars.open[entry_index])
    risk = abs(entry - stop)
    target = entry + risk if side == "long" else entry - risk
    first_minute = int(bars.open_ms[entry_index] // MINUTE_MS)
    mutated = [array.copy() for array in raw]
    path_end = first_minute + horizon * tf
    mutated[1][first_minute:path_end] = entry
    mutated[2][first_minute:path_end] = entry + 0.2 * risk
    mutated[3][first_minute:path_end] = entry - 0.2 * risk
    mutated[4][first_minute:path_end] = entry
    if side == "long":
        mutated[2][first_minute] = target
    else:
        mutated[3][first_minute] = target

    changed_raw = tuple(mutated)
    changed_bars = _bars_for_tf(changed_raw, tf)
    changed_macro = macro.copy()
    changed_events = list(_events_by_lag(changed_bars, changed_macro, oscillator, tf))
    prefix_limit = event["index"] + 1
    assert _signal_signature(events, prefix_limit) == _signal_signature(
        changed_events, prefix_limit)

    params = {"entry": "next_open", "stop_buffer_atr": 0.0, "target_r": 1.0}
    original_outcome = _label(raw, _event_bars(bars, event["segment"]), tf,
                              event, horizon=horizon, params=params)
    changed_outcome = _label(changed_raw,
                             _event_bars(changed_bars, event["segment"]), tf,
                             event, horizon=horizon, params=params)
    assert changed_outcome["status"] == "target"
    assert changed_outcome["entry_ms"] == original_outcome["entry_ms"]
    assert changed_outcome["entry_price"] == original_outcome["entry_price"]


@pytest.mark.parametrize("tf", TIMEFRAMES)
@pytest.mark.parametrize("horizon", HORIZONS)
def test_future_injection_control_is_detected_by_registered_signal_path(tf, horizon):
    raw = _synthetic_native(tf)
    base = _bars_for_tf(raw, tf)
    changed_raw = [x.copy() for x in raw]
    cutoff = 1000
    cutoff_minute = cutoff * tf
    # Force the future suffix to reverse the sign of the full-sample return
    # while keeping all prices positive and each OHLC bar internally valid.
    for field in (1, 2, 3, 4):
        changed_raw[field][cutoff_minute:] -= 60
    changed = _bars_for_tf(tuple(changed_raw), tf)

    # Negative control: deliberately use the full-sample return as a macro
    # feature. Mutating only post-cutoff bars must flip this leaky prefix.
    leaked_base = np.full(
        len(base.open_ms), 1 if base.close[-1] > base.close[0] else -1,
        dtype=np.int8)
    leaked_changed = np.full(
        len(changed.open_ms), 1 if changed.close[-1] > changed.close[0] else -1,
        dtype=np.int8)
    assert leaked_base[cutoff - horizon] != leaked_changed[cutoff - horizon]
    baseline_events = list(_events_by_lag(base, leaked_base, "rsi14", tf))
    mutated_events = list(_events_by_lag(changed, leaked_changed, "rsi14", tf))
    baseline_prefix = _signal_signature(baseline_events, cutoff)
    mutated_prefix = _signal_signature(mutated_events, cutoff)
    assert baseline_prefix, "fixture must emit a signal before the mutation boundary"
    assert mutated_prefix != baseline_prefix
