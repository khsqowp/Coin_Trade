import numpy as np
import sqlite3

from chart_predictor.micro_maru_m2 import (
    _claim_decision,
    _eligible_signal_indexes,
    _load_symbol,
    _nonoverlap_indexes,
    _signal_from_ohlc,
)


def test_body_dominance_signal_includes_exact_eighty_percent_boundary():
    signals = _signal_from_ohlc(
        np.array([100.0, 110.0, 100.0, 100.0]),
        np.array([110.0, 110.0, 110.0, 110.0]),
        np.array([100.0, 100.0, 100.0, 100.0]),
        np.array([108.0, 102.0, 107.999, 100.0]),
    )
    assert signals.tolist() == [1, -1, 0, 0]


def test_invalid_nonfinite_and_zero_range_candles_never_emit():
    signals = _signal_from_ohlc(
        np.array([100.0, 100.0, np.nan]),
        np.array([100.0, 110.0, 110.0]),
        np.array([100.0, 100.0, 100.0]),
        np.array([100.0, 108.0, 108.0]),
    )
    assert signals.tolist() == [0, 1, 0]


def test_nonoverlap_selector_accepts_signal_at_exact_horizon_boundary():
    indexes = np.array([0, 9, 10, 19, 20, 21], dtype=np.int64)
    timestamps = np.arange(30, dtype=np.int64) * 60_000
    selected = _nonoverlap_indexes(indexes, 10, timestamps)
    assert selected.tolist() == [0, 10, 20]
    for prior, current in zip(selected, selected[1:]):
        prior_outcome_bars = set(range(prior + 1, prior + 11))
        current_outcome_bars = set(range(current + 1, current + 11))
        assert prior_outcome_bars.isdisjoint(current_outcome_bars)


def test_nonoverlap_selector_uses_elapsed_minutes_across_gaps():
    indexes = np.array([0, 1, 2], dtype=np.int64)
    timestamps = np.array([0, 60_000, 10 * 60_000], dtype=np.int64)
    selected = _nonoverlap_indexes(indexes, 10, timestamps)
    assert selected.tolist() == [0, 2]


def test_coverage_numerator_requires_atr_but_all_issued_denominator_does_not():
    indexes = np.array([2, 5, 8], dtype=np.int64)
    atr = np.array([np.nan, np.nan, np.nan, np.nan, np.nan,
                    1.0, np.nan, np.nan, 2.0])
    valid = np.array([False, False, True, False, False, True, False, False, True])
    high = np.full(9, 101.0)
    low = np.full(9, 99.0)
    eligible_issued = _eligible_signal_indexes(indexes, atr, valid, high, low)
    assert len(indexes) == 3  # all emitted signals stay in M2 denominator
    assert eligible_issued.tolist() == [5, 8]  # only these count toward coverage


def test_fold_truncation_keeps_crossing_path_unresolved():
    from chart_predictor.micro_candle_m2 import score_chunk

    t = np.arange(40, dtype=np.int64) * 60_000
    o = np.full(40, 100.0)
    h = np.full(40, 100.5)
    low = np.full(40, 99.5)
    c = np.full(40, 100.0)
    atr = np.ones(40)
    anchor = 24
    full = score_chunk(t, o, h, low, c, atr, np.array([anchor]),
                       np.array([1], dtype=np.int8), 10, "X")
    truncated = score_chunk(t[:34], o[:34], h[:34], low[:34], c[:34], atr[:34],
                            np.array([anchor]), np.array([1], dtype=np.int8), 10, "X")
    assert full[0, 0] == 1
    assert truncated[0, 0] == 0


def _gate_inputs(m2=0.80, resolution=0.95, count=200, symbol_count=20):
    candidate = {
        "target_first_all_issued": m2,
        "matched_momentum_all_issued": m2,
        "matched_random_all_issued": 0.79,
        "path_resolution": resolution,
        "mean_net_r_base": 0.01,
    }
    nonoverlap = {"n_issued": count, "n_symbols": symbol_count}
    coverage = {"rate": 0.10}
    return candidate, nonoverlap, coverage


def test_primary_gates_pass_at_fixed_boundaries_but_remain_review_required():
    audit = {"sampled": 12, "label_mismatches": 0,
             "resolved_samples": 3,
             "max_abs_net_r_error": 0.0,
             "max_abs_stress_net_r_error": 0.0}
    result = _claim_decision(*_gate_inputs(), audit)
    assert result["decision"] == "PRIMARY_SCREEN_SURVIVOR_REVIEW_REQUIRED"
    assert result["statistical_inference_complete"] is False
    assert result["independent_oos"] is False


def test_failed_data_gate_is_inconclusive_not_performance_reject():
    audit = {"sampled": 12, "label_mismatches": 0,
             "resolved_samples": 3,
             "max_abs_net_r_error": 0.0,
             "max_abs_stress_net_r_error": 0.0}
    result = _claim_decision(*_gate_inputs(resolution=0.949), audit)
    assert result["decision"] == "INCONCLUSIVE_DATA_GATES"


def test_scalar_vectorized_audit_failure_is_inconclusive():
    candidate, independent, coverage = _gate_inputs()
    audit = {"sampled": 12, "label_mismatches": 1,
             "resolved_samples": 3,
             "max_abs_net_r_error": 0.0,
             "max_abs_stress_net_r_error": 0.0}
    result = _claim_decision(candidate, independent, coverage, audit)
    assert result["decision"] == "INCONCLUSIVE_DATA_GATES"
    assert result["data_gates"]["scalar_audit_pass"] is False


def test_m2_below_eighty_rejects_after_data_gates_pass():
    candidate, independent, coverage = _gate_inputs(m2=0.799)
    audit = {"sampled": 12, "label_mismatches": 0,
             "resolved_samples": 3,
             "max_abs_net_r_error": 0.0,
             "max_abs_stress_net_r_error": 0.0}
    result = _claim_decision(candidate, independent, coverage, audit)
    assert result["decision"] == "REJECT_PRIMARY_SCREEN"


def test_scalar_audit_with_zero_resolved_samples_cannot_pass():
    candidate, independent, coverage = _gate_inputs()
    audit = {"sampled": 12, "resolved_samples": 0,
             "label_mismatches": 0, "max_abs_net_r_error": 0.0,
             "max_abs_stress_net_r_error": 0.0}
    result = _claim_decision(candidate, independent, coverage, audit)
    assert result["decision"] == "INCONCLUSIVE_DATA_GATES"


def test_invalid_ohlc_and_missing_minute_remain_path_breaks_not_global_abort():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE candles(symbol TEXT, t_open_ms INTEGER, o REAL, h REAL, l REAL, c REAL)")
    rows = []
    for i in range(42):
        minute = i if i < 20 else i + 1  # missing minute 20
        low, high = 99.0, 101.0
        if i == 10:
            high = 98.0  # malformed: high below open/close
        rows.append(("X", minute * 60_000, 100.0, high, low, 100.5))
    db.executemany("INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?)", rows)
    t, o, h, low, c, atr, signal, valid = _load_symbol(db, "X", 43 * 60_000)
    assert len(t) == len(rows)
    assert not bool(valid[10])
    assert signal[10] == 0
    assert np.isnan(atr[10])
    assert np.isnan(atr[21])  # ATR cannot bridge the missing timestamp
    assert not np.all(valid)
    db.close()
