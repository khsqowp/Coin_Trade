"""Round 4: US-18 mechanism on survivorship-robust (frozen) universes with other leader / dip definitions."""
import numpy as np
from .common import *  # noqa
from .hyp import lag

FREEZE = {"F14": "2014-12-31", "F18": "2018-12-31"}


def frozen_mask(P, asof, K=100):
    i = int(np.searchsorted(P.dates, pd.Timestamp(asof), side="right") - 1)
    v = np.nan_to_num(P.value20[i], nan=-1.0)
    top = np.zeros(P.close.shape[1], bool)
    top[np.argsort(-v)[:K]] = True
    m = np.zeros(P.close.shape, bool)
    m[i + 1:, :] = top[None, :]
    return m & np.isfinite(P.close)


def top_frac(score, el, frac):
    ok = el & np.isfinite(score)
    r = np.where(ok, -score, np.inf)
    rank = np.argsort(np.argsort(r, axis=1, kind="stable"), axis=1)
    return (rank < np.ceil(ok.sum(axis=1) * frac - 1e-9)[:, None]) & ok


def sma5_exit_events(W, P, mask, el):
    s5 = W.sma(5) if P is W.P else F.sma(P.close, 5)

    def cond(ti, ci, kk):
        return P.close[ti + kk, ci] > s5[ti + kk, ci]
    return var_exit_events(P, mask, 5, cond, el)


def score(W, kind):
    P = W.P
    if kind == "mom126":
        return W.f("mom126", lambda: P.close / lag(P.close, 126) - 1)
    if kind == "mom12_1":
        return W.f("mom121", lambda: lag(P.close, 21) / lag(P.close, 252) - 1)
    if kind == "hi52":
        return W.f("hi52", lambda: P.close / F.rolling_max(P.close, 252))
    raise KeyError(kind)


def trigger(W, kind):
    P = W.P
    if kind == "rsi5":
        return W.f("rsi2", lambda: F.rsi(P.close, 2)) < 5
    if kind == "rsi10":
        return W.f("rsi2", lambda: F.rsi(P.close, 2)) < 10
    if kind == "ibs":
        return W.f("ibs", lambda: F.ibs(P.high, P.low, P.close)) < 0.10
    if kind == "drop3":
        return (P.close / lag(P.close, 3) - 1) <= -0.05
    if kind == "sma10":
        return P.close <= 0.96 * W.sma(10)
    raise KeyError(kind)


def stock_events(W, uni, score_kind, trig_kind, frac):
    P = W.P
    el = frozen_mask(P, FREEZE[uni])
    mask = top_frac(score(W, score_kind), el, frac) & trigger(W, trig_kind)
    return sma5_exit_events(W, P, mask, el)


def us27(W):
    E = W.E
    el = np.isfinite(E.close)
    sc = E.close / lag(E.close, 126) - 1
    mask = top_frac(sc, el, 1 / 3.0) & (F.rsi(E.close, 2) < 10)
    return sma5_exit_events(W, E, mask, el)


def registry():
    """(rid, h, idea, fn, N, etf, start)"""
    R = []
    spec = [("US-21", "mom12_1", "rsi5", 0.25, "12-1 momentum leader + RSI2<5"),
            ("US-22", "hi52", "rsi5", 0.25, "52w-high proximity leader + RSI2<5"),
            ("US-23", "mom126", "ibs", 0.25, "126d leader + IBS<0.10"),
            ("US-24", "mom126", "drop3", 0.25, "126d leader + 3d drop>=5%"),
            ("US-25", "mom126", "sma10", 0.25, "126d leader + close<=0.96*SMA10"),
            ("US-26", "mom126", "rsi10", 1 / 3.0, "US-18 default cell (126d top third, RSI2<10)")]
    for h, sk, tk, fr, idea in spec:
        for u in ("F14", "F18"):
            R.append((f"{h}-{u}", h, f"{idea}, frozen top100 {u}, exit >SMA5/5d",
                      lambda W, u=u, sk=sk, tk=tk, fr=fr: stock_events(W, u, sk, tk, fr), 5, False, FREEZE[u]))
    R.append(("US-27-ETF", "US-27", "ETF leader dip: 14 ETFs, 126d top third, RSI2<10, exit >SMA5/5d", us27, 5, True, None))
    return R
