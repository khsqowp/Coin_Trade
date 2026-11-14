#!/usr/bin/env python3
"""Independent, offline reproduction of selected Coin_Trade US stock strategies.

Inputs are Yahoo daily parquet files, adjusted via adjclose/close. This script
does not import or modify Coin_Trade source and has no network/order code.
"""
import os, glob, json, hashlib, datetime, math
import numpy as np
import pandas as pd

DATA=os.environ.get('DATA_DIR','/data'); OUT=os.environ.get('OUT_DIR','/out')
START=pd.Timestamp('2022-01-03'); END=pd.Timestamp('2026-10-30')
FEES={'KIS_approx_0.36pct_each_side':0.0036,'low_cost_0.08pct_each_side':0.0008}
ANN=252

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()

def metrics(eq):
 s=eq.dropna(); s=s.loc[START:END]
 if len(s)<30:return {}
 s=s/s.iloc[0]; yrs=(s.index[-1]-s.index[0]).days/365.25
 rr=s.pct_change().dropna(); peak=s.cummax()
 yr=s.groupby(s.index.year).last(); prev=yr.shift(1); prev.iloc[0]=s.iloc[0]; yr=yr/prev-1
 mo=s.resample('ME').last().pct_change().dropna()
 cagr=float(s.iloc[-1]**(1/yrs)-1) if yrs>0 else None
 mdd=float((1-s/peak).max())
 return {'start':str(s.index[0].date()),'end':str(s.index[-1].date()),'bars':len(s),'years':yrs,
         'final_multiple':float(s.iloc[-1]),'cagr':cagr,'max_drawdown':mdd,
         'sharpe_daily_252':float(rr.mean()/rr.std()*np.sqrt(ANN)) if rr.std()>0 else 0.0,
         'calmar':float(cagr/mdd) if mdd>0 else None,'months_positive_fraction':float((mo>0).mean()) if len(mo) else None,
         'yearly_returns':{str(int(k)):float(v) for k,v in yr.items()}}

def read_universe():
 files=sorted(glob.glob(DATA+'/*.parquet')); eq=[]; audit=[]; metas={}
 for fp in files:
  sym=os.path.basename(fp)[:-8]; mp=os.path.join(DATA,sym+'.meta.json')
  try:
   meta=json.load(open(mp)); metas[sym]=meta
   if meta.get('vendor',{}).get('instrumentType')!='EQUITY':
    audit.append({'symbol':sym,'instrument_type':meta.get('vendor',{}).get('instrumentType'),'included':False,'reason':'not_metadata_EQUITY'}); continue
   d=pd.read_parquet(fp); d.index=pd.to_datetime(d.index).tz_localize(None).normalize(); d=d[~d.index.duplicated(keep='last')].sort_index()
   raw=d['close'].astype(float); adj=d['adjclose'].astype(float)
   valid=raw.gt(0)&adj.gt(0)&adj.notna()
   pre=int((valid & (d.index<START)).sum()); last=d.index[valid][-1] if valid.any() else pd.NaT
   reasons=[]
   if pre<200: reasons.append(f'warmup_valid_adjusted_close_{pre}_lt_200')
   if pd.isna(last) or last<END: reasons.append(f'last_valid_row_before_2026-10-30:{last.date() if pd.notna(last) else "none"}')
   inc=not reasons
   audit.append({'symbol':sym,'instrument_type':'EQUITY','included':inc,'pre_start_valid_bars':pre,'first':str(d.index[valid][0].date()) if valid.any() else None,'last':str(last.date()) if pd.notna(last) else None,'reason':'included' if inc else ';'.join(reasons)})
   if inc:
    ratio=(adj/raw).replace([np.inf,-np.inf],np.nan)
    x=pd.DataFrame(index=d.index)
    for col in ('open','high','low','close'): x[col]=(d[col].astype(float)*ratio)
    x['volume']=d['volume'].astype(float); x['adjclose']=adj
    eq.append((sym,x))
  except Exception as e:
   audit.append({'symbol':sym,'included':False,'reason':'read_error:'+repr(e)})
 if not eq: raise RuntimeError('No eligible EQUITY parquet files')
 dates=pd.DatetimeIndex(sorted(set().union(*(set(x.index) for _,x in eq))))
 syms=[s for s,_ in eq]; panels={c:pd.DataFrame(index=dates,columns=syms,dtype=float) for c in ['open','high','low','close','volume']}
 for s,x in eq:
  for c in panels: panels[c].loc[x.index,s]=x[c]
 return panels,syms,audit,metas,files

def cross(a,b): return (a>b)&~(a.shift(1)>b.shift(1)), (a<b)&~(a.shift(1)<b.shift(1))

def strategy_signals(P):
 C=P['close'].ffill(); H=P['high'].ffill(); L=P['low'].ffill(); V=P['volume']
 e9=C.ewm(span=9,adjust=False).mean(); e21=C.ewm(span=21,adjust=False).mean(); sma200=C.rolling(200,min_periods=200).mean()
 up,dn=cross(e9,e21); signals={}
 signals['S3_sig_trx_EMA9_21_stop12_slots20']=(up.fillna(False),np.zeros(C.shape),dn.fillna(False),20,.12,None)
 signals['S4_sig_swing6_EMA9_21_close_gt_SMA200_slots6_TP8_SL4']=( (up&(C>sma200)).fillna(False), ((C-sma200)/sma200).to_numpy(),dn.fillna(False),6,.04,.08)
 ef=C.ewm(span=10,adjust=False).mean(); em=C.ewm(span=50,adjust=False).mean(); es=C.ewm(span=200,adjust=False).mean()
 dipped=(L<=ef).rolling(10,min_periods=1).max().astype(bool); reclaim=(C>ef)&(C>H.shift(1))
 ent=((ef>em)&(em>es)&dipped&reclaim).fillna(False); ex=(C<em).fillna(False); rs90=(C/C.shift(90)-1)
 signals['S5_sig_mach7_10_50_200_win10_exitEMA50_RS90_top5_SL8']=(ent,rs90.to_numpy(),ex.to_numpy(),5,.08,None)
 s20=C.rolling(20,min_periods=20).mean(); gap=(s20-sma200).abs()/sma200*100
 sq=(gap<=3).rolling(10,min_periods=1).max().astype(bool); whips=((s20>sma200)!=(s20>sma200).shift(1)).rolling(20,min_periods=1).sum()>3
 ab=C>s20; cu=ab&~ab.shift(1).fillna(False).astype(bool)
 ent=(cu&(C>sma200)&sq&~whips).fillna(False); ex=(~ab).fillna(False)
 signals['S5_sig_squeeze_RS90_top5']=(ent,rs90.to_numpy(),ex.to_numpy(),5,None,None)
 ma=C.rolling(10,min_periods=10).mean(); turnover=C*V; ratio=turnover/turnover.rolling(60,min_periods=20).mean(); ab=C>ma; cu=ab&~ab.shift(1).fillna(False).astype(bool)
 ent=(cu&(ratio>=1.5)).fillna(False); ex=(~ab).fillna(False)
 signals['S5_sig_pullback_MA10_volfilter_top5_SL3_TP6']=(ent,(C/C.shift(20)-1).to_numpy(),ex.to_numpy(),5,.03,.06)
 return signals,C,sma200

def run_slots(P,entry,score,exit_sig,slots,fee,sl,tp):
 O,H,L,C=[P[k].to_numpy(float) for k in ('open','high','low','close')]; T,N=C.shape
 cash=1.; pos={}; out=np.empty(T); trades=[]; turnover=costs=0.
 for t in range(T):
  for i in list(pos):
   p=pos[i]; c=C[t,i]
   if not np.isfinite(c):continue
   o,h,l=c if False else (O[t,i],H[t,i],L[t,i])
   px=None
   if p['stop'] is not None and l<=p['stop']: px=min(p['stop'],o)
   elif p['tp'] is not None and h>=p['tp']: px=max(p['tp'],o)
   if px is None and t>=1 and exit_sig[t-1,i]: px=c
   if px is not None:
    gross=p['qty']*px; cash+=gross*(1-fee); ref=out[t-1] if t else 1.; costs+=gross*fee/max(ref,1e-9); turnover+=gross/max(ref,1e-9); trades.append(px/p['entry']-1-2*fee); del pos[i]
  if t>=1 and len(pos)<slots:
   eqv=cash+sum(p['qty']*(C[t,i] if np.isfinite(C[t,i]) else p['entry']) for i,p in pos.items()); cand=[]
   for i in np.where(entry[t-1])[0]:
    if i not in pos and np.isfinite(C[t,i]) and np.isfinite(score[t-1,i]):cand.append((score[t-1,i],i))
   cand.sort(reverse=True)
   for _,i in cand:
    if len(pos)>=slots:break
    px=C[t,i]; alloc=min(eqv/slots,cash)
    if alloc<=0:break
    st=px*(1-sl) if sl is not None else None; take=px*(1+tp) if tp is not None else None
    qty=alloc/px; cst=alloc*fee; cash-=alloc+cst; ref=out[t-1] if t else 1.; costs+=cst/max(ref,1e-9);turnover+=alloc/max(ref,1e-9)
    pos[i]={'qty':qty,'entry':px,'stop':st,'tp':take}
  out[t]=cash+sum(p['qty']*(C[t,i] if np.isfinite(C[t,i]) else p['entry']) for i,p in pos.items())
 return pd.Series(out,index=P['close'].index),trades,turnover,costs

def run_momentum(P,fee):
 C=P['close'].ffill(); dates=C.index; T,N=C.shape; ret=C/C.shift(60)-1
 # Coin_Trade rs_us S1: universe equal-weight close-return proxy and SMA200 filter.
 daily=C.pct_change(fill_method=None); idxret=daily.mean(axis=1).fillna(0); idx=(1+idxret).cumprod(); bad=(idx<idx.rolling(200,min_periods=200).mean()).fillna(False).to_numpy()
 R=C.pct_change(fill_method=None).fillna(0).to_numpy(copy=True); R[~np.isfinite(R)]=0.
 phases=[]
 for off in (0,7,14):
  tgt=np.full((T,N),np.nan); base=np.zeros(N); prev=False
  for t in range(T):
   reb=t%21==off
   if reb:
    sc=ret.iloc[t].to_numpy(); ok=np.isfinite(sc); w=np.zeros(N)
    if ok.sum()>=10:
     top=np.argsort(np.where(ok,sc,-np.inf))[::-1][:5]; w[top]=.2
    base=w
   if reb or bad[t]!=prev:tgt[t]=base*(0 if bad[t] else 1)
   prev=bad[t]
  # source engine: target decided at close, executes after 1 daily bar at close
  v=np.zeros(N); cash=1.; eq=np.empty(T); to=cost=0.
  for t in range(T):
   v*=1+R[t]; cur=cash+v.sum()
   if t-1>=0 and np.isfinite(tgt[t-1,0]):
    target=np.nan_to_num(tgt[t-1])*cur; traded=np.abs(target-v).sum(); c=traded*fee; cost+=c/max(cur,1e-9);to+=traded/max(cur,1e-9);cur-=c;v=np.nan_to_num(tgt[t-1])*cur;cash=cur-v.sum()
   eq[t]=cash+v.sum()
  phases.append((np.diff(eq,prepend=1)/np.concatenate(([1.],eq[:-1])),to,cost))
 avgret=np.mean([x[0] for x in phases],axis=0); eq=pd.Series(np.cumprod(1+avgret),index=dates)
 return eq,float(np.mean([x[1] for x in phases])),float(np.mean([x[2] for x in phases]))

def main():
 os.makedirs(OUT,exist_ok=True); P,syms,audit,metas,allfiles=read_universe(); pd.DataFrame(audit).sort_values('symbol').to_csv(OUT+'/universe_eligibility.csv',index=False)
 # Limit engine to last input row 2026-11-03 but summarize on the common 2026-10-30 close.
 dates=P['close'].index; signals,C,sma200=strategy_signals(P); results=[]; curves={}
 for name,(ent,score,ex,slots,sl,tp) in signals.items():
  for fee_name,fee in FEES.items():
   eq,tr,to,cost=run_slots(P,ent.to_numpy(bool),np.asarray(score,dtype=float),np.asarray(ex,dtype=bool),slots,fee,sl,tp)
   curves[(name,fee_name)]=eq
   m=metrics(eq); m.update({'strategy':name,'fee_scenario':fee_name,'fee_each_side':fee,'fill':'signal at t close; execute t+1 close; daily high/low stop/take, stop prioritized; gap through stop/take fills at open','trade_count':len(tr),'mean_trade_net':float(np.mean(tr)) if tr else None,'turnover_x_per_year':float(to/max(m.get('years',1),1e-9)),'cost_drag_x_per_year':float(cost/max(m.get('years',1),1e-9)),'slots':slots,'stop_pct':sl,'take_pct':tp})
   results.append(m)
 for fee_name,fee in FEES.items():
  eq,to,cost=run_momentum(P,fee); m=metrics(eq); m.update({'strategy':'S1_momentum_L60_K5_rebalance21_filter_SMA200_long_only_US_phases_0_7_14_mean','fee_scenario':fee_name,'fee_each_side':fee,'fill':'source run_weights: target from close t executes at close t+1; 3 equity-return curves averaged over phases 0,7,14','turnover_x_per_year':float(to/max(m.get('years',1),1e-9)),'cost_drag_x_per_year':float(cost/max(m.get('years',1),1e-9)),'lookback_days':60,'top_k':5,'rebalance_days':21,'market_filter':'equal-weight eligible-universe return proxy below SMA200 -> cash'});results.append(m)
 pd.DataFrame(results).to_csv(OUT+'/strategy_metrics.csv',index=False)
 # Persist daily normalized equity and returns, restricted to evaluation dates.
 for (name,fee),eq in curves.items():
  v=eq.loc[START:END];v=(v/v.iloc[0]);v.rename('equity').to_frame().to_csv(OUT+'/curve_'+name+'_'+fee+'.csv',index_label='date')
 # S1 curves saved separately
 for fee_name,fee in FEES.items():
  eq,_,_=run_momentum(P,fee);v=eq.loc[START:END];(v/v.iloc[0]).rename('equity').to_frame().to_csv(OUT+'/curve_S1_'+fee_name+'.csv',index_label='date')
 used=[os.path.join(DATA,s+'.parquet') for s in syms]+[os.path.join(DATA,s+'.meta.json') for s in syms]
 src=['/src/app/rs_us_engine.py','/src/app/rs_us_run.py','/src/app/rs_kr_strats.py']
 source_hashes={p.replace('/src','/home/opc/Coin_Trade'):sha(p) for p in src if os.path.isfile(p)}
 # Metadata records input source file hashes from provider metadata and full file hashes separately.
 input_hashes={s:{'parquet_sha256':sha(os.path.join(DATA,s+'.parquet')),'provider_meta_sha256':metas[s].get('sha256'),'source':metas[s].get('source'),'instrumentType':metas[s].get('vendor',{}).get('instrumentType'),'last_file_date':metas[s].get('last')} for s in syms}
 dates_ready=[str(pd.Timestamp(metas[s].get('last')).date()) for s in syms if metas[s].get('last')]
 manifest={'run_id':'cointrade_us_independent_2026-11-05','market':'US','universe_claim':'server file universe; not all US exchanges','evaluated_symbols':len(syms),'source_file_parquet_count':len(allfiles),'equity_metadata_candidates':sum(1 for x in audit if x.get('instrument_type')=='EQUITY'),'included':len(syms),'excluded_count':len(audit)-len(syms),'eligibility_rule':'metadata instrumentType=EQUITY; >=200 valid adjusted-close rows before 2022-01-03; last valid row >= 2026-10-30','evaluation_start':str(START.date()),'evaluation_end':str(END.date()),'latest_input_row_max':max(dates_ready) if dates_ready else None,'input_files_max_latest_row':'2026-11-03','warmup':'all available rows before start; valid adjusted close=close*adjclose/close','ohlc_adjustment':'all OHLC multiplied by adjclose/close; volume unadjusted','fees_each_side':FEES,'strategies':'see strategy_metrics.csv; Coin_Trade US formulas independently ported from rs_kr_strats defaults per main spec','cointrade_source_hashes':source_hashes,'input_hashes':input_hashes,'script_sha256':sha(__file__),'cross_market_caveat':'US source fills at next close; KR source fills next open. S1 US averages 0/7/14 phase equity returns; KR uses one start-anchored phase. Cross-market raw return comparisons are limited.','execution':'offline one-off read-only data container; no network, no service restart, no trading/orders'}
 with open(OUT+'/manifest.json','w') as f:json.dump(manifest,f,indent=2)
 print(json.dumps({'symbols':len(syms),'equity_candidates':manifest['equity_metadata_candidates'],'excluded':manifest['excluded_count'],'dates':{'start':str(START.date()),'end':str(END.date()),'latest_input':manifest['latest_input_row_max']},'metrics':len(results),'source_hashes':source_hashes,'script_sha256':manifest['script_sha256']},indent=2))
if __name__=='__main__':main()
