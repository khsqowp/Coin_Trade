"""Builds a synthetic tradeable OHLC series from the price ratio of two correlated assets,
so a market-neutral pairs/stat-arb idea (app/pairs_strategies.py) can be tested inside
backtesting.py's single-asset Strategy framework.

Disclosed simplification: real pairs trading holds long one asset and short the other
simultaneously, sized so dollar exposure roughly cancels. Here the price ratio (A/B) itself
is treated as one tradeable instrument — "buying" it approximates "long A, short B" and vice
versa. This reuses the existing backtesting infrastructure but does not model the actual
two-leg execution, rebalancing, or borrow cost of a real short leg.
"""
from __future__ import annotations

import pandas as pd


def build_ratio_frame(frame_a: pd.DataFrame, frame_b: pd.DataFrame) -> pd.DataFrame:
    aligned = frame_a.join(frame_b, how="inner", lsuffix="_a", rsuffix="_b")
    ratio_open = aligned["Open_a"] / aligned["Open_b"]
    ratio_close = aligned["Close_a"] / aligned["Close_b"]
    cross_high = aligned["High_a"] / aligned["Low_b"]
    cross_low = aligned["Low_a"] / aligned["High_b"]
    # Open/Close를 포함해 max/min을 잡아 OHLC 불변식(High>=Open,Close / Low<=Open,Close)을 항상 만족시킨다.
    ratio_high = pd.concat([ratio_open, ratio_close, cross_high, cross_low], axis=1).max(axis=1)
    ratio_low = pd.concat([ratio_open, ratio_close, cross_high, cross_low], axis=1).min(axis=1)
    return pd.DataFrame({
        "Open": ratio_open, "High": ratio_high, "Low": ratio_low, "Close": ratio_close,
        "Volume": aligned["Volume_a"],
    }, index=aligned.index)
