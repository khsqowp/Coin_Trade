"""Independent Round 8 winner replay and stored robustness arithmetic."""
import json

import numpy as np
import pandas as pd

from app.crypto_round8_research import PATH, DOC, aggregate, core, filtered, resolved, dominates
from app.crypto_technical_ict_research import ROOT, load_data
from app.crypto_round4_robustness import ledger_run
from app.crypto_round7_research import random_data, summary
from app.technical_portfolio_engine import prepare, simulate_portfolio


def run():
    d=json.loads(PATH.read_text())
    frames,manifest,_=load_data()
    assert manifest==d['manifest'] and len(frames)==45
    _,inventory,top,_=aggregate()
    assert len(inventory)==len(d['historical_inventory'])
    assert [(r['family'],r['metrics']) for r in top]==[(r['family'],r['metrics']) for r in d['top10']]
    assert len(top)==len({r['family'] for r in top})==10
    pairs=[(r['metrics']['sharpe'],r['metrics']['cagr']) for r in top]
    assert pairs==sorted(pairs,reverse=True)
    winners=[r for r in d['experiments'] if r.get('robustness',{}).get('verdict')=='통과']
    assert len(winners)==1 and d['status']=='복귀조건 A 달성'
    r=winners[0]; b=r['robustness']
    p=filtered(core(r['family'],frames),frames,r['filter']); cfg=resolved(r['config'],frames)
    full,records,_,_,_=ledger_run(p,cfg)
    assert summary(full)==r['metrics'] and records==b['trades'] and dominates(full)
    # Independent contribution arithmetic, not reuse of concentration helper.
    net=sum(t['pnl'] for t in records)
    top10=sum(sorted([t['pnl'] for t in records],reverse=True)[:10])/net*100
    by_symbol={s:sum(t['pnl'] for t in records if t['symbol']==s) for s in frames}
    top5=sum(sorted(by_symbol.values(),reverse=True)[:5])/net*100
    np.testing.assert_allclose([top10,top5],[b['concentration']['10']['net_pct'],b['symbols']['net_pct']],atol=1e-12)
    assert len(b['periods'])==8 and len({(c['start'],c['end']) for c in b['periods']})==8
    for c in b['periods']:
        start,end=c['start'],c['end']; bars=frames['BTC'].loc[start:end]
        assert 728 <= (bars.index[-1]-bars.index[0]).days <= 731
        years=(bars.index[-1]-bars.index[0]).days/365.25
        btc=((bars.Close.iloc[-1]/bars.Open.iloc[0])*(1-.0004)**2)**(1/years)*100-100
        np.testing.assert_allclose(btc,c['btc_cagr'],atol=1e-12)
        sub={s:df.loc[start:end] for s,df in p.items() if len(df.loc[start:end])}
        assert summary(simulate_portfolio(sub,**cfg))==c['metrics']
        assert c['alpha']==c['metrics']['cagr']-c['btc_cagr']
    mc=b['monte_carlo']; trials=mc['trials']; data=prepare(p)
    assert len(trials)==len({t['seed'] for t in trials})==300
    eligible=np.isfinite(data[2]['Open'][:-1]) & np.isfinite(data[2]['Open'][1:])
    assert mc['probability']==len(records)/eligible.sum()
    for trial in [trials[0],trials[149],trials[-1]]:
        m=simulate_portfolio(p,prepared=random_data(data,trial['seed'],mc['probability']),**cfg)
        assert summary(m)=={k:trial[k] for k in summary(m)}
    for k in ['cagr','sharpe']:
        values=np.array([t[k] for t in trials]); test=mc['tests'][k]
        assert test['p']==(1+sum(values>=full[k]))/301
        assert test['q95']==np.percentile(values,95)
    boot=b['bootstrap']; ordered=sorted(records,key=lambda t:(t['entry'],t['exit'],t['id']))
    returns=np.array([t['pnl']/t['cost'] for t in ordered])
    np.testing.assert_allclose(returns,boot['returns'],atol=1e-14)
    samples=[]
    for starts in boot['block_starts']:
        assert len(starts)==int(np.ceil(len(records)/20)) and 0<=min(starts)<=max(starts)<=len(records)-20
        indices=np.concatenate([np.arange(s,s+20) for s in starts])[:len(records)]
        x=returns[indices]; samples.append(x.mean()/x.std(ddof=1)*np.sqrt(len(records)/full['years']))
    assert len(samples)==1000 and boot['block_size']==20
    np.testing.assert_allclose(samples,boot['samples'],atol=1e-12)
    np.testing.assert_allclose(np.percentile(samples,[2.5,97.5]),boot['ci95'],atol=1e-12)
    votes=[sum(c['alpha']>0 for c in b['periods'])>=7,top10<=103 and top5<=88,
           all(mc['tests'][k]['p']<.05 for k in ['cagr','sharpe']),np.percentile(samples,2.5)>0]
    assert votes==b['votes'] and sum(votes)>=3
    for n in [1200,1900]:
        rd=(data[0][:n],data[1],{k:v[:n] for k,v in data[2].items()})
        short=simulate_portfolio(p,prepared=rd,return_trace=True,**cfg)
        assert short['trace'][:-1]==full['trace'][:n-1]
        assert short['allocations']==[a for a in full['allocations'] if pd.Timestamp(a['date'])<=data[0][n-1]]
    assert all(pd.Timestamp(a['known_through'])<pd.Timestamp(a['date']) for a in full['allocations'])
    doc=DOC.read_text()
    assert doc.count('## 21.')==doc.count('## 22.')==1
    assert '알파 양수 5/8' in doc and '**복귀조건 A 달성**' in doc
    for n in range(1,8):
        log=(ROOT/f'docs/round8-round{n}-regression-2026-10-07.txt').read_text()
        assert 'PASS:' in log and 'Traceback' not in log
    print('PASS: 8-source/10-family ranking; exact winner/969-trade ledger; 8 actual two-year windows independently replayed; concentration; 300 unique random seeds/3 full replays/p arithmetic; 1000 bootstrap sequences reconstructed; 2 execution prefixes/causal timestamps; 3-of-4 verdict; document and Round1-7 regression logs')


if __name__=='__main__': run()
