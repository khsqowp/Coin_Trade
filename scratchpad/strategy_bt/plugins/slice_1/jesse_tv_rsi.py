"""Jesse TradingView RSI: long on RSI(5) crossing above 35; exit RSI<75 cross or <10 cross; -5% stop, +10% target."""
import numpy as np
import pandas as pd

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "jesse_tv_rsi"
PARAMS = {"rsi": 5, "xparam": 75}
PARAM_GRID = {"rsi": [5, 7, 10], "xparam": [70, 75, 80]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited source (jesse TradingView_RSI): long when RSI(rsi) crosses above 35 (prev <= 35, now > 35); close when RSI crosses below xparam (prev >= x, now < x) or below 10; stop at 0.95*entry, take profit at 1.10*entry (jesse limit/stop orders, filled by harness stop/tp logic).",
    "Wilder RSI (SMA seed) implemented here; jesse uses TA-Lib RSI. Leverage 3x ignored (harness fixed notional, unleveraged returns). No timeframe claimed (crypto): 1h and 4h. Jesse 'crossed' helper approximated by prev/current comparison.",
]

def _rsi(c, n):
    c = np.asarray(c, float); n = int(n); out = np.full(len(c), np.nan)
    if len(c) <= n: return out
    d = np.diff(c); g = np.maximum(d, 0.0); ls = np.maximum(-d, 0.0)
    ag = g[:n].mean(); al = ls[:n].mean()
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n, len(d)):
        ag = (ag * (n - 1) + g[i]) / n; al = (al * (n - 1) + ls[i]) / n
        out[i + 1] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out

def signals(df, rsi=5, xparam=75):
    c = df.close.to_numpy(float); n = len(c)
    r = _rsi(c, rsi); p = np.r_[np.nan, r[:-1]]
    le = (p <= 35) & (r > 35)
    lx = ((p >= xparam) & (r < xparam)) | ((p >= 10) & (r < 10))
    z = np.zeros(n, bool)
    return _frame(df, le, z, lx, z, stop_pct=np.full(n, 0.05), tp_pct=np.full(n, 0.10))
