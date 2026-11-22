"""Daily EMA(5/30) cross and reverse strategy."""
import numpy as np
import pandas as pd
from common.indicators import ema

SPEC_ID = "btc-ema-5-30"
PARAMS = {"fast": 5, "slow": 30}
PARAM_GRID = {"fast": [4, 5, 6], "slow": [25, 30, 35]}
TIMEFRAMES = ["1d"]
SIDES = "both"
DEVIATIONS = [
    "Signals execute at the next open under the harness.",
    "Entry pulses are extended for one bar when there is no opposite cross, because the engine fills the exit at the next open and cannot re-enter on that bar; a reversal therefore exits at one open and re-enters at the following open.",
]
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "timeframes"]


def signals(df, fast=5, slow=30):
    close = pd.to_numeric(df["close"], errors="coerce").to_numpy(float)
    f, s = ema(close, int(fast)), ema(close, int(slow))
    up = np.zeros(len(df), dtype=bool)
    down = np.zeros(len(df), dtype=bool)
    if len(df) > 1:
        up[1:] = (f[1:] > s[1:]) & (f[:-1] <= s[:-1])
        down[1:] = (f[1:] < s[1:]) & (f[:-1] >= s[:-1])
    long_entry = up.copy()
    short_entry = down.copy()
    if len(df) > 1:
        long_entry[1:] |= up[:-1] & ~down[1:]
        short_entry[1:] |= down[:-1] & ~up[1:]
    return pd.DataFrame({"long_entry": long_entry, "short_entry": short_entry, "long_exit": down, "short_exit": up}, index=df.index).fillna(False).astype(bool)
