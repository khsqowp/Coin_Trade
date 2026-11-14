from __future__ import annotations
import io, logging, re
from datetime import datetime
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
NDX_EXTRA_APPROX = 'ASML ARM PDD MELI TEAM ZS CCEP MDB TTD'.split()
ALIAS = {'BRKB':'BRK-B','BFB':'BF-B'}

def _cache(name: str) -> Path:
    primary=Path(__import__('os').environ.get('STOCK_LOOP_ROOT',ROOT))
    for p in (primary/'lib/cache'/name, Path('/home/noroot/research/gulp_pattern/cache')/name):
        if p.exists(): return p
    raise FileNotFoundError(name)

def _save(frame: pd.DataFrame, market: str, root: Path) -> None:
    target=root/'collect/universe'; target.mkdir(parents=True,exist_ok=True)
    frame.to_csv(target/f"{market}_{datetime.now().strftime('%Y%m%d')}.csv",index=False)

def us_universe() -> pd.DataFrame:
    root=Path(__import__('os').environ.get('STOCK_LOOP_ROOT',ROOT))
    sp=[ALIAS.get(s,s) for s in pd.read_csv(_cache('us_universe.csv'))['symbol'].dropna().astype(str).str.replace('.','-',regex=False).tolist()]
    ndx=[]
    ndx_approx=[]
    try:
        import requests
        response=requests.get('https://en.wikipedia.org/wiki/Nasdaq-100',headers={'User-Agent':'stock_loop-research/1.0 (personal research; contact: local)'},timeout=20)
        response.raise_for_status()
        tables=pd.read_html(io.StringIO(response.text))
        table=next((t for t in tables if len(t)>=80 and any(str(c).strip().lower() in {'ticker','symbol'} for c in t.columns)),None)
        if table is not None:
            col=next(c for c in table.columns if str(c).strip().lower() in {'ticker','symbol'})
            ndx=table[col].dropna().astype(str).str.replace('.','-',regex=False).tolist()
        else:
            logging.info('Nasdaq-100 fetch found no components table')
    except Exception as exc:
        logging.info('Nasdaq-100 fetch failed: %s',exc)
        files=sorted((root/'collect/universe').glob('us_*.csv'))
        if files:
            cached=pd.read_csv(files[-1])
            ndx=cached.loc[cached.group.eq('ndx'),'symbol'].astype(str).tolist()
            ndx_approx=cached.loc[cached.group.eq('ndx_approx'),'symbol'].astype(str).tolist()
    ndx_approx=list(dict.fromkeys(ndx_approx+[s for s in NDX_EXTRA_APPROX if s not in sp]))
    etfs='SPY QQQ IWM DIA XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY SMH XBI GLD TLT'.split()
    rows=[(s,'sp500') for s in dict.fromkeys(sp)]+[(s,'ndx') for s in dict.fromkeys(ndx) if s not in sp]+[(s,'ndx_approx') for s in ndx_approx]+[(s,'etf') for s in etfs]
    frame=pd.DataFrame(rows,columns=['symbol','group']).drop_duplicates('symbol')
    _save(frame,'us',root); return frame

def _is_common(frame: pd.DataFrame) -> pd.DataFrame:
    excluded=r'스팩|기업인수목적|ETN|ETF|KODEX|TIGER|KBSTAR|ARIRANG|HANARO|KOSEF|SOL |ACE |RISE |PLUS |우$|우B$|우\(|리츠|인프라'
    return frame[frame.Market.isin(['KOSPI','KOSDAQ']) & frame.Code.astype(str).str.endswith('0') & ~frame.Name.astype(str).str.contains(excluded,regex=True)]

def _value20(code: str, base: Path, fallback: Path) -> tuple[float,pd.Timestamp] | None:
    path=base/f'{code}.parquet'
    if not path.exists(): path=fallback/f'{code}.parquet'
    if not path.exists(): return None
    daily=pd.read_parquet(path)
    if daily.empty or not {'close','volume'}.issubset(daily.columns): return None
    dates=pd.DatetimeIndex(daily.index)
    last=dates.max()
    if (pd.Timestamp.now().normalize()-last.tz_localize(None).normalize()).days>10: return None
    value=(daily.close*daily.volume).tail(20).mean()
    return (float(value),pd.Timestamp(last)) if pd.notna(value) else None

def kr_universe(top_kospi: int=200, top_kosdaq: int=150) -> pd.DataFrame:
    root=Path(__import__('os').environ.get('STOCK_LOOP_ROOT',ROOT))
    listing=pd.read_csv(_cache('kr_universe.csv'),dtype={'Code':str})
    listing['Code']=listing.Code.str.zfill(6); listing=_is_common(listing)
    base=root/'lib/cache/kr'; fallback=Path('/home/noroot/research/gulp_pattern/cache/kr')
    records=[]
    for row in listing.itertuples(index=False):
        result=_value20(row.Code,base,fallback)
        if result is not None: records.append({'code':row.Code,'yahoo':row.Code+('.KS' if row.Market=='KOSPI' else '.KQ'),'name':row.Name,'market':row.Market,'value20':result[0]})
    frame=pd.DataFrame(records,columns=['code','yahoo','name','market','value20'])
    limits={'KOSPI':top_kospi,'KOSDAQ':top_kosdaq}
    frame=pd.concat([g.nlargest(limits[m],'value20') for m,g in frame.groupby('market') if m in limits],ignore_index=True) if not frame.empty else frame
    _save(frame,'kr',root); return frame
