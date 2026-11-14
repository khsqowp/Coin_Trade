"""Event study: forward returns, cluster-robust t-stats, BH correction.

Conventions: signal known at bar t. entry=(kind, offset) means price `kind` ("open"/"close") at bar t+offset;
exit likewise. e.g. entry=("open",1), exit=("close",3): buy next open, sell close of t+3.
Slots: 2*bar + (0 open / 1 close); a position occupies [entry_slot, exit_slot).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats
from . import splits


def shift_up(a, k):
    """value at bar t+k aligned to bar t (NaN beyond end)."""
    a = np.asarray(a, dtype=float)
    out = np.full_like(a, np.nan)
    if k == 0:
        return a.copy()
    out[:-k] = a[k:]
    return out


def slot(kind, off):
    return 2 * off + (1 if kind == "close" else 0)


def fwd_returns(panel, entry=("open", 1), exit=("close", 1)):
    if slot(*exit) <= slot(*entry):
        raise ValueError("exit must be after entry")
    e = shift_up(getattr(panel, entry[0]), entry[1])
    x = shift_up(getattr(panel, exit[0]), exit[1])
    with np.errstate(invalid="ignore", divide="ignore"):
        return x / e - 1.0


@dataclass
class Events:
    ti: np.ndarray        # signal bar
    ci: np.ndarray        # column
    e_slot: np.ndarray
    x_slot: np.ndarray
    gross: np.ndarray
    cost: np.ndarray
    dates: pd.DatetimeIndex   # entry date
    xdates: pd.DatetimeIndex  # exit date

    @property
    def net(self):
        return self.gross - self.cost

    def __len__(self):
        return len(self.ti)

    def subset(self, m):
        m = np.asarray(m)
        return Events(self.ti[m], self.ci[m], self.e_slot[m], self.x_slot[m], self.gross[m], self.cost[m],
                      self.dates[m], self.xdates[m])

    def with_cost(self, cost):
        return Events(self.ti, self.ci, self.e_slot, self.x_slot, self.gross, np.asarray(cost), self.dates, self.xdates)


def make_events(panel, mask, entry=("open", 1), exit=("close", 1), cost_model=None, eligible=None, cost_frac=None) -> Events:
    """mask: bool (T x N) signal. cost_model.roundtrip(value20) gives per-trade cost; or pass scalar cost_frac."""
    g = fwd_returns(panel, entry, exit)
    ok = np.asarray(mask, dtype=bool) & np.isfinite(g)
    if eligible is not None:
        ok &= eligible
    ti, ci = np.nonzero(ok)
    gross = g[ti, ci]
    if cost_model is not None:
        cost = cost_model.roundtrip(panel.value20[ti, ci])
    else:
        cost = np.full(len(ti), float(cost_frac or 0.0))
    d = panel.dates
    ed, xd = ti + entry[1], ti + exit[1]
    dates, xdates = d[ed], d[xd]
    splits.guard_dev(xdates, "events") if len(ti) else None
    return Events(ti, ci, 2 * ti + slot(*entry), 2 * ti + slot(*exit), gross, np.broadcast_to(cost, ti.shape).astype(float).copy(), dates, xdates)


def cluster_t(r, clusters):
    """t-stat of mean(r) with SE clustered by `clusters` (e.g. entry date). Returns (mean, t)."""
    r = np.asarray(r, dtype=float)
    n = len(r)
    if n < 2:
        return (float(r.mean()) if n else np.nan), np.nan
    m = r.mean()
    _, inv = np.unique(np.asarray(clusters), return_inverse=True)
    s = np.bincount(inv, weights=r - m)
    se = np.sqrt((s ** 2).sum()) / n
    return float(m), (float(m / se) if se > 0 else np.nan)


def t_to_p(t):
    return float(2 * stats.norm.sf(abs(t))) if np.isfinite(t) else 1.0


def bh_qvalues(ps):
    a = np.array([1.0 if p is None or not np.isfinite(p) else p for p in ps])
    n = len(a)
    if n == 0:
        return []
    order = np.argsort(a)
    v = a[order] * n / (np.arange(n) + 1)
    v = np.minimum.accumulate(v[::-1])[::-1]
    q = np.empty(n)
    q[order] = np.minimum(v, 1.0)
    return q.tolist()


def summarize(ev: Events, split_date=None) -> dict:
    """Net-of-cost stats. split_date: boundary between dev halves (sign-consistency check)."""
    n = len(ev)
    if n == 0:
        return dict(n=0, mean=np.nan, t=np.nan, gross=np.nan, hit=np.nan, h1=np.nan, h2=np.nan, years_pos=np.nan, p=1.0, break_even=np.nan)
    net = ev.net
    m, t = cluster_t(net, ev.dates.asi8)
    out = dict(n=n, mean=m, t=t, gross=float(ev.gross.mean()), hit=float((net > 0).mean()), p=t_to_p(t),
               cost=float(ev.cost.mean()), break_even=float(ev.gross.mean()))  # break-even round-trip cost = gross mean
    if split_date is not None:
        a = ev.dates < split_date
        out["h1"] = float(net[a].mean()) if a.any() else np.nan
        out["h2"] = float(net[~a].mean()) if (~a).any() else np.nan
    yrs = pd.Series(net).groupby(ev.dates.year).mean()
    out["years_pos"] = float((yrs > 0).mean())
    out["sd"] = float(net.std())
    return out
