import numpy as np
import pandas as pd
import pytest

from scripts.research.adaptive_selective_m2_probe import (
    MINUTE_MS,
    compute_features,
    funding_minute_indices,
    global_nonoverlap,
    label_first_touch,
    nearest_rank_quantile,
    refit_window,
    select_direction,
)


def bars(n=80):
    close = 100.0 + np.arange(n, dtype=float) * 0.01
    open_ = close - 0.005
    high = close + 0.02
    low = open_ - 0.02
    return pd.DataFrame({
        "open_time": np.arange(n, dtype=np.int64) * MINUTE_MS,
        "open": open_, "high": high, "low": low, "close": close,
        "volume": np.full(n, 10.0),
        "taker_buy_volume": np.full(n, 6.0),
    })


def test_features_are_prefix_invariant_and_have_exact_whitelist():
    frame = bars()
    features, ready = compute_features(frame)
    mutated = frame.copy()
    mutated.loc[60:, ["open", "high", "low", "close", "volume", "taker_buy_volume"]] *= 3
    changed, _ = compute_features(mutated)

    assert list(features.columns) == [
        "ret_1", "ret_3", "ret_5", "ret_10", "range_pct", "body_ratio",
        "upper_wick_ratio", "lower_wick_ratio", "atr14_pct", "rv20",
        "volume_z60", "taker_fraction_5",
    ]
    assert ready[:60].sum() == 1
    np.testing.assert_allclose(features.iloc[59].to_numpy(), changed.iloc[59].to_numpy())
    assert not ready[58]
    assert ready[59]


def test_feature_readiness_does_not_roll_across_timestamp_gap():
    frame = bars()
    frame.loc[60:, "open_time"] += MINUTE_MS
    _, ready = compute_features(frame)

    assert not ready[60]
    assert not ready[118]
    assert ready[119]


def test_label_first_touch_up_down_nohit_and_same_bar_collision():
    frame = bars(20)
    frame.loc[2, ["high", "low"]] = [101.1, 99.9]
    assert label_first_touch(frame, 0, 1.0)["label"] == "UP_FIRST"

    frame.loc[2, ["high", "low"]] = [100.1, 98.9]
    assert label_first_touch(frame, 0, 1.0)["label"] == "DOWN_FIRST"

    frame.loc[2, ["high", "low"]] = [101.1, 98.9]
    result = label_first_touch(frame, 0, 1.0)
    assert result["label"] == "NO_HIT"
    assert result["status"] == "AMBIGUOUS_BOTH"


def test_label_timeout_and_missing_path_are_distinct():
    frame = bars(15)
    result = label_first_touch(frame, 0, 1.0)
    assert result["label"] == "NO_HIT"
    assert result["status"] == "TIMEOUT"

    frame.loc[7:, "open_time"] += MINUTE_MS
    result = label_first_touch(frame, 0, 1.0)
    assert result["status"] == "MISSING_PATH"
    assert result["label"] is None


@pytest.mark.parametrize("values,q,expected", [
    ([1.0, 2.0, 3.0, 4.0], 0.50, 2.0),
    ([1.0, 2.0, 3.0, 4.0], 0.90, 4.0),
    ([1.0, 1.0, 1.0, 1.0], 0.90, 1.0),
])
def test_nearest_rank_threshold_is_deterministic(values, q, expected):
    assert nearest_rank_quantile(values, q) == expected


def test_select_direction_requires_positive_edge_and_strict_class_winner():
    assert select_direction(0.60, 0.20, 0.20, 0.30) == ("long", 0.40)
    assert select_direction(0.20, 0.60, 0.20, 0.30) == ("short", 0.40)
    assert select_direction(0.30, 0.30, 0.40, -0.20) is None
    assert select_direction(0.40, 0.40, 0.20, 0.10) is None
    assert select_direction(0.45, 0.35, 0.20, 0.30) is None


def test_refit_training_window_is_180_days_with_28_day_embargo():
    t = 1_800_000_000_000
    start, end = refit_window(t)
    assert end == t - 28 * 24 * 60 * MINUTE_MS
    assert end - start == 180 * 24 * 60 * MINUTE_MS


def test_global_nonoverlap_keeps_missing_entry_scheduled_window():
    events = [
        {"anchor_ms": 0, "scheduled_entry_ms": MINUTE_MS, "symbol": "ETHUSDT",
         "score": 0.4, "entry_missing": True},
        {"anchor_ms": 0, "scheduled_entry_ms": MINUTE_MS, "symbol": "BTCUSDT",
         "score": 0.3, "entry_missing": False},
        {"anchor_ms": 5 * MINUTE_MS, "scheduled_entry_ms": 6 * MINUTE_MS,
         "symbol": "BTCUSDT", "score": 0.9, "entry_missing": False},
        {"anchor_ms": 11 * MINUTE_MS, "scheduled_entry_ms": 12 * MINUTE_MS,
         "symbol": "BTCUSDT", "score": 0.2, "entry_missing": False},
    ]
    selected = global_nonoverlap(events)

    assert [event["symbol"] for event in selected] == ["ETHUSDT", "BTCUSDT"]
    assert selected[0]["entry_missing"]
    assert selected[1]["anchor_ms"] == 11 * MINUTE_MS


def test_funding_timestamp_maps_to_exact_containing_mark_minute():
    mark_times = np.array([0, MINUTE_MS, 2 * MINUTE_MS], dtype=np.int64)
    funding_times = np.array([MINUTE_MS + 999, 2 * MINUTE_MS], dtype=np.int64)
    np.testing.assert_array_equal(
        funding_minute_indices(mark_times, funding_times), np.array([1, 2])
    )


def test_funding_timestamp_over_one_second_off_grid_is_rejected():
    mark_times = np.array([0, MINUTE_MS], dtype=np.int64)
    funding_times = np.array([MINUTE_MS + 1_001], dtype=np.int64)
    with pytest.raises(ValueError, match="off the UTC minute grid"):
        funding_minute_indices(mark_times, funding_times)
