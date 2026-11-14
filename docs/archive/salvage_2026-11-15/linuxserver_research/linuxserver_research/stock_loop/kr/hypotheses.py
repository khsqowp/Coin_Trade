"""KR Stage 1/2 hypotheses (daily bars, long-only, hold 1-5 bars). Defaults fixed in prereg BEFORE any run.

build(panel, ctx, **p) -> (mask[T,N] signal known at bar t, entry, exit, extra_eligible or None)
Signal bar t; entry/exit per lib.eventstudy conventions. Universe: 20-bar mean traded value >= 2e9 KRW at t.
"""
import numpy as np
import pandas as pd
from lib import features as F
from lib.eventstudy import shift_up


def _ma_ok(P, ctx, ma):
    if not ma:
        return np.ones(P.close.shape, bool)
    return P.close > ctx.sma(ma)


def gap(P):
    return P.open / F.lag(P.close, 1) - 1


def h_gapdown(P, ctx, g=0.03, h=1, ma=0):
    m = (gap(P) <= -g) & _ma_ok(P, ctx, ma)    # MA uses close_t, mild; for gap uses prior close below
    if ma:
        m = (gap(P) <= -g) & (F.lag(P.close, 1) > F.lag(ctx.sma(ma), 1))
    # signal known at open t; entry at open t => signal bar t, entry offset 0
    return m, ("open", 0), ("close", h - 1 if h > 1 else 0), None


def h_gapup(P, ctx, g=0.03, h=1, ma=0):
    m = (gap(P) >= g)
    if ma:
        m = m & (F.lag(P.close, 1) > F.lag(ctx.sma(ma), 1))
    return m, ("open", 0), ("close", h - 1 if h > 1 else 0), None


def h_overnight(P, ctx, group="KOSPI", thr=2e9):
    m = np.broadcast_to((P.group == group)[None, :], P.close.shape) & (np.nan_to_num(P.value20) >= thr)
    return m, ("close", 0), ("open", 1), None


def h_ibs(P, ctx, x=0.2, h=3, ma=200):
    m = (F.ibs(P.high, P.low, P.close) <= x) & _ma_ok(P, ctx, ma)
    return m, ("open", 1), ("close", h), None


def h_rsi2(P, ctx, x=10, h=3, ma=200):
    m = (ctx.rsi(2) <= x) & _ma_ok(P, ctx, ma)
    return m, ("open", 1), ("close", h), None


def h_rev3(P, ctx, k=3, h=3, ma=0):
    m = (F.down_streak(P.close) >= k) & _ma_ok(P, ctx, ma)
    return m, ("open", 1), ("close", h), None


def h_limitup(P, ctx, r=0.29, h=1, minv=2e9):
    ret = P.close / F.lag(P.close, 1) - 1
    m = (ret >= r) & (np.nan_to_num(P.value20) >= minv)
    # tradable only if next open is not locked at the limit (open < 1.29 * close_t is implied by buying at open; require open_{t+1} < close_t*1.29)
    nxt_open = shift_up(P.open, 1)
    m = m & (nxt_open < P.close * 1.29)
    # also require it was NOT a same-limit open: price must be below the next-day upper limit approx
    return m, ("open", 1), ("close", h), None


def h_volspike(P, ctx, v=3.0, r=0.015, h=3):
    ret = P.close / F.lag(P.close, 1) - 1
    v20 = F.lag(ctx.avgvol20(), 1)
    m = (P.volume >= v * v20) & (np.abs(ret) <= r)
    return m, ("open", 1), ("close", h), None


def h_breakout(P, ctx, n=20, v=2.0, h=5):
    hi = F.lag(F.rolling_max(P.high, n), 1)
    v20 = F.lag(ctx.avgvol20(), 1)
    m = (P.close > hi) & (P.volume >= v * v20)
    return m, ("open", 1), ("close", h), None


def h_tom(P, ctx, k=1, h=4):
    d = P.dates
    ym = d.year * 12 + d.month
    last_idx = pd.Series(np.arange(len(d))).groupby(ym).transform("max").to_numpy()
    entry_bar = last_idx - (k - 1)           # entry at open of the k-th-from-last trading day
    sig_bar = np.arange(len(d)) == (entry_bar - 1)
    # month-complete days only: need a bar exist for last_idx (last month in dev may be partial; harmless since exits NaN)
    mask = np.zeros(P.close.shape, bool)
    for t in np.nonzero(np.isin(np.arange(len(d)), np.unique(entry_bar - 1)))[0]:
        mask[t, :] = True
    return mask, ("open", 1), ("close", h), None


def h_kqrel(P, ctx, x=0.03, n=3, h=3):
    kq = ctx.index("KOSDAQ").reindex(P.dates).ffill()
    ks = ctx.index("KOSPI").reindex(P.dates).ffill()
    rel = (kq / kq.shift(n) - 1) - (ks / ks.shift(n) - 1)
    sig = (rel <= -x).to_numpy()
    m = np.broadcast_to(sig[:, None], P.close.shape) & (P.group == "KOSDAQ")[None, :]
    return m, ("open", 1), ("close", h), None


# id, fn, defaults, grid (<=3 params x 3 values), idea
H = {
 "KR-01": (h_gapdown, dict(g=0.03, h=1, ma=0), dict(g=(0.02, 0.03, 0.05), h=(1, 2, 3), ma=(0, 60, 200)),
           "gap-down open <= -3% fade: buy open, sell close same day"),
 "KR-02": (h_gapup, dict(g=0.03, h=1, ma=0), dict(g=(0.02, 0.03, 0.05), h=(1, 2, 3), ma=(0, 60, 200)),
           "gap-up open >= +3% continuation: buy open, sell close same day"),
 "KR-03": (h_overnight, dict(group="KOSPI", thr=2e9), dict(thr=(2e9, 5e9, 2e10)),
           "overnight drift KOSPI liquid names: buy close, sell next open (complement=intraday)"),
 "KR-04": (h_overnight, dict(group="KOSDAQ", thr=2e9), dict(thr=(2e9, 5e9, 2e10)),
           "overnight drift KOSDAQ liquid names: buy close, sell next open"),
 "KR-05": (h_ibs, dict(x=0.2, h=3, ma=200), dict(x=(0.1, 0.2, 0.3), h=(2, 3, 5), ma=(0, 100, 200)),
           "IBS<=0.2 & close>MA200 mean reversion, buy next open, hold 3"),
 "KR-06": (h_rsi2, dict(x=10, h=3, ma=200), dict(x=(5, 10, 15), h=(2, 3, 5), ma=(0, 100, 200)),
           "RSI(2)<=10 oversold bounce in uptrend (>MA200), buy next open, hold 3"),
 "KR-07": (h_rev3, dict(k=3, h=3, ma=0), dict(k=(3, 4, 5), h=(2, 3, 5), ma=(0, 100, 200)),
           "reversal after >=3 consecutive down closes, buy next open, hold 3"),
 "KR-08": (h_limitup, dict(r=0.29, h=1, minv=2e9), dict(r=(0.25, 0.27, 0.29), h=(1, 2, 3), minv=(2e9, 5e9, 1e10)),
           "limit-up (>=+29%) next-day continuation (long only; fade not shortable), buy next open if not locked"),
 "KR-09": (h_volspike, dict(v=3.0, r=0.015, h=3), dict(v=(2.0, 3.0, 4.0), r=(0.01, 0.015, 0.02), h=(2, 3, 5)),
           "volume >=3x avg20 with |ret|<=1.5% (accumulation) -> buy next open, hold 3"),
 "KR-10": (h_breakout, dict(n=20, v=2.0, h=5), dict(n=(20, 40, 60), v=(1.5, 2.0, 3.0), h=(3, 5, 10)),
           "20-day high close breakout with volume >=2x avg20, buy next open, hold 5"),
 "KR-11": (h_tom, dict(k=1, h=4), dict(k=(1, 2, 3), h=(3, 4, 5)),
           "turn-of-month: buy open of last trading day of month, hold 4 bars (all liquid names)"),
 "KR-12": (h_kqrel, dict(x=0.03, n=3, h=3), dict(x=(0.02, 0.03, 0.04), n=(2, 3, 5), h=(2, 3, 5)),
           "KOSDAQ lags KOSPI by >=3% over 3 days -> buy liquid KOSDAQ stocks next open, hold 3"),
}
