import numpy as np

from chart_predictor.crypto_divergence_engine import (
    Bars, MINUTE_MS, aggregate_complete_minutes, closed_4h_regime,
    contiguous_slices, evaluate_divergence_event, matched_baseline_sides,
)


def test_aggregation_discards_incomplete_bucket_without_bridging():
    ts = np.array([0, 60_000, 180_000, 240_000, 300_000, 360_000], dtype=np.int64)
    close = np.array([10, 11, 13, 14, 15, 16], dtype=float)
    bars = aggregate_complete_minutes(ts, close, close + 1, close - 1,
                                      close, np.ones(len(ts)), 2)
    assert bars.open_ms.tolist() == [0, 240_000]
    assert bars.open.tolist() == [10, 14]
    assert bars.close.tolist() == [11, 15]
    assert bars.high.tolist() == [12, 16]
    assert bars.low.tolist() == [9, 13]
    assert bars.volume.tolist() == [2, 2]


def test_aggregation_rejects_duplicate_or_off_minute_timestamps():
    x = np.array([1.0, 2.0])
    for ts in ([0, 0], [1, 60_001]):
        try:
            aggregate_complete_minutes(ts, x, x, x, x, x, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid minute timestamps were accepted")


def test_contiguous_slices_never_allow_indicators_to_bridge_a_gap():
    ts = np.array([0, 60_000, 180_000, 240_000, 300_000], dtype=np.int64)
    assert contiguous_slices(ts, 1) == [slice(0, 2), slice(2, 5)]


def test_baselines_are_deterministic_and_zero_momentum_uses_hash_fallback():
    a = matched_baseline_sides(100, 100, symbol="BTCUSDT", timeframe_minutes=5,
                               anchor_ms=123456, seed=17)
    b = matched_baseline_sides(100, 100, symbol="BTCUSDT", timeframe_minutes=5,
                               anchor_ms=123456, seed=17)
    assert a == b
    assert set(a.values()) <= {"long", "short"}
    assert matched_baseline_sides(99, 100, symbol="BTCUSDT", timeframe_minutes=5,
                                  anchor_ms=123456)["momentum"] == "long"


def test_mirrored_fair_direction_barriers_cannot_both_win_on_one_path():
    rng = np.random.default_rng(20261119)
    for _ in range(250):
        count = 12
        opens = np.empty(count, dtype=float)
        highs = np.empty(count, dtype=float)
        lows = np.empty(count, dtype=float)
        closes = np.empty(count, dtype=float)
        opens[0] = closes[0] = 100.0
        highs[0], lows[0] = 100.1, 99.9
        for i, move in enumerate(rng.normal(0.0, 0.015, count - 1), start=1):
            opens[i] = closes[i - 1]
            closes[i] = opens[i] * np.exp(move)
            wick_up, wick_down = np.abs(rng.normal(0.0, 0.003, 2))
            highs[i] = max(opens[i], closes[i]) * np.exp(wick_up)
            lows[i] = min(opens[i], closes[i]) * np.exp(-wick_down)

        path = Bars(np.arange(count, dtype=np.int64) * MINUTE_MS,
                    opens.copy(), highs.copy(), lows.copy(), closes.copy(),
                    np.ones(count))
        for target_r in (1.0, 1.5, 2.0, 3.0):
            wins = []
            for side, stop in (("long", 99.0), ("short", 101.0)):
                outcome = evaluate_divergence_event(
                    minute_open_ms=path.open_ms, minute_opens=path.open,
                    minute_highs=path.high, minute_lows=path.low,
                    minute_closes=path.close, native_bars=path,
                    native_tf_minutes=1, signal_index=0, side=side,
                    pivot_stop=stop, atr_at_signal=1.0, stop_buffer_atr=0.0,
                    target_r=target_r, horizon_bars=10, entry_mode="next_open",
                    fee_per_side=0.0, slippage_per_side=0.0)
                assert outcome["status"] != "unresolved"
                wins.append(bool(outcome["target_first"]))
            assert sum(wins) <= 1


def test_sha_fair_direction_is_balanced_and_independent_on_fixed_anchors():
    future = np.random.default_rng(20261120).normal(size=20_000)
    sides = np.empty(future.size, dtype=float)
    i = 0
    for symbol_i in range(20):
        symbol = f"SYNTH{symbol_i:02d}"
        for anchor_i in range(1_000):
            side = matched_baseline_sides(
                99, 100, symbol=symbol, timeframe_minutes=5,
                anchor_ms=anchor_i * 5 * MINUTE_MS, seed=20261117)["random"]
            sides[i] = 1.0 if side == "long" else -1.0
            i += 1
    assert abs(float(sides.mean())) < 0.03
    assert abs(float(np.corrcoef(sides, future)[0, 1])) < 0.03


def test_closed_4h_regime_only_appears_after_200_closed_bars():
    count = 201 * 240
    ts = np.arange(count, dtype=np.int64) * MINUTE_MS
    close = np.repeat(np.arange(1000, 1201, dtype=float), 240)
    native = np.array([199 * 240 * MINUTE_MS, 200 * 240 * MINUTE_MS], dtype=np.int64)
    regime = closed_4h_regime(ts, close, native, 240)
    assert regime.tolist() == [1, 1]
    before = closed_4h_regime(ts, close, np.array([198 * 240 * MINUTE_MS]), 240)
    assert before.tolist() == [0]


def test_missing_4h_interval_resets_macro_warmup_without_forward_fill():
    count = 203 * 240
    ts = np.arange(count, dtype=np.int64) * MINUTE_MS
    close = np.repeat(np.arange(1000, 1203, dtype=float), 240)
    missing = 201 * 240 + 17
    ts = np.delete(ts, missing)
    close = np.delete(close, missing)
    native = np.array([200 * 240 * MINUTE_MS, 202 * 240 * MINUTE_MS], dtype=np.int64)
    regime = closed_4h_regime(ts, close, native, 240)
    assert regime.tolist() == [1, 0]


def _native(tf=1, count=14, *, signal_high=102):
    opens = np.full(count, 100.0)
    highs = np.full(count, 101.0)
    lows = np.full(count, 99.0)
    closes = np.full(count, 100.0)
    highs[0] = signal_high
    return Bars(np.arange(count, dtype=np.int64) * tf * MINUTE_MS,
                opens, highs, lows, closes, np.ones(count))


def _event(native, high, low, *, entry_mode="next_open", side="long"):
    times = native.open_ms[0] + np.arange(13, dtype=np.int64) * MINUTE_MS
    opens = np.full(13, 100.0)
    highs = np.full(13, 101.0)
    lows = np.full(13, 99.0)
    closes = np.full(13, 100.0)
    if side == "long":
        lows[0] = 99
        highs[0] = high
        highs[2] = 115 if entry_mode == "next_open" else native.high[2]
        lows[2] = low
    else:
        highs[0] = 101
        lows[0] = 98
        lows[2] = 85
        highs[2] = 101
    return evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side=side,
        pivot_stop=90 if side == "long" else 110, atr_at_signal=2,
        stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode=entry_mode, fee_per_side=0, slippage_per_side=0)


def test_next_open_target_first_has_realized_trade_net_r():
    result = _event(_native(), 102, 99)
    assert result["status"] == "target"
    assert result["target_first"] is True
    assert result["entry_price"] == 100
    assert result["trade_net_r"] == 1


def test_next_open_rejects_mismatched_native_and_minute_execution_prices():
    native = _native()
    times = np.arange(13, dtype=np.int64) * MINUTE_MS
    opens = np.full(13, 100.0)
    highs = np.full(13, 101.0)
    lows = np.full(13, 99.0)
    closes = np.full(13, 100.0)
    # Deliberately corrupt the execution-level open while leaving the native
    # candle's open unchanged. A target touch later must not rescue this path.
    opens[1], highs[1], lows[1], closes[1] = 101.0, 102.0, 100.5, 101.0
    highs[2] = 111.0
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="long", pivot_stop=90,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == "unresolved"
    assert result["target_first"] is None
    assert result["trade_net_r"] is None


def test_short_target_first_is_mirrored_and_costs_reduce_net_r():
    native = _native()
    times = np.arange(13, dtype=np.int64) * MINUTE_MS
    opens = np.full(13, 100.0)
    highs = np.full(13, 101.0)
    lows = np.full(13, 99.0)
    closes = np.full(13, 100.0)
    lows[1] = 89
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="short", pivot_stop=110,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == "target"
    assert result["target_first"] is True
    assert result["trade_net_r"] == 1

    charged = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="short", pivot_stop=110,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0.0005,
        slippage_per_side=0.00025)
    assert charged["trade_net_r"] < result["trade_net_r"]


def test_stop_entry_gap_and_expiry_are_explicit_no_trade_failures():
    native = _native()
    native.high[2] = 115
    result = _event(native, 102, 99, entry_mode="stop_entry")
    assert result["status"] == "target"
    assert result["entry_price"] == 102
    assert result["target_first"] is True

    native.high[1:4] = 101
    result = _event(native, 102, 99, entry_mode="stop_entry")
    assert result["status"] == "expired"
    assert result["target_first"] is False
    assert result["trade_net_r"] is None


def test_stop_entry_open_gap_fills_before_testing_bar_extremes():
    native = _native()
    native.open[1] = 103
    times = np.arange(13, dtype=np.int64) * MINUTE_MS
    opens = np.full(13, 100.0); opens[1] = 103
    highs = np.full(13, 101.0); highs[0] = 102; highs[1] = 104; highs[2] = 120
    lows = np.full(13, 99.0); lows[1] = 95
    closes = np.full(13, 100.0)
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="long", pivot_stop=90,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="stop_entry", fee_per_side=0, slippage_per_side=0)
    assert result["entry_price"] == 103
    assert result["status"] == "target"


def test_same_minute_stop_target_tie_resolves_stop_first():
    native = _native()
    times = np.arange(13, dtype=np.int64) * MINUTE_MS
    opens = np.full(13, 100.0)
    highs = np.full(13, 101.0)
    lows = np.full(13, 99.0)
    closes = np.full(13, 100.0)
    highs[1] = 111
    lows[1] = 89
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="long", pivot_stop=90,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == "stop"
    assert result["target_first"] is False
    assert result["trade_net_r"] == -1


def test_missing_outcome_minute_is_unresolved_not_success_or_failure():
    native = _native()
    times = np.delete(np.arange(13, dtype=np.int64) * MINUTE_MS, 5)
    vals = np.full(len(times), 100.0)
    result = evaluate_divergence_event(
        minute_open_ms=times, minute_opens=vals, minute_highs=vals + 1,
        minute_lows=vals - 1, minute_closes=vals, native_bars=native,
        native_tf_minutes=1, signal_index=0, side="long", pivot_stop=90,
        atr_at_signal=2, stop_buffer_atr=0, target_r=1, horizon_bars=10,
        entry_mode="next_open", fee_per_side=0, slippage_per_side=0)
    assert result["status"] == "unresolved"
    assert result["target_first"] is None
    assert result["trade_net_r"] is None
