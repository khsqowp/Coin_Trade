from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from .common import SCHEMA,TZ,check_disk

def inspect(root: Path) -> tuple[list[str],list[str]]:
    base=root/'data/minute'; errors=[]; warnings=[]
    for path in base.glob('*/*/date=*/batch=*.parquet'):
        try: df=pd.read_parquet(path)
        except Exception as exc: errors.append(f'{path}: unreadable: {exc}'); continue
        if list(df.columns)!=SCHEMA: errors.append(f'{path}: schema mismatch')
        if df.duplicated(['symbol','ts_utc']).any(): errors.append(f'{path}: duplicate symbol/timestamp')
        bad=(df.low>df[['open','close']].min(axis=1))|(df.high<df[['open','close']].max(axis=1))|(df.low>df.high)
        if bad.any(): warnings.append(f'{path}: {int(bad.sum())} OHLC violations')
        market,interval=path.parts[-4:-2]; day=path.parent.name.split('=',1)[1]
        local=pd.to_datetime(df.ts_utc,utc=True).dt.tz_convert(TZ[market])
        if (local.dt.strftime('%Y-%m-%d')!=day).any(): warnings.append(f'{path}: partition date mismatch')
        open_time='09:30' if market=='us' else '09:00'; close_time='16:00' if market=='us' else '15:30'
        mins=local.dt.hour*60+local.dt.minute; a,b=map(lambda s:int(s[:2])*60+int(s[3:]),(open_time,close_time))
        outside=(mins<a)|(mins>=b if market=='us' else mins>b)
        if outside.any(): warnings.append(f'{path}: out of exchange session')
    try: check_disk(base)
    except Exception as exc: warnings.append(str(exc))
    return errors,warnings

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--root',default=None); args=parser.parse_args()
    import os
    root=Path(args.root or os.environ.get('STOCK_LOOP_ROOT','/home/noroot/research/stock_loop')); errors,warnings=inspect(root)
    print('LEVEL\tCOUNT\tDETAIL')
    for level,items in [('ERROR',errors),('WARN',warnings)]:
        for item in items: print(f'{level}\t{len(items)}\t{item}')
    print(f'ERRORS={len(errors)} WARNINGS={len(warnings)}'); return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())
