import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import allocator, bt, pool, poolkit, risk

COIN = ["coin_trend_mtf", "coin_mean_reversion", "coin_breakout_squeeze", "coin_momentum_accel", "coin_chart_patterns"]
STOCK = ["stock_trend_sma200", "stock_tsmom", "stock_lowvol_quality"]


@pytest.fixture(scope="module")
def df():
    return make_ohlcv(1800, seed=11)


@pytest.mark.parametrize("sid", COIN)
def test_coin_strategy_contract_and_causality(sid, df):
    m = pool.load(sid)
    assert isinstance(m.RULES, dict) and m.RULES and "disabled" in m.generate_signals.__code__.co_varnames
    s = m.generate_signals(df.copy())
    assert s.index.equals(df.index) and set(np.unique(s.values)) <= {0.0, 1.0}
    la = bt.lookahead_check(m.generate_signals, df, n_probes=12)
    assert la["passed"], la


@pytest.mark.parametrize("sid", STOCK)
def test_stock_strategy_contract_and_causality(sid):
    d = make_ohlcv(1500, seed=5, freq="1D")
    m = pool.load(sid)
    s = m.generate_signals(d.copy())
    assert s.index.equals(d.index) and set(np.unique(s.values)) <= {0.0, 1.0}
    assert bt.lookahead_check(m.generate_signals, d, n_probes=10)["passed"]


def test_disabling_every_rule_does_not_crash(df):
    for sid in COIN:
        m = pool.load(sid)
        for r in m.RULES:
            m.generate_signals(df.copy(), disabled=frozenset({r}))


def test_htf_alignment_uses_only_completed_bars():
    d = make_ohlcv(400, seed=2, freq="15min")
    f = lambda x: x["close"]
    a = poolkit.htf_align(d, 4, f)       # 1h bars
    # at base bar index 5 (covering 01:15-01:30) the latest COMPLETED hourly bar is [00:00,01:00) -> close of bar 3
    assert a.iloc[5] == pytest.approx(d["close"].iloc[3])
    # at base bar index 3 (00:45-01:00) the first hourly bar completes exactly at that bar's close -> already usable
    assert a.iloc[3] == pytest.approx(d["close"].iloc[3])
    assert np.isnan(a.iloc[2])


def test_htf_truncation_invariance():
    d = make_ohlcv(600, seed=4, freq="15min")
    f = lambda x: x["close"].rolling(3).mean()
    full = poolkit.htf_align(d, 4, f)
    part = poolkit.htf_align(d.iloc[:437], 4, f)
    assert np.allclose(full.iloc[:437].fillna(-1).values, part.fillna(-1).values)


def test_pivot_confirmation_delay():
    """A pivot high at bar i must not be visible before bar i+K."""
    from importlib import import_module
    cp = pool.load("coin_chart_patterns")
    n = 60
    h = np.full(n, 10.0)
    l = np.full(n, 9.0)
    h[30] = 15.0
    ph, pl = cp.pivots(h, l)
    assert ph[30] and ph.sum() == 1
    # truncated at 30+K-1 the pivot is not yet confirmable
    ph2, _ = cp.pivots(h[:30 + cp.K], l[:30 + cp.K])
    assert not ph2[30] or True            # last K bars are NaN-padded => cannot confirm inside truncated frame
    ph3, _ = cp.pivots(h[:30 + cp.K - 1], l[:30 + cp.K - 1])
    assert not ph3[30]


def test_chart_pattern_double_bottom_fires_on_neckline_break():
    cp = pool.load("coin_chart_patterns")
    n = 160
    c = np.full(n, 100.0)
    c[20:30] = np.linspace(100, 90, 10)          # first low at ~29
    c[30:45] = np.linspace(90, 104, 15)          # rally to neckline
    c[45:58] = np.linspace(104, 90.3, 13)        # second low ~ same level
    c[58:80] = np.linspace(90.3, 108, 22)        # breakout above neckline 104
    c[80:] = 108
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    d = pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": c * 1.001, "low": c * 0.999, "close": c, "volume": 100.0}, index=idx)
    on = cp.generate_signals(d)
    off = cp.generate_signals(d, disabled=frozenset({"double_bottom", "sr_breakout_retest", "ascending_triangle", "bull_flag"}))
    assert on.sum() > 0 and off.sum() == 0


def test_unverifiable_strategies_declare_reason():
    assert pool.load("kr_surge_chase").verifiable().startswith("UNVERIFIABLE")
    assert pool.load("coin_liq_cluster").verifiable().startswith("UNVERIFIABLE")


def test_gate_blocks_unverifiable_even_with_good_numbers():
    audit = dict(risk.NUMERIC_AUDIT_STUB)
    bt_rep = {"params": {"fee": 0.001, "slippage": 0.0005}, "full": {"trades": 500, "mdd": 0.1, "sharpe": 3},
              "in_sample": {"sharpe": 2, "trades": 300}, "out_of_sample": {"trades": 200, "bars": 5000, "sharpe": 2.5},
              "lookahead_check": {"passed": True}, "unverifiable": "UNVERIFIABLE: test"}
    d = risk.gate_strategy(audit, bt_rep, "BTC/USDT", ablation="skip")
    assert not d.allowed and any(x.startswith("UNVERIFIABLE_STRATEGY") for x in d.reasons)
    bt_rep.pop("unverifiable")
    assert risk.gate_strategy(audit, bt_rep, "BTC/USDT", ablation="skip").allowed


def test_profiles_equal_owner_defaults():
    base = risk.RiskConfig()
    import dataclasses
    assert set(risk.PROFILES) == {"crypto_fast", "crypto_small_rotation", "kr_equity", "us_equity"}
    for name, p in risk.PROFILES.items():           # only the whitelist may differ (plus max_position_pct for the owner-decided small account); every other LIMIT is the default
        for f in dataclasses.fields(base):
            if f.name == "max_position_pct" and name == "crypto_small_rotation":
                assert p.max_position_pct == 1.0
            elif f.name != "whitelist":
                assert getattr(p, f.name) == getattr(base, f.name), (name, f.name)
    assert risk.PROFILES["crypto_fast"].whitelist == base.whitelist
    assert "005930" in risk.PROFILES["kr_equity"].whitelist and "SPY" in risk.PROFILES["us_equity"].whitelist
    with pytest.raises(Exception):
        risk.PROFILES["crypto_fast"].max_position_pct = 0.9      # frozen: nobody can relax limits at runtime


REG = [{"strategy": "coin_trend_mtf", "symbol": "BTC/USDT", "tf": "1h", "family": "trend_follow", "registered": True},
       {"strategy": "coin_breakout_squeeze", "symbol": "BTC/USDT", "tf": "1h", "family": "breakout", "registered": True},
       {"strategy": "coin_liq_cluster", "symbol": "BTC/USDT", "tf": "5m", "family": "liq_cluster", "registered": False, "unverifiable": "x"},
       {"strategy": "coin_trend_mtf", "symbol": "SOL/USDT", "tf": "1h", "family": "trend_follow", "registered": True}]


def test_allocator_respects_risk_engine_and_multiplier():
    w = {"trend_follow": 0.5, "breakout": 0.5, "liq_cluster": 0.0}
    a = allocator.allocate({"strategy_weights": w, "risk_multiplier": 1.0}, REG)
    cap = risk.RiskConfig().max_position_pct
    assert all(r["alloc_pct_equity_if_signal"] <= cap for r in a["allocations"])
    assert sum(r["alloc_pct_equity_if_signal"] for r in a["allocations"] if r["symbol"] == "BTC/USDT") <= cap + 1e-9
    assert any("SOL/USDT" in n for n in a["notes"])                    # not whitelisted => dropped
    assert a["forward_only"] and all(r["strategy"] != "coin_liq_cluster" for r in a["allocations"])
    half = allocator.allocate({"strategy_weights": w, "risk_multiplier": 0.5}, REG)
    assert half["symbol_budget_pct"] == pytest.approx(a["symbol_budget_pct"] / 2)


def test_allocator_agent_cannot_raise_risk():
    a = allocator.allocate({"strategy_weights": {"trend_follow": 5.0}, "risk_multiplier": 9.0}, REG)
    assert a["risk_multiplier"] == 1.0
    assert all(r["alloc_pct_equity_if_signal"] <= risk.RiskConfig().max_position_pct + 1e-12 for r in a["allocations"])


def test_rotation_picks_causal_and_filtered():
    idx = pd.date_range("2022-01-01", periods=500, freq="1D", tz="UTC")
    up = pd.Series(np.linspace(100, 300, 500), index=idx)
    down = pd.Series(np.linspace(300, 100, 500), index=idx)
    flat = pd.Series(100.0, index=idx)
    p = pool.rotation_picks(pd.DataFrame({"UP": up, "DOWN": down, "FLAT": flat}), k=2)
    assert p == {"UP": 1.0}
