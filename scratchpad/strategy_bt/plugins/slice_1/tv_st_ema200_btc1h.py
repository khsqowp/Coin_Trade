"""Bitcoin SuperFlip: Supertrend(10, 1.8) flips filtered by EMA200, reverse on opposite flip."""
import numpy as np
import pandas as pd

def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()

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

def _sticky(entry, opp_exit, own_exit):
    """Harness workaround (see HARNESS_ISSUES.md #1): a same-bar reversal cannot fill at the exit bar's open, so a
    reversal entry signal is repeated one bar later (unless the new position's own exit fired meanwhile)."""
    e = np.asarray(entry, bool); ox = np.asarray(opp_exit, bool); wx = np.asarray(own_exit, bool)
    prev = np.zeros(len(e), bool)
    if len(e) > 1:
        prev[1:] = (e[:-1] & ox[:-1]) & ~wx[1:]
    return e | prev

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "tv_st_ema200_btc1h"
PARAMS = {"factor": 1.8, "ema_len": 200, "atr_len": 10}
PARAM_GRID = {"factor": [1.5, 1.8, 2.1], "ema_len": [150, 200, 250]}
TIMEFRAMES = ["1h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is a lossy summary and the TradingView source was not readable here: implemented from the spec text. Long = Supertrend direction flips bullish AND close > EMA(ema_len); short = flips bearish AND close < EMA. Exit = opposite flip (regardless of the EMA filter). Supertrend per Pine ta.supertrend (hl2, RMA ATR).",
    "Optional ADX(14,14)>20 filter, optional 4% stop and 8% target are OFF by default per spec and are not implemented. Claimed timeframe BTCUSD 1h kept; harness pools the 5 majors. Reversal on an opposite flip that passes the filter fills one bar later (HARNESS_ISSUES.md #1).",
]

def signals(df, factor=1.8, ema_len=200, atr_len=10):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    d, _ = _supertrend(h, l, c, int(atr_len), float(factor)); bull = d == -1
    fu = np.zeros(n, bool); fd = np.zeros(n, bool)
    fu[1:] = bull[1:] & ~bull[:-1]; fd[1:] = ~bull[1:] & bull[:-1]
    e = _ema(c, ema_len); warm = np.arange(n) >= int(ema_len)
    le = fu & (c > e) & warm; se = fd & (c < e) & warm
    return _frame(df, _sticky(le, fu, fd), _sticky(se, fd, fu), fd, fu)
