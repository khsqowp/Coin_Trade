import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame) -> pd.Series:
    close = df["close"]
    sma_fast = close.rolling(window=10, min_periods=10).mean()
    sma_slow = close.rolling(window=30, min_periods=30).mean()
    valid = sma_fast.notna() & sma_slow.notna()
    signal = pd.Series(0.0, index=df.index, dtype=float)
    signal[valid & (sma_fast > sma_slow)] = 1.0
    return signal
