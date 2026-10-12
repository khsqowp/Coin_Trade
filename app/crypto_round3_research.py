"""Offline Round 3: 48 restart variants, three sizing and two loose hybrids."""
import json
import sys
import numpy as np
import pandas as pd
from app.technical_signal_common import ta
from app.crypto_technical_ict_research import ROOT, load_data
from app.crypto_hybrid_drawdown_research import signals, checked
from app.technical_portfolio_engine import prepare, simulate_portfolio

PATH=ROOT/'docs/round3-results-2026-10-06.json'
NAMES=['volume_spike_cap5','heikin_ashi','frvp']
LABELS={'volume_spike_cap5':'거래량폭증 cap5%','heikin_ashi':'하이킨 아시','frvp':'FRVP',
        'heikin_ashi_volume_spike_loose':'하이킨 아시+거래량폭증 ±3일',
        'frvp_volume_spike_loose':'FRVP+거래량폭증 ±3일'}


def target(m):
    return bool(m['cagr']>=62.35 and m['sharpe']>=1.165 and m['mdd']<=53.38)


def prep(name,frames):
    return signals('volume_spike',frames,5.) if name=='volume_spike_cap5' else signals(name,frames)


def btc_trend(frame):
    return (frame.Close > frame.Close.rolling(50).mean()).to_dict()


def dominates(a,b):
    return a['cagr']>=b['cagr'] and a['sharpe']>=b['sharpe'] and a['mdd']<=b['mdd'] and any(a[k]!=b[k] for k in ['cagr','sharpe','mdd'])


def run():
    frames,manifest,skipped=load_data()
    prior=json.loads((ROOT/'docs/hybrid-drawdown-results-2026-10-06.json').read_text())
    assert manifest==prior['manifest']
    reference=prior['supplemental_baselines'][0]['metrics']
    d=dict(runtime=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,indicators=ta.__name__),manifest=manifest,skipped=skipped,
           config=dict(top_k=8,hold_days=20,fee_pct_one_way=.04,target_vol=.40,weight_cap=.25,
                       lookback=20,annualization=365,resume_grace_days=1),
           literal_target=dict(cagr=62.35,sharpe=1.165,mdd=53.38),reference=reference,
           baselines=[],breaker=[],volatility=[],loose=[])
    def add(group,name,config,prepared,prepped):
        m=checked(simulate_portfolio(prepped,prepared=prepared,**config))
        r=dict(name=name,config=config.copy(),metrics=m,target=target(m),
               reference_dominance=bool(all(m[k]>=reference[k] for k in ['cagr','sharpe']) and m['mdd']<=reference['mdd']))
        r['config'].pop('btc_resume',None)
        d[group].append(r)
        print(group,name,r['config'],json.dumps({k:v for k,v in m.items() if k!='breaker_log'}),flush=True)
        return r
    trend=btc_trend(frames['BTC'])
    for name in NAMES:
        prepped=prep(name,frames); data=prepare(prepped)
        baseline=add('baselines',name,{},data,prepped)
        old=reference if name==NAMES[0] else next(r['metrics'] for r in prior['baselines'] if r['name']==name)
        assert all(abs(baseline['metrics'][k]-old[k])<1e-10 for k in ['cagr','mdd','sharpe','trades'])
        for threshold in [.15,.20,.25,.30]:
            for mode,days in [('cooldown',20),('cooldown',40),('cooldown',60),('btc_sma50',20)]:
                config=dict(dd_trigger=threshold,resume_mode=mode,cooldown_days=days)
                if mode=='btc_sma50': config['btc_resume']=trend
                add('breaker',name,config,data,prepped)
        add('volatility',name,dict(sizing='inverse_vol',target_vol=.40,weight_cap=.25),data,prepped)
    for name in ['heikin_ashi_volume_spike_loose','frvp_volume_spike_loose']:
        prepped=prep(name,frames)
        r=add('loose',name,{},prepare(prepped),prepped)
        r['signal_count']=sum(int(df.SIGNAL.sum()) for df in prepped.values())
        r['strict']=next(x for x in prior['baselines'] if x['name']==name.replace('_loose',''))
    rows=d['breaker']+d['volatility']+d['loose']
    d['winners']=[r for r in rows if r['target']]
    d['reference_winners']=[r for r in rows if r['reference_dominance']]
    allrows=rows+d['baselines']
    d['pareto_frontier']=[r for r in allrows if not any(dominates(o['metrics'],r['metrics']) for o in allrows)]
    def deficit(r):
        m=r['metrics'];return max(0,(62.35-m['cagr'])/62.35)+max(0,(1.165-m['sharpe'])/1.165)+max(0,(m['mdd']-53.38)/53.38)
    d['candidates']=sorted([r for r in d['pareto_frontier'] if r not in d['baselines']],key=deficit)[:3]
    PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str))
    print('DONE: 53 experiments; literal winners',len(d['winners']),'reference winners',len(d['reference_winners']),flush=True)
    return d


if __name__=='__main__':
    run()
