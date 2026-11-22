"""Archived spec jesse_donchian: close > prior Donchian upper & close > SMA200, exit close < prior lower."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "jesse_donchian"
PARAMS = {"period": 20, "sma_n": 200}
PARAM_GRID = {"period": [15, 20, 25]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "exit", "filters", "timeframes"]
DEVIATIONS = [
    "Spec shows 6h results; no 6h cache, so 1h and 4h are run.",
    "Donchian bands computed on candles[:-1], i.e. highest high / lowest low of the previous `period` bars excluding the signal bar; signal at bar close, next-open fill.",
    "All-in sizing replaced by harness fixed notional. Exit uses same period as entry (per spec).",
]

def signals(df, period=20, sma_n=200):
    c = df.close.to_numpy(float)
    up = L.prior_extreme(df.high, period, "max"); lo = L.prior_extreme(df.low, period, "min")
    sma = L.sma_(c, sma_n)
    with np.errstate(invalid="ignore"):
        return L.frame(df, le=(c > up) & (c > sma), lx=c < lo)
