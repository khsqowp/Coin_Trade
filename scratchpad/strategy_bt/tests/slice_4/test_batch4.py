import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
from common.protocol import check_no_lookahead
ROOT=Path(__file__).resolve().parents[2]/"plugins"/"slice_4"

def load(sid):
    p=ROOT/f"{sid}.py"; spec=importlib.util.spec_from_file_location(sid.replace('-','_'),p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def frame(idx,o,h,l,c,v=None):
    return pd.DataFrame({"open":o,"high":h,"low":l,"close":c,"volume":np.ones(len(idx)) if v is None else v},index=idx)

def test_no_lookahead_each_plugin():
    daily=pd.date_range("2020-01-01",periods=260,freq="D",tz="UTC")
    close=100+np.sin(np.arange(len(daily))/3)+np.arange(len(daily))*.01
    d=frame(daily,close,close+1,close-1,close)
    hourly=pd.date_range("2024-01-01",periods=96,freq="h",tz="UTC")
    c=100+np.sin(np.arange(len(hourly))/4)
    h=frame(hourly,c,c+1,c-1,c,1+np.arange(len(hourly))%4)
    for sid,df in [("c5-connors-3day-reversion-etf",d),("c5-hobbiecode-ibs-monday-reversal",d),("c5-opening-range-breakout-24x7-crypto-3bar",h),("c5-sc-connors-rsi2-sma200-sma5",d),("c5-strat-inside-outside-bar-3pct-1pct",d)]:
        p=load(sid); assert check_no_lookahead(p,df)

def test_connors_three_lower_high_low_pattern():
    idx=pd.date_range("2024-01-01",periods=8,freq="D",tz="UTC")
    h=np.array([20,19,18,17,16,17,16,15.],float); l=np.array([15,14,13,12,11,13,12,11.],float); c=np.array([18,17,16,15,14,15,14,13.],float)
    s=load("c5-connors-3day-reversion-etf").signals(frame(idx,c,h,l,c),trend_filter=0)
    assert bool(s.long_entry.iloc[4]) and not bool(s.long_entry.iloc[7])

def test_monday_ibs_and_friday_reference():
    idx=pd.date_range("2024-01-05",periods=4,freq="D",tz="UTC") # Fri-Mon
    o=np.array([100,100,100,100.]); h=np.array([102,101,101,102.]); l=np.array([98,99,99,98.]); c=np.array([101,100,100,99.])
    s=load("c5-hobbiecode-ibs-monday-reversal").signals(frame(idx,o,h,l,c))
    assert bool(s.long_entry.iloc[3]); assert s.max_hold.iloc[3]==4

def test_opening_range_breakout_3_bars_and_volume():
    idx=pd.date_range("2024-01-01",periods=6,freq="h",tz="UTC")
    o=np.array([10,10,10,10,11,10.]); h=np.array([11,12,11,12,12,11.]); l=np.array([9,9,9,10,10,9.]); c=np.array([10,11,10,12.5,10.5,10.])
    v=np.array([2,2,2,2,1,2.])
    s=load("c5-opening-range-breakout-24x7-crypto-3bar").signals(frame(idx,o,h,l,c,v))
    assert bool(s.long_entry.iloc[3]); assert s.stop_pct.iloc[3]>0 and np.isclose(s.tp_pct.iloc[3],2*s.stop_pct.iloc[3])
    assert not bool(s.long_entry.iloc[4])

def test_inside_outside_setup_followed_by_directional_break():
    idx=pd.date_range("2024-01-01",periods=5,freq="D",tz="UTC")
    o=np.array([10,10,10,10,10.]); h=np.array([12,11,13,14,13.]); l=np.array([8,9,7,6,5.]); c=np.array([10,10,12,13,9.])
    s=load("c5-strat-inside-outside-bar-3pct-1pct").signals(frame(idx,o,h,l,c))
    assert bool(s.long_entry.iloc[2]) # prior bar inside
    assert bool(s.long_entry.iloc[3]) # prior bar outside
    assert bool(s.short_entry.iloc[4]) # prior bar outside
    assert s.stop_pct.eq(.01).all() and s.tp_pct.eq(.03).all()
