import numpy as np
import pandas as pd

from chart_predictor.p7d_supertrend_60m import (
    WIDTH, fold_for, htf_aligned, resolve_native_trade, split_boundary,
)
from chart_predictor.setups import Signal


def bars(opens, highs, lows, closes):
    return pd.DataFrame({"t_open_ms": np.arange(len(opens)) * WIDTH,
                         "o": opens, "h": highs, "l": lows, "c": closes,
                         "v": np.ones(len(opens))})


def test_resolver_next_bar_entry_and_2r_target():
    frame = bars([100, 101, 102], [101, 103, 106], [99, 100, 101], [100, 102, 105])
    result = resolve_native_trade(Signal(index=0, side="long", stop=99), frame, 2, fee=0)
    assert result["entry"] == 101
    assert result["reason"] == "target"
    assert result["gross"] == (105 / 101 - 1)


def test_resolver_stop_wins_same_bar_tie():
    frame = bars([100, 100], [101, 110], [99, 90], [100, 100])
    result = resolve_native_trade(Signal(index=0, side="long", stop=95), frame, 2, fee=0)
    assert result["reason"] == "stop"
    assert np.isclose(result["gross"], -0.05)


def test_resolver_times_out_after_at_most_12_entry_bars():
    count = 15
    frame = bars([100] * count, [101] * count, [99] * count, [100] * count)
    result = resolve_native_trade(Signal(index=0, side="long", stop=90), frame, 3, fee=0)
    assert result["reason"] == "timeout"
    assert result["exit_ms"] == 13 * WIDTH


def test_split_boundary_and_five_equal_duration_folds():
    assert split_boundary(0, 1000) == 700
    assert [fold_for(x, 0, 1000) for x in (0, 200, 400, 600, 800, 999)] == [0, 1, 2, 3, 4, 4]


def test_htf_alignment_uses_latest_fully_closed_native_240m_bar():
    opens = np.array([0, 14_400_000, 28_800_000], dtype=np.int64)
    dirs = np.array([1, -1, 1])
    # At 4h open + 1h, the current 4h candle is incomplete; previous direction wins.
    assert htf_aligned(opens, dirs, "long", 18_000_000)
    assert not htf_aligned(opens, dirs, "short", 18_000_000)
    # At the 8h close, the second 4h bar has closed and its short direction applies.
    assert htf_aligned(opens, dirs, "short", 28_800_000)
