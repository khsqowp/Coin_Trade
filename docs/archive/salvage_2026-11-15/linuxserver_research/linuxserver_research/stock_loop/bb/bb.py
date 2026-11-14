"""Vectorised panel and trade engine for the preregistered BB-01 screen."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent

class Panel:
    pass

def load_dataset(name):
    tz='America/New_York' if name=='us' else 'Asia/Seoul'
    if name in ('us','kr'):
        d=pd.read_parquet(ROOT/'cache'/f'{name}_5m.parquet')
    elif name in ('tick1','tick5'):
        d=pd.read_parquet(ROOT/'cache'/'kr_tick_1m.parquet')
        d['ts']=pd.to_datetime(d.ts)
        if name=='tick5':
            d=d.set_index('ts').groupby('symbol').resample('5min',label='left',closed='left').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('n_ticks','sum')).dropna(subset=['open']).reset_index()
        else: d=d.rename(columns={'n_ticks':'volume'})
    else: raise ValueError(name)
    d['ts']=pd.to_datetime(d.ts)
    if d.ts.dt.tz is None: d['ts']=d.ts.dt.tz_localize(tz)
    else: d['ts']=d.ts.dt.tz_convert(tz)
    d=d.sort_values(['ts','symbol']); syms=sorted(d.symbol.unique()); times=pd.DatetimeIndex(sorted(d.ts.unique()))
    T,N=len(times),len(syms); ti=pd.Index(times); ni=pd.Index(syms)
    arrays={k:np.full((T,N),np.nan,np.float32) for k in ['open','high','low','close','volume']}
    ri=ti.get_indexer(d.ts); ci=ni.get_indexer(d.symbol)
    for k in arrays: arrays[k][ri,ci]=pd.to_numeric(d[k],errors='coerce').to_numpy(np.float32)
    valid=np.isfinite(arrays['close']) & (arrays['close']>0)
    sessions=pd.Index(times.date); unique=list(dict.fromkeys(sessions)); sid=np.array([unique.index(x) for x in sessions],np.int16)
    bod=np.zeros(T,np.int16); first=np.full(T,-1,np.int32); last=np.full(T,-1,np.int32)
    for s in np.unique(sid):
        ix=np.flatnonzero(sid==s); first[ix]=ix[0]; last[ix]=ix[-1]; bod[ix]=np.arange(len(ix))
    # Fill only internal missing bars; never turn the fill into a tradable observation.
    for j in range(N):
        prev=np.nan
        for t in range(T):
            if t and sid[t]!=sid[t-1]: prev=np.nan
            if valid[t,j]: prev=arrays['close'][t,j]
            elif np.isfinite(prev):
                for k in ('open','high','low','close'): arrays[k][t,j]=prev
    prevclose=np.full((T,N),np.nan,np.float32)
    for s in range(1,len(unique)):
        now=np.flatnonzero(sid==s); old=np.flatnonzero(sid==s-1)
        for j in range(N):
            ok=old[valid[old,j]]
            if len(ok): prevclose[now,j]=arrays['close'][ok[-1],j]
    p=Panel(); p.name=name; p.warm_sessions=10 if name in ('us','kr') else 1; p.times=times; p.symbols=syms; p.T=T; p.N=N
    p.O,p.H,p.L,p.C,p.V=(arrays[k] for k in ('open','high','low','close','volume'))
    p.valid=valid; p.session=sid; p.session_dates=np.array(unique,dtype=object); p.bod=bod; p.first=first; p.last=last; p.prevclose=prevclose
    p.value20=np.full(N,np.nan); p.value20_by_session=np.full((len(unique),N),np.nan)
    if name=='kr':
        try:
            meta=json.loads((ROOT/'cache'/'fetch_meta.json').read_text()); vals=meta['kr'].get('value20_by_code',{})
            for j,sym in enumerate(syms): p.value20[j]=vals.get(sym[:6],np.nan)
        except Exception: pass
    elif name.startswith('tick'):
        for j,sym in enumerate(syms):
            code=str(sym).split('.')[0]
            try:
                dly=pd.read_parquet(Path('/home/noroot/research/gulp_pattern/cache/kr')/f'{code}.parquet')
                dly.columns=[str(c).lower() for c in dly.columns]
                p.value20[j]=float((dly.close*dly.volume).tail(20).mean())
            except Exception: p.value20[j]=np.nan
    else: p.value20[:]=np.nan
    return p

def bollinger(C,n=20,k=2.0):
    x=np.asarray(C,float); T,N=x.shape; mid=np.full((T,N),np.nan); sd=mid.copy()
    for j in range(N):
        v=pd.Series(x[:,j]); mid[:,j]=v.rolling(n,min_periods=n).mean().to_numpy(); sd[:,j]=v.rolling(n,min_periods=n).std(ddof=0).to_numpy()
    return mid-k*sd,mid,mid+k*sd

def candidates(p):
    with np.errstate(divide='ignore',invalid='ignore'): pct=p.C/p.prevclose-1
    rank=np.full(p.C.shape,np.nan)
    for t in range(p.T):
        ix=np.flatnonzero(p.valid[t]&np.isfinite(pct[t]));
        if len(ix): rank[t,ix]=1+np.argsort(np.argsort(-pct[t,ix],kind='stable'),kind='stable')
    active=np.ones_like(p.valid)
    if p.name in ('us','kr'):
        value=p.C*p.V; cum=np.zeros_like(value)
        for t in range(p.T): cum[t]=np.nan_to_num(value[t],nan=0.0)+(cum[t-1] if t and p.session[t]==p.session[t-1] else 0)
        session_rows=[np.flatnonzero(p.session==s) for s in range(int(p.session.max())+1)]
        for s,rows in enumerate(session_rows):
            earlier=range(max(0,s-20),s)
            if s<10: active[rows]=False; continue
            for t in rows:
                b=p.bod[t]; hist=[]
                for old in earlier:
                    oldrows=session_rows[old]
                    if b<len(oldrows): hist.append(cum[oldrows[b]])
                if len(hist)<10: active[t]=False; continue
                h=np.asarray(hist); count=np.isfinite(h).sum(axis=0)
                avg=np.divide(np.nansum(h,axis=0),count,out=np.full(p.N,np.nan),where=count>0)
                active[t]=np.isfinite(cum[t])&np.isfinite(avg)&(cum[t]>=1.5*avg)
    warm=p.session>=p.warm_sessions
    return rank,active,warm

def candidate_state(p,rank,active,fill):
    if fill!='opt': return rank,active
    prev_rank=np.full_like(rank,np.nan); prev_active=np.zeros_like(active)
    same=p.session[1:]==p.session[:-1]
    prev_rank[1:]=np.where(same[:,None],rank[:-1],np.nan)
    prev_active[1:]=same[:,None]&active[:-1]
    # A resting order can fill intrabar, so eligibility must use the prior bar's state.
    return prev_rank,prev_active

def simulate_entries(p,bands,params,fill='base'):
    """Simulate every signal with a vectorised time-by-symbol state matrix."""
    lo,middle,upper=bands; exitband=upper if params['target']=='upper' else middle
    T,N=p.C.shape; ti=np.arange(T,dtype=np.int32)[:,None]; cols=np.broadcast_to(np.arange(N),(T,N))
    entry_off=0 if fill=='opt' else 1; et=ti+entry_off; safe=np.minimum(et,T-1)
    possible=np.broadcast_to((et<T)&(p.session[safe]==p.session[:,None]),(T,N))
    ent=np.where(possible,np.broadcast_to(et,(T,N)),np.nan).astype(float)
    if fill=='opt': ep=np.minimum(p.O,np.vstack([np.full((1,N),np.nan),lo[:-1]]))
    else: ep=p.O[safe,cols]
    entry_valid=p.valid[safe,cols] if fill=='base' else p.valid
    ep=np.where(possible&entry_valid&(ep>0),ep,np.nan)
    ex=np.full((T,N),np.nan); xp=np.full((T,N),np.nan); reason=np.full((T,N),'',object)
    active=np.isfinite(ep); stop_level=ep*(1-float(params['stop']))
    for off in range(13):
        q=np.broadcast_to(ti+entry_off+off,(T,N)); sq=np.minimum(q,T-1)
        live=active&(q<T)&(p.session[sq]==p.session[:,None])
        if not live.any(): break
        op=p.O[sq,cols]; low=p.L[sq,cols]; high=p.H[sq,cols]; close=p.C[sq,cols]
        skip=fill=='opt' and off==0
        sh=(live&(low<=stop_level)) if not skip else np.zeros_like(live)
        ex[sh]=sq[sh]; xp[sh]=np.minimum(op[sh],stop_level[sh]); reason[sh]='stop'; active[sh]=False
        rem=live&active; bq=np.maximum(sq-1,0) if fill=='opt' else sq; band=exitband[bq,cols]
        th=(rem&np.isfinite(band)&(high>=band)) if not skip else np.zeros_like(rem)
        if th.any():
            last=sq>=p.last[:,None]
            nq=np.minimum(sq+1,T-1)
            if fill=='opt': px=np.maximum(op,band); xi=sq
            else: px=np.where(last,close,p.O[nq,cols]); xi=np.where(last,sq,nq)
            ex[th]=xi[th]; xp[th]=px[th]; reason[th]='target'; active[th]=False
        rem=live&active; terminal=rem&((off==12)|(sq>=p.last[:,None]))
        if terminal.any():
            ex[terminal]=sq[terminal]; xp[terminal]=close[terminal]
            reason[terminal]=np.where(off==12,'time','session'); active[terminal]=False
    with np.errstate(divide='ignore',invalid='ignore'): gross=xp/ep-1
    return {'entry_idx':ent,'exit_idx':ex,'entry_px':ep,'exit_px':xp,'gross':gross,'reason':reason}

def signal_mask(p,lo,rank,active,warm,filter_name,fill):
    rank,active=candidate_state(p,rank,active,fill)
    touch=p.L<= (lo if fill=='base' else np.vstack([np.full((1,p.N),np.nan),lo[:-1]]))
    ok=p.valid & np.isfinite(lo) & touch & warm[:,None]
    late=np.array([p.last[t]-t<3 for t in range(p.T)])
    ok &= ~late[:,None]
    if filter_name=='A0': ok &= (rank>=20)&(rank<=50)&active
    elif filter_name=='A1': ok &= active
    return ok

def portfolio(trades,signals,priority_seed=7):
    import heapq
    rng=np.random.default_rng(priority_seed); rows=[]
    T,N=signals.shape
    for t in range(T):
        ids=np.flatnonzero(signals[t]&np.isfinite(trades['gross'][t]))
        if len(ids):
            for j in ids: rows.append((t,int(j),float(rng.random())))
    rows.sort(key=lambda z:(z[0],z[2])); accepted=[]; bysym=np.full(N,-1); open_exits=[]
    for t,j,key in rows:
        e=int(trades['entry_idx'][t,j]); x=int(trades['exit_idx'][t,j])
        if not np.isfinite(e+x) or e<=bysym[j]: continue
        # Concurrent-position count uses accepted intervals [entry,exit].
        while open_exits and open_exits[0] < e: heapq.heappop(open_exits)
        if len(open_exits)>=5: continue
        g=float(trades['gross'][t,j]); accepted.append(dict(signal_idx=t,symbol_idx=j,entry_idx=e,exit_idx=x,entry_px=trades['entry_px'][t,j],exit_px=trades['exit_px'][t,j],gross=g,reason=trades['reason'][t,j],priority=key)); bysym[j]=x; heapq.heappush(open_exits,x)
    return accepted

def _costs(p, trades, model='base'):
    try:
        import sys; sys.path.insert(0,'/home/noroot/research/stock_loop')
        from lib.costs import KRCost,USCost
    except Exception:
        # Same formulas as lib.costs, retained for local synthetic self-tests.
        KRCost=USCost=None
    j=trades['symbol_idx']; v=p.value20[j]
    if p.name=='us':
        base=USCost() if USCost else None
        c=float(base.roundtrip()) if base else .0030278
        c=np.full(len(j),c)
        return c, c, 2*c
    if KRCost:
        cm=KRCost('B'); ca=KRCost('A'); c2=cm.with_(mult=2)
        return cm.roundtrip(v),ca.roundtrip(v),c2.roundtrip(v)
    slip=np.where(np.nan_to_num(v,nan=0)>=2e10,.0005,.001)
    c=.002+.0003+2*slip
    return c,c,2*c

def _stats(p, accepted, half_boundary=None):
    if not accepted: return {'n':0,'trades_per_session':0}
    d={'signal_idx':np.array([a['signal_idx'] for a in accepted]),'symbol_idx':np.array([a['symbol_idx'] for a in accepted])}
    gross=np.array([a['gross'] for a in accepted]); c,ca,c2=_costs(p,d)
    net=gross-c; dates=np.array([p.session_dates[p.session[a['signal_idx']]] for a in accepted],object)
    try:
        import sys; sys.path.insert(0,'/home/noroot/research/stock_loop'); from lib.eventstudy import cluster_t
        mean,t=cluster_t(net,dates)
    except Exception:
        mean=float(net.mean()); groups={x:net[dates==x].sum() for x in set(dates)}; se=np.sqrt(sum(v*v for v in groups.values()))/len(net); t=mean/se if se else np.nan
    unique=max(1,len(set(dates)))
    out={'n':len(net),'trades_per_session':len(net)/unique,'gross_mean':float(gross.mean()),'net_mean':float(net.mean()),'cluster_t':float(t),'naive_t':float(net.mean()/(net.std(ddof=1)/np.sqrt(len(net)))) if len(net)>1 and net.std(ddof=1)>0 else None,'win_rate':float((net>0).mean()),'median':float(np.median(net)),'avg_hold_bars':float(np.mean([a['exit_idx']-a['entry_idx'] for a in accepted])),'exit_shares':{k:float(np.mean([a['reason']==k for a in accepted])) for k in ['stop','target','time','session']},'break_even_rt_cost':float(gross.mean()),'avg_cost':float(c.mean()),'net_A_mean':float((gross-ca).mean()),'net_2x_mean':float((gross-c2).mean()),'worst_trade':float(net.min())}
    if half_boundary is not None:
        out['h1_net_mean']=float(net[dates<half_boundary].mean()) if (dates<half_boundary).any() else None
        out['h2_net_mean']=float(net[dates>=half_boundary].mean()) if (dates>=half_boundary).any() else None
    return out

def evaluate(p, cell, phase='dev', cache=None):
    cache=cache if cache is not None else {}
    if 'candidates' not in cache: cache['candidates']=candidates(p)
    rank,active,warm=cache['candidates']; key=(cell['k'],cell['exit'],cell['stop'],cell['fill'])
    if key not in cache:
        bands=bollinger(p.C,20,cell['k'])
        cache[key]=(bands,simulate_entries(p,bands,{'target':cell['exit'],'stop':cell['stop']},cell['fill']))
    bands,sim=cache[key]
    mask=signal_mask(p,bands[0],rank,active,warm,cell['filter'],cell['fill'])
    # Restrict signal bars to requested chronological split.
    sessions=np.arange(len(p.session_dates)); trad=sessions[sessions>=p.warm_sessions]; cut=int(np.floor(.7*len(trad)))
    allowed=trad[:cut] if phase=='dev' else trad[cut:]
    mask &= np.isin(p.session,allowed)[:,None]
    accepted=portfolio(sim,mask); boundary=p.session_dates[p.warm_sessions+cut//2] if len(trad)>cut else None
    out=_stats(p,accepted,boundary if phase=='dev' else None)
    out['trades']=[dict(signal_idx=a['signal_idx'],symbol=p.symbols[a['symbol_idx']],entry_idx=a['entry_idx'],exit_idx=a['exit_idx'],gross=a['gross'],reason=a['reason']) for a in accepted]
    return out
