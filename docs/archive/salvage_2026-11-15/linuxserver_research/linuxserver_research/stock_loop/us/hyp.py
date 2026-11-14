"""US-01..US-12 Stage-1 hypotheses with PREREGISTERED fixed defaults (see spec/US-*/prereg.md + US-ADDENDUM-data.md)."""
import numpy as np
from .common import *  # noqa


class Ctx:
    def __init__(self, P, E):
        self.P, self.E, self._c = P, E, {}

    def f(self, key, fn):
        if key not in self._c:
            self._c[key] = fn()
        return self._c[key]

    def sma(self, n, which="P"):
        X = getattr(self, which)
        return self.f((which, "sma", n), lambda: F.sma(X.close, n))

    def avgvol(self, n=20):
        return self.f(("v", n), lambda: F.sma(self.P.volume, n))

    def elig(self, k, lag=0):
        return self.f(("elig", k, lag), lambda: topk_mask(F.lag(self.P.value20, lag) if lag else self.P.value20, k))

    def spy_ret(self):
        j = self.E.codes.index("SPY")
        c = self.E.close[:, j]
        r = np.full(len(c), np.nan)
        r[1:] = c[1:] / c[:-1] - 1
        return r


def lag(a, k=1):
    return F.lag(a, k)


def us01(W, k):
    P = W.P
    cl1 = lag(P.close)
    mask = (P.open / cl1 - 1 <= -0.02) & (cl1 > lag(W.sma(200))) & (lag(P.volume) < 2 * lag(W.avgvol(20)))
    return fixed_events(P, mask, ("open", 0), ("close", 0), W.elig(k, 1))


def us02(W, k):
    P = W.P
    cl1 = lag(P.close)
    vavg = lag(W.avgvol(20))
    mask = (P.open / cl1 - 1 >= 0.04) & (P.volume >= 3 * vavg) & (P.close > P.open)
    return fixed_events(P, mask, ("close", 0), ("close", 3), W.elig(k))


def us03_etf(W, sym, cond):
    E = W.E
    j = E.codes.index(sym)
    m = np.zeros(E.close.shape, bool)
    m[:, j] = True if not cond else (E.close[:, j] < W.sma(5, "E")[:, j])
    return fixed_events(E, m, ("close", 0), ("open", 1))


def us03_univ(W, k, cond):
    P = W.P
    mask = np.ones(P.close.shape, bool)
    if cond:
        mask = P.close < W.sma(5)
    return fixed_events(P, mask, ("close", 0), ("open", 1), W.elig(k))


def us04(W, k):
    P = W.P
    ibs = W.f("ibs", lambda: F.ibs(P.high, P.low, P.close))
    mask = (ibs < 0.20) & (P.close > W.sma(200))

    def cond(ti, ci, kk):
        return ibs[ti + kk, ci] > 0.70
    return var_exit_events(P, mask, 5, cond, W.elig(k))


def us05(W, k):
    P = W.P
    rsi = W.f("rsi2", lambda: F.rsi(P.close, 2))
    s5 = W.sma(5)
    mask = (rsi < 10) & (P.close > W.sma(200))

    def cond(ti, ci, kk):
        return P.close[ti + kk, ci] > s5[ti + kk, ci]
    return var_exit_events(P, mask, 5, cond, W.elig(k))


def us06(W, k):
    P = W.P
    el = W.elig(k)
    ret3 = P.close / lag(P.close, 3) - 1
    r = np.where(el & np.isfinite(ret3), ret3, np.inf)
    rank = np.argsort(np.argsort(r, axis=1, kind="stable"), axis=1)
    nel = (el & np.isfinite(ret3)).sum(axis=1)
    kk = np.maximum(3, np.floor(0.10 * nel)).astype(int)
    mask = (rank < kk[:, None]) & np.isfinite(r) & (P.close > W.sma(200)) & (nel >= 3)[:, None]
    return fixed_events(P, mask, ("close", 0), ("close", 5), el)


def us07(W, k):
    P = W.P
    pc = lag(P.close)
    tr = np.fmax(P.high - P.low, np.fmax(np.abs(P.high - pc), np.abs(P.low - pc)))
    atr = F.sma(tr, 14)
    rng = P.high - P.low
    mask = (rng >= 2.0 * lag(atr)) & ((P.close - P.low) <= 0.2 * rng) & (rng > 0) & (P.close > W.sma(200))
    return fixed_events(P, mask, ("close", 0), ("close", 2), W.elig(k))


def us08(W, sym):
    E = W.E
    j = E.codes.index(sym)
    days = month_turn_days(E.dates, 2)
    m = np.zeros(E.close.shape, bool)
    m[days, j] = True
    return fixed_events(E, m, ("close", 0), ("close", 4))


def us09_spy(W):
    E = W.E
    j = E.codes.index("SPY")
    r = W.spy_ret()
    m = np.zeros(E.close.shape, bool)
    m[:, j] = (E.dates.dayofweek == 4) & (r <= -0.01)
    return fixed_events(E, m, ("close", 0), ("close", 1))


def us09_stocks(W, k):
    P = W.P
    ret1 = P.close / lag(P.close) - 1
    mask = (P.dates.dayofweek == 4)[:, None] & (ret1 <= -0.025)
    return fixed_events(P, mask, ("close", 0), ("close", 1), W.elig(k))


def us10(W):
    E = W.E
    cols = [E.codes.index(s) for s in SECTORS]
    spy5 = E.close[:, E.codes.index("SPY")] / lag(E.close[:, [E.codes.index("SPY")]], 5)[:, 0] - 1
    ret5 = E.close / lag(E.close, 5) - 1
    rel = ret5 - spy5[:, None]
    sec = np.full(rel.shape, np.inf)
    sec[:, cols] = np.where(np.isfinite(rel[:, cols]), rel[:, cols], np.inf)
    rank = np.argsort(np.argsort(sec, axis=1, kind="stable"), axis=1)
    mask = (rank < 2) & np.isfinite(sec) & (E.close > W.sma(200, "E"))
    return fixed_events(E, mask, ("close", 0), ("close", 5))


def us11(W, k):
    P = W.P
    minprev = lag(rolling_min(P.low, 20), 2)
    mask = (lag(P.low) < minprev) & (P.close > lag(P.high))

    def cond(ti, ci, kk):
        return P.close[ti + kk, ci] < P.low[ti - 1, ci]
    return var_exit_events(P, mask, 5, cond, W.elig(k))


def us12(W, k):
    P = W.P
    ret1 = P.close / lag(P.close) - 1
    mask = (W.spy_ret() <= -0.0075)[:, None] & (ret1 >= 0.01) & (P.close > W.sma(50))
    return fixed_events(P, mask, ("close", 0), ("close", 3), W.elig(k))


def registry():
    """(row id, hypothesis, idea, builder, portfolio N, tag)"""
    R = []

    def add(rid, h, idea, fn, N=5):
        R.append((rid, h, idea, fn, N))
    for k, tag in ((30, ""), (100, "-T100")):
        add("US-01" + tag, "US-01", f"gap-down open<=-2% fade, >SMA200, prior vol<2x: buy open sell close, top{k}", lambda W, k=k: us01(W, k))
        add("US-02" + tag, "US-02", f"gap-up>=4% & vol>=3x & close>open: buy close, hold 3d, top{k}", lambda W, k=k: us02(W, k))
    for sym in ("SPY", "QQQ"):
        add(f"US-03-{sym}", "US-03", f"overnight {sym}: buy close sell next open, every day", lambda W, s=sym: us03_etf(W, s, False))
        add(f"US-03-{sym}-SMA5", "US-03", f"overnight {sym} only when close<SMA5", lambda W, s=sym: us03_etf(W, s, True))
    for k, tag in ((30, "T30"), (100, "T100")):
        add(f"US-03-{tag}", "US-03", f"overnight universe top{k}: every day", lambda W, k=k: us03_univ(W, k, False))
        add(f"US-03-{tag}-SMA5", "US-03", f"overnight universe top{k} only when close<SMA5", lambda W, k=k: us03_univ(W, k, True))
    for k, tag in ((30, ""), (100, "-T100")):
        add("US-04" + tag, "US-04", f"IBS<0.2 & >SMA200: buy close, exit IBS>0.7 or 5d, top{k}", lambda W, k=k: us04(W, k))
        add("US-05" + tag, "US-05", f"RSI2<10 & >SMA200: buy close, exit close>SMA5 or 5d, top{k}", lambda W, k=k: us05(W, k))
        add("US-06" + tag, "US-06", f"bottom decile 3d return & >SMA200: buy close, hold 5d, top{k}", lambda W, k=k: us06(W, k))
        add("US-07" + tag, "US-07", f"range>=2xATR14 & close in bottom 20% & >SMA200: hold 2d, top{k}", lambda W, k=k: us07(W, k))
    for sym in ("SPY", "QQQ"):
        add(f"US-08-{sym}", "US-08", f"turn-of-month {sym}: buy close of day -2, sell close day +3", lambda W, s=sym: us08(W, s))
    add("US-09-SPY", "US-09", "weak Friday SPY<=-1%: buy Fri close sell Mon close", us09_spy)
    for k, tag in ((30, "T30"), (100, "T100")):
        add(f"US-09-{tag}", "US-09", f"Friday stock return<=-2.5% -> Monday close, top{k}", lambda W, k=k: us09_stocks(W, k))
    add("US-10", "US-10", "sector ETF bottom-2 rel 5d vs SPY & >SMA200: hold 5d", us10, N=2)
    for k, tag in ((30, ""), (100, "-T100")):
        add("US-11" + tag, "US-11", f"reclaim after 20d low: buy close, exit 5d or close<low[t-1], top{k}", lambda W, k=k: us11(W, k))
        add("US-12" + tag, "US-12", f"SPY<=-0.75% day, stock>=+1% & >SMA50: hold 3d, top{k}", lambda W, k=k: us12(W, k))
    return R
