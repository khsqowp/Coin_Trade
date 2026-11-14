import numpy as np
import pandas as pd


def generate_signals(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / 14.0, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / 14.0, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(avg_loss != 0.0, 100.0)
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss == 0.0)), 50.0)

    rsi_values = rsi.to_numpy(dtype=float)
    n = len(rsi_values)

    signals = np.zeros(n, dtype=float)
    state = 0.0
    for i in range(n):
        r = rsi_values[i]
        if not np.isnan(r):
            if state == 0.0:
                if r < 30.0:
                    state = 1.0
            else:
                if r > 55.0:
                    state = 0.0
        signals[i] = state

    return pd.Series(signals, index=df.index, dtype=float)
