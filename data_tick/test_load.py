import datetime as dt
import pyarrow as pa, pyarrow.parquet as pq
import load

def write(root,cat,sym,day,rows):
 p=root/cat/f'symbol={sym}'/f'date={day}'/'part-0.parquet';p.parent.mkdir(parents=True);pq.write_table(pa.Table.from_pylist(rows),p);return p

def row(ts,price,qty,maker,tid):return dict(symbol='BTC',ts=ts,exchange_event_ts=ts//1000,trade_ts=ts//1000,trade_id=tid,price=price,quantity=qty,buyer_is_maker=maker)
def test_partition_and_range(tmp_path,monkeypatch):
 monkeypatch.setattr(load,'ROOT',tmp_path)
 write(tmp_path,'crypto_perp','BTC','2026-01-01',[row(1_000_000,10,2,False,1)])
 write(tmp_path,'crypto_perp','BTC','2026-01-02',[row(86_401_000_000,11,3,True,2)])
 t=load.load_trades('crypto_perp','BTC','2026-01-01','2026-01-01');assert t.num_rows==1 and t['trade_id'][0].as_py()==1
 assert load.load_trades('crypto_perp','BTC','2026-01-01','2026-01-02').num_rows==2
 assert load.load_funding('BTC','2026-01-01','2026-01-02').num_rows==0

def test_resample_seconds_and_empty_forward_fill(tmp_path,monkeypatch):
 t=pa.Table.from_pylist([row(0,10,2,False,1),row(2_000_000,12,1,True,2)])
 b=load.resample_trades(t,'1s');assert b.num_rows==3
 assert b['signed_volume'].to_pylist()==[2.0,0.0,-1.0]
 assert b['close'].to_pylist()==[10.0,10.0,12.0]
 assert b['volume'].to_pylist()==[2.0,0.0,1.0]

def test_resample_minute():
 t=pa.Table.from_pylist([row(1_000_000,10,2,False,1),row(59_000_000,12,1,True,2),row(61_000_000,14,4,False,3)])
 b=load.resample_trades(t,'1m');assert b.num_rows==2
 assert b['open'].to_pylist()==[10.0,14.0] and b['close'].to_pylist()==[12.0,14.0]
 assert b['signed_volume'].to_pylist()==[1.0,4.0]
