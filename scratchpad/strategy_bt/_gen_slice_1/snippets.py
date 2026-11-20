"""Shared code snippets textually inlined into each slice_1 plugin (plugins must be self-contained)."""
IMPORTS = "import numpy as np\nimport pandas as pd\n"

EMA = '''
def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()
'''
SMA = '''
def _sma(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).mean().to_numpy()
'''
HHLL = '''
def _hh(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).max().to_numpy()

def _ll(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).min().to_numpy()
'''
SHIFT = '''
def _shift(x, k):
    x = np.asarray(x, float); k = int(k)
    if k <= 0: return x.copy()
    out = np.full(len(x), np.nan)
    if k < len(x): out[k:] = x[:-k]
    return out
'''
CROSS = '''
def _crossover(a, b):
    """a[t] > b[t] and a[t-1] <= b[t-1] (Pine ta.crossover); False where NaN."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    out = np.zeros(len(a), bool)
    if len(a) > 1:
        out[1:] = (a[1:] > b[1:]) & (a[:-1] <= b[:-1])
    return out
'''
ATR = '''
def _atr(h, l, c, n):
    """Pine ta.atr: RMA of true range (tr[0] = high-low), SMA seed."""
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float); n = int(n)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.nan_to_num(np.abs(h - pc), nan=0.0), np.nan_to_num(np.abs(l - pc), nan=0.0)])
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        out[n - 1] = tr[:n].mean()
        for i in range(n, len(c)):
            out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out
'''
STICKY = '''
def _sticky(entry, opp_exit, own_exit):
    """Harness workaround (see HARNESS_ISSUES.md #1): a same-bar reversal cannot fill at the exit bar's open, so a
    reversal entry signal is repeated one bar later (unless the new position's own exit fired meanwhile)."""
    e = np.asarray(entry, bool); ox = np.asarray(opp_exit, bool); wx = np.asarray(own_exit, bool)
    prev = np.zeros(len(e), bool)
    if len(e) > 1:
        prev[1:] = (e[:-1] & ox[:-1]) & ~wx[1:]
    return e | prev
'''
FRAME = '''
def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out
'''
SUPERTREND = '''
def _supertrend(h, l, c, n, mult):
    """Pine v5 ta.supertrend(mult, n) on hl2 with RMA ATR. Returns direction (-1 bullish, +1 bearish)."""
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float); N = len(c)
    atr = _atr(h, l, c, n); hl2 = (h + l) / 2.0
    up = hl2 + mult * atr; lo = hl2 - mult * atr
    lf = np.full(N, np.nan); uf = np.full(N, np.nan); st = np.full(N, np.nan); d = np.ones(N, int)
    for i in range(N):
        if np.isnan(atr[i]):
            continue
        pl = lf[i - 1] if i > 0 and not np.isnan(lf[i - 1]) else 0.0
        pu = uf[i - 1] if i > 0 and not np.isnan(uf[i - 1]) else 0.0
        cp = c[i - 1] if i > 0 else np.nan          # close[1] is na on the first bar (no wrap-around)
        lv = lo[i] if (lo[i] > pl or cp < pl) else pl
        uv = up[i] if (up[i] < pu or cp > pu) else pu
        lf[i] = lv; uf[i] = uv
        if i == 0 or np.isnan(atr[i - 1]):
            d[i] = 1
        elif st[i - 1] == pu:
            d[i] = -1 if c[i] > uv else 1
        else:
            d[i] = 1 if c[i] < lv else -1
        st[i] = lv if d[i] == -1 else uv
    return d, st
'''

TIMES = '''
import os
from pathlib import Path

_TIME_CACHE = {}

def _times(df, tf):
    """Timestamps of df bars. The harness passes TRAIN/TEST slices with the DatetimeIndex dropped (RangeIndex), see
    HARNESS_ISSUES.md #2; in that case recover the timestamps by exact OHLCV matching against the cached parquet files
    (same data the harness loaded). Pure metadata lookup: no future values are used by the signal logic."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df.index
    n = len(df)
    c = df.close.to_numpy(float); o = df.open.to_numpy(float); v = df.volume.to_numpy(float)
    key = (n, float(c[0]), float(c[-1]), float(o[0]), float(v[0]))
    if key in _TIME_CACHE:
        return _TIME_CACHE[key]
    dirs = [Path(os.environ["STRATEGY_BT_DATA_DIR"])] if os.environ.get("STRATEGY_BT_DATA_DIR") else []
    dirs.append(Path(__file__).resolve().parents[3] / "bb_stoch_stc" / "data")
    for d in dirs:
        for f in sorted(d.glob(f"*_{tf}.parquet")):
            p = pd.read_parquet(f)
            pc = p.close.to_numpy(float); po = p.open.to_numpy(float); pv = p.volume.to_numpy(float)
            for s in np.flatnonzero((pc == c[0]) & (po == o[0]) & (pv == v[0])):
                if s + n <= len(p) and np.array_equal(pc[s:s + n], c) and np.array_equal(po[s:s + n], o) and np.array_equal(pv[s:s + n], v):
                    _TIME_CACHE[key] = p.index[s:s + n]
                    return _TIME_CACHE[key]
    raise RuntimeError("cannot recover bar timestamps for a RangeIndex frame (cache miss in " + str(dirs) + ")")
'''
