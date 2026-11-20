"""Causal indicator implementations; formulas are stated in each function docstring."""
import numpy as np
import pandas as pd

def sma(x,n): return pd.Series(x).rolling(n,min_periods=n).mean().to_numpy()
def ema(x,n):
    """EMA uses alpha=2/(n+1), seeded by first finite sample; causal recursive updates."""
    x=np.asarray(x,float); out=np.full(len(x),np.nan); a=2/(n+1); prev=np.nan
    for i,v in enumerate(x):
        if np.isfinite(v): prev=v if not np.isfinite(prev) else a*v+(1-a)*prev
        out[i]=prev
    return out

def bollinger(close,n=20,k=2):
    """SMA(n) ± k times population standard deviation (ddof=0), using trailing bars."""
    s=pd.Series(close); mid=s.rolling(n,min_periods=n).mean().to_numpy(); sd=s.rolling(n,min_periods=n).std(ddof=0).to_numpy();return mid,mid+k*sd,mid-k*sd

def stochastic(high,low,close,k_len=14,k_smooth=3,d_len=3):
    """Raw %K=100*(close-rolling LL)/(rolling HH-LL); smooth %K and %D with trailing SMAs; zero range -> NaN."""
    h=pd.Series(high);l=pd.Series(low); c=np.asarray(close,float); hh=h.rolling(k_len,min_periods=k_len).max().to_numpy();ll=l.rolling(k_len,min_periods=k_len).min().to_numpy(); den=hh-ll
    raw=np.divide(100*(c-ll),den,out=np.full(len(c),np.nan),where=den!=0); kk=sma(raw,k_smooth);return kk,sma(kk,d_len)

def stc(close,fast=23,slow=50,cycle=10):
    """MACD=EMA(fast)-EMA(slow); stochastic over cycle, recursive 0.5 smoothing, repeat stochastic and smooth. Zero ranges -> NaN; no future data."""
    m=ema(close,fast)-ema(close,slow)
    def smooth_stoch(x):
        s=pd.Series(x); lo=s.rolling(cycle,min_periods=cycle).min().to_numpy();hi=s.rolling(cycle,min_periods=cycle).max().to_numpy(); z=np.divide(100*(x-lo),hi-lo,out=np.full(len(x),np.nan),where=hi!=lo)
        out=np.full(len(x),np.nan); prev=np.nan
        for i,v in enumerate(z):
            if np.isfinite(v): prev=v if not np.isfinite(prev) else prev+.5*(v-prev)
            out[i]=prev
        return out
    return smooth_stoch(smooth_stoch(m))

def atr(high,low,close,n=14):
    """Wilder ATR: TR=max(H-L, abs(H-prevC), abs(L-prevC)); Wilder alpha=1/n, seeded by first n TR mean."""
    h,l,c=map(lambda x:np.asarray(x,float),(high,low,close)); pc=np.r_[np.nan,c[:-1]]; tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)]);out=np.full(len(c),np.nan)
    if len(c)<n:return out
    out[n-1]=np.nanmean(tr[:n]);
    for i in range(n,len(c)):out[i]=(out[i-1]*(n-1)+tr[i])/n
    return out
