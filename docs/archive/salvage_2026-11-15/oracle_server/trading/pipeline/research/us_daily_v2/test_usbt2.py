"""Synthetic tests for the v2 simulators (no network, no cache)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "us_daily_v1"))
import usbt2  # noqa: E402


def _P(n=30, k=3, price=100.0):
    idx = pd.bdate_range("2010-01-04", periods=n)
    P = usbt2.Panel()
    cols = ["A", "B", "C"][:k]
    P.C = pd.DataFrame(price, index=idx, columns=cols)
    P.O = P.C.copy()
    P.V = pd.DataFrame(1000.0, index=idx, columns=cols)
    P.E = pd.DataFrame(True, index=idx, columns=cols)
    P.rf = pd.Series(0.0, index=idx)
    return P


def test_targets_delisted_name_valued_at_last_close_then_sold():
    P = _P()
    P.C.iloc[10:, 0] = np.nan          # A's data ends after day 9 (last close 100)
    P.O.iloc[10:, 0] = np.nan
    P.C.iloc[5:10, 0] = 120.0
    P.O.iloc[5:10, 0] = 120.0
    tg = {0: np.array([1.0, 0.0, 0.0]), 20: np.array([0.0, 1.0, 0.0])}
    res = usbt2.sim_targets(P, tg, cost=0.0)
    assert res["eq"].iloc[15] == pytest.approx(1.2)            # frozen at last close, not zero
    assert res["eq"].iloc[-1] == pytest.approx(1.2)            # sold at last close on day 21, rotated into B (flat)
    assert res["gross"].iloc[-1] == pytest.approx(1.0)


def test_targets_cannot_buy_without_open():
    P = _P()
    P.O.iloc[1, 1] = np.nan
    res = usbt2.sim_targets(P, {0: np.array([0.0, 1.0, 0.0])}, cost=0.0)
    assert res["gross"].iloc[1] == pytest.approx(0.0)


def test_slots_fixed_hold_and_slot_size():
    P = _P(n=40)
    cand = np.zeros(P.C.shape, bool)
    cand[2, 0] = True                         # signal at close day 2 -> buy open day 3
    prio = np.zeros(P.C.shape)
    P.C.iloc[3:, 0] = np.linspace(100, 139, 37)
    P.O.iloc[3:, 0] = P.C.iloc[3:, 0].values
    res = usbt2.sim_slots(P, "x", cost=0.0, pre=(cand, prio, True, None, 20), slots=20, slot_w=0.05)
    buys = [f for f in res["fills"] if f[2] > 0]
    sells = [f for f in res["fills"] if f[2] < 0]
    assert len(buys) == 1 and len(sells) == 1
    assert buys[0][0] == P.C.index[3]
    assert sells[0][0] == P.C.index[3 + 20]                  # held exactly 20 sessions
    assert buys[0][2] == pytest.approx(0.05)


def test_slots_random_null_same_count():
    P = _P(n=20)
    cand = np.zeros(P.C.shape, bool)
    cand[2, 0] = True
    rng = np.random.default_rng(0)
    res = usbt2.sim_slots(P, "x", cost=0.0, pre=(cand, np.zeros(P.C.shape), True, None, 5), rng=rng)
    assert len([f for f in res["fills"] if f[2] > 0]) == 1


def test_repair_adjustment_double_count_only():
    idx = pd.bdate_range("2016-06-27", periods=6)
    close = pd.Series([100, 100, 100, 101, 101, 101.0], index=idx)
    adj = pd.Series([60, 60, 60, 98, 98, 98.0], index=idx)          # fake +63% jump in adjclose, close smooth -> repair
    d = pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "adjclose": adj, "volume": 1.0})
    r, fx = usbt2.repair_adjustment(d)
    assert fx == ["2016-06-30"]
    assert r["adjclose"].pct_change().abs().max() < 0.05
    close2 = pd.Series([100, 100, 30, 30, 30, 30.0], index=idx)       # spin-off: close drops, adjclose smooth -> untouched
    adj2 = pd.Series([30, 30, 30, 30, 30, 30.0], index=idx)
    d2 = pd.DataFrame({"open": close2, "high": close2, "low": close2, "close": close2, "adjclose": adj2, "volume": 1.0})
    assert usbt2.repair_adjustment(d2)[1] == []
