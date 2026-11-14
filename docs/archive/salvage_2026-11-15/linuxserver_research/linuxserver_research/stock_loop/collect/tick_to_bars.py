from __future__ import annotations
import argparse, gzip, json, logging, os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from .common import merge_write

DEFAULT_BASES=['/home/noroot/CODE/Ochestration/trading-tick-archive','/mnt/nas/Ochestration/market-data/tick-archive']

def _files(base: Path, day: date) -> dict[int,list[Path]]:
    found=defaultdict(list); flat=base/day.strftime('%Y/%m/%d')/'kr.jsonl'
    if flat.exists(): found[-1].append(flat)
    if (flat.with_suffix('.jsonl.gz')).exists(): found[-1].append(flat.with_suffix('.jsonl.gz'))
    for hour in range(7):
        path=base/day.strftime(f'%Y/%m/%d/{hour:02d}')/'kr.jsonl'
        for item in (path,path.with_suffix('.jsonl.gz')):
            if item.exists(): found[hour].append(item)
    return found

def _open(path: Path):
    return gzip.open(path,'rt',encoding='utf-8') if path.suffix=='.gz' else path.open(encoding='utf-8')

def _tick_files(bases: list[Path], day: date) -> list[Path]:
    local=_files(bases[0],day); selected=[]
    for hour,files in local.items(): selected.extend(files)
    for base in bases[1:]:
        for hour,files in _files(base,day).items():
            if hour not in local: selected.extend(files)
    return selected

def convert_date(day: date, bases: list[Path], root: Path) -> dict:
    aggregate={}; malformed=0; ticks=0
    for path in _tick_files(bases,day):
        try: stream=_open(path)
        except OSError as exc: logging.warning('cannot open %s: %s',path,exc); continue
        with stream:
            for line in stream:
                try:
                    item=json.loads(line); symbol=str(item['symbol']); ts=pd.Timestamp(item['ts']); price=float(item['price'])
                    if ts.tzinfo is None: raise ValueError('naive timestamp')
                except Exception:
                    malformed+=1; continue
                ts=ts.tz_convert('UTC'); local=ts.tz_convert('Asia/Seoul')
                if local.date()!=day or not (local.hour>9 or (local.hour==9 and local.minute>=0)) or (local.hour,local.minute)>=(15,30): continue
                ticks+=1; minute=ts.floor('min'); group=(symbol,minute)
                if group not in aggregate: aggregate[group]=[ts,price,price,price,ts,price]
                row=aggregate[group]; row[2]=max(row[2],price); row[3]=min(row[3],price)
                if ts<row[0]: row[0]=ts; row[1]=price
                if ts>=row[4]: row[4]=ts; row[5]=price
    rows=[{'symbol':s,'ts_utc':m,'open':v[1],'high':v[2],'low':v[3],'close':v[5],'volume':0,'adjusted':False,'src':'tick'} for (s,m),v in aggregate.items()]
    frame=pd.DataFrame(rows,columns=['symbol','ts_utc','open','high','low','close','volume','adjusted','src'])
    if len(frame): merge_write(frame,'kr','1m',root)
    return {'date':day.isoformat(),'ticks_read':ticks,'bars':len(frame),'symbols':frame.symbol.nunique() if len(frame) else 0,'malformed':malformed}

def _days(args: argparse.Namespace) -> list[date]:
    if args.date: return [date.fromisoformat(args.date)]
    start=date.fromisoformat(args.from_date); end=date.fromisoformat(args.to_date)
    if end<start: raise ValueError('--to must be on or after --from')
    return [start+timedelta(days=i) for i in range((end-start).days+1)]

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--date'); parser.add_argument('--from',dest='from_date'); parser.add_argument('--to',dest='to_date'); parser.add_argument('--src-dirs',nargs='*',default=DEFAULT_BASES); args=parser.parse_args()
    root=Path(os.environ.get('STOCK_LOOP_ROOT','/home/noroot/research/stock_loop')); state=root/'collect/state'; state.mkdir(parents=True,exist_ok=True); summaries=[]
    for day in _days(args):
        result=convert_date(day,[Path(p) for p in args.src_dirs],root); (state/f'tick_to_bars_{day.isoformat()}.json').write_text(json.dumps(result,indent=2)); summaries.append(result)
    print(json.dumps(summaries,separators=(',',':'))); return 0
if __name__=='__main__': raise SystemExit(main())
