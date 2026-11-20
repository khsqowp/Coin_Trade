"""Daily IBS and rolling-range lower-band mean reversion."""
import numpy as np
import pandas as pd

SPEC_ID = "ibs-range-break-meanrev"
PARAMS = {"n_high": 10, "n_range": 25, "mult": 2.5, "ibs_max": 0.30}
PARAM_GRID = {"mult": [2.0, 2.5, 3.0], "ibs_max": [0.2, 0.3, 0.4]}
TIMEFRAMES = ["1d"]
SIDES = "long"
DEVIATIONS = [
    "The archived specification names SPY; this implementation is applied to crypto daily bars.",
    "Signals execute at the next open under the harness rather than at the signal close.",
    "The exit condition compares the current close with the previous bar high.",
]
IMPLEMENTED_FIELDS = ["entry_long", "exit", "filters", "timeframes"]


def signals(df, n_high=10, n_range=25, mult=2.5, ibs_max=0.30):
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    lower = high.rolling(int(n_high), min_periods=int(n_high)).max() - float(mult) * (high - low).rolling(int(n_range), min_periods=int(n_range)).mean()
    denom = high - low
    ibs = (close - low) / denom.where(denom != 0)
    entry = (close < lower) & (ibs < float(ibs_max))
    prev_high = high.shift(1)
    exit_ = close > prev_high
    out = pd.DataFrame({"long_entry": entry, "short_entry": False, "long_exit": exit_, "short_exit": False}, index=df.index)
    return out.fillna(False).astype(bool)
