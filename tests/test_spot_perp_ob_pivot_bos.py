import json
from types import SimpleNamespace

import numpy as np

from scripts.research.spot_perp_ob_pivot_bos import (
    CUTOFF_MS,
    PANEL_REVIEWER_IDS,
    block_bootstrap,
    development_screen,
    find_bos,
    global_nonoverlap_count,
    is_confirmed_pivot,
    score_trade,
    _eligible_mask,
    _invalid_ohlc_bar_count,
    _committed_blob_sha,
    _write_data_invalid,
    first_touch_conversion_metrics,
    signal_anchor_coverage,
    unique_signal_anchor_count,
)
from scripts.research.audit_ob_pivot_bos_cost_inputs import (
    funding_interval_gaps,
    minute_grid_gaps,
)
from scripts.research.spot_perp_ob_pivot_bos import (
    EXPECTED_COST_AUDIT_SHA256,
    load_supporting_cost_audit,
    validate_supporting_cost_audit,
)


def _bars(n=80, close=100.0):
    return {
        "time": np.arange(n, dtype=np.int64) * 60_000,
        "open": np.full(n, close, dtype=float),
        "high": np.full(n, close + .2, dtype=float),
        "low": np.full(n, close - .2, dtype=float),
        "close": np.full(n, close, dtype=float),
        "volume": np.ones(n, dtype=float),
    }


def _five(n=16, close=100.0):
    return {"close": np.full(n, close, dtype=float),
            "low": np.full(n, close - .2, dtype=float),
            "high": np.full(n, close + .2, dtype=float)}


def test_pivot_uses_two_closed_right_bars_and_cannot_center_on_touch_or_before():
    one = _bars()
    one["high"][7] = 101.0
    assert not is_confirmed_pivot(one["high"], one["low"], 7, "long", arm_start=8)
    assert is_confirmed_pivot(one["high"], one["low"], 7, "long", arm_start=5)
    assert not is_confirmed_pivot(one["high"], one["low"], 7, "long", arm_start=6)


def test_bos_must_be_after_confirmation_and_inside_ten_bar_window():
    one, five = _bars(), _five()
    one["high"][7] = 101.0
    one["close"][10] = 102.0
    one["high"][10] = 102.2
    event = {"index": 0, "side": "long", "zone_low": 90.0, "zone_high": 95.0}
    result = find_bos(event, one, five)
    assert result["status"] == "BOS"
    assert result["signal_index"] == 10  # pivot confirms at 9; BOS is the next close
    assert result["stop"] == min(five["low"][0], np.min(one["low"][5:11]))


def test_no_bos_after_fixed_window_is_an_unissued_arm():
    one, five = _bars(), _five()
    one["high"][7] = 101.0
    one["close"][15] = 103.0
    event = {"index": 0, "side": "long", "zone_low": 90.0, "zone_high": 95.0}
    assert find_bos(event, one, five)["status"] == "NO_BOS"


def test_prior_five_minute_close_invalidation_cancels_pending_arm():
    one, five = _bars(), _five()
    one["high"][7] = 101.0
    one["close"][10] = 102.0
    one["high"][10] = 102.2
    five["close"][1] = 89.0  # 5m close at minute 10, before the later BOS.
    event = {"index": 0, "side": "long", "zone_low": 90.0, "zone_high": 95.0}
    assert find_bos(event, one, five)["status"] == "INVALIDATED"


def test_nonfinite_five_minute_invalidation_close_is_data_defect():
    one, five = _bars(), _five()
    five["close"][1] = np.nan
    event = {"index": 0, "side": "long", "zone_low": 90.0, "zone_high": 95.0}
    assert find_bos(event, one, five)["status"] == "DATA_DEFECT"


def test_incomplete_five_minute_bar_in_cutoff_tail_still_invalidates_screen():
    times = np.array([CUTOFF_MS - 10 * 60_000, CUTOFF_MS - 5 * 60_000], dtype=np.int64)
    bars = {"time": times, "open": np.ones(2), "high": np.ones(2),
            "low": np.ones(2), "close": np.ones(2), "volume": np.ones(2)}
    bars["close"][1] = np.nan
    eligible, _, invalid, _ = _eligible_mask(bars, np.ones(2))
    assert not eligible[1]
    assert invalid == 1


def test_data_invalid_output_suppresses_all_economic_scores_and_ledgers(tmp_path):
    args = SimpleNamespace(output_dir=tmp_path / "screen")
    result = _write_data_invalid(
        args, input_sha="input", prereg_sha="prereg", code_sha="code",
        freeze={"code_commit_sha": "code-commit", "_observed_freeze_commit_sha": "freeze-commit"},
        preflight={"invalid_5m_bars": 1, "invalid_ohlc_bars": 0, "eligible_anchors": 10,
                   "invalid_5m_bars_by_symbol": {"X": 1},
                   "invalid_ohlc_bars_by_symbol": {"X": 0},
                   "eligible_anchors_by_symbol": {"X": 10}},
    )
    saved = json.loads((args.output_dir / "metrics.json").read_text())
    assert result["status"] == saved["status"] == "DATA_INVALID"
    assert saved["economic_scoring"] == "NOT_RUN_OR_SUPPRESSED"
    assert saved["trade_ledgers_written"] is False
    assert "issued_m2_rate" not in saved
    assert not (args.output_dir / "arm_ledger.jsonl.gz").exists()


def test_finite_but_invalid_ohlc_minute_is_counted_as_data_defect():
    minute = _bars(n=4)
    minute["high"][2] = minute["close"][2] - 1.0
    assert _invalid_ohlc_bar_count(minute) == 1


def test_missing_confirmation_minute_is_a_data_defect_not_a_silent_no_signal():
    one, five = _bars(), _five()
    one["close"][6] = np.nan
    event = {"index": 0, "side": "long", "zone_low": 90.0, "zone_high": 95.0}
    assert find_bos(event, one, five)["status"] == "DATA_DEFECT"


def test_triple_barrier_stop_first_and_gap_fills_are_conservative():
    one = _bars(close=100.0)
    event = {"side": "long", "atr_1m": .1}
    # Entry 100, stop 99, target 102; both touched in first minute => stop first.
    one["high"][1], one["low"][1] = 103.0, 98.0
    dual = score_trade(event, one, entry_index=1, stop=99.0, signal_index=0)
    assert dual["exit_reason"] == "STOP"
    assert not dual["m2_hit"]
    assert dual["net_return_base"] < 0

    one = _bars(close=100.0)
    one["open"][1] = 98.0
    gap = score_trade(event, one, entry_index=1, stop=99.0, signal_index=0)
    assert gap["exit_reason"] == "NON_EXECUTABLE"
    assert not gap["m2_hit"]
    assert gap["net_return_stress"] == 0.0

    one = _bars(close=100.0)
    one["open"][2] = 98.0
    stop_gap = score_trade(event, one, entry_index=1, stop=99.0, signal_index=0)
    assert stop_gap["exit_reason"] == "STOP_GAP"
    assert stop_gap["exit_price"] == 98.0

    one = _bars(close=100.0)
    one["open"][2] = 103.0
    target_gap = score_trade(event, one, entry_index=1, stop=99.0, signal_index=0)
    assert target_gap["exit_reason"] == "TARGET_GAP"
    assert target_gap["exit_price"] == target_gap["target"]


def test_market_wide_nonoverlap_counts_only_nonoverlapping_20m_intervals():
    rows = [
        {"signal_time_ms": 0, "symbol": "BTCUSDT", "side": "long"},
        {"signal_time_ms": 0, "symbol": "ETHUSDT", "side": "long"},
        {"signal_time_ms": 19 * 60_000, "symbol": "SOLUSDT", "side": "short"},
        {"signal_time_ms": 20 * 60_000, "symbol": "XRPUSDT", "side": "long"},
    ]
    assert global_nonoverlap_count(rows) == 2


def test_signal_coverage_counts_unique_symbol_anchor_not_duplicate_rows():
    rows = [
        {"symbol": "BTCUSDT", "anchor_time_ms": 300_000},
        {"symbol": "BTCUSDT", "anchor_time_ms": 300_000},
        {"symbol": "ETHUSDT", "anchor_time_ms": 300_000},
    ]
    assert unique_signal_anchor_count(rows) == 2
    assert signal_anchor_coverage(rows, 20) == (2, 10.0)


def test_arm_conversion_and_distinct_anchor_coverage_use_matching_units():
    arms = [
        {"symbol": "BTCUSDT", "anchor_time_ms": 300_000, "candidate_signal": True,
         "zone_id": "older"},
        {"symbol": "BTCUSDT", "anchor_time_ms": 300_000, "candidate_signal": True,
         "zone_id": "newer"},
    ]
    both_issued = first_touch_conversion_metrics(arms)
    assert both_issued["issuance_per_first_touch_pct"] == 100.0
    assert both_issued["issued_anchor_coverage_per_first_touch_pct"] == 100.0

    arms[1]["candidate_signal"] = False
    one_issued = first_touch_conversion_metrics(arms)
    assert one_issued["issuance_per_first_touch_pct"] == 50.0
    assert one_issued["issued_anchor_coverage_per_first_touch_pct"] == 100.0


def test_cost_input_audit_detects_missing_funding_and_mark_minutes():
    times = np.array([5, 4 * 60 * 60_000 + 5, 12 * 60 * 60_000 + 5], dtype=np.int64)
    intervals = np.array([4, 4, 4], dtype=np.int64)
    gaps = funding_interval_gaps(times, intervals)
    assert len(gaps) == 1
    assert gaps[0]["estimated_missing_events"] == 1

    mark = np.array([0, 60_000, 1441 * 60_000], dtype=np.int64)
    mark_gaps = minute_grid_gaps(mark)
    assert len(mark_gaps) == 1
    assert mark_gaps[0]["missing_minutes"] == 1439


def test_reviewed_cost_audit_is_hash_bound_and_tampering_is_rejected():
    audit, sha = load_supporting_cost_audit()
    assert sha == EXPECTED_COST_AUDIT_SHA256
    assert audit["funding"]["rows"] == 79902
    assert len(audit["funding"]["interval_gap_anomalies"]) == 3
    assert len(audit["mark_price_june_2026"]["grid_gap_anomalies"]) == 32
    audit["funding"]["rows"] += 1
    try:
        validate_supporting_cost_audit(audit)
    except ValueError:
        pass
    else:
        raise AssertionError("tampered audit counts must fail closed")


def test_freeze_blob_hash_is_computed_from_committed_bytes(monkeypatch):
    from scripts.research import spot_perp_ob_pivot_bos as scorer
    import hashlib

    def fake_run(command, **kwargs):
        assert command == ["git", "show", "parent:artifact.json"]
        return SimpleNamespace(stdout=b'{"frozen":true}\n')

    monkeypatch.setattr(scorer.subprocess, "run", fake_run)
    assert _committed_blob_sha("parent", "artifact.json") == hashlib.sha256(
        b'{"frozen":true}\n').hexdigest()


def test_weekly_cluster_bootstrap_is_reproducible_and_paired_by_arm():
    arms = []
    for i in range(8):
        arms.append({"anchor_time_ms": i * 7 * 24 * 60 * 60 * 1000,
                     "candidate_arm_m2": i % 2 == 0,
                     "baseline_m2": False,
                     "candidate_arm_net_base": .01 if i % 2 == 0 else -.01,
                     "candidate_arm_net_stress": .008 if i % 2 == 0 else -.012,
                     "baseline_net_base": -.01, "baseline_net_stress": -.03})
    assert block_bootstrap(arms) == block_bootstrap(arms)
    assert block_bootstrap(arms)["candidate_minus_baseline_arm_m2_ci95"][0] > 0


def test_dev_screen_never_calls_success_approved_without_funding_or_oos():
    metrics = {
        "issued_m2_rate": .85, "issued_n": 300, "symbol_nonoverlap_n": 250,
        "market_time_nonoverlap_n": 220, "issuance_per_first_touch_pct": 20,
        "issued_anchor_coverage_per_first_touch_pct": 15,
        "issued_symbol_count": 20, "max_symbol_issued_share": .20,
        "invalid_5m_bars": 0,
        "arm_mean_net_base": .01, "arm_mean_net_stress": .005, "data_defects": 0,
        "block_bootstrap": {
            "candidate_minus_baseline_arm_m2_ci95": [.01, .2],
            "candidate_minus_baseline_arm_net_base_ci95": [.001, .02],
            "candidate_minus_baseline_arm_net_stress_ci95": [.001, .02],
        },
    }
    assert development_screen(metrics)["status"] == "HOLD_FUNDING_AND_OOS"

    metrics["invalid_5m_bars"] = 1
    assert development_screen(metrics)["checks"]["invalid_5m_bars_zero"] is False
    assert development_screen(metrics)["status"] == "REJECT_DEV"
    metrics["invalid_5m_bars"] = 0
    metrics["block_bootstrap"]["candidate_minus_baseline_arm_net_stress_ci95"] = [-.001, .02]
    assert development_screen(metrics)["checks"]["arm_net_stress_block_bootstrap_lower_above_baseline"] is False
    assert development_screen(metrics)["status"] == "REJECT_DEV"


def test_freeze_uses_actual_reviewer_identifiers_not_inferred_roles():
    assert PANEL_REVIEWER_IDS == {
        "BANACH", "RAMAN", "HARVEY", "SINGER"}
