"""Archived spec c4-vwap-bollinger-bands: long when high > BB upper, close when low < BB lower."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "c4-vwap-bollinger-bands"
PARAMS = {"length": 20, "mult": 2.0}
PARAM_GRID = {"length": [15, 20, 25], "mult": [1.5, 2.0, 2.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "exit", "timeframes"]
DEVIATIONS = [
    "Despite the name, the archived calls use ta.sma(src, length) (no VWAP); BB basis = SMA(close,length), bands = basis +/- mult*population stdev. src assumed close, offset 0.",
    "Conditions evaluated at bar close (high>upper, low<lower of the signal bar), fill at next open. If both occur on one bar the strategy enters only when flat / exits when long (engine order).",
    "Spec timeframe unspecified; 1h and 4h run.",
]

def signals(df, length=20, mult=2.0):
    from common.indicators import bollinger
    _, up, lo = bollinger(df.close.to_numpy(float), int(length), mult)
    with np.errstate(invalid="ignore"):
        return L.frame(df, le=df.high.to_numpy(float) > up, lx=df.low.to_numpy(float) < lo)
