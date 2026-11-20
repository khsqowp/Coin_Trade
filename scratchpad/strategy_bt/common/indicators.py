"""Small causal indicator library copied/adapted from bb_stoch_stc."""
import numpy as np
import pandas as pd

def sma(x, n):
    return pd.Series(x).rolling(int(n), min_periods=int(n)).mean().to_numpy()

def ema(x, n):
    x=np.asarray(x,float); out=np.full(len(x),np.nan); alpha=2/(int(n)+1); prev=np.nan
    for i,v in enumerate(x):
        if np.isfinite(v): prev=v if not np.isfinite(prev) else alpha*v+(1-alpha)*prev
        out[i]=prev
    return out

def bollinger(close, n=20, k=2):
    s=pd.Series(close); mid=s.rolling(n,min_periods=n).mean().to_numpy(); sd=s.rolling(n,min_periods=n).std(ddof=0).to_numpy()
    return mid,mid+k*sd,mid-k*sd

def atr(high, low, close, n=14):
    h,l,c=map(lambda z:np.asarray(z,float),(high,low,close)); pc=np.r_[np.nan,c[:-1]]
    tr=np.maximum.reduce([h-l,np.abs(h-pc),np.abs(l-pc)]); out=np.full(len(c),np.nan)
    if len(c)>=n:
        out[n-1]=np.nanmean(tr[:n])
        for i in range(n,len(c)): out[i]=(out[i-1]*(n-1)+tr[i])/n
    return out
