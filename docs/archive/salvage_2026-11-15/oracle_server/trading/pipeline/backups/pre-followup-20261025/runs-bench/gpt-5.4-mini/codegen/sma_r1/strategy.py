import pandas as pd


def generate_signals(df) -> pd.Series:
    close = df["close"]
    sma10 = close.rolling(window=10, min_periods=10).mean()
    sma30 = close.rolling(window=30, min_periods=30).mean()

    signal = (sma10 > sma30).fillna(False).astype(float)
    signal.name = "signal"
    return signal.reindex(df.index).astype(float)
