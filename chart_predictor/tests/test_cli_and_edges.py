import json
import sys
import numpy as np
import pandas as pd
import pytest
from chart_predictor import cli, collector, resample, universe
from chart_predictor.collector import connect


class JsonResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload, self.status_code = payload, status
        self.headers = headers or {}
    def json(self): return self.payload
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError("http status")


class HttpMock:
    def __init__(self, responses): self.responses, self.urls = list(responses), []
    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


def sample_frame(n=80):
    base = 1_700_000_040_000 // 60_000 * 60_000
    x = np.arange(n, dtype=float); close = 100 + np.sin(x/4)*3 + x*.1
    return pd.DataFrame({"t_open_ms":base+x.astype(int)*60_000,"o":close-.2,"h":close+1,
        "l":close-1,"c":close,"v":x+1,"quote_v":(x+1)*close,"trades":x.astype(int)+1})


def _cli(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["chart_predictor.cli", *args])
    from chart_predictor.cli import main
    main()


def test_universe_fetch_uses_public_payload_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(universe, "DATA_DIR", tmp_path)
    info={"symbols":[{"symbol":"BTCUSDT","contractType":"PERPETUAL","quoteAsset":"USDT",
        "status":"TRADING","underlyingType":"COIN"}]}
    session=HttpMock([JsonResponse(info),JsonResponse([{"symbol":"BTCUSDT","quoteVolume":"12"}])])
    assert universe.fetch_universe(1,session)==[{"symbol":"BTCUSDT","quoteVolume":12.0}]
    saved=list(tmp_path.glob("universe_*.json"))
    assert len(saved)==1 and json.loads(saved[0].read_text())["symbols"][0]["symbol"]=="BTCUSDT"
    assert len(session.urls)==2


def test_cli_universe_collect_and_update_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(cli,"fetch_universe",lambda top:[{"symbol":"BTCUSDT","top":top}])
    _cli(monkeypatch,["universe","--top","7"])
    assert json.loads(capsys.readouterr().out)[0]["top"]==7
    calls=[]
    monkeypatch.setattr(cli,"collect_symbols",lambda symbols,days:calls.append((symbols,days)) or {symbols[0]:2})
    _cli(monkeypatch,["collect","--symbol","ETHUSDT","--days","4"])
    assert json.loads(capsys.readouterr().out)=={"ETHUSDT":2}
    _cli(monkeypatch,["update","--symbol","BTCUSDT","--days","9"])
    assert calls==[(["ETHUSDT"],4),(["BTCUSDT"],1)]


def test_cli_features_1m_and_resampled_paths(monkeypatch, tmp_path, capsys):
    path=tmp_path/"cli.sqlite"; db=connect(path); frame=sample_frame()
    frame.insert(0,"symbol","BTCUSDT")
    frame.to_sql("candles",db,if_exists="append",index=False); db.close()
    monkeypatch.setattr(cli,"connect",lambda:connect(path))
    anchor=pd.to_datetime(int(frame.t_open_ms.iloc[30])+59_999,unit="ms",utc=True).isoformat()
    _cli(monkeypatch,["features","--symbol","BTCUSDT","--tf","1m","--anchor",anchor])
    result=json.loads(capsys.readouterr().out)
    assert result["anchor_time"]==anchor
    _cli(monkeypatch,["features","--symbol","BTCUSDT","--tf","5m"])
    assert json.loads(capsys.readouterr().out)["timeframe"]=="5m"


def test_universe_empty_and_resample_error_empty_and_sqlite_loader(tmp_path):
    assert universe.select_universe({},[],100)==[]
    with pytest.raises(ValueError): resample.resample_frame(pd.DataFrame(),"2m")
    empty=pd.DataFrame(columns=["t_open_ms","o","h","l","c","v","quote_v","trades"])
    assert resample.resample_frame(empty,"5m").empty
    db=connect(tmp_path/"empty.sqlite")
    assert resample.load_resampled(db,"BTCUSDT","5m").empty
    db.close()


def test_collector_owned_connection_nonadvancing_page_and_collect_symbols(tmp_path, monkeypatch):
    path=tmp_path/"owned.sqlite"; monkeypatch.setattr(collector,"connect",lambda:connect(path))
    open_ms=1_700_000_000_000//60_000*60_000; close_ms=open_ms+59_999
    row=[open_ms,"1","2",".5","1.5","4",close_ms,"6",7,"0","0","0"]
    session=HttpMock([JsonResponse([row])])
    count=collector.collect_symbol("BTCUSDT",open_ms,open_ms+60_000,session=session,sleep=lambda _:None)
    assert count==1
    db=connect(path)
    assert db.execute("SELECT COUNT(*) FROM candles").fetchone()[0]==1
    db.close()
    monkeypatch.setattr(collector,"collect_symbol",lambda symbol,start,end,**kw: symbol)
    assert collector.collect_symbols(["A","B"],days=2)=={"A":"A","B":"B"}


def test_collector_rate_limit_exhaustion_and_high_weight_pause():
    class Limited:
        def get(self,*args,**kwargs): return JsonResponse([],429,{"Retry-After":"2"})
    sleeps=[]
    with pytest.raises(RuntimeError,match="retries exhausted"):
        collector._request(Limited(),{},sleeps.append,retries=1)
    assert sleeps==[2.0]
    class Heavy:
        def get(self,*args,**kwargs): return JsonResponse([] ,headers={"X-MBX-USED-WEIGHT-1M":"1100"})
    sleeps=[]; collector._request(Heavy(),{},sleeps.append)
    assert sleeps==[60]


def test_features_reject_empty_and_missing_columns():
    from chart_predictor.features import build_features
    with pytest.raises(ValueError,match="at least one"):
        build_features(pd.DataFrame(),"1m")
    with pytest.raises(ValueError,match="missing candle columns"):
        build_features(pd.DataFrame({"t_open_ms":[0]}),"1m")
