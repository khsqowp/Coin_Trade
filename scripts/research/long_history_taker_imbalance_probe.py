#!/usr/bin/env python3
"""Fixed 30m breakout plus taker-buy imbalance probe; no parameter tuning."""
import sqlite3
import numpy as np
import pandas as pd

DB='chart_predictor/data/vision_dev.sqlite'
CUTOFF_MS=int(pd.Timestamp('2026-10-09T00:00:00Z').timestamp()*1000)
SYMBOLS=('BNBUSDT','BTCUSDT','DOGEUSDT','ETHUSDT')
BAR_MS=30*60_000
HORIZONS=(10,20)
LEVERAGES=(10,20)
COSTS={'base':.001,'stress':.003}


def main():
    db=sqlite3.connect(f'file:{DB}?mode=ro',uri=True); rows=[]
    for symbol in SYMBOLS:
        raw=pd.read_sql_query(
            'SELECT open_ms,open AS o,high AS h,low AS l,close AS c,volume AS v,'
            'quote_volume,taker_buy_quote FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms',
            db,params=(symbol,CUTOFF_MS))
        raw['dt']=pd.to_datetime(raw.open_ms,unit='ms',utc=True); raw=raw.set_index('dt')
        f=raw.resample('30min',origin='epoch',label='left',closed='left').agg({
            'o':'first','h':'max','l':'min','c':'last','v':'sum','open_ms':'first',
            'quote_volume':'sum','taker_buy_quote':'sum'}).dropna()
        f=f[f.open_ms+BAR_MS<=CUTOFF_MS].reset_index(drop=True)
        o,h,l,c,v=(f[k].to_numpy(float) for k in ('o','h','l','c','v'))
        qv=f.quote_volume.to_numpy(float); tb=f.taker_buy_quote.to_numpy(float)
        imbalance=np.divide(2*tb,qv,out=np.full(len(f),np.nan),where=qv>0)-1
        p_hi=pd.Series(h).rolling(20,min_periods=20).max().shift(1).to_numpy()
        p_lo=pd.Series(l).rolling(20,min_periods=20).min().shift(1).to_numpy()
        vmed=pd.Series(v).rolling(20,min_periods=20).median().shift(1).to_numpy()
        pc=np.r_[np.nan,c[:-1]]
        tr=np.maximum(h-l,np.maximum(np.abs(h-pc),np.abs(l-pc)))
        atr=pd.Series(tr).rolling(14,min_periods=14).mean().to_numpy()
        masks={
            'long':(c>p_hi)&(imbalance>=.30)&(v>=1.5*vmed),
            'short':(c<p_lo)&(imbalance<=-.30)&(v>=1.5*vmed),
        }
        times=f.open_ms.to_numpy(np.int64)
        for side_name,side,mask in (('long',1,masks['long']),('short',-1,masks['short'])):
            signal_ix=np.flatnonzero(mask)
            for horizon in HORIZONS:
                events=[i for i in signal_ix if i+1+horizon<=len(f)]
                for leverage in LEVERAGES:
                    valid=[]; liq=0
                    for i in events:
                        entry_i=i+1; entry=o[entry_i]; risk=1.5*atr[i]
                        if not np.isfinite(risk) or risk<=0:continue
                        if risk/entry>=1/leverage-.005:liq+=1;continue
                        valid.append((i,entry_i,entry,risk))
                    for cost_name,cost in COSTS.items():
                        rets=[]; target_first=direction_correct=0
                        for i,entry_i,entry,risk in valid:
                            stop=entry-side*risk; target=entry+side*2*risk
                            exitp=c[entry_i+horizon-1]; reason='timeout'
                            for j in range(entry_i,entry_i+horizon):
                                hs=l[j]<=stop if side>0 else h[j]>=stop
                                ht=h[j]>=target if side>0 else l[j]<=target
                                if hs or ht:
                                    exitp=stop if hs else target; reason='stop' if hs else 'target'; break
                            rets.append(side*(exitp/entry-1)-cost)
                            target_first+=reason=='target'
                            direction_correct+=side*(c[entry_i+horizon-1]/entry-1)>0
                        if rets:
                            n=len(rets)
                            rows.append((symbol,side_name,horizon,leverage,cost_name,n,len(events),liq,
                                         target_first/n,direction_correct/n,float(np.mean(np.asarray(rets)>0)),float(np.mean(rets)*100)))
    db.close()
    print('symbol,side,horizon_bars,leverage,cost,n,eligible_signals,liq_rejected,target_first,direction_correct,net_positive,mean_net_pct')
    for r in rows:print(','.join(map(str,r)))
    for horizon in HORIZONS:
        for leverage in LEVERAGES:
            for cost_name in COSTS:
                for side in ('long','short'):
                    sub=[r for r in rows if r[1]==side and r[2]==horizon and r[3]==leverage and r[4]==cost_name]
                    n=sum(r[5] for r in sub)
                    if n:print('POOLED',side,horizon,leverage,cost_name,'n',n,
                               'target_first',sum(r[5]*r[8] for r in sub)/n,
                               'direction_correct',sum(r[5]*r[9] for r in sub)/n,
                               'net_positive',sum(r[5]*r[10] for r in sub)/n,
                               'weighted_mean_net_pct',sum(r[5]*r[11] for r in sub)/n)


if __name__=='__main__':main()
