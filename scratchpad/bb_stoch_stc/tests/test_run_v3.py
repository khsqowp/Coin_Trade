import run_v3 as v3


def test_cohort_definitions_and_timeframes():
    assert v3.COHORTS['L2'] == ['BTCUSDT', 'ETHUSDT']
    assert v3.COHORTS['L5'] == ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
    assert len(v3.COHORTS['M']) == 9
    assert set(v3.TFS) == {'15m', '1h', '4h'}


def test_scaled_event_floor():
    assert v3.event_floor(1) == 30
    assert v3.event_floor(2) == 30
    assert v3.event_floor(5) == 60
    assert v3.event_floor(9) == 108


def test_with_stop_selection_requires_stop_config():
    items=[
        dict(score=9.,trades=50,side='combined',management={'sl_pct':None,'atr_mult':None},tag='no-stop'),
        dict(score=5.,trades=40,side='combined',management={'sl_pct':5.,'atr_mult':None},tag='stop')]
    selected=v3.select_winners(items)
    assert selected['unconstrained']['tag']=='no-stop'
    assert selected['with_stop']['tag']=='stop'


def test_test_metrics_do_not_affect_train_selection():
    items=[
        dict(score=3.,trades=40,side='combined',management={'sl_pct':None},test_return=-1e9,tag='train-winner'),
        dict(score=2.,trades=40,side='combined',management={'sl_pct':5.},test_return=1e9,tag='test-winner')]
    original=v3.select_winners(items)['unconstrained']['tag']
    items[0]['test_return']=1e99; items[1]['test_return']=-1e99
    corrupted=v3.select_winners(items)['unconstrained']['tag']
    assert original == corrupted == 'train-winner'


def test_stage_budget_is_total_not_per_cohort():
    assert not v3.budget_exceeded(10.0, 40, now=2409.9)
    assert v3.budget_exceeded(10.0, 40, now=2410.1)


def test_signal_grid_and_dedup_ranking_are_deterministic():
    a=v3.signal_grid(); b=v3.signal_grid()
    assert len(a)==1024 and a==b
    ranked=sorted(range(len(a)),key=lambda i:(i%13, -i),reverse=True)
    def select():
        picks=[]
        for i in ranked:
            if all(sum(a[i][k]!=a[j][k] for k in a[i])>=2 for j in picks): picks.append(i)
            if len(picks)==12: break
        return picks
    assert len(select())==12 and select()==select()


def test_cross_cohort_parameters_are_frozen():
    winner=dict(signal={'bb_window':4},management={'sl_pct':5.0},side='combined',score=3)
    assert v3.frozen_cross_params(winner)==(winner['signal'],winner['management'],'combined')


def test_pooled_metrics_use_pooled_trade_returns():
    pooled=v3._pooled_metrics([
        {'total_return':2.,'max_dd':-1.,'trade_details':[{'return':3.},{'return':-1.}]},
        {'total_return':-1.,'max_dd':-2.,'trade_details':[{'return':1.},{'return':-2.}]},
    ])
    assert pooled['total_return']==1.
    assert pooled['max_dd']==-3.
    assert pooled['pf']==4/3
    assert pooled['score']==1.-3.+.25*(4/3)


def test_wf_month_windows_are_pooled_without_train_test_overlap():
    import pandas as pd
    idx=pd.date_range('2024-01-01',periods=500,freq='D')
    train,test,train_end,test_end=v3.window_indices(idx,idx[0],12,3)
    assert len(train)>0 and len(test)>0
    assert idx[train].max()<idx[test].min()
    assert idx[train].max()<train_end<=idx[test].min()<test_end


def test_null_summary_verdict_wiring_uses_all_mechanical_gates():
    assert v3.null_verdict(5,4,'ROBUST',35)[0]=='COUNTS'
    assert v3.null_verdict(5,4,'FRAGILE',35)[0]=='no edge'
    assert v3.null_verdict(5,4,'ROBUST',29)[0]=='no edge'
    assert v3.null_verdict(4,4,'ROBUST',35)[0]=='no edge'


def test_cross_frozen_portions_preserve_requested_metrics():
    m={'trades':4,'total_return':2.,'pf':1.5,'max_dd':-3.}
    result=v3.cross_portions(m,m,m)
    assert set(result)=={'full','train','test'}
    assert result['test']=={'trades':4,'total_return':2.,'pf':1.5,'max_dd':-3.}
