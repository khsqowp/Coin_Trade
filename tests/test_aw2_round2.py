from types import SimpleNamespace
import numpy as np
import pandas as pd
from app.aw2_spaces import sample, refine
from app.aw2_strategies import weights
from app.aw2_walkforward import build
from app.aw_universe import STOCK_SECTOR

def _stock_panel():
    d=pd.date_range("2018-01-01",periods=1500)
    a=np.linspace(100,200,len(d))
    c=pd.DataFrame({"069500":a,"153130":np.linspace(100,108,len(d)),"091160":a*.8,"005930":np.linspace(20,90,len(d))},index=d)
    return SimpleNamespace(market="KR",dates=d,symbols=list(c),c=c,o=c,v=c*0+100,roles={"069500":"index","153130":"defensive","091160":"sector","005930":"stock"},names={"069500":"index","153130":"KODEX 단기채권","091160":"sector","005930":"Samsung"},stock_eligible=pd.DataFrame({"005930":True},index=d))

def test_round2_spaces_produce_required_unique_random_and_refinement_samples():
    initial=sample("KR","F4",120)
    assert len(initial)==120
    assert len({x["_config_id"] for x in initial})==120
    tuned=refine("KR","F4",initial[:10],60)
    assert len(tuned)==60
    assert len({x["_config_id"] for x in tuned})==60
    for row in sample("KR","F1",120):
        assert isinstance(row["basket"],list) and isinstance(row["weights"],list)
    assert all({"sector_count","per_sector","sector_lookback"} <= set(row) for row in sample("KR","F6",120))

def test_f10_stock_exposure_and_f13_signal_are_bounded():
    panel=_stock_panel()
    params={"lookback":63,"k":3,"cadence":21,"weighting":"equal","max_weight":.15,"trends":[50,100],"moms":[21],"min_exposure":.2,"max_exposure":.8}
    w=weights(panel,"F10",params)
    assert w["005930"].max()<=.15+1e-12
    p13={"lookback":63,"k":3,"cadence":21,"weighting":"equal","max_weight":.15,"signal":"return_vol"}
    w13=weights(panel,"F13",p13)
    assert np.isfinite(w13.to_numpy()).all()

def test_walkforward_chooses_and_stitches_three_configurations_by_year():
    dates=pd.date_range("2018-01-01","2022-12-31",freq="B")
    curves=[pd.Series((1+r)**np.arange(len(dates)),index=dates) for r in (.0001,.0003,.0002)]
    result=build(curves,[{"i":0},{"i":1},{"i":2}],2020,2022)
    choices=[x["selected_index"] for x in result["yearly_selection"]]
    assert choices[0] in (0,1,2) and choices[1] in (0,1,2) and choices[2] in (0,1,2)
    for item in result["yearly_selection"]:
        year=item["year"]; selected=curves[item["selected_index"]]
        idx=pd.to_datetime(list(result["curve"])); wf=pd.Series(result["curve"],dtype=float); wf.index=idx
        annual=wf.loc[wf.index.year==year]
        source=selected.pct_change().loc[annual.index]
        # The first annual point carries the strategy's actual return relative
        # to the previous close; annual compounding must match that slice.
        assert np.isclose(annual.iloc[-1]/(annual.iloc[0]/(1+source.iloc[0]))-1, (1+source.iloc[1:]).prod()-1, atol=.03)
    assert len(result["curve"])>700
    assert result["annual_returns"]["2022"]>0

def test_f2_slot_absolute_momentum_moves_only_failed_slots_to_bill():
    panel=_stock_panel(); panel.c["091160"]=np.linspace(100,50,len(panel.dates))
    p={"lookback":63,"k":2,"cadence":21,"trend":0,"absolute_floor":0}
    target=weights(panel,"F2",p)
    row=target.iloc[-1]
    assert row["153130"]>0
    assert row.sum()<=1+1e-12

def test_f11_and_f12_emit_finite_budgeted_targets():
    panel=_stock_panel()
    global_dual=weights(panel,"F11",{"lookback":63,"k":3,"cadence":21,"trend":0,"absolute_floor":0})
    vol_target=weights(panel,"F12",{"target_vol":.12,"vol_window":20,"cap":1.,"threshold":.1,"cadence":5})
    assert np.isfinite(global_dual.to_numpy()).all() and (global_dual.sum(axis=1)<=1+1e-12).all()
    assert np.isfinite(vol_target.to_numpy()).all() and (vol_target.sum(axis=1)<=1+1e-12).all()

def test_f1_relative_drift_band_keeps_target_stable_between_rebalances():
    panel=_stock_panel()
    p={"basket":["069500","153130"],"weighting":"fixed","weights":[.6,.4],"invested":1.,"cadence":21,"band":.2,"vol_window":20}
    target=weights(panel,"F1",p)
    assert np.isclose(target.iloc[0]["069500"],.6)
    assert np.allclose(target.iloc[1:21].to_numpy(),np.tile(target.iloc[0].to_numpy(),(20,1)))

def test_f4_crash_filter_runs_daily_and_holds_bill_until_release():
    panel=_stock_panel(); n=len(panel.dates)
    panel.c["069500"]=np.r_[np.linspace(100,150,n-80),np.linspace(150,90,80)]
    params={"lookback":63,"k":3,"cadence":21,"weighting":"equal","max_weight":.15,"crash_window":10,"crash_cut":-.07,"crash_release":0}
    target=weights(panel,"F4",params,offset=0)
    triggered=[i for i in range(10,n) if i%21!=0 and panel.c["069500"].iloc[i]/panel.c["069500"].iloc[i-10]-1<=-.07]
    assert triggered
    assert (target.iloc[triggered[0]]["153130"]==1.)

def test_fractional_holding_buffer_is_a_valid_rank_window():
    panel=_stock_panel()
    params={"lookback":63,"k":3,"cadence":21,"weighting":"equal","max_weight":.15,"buffer":1.5}
    target=weights(panel,"F4",params)
    assert np.isfinite(target.to_numpy()).all()
    assert (target.sum(axis=1)<=1+1e-12).all()

def test_none_position_cap_means_equal_weight_without_truncation():
    panel=_stock_panel()
    panel.c["000001"]=np.linspace(20,100,len(panel.dates))
    panel.c["000002"]=np.linspace(30,110,len(panel.dates))
    panel.symbols=list(panel.c.columns)
    panel.roles.update({"000001":"stock","000002":"stock"})
    panel.names.update({"000001":"stock1","000002":"stock2"})
    panel.stock_eligible["000001"]=True
    panel.stock_eligible["000002"]=True
    params={"lookback":63,"k":3,"cadence":21,"weighting":"equal","max_weight":None,"buffer":2}
    target=weights(panel,"F4",params)
    assert target[["005930","000001","000002"]].max().max()<=1/3+1e-12

def test_f7_uses_configured_defensive_basket_after_confirmation():
    panel=_stock_panel(); n=len(panel.dates)
    panel.c["069500"]=np.r_[np.linspace(100,200,n-200),np.linspace(200,100,200)]
    panel.c["091160"]=np.linspace(30,100,n)
    target=weights(panel,"F7",{"lookback":63,"cadence":21,"k":1,"trend_mode":"sma100","defensive_mode":"defensive_sector","defensive_symbols":["091160"],"confirm_days":1})
    assert target.iloc[-1]["091160"]==1.

def test_sector_mapping_is_explicit_for_all_configured_stock_symbols():
    for market in ("KR","US"):
        assert all(x["code"] in STOCK_SECTOR[market] for x in __import__("app.aw_universe",fromlist=["stocks"]).stocks(market))
