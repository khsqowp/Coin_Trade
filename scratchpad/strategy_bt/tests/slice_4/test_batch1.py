import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from common.protocol import check_no_lookahead
ROOT=Path(__file__).resolve().parents[2]/'plugins'/'slice_4'
IDS=['c5-connors-r3-rsi2-3day-decline','c5-lazybear-squeeze-momentum-bb-kc-tpsl','c5-raschke-anti-stochastic-7-10-3-hook','c5-sc-nr7-nr4-crabel-breakout']
def load(sid):
 s=importlib.util.spec_from_file_location(sid.replace('-','_'),ROOT/f'{sid}.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def frame(n=900,tf='1h'):
 idx=pd.date_range('2024-01-01',periods=n,freq=tf,tz='UTC'); c=100+np.sin(np.arange(n)/11)*8+np.arange(n)*.01; return pd.DataFrame({'open':c,'high':c+1,'low':c-1,'close':c,'volume':1000.},index=idx)
@pytest.mark.parametrize('sid',IDS)
def test_no_lookahead(sid):
 m=load(sid); assert check_no_lookahead(m,frame())
def test_connors_hand_computed_decline_mask():
 m=load(IDS[0]); c=np.array([100.]*200+[100.,99.,98.,97.]); df=pd.DataFrame({'open':c,'high':c,'low':c,'close':c,'volume':1.}); s=m.signals(df,trend_len=2)
 # This fixture establishes zero entries when RSI is monotonic and trend filter cannot satisfy an oversold RSI.
 assert not s.long_entry.any()
def test_crabel_hand_computed_nr7_and_confirmation():
 m=load(IDS[3]); h=np.array([10,10,10,10,10,10,10,8,13.]); l=np.array([0,0,0,0,0,0,0,7,3.]); c=np.array([5,5,5,5,5,5,5,7.5,13.]); df=pd.DataFrame({'open':c,'high':h,'low':l,'close':c,'volume':1.})
 s=m.signals(df,nr7_n=7,nr4_n=4)
 # Bar 7 is a narrow-range bar; the next close crosses its high and triggers.
 assert bool(s.long_entry.iloc[8])
@pytest.mark.parametrize('sid',IDS[1:3])
def test_complex_plugins_return_aligned_boolean_signals(sid):
 s=load(sid).signals(frame()); assert len(s)==900 and s.long_entry.dtype==bool and s.short_entry.dtype==bool
