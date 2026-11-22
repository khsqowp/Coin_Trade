from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app import aw_engine as E
from app import aw_regime as R


def test_cost_tax_differs_for_kr_stock_and_etf():
    assert E.cost_rates("KR", "index") == (.00065, .00065)
    assert E.cost_rates("KR", "stock") == (.00065, .00245)


def test_simulated_kr_stock_sell_cost_includes_tax_but_etf_does_not():
    dates = pd.date_range("2024-01-01", periods=3)
    def panel(role):
        px = pd.DataFrame({"X": [100., 100., 100.]}, index=dates)
        return SimpleNamespace(market="KR", dates=dates, symbols=["X"], c=px, o=px.copy(),
            v=px * 0 + 100, tradable=px.notna(), roles={"X": role})
    target = pd.DataFrame({"X": [1., 0., 0.]}, index=dates)
    stock = E.simulate(panel("stock"), target, drawdown_breaker=False)
    etf = E.simulate(panel("index"), target, drawdown_breaker=False)
    assert stock["costs"].sum() == pytest.approx(.00065 + .00245)
    assert etf["costs"].sum() == pytest.approx(.00065 + .00065)


def test_role_weight_caps():
    assert [E.cap_weight(r) for r in ("stock", "sector", "index", "defensive", "inverse")] == [.1, .2, .5, .5, .25]


def test_mean_reversion_entry_exit_rules():
    # 200일 상승 추세 중 급락은 진입, 5일선 회복 또는 손절/시간만료는 청산.
    close = pd.Series(np.r_[np.repeat(100., 200), [120., 110., 105.]])
    assert E.mean_reversion_entry(close, len(close) - 1)
    assert E.mean_reversion_exit(pd.Series([100., 101., 102., 103., 104.]), 100, 1, 4)
    assert E.mean_reversion_exit(pd.Series([100.] * 12), 100, 10, 11)
    assert E.mean_reversion_exit(pd.Series([100., 92.]), 100, 1, 1)


def test_inverse_requires_below_sma200_and_negative_20d_return():
    falling = pd.Series(np.r_[np.linspace(100, 150, 200), np.linspace(149, 100, 21)])
    assert E.inverse_hold_condition(falling, len(falling) - 1)
    rising = pd.Series(np.r_[np.linspace(100, 150, 200), np.linspace(149, 160, 21)])
    assert not E.inverse_hold_condition(rising, len(rising) - 1)


def test_no_lookahead_future_price_perturbation():
    dates = pd.date_range("2020-01-01", periods=420)
    syms = ["069500", "091160", "153130", "114800", "261240"]
    rng = np.random.default_rng(21)
    base = np.linspace(100, 140, len(dates)) * np.exp(np.cumsum(rng.normal(0, .006, len(dates))))
    raw = np.column_stack([base, base * 1.1, np.linspace(100, 103, len(dates)),
                           np.linspace(100, 90, len(dates)), np.linspace(100, 110, len(dates))])
    def panel(c):
        close = pd.DataFrame(c, index=dates, columns=syms)
        return SimpleNamespace(market="KR", dates=dates, symbols=syms,
            roles={"069500": "index", "091160": "sector", "153130": "defensive", "114800": "inverse", "261240": "defensive"},
            names={"069500": "index", "091160": "sector", "153130": "KODEX 단기채권", "114800": "inverse", "261240": "fx"},
            c=close, o=close.copy(), v=pd.DataFrame(10000, index=dates, columns=syms),
            tradable=pd.DataFrame(True, index=dates, columns=syms),
            stock_eligible=pd.DataFrame(index=dates))
    p1 = panel(raw.copy())
    changed = raw.copy(); changed[300:] *= 1.5
    p2 = panel(changed)
    curves = []
    for p in (p1, p2):
        score = R.classify(p.c, "KR", "069500", ["091160"], "261240", 3)
        target = E.target_weights(p, score.regime, 60, .25, True, False, offset=0)
        curves.append(E.simulate(p, target, regimes=score.regime)["equity"])
    assert np.allclose(curves[0].iloc[:300], curves[1].iloc[:300])


def test_ret120_vectorization_and_lookback_weights():
    dates = pd.date_range('2020-01-01', periods=240)
    syms=['069500','AAA']
    c=pd.DataFrame({'069500':np.linspace(100,120,240),'AAA':np.r_[np.ones(180)*100,np.linspace(100,180,60)]},index=dates)
    p=SimpleNamespace(market='KR',dates=dates,symbols=syms,c=c,o=c,v=c*0+10,tradable=c.notna(),
      roles={'069500':'index','AAA':'stock'},names={'069500':'index','AAA':'stock'},stock_eligible=pd.DataFrame({'AAA':True},index=dates))
    a=E.target_weights(p,pd.Series('BULL',index=dates),60)
    b=E.target_weights(p,pd.Series('BULL',index=dates),120)
    assert a.AAA.iloc[-1] == .1 and b.AAA.iloc[-1] == .1


def test_simulate_returns_regime_weights_and_role_contributions():
    dates=pd.date_range('2024-01-01',periods=3); px=pd.DataFrame({'X':[100.,110.,121.]},index=dates)
    p=SimpleNamespace(market='KR',dates=dates,symbols=['X'],c=px,o=px.copy(),v=px*0+10,tradable=px.notna(),roles={'X':'index'})
    reg=pd.Series(['RANGE']*3,index=dates); out=E.simulate(p,pd.DataFrame({'X':[1.,1.,1.]},index=dates),drawdown_breaker=False,regimes=reg)
    assert out['regime'].equals(reg)
    assert out['weights'].shape == (3,1)
    assert out['sleeve_contribution']['index'].iloc[2] > 0


def test_periodic_metrics_compound_only_masked_daily_returns():
    from app.aw_run import _period_cagr
    dates=pd.date_range('2020-01-01',periods=5)
    curve=pd.Series([1.,2.,4.,8.,16.],index=dates)
    mask=pd.Series([False,True,False,True,False],index=dates)
    # Included returns are day 1 and day 3: 2x * 2x, annualised across two days.
    expected=4**(252/2)-1
    assert _period_cagr(curve,mask)==pytest.approx(expected)


def test_stock_lookback_changes_vectorized_ranking():
    dates=pd.date_range('2020-01-01',periods=240)
    idx=np.linspace(100,150,240)
    levels={}
    for i in range(6):
        x=np.ones(240)*100
        if i==0: x[239]=200
        elif i==1: x[179:]=20; x[239]=100
        elif i==2: x[179:]=200
        else: x[239]=105+i
        levels[f'S{i}']=x
    close=pd.DataFrame({'069500':idx,**levels},index=dates)
    symbols=list(close.columns)
    roles={s:('index' if s=='069500' else 'stock') for s in symbols}
    p=SimpleNamespace(market='KR',dates=dates,symbols=symbols,c=close,o=close,v=close*0+100,
      tradable=close.notna(),roles=roles,names={s:s for s in symbols},
      stock_eligible=pd.DataFrame(True,index=dates,columns=symbols[1:]))
    regimes=pd.Series('BULL',index=dates)
    w60=E.target_weights(p,regimes,60,offset=239%21)
    w120=E.target_weights(p,regimes,120,offset=239%21)
    assert w60.loc[dates[-1],'S1']==.1 and w120.loc[dates[-1],'S1']==0


def test_range_mr_daily_updates_preserve_index_and_bill_core():
    dates=pd.date_range('2020-01-01',periods=225)
    idx=np.linspace(100,140,225)
    sec=np.linspace(80,120,225); sec[-2:]=[118,116]
    c=pd.DataFrame({'069500':idx,'SEC':sec,'153130':np.linspace(100,102,225)},index=dates)
    p=SimpleNamespace(market='KR',dates=dates,symbols=list(c.columns),c=c,o=c,v=c*0+10,tradable=c.notna(),
      roles={'069500':'index','SEC':'sector','153130':'defensive'},
      names={'069500':'index','SEC':'sector','153130':'KODEX 단기채권'},stock_eligible=pd.DataFrame(index=dates))
    w=E.target_weights(p,pd.Series('RANGE',index=dates),mean_reversion=True,offset=0)
    assert w.iloc[-2]['069500']==pytest.approx(.3)
    assert w.iloc[-2]['153130']==pytest.approx(.3)
    assert w.iloc[-2]['SEC']>=0


def test_bull_with_no_eligible_stocks_routes_empty_stock_sleeve_to_index_cap():
    dates=pd.date_range('2020-01-01',periods=240)
    c=pd.DataFrame({'069500':np.linspace(100,150,240),'A':np.linspace(100,130,240)},index=dates)
    p=SimpleNamespace(market='KR',dates=dates,symbols=list(c.columns),c=c,o=c,v=c*0+1,tradable=c.notna(),
      roles={'069500':'index','A':'stock'},names={'069500':'index','A':'A'},
      stock_eligible=pd.DataFrame({'A':False},index=dates))
    w=E.target_weights(p,pd.Series('BULL',index=dates))
    assert w.iloc[-1]['A']==0
    assert w.iloc[-1]['069500']==pytest.approx(.5)
