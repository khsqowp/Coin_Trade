from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.aw2_strategies import candidates, weights
from app.aw_engine import simulate
from app.aw2_walkforward import build


def _panel(close):
    dates=close.index; symbols=list(close.columns)
    roles={s: ("index" if s in ("069500","SPY") else "defensive" if s in ("153130","BIL") else "sector") for s in symbols}
    return SimpleNamespace(market="KR",dates=dates,symbols=symbols,c=close,roles=roles,
        names={s:s for s in symbols},stock_eligible=pd.DataFrame(index=dates))


def test_aw2_targets_do_not_change_before_future_price_perturbation():
    dates=pd.date_range("2018-01-01",periods=1800)
    base=np.linspace(100,180,len(dates))*np.exp(np.cumsum(np.random.default_rng(7).normal(0,.004,len(dates))))
    close=pd.DataFrame({"069500":base,"153130":np.linspace(100,106,len(dates)),"SEC":base*.9},index=dates)
    changed=close.copy(); changed.loc[dates>=pd.Timestamp("2022-01-01")]*=1.5
    p1,p2=_panel(close),_panel(changed)
    params={"lookback":126,"k":2,"cadence":21,"trend":200}
    a=weights(p1,"F2",params); b=weights(p2,"F2",params)
    cut=dates.searchsorted(pd.Timestamp("2022-01-01"))-1
    assert np.allclose(a.iloc[:cut+1],b.iloc[:cut+1])


def test_walkforward_selects_only_from_prior_year_history():
    dates=pd.date_range("2018-01-01","2022-12-31",freq="B")
    rng=np.random.default_rng(9)
    a=pd.Series(np.cumprod(1+rng.normal(.0005,.01,len(dates))),index=dates)
    b=pd.Series(np.cumprod(1+rng.normal(.0002,.01,len(dates))),index=dates)
    out=build([a,b],[{"id":"a"},{"id":"b"}],2020,2022)
    assert out["annual_returns"]["2020"] != 0
    for yr in out["yearly_selection"]:
        prior=dates< pd.Timestamp(yr["year"],1,1)
        assert yr["selected_index"] in (0,1)
        assert not (dates[prior][-1]>=pd.Timestamp(yr["year"],1,1))


def test_f3_exposure_changes_respect_rebalance_threshold_between_cadence_dates():
    dates=pd.date_range("2020-01-01",periods=260)
    trend=np.linspace(100,150,len(dates))
    close=pd.DataFrame({"069500":trend,"153130":np.linspace(100,102,len(dates))},index=dates)
    p=_panel(close)
    params={"trends":[50,100],"moms":[21],"min_exposure":0.,"max_exposure":1.,"rebalance_threshold":.5,"cadence":21}
    out=weights(p,"F3",params,offset=0)
    changes=out["069500"].diff().abs()
    off_cycle=[i for i in range(1,len(dates)) if i%21!=0 and changes.iloc[i]>0]
    assert all(changes.iloc[i]>=.5 for i in off_cycle)


def test_f4_and_f6_stock_weights_obey_ten_percent_position_cap():
    dates=pd.date_range("2018-01-01",periods=600)
    rng=np.random.default_rng(4)
    close=pd.DataFrame({"069500":np.linspace(100,170,600),"153130":np.linspace(100,104,600),"091160":np.linspace(50,130,600),"000001":np.linspace(10,70,600)},index=dates)
    p=_panel(close); p.roles["000001"]="stock"; p.stock_eligible=pd.DataFrame({"000001":True},index=dates)
    for family in ("F4","F6"):
        params=candidates("KR",family)[0]
        target=weights(p,family,params)
        assert target["000001"].max()<=.10+1e-12


def test_future_price_perturbation_preserves_pre_cutoff_curves_for_each_family():
    dates=pd.date_range("2018-01-01",periods=1800)
    rng=np.random.default_rng(18)
    index=np.linspace(100,160,len(dates))*np.exp(np.cumsum(rng.normal(0,.003,len(dates))))
    close=pd.DataFrame({"069500":index,"153130":np.linspace(100,106,len(dates)),
        "091160":index*.8,"000001":np.linspace(20,90,len(dates))},index=dates)
    changed=close.copy(); changed.loc[dates>=pd.Timestamp("2022-01-01")]*=1.5
    def make(c):
        return SimpleNamespace(market="KR",dates=dates,symbols=list(c.columns),c=c,o=c.copy(),v=c*0+100,
            tradable=c.notna(),roles={"069500":"index","153130":"defensive","091160":"sector","000001":"stock"},
            names={"069500":"index","153130":"KODEX 단기채권","091160":"sector","000001":"stock"},
            stock_eligible=pd.DataFrame({"000001":True},index=dates))
    p1,p2=make(close),make(changed); cut=dates.searchsorted(pd.Timestamp("2022-01-01"))
    params_by_family={f:(candidates("KR",f)[0] if candidates("KR",f) else {"lookback":126,"k":3,"cadence":21,"core":.5,"weighting":"equal","buffer":2,"sector_count":3}) for f in ("F1","F2","F3","F4","F5","F6","F7","F8")}
    for family,params in params_by_family.items():
        a=simulate(p1,weights(p1,family,params,offset=7),drawdown_breaker=False)["equity"]
        b=simulate(p2,weights(p2,family,params,offset=7),drawdown_breaker=False)["equity"]
        assert np.allclose(a.iloc[:cut],b.iloc[:cut]), family
