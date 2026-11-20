"""Archived spec pk_rsi_directional (freqtrade, 1h): RSI(4) oversold cross-up above EMA100."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "pk_rsi_directional"
PARAMS = {"rsi_len": 4, "ema_len": 100, "buy_lvl": 15, "sell_lvl": 85}
PARAM_GRID = {"buy_lvl": [10, 15, 20], "sell_lvl": [80, 85, 90]}
TIMEFRAMES = ["1h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "exit", "stop_loss", "filters", "timeframes"]
DEVIATIONS = [
    "EMA100 source not stated; EMA of close assumed.",
    "Main variant only (RSI4/EMA100/-10% stop); 'slow variant' in notes not run. minimal_roi (commented-out alt) not implemented.",
    "RSI Wilder (TA-Lib), EMA TA-Lib seeded; crossed_above(x,L)= x[t]>L & x[t-1]<=L. Signals at candle close, next-open fill.",
    "Stop -10% via stop_pct=0.10 (intrabar, harness).",
]

def signals(df, rsi_len=4, ema_len=100, buy_lvl=15, sell_lvl=85):
    l = df.low.to_numpy(float); r = L.rsi_wilder(df.close, int(rsi_len)); e = L.ema_ta(df.close.to_numpy(float), int(ema_len))
    with np.errstate(invalid="ignore"):
        entry = L.crossed_above(r, buy_lvl) & (l > e)
        ex = L.crossed_above(r, sell_lvl) | (l < e)
    return L.frame(df, le=entry, lx=ex, stop_pct=np.full(len(l), 0.10))
