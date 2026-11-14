"""Protective-rule verification (task E): history-dead protective rules are checked on synthetic stress instead of being blocked."""
import numpy as np
import pandas as pd
import pytest

from helpers_ext import make_ohlcv
from tp import ablation, bt, risk, stress

# The rule set of run fu-crypto-003-h2 (hard_catastrophe_stop was DEAD there and blocked the strategy).
HARD_CAT = '''
import numpy as np
import pandas as pd
RULES = {"ema_stack_filter": "EMA20>EMA50>EMA200", "pullback_touch_entry": "low touches EMA20 and green close",
         "ema50_loss_exit": "close < EMA50", "hard_catastrophe_stop": "close < entry*0.90"}
PROTECTIVE = {"hard_catastrophe_stop"}
RULE_KINDS = {"ema_stack_filter": "filter", "pullback_touch_entry": "entry", "ema50_loss_exit": "exit", "hard_catastrophe_stop": "protective"}


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    n = len(df)
    sig = np.zeros(n)
    close, open_, low = (df[k].astype(float) for k in ("close", "open", "low"))
    e20 = close.ewm(span=20, adjust=False, min_periods=20).mean()
    e50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    e200 = close.ewm(span=200, adjust=False, min_periods=200).mean()
    pos, entry_price = False, np.nan
    for i in range(n):
        if pos:
            ex = ("ema50_loss_exit" not in disabled) and close.iat[i] < e50.iat[i]
            if (not ex) and ("hard_catastrophe_stop" not in disabled) and close.iat[i] < entry_price * __STOP__:
                ex = True
            if ex:
                pos, entry_price = False, np.nan
        if not pos:
            f = True if "ema_stack_filter" in disabled else (e20.iat[i] > e50.iat[i] > e200.iat[i])
            e = True if "pullback_touch_entry" in disabled else (low.iat[i] <= e20.iat[i] and close.iat[i] > open_.iat[i])
            if f and e and not np.isnan(e200.iat[i]):
                pos, entry_price = True, close.iat[i]
        sig[i] = 1.0 if pos else 0.0
    return pd.Series(sig, index=df.index, dtype=float)
'''


def _load(src):
    import types
    m = types.ModuleType("fx")
    exec(compile(src, "fx", "exec"), m.__dict__)      # test fixture (our own code)
    return m


@pytest.fixture(scope="module")
def data():
    return make_ohlcv(2500, seed=21, drift=0.0006)


def test_prior_behaviour_without_protective_flag_is_dead(data):
    m = _load(HARD_CAT.replace("__STOP__", "0.90"))
    rep = ablation.run_ablation(data, m.generate_signals, m.RULES, 8760)       # legacy call: no protective info
    assert "hard_catastrophe_stop" in rep["dead_rules"]                          # the old policy blocks it


def test_protective_dead_on_history_is_verified_by_stress(data):
    m = _load(HARD_CAT.replace("__STOP__", "0.90"))
    rep = ablation.run_ablation(data, m.generate_signals, m.RULES, 8760, protective=m.PROTECTIVE, kinds=m.RULE_KINDS)
    assert rep["status"] == "ok" and "hard_catastrophe_stop" not in rep["dead_rules"]
    p = rep["protective_rules"][0]
    assert p["fired"] and p["history_verdict"] in ("dead", "weak")
    assert p["isolated_fired_in"], "redundant with ema50 exit in the plain test; must be shown by the isolated test"
    d = risk.gate_strategy(risk.NUMERIC_AUDIT_STUB, {"params": {"fee": .001, "slippage": .0005}, "full": {"trades": 99, "mdd": .1},
                                                    "in_sample": {"sharpe": 1}, "out_of_sample": {"trades": 50, "bars": 999, "sharpe": 1},
                                                    "lookahead_check": {"passed": True}}, "BTC/USDT", ablation=rep)
    assert not any(r.startswith("DEAD_RULE") for r in d.reasons)


def test_protective_rule_that_never_fires_is_still_dead(data):
    m = _load(HARD_CAT.replace("__STOP__", "0.0001"))        # stop at -99.99%: impossible even in the stress paths
    rep = ablation.run_ablation(data, m.generate_signals, m.RULES, 8760, protective=m.PROTECTIVE, kinds=m.RULE_KINDS)
    assert "hard_catastrophe_stop" in rep["dead_rules"]
    p = rep["protective_rules"][0]
    assert not p["fired"] and p["tested"] > 0
    d = risk.gate_strategy(risk.NUMERIC_AUDIT_STUB, {"params": {"fee": .001, "slippage": .0005}, "full": {"trades": 99, "mdd": .1},
                                                    "in_sample": {"sharpe": 1}, "out_of_sample": {"trades": 50, "bars": 999, "sharpe": 1},
                                                    "lookahead_check": {"passed": True}}, "BTC/USDT", ablation=rep)
    assert not d.allowed and any(r.startswith("DEAD_RULE") for r in d.reasons)


def test_non_protective_dead_rule_policy_unchanged(data):
    m = _load(HARD_CAT.replace("__STOP__", "0.90"))
    rep = ablation.run_ablation(data, m.generate_signals, m.RULES, 8760, protective=set(), kinds=m.RULE_KINDS)
    assert "hard_catastrophe_stop" in rep["dead_rules"]       # same rule WITHOUT the protective mark is blocked as before


def test_stress_injection_is_deterministic_and_shapes(data):
    sig = pd.Series(1.0, index=data.index)
    pts = stress.held_points(sig)
    assert pts == stress.held_points(sig) and len(pts) == 3
    t = pts[0]
    d1, tt = stress.inject(data, t, "gap_25")
    d2, _ = stress.inject(data, t, "gap_25")
    assert d1.equals(d2)
    assert d1["close"].iloc[tt + 1] / d1["close"].iloc[tt] < 0.80 and d1["close"].iloc[tt] == data["close"].iloc[t]
    dc, tt = stress.inject(data, t, "consecutive")
    assert dc["close"].iloc[tt + 10] == pytest.approx(data["close"].iloc[t] * 0.97 ** 10)
    dh, tt = stress.inject(data, t, "halt_gap")
    assert (dh["volume"].iloc[tt + 1:tt + 4] == 0).all() and (dh["high"].iloc[tt + 1:tt + 4] == dh["low"].iloc[tt + 1:tt + 4]).all()
    assert dh["close"].iloc[tt + 4] < dh["close"].iloc[tt] * 0.9


def test_pool_protective_stops_fire_in_stress(data):
    from tp import pool
    for sid in ("coin_mean_reversion", "coin_trend_mtf", "stock_trend_sma200"):
        m = pool.load(sid)
        d = make_ohlcv(3000, seed=8, drift=0.0005) if sid != "stock_trend_sma200" else make_ohlcv(3000, seed=8, drift=0.001, freq="1D")
        rule = sorted(m.PROTECTIVE)[0]
        res = stress.check_protective(m.generate_signals, d, rule, m.RULE_KINDS)
        assert res["fired"], (sid, rule, res)
