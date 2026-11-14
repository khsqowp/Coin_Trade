"""Equal-weight slot portfolio: at most N concurrent positions, first-come (entry-slot) ordering.

Ties at the same entry slot are broken by a seeded random key (no code-order bias). Capital/N per slot,
cash earns 0, P&L booked on exit day (realised basis).
"""
from __future__ import annotations
import heapq
import numpy as np
import pandas as pd
from . import splits


def select_trades(ev, N=5, seed=0):
    """Return boolean mask of accepted events (first-come, max N concurrent)."""
    rng = np.random.default_rng(seed)
    key = rng.random(len(ev))
    order = np.lexsort((key, ev.e_slot))
    acc = np.zeros(len(ev), dtype=bool)
    heap = []
    es, xs = ev.e_slot, ev.x_slot
    for i in order:
        s = es[i]
        while heap and heap[0] <= s:
            heapq.heappop(heap)
        if len(heap) < N:
            acc[i] = True
            heapq.heappush(heap, xs[i])
    return acc


def max_concurrent(ev):
    pts = np.concatenate([ev.e_slot * 2 + 1, ev.x_slot * 2])  # exit processed before entry at same slot
    kind = np.concatenate([np.ones(len(ev)), -np.ones(len(ev))])
    o = np.argsort(pts, kind="stable")
    return int(np.cumsum(kind[o]).max()) if len(ev) else 0


def simulate(ev, dates, N=5, seed=0, capital=1.3e6, cost_model=None) -> dict:
    """dates: panel calendar (DatetimeIndex) used for the daily series."""
    splits.guard_dev(ev.xdates, "portfolio")
    acc = select_trades(ev, N, seed)
    sel = ev.subset(acc)
    if len(sel) == 0:
        return dict(n=0, sharpe=np.nan, ann=np.nan, maxdd=np.nan, trades_month=0, turnover_month=0.0, worst=np.nan, max_conc=0, daily=pd.Series(dtype=float))
    idx = pd.DatetimeIndex(dates)
    lo, hi = sel.dates.min(), sel.xdates.max()
    cal = idx[(idx >= lo) & (idx <= hi)]
    daily = pd.Series(0.0, index=cal)
    pnl = pd.Series(sel.net / N).groupby(sel.xdates).sum()
    daily.loc[pnl.index.intersection(cal)] += pnl.reindex(pnl.index.intersection(cal)).to_numpy()
    fixed = cost_model.fixed_monthly_return(capital) if cost_model is not None else 0.0
    if fixed:
        last = pd.Series(cal, index=cal).groupby([cal.year, cal.month]).max()
        daily.loc[last.to_numpy()] -= fixed
    sd = daily.std()
    sharpe = float(daily.mean() / sd * np.sqrt(252)) if sd > 0 else np.nan
    eq = daily.cumsum()
    months = max((cal[-1] - cal[0]).days / 30.44, 1.0)
    return dict(n=len(sel), sharpe=sharpe, ann=float(daily.mean() * 252), maxdd=float((eq - eq.cummax()).min()),
                trades_month=len(sel) / months, turnover_month=len(sel) / months * 2 * capital / N,
                turnover_cap_ratio=len(sel) / months * 2 * capital / N / 1e8,
                worst=float(sel.net.min()), max_conc=max_concurrent(sel), daily=daily)
