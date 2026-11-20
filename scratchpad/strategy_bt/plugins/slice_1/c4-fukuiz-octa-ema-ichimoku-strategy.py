"""Fukuiz Octa-EMA + Ichimoku: long when EMA2>EMA8 and ribbon midpoint above cloud."""
import numpy as np
import pandas as pd

def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()

def _hh(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).max().to_numpy()

def _ll(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).min().to_numpy()

def _shift(x, k):
    x = np.asarray(x, float); k = int(k)
    if k <= 0: return x.copy()
    out = np.full(len(x), np.nan)
    if k < len(x): out[k:] = x[:-k]
    return out

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "c4-fukuiz-octa-ema-ichimoku-strategy"
PARAMS = {"ema2": 11, "ema8": 34}
PARAM_GRID = {"ema2": [8, 11, 14], "ema8": [28, 34, 40]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Archived text is lossy; rule taken from the cited Pine source ('Fukuiz Octa-EMA + Ichimoku (Strategy).pine'): active orders are buy2 = (EMA2 > EMA8) and fukuiz > SenkouA[26] and fukuiz > SenkouB, exit sell2 = EMA2 < EMA8, where fukuiz = (EMA2+EMA8)/2. The cross-based `buy`/`sell` in the source are unused.",
    "SenkouA = Donchian-mid(52) (as in the source, NOT the usual (Tenkan+Kijun)/2) delayed 26 bars; SenkouB = (Tenkan[26]+Kijun[26])/2 with Tenkan=Donchian-mid(9), Kijun=Donchian-mid(26) (source's own, unconventional, definitions). Donchian uses high/low.",
    "Source date window (2017-01-01..2023-12-31) NOT applied (would remove most of the test period). No timeframe claimed: 1h and 4h. State-based entry re-evaluated every flat bar (Pine behaviour). Long-only. 0.25% commission in source replaced by harness costs.",
    "Signals suppressed for the first 120 bars (Ichimoku 52+26 lookback and EMA warm-up).",
]

def signals(df, ema2=11, ema8=34):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    e2 = _ema(c, ema2); e8 = _ema(c, ema8); fk = (e2 + e8) / 2.0
    don = lambda k: (_hh(h, k) + _ll(l, k)) / 2.0
    tenkan = don(9); kijun = don(26); sa = _shift(don(52), 26)
    sb = (_shift(tenkan, 26) + _shift(kijun, 26)) / 2.0
    buy2 = (e2 > e8) & (fk > sa) & (fk > sb) & (np.arange(n) >= 120)
    sell2 = e2 < e8
    z = np.zeros(n, bool)
    return _frame(df, buy2, z, sell2, z)
