"""Offline pandas-ta-compatible non-TA-Lib definitions, not a pandas_ta replacement."""
import pandas as pd


def rma(series, length=14):
    return series.ewm(alpha=1/length,min_periods=length).mean()


def rsi(close, length=14):
    diff=close.diff(); positive=diff.clip(lower=0); negative=diff.clip(upper=0)
    up=rma(positive,length); down=rma(negative,length).abs()
    return 100*up/(up+down)


def atr(high, low, close, length=14):
    tr=pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    tr.iloc[0]=float('nan')
    return rma(tr,length)


def ema(close,length):
    seeded=close.copy(); seeded.iloc[:length-1]=float('nan')
    seeded.iloc[length-1]=close.iloc[:length].mean()
    return seeded.ewm(span=length,adjust=False).mean()


def add_ema_cross_indicators(frame):
    out=frame.copy()
    out['EMA9']=ema(out.Close,9); out['EMA21']=ema(out.Close,21)
    out['SMA200']=out.Close.rolling(200).mean()
    return out
