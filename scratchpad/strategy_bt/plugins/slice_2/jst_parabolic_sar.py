"""Archived spec jst_parabolic_sar (daily): always-in-market SAR reversal."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "jst_parabolic_sar"
PARAMS = {"af": 0.02, "af_max": 0.2}
PARAM_GRID = {"af": [0.01, 0.02, 0.03], "af_max": [0.1, 0.2, 0.3]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "timeframes"]
DEVIATIONS = [
    "initial_af and step_af both set to the single param `af` (spec: 0.02 / 0.02); af_max default 0.2.",
    "Flip detected when the bar's low/high penetrates the SAR (standard Wilder); this is known only at bar close, so the reversal executes at the NEXT open (spec's SAR stop would fill intrabar).",
    "HARNESS LIMITATION: engine cannot exit and re-enter on the same open, so every reversal is flat for one extra bar (entry happens one bar after the exit). Entries are level signals (trend state).",
    "SAR initialised long at bar 0 (low[0], EP=high[0]); first few bars arbitrary.",
]

def signals(df, af=0.02, af_max=0.2):
    t = L.psar(df.high, df.low, af, af, af_max)
    return L.frame(df, le=t == 1, se=t == -1, lx=t == -1, sx=t == 1)
