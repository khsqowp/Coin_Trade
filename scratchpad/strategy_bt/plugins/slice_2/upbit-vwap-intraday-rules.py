"""Archived spec upbit-vwap-intraday-rules: trend variant, hold while close > session VWAP (session = 09:00 KST = 00:00 UTC)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "upbit-vwap-intraday-rules"
PARAMS = {}
PARAM_GRID = {}
TIMEFRAMES = ["4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "exit", "filters"]
DEVIATIONS = [
    "Only the 'trend variant' (entry_long) is implemented: long while close > session VWAP, exit when close <= VWAP. The dip-threshold variants (0.3/0.5/1/2%) have no stated entry rule in the spec, so they are NOT implemented and no grid is run.",
    "VWAP from OHLCV bars: cumulative sum(typical price (H+L+C)/3 * volume)/cumulative volume since 00:00 UTC (= 09:00 KST); bar volume used instead of trade-size-weighted ticks.",
    "Bar-close signal, next-open fill (as spec filter says). Unstated: the first bar of a session already has VWAP=its own typical price. Positions are not force-closed at the session reset; the exit comes from the close<=VWAP rule.",
    "Spec timeframe not stated; 1h+4h exceeded the 600s hard timeout in the first run (bar-by-bar trades every VWAP cross, ~10^4 trades), so only 4h is run.",
]

def signals(df):
    ts = L.timestamps(df)
    day = pd.Series(ts.normalize().to_numpy())
    tp = (df.high + df.low + df.close).to_numpy(float) / 3
    v = df.volume.to_numpy(float)
    pv = pd.Series(tp * v).groupby(day.to_numpy()).cumsum().to_numpy()
    vv = pd.Series(v).groupby(day.to_numpy()).cumsum().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        vwap = pv / vv
    c = df.close.to_numpy(float)
    above = c > vwap
    return L.frame(df, le=above, lx=~above & np.isfinite(vwap))
