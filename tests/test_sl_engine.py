"""Fast synthetic mechanics plus offline real-panel parity tests for SL engine."""
import os
import numpy as np
import pandas as pd
import pytest
from app.rs_sl_engine import TPSim as SLSim, _sim_tp, tp_params, sl_params
from app.rs_tp_engine import TPSim as TPSim
from app.rs_final_engine import Sim as BaseSim, params


def toy(sl=None, tp=None, score=None, day_low=None, day_high=None, day_close=None, crash=None, nday=6, score_by_day=None):
    n = len(score[0]) if score is not None else 2
    C = np.full((nday, 24, n), 100., dtype=float); H = C.copy(); L = C.copy()
    for d, j, v in (day_low or []): L[d, :, j] = v
    for d, j, v in (day_high or []): H[d, :, j] = v
    for d, j, v in (day_close or []): C[d, 0, j] = v
    sc = np.asarray(score if score is not None else np.tile([1., -1.], (nday, 1)), dtype=float)
    if score_by_day:
        for d, row in score_by_day.items(): sc[d] = row
    flag = np.asarray(crash if crash is not None else np.zeros(nday), dtype=float)
    log = np.zeros((200, 12))
    out = _sim_tp(H, L, C, np.zeros((nday,n)), np.zeros((nday,24,n)), sc, flag,
                  params(rebal=3, K=1, lev=2, deploy=1, cost=0, kill=1., cool=0),
                  np.zeros(n), np.zeros(n), 0, nday,
                  tp_params(**(tp or {})), sl_params(**(sl or {})), 0, log)
    return out, log


def test_gap_stop_is_clamped_and_mode_fills():
    (eq, _, _, stats), log = toy(sl={"SL": .10, "fillmode": 0}, day_low=[(1,0,80)], day_high=[(1,0,90)], day_close=[(1,0,85)])
    assert stats[8] == 1 and log[0, 10] == 0
    assert log[0, 9] == 90  # gap-through: best-case-adverse bar high
    assert eq[1] < 1.
    (_, _, _, st), log1 = toy(sl={"SL": .10, "fillmode": 1}, day_low=[(1,0,80)], day_high=[(1,0,90)])
    assert st[8] == 1 and 80 <= log1[0,9] <= 90
    (_, _, _, st), log2 = toy(sl={"SL": .10, "fillmode": 2}, day_low=[(1,0,80)], day_high=[(1,0,90)], day_close=[(1,0,85)])
    assert st[8] == 1 and log2[0,9] == 85


def test_short_stop_and_same_bar_sl_wins():
    (_, _, _, st), log = toy(sl={"SS": .10}, day_high=[(1,1,115)], day_low=[(1,1,105)])
    assert st[8] == 1 and log[0,1] == -1
    (_, _, _, st), log = toy(sl={"SL": .10}, tp={"XL": .10}, day_low=[(1,0,85)], day_high=[(1,0,115)])
    assert log[0,4] == 4  # SL type has priority in same bar


def test_first_exposure_is_day_after_close_and_no_redeployment():
    # Entry happens at day 0 close; day 0's extreme is ignored. Freed slot stays cash until day 3.
    out, log = toy(sl={"SL": .10}, day_low=[(0,0,50),(1,0,80)], nday=6)
    assert out[3][8] == 1
    assert log[0,2] == 0 and log[0,3] == 1
    # At day 2, the stopped leg remains absent; no second entry until due rebalance day 3.
    assert out[0][2] == out[0][1]


def test_zero_percent_stop_triggers_at_entry_on_first_eligible_bar():
    out, log = toy(sl={"SL": 0.0}, day_low=[(0,0,50),(1,0,99.99)])
    hit = log[log[:,4] == 4]
    assert out[3][8] >= 1
    assert np.any((hit[:,2] == 0) & (hit[:,3] == 1) & (hit[:,10] == 0))
    assert np.all(hit[:,9] <= 100.0)


def test_stop_off_is_distinct_from_zero_percent():
    (eq_off, _, _, stats_off), _ = toy(sl={"SL": -1.0, "SS": -1.0}, day_low=[(1,0,90)])
    (eq_zero, _, _, stats_zero), _ = toy(sl={"SL": 0.0, "SS": -1.0}, day_low=[(1,0,90)])
    assert stats_off[8] == 0
    assert stats_zero[8] >= 1
    assert eq_off[1] != eq_zero[1]


def test_kept_position_retains_original_entry_reference():
    # Daily close rises, but same-side rebalance keeps original qty and stop entry.
    out, log = toy(sl={"SL": .10}, day_high=[(1,0,120)], day_low=[(4,0,89)], nday=6)
    rows = log[log[:,4] == 4]
    assert len(rows) == 1 and rows[0,8] == 100
    assert rows[0,2] == 0 and rows[0,3] == 4


def test_lockout_applies_to_next_rebalance_only():
    score = np.tile([3.,2.,1.], (8,1))
    out, log = toy(sl={"SL": .10, "lockout": 1}, score=score, nday=8,
                   day_low=[(1,0,80),(4,0,80)])
    # The second adverse bar cannot stop symbol 0: lockout excluded it at day 3.
    assert out[3][8] == 1


def test_crash_long_only_keeps_short_book():
    nday=6; C=np.full((nday,24,2),100.); H=C.copy(); L=C.copy(); sc=np.tile([1.,-1.],(nday,1))
    flag=np.array([0,0,1,1,0,0.],float)
    res=_sim_tp(H,L,C,np.zeros((nday,2)),np.zeros((nday,24,2)),sc,flag,
        params(rebal=3,K=1,lev=2,deploy=1,cost=0,kill=1,cool=0),np.zeros(2),np.zeros(2),0,nday,
        tp_params(),sl_params(),2,np.zeros((100,12)))
    # At the flag-on close the long is absent and the short remains open.
    assert res[2][2] > 0


def test_future_perturbation_does_not_change_prefix():
    nday=6; C=np.full((nday,24,2),100.); H=C.copy(); L=C.copy(); sc=np.tile([1.,-1.],(nday,1))
    def run(H,L,C):
        log=np.zeros((200,12))
        out=_sim_tp(H,L,C,np.zeros((nday,2)),np.zeros((nday,24,2)),sc,np.zeros(nday),
            params(rebal=3,K=1,lev=2,deploy=1,cost=0,kill=1,cool=0),np.zeros(2),np.zeros(2),0,nday,
            tp_params(),sl_params(SL=.1),0,log)
        return out[:3],log[:int(out[3][7])]
    a=run(H,L,C); H2=H.copy(); L2=L.copy(); C2=C.copy(); H2[4:]*=3; L2[4:]*=.1; C2[4:]*=4
    b=run(H2,L2,C2)
    for aa,bb in zip(a[0],b[0]): np.testing.assert_array_equal(aa[:4],bb[:4])
    ta=a[1][a[1][:,3]<=3]; tb=b[1][b[1][:,3]<=3]
    np.testing.assert_array_equal(ta,tb)


def _real_data():
    panel = os.path.join(os.environ.get("RS_FINAL_SCRATCH", ".rs_cache/sl_panel"), "rs_final_panel.npz")
    if not os.path.exists(panel): pytest.skip("real local panel cache absent")
    from docs.research.sl_loop.lib import load_all
    return load_all()


def test_no_overlay_matches_base_exactly_all_phases():
    P, CF = _real_data(); base=BaseSim(P); new=SLSim(P,CF)
    kw=dict(rebal=3,K=8,lev=4.,deploy=.95,kill=.35,cool=14,cost=.001,fund=1,minn=0.,eq0=1.)
    for ph in range(3):
        a=new.run(sl={},phase=ph,crash_mode=1,**kw)
        b=base.run(lbs=(14,),crash_flat=True,phase=ph,**kw)
        for k in ("eq","worst","expo"):
            np.testing.assert_array_equal(a[k].to_numpy(),b[k].to_numpy())


@pytest.mark.parametrize("fill", [0,1,2])
@pytest.mark.parametrize("x", [.10,.25])
def test_tp_only_matches_existing_engine_exactly(fill,x):
    P, CF = _real_data(); old=TPSim(P,CF); new=SLSim(P,CF)
    kw=dict(rebal=3,K=8,lev=4.,deploy=.95,kill=.35,cool=14,cost=.001,fund=1,minn=0.,eq0=1.)
    params_tp=dict(XL=x,XS=x,frac=1.,fillmode=fill,slipx=.003)
    params_sl=dict(XL=x,XS=x,fillmode=fill,slipx=.003)
    for ph in range(3):
        a=new.run(tp=params_tp,phase=ph,crash_mode=1,**kw)
        b=old.run(tp=params_tp,phase=ph,crash_flat=True,**kw)
        for k in ("eq","worst","expo"):
            np.testing.assert_array_equal(a[k].to_numpy(),b[k].to_numpy())
