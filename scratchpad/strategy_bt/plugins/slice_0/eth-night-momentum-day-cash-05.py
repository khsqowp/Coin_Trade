from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s0_timeutil import session_signals
SPEC_ID="eth-night-momentum-day-cash-05"; PARAMS={"cut":5}; PARAM_GRID={"cut":[4,5,6]}; TIMEFRAMES=["1h"]; SIDES="both"
DEVIATIONS=["Only first-day-of-data sessions without a prior session are flat.","Cut hour grid is an added plateau axis around the spec hour.","Entry fills at the session first-bar open and exit at its last-bar close, approximating the boundary.","Spec instrument ETHUSD but harness pools five majors.","Cost model is the harness, not the paper's.","Short-short positions, where applicable, reopen at every boundary with session costs."]
IMPLEMENTED_FIELDS=["entry_long","entry_short","exit","filters","timeframes"]
def signals(df, cut=5): return session_signals(df,1,int(cut),"cash","mom")
