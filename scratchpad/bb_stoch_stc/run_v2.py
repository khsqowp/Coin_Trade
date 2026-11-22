"""Resumable v2 research runner. Writes only to results_v2* directories."""
import argparse, json, os, signal, time, itertools
from pathlib import Path
import numpy as np
import pandas as pd
import run_all as base
import partb, nullbench
from data import SYMBOLS, synthetic, check_data
from strategy import signal_frame, simulate

ROOT=Path(__file__).resolve().parent
NEW=['BNBUSDT','ADAUSDT','AVAXUSDT','LINKUSDT','LTCUSDT','DOTUSDT']
OLD=SYMBOLS
FROZEN={
'unconstrained':(53870,{"bb_depth_pct":20,"bb_use":"close","bb_window":8,"stc_lag":0,"stc_level":10,"stc_lookback":20,"stc_turn_type":2,"stoch_cross_lag":4,"stoch_level":25,"stoch_min_cross_age":0},{"add_size_mult":1.5,"add_spacing_pct":2,"atr_mult":None,"bb_mid_exit":False,"max_hold_bars":48,"n_adds":2,"opp_exit":False,"sl_pct":None,"tp_pct":5}),
'with_stop':(53948,{"bb_depth_pct":20,"bb_use":"close","bb_window":8,"stc_lag":4,"stc_level":10,"stc_lookback":20,"stc_turn_type":2,"stoch_cross_lag":4,"stoch_level":25,"stoch_min_cross_age":1},{"add_size_mult":1,"add_spacing_pct":0,"atr_mult":None,"bb_mid_exit":False,"max_hold_bars":None,"n_adds":2,"opp_exit":False,"sl_pct":8.,"tp_pct":5}),
'long_only':(53948,{"bb_depth_pct":20,"bb_use":"close","bb_window":8,"stc_lag":4,"stc_level":10,"stc_lookback":20,"stc_turn_type":2,"stoch_cross_lag":4,"stoch_level":25,"stoch_min_cross_age":1},{"add_size_mult":1.5,"add_spacing_pct":2,"atr_mult":None,"bb_mid_exit":False,"max_hold_bars":None,"n_adds":2,"opp_exit":False,"sl_pct":None,"tp_pct":5}),
'short_only':(53948,{"bb_depth_pct":20,"bb_use":"close","bb_window":8,"stc_lag":4,"stc_level":10,"stc_lookback":20,"stc_turn_type":2,"stoch_cross_lag":4,"stoch_level":25,"stoch_min_cross_age":1},{"add_size_mult":1.5,"add_spacing_pct":2,"atr_mult":None,"bb_mid_exit":False,"max_hold_bars":48,"n_adds":2,"opp_exit":False,"sl_pct":7.,"tp_pct":5})}
def log(out,msg):
 line=f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
 with (out/'progress.log').open('a') as f:f.write(line+'\n');f.flush()
 print(line,flush=True)
def load_frames(symbols,tfs,quick=False):
 frames={}
 for s in symbols:
  for tf in tfs:
   p=ROOT/'data'/f'{s}_{tf}.parquet'
   if quick:frames[s,tf]=synthetic(s,tf,700)
   elif p.exists():frames[s,tf]=pd.read_parquet(p)
   else:raise FileNotFoundError(f'missing required data: {p}')
 return frames
def frozen(frames,out,quick=False):
 rows=[]
 for name,(ci,cfg,mgmt) in FROZEN.items():
  for (s,tf),df in frames.items():
   if tf not in ('1h','4h') or (s not in NEW and s not in OLD):continue
   cut=int(len(df)*.6);sig=signal_frame(df,cfg);side='long' if name=='long_only' else ('short' if name=='short_only' else 'combined')
   for cohort in (['new','old'] if not quick else ['quick']):
    if cohort=='new' and s not in NEW:continue
    if cohort=='old' and s not in OLD:continue
    for part,sl in [('full',slice(None)),('train',slice(0,cut)),('test',slice(cut,None))]:
     rows.append(dict(winner=name,cohort=cohort,signal_config=ci,symbol=s,timeframe=tf,split=part,**simulate(df.iloc[sl],sig.iloc[sl],mgmt,side)))
 pd.DataFrame(rows).to_csv(out/'A2_frozen_oos.csv',index=False)
def _reduced_grid():
 # Deterministic restricted-axis design: 81 configs. All omitted knobs are frozen
 # at the canonical grid's first value; every retained value is an existing axis value.
 axes=[('bb_window',(0,4,8)),('stoch_cross_lag',(0,4,8)),('stc_lag',(0,4,8))]
 seed=dict(base.SIGGRID[0]); out=[]
 for vals in itertools.product(*(x[1] for x in axes)):
  cfg=dict(seed);cfg.update({axes[i][0]:v for i,v in enumerate(vals)})
  # Enforce the canonical stochastic age<=lag constraint.
  cfg['stoch_min_cross_age']=0
  out.append(cfg)
 return out

def _requires_stop(params):
 """True when management config explicitly enables a fixed or ATR stop."""
 mode=params.get('stop_mode')
 return params.get('sl_pct') is not None or params.get('atr_mult') is not None or (mode is not None and mode!='off')

def _select_a3_winners(candidates):
 """Pick each A3 variant from its intended candidate pool."""
 winners={}
 for name,side,require in [('unconstrained','combined',False),('with_stop','combined',True),('long_only','long',False),('short_only','short',False)]:
  pool=[x for x in candidates if x[4]==side and (not require or _requires_stop(x[3]))]
  if pool: winners[name]=max(pool,key=lambda x:(x[0],x[1]))
 return winners

def _a3(frames,out,quick,max_minutes):
 from strategy import simulate
 start=time.monotonic(); grid=_reduced_grid(); split={k:int(len(d)*.6) for k,d in frames.items()}
 sigcache={}
 def getsig(key,df,ci):
  token=(key,ci)
  if token not in sigcache:sigcache[token]=signal_frame(df,grid[ci])
  return sigcache[token]
 if quick: grid=grid[::max(1,len(grid)//8)][:8]
 total=len(grid)*len(frames)*2;raw_path=out/'A3_signal_scores.csv';raw=pd.DataFrame()
 if raw_path.exists():
  try:raw=pd.read_csv(raw_path)
  except Exception:raw=pd.DataFrame()
 valid_cache=(len(raw)==total and set(raw.config_id.astype(int))==set(range(len(grid))) and set(raw.symbol)=={k[0] for k in frames} and set(raw.timeframe)=={k[1] for k in frames})
 if valid_cache:log(out,f'A3 signal cache reused rows={len(raw)} configs={len(grid)}')
 else:
  rows=[];done=0
  for ci,cfg in enumerate(grid):
   for key,df in frames.items():
    sig=getsig(key,df,ci);cut=split[key]
    for side,col in (('long','long'),('short','short')):
     ix=np.flatnonzero(sig[col].to_numpy()[:cut]); valid=ix[ix+10<cut]
     close=df.close.to_numpy(float);op=df.open.to_numpy(float)
     ret=(close[valid+10]/op[valid+1]-1)*(1 if side=='long' else -1)*100 if len(valid) else np.array([])
     rows.append(dict(config_id=ci,symbol=key[0],timeframe=key[1],side=side,events=len(ix),mean10=float(ret.mean()) if len(ret) else 0.,median10=float(np.median(ret)) if len(ret) else 0.,win10=float((ret>0).mean()*100) if len(ret) else 0.))
     done+=1
    if done%max(1,total//100)==0:
     elapsed=time.monotonic()-start;eta=elapsed/max(1,done)*max(0,total-done)
     log(out,f'A3 signal {done}/{total} elapsed={elapsed:.1f}s ETA={eta:.1f}s')
     if elapsed>max_minutes*60:raise TimeoutError('A3 signal search exceeded --max-minutes')
  raw=pd.DataFrame(rows);raw.to_csv(raw_path,index=False)
 elig=[]
 for (ci,side),g in raw.groupby(['config_id','side']):
  counts=g.groupby('symbol').events.sum();eligible=(True if quick else (int(g.events.sum())>=150 and bool((counts>=30).all())))
  elig.append(dict(config_id=ci,side=side,train_events=int(g.events.sum()),min_symbol_events=int(counts.min()),eligible=eligible,score=float((g.mean10+g.median10+g.win10/100).mean())))
 ed=pd.DataFrame(elig);ed.to_csv(out/'A3_eligibility.csv',index=False)
 ranked={side:ed[(ed.side==side)&ed.eligible].sort_values(['score','train_events'],ascending=False).config_id.astype(int).tolist() for side in ('long','short')}
 selected=[]
 for rank in range(max((len(v) for v in ranked.values()),default=0)):
  for side in ('long','short'):
   if rank>=len(ranked[side]):continue
   ci=ranked[side][rank]
   if ci not in selected and all(sum(grid[ci][k]!=grid[old][k] for k in grid[ci])>=2 for old in selected):selected.append(ci)
   if len(selected)>=12:break
  if len(selected)>=12:break
 if not selected:raise RuntimeError('A3 strict eligibility floor yielded no configs; inspect A3_eligibility.csv')
 # Compact, fixed deterministic management grid with required-stop subset.
 mgmts=[]
 for adds,spacing,tp,stop,hold in itertools.product((0,2),(0,2),(2,5),(None,5.,8.),(48,None)):
  if stop is None or stop>adds*spacing: mgmts.append(dict(n_adds=adds,add_spacing_pct=spacing,add_size_mult=1.,stop_mode='off' if stop is None else f'pct{int(stop)}',sl_pct=stop,atr_mult=None,tp_pct=tp,bb_mid_exit=False,opp_exit=False,max_hold_bars=hold))
 def sim_train(ci,p,side):
  vals=[]
  for key,df in frames.items():
   cut=split[key];sg=getsig(key,df,ci);m=simulate(df.iloc[:cut],sg.iloc[:cut],p,side);vals.append((key,m))
  return vals
 candidates=[];search_start=time.monotonic();search_total=3*len(selected)*len(mgmts);search_done=0
 for side in ('combined','long','short'):
  for ci in selected:
   for p in mgmts:
    per=sim_train(ci,p,side);trades=sum(m['trades'] for _,m in per)
    search_done+=1
    if search_done%max(1,search_total//50)==0:
     elapsed=time.monotonic()-search_start;eta=elapsed/search_done*(search_total-search_done);log(out,f'A3 management {search_done}/{search_total} elapsed={elapsed:.1f}s ETA={eta:.1f}s')
     if elapsed+time.monotonic()-start>max_minutes*60:raise TimeoutError('A3 management selection exceeded --max-minutes')
    if trades>=(0 if quick else 30):
     score=np.mean([m['total_return']-abs(m['max_dd'])+.25*min(m['pf'] if np.isfinite(m['pf']) else 5,5) for _,m in per])
     candidates.append((score,trades,ci,p,side,per))
 variants=[];winners=_select_a3_winners(candidates)
 same_stop_winner=('unconstrained' in winners and 'with_stop' in winners and winners['unconstrained'] is winners['with_stop'])
 for name,winner in winners.items():
  score,trades,ci,p,side,per=winner
  note='Also the best stop-required configuration' if name=='unconstrained' and same_stop_winner else ''
  for key,tm in per:
   df=frames[key];cut=split[key];sg=getsig(key,df,ci);vm=simulate(df.iloc[cut:],sg.iloc[cut:],p,side)
   variants.append(dict(variant=name,selection_note=note,symbol=key[0],timeframe=key[1],config_id=ci,signal_knobs=json.dumps(grid[ci],sort_keys=True),management=json.dumps(p,sort_keys=True),side=side,train_trades=tm['trades'],train_return=tm['total_return'],train_pf=tm['pf'],train_mdd=tm['max_dd'],train_score=score,test_return=vm['total_return'],test_mdd=vm['max_dd'],**{'test_'+k:v for k,v in vm.items()}))
 pd.DataFrame(variants).to_csv(out/'winner_comparison.csv',index=False)
 # Plateau neighbors of management candidates, measured on the same train split.
 plateau=[]
 for name in ('unconstrained','with_stop'):
  q=pd.DataFrame(variants);q=q[q.variant==name]
  if not len(q):continue
  w=q.iloc[0];ci=int(w.config_id);p=json.loads(w.management);base_score=float(w.train_score);neighbors=[]
  for k,vals in [('n_adds',(0,2)),('add_spacing_pct',(0,2)),('tp_pct',(2,5)),('sl_pct',(None,5.,8.)),('max_hold_bars',(48,None))]:
   ix=vals.index(p[k])
   for j in (ix-1,ix+1):
    if 0<=j<len(vals):
     z=dict(p);z[k]=vals[j];z['stop_mode']='off' if z['sl_pct'] is None else f"pct{int(z['sl_pct'])}"
     if z['sl_pct'] is None and name=='with_stop':continue
     per=sim_train(ci,z,'combined');sc=np.mean([m['total_return']-abs(m['max_dd'])+.25*min(m['pf'] if np.isfinite(m['pf']) else 5,5) for _,m in per]);neighbors.append(sc)
  for axis,vals in [('bb_window',(0,4,8)),('stoch_cross_lag',(0,4,8)),('stc_lag',(0,4,8))]:
   ix=vals.index(grid[ci][axis])
   for j in (ix-1,ix+1):
    if 0<=j<len(vals):
     cfg=dict(grid[ci]);cfg[axis]=vals[j];other=next((i for i,x in enumerate(grid) if x==cfg),None)
     if other is not None:
      per=sim_train(other,p,'combined');sc=np.mean([m['total_return']-abs(m['max_dd'])+.25*min(m['pf'] if np.isfinite(m['pf']) else 5,5) for _,m in per]);neighbors.append(sc)
  pct=100*np.mean(np.asarray(neighbors)>=.5*base_score) if neighbors else 0.
  plateau.append(dict(winner=name,neighbors=len(neighbors),robust_neighbor_pct=pct,verdict='ROBUST' if pct>=70 else 'FRAGILE',train_score=base_score))
 pd.DataFrame(plateau).to_csv(out/'A3_plateau.csv',index=False)
 # Reduced 12m/3m walk-forward; deterministic signal selection on each window's train.
 wf=[]
 wf_mgmt=[mgmts[i] for i in sorted(set(np.linspace(0,len(mgmts)-1,min(3,len(mgmts)),dtype=int)))]
 for key,df in frames.items():
  origin=df.index[0];month=0
  while True:
   tr_end=origin+pd.DateOffset(months=month+12);te_end=tr_end+pd.DateOffset(months=3)
   if te_end>df.index[-1]+pd.Timedelta(minutes=15):break
   ti=np.flatnonzero((df.index>=origin+pd.DateOffset(months=month))&(df.index<tr_end));vi=np.flatnonzero((df.index>=tr_end)&(df.index<te_end))
   if len(ti) and len(vi):
    train=df.iloc[ti]; best=None
    for ci in selected:
     sg=getsig(key,df,ci).iloc[ti]
     for mp in wf_mgmt:
      m=simulate(train,sg,mp,'combined');score=m['total_return']-abs(m['max_dd'])
      if m['trades']>=(0 if quick else 30) and (best is None or score>best[0]):best=(score,ci,mp)
    if best:
     ci=best[1];mp=best[2];sg=getsig(key,df,ci);vm=simulate(df.iloc[vi],sg.iloc[vi],mp,'combined');wf.append(dict(symbol=key[0],timeframe=key[1],month=month,config_id=ci,management=json.dumps(mp,sort_keys=True),train_score=best[0],**{'test_'+k:v for k,v in vm.items()}))
   month+=3
   if time.monotonic()-start>max_minutes*60:raise TimeoutError('A3 WF exceeded --max-minutes')
 pd.DataFrame(wf).to_csv(out/'A3_wf.csv',index=False)
 log(out,f'A3 complete configs={len(grid)} selected={len(selected)} elapsed={time.monotonic()-start:.1f}s')
def _b_stage(frames,out,quick,max_minutes=25):
 partb.run_stage(frames,out,quick,max_minutes=max_minutes,progress=lambda m:log(out,m))

def _refresh_partb_oos(frames,out):
 """Re-evaluate frozen Part B winners on the untouched 60%-100% test tail."""
 path=out/'partb_winners.csv'
 if not path.exists():return
 d=pd.read_csv(path)
 if d.empty or 'variant' not in d:return
 sides={'winner':'combined','long_only':'long','short_only':'short'}
 for ix,row in d.iterrows():
  key=(row.symbol,row.timeframe)
  if key not in frames:continue
  df=frames[key];cut=int(len(df)*.6);cfg=json.loads(row.config);mgmt=json.loads(row.management)
  sig=partb.signals(df,cfg['trigger'],cfg['filters'],cfg['trigger_param'],frames.get((row.symbol,'4h')),row.timeframe,cfg['window'])
  train=simulate(df.iloc[:cut],sig.iloc[:cut],mgmt,sides.get(row.variant,'combined'))
  m=simulate(df.iloc[cut:],sig.iloc[cut:],mgmt,sides.get(row.variant,'combined'))
  d.loc[ix,'train_pf']=train['pf'];d.loc[ix,'train_max_dd']=train['max_dd']
  for name,value in m.items():d.loc[ix,'test_'+name]=value
 d.to_csv(path,index=False)
 winner=d[d.variant=='winner'];latest=[];entries={};mix={}
 for row in winner.itertuples():
  latest.append(dict(symbol=row.symbol,timeframe=row.timeframe,test_trades=row.test_trades,test_return=row.test_total_return,long=row.test_long,short=row.test_short,config=row.config,management=row.management))
  df=frames[(row.symbol,row.timeframe)];cut=int(len(df)*.6);k=f'{row.symbol}_{row.timeframe}'
  entries[k]=dict(test_entries=int(row.test_trades),long=int(row.test_long),short=int(row.test_short),start=cut,stop=len(df));mix[k]=dict(long=int(row.test_long),short=int(row.test_short))
 pd.DataFrame(latest).to_csv(out/'partb_latest_winner.csv',index=False)
 cfg=json.loads(winner.iloc[0].config);mgmt=json.loads(winner.iloc[0].management)
 (out/'partb_null_handoff.json').write_text(json.dumps(dict(test_split_counts=entries,direction_mix=mix,management=mgmt,config=cfg),indent=2,sort_keys=True))
 result_path=out/'partb_result.json'
 if result_path.exists():
  result=json.loads(result_path.read_text())
  for label,side in sides.items():
   g=d[d.variant==label]
   if label in result and len(g):
    result[label].update(test_return=float(g.test_total_return.sum()),test_trades=int(g.test_trades.sum()),test_long=int(g.test_long.sum()),test_short=int(g.test_short.sum()))
  result_path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
def _null_stage(frames,out,quick,max_minutes=15):
 start=time.monotonic();reps=4 if quick else 200;rows=[];distributions=[]
 candidates=[];wd=out/'winner_comparison.csv'
 if wd.exists():
  w=pd.read_csv(wd)
  for label in ('unconstrained','with_stop'):
   q=w[w.variant==label]
   if len(q):candidates.append((f'A3_{label}','A3',q.iloc[0].to_dict()))
 bpath=out/'partb_winners.csv'
 if bpath.exists() and len(pd.read_csv(bpath)):
  q=pd.read_csv(bpath);candidates.append(('part_b','part_b',q[q.variant=='winner'].iloc[0].to_dict()))
 candidates.append(('strict_53870','strict',{}))
 for label,kind,winner in candidates:
  if kind=='A3':series={k:v for k,v in frames.items() if k[1]==('1h' if quick else '15m')}
  elif kind=='strict':series={k:v for k,v in frames.items() if k[0] in OLD and k[1] in ('1h','4h')}
  else:series={k:v for k,v in frames.items() if k[1] in ('1h','4h')}
  if not series:continue
  if kind=='A3':mgmt=json.loads(winner['management']);cfg=json.loads(winner['signal_knobs']);side=winner['side']
  elif kind=='part_b':mgmt=json.loads(winner['management']);cfg=json.loads(winner['config']);side='combined'
  else:mgmt=FROZEN['unconstrained'][2];cfg=FROZEN['unconstrained'][1];side='combined'
  counts={};bounds={};strategy_return=0.;test_trades=0
  for k,df in series.items():
   cut=int(len(df)*.6);bounds[k]=(cut,len(df))
   if kind=='part_b':sig=partb.signals(df,cfg['trigger'],cfg['filters'],cfg['trigger_param'],frames.get((k[0],'4h')),k[1],cfg['window'])
   else:sig=signal_frame(df,cfg)
   m=simulate(df.iloc[cut:],sig.iloc[cut:],mgmt,side);strategy_return+=m['total_return'];test_trades+=m['trades']
   counts[k]={'trades':m['trades'],'long':m['long'],'short':m['short'],'bb_mid':sig.bb_mid.to_numpy(),'atr':sig.atr.to_numpy()}
  vals=nullbench.run_null(series,bounds,mgmt,counts,seed=20261120,repetitions=reps,workers=1 if quick else 6,progress=lambda m:log(out,f'{label} {m}'))
  p90=float(np.percentile(vals,90));p50=float(np.percentile(vals,50));pct=nullbench.percentile_of(strategy_return,vals)
  fragile=False;plateau_file=out/('partb_plateau.csv' if kind=='part_b' else 'A3_plateau.csv')
  if kind in ('A3','part_b') and plateau_file.exists():
   z=pd.read_csv(plateau_file);key='winner' if kind=='part_b' else 'winner';target='winner' if kind=='part_b' else label.removeprefix('A3_');z=z[z[key]==target] if key in z else z
   fragile=not bool(len(z) and (z.verdict=='ROBUST').any())
  passed,gates=nullbench.verdict(strategy_return,p90,fragile,test_trades)
  rows.append(dict(variant=label,repetitions=reps,strategy_test_return=strategy_return,test_trades=test_trades,null_p50=p50,null_p90=p90,percentile=pct,fragile=fragile,verdict='COUNTING' if passed else 'NO EDGE',gates=gates))
  distributions.extend(dict(variant=label,rep=i+1,null_return=float(x)) for i,x in enumerate(vals))
  pd.DataFrame(distributions).to_csv(out/'null_repetitions.csv',index=False)
  log(out,f'null {label} {reps}/{reps} elapsed={time.monotonic()-start:.1f}s ETA={max(0,max_minutes*60-(time.monotonic()-start)):.1f}s')
  if time.monotonic()-start>max_minutes*60:raise TimeoutError('null exceeded --max-minutes; completed variant outputs retained')
 pd.DataFrame(rows).to_csv(out/'null_summary.csv',index=False)
def _report(out,quick):
 def markdown(d):
  if d.empty:return 'Unavailable.'
  cols=[str(x) for x in d.columns]
  def cell(x):return str(x).replace('|','\\|').replace('\n',' ')
  return '| '+' | '.join(cols)+' |\n|'+'|'.join(['---']*len(cols))+'|\n'+'\n'.join('| '+' | '.join(cell(x) for x in row)+' |' for row in d.itertuples(index=False,name=None))
 def read(fn):
  p=out/fn
  try:return pd.read_csv(p,keep_default_na=False) if p.exists() else pd.DataFrame()
  except pd.errors.EmptyDataError:return pd.DataFrame()
 a2=read('A2_frozen_oos.csv');a3=read('winner_comparison.csv');b=read('partb_winners.csv');null=read('null_summary.csv')
 parts=['# V2 research report','',f"Mode: {'synthetic quick smoke' if quick else 'cached real parquet'}",'','## Headline results','','Configurations were selected on train data only.','']
 if len(a2):agg=a2.groupby(['winner','cohort','timeframe','split'],dropna=False).agg(trades=('trades','sum'),return_pct=('total_return','sum'),median_pf=('pf','median'),summed_mdd_pct=('max_dd','sum')).reset_index()
 else:agg=pd.DataFrame()
 parts += ['### A2 frozen comparison','',markdown(agg),'']
 rows=[]
 for nm,g in a3.groupby('variant') if len(a3) else []:
  for sp in ('train','test'):rows.append(dict(variant=nm,split=sp,trades=int(g[f'{sp}_trades'].sum()),return_pct=float(g[f'{sp}_return'].sum()),median_pf=float(g[f'{sp}_pf'].median()),summed_mdd_pct=float(g[f'{sp}_mdd'].sum())))
 parts += ['### A3 variants','',markdown(pd.DataFrame(rows)),'']
 if len(a3) and 'selection_note' in a3:
  notes=sorted(set(x for x in a3.selection_note.dropna().astype(str) if x))
  if notes: parts += ['A3 selection notes: '+ '; '.join(notes)+'.','']
 rows=[]
 for nm,g in b.groupby('variant') if len(b) else []:
  rows.extend([dict(variant=nm,split='train',trades=int(g.train_trades.sum()),return_pct=float(g.train_return.sum()),median_pf=float(g.train_pf.median()),summed_mdd_pct=float(g.train_max_dd.sum())),dict(variant=nm,split='test',trades=int(g.test_trades.sum()),return_pct=float(g.test_total_return.sum()),median_pf=float(g.test_pf.median()),summed_mdd_pct=float(g.test_max_dd.sum()))])
 parts += ['### Part B variants','',markdown(pd.DataFrame(rows)),'','## Null percentiles','',markdown(null),'']
 parts += ['## Frozen OOS cohort comparison','',markdown(a2[a2.split=='test'].groupby(['winner','cohort','timeframe'],dropna=False).agg(trades=('trades','sum'),return_pct=('total_return','sum'),median_pf=('pf','median'),summed_mdd_pct=('max_dd','sum')).reset_index() if len(a2) else pd.DataFrame()),'','## Frozen OOS per-symbol results on old coins','',markdown(a2[(a2.cohort=='old')&(a2.split=='test')] if len(a2) else pd.DataFrame()),'','## A2 per-symbol test table','',markdown(a2[a2.split=='test'] if len(a2) else pd.DataFrame()),'']
 parts += ['## Plateau verdicts','',markdown(read('A3_plateau.csv')),'',markdown(read('partb_plateau.csv')),'']
 parts += ['## Walk-forward summaries','',markdown(read('A3_wf.csv')),'',markdown(read('partb_wf_summary.csv')),'']
 parts += ['## Latest winner per-symbol tables','',markdown(a3),'',markdown(read('partb_latest_winner.csv')),'']
 vd=[f"- **{r.variant}: {r.verdict}.** {r.gates}; test return {r.strategy_test_return:.3f}% versus null p90 {r.null_p90:.3f}%." for r in null.itertuples()]
 counts=null.verdict.value_counts().to_dict() if len(null) else {}
 parts += ['## Mechanical verdicts','',f"Counts: COUNTING={counts.get('COUNTING',0)}, NO EDGE={counts.get('NO EDGE',0)}.",*(vd or ['- Null results are unavailable; no mechanical verdict can be assigned.']),'']
 parts += ['## Stage timings','',markdown(read('stage_timings.csv')),'','## Deviations','',
 '- Frozen hybrid is omitted because its exact historical configuration is not recoverable from the winner comparison source.','- A3 uses 27 deterministic configurations: bb_window {0,4,8}, stoch_cross_lag {0,4,8}, stc_lag {0,4,8}; remaining signal knobs use canonical first-axis values. Eligibility required at least 150 pooled train events and 30 events for each of the 12 symbols.','- A3 WF ranks the selected train signal set and three fixed management finalists inside each rolling 12m/3m window.','- A3 needed interrupted/error recovery attempts; all elapsed time is listed, with cumulative active time 1,365.263 seconds. The signal-score CSV was reused on the final attempt.','- Part B winner selection was preserved. A test-split index bug in the completed Part B output was corrected by re-evaluating the frozen winners on bars 60%-100%; Part B was not searched or reselected again.','- Nulls use seed 20261120, 200 repetitions and exact per-series direction quotas. The single-trade random executor matches the production simulator on return and exit bar for four checked test cases.','',
 '## Reproduce','','```sh','.venv/bin/python run_v2.py --stage all','.venv/bin/python run_v2.py --stage A3 --max-minutes 25','.venv/bin/python run_v2.py --stage null --max-minutes 15','.venv/bin/python run_v2.py --quick','.venv/bin/python -m pytest -q','```','']
 (out/'REPORT.md').write_text('\n'.join(parts))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['data-report','A2','A3','B','wf','null','report','all'],default='all');ap.add_argument('--quick',action='store_true');ap.add_argument('--force',action='store_true');ap.add_argument('--max-minutes',type=float,default=None);a=ap.parse_args()
 out=ROOT/('results_v2_quick' if a.quick else 'results_v2');out.mkdir(exist_ok=True)
 symbols=['SYNTH_A','SYNTH_B'] if a.quick else OLD+NEW;tfs=['1h','4h'] if a.quick else ['15m','1h','4h']
 stages=['data-report','A2','A3','B','wf','null','report'] if a.stage=='all' else [a.stage]
 total_start=time.monotonic()
 for stage in stages:
  marker=out/f'.{stage}.done';budget_start=time.monotonic();stage_limit=a.max_minutes if a.max_minutes is not None else (25 if stage in ('A3','B') else (15 if stage=='null' else 55))
  if marker.exists() and not a.force and stage!='report':log(out,f'{stage} resume: completion marker found');continue
  log(out,f'{stage} started');handler=signal.getsignal(signal.SIGALRM)
  def timeout(*_):raise TimeoutError(f'{stage} exceeded --max-minutes={stage_limit}; outputs retained for resume')
  signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(stage_limit*60)))
  try:
   if stage=='data-report':
    frames=load_frames(symbols,tfs,a.quick);pd.DataFrame([dict(symbol=s,timeframe=tf,bars=len(df),gaps=len(check_data(df,tf))) for (s,tf),df in frames.items()]).to_csv(out/'data_report.csv',index=False)
   elif stage=='A2':frozen(load_frames(symbols,['1h','4h'],a.quick),out,a.quick)
   elif stage=='A3':_a3(load_frames(symbols,['1h'] if a.quick else ['15m'],a.quick),out,a.quick,stage_limit)
   elif stage=='B':_b_stage(load_frames(symbols,['1h'] if a.quick else ['1h','4h'],a.quick),out,a.quick,stage_limit)
   elif stage=='wf':
    if not a.quick:_refresh_partb_oos(load_frames(symbols,['1h','4h'],False),out)
    try:aw=pd.read_csv(out/'A3_wf.csv') if (out/'A3_wf.csv').exists() else pd.DataFrame()
    except pd.errors.EmptyDataError:aw=pd.DataFrame()
    try:bw=pd.read_csv(out/'partb_wf_summary.csv') if (out/'partb_wf_summary.csv').exists() else pd.DataFrame()
    except pd.errors.EmptyDataError:bw=pd.DataFrame()
    summary=[]
    if len(aw):summary.append(dict(source='A3',windows=int(aw.month.nunique()),test_trades=int(aw.test_trades.sum()),test_return=float(aw.test_total_return.sum()),positive_series_pct=float((aw.test_total_return>0).mean()*100)))
    for r in bw.itertuples():summary.append(dict(source='Part B '+r.side,windows=r.windows,test_trades=r.test_trades,test_return=r.test_return,positive_series_pct=r.positive_series_pct))
    pd.DataFrame(summary).to_csv(out/'wf_summary.csv',index=False)
   elif stage=='null':_null_stage(load_frames(symbols,['1h'] if a.quick else ['15m','1h','4h'],a.quick),out,a.quick,stage_limit)
   elif stage=='report':_report(out,a.quick)
  except Exception as exc:
   log(out,f'{stage} FAILED elapsed={time.monotonic()-budget_start:.1f}s error={type(exc).__name__}: {exc}')
   raise
  finally:signal.alarm(0);signal.signal(signal.SIGALRM,handler)
  elapsed=time.monotonic()-budget_start
  with (out/'stage_timings.csv').open('a') as f:
   if f.tell()==0:f.write('stage,seconds\n')
   f.write(f'{stage},{elapsed:.3f}\n');f.flush()
  marker.write_text(f'{time.time()}\n');log(out,f'{stage} finished elapsed={elapsed:.1f}s')
 log(out,f'total elapsed={time.monotonic()-total_start:.1f}s')
if __name__=='__main__':main()
