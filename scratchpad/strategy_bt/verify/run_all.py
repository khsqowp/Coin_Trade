"""Regenerate the adversarial verification tables from local parquet and harness summaries."""
import csv,json,sys,itertools
from pathlib import Path
import numpy as np,pandas as pd
import reimpl as R
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parents[2]; DATA=ROOT.parent/'bb_stoch_stc'/'data'; OUT=ROOT/'verify'
SYMS=['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT']
def write(name,rows):
 pd.DataFrame(rows).to_csv(OUT/name,index=False)
def summary_rows():
 d={}
 for p in (ROOT/'results').glob('slice_*/summary.csv'):
  for r in csv.DictReader(p.open()):
   if r['strategy_id'] in R.IDS and r['raw_verdict']=='PASS': d[r['strategy_id'],r['timeframe']]=r
 return d
def indicators_neighbors(sid,p):
 vals={}
 for k,v in p.items():
  if isinstance(v,(int,float)) and not isinstance(v,bool):
   if k in ('k','thr','factor','stop_n','stop_mult'): a=[round(float(v)*x,5) for x in (.7,.85,1,1.15,1.3)]
   else: a=[max(1,int(round(float(v)*x))) for x in (.7,.85,1,1.15,1.3)]
   vals[k]=list(dict.fromkeys(a))
 if len(vals)>3:
  vals={}
  for k,v in p.items():
   if isinstance(v,(int,float)) and not isinstance(v,bool):
    vals[k]=list(dict.fromkeys(max(1,int(round(v*x))) if isinstance(v,int) else round(float(v)*x,5) for x in (.7,1,1.3)))
 return vals
def run():
 sums=summary_rows(); trades_by={}; infos={}; repro=[]; bet=[];sub=[];neighbor=[];stress=[]; daily_series={}; bench_daily={}
 for sid in R.IDS:
  tf=R.TF.get(sid,'1d'); raw=sums.get((sid,tf)); frozen=json.loads(raw['params']) if raw else R.PARAMS[sid]; side=R.SIDE.get(sid,'both'); frames={}; alltr=[]; splitdata={}
  for sym in SYMS:
   d=pd.read_parquet(DATA/f'{sym}_{tf}.parquet'); cut=int(len(d)*.6); tr=d.iloc[:cut].copy(); te=d.iloc[cut:].copy(); frames[sym]=(tr,te,d); splitdata[sym]=cut
   for part,df in [('train',tr),('test',te)]:
    sig=R.SIGNALS[sid](df,**frozen); ts=R.simulate(df,sig,side=side); 
    for t in ts: t['symbol']=sym;t['part']=part;t['entry_abs']=t['entry']+(0 if part=='train' else cut);t['exit_abs']=t['exit']+(0 if part=='train' else cut)
    alltr.extend(ts)
  trades_by[sid]=alltr; test=[x for x in alltr if x['part']=='test']; train=[x for x in alltr if x['part']=='train']; testret=sum(x['pct'] for x in test); trainret=sum(x['pct'] for x in train)
  ref=float(raw['test_return']) if raw and raw.get('test_return') else 0.; rel=abs(testret-ref)/max(abs(ref),1e-9); nref=int(float(raw['test_trades'])) if raw else 0; nrel=abs(len(test)-nref)/max(1,nref); reproduce=rel<=.15 and nrel<=.15
  reason='Independent spec implementation differs from plugin/harness behavior; see diagnosis' if not reproduce else 'Return and trade count within 15%';
  if sid=='btc-ema-5-30' and not reproduce: reason='Plugin extends crossover entries one bar to accommodate next-open reversal; independent implementation initially omitted this harness workaround; plugin deviation explains trade-count/return mismatch.'
  if sid=='btc-macd-15-41-12' and not reproduce: reason='Plugin uses sticky one-bar reversal entry workaround; independent implementation does not fully reproduce it; test return alone is within 15%, but trade count is checked too.'
  if sid=='turtle-system-1' and not reproduce: reason='Plugin uses a hypothetical prior-trade winner filter plus always-active 55-day fallback; independent literal channel proxy omits that state machine, causing the mismatch. This is an independent reimplementation gap, not evidence of a plugin defect.'
  if sid=='c4-ema-supertrend': reason='Spec JSON is lossy; implemented source-derived EMA rule. Inspect plugin shows explicit recovered Pine rule.'
  if sid=='c4-strategy-myth-busting-12-osgfc-supertrend-myn': reason='Spec JSON omits executable equations; independent proxy is not equivalent to plugin source-derived OSGFC/Supertrend; discrepancy is reimplementation limitation.'
  trainref=float(raw['train_return']) if raw else np.nan; trainrel=abs(trainret-trainref)/max(abs(trainref),1e-9) if raw else np.nan
  repro.append(dict(strategy_id=sid,timeframe=tf,frozen_params=json.dumps(frozen,sort_keys=True),summary_train_return=trainref,reimpl_train_return=trainret,train_abs_diff=trainret-trainref,relative_train_diff=trainrel,train_return_over_15pct=bool(trainrel>.15) if raw else True,summary_test_return=ref,reimpl_test_return=testret,relative_test_diff=rel,summary_trades=nref,reimpl_trades=len(test),relative_trade_diff=nrel,test_return_over_15pct=rel>.15,trade_count_over_15pct=nrel>.15,reproduced=reproduce,diagnosis=reason))
  exp=0.; bh=0.; longp=shortp=0.; b_rows=[]
  for sym,(tr,te,full) in frames.items():
   ts=[x for x in test if x['symbol']==sym]; lp=sum(x['pct'] for x in ts if x['side']=='long');sp=sum(x['pct'] for x in ts if x['side']=='short');longp+=lp;shortp+=sp
   frac=sum((x['exit_abs']-x['entry_abs']+1) for x in ts)/max(1,len(te)); frac=min(1.,frac)
   b=(te.close.iloc[-1]/te.open.iloc[0]-1)*10 # % capital at 1000 notional
   bh+=b;exp+=frac*b;b_rows.append((sym,frac,b,lp+sp))
   bet.append(dict(strategy_id=sid,symbol=sym,long_pnl=lp,short_pnl=sp,exposure_fraction=frac,exposure_days=frac*len(te),return_per_exposure_day=(lp+sp)/(frac*len(te)) if frac else 0,buy_hold_return=b,exposure_scaled_bh=frac*b))
  beta_only=longp<=exp*1.3 and shortp<=0 and longp>=exp*.7
  for row in bet[-len(SYMS):]:
   if row['strategy_id']==sid:
    row['strategy_long_profit_exceeds_scaled_bh']=longp>exp*1.3
    row['beta_only_rule']=beta_only
  # Subperiod attribution by trade exit timestamp; positive-contributor denominator for concentration.
  halfvals={}; yearvals={}
  for t in test:
   dt=pd.Timestamp(t['exit_time']); half='first_half' if t['exit_abs']<min(splitdata.values())+(len(next(iter(frames.values()))[1])//2) else 'second_half'
   halfvals[half]=halfvals.get(half,0.)+t['pct']; yearvals[str(dt.year)]=yearvals.get(str(dt.year),0.)+t['pct']
   sub.append(dict(strategy_id=sid,period=half,symbol=t['symbol'],return_pct=t['pct'],exit_time=t['exit_time']))
   sub.append(dict(strategy_id=sid,period=str(dt.year),symbol=t['symbol'],return_pct=t['pct'],exit_time=t['exit_time']))
  def topshare(vals):
   pos=sum(max(0,x) for x in vals.values());return max([max(0,x) for x in vals.values()] or [0])/pos if pos else 0.
  symvals={s:sum(x['pct'] for x in test if x['symbol']==s) for s in SYMS}; top_sym=topshare(symvals); top_sub=max(topshare(halfvals),topshare(yearvals))
  # Nearby parameter combinations; unchanged frozen baseline included, no selection.
  axes=indicators_neighbors(sid,frozen); combos=list(itertools.product(*axes.values())) if axes else [()]; keys=list(axes); npos=0; nr=[]; nb=[]
  for combo in combos:
   pp=dict(frozen); pp.update(dict(zip(keys,combo))); ret=0.
   for sym,(_,te,_) in frames.items(): ret+=sum(x['pct'] for x in R.simulate(te,R.SIGNALS[sid](te,**pp),side=side))
   nr.append(ret);npos+=ret>0
  neighbor.append(dict(strategy_id=sid,combos=len(nr),test_profitable_share=npos/len(nr) if nr else 0,median_test_return=float(np.median(nr)) if nr else 0,share_beating_exposure_bh=sum(x>exp for x in nr)/len(nr) if nr else 0,train_baseline_return=trainret,neighbor_returns=json.dumps(nr)))
  for mult in [2,3]:
   stressret=0.
   for sym,(_,te,_) in frames.items(): stressret+=sum(x['pct'] for x in R.simulate(te,R.SIGNALS[sid](te,**frozen),side=side,fee=R.FEE*mult,slippage=R.SLIPPAGE*mult))
   stress.append(dict(strategy_id=sid,cost_multiple=mult,fee_per_side=R.FEE*mult,slippage=R.SLIPPAGE*mult,test_return=stressret))
  infos[sid]=dict(tf=tf,ret=testret,long=longp,short=shortp,bh=bh,exp=exp,beta=beta_only,top_sym=top_sym,top_sub=top_sub,neighbor=npos/len(nr),stress=[r['test_return'] for r in stress if r['strategy_id']==sid and r['cost_multiple']==2][0],repro=reproduce,rel=rel,reason=reason)
  # Daily mark-to-market PnL while positions are open, plus entry/exit friction on event days.
  dr=pd.Series(0.,index=pd.date_range(start=min(f[1].index.min() for f in frames.values()).floor('D'),end=max(f[1].index.max() for f in frames.values()).ceil('D'),freq='D',tz='UTC'))
  for sym,(tr,te,full) in frames.items():
   d=te; ts=[x for x in test if x['symbol']==sym]
   for t in ts:
    a,b=t['entry'],t['exit']; direction=1 if t['side']=='long' else -1; qty=t['qty']; entfill=t['entry_fill']; extfill=t['exit_fill']
    for j in range(a,b+1):
     if j==a: pnl=(d.close.iloc[j]-d.open.iloc[j])*qty*direction+(d.open.iloc[j]-entfill)*qty*direction-entfill*qty*R.FEE
     else: pnl=(d.close.iloc[j]-d.close.iloc[j-1])*qty*direction
     if j==b: pnl+=(extfill-d.close.iloc[j])*qty*direction-extfill*qty*R.FEE
     dt=pd.Timestamp(d.index[j]).floor('D')
     if dt in dr.index:dr.loc[dt]+=pnl/10000.
  daily_series[sid]=dr
 # consolidated outputs
 write('reproduce.csv',repro);write('beta.csv',bet);write('subperiod.csv',sub);write('neighbors.csv',neighbor);write('cost_stress.csv',stress)
 ids=list(daily_series); mat=pd.DataFrame({k:v for k,v in daily_series.items()}).fillna(0); corr=mat.corr(); corr.to_csv(OUT/'correlation.csv')
 # Connected components on correlation > .7
 unseen=set(ids); clusters=[]
 while unseen:
  seed=unseen.pop(); comp={seed}; stack=[seed]
  while stack:
   a=stack.pop()
   for b in list(unseen):
    if corr.loc[a,b]>.7:unseen.remove(b);comp.add(b);stack.append(b)
  clusters.append(sorted(comp))
 # equal-weight long-only buy and hold daily returns, normalized percentage points
 bhparts=[]
 for sym in SYMS:
  d=pd.read_parquet(DATA/f'{sym}_1d.parquet'); cut=int(len(d)*.6); q=d.iloc[cut:]; r=q.close.pct_change().fillna(0); bhparts.append(pd.Series(r.to_numpy()/5,index=pd.DatetimeIndex(q.index).floor('D')))
 bhseries=sum(bhparts); bh_corr=mat.corrwith(bhseries.reindex(mat.index).fillna(0))
 clrows=[dict(cluster=i+1,members=';'.join(c),size=len(c)) for i,c in enumerate(clusters)]
 for sid in ids: clrows.append(dict(cluster='bh_corr',members=sid,size=bh_corr[sid]))
 write('cluster.csv',clrows);mat.to_csv(OUT/'daily_returns.csv',index_label='date')
 # report generated from in-memory projections of the CSV source rows above
 lines=['# Adversarial backtest verification','','All returns are pooled trade net PnL as percent of $10,000 capital. “Reproduced” requires both test-return and test-trade-count differences <=15%; `reproduce.csv` separately flags >15% train-return, test-return, and trade-count gaps. Relative-return denominator is absolute source return. Exposure is occupied bars divided by test bars; benchmark is simple close/open return at $1,000 per symbol. Subperiod trade PnL is attributed to exit time. Concentration shares are largest positive contributor divided by positive contributors’ sum, calculated separately across symbols, test halves, and calendar years; the reported subperiod share is the maximum half/year share. Neighbor medians use independent per-axis ±30% values, up to 5 values; >3 parameters uses 3 values per axis.','','| Candidate | Reproduced? | Long / short | B&H-scaled | Top-symbol | Top-subperiod | Neighbor profitable | 2x cost | Final tag |','|---|---:|---:|---:|---:|---:|---:|---:|---|']
 for sid in R.IDS:
  x=infos[sid]; tag='IRREPRODUCIBLE' if not x['repro'] else ('BETA_ONLY' if x['beta'] else ('FRAGILE' if x['top_sym']>.7 or x['top_sub']>.7 or x['neighbor']<.6 or x['stress']<=0 else 'ROBUST_ALPHA'))
  lines.append(f"| {sid} | {'yes' if x['repro'] else 'no'} ({x['rel']:.1%}) | {x['long']:.2f} / {x['short']:.2f} | {x['exp']:.2f} | {x['top_sym']:.0%} | {x['top_sub']:.0%} | {x['neighbor']:.0%} | {x['stress']:.2f}% | {tag} |")
 lines += ['',f"## Cluster result",'',f"Mark-to-market daily returns are calculated from position open/close price changes, with entry and exit friction on event days, pooled across symbols and resampled to UTC dates. At corr >0.7 connected components: {len(clusters)} components among 12 strategies: "+'; '.join(', '.join(c) for c in clusters)+'. Correlation with equal-weight five-coin daily buy-and-hold is in `cluster.csv`; full matrix in `correlation.csv`.','', '## Definitions and limitations','','- Reimplementation is independent of harness imports. `c4-strategy-myth-busting...` specification does not encode executable OSGFC/Supertrend equations; its independent causal smoothed-slope proxy is not a reproduction of plugin source logic.','- Turtle signals use prior-bar channels and a stop, but do not implement hypothetical prior-breakout winner state or pyramiding. Fixed notional follows the harness rather than original risk-unit sizing.','- The supplied split is per symbol at `int(len*0.6)`. Test halves and years use exit-time trade attribution. Benchmarks use open of first test bar to close of last test bar and are not fee adjusted.','- `beta_only` requires long pnl in [70%,130%] of exposure-scaled B&H and short pnl <=0. FRAGILE concentration >70%, neighbor profit share <60%, or doubled-cost return <=0. IRREPRODUCIBLE takes precedence.','','## Per-candidate notes','']
 for sid in R.IDS: lines.append(f"- `{sid}`: {infos[sid]['reason']} Train reimplementation return {next(r['reimpl_train_return'] for r in repro if r['strategy_id']==sid):.2f}% vs harness {next(r['summary_train_return'] for r in repro if r['strategy_id']==sid):.2f}%; test {infos[sid]['ret']:.2f}%.")
 (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':run()
