"""Ichimoku long & short strategy (cloud-edge stop, risk:reward target, lagging-span exit)."""
import numpy as np
import pandas as pd

def _hh(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).max().to_numpy()

def _ll(x, n):
    return pd.Series(np.asarray(x, float)).rolling(int(n), min_periods=int(n)).min().to_numpy()

def _shift(x, k):
    x = np.asarray(x, float); k = int(k)
    if k <= 0: return x.copy()
    out = np.full(len(x), np.nan)
    if k < len(x): out[k:] = x[:-k]
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

SPEC_ID = "c4-ichimoku-long-and-short-strategy"
PARAMS = {"disp": 26, "rr": 2.0}
PARAM_GRID = {"disp": [22, 26, 30], "rr": [1.5, 2.0, 2.5]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "position_sizing", "filters", "timeframes"]
DEVIATIONS = [
    "Archived conditions are named only (conAbvBase, cloudGreen, ...); definitions taken from the cited Pine source ('Ichimoku Long and Short Strategy.pine'), default exitStrategy='Ichimoku', closeLagBelow/closelagAbove = true. No timeframe claimed: 1h and 4h.",
    "Source quirk reproduced: the `long`/`short` state vars are only cleared by the OPPOSITE entry condition (not by exits), so after a long exits (stop/target/lag) the next long can only occur after a short signal has fired.",
    "Stop = lower (long) / upper (short) cloud edge shifted by `disp` bars; target = open + (open-stop)*rr using the SIGNAL bar's open (source). The harness takes fractions, so both are converted to fractions of the signal-bar CLOSE and applied to the actual next-open fill (levels drift by the open-vs-close gap). Target not above the entry (tp<=0) is dropped.",
    "Lagging-span exit `open < close[disp+1]` (long) / `open > close[disp+1]` (short) uses the signal bar's own open and is filled at the next open. Opposite entry reverses (Pine strategy.entry semantics); reversal fills one bar later (HARNESS_ISSUES.md #1), re-using the cloud levels computed at the signal bar.",
    "Source sizing (10 contracts) replaced by harness fixed notional. Signals suppressed for the first 2*disp+52 bars (cloud lookback).",
]

def signals(df, disp=26, rr=2.0):
    o = df.open.to_numpy(float); h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    disp = int(disp)
    don = lambda k: (_hh(h, k) + _ll(l, k)) / 2.0
    conv = don(9); base = don(26); l1 = (conv + base) / 2.0; l2 = don(52)
    l1d = _shift(l1, disp); l2d = _shift(l2, disp); l1dd = _shift(l1, 2 * disp); l2dd = _shift(l2, 2 * disp)
    raw_l = (conv > base) & (l1 > l2) & (o > l1d) & (o > l2d) & (c > l1dd) & (c > l2dd)
    raw_s = (conv < base) & (l2 > l1) & (o < l1d) & (o < l2d) & (c < l1dd) & (c < l2dd)
    raw_l &= np.arange(n) >= 2 * disp + 52; raw_s &= np.arange(n) >= 2 * disp + 52
    cl = np.zeros(n, bool); cs = np.zeros(n, bool)
    lf = sf = False
    for i in range(n):
        a = (not lf) and bool(raw_l[i]); b = (not sf) and bool(raw_s[i])
        if a: lf, sf = True, False; cl[i] = True
        if b: sf, lf = True, False; cs[i] = True
    lag_c = _shift(c, disp + 1)
    lag_exit_l = o < lag_c; lag_exit_s = o > lag_c
    lx = lag_exit_l | cs; sx = lag_exit_s | cl
    le = _sticky(cl, cl, lx); se = _sticky(cs, cs, sx)
    # absolute stop / target levels set at the original signal bar, carried to a sticky repeat bar
    stop_l = np.minimum(l1d, l2d); tgt_l = o + (o - stop_l) * rr
    stop_s = np.maximum(l1d, l2d); tgt_s = o - (stop_s - o) * rr
    sl = np.full(n, np.nan); tl = np.full(n, np.nan)
    for i in range(n):
        j = i if cl[i] or cs[i] else (i - 1 if i > 0 and (cl[i - 1] or cs[i - 1]) else -1)
        if j < 0: continue
        if cl[j] and le[i]:
            sl[i] = (c[i] - stop_l[j]) / c[i]; t = (tgt_l[j] - c[i]) / c[i]; tl[i] = t if t > 0 else np.nan
        elif cs[j] and se[i]:
            sl[i] = (stop_s[j] - c[i]) / c[i]; t = (c[i] - tgt_s[j]) / c[i]; tl[i] = t if t > 0 else np.nan
    # Off-signal bars get the median signal-bar stop/target distances so the harness's random-entry null (which reuses
    # these columns bar-by-bar, HARNESS_ISSUES.md #3) also applies them. Real entries only use signal-bar values.
    # Fill = EXPANDING median of past signal-bar values (causal; a full-sample median would look ahead).
    ent = le | se
    fs = pd.Series(np.where(ent, sl, np.nan)).expanding(min_periods=1).median().to_numpy()
    ft = pd.Series(np.where(ent, tl, np.nan)).expanding(min_periods=1).median().to_numpy()
    sl = np.where(ent, sl, fs); tl = np.where(ent, tl, ft)
    return _frame(df, le, se, lx, sx, stop_pct=sl, tp_pct=tl)
