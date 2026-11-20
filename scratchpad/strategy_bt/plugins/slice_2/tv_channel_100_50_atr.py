"""Archived spec tv_channel_100_50_atr (4h): 100-bar Donchian breakout, stop from prior daily close -/+ 2x daily ATR, 4R target."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "tv_channel_100_50_atr"
PARAMS = {"n_entry": 100, "atr_mult": 2.0, "atr_len": 14, "tp_r": 4.0}
PARAM_GRID = {"n_entry": [75, 100, 125], "atr_mult": [1.5, 2.0, 2.5]}
TIMEFRAMES = ["4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "stop_loss", "take_profit", "timeframes"]
DEVIATIONS = [
    "TRAILING STOP (starts at 2R, steps 1R) NOT implemented - harness has only a fixed stop/target per trade. Material: results are for a fixed 1R-stop / 4R-target version. 'exit' field only partly implemented (stop/TP; the 50-bar exit channel is computed-but-unused per spec notes).",
    "Daily ATR14 (Wilder) and prior daily close built by grouping the 4h frame into UTC days and shifting one full day (equivalent to security(...)[1] with lookahead off); needs timestamps (recovered by s2_lib.timestamps).",
    "Risk R = entry - stop where entry approximated by the signal-bar close (actual fill is the next open); stop distance converted to a fraction of the signal close (stop_pct); TP = tp_r * stop_pct. Entries with R<=0 skipped (spec 'risk>0').",
    "1%-risk position sizing replaced by harness fixed notional. Breakout levels use previous n_entry bars excluding the current bar.",
]

def signals(df, n_entry=100, atr_mult=2.0, atr_len=14, tp_r=4.0):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); n = len(c)
    ts = L.timestamps(df); day = ts.normalize()
    g = pd.DataFrame({"h": h, "l": l, "c": c}).groupby(day.to_numpy()).agg(h=("h", "max"), l=("l", "min"), c=("c", "last"))
    datr = pd.Series(L.tr_atr(g.h.to_numpy(), g.l.to_numpy(), g.c.to_numpy(), atr_len), index=g.index)
    # first-day TR uses h-l (no prev close); Pine ta.atr same. Shift one day for causal alignment.
    prev_atr = datr.shift(1).reindex(day).to_numpy(); prev_c = g.c.shift(1).reindex(day).to_numpy()
    up = L.prior_extreme(h, n_entry, "max"); lo = L.prior_extreme(l, n_entry, "min")
    with np.errstate(invalid="ignore"):
        long_stop = prev_c - atr_mult * prev_atr; short_stop = prev_c + atr_mult * prev_atr
        rl = c - long_stop; rs = short_stop - c
        le = (c > up) & (rl > 0); se = (c < lo) & (rs > 0)
        risk = np.where(le, rl, np.where(se, rs, np.nan))
    stop_pct = risk / c
    return L.frame(df, le=le, se=se, stop_pct=stop_pct, tp_pct=tp_r * stop_pct)
