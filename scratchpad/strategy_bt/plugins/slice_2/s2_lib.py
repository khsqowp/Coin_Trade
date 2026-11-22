"""Shared helpers for slice_2 plugins (causal, numpy based). Not a plugin (no SPEC_ID)."""
import os
from pathlib import Path
import numpy as np
import pandas as pd

_DATA = Path(os.environ.get("S2_DATA_DIR", Path(__file__).resolve().parents[3] / "bb_stoch_stc" / "data"))
_REF = {}
_CACHE = {}


def _ref_arrays():
    """Lazy-load (index, open, close) of every cached parquet; used only to recover timestamps."""
    if not _REF:
        for f in sorted(_DATA.glob("*_*.parquet")):
            d = pd.read_parquet(f, columns=["open", "close"])
            _REF[f.name] = (d.index, d["open"].to_numpy(float), d["close"].to_numpy(float))
    return _REF


def timestamps(df):
    """UTC DatetimeIndex of df. common.protocol.evaluate passes frames with reset_index(drop=True)
    (timestamps lost), so recover them by exact open/close fingerprint match against the cache."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index.tz_localize("UTC") if df.index.tz is None else df.index
    n = len(df)
    o = df["open"].to_numpy(float); c = df["close"].to_numpy(float)
    key = (n, o[0], c[0], o[-1], c[-1], float(o.sum()))
    if key in _CACHE:
        return _CACHE[key]
    for name, (idx, ro, rc) in _ref_arrays().items():
        if len(ro) < n:
            continue
        for p in np.where(ro[: len(ro) - n + 1] == o[0])[0]:
            if rc[p] == c[0] and np.array_equal(ro[p:p + n], o) and np.array_equal(rc[p:p + n], c):
                _CACHE[key] = idx[p:p + n]
                return _CACHE[key]
    raise RuntimeError("cannot recover timestamps for frame (no cached parquet match)")


def rma(x, n):
    """Wilder smoothing seeded with SMA of first n valid values (TA-Lib / Pine ta.rma)."""
    x = np.asarray(x, float); out = np.full(len(x), np.nan)
    valid = np.where(np.isfinite(x))[0]
    if len(valid) < n:
        return out
    s = valid[0] + n - 1
    out[s] = x[valid[0]:s + 1].mean()
    for i in range(s + 1, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n if np.isfinite(x[i]) else out[i - 1]
    return out


def ema_ta(x, n):
    """EMA seeded with SMA of first n values (TA-Lib)."""
    x = np.asarray(x, float); out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = x[:n].mean(); a = 2 / (n + 1)
    for i in range(n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi_wilder(close, n):
    c = np.asarray(close, float); d = np.r_[np.nan, np.diff(c)]
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0); up[0] = dn[0] = np.nan
    au = rma(up, n); ad = rma(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100 - 100 / (1 + au / ad)
    r = np.where((ad == 0) & np.isfinite(au), 100.0, r)
    return r


def adx_wilder(h, l, c, n=14):
    h, l, c = (np.asarray(v, float) for v in (h, l, c)); N = len(c)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    up = np.r_[np.nan, h[1:] - h[:-1]]; dn = np.r_[np.nan, l[:-1] - l[1:]]
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pdm[0] = mdm[0] = np.nan
    atr_ = rma(tr, n); p = rma(pdm, n); m = rma(mdm, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * p / atr_; mdi = 100 * m / atr_; dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return rma(dx, n)


def tr_atr(h, l, c, n):
    h, l, c = (np.asarray(v, float) for v in (h, l, c))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    tr[0] = h[0] - l[0]
    return rma(tr, n)


def supertrend(h, l, c, atr_period, mult):
    """Pine ta.supertrend semantics; mult scalar or per-bar array. Returns (line, direction) with
    direction +1 uptrend (line = lower band), -1 downtrend (line = upper band)."""
    h, l, c = (np.asarray(v, float) for v in (h, l, c)); n = len(c)
    mult = np.broadcast_to(np.asarray(mult, float), (n,))
    atr_ = tr_atr(h, l, c, atr_period); hl2 = (h + l) / 2
    line = np.full(n, np.nan); dire = np.zeros(n, int)
    lo = np.full(n, np.nan); up = np.full(n, np.nan)
    for i in range(n):
        if not np.isfinite(atr_[i]):
            continue
        lb = hl2[i] - mult[i] * atr_[i]; ub = hl2[i] + mult[i] * atr_[i]
        if i > 0 and np.isfinite(lo[i - 1]):
            plb, pub = lo[i - 1], up[i - 1]
            lb = lb if (lb > plb or c[i - 1] < plb) else plb
            ub = ub if (ub < pub or c[i - 1] > pub) else pub
            if dire[i - 1] == 1:
                d = -1 if c[i] < lb else 1
            else:
                d = 1 if c[i] > ub else -1
        else:
            d = 1
        lo[i], up[i], dire[i] = lb, ub, d
        line[i] = lb if d == 1 else ub
    return line, dire


def psar(h, l, af0=0.02, step=0.02, afmax=0.2):
    """Wilder parabolic SAR. Returns trend array (+1 long, -1 short, 0 undefined) at each bar close."""
    h = np.asarray(h, float); l = np.asarray(l, float); n = len(h)
    trend = np.zeros(n, int)
    if n < 2:
        return trend
    long_ = True; sar = l[0]; ep = h[0]; af = af0; trend[0] = 1
    for i in range(1, n):
        s = sar + af * (ep - sar)
        if long_:
            s = min(s, l[i - 1], l[i - 2] if i >= 2 else l[i - 1])
            if l[i] < s:
                long_ = False; s = ep; ep = l[i]; af = af0
            elif h[i] > ep:
                ep = h[i]; af = min(af + step, afmax)
        else:
            s = max(s, h[i - 1], h[i - 2] if i >= 2 else h[i - 1])
            if h[i] > s:
                long_ = True; s = ep; ep = h[i]; af = af0
            elif l[i] < ep:
                ep = l[i]; af = min(af + step, afmax)
        sar = s; trend[i] = 1 if long_ else -1
    return trend


def prior_extreme(x, n, fn):
    """Rolling max/min of the previous n values, EXCLUDING the current bar."""
    s = pd.Series(np.asarray(x, float)).shift(1).rolling(int(n), min_periods=int(n))
    return (s.max() if fn == "max" else s.min()).to_numpy()


def crossed_above(a, b):
    a = np.asarray(a, float); b = np.broadcast_to(np.asarray(b, float), a.shape)
    out = np.zeros(len(a), bool)
    out[1:] = (a[1:] > b[1:]) & (a[:-1] <= b[:-1])
    return out


def frame(df, le=None, se=None, lx=None, sx=None, **cols):
    n = len(df); z = np.zeros(n, bool)
    f = lambda v: z.copy() if v is None else np.asarray(v, bool)
    out = pd.DataFrame({"long_entry": f(le), "short_entry": f(se), "long_exit": f(lx), "short_exit": f(sx)}, index=df.index)
    for k, v in cols.items():
        out[k] = np.asarray(v, float)
    return out


def session_signals(df, day_start, day_rule, night_rule):
    """12h-session calendar strategies. Rules per session: long|short|cash|mom|rev.
    Day = [day_start, day_start+12) UTC, night = complement. Signal bar b = last bar before a session;
    entry executes at the next open (= session start). 'Previous return of the same session' = return of
    that same session type 24h earlier (open of its first bar -> close of its last bar). Zero => flat.
    Exit is by constant PARAMS max_hold (close of last session bar) set by the plugin."""
    n = len(df); ts = timestamps(df)
    if n < 2:
        return frame(df)
    tf = ts[1] - ts[0]; tfh = tf / pd.Timedelta(hours=1)
    k = int(round(12 / tfh)); m = 2 * k
    nxt = ts + tf
    o = df["open"].to_numpy(float); c = df["close"].to_numpy(float)
    le = np.zeros(n, bool); se = np.zeros(n, bool)
    for b in range(0, n):
        t = nxt[b]
        if t.minute != 0 or t.hour not in (day_start, (day_start + 12) % 24):
            continue
        rule = day_rule if t.hour == day_start else night_rule
        if rule == "cash":
            continue
        if rule in ("long", "short"):
            sgn = 1 if rule == "long" else -1
        else:
            s0 = b + 1 - m
            if s0 < 0 or b - k < 0:
                continue
            if ts[s0] != t - pd.Timedelta(hours=24) or ts[b - k] != t - pd.Timedelta(hours=12) - tf or ts[b - k] - ts[s0] != pd.Timedelta(hours=12) - tf:
                continue  # gap in data: previous-session return unavailable
            r = c[b - k] / o[s0] - 1
            sgn = int(np.sign(r)) * (1 if rule == "mom" else -1)
        if sgn > 0:
            le[b] = True
        elif sgn < 0:
            se[b] = True
    return frame(df, le=le, se=se)


def sma_(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).mean().to_numpy()
