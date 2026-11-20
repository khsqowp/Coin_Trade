#!/usr/bin/env python3
"""Streaming daily crypto JSONL to verified parquet partitions."""
import argparse,csv,datetime as dt,hashlib,json,math,os,pathlib,sys
from collections import defaultdict
import pyarrow as pa, pyarrow.parquet as pq
BASE=pathlib.Path(__file__).resolve().parent; ROOT=BASE.parent.parent/'trading-tick-archive'; OUT=BASE/'parquet'; CSV=BASE/'parquet_verification.csv'
CATS=('crypto_spot','crypto_perp','crypto_funding')
TRADE_FIELDS=['symbol','ts','exchange_event_ts','trade_ts','trade_id','price','quantity','buyer_is_maker']
FUND_FIELDS=['symbol','ts','exchange_event_ts','mark_price','funding_rate','next_funding_ts']
def files(cat,day):
 y,m,d=day.split('-');return sorted((ROOT/y/m/d).glob(f'*/{cat}.jsonl'))
def checksum_row(cat,o):
 fields=['symbol','trade_id','exchange_event_ts','price','quantity','buyer_is_maker'] if cat!='crypto_funding' else ['symbol','exchange_event_ts','mark_price','funding_rate','next_funding_ts']
 vals=[]
 for k in fields:
  v=o.get(k)
  if k in ('price','quantity','mark_price','funding_rate') and v is not None:v=repr(float(v))
  vals.append(v)
 b=json.dumps(vals,separators=(',',':'),ensure_ascii=False).encode();return int.from_bytes(hashlib.blake2b(b,digest_size=8).digest(),'big')
def checksum_add(acc,cat,o):return (acc+checksum_row(cat,o))&((1<<64)-1)
def schema(cat):
 fields={'symbol':pa.string(),'ts':pa.int64(),'exchange_event_ts':pa.int64()}
 if cat=='crypto_funding': fields.update(mark_price=pa.float64(),funding_rate=pa.float64(),next_funding_ts=pa.int64())
 else: fields.update(trade_ts=pa.int64(),trade_id=pa.int64(),price=pa.float64(),quantity=pa.float64(),buyer_is_maker=pa.bool_())
 return pa.schema(fields)
def normalize(cat,o):
 r={'symbol':str(o['symbol']),'ts':int(dt.datetime.fromisoformat(o['ts'].replace('Z','+00:00')).timestamp()*1_000_000),'exchange_event_ts':int(o['exchange_event_ts'])}
 if cat=='crypto_funding': r.update(mark_price=float(o['mark_price']),funding_rate=float(o['funding_rate']),next_funding_ts=int(o['next_funding_ts']))
 else:
  price=float(o['price_raw']);quantity=float(o['quantity_raw'])
  if price!=float(o['price']) or quantity!=float(o['quantity']):raise ValueError('numeric price/quantity does not round-trip from *_raw string')
  r.update(trade_ts=int(o['trade_ts']),trade_id=int(o['trade_id']),price=price,quantity=quantity,buyer_is_maker=bool(o['buyer_is_maker']))
 return r
def parquet_obj(cat,row):
 return {'symbol':row['symbol'],'exchange_event_ts':row['exchange_event_ts'],**({'mark_price':row['mark_price'],'funding_rate':row['funding_rate'],'next_funding_ts':row['next_funding_ts']} if cat=='crypto_funding' else {'trade_id':row['trade_id'],'price':row['price'],'quantity':row['quantity'],'buyer_is_maker':row['buyer_is_maker']})}
def verify(cat,day,paths,dropped):
 src_n=bad=src_bytes=0;src_sum=0; seen=set(); kept_n=0
 for fp in files(cat,day):
  src_bytes+=fp.stat().st_size
  with fp.open('rb') as f:
   for line in f:
    try:o=json.loads(line)
    except Exception:bad+=1;continue
    src_n+=1
    if cat!='crypto_funding':
     k=(o['symbol'],int(o['trade_id']))
     if k in seen:continue
     seen.add(k)
    kept_n+=1;src_sum=checksum_add(src_sum,cat,o)
 pq_n=pq_bytes=0;pq_sum=0
 for pp in paths:
  pq_bytes+=pp.stat().st_size
  pf=pq.ParquetFile(pp)
  for batch in pf.iter_batches(batch_size=100000):
   for o in batch.to_pylist():pq_n+=1;pq_sum=checksum_add(pq_sum,cat,o)
 return dict(category=cat,date=day,source_rows=src_n,source_malformed_lines=bad,source_dup_dropped=src_n-kept_n,parquet_rows=pq_n,rows_match=kept_n==pq_n,source_bytes=src_bytes,parquet_bytes=pq_bytes,src_checksum=f'{src_sum:016x}',pq_checksum=f'{pq_sum:016x}',checksum_match=src_sum==pq_sum,verified=(kept_n==pq_n and src_sum==pq_sum))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--categories',nargs='*',default=CATS);a=ap.parse_args()
 rows_out=[]
 if CSV.exists():
  with CSV.open() as f:rows_out=list(csv.DictReader(f))
 verified={(r['category'],r['date']) for r in rows_out if r.get('verified')=='True'}
 with (BASE/'work/convert.log').open('a') as log:
  for cat in a.categories:
   days=sorted({'-'.join(p.relative_to(ROOT).parts[:3]) for p in ROOT.glob(f'????/??/??/*/{cat}.jsonl')})
   for day in days:
    if day>=dt.datetime.now(dt.timezone.utc).date().isoformat() or (cat,day) in verified:continue
    # Recover existing outputs without modifying them; an incomplete day stays unverified.
    existing=sorted(OUT.glob(f'{cat}/symbol=*/date={day}/part-0.parquet'))
    if existing:
     row=verify(cat,day,existing,0)
     rows_out=[r for r in rows_out if not (r['category']==cat and r['date']==day)];rows_out.append(row)
     with CSV.open('w',newline='') as f:
      w=csv.DictWriter(f,fieldnames=['category','date','source_rows','source_malformed_lines','source_dup_dropped','parquet_rows','rows_match','source_bytes','parquet_bytes','src_checksum','pq_checksum','checksum_match','verified']);w.writeheader();w.writerows(rows_out)
     if row['verified']:(OUT/cat/f'.verified-{day}').write_text(json.dumps(row)+'\n')
     log.write(f"{cat} {day}: recovered existing output verified={row['verified']} rows={row['parquet_rows']}\n");log.flush();continue
    writers={}; seen=set(); dropped=0; malformed=0
    try:
     for fp in files(cat,day):
      with fp.open('rb') as f:
       for line in f:
        try:o=json.loads(line); row=normalize(cat,o)
        except Exception:malformed+=1;continue
        if cat!='crypto_funding':
         k=(row['symbol'],row['trade_id'])
         if k in seen:dropped+=1;continue
         seen.add(k)
        sym=row['symbol']; part=OUT/cat/f'symbol={sym}'/f'date={day}';part.mkdir(parents=True,exist_ok=True);path=part/'part-0.parquet'
        if sym not in writers:
         if path.exists(): raise RuntimeError(f'Existing unverified output blocks safe resume: {path}')
         writers[sym]=pq.ParquetWriter(path,schema(cat),compression='zstd',compression_level=6)
         writers[sym+'_buf']=[]
        buf=writers[sym+'_buf'];buf.append(row)
        if len(buf)>=500000:
         buf.sort(key=lambda r:r['exchange_event_ts'] if cat=='crypto_funding' else r['trade_id']);writers[sym].write_table(pa.Table.from_pylist(buf,schema=schema(cat)));buf.clear()
     for k,w in list(writers.items()):
      if k.endswith('_buf'):continue
      buf=writers[k+'_buf'];
      if buf:buf.sort(key=lambda r:r['exchange_event_ts'] if cat=='crypto_funding' else r['trade_id']);w.write_table(pa.Table.from_pylist(buf,schema=schema(cat)))
      w.close()
     paths=sorted(OUT.glob(f'{cat}/symbol=*/date={day}/part-0.parquet'))
     row=verify(cat,day,paths,dropped);row['source_malformed_lines']=malformed
     rows_out=[r for r in rows_out if not (r['category']==cat and r['date']==day)];rows_out.append(row)
     with CSV.open('w',newline='') as f:
      w=csv.DictWriter(f,fieldnames=['category','date','source_rows','source_malformed_lines','source_dup_dropped','parquet_rows','rows_match','source_bytes','parquet_bytes','src_checksum','pq_checksum','checksum_match','verified']);w.writeheader();w.writerows(rows_out)
     if row['verified']:
      marker=OUT/cat/f'.verified-{day}';marker.write_text(json.dumps(row)+'\n')
     log.write(f"{cat} {day}: verified={row['verified']} rows={row['parquet_rows']} dropped={dropped}\n");log.flush()
    except Exception as e:
     for k,w in list(writers.items()):
      if not k.endswith('_buf'):
       try:w.close()
       except:pass
     log.write(f'ERROR {cat} {day}: {type(e).__name__}: {e}\n');log.flush();raise
if __name__=='__main__':main()
