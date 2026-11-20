import numpy as np

from scripts.research.pine_regime_m2_probe import (
    atr_wilder,
    build_nonoverlap_clusters,
    compute_regime,
    evaluate_m2_path,
)


def _bars(rows, start_ms=0):
    result = []
    for i, (open_, high, low, close) in enumerate(rows):
        result.append({
            "open_time_ms": start_ms + i * 3_600_000,
            "o": open_,
            "h": high,
            "l": low,
            "c": close,
        })
    return result


def test_pine_early_fallbacks_and_first_state_match_source_order():
    actual = compute_regime(
        high=np.array([101.0]),
        low=np.array([99.0]),
        close=np.array([100.0]),
    )

    assert actual["er"][0] == 0.0
    assert actual["fdi"][0] == 1.5
    assert actual["chop"][0] == 50.0
    np.testing.assert_allclose(actual["score"][0], 0.25)
    assert actual["labels"][0] == "Range"
    assert not actual["to_trend"][0]


def test_zero_er_denominator_uses_zero_fallback():
    actual = compute_regime(
        high=np.full(40, 100.0),
        low=np.full(40, 100.0),
        close=np.full(40, 100.0),
    )

    assert np.all(actual["er"] == 0.0)
    assert np.all(np.isfinite(actual["score"]))


def test_regime_features_are_prefix_invariant_and_ignore_future_mutation():
    n = 180
    close = 100.0 + np.cumsum(np.sin(np.arange(n) / 5.0) * 0.2 + 0.03)
    high = close + 0.4
    low = close - 0.4
    cutoff = 97
    prefix = compute_regime(high[:cutoff], low[:cutoff], close[:cutoff])
    full = compute_regime(high, low, close)
    mutated_high, mutated_low, mutated_close = high.copy(), low.copy(), close.copy()
    mutated_high[cutoff:] += 500
    mutated_low[cutoff:] -= 300
    mutated_close[cutoff:] *= 1.7
    future_mutated = compute_regime(mutated_high, mutated_low, mutated_close)

    for key in ("er", "fdi", "chop", "score", "labels", "to_trend"):
        np.testing.assert_equal(prefix[key], full[key][:cutoff])
        np.testing.assert_equal(prefix[key], future_mutated[key][:cutoff])


def test_wilder_atr_uses_sma_seed_then_recursion():
    high = np.full(18, 101.0)
    low = np.full(18, 99.0)
    close = np.full(18, 100.0)

    actual = atr_wilder(high, low, close, period=14)

    assert np.isnan(actual[:13]).all()
    assert actual[13] == 2.0
    np.testing.assert_allclose(actual[14:], 2.0)


def test_same_bar_stop_and_target_is_stop_first():
    bars = _bars([(100, 103, 98, 101)] + [(101, 101, 101, 101)] * 19)

    result = evaluate_m2_path("LONG", 100.0, 1.0, bars, [], [], fee_rate=0.001)

    assert result["reason"] == "STOP"
    assert result["m2_hit"] is False
    assert result["exit_price"] == 99.0


def test_gap_stop_fills_at_adverse_open_and_timeout_is_failure():
    gap_bars = _bars([(97, 100, 96, 98)] + [(98, 98, 98, 98)] * 19)
    timeout_bars = _bars([(100, 100.5, 99.5, 100.2)] * 20)

    gap = evaluate_m2_path("LONG", 100.0, 1.0, gap_bars, [], [], fee_rate=0.0)
    timeout = evaluate_m2_path("LONG", 100.0, 1.0, timeout_bars, [], [], fee_rate=0.0)

    assert gap["reason"] == "STOP_GAP"
    assert gap["exit_price"] == 97.0
    assert timeout["reason"] == "TIMEOUT"
    assert timeout["m2_hit"] is False
    assert timeout["exit_price"] == 100.2


def test_short_target_is_not_improved_by_gap_open():
    bars = _bars([(100, 100, 97, 98)] + [(98, 98, 98, 98)] * 19)
    result = evaluate_m2_path("SHORT", 100.0, 1.0, bars, [], [], fee_rate=0.0)

    assert result["reason"] == "TARGET"
    assert result["exit_price"] == 98.0
    assert result["m2_hit"] is True


def test_missing_bar_is_retained_as_m2_failure():
    bars = _bars([(100, 100.5, 99.5, 100.0)] * 20)
    bars[8]["open_time_ms"] += 3_600_000

    result = evaluate_m2_path("SHORT", 100.0, 1.0, bars, [], [], fee_rate=0.0)

    assert result["reason"] == "DATA_GAP"
    assert result["m2_hit"] is False


def test_funding_event_at_entry_is_excluded_and_exit_bar_credit_is_not_counted():
    start = 10_000_000
    bars = _bars([(100, 102, 100, 101)] + [(101, 101, 101, 101)] * 19, start)
    # Set target at +2R and touch it in bar 2; entry time itself is excluded.
    bars[0].update({"h": 101.0, "l": 99.5, "c": 100.5})
    bars[1].update({"h": 102.0, "l": 100.0, "c": 101.5})
    funding_times = [start, start + 3_600_000, start + 3_600_000 + 1]
    rates = [0.05, 0.01, -0.02]

    result = evaluate_m2_path("LONG", 100.0, 1.0, bars, funding_times, rates, fee_rate=0.0)

    assert result["reason"] == "TARGET"
    assert result["funding_cost_fraction"] == 0.01
    assert result["actual_signed_funding_rate_sum"] == 0.01


def test_exit_candle_funding_cost_is_charged_but_credit_is_ignored():
    start = 20_000_000
    bars = _bars([(100, 100.5, 99.5, 100)] * 20, start)
    bars[1].update({"h": 103.0, "l": 100.0, "c": 102.0})
    times = [start + 3_600_000, start + 3_600_001, start + 3_600_002]
    rates = [0.01, -0.02, 0.03]

    result = evaluate_m2_path("LONG", 100.0, 1.0, bars, times, rates, fee_rate=0.0)

    assert result["reason"] == "TARGET"
    np.testing.assert_allclose(result["funding_cost_fraction"], 0.04)
    np.testing.assert_allclose(result["actual_signed_funding_rate_sum"], 0.04)


def test_market_nonoverlap_clusters_are_fixed_by_entry_time_only():
    hour = 3_600_000
    events = [
        {"entry_open_ms": 0, "symbol": "BTCUSDT", "side": "LONG"},
        {"entry_open_ms": 0, "symbol": "ETHUSDT", "side": "SHORT"},
        {"entry_open_ms": 10 * hour, "symbol": "SOLUSDT", "side": "LONG"},
        {"entry_open_ms": 20 * hour, "symbol": "XRPUSDT", "side": "SHORT"},
        {"entry_open_ms": 39 * hour, "symbol": "ADAUSDT", "side": "LONG"},
        {"entry_open_ms": 40 * hour, "symbol": "DOGEUSDT", "side": "SHORT"},
    ]

    clusters = build_nonoverlap_clusters(events, horizon_hours=20)

    assert [cluster["entry_open_ms"] for cluster in clusters] == [0, 20 * hour, 40 * hour]
    assert [len(cluster["events"]) for cluster in clusters] == [2, 1, 1]
