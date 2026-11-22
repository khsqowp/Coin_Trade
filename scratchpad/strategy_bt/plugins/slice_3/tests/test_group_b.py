import importlib.util
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]
IDS=['btc-adx-di-24-9','btc-donchian-37-6','raschke-holy-grail','turtle-system-2','c4-supertrend-lsma-long-strategy','ft_adx_momentum','pk_double_ema','jesse_simple_bollinger']
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/(name+'.py')); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def frame(n=400,seed=1):
 r=np.random.default_rng(seed); c=100+np.cumsum(r.normal(0,1,n)); o=np.r_[c[0],c[:-1]]; return pd.DataFrame({'open':o,'high':np.maximum(o,c)+r.random(n),'low':np.minimum(o,c)-r.random(n),'close':c,'volume':r.random(n)},index=pd.date_range('2020-01-01',periods=n,freq='h',tz='UTC'))
def test_all_plugins_causal_on_random_walk():
 from common.protocol import check_no_lookahead
 d=frame()
 for name in IDS: assert check_no_lookahead(load(name),d)
def test_donchian_prior_channel_and_exit():
 m=load('btc-donchian-37-6'); d=pd.DataFrame({'open':[1]*8,'high':[2,3,4,5,6,7,8,9],'low':[0,1,2,3,4,5,6,7],'close':[1,2,3,4,5,6,8,4],'volume':[1]*8},index=pd.date_range('2020',periods=8,tz='UTC')); s=m.signals(d,entry_n=3,exit_n=2); assert bool(s.long_entry.iloc[6]); assert bool(s.long_exit.iloc[7])
def test_turtle_atr_stop():
 m=load('turtle-system-2'); n=30; d=frame(n); s=m.signals(d,n_len=3); from common.indicators import atr; np.testing.assert_allclose(s.atr_stop.dropna(),pd.Series(2*atr(d.high,d.low,d.close,3)).dropna())
def test_pk_double_ema_edge_and_stop():
 m=load('pk_double_ema'); d=frame(500); s=m.signals(d,fast=2,slow=5,trend=2); assert s.long_entry.dtype==bool and s.long_exit.dtype==bool; assert np.allclose(s.stop_pct,.20)
def test_jesse_bollinger_and_cloud_contract():
 m=load('jesse_simple_bollinger'); d=frame(200); s=m.signals(d,bb_len=5,bb_k=0,conv=2,base=3,span_b=4,disp=2); assert s.long_entry.dtype==bool and s.long_exit.dtype==bool
def test_supertrend_flip_signals_are_edges():
 m=load('c4-supertrend-lsma-long-strategy'); s=m.signals(frame(500),atr_period=5,lsma_len=5); assert not (s.long_entry & s.long_exit).any()
def test_holy_grail_management_columns_are_causal():
 m=load('raschke-holy-grail'); s=m.signals(frame(500)); assert {'stop_pct','tp_pct','max_hold'}<=set(s.columns); assert not s.long_entry[s.stop_pct.isna()].any()
def test_real_btc_head_slices_causal():
 from common.protocol import check_no_lookahead
 data=ROOT.parents[2]/'bb_stoch_stc'/'data'
 for name,tf in [('btc-adx-di-24-9','1d'),('btc-donchian-37-6','1d'),('raschke-holy-grail','1d'),('turtle-system-2','1d'),('c4-supertrend-lsma-long-strategy','1h'),('ft_adx_momentum','1h'),('pk_double_ema','1h'),('jesse_simple_bollinger','1h')]:
  d=pd.read_parquet(data/f'BTCUSDT_{tf}.parquet').iloc[:600]
  assert check_no_lookahead(load(name),d)
def test_pk_double_ema_known_up_cross():
 m=load('pk_double_ema'); c=np.array([10,10,10,10,10,20,20,20,20.],float); d=pd.DataFrame({'open':c,'high':c+2,'low':c+1,'close':c,'volume':1},index=pd.date_range('2020',periods=len(c),tz='UTC')); s=m.signals(d,fast=2,slow=3,trend=1); assert np.flatnonzero(s.long_entry).tolist()==[5]
def test_jesse_constant_cloud_breakout_and_middle_exit():
 m=load('jesse_simple_bollinger'); c=np.array([12.5]*10+[11.]); h=np.full(len(c),13.); l=np.full(len(c),11.); d=pd.DataFrame({'open':c,'high':h,'low':l,'close':c,'volume':1},index=pd.date_range('2020',periods=len(c),tz='UTC')); s=m.signals(d,bb_len=3,bb_k=0,conv=2,base=2,span_b=2,disp=1); assert s.long_entry.iloc[3:9].all(); assert bool(s.long_exit.iloc[-1])
