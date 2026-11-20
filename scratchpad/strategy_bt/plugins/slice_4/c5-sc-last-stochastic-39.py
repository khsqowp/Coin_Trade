import numpy as np
import pandas as pd

SPEC_ID = "c5-sc-last-stochastic-39"
PARAMS = {"length": 39, "week_bars": 5}
PARAM_GRID = {"length": [35, 39, 43], "week_bars": [5]}
TIMEFRAMES = ["1d"]
SIDES = "both"
DEVIATIONS = [
    "The prior-week close high/low is represented by the maximum/minimum close over the preceding five daily bars, excluding the current bar.",
    "Fast %K is the unsmoothed 39-period stochastic; optional 3-SMA, OBV confirmation, and 40/60 alternatives are omitted because the specification labels them optional and gives no enabled default.",
    "Exit rules are direction-specific: long exits on the bearish stochastic cross with the prior-week-low-close condition; short exits on the bullish cross with the prior-week-high-close condition, implementing the stated stop-and-reverse concept without same-bar reversal.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "filters", "timeframes"]

def signals(df, length=39, week_bars=5):
    n, w = int(length), int(week_bars)
    h, l, c = [df[k].to_numpy(float) for k in ("high", "low", "close")]
    lo = pd.Series(l, index=df.index).rolling(n, min_periods=n).min().to_numpy()
    hi = pd.Series(h, index=df.index).rolling(n, min_periods=n).max().to_numpy()
    k = 100.0 * (c - lo) / (hi - lo)
    prev = np.r_[np.nan, k[:-1]]
    up = (prev <= 50.) & (k > 50.)
    down = (prev >= 50.) & (k < 50.)
    prior_hi = pd.Series(c, index=df.index).shift(1).rolling(w, min_periods=w).max().to_numpy()
    prior_lo = pd.Series(c, index=df.index).shift(1).rolling(w, min_periods=w).min().to_numpy()
    long_entry = up & (c > prior_hi)
    short_entry = down & (c < prior_lo)
    long_exit = down & (c < prior_lo)
    short_exit = up & (c > prior_hi)
    return pd.DataFrame({"long_entry": long_entry, "short_entry": short_entry, "long_exit": long_exit, "short_exit": short_exit}, index=df.index).fillna(False)
