"""Archived spec btc-monday-intraday: long during Monday (UTC daily bar)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "btc-monday-intraday"
PARAMS = {}
PARAM_GRID = {}
TIMEFRAMES = ["1d"]
SIDES = "long"
IMPLEMENTED_FIELDS = ["entry_long", "exit", "filters", "timeframes"]
DEVIATIONS = [
    "'Start of Monday' = Monday 00:00 UTC (spec says verify timezone vs paper; not verified). Signal on Sunday daily bar close -> fill at Monday open; exit signal on Monday bar close -> fills Tuesday open (= end of Monday).",
    "Spec filter 'BTC only'; the harness pools BTC/ETH/BNB/SOL/XRP and the rule is applied to all of them.",
    "Random-entry null in the harness keeps the Monday exit signals (holds until a following Monday close), so the null hold length differs from the strategy's 1-day hold.",
]

def signals(df):
    dow = L.timestamps(df).dayofweek.to_numpy()
    return L.frame(df, le=(dow == 6), lx=(dow == 0))
