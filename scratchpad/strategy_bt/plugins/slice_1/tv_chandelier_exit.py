"""Chandelier Exit (ATR 22 x 3, close-based extremes) stop-and-reverse on direction flips."""
import numpy as np
import pandas as pd

def _atr(h, l, c, n):
    """Pine ta.atr: RMA of true range (tr[0] = high-low), SMA seed."""
    h = np.asarray(h, float); l = np.asarray(l, float); c = np.asarray(c, float); n = int(n)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.nan_to_num(np.abs(h - pc), nan=0.0), np.nan_to_num(np.abs(l - pc), nan=0.0)])
    out = np.full(len(c), np.nan)
    if len(c) >= n:
        out[n - 1] = tr[:n].mean()
        for i in range(n, len(c)):
            out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out

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

SPEC_ID = "tv_chandelier_exit"
PARAMS = {"length": 22, "mult": 3.0}
PARAM_GRID = {"length": [18, 22, 26], "mult": [2.5, 3.0, 3.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Spec is a lossy summary of a TradingView INDICATOR (not a strategy); the TradingView source could not be read here. Implemented the standard Chandelier Exit logic (as in the widely used Pine 'Chandelier Exit' study with useClose=true): longStop = highest(close,L) - mult*ATR(L), shortStop = lowest(close,L) + mult*ATR(L), each ratcheted (longStop only rises while close[1] > longStop[1]; shortStop only falls while close[1] < shortStop[1]); dir = 1 if close > shortStop[1], -1 if close < longStop[1], else unchanged (initial 1). Buy on dir -1->1, sell on 1->-1; stop-and-reverse, i.e. the 'stop' IS the flip so no separate stop.",
    "This signal inference was not verified against the original script; treat as the standard-definition test. ATR = Wilder (Pine ta.atr). Reversal fills one bar later (HARNESS_ISSUES.md #1). No timeframe claimed: 1h and 4h.",
]

def signals(df, length=22, mult=3.0):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c); L = int(length)
    atr = float(mult) * _atr(h, l, c, L)
    ls_raw = _hh(c, L) - atr; ss_raw = _ll(c, L) + atr
    ls = np.full(n, np.nan); ss = np.full(n, np.nan); d = np.ones(n, int)
    for i in range(n):
        if np.isnan(ls_raw[i]) or np.isnan(ss_raw[i]):
            continue
        lp = ls[i - 1] if i > 0 and not np.isnan(ls[i - 1]) else ls_raw[i]
        sp = ss[i - 1] if i > 0 and not np.isnan(ss[i - 1]) else ss_raw[i]
        ls[i] = max(ls_raw[i], lp) if c[i - 1] > lp else ls_raw[i]
        ss[i] = min(ss_raw[i], sp) if c[i - 1] < sp else ss_raw[i]
        prev = d[i - 1] if i > 0 else 1
        d[i] = 1 if c[i] > sp else (-1 if c[i] < lp else prev)
    buy = np.zeros(n, bool); sell = np.zeros(n, bool)
    valid = ~np.isnan(ls) & np.r_[False, ~np.isnan(ls[:-1])]
    buy[1:] = (d[1:] == 1) & (d[:-1] == -1); sell[1:] = (d[1:] == -1) & (d[:-1] == 1)
    buy &= valid; sell &= valid
    return _frame(df, _sticky(buy, buy, sell), _sticky(sell, sell, buy), sell, buy)
