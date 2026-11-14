"""Vectorised daily features on (T x N) arrays."""
import numpy as np
import pandas as pd


def _df(a):
    return pd.DataFrame(a)


def sma(a, n):
    return _df(a).rolling(n, min_periods=n).mean().to_numpy()


def rolling_max(a, n):
    return _df(a).rolling(n, min_periods=n).max().to_numpy()


def lag(a, k=1):
    out = np.full_like(a, np.nan, dtype=float)
    if k == 0:
        return a.astype(float).copy()
    out[k:] = a[:-k]
    return out


def rsi(close, n=2):
    d = _df(close).diff()
    up = d.clip(lower=0).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(100.0).where(up.notna()).to_numpy()


def ibs(high, low, close):
    rng = high - low
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(rng > 0, (close - low) / rng, np.nan)


def down_streak(close):
    """Number of consecutive down closes ending at t."""
    d = np.diff(close, axis=0, prepend=np.nan) < 0
    out = np.zeros(close.shape, dtype=float)
    for t in range(1, close.shape[0]):
        out[t] = np.where(d[t], out[t - 1] + 1, 0)
    return out
