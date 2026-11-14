import numpy as np
import pandas as pd


def _rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)
    alpha = 1.0 / period
    avg_gain = gains.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = losses.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 with avg_gain > 0 -> RSI 100; both zero -> undefined (NaN)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return rsi


def generate_signals(df: pd.DataFrame) -> pd.Series:
    close = df["close"].astype(float)
    rsi = _rsi_wilder(close, 14).to_numpy()

    n = len(close)
    out = np.zeros(n, dtype=float)
    state = 0.0
    for i in range(n):
        r = rsi[i]
        if not np.isnan(r):
            if state == 0.0 and r < 30.0:
                state = 1.0
            elif state == 1.0 and r > 55.0:
                state = 0.0
        out[i] = state

    return pd.Series(out, index=df.index, dtype=float, name="signal")
