import numpy as np
import pytest

from chart_predictor.micro_sweep_m2 import (
    FOLDS, _metrics, _new_agg, _no_trade_candidates, _score_dynamic,
    _validate_frequency_report,
    _score_scalar, _signal_array,
)
from chart_predictor.micro_sweep_feasibility import candidate_side


def _bars():
    t = np.arange(40, dtype=np.int64) * 60_000
    o = np.full(40, 100.0)
    h = np.full(40, 100.2)
    low = np.full(40, 99.8)
    c = np.full(40, 100.0)
    return t, o, h, low, c


def test_vector_signal_matches_frozen_scalar_predicate():
    t, o, h, low, c = _bars()
    o[1], h[1], low[1], c[1] = 100.0, 110.0, 90.0, 95.0
    o[2], h[2], low[2], c[2] = 95.0, 105.0, 89.0, 101.0
    valid = np.ones(len(t), dtype=bool)
    contiguous = np.r_[False, np.diff(t) == 60_000]
    signals = _signal_array(o, h, low, c, valid, contiguous)
    assert signals[2] == candidate_side(tuple(x[1] for x in (o, h, low, c)),
                                        tuple(x[2] for x in (o, h, low, c))) == 1


def test_dynamic_vector_and_scalar_target_first_match():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    h[12] = 100.6
    indexes = np.array([10], dtype=np.int64)
    sides = np.array([1], dtype=np.int8)
    stops = np.array([99.5])
    fast = _score_dynamic(t, o, h, low, c, indexes, sides, stops, 5, "X")[0]
    slow = _score_scalar(t, o, h, low, c, 10, 1, 5)
    assert fast[0] == 1 and fast[1] == 1
    assert tuple(fast[i] for i in (0, 1, 2, 3, 6)) == tuple(int(slow[i]) for i in (0, 1, 2, 3, 6))
    assert fast[4] == slow[4]
    assert fast[5] == slow[5]


def test_same_bar_stop_target_tie_is_stop_first():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    h[11], low[11] = 100.6, 99.4
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    assert fast[0] == 1 and fast[1] == 0


def test_short_same_bar_stop_target_tie_is_stop_first():
    t, o, h, low, c = _bars()
    h[10] = 100.5
    low[11], h[11] = 99.4, 100.6
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([-1]),
                          np.array([100.5]), 5, "X")[0]
    slow = _score_scalar(t, o, h, low, c, 10, -1, 5)
    assert fast[0] == 1 and fast[1] == 0
    assert fast[4] == slow[4]


def test_adverse_stop_gap_uses_worse_open():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    o[12], h[12], low[12], c[12] = 98.9, 99.0, 98.8, 98.95
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    slow = _score_scalar(t, o, h, low, c, 10, 1, 5)
    assert fast[0] == 1 and fast[1] == 0
    assert fast[4] == slow[4]
    assert fast[4] < -1.9


def test_adverse_short_stop_gap_uses_worse_open():
    t, o, h, low, c = _bars()
    h[10] = 100.5
    o[12], h[12], low[12], c[12] = 101.0, 101.2, 100.8, 101.05
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([-1]),
                          np.array([100.5]), 5, "X")[0]
    slow = _score_scalar(t, o, h, low, c, 10, -1, 5)
    assert fast[0] == 1 and fast[1] == 0
    assert fast[4] == slow[4]
    assert fast[4] < -1.9


def test_target_gap_fills_at_barrier_not_better_open():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    o[12], h[12], low[12], c[12] = 101.0, 101.2, 100.8, 101.1
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    slow = _score_scalar(t, o, h, low, c, 10, 1, 5)
    assert fast[1] == 1
    assert fast[4] == slow[4]
    assert fast[4] == pytest.approx(0.72)


def test_entry_at_or_beyond_stop_is_resolved_no_trade_failure():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    o[11] = 99.4
    low[11] = 99.3
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    slow = _score_scalar(t, o, h, low, c, 10, 1, 5)
    assert fast[0] == 1 and fast[1] == 0 and fast[6] == 1
    assert slow[0] is True and slow[6] is True


def test_missing_or_malformed_outcome_path_is_unresolved():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    t[13] += 1
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    assert fast[0] == 0
    t, o, h, low, c = _bars()
    low[10] = 99.5
    h[12] = 98.0
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    assert fast[0] == 0


def test_missing_or_malformed_entry_bar_is_unresolved():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    t[11] += 1
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    assert fast[0] == 0
    t, o, h, low, c = _bars()
    low[10] = 99.5
    h[11] = 98.0
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    assert fast[0] == 0


def test_timeout_is_resolved_and_costs_reduce_net_r():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    fast = _score_dynamic(t, o, h, low, c, np.array([10]), np.array([1]),
                          np.array([99.5]), 5, "X")[0]
    slow = _score_scalar(t, o, h, low, c, 10, 1, 5)
    assert fast[0] == 1 and fast[1] == 0 and fast[2] == 1
    assert fast[4] == pytest.approx(slow[4])
    assert fast[4] == pytest.approx(-0.28)
    assert fast[5] == pytest.approx(slow[5])
    assert fast[5] == pytest.approx(-0.56)


def test_path_ending_exactly_at_horizon_is_resolved_but_truncated_path_is_not():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    full = _score_dynamic(t[:16], o[:16], h[:16], low[:16], c[:16],
                          np.array([10]), np.array([1]), np.array([99.5]), 5, "X")[0]
    truncated = _score_dynamic(t[:15], o[:15], h[:15], low[:15], c[:15],
                               np.array([10]), np.array([1]), np.array([99.5]), 5, "X")[0]
    assert full[0] == 1 and full[2] == 1
    assert truncated[0] == 0


def test_no_trade_audit_selector_returns_first_resolved_no_trade_anchor():
    t, o, h, low, c = _bars()
    low[10] = 99.5
    o[11], low[11] = 99.4, 99.3
    indexes = np.array([10, 15], dtype=np.int64)
    sides = np.array([1, 1], dtype=np.int8)
    selected = _no_trade_candidates(t, o, h, low, c, indexes, sides)
    assert selected.tolist() == [10]


def test_nonoverlap_metric_does_not_fabricate_uncomputed_baselines():
    agg = _new_agg()
    agg.update({"issued": 10, "resolved": 10, "wins": 8,
                "tradable_resolved": 10, "base_r": 1.0, "stress_r": -1.0})
    metrics = _metrics(agg)
    assert metrics["target_first_all_issued"] == 0.8
    assert metrics["matched_momentum_all_issued"] is None
    assert metrics["matched_random_all_issued"] is None


def test_no_trade_events_are_in_m2_but_not_tradable_path_accuracy_denominator():
    agg = _new_agg()
    agg.update({"issued": 10, "resolved": 10, "wins": 7,
                "tradable_resolved": 8, "no_trade": 2,
                "base_r": 1.0, "stress_r": -1.0})
    metrics = _metrics(agg, momentum_wins=6, random_wins=5)
    assert metrics["target_first_all_issued"] == 0.7
    assert metrics["target_first_resolved_trades"] == 0.875


def test_decision_gate_handles_unavailable_comparator_metrics():
    from chart_predictor.micro_sweep_m2 import _claim

    candidate = {"target_first_all_issued": 0.8,
                 "matched_momentum_all_issued": None,
                 "matched_random_all_issued": None,
                 "path_resolution": 0.99, "mean_net_r_base": 0.1,
                 "n_no_trade": 0}
    independent = {"n_issued": 200, "n_symbols": 20}
    audit = {"resolved_samples": 1, "tradable_samples": 1,
             "no_trade_samples": 0, "no_trade_mismatches": 0,
             "label_mismatches": 0, "max_abs_net_r_error": 0.0,
             "max_abs_stress_net_r_error": 0.0}
    result = _claim(candidate, independent, {}, audit)
    assert result["performance_gates"]["not_below_matched_random"] is False


def test_present_no_trade_events_require_a_scalar_no_trade_audit():
    from chart_predictor.micro_sweep_m2 import _claim

    candidate = {"target_first_all_issued": 0.80,
                 "matched_momentum_all_issued": 0.80,
                 "matched_random_all_issued": 0.79,
                 "path_resolution": 0.99, "mean_net_r_base": 0.1,
                 "n_no_trade": 1}
    independent = {"n_issued": 200, "n_symbols": 20}
    audit = {"resolved_samples": 1, "tradable_samples": 1,
             "no_trade_samples": 0, "no_trade_mismatches": 0,
             "label_mismatches": 0, "max_abs_net_r_error": 0.0,
             "max_abs_stress_net_r_error": 0.0}
    result = _claim(candidate, independent, {}, audit)
    assert result["decision"] == "INCONCLUSIVE_DATA_GATES"


def _frequency_report():
    per_symbol = []
    for symbol_number in range(100):
        per_symbol.append({
            "symbol": f"S{symbol_number:03d}",
            "folds": {str(i + 1): {
                "eligible_pairs": 100, "signals": 3, "long": 2, "short": 1,
                "nonoverlap_10m": 2, "nonoverlap_20m": 2,
            } for i in range(len(FOLDS))},
        })
    folds = [{"start_utc": start, "end_utc": end,
              "eligible_pairs": 10_000, "signals": 300, "long": 200,
              "short": 100, "coverage": 0.03, "nonoverlap_n": 200,
              "nonoverlap_symbols": 100} for start, end in FOLDS]
    horizon = {"frequency_gate_pass": True,
               "decision": "READY_FOR_OUTCOME_PREREG",
               "nonoverlap_n": 1_000, "nonoverlap_symbols": 100,
               "eligible_pairs": 50_000, "signals": 1_500,
               "coverage": 0.03, "folds": folds}
    return {
        "protocol": "micro-candle-phase6-sweep-reclaim-frequency-only",
        "database_sha256": "db-sha", "database_bytes": 123,
        "completed_through_utc": "2026-11-14T00:29:00Z", "symbols": 100,
        "candidate": ("bar2 sweeps exactly one bar1 extreme, then closes inside bar1 range "
                      "and beyond its midpoint; entry and outcomes not evaluated"),
        "implementation_source_sha256": {
            "frequency_screen": "freq-code-sha",
            "timestamp_and_nonoverlap_helper": "helper-code-sha",
        },
        "outcome_rows_read": 0, "target_stop_labels_read": 0,
        "horizons": {"10m": horizon, "20m": horizon},
        "per_symbol": per_symbol,
    }


def test_outcome_runner_requires_matching_label_blind_frequency_pass():
    report = _frequency_report()
    validated = _validate_frequency_report(report, "db-sha", 123,
                                           "freq-code-sha", "helper-code-sha")
    assert validated["10m"]["nonoverlap_n"] == 1_000
    report["horizons"]["20m"]["frequency_gate_pass"] = False
    with pytest.raises(ValueError, match="frequency gate"):
        _validate_frequency_report(report, "db-sha", 123,
                                   "freq-code-sha", "helper-code-sha")


def test_frequency_preflight_rejects_wrong_snapshot_or_side_totals():
    report = _frequency_report()
    with pytest.raises(ValueError, match="snapshot identity"):
        _validate_frequency_report(report, "other-sha", 123,
                                   "freq-code-sha", "helper-code-sha")
    report = _frequency_report()
    report["horizons"]["10m"]["folds"][0]["short"] = 29
    with pytest.raises(ValueError, match="side counts"):
        _validate_frequency_report(report, "db-sha", 123,
                                   "freq-code-sha", "helper-code-sha")


def test_frequency_preflight_rejects_changed_screen_implementation():
    report = _frequency_report()
    with pytest.raises(ValueError, match="implementation fingerprint"):
        _validate_frequency_report(report, "db-sha", 123,
                                   "changed-code-sha", "helper-code-sha")
