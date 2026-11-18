"""Synthetic integration checks for event entry, OHLC exits, and costs.

The oracle below is intentionally scalar and independent of the production
resolver. These fixtures contain no market data and are not strategy evidence.
"""
import numpy as np
import pytest

from chart_predictor.crypto_divergence_engine import (
    Bars, MINUTE_MS, evaluate_divergence_event,
)


def _fixture(side="long"):
    times = np.arange(13, dtype=np.int64) * MINUTE_MS
    opens = np.full(13, 100.0)
    highs = np.full(13, 101.0)
    lows = np.full(13, 99.0)
    closes = np.full(13, 100.0)
    if side == "long":
        highs[0] = 102.0
        stop = 90.0
    else:
        lows[0] = 98.0
        stop = 110.0
    native = Bars(times.copy(), opens.copy(), highs.copy(), lows.copy(),
                  closes.copy(), np.ones(13))
    return times, opens, highs, lows, closes, native, stop


def _evaluate(side, edit=None, *, fee=0.0005, slip=0.00025):
    times, opens, highs, lows, closes, native, stop = _fixture(side)
    if edit:
        edit(opens, highs, lows, closes)
        native = Bars(times.copy(), opens.copy(), highs.copy(), lows.copy(),
                      closes.copy(), np.ones(13))
    return evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side=side, pivot_stop=stop,
        atr_at_signal=2.0, stop_buffer_atr=0.0, target_r=1.0,
        horizon_bars=10, entry_mode="next_open", fee_per_side=fee,
        slippage_per_side=slip)


def _oracle(opens, highs, lows, closes, side, stop, target):
    """Independent scalar stop-first OHLC reference for a complete path."""
    for i in range(10):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if not np.isfinite([o, h, l, c]).all() or h < max(o, c) or l > min(o, c) or l > h:
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
    return "timeout", closes[9], 9


def _set_bar(index, *, open_=100, high=101, low=99, close=100):
    def edit(opens, highs, lows, closes):
        opens[index], highs[index], lows[index], closes[index] = open_, high, low, close
    return edit


@pytest.mark.parametrize(
    "side,edit,expected,price",
    [
        ("long", _set_bar(2, high=111), "target", 110),
        ("long", _set_bar(2, low=89), "stop", 90),
        ("long", _set_bar(2, open_=89, high=100, low=88, close=95), "stop", 89),
        ("long", _set_bar(2, open_=111, high=112, low=109, close=111), "target", 110),
        ("long", _set_bar(2, high=111, low=89), "stop", 90),
        ("short", _set_bar(2, low=89), "target", 90),
        ("short", _set_bar(2, high=111), "stop", 110),
        ("short", _set_bar(2, open_=111, high=112, low=100, close=105), "stop", 111),
        ("short", _set_bar(2, open_=89, high=91, low=88, close=89), "target", 90),
        ("short", _set_bar(2, high=111, low=89), "stop", 110),
    ],
)
def test_long_short_event_path_matches_independent_scalar_oracle(side, edit, expected, price):
    times, opens, highs, lows, closes, _, stop = _fixture(side)
    edit(opens, highs, lows, closes)
    target = 110.0 if side == "long" else 90.0
    oracle_status, oracle_price, oracle_i = _oracle(
        opens[1:11], highs[1:11], lows[1:11], closes[1:11], side, stop, target)
    result = _evaluate(side, edit)
    assert (oracle_status, oracle_price, oracle_i) == (expected, price, 1)
    assert result["status"] == oracle_status
    assert result["exit_price"] == oracle_price
    assert result["exit_ms"] == times[oracle_i + 1]
    assert result["entry_ms"] == times[1]
    assert result["entry_price"] == opens[1]


@pytest.mark.parametrize("fee,slip", [(0.0005, 0.00025), (0.001, 0.0005)])
def test_registered_base_and_stress_costs_match_independent_net_r(fee, slip):
    result = _evaluate("long", _set_bar(2, high=111), fee=fee, slip=slip)
    independently_computed = (
        (110.0 * (1 - fee - slip) - 100.0 * (1 + fee + slip)) / 100.0
    ) * 100.0 / 10.0
    assert result["target_first"] is True
    assert result["trade_net_r"] == pytest.approx(independently_computed, abs=1e-12)


@pytest.mark.parametrize(
    "side,trigger_edit,exit_edit,status,entry,exit_price",
    [
        ("long", _set_bar(2, high=103), _set_bar(3, high=115), "target", 102, 114),
        ("long", _set_bar(2, high=103), _set_bar(3, low=89), "stop", 102, 90),
        ("short", _set_bar(2, low=97), _set_bar(3, low=85), "target", 98, 86),
        ("short", _set_bar(2, low=97), _set_bar(3, high=111), "stop", 98, 110),
    ],
)
def test_stop_entry_uses_first_trigger_then_resolves_later_path(
        side, trigger_edit, exit_edit, status, entry, exit_price):
    times, opens, highs, lows, closes, native, stop = _fixture(side)
    trigger_edit(opens, highs, lows, closes)
    exit_edit(opens, highs, lows, closes)
    native = Bars(times.copy(), opens.copy(), highs.copy(), lows.copy(),
                  closes.copy(), np.ones(13))
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side=side, pivot_stop=stop,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="stop_entry", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == status
    assert result["entry_ms"] == times[2]
    assert result["entry_price"] == entry
    assert result["exit_price"] == exit_price
    assert result["target_first"] is (status == "target")


@pytest.mark.parametrize("missing_index", [1, 5, 10])
def test_missing_entry_interior_or_horizon_tail_is_unresolved(missing_index):
    times, opens, highs, lows, closes, native, stop = _fixture()
    keep = np.arange(13) != missing_index
    result = evaluate_divergence_event(
        minute_open_ms=times[keep], minute_opens=opens[keep],
        minute_highs=highs[keep], minute_lows=lows[keep],
        minute_closes=closes[keep], native_bars=native,
        native_tf_minutes=1, signal_index=0, side="long", pivot_stop=stop,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == "unresolved"
    assert result["target_first"] is None
    assert result["trade_net_r"] is None


@pytest.mark.parametrize("corruption", ["duplicate", "unordered", "malformed"])
def test_corrupt_time_or_ohlc_path_fails_closed(corruption):
    times, opens, highs, lows, closes, native, stop = _fixture()
    if corruption == "duplicate":
        times[5] = times[4]
    elif corruption == "unordered":
        times[5], times[6] = times[6], times[5]
    else:
        highs[2] = 98.0  # below the unchanged close at 100
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="long", pivot_stop=stop,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == "unresolved"
    assert result["target_first"] is None


def test_timeout_uses_exact_last_horizon_close_and_future_changes_not_entry():
    times, opens, highs, lows, closes, native, stop = _fixture()
    closes[10] = 105.0
    highs[10] = 105.0
    native = Bars(times.copy(), opens.copy(), highs.copy(), lows.copy(),
                  closes.copy(), np.ones(13))
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="long", pivot_stop=stop,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == "timeout"
    assert result["exit_ms"] == times[10]
    assert result["exit_price"] == 105.0
    assert result["entry_ms"] == times[1]
    assert result["entry_price"] == 100.0
    changed_future = _evaluate("long", _set_bar(2, high=111), fee=0, slip=0)
    assert changed_future["status"] == "target"
    assert changed_future["entry_ms"] == result["entry_ms"]
    assert changed_future["entry_price"] == result["entry_price"]
