"""Archived spec btc-08utc-momentum-long: 12h session calendar rule (day=mom, night=long)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L

SPEC_ID = "btc-08utc-momentum-long"
# max_hold is a constant (bars): the position is closed at the close of the last bar of the 12h session.
PARAMS = {"max_hold": 2}
PARAM_GRID = {}
TIMEFRAMES = ["4h"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "filters", "timeframes"]
DAY_START = 8
DAY_RULE = "mom"
NIGHT_RULE = "long"
DEVIATIONS = [
    "Spec names no timeframe; session boundaries 08:00/20:00 UTC need bars aligned to them, so only 4h is run (1h/4h fallback reduced to one timeframe because the harness PARAMS.max_hold is a single constant that cannot vary per timeframe).",
    "Day session = [08:00,20:00) UTC, night = complement. Day rule = mom, night rule = long. 'Previous return of the same session' read literally as the return of the SAME session type 24h earlier (first-bar open -> last-bar close); sign 0 or missing data => flat.",
    "Instrument limited to BTC in the source but the harness pools 5 majors (BTC/ETH/BNB/SOL/XRP) - rule applied identically to all.",
    "Every session is closed (at last-bar close via max_hold) and re-opened at next open, so consecutive same-direction sessions pay fees twice (literal 'close/recompute at session boundary'); fees/slippage per harness, no funding.",
    "Position size fixed unit notional (harness); full-sample selected cutoff hour in the paper is not tuned here (no param grid).",
]

def signals(df, max_hold=2):
    return L.session_signals(df, DAY_START, DAY_RULE, NIGHT_RULE)
