import numpy as np
import pytest

from scripts.research.crypto_round11_streak_probe import (
    MINUTE_MS,
    resolve_trade,
    streak_signals,
)


def test_streak_signal_prefix_is_unchanged_by_future_candles():
    timestamps = np.arange(20, dtype=np.int64) * MINUTE_MS
    open_ = np.full(20, 100.0)
    close = open_.copy()
    close[2:5] = 101.0
    first = streak_signals(open_, close, timestamps)
    mutated = close.copy()
    mutated[10:] = 1.0
    second = streak_signals(open_, mutated, timestamps)
    np.testing.assert_array_equal(first[:10], second[:10])
    assert first[4] == 1


def test_streak_requires_contiguous_minutes():
    timestamps = np.arange(20, dtype=np.int64) * MINUTE_MS
    timestamps[5:] += MINUTE_MS
    open_ = np.full(20, 100.0)
    close = open_ + 1
    signals = streak_signals(open_, close, timestamps)
    assert signals[2] == 1
    assert signals[5] == 0


def test_same_minute_stop_and_target_tie_uses_adverse_stop():
    timestamps = np.arange(24, dtype=np.int64) * MINUTE_MS
    open_ = np.full(24, 100.0)
    high = np.full(24, 100.5)
    low = np.full(24, 99.5)
    close = np.full(24, 100.0)
    atr = np.full(24, 1.0)
    high[3], low[3] = 102.0, 98.0
    trade = resolve_trade(2, 1, timestamps, open_, high, low, close, atr)
    assert trade is not None
    assert trade["target_first"] is False
    assert trade["gross_return"] == pytest.approx(-0.01)


def test_stop_gap_fills_at_adverse_open():
    timestamps = np.arange(24, dtype=np.int64) * MINUTE_MS
    open_ = np.full(24, 100.0)
    high = np.full(24, 100.5)
    low = np.full(24, 99.5)
    close = np.full(24, 100.0)
    atr = np.full(24, 1.0)
    open_[4], high[4], low[4] = 98.0, 102.0, 97.0
    trade = resolve_trade(2, 1, timestamps, open_, high, low, close, atr)
    assert trade is not None
    assert trade["target_first"] is False
    assert trade["gross_return"] == pytest.approx(-0.02)
