import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import gulp


def synthetic(n=90, seed=7):
    rng=np.random.default_rng(seed)
    dates=pd.bdate_range("2019-01-01",periods=n)
    close=np.full(n,100000.0)
    close += rng.normal(0,80,n)
    op=close.copy(); high=close+300; low=close-300; volume=np.full(n,20000.0)
    # Sideways 15-bar window, high-volume shakeout at t, then green confirmation.
    t=45
    close[t-15:t]=100000; op[t-15:t]=100000; high[t-15:t]=100200; low[t-15:t]=99800
    close[t-1]=100000; close[t]=90000; op[t]=99000; low[t]=89000; high[t]=100000; volume[t]=100000
    op[t+1]=91000; close[t+1]=94000; high[t+1]=95000; low[t+1]=90500; volume[t+1]=30000
    # Set a clear future path for exit tests.
    op[t+2]=94000; close[t+2]=96000; high[t+2]=97000; low[t+2]=93000
    return pd.DataFrame({"open":op,"high":high,"low":low,"close":close,"volume":volume},index=dates),t


def multi_year_synthetic():
    pieces=[synthetic(seed=i)[0].reset_index(drop=True) for i in range(12)]
    df=pd.concat(pieces,ignore_index=True)
    df.index=pd.bdate_range("2018-01-02",periods=len(df))
    df["rawclose"]=df["close"]
    return df


def test_signal_and_no_lookahead():
    df,t=synthetic()
    cand=gulp._signal_frame(df,"kr",15,.10,.05,2)
    assert any(i==t and green for i,green,_ in cand)
    truncated=gulp._signal_frame(df.iloc[:t+2],"kr",15,.10,.05,2)
    assert [(i,g) for i,g,_ in cand if i==t] == [(i,g) for i,g,_ in truncated if i==t]


@pytest.mark.parametrize("unit", ["us", "s"])
def test_date_unit_normalization_preserves_signals_and_gap_rule(unit):
    df,t=synthetic()
    expected=gulp._signal_frame(df,"kr",15,.10,.05,2)
    coarse=df.copy()
    coarse.index=coarse.index.as_unit(unit)
    normalized=gulp._dates(coarse)
    assert normalized.index.as_unit("ns").equals(df.index)
    assert gulp._signal_frame(normalized,"kr",15,.10,.05,2)==expected
    combo=(15,.10,.05,2,"E1","X1_3")
    assert gulp._collect(normalized,"kr",combo,.0041)==gulp._collect(gulp._dates(df),"kr",combo,.0041)

    # A ten-calendar-day hole inside the lookback invalidates the signal.
    gap=normalized.copy()
    gap.index=gap.index.where(np.arange(len(gap))<t-5, gap.index + pd.Timedelta(days=10))
    gap.index=gap.index.as_unit(unit)
    gap=gulp._dates(gap)
    assert not any(i==t for i,_,_ in gulp._signal_frame(gap,"kr",15,.10,.05,2))


def test_entries_exits_and_costs():
    df,t=synthetic()
    e1=gulp._trade(df,t,"E1","X1_3","kr",.0041)
    e2=gulp._trade(df,t,"E2","X1_3","kr",.0041)
    assert e1["entry"]==df.close.iloc[t+1]
    assert e2["entry"]==df.open.iloc[t+2]
    assert abs(e1["net"]-(e1["gross"]-.0041))<1e-12
    # X2 target is the pre-drop close; later bar simultaneously crosses target and closes below stop.
    altered=df.copy(); altered.loc[altered.index[t+2],"high"]=101000; altered.loc[altered.index[t+2],"close"]=88000
    x2=gulp._trade(altered,t,"E2","X2","kr",.0041)
    assert x2["x"]==t+2 and x2["exit"]==88000


def test_limit_down_exclusion_and_slot_cap():
    df,t=synthetic(); df.loc[df.index[t],"close"]=70000
    assert not any(i==t for i,_,_ in gulp._signal_frame(df,"kr",15,.15,.05,2))
    clean,_=synthetic(); trades=[]
    for i in range(12):
        tr={"e":20,"x":30,"entry":clean.close.iloc[20],"volume_ratio":float(i),"net":0.01,"hold":10}
        trades.append(tr)
    accepted,_=gulp._portfolio(clean,trades,.0041)
    assert len(accepted)<=10


def test_cluster_bootstrap_and_year_summary():
    trades=[{"entry_date":"2020-01-03","net":.02,"hold":3},{"entry_date":"2020-01-10","net":-.01,"hold":2},{"entry_date":"2020-02-03","net":.03,"hold":5}]
    a=gulp._boot(trades,200,np.random.default_rng(1))
    b=gulp._cluster_diff(trades,[{"entry_date":"2020-01-08","net":0.}],200,np.random.default_rng(2))
    assert len(a["ci95"])==2 and a["p_two_sided"]>=1/200
    assert b["difference"] is not None and len(b["ci95"])==2
    y=gulp._per_year(trades,.0041)
    assert y["2020"]["trades"]==3 and y["2020"]["mean_net_trade_return"]==pytest.approx(.0133333333)


def test_us_index_prefers_adjusted_close(tmp_path):
    (tmp_path/"idx").mkdir()
    ix=pd.bdate_range("2019-01-01",periods=30)
    for name in ("SPY","QQQ"):
        pd.DataFrame({"Close":np.full(30,100.),"Adj Close":np.linspace(50,100,30)},index=ix).to_parquet(tmp_path/"idx"/f"{name}.parquet")
    result=gulp._index_metrics(tmp_path,"us")
    assert result["SPY"]["ALL"]["cagr"]>0
    assert result["SPY"]["OOS"]["cagr"] is None


def test_us_liquidity_uses_rawclose_and_random_candidates_are_year_scoped():
    df,t=synthetic()
    df["rawclose"]=df.close
    df["rawclose"]*=0.02
    assert any(i==t for i,_,_ in gulp._signal_frame(df,"us",15,.10,.05,2))
    df["rawclose"]*=0.0001
    assert not any(i==t for i,_,_ in gulp._signal_frame(df,"us",15,.10,.05,2))
    picks=gulp._random_candidates(df,"SYN",15,"us",2019)
    assert np.all(df.index[picks].year==2019)


def test_boot_empty_and_nonfinite_report_sanitizer(tmp_path):
    assert gulp._boot([],100,np.random.default_rng(1))=={"ci95":[None,None],"p_two_sided":None}
    # End-to-end writer rejects NaN after the report sanitation pass.
    cache=tmp_path/"cache"; out=tmp_path/"out"; (cache/"kr").mkdir(parents=True); (cache/"idx").mkdir()
    df,_=synthetic(); df.to_parquet(cache/"kr"/"00000.parquet")
    pd.DataFrame([{"Code":"00000","Name":"S0","Market":"KOSPI"}]).to_csv(cache/"kr_universe.csv",index=False)
    gulp.run("kr",cache,out,draws=2,boot=10,limit_names=1)
    json.loads((out/"results_kr.json").read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def test_end_to_end(tmp_path):
    cache=tmp_path/"cache"; out=tmp_path/"out"; (cache/"kr").mkdir(parents=True); (cache/"idx").mkdir()
    rows=[]
    for i in range(30):
        df,_=synthetic(seed=i)
        code=f"{i:05d}0"; df.to_parquet(cache/"kr"/f"{code}.parquet")
        rows.append({"Code":code,"Name":f"S{i}","Market":"KOSPI"})
    pd.DataFrame(rows).to_csv(cache/"kr_universe.csv",index=False)
    idx=pd.DataFrame({"Close":np.linspace(100,150,90)},index=pd.bdate_range("2019-01-01",periods=90))
    idx.to_parquet(cache/"idx"/"KOSPI.parquet"); idx.to_parquet(cache/"idx"/"KOSDAQ.parquet")
    gulp.run("kr",cache,out,draws=50,boot=200,limit_names=30)
    data=json.loads((out/"results_kr.json").read_text())
    assert len(data["combos"])==128
    assert len([x for x in data["combos"] if x["combo"]["M"]==2 and "volume_ablation_m0" in x])==64
    row=data["combos"][0]
    assert set(row["portfolio"])=={"ALL","IS","OOS","ALL_2x","IS_2x","OOS_2x"}
    assert set(row["random_entry_baseline"])=={"ALL","IS","OOS"}
    assert "confirmed_vs_failed_cluster_bootstrap" in row["confirmation_ablation"]
    assert "bonferroni_x256_all" in row and "per_year_all" in row
    assert set(data["index_buy_hold"])=={"KOSPI","KOSDAQ"}
    assert data["index_buy_hold"]["KOSPI"]["ALL"]["cagr"] is not None
    assert "signals_by_N_R_D_M" in data["metadata"]
    assert (out/"combos_kr.csv").exists()


@pytest.mark.parametrize("market,unit", [("kr","us"),("us","s")])
def test_multiyear_coarse_cache_has_oos_trades_and_random_baseline(tmp_path,market,unit):
    cache=tmp_path/"cache"; out=tmp_path/"out"
    (cache/market).mkdir(parents=True); (cache/"idx").mkdir()
    code="000000" if market=="kr" else "SYN"
    df=multi_year_synthetic(); df.index=df.index.as_unit(unit)
    df.to_parquet(cache/market/f"{code}.parquet")
    if market=="kr":
        pd.DataFrame([{"Code":code,"Name":"SYN","Market":"KOSPI"}]).to_csv(cache/"kr_universe.csv",index=False)
        idx_names=("KOSPI","KOSDAQ")
    else:
        pd.DataFrame([{"symbol":code}]).to_csv(cache/"us_universe.csv",index=False)
        idx_names=("SPY","QQQ")
    idx=pd.DataFrame({"Close":np.linspace(100,150,len(df)),"Adj Close":np.linspace(100,150,len(df))},index=df.index)
    for name in idx_names: idx.to_parquet(cache/"idx"/f"{name}.parquet")
    gulp.run(market,cache,out,draws=2,boot=10,limit_names=1)
    result=json.loads((out/f"results_{market}.json").read_text())
    combo=next(row for row in result["combos"] if row["combo"]=={"N":15,"R":0.1,"D":0.05,"M":2,"entry":"E1","exit":"X1_3"})
    assert combo["portfolio"]["OOS"]["trades"]>0
    assert combo["random_entry_baseline"]["OOS"]["n"]>0
