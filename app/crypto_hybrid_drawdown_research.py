"""Offline Round 2 paired-engine comparison and complete breaker grid."""
import importlib
import json
import sys
import numpy as np
from app.crypto_technical_ict_research import ROOT, load_data
from app.technical_signal_common import ta
from app.technical_portfolio_engine import prepare, simulate_portfolio
from app.volume_spike_signal_core import find_signals as volume_signals, simulate_portfolio as legacy

NAMES=['volume_spike','heikin_ashi','frvp','heikin_ashi_volume_spike','frvp_volume_spike']
LABELS=dict(zip(NAMES,['거래량폭증 cap3%','하이킨 아시','FRVP','하이킨 아시+거래량폭증','FRVP+거래량폭증']))
PATH=ROOT/'docs/hybrid-drawdown-results-2026-10-06.json'


def signals(name,frames,cap=3.):
    if name=='volume_spike':
        out={s:volume_signals(df,volume_multiple=3.,max_price_change_pct=cap) for s,df in frames.items()}
        for df in out.values():
            df['ATR14']=ta.atr(df.High,df.Low,df.Close,length=14)
            df['STOP_LEVEL']=df.Low.shift(1).rolling(20).min()
        return out
    core=importlib.import_module(f'app.{name}_signal_core')
    return {s:core.find_signals(df) for s,df in frames.items()}


def target(m):
    return bool(m['cagr']>=66 and m['sharpe']>=1.20 and m['mdd']<=55)


def checked(m):
    assert m['trades']>0 and all(np.isfinite(m[k]) for k in ['cagr','mdd','sharpe','final'])
    assert -100<m['cagr']<1000 and 0<=m['mdd']<=100 and m['final']>0
    return m


def run_strategy(name,frames=None):
    if frames is None: frames,_,_=load_data()
    prepped=signals(name,frames); data=prepare(prepped)
    m=checked(simulate_portfolio(prepped,prepared=data,top_k=8,hold_days=20))
    print(name,json.dumps(m),flush=True)
    return m


def run():
    frames,manifest,skipped=load_data()
    old=json.loads((ROOT/'docs/technical-ict-results-2026-10-06.json').read_text())
    assert manifest==old['manifest'], 'Round 1 cache changed'
    output=dict(runtime=dict(python=sys.version,numpy=np.__version__,indicators=ta.__name__),
                since='2019-01-01',cutoff_exclusive='2026-10-06',manifest=manifest,skipped=skipped,
                config=dict(top_k=8,hold_days=20,fee_pct_one_way=.04,stop='none',tp='none',timing='next_open',selection='rank',dd_resume=.10),
                engine_comparison=[],baselines=[],sweep=[])
    for cap in [3.,5.]:
        prepped=signals('volume_spike',frames,cap)
        a=checked(legacy(prepped,8,20)); b=checked(simulate_portfolio(prepped,top_k=8,hold_days=20))
        output['engine_comparison'].append(dict(price_cap=cap,legacy=a,new=b,delta_new_minus_legacy={k:b[k]-a[k] for k in ['cagr','mdd','sharpe','trades']}))
        print('paired engines',cap,a,b,flush=True)
    for name in NAMES:
        prepped=signals(name,frames); data=prepare(prepped)
        baseline=checked(simulate_portfolio(prepped,prepared=data,top_k=8,hold_days=20))
        if name in ['heikin_ashi','frvp']:
            prior=next(s['baseline'] for s in old['strategies'] if s['name']==name)
            assert all(abs(baseline[k]-prior[k])<1e-10 for k in ['cagr','mdd','sharpe','trades'])
        row=dict(name=name,metrics=baseline,target=target(baseline),signal_count=sum(int(df.SIGNAL.sum()) for df in prepped.values()))
        output['baselines'].append(row); print('baseline',name,baseline,flush=True)
        for threshold in [.15,.20,.25,.30]:
            m=checked(simulate_portfolio(prepped,prepared=data,top_k=8,hold_days=20,dd_trigger=threshold))
            row=dict(name=name,dd_trigger=threshold,metrics=m,target=target(m),
                     mdd_improvement=baseline['mdd']-m['mdd'],cagr_loss=baseline['cagr']-m['cagr'],sharpe_loss=baseline['sharpe']-m['sharpe'])
            output['sweep'].append(row); print('breaker',name,threshold,m,flush=True)
        PATH.write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str))
    output['supplemental_baselines']=[dict(name='volume_spike_cap5',metrics=output['engine_comparison'][1]['new'],target=target(output['engine_comparison'][1]['new']))]
    rows=output['baselines']+output['sweep']+output['supplemental_baselines']
    def dominates(a,b):
        x,y=a['metrics'],b['metrics']
        return x['cagr']>=y['cagr'] and x['sharpe']>=y['sharpe'] and x['mdd']<=y['mdd'] and any(x[k]!=y[k] for k in ['cagr','sharpe','mdd'])
    frontier=[r for r in rows if not any(dominates(o,r) for o in rows)]
    def deficit(r):
        m=r['metrics']
        return max(0,(66-m['cagr'])/66)+max(0,(1.2-m['sharpe'])/1.2)+max(0,(m['mdd']-55)/55)
    output['winners']=[r for r in rows if r['target']]
    output['pareto_frontier']=frontier
    output['closest_candidates']=sorted(frontier,key=deficit)[:3]
    output['largest_mdd_improvement']=max(output['sweep'],key=lambda r:r['mdd_improvement'])
    PATH.write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str))
    return output


if __name__=='__main__':
    run()
