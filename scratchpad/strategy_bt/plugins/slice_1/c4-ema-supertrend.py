"""hasnocool 'EMA & Supertrend' Pine strategy: long-only EMA21/55 + EMA233 trend entry, exit on close under EMA55."""
import numpy as np
import pandas as pd

def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()

def _crossover(a, b):
    """a[t] > b[t] and a[t-1] <= b[t-1] (Pine ta.crossover); False where NaN."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    out = np.zeros(len(a), bool)
    if len(a) > 1:
        out[1:] = (a[1:] > b[1:]) & (a[:-1] <= b[:-1])
    return out

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "c4-ema-supertrend"
PARAMS = {"len1": 21, "len2": 55, "len4": 233}
PARAM_GRID = {"len1": [15, 21, 28], "len2": [45, 55, 70]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "The archived spec text ('time is at least start') is lossy; the real trading rule was taken from the cited Pine source (hasnocool/tradingview-pine-scripts 'EMA & Supertrend.pine'): Enterlong = crossover(ema1,ema2) or (close>ema1 and close>ema2 and ema1>ema2 and close>ema4) [Pine precedence: `and` binds tighter than `or`, so the ema4 filter applies only to the state branch, not the crossover branch]; Exitlong = crossunder(close, ema2). The Supertrend plot in the source is cosmetic and does not enter the trading logic.",
    "Short side is commented out in the source -> long-only. Date window (start 2008) irrelevant to cached data. No timeframe claimed: run on 1h and 4h.",
    "Entry condition is state-based (re-evaluated every bar while flat) as in Pine; sizing = harness fixed notional (source: 100% equity).",
    "Signals suppressed for the first len4 bars as EMA warm-up (EMAs seeded at first close).",
]

def signals(df, len1=21, len2=55, len4=233):
    c = df.close.to_numpy(float); n = len(c)
    e1 = _ema(c, len1); e2 = _ema(c, len2); e4 = _ema(c, len4)
    enter = _crossover(e1, e2) | ((c > e1) & (c > e2) & (e1 > e2) & (c > e4))
    exit_ = _crossover(e2, c)
    enter &= np.arange(n) >= int(len4)
    z = np.zeros(n, bool)
    return _frame(df, enter, z, exit_, z)
