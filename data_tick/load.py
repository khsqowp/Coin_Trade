"""Partition reader for converted tick parquet. End dates are inclusive UTC dates."""
import datetime as dt,pathlib
import numpy as np
import pyarrow as pa, pyarrow.parquet as pq
import os
ROOT=pathlib.Path(os.environ.get('TICK_PARQUET_DIR',pathlib.Path.home()/'CODE'/'trading_data'/'tick'/'parquet'))
def _days(start,end):
 s=dt.date.fromisoformat(str(start)[:10]);e=dt.date.fromisoformat(str(end)[:10]);
 while s<=e:yield s.isoformat();s+=dt.timedelta(days=1)
def _load(cat,symbol,start,end):
 tabs=[]
 for day in _days(start,end):
  p=ROOT/cat/f'symbol={symbol}'/f'date={day}'/'part-0.parquet'
  if p.exists():tabs.append(pq.read_table(p))
 if not tabs:return pa.table({})
 return pa.concat_tables(tabs)
def load_trades(category,symbol,start,end):
 if category not in ('crypto_perp','crypto_spot'):raise ValueError('category must be crypto_perp or crypto_spot')
 return _load(category,symbol,start,end)
def load_funding(symbol,start,end):return _load('crypto_funding',symbol,start,end)
def resample_trades(table,freq='1s'):
 """UTC bars; empty bars carry prior close and have zero volume/count. No leading fill before first trade."""
 if isinstance(freq,str) and freq.endswith('s'):width=int(freq[:-1])*1_000_000
 elif isinstance(freq,str) and freq.endswith('m'):width=int(freq[:-1])*60_000_000
 else:raise ValueError("freq must use seconds or minutes, e.g. '1s' or '1m'")
 if table.num_rows==0:return pa.table({'ts':pa.array([],pa.int64()),'open':pa.array([],pa.float64()),'high':pa.array([],pa.float64()),'low':pa.array([],pa.float64()),'close':pa.array([],pa.float64()),'volume':pa.array([],pa.float64()),'buy_volume':pa.array([],pa.float64()),'sell_volume':pa.array([],pa.float64()),'signed_volume':pa.array([],pa.float64()),'trade_count':pa.array([],pa.int64()),'vwap':pa.array([],pa.float64())})
 ts=np.asarray(table['ts'].to_numpy(),dtype=np.int64); price=np.asarray(table['price'].to_numpy(),dtype=np.float64); qty=np.asarray(table['quantity'].to_numpy(),dtype=np.float64); maker=np.asarray(table['buyer_is_maker'].to_numpy(),dtype=np.bool_)
 bins=ts//width*width; order=np.argsort(ts,kind='stable');bins,price,qty,maker=bins[order],price[order],qty[order],maker[order]
 out={k:[] for k in ['ts','open','high','low','close','volume','buy_volume','sell_volume','signed_volume','trade_count','vwap']};i=0;last=None;cur=bins[0]
 while i<len(ts):
  b=bins[i]
  if last is not None:
   empty=cur+width
   while empty<b:
    out['ts'].append(int(empty));out['open'].append(last);out['high'].append(last);out['low'].append(last);out['close'].append(last);out['volume'].append(0.);out['buy_volume'].append(0.);out['sell_volume'].append(0.);out['signed_volume'].append(0.);out['trade_count'].append(0);out['vwap'].append(float('nan'));empty+=width
  j=i+1
  while j<len(ts) and bins[j]==b:j+=1
  q=qty[i:j];p=price[i:j];buy=(~maker[i:j]);bv=float(q[buy].sum());sv=float(q[~buy].sum());vol=float(q.sum());close=float(p[-1]);
  out['ts'].append(int(b));out['open'].append(float(p[0]));out['high'].append(float(p.max()));out['low'].append(float(p.min()));out['close'].append(close);out['volume'].append(vol);out['buy_volume'].append(bv);out['sell_volume'].append(sv);out['signed_volume'].append(bv-sv);out['trade_count'].append(j-i);out['vwap'].append(float((p*q).sum()/vol) if vol else float('nan'));last=close;cur=b;i=j
 return pa.table(out)
