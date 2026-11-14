import pandas as pd


def generate_signals(df: pd.DataFrame) -> pd.Series:
    close = df["close"]
    sma10 = close.rolling(window=10, min_periods=10).mean()
    sma30 = close.rolling(window=30, min_periods=30).mean()

    signal = (sma10 > sma30).astype(float)
    signal = signal.fillna(0.0)

    return pd.Series(signal.to_numpy(dtype=float), index=df.index, dtype=float)
