"""Turtle system: 55-bar Donchian breakout entries, 20-bar Donchian exits, long/short."""
import numpy as np
import pandas as pd

def _hh(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).max().to_numpy()

def _ll(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).min().to_numpy()

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

SPEC_ID = "c4-turtle-trend-trading-system-racer8"
PARAMS = {"n": 55, "e": 20}
PARAM_GRID = {"n": [40, 55, 70], "e": [15, 20, 25]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Exact rule from the cited Pine source (Turtle Trend Trading System [racer8].pine): long if close > highest(high,n)[1]; short if close < lowest(low,n)[1]; close long if low < lowest(low,e)[1]; close short if high > highest(high,e)[1]. Entries are state-based (re-fired every bar the condition holds while flat, as Pine does).",
    "Exit conditions are evaluated at bar close (Pine default calc-on-close) and filled at the next open (not at the channel level intrabar). Reversal fills one bar later (HARNESS_ISSUES.md #1). No timeframe claimed: 1h and 4h. Source sizing replaced by harness fixed notional.",
]

def signals(df, n=55, e=20):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); N = len(c)
    sh1 = lambda x: np.r_[np.nan, x[:-1]]
    HI = sh1(_hh(h, n)); LO = sh1(_ll(l, n)); hi = sh1(_hh(h, e)); lo = sh1(_ll(l, e))
    ent_l = c > HI; ent_s = c < LO
    lx = l < lo; sx = h > hi
    lxt = lx | ent_s; sxt = sx | ent_l
    return _frame(df, _sticky(ent_l, sxt, lxt), _sticky(ent_s, lxt, sxt), lxt, sxt)
