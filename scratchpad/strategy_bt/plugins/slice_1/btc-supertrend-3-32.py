"""BTC daily Supertrend(ATR 3, mult 3.2), long-only flip."""
import numpy as np
import pandas as pd

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

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "btc-supertrend-3-32"
PARAMS = {"atr_len": 3, "mult": 3.2}
PARAM_GRID = {"atr_len": [2, 3, 4], "mult": [2.8, 3.2, 3.6]}
TIMEFRAMES = ["1d"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is BTC only; harness pools BTC/ETH/BNB/SOL/XRP daily bars.",
    "Spec says source does not identify ATR smoothing, price basis or fill timing: assumed TradingView ta.supertrend defaults (hl2 basis, Wilder/RMA ATR), signal at daily close, fill next open.",
    "'Price crosses above Supertrend line' is implemented as the Supertrend direction flip to bullish (close above the upper band); equivalent to the close crossing the plotted line. Exit on flip to bearish.",
    "Long-only per spec filter ('Long-only implementation stated'); entry_short text in spec is the exit condition only.",
]

def signals(df, atr_len=3, mult=3.2):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float)
    d, _ = _supertrend(h, l, c, atr_len, float(mult)); bull = d == -1
    up = np.zeros(len(c), bool); dn = np.zeros(len(c), bool)
    up[1:] = bull[1:] & ~bull[:-1]; dn[1:] = ~bull[1:] & bull[:-1]
    z = np.zeros(len(c), bool)
    return _frame(df, up, z, dn, z)
