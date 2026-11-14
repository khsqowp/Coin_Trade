from __future__ import annotations
import argparse, json, time
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

ROOT=Path(__file__).resolve().parent
EXTRAS='ASML ARM MELI PDD CRWD PANW DASH ABNB TEAM ZS DDOG TTD MDB WDAY CDNS MRVL CSGP TTWO GFS ON CCEP AZN TRI LIN APP'.split()

def _lib():
    import sys
    sys.path.insert(0, '/home/noroot/research/stock_loop')
    from lib.data import us_universe, kr_universe
    return us_universe, kr_universe

def _daily_value(code):
    p=Path('/home/noroot/research/gulp_pattern/cache/kr')/f'{code}.parquet'
    try:
        d=pd.read_parquet(p); d.columns=[str(x).lower() for x in d.columns]
        return float((d.close*d.volume).tail(20).mean())
    except Exception: return float('nan')

def _download(tickers):
    for attempt in range(3):
        try:
            return yf.download(tickers, period='60d', interval='5m', group_by='ticker', progress=False, auto_adjust=False, threads=False)
        except Exception:
            if attempt==2: raise
            time.sleep(3*(attempt+1))

def _extract(df,ticker):
    if df is None or df.empty: return pd.DataFrame()
    if isinstance(df.columns,pd.MultiIndex):
        if ticker in df.columns.get_level_values(0): x=df[ticker].copy()
        elif ticker in df.columns.get_level_values(-1): x=df.xs(ticker,axis=1,level=-1).copy()
        else: return pd.DataFrame()
    else: x=df.copy()
    x.columns=[str(c).lower().replace(' ','') for c in x.columns]
    if not {'open','high','low','close','volume'}<=set(x.columns): return pd.DataFrame()
    x=x[['open','high','low','close','volume']].dropna(how='all')
    return x

def _fetch_set(tickers, market, force, v20=None):
    path=ROOT/'cache'/f'{market}_5m.parquet'
    if path.exists() and not force: return pd.read_parquet(path), []
    zone='America/New_York' if market=='us' else 'Asia/Seoul'; frames=[]; failed=[]
    for start in range(0,len(tickers),40):
        batch=tickers[start:start+40]
        try: raw=_download(batch)
        except Exception: raw=None
        for ticker in batch:
            x=_extract(raw,ticker)
            if x.empty: failed.append(ticker); continue
            idx=pd.DatetimeIndex(pd.to_datetime(x.index))
            if idx.tz is None: idx=idx.tz_localize(zone,ambiguous='NaT', nonexistent='NaT')
            else: idx=idx.tz_convert(zone)
            x.index=idx; x=x[~x.index.isna()]
            mins=x.index.hour*60+x.index.minute
            lo,hi=(9*60+30,16*60) if market=='us' else (9*60,15*60+30)
            x=x[(mins>=lo)&(mins<hi)]
            x=x.dropna(subset=['open','high','low','close'],how='all')
            x['symbol']=ticker; x['ts']=x.index
            frames.append(x.reset_index(drop=True)[['symbol','ts','open','high','low','close','volume']])
        if start+40<len(tickers): time.sleep(3)
    out=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=['symbol','ts','open','high','low','close','volume'])
    if len(out): out=out.sort_values(['ts','symbol']).reset_index(drop=True)
    path.parent.mkdir(parents=True,exist_ok=True); out.to_parquet(path,index=False)
    return out,failed

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--force',action='store_true'); a=ap.parse_args()
    us_fn,kr_fn=_lib()
    us=list(dict.fromkeys([s.replace('.','-') for s in us_fn()]+EXTRAS))
    u=kr_fn(); u['Code']=u.Code.astype(str).str.zfill(6)
    vals={r.Code:_daily_value(r.Code) for r in u.itertuples()}
    u['v20']=u.Code.map(vals); u=u.sort_values('v20',ascending=False,na_position='last').head(300)
    kr=[(r.Code+'.KS' if r.Market=='KOSPI' else r.Code+'.KQ') for r in u.itertuples()]
    usdf,uf=_fetch_set(us,'us',a.force); krdf,kf=_fetch_set(kr,'kr',a.force,vals)
    meta={'us':{'rows':len(usdf),'symbols':int(usdf.symbol.nunique()) if len(usdf) else 0,'first_ts':str(usdf.ts.min()) if len(usdf) else None,'last_ts':str(usdf.ts.max()) if len(usdf) else None,'failed_tickers':uf},'kr':{'rows':len(krdf),'symbols':int(krdf.symbol.nunique()) if len(krdf) else 0,'first_ts':str(krdf.ts.min()) if len(krdf) else None,'last_ts':str(krdf.ts.max()) if len(krdf) else None,'failed_tickers':kf,'value20_by_code':vals}}
    (ROOT/'cache'/'fetch_meta.json').write_text(json.dumps(meta,indent=2,allow_nan=False))
if __name__=='__main__': main()
