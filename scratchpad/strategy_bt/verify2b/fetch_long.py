"""Download Binance spot monthly kline zips (data.binance.vision) into data_long/<SYM>_<tf>.parquet."""
from __future__ import annotations
import io, sys, zipfile
from datetime import date
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / 'data_long'
COLS = ['open_time','open','high','low','close','volume','close_time','qv','trades','tb','tq','ig']

def parse_zip_bytes(b: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), header=None, names=COLS)
    t = df['open_time'].astype('int64')
    unit = 'us' if t.iloc[0] > 10**14 else 'ms'   # spot files switched to microseconds in 2025
    df.index = pd.to_datetime(t, unit=unit, utc=True)
    df.index.name = 'open_time'
    return df[['open','high','low','close','volume']].astype(float)

def fetch(sym, tf, start_year=2017):
    today = date.today(); parts = []
    for y in range(start_year, today.year + 1):
        for m in range(1, 13):
            if (y, m) >= (today.year, today.month): break
            url = f'https://data.binance.vision/data/spot/monthly/klines/{sym}/{tf}/{sym}-{tf}-{y}-{m:02d}.zip'
            try:
                with urlopen(Request(url, headers={'User-Agent': 'bt/1'}), timeout=60) as r: parts.append(parse_zip_bytes(r.read()))
            except HTTPError as e:
                if e.code != 404: raise
    if not parts: return None
    df = pd.concat(parts); return df[~df.index.duplicated()].sort_index()

def main(jobs):
    OUT.mkdir(exist_ok=True)
    for sym, tf in jobs:
        p = OUT / f'{sym}_{tf}.parquet'
        if p.exists(): continue
        df = fetch(sym, tf)
        if df is None: print('NONE', sym, tf, flush=True); continue
        df.to_parquet(p); print(sym, tf, len(df), df.index[0], df.index[-1], flush=True)

if __name__ == '__main__':
    four = ['BTCUSDT','ETHUSDT','BNBUSDT','XRPUSDT']
    jobs = [(s,'1d') for s in four] + [(s,'1h') for s in four] + [(s,'15m') for s in ('BTCUSDT','ETHUSDT')]
    main(jobs)
