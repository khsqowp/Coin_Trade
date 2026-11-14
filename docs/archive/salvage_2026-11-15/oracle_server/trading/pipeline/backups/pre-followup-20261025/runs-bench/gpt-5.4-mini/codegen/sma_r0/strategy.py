import pandas as pd


def generate_signals(df) -> pd.Series:
    close = df["close"]
    sma_10 = close.rolling(window=10, min_periods=10).mean()
    sma_30 = close.rolling(window=30, min_periods=30).mean()

    signals = (sma_10 > sma_30).fillna(False).astype(float)
    signals = signals.reindex(df.index)
    return signals
