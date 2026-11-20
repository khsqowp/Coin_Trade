"""Archived spec jesse_rsi2 (Connors RSI2 on daily)."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "jesse_rsi2"
PARAMS = {"rsi_lo": 10, "rsi_len": 2, "sma_exit": 5, "sma_trend": 200}
PARAM_GRID = {"rsi_lo": [5, 10, 15]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "filters", "timeframes"]
DEVIATIONS = [
    "Short threshold tied to the long one as 100-rsi_lo (spec default 90 = 100-10); the grid varies both together.",
    "RSI is Wilder (TA-Lib) RSI(2); price = close; signal at bar close, next-open fill; exit when close>SMA5 (long) / close<SMA5 (short).",
    "All-in sizing replaced by harness fixed notional. Only the daily timeframe (spec claim) is run: few trades expected.",
]

def signals(df, rsi_lo=10, rsi_len=2, sma_exit=5, sma_trend=200):
    c = df.close.to_numpy(float); r = L.rsi_wilder(c, int(rsi_len))
    s5 = L.sma_(c, sma_exit); s200 = L.sma_(c, sma_trend)
    with np.errstate(invalid="ignore"):
        return L.frame(df, le=(c > s200) & (r <= rsi_lo), se=(c < s200) & (r >= 100 - rsi_lo), lx=c > s5, sx=c < s5)
