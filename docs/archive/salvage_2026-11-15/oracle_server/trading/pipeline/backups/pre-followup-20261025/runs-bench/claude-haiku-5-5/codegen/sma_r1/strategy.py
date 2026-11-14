import numpy as np
import pandas as pd


def generate_signals(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)

    # Trailing simple moving averages; rolling(...).mean() uses only data
    # up to and including the current bar. min_periods=window makes the
    # first window-1 bars NaN (undefined).
    sma_fast = close.rolling(window=10, min_periods=10).mean()
    sma_slow = close.rolling(window=30, min_periods=30).mean()

    # Comparisons involving NaN are False, so undefined bars become 0.0.
    long_condition = (sma_fast > sma_slow).fillna(False)

    signal = np.where(long_condition.to_numpy(), 1.0, 0.0).astype(float)

    return pd.Series(signal, index=df.index, dtype=float, name="signal")
