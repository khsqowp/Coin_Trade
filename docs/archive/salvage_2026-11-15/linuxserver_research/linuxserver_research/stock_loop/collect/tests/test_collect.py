import json
import pandas as pd
import pytest
from collect.common import SCHEMA, check_disk, Abort, merge_write, normalize_bars
from collect.manifest import build_manifest, rebuild_all
from collect.yf_collect import split_download, _windows, _marker
from collect.tick_to_bars import convert_date
from collect.manifest_check import main as check_main

def raw(index):
    return pd.DataFrame({'Open':[1.], 'High':[3.], 'Low':[1.], 'Close':[2.], 'Volume':[0]},index=[pd.Timestamp(index)])

@pytest.mark.parametrize(('market','idx','expected'), [('us','2026-01-02 09:30:00-05:00','2026-01-02 14:30:00+00:00'),('us','2026-07-02 09:30:00-04:00','2026-07-02 13:30:00+00:00'),('kr','2026-01-02 09:00:00+09:00','2026-01-02 00:00:00+00:00')])
def test_normalize_tz(market,idx,expected):
    out=normalize_bars(raw(idx),'AAA',market,'1m')
    assert out.ts_utc.iloc[0]==pd.Timestamp(expected)
    assert out.adjusted.iloc[0] is False or not out.adjusted.iloc[0]

def _row(symbol,ts,src='yf',close=10):
    return {'symbol':symbol,'ts_utc':pd.Timestamp(ts),'open':close,'high':close,'low':close,'close':close,'volume':1,'adjusted':False,'src':src}

def test_merge_idempotent_priority_and_local_date(tmp_path):
    rows=pd.DataFrame([_row('AAA','2026-01-02 20:00Z','tick',11),_row('AAA','2026-01-02 20:00Z','yf',10),_row('BBB','2026-01-02 20:00Z')])
    merge_write(rows,'us','1m',tmp_path); path=next((tmp_path/'data/minute/us/1m').rglob('*.parquet')); before=path.read_bytes()
    merge_write(rows,'us','1m',tmp_path); assert path.read_bytes()==before
    result=pd.read_parquet(path); assert not result.duplicated(['symbol','ts_utc']).any()
    assert result.loc[result.symbol.eq('AAA'),'src'].iloc[0]=='yf'
    assert 'date=2026-01-02' in str(path)

def test_split_multiindex():
    frame=pd.DataFrame([[1,2]],columns=pd.MultiIndex.from_product([['AAA','BBB'],['Close']]))
    assert split_download(frame,'AAA').iloc[0,0]==1
    assert split_download(frame,'CCC').empty

def test_split_and_normalize_multi_ticker_with_adj_close():
    columns=pd.MultiIndex.from_product([['AAA','BBB'],['Open','High','Low','Close','Adj Close','Volume']])
    frame=pd.DataFrame([[10,12,9,11,10.5,100,20,22,19,21,20.5,200]],
                       index=[pd.Timestamp('2026-01-02 14:30Z')],columns=columns)
    piece=split_download(frame,'AAA')
    out=normalize_bars(piece,'AAA','us','1m')
    assert list(out.columns)==SCHEMA
    assert len(out)==1
    assert out.close.iloc[0]==11

def test_backfill_windows_are_utc_date_strings():
    from datetime import date, datetime, timedelta, timezone
    windows=_windows(); today=datetime.now(timezone.utc).date()
    assert windows[0][0]==(today-timedelta(days=29)).isoformat()
    assert windows[-1][1]==(today+timedelta(days=1)).isoformat()
    assert all(len(a)==10 and len(b)==10 and a<b for a,b in windows)
    assert all((date.fromisoformat(b)-date.fromisoformat(a)).days<=7 for a,b in windows)
    assert all(windows[i][1]==windows[i+1][0] for i in range(len(windows)-1))

def test_backfill_marker_is_stable_under_symbol_order(tmp_path):
    assert _marker(tmp_path,'backfill5m','us',['BBB','AAA']) == _marker(tmp_path,'backfill5m','us',['AAA','BBB'])
    assert _marker(tmp_path,'backfill5m','us',['AAA']) != _marker(tmp_path,'backfill5m','us',['AAA','BBB'])
    assert _marker(tmp_path,'backfill5m','us',['AAA']).name.endswith('.done')

def test_manifest_gaps_tiny(tmp_path):
    frame=pd.DataFrame([_row('A','2026-01-02 14:30Z'),_row('A','2026-01-02 14:40Z')])
    merge_write(frame,'us','1m',tmp_path)
    result=build_manifest('us','1m','2026-01-02',tmp_path)
    assert result['rows']==2 and result['gaps']==[] # tiny data qualifies as short session
    assert result['short_session'] is True

def test_manifest_kr_universe_uses_yahoo_column_and_oldest_fallback(tmp_path):
    universe=tmp_path/'collect/universe'; universe.mkdir(parents=True)
    pd.DataFrame({'code':['005930'],'yahoo':['005930.KS']}).to_csv(universe/'kr_20260103.csv',index=False)
    frame=pd.DataFrame([_row('005930.KS','2026-01-02 00:00Z')])
    merge_write(frame,'kr','1m',tmp_path)
    result=build_manifest('kr','1m','2026-01-02',tmp_path)
    assert result['universe_missing']==[]
    assert result['universe_snapshot_used']=='kr_20260103.csv'

def test_manifest_prefers_symbol_when_no_yahoo(tmp_path):
    universe=tmp_path/'collect/universe'; universe.mkdir(parents=True)
    pd.DataFrame({'code':['wrong'],'symbol':['RIGHT']}).to_csv(universe/'us_20260101.csv',index=False)
    result=build_manifest('us','1m','2026-01-02',tmp_path)
    assert result['universe_missing']==['RIGHT']

def test_rebuild_all_discovers_market_interval_date_partitions(tmp_path):
    (tmp_path/'data/minute/us/1m/date=2026-01-02').mkdir(parents=True)
    (tmp_path/'data/minute/kr/5m/date=2026-01-03').mkdir(parents=True)
    results=rebuild_all(tmp_path)
    assert [(r['market'],r['interval'],r['date']) for r in results]==[('kr','5m','2026-01-03'),('us','1m','2026-01-02')]
    assert len(list((tmp_path/'data/minute/_manifests').glob('*.json')))==2

def test_us_universe_aliases_legacy_sp500_tickers(tmp_path,monkeypatch):
    import collect.universe as universe
    cache=tmp_path/'us_universe.csv'; pd.DataFrame({'symbol':['BRKB','BFB']}).to_csv(cache,index=False)
    monkeypatch.setattr(universe,'_cache',lambda name: cache)
    monkeypatch.setenv('STOCK_LOOP_ROOT',str(tmp_path))
    class Response:
        text=''
        def raise_for_status(self): pass
    class Requests:
        @staticmethod
        def get(*args,**kwargs): return Response()
    import sys
    monkeypatch.setitem(sys.modules,'requests',Requests)
    frame=universe.us_universe()
    assert set(frame.loc[frame.group.eq('sp500'),'symbol'])=={'BRK-B','BF-B'}

def test_tick_flat_hourly_duplicate_bad_line(tmp_path):
    base=tmp_path/'archive'; day='2026/11/12'; (base/day/'00').mkdir(parents=True); (base/day).mkdir(parents=True,exist_ok=True)
    flat=base/day/'kr.jsonl'; hour=base/day/'00/kr.jsonl'
    tick={'symbol':'000660','ts':'2026-11-12T00:00:01+00:00','price':100}
    flat.write_text(json.dumps(tick)+'\nnot-json\n'); hour.write_text(json.dumps(tick)+'\n'+json.dumps({**tick,'ts':'2026-11-12T00:00:50+00:00','price':102})+'\n')
    stats=convert_date(pd.Timestamp('2026-11-12').date(),[base],tmp_path)
    assert stats['ticks_read']==3 and stats['bars']==1 and stats['malformed']==1
    result=pd.read_parquet(next((tmp_path/'data/minute/kr/1m').rglob('*.parquet')))
    assert result.close.iloc[0]==102 and result.volume.iloc[0]==0

def test_manifest_check_accepts_kr_1530(tmp_path,monkeypatch):
    import collect.manifest_check as checker
    frame=pd.DataFrame([_row('A','2026-01-02 06:30Z')]) # 15:30 KST
    merge_write(frame,'kr','1m',tmp_path)
    monkeypatch.setattr(checker,'check_disk',lambda p: None)
    errors,warnings=checker.inspect(tmp_path)
    assert errors==[]
    assert not any('out of exchange session' in item for item in warnings)

def test_check_disk_cap(tmp_path,monkeypatch):
    import collect.common as common
    (tmp_path/'big').write_bytes(b'x')
    monkeypatch.setattr(common,'check_disk',lambda p: (_ for _ in ()).throw(Abort('cap')))
    with pytest.raises(Abort): common.check_disk(tmp_path)

def test_manifest_check_duplicate_exit(tmp_path,monkeypatch):
    frame=pd.DataFrame([_row('A','2026-01-02 14:30Z')]*2)
    merge_write(frame,'us','1m',tmp_path)
    path=next((tmp_path/'data/minute/us/1m').rglob('*.parquet'))
    duplicated=pd.concat([pd.read_parquet(path)]*2,ignore_index=True); duplicated.to_parquet(path,index=False)
    from collect.manifest_check import inspect
    errors,_=inspect(tmp_path); assert any('duplicate' in e for e in errors)
