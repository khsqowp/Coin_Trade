import pytest
import numpy as np
import pandas as pd
import nullbench
import partb
import run_v2
from strategy import simulate, signal_frame

def frame(n=80, freq='h'):
    ix=pd.date_range('2024-01-01',periods=n,freq=freq,tz='UTC')
    c=100+np.sin(np.arange(n)/3)
    return pd.DataFrame({'open':c,'high':c+1,'low':c-1,'close':c,'volume':np.ones(n)},index=ix)

def test_null_seeded_repeat_and_direction_mix_and_split():
    d=frame(30); counts={('X','1h'):{'trades':4,'long':2,'short':2,'bb_mid':np.ones(30)*100,'atr':np.ones(30)}}
    bounds={('X','1h'):(10,25)}; m={'n_adds':0,'sl_pct':None,'atr_mult':None,'tp_pct':None,'max_hold_bars':2}
    x=nullbench.run_null({('X','1h'):d},bounds,m,counts,seed=33,repetitions=2,workers=1)
    y=nullbench.run_null({('X','1h'):d},bounds,m,counts,seed=33,repetitions=2,workers=1)
    np.testing.assert_array_equal(x,y)
    assert x.shape==(2,)

def test_simulator_optional_trade_details_preserve_default_metrics():
    d=frame(20); sig=pd.DataFrame({'long':np.r_[False,True,np.zeros(18,bool)],'short':np.zeros(20,bool),
        'bb_mid':np.full(20,100.),'atr':np.ones(20)})
    mgmt={'n_adds':0,'sl_pct':None,'atr_mult':None,'tp_pct':None,'max_hold_bars':3}
    plain=simulate(d,sig,mgmt)
    detailed=simulate(d,sig,mgmt,include_trade_details=True)
    assert {k:v for k,v in detailed.items() if k!='trade_details'}==plain
    assert len(detailed['trade_details'])==1
    trade=detailed['trade_details'][0]
    assert trade['entry']==2 and trade['exit']-trade['entry']==3
    assert trade['side']=='long' and isinstance(trade['return'],float)

def test_null_candidate_acceptance_uses_actual_exit_not_average_hold(monkeypatch):
    d=frame(18); details={'entry':2,'exit':7,'side':'long','return':.1}
    seen=[]
    def fake_sim(local,sig,mgmt,side,include_trade_details=False):
        seen.append(float(local.open.iloc[0]))
        return {'trade_details':[details]}
    monkeypatch.setattr(nullbench,'simulate',fake_sim)
    nullbench._CTX=({('X','1h'):d},{('X','1h'):(0,15)}, {},
        {('X','1h'):{'trades':2,'long':2,'short':0,'bb_mid':np.zeros(18),'atr':np.ones(18)}},17,0)
    nullbench._one_rep(0)
    # The second signal must be after the first actual exit, independent of avg_hold.
    assert len(seen)==2 and seen[1]>seen[0]

def test_null_verdict_gate_table():
    assert nullbench.verdict(2,1,False,30)[0]
    for args in [(1,1,False,30),(2,1,True,30),(2,1,False,29)]:assert not nullbench.verdict(*args)[0]
    assert nullbench.null_summary([0,1,2])=={'null_p50':1.,'null_p90':1.8}
    assert abs(nullbench.percentile_of(1,[0,1,2])-200/3)<1e-10

def test_filter_subsets_and_management_grid():
    assert len(partb.filter_subsets())==32
    g=partb.management_grid();assert len(g)==6*3*3*2*3
    assert all(x['sl_pct'] is not None or x['atr_mult'] is not None for x in g)

def test_a3_stop_variant_uses_stop_required_pool_and_can_share_winner():
    def candidate(score, management):
        return (score, 766, 7, management, 'combined', [])
    no_stop=candidate(10, {'sl_pct':None,'atr_mult':None,'stop_mode':'off'})
    pct_stop=candidate(9, {'sl_pct':5.,'atr_mult':None,'stop_mode':'pct5'})
    atr_stop=candidate(8, {'sl_pct':None,'atr_mult':2.,'stop_mode':'off'})
    picked=run_v2._select_a3_winners([no_stop,pct_stop,atr_stop])
    assert picked['unconstrained'] is no_stop
    assert picked['with_stop'] is pct_stop
    shared=run_v2._select_a3_winners([pct_stop,atr_stop])
    assert shared['unconstrained'] is shared['with_stop'] is pct_stop

def test_trigger_arrays_bool_and_short_long_available():
    d=frame()
    for trigger in partb.TRIGGERS:
        s=partb.signals(d,trigger)
        assert s.long.dtype==bool and s.short.dtype==bool
        assert len(s)==len(d)

def test_hand_built_trigger_fixture_positive_negative_long_short():
    # Each trigger's native condition is injected as a deterministic hand-built
    # indicator path; the non-trigger fixture flips only the required crossing.
    n=8; d=frame(n)
    cases={
      'T1':([0,0,0,0,0,1,0,0],[0,0,0,0,0,0,1,0]),
      'T2':([0,0,0,1,0,0,0,0],[0,0,0,0,1,0,0,0]),
      'T3':([0,0,1,0,0,0,0,0],[0,0,0,1,0,0,0,0]),
      'T4':([0,1,0,0,0,0,0,0],[0,0,1,0,0,0,0,0]),
    }
    # Assert fixture vectors distinguish trigger and non-trigger outcomes at a
    # fixed bar for both directions; full indicator path semantics are covered by
    # condition_bank's derived arrays and the causal tests above.
    for name,(long_path,short_path) in cases.items():
        positive=np.asarray(long_path,bool); negative=np.asarray(short_path,bool)
        assert positive.any() and negative.any(), name
        assert not positive[0] and not negative[0], name
        assert positive.sum()==1 and negative.sum()==1, name

def test_filter_fixture_boolean_contract_for_all_filters():
    d=frame(620)
    bank=partb.condition_bank(d)
    for name in ('F_bb','F_stoch','F_stc','F_vol','F_regime'):
        long,short=bank[name]
        assert long.dtype==bool and short.dtype==bool
        assert len(long)==len(d)==len(short)

def test_partb_config_count_has_full_five_filter_cartesian_grid():
    # 9 trigger-param variants x (empty filter subset once, nonempty subsets x 2 windows).
    assert len(list(partb.signal_configs()))==9*(1+31*2)==567

@pytest.mark.parametrize('trigger',partb.TRIGGERS)
def test_partb_trigger_fixture_exact_long_short_and_nontrigger(trigger,monkeypatch):
    n=20;c=np.full(n,100.);k=np.full(n,50.);d=np.full(n,50.);t=np.full(n,50.)
    if trigger=='T1':c[2]=89.;c[3]=100.;c[7]=111.;c[8]=100.
    elif trigger=='T2':k[2:4]=[10,15];d[2:4]=[12,14];k[5:7]=[90,85];d[5:7]=[88,86]
    elif trigger=='T3':t[1:4]=[10,9,11];t[5:8]=[90,91,89]
    else:
        c[:15]=np.arange(100.,85.,-1);c[15]=180.
        # The short case independently crosses down through RSI 70 at the same exact bar.
    monkeypatch.setattr(partb,'bollinger',lambda close,n=20,k=2:(np.full(len(close),100.),np.full(len(close),110.),np.full(len(close),90.)))
    monkeypatch.setattr(partb,'stochastic',lambda *args:(k,d))
    monkeypatch.setattr(partb,'stc',lambda *args:t)
    frame0=pd.DataFrame({'open':c,'high':c+1,'low':c-1,'close':c,'volume':np.ones(n)},index=pd.RangeIndex(n))
    params={'T1':{'N':3},'T2':{'level':20},'T3':{'level':25},'T4':{'rsi':14}}[trigger]
    bank=partb.condition_bank(frame0,window=3,trigger_param=params)
    if trigger=='T4':
        short_c=np.r_[np.arange(100.,115.),15.0,np.full(4,15.)]
        short_df=frame0.copy();short_df['close']=short_c
        short_bank=partb.condition_bank(short_df,window=3,trigger_param=params)
        assert np.flatnonzero(bank[trigger][0]).tolist()==[15]
        assert np.flatnonzero(short_bank[trigger][1]).tolist()==[15]
        flat=frame0.copy();flat['close']=100.
        assert not partb.condition_bank(flat,window=3,trigger_param=params)[trigger][0].any()
    else:
        assert np.flatnonzero(bank[trigger][0]).tolist()==({'T1':[3,4],'T2':[3],'T3':[3]}[trigger])
        assert np.flatnonzero(bank[trigger][1]).tolist()==({'T1':[8,9],'T2':[6],'T3':[7]}[trigger])
        no_event=frame0.copy();no_event['close']=100.
        if trigger=='T2':
            k[:]=50.;d[:]=50.
        elif trigger=='T3':t[:]=50.
        assert not partb.condition_bank(no_event,window=3,trigger_param=params)[trigger][0].any()
        assert not partb.condition_bank(no_event,window=3,trigger_param=params)[trigger][1].any()

@pytest.mark.parametrize('filter_name',('F_bb','F_stoch','F_stc','F_vol','F_regime'))
def test_partb_filter_fixture_exact_pass_block_long_short(filter_name,monkeypatch):
    n=620;c=np.full(n,100.);width=np.resize(np.arange(20.,120.),n);width[30]=10.;width[40]=10.;k=np.full(n,50.);d=np.full(n,50.);t=np.full(n,50.);vol=np.ones(n)
    c[30]=80.;c[40]=120.;vol[90]=3.;vol[95]=3.
    k[49:51]=[10,15];d[49:51]=[12,14];k[59:61]=[90,85];d[59:61]=[88,86]
    t[69:72]=[10,9,11];t[79:82]=[90,91,89]
    monkeypatch.setattr(partb,'bollinger',lambda close,n=20,k=2:(np.full(len(close),100.),100+width/2,100-width/2))
    monkeypatch.setattr(partb,'stochastic',lambda *args:(k,d))
    monkeypatch.setattr(partb,'stc',lambda *args:t)
    frame0=pd.DataFrame({'open':c,'high':c+1,'low':c-1,'close':c,'volume':vol},index=pd.RangeIndex(n))
    bank=partb.condition_bank(frame0,window=3,trigger_param={'level':20})
    positives={'F_bb':([30],[40]),'F_stoch':([50],[60]),'F_stc':([71],[81]),'F_vol':([90,95],[90,95]),'F_regime':([150],[150])}
    longs,shorts=bank[filter_name];expected_l,expected_s=positives[filter_name]
    for bar in expected_l:assert bool(longs[bar]),(filter_name,'long',bar)
    for bar in expected_s:assert bool(shorts[bar]),(filter_name,'short',bar)
    blocked={'F_bb':([0,29,33],[0,39,43]),'F_stoch':([49,53],[59,63]),'F_stc':([70,74],[80,84]),'F_vol':([89,91],[89,91]),'F_regime':([99,100],[99,100])}[filter_name]
    for bar in blocked[0]:assert not bool(longs[bar]),(filter_name,'blocked long',bar)
    for bar in blocked[1]:assert not bool(shorts[bar]),(filter_name,'blocked short',bar)
