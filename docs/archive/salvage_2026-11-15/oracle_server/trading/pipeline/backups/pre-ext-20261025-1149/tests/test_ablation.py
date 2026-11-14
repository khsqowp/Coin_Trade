import json

import pytest

from fixtures_ablation import (FIXED, NO_DISABLED_PARAM, NO_RULES, NONDETERMINISTIC, PRIOR_DEFECT, RAISES_WHEN_DISABLED,
                               TWO_EFFECTIVE, UNUSED_RULE, WEAK_RULE, load_fn, make_df)
from tp import ablation
from tp.ablation import declared_rules, hypothesis_rule_names, run_ablation, summarize
from tp.risk import RiskConfig, gate_strategy
from test_risk import good_audit, good_bt

DF = make_df()
PPY = 365


def abl(src, tmp_path, hyp_rules=None):
    m = load_fn(src, tmp_path)
    return run_ablation(DF, m.generate_signals, getattr(m, "RULES", None), PPY, hyp_rules)


def verdicts(rep):
    return {r["rule"]: r["verdict"] for r in rep["rules"]}


# ---- the previous defect (run-main-002) -------------------------------------------------------
def test_prior_defect_atr_trailing_rule_is_dead(tmp_path):
    rep = abl(PRIOR_DEFECT, tmp_path)
    assert rep["status"] == "ok"
    v = verdicts(rep)
    assert v["atr_trailing_exit"] == "dead"
    assert rep["dead_rules"] == ["atr_trailing_exit"]
    atr = next(r for r in rep["rules"] if r["rule"] == "atr_trailing_exit")
    assert atr["signals_identical"] and atr["diff_bars"] == 0 and atr["trades_delta"] == 0 and atr["return_delta"] == 0
    # the other two rules do matter
    assert v["sma_trend_entry"] == "effective"


def test_prior_defect_signals_equal_plain_sma_filter(tmp_path):
    """Documents the symptom: with the bug, the 'complex' strategy IS close > SMA."""
    m = load_fn(PRIOR_DEFECT, tmp_path)
    full = m.generate_signals(DF)
    plain = (DF["close"] > DF["close"].rolling(50).mean()).astype(float)
    assert bool((full == plain).all())


def test_fixed_strategy_trailing_rule_is_effective(tmp_path):
    rep = abl(FIXED, tmp_path)
    assert rep["status"] == "ok"
    assert verdicts(rep)["atr_trailing_exit"] == "effective"
    assert rep["dead_rules"] == []
    c = next(r for r in rep["rules"] if r["rule"] == "atr_trailing_exit")
    assert c["diff_bars"] > 0


def test_gate_blocks_prior_defect_even_when_everything_else_is_perfect(tmp_path):
    rep = abl(PRIOR_DEFECT, tmp_path)
    d = gate_strategy(good_audit(), good_bt(), "BTC/USDT", ablation=rep)
    assert not d.allowed
    assert any(x.startswith("DEAD_RULE: atr_trailing_exit") for x in d.reasons)


def test_gate_allows_fixed_strategy_with_perfect_other_evidence(tmp_path):
    rep = abl(FIXED, tmp_path)
    d = gate_strategy(good_audit(), good_bt(), "BTC/USDT", ablation=rep)
    assert d.allowed, d.reasons


# ---- other classifications ---------------------------------------------------------------------
def test_declared_but_unused_rule_is_dead(tmp_path):
    rep = abl(UNUSED_RULE, tmp_path)
    assert rep["dead_rules"] == ["volume_filter"]


def test_two_effective_rules(tmp_path):
    rep = abl(TWO_EFFECTIVE, tmp_path)
    assert rep["status"] == "ok" and rep["dead_rules"] == [] and rep["weak_rules"] == []
    assert set(rep["effective_rules"]) == {"sma_entry", "volume_filter"}


def test_weak_rule_is_warning_not_block(tmp_path):
    rep = abl(WEAK_RULE, tmp_path)
    assert rep["weak_rules"] == ["one_extra_bar"] and rep["dead_rules"] == []
    d = gate_strategy(good_audit(), good_bt(), "BTC/USDT", ablation=rep)
    assert d.allowed and any(w.startswith("WEAK_RULE") for w in d.warnings)


def test_hypothesis_rule_missing_in_code_blocks(tmp_path):
    rep = abl(TWO_EFFECTIVE, tmp_path, hyp_rules=["sma_entry", "volume_filter", "atr_trailing_exit"])
    assert rep["undeclared_hypothesis_rules"] == ["atr_trailing_exit"]
    d = gate_strategy(good_audit(), good_bt(), "BTC/USDT", ablation=rep)
    assert not d.allowed and any(x.startswith("HYPOTHESIS_RULE_NOT_IMPLEMENTED") for x in d.reasons)


@pytest.mark.parametrize("src,status", [(NO_RULES, "no_rules"), (NO_DISABLED_PARAM, "unsupported"),
                                        (RAISES_WHEN_DISABLED, "error"), (NONDETERMINISTIC, "nondeterministic")])
def test_unusable_ablation_blocks(tmp_path, src, status):
    rep = abl(src, tmp_path)
    assert rep["status"] == status
    d = gate_strategy(good_audit(), good_bt(), "BTC/USDT", ablation=rep)
    assert not d.allowed and any(x.startswith("ABLATION_UNAVAILABLE") for x in d.reasons)


def test_missing_ablation_blocks_but_skip_keeps_legacy_behaviour():
    assert not gate_strategy(good_audit(), good_bt(), "BTC/USDT", ablation=None).allowed
    assert gate_strategy(good_audit(), good_bt(), "BTC/USDT").allowed          # legacy call signature unchanged


def test_code_hash_mismatch_blocks(tmp_path):
    rep = abl(FIXED, tmp_path)
    rep["strategy_sha256"] = "a" * 64
    bt = good_bt()
    bt["strategy_sha256"] = "b" * 64
    d = gate_strategy(good_audit(), bt, "BTC/USDT", ablation=rep)
    assert not d.allowed and any(x.startswith("EVIDENCE_CODE_MISMATCH") for x in d.reasons)


def test_ablation_is_deterministic(tmp_path):
    a, b = abl(FIXED, tmp_path), abl(FIXED, tmp_path)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_helpers():
    assert declared_rules({"a_rule": "x", "b_rule": "y"}) == ["a_rule", "b_rule"]
    assert declared_rules(["a_rule"]) == ["a_rule"]
    for bad in ({}, [], ["Bad Name"], ["a_rule", "a_rule"], 5):
        with pytest.raises(ValueError):
            declared_rules(bad)
    assert hypothesis_rule_names({"rules": [{"name": "x_y", "kind": "entry", "description": "d"}]}) == ["x_y"]
    assert hypothesis_rule_names({}) == []
    assert "DEAD" in summarize({"status": "ok", "rules": [1], "effective_rules": [], "dead_rules": ["r"], "weak_rules": [],
                                "undeclared_hypothesis_rules": []})
    assert "unavailable" in summarize(None)
