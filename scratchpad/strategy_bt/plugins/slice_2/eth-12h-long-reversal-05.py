"""Archived spec eth-12h-long-reversal-05: 12h session calendar rule (day=long, night=rev)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "eth-12h-long-reversal-05"
# max_hold is a constant (bars): the position is closed at the close of the last bar of the 12h session.
PARAMS = {"max_hold": 11}
PARAM_GRID = {}
TIMEFRAMES = ["1h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "filters", "timeframes"]
DAY_START = 5
DAY_RULE = "long"
NIGHT_RULE = "rev"
DEVIATIONS = [
    "Spec names no timeframe; session boundaries 05:00/17:00 UTC need bars aligned to them, so only 1h is run (1h/4h fallback reduced to one timeframe because the harness PARAMS.max_hold is a single constant that cannot vary per timeframe).",
    "Day session = [05:00,17:00) UTC, night = complement. Day rule = long, night rule = rev. 'Previous return of the same session' read literally as the return of the SAME session type 24h earlier (first-bar open -> last-bar close); sign 0 or missing data => flat.",
    "Instrument limited to ETH in the source but the harness pools 5 majors (BTC/ETH/BNB/SOL/XRP) - rule applied identically to all.",
    "Every session is closed (at last-bar close via max_hold) and re-opened at next open, so consecutive same-direction sessions pay fees twice (literal 'close/recompute at session boundary'); fees/slippage per harness, no funding.",
    "Position size fixed unit notional (harness); full-sample selected cutoff hour in the paper is not tuned here (no param grid).",
]

def signals(df, max_hold=11):
    return L.session_signals(df, DAY_START, DAY_RULE, NIGHT_RULE)
