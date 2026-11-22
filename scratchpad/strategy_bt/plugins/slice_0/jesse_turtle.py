"""Daily Turtle Donchian breakout and ATR stop signals."""
import numpy as np
import pandas as pd
from common.indicators import atr

SPEC_ID = "jesse_turtle"
PARAMS = {"entry": 20, "exit": 10, "atr_n": 20, "stop_n": 2.0}
PARAM_GRID = {"entry": [15, 20, 25], "exit": [8, 10, 12]}
TIMEFRAMES = ["1d"]
SIDES = "both"
DEVIATIONS = [
    "The S1 skip-after-winner filter is referenced but unclear and is not implemented.",
    "Pyramiding every 0.5N up to four units is not implemented; the strategy uses one position unit.",
    "Position sizing is fixed notional because the harness does not implement the specification's 1% equity risk unit.",
    "Breakout signals fill at the next open under the harness instead of at an intrabar breakout level.",
    "The 2N stop is measured from the single position entry fill.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "timeframes"]


def signals(df, entry=20, exit=10, atr_n=20, stop_n=2.0):
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    prior_upper = high.shift(1).rolling(int(entry), min_periods=int(entry)).max()
    prior_lower = low.shift(1).rolling(int(entry), min_periods=int(entry)).min()
    long_entry = high >= prior_upper
    short_entry = low <= prior_lower
    exit_lower = low.shift(1).rolling(int(exit), min_periods=int(exit)).min()
    exit_upper = high.shift(1).rolling(int(exit), min_periods=int(exit)).max()
    long_exit = (low <= exit_lower) | short_entry
    short_exit = (high >= exit_upper) | long_entry
    distance = float(stop_n) * atr(high.to_numpy(float), low.to_numpy(float), close.to_numpy(float), int(atr_n))
    out = pd.DataFrame({"long_entry": long_entry, "short_entry": short_entry, "long_exit": long_exit, "short_exit": short_exit, "stop_pct": np.nan, "atr_stop": distance}, index=df.index)
    return out.fillna({"long_entry": False, "short_entry": False, "long_exit": False, "short_exit": False}).astype({"long_entry": bool, "short_entry": bool, "long_exit": bool, "short_exit": bool})
