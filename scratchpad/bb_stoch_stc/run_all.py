"""Deterministic, train-only strategy research pipeline."""
import argparse,itertools,json,os,time,hashlib,sys,signal
from multiprocessing import Pool,get_context
from pathlib import Path
import numpy as np,pandas as pd
from data import SYMBOLS,synthetic,check_data
from strategy import signal_frame,simulate,is_coherent
from report import generate
from indicators import bollinger,stochastic,stc,atr
ROOT=Path(__file__).resolve().parent
BB=[dict(bb_use=u,bb_depth_pct=d,bb_window=w) for u,d,w in itertools.product(('close','low'),(0,5,10,20),(0,2,4,8))]
STO=[dict(stoch_level=l,stoch_cross_lag=g,stoch_min_cross_age=a) for l,g,a in itertools.product((15,20,25,30),(0,2,4,8),(0,1,2,3)) if a<=g]
STC=[dict(stc_level=l,stc_turn_type=t,stc_lag=g,stc_lookback=b) for l,t,g,b in itertools.product((10,25,40),(1,2),(0,2,4,8),(5,10,20))]
SIGGRID=[{**b,**s,**t} for b,s,t in itertools.product(BB,STO,STC)]
TOP_K=12;MIN_EVENTS=150;MIN_TF_EVENTS=30
WORKERS=6
_MAX_SECONDS=40*60
_DEADLINE=None
def _log(out,message):
 line=f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
 with (out/'progress.log').open('a') as f:f.write(line+'\n');f.flush()
 print(line,flush=True)
def _grid_hash(quick=False):
 indices=np.linspace(0,len(SIGGRID)-1,48,dtype=int).tolist() if quick else list(range(len(SIGGRID)))
 return hashlib.sha256(json.dumps({'grid':SIGGRID,'indices':indices},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _stage_a_valid(out,quick=False):
 path=out/'stage_a.csv';meta=out/'stage_a.meta'
 if not path.exists():return False
 expected=_grid_hash(quick)
 if meta.exists():
  try:
   if json.loads(meta.read_text()).get('grid_hash')==expected:return True
  except (ValueError,OSError):return False
 # Certify the historical file by checking every configuration's stored knobs.
 cols=['signal_config',*SIGGRID[0].keys()]
 d=pd.read_csv(path,usecols=cols,dtype={'signal_config':'int32'})
 actual=d.drop_duplicates('signal_config').sort_values('signal_config')
 valid=len(actual)>0
 if valid:
  for r in actual.itertuples(index=False,name=None):
   ci=int(r[0]);valid &= 0<=ci<len(SIGGRID) and all(str(a)==str(b) for a,b in zip(r[1:],SIGGRID[ci].values()))
 if valid:meta.write_text(json.dumps({'grid_hash':expected,'verified_configs':len(actual),'verified_by':'stored signal knob verification'},indent=2)+'\n')
 return bool(valid)
def _ensure_stage_a(out,reuse=True,quick=False):
 if reuse and _stage_a_valid(out,quick):
  if not (out/'stage_a_eligibility.csv').exists():raise FileNotFoundError('Stage A eligibility cache missing; Stage A will not be rerun automatically.')
  return
 raise RuntimeError('Stage A cache is absent or grid-mismatched; run --stage A explicitly.')
def _run_tasks(tasks,func,frames,out,stage,quick=False):
 workers=2 if quick else WORKERS; total=len(tasks); done=0;start=time.perf_counter();next_report=max(1,int(total*.02))
 with get_context('fork').Pool(workers,initializer=_init,initargs=(frames,)) as proc:
  iterator=proc.imap_unordered(_execute_task,((func,task) for task in tasks),chunksize=1)
  for result in iterator:
   done+=1
   if done==1 or done%max(1,total//100)==0 or done==total:
    elapsed=time.perf_counter()-start;rate=elapsed/done;estimate=rate*total
    _log(out,f'{stage} progress {done}/{total} ({done/total:.1%}) elapsed={elapsed:.1f}s projected={estimate:.1f}s')
    remaining=max(0,_DEADLINE-time.monotonic()) if _DEADLINE else _MAX_SECONDS
    if done>=next_report and estimate>remaining:proc.terminate();raise TimeoutError(f'{stage} projected {estimate/60:.1f} min exceeds remaining --max-minutes budget {remaining/60:.1f}')
   yield result
def _execute_task(item):
 func,task=item
 try:return func(task)
 except Exception as exc:
  raise RuntimeError(f"Worker failed in {func.__name__}; task={task!r}") from exc
def _weighted_median(values,weights):
 order=np.argsort(np.asarray(values,float));v=np.asarray(values,float)[order];w=np.asarray(weights,float)[order]
 return float(v[np.searchsorted(np.cumsum(w),w.sum()/2,side='left')])
def getdata(quick=False):
 frames={};syms=['SYNTH_A','SYNTH_B'] if quick else SYMBOLS;tfs=['1h'] if quick else ['1h','4h']
 for s in syms:
  for tf in tfs:
   f=ROOT/'data'/f'{s}_{tf}.parquet'
   if not quick and not f.exists(): raise FileNotFoundError(f'Required real-data input missing: {f}')
   frames[(s,tf)]=synthetic(s,tf,2500) if quick else pd.read_parquet(f)
 return frames
def _condition_bank(df):
 c=df.close.to_numpy(float);h=df.high.to_numpy(float);l=df.low.to_numpy(float);mid,up,dn=bollinger(c,20,2);k,d=stochastic(h,l,c);t=stc(c);atrv=atr(h,l,c);width=up-dn
 def recent(x,n):return x.copy() if n==0 else pd.Series(x.astype(np.uint8)).rolling(n+1,min_periods=1).max().to_numpy()>0
 bb={};
 for q in BB:
  lp=c if q['bb_use']=='close' else l;sp=c if q['bb_use']=='close' else h;bb[tuple(q.values())]=((recent((lp<dn)&((dn-lp)>=width*q['bb_depth_pct']/100),q['bb_window']),recent((sp>up)&((sp-up)>=width*q['bb_depth_pct']/100),q['bb_window'])))
 sto={};upx=np.r_[False,(k[1:]>d[1:])&(k[:-1]<=d[:-1])];dnx=np.r_[False,(k[1:]<d[1:])&(k[:-1]>=d[:-1])]
 for q in STO:
  lag=q['stoch_cross_lag'];age=q['stoch_min_cross_age'];level=q['stoch_level'];su=upx&(k<level)&(d<level);sd=dnx&(k>100-level)&(d>100-level)
  roll=lambda x:pd.Series((np.r_[np.zeros(age,bool),x[:max(0,len(x)-age)]] if age else x).astype(np.uint8)).rolling(lag-age+1,min_periods=1).max().to_numpy()>0
  sto[tuple(q.values())]=(roll(su),roll(sd))
 stc_bank={}
 for q in STC:
  n=q['stc_turn_type'];delta=np.diff(t,prepend=np.nan);long_ok=delta>=0;short_ok=delta<=0
  turns=[]
  for ok,zone in ((long_ok,t<q['stc_level']),(short_ok,t>100-q['stc_level'])):
   x=pd.Series(ok.astype(np.uint8)).rolling(n,min_periods=n).min().to_numpy()>0;prior=pd.Series(zone.astype(np.uint8)).rolling(q['stc_lookback']+1,min_periods=1).max().to_numpy()>0;candidate=x&prior
   turns.append(pd.Series(candidate.astype(np.uint8)).rolling(q['stc_lag']+1,min_periods=1).max().to_numpy()>0)
  stc_bank[tuple(q.values())]=tuple(turns)
 return bb,sto,stc_bank,mid,atrv
def _stage_a_one(args):
 (s,tf),df,quick=args;cut=int(len(df)*.6);train=df.iloc[:cut];bb,sto,stcb,_,_=_condition_bank(train);packed={};n=len(train)
 for key,value in bb.items():packed[('b',key)]=tuple(np.packbits(x) for x in value)
 for key,value in sto.items():packed[('s',key)]=tuple(np.packbits(x) for x in value)
 for key,value in stcb.items():packed[('t',key)]=tuple(np.packbits(x) for x in value)
 rows=[];close=train.close.to_numpy(float);op=train.open.to_numpy(float); horizons=(5,10,20,40)
 # Full deterministic enumeration. Conditions are cached independently; combinations use packed-bitwise AND.
 indices=np.linspace(0,len(SIGGRID)-1,48 if quick else len(SIGGRID),dtype=int) if quick else range(len(SIGGRID))
 for ci in indices:
  p=SIGGRID[int(ci)]
  bkey=tuple(p[k] for k in ('bb_use','bb_depth_pct','bb_window'));skey=tuple(p[k] for k in ('stoch_level','stoch_cross_lag','stoch_min_cross_age'));tkey=tuple(p[k] for k in ('stc_level','stc_turn_type','stc_lag','stc_lookback'))
  for side in (0,1):
   bits=packed[('b',bkey)][side]&packed[('s',skey)][side]&packed[('t',tkey)][side];idx=np.flatnonzero(np.unpackbits(bits)[:n]);events=len(idx)
   if events<1:continue
   row=dict(symbol=s,timeframe=tf,signal_config=ci,**p,events=events,long_events=events if side==0 else 0,short_events=events if side else 0)
   for hz in horizons:
    valid=idx[idx+hz<n];rets=(close[valid+hz]/op[valid+1]-1)*(1 if side==0 else -1)*100 if len(valid) else np.array([])
    row[f'mean_{hz}']=float(rets.mean()) if len(rets) else 0.;row[f'median_{hz}']=float(np.median(rets)) if len(rets) else 0.;row[f'win_{hz}']=float((rets>0).mean()*100) if len(rets) else 0.
   rows.append(row)
 return rows
def stage_a(frames,out,quick):
 workers=2 if quick else min(max(1,(os.cpu_count() or 1)//2),6);args=[(key,df,quick) for key,df in frames.items()]
 with get_context('fork').Pool(workers) as pool: rows=[r for group in pool.map(_stage_a_one,args) for r in group]
 cols=['symbol','timeframe','signal_config',*[k for q in SIGGRID[:1] for k in q], 'events','long_events','short_events',*[f'{m}_{h}' for h in (5,10,20,40) for m in ('mean','median','win')]]
 raw=pd.DataFrame(rows,columns=cols)
 raw.to_csv(out/'stage_a.csv',index=False)
 (out/'stage_a.meta').write_text(json.dumps({'grid_hash':_grid_hash(quick),'verified_rows':len(raw),'verified_configs':raw.signal_config.nunique()},indent=2)+'\n')
 elig=[]
 if len(raw):
  raw['side']=np.where(raw.long_events>0,'long','short')
  grouped={(int(ci),side):g for (ci,side),g in raw.groupby(['signal_config','side'])}
  for ci in range(len(SIGGRID)):
   for side in ('long','short'):
    g=grouped.get((ci,side),raw.iloc[0:0]);counts=g.groupby('timeframe').events.sum().to_dict();total=int(g.events.sum())
    row=dict(signal_config=ci,side=side,train_events=total,eligible=total>=MIN_EVENTS and all(counts.get(tf,0)>=MIN_TF_EVENTS for tf in sorted({k[1] for k in frames})))
    for tf in sorted({k[1] for k in frames}): row[f'events_{tf}']=int(counts.get(tf,0))
    for hz in (10,20):
     weights=g.events.clip(lower=1);row[f'mean_{hz}']=float(np.average(g[f'mean_{hz}'],weights=weights)) if len(g) else 0.;row[f'median_{hz}']=_weighted_median(g[f'median_{hz}'],weights) if len(g) else 0.;row[f'win_{hz}']=float(np.average(g[f'win_{hz}'],weights=weights)) if len(g) else 0.
    elig.append(row)
 pd.DataFrame(elig).to_csv(out/'stage_a_eligibility.csv',index=False)
def grid(quick,require_stop=False):
 stops=[('pct3',3.,None),('pct7',7.,None),('off',None,None),('atr1_5',None,1.5),('atr2_5',None,2.5)];axes=([0,2],[2,4],[1,1.5],stops,[2,5],[False,True],[False,True],[None,48])
 if quick:axes=([0],[3],[1],[('pct4',4.,None),('off',None,None),('atr2',None,2.)],[3],[False],[False],[None,48])
 if require_stop:axes=([0,2],[0,2],[1],[('pct4',4.,None),('atr2',None,2.)] if quick else [*((f'pct{x}',float(x),None) for x in (3,5,8,12)),*((f'atr{x}',None,float(x)) for x in range(2,7))],[2,5],[False,True],[False,True],[None,48])
 result=[]
 for n,sp,sz,stop,tp,mid,opp,mh in itertools.product(*axes):
  mode,sl,atrm=stop;p=dict(n_adds=n,add_spacing_pct=sp,add_size_mult=sz,stop_mode=mode,sl_pct=sl,atr_mult=atrm,tp_pct=tp,bb_mid_exit=mid,opp_exit=opp,max_hold_bars=mh)
  if require_stop and sl is None and atrm is None:continue
  if atrm is None and is_coherent(n,sp,sl):result.append(p)
  elif atrm is not None:result.append(p) # Per-entry ATR percent coherence is checked by simulate().
 return result
_FRAMES={};_SIGNALS={}
def _init(frames):
 global _FRAMES,_SIGNALS;_FRAMES=frames;_SIGNALS={}
def _signal(key,si):
 config=si if isinstance(si,dict) else SIGGRID[si];token=(key,tuple(config.items()))
 if token not in _SIGNALS:_SIGNALS[token]=signal_frame(_FRAMES[key],config)
 return _SIGNALS[token]
def _work(task):
 key,si,p,cut=task;df=_FRAMES[key];sig=_signal(key,si);return [dict(symbol=key[0],timeframe=key[1],signal_config=si,side=side,params=json.dumps(p,sort_keys=True),**{'train_'+k:v for k,v in simulate(df.iloc[:cut],sig.iloc[:cut],p,side).items()}) for side in ('long','short','combined')]
def _robust(g):
 ret=float(g.train_total_return.sum());dd=float(g.train_max_dd.abs().mean());pf=float(g.train_pf.replace([np.inf,-np.inf],np.nan).fillna(0).mean());return ret-dd+min(pf,5)*.25
def _winner_task(task):
 ci,p,side=task;per=[]
 for (s,tf),df in _FRAMES.items():
  cut=int(len(df)*.6);m=simulate(df.iloc[:cut],_signal((s,tf),ci).iloc[:cut],p,side);per.append((s,tf,m))
 trades=sum(x[2]['trades'] for x in per)
 if trades<30:return None
 score=sum(x[2]['total_return'] for x in per)-np.mean([abs(x[2]['max_dd']) for x in per])+min(np.mean([x[2]['pf'] if np.isfinite(x[2]['pf']) else 5 for x in per]),5)*.25
 return score,ci,p,per,trades
def _neighbor_task(task):
 config,p=task;ms=[]
 for key,df in _FRAMES.items():
  cut=int(len(df)*.6);ms.append(simulate(df.iloc[:cut],_signal(key,config).iloc[:cut],p,'combined'))
 return sum(m['total_return'] for m in ms)-np.mean([abs(m['max_dd']) for m in ms])+min(np.mean([m['pf'] if np.isfinite(m['pf']) else 5 for m in ms]),5)*.25
def _signal_neighbor_specs(sigcfg,management):
 axes=[('bb_use',['close','low']),('bb_depth_pct',[0,5,10,20]),('bb_window',[0,2,4,8]),('stoch_level',[15,20,25,30]),('stoch_cross_lag',[0,2,4,8]),('stoch_min_cross_age',[0,1,2,3]),('stc_level',[10,25,40]),('stc_turn_type',[1,2]),('stc_lag',[0,2,4,8]),('stc_lookback',[5,10,20])]
 specs=[]
 for axis,values in axes:
  if sigcfg[axis] not in values:continue
  ix=values.index(sigcfg[axis])
  for j in (ix-1,ix+1):
   if 0<=j<len(values):
    value=values[j]
    if axis=='stoch_cross_lag' and sigcfg['stoch_min_cross_age']>value:continue
    specs.append((axis,value,management,{**sigcfg,axis:value},'signal'))
 return specs
def stage_b(frames,out,quick):
 e=pd.read_csv(out/'stage_a_eligibility.csv');tops={}
 for side in ('long','short'):
  q=e[(e.side==side)&e.eligible].copy();q['score']=q.mean_10+q.median_10+q.mean_20+q.median_20+q.win_10/100+q.win_20/100
  tops[side]=q.sort_values(['score','train_events'],ascending=False).signal_config.astype(int).tolist()
 top=[]
 for ci in sorted(set(tops['long'][:TOP_K]+tops['short'][:TOP_K]),key=lambda x:min((tops[z].index(x) if x in tops[z] else TOP_K+1) for z in tops)):
  if all(sum(SIGGRID[ci][k]!=SIGGRID[old][k] for k in SIGGRID[ci])>=2 for old in top):top.append(ci)
  if len(top)>=TOP_K:break
 if quick: top=top[:2]
 if not top and quick: top=[0]  # Synthetic smoke run only; never feeds a real-data selection.
 combos=grid(quick);tasks=[(key,si,p,int(len(df)*.6)) for key,df in frames.items() for si in top for p in combos];workers=2 if quick else min(6,os.cpu_count() or 1)
 global _MAX_SECONDS
 rows=[r for group in _run_tasks(tasks,_work,frames,out,'B',quick) for r in group]
 d=pd.DataFrame(rows);pooled=[]
 for (si,side,params),g in d.groupby(['signal_config','side','params']):
  trades=int(g.train_trades.sum());pooled.append(dict(signal_config=si,side=side,params=params,train_trades=trades,robust_score=_robust(g),train_return=float(g.train_total_return.sum()),train_max_dd=float(g.train_max_dd.abs().mean()),eligible=trades>=30))
 pr=pd.DataFrame(pooled);both=set(e[(e.side=='long')&e.eligible].signal_config)&set(e[(e.side=='short')&e.eligible].signal_config);eligible=pr[(pr.eligible)&(pr.side=='combined')&pr.signal_config.isin(both)];winner=eligible.sort_values(['robust_score','train_return'],ascending=False).iloc[0] if len(eligible) else None
 d['selected_train']=False;d['headline_baseline']=False
 if winner is not None:
  chosen=json.loads(winner.params);si=int(winner.signal_config);d.loc[(d.signal_config==si)&(d.params==winner.params)&(d.side=='combined'),'selected_train']=True
 else:
  chosen=dict(n_adds=0,add_spacing_pct=3,add_size_mult=1,stop_mode='baseline',sl_pct=5,atr_mult=None,tp_pct=3,bb_mid_exit=False,opp_exit=False,max_hold_bars=None);si=top[0]
  fallback=[]
  for key,df0 in frames.items():
   cut=int(len(df0)*.6);sig=signal_frame(df0,SIGGRID[si])
   for side in ('long','short','combined'):
    m=simulate(df0.iloc[:cut],sig.iloc[:cut],chosen,side);fallback.append(dict(symbol=key[0],timeframe=key[1],signal_config=si,side=side,params=json.dumps(chosen,sort_keys=True),selected_train=False,headline_baseline=True,**{'train_'+k:v for k,v in m.items()}))
  d=pd.concat([d,pd.DataFrame(fallback)],ignore_index=True,sort=False)
 testcols=[]
 for (s,tf),df in frames.items():
  cut=int(len(df)*.6);sig=signal_frame(df,SIGGRID[si])
  for side in ('long','short','combined'):
   m=simulate(df.iloc[cut:],sig.iloc[cut:],chosen,side);mask=(d.symbol==s)&(d.timeframe==tf)&(d.signal_config==si)&(d.params==json.dumps(chosen,sort_keys=True))&(d.side==side)
   for k,v in m.items():
    col='test_'+k
    if col not in d:d[col]=np.nan
    d.loc[mask,col]=v
 ab=[]
 for mask in itertools.product((0,1),repeat=3):
  for (s,tf),df in frames.items():
   cut=int(len(df)*.6);sig=signal_frame(df,SIGGRID[si],enabled=mask)
   for split,part,ss in (('train',df.iloc[:cut],sig.iloc[:cut]),('test',df.iloc[cut:],sig.iloc[cut:])):
    m=simulate(part,ss,chosen,'combined');ab.append(dict(bb=mask[0],stoch=mask[1],stc=mask[2],symbol=s,timeframe=tf,split=split,events=int((ss.long|ss.short).sum()),**m))
 pd.DataFrame(ab).to_csv(out/'ablation.csv',index=False)
 plateau=[]
 if winner is not None:
  base=json.loads(winner.params);subset=pr[(pr.signal_config==int(winner.signal_config))&(pr.side=='combined')]
  axis_values={k:[] for k in base}
  for candidate in combos:
   for k,v in candidate.items():
    if v not in axis_values[k]:axis_values[k].append(v)
  for r in subset.itertuples():
   other=json.loads(r.params);diff=[k for k in base if base[k]!=other[k]]
   if len(diff)==1:
    axis=diff[0];vals=axis_values[axis]
    if abs(vals.index(base[axis])-vals.index(other[axis]))==1:plateau.append(dict(axis=axis,params=r.params,train_trades=r.train_trades,robust_score=r.robust_score,eligible=r.eligible))
 # Side-specific and hard-stop constrained winners use independent train-only selection.
 summaries=[];plateau_rows=[]
 stop_combos=grid(quick,require_stop=True)
 for label,side,source,require_stop in [('unconstrained','combined',combos,False),('with_stop','combined',stop_combos,True),('long_only','long',combos,False),('short_only','short',combos,False)]:
  pool_rows=[]
  candidates=top if top else [0]
  tasks=[(ci,p,side) for ci in candidates for p in source]
  pool_rows=[r for r in _run_tasks(tasks,_winner_task,frames,out,f'B/{label}',quick) if r is not None]
  pool_rows.sort(key=lambda x:x[0],reverse=True);winner0=pool_rows[0] if pool_rows else None
  if winner0 is None:
   summaries.append(dict(kind=label,selected=False));continue
  score,ci,p,per,trades=winner0;sigcfg=SIGGRID[ci]
  for (s,tf,trainm) in per:
   df0=frames[(s,tf)];cut=int(len(df0)*.6);sg=signal_frame(df0,sigcfg);testm=simulate(df0.iloc[cut:],sg.iloc[cut:],p,side)
   summaries.append(dict(kind=label,symbol=s,timeframe=tf,selected=True,signal_config=ci,signal_knobs=json.dumps(sigcfg,sort_keys=True),side=side,params=json.dumps(p,sort_keys=True),train_trades=trainm['trades'],train_return=trainm['total_return'],train_score=score,**{'test_'+k:v for k,v in testm.items()}))
  # Axial management neighbors and one-step signal knob neighbors, all scored on train with winner management.
  if label in ('unconstrained','with_stop'):
   axes=source;management_axes={'n_adds':['n_adds'],'add_spacing_pct':['add_spacing_pct'],'add_size_mult':['add_size_mult'],'stop':['stop_mode','sl_pct','atr_mult'],'tp_pct':['tp_pct'],'bb_mid_exit':['bb_mid_exit'],'opp_exit':['opp_exit'],'max_hold_bars':['max_hold_bars']};neighbor_specs=[]
   for axis,fields in management_axes.items():
    baseval=tuple(p[k] for k in fields);vals=list(dict.fromkeys(tuple(x[k] for k in fields) for x in axes));ix=vals.index(baseval) if baseval in vals else -1
    if ix<0:continue
    for j in (ix-1,ix+1):
     if j<0 or j>=len(vals):continue
     q={**p,**dict(zip(fields,vals[j]))};neighbor_specs.append((axis,vals[j],q,sigcfg,'management'))
   neighbor_specs.extend(_signal_neighbor_specs(sigcfg,p))
   scores=_run_tasks([(q,mp) for _,_,mp,q,_ in neighbor_specs],_neighbor_task,frames,out,f'B/{label}/neighbors',quick)
   for (axis,value,_,_,kind),sc in zip(neighbor_specs,scores):plateau_rows.append(dict(winner=label,axis=axis,neighbor_value=value,score=sc,ratio=sc/score if sc else np.nan,neighbor_kind=kind))
 # Hybrid uses side-specific train-selected signals with the train-selected combined management rule.
 lw=next((x for x in summaries if x.get('kind')=='long_only' and x.get('selected')),None);sw=next((x for x in summaries if x.get('kind')=='short_only' and x.get('selected')),None);cw=next((x for x in summaries if x.get('kind')=='unconstrained' and x.get('selected')),None)
 if lw and sw and cw:
  lp=json.loads(lw['signal_knobs']);sp=json.loads(sw['signal_knobs']);mp=json.loads(cw['params'])
  for (s,tf),df0 in frames.items():
   cut=int(len(df0)*.6);ls=signal_frame(df0,lp);ss=signal_frame(df0,sp);hy=ls.copy();hy['long']=ls.long;hy['short']=ss.short
   tm=simulate(df0.iloc[:cut],hy.iloc[:cut],mp,'combined');vm=simulate(df0.iloc[cut:],hy.iloc[cut:],mp,'combined')
   summaries.append(dict(kind='hybrid_side_signals',symbol=s,timeframe=tf,selected=True,signal_config=-1,signal_knobs=json.dumps({'long':lp,'short':sp},sort_keys=True),side='combined',params=json.dumps(mp,sort_keys=True),train_trades=tm['trades'],train_return=tm['total_return'],train_score=np.nan,**{'test_'+k:v for k,v in vm.items()}))
 pd.DataFrame(summaries).to_csv(out/'winner_comparison.csv',index=False)
 pl=pd.DataFrame(plateau_rows)
 if len(pl):
  for label,g in pl.groupby('winner'):
   w=next((x for x in summaries if x.get('kind')==label and x.get('selected')),None);ws=w['train_score'] if w else 0
   verdict,pct=plateau_verdict(g.score.to_numpy(),ws);pl.loc[g.index,'verdict']=verdict;pl.loc[g.index,'robust_neighbor_pct']=pct
 pl.to_csv(out/'plateau.csv',index=False)
 d.to_csv(out/'stage_b.csv',index=False);pr.to_csv(out/'stage_b_pooled.csv',index=False)
def _event_rank(df,indices=None):
 rows=[]
 indices=list(range(len(SIGGRID))) if indices is None else indices
 for ci in indices:
  p=SIGGRID[ci]
  sig=signal_frame(df,p)
  for side,col in [('long','long'),('short','short')]:
   ix=np.flatnonzero(sig[col].to_numpy());valid=ix[ix+10<len(df)];close=df.close.to_numpy(float);op=df.open.to_numpy(float);r=(close[valid+10]/op[valid+1]-1)*(1 if side=='long' else -1)*100 if len(valid) else np.array([])
   rows.append(dict(signal_config=ci,side=side,events=len(ix),score=float(r.mean()) if len(r) else 0))
 return pd.DataFrame(rows)
def _select_configs(train, top_k=1):
 # Eight deterministic candidates span the full signal grid.
 candidates0=np.linspace(0,len(SIGGRID)-1,8,dtype=int).tolist()
 rank=_event_rank(train,candidates0);candidates=[]
 for side in ('long','short'):
  q=rank[(rank.side==side)&(rank.events>=40)].sort_values(['score','events'],ascending=False).head(top_k)
  candidates.extend(q.signal_config.astype(int).tolist())
 return list(dict.fromkeys(candidates))
def _window_bounds(df,start,train_months=12,test_months=3):
 origin=df.index[0];tr_end=origin+pd.DateOffset(months=start+train_months);te_end=tr_end+pd.DateOffset(months=test_months)
 ti=np.flatnonzero((df.index>=origin+pd.DateOffset(months=start))&(df.index<tr_end));vi=np.flatnonzero((df.index>=tr_end)&(df.index<te_end))
 if not len(ti) or not len(vi):return None
 return slice(ti[0],ti[-1]+1),slice(vi[0],vi[-1]+1)
def plateau_verdict(neighbor_scores,winner_score):
 scores=np.asarray(neighbor_scores,float)
 pct=float(np.mean(scores>=.5*winner_score)*100) if len(scores) else 0.
 return ('ROBUST' if pct>=70 else 'FRAGILE'),pct
def _wf_task(task):
 (s,tf),month,configs=task;df=_FRAMES[(s,tf)];bounds=_window_bounds(df,month)
 if bounds is None:return None
 ts,vs=bounds;tr=df.iloc[ts];te=df.iloc[vs];indices=_select_configs(tr);sigs={ci:_signal((s,tf),ci) for ci in indices};best=None
 for ci in indices:
  for p in configs:
   m=simulate(tr,sigs[ci].iloc[ts],p,'combined')
   if m['trades']<15:continue
   score=m['total_return']-abs(m['max_dd'])
   if best is None or score>best[0]:best=(score,ci,p,m)
 if best is None:return dict(symbol=s,timeframe=tf,train_start=str(tr.index[0]),test_start=str(te.index[0]),test_end=str(te.index[-1]),selected=False,train_score=np.nan,test_trades=0,test_total_return=0,test_max_dd=0,test_long=0,test_short=0)
 score,ci,p,tm=best;wsig=sigs[ci].iloc[vs];em=simulate(te,wsig,p,'combined');lm=simulate(te,wsig,p,'long');sm=simulate(te,wsig,p,'short')
 return dict(symbol=s,timeframe=tf,train_start=str(tr.index[0]),test_start=str(te.index[0]),test_end=str(te.index[-1]),selected=True,signal_config=ci,selected_params=json.dumps(p,sort_keys=True),train_trades=tm['trades'],train_score=score,**{'test_'+k:v for k,v in em.items()},test_long_return=lm['total_return'],test_short_return=sm['total_return'])
def wf(frames,out,quick=False):
 rows=[];configs=grid(quick);# Deterministic WF finalists sampled across the complete grid.
 wf_management_count=3 if not quick else min(3,len(configs))
 if len(configs)>wf_management_count:configs=[configs[i] for i in np.linspace(0,len(configs)-1,wf_management_count,dtype=int)]
 tasks=[]
 for (s,tf),df in frames.items():
  for month in range(0,max(0,(df.index[-1]-df.index[0]).days//30-15)+1,3):
   if _window_bounds(df,month) is not None:tasks.append(((s,tf),month,configs))
 rows=[r for r in _run_tasks(tasks,_wf_task,frames,out,'wf',quick) if r is not None]
 d=pd.DataFrame(rows);d.to_csv(out/'wf.csv',index=False)
 selected=d[d.selected.astype(bool)] if len(d) else d
 summary=[]
 for side in ('long','short','combined'):
  trades=int(selected.get('test_'+('trades' if side=='combined' else side),pd.Series(dtype=float)).sum()) if len(selected) else 0
  retcol={'long':'test_long_return','short':'test_short_return','combined':'test_total_return'}[side];returns=selected.get(retcol,pd.Series(dtype=float)) if len(selected) else pd.Series(dtype=float)
  ddcol={'long':'test_long_max_dd','short':'test_short_max_dd','combined':'test_max_dd'}[side]
  dd=selected.get(ddcol,pd.Series(dtype=float)) if len(selected) else pd.Series(dtype=float)
  summary.append(dict(side=side,windows=len(d),windows_selected=len(selected),test_trades=trades,test_return_sum=float(returns.sum()) if len(returns) else 0,test_return_mean=float(returns.mean()) if len(returns) else 0,windows_positive_pct=float((returns>0).mean()*100) if len(returns) else 0,test_max_dd_mean=float(dd.mean()) if len(dd) else 0))
 pd.DataFrame(summary).to_csv(out/'wf_summary.csv',index=False)
def signal_counts(frames,out):
 rows=[]
 chosen=0
 f=out/'stage_b.csv'
 if f.exists():
  b=pd.read_csv(f);sel=b[b.get('selected_train',False).astype(bool)] if 'selected_train' in b else pd.DataFrame()
  if not len(sel) and 'headline_baseline' in b:sel=b[b.headline_baseline.astype(bool)]
  if len(sel):chosen=int(sel.iloc[0].signal_config)
 for (s,tf),df in frames.items():
  si=chosen;sig=signal_frame(df,SIGGRID[si]);cut=int(len(df)*.6)
  for split,sl in (('train',slice(0,cut)),('test',slice(cut,None))):
   z=sig.iloc[sl];rows.append(dict(symbol=s,timeframe=tf,signal_config=si,split=split,all_3_on=int((z.long|z.short).sum()),long=int(z.long.sum()),short=int(z.short.sum())))
 pd.DataFrame(rows).to_csv(out/'signal_counts.csv',index=False)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['data','A','B','select','wf','report','all'],default='all');ap.add_argument('--quick',action='store_true');ap.add_argument('--reuse-stage-a',action=argparse.BooleanOptionalAction,default=None);ap.add_argument('--max-minutes',type=float,default=40);a=ap.parse_args();out=ROOT/('results_quick' if a.quick else 'results');out.mkdir(exist_ok=True);frames=getdata(a.quick);stages=[]
 global _MAX_SECONDS,_DEADLINE
 _MAX_SECONDS=max(1,a.max_minutes*60)
 _DEADLINE=time.monotonic()+_MAX_SECONDS
 reuse=_stage_a_valid(out,a.quick) if a.reuse_stage_a is None else a.reuse_stage_a
 if a.stage=='all' and reuse:
  _ensure_stage_a(out,True,a.quick)
 jobs=[]
 if a.stage in ('data','all'):jobs.append(('data',lambda:pd.DataFrame([dict(symbol=s,timeframe=tf,bars=len(d),gaps=len(check_data(d,tf))) for (s,tf),d in frames.items()]).to_csv(out/'data_report.csv',index=False)))
 if a.stage=='A' or (a.stage=='all' and not reuse):jobs.append(('A',lambda:stage_a(frames,out,a.quick)))
 if a.stage in ('B','select','all'):jobs.append(('B',lambda:stage_b(frames,out,a.quick)))
 if a.stage in ('B','select','all'):jobs.append(('signal_counts',lambda:signal_counts(frames,out)))
 if a.stage in ('wf','all'):jobs.append(('wf',lambda:wf(frames,out,a.quick)))
 if a.stage in ('report','all'):jobs.append(('report',lambda:generate(out)))
 for name,fn in jobs:
  _log(out,f'{name} started');start=time.perf_counter()
  old_handler=signal.getsignal(signal.SIGALRM)
  signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError(f'{name} exceeded --max-minutes={a.max_minutes}')))
  remaining=int(_DEADLINE-time.monotonic())
  if remaining<=0:raise TimeoutError(f'total --max-minutes={a.max_minutes} budget exhausted before {name}')
  signal.alarm(remaining)
  try:fn()
  finally:signal.alarm(0);signal.signal(signal.SIGALRM,old_handler)
  elapsed=time.perf_counter()-start;stages.append(dict(stage=name,seconds=round(elapsed,3)));_log(out,f'{name} finished elapsed={elapsed:.1f}s')
 pd.DataFrame(stages).to_csv(out/'stage_timings.csv',index=False)
 if (out/'REPORT.md').exists() and a.stage in ('report','all'):
  p=out/'REPORT.md';table='| Stage | Seconds |\n|---|---:|\n'+'\n'.join(f"| {r['stage']} | {r['seconds']:.3f} |" for r in stages)
  counts=pd.read_csv(out/'signal_counts.csv') if (out/'signal_counts.csv').exists() else pd.DataFrame()
  count_table='| Symbol | Timeframe | Split | All 3 on | Long | Short |\n|---|---|---|---:|---:|---:|\n'+'\n'.join(f"| {r.symbol} | {r.timeframe} | {r.split} | {r.all_3_on} | {r.long} | {r.short} |" for r in counts.itertuples())
  p.write_text(p.read_text()+'\n## Stage timings\n\n'+table+'\n\n## Signal counts\n\n'+count_table+'\n')
if __name__=='__main__':main()
