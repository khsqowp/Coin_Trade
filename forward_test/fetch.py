"""Public Binance spot klines only; no authentication or order endpoints."""
import time
from datetime import datetime, timezone
import pandas as pd
from .config import INTERVAL_MS

URL='https://api.binance.com/api/v3/klines'
def fetch(symbol,start_ms,session=None,now_ms=None,sleep=.12):
    if session is None:
        import requests
        session=requests
    now_ms=now_ms or int(time.time()*1000); cursor=int(start_ms); rows=[]
    while cursor+INTERVAL_MS<=now_ms:
        response=None
        for attempt in range(7):
            try:
                response=session.get(URL,params={'symbol':symbol,'interval':'4h','startTime':cursor,'endTime':now_ms-1,'limit':1000},timeout=30)
                if response.status_code==429 or response.status_code>=500: raise RuntimeError(f'HTTP {response.status_code}')
                response.raise_for_status(); data=response.json(); break
            except Exception:
                if attempt==6: raise
                retry_after=(getattr(response,'headers',{}) or {}).get('Retry-After') if response is not None else None
                try: pause=max(1.5**attempt,float(retry_after)) if retry_after is not None else 1.5**attempt
                except (TypeError,ValueError): pause=1.5**attempt
                time.sleep(min(60,pause))
        if not data: break
        rows.extend(data); nxt=int(data[-1][0])+INTERVAL_MS
        if nxt<=cursor: raise RuntimeError('Binance pagination did not advance')
        cursor=nxt; time.sleep(sleep)
    if not rows:return pd.DataFrame(columns=['open','high','low','close','volume'])
    f=pd.DataFrame(rows,columns=['ts','open','high','low','close','volume','close_ts','q','n','tb','tq','x'])
    if f['ts'].duplicated().any(): raise ValueError(f'duplicate Binance candles for {symbol}')
    f=f.set_index('ts')[['open','high','low','close','volume']].astype(float)
    f.index=pd.to_datetime(f.index,unit='ms',utc=True); f.index.name='open_time'
    f=f[[int(x.timestamp()*1000)+INTERVAL_MS<=now_ms for x in f.index]]
    return f

def gaps(frame):
    if frame.index.has_duplicates: raise ValueError('duplicate candle timestamps')
    ns=frame.index.as_unit('ns').asi8
    return [(int(a//1_000_000+INTERVAL_MS),int(b//1_000_000)) for a,b in zip(ns[:-1],ns[1:]) if b-a!=INTERVAL_MS*1_000_000]
