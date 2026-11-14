import numpy as np
import pandas as pd


def generate_signals(df: pd.DataFrame) -> pd.Series:
    """Long/flat SMA crossover signal.

    Returns 1.0 when SMA(close, 10) > SMA(close, 30), else 0.0.
    Bars where either SMA is undefined (insufficient history) are 0.0.
    Each value at bar t uses only data up to and including bar t.
    """
    close = df["close"].astype(float)

    # rolling(...).mean() is trailing (uses current and prior bars only)
    fast = close.rolling(window=10, min_periods=10).mean()
    slow = close.rolling(window=30, min_periods=30).mean()

    # Comparisons with NaN evaluate to False, so undefined bars become 0.0
    long_condition = (fast > slow).fillna(False)

    signal = long_condition.astype(float)
    signal.name = None
    return pd.Series(
        signal.to_numpy(dtype=float),
        index=df.index,
        dtype=float,
    )
