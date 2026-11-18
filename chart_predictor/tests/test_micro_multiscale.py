import numpy as np

from chart_predictor.micro_multiscale import (
    aggregate_bars,
    fold_indices,
    nonoverlap_indices,
    signal_masks,
)


MINUTE = 60_000


def test_aggregate_requires_exact_full_utc_buckets_and_valid_constituents():
    # First 3m bucket is complete. Second has a missing minute. Third has a
    # malformed candle. Fourth is a partial terminal bucket.
    t = np.array([0, MINUTE, 2 * MINUTE, 3 * MINUTE, 5 * MINUTE,
                  6 * MINUTE, 7 * MINUTE, 8 * MINUTE, 9 * MINUTE,
                  10 * MINUTE])
    o = np.array([10, 11, 12, 13, 15, 16, 17, 18, 19, 20.], dtype=float)
    h = o + 2
    l = o - 2
    c = o + 1
    h[7] = l[7] - 1  # invalid OHLC poisons the whole bucket

    bars = aggregate_bars(t, o, h, l, c, 3)

    assert bars["open_ms"].tolist() == [0]
    assert bars["open"].tolist() == [10.0]
    assert bars["high"].tolist() == [14.0]
    assert bars["low"].tolist() == [8.0]
    assert bars["close"].tolist() == [13.0]


def test_body_and_sweep_signals_are_causal_and_require_adjacent_bars():
    t = np.array([0, 3 * MINUTE, 6 * MINUTE, 12 * MINUTE])
    o = np.array([9.1, 10., 10., 10.])
    h = np.array([11., 10.8, 12., 12.])
    l = np.array([9., 8.8, 9., 9.])
    c = np.array([10.9, 10.6, 11., 11.])

    body, sweep = signal_masks(t, o, h, l, c, 3 * MINUTE)

    assert body.tolist() == [1, 0, 0, 0]
    # Bar 2 sweeps bar 1's low, then reclaims above its midpoint.
    assert sweep.tolist() == [0, 1, 0, 0]
    # Bar 4 is not adjacent to bar 3 and cannot form a 2-bar signal.


def test_nonoverlap_uses_actual_availability_time_and_allows_exact_boundary():
    availability = np.array([0, 3 * MINUTE, 6 * MINUTE, 9 * MINUTE,
                             12 * MINUTE], dtype=np.int64)
    indexes = np.array([0, 1, 2, 3, 4], dtype=np.int64)

    selected = nonoverlap_indices(indexes, availability, horizon=2, interval_ms=3 * MINUTE)

    assert selected.tolist() == [0, 2, 4]


def test_fold_membership_is_half_open_on_availability():
    boundaries = np.array([0, 10, 20], dtype=np.int64)
    assert fold_indices(np.array([0, 9, 10, 19, 20]), boundaries).tolist() == [0, 0, 1, 1, -1]
