from __future__ import annotations
import argparse, hashlib, json, logging, os, random, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from .common import Abort, check_resources, normalize_bars, merge_write
from .manifest import build_manifest
from .universe import us_universe, kr_universe

def split_download(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if isinstance(frame.columns,pd.MultiIndex):
        if symbol not in frame.columns.get_level_values(0): return pd.DataFrame()
        out=frame[symbol].copy()
        if isinstance(out.columns,pd.MultiIndex): out.columns=out.columns.get_level_values(-1)
        return out
    return frame.copy()

def _download(symbols: list[str], interval: str, period: str|None, start: str|None=None, end: str|None=None) -> pd.DataFrame:
    import yfinance as yf
    opts={'tickers':symbols,'interval':interval,'auto_adjust':False,'prepost':False,'threads':False,'progress':False,'group_by':'ticker'}
    if period: opts['period']=period
    if start: opts['start']=start; opts['end']=end
    return yf.download(**opts)

def _logging(root: Path, market: str, mode: str) -> None:
    folder=root/'collect/logs'; folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{market}_{mode}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[logging.StreamHandler(sys.stderr),logging.FileHandler(path)])

def _universe(market: str) -> list[str]:
    frame=us_universe() if market=='us' else kr_universe()
    return frame.symbol.tolist() if 'symbol' in frame else frame.yahoo.tolist()

def _windows() -> list[tuple[str,str]]:
    today=datetime.now(timezone.utc).date(); start=today-timedelta(days=29); finish=today+timedelta(days=1); out=[]
    while start<finish:
        end=min(start+timedelta(days=7),finish); out.append((start.isoformat(),end.isoformat())); start=end
    return out

def _requests(mode: str, market: str) -> list[tuple[str,str|None,str|None]]:
    if mode=='daily': return [('1m','7d',None),('5m','5d',None)]
    if mode=='backfill5m': return [('5m','60d',None)]
    if mode=='backfill1m': return [('1m',None,None)]
    raise ValueError('invalid mode')

def _fetch_batch(batch: list[str], interval: str, period: str|None, start: str|None, end: str|None) -> pd.DataFrame:
    delays=[10,30,90]
    for attempt in range(4):
        try:
            result=_download(batch,interval,period,start,end)
            if not result.empty: return result
            raise RuntimeError('empty response')
        except Exception as exc:
            if attempt==3: raise
            wait=120 if '429' in str(exc) or 'too many' in str(exc).lower() else delays[attempt]
            logging.warning('download retry %d/3 interval=%s error=%s wait=%ds',attempt+1,interval,exc,wait)
            time.sleep(wait)
    raise RuntimeError('unreachable')

def _batches(symbols: list[str], size: int) -> list[list[str]]:
    return [symbols[i:i+size] for i in range(0,len(symbols),size)]

def _marker(root: Path, mode: str, market: str, batch: list[str]) -> Path:
    digest=hashlib.sha1(','.join(sorted(batch)).encode()).hexdigest()[:12]
    return root/'collect/state'/f'{mode}_{market}_{digest}.done'

def _fetch_normalized(batch: list[str], interval: str, period: str|None, start: str|None,
                      end: str|None, market: str) -> pd.DataFrame:
    frame=_fetch_batch(batch,interval,period,start,end); pieces=[]
    for symbol in batch:
        piece=split_download(frame,symbol)
        if not piece.empty:
            normalized=normalize_bars(piece,symbol,market,interval)
            if len(normalized): pieces.append(normalized)
    return pd.concat(pieces,ignore_index=True) if pieces else pd.DataFrame()

def _record_frame(df: pd.DataFrame, interval: str, market: str, root: Path,
                  dry_run: bool, touched: set[tuple[str,str]], data_symbols: set[str]) -> int:
    if df.empty: return 0
    local_tz='America/New_York' if market=='us' else 'Asia/Seoul'
    touched.update((interval,d) for d in df.ts_utc.dt.tz_convert(local_tz).dt.strftime('%Y-%m-%d'))
    data_symbols.update(df.symbol.tolist())
    if not dry_run: merge_write(df,market,interval,root)
    return len(df)

def _process_batch(batch: list[str], args: argparse.Namespace, root: Path,
                   touched: set[tuple[str,str]], data_symbols: set[str], dry_run: bool) -> tuple[bool,int]:
    rows=0
    for interval,period,end in _requests(args.mode,args.market):
        windows=_windows() if args.mode=='backfill1m' else [(None,None)]
        for start,stop in windows:
            try:
                df=_fetch_normalized(batch,interval,period if start is None else None,
                                     start,stop or end,args.market)
            except Exception as exc:
                logging.exception('batch failed: %s',exc); return False,rows
            rows+=_record_frame(df,interval,args.market,root,dry_run,touched,data_symbols)
    return True,rows

def _finish(root: Path, market: str, touched: set[tuple[str,str]], dry_run: bool) -> None:
    if dry_run:
        logging.info('dry run: would write %d manifests',len(touched)); return
    for interval,day in sorted(touched): build_manifest(market,interval,day,root)

def run(args: argparse.Namespace) -> int:
    started=time.monotonic(); root=Path(os.environ.get('STOCK_LOOP_ROOT','/home/noroot/research/stock_loop')); _logging(root,args.market,args.mode)
    try: check_resources()
    except Abort as exc: logging.error('ABORT: %s',exc); return 3
    symbols=_universe(args.market); symbols=symbols[:args.limit] if args.limit else symbols
    root.mkdir(parents=True,exist_ok=True); failed=set(); touched=set(); data_symbols=set(); row_count=0; consecutive=0
    backfill=args.mode.startswith('backfill')
    exit_code=0
    for batchno,batch in enumerate(_batches(symbols,args.batch)):
        marker=_marker(root,args.mode,args.market,batch) if backfill else None
        if marker and marker.exists(): continue
        if not backfill and batchno and batchno%10==0:
            try: check_resources()
            except Abort as exc: logging.error('ABORT: %s',exc); return 3
        success,rows=_process_batch(batch,args,root,touched,data_symbols,args.dry_run); row_count+=rows
        if success and marker and not args.dry_run: marker.parent.mkdir(parents=True,exist_ok=True); marker.write_text('ok\n')
        if not success: failed.update(batch)
        consecutive=0 if success else consecutive+1
        if consecutive>=5:
            exit_code=4
            break
        time.sleep(args.sleep+random.random())
    _finish(root,args.market,touched,args.dry_run)
    summary={'rows':row_count,'symbols_requested':len(symbols),'symbols_with_data':len(data_symbols),'failed_symbols':len(failed),'seconds':round(time.monotonic()-started,2)}
    print(json.dumps(summary,separators=(',',':')))
    if exit_code: return exit_code
    if symbols and len(failed)==len(symbols): return 5
    if not args.dry_run and row_count==0 and failed: return 5
    return 0

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--market',choices=['us','kr'],required=True); parser.add_argument('--mode',choices=['daily','backfill5m','backfill1m'],required=True); parser.add_argument('--limit',type=int); parser.add_argument('--dry-run',action='store_true'); parser.add_argument('--batch',type=int,default=25); parser.add_argument('--sleep',type=float,default=2.0)
    return run(parser.parse_args())

if __name__=='__main__': raise SystemExit(main())
