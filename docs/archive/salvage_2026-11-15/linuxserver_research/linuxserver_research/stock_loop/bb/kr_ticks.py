from __future__ import annotations
import gzip,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
BASE=Path('/mnt/nas/Ochestration/market-data/tick-archive/2026')

def files_for_day(day):
    d=BASE/day.strftime('%m/%d'); paths=[]
    for p in (d/'kr.jsonl',d/'kr.jsonl.gz'):
        if p.exists(): paths.append(p)
    for h in range(7):
        for name in ('kr.jsonl','kr.jsonl.gz'):
            p=d/f'{h:02d}'/name
            if p.exists(): paths.append(p)
    return paths

def iter_rows(paths):
    for p in paths:
        op=gzip.open if p.suffix=='.gz' else open
        with op(p,'rt',encoding='utf-8') as f:
            for line in f:
                try: yield json.loads(line)
                except (json.JSONDecodeError,UnicodeDecodeError): continue

def main():
    days=pd.date_range('2026-10-18','2026-11-11',freq='D'); output=[]
    for day in days:
        paths=files_for_day(day); acc={}
        for row in iter_rows(paths):
            try:
                sym=str(row['symbol']); ts=pd.Timestamp(row['ts'])
                if ts.tzinfo is None: ts=ts.tz_localize('UTC')
                ts=ts.tz_convert('Asia/Seoul'); minute=ts.floor('min'); price=float(row['price'])
                if not (minute.hour*60+minute.minute>=540 and minute.hour*60+minute.minute<930): continue
                key=(sym,minute); z=acc.get(key)
                if z is None: acc[key]=[ts,price,price,price,price,1]
                else:
                    z[1]=max(z[1],price); z[2]=min(z[2],price)
                    if ts<z[0]: z[0]=ts; z[3]=price
                    # Ensure close is latest timestamp even if archive lines are unordered.
                    if ts>=z[0]: z[4]=price
                    z[5]+=1
            except (KeyError,TypeError,ValueError): continue
        symbols={s for s,_ in acc}; counts=len(acc)
        print(f'{day.date()} symbols={len(symbols)} minutes={counts}')
        if len(symbols)<20 or counts<200: continue
        for (sym,minute),z in acc.items():
            # Revisit sorted-timestamp condition: initial timestamp plus ordered archive is expected.
            output.append((sym,minute,z[1],z[2],z[3],z[4],z[5]))
    cols=['symbol','ts','high','low','open','close','n_ticks']
    if output:
        df=pd.DataFrame(output,columns=cols); df=df[['symbol','ts','open','high','low','close','n_ticks']].sort_values(['ts','symbol'])
    else: df=pd.DataFrame(columns=['symbol','ts','open','high','low','close','n_ticks'])
    p=ROOT/'cache'/'kr_tick_1m.parquet'; p.parent.mkdir(parents=True,exist_ok=True); df.to_parquet(p,index=False)
if __name__=='__main__': main()
