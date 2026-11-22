"""Vendored causal signal implementation for the frozen jesse_simple_bollinger profile."""
import numpy as np
import pandas as pd


def bollinger(close, n=20, k=2):
    values = pd.Series(close)
    mid = values.rolling(int(n), min_periods=int(n)).mean().to_numpy()
    deviation = values.rolling(int(n), min_periods=int(n)).std(ddof=0).to_numpy()
    return mid, mid + float(k) * deviation, mid - float(k) * deviation


def signals(frame, bb_len=25, bb_k=2.5, conv=9, base=26, span_b=52, disp=26):
    high, low, close = frame.high, frame.low, frame.close
    midpoint, upper, _ = bollinger(((high + low) / 2).to_numpy(float), bb_len, bb_k)
    conversion = (high.rolling(conv, min_periods=conv).max() + low.rolling(conv, min_periods=conv).min()) / 2
    baseline = (high.rolling(base, min_periods=base).max() + low.rolling(base, min_periods=base).min()) / 2
    span_a = ((conversion + baseline) / 2).shift(disp)
    span_b_values = ((high.rolling(span_b, min_periods=span_b).max() + low.rolling(span_b, min_periods=span_b).min()) / 2).shift(disp)
    return pd.DataFrame({
        "long_entry": (close.to_numpy() > upper) & (close.to_numpy() > span_a.to_numpy()) & (close.to_numpy() > span_b_values.to_numpy()),
        "short_entry": False,
        "long_exit": close.to_numpy() < midpoint,
        "short_exit": False,
    }, index=frame.index).fillna(False)
