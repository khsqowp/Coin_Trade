import numpy as np
import pytest

from chart_predictor.r021_funding_reentry import funding_extreme_side, macro_side, first_reentry_breakout


def test_funding_extreme_uses_only_prior_history_and_reverses_crowded_side():
    prior = np.linspace(-0.001, 0.001, 100)
    assert funding_extreme_side(prior, -0.0015) == 1
    assert funding_extreme_side(prior, 0.0015) == -1
    assert funding_extreme_side(prior, 0.0) is None


def test_funding_extreme_requires_minimum_history():
    assert funding_extreme_side(np.arange(59, dtype=float), -1.0) is None


@pytest.mark.parametrize("close, ema, expected", [(101, 100, 1), (99, 100, -1), (100, 100, 0)])
def test_macro_side_is_defined_by_completed_close(close, ema, expected):
    assert macro_side(close, ema) == expected


def test_breakout_requires_pullback_then_three_bar_close_break():
    high = np.array([101, 102, 101, 100, 101, 102, 103, 106], dtype=float)
    low = np.array([99, 100, 99, 97, 98, 99, 100, 101], dtype=float)
    close = np.array([100, 101, 100, 98, 100, 101, 102, 105], dtype=float)
    atr = np.ones_like(close)
    assert first_reentry_breakout(high, low, close, atr, event_index=2, side=1) == 7


def test_breakout_is_absent_without_pullback_or_with_expired_window():
    high = np.arange(10, dtype=float) + 101
    low = high - 2
    close = high - 1
    atr = np.ones_like(close)
    assert first_reentry_breakout(high, low, close, atr, event_index=2, side=1) is None
    assert first_reentry_breakout(high, low, close, atr, event_index=2, side=1, max_wait=2) is None


def test_short_breakout_mirrors_long_logic():
    high = np.array([101, 102, 101, 103, 102, 101, 100, 99], dtype=float)
    low = np.array([99, 100, 99, 100, 99, 98, 97, 94], dtype=float)
    close = np.array([100, 101, 100, 102, 100, 99, 98, 95], dtype=float)
    atr = np.ones_like(close)
    assert first_reentry_breakout(high, low, close, atr, event_index=2, side=-1) == 7


def test_invalid_arguments_fail_closed():
    with pytest.raises(ValueError):
        first_reentry_breakout(np.array([1.]), np.array([1.]), np.array([1.]), np.array([1.]), 0, 0)
