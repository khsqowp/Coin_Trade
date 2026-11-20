"""Binance public kline downloader and deterministic synthetic OHLCV generator.

Network downloader is deliberately not run in this sandbox. Binance timestamps are UTC;
all ranges are half-open [start, end), and the still-open final candle is discarded.
"""
from __future__ import annotations
import argparse, csv, json, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parent
SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','TRXUSDT','DOGEUSDT']
TFS=['1h','4h','15m','8h','12h','1d']
MS={'15m':900_000,'1h':3_600_000,'4h':14_400_000,'8h':28_800_000,'12h':43_200_000,'1d':86_400_000}
SPOT_URL='https://api.binance.com/api/v3/klines'
FUTURES_URL='https://fapi.binance.com/fapi/v1/klines'
URL=SPOT_URL
def synthetic(symbol='SYNTH',tf='1h',n=12000,seed=1729):
    """Seeded geometric random walk with alternating drift/volatility regimes."""
    rng=np.random.default_rng(seed+sum(map(ord,symbol))+MS[tf]); regime=np.arange(n)//max(80,n//12)%4
    drift=np.choose(regime,[-.00015,.0002,0,.00005]); vol=np.choose(regime,[.004,.006,.012,.003])
    close=100*np.exp(np.cumsum(drift+rng.normal(0,vol,n))); op=np.r_[close[0],close[:-1]]
    spread=np.abs(rng.normal(.0015,.001,n)); hi=np.maximum(op,close)*(1+spread); lo=np.minimum(op,close)*(1-spread)
    return pd.DataFrame({'open':op,'high':hi,'low':lo,'close':close,'volume':rng.lognormal(5,.8,n)},index=pd.date_range('2022-01-01',periods=n,freq=tf,tz='UTC')).rename_axis('open_time')
def _ms(dt): return int(pd.Timestamp(dt,tz='UTC').timestamp()*1000)
def _fetch_json(url,timeout=30):
    req=Request(url,headers={'User-Agent':'reproducible-backtest/1.0'})
    with urlopen(req,timeout=timeout) as res: return json.loads(res.read())

def download(symbol,tf,start='2022-01-01',end=None,sleep=.15,market='spot'):
    """Fetch Binance klines with pagination, polite pacing, retries and exponential backoff."""
    if market not in ('spot','futures'): raise ValueError("market must be 'spot' or 'futures'")
    end=end or datetime.now(timezone.utc).strftime('%Y-%m-%d'); a=0 if start=='earliest' else _ms(start); b=_ms(end); step=MS[tf]; rows=[]
    url=FUTURES_URL if market=='futures' else SPOT_URL
    while a < b:
        q=f'{url}?symbol={symbol}&interval={tf}&startTime={a}&endTime={b-1}&limit=1000'; last=None
        for attempt in range(7):
            try:
                payload=_fetch_json(q)
                if isinstance(payload,dict): raise RuntimeError(payload)
                last=None; break
            except (URLError,HTTPError,TimeoutError,ValueError,RuntimeError) as e:
                last=e; time.sleep(min(60,1.5**attempt))
        if last: raise RuntimeError(f'Binance request failed: {last}')
        if not payload: break
        rows.extend(payload); a=int(payload[-1][0])+step; time.sleep(sleep)
    df=pd.DataFrame(rows,columns=['open_time','open','high','low','close','volume','close_time','quote_volume','trades','taker_base','taker_quote','ignore'])
    if df.empty: return pd.DataFrame(columns=['open','high','low','close','volume'])
    df=df.drop_duplicates('open_time').set_index('open_time'); df.index=pd.to_datetime(df.index,unit='ms',utc=True)
    df=df[['open','high','low','close','volume']].astype(float); now=int(datetime.now(timezone.utc).timestamp()*1000)
    df=df[df.index.asi8//1_000_000 + step <= now]
    return df

def check_data(df,tf):
    step=pd.Timedelta(milliseconds=MS[tf]); idx=df.index; gaps=[]
    if idx.has_duplicates: raise AssertionError('duplicate timestamps')
    if len(idx)>1:
        ns=idx.to_numpy(dtype='datetime64[ns]').astype(np.int64);delta=step.value
        for i in np.flatnonzero(np.diff(ns)>delta): gaps.append((idx[i],idx[i+1],max(0,int((ns[i+1]-ns[i])//delta-1))))
    return gaps

def main():
    p=argparse.ArgumentParser();p.add_argument('--symbols',nargs='+',default=SYMBOLS);p.add_argument('--timeframes',nargs='+',default=['1h','4h']);p.add_argument('--start',default='2022-01-01');p.add_argument('--market',choices=['spot','futures'],default='spot');p.add_argument('--synthetic',action='store_true');p.add_argument('--report-only',action='store_true');p.add_argument('--out',type=Path,default=BASE/'results'/'data_report.csv');p.add_argument('--first-dates-out',type=Path);a=p.parse_args()
    out=BASE/'data'
    if not a.report_only: out.mkdir(exist_ok=True)
    reports=[];first_dates={s:[] for s in a.symbols}
    for s in a.symbols:
      for tf in a.timeframes:
        f=out/f'{s}_{tf}.parquet'
        if a.report_only:
            if not f.exists():raise FileNotFoundError(f'cached parquet missing: {f}')
            df=pd.read_parquet(f)
        else:
            df=synthetic(s,tf) if a.synthetic else download(s,tf,a.start,market=a.market)
            df.to_parquet(f)
        if len(df):first_dates[s].append(df.index.min())
        gaps=check_data(df,tf)
        reports.append({'symbol':s,'timeframe':tf,'bars':len(df),'gaps':len(gaps),'gap_details':json.dumps([(str(x),str(y),n) for x,y,n in gaps])})
    a.out.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(reports).to_csv(a.out,index=False)
    if a.first_dates_out:
        a.first_dates_out.parent.mkdir(parents=True,exist_ok=True)
        pd.DataFrame([{'symbol':s,'first_date':min(values).isoformat() if values else ''} for s,values in first_dates.items()]).to_csv(a.first_dates_out,index=False)
if __name__=='__main__': main()
