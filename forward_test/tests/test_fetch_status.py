import sqlite3
import pandas as pd
from forward_test.fetch import fetch, gaps
from forward_test.engine import Engine
from forward_test.status import status_data

class Response:
    status_code=200
    def __init__(self,data): self.data=data
    def raise_for_status(self): pass
    def json(self): return self.data
class Session:
    def __init__(self): self.calls=[]
    def get(self,url,params,timeout):
        self.calls.append(params['startTime']); a=params['startTime']; step=14_400_000
        return Response([[a+i*step,1,2,.5,1.5,4,a+i*step+step-1,0,0,0,0,0] for i in range(min(1000,(params['endTime']-a)//step+1))])

def test_fetch_pagination_and_closed_filter():
    s=Session(); frame=fetch('BTCUSDT',0,session=s,now_ms=1001*14_400_000+1,sleep=0)
    assert len(s.calls)==2 and len(frame)==1001
    assert frame.index.is_monotonic_increasing

def test_fetch_retries_rate_limit(monkeypatch):
    import forward_test.fetch as mod
    monkeypatch.setattr(mod.time,'sleep',lambda _:None)
    class RetrySession(Session):
        def __init__(self): super().__init__(); self.first=True
        def get(self,url,params,timeout):
            if self.first:
                self.first=False
                return type('RateLimited',(),{'status_code':429,'headers':{'Retry-After':'0'}})()
            return super().get(url,params,timeout)
    s=RetrySession(); frame=fetch('BTCUSDT',0,session=s,now_ms=14_400_001,sleep=0)
    assert len(frame)==1 and not s.first

def test_gap_detection():
    idx=pd.to_datetime([0,28_800_000],unit='ms',utc=True)
    f=pd.DataFrame({'open':[1,1],'high':[1,1],'low':[1,1],'close':[1,1],'volume':[1,1]},index=idx)
    assert gaps(f)==[(14_400_000,28_800_000)]

def test_empty_populated_status_and_stale(tmp_path):
    e=Engine(tmp_path/'empty.db'); data=status_data(e.db)
    assert data['health']=='STALE' and data['progress']['verdict']=='INSUFFICIENT DATA'
    e.db.execute("INSERT INTO meta VALUES('forward_start_ts','0')")
    e.db.execute('UPDATE heartbeat SET last_run=0,bars_processed=4,last_candle=14400000');e.db.commit()
    data=status_data(e.db); assert data['bars_processed']==4 and data['health']=='STALE'
