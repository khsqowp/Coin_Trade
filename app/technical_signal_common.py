"""Causal daily signals. Zones/pivots become usable only on confirmation dates."""
import numpy as np
import pandas as pd
try:
    import pandas_ta as ta
    from app.more_indicators import add_ema_cross_indicators
except ModuleNotFoundError as exc:
    if exc.name != "pandas_ta":
        raise
    from app import technical_indicator_fallback as ta
    from app.technical_indicator_fallback import add_ema_cross_indicators

NAMES = ['elliott_wave','rsi','ema_cross','heikin_ashi','fibonacci','vwap','fvg','frvp','order_block','liquidity_sweep']
LABELS = ['엘리엇 파동','RSI','EMA 크로스','하이킨 아시','피보나치 되돌림','VWAP','FVG','FRVP','오더블록','리퀴디티 스윕']


def confirmed_pivots(close, reversal=.05):
    """Close-based 5% ZigZag: emit extreme on reversal, never backdate signal."""
    pivots = []
    direction = 0
    extreme = float(close[0])
    for i, value in enumerate(close):
        value = float(value)
        pivot = None
        if direction >= 0:
            if value > extreme:
                extreme = value
            elif value <= extreme * (1-reversal):
                pivot = ('H', extreme)
                direction, extreme = -1, value
        if direction <= 0 and pivot is None:
            if value < extreme:
                extreme = value
            elif value >= extreme * (1+reversal):
                pivot = ('L', extreme)
                direction, extreme = 1, value
        if pivot:
            pivots.append(pivot)
        yield i, pivot, pivots[-5:]


def find(frame, name):
    df = frame.copy()
    c, o, h, l, v = (df[k] for k in ['Close','Open','High','Low','Volume'])
    atr = ta.atr(h,l,c,length=14)
    df['ATR14'] = atr
    df['STOP_LEVEL'] = l.shift(1).rolling(20).min()
    signal = pd.Series(False,index=df.index)
    score = pd.Series(0.,index=df.index)
    if name == 'rsi':
        r = ta.rsi(c,length=14)
        signal = (r.shift(1)<30)&(r>=30)
        score = 100-r
    elif name == 'ema_cross':
        df = add_ema_cross_indicators(df)
        signal = (df.EMA9.shift(1)<=df.EMA21.shift(1))&(df.EMA9>df.EMA21)&(c>df.SMA200)
        score = (df.EMA9/df.EMA21-1)*100
    elif name == 'heikin_ashi':
        hc = (o+h+l+c)/4
        ho = np.empty(len(df)); ho[0] = (o.iloc[0]+c.iloc[0])/2
        for i in range(1,len(df)):
            ho[i] = (ho[i-1]+hc.iloc[i-1])/2
        bullish = hc > ho
        signal = bullish & ~bullish.shift(1,fill_value=True)
        score = (hc-pd.Series(ho,index=df.index))/atr
    elif name == 'vwap':
        vw = (((h+l+c)/3)*v).rolling(20).sum()/v.rolling(20).sum()
        signal = (c.shift(1)<vw.shift(1))&(c>vw)
        score = (vw.shift(1)-c.shift(1))/atr
    elif name == 'liquidity_sweep':
        level = l.shift(1).rolling(20).min()
        swept = (l<level)&(l>=level*.95)  # slight penetration, at most 5%
        same = swept&(c>level)
        next_day = swept.shift(1,fill_value=False)&(c.shift(1)<=level.shift(1))&(c>level.shift(1))
        signal = same|next_day
        score = ((level-l)/atr).where(~next_day, (level.shift(1)-l.shift(1))/atr)
        df['STOP_LEVEL'] = np.minimum(l,l.shift(1))
    elif name in ('elliott_wave','fibonacci'):
        impulse = None; tapped = False
        for i, pivot, points in confirmed_pivots(c.to_numpy()):
            if name == 'elliott_wave' and pivot and len(points)==5:
                types = ''.join(p[0] for p in points)
                p0,p1,p2,p3,p4 = [p[1] for p in points]
                if types=='LHLHL' and p2>p0 and p3>p1 and p4>p1 and p3-p2>p1-p0:
                    retr = (p3-p4)/(p3-p2)
                    if .236<=retr<=.618:
                        signal.iloc[i]=True; score.iloc[i]=(p3-p2)/(p1-p0)
                        df.iloc[i,df.columns.get_loc('STOP_LEVEL')]=p4
            elif name == 'fibonacci':
                if pivot and len(points)>=2 and points[-2][0]=='L' and pivot[0]=='H':
                    impulse = (points[-2][1],pivot[1]); tapped=False
                if impulse:
                    lo,hi=impulse; upper=hi-.5*(hi-lo); lower=hi-.618*(hi-lo)
                    if c.iloc[i]<hi-.786*(hi-lo):
                        impulse=None; continue
                    if lower<=c.iloc[i]<=upper:
                        tapped=True
                    elif tapped and c.iloc[i]>upper:
                        signal.iloc[i]=True; score.iloc[i]=(hi-lo)/atr.iloc[i]
                        df.iloc[i,df.columns.get_loc('STOP_LEVEL')]=hi-.786*(hi-lo)
                        impulse=None
    elif name in ('fvg','order_block'):
        zones=[]
        for i in range(len(df)):
            remaining=[]
            for low,high,born in zones:
                if i-born>60 or c.iloc[i]<low:
                    continue
                if l.iloc[i]<=high and h.iloc[i]>=low and (name=='fvg' or c.iloc[i]>high):
                    signal.iloc[i]=True; score.iloc[i]=max(score.iloc[i],(high-low)/atr.iloc[i])
                    df.iloc[i,df.columns.get_loc('STOP_LEVEL')]=low
                else:
                    remaining.append((low,high,born))
            zones=remaining
            if name=='fvg' and i>=2 and l.iloc[i]>h.iloc[i-2]:
                zones.append((h.iloc[i-2],l.iloc[i],i))
            if name=='order_block' and i>=14 and c.iloc[i]-o.iloc[i]>1.5*atr.iloc[i-1] and c.iloc[i]>h.iloc[i-1]:
                for j in range(i-1,max(-1,i-6),-1):
                    if c.iloc[j]<o.iloc[j]:
                        zones.append((l.iloc[j],h.iloc[j],i)); break
    elif name=='frvp':
        # Daily OHLCV cannot recover true volume-at-price: typical-price histogram proxy.
        typical=((h+l+c)/3).to_numpy(); volumes=v.to_numpy()
        for i in range(60,len(df)):
            hist,edges=np.histogram(typical[i-60:i],bins=24,weights=volumes[i-60:i])
            centers=(edges[:-1]+edges[1:])/2; poc=int(hist.argmax())
            below=np.flatnonzero((np.arange(24)<poc)&(hist>0)&(hist<.5*hist[poc]))
            if not len(below): continue
            level=centers[poc]; lvn=centers[below[-1]]
            if lvn<=c.iloc[i-1]<level and c.iloc[i]>level:
                signal.iloc[i]=True; score.iloc[i]=hist[poc]/max(hist[below[-1]],1)
    else:
        raise ValueError(name)
    df['SIGNAL']=signal.fillna(False).astype(bool)
    df['VOL_RATIO']=score.replace([np.inf,-np.inf],0).fillna(0)
    return df
