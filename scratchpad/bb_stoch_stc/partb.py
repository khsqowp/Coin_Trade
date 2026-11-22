"""Causal Part B triggers, filters, deterministic search, plateau and walk-forward."""
import itertools
import numpy as np
import pandas as pd
from indicators import bollinger, stochastic, stc, atr

TRIGGERS=('T1','T2','T3','T4')
FILTERS=('F_bb','F_stoch','F_stc','F_vol','F_regime')

def filter_subsets(): return [tuple(x for x,on in zip(FILTERS,b) if on) for b in itertools.product((0,1),repeat=len(FILTERS))]
def management_grid():
    out=[]
    for stop,tp,hold,adds,spacing in itertools.product((('pct',3),('pct',5),('pct',8),('atr',2),('atr',3),('atr',4)),(2,4,6),(24,48,96),(0,2),(0,2,4)):
        out.append(dict(sl_pct=stop[1] if stop[0]=='pct' else None,atr_mult=stop[1] if stop[0]=='atr' else None,tp_pct=tp,max_hold_bars=hold,n_adds=adds,add_spacing_pct=spacing,add_size_mult=1.5))
    return out

def _recent(x,n): return pd.Series(np.asarray(x,bool).astype('uint8')).rolling(n,min_periods=1).max().to_numpy().astype(bool)
def _cross_up(x,level): return np.r_[False,(x[1:]>level)&(x[:-1]<=level)]
def _cross_dn(x,level): return np.r_[False,(x[1:]<level)&(x[:-1]>=level)]

def condition_bank(df, higher=None, timeframe=None, window=8, trigger_param=None):
    c=df.close.to_numpy(float);h=df.high.to_numpy(float);l=df.low.to_numpy(float);n=len(c)
    mid,up,dn=bollinger(c,20,2);k,d=stochastic(h,l,c);t=stc(c);width=up-dn
    breach_l=c<dn;breach_s=c>up
    p=trigger_param or {};nbreach=int(p.get('N',5));level=int(p.get('level',20))
    t1l=(c>=dn)&_recent(breach_l,nbreach);t1s=(c<=up)&_recent(breach_s,nbreach)
    crossup=np.r_[False,(k[1:]>d[1:])&(k[:-1]<=d[:-1])];crossdn=np.r_[False,(k[1:]<d[1:])&(k[:-1]>=d[:-1])]
    sto_l=crossup&(k<level)&(d<level);sto_s=crossdn&(k>100-level)&(d>100-level)
    td=np.diff(t,prepend=np.nan);stclevel=level
    stc_l=(td>0)&np.r_[False,td[:-1]<=0]&(t<stclevel);stc_s=(td<0)&np.r_[False,td[:-1]>=0]&(t>100-stclevel)
    delta=np.diff(c,prepend=np.nan);gain=np.where(delta>0,delta,0.);loss=np.where(delta<0,-delta,0.)
    def wilder(x,period):
        out=np.full(len(x),np.nan)
        if len(x)>period: out[period]=np.nanmean(x[1:period+1])
        for j in range(period+1,len(x)):out[j]=(out[j-1]*(period-1)+x[j])/period
        return out
    ag=wilder(gain,14);al=wilder(loss,14);rs=np.divide(ag,al,out=np.full(n,np.nan),where=al!=0);rsi=100-100/(1+rs);rsi[(al==0)&(ag>0)]=100.
    t4l=_cross_up(rsi,30);t4s=_cross_dn(rsi,70)
    fbb_l=_recent(breach_l,window);fbb_s=_recent(breach_s,window)
    fsto_l=_recent(sto_l,window);fsto_s=_recent(sto_s,window)
    fstc_l=_recent(stc_l,window);fstc_s=_recent(stc_s,window)
    vol=df.volume.to_numpy(float) if 'volume' in df else np.full(n,np.nan)
    avg=pd.Series(vol).rolling(20,min_periods=20).mean().to_numpy();fvol=vol>2*avg
    rank=pd.Series(width).rolling(500,min_periods=100).apply(lambda x:100*np.mean(x<=x[-1]),raw=True).to_numpy();freg=(rank>=20)&(rank<=80)
    return {'T1':(t1l,t1s),'T2':(sto_l,sto_s),'T3':(stc_l,stc_s),'T4':(t4l,t4s),'F_bb':(fbb_l,fbb_s),'F_stoch':(fsto_l,fsto_s),'F_stc':(fstc_l,fstc_s),'F_vol':(fvol,fvol),'F_regime':(freg,freg),'mid':mid,'atr':atr(h,l,c)}

def combine_bank(bank,trigger,enabled_filters,index):
    long,short=(np.asarray(x,bool).copy() for x in bank[trigger])
    for f in enabled_filters: long &= bank[f][0];short &= bank[f][1]
    return pd.DataFrame({'long':long,'short':short,'bb_mid':bank['mid'],'atr':bank['atr']},index=index)
def signals(df,trigger,enabled_filters=(),trigger_param=None,higher=None,timeframe=None,window=8,cache=None):
    key=('condition',id(df),tuple(sorted((trigger_param or {}).items())),window)
    if cache is not None and key not in cache:cache[key]=condition_bank(df,window=window,trigger_param=trigger_param)
    b=cache[key] if cache is not None else condition_bank(df,window=window,trigger_param=trigger_param)
    return combine_bank(b,trigger,enabled_filters,df.index)

def signal_configs():
    params={'T1':[{'N':3},{'N':5}],'T2':[{'level':20},{'level':25},{'level':30}],'T3':[{'level':10},{'level':25},{'level':40}],'T4':[{'rsi':14}]}
    for t in TRIGGERS:
      for p in params[t]:
       for fs in filter_subsets():
        for w in ((3,8) if fs else (8,)):
         yield {'trigger':t,'trigger_param':p,'filters':fs,'window':w}
def robust_score(m):
    pf=m['pf'] if np.isfinite(m['pf']) else 5
    return float(m['total_return']-abs(m['max_dd'])+min(pf,5)*.25)

# Fork workers inherit the immutable series/bank cache built by the coordinator.
_WORK=None

def _init_worker(ctx):
    global _WORK
    _WORK=ctx

def _score_task(task):
    cfg,mgmt,side=task;frames,banks,splits=_WORK
    from strategy import simulate
    vals={s:[] for s in ('combined','long','short')}; totals={s:{'trades':0,'ret':0.,'scores':[]} for s in vals}
    sid=json_key(cfg)
    for key,df in frames.items():
        split=splits.get(key,(int(len(df)*.6),len(df)))
        a,b=split;bank=banks[(key,tuple(sorted(cfg['trigger_param'].items())),cfg['window'])]
        sig=combine_bank(bank,cfg['trigger'],cfg['filters'],df.index)
        for sd in (side,) if side!='all' else ('combined','long','short'):
            try:m=simulate(df.iloc[a:b],sig.iloc[a:b],mgmt,sd)
            except Exception as exc:raise RuntimeError(f'Part B failed config={cfg} management={mgmt} side={sd} series={key}: {type(exc).__name__}: {exc}') from exc
            q=totals[sd]
            q['trades']+=m['trades'];q['ret']+=m['total_return'];q['scores'].append(robust_score(m));vals[sd].append((key,m))
    return sid,mgmt,side,{sd:{'trades':v['trades'],'ret':v['ret'],'score':float(np.mean(v['scores'])) if v['scores'] else 0.,'per':vals[sd]} for sd,v in totals.items() if v['scores']}

def json_key(cfg): return str((cfg['trigger'],tuple(sorted(cfg['trigger_param'].items())),tuple(cfg['filters']),cfg['window']))
def _run_tasks(tasks,frames,banks,splits,workers,progress=None,label='search'):
    from multiprocessing import Pool, get_context
    ctx=(frames,banks,splits);out=[];total=len(tasks)
    if not total:return out
    start=__import__('time').monotonic()
    with get_context('fork').Pool(workers,initializer=_init_worker,initargs=(ctx,)) as pool:
        for i,row in enumerate(pool.imap(_score_task,tasks,chunksize=max(1,total//(workers*24))),1):
            out.append(row)
            if progress and (i==1 or i%max(1,total//100)==0 or i==total):
                elapsed=__import__('time').monotonic()-start;eta=elapsed/i*(total-i)
                progress(f'{label} {i}/{total} elapsed={elapsed:.1f}s ETA={eta:.1f}s')
    return out

def _rank(rows,side,min_trades):
    eligible=[(r[3][side]['score'],r[3][side]['trades'],r[0],r) for r in rows if side in r[3] and r[3][side]['trades']>=min_trades]
    return sorted(eligible,key=lambda x:(-x[0],-x[1],x[2]))

def _neighbor_configs(cfg):
    out=[]
    for f in FILTERS:
        fs=tuple(x for x in cfg['filters'] if x!=f) if f in cfg['filters'] else tuple(sorted((*cfg['filters'],f)))
        out.append({**cfg,'filters':fs})
    if cfg['trigger']=='T1': vals=[{'N':3},{'N':5}]
    elif cfg['trigger']=='T2': vals=[{'level':20},{'level':25},{'level':30}]
    elif cfg['trigger']=='T3': vals=[{'level':10},{'level':25},{'level':40}]
    else: vals=[{'rsi':14}]
    ix=vals.index(cfg['trigger_param'])
    for j in (ix-1,ix+1):
        if 0<=j<len(vals):out.append({**cfg,'trigger_param':vals[j]})
    if cfg['filters']:
        w=[3,8];j=w.index(cfg['window']);out.append({**cfg,'window':w[1-j]})
    return out

def _windows(df):
    origin=df.index[0];last=df.index[-1];out=[];month=0
    while True:
        tr_end=origin+pd.DateOffset(months=month+12);te_end=tr_end+pd.DateOffset(months=3)
        if te_end>last+pd.Timedelta(hours=4):break
        tr=np.flatnonzero((df.index>=origin+pd.DateOffset(months=month))&(df.index<tr_end));te=np.flatnonzero((df.index>=tr_end)&(df.index<te_end))
        if len(tr) and len(te):out.append((slice(tr[0],tr[-1]+1),slice(te[0],te[-1]+1),month))
        month+=3
    return out

def run_stage(frames,out,quick=False,max_minutes=25,progress=print):
    import json,time
    from pathlib import Path
    from multiprocessing import get_context
    from strategy import simulate
    out=Path(out);start=time.monotonic();workers=1 if quick else 6
    configs=list(signal_configs());management=management_grid();cheap=dict(sl_pct=5.,atr_mult=None,tp_pct=4,max_hold_bars=48,n_adds=0,add_spacing_pct=2,add_size_mult=1.5)
    min_trades=0 if quick else 30
    if quick:
        configs=configs[::max(1,len(configs)//12)][:12];management=[management[i] for i in sorted(set(np.linspace(0,len(management)-1,3,dtype=int)))]
    banks={};splits={k:(0,int(len(df)*.6)) for k,df in frames.items()}
    # Cache all unique indicator banks once; fork workers inherit them read-only.
    params={tuple(sorted(c['trigger_param'].items())):c['trigger_param'] for c in configs}
    windows=sorted(set(c['window'] for c in configs))
    for key,df in frames.items():
        for pkey,p in params.items():
            for w in windows:banks[(key,pkey,w)]=condition_bank(df,window=w,trigger_param=p)
    progress(f'B inventory signals={len(configs)} phase2_management={len(management)} series={len(frames)} phase1_tasks={len(configs)} phase2_tasks={len(configs[:25])*len(management)} workers={workers}')
    phase1=_run_tasks([(c,cheap,'combined') for c in configs],frames,banks,splits,workers,progress,'B phase1')
    ranks=_rank(phase1,'combined',min_trades);top=[]
    seen=set()
    for score,trades,cid,row in ranks:
        cfg=next(c for c in configs if json_key(c)==cid)
        if cid not in seen:top.append((cfg,score,trades));seen.add(cid)
        if len(top)==25:break
    pd.DataFrame([dict(rank=i+1,config_id=json_key(c),config=json.dumps(c,sort_keys=True),train_score=s,train_trades=t) for i,(c,s,t) in enumerate(top)]).to_csv(out/'partb_phase1.csv',index=False)
    if not top:raise RuntimeError('Part B phase 1 found no signal configuration with at least 30 pooled train trades')
    cand=[x[0] for x in top];tasks=[(c,m,'all') for c in cand for m in management]
    phase2=_run_tasks(tasks,frames,banks,splits,workers,progress,'B phase2')
    by_side={}
    for side in ('combined','long','short'):
        ranked=_rank(phase2,side,min_trades);by_side[side]=ranked[0] if ranked else None
    variants={'winner':'combined','long_only':'long','short_only':'short'};headline={};detail=[];winner_cfg=None;winner_mgmt=None
    # Map exact config/management from deterministic phase2 row.
    lookup={(r[0],json.dumps(r[1],sort_keys=True)):r for r in phase2}
    for label,sd in variants.items():
        best=by_side[sd]
        if best is None:continue
        score,trades,cid,bestrow=best;cfg=next(c for c in cand if json_key(c)==cid);mgmt=bestrow[1]
        headline[label]={'config':cfg,'management':mgmt,'train_score':score,'train_trades':trades,'train_return':bestrow[3][sd]['ret']}
        if label=='winner':winner_cfg,winner_mgmt=cfg,mgmt
        r=lookup[(cid,json.dumps(mgmt,sort_keys=True))]
        test_return=0.;test_trades=0;test_long=0;test_short=0
        for key,tm in r[3][sd]['per']:
            df=frames[key];cut=splits[key][1];sig=combine_bank(banks[(key,tuple(sorted(cfg['trigger_param'].items())),cfg['window'])],cfg['trigger'],cfg['filters'],df.index)
            test=simulate(df.iloc[cut:],sig.iloc[cut:],mgmt,sd)
            test_return+=test['total_return'];test_trades+=test['trades'];test_long+=test['long'];test_short+=test['short']
            detail.append(dict(variant=label,symbol=key[0],timeframe=key[1],config=json.dumps(cfg,sort_keys=True),management=json.dumps(mgmt,sort_keys=True),train_trades=tm['trades'],train_return=tm['total_return'],train_score=score,**{'test_'+k:v for k,v in test.items()}))
        headline[label].update(test_return=test_return,test_trades=test_trades,test_long=test_long,test_short=test_short)
    pd.DataFrame(detail).to_csv(out/'partb_winners.csv',index=False)
    if winner_cfg is None:raise RuntimeError('Part B combined winner could not be selected')
    # Axial plateau: management axes plus each filter toggle, trigger param, shared window.
    winrow=by_side['combined'];winner_score=winrow[0];winner_id=winrow[2];wr=winrow[3];winner_mgmt=wr[1]
    ns=_neighbor_configs(winner_cfg);neighbors=[(c,winner_mgmt,'combined') for c in ns]
    # One-step management neighbors are the nearest valid grid point on every axis.
    axes={'stop':('sl_pct','atr_mult'),'tp_pct':('tp_pct',),'max_hold_bars':('max_hold_bars',),'n_adds':('n_adds',),'add_spacing_pct':('add_spacing_pct',)}
    for axis,fields in axes.items():
        vals=list(dict.fromkeys(tuple(m[f] for f in fields) for m in management));base=tuple(winner_mgmt[f] for f in fields);i=vals.index(base)
        for j in (i-1,i+1):
            if 0<=j<len(vals):
                q=dict(winner_mgmt);q.update(dict(zip(fields,vals[j])));neighbors.append((winner_cfg,q,'combined'))
    nrows=_run_tasks(neighbors,frames,banks,splits,workers,progress,'B plateau')
    nr=[]
    for c,m,side in neighbors:
        key=(json_key(c),json.dumps(m,sort_keys=True));r=next((x for x in nrows if x[0]==key[0] and json.dumps(x[1],sort_keys=True)==key[1]),None)
        if r and 'combined' in r[3]:nr.append(dict(axis='signal' if c!=winner_cfg else 'management',config=json.dumps(c,sort_keys=True),management=json.dumps(m,sort_keys=True),score=r[3]['combined']['score'],ratio=r[3]['combined']['score']/winner_score if winner_score else np.nan))
    pct=100*sum(x['score']>=.5*winner_score for x in nr)/len(nr) if nr else 0.;verdict='ROBUST' if pct>=70 else 'FRAGILE'
    for x in nr:x.update(robust_neighbor_pct=pct,verdict=verdict)
    pd.DataFrame(nr).to_csv(out/'partb_plateau.csv',index=False)
    # Walk-forward re-ranks the complete signal grid inside each 12m train window.
    wf_rows=[];wf_mgmt=[management[i] for i in np.linspace(0,len(management)-1,12,dtype=int)] if len(management)>12 else management
    series_windows={k:_windows(df) for k,df in frames.items()};nwin=min((len(v) for v in series_windows.values()),default=0)
    for wi in range(nwin):
        wframes={k:df for k,df in frames.items()};wsplits={k:(series_windows[k][wi][0].start,series_windows[k][wi][0].stop) for k in frames}
        # Recompute train-only rank over all configurations; cache is already precomputed causally.
        p1=_run_tasks([(c,cheap,'combined') for c in configs],wframes,banks,wsplits,workers,progress,f'B wf{wi+1} rank')
        r5=_rank(p1,'combined',30)[:5];wf_cfg=[next(c for c in configs if json_key(c)==x[2]) for x in r5]
        if not wf_cfg:continue
        final=_run_tasks([(c,m,'all') for c in wf_cfg for m in wf_mgmt],wframes,banks,wsplits,workers,progress,f'B wf{wi+1} final')
        for side in ('combined','long','short'):
            rr=_rank(final,side,30)
            if not rr:continue
            score,tr,cid,row=rr[0];cfg=next(c for c in wf_cfg if json_key(c)==cid);mg=row[1]
            result=next(x for x in final if x[0]==cid and x[1]==mg);wi_map={k:v for k,v in series_windows.items()}
            for key,tm in result[3][side]['per']:
                ts,vs,month=series_windows[key][wi];df=frames[key];bank=banks[(key,tuple(sorted(cfg['trigger_param'].items())),cfg['window'])];sig=combine_bank(bank,cfg['trigger'],cfg['filters'],df.index)
                test=simulate(df.iloc[vs],sig.iloc[vs],mg,side)
                wf_rows.append(dict(window=wi,month=month,side=side,symbol=key[0],timeframe=key[1],config=json.dumps(cfg,sort_keys=True),management=json.dumps(mg,sort_keys=True),train_score=score,train_trades=tm['trades'],**{'test_'+k:v for k,v in test.items()}))
        if time.monotonic()-start>max_minutes*60:raise TimeoutError(f'B exceeded --max-minutes={max_minutes}; completed WF window {wi+1}/{nwin}')
    wf=pd.DataFrame(wf_rows);wf.to_csv(out/'partb_wf.csv',index=False)
    summary=[]
    for side,g in wf.groupby('side') if len(wf) else []:summary.append(dict(side=side,windows=g.window.nunique(),test_trades=int(g.test_trades.sum()),test_return=float(g.test_total_return.sum()),positive_series_pct=float((g.test_total_return>0).mean()*100)))
    pd.DataFrame(summary).to_csv(out/'partb_wf_summary.csv',index=False)
    # Per-symbol latest winner and null benchmark handoff.
    latest=[];null_entries={};test_cut={}
    for key,df in frames.items():
        sig=combine_bank(banks[(key,tuple(sorted(winner_cfg['trigger_param'].items())),winner_cfg['window'])],winner_cfg['trigger'],winner_cfg['filters'],df.index);cut=splits[key][1]
        m=simulate(df.iloc[cut:],sig.iloc[cut:],winner_mgmt,'combined');latest.append(dict(symbol=key[0],timeframe=key[1],test_trades=m['trades'],test_return=m['total_return'],long=m['long'],short=m['short'],config=json.dumps(winner_cfg,sort_keys=True),management=json.dumps(winner_mgmt,sort_keys=True)))
        null_entries[f'{key[0]}_{key[1]}']=dict(test_entries=m['trades'],long=m['long'],short=m['short'],start=cut,stop=len(df))
    pd.DataFrame(latest).to_csv(out/'partb_latest_winner.csv',index=False)
    (out/'partb_null_handoff.json').write_text(json.dumps(dict(test_split_counts=null_entries,direction_mix={k:{'long':v['long'],'short':v['short']} for k,v in null_entries.items()},management=winner_mgmt,config=winner_cfg),indent=2,sort_keys=True))
    (out/'partb_result.json').write_text(json.dumps(dict(winner=headline.get('winner'),long_only=headline.get('long_only'),short_only=headline.get('short_only'),plateau_verdict=verdict,plateau_neighbor_pct=pct,wf_summary=summary,elapsed_seconds=time.monotonic()-start),indent=2,sort_keys=True))
    progress(f'B complete elapsed={time.monotonic()-start:.1f}s phase1={len(configs)} phase2={len(cand)*len(management)} plateau_neighbors={len(neighbors)} wf_windows={nwin}')
