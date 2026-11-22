"""Signal construction, OHLC position simulation and performance statistics."""
import numpy as np
import pandas as pd
from indicators import bollinger,stochastic,stc,atr

def _recent(x,n):
    return x.copy() if n<=0 else pd.Series(x.astype(np.uint8)).rolling(n+1,min_periods=1).max().to_numpy()>0

def signal_frame(df,p=None,enabled=(1,1,1)):
    p={**dict(bb_n=20,bb_k=2.,bb_use='close',bb_depth_pct=0.,bb_window=0,stoch_level=20,stoch_cross_lag=0,stoch_min_cross_age=0,stoch_k=14,stoch_smooth=3,stoch_d=3,stc_level=25,stc_turn_type=1,stc_min_slope=0.,stc_lag=0,stc_lookback=10,stc_fast=23,stc_slow=50,stc_cycle=10),**(p or {})}
    c=df.close.to_numpy(float);h=df.high.to_numpy(float);l=df.low.to_numpy(float);mid,up,dn=bollinger(c,p['bb_n'],p['bb_k']);k,d=stochastic(h,l,c,p['stoch_k'],p['stoch_smooth'],p['stoch_d']);t=stc(c,p['stc_fast'],p['stc_slow'],p['stc_cycle'])
    lp=c if p['bb_use']=='close' else l;sp=c if p['bb_use']=='close' else h;width=up-dn
    bl=_recent((lp<dn)&((dn-lp)>=width*p['bb_depth_pct']/100),p['bb_window']);bs=_recent((sp>up)&((sp-up)>=width*p['bb_depth_pct']/100),p['bb_window'])
    crossup=np.r_[False,(k[1:]>d[1:])&(k[:-1]<=d[:-1])];crossdn=np.r_[False,(k[1:]<d[1:])&(k[:-1]>=d[:-1])]
    def qualified(cross,long):
        lag=p['stoch_cross_lag'];age=p['stoch_min_cross_age'];level=p['stoch_level'] if long else 100-p['stoch_level']; zone=(k<level)&(d<level) if long else (k>level)&(d>level)
        # A qualifying cross lies between i-lag and i-age inclusive.
        eligible=cross&zone
        delayed=np.r_[np.zeros(age,bool),eligible[:max(0,len(eligible)-age)]] if age else eligible
        return pd.Series(delayed.astype(np.uint8)).rolling(lag-age+1,min_periods=1).max().to_numpy()>0
    su=qualified(crossup,True);sd=qualified(crossdn,False)
    def turns(long):
        n=p['stc_turn_type'];slope=p['stc_min_slope'];deltas=np.diff(t,prepend=np.nan)
        ok=deltas>=slope if long else deltas<=-slope
        # Every n successive one-bar slopes must qualify.
        x=pd.Series(ok.astype(np.uint8)).rolling(n,min_periods=n).min().to_numpy()>0
        zone=t<p['stc_level'] if long else t>100-p['stc_level'];prior=pd.Series(zone.astype(np.uint8)).rolling(p['stc_lookback']+1,min_periods=1).max().to_numpy()>0
        eligible=x&prior
        return pd.Series(eligible.astype(np.uint8)).rolling(p['stc_lag']+1,min_periods=1).max().to_numpy()>0
    tu=turns(True);td=turns(False); cond=(bl,su,tu);conds=(bs,sd,td)
    long=np.logical_and.reduce([x for x,on in zip(cond,enabled) if on]) if any(enabled) else np.ones(len(c),bool);short=np.logical_and.reduce([x for x,on in zip(conds,enabled) if on]) if any(enabled) else np.ones(len(c),bool)
    return pd.DataFrame({'long':long,'short':short,'bb_long':bl,'stoch_long':su,'stc_long':tu,'bb_short':bs,'stoch_short':sd,'stc_short':td,'bb_mid':mid,'atr':atr(h,l,c)},index=df.index)

def is_coherent(n_adds,spacing_pct,sl_pct,atr_mult=None,atr_pct_at_entry=None):
    """An ATR stop is coherent only when entry ATR percent stop clears the final DCA level."""
    stop=sl_pct if sl_pct is not None else (atr_mult*atr_pct_at_entry if atr_mult is not None and atr_pct_at_entry is not None else None)
    return stop is None or stop>max(0,n_adds)*spacing_pct

def simulate(df,sig,p,side='combined',capital=10000,base_notional=1000,fee=.0004,slippage=.0002,include_trade_details=False):
    """Next-open fill; check entry-bar OHLC immediately, pessimistically stop before target/adds."""
    o,h,l,c=[df[x].to_numpy(float) for x in ['open','high','low','close']];n=len(c);long=sig.long.to_numpy();short=sig.short.to_numpy();mid=sig.bb_mid.to_numpy();av=sig.atr.to_numpy()
    trades=[];pos=0;qty=0.;avg=0.;adds=0;entry_i=0;cash=0.;lastfill=0.;entry_cost=0.;equity_curve=[]
    def close_trade(i,px,reason):
        nonlocal pos,qty,avg,adds,cash,entry_cost
        exitpx=px*(1-slippage if pos>0 else 1+slippage);gross=(exitpx-avg)*qty*pos;costs=entry_cost+exitpx*qty*fee;net=gross-costs
        trades.append(dict(side='long' if pos>0 else 'short',entry=entry_i,exit=i,bars=i-entry_i,net=net,pct=net/capital*100,reason=reason,adds=adds,entry_atr=entry_atr,entry_atr_pct=entry_atr/avg*100 if np.isfinite(entry_atr) else np.nan));cash+=net;pos=0;qty=avg=0.;adds=0;entry_cost=0.
    entry_atr=np.nan
    for i in range(n):
        # Equity at bar extremes uses the adverse side of OHLC for any open position.
        if pos:
            adverse=l[i] if pos>0 else h[i];equity_curve.append(capital+cash+(adverse-avg)*qty*pos-entry_cost)
            atr_mult=p.get('atr_mult');stopdist=(p.get('sl_pct')/100 if p.get('sl_pct') is not None else (atr_mult*entry_atr/avg if atr_mult is not None and np.isfinite(entry_atr) else 999))
            stop=avg*(1-pos*stopdist);tp=avg*(1+pos*p['tp_pct']/100) if p.get('tp_pct') else None
            stop_hit=(l[i]<=stop if pos>0 else h[i]>=stop);tp_hit=tp is not None and (h[i]>=tp if pos>0 else l[i]<=tp)
            if stop_hit:close_trade(i,o[i] if (o[i]<stop if pos>0 else o[i]>stop) else stop,'stop');continue
            if tp_hit:close_trade(i,o[i] if (o[i]>tp if pos>0 else o[i]<tp) else tp,'tp');continue
            if p.get('max_hold_bars') and i-entry_i>=p['max_hold_bars']:close_trade(i,c[i],'time');continue
            if p.get('bb_mid_exit') and ((pos>0 and h[i]>=mid[i]) or (pos<0 and l[i]<=mid[i])):close_trade(i,mid[i],'mid');continue
            if adds<p.get('n_adds',0):
                level=lastfill*(1-pos*p.get('add_spacing_pct',0)/100);touched=(l[i]<=level if pos>0 else h[i]>=level)
                if touched:
                    px=o[i] if (o[i]<level if pos>0 else o[i]>level) else level;px*=1+pos*slippage;aq=base_notional*p.get('add_size_mult',1)/px;avg=(avg*qty+px*aq)/(qty+aq);qty+=aq;entry_cost+=px*aq*fee;lastfill=px;adds+=1
            if p.get('opp_exit') and ((pos>0 and short[i]) or (pos<0 and long[i])):close_trade(i,c[i],'opposite')
        if pos==0 and i>0:
            # One portfolio position: side-specific runs filter signals, combined gives
            # long precedence when both arrive on the same closed bar.
            direction=(1 if long[i-1] else 0) if side=='long' else ((-1 if short[i-1] else 0) if side=='short' else (1 if long[i-1] else (-1 if short[i-1] else 0)))
            if direction:
                px=o[i]*(1+direction*slippage);candidate_atr=av[i-1] if i>0 else np.nan
                if not is_coherent(p.get('n_adds',0),p.get('add_spacing_pct',0),p.get('sl_pct'),p.get('atr_mult'),100*candidate_atr/px if np.isfinite(candidate_atr) else None):continue
                pos=direction;entry_i=i;qty=base_notional/px;avg=px;entry_cost=px*qty*fee;lastfill=px;adds=0;entry_atr=candidate_atr
                adverse=l[i] if pos>0 else h[i];equity_curve.append(capital+cash+(adverse-avg)*qty*pos-entry_cost)
                atr_mult=p.get('atr_mult');stopdist=(p.get('sl_pct')/100 if p.get('sl_pct') is not None else (atr_mult*entry_atr/avg if atr_mult is not None and np.isfinite(entry_atr) else 999));stop=avg*(1-pos*stopdist);tp=avg*(1+pos*p['tp_pct']/100) if p.get('tp_pct') else None
                if (l[i]<=stop if pos>0 else h[i]>=stop):close_trade(i,o[i] if (o[i]<stop if pos>0 else o[i]>stop) else stop,'stop')
                elif tp is not None and (h[i]>=tp if pos>0 else l[i]<=tp):close_trade(i,o[i] if (o[i]>tp if pos>0 else o[i]<tp) else tp,'tp')
                elif adds<p.get('n_adds',0):
                    level=lastfill*(1-pos*p.get('add_spacing_pct',0)/100);touched=(l[i]<=level if pos>0 else h[i]>=level)
                    if touched:
                        addpx=o[i] if (o[i]<level if pos>0 else o[i]>level) else level;addpx*=1+pos*slippage;aq=base_notional*p.get('add_size_mult',1)/addpx;avg=(avg*qty+addpx*aq)/(qty+aq);qty+=aq;entry_cost+=addpx*aq*fee;lastfill=addpx;adds+=1
    if pos:close_trade(n-1,c[-1],'end_mark')
    result=metrics(trades,capital,equity_curve)
    if include_trade_details:
        result['trade_details']=[{'entry':int(t['entry']),'exit':int(t['exit']),'side':t['side'],'return':float(t['pct'])} for t in trades]
    return result

def metrics(trades,capital=10000,equity_curve=None):
    if not trades:return dict(trades=0,win_rate=0,avg_win=0,avg_loss=0,pf=0,total_return=0,max_dd=0,closed_trade_max_dd=0,sharpe=0,avg_hold=0,worst=0,dca_fills=0,stopouts=0,long=0,short=0)
    x=np.array([t['net'] for t in trades]);eq=capital+np.cumsum(x);peaks=np.maximum.accumulate(np.r_[capital,eq]);closed_dd=(eq-peaks[1:])/peaks[1:]*100
    mtm=np.asarray(equity_curve if equity_curve is not None else eq,float);mtm=np.r_[capital,mtm,eq[-1]];peak=np.maximum.accumulate(mtm);dd=(mtm-peak)/peak*100
    wins=x[x>0];loss=x[x<0]
    return dict(trades=len(x),win_rate=float((x>0).mean()*100),avg_win=float(wins.mean()) if len(wins) else 0,avg_loss=float(loss.mean()) if len(loss) else 0,pf=float(wins.sum()/abs(loss.sum())) if len(loss) else float('inf'),total_return=float(x.sum()/capital*100),max_dd=float(dd.min()),closed_trade_max_dd=float(closed_dd.min()),sharpe=float(x.mean()/x.std()*np.sqrt(len(x))) if x.std() else 0,avg_hold=float(np.mean([t['bars'] for t in trades])),worst=float(x.min()),dca_fills=int(sum(t['adds'] for t in trades)),stopouts=int(sum(t['reason']=='stop' for t in trades)),long=int(sum(t['side']=='long' for t in trades)),short=int(sum(t['side']=='short' for t in trades)))
