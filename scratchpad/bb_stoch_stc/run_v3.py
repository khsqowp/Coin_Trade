"""Cohort-level, train-only v3 strategy research runner."""
from __future__ import annotations
import argparse, itertools, json, os, signal, time, hashlib
from multiprocessing import get_context
from pathlib import Path
import numpy as np
import pandas as pd
from data import synthetic
from strategy import signal_frame, simulate
import run_v2 as v2
import nullbench

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results_v3'
_RUN_START=time.monotonic()
COHORTS={'L2':['BTCUSDT','ETHUSDT'], 'L5':['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT'],
         'M':['PEPEUSDT','PUMPUSDT','BEATUSDT','PENGUUSDT','TRUMPUSDT','BONKUSDT','SHIBUSDT','WIFUSDT','BOMEUSDT']}
TFS=('15m','1h','4h'); VARIANTS=('unconstrained','with_stop','long_only','short_only','combined')
SEED=20261120; WORKERS=6
_FRAMES={}; _SIGS={}

def _init(frames):
    global _FRAMES,_SIGS
    _FRAMES=frames; _SIGS={}
def _sig(key,cfg):
    token=(key,tuple(sorted(cfg.items())))
    if token not in _SIGS:
        df=_FRAMES[key]; seed=dict(v2.base.SIGGRID[0]); seed['stoch_min_cross_age']=0
        axes={name:cfg[name] for name in ('bb_window','stoch_cross_lag','stoch_level','stc_lag','stc_level')}
        bbkey=(key,'bb',axes['bb_window']); skey=(key,'stoch',axes['stoch_cross_lag'],axes['stoch_level']); tkey=(key,'stc',axes['stc_lag'],axes['stc_level'])
        if bbkey not in _SIGS:
            p=dict(seed,bb_window=axes['bb_window']); _SIGS[bbkey]=signal_frame(df,p)
        if skey not in _SIGS:
            p=dict(seed,stoch_cross_lag=axes['stoch_cross_lag'],stoch_level=axes['stoch_level']); _SIGS[skey]=signal_frame(df,p)
        if tkey not in _SIGS:
            p=dict(seed,stc_lag=axes['stc_lag'],stc_level=axes['stc_level']); _SIGS[tkey]=signal_frame(df,p)
        b,s,t=_SIGS[bbkey],_SIGS[skey],_SIGS[tkey]
        _SIGS[token]=pd.DataFrame({'long':b.bb_long.to_numpy() & s.stoch_long.to_numpy() & t.stc_long.to_numpy(),
            'short':b.bb_short.to_numpy() & s.stoch_short.to_numpy() & t.stc_short.to_numpy(),
            'bb_mid':b.bb_mid.to_numpy(),'atr':b.atr.to_numpy()},index=df.index)
        return _SIGS[token]
    return _SIGS[token]
def signal_grid():
    # 1,024 deterministic strict-signal combinations. Component conditions are
    # cached by signal_frame in each worker; omitted knobs stay canonical.
    seed=dict(v2.base.SIGGRID[0]); axes=(('bb_window',(0,2,4,8)),('stoch_cross_lag',(0,2,4,8)),
        ('stoch_level',(15,20,25,30)),('stc_lag',(0,2,4,8)),('stc_level',(10,25,40,50)))
    out=[]
    for vals in itertools.product(*(a[1] for a in axes)):
        p=seed.copy(); p.update({axes[i][0]:x for i,x in enumerate(vals)}); p['stoch_min_cross_age']=0; out.append(p)
    return out
def budgeted_signal_grid(quick=False):
    grid=signal_grid()
    if quick:return grid[:3]
    # Deterministic evenly spaced subset preserving coverage across all five axes.
    return [grid[i] for i in np.linspace(0,len(grid)-1,64,dtype=int)]
def management_grid():
    # 44 unique settings: 8 no-stop controls and 36 required-stop settings.
    base=dict(add_size_mult=1.,bb_mid_exit=False,opp_exit=False)
    out=[]
    for n,sp,tp,hold in itertools.product((0,2),(0,2),(2,5),(48,None)):
        if n and sp==0: continue
        out.append(dict(base,n_adds=n,add_spacing_pct=sp,tp_pct=tp,sl_pct=None,
                        atr_mult=None,stop_mode='off',max_hold_bars=hold))
    out=out[:8]
    for sl,atr_mult in [(3.,None),(5.,None),(8.,None),(None,2.),(None,3.),(None,4.)]:
        for tp in (2,5):
            for n,sp,hold in ((0,0,48),(2,2,None),(2,2,48)):
                out.append(dict(base,n_adds=n,add_spacing_pct=sp,tp_pct=tp,sl_pct=sl,
                    atr_mult=atr_mult,stop_mode='off' if sl is None and atr_mult is None else (f'pct{int(sl)}' if atr_mult is None else f'atr{atr_mult:g}'),max_hold_bars=hold))
    return out
def management_grid_for(tf, quick=False):
    grid=management_grid()
    if quick:return grid[:6]
    # On 15m, simulator cost grows with bars. Keep a deterministic 12-point
    # orthogonal coverage of exit, stop, add and hold axes; 1h/4h use all 44.
    if tf=='15m':
        no_stop=[x for x in grid if not requires_stop(x)][:6]
        required=[x for x in grid if requires_stop(x)]
        chosen=[next(x for x in required if x['stop_mode']==stopkey) for stopkey in ('pct3','pct5','pct8','atr2','atr3','atr4')]
        return no_stop+chosen
    return grid
def requires_stop(p): return p.get('sl_pct') is not None or p.get('atr_mult') is not None
def select_winners(candidates):
    """Shared selector: with_stop only considers explicitly stop-required settings."""
    result={}
    for name,side,stop in [('unconstrained',None,False),('with_stop','combined',True),
                           ('long_only','long',False),('short_only','short',False),('combined','combined',False)]:
        eligible=[x for x in candidates if (side is None or x['side']==side) and (not stop or requires_stop(x['management']))]
        if eligible: result[name]=max(eligible,key=lambda x:(x['score'],x['trades']))
    return result
def event_floor(n_series): return max(30,12*int(n_series))
def budget_exceeded(stage_start, max_minutes, now=None):
    """Stage wall budget applies once to the complete invoked stage set."""
    return (time.monotonic() if now is None else now)-stage_start > max_minutes*60
def frozen_cross_params(winner):
    """Return immutable parameter payload used for cross-cohort evaluation."""
    return (winner['signal'],winner['management'],winner['side'])
def window_indices(index, start, train_months, test_months):
    train_end=start+pd.DateOffset(months=train_months);test_end=train_end+pd.DateOffset(months=test_months)
    train=np.flatnonzero((index>=start)&(index<train_end));test=np.flatnonzero((index>=train_end)&(index<test_end))
    if len(train) and len(test): assert index[train[-1]] < index[test[0]]
    return train,test,train_end,test_end
def null_verdict(strategy_return,null_p90,plateau,trades):
    ok,gates=nullbench.verdict(strategy_return,null_p90,plateau=='FRAGILE',trades)
    return ('COUNTS' if ok else 'no edge'),gates
def cross_portions(full,train,test):
    return {name:{k:m[k] for k in ('trades','total_return','pf','max_dd')} for name,m in [('full',full),('train',train),('test',test)]}
def _score(m):
    pf=m['pf'] if np.isfinite(m['pf']) else 5.
    return m['total_return']-abs(m['max_dd'])+.25*min(pf,5.)
def _pooled_metrics(metrics):
    details=[]
    for m in metrics:
        if 'trade_details_json' in m: details.extend(json.loads(m['trade_details_json']))
        elif 'trade_details' in m: details.extend(m['trade_details'])
    returns=[float(t['return']) for t in details]
    gains=sum(x for x in returns if x>0);losses=abs(sum(x for x in returns if x<0))
    pf=gains/losses if losses else (float('inf') if gains else 0.)
    total=sum(float(m['total_return']) for m in metrics)
    mdd=sum(float(m['max_dd']) for m in metrics)
    return dict(total_return=total,max_dd=mdd,pf=pf,score=_score(dict(total_return=total,max_dd=mdd,pf=pf)))
def _log(msg):
    OUT.mkdir(exist_ok=True); line=f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with (OUT/'progress.log').open('a') as f:f.write(line+'\n');f.flush()
    print(line,flush=True)
def _load(cohort,tf,quick=False):
    frames={}
    for s in COHORTS[cohort]:
        p=ROOT/'data'/f'{s}_{tf}.parquet'
        frames[(s,tf)]=synthetic(s,tf,1200) if quick else pd.read_parquet(p)
    return frames
def _events_task(task):
    key,ci,cfg,cut=task; df=_FRAMES[key]; sf=_sig(key,cfg)
    close=df.close.to_numpy(float); op=df.open.to_numpy(float)
    scores=[]; events=0
    for col,direction in (('long',1.),('short',-1.)):
        ix=np.flatnonzero(sf[col].to_numpy()[:cut]); events += len(ix)
        valid=ix[ix+10<cut]
        if len(valid): scores.extend(((close[valid+10]/op[valid+1]-1)*direction*100).tolist())
    return ci,key,int(events),float(np.mean(scores)) if scores else 0.
def _eval_task(task):
    key,ci,cfg,mgmt,side,start,end=task; df=_FRAMES[key]; sf=_sig(key,cfg)
    return ci,key,side,mgmt,simulate(df.iloc[start:end],sf.iloc[start:end],mgmt,side,include_trade_details=True)
def _sig_local(df,cfg):
    return _sig(('local','tf'),cfg)
def _event_local(df,sf,cut):
    close=df.close.to_numpy(float);op=df.open.to_numpy(float);scores=[];events=0
    for col,direction in (('long',1.),('short',-1.)):
        ix=np.flatnonzero(sf[col].to_numpy()[:cut]);events+=len(ix);valid=ix[ix+10<cut]
        if len(valid):scores.extend(((close[valid+10]/op[valid+1]-1)*direction*100).tolist())
    return int(events),float(np.mean(scores)) if scores else 0.
def _pool_map(frames,tasks,fn,progress=False):
    with get_context('fork').Pool(WORKERS,initializer=_init,initargs=(frames,)) as pool:
        out=[];total=len(tasks);step=max(1,total//20);started=time.monotonic()
        for i,row in enumerate(pool.imap_unordered(fn,tasks,chunksize=1),1):
            out.append(row)
            if progress and (i==1 or i%step==0 or i==total):_log(f'tune simulations {i}/{total} elapsed={time.monotonic()-started:.1f}s')
        return out
def _tune_scope(cohort,tf,frames,quick=False,max_minutes=10):
    _init(frames)
    start=time.monotonic(); keys=list(frames); grid=budgeted_signal_grid(quick); cuts={k:int(len(frames[k])*.6) for k in keys}
    phase=OUT/'cache'/tf;phase.mkdir(parents=True,exist_ok=True)
    sig_cache={}; ev=[]
    for i,cfg in enumerate(grid):
        per=[]
        for k in keys:
            sig_cache[(k,i)]=_sig(k,cfg)
            evrow=_event_local(frames[k],sig_cache[(k,i)],cuts[k]);ev.append((i,k,*evrow));per.append((k,evrow))
        pd.DataFrame([dict(config_id=i,symbol=k[0],events=x[0],forward_return=x[1]) for k,x in per]).to_parquet(phase/f'events_{cohort}_{i:04d}.parquet',index=False)
        if i==max(1,int(len(grid)*.02))-1:
            elapsed=time.monotonic()-start;estimate=elapsed*len(grid)/max(1,i+1)
            _log(f'tune {cohort}/{tf} phase1 2% elapsed={elapsed:.1f}s projected_phase1={estimate:.1f}s')
    counts={i:sum(n for ci,k,n,s in ev if ci==i) for i in range(len(grid))}
    forward={i:float(sum(n*s for ci,k,n,s in ev if ci==i)/max(1,counts[i])) for i in range(len(grid))}
    floor=event_floor(len(keys)); eligible=[i for i in counts if counts[i]>=floor]
    # Directional train-only forward-return rank and >=2-knob de-duplication.
    ranked=sorted(eligible,key=lambda i:(forward[i],counts[i],-i),reverse=True)
    selected=[]
    for i in ranked:
        if all(sum(grid[i][k]!=grid[j][k] for k in grid[i])>=2 for j in selected): selected.append(i)
        if len(selected)>=(2 if quick else 12):break
    if quick and not selected: selected=[max(counts,key=counts.get)]
    if not selected:
        status=pd.DataFrame([dict(cohort=cohort,timeframe=tf,variant=v,status=f"INELIGIBLE: {max(counts.values(),default=0)} events",event_floor=floor) for v in VARIANTS])
        return [],pd.DataFrame(),status
    mgmts=management_grid_for(tf,quick); tasks=[]
    for ci in selected:
        for k in keys:
            cut=cuts[k]
            for side in ('combined','long','short'):
                for mg in mgmts: tasks.append((k,ci,grid[ci],mg,side,0,cut))
    vals=[];missing=[];tokens=[]
    for k,ci,cfg,mg,side,lo,hi in tasks:
        mgid=hashlib.sha256(json.dumps(mg,sort_keys=True).encode()).hexdigest()[:12]
        token=f'{k[0]}_{ci:04d}_{side}_{mgid}_{lo}_{hi}'
        cache=phase/f'{token}.parquet'
        if cache.exists():
            m=pd.read_parquet(cache).iloc[0].to_dict()
        else:
            missing.append((k,ci,cfg,mg,side,lo,hi));tokens.append(cache)
            continue
        vals.append((ci,k,side,mg,m))
    if missing:
        computed=_pool_map(frames,missing,_eval_task,progress=True)
        for (ci,k,side,mg,m),cache in zip(computed,tokens):
            m['trade_details_json']=json.dumps(m.pop('trade_details'),separators=(',',':'))
            pd.DataFrame([m]).to_parquet(cache,index=False);vals.append((ci,k,side,mg,m))
    grouped={}
    for ci,k,side,mg,m in vals: grouped.setdefault((ci,side,json.dumps(mg,sort_keys=True)),[]).append((k,mg,m))
    candidates=[]
    for (ci,side,mgj),per in grouped.items():
        ntr=sum(m['trades'] for _,_,m in per)
        if ntr < (0 if quick else 30): continue
        pooled=_pooled_metrics([m for _,_,m in per])
        candidates.append(dict(config_id=ci,signal=grid[ci],management=json.loads(mgj),side=side,trades=ntr,
                               score=pooled['score'],pool_pf=pooled['pf'],pool_mdd=pooled['max_dd'],pool_return=pooled['total_return'],per=per))
    winners=select_winners(candidates); rows=[]
    for name,w in winners.items():
        for k,mg,tr in w['per']:
            df=frames[k];cut=cuts[k];testpath=phase/f'{k[0]}_{w["config_id"]:04d}_{w["side"]}_{hashlib.sha256(json.dumps(w["management"],sort_keys=True).encode()).hexdigest()[:12]}_test.parquet'
            if testpath.exists():
                test=pd.read_parquet(testpath).iloc[0].to_dict();test['trade_details']=json.loads(test.pop('trade_details_json'))
            else:
                test=simulate(df.iloc[cut:],sig_cache[(k,w['config_id'])].iloc[cut:],w['management'],w['side'],include_trade_details=True)
                payload=dict(test);payload['trade_details_json']=json.dumps(payload.pop('trade_details'),separators=(',',':'));pd.DataFrame([payload]).to_parquet(testpath,index=False)
            train=tr
            row=dict(cohort=cohort,timeframe=tf,variant=name,symbol=k[0],config_id=w['config_id'],
                signal=json.dumps(w['signal'],sort_keys=True),management=json.dumps(w['management'],sort_keys=True),side=w['side'],
                train_trades=train['trades'],train_return=train['total_return'],train_score=w['score'],
                train_pf=train['pf'],train_mdd=train['max_dd'],test_trades=test['trades'],test_return=test['total_return'],test_mdd=test['max_dd'],test_pf=test['pf'],
                train_trades_json=train.get('trade_details_json','[]'),test_trades_json=json.dumps(test['trade_details'],separators=(',',':')))
            row.update({'test_'+x:y for x,y in test.items()});rows.append(row)
    # Axial signal and management neighbors, all scored on training slices only.
    p_rows=[]
    for name,w in winners.items():
        axial=[]; base=w['score']; cfg=w['signal']; mg=w['management']
        for axis,vals_axis in [('bb_window',(0,2,4,8)),('stoch_cross_lag',(0,2,4,8)),
                               ('stoch_level',(15,20,25,30)),('stc_lag',(0,2,4,8)),('stc_level',(10,25,40,50))]:
            ix=vals_axis.index(cfg[axis])
            for j in (ix-1,ix+1):
                if 0<=j<len(vals_axis):
                    z=cfg.copy();z[axis]=vals_axis[j]
                    scores=[]
                    for k in keys:
                        cut=cuts[k];scores.append(simulate(frames[k].iloc[:cut],signal_frame(frames[k],z).iloc[:cut],mg,w['side'],include_trade_details=True))
                    axial.append(_pooled_metrics(scores)['score'])
        for axis,vals_axis in [('tp_pct',(2,5)),('sl_pct',(None,3.,5.,8.)),('atr_mult',(None,2.,3.,4.)),('n_adds',(0,2)),('add_spacing_pct',(0,2)),('max_hold_bars',(48,None))]:
            ix=vals_axis.index(mg[axis])
            for j in (ix-1,ix+1):
                if 0<=j<len(vals_axis):
                    z=mg.copy();z[axis]=vals_axis[j]
                    if axis=='sl_pct':z['atr_mult']=None
                    if axis=='atr_mult':z['sl_pct']=None
                    z['stop_mode']='off' if z['sl_pct'] is None and z.get('atr_mult') is None else (f"pct{int(z['sl_pct'])}" if z['sl_pct'] is not None else f"atr{z['atr_mult']:g}")
                    if name=='with_stop' and not requires_stop(z):continue
                    scores=[]
                    for k in keys:
                        cut=cuts[k];scores.append(simulate(frames[k].iloc[:cut],signal_frame(frames[k],cfg).iloc[:cut],z,w['side'],include_trade_details=True))
                    axial.append(_pooled_metrics(scores)['score'])
        pct=100*sum(x>=.5*base for x in axial)/len(axial) if axial else 0
        p_rows.append(dict(cohort=cohort,timeframe=tf,variant=name,neighbors=len(axial),robust_neighbor_pct=pct,verdict='ROBUST' if pct>=70 else 'FRAGILE'))
    elapsed=time.monotonic()-start
    _log(f'tune {cohort}/{tf}: configs={len(grid)} eligible={len(eligible)} selected={len(selected)} floor={floor} elapsed={elapsed:.1f}s')
    status=pd.DataFrame([dict(cohort=cohort,timeframe=tf,variant=v,status='ELIGIBLE' if v in winners else f'INELIGIBLE: train trades below 30',event_floor=floor) for v in VARIANTS])
    return rows,pd.DataFrame(p_rows),status

def tune(quick=False,max_minutes=10):
    stage_start=time.monotonic(); budget=max_minutes*60
    all_winners=pd.read_csv(OUT/'tune_winners.csv').to_dict('records') if (OUT/'tune_winners.csv').exists() else []
    all_symbols=pd.read_csv(OUT/'tune_per_symbol.csv').to_dict('records') if (OUT/'tune_per_symbol.csv').exists() else []
    timings=pd.read_csv(OUT/'stage_timings.csv').to_dict('records') if (OUT/'stage_timings.csv').exists() else []
    all_elig=[]
    for cohort in COHORTS:
        for tf in TFS:
            marker=OUT/f'.tune_{cohort}_{tf}.done'
            if marker.exists():
                continue
            t=time.monotonic();frames=_load(cohort,tf,quick);rows,plate,status=_tune_scope(cohort,tf,frames,quick,max_minutes)
            pr=OUT/f'plateau_{cohort}_{tf}.csv';pd.DataFrame(plate).to_csv(pr,index=False)
            all_symbols.extend(rows);all_elig.extend(status.to_dict('records'))
            summary=[]
            for (variant,config_id),g in pd.DataFrame(rows).groupby(['variant','config_id']) if rows else []:
                first=g.iloc[0]
                summary.append(dict(cohort=cohort,timeframe=tf,variant=variant,signal=first.signal,management=first.management,side=first.side,
                    train_trades=int(g.train_trades.sum()),train_return=float(g.train_return.sum()),train_pf=_pooled_metrics([dict(total_return=float(r.train_return),max_dd=float(r.train_mdd),trade_details_json=r.train_trades_json) for r in g.itertuples()])['pf'],train_mdd=float(g.train_mdd.sum()),
                    test_trades=int(g.test_trades.sum()),test_return=float(g.test_return.sum()),test_pf=_pooled_metrics([dict(total_return=float(r.test_return),max_dd=float(r.test_mdd),trade_details_json=r.test_trades_json) for r in g.itertuples()])['pf'],test_mdd=float(g.test_mdd.sum()),
                    plateau_verdict=next((x['verdict'] for x in plate.to_dict('records') if x['variant']==variant),'FRAGILE'),eligibility_note='ELIGIBLE'))
            status_by={x['variant']:x['status'] for x in status.to_dict('records')}
            present={x['variant'] for x in summary}
            for variant in VARIANTS:
                if variant not in present:
                    summary.append(dict(cohort=cohort,timeframe=tf,variant=variant,signal=None,management=None,side=None,
                        train_trades=np.nan,train_return=np.nan,train_pf=np.nan,train_mdd=np.nan,
                        test_trades=np.nan,test_return=np.nan,test_pf=np.nan,test_mdd=np.nan,
                        plateau_verdict='FRAGILE',eligibility_note=status_by.get(variant,'INELIGIBLE: no train candidate')))
            all_winners.extend(summary)
            timings.append(dict(cohort=cohort,timeframe=tf,seconds=time.monotonic()-t))
            all_winners=[x for x in all_winners if not (x.get('cohort')==cohort and x.get('timeframe')==tf)]+summary
            all_symbols=[x for x in all_symbols if not (x.get('cohort')==cohort and x.get('timeframe')==tf)]+rows
            pd.DataFrame(all_winners).to_csv(OUT/'tune_winners.csv',index=False)
            pd.DataFrame(all_symbols).to_csv(OUT/'tune_per_symbol.csv',index=False)
            status.to_csv(OUT/f'eligibility_{cohort}_{tf}.csv',index=False)
            pd.DataFrame(timings).to_csv(OUT/'stage_timings.csv',index=False)
            marker.write_text(str(time.time()))
            if budget_exceeded(stage_start,max_minutes): raise TimeoutError(f'tune stage set exceeded total max-minutes={max_minutes}')
    pd.DataFrame(timings).to_csv(OUT/'stage_timings.csv',index=False)
    (OUT/'.tune.done').write_text(str(time.time()))

def wf(quick=False,max_minutes=10):
    """Cohort-pooled rolling selection with a checkpoint after every window."""
    from strategy import signal_frame
    started=time.monotonic(); budget=max_minutes*60
    rows=pd.read_csv(OUT/'wf.csv').to_dict('records') if (OUT/'wf.csv').exists() else []
    mark=OUT/'wf_windows.jsonl'; completed=set()
    if mark.exists():
        completed={tuple(json.loads(x)) for x in mark.read_text().splitlines() if x.strip()}
    scopes=[]
    for cohort in COHORTS:
      for tf in TFS:
        frames=_load(cohort,tf,quick)
        valid={k:d for k,d in frames.items() if cohort!='M' or d.index[-1]-d.index[0]>=pd.Timedelta(days=240)}
        for k in frames.keys()-valid.keys():_log(f'wf skip {k}: history under 8 months')
        if not valid:continue
        tm,vm=(6,2) if cohort=='M' else (12,3)
        origin=max(d.index[0] for d in valid.values()); last=min(d.index[-1] for d in valid.values()); month=0
        while origin+pd.DateOffset(months=month+tm+vm)<=last:
            scopes.append((cohort,tf,valid,origin,month,tm,vm));month+=vm
    total=len(scopes); full_grid=budgeted_signal_grid(False)
    # Measured 3-window ETA exceeded the remaining total budget at 64x12.
    # Keep broad deterministic axis coverage and still re-rank five signals per window.
    grid=[full_grid[i] for i in np.linspace(0,len(full_grid)-1,8,dtype=int)]; mg=management_grid()
    mg=[mg[i] for i in sorted(set(np.linspace(0,len(mg)-1,3,dtype=int)))]
    for wi,(cohort,tf,frames,origin,month,tm,vm) in enumerate(scopes,1):
        token=(cohort,tf,str(origin),month)
        if token in completed:continue
        a=origin+pd.DateOffset(months=month); b=a+pd.DateOffset(months=tm); c=b+pd.DateOffset(months=vm)
        train={k:d.loc[(d.index>=a)&(d.index<b)] for k,d in frames.items()}; test={k:d.loc[(d.index>=b)&(d.index<c)] for k,d in frames.items()}
        train={k:d for k,d in train.items() if len(d)}; test={k:d for k,d in test.items() if len(d)}
        if train and test:
            ranks=[]
            for ci,cfg in enumerate(grid):
                nsum=0; weighted=0.
                for k,d in train.items():
                    n,r=_event_local(d,signal_frame(d,cfg),len(d)); nsum+=n; weighted+=n*r
                ranks.append((weighted/max(1,nsum),nsum,-ci,cfg))
            top=[x[3] for x in sorted(ranks,reverse=True)[:5]]
            candidates=[]
            for cfg in top:
                sigs={k:signal_frame(d,cfg) for k,d in train.items()}
                for side in ('combined','long','short'):
                    for management in mg:
                        ms=[simulate(d,sigs[k],management,side,include_trade_details=True) for k,d in train.items()]
                        n=sum(x['trades'] for x in ms)
                        if n>=15:
                            pool=_pooled_metrics(ms); candidates.append((pool['score'],n,cfg,management,side))
            candidates.sort(key=lambda x:(x[0],x[1]),reverse=True); finalists=[]
            for item in candidates:
                if all(item[2]!=old[2] or item[3]!=old[3] or item[4]!=old[4] for old in finalists):finalists.append(item)
                if len(finalists)>=12:break
            if finalists:
                score,n,cfg,management,side=finalists[0]
                for key,d in test.items():
                    result=simulate(d,signal_frame(d,cfg),management,side)
                    rows.append(dict(cohort=cohort,timeframe=tf,symbol=key[0],month=month,train_start=str(a),train_end=str(b),test_start=str(b),test_end=str(c),train_score=score,train_trades=n,config=json.dumps(cfg,sort_keys=True),management=json.dumps(management,sort_keys=True),side=side,**{'test_'+k:v for k,v in result.items()}))
        pd.DataFrame(rows).to_csv(OUT/'wf.csv',index=False)
        with mark.open('a') as f:f.write(json.dumps(token)+'\n')
        elapsed=time.monotonic()-started; eta=elapsed/max(1,wi)*(total-wi)
        _log(f'wf windows {wi}/{total} elapsed={elapsed:.1f}s ETA={eta:.1f}s cohort={cohort}/{tf} month={month}')
        if elapsed>budget:raise TimeoutError('wf total --max-minutes exceeded')
    d=pd.DataFrame(rows)
    if len(d):
        marks=[json.loads(x) for x in mark.read_text().splitlines() if x.strip()]
        agg=[]
        for cohort,tf in sorted({(x[0],x[1]) for x in marks}):
          months=sorted(x[3] for x in marks if x[0]==cohort and x[1]==tf)
          for side in ('combined','long','short'):
            g=d[(d.cohort==cohort)&(d.timeframe==tf)&(d.side==side)]
            by_month={m:q for m,q in g.groupby('month')}; returns=[]; trades=0; selected=0
            for m in months:
                q=by_month.get(m)
                if q is None:returns.append(0.);continue
                trades+=int(q.test_trades.sum());returns.append(float(q.test_total_return.sum()));selected+=int(float(q.train_trades.iloc[0])>=15)
            agg.append(dict(cohort=cohort,timeframe=tf,side=side,windows=len(months),windows_selected=selected,test_trades=trades,total_test_return=float(sum(returns)),mean_test_return=float(np.mean(returns)) if returns else 0.,positive_windows_pct=float(np.mean(np.asarray(returns)>0)*100) if returns else 0.))
        pd.DataFrame(agg).to_csv(OUT/'wf_summary.csv',index=False)
    (OUT/'.wf.done').write_text(str(time.time()))

def null_stage(max_minutes=35):
    import json
    from strategy import signal_frame
    src=pd.read_csv(OUT/'tune_winners.csv'); per=pd.read_csv(OUT/'tune_per_symbol.csv'); out=OUT/'null_summary.csv'
    done=pd.read_csv(out).to_dict('records') if out.exists() else []; seen={(x['cohort'],x['timeframe'],x['variant']) for x in done}; started=time.monotonic()
    for row in src.to_dict('records'):
        k=(row['cohort'],row['timeframe'],row['variant'])
        if k in seen:continue
        trades=pd.to_numeric(row.get('test_trades'),errors='coerce')
        if not isinstance(row.get('signal'),str) or not row['signal'].startswith('{') or pd.isna(trades) or int(trades)<1:
            done.append(dict(cohort=k[0],timeframe=k[1],variant=k[2],status='INELIGIBLE',null_reps=0))
            pd.DataFrame(done).to_csv(out,index=False);seen.add(k);continue
        g=per[(per.cohort==k[0])&(per.timeframe==k[1])&(per.variant==k[2])]; frames={};bounds={};counts={}
        cfg=json.loads(row['signal']);mg=json.loads(row['management']);side=row['side'];
        for x in g.to_dict('records'):
            df=pd.read_parquet(ROOT/'data'/f"{x['symbol']}_{k[1]}.parquet");cut=int(len(df)*.6);sf=signal_frame(df,cfg);sg=sf.iloc[cut:]
            frames[(x['symbol'],k[1])]=df;bounds[(x['symbol'],k[1])]=(cut,len(df))
            details=json.loads(x.get('test_trades_json') or '[]');counts[(x['symbol'],k[1])]=dict(trades=len(details),long=sum(t.get('side')=='long' for t in details),short=sum(t.get('side')=='short' for t in details),bb_mid=sf.bb_mid.to_numpy(),atr=sf.atr.to_numpy())
        ck=OUT/f"null_reps_{k[0]}_{k[1]}_{k[2]}.jsonl"
        vals=nullbench.run_null(frames,bounds,mg,counts,seed=SEED,repetitions=200,workers=WORKERS,progress=lambda msg:_log(f'null {k} {msg}'),checkpoint=ck)
        ns=nullbench.null_summary(vals);pct=nullbench.percentile_of(float(row['test_return']),vals);verdict_text,why=null_verdict(float(row['test_return']),ns['null_p90'],row.get('plateau_verdict'),int(row['test_trades']))
        done.append(dict(cohort=k[0],timeframe=k[1],variant=k[2],status='DONE',strategy_test_return=row['test_return'],test_trades=row['test_trades'],null_reps=len(vals),null_percentile=pct,**ns,verdict=verdict_text,verdict_gates=why))
        pd.DataFrame(done).to_csv(out,index=False);_log(f'null checkpoint {len(done)}/{len(src)} elapsed={time.monotonic()-started:.1f}s ETA=remaining guarded')
        if time.monotonic()-started>max_minutes*60:raise TimeoutError('null stage total --max-minutes exceeded')

def cross_stage(max_minutes=35):
    from strategy import signal_frame
    winners=pd.read_csv(OUT/'tune_winners.csv'); rows=[];started=time.monotonic()
    for src,dst in [('L5','M'),('M','L5'),('L2','M')]:
      for tf in TFS:
       for variant in VARIANTS:
        w=winners[(winners.cohort==src)&(winners.timeframe==tf)&(winners.variant==variant)]
        if not len(w) or not isinstance(w.iloc[0].signal,str) or not w.iloc[0].signal.startswith('{'):continue
        w=w.iloc[0];cfg=json.loads(w.signal);mg=json.loads(w.management);side=w.side
        for sym in COHORTS[dst]:
         df=pd.read_parquet(ROOT/'data'/f'{sym}_{tf}.parquet');short=dst=='M' and df.index[-1]-df.index[0]<pd.Timedelta(days=240)
         cut=int(len(df)*(.6 if short else .6));testcut=int(len(df)*(.6 if short else .6));sg=signal_frame(df,cfg)
         for part,lo,hi in [('full',0,len(df)),('train',0,cut),('test',testcut,len(df))]:
          m=simulate(df.iloc[lo:hi],sg.iloc[lo:hi],mg,side)
          rows.append(dict(source_cohort=src,target_cohort=dst,timeframe=tf,variant=variant,symbol=sym,short_history_whole=short,split=part,trades=m['trades'],total_return=m['total_return'],pf=m['pf'],mdd=m['max_dd']))
        _log(f'cross {src}->{dst} {tf} {variant} complete')
        if time.monotonic()-started>max_minutes*60:raise TimeoutError('cross stage max-minutes exceeded')
    pd.DataFrame(rows).to_csv(OUT/'cross_summary.csv',index=False)

def partb_stage(max_minutes=35):
    # The full v2 Part B funnel is deliberately budget-gated before any search.
    from partb import signal_configs, management_grid
    rem=max_minutes*60-(time.monotonic()-_RUN_START)
    estimate=12*len(list(signal_configs()))*.01466*171163/2500/6
    if rem<600 or estimate>rem:
        (OUT/'partb_SKIPPED.txt').write_text(f'Part B skipped: remaining global budget {rem/60:.1f} min; required reserve is 10 min; projected signal construction {estimate/60:.1f} min. No Part B search was run.\n')
        _log('partb skipped: budget gate');return
    import partb, json
    rows=[]; started=time.monotonic()
    for cohort in ('L5','M'):
      for tf in ('1h','4h'):
        if time.monotonic()-started+600>max_minutes*60:
            (OUT/'partb_SKIPPED.txt').write_text(f'Part B remaining scopes skipped: global budget reserve fell below 10 minutes after {cohort}/{tf}.\n');return
        frames=_load(cohort,tf); splits={k:(int(len(d)*.6),len(d)) for k,d in frames.items()}
        scope=OUT/f'partb_{cohort}_{tf}';scope.mkdir(exist_ok=True)
        partb.run_stage(frames,scope,False,max_minutes=min(10,(max_minutes*60-(time.monotonic()-_RUN_START))/60),progress=_log)
        # Null bench the combined/long/short finalists with their observed test counts.
        winners=pd.read_csv(scope/'partb_winners.csv'); plateau=json.loads((scope/'partb_result.json').read_text())['plateau_verdict']; nullrows=[]
        for variant,side in [('winner','combined'),('long_only','long'),('short_only','short')]:
            g=winners[winners.variant==variant]
            if g.empty:continue
            first=g.iloc[0];cfg=json.loads(first.config);mg=json.loads(first.management);nullframes={};bounds={};counts={};testret=0.;trades=0
            for x in g.to_dict('records'):
                key=(x['symbol'],tf);df=frames[key];cut=int(len(df)*.6);sig=partb.signals(df,cfg['trigger'],cfg['filters'],cfg['trigger_param'],timeframe=tf,window=cfg['window'])
                nullframes[key]=df;bounds[key]=(cut,len(df));counts[key]=dict(trades=int(x['test_trades']),long=int(x.get('test_long',0)),short=int(x.get('test_short',0)),bb_mid=sig.bb_mid.to_numpy(),atr=sig.atr.to_numpy())
                testret+=float(x['test_total_return']);trades+=int(x['test_trades'])
            vals=nullbench.run_null(nullframes,bounds,mg,counts,seed=SEED,repetitions=200,workers=WORKERS,progress=lambda msg:_log(f'partb null {cohort}/{tf}/{variant} {msg}'),checkpoint=scope/f'null_reps_{variant}.jsonl')
            ns=nullbench.null_summary(vals);label,gates=null_verdict(testret,ns['null_p90'],plateau,trades)
            nullrows.append(dict(cohort=cohort,timeframe=tf,variant=variant,strategy_test_return=testret,test_trades=trades,null_reps=len(vals),null_percentile=nullbench.percentile_of(testret,vals),**ns,verdict=label,verdict_gates=gates))
        pd.DataFrame(nullrows).to_csv(scope/'partb_null_summary.csv',index=False)
        rows.append(dict(cohort=cohort,timeframe=tf,status='completed',variants=len(nullrows)))
    pd.DataFrame(rows).to_csv(OUT/'partb_stage_summary.csv',index=False)

def report_stage(max_minutes=35):
    winners=pd.read_csv(OUT/'tune_winners.csv'); null=pd.read_csv(OUT/'null_summary.csv') if (OUT/'null_summary.csv').exists() else pd.DataFrame()
    def md(d):
        if not len(d):return '(no rows)'
        cols=list(d.columns); rows_=['| '+' | '.join(map(str,cols))+' |','| '+' | '.join('---' for _ in cols)+' |']
        for _,r in d.iterrows():rows_.append('| '+' | '.join(str(r[c]).replace('|','\\|').replace('\n',' ') for c in cols)+' |')
        return '\n'.join(rows_)
    joined=winners.merge(null[['cohort','timeframe','variant','null_percentile','verdict','status']],on=['cohort','timeframe','variant'],how='left') if len(null) else winners.assign(null_percentile=np.nan,verdict='pending null',status='PENDING')
    source_ineligible=joined.eligibility_note.fillna('').str.startswith('INELIGIBLE')
    no_test=joined.status.fillna('').eq('INELIGIBLE')
    joined.loc[source_ineligible,'verdict']='INELIGIBLE'
    joined.loc[no_test & ~source_ineligible,'verdict']='INELIGIBLE (zero test trades)'
    chunks=['# V3 research results','', '## Headline by cohort, timeframe, variant','',md(joined[['cohort','timeframe','variant','train_return','test_return','test_trades','null_percentile','verdict']]),'','## Per-symbol test results','',md(pd.read_csv(OUT/'tune_per_symbol.csv')[['cohort','timeframe','variant','symbol','test_trades','test_return']]),'','## Frozen cross-cohort evaluation','',md(pd.read_csv(OUT/'cross_summary.csv') if (OUT/'cross_summary.csv').exists() else pd.DataFrame()),'','## Walk-forward summaries','',md(pd.read_csv(OUT/'wf_summary.csv') if (OUT/'wf_summary.csv').exists() else pd.DataFrame()),'','## Plateau verdicts','',md(pd.concat([pd.read_csv(p) for p in sorted(OUT.glob('plateau_*.csv'))],ignore_index=True)),'','## Data first dates and gaps','',md(pd.concat([pd.read_csv(p) for p in sorted(OUT.glob('first_dates_m_*.csv'))],ignore_index=True)),'',md(pd.concat([pd.read_csv(p) for p in sorted(OUT.glob('data_report_m_*.csv'))]+[pd.read_csv(ROOT/'results_v2/data_report.csv')],ignore_index=True)),'','## Stage timings','',md(pd.read_csv(OUT/'stage_timings.csv',keep_default_na=False)),'','## Deviations','', '- WF requires >=15 pooled train trades per window; M series under eight months skipped.', '- WF candidate reduction: '+((OUT/'wf_deviation.txt').read_text().strip() if (OUT/'wf_deviation.txt').exists() else 'none.'), '- Earlier identical unconstrained/with_stop selection is labelled by actual stop constraint: with_stop only selects explicit stop-enabled management; unconstrained may also select a stop-enabled configuration.', '- Mechanical verdict is COUNTS only when test return > null p90, plateau is not FRAGILE, and test trades >=30; all other measured outcomes are labelled no edge.', '- '+((OUT/'partb_SKIPPED.txt').read_text().strip() if (OUT/'partb_SKIPPED.txt').exists() else 'Part B stage status is recorded in its output files.'),'','## Reproduction','', '`.venv/bin/python run_v3.py --stage all --max-minutes 35`','`.venv/bin/python -m pytest -q`','']
    chunks += ['', '## Part B results by scope', '']
    for p in sorted(OUT.glob('partb_*/partb_null_summary.csv')):
        result=json.loads((p.parent/'partb_result.json').read_text())
        wf_note='Part B walk-forward produced no windows.' if not result.get('wf_summary') else md(pd.read_csv(p.parent/'partb_wf_summary.csv'))
        chunks += [f'### {p.parent.name}', '', md(pd.read_csv(p)), '', 'Plateau:', md(pd.read_csv(p.parent/'partb_plateau.csv')), '', 'Part B WF:', wf_note, '']
    if (OUT/'wf_deviation.txt').exists():chunks += ['## WF runtime reduction', '', (OUT/'wf_deviation.txt').read_text().strip(), '']
    (OUT/'REPORT.md').write_text('\n'.join(chunks))

def quick_run(max_minutes=2):
    _tune_scope('QUICK','1h',_load('L2','1h',True),True,max_minutes)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['tune','wf','null','cross','partb','report','all'],default='all');ap.add_argument('--quick',action='store_true');ap.add_argument('--force',action='store_true');ap.add_argument('--max-minutes',type=float,default=10);a=ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.quick: quick_run(a.max_minutes);return
    global _RUN_START
    _RUN_START=time.monotonic()
    stages=['wf','null','cross','partb','report'] if a.stage=='all' else [a.stage]
    for stage in stages:
        marker=OUT/f'.{stage}.done'
        if marker.exists() and not a.force: _log(f'{stage} resumed from done marker');continue
        t=time.monotonic();_log(f'{stage} started budget={a.max_minutes}m')
        if stage=='wf': wf(False,max(0.1,a.max_minutes-(time.monotonic()-_RUN_START)/60))
        elif stage=='null': null_stage(max(0.1,a.max_minutes-(time.monotonic()-_RUN_START)/60))
        elif stage=='cross': cross_stage(max(0.1,a.max_minutes-(time.monotonic()-_RUN_START)/60))
        elif stage=='partb': partb_stage(a.max_minutes)
        elif stage=='report': report_stage(a.max_minutes)
        elapsed=time.monotonic()-t
        _log(f'{stage} finished elapsed={elapsed:.1f}s')
        timing=pd.read_csv(OUT/'stage_timings.csv') if (OUT/'stage_timings.csv').exists() else pd.DataFrame(columns=['cohort','timeframe','seconds'])
        timing=pd.concat([timing,pd.DataFrame([dict(cohort='STAGE',timeframe=stage,seconds=elapsed)])],ignore_index=True)
        timing.to_csv(OUT/'stage_timings.csv',index=False)
        marker.write_text(str(time.time()))
if __name__=='__main__': main()
