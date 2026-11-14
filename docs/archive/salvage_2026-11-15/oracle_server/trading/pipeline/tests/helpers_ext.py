"""Shared synthetic data for the extension tests (seeded, deterministic)."""
import numpy as np
import pandas as pd


def make_ohlcv(n=1500, seed=3, drift=0.0004, vol=0.006, freq="1h"):
    rng = np.random.RandomState(seed)
    r = rng.normal(drift, vol, n)
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": rng.uniform(50, 150, n)}, index=idx)
