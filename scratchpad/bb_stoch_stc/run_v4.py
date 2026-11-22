"""Real-data v4 evaluation for strict BB AND stochastic AND STC signals."""
from __future__ import annotations
import argparse, itertools, json, time, hashlib, traceback
from pathlib import Path
import numpy as np
import pandas as pd
from multiprocessing import get_context
import run_v3 as v3
import nullbench
from strategy import signal_frame, simulate
from data import check_data, MS

ROOT=Path(__file__).resolve().parent; OUT=ROOT/'results_v4'
COHORTS={'L2':['BTCUSDT','ETHUSDT'],'L5':['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT']}
TFS=('1d','12h','8h'); VARIANTS=('combined','long_only','short_only','unconstrained','with_stop')
SEED=20261120; WORKERS=6
_EVAL_FRAMES={}; _EVAL_SIGNALS={}
def _eval_init(frames,signals):
    global _EVAL_FRAMES,_EVAL_SIGNALS
    _EVAL_FRAMES=frames;_EVAL_SIGNALS=signals
def _eval_job(task):
    k,ci,mg,side,lo,hi=task;df=_EVAL_FRAMES[k];sf=_EVAL_SIGNALS[(k,ci)]
    return k,ci,mg,side,simulate(df.iloc[lo:hi],sf.iloc[lo:hi],mg,side,include_trade_details=True)
# Ten signal knobs are recorded. v3 signal_frame defines all ten; the 64-point
# design varies its five timing/threshold axes while holding remaining knobs canonical.
AXES={'bb_window':(0,2,4,8),'stoch_cross_lag':(0,2,4,8),'stoch_level':(15,20,25,30),
      'stc_lag':(0,2,4,8),'stc_level':(10,25,40,50)}
BASE=dict(bb_depth_pct=0,bb_use='close',bb_n=20,bb_k=2.,stoch_k=14,stoch_smooth=3,stoch_d=3,
          stoch_min_cross_age=0,stc_turn_type=1,stc_min_slope=0.,stc_lookback=5,stc_fast=23,stc_slow=50,stc_cycle=10)
def log(msg):
    OUT.mkdir(exist_ok=True); line=f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with (OUT/'progress.log').open('a') as f:f.write(line+'\n');f.flush()
    print(line,flush=True)
def signal_grid():
    allcfg=[]
    for j in np.linspace(0,1023,64,dtype=int):
        vals=np.unravel_index(j,(4,4,4,4,4)); p={**BASE,**{k:AXES[k][v] for k,v in zip(AXES,vals)}}; allcfg.append(p)
    return allcfg
def management_grid():
    # Deterministic 36-setting orthogonal sample over requested wide axes.
    out=[]
    stops=[(None,2.),(None,3.),(None,4.),(None,6.),(3.,None),(5.,None),(8.,None),(12.,None)]
    for i,(tp,stop,hold,adds,spacing) in enumerate(itertools.product((2,4,6,10,15),stops,(None,20,40,60),(0,1,2),(2,4,6))):
        if adds==0 and spacing!=2:continue
        if adds and stop[0] is not None and stop[0]<=adds*spacing:continue
        out.append(dict(add_size_mult=1.,bb_mid_exit=False,opp_exit=False,n_adds=adds,add_spacing_pct=spacing,
          tp_pct=tp,sl_pct=stop[0],atr_mult=stop[1],stop_mode=(f'pct{int(stop[0])}' if stop[0] else f'atr{stop[1]:g}'),max_hold_bars=hold))
    # The canonical order is stable; select 36 evenly spaced unique designs.
    return [out[i] for i in np.linspace(0,len(out)-1,36,dtype=int)]
def load(cohort,tf):
    return {(s,tf):pd.read_parquet(ROOT/'data'/f'{s}_{tf}.parquet') for s in COHORTS[cohort]}
def pooled(ms):
    trs=[t for m in ms for t in m.get('trade_details',[])]
    ret=sum(m['total_return'] for m in ms); dd=sum(m['max_dd'] for m in ms)
    gain=sum(t['return'] for t in trs if t['return']>0); loss=-sum(t['return'] for t in trs if t['return']<0)
    return dict(trades=len(trs),total_return=ret,pf=gain/loss if loss else (float('inf') if gain else 0),max_dd=dd,details=trs)
def event_count(sf,lo,hi,side='combined'):
    return int(sf.iloc[lo:hi].long.sum()+sf.iloc[lo:hi].short.sum()) if side=='combined' else int(sf.iloc[lo:hi][side].sum())
def summarize_frames(frames,signals,mgmt,side,lohi):
    ms=[]
    for k,df in frames.items():
        lo,hi=lohi[k]; ms.append(simulate(df.iloc[lo:hi],signals[k].iloc[lo:hi],mgmt,side,include_trade_details=True))
    return pooled(ms),ms
def null_run(frames,bounds,mgmt,counts,label):
    ck=OUT/f'null_reps_v4b_{label}.jsonl'
    vals=nullbench.run_null(frames,bounds,mgmt,counts,seed=SEED,repetitions=200,workers=WORKERS,progress=lambda m:log(f'{label} {m}'),checkpoint=ck)
    unique=len(np.unique(np.round(vals,10))); sd=float(np.std(vals))
    return vals, ('NULL_DEGENERATE' if unique<10 or sd<1e-10 else 'OK')
def e1():
    winner=pd.read_csv(ROOT/'results_v3/tune_winners.csv'); r=winner[(winner.cohort=='L5')&(winner.timeframe=='4h')&(winner.variant=='combined')].iloc[0]
    cfg=json.loads(r.signal); mg=json.loads(r.management)
    expected={'bb_depth_pct':0,'bb_use':'close','bb_window':4,'stc_lag':4,'stc_level':40,
      'stc_lookback':5,'stc_turn_type':1,'stoch_cross_lag':4,'stoch_level':30,'stoch_min_cross_age':0}
    if cfg!=expected:
        raise ValueError('frozen E1 signal mismatch')
    # Use exact v3 row management, including DCA size multiplier.
    rows=[]; pooled_rows=[]; sigrows=[]; nullrows=[]
    for cohort in ('L5','L2'):
      for tf in TFS:
        frames=load(cohort,tf); signals={k:signal_frame(df,cfg) for k,df in frames.items()}; cuts={k:int(len(df)*.6) for k,df in frames.items()}
        for k,df in frames.items():
          for part,lo,hi in [('full',0,len(df)),('train',0,cuts[k]),('test',cuts[k],len(df))]:
            n=event_count(signals[k],lo,hi); sigrows.append(dict(cohort=cohort,timeframe=tf,symbol=k[0],split=part,all3_events=n))
        per={}
        for k,df in frames.items():
          per[k]={}
          for part,lo,hi in [('full',0,len(df)),('train',0,cuts[k]),('test',cuts[k],len(df))]:
            m=simulate(df.iloc[lo:hi],signals[k].iloc[lo:hi],mg,'combined',include_trade_details=True)
            per[k][part]=m; rows.append(dict(cohort=cohort,timeframe=tf,symbol=k[0],split=part,**{x:m[x] for x in ('trades','total_return','pf','max_dd','long','short')}))
        for part in ('full','train','test'):
          items=[per[k][part] for k in frames]; pm=pooled(items); pooled_rows.append(dict(cohort=cohort,timeframe=tf,split=part,**{x:pm[x] for x in ('trades','total_return','pf','max_dd')}))
        if cohort in ('L5','L2'):
          bounds={k:(cuts[k],len(frames[k])) for k in frames}; counts={}
          for k in frames:
            details=per[k]['test']['trade_details'];counts[k]=dict(trades=len(details),long=sum(t['side']=='long' for t in details),short=sum(t['side']=='short' for t in details),bb_mid=signals[k].bb_mid.to_numpy(),atr=signals[k].atr.to_numpy())
          vals,status=null_run(frames,bounds,mg,counts,f'E1_{cohort}_{tf}')
          test=next(x for x in pooled_rows if x['cohort']==cohort and x['timeframe']==tf and x['split']=='test')
          nullrows.append(dict(cohort=cohort,timeframe=tf,status=status,null_p50=np.percentile(vals,50),null_p90=np.percentile(vals,90),null_percentile=nullbench.percentile_of(test['total_return'],vals),test_return=test['total_return'],reps=len(vals)))
    pd.DataFrame(rows).to_csv(OUT/'e1_per_symbol.csv',index=False);pd.DataFrame(pooled_rows).to_csv(OUT/'e1_pooled.csv',index=False)
    sc=pd.DataFrame(sigrows);sc.to_csv(OUT/'signal_counts.csv',index=False)
    sc.groupby(['cohort','timeframe','split'],as_index=False).all3_events.sum().to_csv(OUT/'signal_counts_pooled.csv',index=False)
    pd.DataFrame(nullrows).to_csv(OUT/'e1_null.csv',index=False)
    (OUT/'e1_frozen.json').write_text(json.dumps(dict(signal=cfg,management=mg,source='results_v3/tune_winners.csv L5/4h/combined'),indent=2))
def tune_scope(cohort,tf,frames):
    start=time.monotonic(); keys=list(frames); cuts={k:int(len(frames[k])*.6) for k in keys}; grid=signal_grid(); mgmts=management_grid()
    phase=[]; signal_cache={}; events=[]
    for ci,cfg in enumerate(grid):
      counts=[]; scores=[]
      for k,df in frames.items():
        sf=signal_frame(df,cfg);signal_cache[(k,ci)]=sf;cut=cuts[k];counts.append(event_count(sf,0,cut));
        if counts[-1]:
          ix=np.flatnonzero((sf.long|sf.short).to_numpy()[:cut]); ix=ix[ix+10<cut]; close=df.close.to_numpy(float);op=df.open.to_numpy(float)
          scores.extend([((close[i+10]/op[i+1]-1)*(1 if sf.long.iloc[i] else -1)) for i in ix])
      ev=sum(counts);events.append(dict(cohort=cohort,timeframe=tf,config_id=ci,pooled_train_events=ev)); phase.append((float(np.mean(scores)) if scores else -1e9,ev,ci,cfg))
    floor=v3.event_floor(len(keys)); eligible=[x for x in phase if x[1]>=floor]
    ranked=sorted(eligible,key=lambda x:(x[0],x[1],-x[2]),reverse=True);selected=[]
    for x in ranked:
      if all(sum(x[3][a]!=y[3][a] for a in AXES)>=2 for y in selected): selected.append(x)
      if len(selected)==12:break
    if not selected:
      return [],[],dict(cohort=cohort,timeframe=tf,status=f'INELIGIBLE: {max((x[1] for x in phase),default=0)} events',event_floor=floor,pooled_train_events=max((x[1] for x in phase),default=0)),events
    candidates=[]; tasks=[]
    for _,ev,ci,cfg in selected:
      for mg in mgmts:
       for side in ('combined','long','short'):
        for k in keys:tasks.append((k,ci,mg,side,0,cuts[k]))
    by_candidate={}
    with get_context('fork').Pool(WORKERS,initializer=_eval_init,initargs=(frames,signal_cache)) as pool:
      completed=0; started=time.monotonic()
      for k,ci,mg,side,m in pool.imap_unordered(_eval_job,tasks,chunksize=8):
       token=(ci,json.dumps(mg,sort_keys=True),side);by_candidate.setdefault(token,{})[k]=m;completed+=1
       if completed%max(1,len(tasks)//20)==0:
        elapsed=time.monotonic()-started;eta=elapsed/max(1,completed)*(len(tasks)-completed)
        log(f'tune {cohort}/{tf} simulations {completed}/{len(tasks)} elapsed={elapsed:.1f}s ETA={eta:.1f}s')
    for (ci,mgj,side),permap in by_candidate.items():
      cfg=next(x[3] for x in selected if x[2]==ci);mg=json.loads(mgj);ms=[permap[k] for k in keys];p=pooled(ms)
      if p['trades']>=30:candidates.append(dict(config_id=ci,signal=cfg,management=mg,side=side,train=p,per=ms,keys=keys))
    names={'combined':('combined','combined',False),'long_only':('long','long',False),'short_only':('short','short',False),'unconstrained':(None,None,False),'with_stop':('combined','combined',True)}
    winners={}
    for name,(side,_,stop) in names.items():
      avail=[x for x in candidates if (side is None or x['side']==side) and (not stop or v3.requires_stop(x['management']))]
      if avail:winners[name]=max(avail,key=lambda x:(x['train']['total_return']-abs(x['train']['max_dd'])+.25*min(x['train']['pf'],5),x['train']['trades']))
    rows=[];plates=[];null_handoff=[]
    headlines=[]
    for name,w in winners.items():
      cfg=w['signal'];mg=w['management'];side=w['side']; ci=w['config_id']; train=w['train'];test_ms=[];train_ms=w['per']; sigs={k:signal_cache[(k,ci)] for k in keys}
      for k,df in frames.items(): test_ms.append(simulate(df.iloc[cuts[k]:],sigs[k].iloc[cuts[k]:],mg,side,include_trade_details=True))
      test=pooled(test_ms);scores=[]
      # signal axial neighbors measured on train; selected set is the bounded management surface sample.
      for a,values in AXES.items():
       ix=values.index(cfg[a])
       for j in (ix-1,ix+1):
        if 0<=j<len(values):
         neighbor=dict(cfg);neighbor[a]=values[j]; ms=[simulate(df.iloc[:cuts[k]],signal_frame(df,neighbor).iloc[:cuts[k]],mg,side,include_trade_details=True) for k,df in frames.items()]; q=pooled(ms);scores.append(q['total_return']-abs(q['max_dd'])+.25*min(q['pf'],5))
      # Management neighbors from the evaluated candidates for this signal/side.
      related=[x for x in candidates if x['config_id']==ci and x['side']==side];scores.extend(x['train']['total_return']-abs(x['train']['max_dd'])+.25*min(x['train']['pf'],5) for x in related)
      base=train['total_return']-abs(train['max_dd'])+.25*min(train['pf'],5);pct=100*sum(s>=.5*base for s in scores)/len(scores) if scores else 0;plate='ROBUST' if pct>=70 else 'FRAGILE'
      for k,df,tr,te in zip(keys,frames.values(),train_ms,test_ms):
       rows.append(dict(cohort=cohort,timeframe=tf,variant=name,symbol=k[0],signal=json.dumps(cfg,sort_keys=True),management=json.dumps(mg,sort_keys=True),side=side,train_trades=tr['trades'],train_return=tr['total_return'],train_pf=tr['pf'],train_mdd=tr['max_dd'],test_trades=te['trades'],test_return=te['total_return'],test_pf=te['pf'],test_mdd=te['max_dd'],train_details=json.dumps(tr['trade_details']),test_details=json.dumps(te['trade_details'])))
      plates.append(dict(cohort=cohort,timeframe=tf,variant=name,neighbors=len(scores),robust_neighbor_pct=pct,verdict=plate))
      if test['trades']:
       counts={};bounds={}
       for k,df,te in zip(keys,frames.values(),test_ms):
        bounds[k]=(cuts[k],len(df));details=te['trade_details'];counts[k]=dict(trades=len(details),long=sum(t['side']=='long' for t in details),short=sum(t['side']=='short' for t in details),bb_mid=sigs[k].bb_mid.to_numpy(),atr=sigs[k].atr.to_numpy())
       null_handoff.append((name,test,mg,plate,bounds,counts,sigs))
    # Aggregate winners include pooled values once per scope.
    for name,w in winners.items():
      g=[r for r in rows if r['variant']==name];tr=sum(r['train_trades'] for r in g);te=sum(r['test_trades'] for r in g);trainret=sum(r['train_return'] for r in g);testret=sum(r['test_return'] for r in g)
      platesel=next(x['verdict'] for x in plates if x['variant']==name)
      headlines.append(dict(cohort=cohort,timeframe=tf,variant=name,train_trades=tr,train_return=trainret,test_trades=te,test_return=testret,plateau_verdict=platesel,status='ELIGIBLE',signal=json.dumps(w['signal'],sort_keys=True),management=json.dumps(w['management'],sort_keys=True),side=w['side']))
    log(f'tune {cohort}/{tf} configs={len(grid)} eligible={len(eligible)} selected={len(selected)} mgmt={len(mgmts)} sims={len(selected)*len(mgmts)*3*len(keys)} elapsed={time.monotonic()-start:.1f}s')
    return rows,plates,headlines,events,null_handoff

def run_tune(force=False):
    winners=[]; per=[]; plate=[]; events=[]
    for cohort in ('L2','L5'):
      for tf in TFS:
       marker=OUT/f'.tune_{cohort}_{tf}.done'
       if marker.exists() and not force:continue
       t=time.monotonic();frames=load(cohort,tf); rows,plates,heads,ev,_=tune_scope(cohort,tf,frames)
       per=[x for x in per if not (x.get('cohort')==cohort and x.get('timeframe')==tf)]+rows
       winners=[x for x in winners if not (x.get('cohort')==cohort and x.get('timeframe')==tf)]+heads
       plate=[x for x in plate if not (x.get('cohort')==cohort and x.get('timeframe')==tf)]+plates
       events=[x for x in events if not (x.get('cohort')==cohort and x.get('timeframe')==tf)]+ev
       pd.DataFrame(per).to_csv(OUT/'tune_per_symbol.csv',index=False);pd.DataFrame(winners).to_csv(OUT/'tune_winners.csv',index=False)
       pd.DataFrame(plate).to_csv(OUT/'plateau.csv',index=False);pd.DataFrame(events).to_csv(OUT/'phase1_events.csv',index=False)
       timings=pd.read_csv(OUT/'stage_timings.csv',keep_default_na=False).to_dict('records') if (OUT/'stage_timings.csv').exists() else []
       timings=[x for x in timings if not (x.get('cohort')==cohort and x.get('timeframe')==tf)];timings.append(dict(cohort=cohort,timeframe=tf,stage='tune',seconds=time.monotonic()-t));pd.DataFrame(timings).to_csv(OUT/'stage_timings.csv',index=False)
       marker.write_text(str(time.time()))

def walk_forward():
    # Cohort-pooled chronological rolling windows; bounded 6-signal x 6-management surface.
    rows=[]; started=time.monotonic()
    for cohort in ('L2','L5'):
      for tf in TFS:
       frames=load(cohort,tf); train_m,test_m=(36,12) if tf=='1d' else (24,6)
       # Align cohort start/end; monthly roll by test length.
       start=max(df.index[0] for df in frames.values()); end=min(df.index[-1] for df in frames.values()); month=0
       while start+pd.DateOffset(months=month+train_m+test_m)<=end:
        a=start+pd.DateOffset(months=month);b=a+pd.DateOffset(months=train_m);c=b+pd.DateOffset(months=test_m)
        train={k:d.loc[(d.index>=a)&(d.index<b)] for k,d in frames.items()};test={k:d.loc[(d.index>=b)&(d.index<c)] for k,d in frames.items()}
        train={k:d for k,d in train.items() if len(d)>20};test={k:d for k,d in test.items() if len(d)>2}
        if train and test:
         grid=signal_grid(); grid=[grid[i] for i in np.linspace(0,len(grid)-1,6,dtype=int)]; mg=management_grid();mg=[mg[i] for i in np.linspace(0,len(mg)-1,6,dtype=int)]
         cand=[]
         for cfg in grid:
          sigs={k:signal_frame(d,cfg) for k,d in train.items()}
          for side in ('combined','long','short'):
           for m in mg:
            ms=[simulate(d,sigs[k],m,side,include_trade_details=True) for k,d in train.items()];p=pooled(ms)
            if p['trades']>=30:cand.append((p['total_return']-abs(p['max_dd'])+.25*min(p['pf'],5),cfg,m,side,p['trades']))
         if cand:
          score,cfg,m,side,n=max(cand,key=lambda x:(x[0],x[4])); testms=[simulate(d,signal_frame(d,cfg),m,side) for d in test.values()]
          rows.append(dict(cohort=cohort,timeframe=tf,window=month,train_start=str(a),train_end=str(b),test_start=str(b),test_end=str(c),train_trades=n,train_score=score,side=side,config=json.dumps(cfg,sort_keys=True),management=json.dumps(m,sort_keys=True),test_trades=sum(x['trades'] for x in testms),test_return=sum(x['total_return'] for x in testms),test_mdd=sum(x['max_dd'] for x in testms)))
        month+=test_m
    pd.DataFrame(rows).to_csv(OUT/'wf.csv',index=False)
    if rows:
      d=pd.DataFrame(rows);g=d.groupby(['cohort','timeframe']);g.agg(windows=('window','count'),test_trades=('test_trades','sum'),test_return=('test_return','sum'),positive_windows_pct=('test_return',lambda x:100*(x>0).mean())).reset_index().to_csv(OUT/'wf_summary.csv',index=False)
    log(f'wf windows={len(rows)} elapsed={time.monotonic()-started:.1f}s')

def run_nulls(force=False):
    src=pd.read_csv(OUT/'tune_winners.csv'); detail=pd.read_csv(OUT/'tune_per_symbol.csv'); out=[]; started=time.monotonic()
    for w in src.to_dict('records'):
      token=(w['cohort'],w['timeframe'],w['variant']);path=OUT/f"null_v4b_{token[0]}_{token[1]}_{token[2]}.csv"
      if path.exists() and not force:out.extend(pd.read_csv(path).to_dict('records'));continue
      if not isinstance(w.get('signal'),str) or not w['signal'].startswith('{') or int(w.get('test_trades') or 0)<1:
       out.append(dict(cohort=token[0],timeframe=token[1],variant=token[2],status='INELIGIBLE',null_reps=0));continue
      rows=detail[(detail.cohort==token[0])&(detail.timeframe==token[1])&(detail.variant==token[2])];frames={};bounds={};counts={};cfg=json.loads(w['signal']); mg=json.loads(w['management'])
      for x in rows.to_dict('records'):
       key=(x['symbol'],token[1]);df=pd.read_parquet(ROOT/'data'/f'{key[0]}_{key[1]}.parquet');sf=signal_frame(df,cfg);cut=int(len(df)*.6);td=json.loads(x['test_details']);frames[key]=df;bounds[key]=(cut,len(df));counts[key]=dict(trades=len(td),long=sum(t['side']=='long' for t in td),short=sum(t['side']=='short' for t in td),bb_mid=sf.bb_mid.to_numpy(),atr=sf.atr.to_numpy())
       if w['variant']=='long_only' and counts[key]['short']:raise ValueError(f'one-sided null direction leak {token} {key}')
       if w['variant']=='short_only' and counts[key]['long']:raise ValueError(f'one-sided null direction leak {token} {key}')
      vals,status=null_run(frames,bounds,mg,counts,'_'.join(token)); ns=nullbench.null_summary(vals); pct=np.nan if status!='OK' else nullbench.percentile_of(float(w['test_return']),vals)
      verdict='INELIGIBLE' if status!='OK' else ('COUNTS' if float(w['test_return'])>ns['null_p90'] and w['plateau_verdict']!='FRAGILE' and int(w['test_trades'])>=30 else 'no edge')
      out.append(dict(cohort=token[0],timeframe=token[1],variant=token[2],status=status,null_reps=len(vals),null_percentile=pct,**ns,test_return=w['test_return'],test_trades=w['test_trades'],verdict=verdict))
      pd.DataFrame([out[-1]]).to_csv(path,index=False)
    pd.DataFrame(out).to_csv(OUT/'null_summary.csv',index=False);log(f'nulls variants={len(out)} elapsed={time.monotonic()-started:.1f}s')

def data_audit():
    first=[]; report=[]
    for s in COHORTS['L5']:
      for tf in TFS:
       df=pd.read_parquet(ROOT/'data'/f'{s}_{tf}.parquet');gaps=check_data(df,tf)
       first.append(dict(symbol=s,timeframe=tf,first_date=df.index[0].isoformat(),last_date=df.index[-1].isoformat(),bars=len(df)))
       report.append(dict(symbol=s,timeframe=tf,bars=len(df),gaps=len(gaps),gap_details=json.dumps([(str(a),str(b),n) for a,b,n in gaps])))
    pd.DataFrame(first).to_csv(OUT/'first_dates.csv',index=False);pd.DataFrame(report).to_csv(OUT/'data_report.csv',index=False)

def report():
    def table(df):
      if df is None or not len(df):return '(no rows)'
      return '| '+' | '.join(df.columns)+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(str(v).replace('|','/') for v in row)+' |' for row in df.itertuples(index=False,name=None))
    headline=pd.read_csv(OUT/'tune_winners.csv');null=pd.read_csv(OUT/'null_summary.csv') if (OUT/'null_summary.csv').exists() else pd.DataFrame()
    if len(null):headline=headline.merge(null[['cohort','timeframe','variant','null_percentile','status','verdict']],on=['cohort','timeframe','variant'],how='left')
    e1p=pd.read_csv(OUT/'e1_pooled.csv'); e1s=pd.read_csv(OUT/'e1_per_symbol.csv'); sig=pd.read_csv(OUT/'signal_counts.csv')
    chunks=['# V4 real-data research results','', '## Headline cohort x timeframe x variant','',table(headline[['cohort','timeframe','variant','train_trades','train_return','test_trades','test_return','null_percentile','plateau_verdict','verdict']] if len(headline) else headline),
      '', '## E1 frozen pooled full/train/test','',table(e1p), '', '## E1 frozen per-symbol full/train/test','',table(e1s), '', '## Pooled all-3 signal counts by symbol and split','',table(sig),
      '', '## Cohort-timeframe pooled all-3 events','',table(pd.read_csv(OUT/'signal_counts_pooled.csv')),
      '', '## E1 random-entry null','',table(pd.read_csv(OUT/'e1_null.csv')), '', '## Tuned walk-forward summary','',table(pd.read_csv(OUT/'wf_summary.csv') if (OUT/'wf_summary.csv').exists() else pd.DataFrame()),
      '', '## Plateau','',table(pd.read_csv(OUT/'plateau.csv')), '', '## Data starts and gaps','',table(pd.read_csv(OUT/'first_dates.csv')),table(pd.read_csv(OUT/'data_report.csv')),
      '', '## Stage timings','',table(pd.read_csv(OUT/'stage_timings.csv')), '', '## Search design and deviations','',
      '- Strict all-3 conjunction is the existing `strategy.signal_frame` BB AND stochastic AND STC logic.',
      '- Per-series chronological 60/40 cut; all candidate selection and plateau scoring use train slices only.',
      '- Signal phase 1 uses 64 deterministic points sampled evenly from the 4^5 five-axis design. The other five signal parameters remain at v3 canonical values. The requested 10-knob full search was reduced to fit runtime.',
      '- Management phase uses 36 deterministic evenly spaced settings from the requested wide Cartesian surface; full Cartesian management enumeration was not run.',
      '- Pool workers: 6 for tune finalist simulations and random-entry null; WF simulation is coordinator-serial.',
      '- Pooled return and PF sum pooled trade outcomes using the v3 aggregation convention. Pooled MDD is the sum of per-series mark-to-market MDDs, not a synchronized multi-asset portfolio equity curve.',
      '- The research process ran in supervised attached execution sessions; detached nohup children could not be retained by the shell environment.',
      '- Random-entry null is valid only when at least 10 unique returns and nonzero variance; otherwise status is NULL_DEGENERATE and percentile is withheld.',
      '- Mechanical verdict is COUNTS only when test return beats null p90, plateau is not FRAGILE, and test trades >=30.',
      '- Reproduce: `.venv/bin/python run_v4.py --stage all --max-minutes 45`; force: append `--force`.',
      '- E1 management and signal were loaded from `results_v3/tune_winners.csv`, L5/4h/combined.', '']
    (OUT/'REPORT.md').write_text('\n'.join(chunks))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['data','e1','tune','wf','null','report','all'],default='all');ap.add_argument('--force',action='store_true');ap.add_argument('--max-minutes',type=float,default=45);a=ap.parse_args()
    OUT.mkdir(exist_ok=True); started=time.monotonic(); stages=['data','e1','tune','wf','null','report'] if a.stage=='all' else [a.stage]
    for stage in stages:
      marker=OUT/f'.{stage}.done'
      if marker.exists() and not a.force:log(f'{stage} resumed from done marker');continue
      t=time.monotonic();log(f'{stage} started')
      try:
       if stage=='data':data_audit()
       elif stage=='e1':e1()
       elif stage=='tune':run_tune(a.force)
       elif stage=='wf':walk_forward()
       elif stage=='null':run_nulls(a.force)
       elif stage=='report':report()
      except Exception as exc:
       log(f'FAILED stage={stage} type={type(exc).__name__} error={exc}\n{traceback.format_exc()}');raise
      elapsed=time.monotonic()-t; rows=pd.read_csv(OUT/'stage_timings.csv',keep_default_na=False).to_dict('records') if (OUT/'stage_timings.csv').exists() else []
      timing_name='random_null' if stage=='null' else stage
      rows=[r for r in rows if not (r.get('stage')==timing_name and r.get('cohort')=='STAGE')];rows.append(dict(cohort='STAGE',timeframe=timing_name,stage=timing_name,seconds=elapsed));pd.DataFrame(rows).to_csv(OUT/'stage_timings.csv',index=False)
      marker.write_text(str(time.time()));log(f'{stage} finished elapsed={elapsed:.1f}s total={time.monotonic()-started:.1f}s ETA={max(0,a.max_minutes*60-(time.monotonic()-started)):.1f}s')
      if time.monotonic()-started>a.max_minutes*60:raise TimeoutError(f'total --max-minutes={a.max_minutes} exceeded')
if __name__=='__main__':main()
