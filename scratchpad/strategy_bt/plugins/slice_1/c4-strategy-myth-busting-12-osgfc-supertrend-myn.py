"""MYN Strategy Myth-Busting #12: one-sided Gaussian filter cross + Supertrend confirmation, reversal on filter cross."""
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

def _sticky(entry, opp_exit, own_exit):
    """Harness workaround (see HARNESS_ISSUES.md #1): a same-bar reversal cannot fill at the exit bar's open, so a
    reversal entry signal is repeated one bar later (unless the new position's own exit fired meanwhile)."""
    e = np.asarray(entry, bool); ox = np.asarray(opp_exit, bool); wx = np.asarray(own_exit, bool)
    prev = np.zeros(len(e), bool)
    if len(e) > 1:
        prev[1:] = (e[:-1] & ox[:-1]) & ~wx[1:]
    return e | prev

SPEC_ID = "c4-strategy-myth-busting-12-osgfc-supertrend-myn"
PARAMS = {"smthper": 10, "extrasmthper": 10, "factor": 3.0, "st_atr": 10}
PARAM_GRID = {"extrasmthper": [8, 10, 14], "factor": [2.5, 3.0, 3.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Archived conditions are abstract (longConditionCalc, calcPeriod ...); real logic from the cited Pine source (Strategy Myth-Busting #12 - OSGFC+SuperTrend - [MYN].pine) with all defaults: source=Close, one-sided Gaussian filter on Fibonacci levels with smthper=10 (reduces to a Gaussian-weighted mean of the last 11 closes), then 2-pole Ehlers smoother (extrasmthper=10); goLong = crossover(out, out[1]), goShort = crossunder(out, out[1]); Supertrend(10, factor 3) must agree (direction<0 long / >0 short); ADX filter disabled (default); lookback-validation inputs 0.",
    "Pine `ta.barssince(x) > 0` is NA-false until x has occurred once, so entries only become possible after the first opposite filter cross and the first opposite Supertrend bar have occurred; reproduced via 'seen before' flags.",
    "Exit: opposite filter cross (closeLong = goShort, closeShort = goLong). Stop-loss input default 999% = disabled. Take-profit default is 100% of price with 100% of the position: applied as tp_pct=1.0 (a long doubling closes; for shorts a 100% gain is unreachable). The Kaufman/T3/AMA smoothing options only affect the unused 'HAB' sources and are not implemented.",
    "Reversal on opposite entry fills one bar later (HARNESS_ISSUES.md #1). Sizing = harness fixed notional (source: 10% equity). Signals suppressed for first 60 bars.",
    "No timeframe claimed: 1h and 4h.",
]

def _weights(p):
    lv = []; t1, t2, nxt = 0, 1, 1
    for _ in range(p + 1):
        lv.append(nxt); t1 = t2; t2 = nxt; nxt = t1 + t2
    size = lv[p]
    w = np.array([np.exp(-i * i * 9.0 / ((size + 1) * (size + 1))) if i < size else 0.0 for i in range(p + 1)])
    return w / w.sum()

def _twopole(src, per):
    a1 = np.exp(-1.414 * np.pi / per); b1 = 2 * a1 * np.cos(1.414 * np.pi / per)
    c2 = b1; c3 = -a1 * a1; c1 = 1 - c2 - c3
    f = np.zeros(len(src))
    for i in range(len(src)):
        f[i] = src[i] if i < 3 else c1 * src[i] + c2 * f[i - 1] + c3 * f[i - 2]
    return f

def signals(df, smthper=10, extrasmthper=10, factor=3.0, st_atr=10):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    out1 = np.convolve(c, _weights(int(smthper)))[:n]     # nz() of missing history = 0
    out = _twopole(out1, float(extrasmthper))
    go_long = np.zeros(n, bool); go_short = np.zeros(n, bool)
    go_long[2:] = (out[2:] > out[1:-1]) & (out[1:-1] <= out[:-2])
    go_short[2:] = (out[2:] < out[1:-1]) & (out[1:-1] >= out[:-2])
    d, _ = _supertrend(h, l, c, int(st_atr), float(factor)); bull = d < 0; bear = d > 0
    prior = lambda x: np.r_[False, np.maximum.accumulate(x)[:-1]]   # x occurred strictly before this bar
    long_c = go_long & prior(go_short) & bull & prior(bear)
    short_c = go_short & prior(go_long) & bear & prior(bull)
    warm = np.arange(n) >= 60
    long_c &= warm; short_c &= warm
    lx = go_short; sx = go_long
    le = _sticky(long_c, go_long, lx); se = _sticky(short_c, go_short, sx)
    return _frame(df, le, se, lx, sx, tp_pct=np.full(n, 1.0))
