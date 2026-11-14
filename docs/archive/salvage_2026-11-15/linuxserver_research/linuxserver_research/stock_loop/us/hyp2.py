"""Round 2 hypotheses US-13..US-20 (preregs in spec/US-13..20, written before running)."""
import numpy as np
from .common import *  # noqa
from .hyp import lag


def etf_events(W, sym, mask_1d, exit_off):
    E = W.E
    j = E.codes.index(sym)
    m = np.zeros(E.close.shape, bool)
    m[:, j] = mask_1d
    return fixed_events(E, m, ("close", 0), ("close", exit_off))


def us13(W, sym):
    E = W.E
    j = E.codes.index(sym)
    c = E.close[:, j]
    r3 = c / lag(c[:, None], 3)[:, 0] - 1
    return etf_events(W, sym, (r3 <= -0.025) & (c > W.sma(200, "E")[:, j]), 5)


def us14(W, k):
    P = W.P
    el100 = W.elig(100)
    down = (P.close < lag(P.close)) & np.isfinite(lag(P.close))
    n = (el100 & np.isfinite(P.close) & np.isfinite(lag(P.close))).sum(axis=1)
    frac = np.where(n > 0, (down & el100).sum(axis=1) / np.maximum(n, 1), 0.0)
    spy = W.E.codes.index("SPY")
    up = W.E.close[:, spy] > W.sma(200, "E")[:, spy]
    day = (frac >= 0.85) & up & (n >= 50)
    mask = np.broadcast_to(day[:, None], P.close.shape)
    return fixed_events(P, mask, ("close", 0), ("close", 5), W.elig(k))


def us15(W, k):
    P = W.P
    spy = W.E.codes.index("SPY")
    sc = W.E.close[:, spy]
    sr3 = sc / lag(sc[:, None], 3)[:, 0] - 1
    r3 = P.close / lag(P.close, 3) - 1
    mask = ((r3 - sr3[:, None]) <= -0.06) & (P.close > W.sma(200)) & (P.volume >= 1.5 * lag(W.avgvol(20)))
    return fixed_events(P, mask, ("close", 0), ("close", 5), W.elig(k))


def us16(W, k):
    P = W.P
    r1 = P.close / lag(P.close) - 1
    rng = P.high - P.low
    mask = (r1 >= 0.05) & (P.volume >= 2.5 * lag(W.avgvol(20))) & (rng > 0) & ((P.close - P.low) >= 0.75 * rng)
    return fixed_events(P, mask, ("close", 0), ("close", 5), W.elig(k))


def us17(W, k):
    P = W.P
    rng = P.high - P.low
    mask = (P.open / lag(P.close) - 1 <= -0.02) & (P.close > P.open) & (rng > 0) & ((P.close - P.low) >= 0.70 * rng) \
        & (lag(P.close) > lag(W.sma(200)))
    return fixed_events(P, mask, ("close", 0), ("close", 3), W.elig(k))


def _rsi_exit_events(W, mask, k):
    P = W.P
    s5 = W.sma(5)

    def cond(ti, ci, kk):
        return P.close[ti + kk, ci] > s5[ti + kk, ci]
    return var_exit_events(P, mask, 5, cond, W.elig(k))


def us18(W, k):
    P = W.P
    el = W.elig(k)
    r126 = P.close / lag(P.close, 126) - 1
    r = np.where(el & np.isfinite(r126), -r126, np.inf)           # most negative = strongest
    rank = np.argsort(np.argsort(r, axis=1, kind="stable"), axis=1)
    nel = (el & np.isfinite(r126)).sum(axis=1)
    top3rd = rank < np.ceil(nel / 3.0)[:, None]
    rsi = W.f("rsi2", lambda: F.rsi(P.close, 2))
    return _rsi_exit_events(W, top3rd & np.isfinite(r) & (rsi < 10), k)


def us19(W, k):
    P = W.P
    spy = W.E.codes.index("SPY")
    sc = W.E.close[:, spy]
    sret = np.full(len(sc), np.nan)
    sret[1:] = sc[1:] / sc[:-1] - 1
    vol10 = pd.Series(sret).rolling(10, min_periods=10).std().to_numpy() * np.sqrt(252)
    med = pd.Series(vol10).rolling(250, min_periods=250).median().to_numpy()
    hv = np.nan_to_num(vol10 >= med, nan=0).astype(bool) & np.isfinite(med)
    rsi = W.f("rsi2", lambda: F.rsi(P.close, 2))
    mask = (rsi < 10) & (P.close > W.sma(200)) & hv[:, None]
    return _rsi_exit_events(W, mask, k)


def us20(W):
    E = W.E
    i, s = E.codes.index("IWM"), E.codes.index("SPY")
    r3 = lambda c: c / lag(c[:, None], 3)[:, 0] - 1
    return etf_events(W, "IWM", (r3(E.close[:, i]) - r3(E.close[:, s])) <= -0.02, 3)


def registry():
    R = []

    def add(rid, h, idea, fn, N=5, etf=False):
        R.append((rid, h, idea, fn, N, etf))
    for sym in ("SPY", "QQQ"):
        add(f"US-13-{sym}", "US-13", f"{sym} 3d ret<=-2.5% & >SMA200: buy close, hold 5d", lambda W, s=sym: us13(W, s), etf=True)
    for k, tag in ((30, ""), (100, "-T100")):
        add("US-14" + tag, "US-14", f"breadth washout (>=85% of top100 down, SPY>SMA200): basket top{k}, hold 5d", lambda W, k=k: us14(W, k))
        add("US-15" + tag, "US-15", f"idio capitulation (3d rel SPY<=-6%, vol>=1.5x, >SMA200): hold 5d, top{k}", lambda W, k=k: us15(W, k))
        add("US-16" + tag, "US-16", f"breakout day ret>=5%, vol>=2.5x, close top25% range: hold 5d, top{k}", lambda W, k=k: us16(W, k))
        add("US-17" + tag, "US-17", f"hammer after gap-down<=-2% (close>open, top30% range, >SMA200): hold 3d, top{k}", lambda W, k=k: us17(W, k))
        add("US-18" + tag, "US-18", f"momentum-leader (126d top third) RSI2<10: exit >SMA5 or 5d, top{k}", lambda W, k=k: us18(W, k))
        add("US-19" + tag, "US-19", f"RSI2<10 & >SMA200 in high SPY realized-vol regime: exit >SMA5 or 5d, top{k}", lambda W, k=k: us19(W, k))
    add("US-20-IWM", "US-20", "IWM lags SPY by >=2% over 3d: buy IWM close, hold 3d", us20, etf=True)
    return R
