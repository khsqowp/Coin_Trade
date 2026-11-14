#!/usr/bin/env python3
"""Preregistered daily shakeout/rebound backtest. Research only."""
import os
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse, json, sys, math, itertools, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

SEED = 20261113
NS = (15, 20); RS = (.10, .15); DS = (.05, .08); MS = (2, 3)
ENTRIES = ("E1", "E2"); EXITS = ("X1_3", "X1_5", "X1_10", "X2")
GRID = list(itertools.product(NS, RS, DS, MS, ENTRIES, EXITS))
IS_END = pd.Timestamp("2019-12-31"); OOS_START = pd.Timestamp("2020-01-01")

def _dates(df):
    df = df.copy()
    index = pd.DatetimeIndex(pd.to_datetime(df.index))
    if index.tz is not None:
        index = index.tz_localize(None)
    # pandas 3 can preserve parquet timestamp units such as us or s. All
    # downstream .asi8 values and Timestamp.value boundaries must be ns.
    df.index = index.as_unit("ns")
    return df.sort_index()

def _date_ns(index):
    """Return timestamp integers in ns regardless of the source index unit."""
    return index.to_numpy(dtype="datetime64[ns]").astype("int64")

def _frame(path):
    return _dates(pd.read_parquet(path))

def _limits(date): return .15 if date < pd.Timestamp("2015-06-15") else .30

def _signal_frame(df, market, n, r, d, m):
    """Return candidate drop indices, trigger truth, volume ratios, and validity."""
    a = df
    o,h,l,c,v = (a[x].to_numpy(float) for x in ("open","high","low","close","volume"))
    dates=a.index; size=len(a)
    if size<=n+1:return []
    count=size-n-1; windows=np.lib.stride_tricks.sliding_window_view
    cw=windows(c,n)[:count]; hw=windows(h,n)[:count]; lw=windows(l,n)[:count]; vw=windows(v,n)[:count]
    mean_c=np.mean(cw,axis=1); mean_v=np.mean(vw,axis=1); lo=np.min(lw,axis=1); hi=np.max(hw,axis=1)
    t=np.arange(n,n+count); ret=c[t]/c[t-1]-1
    mask=np.isfinite(mean_c)&(mean_c>0)&((hi-lo)/mean_c<=r)&np.isfinite(mean_v)&(mean_v>0)
    raw = a["rawclose"].to_numpy(float) if market == "us" and "rawclose" in a else c
    raww=windows(raw,n)[:count]
    mask &= v[t] >= (m*mean_v if m else 0); mask &= np.mean(raww*vw,axis=1)>=(1e9 if market=="kr" else 2e7)
    mask &= ret<=-d; mask &= c[t]<lo
    if market=="kr":
        lim=np.where(dates[t]<pd.Timestamp("2015-06-15"),.15,.30); mask &= ret>-(lim-.01)
    else:mask &= (ret>-.25)&(np.abs(o[t]/c[t-1]-1)<=.25)
    # All required bars have positive volume, <=7 calendar-day gaps, and <=50% close returns.
    vvalid=windows(v,n+2)[:count]; mask &= np.all(vvalid>0,axis=1)
    daydiff=np.diff(_date_ns(dates)).astype(float)/86400e9; gapvalid=windows(daydiff,n+1)[:count]; mask &= np.all(gapvalid<=7,axis=1)
    retvalid=windows(c,n+2)[:count]; rr=retvalid[:,1:]/retvalid[:,:-1]-1; mask &= np.all(np.abs(rr)<=.5,axis=1)
    green=(c[t+1]>o[t+1])&(c[t+1]>c[t])
    if market=="kr":
        trigger_limit=np.where(dates[t+1]<pd.Timestamp("2015-06-15"),.15,.30)
        mask &= c[t+1]/c[t]-1<trigger_limit-.01
    idx=np.flatnonzero(mask)
    return [(int(t[i]),bool(green[i]),float(v[t[i]]/mean_v[i])) for i in idx]

def _trade(df, t, entry_kind, exit_kind, market, cost, ratio=1.0):
    o,h,l,c,v=(df[x].to_numpy(float) for x in ("open","high","low","close","volume")); dates=df.index; date_ns=_date_ns(dates); n=len(df)
    e=t+1 if entry_kind=="E1" else t+2
    if e>=n: return None
    ep=c[e] if entry_kind=="E1" else o[e]
    if not np.isfinite(ep) or ep<=0: return None
    if exit_kind.startswith("X1_"):
        hold=int(exit_kind.split("_")[1]); x=e+hold
        if x>=n: return None
        xp=c[x]
    else:
        target=c[t-1]*ratio; stop=l[t]*ratio
        xp=None; x=None
        for j in range(e+1 if entry_kind=="E1" else e, min(n,e+11)):
            hit_stop=c[j]<stop
            hit_target=(ep < target and h[j]>=target)
            if hit_stop: x=j; xp=c[j]; break
            if hit_target: x=j; xp=target; break
        if x is None:
            x=e+10
            if x>=n: return None
            xp=c[x]
    gross=xp/ep-1
    return {"signal_date":str(dates[t].date()),"entry_date":str(dates[e].date()),"exit_date":str(dates[x].date()),
            "entry_ns":int(date_ns[e]),"exit_ns":int(date_ns[x]),"signal_year":int(dates[t].year),"entry_year":int(dates[e].year),
            "t":t,"e":e,"x":x,"entry":float(ep),"exit":float(xp),"gross":float(gross),"net":float(gross-cost),
            "hold":int(x-e),"volume_ratio":float(v[t]/np.mean(v[t-15:t]) if t>=15 else 0),"cost":cost}

def _collect(df, market, combo, cost, confirmation=True, m_override=None):
    n,r,d,m,entry,exit_rule=combo
    cand=_signal_frame(df,market,n,r,d,m if m_override is None else m_override)
    accepted=[]; last_exit=-1
    for t,green,vr in cand:
        if confirmation and not green: continue
        tr=_trade(df,t,entry,exit_rule,market,cost)
        if tr is None or tr["e"]<=last_exit: continue
        tr["volume_ratio"]=vr; accepted.append(tr); last_exit=tr["x"]
    return accepted

def _collect_subset(df, market, combo, cost, want_green):
    n,r,d,m,entry,exit_rule=combo; accepted=[]; last_exit=-1
    for t,green,vr in _signal_frame(df,market,n,r,d,m):
        if bool(green)!=bool(want_green):continue
        tr=_trade(df,t,entry,exit_rule,market,cost)
        if tr is None or tr["e"]<=last_exit:continue
        tr["volume_ratio"]=vr; accepted.append(tr); last_exit=tr["x"]
    return accepted

def _collect_three(df, market, combo, cost, candidates):
    """Build confirmed, failed-trigger, and unconditional streams in one candidate pass."""
    n,r,d,m,entry,exit_rule=combo
    result={"confirmed":[],"failed":[],"unconditional":[]}; last={k:-1 for k in result}
    for t,green,vr in candidates:
        tr=_trade(df,t,entry,exit_rule,market,cost)
        if tr is None: continue
        tr["volume_ratio"]=vr
        for key,allowed in (("confirmed",green),("failed",not green),("unconditional",True)):
            if allowed and tr["e"]>last[key]:
                result[key].append(dict(tr)); last[key]=tr["x"]
    return result

def _collect_from_candidates(df, market, combo, cost, candidates, confirmation=True):
    _,_,_,_,entry,exit_rule=combo; accepted=[]; last_exit=-1
    for t,green,vr in candidates:
        if confirmation and not green: continue
        tr=_trade(df,t,entry,exit_rule,market,cost)
        if tr is not None and tr["e"]>last_exit:
            tr["volume_ratio"]=vr; accepted.append(tr); last_exit=tr["x"]
    return accepted

def _portfolio(df, trades, cost):
    dates=df.index; c=df.close.to_numpy(float); o=df.open.to_numpy(float)
    daily=np.zeros(len(df)); selected=[]; active=[]
    for tr in sorted(trades,key=lambda z:(z["e"],-z["volume_ratio"])):
        active=[q for q in active if q["x"]>=tr["e"]]
        if len(active)>=10: continue
        selected.append(tr); active.append(tr)
        e,x=tr["e"],tr["x"]; ep=tr["entry"]
        prev=ep
        for j in range(e,x+1):
            if j==e and tr["entry"]==c[e]: dayret=0.
            else: dayret=(c[j]/(o[j] if j==e else c[j-1])-1) if j==e else c[j]/c[j-1]-1
            if j==x: dayret-=cost
            daily[j]+=.1*dayret
            prev=c[j]
    return selected,daily

def _metrics(dates, daily, trades):
    if len(daily)==0: return {"cagr":None,"sharpe":None,"max_drawdown":None,"trades":len(trades),"win_rate":None,"mean_trade_return":None,"median_trade_return":None,"worst_trade":None,"avg_hold_bars":None}
    curve=np.cumprod(1+daily); span=max((dates[-1]-dates[0]).days/365.25,1/365.25)
    dd=curve/np.maximum.accumulate(curve)-1
    vals=np.array([t["net"] for t in trades],float)
    return {"cagr":float(curve[-1]**(1/span)-1),"sharpe":float(np.mean(daily)/np.std(daily,ddof=1)*np.sqrt(252)) if len(daily)>1 and np.std(daily,ddof=1)>0 else None,
      "max_drawdown":float(np.min(dd)),"trades":len(trades),"win_rate":float(np.mean(vals>0)) if len(vals) else None,
      "mean_trade_return":float(np.mean(vals)) if len(vals) else None,"median_trade_return":float(np.median(vals)) if len(vals) else None,
      "worst_trade":float(np.min(vals)) if len(vals) else None,"avg_hold_bars":float(np.mean([t["hold"] for t in trades])) if len(vals) else None}

def _index_metrics(cache, market):
    names = ("KOSPI", "KOSDAQ") if market == "kr" else ("SPY", "QQQ")
    result = {}
    for name in names:
        p = Path(cache)/"idx"/(name+".parquet")
        if not p.exists(): result[name] = {k:None for k in ("ALL","IS","OOS")}; continue
        df = _frame(p); col = "Adj Close" if name in ("SPY","QQQ") and "Adj Close" in df else "Close"
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        parts={}
        for period, mask in (("ALL", np.ones(len(s),bool)), ("IS", s.index<=IS_END), ("OOS",s.index>=OOS_START)):
            x=s.iloc[np.flatnonzero(mask)]
            if len(x)<2: parts[period]={"cagr":None,"sharpe":None,"max_drawdown":None}; continue
            dr=x.pct_change().dropna().to_numpy(); curve=np.cumprod(1+dr); span=max((x.index[-1]-x.index[0]).days/365.25,1/365.25)
            parts[period]={"cagr":float((x.iloc[-1]/x.iloc[0])**(1/span)-1),"sharpe":float(np.mean(dr)/np.std(dr,ddof=1)*np.sqrt(252)) if len(dr)>1 and np.std(dr,ddof=1)>0 else None,"max_drawdown":float(np.min(curve/np.maximum.accumulate(curve)-1))}
        result[name]=parts
    return result

def _per_year(trades, cost):
    out={}
    for year in sorted({t["entry_year"] if "entry_year" in t else pd.Timestamp(t["entry_date"]).year for t in trades}):
        ts=[t for t in trades if (t["entry_year"] if "entry_year" in t else pd.Timestamp(t["entry_date"]).year)==year]
        out[str(year)]={"return":float(np.prod([1+.1*t["net"] for t in ts])-1),"trades":len(ts),"mean_net_trade_return":float(np.mean([t["net"] for t in ts]))}
    return out

def _portfolio_years(dates,daily,trades):
    out={}
    for year in sorted(set(d.year for d in dates)):
        ii=np.array([j for j,d in enumerate(dates) if d.year==year],int)
        ts=[t for t in trades if (t["entry_year"] if "entry_year" in t else pd.Timestamp(t["entry_date"]).year)==year]
        out[str(year)]={"return":float(np.prod(1+daily[ii])-1),"trades":len(ts),"mean_net_trade_return":float(np.mean([t["net"] for t in ts])) if ts else None}
    return out

def _cluster_diff(a,b,boot,rng):
    if not a or not b: return {"difference":None,"ci95":[None,None]}
    def grouped(ts):
        d={}
        for t in ts:d.setdefault(t["entry_date"][:7],[]).append(t["net"])
        return np.array([np.mean(v) for v in d.values()])
    x,y=grouped(a),grouped(b); sims=np.mean(x[rng.integers(0,len(x),size=(boot,len(x)))],axis=1)-np.mean(y[rng.integers(0,len(y),size=(boot,len(y)))],axis=1)
    return {"difference":float(np.mean([t["net"] for t in a])-np.mean([t["net"] for t in b])),"ci95":[float(np.quantile(sims,.025)),float(np.quantile(sims,.975))]}

_RANDOM_CANDIDATE_CACHE={}
def _random_candidates(df, code, n, market, year):
    key=(code,n,market,year)
    if key in _RANDOM_CANDIDATE_CACHE:return _RANDOM_CANDIDATE_CACHE[key]
    c=df.close.to_numpy(float); v=df.volume.to_numpy(float); raw=df.rawclose.to_numpy(float) if market=="us" and "rawclose" in df else c
    size=len(df); valid=np.zeros(size,dtype=bool)
    if size>n+12:
        win=np.lib.stride_tricks.sliding_window_view
        vols=win(v,n+2); prices=win(c,n+2); t=np.arange(n,size-12)
        ok=np.all(vols>0,axis=1)[:len(t)]
        rr=prices[:,1:]/prices[:,:-1]-1; ok &= np.all(np.isfinite(rr)&(np.abs(rr)<=.5),axis=1)[:len(t)]
        gaps=np.diff(_date_ns(df.index)).astype(float)/86400e9
        ok &= np.all(win(gaps,n+1)<=7,axis=1)[:len(t)]
        liquidity=np.mean(win(raw,n)[:len(t)]*win(v,n)[:len(t)],axis=1)
        ok &= liquidity >= (1e9 if market=="kr" else 2e7)
        valid[t]=ok
    result=np.flatnonzero(valid & (df.index.year==year)); _RANDOM_CANDIDATE_CACHE[key]=result; return result

def _random_period(trades, frames, combo, market, draws, seed):
    if not trades:return {"percentile":None,"p_one_sided":None,"n":0}
    rng=np.random.default_rng(seed); n,r,d,m,entry,exit_rule=combo; cost=.0041 if market=="kr" else .001
    sim_by_trade=[]
    for tr in trades:
        df=frames[tr["code"]]; o=df.open.to_numpy(float); h=df.high.to_numpy(float); l=df.low.to_numpy(float); c=df.close.to_numpy(float)
        year=tr["signal_year"] if "signal_year" in tr else pd.Timestamp(tr["signal_date"]).year
        picks=_random_candidates(df,tr["code"],n,market,year)
        if not len(picks):continue
        e0=picks+(1 if entry=="E1" else 2); ep0=c[e0] if entry=="E1" else o[e0]
        valid=np.isfinite(ep0)&(ep0>0)
        if exit_rule.startswith("X1_"):valid &= e0+int(exit_rule.split("_")[1])<len(df)
        else:valid &= e0+10<len(df)
        picks=picks[valid]
        if not len(picks):continue
        t=np.asarray(rng.choice(picks,size=draws,replace=True),int); e=t+(1 if entry=="E1" else 2); ep=c[e] if entry=="E1" else o[e]
        if exit_rule.startswith("X1_"):
            x=e+int(exit_rule.split("_")[1]); vals=c[x]/ep-1-cost
        else:
            # Keep each real trade's target and stop offsets relative to entry.
            target_ratio=tr["exit"] if False else c[tr["t"]-1]/tr["entry"]
            stop_ratio=l[tr["t"]]/tr["entry"]
            tgt=ep*target_ratio; stp=ep*stop_ratio
            vals=np.full(draws,np.nan); done=np.zeros(draws,bool)
            for k in range(0,10 if entry=="E1" else 11):
                j=e+k if entry=="E2" else e+1+k
                inrange=j<len(c); safe=np.minimum(j,len(c)-1)
                stop=inrange & (c[safe]<stp) & ~done
                target=inrange & (ep<tgt) & (h[safe]>=tgt) & ~done
                vals[stop]=c[safe[stop]]/ep[stop]-1-cost; done[stop]=True
                hit=target & ~stop; vals[hit]=target_ratio-1-cost; done[hit]=True
            remain=~done; x=e+10; vals[remain]=c[x[remain]]/ep[remain]-1-cost
        sim_by_trade.append(vals)
    if not sim_by_trade:return {"percentile":None,"p_one_sided":None,"n":0}
    means=np.nanmean(np.vstack(sim_by_trade),axis=0); real=float(np.mean([t["net"] for t in trades]))
    return {"percentile":float(np.mean(means<=real)),"p_one_sided":float((1+np.sum(means>=real))/(len(means)+1)),"n":int(len(means)),"real_mean_net":real}

def _boot(trades, draws, rng):
    if not trades: return {"ci95":[None,None],"p_two_sided":None}
    buckets={}
    for t in trades: buckets.setdefault(t["entry_date"][:7],[]).append(t["net"])
    keys=list(buckets)
    if not keys: return {"ci95":[None,None],"p_two_sided":None}
    totals=np.array([np.sum(buckets[k]) for k in keys]); counts=np.array([len(buckets[k]) for k in keys]); pick=rng.integers(0,len(keys),(draws,len(keys)))
    sims=np.sum(totals[pick],axis=1)/np.sum(counts[pick],axis=1)
    p=max(1/draws,2*min(np.mean(sims<=0),np.mean(sims>=0)))
    return {"ci95":[float(np.quantile(sims,.025)),float(np.quantile(sims,.975))],"p_two_sided":float(min(1,p))}

def _load_universe(cache, market):
    if market=="kr":
        u=pd.read_csv(cache/"kr_universe.csv",dtype={"Code":str}); u=u[u.Market.isin(["KOSPI","KOSDAQ"])]; u=u[u.Code.str.endswith("0")]; u=u[~u.Name.str.contains("스팩|기업인수목적",regex=True,na=False)]
        return [(str(x.Code).zfill(6),str(x.Name),str(x.Market)) for x in u.itertuples()]
    u=pd.read_csv(cache/"us_universe.csv"); col="symbol" if "symbol" in u else u.columns[0]; return [(str(x),str(x),"US") for x in u[col].dropna()]

def _bh(ps):
    a=np.array([1. if p is None else p for p in ps]); n=len(a); order=np.argsort(a); q=np.ones(n); vals=a[order]*n/(np.arange(n)+1); vals=np.minimum.accumulate(vals[::-1])[::-1]; q[order]=np.minimum(vals,1); return q.tolist()

def run(market,cache,out,draws=1000,boot=5000,limit_names=None):
    started=time.perf_counter(); phases={"load":0.,"signals":0.,"portfolio":0.,"random":0.,"bootstrap":0.}
    rng=np.random.default_rng(SEED); cache=Path(cache); out=Path(out); out.mkdir(parents=True,exist_ok=True)
    universe=_load_universe(cache,market); universe=universe[:limit_names] if limit_names else universe
    combos={str(i):{"combo":dict(zip(("N","R","D","M","entry","exit"),g)),"trades":[],"unconfirmed":[],"failed":[]} for i,g in enumerate(GRID)}
    vol0={str(i):[] for i,g in enumerate(GRID) if g[3]==2}
    coverage=[]; frames={}; total=len(universe); signal_counts={}
    for ii,(code,name,listing_market) in enumerate(universe,1):
        phase_start=time.perf_counter()
        path=cache/market/(code+".parquet")
        if not path.exists(): continue
        try: df=_frame(path)
        except Exception as e: print(f"skip {code}: {e}",file=sys.stderr); continue
        cols={x.lower():x for x in df.columns}
        # Canonicalize FDR/cache columns.
        df=df.rename(columns={cols[k]:k for k in ("open","high","low","close","volume") if k in cols})
        if "rawclose" not in df and "raw close" in cols: df=df.rename(columns={cols["raw close"]:"rawclose"})
        if not all(k in df for k in ("open","high","low","close","volume")): continue
        keep=[k for k in ("open","high","low","close","volume","rawclose") if k in df]
        df=df[keep].astype(np.float64)
        phases["load"]+=time.perf_counter()-phase_start; phase_start=time.perf_counter()
        frames[code]=df; coverage.append({"code":code,"name":name,"market":listing_market,"first_date":str(df.index.min().date()),"last_date":str(df.index.max().date()),"n_bars":len(df)})
        signal_cache={}
        for n0,r0,d0,m0 in itertools.product(NS,RS,DS,MS):
            candidates=_signal_frame(df,market,n0,r0,d0,m0); signal_cache[(n0,r0,d0,m0)]=candidates
            signal_counts[f'N{n0}_R{r0}_D{d0}_M{m0}']=signal_counts.get(f'N{n0}_R{r0}_D{d0}_M{m0}',0)+sum(1 for _,green,_ in candidates if green)
        for ci,g in enumerate(GRID):
            cost=.0041 if market=="kr" else .001
            streams=_collect_three(df,market,g,cost,signal_cache[(g[0],g[1],g[2],g[3])])
            alltrades=streams["unconditional"]; confirmedtrades=streams["confirmed"]
            if g[3]==2:
                k0=(g[0],g[1],g[2],0)
                if k0 not in signal_cache: signal_cache[k0]=_signal_frame(df,market,*k0)
                for z in _collect_from_candidates(df,market,g,cost,signal_cache[k0]): z.update({"code":code}); vol0[str(ci)].append(z)
            for tr in streams["failed"]:
                tr.update({"code":code}); combos[str(ci)]["failed"].append(tr)
            for trade in alltrades:
                trade.update({"code":code})
                combos[str(ci)]["unconfirmed"].append(trade)
            for trade in confirmedtrades:
                trade.update({"code":code})
                trade["forward"]={str(k):(float(df.close.iloc[trade["e"]+k]/trade["entry"]-1) if trade["e"]+k<len(df) else None) for k in (1,3,5,10)}
                combos[str(ci)]["trades"].append(trade)
        if ii%100==0 or ii==total: print(f"loaded {ii}/{total} names; usable={len(frames)}",file=sys.stderr)
        phases["signals"]+=time.perf_counter()-phase_start
    bydate=sorted({d for f in frames.values() for d in f.index}); calendar=pd.DatetimeIndex(bydate); pos={d:i for i,d in enumerate(calendar)}
    calendar_ns=_date_ns(calendar); pos_ns={int(d):i for i,d in enumerate(calendar_ns)}
    frame_positions={code:np.fromiter((pos[d] for d in f.index),dtype=np.int64,count=len(f)) for code,f in frames.items()}
    records=[]; headlines=[]
    for ix,g in enumerate(GRID):
        portfolio_start=time.perf_counter()
        key=str(ix); ts=combos[key]["trades"]; cost=.0041 if market=="kr" else .001
        # Aggregate event and per-combo trade lists across stocks; portfolio is simulated on calendar returns below.
        per={}; accepted_all=[]; annual_portfolio={}
        for p,lo,hi in (("IS",None,IS_END),("OOS",OOS_START,None),("ALL",None,None)):
            lo_ns=lo.value if lo is not None else None; hi_ns=hi.value if hi is not None else None
            pt=[t for t in ts if (lo_ns is None or t["entry_ns"]>=lo_ns) and (hi_ns is None or t["entry_ns"]<=hi_ns)]
            # Combined daily stream: allocate 1/10 per accepted slot, daily marks by stock.
            daily=np.zeros(len(bydate)); accepted=[]; active=[]
            for tr in sorted(pt,key=lambda z:(z["entry_ns"],-z["volume_ratio"])):
                e_ns=tr["entry_ns"]; x_ns=tr["exit_ns"]; active=[z for z in active if z[0]>=e_ns]
                if len(active)>=10: continue
                active.append((x_ns,tr)); accepted.append(tr); df=frames[tr["code"]]; c=df.close.to_numpy(); o=df.open.to_numpy();
                positions=frame_positions[tr["code"]][tr["e"]:tr["x"]+1]
                js=np.arange(tr["e"],tr["x"]+1)
                drs=np.empty(len(js),dtype=float); drs[0]=0 if tr["entry"]==c[js[0]] else c[js[0]]/o[js[0]]-1
                if len(js)>1: drs[1:]=c[js[1:]]/c[js[:-1]]-1
                drs[-1]-=cost; daily[positions]+=.1*drs
            mask=((calendar_ns>=lo_ns) if lo_ns is not None else np.ones(len(calendar_ns),bool)) & ((calendar_ns<=hi_ns) if hi_ns is not None else np.ones(len(calendar_ns),bool)); idx=np.where(mask)[0]
            per[p]=_metrics(pd.DatetimeIndex([bydate[i] for i in idx]),daily[idx],accepted)
            if p=="ALL": accepted_all=accepted; annual_portfolio=_portfolio_years(bydate,daily,accepted)
            daily2=daily.copy()
            for z in accepted: daily2[pos_ns[z["exit_ns"]]]-=.1*cost
            twice=[{**z,"net":z["gross"]-2*cost} for z in accepted]
            per[p+"_2x"]=_metrics(pd.DatetimeIndex([bydate[i] for i in idx]),daily2[idx],twice)
        event={"n":len(ts),"mean_gross_forward":{str(k):(float(np.mean([t["forward"][str(k)] for t in ts if t["forward"][str(k)] is not None])) if any(t["forward"][str(k)] is not None for t in ts) else None) for k in (1,3,5,10)}}
        event["mean_net_forward_5"]=event["mean_gross_forward"]["5"]-cost if event["mean_gross_forward"]["5"] is not None else None
        event["mean_net_forward_10"]=event["mean_gross_forward"]["10"]-cost if event["mean_gross_forward"]["10"] is not None else None
        cost2=[{**t,"net":t["gross"]-2*cost} for t in ts]
        phases["portfolio"]+=time.perf_counter()-portfolio_start; bootstrap_start=time.perf_counter()
        rngb=np.random.default_rng(SEED+ix)
        bootres={p:_boot([t for t in ts if p=="ALL" or (t["entry_ns"]<=IS_END.value if p=="IS" else t["entry_ns"]>=OOS_START.value)],boot,rngb) for p in ("ALL","IS","OOS")}
        phases["bootstrap"]+=time.perf_counter()-bootstrap_start; random_start=time.perf_counter()
        rand={}
        for p,lo,hi in (("ALL",None,None),("IS",None,IS_END),("OOS",OOS_START,None)):
            sub_lo=lo.value if lo is not None else None; sub_hi=hi.value if hi is not None else None
            subset=[t for t in ts if (sub_lo is None or t["entry_ns"]>=sub_lo) and (sub_hi is None or t["entry_ns"]<=sub_hi)]
            rand[p]=_random_period(subset,frames,g,market,draws,SEED+ix+{"ALL":0,"IS":10000,"OOS":20000}[p])
        phases["random"]+=time.perf_counter()-random_start
        confirmed=ts; unconfirmed=combos[key]["unconfirmed"]; failed=combos[key]["failed"]
        ablation={"confirmed_mean_net":float(np.mean([t["net"] for t in confirmed])) if confirmed else None,"unconditional_mean_net":float(np.mean([t["net"] for t in unconfirmed])) if unconfirmed else None,"failed_trigger_mean_net":float(np.mean([t["net"] for t in failed])) if failed else None,"confirmed_vs_failed_cluster_bootstrap":_cluster_diff(confirmed,failed,boot,rng)}
        rec={"id":ix,"combo":combos[key]["combo"],"event_forward_returns":event,"portfolio":per,"per_year_all":annual_portfolio,"trade_stats":{"n":len(ts),"mean_net":float(np.mean([t["net"] for t in ts])) if ts else None,"mean_gross":float(np.mean([t["gross"] for t in ts])) if ts else None},"random_entry_baseline":rand,"confirmation_ablation":ablation,"cluster_bootstrap":bootres,"bonferroni_p_all":min(1,bootres["ALL"]["p_two_sided"]*128) if bootres["ALL"]["p_two_sided"] is not None else None,"bonferroni_x256_all":min(1,bootres["ALL"]["p_two_sided"]*256) if bootres["ALL"]["p_two_sided"] is not None else None}
        oos_trades=[t["net"] for t in ts if t["entry_ns"]>=OOS_START.value]
        records.append(rec); headlines.append({"id":ix,"N":g[0],"R":g[1],"D":g[2],"M":g[3],"entry":g[4],"exit":g[5],"n":len(ts),"all_mean_net":rec["trade_stats"]["mean_net"],"is_sharpe":per["IS"]["sharpe"],"oos_mean_net":float(np.mean(oos_trades)) if oos_trades else None})
        if (ix+1)%16==0: print(f"combo groups {ix+1}/128",file=sys.stderr)
    for x in records:
        if x["combo"]["M"]==2:
            vals=vol0[str(x["id"])]; peer=next((z for z in records if z["combo"]["N"]==x["combo"]["N"] and z["combo"]["R"]==x["combo"]["R"] and z["combo"]["D"]==x["combo"]["D"] and z["combo"]["entry"]==x["combo"]["entry"] and z["combo"]["exit"]==x["combo"]["exit"] and z["combo"]["M"]==3),None)
            x["volume_ablation_m0"]={"n":len(vals),"mean_net":float(np.mean([z["net"] for z in vals])) if vals else None,"mean_net_m2":x["trade_stats"]["mean_net"],"mean_net_m3":peer["trade_stats"]["mean_net"] if peer else None}
    q=_bh([x["cluster_bootstrap"]["ALL"]["p_two_sided"] for x in records])
    for i,x in enumerate(records): x["bh_q_all"]=q[i]
    eligible=[x for x in records if (x["portfolio"]["IS"]["trades"] or 0)>=30 and x["portfolio"]["IS"]["sharpe"] is not None]
    chosen=max(eligible,key=lambda x:x["portfolio"]["IS"]["sharpe"]) if eligible else None
    corr=spearmanr([x["portfolio"]["IS"]["sharpe"] or 0 for x in records],[x["portfolio"]["OOS"]["sharpe"] or 0 for x in records]).statistic
    isvals=np.array([x["portfolio"]["IS"]["sharpe"] or 0 for x in records]); oosvals=np.array([x["portfolio"]["OOS"]["sharpe"] or 0 for x in records]); top=np.flatnonzero(isvals>=np.quantile(isvals,.75))
    pbo=float(np.mean(oosvals[top]<np.median(oosvals))) if len(top) else None
    verdict="noise"
    if chosen:
        sel=records[chosen["id"]]; qpass=sel["bh_q_all"] is not None and sel["bh_q_all"]<.10
        oos=sel["portfolio"]["OOS"]["mean_trade_return"]
        passrand=all(sel["random_entry_baseline"][p]["percentile"] is not None and sel["random_entry_baseline"][p]["percentile"]>=.95 for p in ("IS","OOS"))
        if oos is not None and oos>0 and qpass and passrand: verdict="helps"
    med=np.median([x["trade_stats"]["mean_net"] for x in records if x["trade_stats"]["mean_net"] is not None]) if any(x["trade_stats"]["mean_net"] is not None for x in records) else None
    if verdict!="helps" and med is not None and med<0 and chosen and chosen["portfolio"]["OOS"]["mean_trade_return"] is not None and chosen["portfolio"]["OOS"]["mean_trade_return"]<0: verdict="hurts"
    annual={}
    for x in records:
        for y,vals in x["per_year_all"].items(): annual.setdefault(y,[]).append(vals["mean_net_trade_return"])
    annual={y:(float(np.median([z for z in v if z is not None and np.isfinite(z)])) if any(z is not None and np.isfinite(z) for z in v) else None) for y,v in annual.items()}
    date_starts=[z["first_date"] for z in coverage]; date_ends=[z["last_date"] for z in coverage]
    report={"metadata":{"market":market,"seed":SEED,"grid_n":128,"universe_names":len(universe),"usable_names":len(frames),"names_with_signals":len({t["code"] for c in combos.values() for t in c["trades"]}),"delisted_present":0,"data_coverage":coverage,"first_date":min(date_starts) if date_starts else None,"last_date":max(date_ends) if date_ends else None,"share_names_first_bar_before_2015":float(np.mean([pd.Timestamp(x["first_date"]).year<2015 for x in coverage])) if coverage else None,"signals_by_N_R_D_M":signal_counts,"source_note":"Current constituents/listings; survivorship bias as preregistered."},"combos":records,"index_buy_hold":_index_metrics(cache,market),"rolling_year_median_over_combos_mean_net_trade_return":annual,"selected":{"combo_id":chosen["id"],"combo":chosen["combo"],"IS":chosen["portfolio"]["IS"],"OOS":chosen["portfolio"]["OOS"]} if chosen else None,"validation":{"spearman_is_oos_sharpe":float(corr) if np.isfinite(corr) else None,"pbo_style_probability_top_is_below_oos_median":pbo,"survivorship":{"delisted_present":0,"n_names":len(universe)},"verdict":verdict}}
    def clean(v):
        if isinstance(v,dict): return {k:clean(x) for k,x in v.items()}
        if isinstance(v,list): return [clean(x) for x in v]
        if isinstance(v,(float,np.floating)) and not np.isfinite(v): return None
        if isinstance(v,np.integer): return int(v)
        return v
    (out/f"results_{market}.json").write_text(json.dumps(clean(report),indent=2,allow_nan=False))
    pd.DataFrame(headlines).to_csv(out/f"combos_{market}.csv",index=False)
    print(json.dumps({"market":market,"usable_names":len(frames),"combos":len(records),"selected_id":report["selected"]["combo_id"] if report["selected"] else None,"files":[str(out/f"results_{market}.json"),str(out/f"combos_{market}.csv")]},indent=2))
    if limit_names is not None:
        phases["load"]+=time.perf_counter()-started-sum(phases.values())
        print("phase_seconds "+json.dumps({**phases,"total":time.perf_counter()-started},sort_keys=True),file=sys.stderr)
    return report

def main():
    p=argparse.ArgumentParser(); p.add_argument("--market",choices=("kr","us"),required=True); p.add_argument("--cache",required=True); p.add_argument("--out",required=True); p.add_argument("--draws",type=int,default=1000); p.add_argument("--boot",type=int,default=5000); p.add_argument("--limit-names",type=int); p.add_argument("--profile-names",type=int,help="print phase timings for a limited run")
    a=p.parse_args(); limit=a.limit_names if a.limit_names is not None else a.profile_names
    run(a.market,a.cache,a.out,a.draws,a.boot,limit)
if __name__=="__main__": main()
