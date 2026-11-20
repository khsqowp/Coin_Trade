"""SMA(30)/SMA(150) always-in trend reversal on daily bars."""
import numpy as np
import pandas as pd

def _sma(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).mean().to_numpy()

def _crossover(a, b):
    """a[t] > b[t] and a[t-1] <= b[t-1] (Pine ta.crossover); False where NaN."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    out = np.zeros(len(a), bool)
    if len(a) > 1:
        out[1:] = (a[1:] > b[1:]) & (a[:-1] <= b[:-1])
    return out

def _sticky(entry, opp_exit, own_exit):
    """Harness workaround (see HARNESS_ISSUES.md #1): a same-bar reversal cannot fill at the exit bar's open, so a
    reversal entry signal is repeated one bar later (unless the new position's own exit fired meanwhile)."""
    e = np.asarray(entry, bool); ox = np.asarray(opp_exit, bool); wx = np.asarray(own_exit, bool)
    prev = np.zeros(len(e), bool)
    if len(e) > 1:
        prev[1:] = (e[:-1] & ox[:-1]) & ~wx[1:]
    return e | prev

def _frame(df, le, se, lx, sx, **extra):
    out = pd.DataFrame({"long_entry": np.asarray(le, bool), "short_entry": np.asarray(se, bool),
                        "long_exit": np.asarray(lx, bool), "short_exit": np.asarray(sx, bool)}, index=df.index)
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out

SPEC_ID = "sma-30-150-always-in"
PARAMS = {"fast": 30, "slow": 150}
PARAM_GRID = {"fast": [20, 30, 40], "slow": [120, 150, 180]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec universe is liquid futures; harness pools the 5 crypto majors on daily bars. Execution convention unspecified: signal at daily close, fill at next open.",
    "Position is entered/reversed only AT crossover events (first cross after warm-up); the archived 'always invested while SMA30 > SMA150' state before the first cross is not entered (harness has no start-in-state).",
    "Always-in reversal fills one bar later than the exit (HARNESS_ISSUES.md #1).",
]

def signals(df, fast=30, slow=150):
    c = df.close.to_numpy(float)
    f = _sma(c, fast); s = _sma(c, slow)
    up = _crossover(f, s); dn = _crossover(s, f)
    return _frame(df, _sticky(up, up, dn), _sticky(dn, dn, up), dn, up)
