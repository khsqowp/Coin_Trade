"""Independent arithmetic and synthetic execution checks for Round10."""
import json
import numpy as np
import pandas as pd
from app.crypto_round10_research import PATH, regimes, confirmed, execution, HOLDS, FAMILIES
from app.crypto_round8_research import core
from app.crypto_technical_ict_research import load_data
from app.crypto_round7_research import summary, random_data
from app.crypto_round4_robustness import ledger_run
from app.technical_portfolio_engine import prepare, simulate_portfolio


def synthetic():
    dates = pd.date_range('2020-01-01', periods=8, tz='UTC')
    frame = pd.DataFrame(dict(Open=100.,High=100.,Low=100.,Close=100.,SIGNAL=True,
                             VOL_RATIO=1.,ATR14=1.,STOP_LEVEL=0.),index=dates)
    p = {'X':frame}
    data = prepare(p)
    full = simulate_portfolio(p,top_k=1,return_trace=True)
    scaled = simulate_portfolio(p,top_k=1,entry_scale={d:.4 for d in dates},return_trace=True)
    assert full['allocations'][0]['weight'] == 1
    assert scaled['allocations'][0]['weight'] == .4
    assert full['trades'] == scaled['trades'] == 1
    assert all(t['positions']==1 for t in scaled['trace'][1:-1])
    # Exact fee accounting for a scaled exposure, no rebalancing of existing shares.
    assert abs(scaled['final']-(.6+.4*(1-.0004)**2))<1e-12
    banks = {'a': data, 'b': data}
    schedule = {d: 'a' if i<3 else 'b' for i,d in enumerate(dates)}
    config = dict(top_k=1,strategy_data=banks,active_strategy=schedule,
                  strategy_holds={'a':2,'b':1},liquidate_on_switch=True)
    switched, records, _, _, _ = ledger_run(p,config)
    early, early_records, _, _, _ = ledger_run(p, dict(config, strategy_holds={'a':20,'b':20}))
    assert early['trades'] == 2 and early_records[0]['exit'] == 4
    assert records[0]['entry']==1 and records[0]['exit']==3
    # B entered day4; its own one-day expiry is preserved.
    assert any(t['entry']==4 and t['exit']==5 for t in records)
    cash = dict(config,active_strategy={d:'a' if i<2 else None for i,d in enumerate(dates)},strategy_holds={'a':20,'b':1})
    liquid = simulate_portfolio(p,return_trace=True,**cash)
    assert liquid['trades']==1 and liquid['trace'][3]['positions']==0
    natural = simulate_portfolio(p,return_trace=True,**dict(cash,liquidate_on_switch=False))
    assert natural['trace'][3]['positions']==1
    # Confirmation preserves established state through an unconfirmed counter-move.
    raw = pd.Series([-1,1,1,1,0,1,0,0,0],index=pd.RangeIndex(9))
    assert confirmed(raw,3).tolist()==[-1,-1,-1,1,1,1,1,1,0]
    for bad in [-.1,1.1,float('nan')]:
        try:
            simulate_portfolio(p,entry_scale={d:bad for d in dates})
        except ValueError:
            pass
        else:
            raise AssertionError('invalid scale accepted')


def run():
    synthetic()
    output = json.loads(PATH.read_text())
    frames, manifest, skipped = load_data()
    assert manifest==output['manifest'] and not skipped
    p = {f:core(f,frames) for f in FAMILIES}
    data = {f:prepare(v) for f,v in p.items()}
    reg = regimes(frames['BTC'])
    btc=frames['BTC']
    assert (reg.binary1.iloc[:199] == -1).all() and (reg.atr_weight.iloc[:199] == 0).all()
    for i in [199,200,500,1200,len(btc)-1]:
        past=btc.iloc[:i+1]
        slow=past.Close.iloc[-200:].mean()
        fast=past.Close.iloc[-50:].mean()
        close=past.Close.iloc[-1]
        assert abs(reg.sma200.iloc[i]-slow)<1e-8
        assert abs(reg.sma50.iloc[i]-fast)<1e-8
        binary=int(close>slow)
        four=3 if close>slow and close>fast else 2 if close>slow else 1 if close>fast else 0
        assert reg.binary1.iloc[i]==binary and reg.four1.iloc[i]==four
        tr=[]
        for j in range(i-199,i+1):
            row=btc.iloc[j]
            previous=btc.Close.iloc[j-1] if j else row.Close
            tr.append(max(row.High-row.Low,abs(row.High-previous),abs(row.Low-previous)))
        assert abs(reg.atr200.iloc[i]-np.mean(tr))<1e-8
        assert abs(reg.atr_weight.iloc[i]-np.clip(.5+(close-slow)/np.mean(tr)/10,0,1))<1e-12
    for cutoff in [pd.Timestamp('2021-06-30',tz='UTC'),pd.Timestamp('2024-06-30',tz='UTC')]:
        pd.testing.assert_frame_equal(reg.loc[:cutoff],regimes(btc.loc[:cutoff]))
    for f in FAMILIES:
        assert summary(simulate_portfolio(p[f],hold_days=HOLDS[f],prepared=data[f]))==output['baseline'][f]
    rows = output['experiments']
    period_cache = {}
    tokens = [json.dumps(r['config'],sort_keys=True) for r in rows]
    assert len(tokens)==len(set(tokens))
    policies=[]
    for row in rows:
        config=row['config']
        if config['meta']=='switch' and config['bear']=='cash' and config['exit']=='natural':
            equivalent=dict(meta='gate',family=config['family'],confirm=config['confirm'])
            gate=next(r for r in rows if r['config']==equivalent)
            assert gate['metrics']==row['metrics'] and gate['thrashing']==row['thrashing']
            policies.append(json.dumps(equivalent,sort_keys=True))
        else:
            policies.append(json.dumps(config,sort_keys=True))
    for r in rows:
        cfg=r['config']
        result=simulate_portfolio(p[cfg['family']],**execution(cfg,data,reg))
        assert summary(result)==r['metrics']
        champ=output['baseline']['volume']
        assert r['dominates']==(result['cagr']>champ['cagr'] and result['mdd']<champ['mdd'] and result['sharpe']>champ['sharpe'])
        t=r['thrashing']; events=t['events']
        gaps=np.diff([e['index'] for e in events])
        assert t['transitions']==len(events)
        for n in [1,3,5]:
            assert t['within'][str(n)]['count']==int((gaps<=n).sum())
            assert t['within'][str(n)]['pct']==(int((gaps<=n).sum())/len(events)*100 if events else 0)
        if 'robustness' not in r:
            assert not r['dominates']
            continue
        b=r['robustness']
        replay, records, _, _, _ = ledger_run(p[cfg['family']],execution(cfg,data,reg))
        assert records==b['trades'] and summary(replay)==r['metrics']
        net=sum(t['pnl'] for t in records)
        top10=sum(sorted([t['pnl'] for t in records],reverse=True)[:10])/net*100
        by_symbol=[sum(t['pnl'] for t in records if t['symbol']==s) for s in frames]
        top5=sum(sorted(by_symbol,reverse=True)[:5])/net*100
        np.testing.assert_allclose([top10,top5],[b['concentration']['10']['net_pct'],b['symbols']['net_pct']],atol=1e-10)
        assert len(b['periods'])==len(b['legacy_periods'])==8
        for cell in { (c['start'],c['end']):c for c in b['periods']+b['legacy_periods']}.values():
            start,end=cell['start'],cell['end']
            key=(start,end)
            if key not in period_cache:
                sub={f:{s:df.loc[start:end] for s,df in v.items() if len(df.loc[start:end])} for f,v in p.items()}
                period_cache[key]=(sub,{f:prepare(v) for f,v in sub.items()})
            sub,sd=period_cache[key]
            assert summary(simulate_portfolio(sub[cfg['family']],**execution(cfg,sd,reg)))==cell['metrics']
            btc=frames['BTC'].loc[start:end]
            expected=((btc.Close.iloc[-1]/btc.Open.iloc[0])*(1-.0004)**2)**(365.25/(btc.index[-1]-btc.index[0]).days)*100-100
            assert abs(expected-cell['btc_cagr'])<1e-10
            assert cell['alpha']==cell['metrics']['cagr']-cell['btc_cagr']
        assert b['alpha_positive']==sum(c['alpha']>0 for c in b['periods'])
        assert b['legacy_alpha_positive']==sum(c['alpha']>0 for c in b['legacy_periods'])
        trials=b['monte_carlo']['trials']
        assert [t['seed'] for t in trials]==list(range(1000000,1000300))
        for k in ['cagr','sharpe']:
            assert b['monte_carlo']['tests'][k]['p']==(1+sum(t[k]>=result[k] for t in trials))/301
        for t in [trials[0],trials[149],trials[-1]]:
            rd={f:random_data(v,t['seed'],b['monte_carlo']['probability']) for f,v in data.items()}
            assert summary(simulate_portfolio(p[cfg['family']],**execution(cfg,rd,reg)))=={k:t[k] for k in r['metrics']}
        boot=b['bootstrap']
        assert boot['iterations']==1000 and boot['block_size']==20
        returns=np.array(boot['returns'])
        ordered=sorted(records,key=lambda t:(t['entry'],t['exit'],t['id']))
        np.testing.assert_allclose(returns,[t['proceeds']/t['cost']-1 for t in ordered],atol=1e-14)
        assert len(boot['block_starts'])==1000
        rng=np.random.default_rng(710000)
        samples=[]
        for starts in boot['block_starts']:
            expected=rng.integers(0,len(records)-20+1,size=int(np.ceil(len(records)/20))).tolist()
            assert starts==expected
            indices=(np.array(starts)[:,None]+np.arange(20)).ravel()[:len(records)]
            x=returns[indices]
            samples.append(float(x.mean()/x.std(ddof=1)*np.sqrt(len(records)/result['years'])))
        np.testing.assert_allclose(samples,boot['samples'],atol=1e-12)
        np.testing.assert_allclose(np.percentile(samples,[2.5,97.5]),boot['ci95'],atol=1e-12)
        votes=[b['alpha_positive']>=7 and b['legacy_alpha_positive']>=7,top10<=103 and top5<=88,
               all(b['monte_carlo']['tests'][k]['p']<.05 for k in ['cagr','sharpe']),
               boot['ci95'][0]>0,r['thrashing']['within']['5']['pct']<=50]
        assert votes==b['votes'] and b['verdict']==('통과' if all(votes) else '기각')
    if output['status']=='복귀조건 B 달성':
        assert len(set(policies))>=50 and not any(all(r.get('robustness',{}).get('votes',[False])) for r in rows)
    print(f'PASS Round10: synthetic scale/fees/strategy holds/cash exits/ledger; 5 baseline exact; {len(rows)} configuration replay / {len(set(policies))} distinct policies; strict votes/transition gaps/MC samples/bootstrap independent arithmetic',flush=True)


if __name__=='__main__':
    run()
