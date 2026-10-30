import numpy as np
def _idx(n, B, rng, mb=20):
    p = 1.0 / mb
    idx = np.empty((B, n), np.int64)
    for b in range(B):
        i = rng.integers(n)
        for t in range(n):
            idx[b, t] = i
            i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return idx
def boot_diff(eqA, eqB, B=2000, seed=12345):
    f = lambda e: np.diff(np.log(np.maximum(e, 1e-6)), axis=1).mean(axis=0)
    d = f(eqA) - f(eqB)
    rng = np.random.default_rng(seed)
    idx = _idx(len(d), B, rng)
    m = d[idx].mean(axis=1) * 365.0
    return d.mean() * 365.0, np.percentile(m, [5, 95])
