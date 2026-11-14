"""Random-entry baseline: same entry dates as the strategy, random eligible stock each, same exit rule and costs."""
from __future__ import annotations
import numpy as np


def random_entry_baseline(net_matrix, eligible, event_ti, actual_mean, draws=1000, seed=0):
    """net_matrix: (T x N) net return of entering at bar t with the strategy's entry/exit rule.
    eligible: bool (T x N) pool. event_ti: signal bars of actual events (with multiplicity).
    Returns dict(pct, mean, sd, draws): pct = share of random draws with mean < actual_mean."""
    ok = eligible & np.isfinite(net_matrix)
    rows, cols = np.nonzero(ok)
    T = net_matrix.shape[0]
    cnt = np.bincount(rows, minlength=T)
    start = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    vals = net_matrix[rows, cols]
    ev = np.asarray(event_ti)
    ev = ev[cnt[ev] > 0]
    if len(ev) == 0:
        return dict(pct=np.nan, mean=np.nan, sd=np.nan, draws=0)
    c, s = cnt[ev], start[ev]
    rng = np.random.default_rng(seed)
    means = np.empty(draws)
    for k in range(draws):
        means[k] = vals[s + (rng.random(len(ev)) * c).astype(np.int64)].mean()
    return dict(pct=float((means < actual_mean).mean()), mean=float(means.mean()), sd=float(means.std()), draws=draws)
