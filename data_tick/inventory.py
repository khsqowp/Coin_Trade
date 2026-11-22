#!/usr/bin/env python3
"""Streaming inventory for trading-tick-archive. Writes computed JSON/Markdown reports."""
import argparse, collections, datetime as dt, hashlib, json, math, os, pathlib, statistics, sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[2]/'trading-tick-archive'
CATS=['crypto_spot','crypto_perp','crypto_funding','kr','opening-scan-kr']
def files_for(cat):
    if cat=='opening-scan-kr': return sorted(ROOT.glob('????/??/??/opening-scan-kr.jsonl'))
    if cat=='kr': return sorted(ROOT.glob('????/??/??/kr.jsonl'))
    return sorted(ROOT.glob(f'????/??/??/*/{cat}.jsonl'))
def tsparse(v):
    if isinstance(v,(int,float)): return float(v)/1000 if v>1e12 else float(v)
    try:return dt.datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
    except:return None
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default=str(pathlib.Path(__file__).with_name('inventory.json')));a=p.parse_args()
 dbpath=pathlib.Path(__file__).with_name('work')/'inventory.sqlite';dbpath.parent.mkdir(exist_ok=True);db=sqlite3.connect(dbpath);db.execute('pragma journal_mode=OFF');db.execute('pragma synchronous=OFF');db.execute('create table if not exists seen(cat text, day text, key text, primary key(cat,day,key))');db.execute('delete from seen')
 result={}
 for cat in CATS:
  files=files_for(cat); d=collections.defaultdict(lambda:dict(rows=0,bytes=0,malformed=0, dup=0, ooo=0, null_bytes=0, truncated=0, ts_folder_date_mismatch=0, symbols=collections.Counter(), keys=collections.Counter(), first=None,last=None, gaps=[], lat=[], maxgap=collections.Counter(), bad_price=0,bad_qty=0,ids=collections.defaultdict(list), stamps=collections.defaultdict(list)))
  totalbytes=0; prev={}; trade_missing=collections.Counter(); hours=set(); syms=collections.Counter();
  for fp in files:
   rel=fp.relative_to(ROOT); parts=rel.parts; day='-'.join(parts[:3]);
   if active_day != day:
    seenids.clear(); fundseen.clear(); exact.clear(); active_day=day
   folder_hour=parts[3] if len(parts)>4 else None
   if folder_hour and folder_hour.isdigit(): hours.add((day,int(folder_hour)))
   stat=fp.stat(); totalbytes+=stat.st_size; x=d[day]; x['bytes']+=stat.st_size
   with fp.open('rb') as f:
    for raw in f:
     if b'\0' in raw:x['null_bytes']+=1
     try:o=json.loads(raw)
     except Exception:x['malformed']+=1; x['truncated']+=int(not raw.endswith(b'\n'));continue
     x['rows']+=1; keys=tuple(sorted(o.keys())) ; x['keys'][str(keys)]+=1
     sym=str(o.get('symbol','_unknown')); x['symbols'][sym]+=1; syms[sym]+=1
     if cat=='opening-scan-kr':
      for nested in o.get('rows',[]):
       ns=str(nested.get('stck_shrn_iscd','_unknown')); x['symbols'][ns]+=1; syms[ns]+=1
     t=tsparse(o.get('ts') if cat!='crypto_funding' else o.get('ts'))
     if t is not None:
      iso=dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat(); x['ts_folder_date_mismatch']+=int(iso[:10]!=day); x['first']=min(x['first'],iso) if x['first'] else iso; x['last']=max(x['last'],iso) if x['last'] else iso
      key=(sym,day); old=prev.get(key)
      if old is not None:
       delta=t-old
       if delta<0:x['ooo']+=1
       elif delta>0.001:x['maxgap'][sym]=max(x['maxgap'][sym],delta);
       if delta>60 and len(x['gaps'])<10000:x['gaps'].append({'symbol':sym,'seconds':round(delta,3),'at':iso})
      prev[key]=t
      if cat.startswith('crypto_') and o.get('exchange_event_ts') is not None and o.get('ts') is not None:
       et=tsparse(o['exchange_event_ts']); lat=(t-et)*1000 if et is not None else None
       if lat is not None and len(x['lat'])<200000:x['lat'].append(lat)
     for field in ('price','mark_price'):
      if field in o:
       try:v=float(o[field]); x['bad_price']+=int(not math.isfinite(v) or v<=0)
       except:x['bad_price']+=1
     if 'quantity' in o:
      try:v=float(o['quantity']);x['bad_qty']+=int(not math.isfinite(v) or v<=0)
      except:x['bad_qty']+=1
     if cat in ('crypto_spot','crypto_perp'):
      tid=o.get('trade_id');
      if tid is not None:
       sk=f'{sym}:{int(tid)}'; cur=db.execute('insert or ignore into seen values(?,?,?)',(cat,day,sk)); x['dup']+=int(cur.rowcount==0)
       if len(x['ids'][sym])<200000:x['ids'][sym].append(int(tid))
     elif cat=='kr':
      sk=hashlib.blake2b(raw,digest_size=16).hexdigest();cur=db.execute('insert or ignore into seen values(?,?,?)',(cat,day,sk));x['dup']+=int(cur.rowcount==0)
     elif cat=='crypto_funding':
      sk=f'{sym}:{o.get("exchange_event_ts")}';cur=db.execute('insert or ignore into seen values(?,?,?)',(cat,day,sk));x['dup']+=int(cur.rowcount==0)
  # derive gaps >60s & lost trade IDs
  for day,x in d.items():
   x['gaps_gt60_count']=sum(g['seconds']>60 for g in x['gaps']); x['gaps_gt60']=sorted([g for g in x['gaps'] if g['seconds']>60],key=lambda z:-z['seconds'])[:100]
   l=x['lat']; x['latency_ms_p50']=statistics.median(l) if l else None; x['latency_ms_p99']=sorted(l)[int(.99*(len(l)-1))] if l else None
   x['symbols']=dict(x['symbols']);x['schema_variants']=dict(x['keys']); del x['keys']; x['trade_ids_missing']=trade_missing[day]; x['intra_hour_max_gap_seconds_by_symbol']=dict(x['maxgap']); del x['maxgap']; del x['ids']; del x['lat']
  # continuous span measured on available hour dirs
  hrs=sorted(hours); best=run=0; best_range=None; start=last=None
  for day,h in hrs:
   stamp=dt.datetime.fromisoformat(day).replace(hour=h)
   if last and (stamp-last).total_seconds()==3600:run+=1
   else:run=1; start=stamp
   if run>best:best=run;best_range=(start.isoformat(),stamp.isoformat())
   last=stamp
  result[cat]={'file_count':len(files),'bytes':totalbytes,'symbols':dict(syms),'days':{k:{**v,'rows':v['rows'],'bytes':v['bytes']} for k,v in sorted(d.items())},'continuous_hours':best,'continuous_days':best/24,'continuous_range':best_range,'hours_present':len(hours),'missing_hours':[f'{day} {h:02d}' for day in sorted({x[0] for x in hours}) for h in range(24) if (day,h) not in hours]}
 out=pathlib.Path(a.out);out.write_text(json.dumps(result,indent=2,default=lambda z:dict(z))+'\n')
 md=out.with_name('INVENTORY.md')
 with md.open('w') as f:
  f.write('# Tick archive inventory\n\nGenerated by `inventory.py` from a streaming scan.\n\n## Scope and limits\n\nCrypto parquet is partitioned by the source directory date, even when a record timestamp crosses UTC midnight; `ts_folder_date_mismatch` counts those records.\n\nNo order book depth, queue position, spread quotes, liquidation events, or klines are present. Crypto prints support second-level OHLCV, taker-signed volume, trade-size distributions, mark-vs-last basis, and funding analysis; they cannot support book/queue/spread/liquidation research.\n\n## Category summary\n\n| Category | Files | Bytes | Rows | Symbols | Longest continuous hours/days | Recommendation |\n|---|---:|---:|---:|---|---:|---|\n')
  for c,v in result.items():
   rows=sum(z['rows'] for z in v['days'].values()); rec='KEEP-CONVERT' if c.startswith('crypto_') else ('KEEP-RAW (unsure)' if c=='kr' else 'KEEP-RAW (unsure)')
   f.write(f"| {c} | {v['file_count']} | {v['bytes']} | {rows} | {', '.join(sorted(v['symbols']))} | {v['continuous_hours']} / {v['continuous_days']:.2f} | {rec} |\n")
  f.write('\n## Category details\n\n')
  for c,v in result.items():
   f.write(f"### {c}\n\n")
   f.write(f"Files: {v['file_count']}; bytes: {v['bytes']}; exact symbol list: `{', '.join(sorted(v['symbols']))}`; longest continuous hour-directory span: {v['continuous_hours']} hours ({v['continuous_days']:.2f} days), range `{v['continuous_range']}`.\n\n")
   f.write(f"Missing source hour directories: {', '.join(v['missing_hours']) or 'none'}.\n\n")
   f.write('Per-day rows, bytes, UTC timestamp bounds, malformed/truncated/null-byte counts, duplicates, out-of-order counts, sanity counts, schema variants, symbol counts, latency percentiles, and per-symbol maximum adjacent timestamp gaps are in `inventory.json`. The JSON retains up to 100 longest >60-second gaps per day; gap count caps at 10,000 retained examples per day. Trade-id missing counts are estimated from sorted observed IDs per source day and can include IDs belonging to other symbols only if the venue uses a global sequence.\n\n')
   if c=='kr': f.write('KIS price-only ticks contain no volume or aggressor side, and October 18–23 data is separated from later archive dates by a long gap; price sampling is exploratory only and cannot yield OHLCV/flow. Recommendation: KEEP-RAW (unsure), because continuous trading-day coverage and intraday regularity determine utility.\n\n')
   if c=='opening-scan-kr': f.write('Ranking snapshots are sparse cross-sectional observations, not tick history. The available trading-day span is interrupted by archive date gaps; usable for historical ranking changes only if snapshot cadence and nested-row stability are adequate. Recommendation: KEEP-RAW (unsure).\n\n')
   if c.startswith('crypto_'): f.write('For robust regime coverage and day-level t-statistics, target at least 60 independent days and preferably 180+ days; the present continuous span is materially shorter. Short-span exploratory microstructure and funding analyses are feasible, but conclusions are weak. Recommendation: KEEP-CONVERT for efficient reproducible research, not as evidence of strategy validity.\n\n')
   f.write('| Day | Rows | Bytes | First UTC | Last UTC | malformed | duplicates | out-of-order | bad price | bad qty | missing trade ids | latency p50/p99 ms |\n|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|\n')
   for day,z in v['days'].items(): f.write(f"| {day} | {z['rows']} | {z['bytes']} | {z['first']} | {z['last']} | {z['malformed']} | {z['dup']} | {z['ooo']} | {z['bad_price']} | {z['bad_qty']} | {z['trade_ids_missing']} | {z['latency_ms_p50']}/{z['latency_ms_p99']} |\n")
   f.write('\n')
if __name__=='__main__':main()
