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
    rsi = 100.0 - (100.0 / (1.0 + rs))

    state = np.empty(len(df), dtype=float)
    cur = 0.0

    for i, val in enumerate(rsi.to_numpy()):
        if not np.isnan(val):
            if val < 30.0:
                cur = 1.0
            elif val > 55.0:
                cur = 0.0
        state[i] = cur

    return pd.Series(state, index=df.index, dtype=float)
