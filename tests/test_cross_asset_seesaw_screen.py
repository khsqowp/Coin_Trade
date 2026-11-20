import numpy as np
import pytest

from scripts.research.cross_asset_seesaw_screen import (
    anchor_aligned,
    bootstrap_block_observations,
    causal_mutation_check,
    draw_mbb_indices,
    entry_exit_indices,
    funding_sum_between,
    net_return,
    signal_sides,
    window_in_split,
)


def test_signal_uses_only_closed_leader_returns_and_fades():
    closes = np.array([[100, 110, 99, 99], [100, 110, 99, 99],
                       [100, 110, 99, 99], [100, 110, 99, 99]], dtype=float)
    assert signal_sides(closes).tolist() == [0, -1, 1, 0]


def test_exact_zero_basket_return_emits_no_signal():
    closes = np.full((4, 3), 100.0)
    assert signal_sides(closes).tolist() == [0, 0, 0]


def test_future_mutation_does_not_change_prefix():
    closes = np.array([[100, 101, 99, 102, 103], [100, 102, 99, 101, 100],
                       [100, 100, 98, 99, 102], [100, 99, 101, 100, 103]], dtype=float)
    assert causal_mutation_check(closes, 2)


def test_wrong_leader_dimension_fails_closed():
    with pytest.raises(ValueError):
        signal_sides(np.ones((3, 4)))


def test_missing_leader_data_fails_closed():
    closes = np.ones((4, 4))
    closes[0, 2] = np.nan
    with pytest.raises(ValueError, match="finite and positive"):
        signal_sides(closes)


def test_entry_and_exit_are_next_open_and_hth_close_indices():
    assert entry_exit_indices(10, 1) == (11, 11)
    assert entry_exit_indices(10, 4) == (11, 14)


def test_funding_interval_excludes_entry_timestamp_and_includes_exit_timestamp():
    times = np.array([100, 101, 102, 103], dtype=np.int64)
    rates = np.array([1, 2, 4, 8], dtype=float)
    assert funding_sum_between(times, rates, 101, 103) == 12
    assert funding_sum_between(times, rates, 101, 103, include_exit=False) == 4


def test_funding_sign_and_round_trip_fee():
    assert net_return(1, 0.01, 0.002, 0.001) == pytest.approx(0.007)
    assert net_return(-1, 0.01, 0.002, 0.001) == pytest.approx(0.011)


def test_horizon_anchor_and_split_end_boundary():
    hour = 3_600_000
    assert anchor_aligned(4 * hour, 4)
    assert not anchor_aligned(5 * hour, 4)
    assert window_in_split(2 * hour, 9 * hour, 0, 9 * hour)
    assert not window_in_split(2 * hour, 10 * hour, 0, 9 * hour)


def test_seven_day_blocks_respect_horizon_sampling_interval():
    assert bootstrap_block_observations(1) == 168
    assert bootstrap_block_observations(4) == 42


def test_moving_block_resamples_contiguous_blocks_without_circular_wrap():
    indices = draw_mbb_indices(10, 4, np.random.default_rng(7))
    assert len(indices) == 10
    assert np.all((indices >= 0) & (indices < 10))
    for start in range(0, len(indices), 4):
        assert np.all(np.diff(indices[start:start + 4]) == 1)
