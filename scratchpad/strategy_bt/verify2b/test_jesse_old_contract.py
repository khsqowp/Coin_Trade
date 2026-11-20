import numpy as np
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_group_b import jesse_cloud_old


def test_jesse_old_rolling_cloud_matches_shift_25():
    rng = np.random.default_rng(501)
    n = 240
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.1, 2, n)
    low = close - rng.uniform(0.1, 2, n)
    candles = np.column_stack([np.arange(n), close, close, high, low, np.ones(n)])
    direct = np.full((n, 4), np.nan)
    for i in range(79, n):
        direct[i] = jesse_cloud_old(candles[i - 79:i + 1])
    conv = (pd.Series(high).rolling(9).max() + pd.Series(low).rolling(9).min()) / 2
    base = (pd.Series(high).rolling(26).max() + pd.Series(low).rolling(26).min()) / 2
    span_b = (pd.Series(high).rolling(52).max() + pd.Series(low).rolling(52).min()) / 2
    vector = np.column_stack([conv, base, ((conv + base) / 2).shift(25), span_b.shift(25)])
    valid = np.isfinite(direct).all(axis=1) & np.isfinite(vector).all(axis=1)
    np.testing.assert_allclose(direct[valid], vector[valid], rtol=0, atol=1e-12)
