from __future__ import annotations
import argparse,json,sys,gc
from pathlib import Path
import numpy as np
from bb import ROOT,load_dataset,evaluate,candidates,candidate_state,bollinger,simulate_entries,signal_mask,portfolio,_stats,_costs

KS=[2.0,2.5]; EXITS=['upper','middle']; STOPS=[.010,.015]; FILLS=['base','opt']; FILTERS=['A0','A1','A2']

def baseline(p,cell,accepted,draws=1000,phase='dev'):
    if not accepted: return {'B1':None,'B2':None}
    rank,active,warm=candidates(p); bands=bollinger(p.C,20,cell['k']); sim=simulate_entries(p,bands,{'target':cell['exit'],'stop':cell['stop']},cell['fill'])
    gross=sim['gross']
    try:
        import sys;sys.path.insert(0,'/home/noroot/research/stock_loop');from lib.costs import KRCost,USCost
    except Exception: KRCost=USCost=None
    if p.name=='us': c=float(USCost().roundtrip()) if USCost else .0030278; cost=np.full_like(gross,c)
    else:
        vals=np.broadcast_to(p.value20[None,:],gross.shape)
        cost=KRCost('B').roundtrip(vals) if KRCost else (.002+.0003+2*np.where(np.nan_to_num(vals,nan=0)>=2e10,.0005,.001))
    net=gross-cost
    sessions=np.arange(len(p.session_dates)); trad=sessions[sessions>=p.warm_sessions]; cut=int(np.floor(.7*len(trad)))
    allowed=trad[:cut] if phase=='dev' else trad[cut:]
    phase_rows=np.isin(p.session,allowed)
    elig1=p.valid & warm[:,None] & phase_rows[:,None]
    rank2,active2=candidate_state(p,rank,active,cell['fill'])
    elig2=elig1 & (rank2>=20)&(rank2<=50)&active2
    event=np.array([a['signal_idx'] for a in accepted if phase_rows[a['signal_idx']]],int); actual=np.mean([a['gross']-cost[a['signal_idx'],a['symbol_idx']] for a in accepted if phase_rows[a['signal_idx']]])
    out={}
    for key,eligible,seed in [('B1',elig1,41),('B2',elig2,42)]:
        ok=eligible & np.isfinite(net); pools=[net[t,ok[t]] for t in event]; pools=[x for x in pools if len(x)]
        rng=np.random.default_rng(seed)
        if pools:
            picks=np.vstack([pool[rng.integers(0,len(pool),size=draws)] for pool in pools]); arr=picks.mean(axis=0)
        else: arr=np.array([])
        out[key]={'draws':int(len(arr)),'draw_mean':float(arr.mean()) if len(arr) else None,'draw_sd':float(arr.std()) if len(arr) else None,'actual_percentile':float((arr<actual).mean()) if len(arr) else None}
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['dev','test'],required=True);ap.add_argument('--datasets',default='us,kr,tick5,tick1');a=ap.parse_args()
    lock=ROOT/'TEST_LOCK'
    if a.phase=='test':
        if lock.exists(): print('TEST_LOCK exists; refusing repeat test',file=sys.stderr);raise SystemExit(2)
        lock.write_text('TEST run consumed\n')
    cells=[]
    for name in a.datasets.split(','):
        p=load_dataset(name); cache={}
        filters=['A0','A1','A2']
        if name.startswith('tick'): filters=['A0','A2'] # A1=A2
        for k in KS:
            for ex in EXITS:
                for stop in STOPS:
                    for fill in FILLS:
                        for f in filters:
                            cell={'dataset':name,'k':k,'exit':ex,'stop':stop,'fill':fill,'filter':f}
                            z=evaluate(p,cell,a.phase,cache); cells.append((cell,z))
                        gc.collect()
                        cache.pop((k,ex,stop,fill),None)
    result={'phase':a.phase,'trial_count':len(set((c['dataset'],c['k'],c['exit'],c['stop']) for c,_ in cells)),'cells':[{'cell':c,'stats':{k:v for k,v in z.items() if k!='trades'}} for c,z in cells]}
    outpath=ROOT/f'results_{a.phase}.json';outpath.write_text(json.dumps(result,indent=2,allow_nan=True))
    if a.phase=='dev':
        extras={}; summary={}
        for name in a.datasets.split(','):
            grouped={}
            for c,z in cells:
                if c['dataset']!=name: continue
                key=(c['k'],c['exit'],c['stop'],c['fill'])
                grouped.setdefault(key,{'k':c['k'],'exit':c['exit'],'stop':c['stop'],'fill':c['fill'],'A0':None,'A1':None,'A2':None})[c['filter']]=z.get('net_mean')
            summary[name]=list(grouped.values())
            subset=[(c,z) for c,z in cells if c['dataset']==name and c['filter']=='A0' and c['fill']=='base' and z['n']>=30]
            primary=next(((c,z) for c,z in subset if c['k']==2.0 and c['exit']=='upper' and c['stop']==.01),None)
            best=max(subset,key=lambda x:x[1].get('net_mean',-np.inf)) if subset else None
            p=load_dataset(name)
            for tag,item in [('primary',primary),('dev_best',best)]:
                if item:
                    c,z=item; sim={'k':c['k'],'exit':c['exit'],'stop':c['stop'],'fill':c['fill']}
                    # reconstruct accepted records from evaluated serialized trade rows
                    alltr=z.get('trades',[]); symidx={s:i for i,s in enumerate(p.symbols)}
                    accepted=[dict(signal_idx=x['signal_idx'],symbol_idx=symidx[x['symbol']],entry_idx=x['entry_idx'],exit_idx=x['exit_idx'],gross=x['gross'],reason=x['reason']) for x in alltr]
                    extras.setdefault(name,{})[tag]={'cell':c,'baselines':baseline(p,sim,accepted,phase='dev')}
        result['baselines']=extras; result['summary']=summary; outpath.write_text(json.dumps(result,indent=2,allow_nan=True))
        for name,rows in summary.items():
            print(f"{name}: cell | A0 | A1 | A2")
            seen={}
            for row in rows:
                print(f"k{row['k']} {row['exit']} s{row['stop']} {row['fill']}: {row['A0']} | {row['A1']} | {row['A2']}")
    # Coverage and combined artifact on test; dev is read if available.
    if a.phase=='test':
        devpath=ROOT/'results_dev.json'; dev=json.loads(devpath.read_text()) if devpath.exists() else None
        extras={}
        if dev:
            for name in a.datasets.split(','):
                primary=next((x for x in dev.get('cells',[]) if x['cell']['dataset']==name and x['cell']['filter']=='A0' and x['cell']['fill']=='base' and x['cell']['k']==2.0 and x['cell']['exit']=='upper' and x['cell']['stop']==.01),None)
                bestmeta=dev.get('baselines',{}).get(name,{}).get('dev_best',{}); bestid=bestmeta.get('cell')
                devbest=next((x for x in dev.get('cells',[]) if bestid and x['cell']==bestid),None)
                p=load_dataset(name); symidx={s:i for i,s in enumerate(p.symbols)}
                for tag,item in [('primary',primary),('dev_best',devbest)]:
                    if item:
                        c=item['cell']; accepted=[dict(signal_idx=x['signal_idx'],symbol_idx=symidx[x['symbol']],entry_idx=x['entry_idx'],exit_idx=x['exit_idx'],gross=x['gross'],reason=x['reason']) for x in item['stats'].get('trades',[])]
                        # Test-phase accepted trades are recovered by evaluating the fixed cell identity.
                        z=evaluate(p,c,'test',{}); accepted=[dict(signal_idx=x['signal_idx'],symbol_idx=symidx[x['symbol']],entry_idx=x['entry_idx'],exit_idx=x['exit_idx'],gross=x['gross'],reason=x['reason']) for x in z.get('trades',[])]
                        extras.setdefault(name,{})[tag]={'cell':c,'baselines':baseline(p,{k:c[k] for k in ('k','exit','stop','fill')},accepted,phase='test')}
        result['baselines']=extras; outpath.write_text(json.dumps(result,indent=2,allow_nan=True))
        meta={'dev':dev,'test':result,'assumptions':{'cost':'lib.costs defaults; KR scenario B, A Prime and 2x sensitivities','survivorship':'current constituents/listings; short sample; no capital inference'},'coverage':{}}
        for name in a.datasets.split(','):
            p=load_dataset(name); meta['coverage'][name]={'sessions':len(p.session_dates),'first_date':str(p.session_dates[0]) if len(p.session_dates) else None,'last_date':str(p.session_dates[-1]) if len(p.session_dates) else None,'symbols':p.N,'bars':p.T}
        (ROOT/'results.json').write_text(json.dumps(meta,indent=2,allow_nan=True))
if __name__=='__main__': main()
