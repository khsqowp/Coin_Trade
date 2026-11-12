from types import SimpleNamespace
import json
from types import SimpleNamespace as NS
import numpy as np
import pandas as pd
from app import aw_run


def test_run_smoke_writes_json_for_synthetic_panel(tmp_path, monkeypatch):
    n=280; dates=pd.date_range('2018-01-01',periods=n)
    symbols=['069500','091160','153130','261240','A','B']
    rng=np.random.default_rng(2)
    close=pd.DataFrame({s:100*np.exp(np.cumsum(rng.normal(.0002,.006,n))) for s in symbols},index=dates)
    roles={'069500':'index','091160':'sector','153130':'defensive','261240':'defensive','A':'stock','B':'stock'}
    names={'069500':'index','091160':'sector','153130':'KODEX 단기채권','261240':'macro','A':'A','B':'B'}
    panel=SimpleNamespace(market='KR',dates=dates,symbols=symbols,roles=roles,names=names,
      c=close,o=close.copy(),v=close*100000,tradable=close.notna(),stock_eligible=pd.DataFrame(True,index=dates,columns=['A','B']),missing=[])
    monkeypatch.setattr(aw_run,'load_panel',lambda market:panel)
    monkeypatch.setattr(aw_run,'itertools',NS(product=lambda *args: iter([(3,60,0.,False,False)])))
    out=tmp_path/'aw.json'
    aw_run.run('KR',str(out))
    report=json.loads(out.read_text())
    assert report['config_count']==1
    sample=next(iter(report['grid'].values()))
    assert set(sample['window_metrics'])=={'A','B'}
    assert 'sharpe' in sample['window_metrics']['A']['strategy']
    assert 'daily_turnover' not in sample and 'sleeve_contribution' not in sample
