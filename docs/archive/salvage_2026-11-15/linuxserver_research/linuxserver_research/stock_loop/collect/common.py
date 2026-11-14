from __future__ import annotations
import logging, os, shutil, zlib
from datetime import date
from pathlib import Path
import pandas as pd

class Abort(RuntimeError): pass

SCHEMA = ['symbol','ts_utc','open','high','low','close','volume','adjusted','src']
TZ = {'us':'America/New_York','kr':'Asia/Seoul'}

def check_resources() -> None:
    import os
    if os.getloadavg()[0] > 4:
        raise Abort('1-minute load average exceeds 4')
    available = None
    with open('/proc/meminfo', encoding='ascii') as f:
        for line in f:
            if line.startswith('MemAvailable:'):
                available = int(line.split()[1]); break
    if available is None or available < 2 * 1024 * 1024:
        raise Abort('MemAvailable is below 2 GiB')

def check_disk(data_dir: str | Path) -> None:
    path = Path(data_dir)
    total = sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.exists() else 0
    probe = path
    while not probe.exists() and probe != probe.parent: probe = probe.parent
    usage = shutil.disk_usage(probe)
    if total >= 20_000_000_000 or usage.free / usage.total < .30:
        raise Abort(f'disk limit reached: bytes={total}, free_fraction={usage.free / usage.total:.3f}')

def _partition(root: Path, market: str, interval: str, day: date, symbol: str) -> Path:
    batch = zlib.crc32(symbol.encode('utf-8')) % 8
    return root / 'data/minute' / market / interval / f'date={day.isoformat()}' / f'batch={batch:02d}.parquet'

def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    try:
        frame[SCHEMA].sort_values(['symbol','ts_utc']).to_parquet(tmp, index=False, compression='zstd', compression_level=6)
        os.replace(tmp, path)
    finally:
        if tmp.exists(): tmp.unlink()

def normalize_bars(raw_df: pd.DataFrame, symbol_map: str | dict[str,str], market: str, interval: str) -> pd.DataFrame:
    if market not in TZ or interval not in {'1m','5m'}: raise ValueError('invalid market or interval')
    if raw_df.empty: return pd.DataFrame(columns=SCHEMA)
    frame = raw_df.copy()
    idx = pd.DatetimeIndex(frame.index)
    idx = idx.tz_localize(TZ[market]) if idx.tz is None else idx.tz_convert(TZ[market])
    frame.index = idx.tz_convert('UTC')
    frame.columns = [str(c).lower() for c in frame.columns]
    # With auto_adjust=False, Close is the raw price we persist. Adj Close is
    # a separate series and must not become a second column named "close".
    frame = frame.drop(columns=['adj close'], errors='ignore')
    required = ['open','high','low','close','volume']
    if not set(required).issubset(frame.columns): raise ValueError('missing OHLCV columns')
    symbol = symbol_map if isinstance(symbol_map, str) else symbol_map.get('symbol','')
    frame = frame.dropna(subset=['close'])
    frame = frame.loc[~frame[['open','high','low','close']].isna().all(axis=1)]
    frame = frame.loc[pd.to_numeric(frame.volume, errors='coerce') >= 0]
    out = frame[required].copy().reset_index(names='ts_utc')
    out['symbol'] = symbol
    out['ts_utc'] = pd.to_datetime(out.ts_utc, utc=True)
    for col in required[:4]: out[col] = pd.to_numeric(out[col], errors='coerce').astype('float64')
    out['volume'] = pd.to_numeric(out.volume).astype('int64')
    out['adjusted'] = False; out['src'] = 'yf'
    return out[SCHEMA].drop_duplicates(['symbol','ts_utc'], keep='last').sort_values(['symbol','ts_utc']).reset_index(drop=True)

def merge_write(df: pd.DataFrame, market: str, interval: str, root: str | Path) -> dict[str,int]:
    if market not in TZ or interval not in {'1m','5m'}: raise ValueError('invalid market or interval')
    if df.empty: return {}
    base = Path(root)
    rows = df[SCHEMA].copy()
    rows['ts_utc'] = pd.to_datetime(rows.ts_utc, utc=True)
    rows['_date'] = rows.ts_utc.dt.tz_convert(TZ[market]).dt.strftime('%Y-%m-%d')
    counts: dict[str,int] = {}
    for day, day_rows in rows.groupby('_date'):
        day_rows = day_rows.drop(columns='_date')
        paths = {_partition(base, market, interval, pd.Timestamp(day).date(), str(s)) for s in day_rows.symbol.unique()}
        for path in sorted(paths):
            check_disk(base / 'data/minute')
            new = day_rows[day_rows.symbol.map(lambda s: _partition(base,market,interval,pd.Timestamp(day).date(),str(s)) == path)]
            old = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=SCHEMA)
            combined = (new[SCHEMA].copy() if old.empty else
                        pd.concat([old[SCHEMA],new[SCHEMA]],ignore_index=True))
            combined['_priority'] = combined.src.map({'tick':0,'yf':1}).fillna(0)
            combined = combined.sort_values(['symbol','ts_utc','_priority'],kind='stable').drop_duplicates(['symbol','ts_utc'],keep='last').drop(columns='_priority').reset_index(drop=True)
            if not path.exists() or not old[SCHEMA].sort_values(['symbol','ts_utc']).reset_index(drop=True).equals(combined):
                _write_parquet(combined,path)
            counts[day] = counts.get(day,0) + len(combined)
    return counts
