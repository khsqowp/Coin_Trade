import hashlib

import numpy as np

from scripts.research.cvd_divergence_engine import HOUR_MS, MarketSeries
from scripts.research.cvd_taker_divergence_probe import (
    _fixed_clusters,
    _sha_side,
    _candidate_anchor_invalid,
    _mark_incomplete_path_cell,
    _validate_gate_inputs,
    _validate_review_gate,
    score_baseline_anchor,
    score_event,
)


def test_sha_direction_uses_frozen_first_digest_byte_lsb():
    symbol, entry = "BTCUSDT", 1_700_000_000_000
    digest = hashlib.sha256(f"20261120|{symbol}|{entry}".encode()).digest()
    expected = "long" if digest[0] & 1 == 0 else "short"
    assert _sha_side(symbol, entry) == expected


def test_invalid_candidate_anchor_is_not_a_baseline_comparison_win():
    times = np.arange(20, dtype=np.int64) * HOUR_MS
    highs, lows = np.full(20, 100.5), np.full(20, 99.5)
    lows[0] = 96.5  # the short control would hit its 3% target absent the candidate-anchor gate
    data = MarketSeries(times, np.full(20, 100.0), highs,
                        lows, np.full(20, 100.0),
                        np.full(20, 10.0), np.full(20, 5.0))
    event = {"entry_idx": 0, "entry_open_ms": 0, "side": "long",
             "pivot2_price": 102.0, "atr_at_confirmation": 4.0}
    assert _candidate_anchor_invalid(data, event) is True
    candidate = score_event(data, np.array([], dtype=np.int64), np.array([]), event,
                            side="long", horizon=10)
    unconstrained_short = score_event(data, np.array([], dtype=np.int64), np.array([]), event,
                                      side="short", horizon=10)
    baseline = score_baseline_anchor(data, np.array([], dtype=np.int64), np.array([]), event,
                                     side="short", horizon=10)
    assert candidate["reason"] == "INVALID_ENTRY"
    assert candidate["m2_hit"] is False and candidate["net_base"] == 0.0
    assert unconstrained_short["reason"] == "TARGET" and unconstrained_short["m2_hit"] is True
    assert baseline["reason"] == "INVALID_ENTRY"
    assert baseline["m2_hit"] is False and baseline["net_base"] == 0.0


def test_path_gap_makes_the_entire_affected_inference_cell_not_evaluable():
    result = _mark_incomplete_path_cell(
        {"status": "PASS", "simultaneous_lower": 0.1}, [{"reason": "DATA_GAP"}])
    assert result["status"] == "NOT_EVALUABLE"
    assert result["simultaneous_lower"] == 0.1


def test_fixed_nonoverlap_clusters_use_entry_timestamps_not_realized_exits():
    events = {
        "cvd": [{"entry_open_ms": stamp} for stamp in (0, 19 * HOUR_MS, 20 * HOUR_MS, 41 * HOUR_MS)],
        "price_only": [{"entry_open_ms": 39 * HOUR_MS}],
    }
    assert _fixed_clusters(events) == [0, 20 * HOUR_MS, 41 * HOUR_MS]


def test_score_event_resolves_candidate_risk_and_cost_on_synthetic_path():
    times = np.arange(20, dtype=np.int64) * HOUR_MS
    opens = np.full(20, 100.0)
    highs = np.full(20, 100.5)
    lows = np.full(20, 99.5)
    closes = np.full(20, 100.0)
    highs[0] = 102.5
    data = MarketSeries(times, opens, highs, lows, closes,
                        np.full(20, 10.0), np.full(20, 5.0))
    event = {"entry_idx": 0, "entry_open_ms": 0, "side": "long",
             "pivot2_price": 99.0, "atr_at_confirmation": 4.0}
    result = score_event(data, np.array([], dtype=np.int64), np.array([]), event,
                         side="long", horizon=10)
    assert result["reason"] == "TARGET"
    assert result["m2_hit"] is True
    assert result["entry"] == 100.0
    assert result["stop"] == 98.0
    assert result["target"] == 102.0
    assert result["net_base"] < result["gross_return"]
    assert result["net_base_ex_exit_candle_funding"] == result["net_base"]


def test_time_eligible_missing_future_bar_is_gap_miss_with_undefined_m1():
    times = np.arange(20, dtype=np.int64) * HOUR_MS
    times[5:] += HOUR_MS
    opens = np.full(20, 100.0)
    highs = np.full(20, 100.5)
    lows = np.full(20, 99.5)
    closes = np.full(20, 100.0)
    data = MarketSeries(times, opens, highs, lows, closes,
                        np.full(20, 10.0), np.full(20, 5.0))
    event = {"entry_idx": 0, "entry_open_ms": 0, "side": "long",
             "pivot2_price": 99.0, "atr_at_confirmation": 4.0}
    result = score_event(data, np.array([], dtype=np.int64), np.array([]), event,
                         side="long", horizon=10)
    assert result["reason"] == "DATA_GAP"
    assert result["m2_hit"] is False
    assert result["m1_hit"] is None
    assert result["net_base"] is None


def test_missing_next_open_is_not_replaced_by_a_later_observed_entry():
    data = MarketSeries(np.array([0, 2 * HOUR_MS], dtype=np.int64),
                        np.array([100.0, 101.0]), np.array([101.0, 102.0]),
                        np.array([99.0, 100.0]), np.array([100.0, 101.0]),
                        np.array([10.0, 10.0]), np.array([5.0, 5.0]))
    event = {"entry_idx": None, "entry_open_ms": HOUR_MS, "side": "long",
             "pivot2_price": 99.0, "atr_at_confirmation": 4.0}
    result = score_event(data, np.array([], dtype=np.int64), np.array([]), event,
                         side="long", horizon=10)
    assert result["reason"] == "MISSING_ENTRY_BAR"
    assert result["m2_hit"] is False
    assert result["m1_hit"] is None
    assert result["net_base"] is None


def test_pre_score_gate_requires_exact_archive_and_funding_audit_records():
    symbols = [f"S{i:02d}" for i in range(36)]
    months = [f"2023-{month:02d}" for month in range(3, 13)] + [
        f"{year}-{month:02d}" for year in (2024, 2025)
        for month in (range(1, 13) if year == 2024 else range(1, 3))
    ]
    archives = [{"kind": kind, "symbol": symbol, "month": month, "status": "PASS",
                 **({"boundary_checked": True, "utc_grid_checked": True} if kind == "funding" else {})}
                for kind in ("klines_1h", "funding") for symbol in symbols for month in months]
    input_audit = {"status": "PASS", "archive_records": 1728,
                   "funding_month_boundary_checks": len(symbols) * len(months), "records": archives}
    dates = ["2023-03-24", "2024-03-24", "2025-02-28"]
    funding_records = [{"symbol": symbol, "date_utc": day, "status": "PASS", "http_status": 200,
                        "response_sha256": "a" * 64, "archive_rows": 3, "api_rows": 3,
                        "timestamp_matches": 3, "exact_rate_matches": 3,
                        "archive_only_timestamps": [], "api_only_timestamps": [],
                        "duplicate_archive_timestamps": False, "duplicate_api_timestamps": False}
                       for symbol in symbols for day in dates]
    funding_audit = {"status": "PASS", "sample_count": 108, "dates_utc": dates,
                     "symbols": symbols, "endpoint": "https://fapi.binance.com/fapi/v1/fundingRate",
                     "records": funding_records}
    _validate_gate_inputs(input_audit, funding_audit, symbols, months)
    first_funding_record = next(r for r in input_audit["records"] if r["kind"] == "funding")
    first_funding_record.pop("boundary_checked")
    try:
        _validate_gate_inputs(input_audit, funding_audit, symbols, months)
        assert False, "funding boundary audit must be mandatory"
    except ValueError as exc:
        assert "UTC-grid/month-boundary" in str(exc)
    first_funding_record["boundary_checked"] = True
    funding_records[0]["exact_rate_matches"] = 2
    try:
        _validate_gate_inputs(input_audit, funding_audit, symbols, months)
        assert False, "mismatched funding audit must fail closed"
    except ValueError as exc:
        assert "funding audit detail" in str(exc)


def test_review_gate_binds_all_four_roles_to_exact_inputs_and_code():
    sources, preregs = {"probe.py": "source-hash"}, {"v7.md": "prereg-hash"}
    reviews = [{"role": role, "verdict": "PASS", "scoring_approval": True,
                "source_hashes": sources, "preregistration_hashes": preregs,
                "input_audit_sha256": "i" * 64, "funding_audit_sha256": "f" * 64}
               for role in ("BLUE", "RED", "METHODS", "JUDGE")]
    _validate_review_gate({"reviews": reviews}, sources, preregs, "i" * 64, "f" * 64)
    reviews[0]["source_hashes"] = {"probe.py": "stale"}
    try:
        _validate_review_gate({"reviews": reviews}, sources, preregs, "i" * 64, "f" * 64)
        assert False, "stale reviewed code hash must fail closed"
    except ValueError as exc:
        assert "source hashes differ" in str(exc)
