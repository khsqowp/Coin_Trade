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

    state = np.zeros(len(df), dtype=float)
    current = 0.0

    for i, r in enumerate(rsi.to_numpy()):
        if not np.isnan(r):
            if r < 30:
                current = 1.0
            elif r > 55:
                current = 0.0
        state[i] = current

    return pd.Series(state, index=df.index, dtype=float)
