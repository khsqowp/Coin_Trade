from datetime import date, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from dateutil.easter import easter
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s0_timeutil import bar_times

SPEC_ID="btc-max10-nyse-close"; PARAMS={"n":10}; PARAM_GRID={"n":[8,10,12]}; TIMEFRAMES=["15m"]; SIDES="long"
DEVIATIONS=["Early-close days are ignored.","NYSE calendar is hardcoded from the specified holiday rules.","Observations use Binance spot USDT 15m rather than Gemini.","Ties at the rolling high count as a high.","Harness pools five majors."]
IMPLEMENTED_FIELDS=["entry_long","exit","filters","timeframes"]

def _observed(d):
    if d.weekday()==5: return d-timedelta(days=1)
    if d.weekday()==6: return d+timedelta(days=1)
    return d

def _nth_weekday(year, month, weekday, nth):
    d=date(year,month,1); return d+timedelta(days=(weekday-d.weekday())%7+7*(nth-1))

def _last_weekday(year, month, weekday):
    d=date(year+(month==12), month%12+1,1)-timedelta(days=1)
    return d-timedelta(days=(d.weekday()-weekday)%7)

def nyse_holidays(year):
    """NYSE full-day closures under the task's explicit holiday rules."""
    fixed=[date(year,1,1),date(year,7,4),date(year,12,25)]
    if year>=2022: fixed.append(date(year,6,19))
    observed=[]
    for d in fixed:
        observed.append(d if (d.month==1 and d.weekday()==5) else _observed(d))
    return set(observed+[ _nth_weekday(year,1,0,3), _nth_weekday(year,2,0,3),
                         easter(year)-timedelta(days=2), _last_weekday(year,5,0),
                         _nth_weekday(year,9,0,1), _nth_weekday(year,11,3,4)])

def _trading_day(d): return d.weekday()<5 and d not in nyse_holidays(d.year)

def signals(df, n=10):
    times=bar_times(df,"15m"); tz=ZoneInfo("America/New_York")
    close_times=times+pd.Timedelta(minutes=15)
    loc=[t.to_pydatetime().astimezone(tz) for t in close_times]
    obs={}; obs_index={}
    for i,t in enumerate(loc):
        if t.hour==16 and t.minute==0 and _trading_day(t.date()):
            obs[t.date()]=float(df.close.iloc[i]); obs_index[t.date()]=i
    entries=np.zeros(len(df),bool); exits=np.zeros(len(df),bool)
    days=sorted(obs)
    for j,d in enumerate(days):
        if j+1<int(n): continue
        window=days[j-int(n)+1:j+1]
        if len(window)!=int(n): continue
        if obs[d]>=max(obs[x] for x in window):
            entries[obs_index[d]]=True
    for i,t in enumerate(loc):
        if t.hour==9 and t.minute==30 and _trading_day(t.date()): exits[i]=True
    return pd.DataFrame({"long_entry":entries,"short_entry":False,"long_exit":exits,"short_exit":False},index=df.index)
