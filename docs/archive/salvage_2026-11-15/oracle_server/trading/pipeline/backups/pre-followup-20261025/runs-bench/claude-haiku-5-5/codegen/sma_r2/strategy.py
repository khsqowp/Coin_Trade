import numpy as np
import pandas as pd


def generate_signals(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    fast = close.rolling(window=10, min_periods=10).mean()
    slow = close.rolling(window=30, min_periods=30).mean()

    signal = (fast > slow).astype(float)
    signal = signal.where(fast.notna() & slow.notna(), 0.0)
    signal = signal.fillna(0.0).astype(float)
    signal = signal.reindex(df.index).fillna(0.0).astype(float)
    signal.name = "signal"
    return signal
