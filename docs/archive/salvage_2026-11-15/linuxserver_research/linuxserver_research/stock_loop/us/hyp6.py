"""Round 6: regime conditioning of the US-18 cell (US-33) and momentum-without-dip baseline (US-34)."""
import numpy as np
from .common import *  # noqa
from .hyp import lag
from .hyp4 import frozen_mask, top_frac, FREEZE, sma5_exit_events


def spy_series(W):
    j = W.E.codes.index("SPY")
    return W.E.close[:, j]


def regime(W, kind):
    c = spy_series(W)
    if kind == "a":
        return c > F.sma(c[:, None], 200)[:, 0]
    if kind == "b":
        r = np.full(len(c), np.nan); r[1:] = c[1:] / c[:-1] - 1
        v = pd.Series(r).rolling(10, min_periods=10).std().to_numpy() * np.sqrt(252)
        med = pd.Series(v).rolling(250, min_periods=250).median().to_numpy()
        return np.isfinite(med) & (v < med)
    if kind == "c":
        return c >= 0.90 * F.rolling_max(c[:, None], 252)[:, 0]
    raise KeyError(kind)


def elig_for(W, uni):
    return W.elig(100) if uni == "DYN" else frozen_mask(W.P, FREEZE[uni], 100)


def us33(W, uni, kind):
    P = W.P
    el = elig_for(W, uni)
    sc = W.f("mom126", lambda: P.close / lag(P.close, 126) - 1)
    base = top_frac(sc, el, 0.25) & (W.f("rsi2", lambda: F.rsi(P.close, 2)) < 5)
    mask = base & np.nan_to_num(regime(W, kind), nan=0).astype(bool)[:, None]
    return sma5_exit_events(W, P, mask, el)


def us34(W, uni):
    P = W.P
    el = frozen_mask(P, FREEZE[uni], 100)
    sc = W.f("mom126", lambda: P.close / lag(P.close, 126) - 1)
    first = int(np.argmax(el.any(axis=1)))
    days = np.zeros(P.close.shape[0], bool)
    days[first::20] = True
    mask = top_frac(sc, el, 0.25) & days[:, None]
    return fixed_events(P, mask, ("close", 0), ("close", 20), el)


def registry():
    R = []
    for kind, nm in (("a", "SPY>SMA200"), ("b", "SPY 10d realized vol < 250d median"), ("c", "SPY within 10% of 252d high")):
        for u in ("DYN", "F14", "F18"):
            R.append((f"US-33{kind}-{u}", "US-33", f"US-18 cell (126d top quartile & RSI2<5) only when {nm}, universe {u}",
                      lambda W, u=u, k=kind: us33(W, u, k), 5, False, None if u == "DYN" else FREEZE[u]))
    for u in ("F14", "F18"):
        R.append((f"US-34-{u}", "US-34", f"126d top-quartile leaders, no dip: buy every 20th bar, hold 20d, frozen top100 {u}",
                  lambda W, u=u: us34(W, u), 5, False, FREEZE[u]))
    return R
