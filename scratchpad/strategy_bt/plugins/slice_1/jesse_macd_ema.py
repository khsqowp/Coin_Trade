"""Jesse MACD+EMA100: long while MACD>signal and close>EMA, exit when both flip."""
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

SPEC_ID = "jesse_macd_ema"
PARAMS = {"ema": 100, "fast": 12, "slow": 26, "signal": 9}
PARAM_GRID = {"ema": [75, 100, 150], "signal": [7, 9, 11]}
TIMEFRAMES = ["1h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (jesse example MACD_EMA): should_long = close > EMA(ema) and MACD > signal (state-based, evaluated while flat); liquidate when MACD < signal and close < EMA. Long-only, no stops/targets.",
    "Jesse places a limit order at the current price; harness fills at the next open. All-in sizing replaced by harness fixed notional. EMAs seeded at first close; signals suppressed for the first max(ema, slow+signal) bars.",
]

def signals(df, ema=100, fast=12, slow=26, signal=9):
    c = df.close.to_numpy(float); n = len(c)
    m = _ema(c, fast) - _ema(c, slow); s = _ema(m, signal); e = _ema(c, ema)
    le = (c > e) & (m > s); lx = (c < e) & (m < s)
    le &= np.arange(n) >= max(int(ema), int(slow) + int(signal))
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z)
