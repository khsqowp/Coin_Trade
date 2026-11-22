"""Fib 0.618 Bollinger bands with EMA trend gate."""
import numpy as np
import pandas as pd

SPEC_ID = "c5-fib-bollinger-0.618-lower-ema-filter"
PARAMS = {"length": 50, "dev_mult": 1.5, "ema_fast": 50, "ema_slow": 200, "stop": 0.05}
PARAM_GRID = {"dev_mult": [1.4, 1.5, 1.6]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
DEVIATIONS = [
    "Band basis and rolling population standard deviation use HLC3 because the spec identifies basis=MA(HLC3) but does not separately name the deviation input.",
    "Entry's close-below OR low-touch condition is implemented as low <= lower_618, the literal inclusive union.",
    "Exit is implemented as a close crossing above upper_618, requiring the previous close at or below its prior band.",
    "Harness fixed stop_pct approximates the source's entry-price 5% stop; harness universe replaces source market selection."
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "stop_loss", "filters", "timeframes"]


def signals(df, length=50, dev_mult=1.5, ema_fast=50, ema_slow=200, stop=0.05, **_):
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    hlc3 = (h + l + c) / 3.0
    basis = pd.Series(hlc3).rolling(int(length), min_periods=int(length)).mean().to_numpy()
    sd = pd.Series(hlc3).rolling(int(length), min_periods=int(length)).std(ddof=0).to_numpy()
    lower = basis - 0.618 * float(dev_mult) * sd
    upper = basis + 0.618 * float(dev_mult) * sd
    ef = pd.Series(c).ewm(span=int(ema_fast), adjust=False, min_periods=1).mean().to_numpy()
    es = pd.Series(c).ewm(span=int(ema_slow), adjust=False, min_periods=1).mean().to_numpy()
    entry = (ef > es) & (l <= lower)
    prevc = np.r_[np.nan, c[:-1]]
    prevu = np.r_[np.nan, upper[:-1]]
    exit_ = (prevc <= prevu) & (c > upper)
    return pd.DataFrame({"long_entry": entry, "short_entry": False, "long_exit": exit_, "short_exit": False,
                         "stop_pct": float(stop)}, index=df.index).fillna(False)
