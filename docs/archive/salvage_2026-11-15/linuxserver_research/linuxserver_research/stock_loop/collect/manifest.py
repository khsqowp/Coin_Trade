from __future__ import annotations
import json
import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import pandas as pd
from .common import SCHEMA,TZ

def build_manifest(market: str, interval: str, day: str | date, root: str | Path) -> dict:
    date_s=str(day); base=Path(root)/'data/minute'/market/interval/f'date={date_s}'
    frames=[pd.read_parquet(p) for p in sorted(base.glob('batch=*.parquet'))]
    df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=SCHEMA)
    expected={('us','1m'):390,('us','5m'):78,('kr','1m'):360,('kr','5m'):72}[(market,interval)]
    counts=df.groupby('symbol').size().sort_values() if not df.empty else pd.Series(dtype='int64')
    median=float(counts.median()) if len(counts) else 0
    short=median < .7*expected
    gaps=[]
    if not short:
        delta=pd.Timedelta(minutes=1 if interval=='1m' else 5)
        for symbol, group in df.groupby('symbol'):
            times=pd.to_datetime(group.ts_utc,utc=True).sort_values().drop_duplicates()
            diffs=times.diff()
            for ix,val in diffs[diffs>delta*6].nlargest(3).items():
                pos=times.index.get_loc(ix); start=times.iloc[pos-1]+delta; end=times.iloc[pos]-delta
                gaps.append({'symbol':symbol,'start_utc':start.isoformat(),'end_utc':end.isoformat(),'missing_bars':max(0,int(val/delta)-1)})
        gaps=sorted(gaps,key=lambda x:x['missing_bars'],reverse=True)[:200]
    snapshots=sorted((Path(root)/'collect/universe').glob(f'{market}_*.csv'))
    eligible=[p for p in snapshots if p.stem[-8:]<=date_s.replace('-','')]
    snapshot=(eligible[-1] if eligible else snapshots[0]) if snapshots else None
    if snapshot is None:
        symbols=set()
    else:
        universe=pd.read_csv(snapshot)
        symbol_col=next((c for c in ('yahoo','symbol') if c in universe.columns),universe.columns[0])
        symbols=set(universe[symbol_col].dropna().astype(str))
    present=set(df.symbol.astype(str)) if not df.empty else set()
    counts_list=counts.tolist()
    result={'market':market,'interval':interval,'date':date_s,'rows':len(df),'n_symbols':len(present),'min_ts_utc':str(df.ts_utc.min()) if len(df) else None,'max_ts_utc':str(df.ts_utc.max()) if len(df) else None,'expected_bars_per_symbol':expected,'per_symbol_count':{'min':min(counts_list) if counts_list else 0,'median':median,'max':max(counts_list) if counts_list else 0},'symbols_short':[{'symbol':s,'n':int(n),'missing':max(0,expected-int(n))} for s,n in counts.items() if n<expected][:200],'gaps':gaps,'short_session':short,'universe_missing':sorted(symbols-present),'universe_snapshot_used':snapshot.name if snapshot else None,'adjusted':False,'tz_note':f'{TZ[market]} exchange-local trading date; timestamps stored in UTC','generated_at':datetime.now(timezone.utc).isoformat(),'src_counts':df.src.value_counts().to_dict() if len(df) else {}}
    out=Path(root)/'data/minute/_manifests'; out.mkdir(parents=True,exist_ok=True)
    (out/f'{market}_{interval}_{date_s}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

def rebuild_all(root: str | Path) -> list[dict]:
    base=Path(root)/'data/minute'
    results=[]
    for market_dir in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith('_')) if base.exists() else []:
        for interval_dir in sorted(p for p in market_dir.iterdir() if p.is_dir()):
            dates=sorted({p.name[5:] for p in interval_dir.glob('date=*') if p.is_dir()})
            for day in dates:
                results.append(build_manifest(market_dir.name,interval_dir.name,day,root))
    return results

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description='Build collection manifests')
    parser.add_argument('--rebuild-all',action='store_true',help='rebuild manifests for all discovered partitions')
    parser.add_argument('--root',default='.',help='collection data root (default: current directory)')
    args=parser.parse_args(argv)
    if not args.rebuild_all:
        parser.error('--rebuild-all is required')
    results=rebuild_all(args.root)
    print(f'Rebuilt {len(results)} manifests under {Path(args.root)/"data/minute/_manifests"}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
