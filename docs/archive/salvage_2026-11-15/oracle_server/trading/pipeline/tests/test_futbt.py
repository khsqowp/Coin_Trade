import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import costs, futbt, metrics


def flat_df(prices, freq="1h"):
    p = np.array(prices, float)
    o = np.r_[p[0], p[:-1]]
    idx = pd.date_range("2024-01-01", periods=len(p), freq=freq, tz="UTC")
    return pd.DataFrame({"open": o, "high": np.maximum(o, p), "low": np.minimum(o, p), "close": p, "volume": 1.0}, index=idx)


ZERO = costs.CostModel(maker=0, taker=0, slip=0.0, name="zero")


def test_fee_models_use_official_numbers_and_are_separate():
    f, s = costs.make("futures"), costs.make("spot")
    assert (f.maker, f.taker, f.bnb_discount) == (0.0002, 0.0005, 0.10) and (s.maker, s.taker, s.bnb_discount) == (0.001, 0.001, 0.25)
    assert f.fee_side == pytest.approx(0.0005)
    assert costs.make("futures", bnb=True).fee_side == pytest.approx(0.00045)
    assert costs.make("futures", taker_share=0.0).fee_side == pytest.approx(0.0002)
    assert costs.make("futures", taker_share=0.5, bnb=True).fee_side == pytest.approx(0.5 * 0.0005 * 0.9 + 0.5 * 0.0002 * 0.9)
    assert costs.make("spot", bnb=True).fee_side == pytest.approx(0.00075)
    assert len(costs.scenarios("futures")) == 18 and "taker|nobnb|slip0.02%" in costs.scenarios("futures")


def test_no_position_no_change():
    d = flat_df(np.linspace(100, 110, 50))
    r = futbt.simulate(d, pd.Series(0.0, index=d.index), ZERO)
    assert r["ret"].abs().sum() == 0 and r["n_open"] == 0


def test_long_pnl_matches_price_move_zero_cost():
    d = flat_df([100.0] * 5 + list(np.linspace(100, 120, 10)) + [120.0] * 5)
    sig = pd.Series(1.0, index=d.index)
    r = futbt.simulate(d, sig, ZERO, lev=1.0)
    assert r["equity"].iloc[-1] == pytest.approx(120 / 100, rel=1e-9)


def test_short_profits_from_decline_and_leverage_scales():
    d = flat_df([100.0, 100.0] + list(np.linspace(100, 90, 8)))
    sig = pd.Series(-1.0, index=d.index)
    e1 = futbt.simulate(d, sig, ZERO, lev=1.0)["equity"].iloc[-1]
    e3 = futbt.simulate(d, sig, ZERO, lev=3.0)["equity"].iloc[-1]
    assert e1 == pytest.approx(1.10, rel=1e-6) and e3 == pytest.approx(1.30, rel=1e-6)


def test_fee_and_slippage_accounting():
    d = flat_df([100.0] * 10)
    sig = pd.Series([0, 1, 1, 1, 0, 0, 0, 0, 0, 0], index=d.index, dtype=float)
    c = costs.CostModel(maker=0.0, taker=0.001, slip=0.0005)
    r = futbt.simulate(d, sig, c, lev=1.0)
    # open + close: each side pays fee 0.1% and adverse slippage 0.05% on ~1.0 notional
    assert r["equity"].iloc[-1] == pytest.approx(1 - 2 * (0.001 + 0.0005), abs=2e-4)
    assert r["fees"] == pytest.approx(0.002, abs=2e-4) and r["n_open"] == 1


def test_funding_sign_longs_pay_when_positive():
    d = flat_df([100.0] * 40)
    sig = pd.Series(1.0, index=d.index)
    ts = (((d.index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).values.astype("int64"))[[10]] + 1800_000            # settles inside bar 10
    fr = futbt.funding_per_bar(d.index, 3_600_000, ts, np.array([0.001]))
    assert fr.sum() == pytest.approx(0.001) and fr[10] == pytest.approx(0.001)
    long_ = futbt.simulate(d, sig, ZERO, lev=1.0, fr=fr)["equity"].iloc[-1]
    short = futbt.simulate(d, -sig, ZERO, lev=1.0, fr=fr)["equity"].iloc[-1]
    assert long_ == pytest.approx(1 - 0.001, abs=1e-6) and short == pytest.approx(1 + 0.001, abs=1e-6)


def test_liquidation_loses_margin_and_locks_direction():
    p = [100.0] * 6 + [100, 95, 88, 80, 75, 100, 110, 120]
    d = flat_df(p)
    sig = pd.Series(1.0, index=d.index)
    r = futbt.simulate(d, sig, ZERO, lev=10.0)          # 10x: liquidated after about -9.5%
    assert r["n_liq"] == 1 and r["equity"].iloc[-1] == pytest.approx(0.0, abs=1e-9) or r["bankrupt"]
    # 2x leverage survives the same path (liquidation needs about -49.5%)
    r2 = futbt.simulate(d, sig, ZERO, lev=2.0)
    assert r2["n_liq"] == 0 and r2["equity"].iloc[-1] > 0


def test_lockout_until_signal_resets():
    # 5x, crash liquidates, price recovers while the signal stays long: no re-entry; fresh signal after a 0 re-enters
    p = [100.0] * 4 + [100, 70, 70, 80, 90, 100, 100, 100, 100, 100]
    d = flat_df(p)
    s = pd.Series([1.0] * 9 + [0.0] + [1.0] * 4, index=d.index)
    cap = costs.CostModel(maker=0, taker=0, slip=0)
    r = futbt.simulate(d, s, cap, lev=5.0, nf=0.5)      # half the equity as notional*... margin = 0.1 of equity
    assert r["n_liq"] == 1 and r["n_open"] >= 2
    assert r["equity"].iloc[-1] < 1.0


def test_gate_cap_sizing_limits_liquidation_loss():
    p = [100.0] * 6 + [100, 60, 60, 60]
    d = flat_df(p)
    sig = pd.Series(1.0, index=d.index)
    r = futbt.simulate(d, sig, ZERO, lev=10.0, nf=0.25)     # margin 2.5% of equity
    assert r["n_liq"] == 1 and r["equity"].iloc[-1] == pytest.approx(1 - 0.025, abs=1e-6)


def test_mirror_turns_long_strategy_into_short():
    d = make_ohlcv(400, seed=2)
    m = futbt.mirror(d)
    assert np.allclose((1 / m["close"]).values, d["close"].values) and (m["high"] >= m["low"]).all()


def test_metrics_dsr_penalises_many_trials():
    rng = np.random.RandomState(0)
    r = rng.normal(0.0003, 0.01, 3000)
    srs = rng.normal(0, 0.02, 100)
    d100, sr0 = metrics.dsr(r, srs, n_trials=100)
    d2, _ = metrics.dsr(r, srs[:2], n_trials=2)
    assert sr0 > 0 and d100 < metrics.psr(r)
    assert metrics.expected_max_sr(0.0004, 1000) > metrics.expected_max_sr(0.0004, 10) > 0
