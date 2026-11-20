"""Archived spec c4-sunny-supertrend-strategy: ta.supertrend(3.0, 10) flip reversal system."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "c4-sunny-supertrend-strategy"
PARAMS = {"factor": 3.0, "atr_period": 10}
PARAM_GRID = {"factor": [2.5, 3.0, 3.5], "atr_period": [7, 10, 14]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "timeframes"]
DEVIATIONS = [
    "longy/shorty/longexity/shortexity are not defined in the archived spec; assumed: long when ta.supertrend direction is up, short when down, exit long on flip down, exit short on flip up (always-in-market reversal). Date-range inputs ignored.",
    "Entries are level (trend-state) signals, not flip events, because the engine cannot exit and re-enter on the same open: every reversal costs one extra flat bar (entry on the open after the exit).",
    "Spec timeframe unspecified; 1h and 4h run. Supertrend per Pine ta.supertrend (hl2, RMA ATR).",
]

def signals(df, factor=3.0, atr_period=10):
    line, d = L.supertrend(df.high, df.low, df.close, int(atr_period), factor)
    ok = np.isfinite(line)
    return L.frame(df, le=(d == 1) & ok, se=(d == -1) & ok, lx=(d == -1) & ok, sx=(d == 1) & ok)
