"""Causal deterministic price-action setup signals for P5."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from . import indicators

SETUPS = ("supertrend", "trendline_breakout", "sr_retest", "sweep_choch_retest",
          "avwap_hl", "rsi_divergence", "candle_reversal", "fibonacci_pocket",
          "order_block", "fabio_liquidity_mss")

@dataclass(frozen=True)
class Signal:
    index: int
    side: str
    stop: float

def generate_signals(frame, setup, prepared=None):
    """Emit closed-bar signals; any pivot is consumed only at confirmation index."""
    if setup not in SETUPS:
        raise ValueError(f"unknown setup: {setup}")
    o,h,l,c,v = (frame[x].to_numpy(float) for x in ("o","h","l","c","v"))
    n=len(c)
    prepared=prepared or {}
    a=prepared["atr"] if "atr" in prepared else indicators.atr(h,l,c,14)
    swings=prepared.get("swings")
    sh,sl=swings if swings is not None else indicators.confirmed_swings(h,l,3)
    out=[]
    def emit(i, side, stop):
        if i+1<n and np.isfinite(stop) and stop>0 and ((side=="long" and stop<c[i]) or (side=="short" and stop>c[i])):
            out.append(Signal(i,side,float(stop)))
    if setup=="supertrend":
        direction=indicators.supertrend_direction(h,l,c,a)
        for i in range(1,n):
            mid=(h[i]+l[i])/2
            if direction[i]!=direction[i-1] and direction[i]: emit(i,"long" if direction[i]>0 else "short", mid-3*a[i] if direction[i]>0 else mid+3*a[i])
    elif setup=="trendline_breakout":
        # Fixed-window O(n) regression: equivalent to polyfit over x=0..19,
        # while avoiding millions of tiny LAPACK calls on 1m data.
        coeff=np.arange(20,dtype=float)-9.5
        weighted=np.convolve(c,coeff[::-1],mode="valid")
        sums=np.convolve(c,np.ones(20),mode="valid")
        slopes=weighted/665.0; intercepts=sums/20-slopes*9.5
        lines=intercepts+slopes*20; prev_lines=intercepts+slopes*19
        for i in range(30,n):
            if not np.isfinite(a[i]): continue
            k=i-20
            if c[i]>lines[k] and c[i-1]<=prev_lines[k]: emit(i,"long",c[i]-3*a[i])
            if c[i]<lines[k] and c[i-1]>=prev_lines[k]: emit(i,"short",c[i]+3*a[i])
    elif setup=="sr_retest":
        for side in ("long","short"):
            level=None; broken=False; known=[]
            for i in range(10,n):
                for pivot in (sh[i],sl[i]):
                    if np.isfinite(pivot): known.append(float(pivot))
                known=known[-60:]
                if not broken:
                    known_arr=np.asarray(known,float)
                    cand=known_arr[known_arr<c[i]] if side=="long" else known_arr[known_arr>c[i]]
                    if len(cand): level=float(cand[-1])
                    if level and ((c[i]>level and c[i-1]<=level) if side=="long" else (c[i]<level and c[i-1]>=level)): broken=True
                elif level and ((l[i]<=level*1.003 and c[i]>level and c[i]>o[i]) if side=="long" else (h[i]>=level*.997 and c[i]<level and c[i]<o[i])):
                    emit(i,side,l[i] if side=="long" else h[i]); broken=False; level=None
    elif setup=="sweep_choch_retest":
        for side in ("long","short"):
            sweep=None; choch=None
            for i in range(3,n):
                piv=sl[i-3] if side=="long" else sh[i-3]
                if np.isfinite(piv) and ((l[i]<piv<c[i]) if side=="long" else (h[i]>piv>c[i])): sweep=(i,float(l[i] if side=="long" else h[i]))
                if sweep and i>sweep[0] and ((c[i]>max(h[sweep[0]:i]) if side=="long" else c[i]<min(l[sweep[0]:i]))): choch=(i,sweep[1],float((o[i-1]+c[i-1])/2))
                if choch and i>choch[0] and ((l[i]<=choch[2]<=c[i]) if side=="long" else (h[i]>=choch[2]>=c[i])): emit(i,side,choch[1]); sweep=choch=None
    elif setup=="avwap_hl":
        prev_lows=[]; prev_highs=[]
        for i in range(3,n):
            if np.isfinite(sl[i]) and i>0:
                if prev_lows and sl[i]>prev_lows[-1]:
                    anchor=i-3; p=(h[anchor:i+1]+l[anchor:i+1]+c[anchor:i+1])/3; vw=np.average(p,weights=np.maximum(v[anchor:i+1],1e-12))
                    if l[i]<=vw*1.003 and c[i]>vw and c[i]>o[i]: emit(i,"long",sl[i])
            if np.isfinite(sh[i]):
                if prev_highs and sh[i]<prev_highs[-1]:
                    anchor=i-3; p=(h[anchor:i+1]+l[anchor:i+1]+c[anchor:i+1])/3; vw=np.average(p,weights=np.maximum(v[anchor:i+1],1e-12))
                    if h[i]>=vw*.997 and c[i]<vw and c[i]<o[i]: emit(i,"short",sh[i])
            if np.isfinite(sl[i]): prev_lows.append(float(sl[i]))
            if np.isfinite(sh[i]): prev_highs.append(float(sh[i]))
    elif setup=="rsi_divergence":
        r=prepared["rsi"] if "rsi" in prepared else indicators.rsi(c,14); lows=[]; highs=[]
        for i in range(n):
            if np.isfinite(sl[i]):
                if lows and sl[i]<lows[-1][1] and r[i]>lows[-1][2]: emit(i,"long",sl[i])
                lows.append((i,sl[i],r[i]))
            if np.isfinite(sh[i]):
                if highs and sh[i]>highs[-1][1] and r[i]<highs[-1][2]: emit(i,"short",sh[i])
                highs.append((i,sh[i],r[i]))
    elif setup=="candle_reversal":
        pat=prepared["patterns"] if "patterns" in prepared else indicators.candle_patterns(o,h,l,c)
        vw=prepared["vwap"] if "vwap" in prepared else indicators.vwap(h,l,c,v,frame.t_open_ms)
        zones=[]
        for i in range(1,n):
            if np.isfinite(sh[i]): zones.append(float(sh[i]))
            if np.isfinite(sl[i]): zones.append(float(sl[i]))
            near=abs(c[i]-vw[i])<=.5*a[i] or (bool(zones) and np.min(np.abs(c[i]-np.asarray(zones[-60:])))<=.5*a[i])
            if near and (pat["bull_engulfing"][i-1] or pat["hammer_pin"][i-1]) and c[i]>h[i-1]: emit(i,"long",l[i-1])
            if near and (pat["bear_engulfing"][i-1] or pat["shooting_star_pin"][i-1]) and c[i]<l[i-1]: emit(i,"short",h[i-1])
    elif setup=="fibonacci_pocket":
        lastlo=lasthi=None
        for i in range(n):
            if np.isfinite(sl[i]): lastlo=(i,float(sl[i]))
            if np.isfinite(sh[i]): lasthi=(i,float(sh[i]))
            if lastlo and lasthi and lastlo[0]<lasthi[0] and i>lasthi[0]:
                lo,hi=lastlo[1],lasthi[1]; z1=hi-.786*(hi-lo); z2=hi-.618*(hi-lo)
                if z1<=l[i]<=z2 and c[i]>o[i]: emit(i,"long",lo-.886*(hi-lo))
            if lastlo and lasthi and lasthi[0]<lastlo[0] and i>lastlo[0]:
                hi,lo=lasthi[1],lastlo[1]; z1=lo+.618*(hi-lo); z2=lo+.786*(hi-lo)
                if z1<=h[i]<=z2 and c[i]<o[i]: emit(i,"short",hi+.886*(hi-lo))
    elif setup=="order_block":
        zones=[]
        for i in range(n):
            remaining=[]
            for low,high,born,side in zones:
                invalid=(i-born>60 or (c[i]<low if side=="long" else c[i]>high))
                if invalid: continue
                if l[i]<=high and h[i]>=low and (c[i]>high if side=="long" else c[i]<low):
                    emit(i,side,low if side=="long" else high)
                    # Port semantics: signal-fired zones are dropped because the original
                    # remaining-list branch appends only in its `else` arm.
                else: remaining.append((low,high,born,side))
            zones=remaining
            if i>=14 and np.isfinite(a[i-1]):
                if c[i]-o[i]>1.5*a[i-1] and c[i]>h[i-1]:
                    for j in range(i-1,max(-1,i-6),-1):
                        if c[j]<o[j]: zones.append((l[j],h[j],i,"long")); break
                # Symmetric short side is an extension; the cited source defines long only.
                if o[i]-c[i]>1.5*a[i-1] and c[i]<l[i-1]:
                    for j in range(i-1,max(-1,i-6),-1):
                        if c[j]>o[j]: zones.append((l[j],h[j],i,"short")); break
    elif setup=="fabio_liquidity_mss":
        if n>=2:
            bar_minutes=round((int(frame.t_open_ms.iloc[1])-int(frame.t_open_ms.iloc[0]))/60000)
            if bar_minutes>0:
                htf_minutes=60 if bar_minutes<60 else 4*bar_minutes
                bar_length=max(1,round(htf_minutes/bar_minutes))
                last_hi=pd.Series(h).rolling(bar_length,min_periods=bar_length).max().shift(1).to_numpy()
                last_lo=pd.Series(l).rolling(bar_length,min_periods=bar_length).min().shift(1).to_numpy()
                mss_hi=pd.Series(h).rolling(4,min_periods=4).max().shift(1).to_numpy()
                mss_lo=pd.Series(l).rolling(4,min_periods=4).min().shift(1).to_numpy()
                state="waiting"; locked_high=locked_low=grab_level=None; entry_type=None
                for i in range(n):
                    if state=="waiting":
                        if np.isfinite(last_hi[i]) and h[i]>last_hi[i]:
                            locked_high,locked_low,grab_level,entry_type=mss_hi[i],mss_lo[i],last_hi[i],"short"; state="waiting_for_mss"
                        elif np.isfinite(last_lo[i]) and l[i]<last_lo[i]:
                            locked_high,locked_low,grab_level,entry_type=mss_hi[i],mss_lo[i],last_lo[i],"long"; state="waiting_for_mss"
                    elif entry_type=="short" and np.isfinite(locked_low) and l[i]<locked_low:
                        emit(i,"short",grab_level); state="waiting"
                    elif entry_type=="long" and np.isfinite(locked_high) and h[i]>locked_high:
                        emit(i,"long",grab_level); state="waiting"
                    # The Pine armed state has no timeout/opposite-grab reset; this port likewise waits
                    # indefinitely, then resets after one entry so a continuing inequality cannot re-fire.
    return out
