"""Independent synthetic price/fee/collateral/stops and saved-result verification."""
import json
import numpy as np
import pandas as pd
from app.crypto_round11_research import PATH, configs
from app.technical_portfolio_engine import prepare, simulate_portfolio, simulate_research_portfolio
from app.crypto_technical_ict_research import load_data
from app.crypto_round8_research import core
from app.crypto_round7_research import summary


def synthetic():
    dates=pd.date_range('2020-01-01',periods=5,tz='UTC')
    f=pd.DataFrame(dict(Open=100.,High=100.,Low=100.,Close=100.,SIGNAL=False,
                        VOL_RATIO=2.,ATR14=2.,STOP_LEVEL=0.),index=dates)
    f.loc[dates[0],'SIGNAL']=True
    long={'X':f.copy()}
    flat=simulate_research_portfolio(long,top_k=1,return_trace=True)
    assert abs(flat['final']-(1-.0004)**2)<1e-12
    cost=simulate_research_portfolio(long,top_k=1,funding_annual=.1095,slippage=.001,return_trace=True)
    qty=(1-.0004)/100.1
    funding=qty*100*.1095/365*(2/3+3)
    expected=(1-.0004)+qty*(99.9-100.1)-funding-qty*99.9*.0004
    assert abs(cost['final']-expected)<1e-12
    # Isolated short: falling100->80 yields20%, fees both legs; cash collateral locked.
    short=f.copy()
    short['SIGNAL']=False
    short['SHORT_SIGNAL']=False
    short.loc[dates[0],'SHORT_SIGNAL']=True
    short.loc[dates[1]:,['Open','High','Low','Close']]=80.
    data=prepare({'L':f,'S':short})
    data[2]['SHORT_SIGNAL']=np.column_stack([np.zeros(5),short.SHORT_SIGNAL.to_numpy()])
    # Entry open must100, exit80; keep long flat to independently inspect pair return.
    data[2]['Open'][1,1]=100.
    pair=simulate_research_portfolio({},prepared=data,long_short=True,top_k=2,return_trace=True)
    records={t['symbol']:t for t in pair['records']}
    q=.5*(1-.0004)/100
    assert abs(records['S']['proceeds']-(.5*(1-.0004)+q*20-q*80*.0004))<1e-12
    assert abs(records['L']['cost']-records['S']['cost'])<1e-12
    assert len(pair['allocations'])==2 and sum(t['weight'] for t in pair['allocations'])<=1+1e-12
    assert pair['trace'][1]['positions']==2
    funded=simulate_research_portfolio({},prepared=data,long_short=True,top_k=2,funding_annual=.1095,return_trace=True)
    assert next(t for t in funded['records'] if t['symbol']=='S')['funding']<0
    # Current-day high must not tighten a stop before same-day low test.
    stop=f.copy()
    stop.loc[dates[2],['High','Low','Close']]=[120.,99.,110.]
    stop.loc[dates[3],['Open','High','Low','Close']]=[90.,100.,80.,95.]
    r=simulate_research_portfolio({'X':stop},top_k=1,trailing=2.,return_trace=True)
    assert r['records'][0]['exit']==3
    assert abs(r['records'][0]['proceeds']-90*(1-.0004)/100*(1-.0004))<1e-12
    assert r['stopped']==1
    # Daily capacity is read from previous completed date.
    dyn=simulate_research_portfolio(long,dynamic_k={d:(2 if i==0 else 8) for i,d in enumerate(dates)},return_trace=True)
    assert dyn['allocations'][0]['capacity']==2 and dyn['allocations'][0]['weight']==.5
    print('synthetic fee/funding/short/collateral/pairing/gap/causal-trailing/dynamic PASS')


def run():
    synthetic()
    if not PATH.exists():
        return
    out=json.loads(PATH.read_text())
    frames,manifest,skipped=load_data()
    assert manifest==out['manifest'] and not skipped
    p=core('volume',frames)
    old=simulate_portfolio(p,return_trace=True)
    new=simulate_research_portfolio(p,return_trace=True)
    for k in summary(old):
        assert abs(new[k]-old[k])<1e-8
    np.testing.assert_allclose([t['closing'] for t in old['trace']],new['equity'],rtol=1e-12)
    assert [(e['date'],e['symbol']) for e in old['allocations']]==[(e['date'],e['symbol']) for e in new['allocations']]
    np.testing.assert_allclose([e['weight'] for e in old['allocations']],
                               [e['weight'] for e in new['allocations']],rtol=1e-12)
    for row in out['experiments']:
        m=row['metrics']
        assert np.isfinite(list(m.values())).all() and m['trades']>0
        assert row['causal_checks']==4
        assert len(row['records'])==m['trades']
        assert abs(sum(t['pnl'] for t in row['records'])-(m['final']-1))<1e-8
        b=out['baseline']
        assert row['dominates']==(m['cagr']>b['cagr'] and m['mdd']<b['mdd'] and m['sharpe']>b['sharpe'])
        if row['dominates']:
            robust=row['robustness']
            assert len(robust['monte_carlo']['trials'])==300
            assert robust['bootstrap']['iterations']==1000
            assert robust['verdict']==('통과' if all(robust['votes']) else '기각')
    if out['status']=='복귀조건 B 달성':
        assert len(out['experiments'])==34
        assert all(sum(r['category']==c for r in out['experiments'])==len(v) for c,v in configs().items())
        assert all(r.get('robustness',{}).get('verdict')!='통과' for r in out['experiments'])
        assert out['sections']==list(range(29,39))
    if out['status']=='복귀조건 A 달성':
        assert any(r.get('robustness',{}).get('verdict')=='통과' for r in out['experiments'])
    print('saved results, champion equity/allocation reproduction PASS',len(out['experiments']))


if __name__=='__main__':
    run()
