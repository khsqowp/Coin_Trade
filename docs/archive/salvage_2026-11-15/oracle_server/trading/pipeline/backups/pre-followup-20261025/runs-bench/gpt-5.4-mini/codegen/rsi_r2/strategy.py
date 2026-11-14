import numpy as np
import pandas as pd


def generate_signals(df) -> pd.Series:
    close = df["close"]

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    out = np.empty(len(df), dtype=float)
    state = 0.0

    rsi_values = rsi.to_numpy()
    for i, v in enumerate(rsi_values):
        if np.isnan(v):
            out[i] = state
        elif v < 30:
            state = 1.0
            out[i] = state
        elif v > 55:
            state = 0.0
            out[i] = state
        else:
            out[i] = state

    return pd.Series(out, index=df.index, dtype=float)
