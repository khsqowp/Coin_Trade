import numpy as np
import pandas as pd

SMA_LENGTH = 50
ATR_LENGTH = 14
ATR_MULTIPLE = 3.0
RULES = {"sma_trend_entry": "enter when close > SMA", "sma_exit": "exit when close < SMA",
         "atr_trailing_exit": "exit when close < highest close since entry - 3*ATR"}


def _prep(df):
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / ATR_LENGTH, adjust=False, min_periods=ATR_LENGTH).mean()
    sma = close.rolling(window=SMA_LENGTH, min_periods=SMA_LENGTH).mean()
    return close, atr, sma


def generate_signals(df, disabled=frozenset()):
    close, atr, sma = _prep(df)
    signals = np.zeros(len(df))
    long_state, highest, locked = False, np.nan, False
    for i in range(len(df)):
        c, s, a = close.iloc[i], sma.iloc[i], atr.iloc[i]
        if locked and (not np.isnan(s)) and c < s:
            locked = False
        if long_state:
            highest = c if np.isnan(highest) else max(highest, c)
            exit_sma = ("sma_exit" not in disabled) and (not np.isnan(s)) and c < s
            exit_trail = ("atr_trailing_exit" not in disabled) and (not np.isnan(a)) and c < highest - ATR_MULTIPLE * a
            if exit_sma or exit_trail:
                long_state, highest = False, np.nan
                locked = exit_trail and not exit_sma
        if (not long_state) and (not locked) and (not np.isnan(s)) and (c > s or "sma_trend_entry" in disabled):
            long_state, highest = True, c
        signals[i] = 1.0 if long_state else 0.0
    return pd.Series(signals, index=df.index, dtype=float)
