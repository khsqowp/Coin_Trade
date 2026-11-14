"""Round 7: membership-date (point-in-time) universe re-judgement (US-35)."""
import io
import numpy as np
from .common import *  # noqa
from .hyp import lag
from .hyp4 import frozen_mask, top_frac, FREEZE, sma5_exit_events

RAW = ROOT / "results" / "us35_raw" / "sp500_wikipedia.html"
_cache = {}


def added_dates():
    if "d" not in _cache:
        t = pd.read_html(io.StringIO(RAW.read_text(encoding="utf8")))[0]
        sym = t["Symbol"].astype(str).str.replace(".", "-", regex=False)
        _cache["d"] = dict(zip(sym, pd.to_datetime(t["Date added"], errors="coerce")))
    return _cache["d"]


def member_mask(P):
    d = added_dates()
    M = np.zeros(P.close.shape, bool)
    unmatched = []
    for j, c in enumerate(P.codes):
        dt = d.get(str(c).replace(".", "-"))
        if dt is None or pd.isna(dt):
            unmatched.append(c)
            continue
        M[:, j] = P.dates >= dt
    return M, unmatched


def mem_elig(W, K=100):
    if "mem" not in W.__dict__.setdefault("_mem", {}):
        M, un = member_mask(W.P)
        v = np.where(M, W.P.value20, np.nan)
        W._mem["mem"] = (topk_mask(v, K) & M, un)
    return W._mem["mem"][0]


def sel(W, el, rsi=5):
    P = W.P
    sc = W.f("mom126", lambda: P.close / lag(P.close, 126) - 1)
    return top_frac(sc, el, 0.25), sc


def spec_events(W, spec, el):
    P = W.P
    top, sc = sel(W, el)
    if spec == "18c":
        return sma5_exit_events(W, P, top & (W.f("rsi2", lambda: F.rsi(P.close, 2)) < 5), el)
    if spec in ("h5", "h10", "h20"):
        h = int(spec[1:])
        return fixed_events(P, top & (W.f("rsi2", lambda: F.rsi(P.close, 2)) < 5), ("close", 0), ("close", h), el)
    if spec == "24":
        return sma5_exit_events(W, P, top & ((P.close / lag(P.close, 3) - 1) <= -0.05), el)
    if spec == "25":
        return sma5_exit_events(W, P, top & (P.close <= 0.96 * W.sma(10)), el)
    if spec == "34":
        first = int(np.argmax(el.any(axis=1)))
        days = np.zeros(P.close.shape[0], bool); days[first::20] = True
        return fixed_events(P, top & days[:, None], ("close", 0), ("close", 20), el)
    raise KeyError(spec)


def registry():
    R = []
    for spec in ("18c", "h5", "h10", "h20", "24", "25", "34"):
        R.append((f"US-35-{spec}-MEM", "US-35", f"membership-date PIT top100 universe, spec {spec} (see prereg)",
                  lambda W, s=spec: spec_events(W, s, mem_elig(W)), 5, False, None))
    for u in ("F14", "F18"):
        R.append((f"US-35-18c-{u}", "US-35", f"US-18 candidate cell (RSI2<5, 126d top quartile, exit >SMA5/5d), frozen top100 {u}",
                  lambda W, u=u: spec_events(W, "18c", frozen_mask(W.P, FREEZE[u], 100)), 5, False, FREEZE[u]))
    return R
