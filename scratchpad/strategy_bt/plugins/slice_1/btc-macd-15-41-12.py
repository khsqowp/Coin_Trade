"""BTC daily MACD(15,41,12) signal-line cross, stop-and-reverse."""
import numpy as np
import pandas as pd

def _ema(x, n):
    """EMA seeded at first value (same convention as common.indicators.ema)."""
    return pd.Series(np.asarray(x, float)).ewm(span=int(n), adjust=False).mean().to_numpy()

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

SPEC_ID = "btc-macd-15-41-12"
PARAMS = {"fast": 15, "slow": 41, "signal": 12}
PARAM_GRID = {"fast": [12, 15, 18], "slow": [35, 41, 47]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is BTC only; harness pools BTC/ETH/BNB/SOL/XRP daily bars with the same rule.",
    "MACD = EMA(fast)-EMA(slow) of close, signal = EMA(signal) of MACD; EMAs seeded at the first close (harness convention); signals suppressed for the first slow+signal bars as EMA warm-up (not in spec).",
    "Execution timing unspecified in spec: signal at daily close, fill at next daily open (harness contract).",
    "Always-in reversal: harness cannot fill an exit and the opposite entry on the same open, so the reversal entry fills one bar later (HARNESS_ISSUES.md #1).",
    "Grid axes fast/slow are neighbours of the archived 15/41; signal stays 12.",
]

def signals(df, fast=15, slow=41, signal=12):
    c = df.close.to_numpy(float)
    m = _ema(c, fast) - _ema(c, slow); s = _ema(m, signal)
    up = _crossover(m, s); dn = _crossover(s, m)
    warm = np.arange(len(c)) < int(slow) + int(signal)
    up &= ~warm; dn &= ~warm
    return _frame(df, _sticky(up, up, dn), _sticky(dn, dn, up), dn, up)
