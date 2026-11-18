import numpy as np
import pytest

from chart_predictor.micro_multiscale import HORIZONS, RULES, SIZES
from chart_predictor.micro_multiscale_m2 import (
    _atr, _scalar_audit_pass, _score_body, _score_one, _score_sweep,
    _verify_frequency_counts,
)


def _bars():
    t = np.arange(6, dtype=np.int64) * 60_000
    open_ = np.array([100., 100., 100., 100., 100., 100.])
    high = np.array([100.5, 102., 100.5, 100.5, 100.5, 100.5])
    low = np.array([99.5, 99.5, 99.5, 99.5, 99.5, 99.5])
    close = np.array([100., 101.5, 100., 100., 100., 100.])
    atr = np.ones(6)
    return t, open_, high, low, close, atr


def test_atr_returns_mutable_masked_array_on_15m_series():
    interval = 15 * 60_000
    t = np.arange(20, dtype=np.int64) * interval
    open_ = np.full(20, 100.0)
    high = np.full(20, 102.0)
    low = np.full(20, 99.0)
    close = np.full(20, 101.0)
    aggregates = {"open_ms": t, "open": open_, "high": high,
                  "low": low, "close": close}

    synthetic_t, atr = _atr(aggregates, interval)

    assert synthetic_t.shape == (20,)
    assert np.isnan(atr[:14]).all()
    assert np.isfinite(atr[14:]).all()


def test_no_trade_audit_sample_required_only_when_no_trade_events_exist():
    audit = {"sampled": 1, "resolved_samples": 1, "tradable_samples": 1,
             "label_mismatches": 0, "no_trade_mismatches": 0,
             "max_abs_net_r_error": 0.0, "max_abs_stress_net_r_error": 0.0,
             "no_trade_samples": 0}

    assert _scalar_audit_pass(audit, "sweep_reclaim", 0)
    assert not _scalar_audit_pass(audit, "sweep_reclaim", 1)


def test_fixed_stop_target_same_bar_tie_is_stop_first_and_scalar_matches():
    t, o, h, low, c, atr = _bars()
    h[1], low[1] = 101.5, 98.5  # target and stop both touch in entry bar
    vector = _score_body(t, o, h, low, c, atr, np.array([0]), np.array([1]), 2, "BTCUSDT")[0]
    scalar = _score_one(t, o, h, low, c, atr, 0, 1, 99., 2, "body_dominance")

    assert vector[0] == 1
    assert vector[1] == 0
    assert scalar[0] is True
    assert scalar[1] is False
    assert abs(vector[4] - scalar[4]) < 1e-12


def test_fixed_target_first_and_timeout_close_match_scalar():
    t, o, h, low, c, atr = _bars()
    vector_target = _score_body(t, o, h, low, c, atr, np.array([0]), np.array([1]), 2, "BTCUSDT")[0]
    scalar_target = _score_one(t, o, h, low, c, atr, 0, 1, 99., 2, "body_dominance")
    assert vector_target[1] == 1
    assert scalar_target[1] is True
    assert abs(vector_target[4] - scalar_target[4]) < 1e-12

    h[1:] = 100.5
    low[1:] = 99.5
    c[1:] = [100.2, 100.3, 100.1, 100.2, 100.1]
    vector_timeout = _score_body(t, o, h, low, c, atr, np.array([0]), np.array([1]), 2, "BTCUSDT")[0]
    scalar_timeout = _score_one(t, o, h, low, c, atr, 0, 1, 99., 2, "body_dominance")
    assert vector_timeout[0] == 1
    assert vector_timeout[1] == 0
    assert vector_timeout[2] == 1
    assert scalar_timeout[2] is True
    assert abs(vector_timeout[4] - scalar_timeout[4]) < 1e-12


def test_sweep_entry_at_or_beyond_bar2_stop_is_no_trade_for_candidate_and_control():
    t, o, h, low, c, _ = _bars()
    low[0] = 100.
    o[1] = 99.
    h[1] = 100.
    low[1] = 98.
    c[1] = 99.
    vector = _score_sweep(t, o, h, low, c, np.array([0]), np.array([1]),
                          np.array([100.]), 2, "BTCUSDT")[0]
    scalar = _score_one(t, o, h, low, c, np.ones(6), 0, 1, 100., 2, "sweep_reclaim")

    assert vector[0] == 1
    assert vector[6] == 1
    assert scalar[0] is True
    assert scalar[6] is True
    assert vector[1] == 0


def _frequency_fixture():
    report = {"per_symbol_fold": {}, "totals": {}}
    recomputed = {}
    for rule in RULES:
        report["per_symbol_fold"][rule] = {}
        report["totals"][rule] = {}
        recomputed[rule] = {}
        for size in SIZES:
            folds = [{
                "fold": i + 1, "start_ms": i * 10, "end_ms": (i + 1) * 10,
                "eligible_anchors": 10, "signals": 1, "coverage": 0.1,
                "long": 1, "short": 0,
                "nonoverlap": {str(h): 1 for h in HORIZONS},
            } for i in range(5)]
            rows = [{"symbol": "BTCUSDT", "folds": folds}]
            recomputed[rule][str(size)] = rows
            report["per_symbol_fold"][rule][str(size)] = rows
            report["totals"][rule][str(size)] = {
                "eligible": 50, "signals": 5, "coverage": 0.1,
                "long": 5, "short": 0,
                "nonoverlap": {str(h): 5 for h in HORIZONS},
                "symbols": {str(h): 1 for h in HORIZONS},
                "horizons": {str(h): {"nonoverlap_n": 5, "nonoverlap_symbols": 1,
                                      "frequency_gate_pass": False} for h in HORIZONS},
            }
    return report, recomputed


def test_frequency_totals_must_reconcile_with_symbol_fold_counts():
    report, recomputed = _frequency_fixture()
    _verify_frequency_counts(report, recomputed)

    report["totals"]["sweep_reclaim"]["3"]["horizons"]["10"]["nonoverlap_n"] = 999
    with pytest.raises(ValueError, match="frequency total reconciliation failed"):
        _verify_frequency_counts(report, recomputed)
