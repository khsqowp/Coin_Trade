"""wbburgin Volatility Range Breakout: breakouts of volatility-weighted bands, exit on cross of band midpoint."""
import numpy as np
import pandas as pd

def _sma(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).mean().to_numpy()

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

SPEC_ID = "c4-volatility-range-breakout-strategy-wbburgin"
PARAMS = {"vm1": 100, "vol_len": 100}
PARAM_GRID = {"vm1": [75, 100, 150], "vol_len": [75, 100, 150]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Rule from the cited Pine source (Volatility Range Breakout Strategy [wbburgin].pine), defaults: volatility = 2*(HH-LL)/(HH+LL) of close over vol_len; bands = close*(1 +/- volatility); the source's wma(price, len, weight) multiplies by a constant (current-bar) weight in both numerator and denominator, so it is exactly a simple moving average of the band series over vm1 bars -> hb1/lb1 = SMA(bands, vm1); hlavg = mean(hb1, lb1).",
    "Long = crossover(high, hb1); short = crossunder(low, lb1); exits ('Volatility MA' default): long exit crossunder(close, hlavg), short exit crossover(close, hlavg). Opposite entry reverses (one-bar-later fill, HARNESS_ISSUES.md #1).",
    "Source has pyramiding=20 with repeated entry signals adding to the position; harness holds one position (no pyramiding). No timeframe claimed: 1h and 4h.",
]

def signals(df, vm1=100, vol_len=100):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    hh = _hh(c, vol_len); ll = _ll(c, vol_len); vol = 2 * (hh - ll) / (hh + ll)
    hb = _sma(c * (1 + vol), vm1); lb = _sma(c * (1 - vol), vm1); mid = (hb + lb) / 2.0
    cx = lambda a, b: np.r_[False, (a[1:] > b[1:]) & (a[:-1] <= b[:-1])]
    up = cx(h, hb); dn = cx(lb, l)                # crossunder(low, lb1)
    lx = cx(mid, c); sx = cx(c, mid)              # crossunder(close, hlavg) ; crossover(close, hlavg)
    lxt = lx | dn; sxt = sx | up
    return _frame(df, _sticky(up, sxt, lxt), _sticky(dn, lxt, sxt), lxt, sxt)
