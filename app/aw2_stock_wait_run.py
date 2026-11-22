"""Complete the stock-family stage after the round-2 cache polling window."""
from __future__ import annotations
import csv,time
from pathlib import Path
import pandas as pd
from app.aw2_round2 import BASE,LOG,STOCK_FAMILIES,run_group
from app.aw_data import _cache_path
from app.aw_universe import stocks

DEADLINE=pd.Timestamp("2026-11-12T23:29:27Z")

def first_bars():
    rows=[]
    for market in ("KR","US"):
        for item in stocks(market):
            path=_cache_path(market,item["code"])
            if not path.exists():rows.append((market,item["code"],None));continue
            try:
                with path.open(encoding="utf-8",newline="") as f: value=next(csv.DictReader(f),{}).get("timestamp")
                rows.append((market,item["code"],str(value)[:10] if value else None))
            except Exception:rows.append((market,item["code"],None))
    return rows

def save_dates(rows):
    path=BASE/"stock_cache_first_dates.csv";path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["market","symbol","first_bar","cache_status"])
        for m,s,d in rows:w.writerow([m,s,d or "","PRESENT" if d else "MISSING"])

def main():
    while True:
        rows=first_bars();save_dates(rows)
        pending=[(m,s,d) for m,s,d in rows if d and d.startswith("2018")]
        now=pd.Timestamp.now(tz="UTC")
        if not pending or now>=DEADLINE:break
        next_wait=min(600,max(1,int((DEADLINE-now).total_seconds())))
        with LOG.open("a",encoding="utf-8") as f:
            f.write(f"\n- cache poll {now.isoformat()}: still-2018 files={len(pending)} ({', '.join(m+'_'+s for m,s,_ in pending)}); wait {next_wait}s.\n")
        time.sleep(next_wait)
    save_dates(rows)
    fallback=any(d and d.startswith("2018") for _,_,d in rows)
    with LOG.open("a",encoding="utf-8") as f:
        f.write(f"\n### 개별주 시작 — {pd.Timestamp.now(tz='UTC').isoformat()}\n\n- 2018년 시작 파일 {sum(1 for _,_,d in rows if d and d.startswith('2018'))}개; fallback={fallback}. `KR_005930={next((d for m,s,d in rows if m=='KR' and s=='005930'),None)}`, `US_AAPL={next((d for m,s,d in rows if m=='US' and s=='AAPL'),None)}`. 심볼별 날짜는 `stock_cache_first_dates.csv`에 기록했다.\n")
    out=[]
    for family in STOCK_FAMILIES:
        for market in ("KR","US"):
            out.append(run_group(market,family,workers=3))
    with LOG.open("a",encoding="utf-8") as f:
        f.write("\n### F9 결정\n\n")
        for market in ("KR","US"):
            valid=[x for x in out if x["market"]==market and x["grade"] in ("A","B")]
            f.write(f"- {market}: A/B 구성요소 {len(valid)}개; "+("F9 ensemble not required." if len(valid)<2 else "F9 ensemble needs explicit follow-up." )+"\n")
    print(f"completed stock groups={len(out)} fallback={fallback}",flush=True)
if __name__=="__main__":main()
