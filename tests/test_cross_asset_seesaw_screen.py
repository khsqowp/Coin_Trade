import numpy as np
import pytest

from scripts.research.cross_asset_seesaw_screen import causal_mutation_check, signal_sides


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
