import numpy as np,pandas as pd
import strategy as strat
from indicators import bollinger,stochastic,stc,atr
from strategy import signal_frame,simulate,is_coherent
from data import check_data
import run_all

def candles(n=160):
 c=100+np.sin(np.arange(n)/4)*3+np.arange(n)*.01
 return pd.DataFrame({'open':c,'high':c+1,'low':c-1,'close':c,'volume':1},index=pd.date_range('2022-01-01',periods=n,freq='h',tz='UTC'))
def test_indicators_prefix_causal():
 d=candles();
 for fn,args in [(bollinger,(d.close,)),(stochastic,(d.high,d.low,d.close)),(stc,(d.close,)),(atr,(d.high,d.low,d.close))]:
  full=fn(*args);short=fn(*(x.iloc[:100] if hasattr(x,'iloc') else x for x in args))
  vals=full if isinstance(full,tuple) else (full,)
  shorts=short if isinstance(short,tuple) else (short,)
  for x,y in zip(vals,shorts):np.testing.assert_allclose(np.asarray(x)[:100],np.asarray(y),equal_nan=True)
def test_signal_prefix_causal():
 d=candles();a=signal_frame(d);b=signal_frame(d.iloc[:100]);pd.testing.assert_frame_equal(a.iloc[:100],b)
def test_each_condition_switches_and_mirror_outputs_bool():
 s=signal_frame(candles());
 for col in ['bb_long','stoch_long','stc_long','bb_short','stoch_short','stc_short']:assert s[col].dtype==bool
 for en in [(1,0,0),(0,1,0),(0,0,1),(1,1,1)]:
  out=signal_frame(candles(),enabled=en);assert out.long.dtype==bool and out.short.dtype==bool

def test_coherence():
 assert is_coherent(2,2,5);assert not is_coherent(3,2,5);assert is_coherent(4,6,None)
 assert not is_coherent(2,2,None,1,3);assert is_coherent(2,2,None,2,3);assert is_coherent(2,2,None)

def test_constrained_stop_grid_excludes_no_stop():
 assert run_all.grid(False,require_stop=True)
 assert all(p['sl_pct'] is not None or p['atr_mult'] is not None for p in run_all.grid(False,require_stop=True))
 assert len(run_all.grid(False))==544
 assert {p['sl_pct'] for p in run_all.grid(False,require_stop=True) if p['sl_pct'] is not None}=={3.,5.,8.,12.}
 assert {p['atr_mult'] for p in run_all.grid(False,require_stop=True) if p['atr_mult'] is not None}=={2.,3.,4.,5.,6.}
 assert {p['max_hold_bars'] for p in run_all.grid(False,require_stop=True)}=={None,48}

def test_signal_neighbors_skip_invalid_lag_and_grid_edges():
 sig={**run_all.SIGGRID[0]}
 sig.update(stoch_cross_lag=2,stoch_min_cross_age=2,bb_window=0)
 specs=run_all._signal_neighbor_specs(sig,{})
 assert all(0<=values.index(value)<len(values) for axis,value,_,_,_ in specs
            for values in [["close","low"]] if axis=='bb_use')
 assert not any(axis=='stoch_cross_lag' and value==0 for axis,value,*_ in specs)
 assert any(axis=='bb_window' and value==2 for axis,value,*_ in specs)
 assert not any(axis=='bb_window' and value<0 for axis,value,*_ in specs)

def test_worker_error_includes_task_and_parameters():
 def fail(_):raise ValueError('bad rolling window')
 try:run_all._execute_task((fail,({'signal_config':3,'stoch_cross_lag':0},)))
 except RuntimeError as exc:
  assert 'signal_config' in str(exc) and 'stoch_cross_lag' in str(exc)
 else:raise AssertionError('worker exception was not raised')
def test_stage_a_resume_uses_matching_meta_without_reading_csv(tmp_path,monkeypatch):
 (tmp_path/'stage_a.csv').write_text('cached')
 (tmp_path/'stage_a_eligibility.csv').write_text('cached')
 monkeypatch.setattr(run_all,'_grid_hash',lambda quick=False:'grid-test')
 (tmp_path/'stage_a.meta').write_text('{"grid_hash":"grid-test"}')
 assert run_all._stage_a_valid(tmp_path)
 run_all._ensure_stage_a(tmp_path,True)

def test_wf_window_bounds_are_disjoint():
 d=candles(24*450)
 bounds=run_all._window_bounds(d,0)
 assert bounds is not None
 tr,te=bounds
 assert tr.stop<=te.start
 assert d.index[tr.stop-1]<d.index[te.start]

def test_wf_selection_uses_train_slice_only(monkeypatch):
 train=candles(500);seen=[]
 monkeypatch.setattr(run_all,'_event_rank',lambda d,indices=None:(seen.append(d.index[-1]) or pd.DataFrame([dict(signal_config=0,side='long',events=50,score=1),dict(signal_config=1,side='short',events=50,score=1)])))
 assert run_all._select_configs(train)==[0,1]
 assert seen==[train.index[-1]]

def test_plateau_criterion_seventy_percent():
 verdict,pct=run_all.plateau_verdict([8,7,6,5,4,3,2,1,0,-1],10)
 assert verdict=='FRAGILE' and pct==40
 assert run_all.plateau_verdict([8,7,6,5,4,3,2,1,0,-1,10,9,8,7,6,5,5,6,7,8],10)[0]=='ROBUST'
def test_stop_first_and_fees_slippage():
 d=pd.DataFrame({'open':[100,100,100],'high':[100,110,120],'low':[100,90,90],'close':[100,100,100]},index=pd.date_range('2020',periods=3,freq='h'))
 sig=pd.DataFrame({'long':[True,False,False],'short':[False]*3,'bb_mid':[100]*3,'atr':[1]*3})
 p=dict(n_adds=0,sl_pct=5,tp_pct=5)
 m=simulate(d,sig,p,'long',capital=10000,base_notional=1000)
 assert m['stopouts']==1 and m['total_return']<0

def test_combined_keeps_both_directions_and_one_position():
 d=pd.DataFrame({'open':[100.]*8,'high':[102.]*8,'low':[98.]*8,'close':[100.,101.,100.,99.,100.,101.,100.,99.]})
 sig=pd.DataFrame({'long':[True,False,False,False,True,False,False,False],
                   'short':[False,False,True,False,False,False,True,False],
                   'bb_mid':[100.]*8,'atr':[1.]*8})
 m=simulate(d,sig,dict(n_adds=0,sl_pct=None,atr_mult=None,tp_pct=.5),side='combined',base_notional=1000,fee=0,slippage=0)
 assert m['long']==2 and m['short']==2
 # Each alternating signal opens one trade only after the prior one exits.
 assert m['trades']==4 and m['trades']==m['long']+m['short']

def test_entry_bar_stop_is_checked():
 d=pd.DataFrame({'open':[100.,100.],'high':[100.,101.],'low':[100.,94.],'close':[100.,99.]})
 sig=pd.DataFrame({'long':[True,False],'short':[False]*2,'bb_mid':[100.]*2,'atr':[1.]*2})
 m=simulate(d,sig,dict(n_adds=0,sl_pct=5,tp_pct=None),'long',base_notional=1000,fee=0,slippage=0)
 assert m['stopouts']==1 and m['total_return']<0

def test_entry_bar_dca_is_checked_after_stop_and_target():
 d=pd.DataFrame({'open':[100.,100.],'high':[100.,101.],'low':[100.,97.],'close':[100.,99.]})
 sig=pd.DataFrame({'long':[True,False],'short':[False]*2,'bb_mid':[100.]*2,'atr':[1.]*2})
 m=simulate(d,sig,dict(n_adds=1,add_spacing_pct=2,add_size_mult=1,sl_pct=None,atr_mult=None,tp_pct=None),'long',base_notional=1000,fee=0,slippage=0)
 assert m['dca_fills']==1

def test_atr_stop_uses_last_closed_bar_before_entry():
 d=pd.DataFrame({'open':[100.,100.,100.],'high':[100.,101.,101.],'low':[100.,97.,97.],'close':[100.,99.,99.]})
 sig=pd.DataFrame({'long':[True,False,False],'short':[False]*3,'bb_mid':[100.]*3,'atr':[2.,50.,50.]})
 m=simulate(d,sig,dict(n_adds=0,sl_pct=None,atr_mult=1,tp_pct=None),'long',base_notional=1000,fee=0,slippage=0)
 assert m['stopouts']==1

def test_max_drawdown_includes_open_adverse_excursion():
 d=pd.DataFrame({'open':[100.,100.,100.],'high':[100.,101.,101.],'low':[100.,80.,99.],'close':[100.,100.,100.]})
 sig=pd.DataFrame({'long':[True,False,False],'short':[False]*3,'bb_mid':[100.]*3,'atr':[1.]*3})
 m=simulate(d,sig,dict(n_adds=0,sl_pct=None,atr_mult=None,tp_pct=None),'long',base_notional=1000,fee=0,slippage=0)
 assert m['max_dd']<m['closed_trade_max_dd'] and m['closed_trade_max_dd']==0

def test_gap_report_counts_only_actual_missing_bars():
 idx=pd.to_datetime(['2020-01-01T00:00:00Z','2020-01-01T01:00:00Z','2020-01-01T04:00:00Z'])
 gaps=check_data(pd.DataFrame(index=idx),'1h')
 assert len(gaps)==1 and gaps[0][2]==2
 assert check_data(pd.DataFrame(index=idx[:2]),'1h')==[]

def test_hand_computed_fees_and_slippage_every_fill():
 # Initial fill at 100, DCA at the 2% adverse level, then end mark at 100.
 d=pd.DataFrame({'open':[100.,100.,100.],'high':[100.,101.,101.],'low':[100.,99.,97.],'close':[100.,100.,100.]})
 sig=pd.DataFrame({'long':[True,False,False],'short':[False]*3,'bb_mid':[100.]*3,'atr':[1.]*3})
 fee=.0004; slip=.0002; q1=1000/(100*(1+slip)); fill1=100*(1+slip)
 raw_add=fill1*(1-.02); fill2=raw_add*(1+slip); q2=1000/fill2
 avg=(fill1*q1+fill2*q2)/(q1+q2); exitpx=100*(1-slip)
 expected=(exitpx-avg)*(q1+q2)-fill1*q1*fee-fill2*q2*fee-exitpx*(q1+q2)*fee
 m=strat.simulate(d,sig,dict(n_adds=1,add_spacing_pct=2,add_size_mult=1,sl_pct=None,atr_mult=None,tp_pct=None),'long',base_notional=1000,fee=fee,slippage=slip)
 assert m['dca_fills']==1
 assert abs(m['total_return']*100-expected)<1e-8

def test_dca_weighted_average_price():
 d=pd.DataFrame({'open':[100.,100.,100.],'high':[100.,101.,101.],'low':[100.,99.,97.],'close':[100.,100.,110.]})
 sig=pd.DataFrame({'long':[True,False,False],'short':[False]*3,'bb_mid':[100.]*3,'atr':[1.]*3})
 first=100.;second=first*(1-.02);q1=1000/first;q2=2000/second;avg=(first*q1+second*q2)/(q1+q2)
 expected=(110-avg)*(q1+q2)/10000*100
 m=strat.simulate(d,sig,dict(n_adds=1,add_spacing_pct=2,add_size_mult=2,sl_pct=None,atr_mult=None,tp_pct=None),'long',base_notional=1000,fee=0,slippage=0)
 assert m['dca_fills']==1 and abs(m['total_return']-expected)<1e-10

def test_signal_condition_hand_built_long_short(monkeypatch):
 # Deterministic indicator fixtures isolate each predicate while OHLC candles remain hand-built.
 def install(c, k, d, t):
  def bb(close,n=20,m=2):
   z=np.asarray(close);return np.full(len(z),100.),np.full(len(z),110.),np.full(len(z),90.)
  monkeypatch.setattr(strat,'bollinger',bb)
  monkeypatch.setattr(strat,'stochastic',lambda h,l,cl,*args:(np.asarray(k,float),np.asarray(d,float)))
  monkeypatch.setattr(strat,'stc',lambda cl,*args:np.asarray(t,float))
 def frame(close, high=None, low=None):
  close=np.asarray(close,float);high=close+1 if high is None else np.asarray(high,float);low=close-1 if low is None else np.asarray(low,float)
  return pd.DataFrame({'open':close,'high':high,'low':low,'close':close})
 n=4
 cases=[('bb_long',frame([100,100,100,100],low=[99,99,89,99]),([50]*n,[50]*n,[50]*n),True),
        ('bb_short',frame([100,100,100,100],high=[101,101,111,101]),([50]*n,[50]*n,[50]*n),True),
        ('stoch_long',frame([100]*n),([10,10,15,30],[10,10,10,30],[50]*n),True),
        ('stoch_short',frame([100]*n),([90,90,85,70],[90,90,90,70],[50]*n),True),
        ('stc_long',frame([100]*n),([50]*n,[50]*n,[10,20,30,40]),True),
        ('stc_short',frame([100]*n),([50]*n,[50]*n,[90,80,70,60]),True)]
 for col,f,vals,expected in cases:
  install(f.close,vals[0],vals[1],vals[2]);s=strat.signal_frame(f,dict(bb_n=2,bb_use='low' if col=='bb_long' else 'high',stoch_k=2,stoch_smooth=1,stoch_d=1,stc_turn_type=1,stc_min_slope=0,stc_level=25),enabled=(1,1,1))
  # Predicate is exposed independently so unrelated conditions cannot hide its trigger.
  cond={'bb_long':'bb_long','bb_short':'bb_short','stoch_long':'stoch_long','stoch_short':'stoch_short','stc_long':'stc_long','stc_short':'stc_short'}[col]
  assert bool(s[cond].any()) is expected
  # A candle series with the relevant price/cross/turn condition removed must not trigger.
  if col.startswith('bb_'):
   f2=frame([100]*n);install(f2.close,vals[0],vals[1],vals[2]);s2=strat.signal_frame(f2,dict(bb_n=2,bb_use='low' if col=='bb_long' else 'high',stoch_k=2,stoch_smooth=1,stoch_d=1,stc_turn_type=1,stc_level=25),enabled=(1,1,1));assert not s2[col].any()
  elif col.startswith('stoch_'):
   install(f.close,[50]*n,[50]*n,vals[2]);s2=strat.signal_frame(f,dict(bb_n=2,stoch_k=2,stoch_smooth=1,stoch_d=1,stc_turn_type=1,stc_level=25),enabled=(1,1,1));assert not s2[col].any()
  else:
   install(f.close,vals[0],vals[1],[50]*n);s2=strat.signal_frame(f,dict(bb_n=2,stoch_k=2,stoch_smooth=1,stoch_d=1,stc_turn_type=1,stc_level=25),enabled=(1,1,1));assert not s2[col].any()
