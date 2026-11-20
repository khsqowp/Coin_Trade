"""Archived spec tv_supertrend_regime_switch: ADX-regime Supertrend flips, stop = line, TP 2R."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "tv_supertrend_regime_switch"
PARAMS = {"atr_len": 10, "trend_mult": 1.75, "chop_mult": 4.5, "adx_len": 14, "adx_trend": 25, "adx_chop": 20, "tp_r": 2.0}
PARAM_GRID = {"trend_mult": [1.5, 1.75, 2.0], "tp_r": [1.5, 2.0, 3.0]}
TIMEFRAMES = ["1h", "4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "take_profit", "filters", "timeframes"]
DEVIATIONS = [
    "Multiplier rule: 1.75 when ADX>25, 4.5 otherwise (spec gives no value for 20<=ADX<=25; assumed the wide/choppy multiplier). 'Choppy' (no new entries) = ADX<20 (disableChop assumed ON).",
    "Spec timeframe 'any'; 1h and 4h run. Supertrend per Pine ta.supertrend (hl2 +/- mult*RMA-ATR(10)) with per-bar multiplier.",
    "Stop = supertrend line: initial fixed stop at (close - line) at the signal bar via stop_pct (intrabar), PLUS a close-based exit when the supertrend flips against the position (proxy for the trailing line; Pine would fill intrabar). The line-as-trailing-stop is therefore approximated. Material.",
    "R = |signal close - line|; TP = tp_r * R fixed (optional trailing and max-bars not used). Entry reference = signal close, fill = next open. 1% equity-risk sizing replaced by fixed notional.",
    "A flip also reverses: after the close-based exit the opposite entry (a flip event) is missed unless it recurs; entries are flip EVENTS only (one-bar signals).",
]

def signals(df, atr_len=10, trend_mult=1.75, chop_mult=4.5, adx_len=14, adx_trend=25, adx_chop=20, tp_r=2.0):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float)
    adx = L.adx_wilder(h, l, c, adx_len)
    with np.errstate(invalid="ignore"):
        mult = np.where(adx > adx_trend, trend_mult, chop_mult); chop = adx < adx_chop
    line, d = L.supertrend(h, l, c, atr_len, mult)
    pd_ = np.r_[0, d[:-1]]
    up = (d == 1) & (pd_ == -1); dn = (d == -1) & (pd_ == 1)
    ok = np.isfinite(adx)
    le = up & ~chop & ok; se = dn & ~chop & ok
    risk = np.abs(c - line); sp = risk / c
    sp = np.where(le | se, sp, np.nan)
    return L.frame(df, le=le, se=se, lx=dn, sx=up, stop_pct=sp, tp_pct=tp_r * sp)
