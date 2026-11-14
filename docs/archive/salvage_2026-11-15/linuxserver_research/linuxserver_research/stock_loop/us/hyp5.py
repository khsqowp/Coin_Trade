"""Round 5: KR crash-rebound analogues (US-28..31) and US-18 horizon sweep (US-32)."""
import numpy as np
from .common import *  # noqa
from .hyp import lag
from .hyp4 import frozen_mask, top_frac, FREEZE


def crash_mask(W, kind):
    P = W.P
    v = P.volume
    c = P.close
    if kind == "US-28":
        r1 = c / lag(c) - 1
        return (lag(r1) <= -0.10) & (v < 0.5 * lag(v))
    if kind == "US-29":
        r5 = c / lag(c, 5) - 1
        v3 = W.f("v3", lambda: F.sma(v, 3))
        v20p = lag(W.avgvol(20), 3)
        return (r5 <= -0.12) & (v3 < 0.5 * v20p)
    if kind == "US-30":
        r10 = c / lag(c, 10) - 1
        q30 = W.f("vq30", lambda: pd.DataFrame(v).rolling(250, min_periods=250).quantile(0.30).to_numpy())
        return (r10 <= -0.15) & (v <= q30)
    if kind == "US-31":
        lowmin = W.f("low252", lambda: rolling_min(P.low, 252))
        r20 = c / lag(c, 20) - 1
        vmax5 = W.f("vmax5", lambda: F.rolling_max(v, 5))
        return (c <= 1.05 * lowmin) & (r20 <= -0.12) & (v < 0.5 * vmax5)
    raise KeyError(kind)


def crash_events(W, kind, uni):
    el = frozen_mask(W.P, FREEZE[uni], K=300)
    return fixed_events(W.P, crash_mask(W, kind), ("close", 0), ("close", 3), el)


def sweep_events(W, uni, h):
    P = W.P
    el = W.elig(100) if uni == "DYN" else frozen_mask(P, FREEZE[uni], K=100)
    sc = W.f("mom126", lambda: P.close / lag(P.close, 126) - 1)
    mask = top_frac(sc, el, 0.25) & (W.f("rsi2", lambda: F.rsi(P.close, 2)) < 5)
    return fixed_events(P, mask, ("close", 0), ("close", h), el)


def registry():
    R = []
    names = {"US-28": "post-crash dry-up (ret_{t-1}<=-10%, vol<0.5x prev)", "US-29": "5d drop>=12% & 3d vol<0.5x 20d",
             "US-30": "10d drop>=15% & vol<=30th pct of 250d", "US-31": "near 52w low, 20d drop>=12%, vol<0.5x 5d max"}
    for k, nm in names.items():
        for u in ("F14", "F18"):
            R.append((f"{k}-{u}", k, f"{nm}, frozen top300 {u}, hold 3d", lambda W, k=k, u=u: crash_events(W, k, u), 5, False, FREEZE[u]))
    for u in ("DYN", "F14", "F18"):
        for h in (5, 10, 20):
            R.append((f"US-32-{u}-h{h}", "US-32", f"US-18 cell (126d top quartile & RSI2<5), fixed hold {h}d, universe {u} top100",
                      lambda W, u=u, h=h: sweep_events(W, u, h), 5, False, None if u == "DYN" else FREEZE[u]))
    return R
