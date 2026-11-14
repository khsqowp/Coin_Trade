import copy
import datetime as dt

import pytest

from tp.risk import RiskConfig, RiskEngine, gate_strategy

T0 = dt.datetime(2026, 1, 5, 12, 0, tzinfo=dt.timezone.utc)
CFG = RiskConfig()


def good_audit():
    return {"verdict": "PASS", "findings": [], "stats_assessment": "ok", "confidence": 0.8, "rationale": "ok",
            "checks": {"lookahead_bias": "clean", "data_leakage": "clean", "overfitting": "clean",
                       "costs_slippage": "clean", "sample_size": "clean"}}


def good_bt():
    st = lambda n, sh, bars: {"bars": bars, "trades": n, "sharpe": sh, "mdd": 0.2}
    return {"params": {"fee": 0.001, "slippage": 0.0005}, "invalid_signal_values": 0,
            "full": st(60, 1.0, 2000), "in_sample": st(36, 1.1, 1200), "out_of_sample": st(24, 0.9, 800),
            "lookahead_check": {"passed": True, "mismatches": 0, "errors": 0}}


# ---- promotion gate
def test_gate_allows_clean_case():
    d = gate_strategy(good_audit(), good_bt(), "BTC/USDT")
    assert d.allowed and d.reasons == []


@pytest.mark.parametrize("verdict", ["FAIL", "INCONCLUSIVE"])
def test_gate_blocks_non_pass(verdict):
    a = good_audit(); a["verdict"] = verdict
    d = gate_strategy(a, good_bt(), "BTC/USDT")
    assert not d.allowed and any("AUDIT_NOT_PASS" in r for r in d.reasons)


def test_gate_blocks_pass_with_high_finding():
    a = good_audit()
    a["findings"] = [{"category": "logic_error", "severity": "high", "evidence": "x", "location": "l1"}]
    assert not gate_strategy(a, good_bt(), "BTC/USDT").allowed


def test_gate_blocks_pass_with_leak_flag():
    a = good_audit(); a["checks"]["lookahead_bias"] = "suspected"
    assert not gate_strategy(a, good_bt(), "BTC/USDT").allowed


def test_gate_blocks_malformed_audit():
    assert not gate_strategy({"verdict": "PASS"}, good_bt(), "BTC/USDT").allowed
    assert not gate_strategy(None, good_bt(), "BTC/USDT").allowed


def test_gate_blocks_when_engine_lookahead_check_fails_even_if_auditor_passes():
    b = good_bt(); b["lookahead_check"] = {"passed": False, "mismatches": 3, "errors": 0}
    d = gate_strategy(good_audit(), b, "BTC/USDT")
    assert not d.allowed and any("LOOKAHEAD" in r for r in d.reasons)


def test_gate_blocks_non_whitelisted_symbol():
    assert not gate_strategy(good_audit(), good_bt(), "DOGE/USDT").allowed


def test_gate_blocks_missing_costs():
    b = good_bt(); b["params"]["fee"] = 0.0
    assert not gate_strategy(good_audit(), b, "BTC/USDT").allowed


def test_gate_blocks_small_sample():
    b = good_bt(); b["full"]["trades"] = 5; b["out_of_sample"]["trades"] = 2
    d = gate_strategy(good_audit(), b, "BTC/USDT")
    assert not d.allowed and len(d.reasons) >= 2


def test_gate_blocks_high_mdd_and_low_sharpe_and_degradation():
    b = good_bt(); b["full"]["mdd"] = 0.6
    assert not gate_strategy(good_audit(), b, "BTC/USDT").allowed
    b = good_bt(); b["out_of_sample"]["sharpe"] = 0.1
    assert not gate_strategy(good_audit(), b, "BTC/USDT").allowed
    b = good_bt(); b["in_sample"]["sharpe"] = 3.0; b["out_of_sample"]["sharpe"] = 0.9
    d = gate_strategy(good_audit(), b, "BTC/USDT")
    assert not d.allowed and any("DEGRADATION" in r for r in d.reasons)


def test_gate_blocks_missing_evidence():
    assert not gate_strategy(good_audit(), {}, "BTC/USDT").allowed


# ---- runtime engine
def eng(equity=10_000):
    return RiskEngine(CFG, equity=equity, now=T0)


def test_order_ok():
    assert eng().check_order("BTC/USDT", "buy", 1000, T0).allowed


def test_whitelist():
    assert not eng().check_order("SOL/USDT", "buy", 100, T0).allowed


def test_live_mode_forbidden():
    d = eng().check_order("BTC/USDT", "buy", 100, T0, mode="live")
    assert not d.allowed and "MODE_FORBIDDEN: live" in d.reasons
    assert not RiskEngine(CFG, mode="live", now=T0).check_order("BTC/USDT", "buy", 1, T0).allowed


def test_position_cap():
    e = eng()
    assert e.check_order("BTC/USDT", "buy", 2500, T0).allowed
    assert not e.check_order("BTC/USDT", "buy", 2501, T0).allowed
    assert not e.check_order("BTC/USDT", "buy", 1000, T0, current_position=2000).allowed


def test_bad_inputs():
    e = eng()
    assert not e.check_order("BTC/USDT", "hold", 100, T0).allowed
    assert not e.check_order("BTC/USDT", "buy", 0, T0).allowed
    assert not e.check_order("BTC/USDT", "buy", -5, T0).allowed


def test_daily_loss_halts_buys_not_sells_and_resets_next_day():
    e = eng()
    e.on_equity(9_700, T0)  # -3% exactly
    assert e.halted
    assert not e.check_order("BTC/USDT", "buy", 100, T0).allowed
    assert e.check_order("BTC/USDT", "sell", 100, T0).allowed
    nxt = T0 + dt.timedelta(days=1)
    e.on_equity(9_700, nxt)
    assert not e.halted_day and e.check_order("BTC/USDT", "buy", 100, nxt).allowed


def test_drawdown_halt_is_sticky_until_manual_reset():
    e = eng()
    d = T0
    for i, eq in enumerate([10_000, 9_900, 9_800, 9_700, 8_500]):  # slow slide to -15%
        d = T0 + dt.timedelta(days=i)
        e.on_equity(eq, d)
    assert e.halted_dd
    d += dt.timedelta(days=5)
    e.on_equity(8_500, d)
    assert e.halted_dd and not e.check_order("ETH/USDT", "buy", 100, d).allowed
    e.manual_reset()
    assert e.check_order("ETH/USDT", "buy", 100, d).allowed


def test_trade_count_limit_and_daily_reset():
    e = eng()
    for _ in range(CFG.max_trades_per_day):
        assert e.check_order("BTC/USDT", "buy", 10, T0).allowed
        e.record_fill(T0)
    assert not e.check_order("BTC/USDT", "buy", 10, T0).allowed
    assert not e.check_order("BTC/USDT", "sell", 10, T0).allowed
    assert e.check_order("BTC/USDT", "buy", 10, T0 + dt.timedelta(days=1)).allowed


def test_config_is_immutable():
    with pytest.raises(Exception):
        CFG.max_trades_per_day = 99
