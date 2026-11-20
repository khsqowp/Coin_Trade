"""Single-position OHLC simulator. Signal at close t fills at open t+1."""
import numpy as np

FEE=0.0004
SLIPPAGE=0.0002
CAPITAL=10000.0
BASE_NOTIONAL=1000.0

def _arr(signals, name, default, n):
    if name not in signals: return np.full(n,default,dtype=float)
    return np.asarray(signals[name],dtype=float)

def simulate(df, signals, params=None, side="both", capital=CAPITAL, base_notional=BASE_NOTIONAL, fee=FEE, slippage=SLIPPAGE):
    """Return (trades, metrics). Stops/targets are fractions (0.05 == 5%)."""
    p=dict(params or {}); n=len(df)
    if n==0: return [],metrics([])
    required={"long_entry","short_entry","long_exit","short_exit"}
    if not required.issubset(signals.columns): raise ValueError(f"signals missing {sorted(required-set(signals.columns))}")
    if len(signals)!=n: raise ValueError("signals length must match OHLC frame")
    o,h,l,c=[df[x].to_numpy(float) for x in ("open","high","low","close")]
    le=signals.long_entry.to_numpy(bool); se=signals.short_entry.to_numpy(bool); lx=signals.long_exit.to_numpy(bool); sx=signals.short_exit.to_numpy(bool)
    stopcol=_arr(signals,"stop_pct",np.nan,n); atrcol=_arr(signals,"atr_stop",np.nan,n); tpcol=_arr(signals,"tp_pct",np.nan,n); mhcol=_arr(signals,"max_hold",np.nan,n)
    pos=0; qty=avg=entrycost=0.; entry=0; entry_atr=np.nan; stopdist=np.nan; tpdist=np.nan; maxhold=0; lastfill=0.; adds=0; cash=0.; trades=[]; curve=[]
    def close(i,px,reason):
        nonlocal pos,qty,avg,entrycost,cash,adds
        ep=px*(1-slippage if pos>0 else 1+slippage); net=(ep-avg)*qty*pos-entrycost-ep*qty*fee
        trades.append(dict(entry=int(entry),exit=int(i),side="long" if pos>0 else "short",reason=reason,net=float(net),pct=float(net/capital*100),bars=int(i-entry),adds=adds))
        cash+=net; pos=0; qty=avg=entrycost=0.; adds=0
    for i in range(n):
        if pos:
            adverse=l[i] if pos>0 else h[i]; curve.append(capital+cash+(adverse-avg)*qty*pos-entrycost)
            stop=avg*(1-pos*stopdist) if np.isfinite(stopdist) else None
            target=avg*(1+pos*tpdist) if np.isfinite(tpdist) and tpdist>0 else None
            stop_hit=stop is not None and (l[i]<=stop if pos>0 else h[i]>=stop)
            tp_hit=target is not None and (h[i]>=target if pos>0 else l[i]<=target)
            if stop_hit:
                close(i,o[i] if (o[i]<stop if pos>0 else o[i]>stop) else stop,"stop"); continue
            if tp_hit:
                close(i,o[i] if (o[i]>target if pos>0 else o[i]<target) else target,"tp"); continue
            held=i-entry
            signal_exit=i>0 and (lx[i-1] if pos>0 else sx[i-1])
            if (maxhold and held>=maxhold) or signal_exit:
                close(i,c[i] if maxhold and held>=maxhold else o[i],"time" if maxhold and held>=maxhold else "signal"); continue
            # Optional DCA, only after stop/target checks, matching source simulator.
            if adds<int(p.get("n_adds",0)):
                level=lastfill*(1-pos*float(p.get("add_spacing_pct",0))/100)
                if (l[i]<=level if pos>0 else h[i]>=level):
                    px=(o[i] if (o[i]<level if pos>0 else o[i]>level) else level)*(1+pos*slippage)
                    aq=base_notional*float(p.get("add_size_mult",1))/px; avg=(avg*qty+px*aq)/(qty+aq); qty+=aq; entrycost+=px*aq*fee; lastfill=px; adds+=1
        if not pos and i>0:
            direction=1 if side!="short" and le[i-1] else (-1 if side!="long" and se[i-1] else 0)
            if direction:
                entry=i; pos=direction; px=o[i]*(1+direction*slippage); qty=base_notional/px; avg=px; entrycost=px*qty*fee; lastfill=px
                stopdist=stopcol[i-1] if np.isfinite(stopcol[i-1]) else (atrcol[i-1]/px if np.isfinite(atrcol[i-1]) else np.nan)
                tpdist=tpcol[i-1] if np.isfinite(tpcol[i-1]) else np.nan
                maxhold=int(mhcol[i-1]) if np.isfinite(mhcol[i-1]) and mhcol[i-1]>0 else int(p.get("max_hold",0) or 0)
                adverse=l[i] if direction>0 else h[i]
                curve.append(capital+cash+(adverse-avg)*qty*direction-entrycost)
                stop=avg*(1-direction*stopdist) if np.isfinite(stopdist) else None; target=avg*(1+direction*tpdist) if np.isfinite(tpdist) and tpdist>0 else None
                if stop is not None and (l[i]<=stop if direction>0 else h[i]>=stop): close(i,o[i] if (o[i]<stop if direction>0 else o[i]>stop) else stop,"stop")
                elif target is not None and (h[i]>=target if direction>0 else l[i]<=target): close(i,o[i] if (o[i]>target if direction>0 else o[i]<target) else target,"tp")
                elif int(p.get("n_adds",0))>0:
                    level=lastfill*(1-direction*float(p.get("add_spacing_pct",0))/100)
                    if (l[i]<=level if direction>0 else h[i]>=level):
                        px=(o[i] if (o[i]<level if direction>0 else o[i]>level) else level)*(1+direction*slippage); aq=base_notional*float(p.get("add_size_mult",1))/px
                        avg=(avg*qty+px*aq)/(qty+aq); qty+=aq; entrycost+=px*aq*fee; lastfill=px; adds+=1
    if pos: close(n-1,c[-1],"end_mark")
    return trades,metrics(trades,capital,curve)

def metrics(trades, capital=CAPITAL, equity_curve=None):
    x=np.array([t["net"] for t in trades],float); pct=np.array([t["pct"] for t in trades],float)
    if not len(x): return dict(trades=0,total_return=0.,pf=0.,win_rate=0.,max_dd=0.)
    eq=capital+np.cumsum(x); peaks=np.maximum.accumulate(np.r_[capital,eq]); dd=np.min((eq-peaks[1:])/peaks[1:]*100)
    if equity_curve:
        mtm=np.r_[capital,np.asarray(equity_curve,float),eq[-1]]; dd=min(dd,float(np.min((mtm-np.maximum.accumulate(mtm))/np.maximum.accumulate(mtm)*100)))
    wins=x[x>0]; losses=x[x<0]
    return dict(trades=len(x),total_return=float(pct.sum()),pf=float(wins.sum()/abs(losses.sum())) if len(losses) else float("inf"),win_rate=float(np.mean(x>0)*100),max_dd=float(dd),long=sum(t["side"]=="long" for t in trades),short=sum(t["side"]=="short" for t in trades))
