"""Frozen exploratory US liquidity-universe study. Backtest only; no orders."""
import sys, json, hashlib, pathlib, subprocess
import numpy as np
import pandas as pd
from types import SimpleNamespace
HERE=pathlib.Path(__file__).resolve().parent
ROOT=pathlib.Path.cwd()
sys.path[:0]=[str(ROOT/"research/us_daily_v2"),str(ROOT/"research/us_daily_v1"),str(ROOT/"src")]
import usbt2 as v2
from tp import usdata
START="2012-06-01"; END="2026-08-18"; NLIST=(50,100,200); COSTS=(0.001,0.0005,0.002,0.004); K=20
REGIMES={"bull_2012_15":("2012-06-01","2015-07-20"),"chop_2015_16":("2015-07-21","2016-12-30"),"q4_2018":("2018-09-21","2018-12-24"),"covid_crash":("2020-02-20","2020-03-23"),"covid_recovery":("2020-03-24","2020-08-10"),"bull_2021":("2021-01-04","2022-01-03"),"bear_2022":("2022-01-04","2022-10-12"),"recovery_bull_2023plus":("2022-10-13","2026-08-18"),"tariff_2025":("2025-02-20","2025-04-08")}

def stat(ret,a=START,b=END):
 r=ret.loc[a:b].dropna()
 if len(r)<2:return {"n":int(len(r))}
 eq=(1+r).cumprod(); mdd=float((eq/eq.cummax()-1).min())
 return {"n":int(len(r)),"total_return":float(eq.iloc[-1]-1),"cagr":float(eq.iloc[-1]**(252/len(r))-1) if eq.iloc[-1]>0 else -1.0,"sharpe":float(r.mean()/r.std(ddof=1)*np.sqrt(252)) if r.std(ddof=1)>0 else None,"max_drawdown":mdd}

def hashfile(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()

def verify_frozen_inputs():
 # A7 binds the strategy script and every imported helper by exact SHA256 before metrics.
 manifest=HERE/"INPUT_HASHES_PRECALC_A7.txt"
 if not manifest.exists():raise RuntimeError("A7 frozen input/dependency hash manifest missing")
 entries=0
 for line in manifest.read_text().splitlines():
  if not line.strip():continue
  parts=line.split(None,1)
  if len(parts)!=2:raise RuntimeError(f"invalid A7 manifest row: {line!r}")
  expected,name=parts;name=name.strip();entries+=1
  if name=="-":
   proc=subprocess.run("sha256sum data/us_daily/*.parquet | sort -k2",shell=True,cwd=ROOT,text=True,capture_output=True,check=True)
   got=hashlib.sha256(proc.stdout.encode()).hexdigest()
  else:
   path=ROOT/name
   if not path.is_file():raise RuntimeError(f"A7 frozen file missing: {name}")
   got=hashfile(path)
  if got!=expected:raise RuntimeError(f"A7 frozen hash mismatch: {name}: expected {expected}, got {got}")
 required={
  "research/us_daily_v3_exploratory_20261108/us_v3.py",
  "research/us_daily_v2/usbt2.py",
  "research/us_daily_v1/usbt.py",
  "src/tp/usdata.py",
 }
 listed={line.split(None,1)[1].strip() for line in manifest.read_text().splitlines() if line.strip() and len(line.split(None,1))==2}
 if not required.issubset(listed):raise RuntimeError(f"A7 manifest missing required provenance files: {sorted(required-listed)}")
 if entries<5:raise RuntimeError("A7 manifest unexpectedly incomplete")
 return True

def monthends(idx): return pd.Series(idx,index=idx).groupby(idx.to_period("M")).tail(1).index

def sim_slots_v3(P,cand,prio,exitf,maxhold,cost,start,slots=K,slot_w=1/K):
 idx=P.C.index; Cv=P.C.values; Ov=P.O.values; Cff=P.C.ffill().values; Vld=P.validbar.values; rf=P.rf.values
 n,k=Cv.shape;i0=idx.get_loc(pd.Timestamp(start));u=np.zeros(k);cash=1.;eq=np.full(n,np.nan);gross=np.zeros(n);costs=np.zeros(n);turn=np.zeros(n);fills=[];held={};to_buy=[];to_sell=[]
 eq[i0]=1.
 c0=np.flatnonzero(cand[i0]);to_buy=list(c0[np.lexsort((c0,prio[i0,c0]))][:slots]) if len(c0) else []
 for i in range(i0+1,n):
  cash*=1+rf[i];px=np.where(Vld[i],Ov[i],Cff[i-1]);Eo=cash+float(np.sum(u*np.nan_to_num(px)));sold=[];pending_sell=[];traded=0.
  for j in to_sell:
   if Vld[i,j] and np.isfinite(Ov[i,j]):
    v=u[j]*Ov[i,j];cash+=v*(1-cost);traded+=v;fills.append((idx[i],P.C.columns[j],-v/max(Eo,1e-12),0.));u[j]=0.;held.pop(j,None);sold.append(j)
   else:pending_sell.append(j)
  to_sell=pending_sell;pending_buy=[]
  for j in to_buy:
   if len(held)>=slots: pending_buy.append(j);continue
   if Vld[i,j] and np.isfinite(Ov[i,j]) and u[j]==0:
    nav=cash+float(np.sum(u*np.nan_to_num(px)));amt=min(slot_w*nav,cash/(1+cost))
    if amt>1e-10:
     u[j]=amt/Ov[i,j];cash-=amt*(1+cost);traded+=amt;held[j]=i;fills.append((idx[i],P.C.columns[j],amt/max(nav,1e-12),float(u[j])))
   else:pending_buy.append(j)
  to_buy=pending_buy;pos=float(np.sum(u*np.nan_to_num(Cff[i])));E=cash+pos;eq[i]=E;gross[i]=pos/E if E>0 else 0.;costs[i]=traded*cost/max(Eo,1e-12);turn[i]=traded/max(Eo,1e-12)
  for j in list(held):
   age=i-held[j]+1
   if (not Vld[i,j]) or age>=maxhold or exitf[i,j]:
    if j not in to_sell:to_sell.append(j)
  free=max(0,slots-len(held)-len(to_buy))
  if free:
   c=np.flatnonzero(cand[i]&(u==0));c=np.array([j for j in c if j not in to_buy and j not in to_sell],dtype=int)
   if len(c):to_buy.extend(list(c[np.lexsort((c,prio[i,c]))][:free]))
 ser=pd.Series(eq,index=idx);return {"eq":ser,"ret":ser.pct_change(),"gross":pd.Series(gross,index=idx),"cost":pd.Series(costs,index=idx),"turn":pd.Series(turn,index=idx),"fills":fills,"pending_orders":len(to_buy)+len(to_sell)}

def sim_targets_v3(P,tg,cost,start):
 idx=P.C.index;Cv=P.C.values;Ov=P.O.values;Cff=P.C.ffill().values;Vld=P.validbar.values;rf=P.rf.values;n,k=Cv.shape;i0=idx.get_loc(pd.Timestamp(start));u=np.zeros(k);cash=1.;eq=np.full(n,np.nan);gross=np.zeros(n);costs=np.zeros(n);turn=np.zeros(n);fills=[];pending={};refnav=1.;eq[i0]=1.
 if i0 in tg:
  initial=np.asarray(tg[i0],dtype=float);pending={j:float(initial[j]) for j in range(k) if (initial[j]>0 or u[j]>0)}
 for i in range(i0+1,n):
  cash*=1+rf[i];px=np.where(Vld[i],Ov[i],Cff[i-1]);px=np.where(np.isfinite(px)&(px>0),px,0.);Eo=cash+float(np.sum(u*px));traded=0.;fee=0.
  # Execute per-symbol deltas once; blocked symbols remain pending without replaying completed fills.
  executable=[j for j in sorted(pending) if Vld[i,j] and np.isfinite(Ov[i,j]) and Ov[i,j]>0]
  for j in executable:
   target_value=pending[j]*refnav/(1+cost);current_value=u[j]*Ov[i,j]
   if target_value<current_value-1e-10:
    value=current_value-target_value;dq=value/Ov[i,j];u[j]-=dq;cash+=value*(1-cost);traded+=value;fee+=value*cost
    fills.append((idx[i],P.C.columns[j],-value/max(Eo,1e-12),float(u[j])))
  for j in executable:
   target_value=pending[j]*refnav/(1+cost);current_value=u[j]*Ov[i,j]
   if target_value>current_value+1e-10:
    value=target_value-current_value
    if value*(1+cost)<=cash+1e-10:
     dq=value/Ov[i,j];u[j]+=dq;cash-=value*(1+cost);traded+=value;fee+=value*cost
     fills.append((idx[i],P.C.columns[j],value/max(Eo,1e-12),float(u[j])))
    else:continue
   pending.pop(j,None)
  costs[i]=fee/max(Eo,1e-12);turn[i]=traded/max(Eo,1e-12)
  pos=float(np.sum(u*np.nan_to_num(Cff[i])));E=cash+pos;eq[i]=E;gross[i]=pos/E if E>0 else 0.
  if i in tg:
   w=np.asarray(tg[i],dtype=float);refnav=E;pending={j:float(w[j]) for j in range(k) if (w[j]>0 or u[j]>0)}
 ser=pd.Series(eq,index=idx);return {"eq":ser,"ret":ser.pct_change(),"gross":pd.Series(gross,index=idx),"cost":pd.Series(costs,index=idx),"turn":pd.Series(turn,index=idx),"fills":fills,"pending_orders":len(pending)}

def sim_gap_v3(P,signal,gap,cost,start):
 idx=P.C.index;Cv=P.C.values;Cff=P.C.ffill().values;Vld=P.validbar.values;n,k=Cv.shape;i0=idx.get_loc(pd.Timestamp(start));cash=1.;pos={};eq=np.full(n,np.nan);gross=np.zeros(n);turn=np.zeros(n);costs=np.zeros(n);fills=[];eq[i0]=1.
 for i in range(i0+1,n):
  marks=np.nan_to_num(Cff[i]);nav_pre=cash+sum(q*marks[j] for j,(q,entry) in pos.items());traded=0.
  # Exit at this close after one full close-to-close holding interval; defer until a valid close exists.
  for j,(q,entry) in list(pos.items()):
   if entry<i and Vld[i,j] and np.isfinite(Cv[i,j]):
    v=q*Cv[i,j];cash+=v*(1-cost);traded+=v;fills.append((idx[i],P.C.columns[j],-v/max(nav_pre,1e-12),0.));del pos[j]
  nav_after=cash+sum(q*marks[j] for j,(q,entry) in pos.items());pool=np.flatnonzero(signal[i]&Vld[i]);
  if len(pool):
   vals=gap.iloc[i].values[pool];sel=pool[np.lexsort((pool,vals))][:max(0,K-len(pos))]
   for j in sel:
    if j in pos or not np.isfinite(Cv[i,j]) or Cv[i,j]<=0:continue
    amt=min(nav_after/K,cash/(1+cost))
    if amt<=1e-10:continue
    q=amt/Cv[i,j];cash-=amt*(1+cost);pos[j]=(q,i);traded+=amt;fills.append((idx[i],P.C.columns[j],amt/max(nav_after,1e-12),float(q)))
  nav=cash+sum(q*marks[j] for j,(q,entry) in pos.items());eq[i]=nav;gross[i]=(nav-cash)/nav if nav>0 else 0.;turn[i]=traded/max(nav_pre,1e-12);costs[i]=traded*cost/max(nav_pre,1e-12)
 ser=pd.Series(eq,index=idx);return {"eq":ser,"ret":ser.pct_change(),"gross":pd.Series(gross,index=idx),"turn":pd.Series(turn,index=idx),"cost":pd.Series(costs,index=idx),"fills":fills,"pending_exit_positions":len(pos)}

def residual_scores(C,benchmark):
 y=np.log(C/C.shift(1));x=pd.Series(np.log(benchmark/benchmark.shift(1)),index=C.index);mask=y.notna()&x.notna().to_numpy()[:,None]
 X=pd.DataFrame(np.broadcast_to(x.to_numpy()[:,None],y.shape),index=y.index,columns=y.columns).where(mask);Y=y.where(mask)
 n=mask.astype(float).rolling(252,min_periods=200).sum();sx=X.rolling(252,min_periods=200).sum();sy=Y.rolling(252,min_periods=200).sum();sxx=(X*X).rolling(252,min_periods=200).sum();sxy=(X*Y).rolling(252,min_periods=200).sum()
 den=sxx-sx*sx/n;beta=(sxy-sx*sy/n).div(den.where(den>1e-16));alpha=sy.div(n)-beta.mul(sx.div(n));resid=(Y-alpha-beta.mul(X)).where(mask);score=resid.rolling(126,min_periods=126).sum()
 return score,beta,n

def unit_self_check():
 idx=pd.date_range("2030-01-01",periods=5,freq="D"); cols=["A","B"]
 C=pd.DataFrame([[10,20],[10,20],[10,20],[10,20],[10,20]],index=idx,columns=cols,dtype=float)
 O=C.copy();valid=pd.DataFrame(True,index=idx,columns=cols);valid.loc[idx[1],"A"]=False
 P=SimpleNamespace(C=C,O=O,validbar=valid,rf=pd.Series(0.,index=idx))
 tgt={0:np.array([.05,.05])};r=sim_targets_v3(P,tgt,.001,idx[0]);fills=r["fills"]
 assert [(d,s) for d,s,_,_ in fills]==[(idx[1],"B"),(idx[2],"A")],fills
 assert r["pending_orders"]==0
 assert abs(r["turn"].iloc[1]-(.05/1.001))<1e-8 and abs(r["cost"].iloc[1]-(.05*.001/1.001))<1e-8
 # A 100% SPY target and a 20 x 5% portfolio must pay costs and complete without negative cash.
 C20=pd.DataFrame(10.,index=idx,columns=[f"S{j:02d}" for j in range(20)]);V20=pd.DataFrame(True,index=idx,columns=C20.columns);P20=SimpleNamespace(C=C20,O=C20.copy(),validbar=V20,rf=pd.Series(0.,index=idx))
 r20=sim_targets_v3(P20,{0:np.full(20,.05)},.001,idx[0]);assert len(r20["fills"])==20 and r20["pending_orders"]==0
 assert abs(r20["turn"].iloc[1]-(1/1.001))<1e-8 and abs(r20["cost"].iloc[1]-(.001/1.001))<1e-8
 Pspy=SimpleNamespace(C=C[["B"]],O=O[["B"]],validbar=pd.DataFrame(True,index=idx,columns=["B"]),rf=pd.Series(0.,index=idx));rspy=sim_targets_v3(Pspy,{0:np.array([1.])},.001,idx[0]);assert rspy["pending_orders"]==0 and len(rspy["fills"])==1
 assert abs(rspy["turn"].iloc[1]-(1/1.001))<1e-8 and abs(rspy["cost"].iloc[1]-(.001/1.001))<1e-8
 # RSI order remains unfilled on an invalid open and is filled once, then exits only on the following valid open.
 cand=np.zeros((5,2),dtype=bool);cand[0,0]=True;prio=np.zeros((5,2));exitf=np.zeros((5,2),dtype=bool);exitf[2,0]=True
 valid2=valid.copy();valid2.loc[idx[1],"A"]=False
 P2=SimpleNamespace(C=C,O=O,validbar=valid2,rf=pd.Series(0.,index=idx))
 r2=sim_slots_v3(P2,cand,prio,exitf,5,.001,idx[0]);f2=r2["fills"]
 assert [(d,s,notional<0) for d,s,notional,_ in f2]==[(idx[2],"A",False),(idx[3],"A",True)],f2
 assert abs(r2["turn"].iloc[2]-.05)<1e-8 and abs(r2["cost"].iloc[2]-.00005)<1e-8
 # Gap unit enters at close, carries over a missing close without a fictional fill, and exits at the next valid close.
 Cg=pd.DataFrame({"A":[10.,10.,np.nan,12.,12.]},index=idx);Og=Cg.copy();vg=Cg.notna();Pg=SimpleNamespace(C=Cg,O=Og,validbar=vg,rf=pd.Series(0.,index=idx))
 sig=np.zeros((5,1),dtype=bool);sig[1,0]=True;gap=pd.DataFrame(0.,index=idx,columns=["A"])
 rg=sim_gap_v3(Pg,sig,gap,.001,idx[0]);fg=rg["fills"]
 assert [(d,s,notional<0) for d,s,notional,_ in fg]==[(idx[1],"A",False),(idx[3],"A",True)],fg
 assert rg["pending_exit_positions"]==0
 assert abs(rg["turn"].iloc[1]-.05)<1e-8 and abs(rg["cost"].iloc[1]-.00005)<1e-8
 assert rg["turn"].iloc[2]==0 and rg["cost"].iloc[2]==0 and rg["turn"].iloc[3]>0 and rg["cost"].iloc[3]>0
 return {"target_per_symbol_deferred_once":True,"target_fee_and_turnover":True,"full_investment_20_slots_affordable":True,"spy_full_target_affordable":True,"slot_open_fill_defers_and_exits":True,"slot_fee_and_turnover":True,"gap_close_exit_defers_on_missing_close":True,"gap_fee_and_turnover":True}

def main():
 verify_frozen_inputs()
 unit_self_check()
 P=v2.load_panel(cache=True)
 idx=P.C.index[(P.C.index>=pd.Timestamp("1998-01-01"))&(P.C.index<=pd.Timestamp(END))]
 C=P.C.loc[idx].copy(); O=P.O.loc[idx].copy(); V=P.V.loc[idx].copy(); M=P.M.loc[idx].copy(); spyC=P.spyC.loc[idx].copy()
 syms=list(C.columns); dollar={}; rawopens={}; rawcloses={}; validbars={}
 for s in syms:
  try:
   d=usdata.load(s).reindex(idx); ohlc=d[["open","high","low","close"]]
   dollar[s]=d["close"]*d["volume"];rawopens[s]=d["open"];rawcloses[s]=d["close"]
   validbars[s]=(ohlc.notna().all(axis=1)&(ohlc>0).all(axis=1)&(d["volume"]>0)&(d["high"]>=d[["open","close"]].max(axis=1))&(d["low"]<=d[["open","close"]].min(axis=1)))
  except Exception:
   dollar[s]=pd.Series(np.nan,index=idx);rawopens[s]=pd.Series(np.nan,index=idx);rawcloses[s]=pd.Series(np.nan,index=idx);validbars[s]=pd.Series(False,index=idx)
 dvol=pd.DataFrame(dollar,index=idx).reindex(columns=syms);rawO=pd.DataFrame(rawopens,index=idx).reindex(columns=syms);rawC=pd.DataFrame(rawcloses,index=idx).reindex(columns=syms); validbar=pd.DataFrame(validbars,index=idx).reindex(columns=syms).fillna(False)
 C=C.where(validbar);O=O.where(validbar);V=V.where(validbar)
 median=dvol.rolling(60,min_periods=55).median(); active=C.notna()&(C.rolling(60,min_periods=55).count()>=55)
 eligible=M&(C.notna().cumsum()>=252)&active&dvol.notna()&(median>=5_000_000)
 ranks=median.where(eligible).rank(axis=1,ascending=False,method="first")
 sma5=C.rolling(5).mean();sma200=C.rolling(200,min_periods=200).mean()
 rsi=C.apply(lambda s:v2.v1.wilder_rsi(s,2))
 p2=SimpleNamespace(C=C,O=O,V=V,E=eligible,rf=pd.Series(0.,index=idx),spyC=spyC,spyO=P.spyO.loc[idx],validbar=validbar)
 results={};returns={};exposures={};turns={};counts={"study_start":START,"study_end":END,"bar_end":str(idx.max().date()),"universe_equity_series":len(syms),"pit_snapshot_last":"2026-08-18","stale_membership_tail_excluded":True,"eligible_avg":float(eligible.loc[START:END].sum(axis=1).mean()),"eligible_min":int(eligible.loc[START:END].sum(axis=1).min())}
 rawse=pd.read_csv(ROOT/"data/us_daily/pit/sp500_ticker_start_end.csv"); rawse["sym"]=rawse.ticker.str.replace(".","-",regex=False)
 countsp=pd.read_csv(ROOT/"data/us_daily/pit/hist_components.csv"); allparquet={p.stem for p in (ROOT/"data/us_daily").glob("*.parquet")}
 counts.update({"pit_unique_ticker_symbols":int(rawse.sym.nunique()),"pit_ticker_spells":int(len(rawse)),"pit_symbols_with_price_parquet":int(len(set(rawse.sym)&allparquet)),"pit_symbols_without_price_parquet":int(len(set(rawse.sym)-allparquet)),"equity_symbols_loaded_after_v2_exclusions":len(syms),"v2_reused_tickers_excluded":len(set(v2.REUSED_TICKER_EXCLUDE)&set(rawse.sym)),"last_snapshot_member_count":int(len(countsp.tickers.iloc[-1].split(",")))})
 for N in NLIST:
  U=eligible&(ranks<=N);counts[f"top{N}_mean_member_count"]=float(U.loc[START:END].sum(axis=1).mean())
  # RSI2 daily: max 20 slots, 5% fixed slot, next-open entry and next-open exit after close signal.
  cand=U&(C>sma200)&(rsi<=10)&C.notna()&C.shift(1).notna()&C.shift(2).notna(); pre=(cand.values,rsi.values,True,(C>sma5).values,K)
  for cost in COSTS:
   rr=sim_slots_v3(p2,cand.values,rsi.values,(C>sma5).values,5,cost,START,slots=K,slot_w=1/K)
   key=f"rsi2_top{N}_{int(cost*10000)}bp";returns[key]=rr["ret"].fillna(0);exposures[key]=rr["gross"];turns[key]=rr["turn"]
   results[key]=stat(returns[key]);results[key].update({"fills":len(rr["fills"]),"mean_turnover":float(rr["turn"].loc[START:END].mean()),"mean_exposure":float(rr["gross"].loc[START:END].mean()),"side_cost_bp":int(cost*10000),"pending_orders":rr.get("pending_orders",0)})
  # Gap: previous-close liquidity rank/trend; observe current open gap; enter current close and exit next close.
  gap=rawO.div(rawC.shift(1))-1; gap_ok=(gap<=-0.025)&(C.shift(1)>sma200.shift(1))&(U.shift(1).fillna(False))
  for cost in COSTS:
   rr=sim_gap_v3(p2,gap_ok.values,gap,cost,START);key=f"gap_reversal_top{N}_{int(cost*10000)}bp";returns[key]=rr["ret"].fillna(0);exposures[key]=rr["gross"];turns[key]=rr["turn"];results[key]=stat(returns[key])
   results[key].update({"fills":len(rr["fills"]),"mean_turnover":float(rr["turn"].loc[START:END].mean()),"mean_exposure":float(rr["gross"].loc[START:END].mean()),"side_cost_bp":int(cost*10000),"pending_exit_positions":rr.get("pending_exit_positions",0)})
  # Residual momentum: OLS in daily log-return space with intercept; latest 126 residuals, max 20 positions.
  score,beta,pairs=residual_scores(C,spyC);valid=U&(score>0)&beta.notna()&(pairs>=200)
  tg={}
  for d in monthends(idx):
   i=idx.get_loc(d);pool=np.flatnonzero(valid.iloc[i].values);w=np.zeros(len(syms))
   if len(pool):
    s=score.iloc[i].values[pool];sel=pool[np.lexsort((pool,-s))][:K];w[sel]=1/K
   tg[i]=w
  for cost in COSTS:
   rr=sim_targets_v3(p2,tg,cost,START);key=f"residual_mom_top{N}_{int(cost*10000)}bp";returns[key]=rr["ret"].fillna(0);exposures[key]=rr["gross"];turns[key]=rr["turn"]
   results[key]=stat(returns[key]);results[key].update({"fills":len(rr["fills"]),"mean_turnover":float(rr["turn"].loc[START:END].mean()),"mean_exposure":float(rr["gross"].loc[START:END].mean()),"side_cost_bp":int(cost*10000),"pending_orders":rr.get("pending_orders",0)})
  # Fair comparator: monthly equal-weight contemporaneous liquidity Top-N portfolio.
  ew={}
  for d in monthends(idx):
   i=idx.get_loc(d);sel=np.flatnonzero(U.iloc[i].values);w=np.zeros(len(syms))
   if len(sel):w[sel]=1/len(sel)
   ew[i]=w
  br=sim_targets_v3(p2,ew,.001,START);key=f"ew_liqtop{N}_10bp";returns[key]=br["ret"].fillna(0);exposures[key]=br["gross"];turns[key]=br["turn"]
  results[key]=stat(returns[key]);results[key].update({"fills":len(br["fills"]),"mean_turnover":float(br["turn"].loc[START:END].mean()),"mean_exposure":float(br["gross"].loc[START:END].mean()),"side_cost_bp":10,"pending_orders":br.get("pending_orders",0)})
 # SPY buy-and-hold: enter at the next available valid open and charge actual 10bp fill cost.
 rawspy=usdata.load("SPY").reindex(idx);asp=usdata.adjusted(rawspy);validspy=(rawspy[["open","high","low","close"]].notna().all(axis=1)&(rawspy[["open","high","low","close"]]>0).all(axis=1)&(rawspy["volume"]>0)&(rawspy["high"]>=rawspy[["open","close"]].max(axis=1))&(rawspy["low"]<=rawspy[["open","close"]].min(axis=1)))
 sp=SimpleNamespace(C=asp["close"].to_frame("SPY"),O=asp["open"].to_frame("SPY"),rf=pd.Series(0.,index=idx),validbar=validspy.to_frame("SPY"))
 returns_i=idx.get_loc(pd.Timestamp(START));spyres=sim_targets_v3(sp,{returns_i:np.array([1.])},.001,START);returns["spy_bh_10bp"]=spyres["ret"].fillna(0.);exposures["spy_bh_10bp"]=spyres["gross"];turns["spy_bh_10bp"]=spyres["turn"];results["spy_bh_10bp"]=stat(returns["spy_bh_10bp"]);results["spy_bh_10bp"]["pending_orders"]=spyres.get("pending_orders",0)
 # Summary slices are descriptive; no winner selection or promotion from reused data.
 for key,rr in returns.items():
  results[key]["periods"]={"IS_2012_2019":stat(rr,"2012-06-01","2019-12-31"),"reused_OOS_2020_2026_08_18":stat(rr,"2020-01-01",END),"full":stat(rr,START,END)}
  results[key]["regimes"]={n:stat(rr,a,b) for n,(a,b) in REGIMES.items()}
 out={"coverage":counts,"results":results,"regimes":REGIMES,"disclaimer":"Exploratory, reused data; no strategy promotion."}
 (HERE/"results.json").write_text(json.dumps(out,indent=2,default=str));(HERE/"coverage.json").write_text(json.dumps(counts,indent=2))
 pd.DataFrame({k:v for k,v in returns.items()}).loc[START:END].to_csv(HERE/"daily_returns.csv")
 pd.DataFrame({k:v for k,v in exposures.items()}).loc[START:END].to_csv(HERE/"daily_exposure.csv")
 print(json.dumps(out,indent=2,default=str))
if __name__=="__main__":main()
