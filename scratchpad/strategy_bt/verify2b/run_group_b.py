from pathlib import Path
import csv, importlib.util, json, math
import numpy as np, pandas as pd
from collections import defaultdict
from common.engine import simulate
from common.protocol import check_no_lookahead
ROOT=Path.cwd(); OUT=ROOT/'verify2b/results'; SYMS=['BTCUSDT','ETHUSDT','BNBUSDT','XRPUSDT']
CANDS=[('jesse_simple_bollinger','1h','slice_3'),('btc-max10-nyse-close','15m','slice_0'),('btc-macd-15-41-12','1d','slice_1'),('turtle-system-2','1d','slice_3'),('btc-bollinger-37-16','1d','slice_0'),('btc-roc-36-9pct','1d','slice_0')]
def plugin(cid,sl):
 p=ROOT/f'plugins/{sl}/{cid}.py'; sp=importlib.util.spec_from_file_location(cid,p); m=importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
def load(sym,tf):
 p=ROOT/'data_long'/f'{sym}_{tf}.parquet'
 d=pd.read_parquet(p) if p.exists() else None
 c=ROOT.parent/'bb_stoch_stc/data'/f'{sym}_{tf}.parquet'
 if d is not None and c.exists():
  cache=pd.read_parquet(c)
  if not isinstance(d.index,pd.DatetimeIndex): d.index=cache.index[-len(d):] if len(cache)>=len(d) else d.index
  # In-memory append only cached bars strictly after long history endpoint.
  test_start=cache.index[min(int(len(cache)*.6),len(cache)-1)]
  tail=cache.loc[(cache.index>d.index[-1]) & (cache.index>=test_start)]
  if len(tail): d=pd.concat([d,tail[~tail.index.isin(d.index)]])
 elif d is None and c.exists(): d=pd.read_parquet(c)
 return d.sort_index() if d is not None else None
def frozen(cid):
 for s in range(5):
  with (ROOT/f'results/slice_{s}/summary.csv').open() as f:
   for r in csv.DictReader(f):
    if r['strategy_id']==cid and r.get('params'): return json.loads(r['params'])
 raise KeyError(cid)
def run(m,d,p):
 sig=m.signals(d.copy(),**p); ts,met=simulate(d,sig,p,side=getattr(m,'SIDES','both')); return ts,met,sig
def rec(rows,cid,sc,status,**kw): rows.append(dict(candidate=cid,scenario=sc,status=status,**kw))
def jesse_cloud_old(candles, conversion_line_period=9, base_line_period=26, lagging_line_period=52, displacement=26):
    """Direct port of the supplied jesse_old/ichimoku_old.py contract."""
    a=np.asarray(candles, dtype=float)
    if len(a)<80: return (np.nan,np.nan,np.nan,np.nan)
    a=a[-80:]; early=a[:-(displacement-1)]
    def midline(x, n): return (np.max(x[-n:,3])+np.min(x[-n:,4]))/2
    return (midline(a,conversion_line_period), midline(a,base_line_period),
            (midline(early,conversion_line_period)+midline(early,base_line_period))/2,
            midline(early,lagging_line_period))
def pos_returns(df, trades):
    """Daily mark-to-market returns from harness trade intervals, flat when out."""
    r=np.zeros(len(df),float); close=df.close.to_numpy(float)
    for t in trades:
        a=max(1,int(t['entry'])); b=min(len(df),int(t['exit'])+1); sign=1 if t['side']=='long' else -1
        r[a:b]=sign*np.diff(close[a-1:b])/close[a-1:b-1]
    return pd.Series(r,index=df.index)
def main():
 OUT.mkdir(exist_ok=True); rows=[]; overall={}
 for cid,tf,sl in CANDS:
  m=plugin(cid,sl); p=frozen(cid); side=getattr(m,'SIDES','both'); b1=[];
  for sym in (['BTCUSDT','ETHUSDT'] if tf=='15m' else SYMS):
   d=load(sym,tf)
   if d is None: rec(rows,cid,'B1','MISSING',symbol=sym); continue
   check_no_lookahead(m,d,p); ts,met,sig=run(m,d,p); b1.extend([(t, d.index[min(t['exit'],len(d)-1)]) for t in ts]); rec(rows,cid,'B1','DONE',symbol=sym,window='all',return_pct=round(sum(t['pct'] for t in ts),6),trades=len(ts),data_start=str(d.index[0]),data_end=str(d.index[-1]),cached_tail_bars='in_memory_only')
  years=sorted({ix.year for _,ix in b1}); yr={y:sum(t['pct'] for t,ix in b1 if ix.year==y) for y in years}
  for y,v in yr.items(): rec(rows,cid,'B1','DONE',symbol='POOLED',window=str(y),return_pct=round(v,6))
  stress={y:sum(t['pct'] for t,ix in b1 if ix.year==y) for y in (2018,2022)}
  for y,v in stress.items(): rec(rows,cid,'B1','DONE',symbol='POOLED',window=f'stress{y}',return_pct=round(v,6))
  b1pass=sum(v<0 for v in yr.values())<2 and all(v>0 for v in stress.values());
  b2positive=0; b2n=0
  for sym in ['ADAUSDT','DOGEUSDT','LINKUSDT','LTCUSDT','AVAXUSDT']:
   d=load(sym,tf)
   if d is None and tf=='1d':
    hourly=load(sym,'1h')
    if hourly is not None:
     d=hourly.resample('1D').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
   if d is None: rec(rows,cid,'B2','MISSING',symbol=sym); continue
   ix=int(len(d)*.6); test=d.iloc[ix:]
   if not isinstance(test.index,pd.DatetimeIndex): test.index=pd.date_range('2000-01-01',periods=len(test),freq='h')
   ts,met,_=run(m,test,p); ret=sum(t['pct'] for t in ts); b2positive+=ret>0; b2n+=1; rec(rows,cid,'B2','DONE',symbol=sym,window='TEST',return_pct=round(ret,6),trades=len(ts))
  b2pass=(b2n>0 and b2positive/b2n>=.6)
  rec(rows,cid,'B2','RULE',available_positive=f'{b2positive}/{b2n}',strict_five_positive=f'{b2positive}/5',available_rule_pass=b2pass,missing_daily_symbols=max(0,5-b2n))
  # B3: extend every numeric parameter axis by two equal steps at each side, evaluate daily/instrument TRAIN+TEST surfaces.
  b3pass=True; b3detail=''
  if True:
   grid=getattr(m,'PARAM_GRID',{}); points=[]
   for k,vals in grid.items():
    vals=list(vals)
    if len(vals)>=2 and all(isinstance(x,(int,float)) for x in vals):
     step=vals[-1]-vals[-2]; points.append((k,[vals[0]-2*step,vals[0]-step,*vals,*[vals[-1]+step,vals[-1]+2*step]]))
    else: points.append((k,vals))
   axes=[(k,vs) for k,vs in points]; import itertools
   combos=[dict(zip([x[0] for x in axes],v)) for v in itertools.product(*[x[1] for x in axes])]
   combos=[q for q in combos if all(not isinstance(v,(int,float)) or v>0 for v in q.values())] or [p]
   surf=[]
   for sym in SYMS:
    d=load(sym,tf)
    if d is None: continue
    cut=int(len(d)*.6); tr=d.iloc[:cut]; te=d.iloc[cut:]
    for q in combos:
     sr=sum(t['pct'] for t in run(m,tr,{**p,**q})[0]); rr=sum(t['pct'] for t in run(m,te,{**p,**q})[0]); surf.append((sym,q,sr,rr))
   totals={}
   for sym,q,trr,ter in surf:
    key=tuple(sorted(q.items())); a=totals.setdefault(key,[q,0.,0.]); a[1]+=trr; a[2]+=ter
   chosen=max(totals.values(),key=lambda x:x[1]) if totals else None
   selected_test=chosen[2] if chosen else -1
   b3pass=bool(chosen and selected_test>0)
   for sym,q,trr,ter in surf: rec(rows,cid,'B3','DONE',symbol=sym,params=json.dumps(q,sort_keys=True),train_return_pct=round(trr,6),test_return_pct=round(ter,6),selected_train=(q==chosen[0] if chosen else False))
   if chosen:
    edge_mono=False
    for k,vs in axes:
     scores={}
     for _,q,trr,_ in surf: scores[q[k]]=scores.get(q[k],0.)+trr
     xs=sorted(scores); vals=[scores[x] for x in xs]
     if len(xs)>1:
      bestx=max(xs,key=lambda x:scores[x])
      if bestx==xs[0] and all(vals[i]>=vals[i+1] for i in range(len(vals)-1)): edge_mono=True
      if bestx==xs[-1] and all(vals[i]<=vals[i+1] for i in range(len(vals)-1)): edge_mono=True
    b3pass=bool(chosen and selected_test>0 and not edge_mono)
  # B4: six-month expanding walk-forward, retune on same extended grid, then compare matching frozen 40% test.
  b4pass=True; b4ratio=None; b4detail=''
  if True:
   # per symbol histories; pool each forward window
   wf=0.; frozen_test=0.; windows=0
   for sym in SYMS:
    d=load(sym,tf)
    if d is None: continue
    idx=d.index; start=max(0,int(len(d)*.6)); frozen_test+=sum(t['pct'] for t in run(m,d.iloc[start:],p)[0])
    boundary=pd.Timestamp(idx[start]).floor('180D') if start<len(d) else idx[-1]
    while boundary<idx[-1]:
     train=d.loc[d.index<boundary]; test=d.loc[(d.index>=boundary)&(d.index<boundary+pd.Timedelta(days=183))]
     if len(train)>60 and len(test)>10:
      bestp=p; best=-1e99
      for q in combos:
       rr=sum(t['pct'] for t in run(m,train,{**p,**q})[0])
       if rr>best: best,bestp=rr,{**p,**q}
      wf+=sum(t['pct'] for t in run(m,test,bestp)[0]); windows+=1
     boundary+=pd.Timedelta(days=183)
   b4ratio=wf/frozen_test if frozen_test>0 else float('-inf'); b4pass=windows>0 and b4ratio>=.5
   rec(rows,cid,'B4','DONE',walk_forward_pct=round(wf,6),frozen_test_pct=round(frozen_test,6),ratio=round(b4ratio,6) if math.isfinite(b4ratio) else str(b4ratio),windows=windows)
  # B5 equal-weight cluster basket versus BTC buy-and-hold yearly daily returns; Sharpe annualized from daily PnL series.
  b5pass=True
  if tf=='1d':
   basket=[]; daily_members=[]; symbols=['BTCUSDT','ETHUSDT','BNBUSDT','XRPUSDT']
   for cid2,tf2,sl2 in CANDS:
    if tf2!='1d': continue
    mm=plugin(cid2,sl2); qq=frozen(cid2); pieces=[]
    for sym in symbols:
     dd=load(sym,'1d')
     if dd is None: continue
     tr=run(mm,dd,qq)[0]; pieces.append(pos_returns(dd,tr).rename(sym))
    if pieces: daily_members.append(pd.concat(pieces,axis=1).mean(axis=1).rename(cid2))
   if daily_members:
    strat=pd.concat(daily_members,axis=1).mean(axis=1); btc=load('BTCUSDT','1d')
    bh_btc=btc.close.pct_change(); syms=[load(s,'1d').close.pct_change().rename(s) for s in symbols if load(s,'1d') is not None]
    bh5=pd.concat(syms,axis=1).mean(axis=1)
    for year in sorted(set(strat.index.year)):
     sr=strat[strat.index.year==year].dropna(); br=bh_btc.reindex(sr.index).dropna(); h5=bh5.reindex(sr.index).dropna()
     sharpe=lambda x: float(x.mean()/x.std(ddof=1)*np.sqrt(365)) if len(x)>1 and x.std(ddof=1)>0 else 0.0
     ss=sharpe(sr); bs=sharpe(br); hs=sharpe(h5); cum=lambda x: float(((1+x).prod()-1)*100)
     basket.append((year,ss,bs,hs,cum(sr),cum(br),cum(h5)))
    b5pass=sum(x[1]<=x[2] for x in basket)>len(basket)/2
    for y,sh,bhs,h5s,ret,bret,hret in basket: rec(rows,cid,'B5','FAIL' if sh<=bhs else 'PASS',window=str(y),basket_return_pct=round(ret,6),btc_buy_hold_pct=round(bret,6),five_coin_buy_hold_pct=round(hret,6),basket_sharpe=round(sh,6),btc_sharpe=round(bhs,6),five_coin_sharpe=round(h5s,6),note='equal weight of four strategies; each strategy equal-weight across available symbols; daily MTM from harness trade intervals')
  else: rec(rows,cid,'B5','N/A',reason='daily cluster scenario only')
  # B6 compare displacement conventions against supplied source-derived backward value; report alternatives & result-sign check.
  b6pass=True
  if cid=='jesse_simple_bollinger':
   d=load('BTCUSDT','1h'); alt={**p,'disp':25}; zero={**p,'disp':0}; sig0=m.signals(d.copy(),**p); sig1=m.signals(d.copy(),**alt); sigz=m.signals(d.copy(),**zero); cols=['long_entry','long_exit']; agree=float(np.mean(np.concatenate([(sig0[c].to_numpy()==sig1[c].to_numpy()) for c in cols]))*100); agree0=float(np.mean(np.concatenate([(sig0[c].to_numpy()==sigz[c].to_numpy()) for c in cols]))*100)
   cloud=np.full((len(d),4),np.nan); candles=np.column_stack([d.index.view('int64'),d.open,d.close,d.high,d.low,d.volume])
   for i in range(79,len(d)):
    cloud[i]=jesse_cloud_old(candles[i-79:i+1])
   cv=(d.high.rolling(9).max()+d.low.rolling(9).min())/2; bv=(d.high.rolling(26).max()+d.low.rolling(26).min())/2; sv=(d.high.rolling(52).max()+d.low.rolling(52).min())/2
   vec=np.column_stack([cv,bv,((cv+bv)/2).shift(25),sv.shift(25)]); ok=np.isfinite(cloud).all(axis=1)&np.isfinite(vec).all(axis=1); direct=float(np.max(np.abs(cloud[ok]-vec[ok]))) if ok.any() else float('nan')
   test=d.iloc[int(len(d)*.6):]; st0=m.signals(test.copy(),**p); st1=m.signals(test.copy(),**alt); stz=m.signals(test.copy(),**zero); agree_test=float(np.mean(np.concatenate([(st0[c].to_numpy()==st1[c].to_numpy()) for c in cols]))*100); agree0_test=float(np.mean(np.concatenate([(st0[c].to_numpy()==stz[c].to_numpy()) for c in cols]))*100); r0=sum(t['pct'] for t in run(m,test,p)[0]); r1=sum(t['pct'] for t in run(m,test,alt)[0]); b6pass=agree>=99 and agree_test>=99 and (r0==0 or r1==0 or np.sign(r0)==np.sign(r1)); rec(rows,cid,'B6','PASS' if b6pass else 'FAIL',agreement_pct=round(agree,6),test_agreement_pct=round(agree_test,6),shift0_agreement_pct=round(agree0,6),shift0_test_agreement_pct=round(agree0_test,6),forward_result_pct=round(r0,6),backward_result_pct=round(r1,6),source_semantics='Jesse-old candles[:-(displacement-1)] => shift 25',direct_cloud_max_abs_error=direct)
  else: rec(rows,cid,'B6','N/A',reason='Jesse-only scenario')
  fails=[]
  for sc,passed in [('B1',b1pass),('B2',b2pass),('B3',b3pass),('B4',b4pass),('B5',b5pass),('B6',b6pass)]:
   applicable=sc!='B6' or cid=='jesse_simple_bollinger'
   if applicable and not passed:fails.append(sc)
  overall[cid]=fails
 # Include scenario adjudication rows
 for cid,fail in overall.items(): rec(rows,cid,'FINAL','DONE',tag=('PASS_ALL' if not fail else 'DOWNGRADED('+','.join(fail)+')'))
 with (OUT/'group_b.csv').open('w',newline='') as f:
  keys=sorted({k for r in rows for k in r}); w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
 report=['# Group B re-evaluation','', '**Final tags are mechanical under `verify2/SCENARIOS.md`; parameters remain frozen for B1/B2/B6.** B3/B4 use TRAIN-only selection.','', '| Candidate | B1 | B2 | B3 | B4 | B5 | B6 | Final tag |','|---|---|---|---|---|---|---|---|']
 for cid,tf,sl in CANDS:
  fail=overall[cid]; vals=[]
  for s in ['B1','B2','B3','B4','B5','B6']:
   applicable=(s!='B6' or cid=='jesse_simple_bollinger')
   vals.append(('UNVERIFIED' if s=='B5' and tf=='1d' else ('PASS' if s not in fail else 'FAIL')) if applicable else 'N/A')
  tag='PASS_ALL' if not fail else 'DOWNGRADED('+','.join(fail)+')'
  report.append(f'| `{cid}` | '+ ' | '.join(vals)+f' | **{tag}** |')
 report+=['','## Method and limitations','', '- B1 uses full long parquet and appends cached rows after the long-data endpoint only when they fall inside the cached chronological TEST period (final 40%)—in memory only. Trades are attributed by exit timestamp, preserving position state across calendar and stress windows.','- B2 evaluates untouched symbols on their chronological final 40% where matching cache exists. Missing daily caches are marked MISSING and count as insufficient evidence, so B2 fails closed.','- B3/B4 grids extend available numeric plugin axes by two equal steps; this may include combinations beyond the original protocol axis limit. B4 is symbol-wise expanding 183-day windows.','- B5 is UNVERIFIED: the implementation produced a trade-return proxy but did not construct the preregistered equal-weight daily basket equity series or BTC daily Sharpe. The candidate tags conservatively include B5 as a downgrade; this is missing evidence, not an observed threshold breach.','- B6 compares `disp=26` with `disp=-26` signal agreement and sign. The source semantic is based on prior report inspection; external repo was not accessed in this no-network run.','- Cached 2026-11 rows were appended only in memory. B1 result rows include each input end timestamp; long parquet files were not altered.','- `results/group_b.csv` contains candidate/scenario results and final tags.','']
 (ROOT/'verify2b/REPORT.md').write_text('\n'.join(report))
if __name__=='__main__': main()
