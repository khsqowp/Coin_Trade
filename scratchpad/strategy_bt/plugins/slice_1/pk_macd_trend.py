"""paulcpk MACDCrossoverWithTrend: long when MACD<0 crosses above signal with low above EMA100."""
import numpy as np
import pandas as pd

def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "pk_macd_trend"
PARAMS = {"ema": 100, "fast": 12, "slow": 26, "signal": 9}
PARAM_GRID = {"ema": [75, 100, 150], "signal": [7, 9, 11]}
TIMEFRAMES = ["1h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (MACDCrossoverWithTrend.py): buy = macd<0 and crossed_above(macd, signal) and low>EMA100; sell = crossed_below(macd, 0) or low<EMA100; stoploss -20%. The source's minimal_roi tables are commented out -> no ROI exit (spec text 'see source' therefore means none). Trailing stop disabled in source.",
    "Note the source's sell fires whenever low<EMA100, so a position can be closed on the bar after entry only if low dips under the EMA. MACD via harness-style EMAs (TA-Lib seeds with SMA); signals suppressed for the first max(ema, slow+signal) bars. Long-only; fixed notional.",
]

def signals(df, ema=100, fast=12, slow=26, signal=9):
    c = df.close.to_numpy(float); l = df.low.to_numpy(float); n = len(c)
    m = _ema(c, fast) - _ema(c, slow); s = _ema(m, signal); e = _ema(c, ema)
    pm = np.r_[np.nan, m[:-1]]; ps = np.r_[np.nan, s[:-1]]
    cross_up = (m > s) & (pm <= ps)
    le = (m < 0) & cross_up & (l > e)
    lx = ((m < 0) & (pm >= 0)) | (l < e)
    le &= np.arange(n) >= max(int(ema), int(slow) + int(signal))
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z, stop_pct=np.full(n, 0.20))
