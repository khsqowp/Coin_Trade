from datetime import datetime, timezone

import numpy as np
import pytest

from chart_predictor.indicators import atr
from scripts.research.spot_perp_ob_first_touch import (
    CUTOFF_MS,
    EXPECTED_BRANCH,
    FROZEN_INPUT_SHA256,
    SYMBOLS,
    aggregate_5m,
    development_screen,
    eligible_anchor_mask,
    first_touch_events,
    normalize_month_grid,
    score_m1,
    score_path,
    validate_run_freeze,
)


def _one_5m_bar(timestamp=0, opened=100.0, high=100.5, low=99.5, close=100.1):
    times = timestamp + np.arange(5, dtype=np.int64) * 60_000
    values = np.arange(5, dtype=float)
    return aggregate_5m(times, np.full(5, opened), np.full(5, high + values * 0.01),
                        np.full(5, low - values * 0.01), np.full(5, close), values + 1)


def _zone_fixture(size=90):
    times = np.arange(size, dtype=np.int64) * 300_000
    opened = np.full(size, 101.0)
    close = np.full(size, 101.1)
    high = np.full(size, 101.3)
    low = np.full(size, 100.8)
    # Last opposite-color bar before a causal bullish displacement.
    opened[14], close[14], high[14], low[14] = 100.1, 100.0, 100.5, 99.5
    opened[15], close[15], high[15], low[15] = 100.0, 102.0, 102.2, 99.8
    # First touch at the 60th valid watch bar (born 15, watch indices 16..75).
    opened[75], close[75], high[75], low[75] = 100.2, 100.2, 100.4, 100.0
    perp = {"time": times, "open": opened, "high": high, "low": low, "close": close}
    perp["volume"] = np.ones(size)
    perp["open"][16:75] = 101.0
    spot = {key: value.copy() for key, value in perp.items()}
    spot["close"][75] = 100.6
    spot["high"][75] = 100.7
    atr_values = atr(perp["high"], perp["low"], perp["close"], 14)
    eligible = np.zeros(size, dtype=bool)
    eligible[75] = True
    return perp, spot, atr_values, eligible


def _minute_path(opened, high, low, close, count=100):
    return {"open": np.full(count, opened, dtype=float),
            "high": np.full(count, high, dtype=float),
            "low": np.full(count, low, dtype=float),
            "close": np.full(count, close, dtype=float)}


def test_aggregate_5m_uses_standard_ohlcv_and_rejects_gap():
    bar = _one_5m_bar(timestamp=1_800_000)
    assert bar["time"].tolist() == [1_800_000]
    assert bar["open"].tolist() == [100.0]
    assert bar["high"].tolist() == [100.54]
    assert bar["low"].tolist() == [99.46]
    assert bar["close"].tolist() == [100.1]
    assert bar["volume"].tolist() == [15.0]
    with pytest.raises(ValueError, match="gap"):
        aggregate_5m(np.array([0, 60_000, 120_000, 240_000, 300_000]),
                     *[np.ones(5) for _ in range(5)])


def test_aggregate_5m_marks_any_bucket_with_missing_minute_values_invalid():
    times = np.arange(5, dtype=np.int64) * 60_000
    high = np.full(5, 101.0)
    high[2] = np.nan

    result = aggregate_5m(times, np.full(5, 100.0), high, np.full(5, 99.0),
                          np.full(5, 100.0), np.ones(5))

    assert np.isnan(result["open"][0])
    assert np.isnan(result["high"][0])
    assert np.isnan(result["close"][0])


def test_missing_minute_is_reindexed_as_nan_instead_of_silently_compressed():
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    times = start + np.array([0, 60_000, 180_000], dtype=np.int64)
    columns = {name: np.array([100.0, 101.0, 103.0])
               for name in ("open", "high", "low", "close", "volume")}

    result = normalize_month_grid("2025-01", times, columns)

    assert len(result["time"]) == 31 * 24 * 60
    assert result["close"][:4].tolist()[:2] == [100.0, 101.0]
    assert np.isnan(result["close"][2])
    assert result["close"][3] == 103.0


def test_missing_minute_is_reindexed_as_nan_instead_of_silently_compressed():
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    times = start + np.array([0, 60_000, 180_000], dtype=np.int64)
    columns = {name: np.array([100.0, 101.0, 103.0])
               for name in ("open", "high", "low", "close", "volume")}

    result = normalize_month_grid("2025-01", times, columns)

    assert len(result["time"]) == 31 * 24 * 60
    assert result["close"][:4][0] == 100.0
    assert result["close"][:4][1] == 101.0
    assert np.isnan(result["close"][2])
    assert result["close"][3] == 103.0


def test_first_touch_on_watch_bar_60_is_actionable_and_consumes_zone():
    perp, spot, atr_values, eligible = _zone_fixture()
    perp["open"][76], perp["close"][76], perp["high"][76], perp["low"][76] = 100.2, 100.2, 100.4, 100.0
    spot["close"][76], spot["high"][76] = 100.6, 100.7
    eligible[76] = True

    events, ambiguous, anchors = first_touch_events(perp, spot, atr_values, eligible)

    assert ambiguous == 0
    assert anchors == 2
    assert len(events) == 1
    assert events[0]["index"] == 75
    assert events[0]["side"] == "long"
    assert events[0]["candidate"] is True


def test_unfiltered_baseline_keeps_filter_failure_first_touch():
    perp, spot, atr_values, eligible = _zone_fixture()
    spot["close"][75] = 100.3

    events, _, _ = first_touch_events(perp, spot, atr_values, eligible)

    assert len(events) == 1
    assert events[0]["candidate"] is False


def test_incomplete_spot_touch_anchor_resets_zones_without_silent_consumption():
    perp, spot, atr_values, eligible = _zone_fixture()
    spot["close"][75] = np.nan
    eligible[75] = False
    eligible[76] = True
    perp["open"][76], perp["close"][76], perp["high"][76], perp["low"][76] = 100.2, 100.2, 100.4, 100.0
    spot["close"][76], spot["high"][76] = 100.6, 100.7

    events, _, anchors = first_touch_events(perp, spot, atr_values, eligible)

    assert anchors == 1
    assert events == []


def test_close_invalidation_precedes_same_bar_zone_touch():
    perp, spot, atr_values, eligible = _zone_fixture()
    perp["low"][75], perp["high"][75], perp["close"][75] = 99.0, 100.2, 99.4

    events, _, _ = first_touch_events(perp, spot, atr_values, eligible)

    assert events == []


def test_first_touch_is_prefix_invariant_to_future_mutation():
    perp, spot, atr_values, eligible = _zone_fixture()
    full, _, _ = first_touch_events(perp, spot, atr_values, eligible)
    prefix = {key: values[:76] for key, values in perp.items()}
    prefix_spot = {key: values[:76] for key, values in spot.items()}
    prefix_atr = atr_values[:76]
    prefix_eligible = eligible[:76]
    prefix_result, _, _ = first_touch_events(prefix, prefix_spot, prefix_atr, prefix_eligible)
    mutated_perp = {key: values.copy() for key, values in perp.items()}
    mutated_spot = {key: values.copy() for key, values in spot.items()}
    for key in ("open", "high", "low", "close"):
        mutated_perp[key][76:] *= 1.7
        mutated_spot[key][76:] *= 1.7
    mutated_atr = atr_values.copy()
    mutated_atr[76:] *= 2
    mutated_result, _, _ = first_touch_events(mutated_perp, mutated_spot, mutated_atr, eligible)

    assert full == prefix_result == mutated_result


def test_m2_includes_entry_minute_and_stop_first_on_dual_touch():
    event = {"side": "long", "zone_low": 99.0, "zone_high": 100.0, "atr": 1.0}
    path = _minute_path(100.0, 103.0, 97.0, 100.0)

    result = score_path(event, path, minute_index=0)

    assert result["path_complete"] is True
    assert result["exit_reason"] == "STOP"
    assert result["m2_hit"] is False


def test_m2_stop_gap_fills_at_open_and_target_gap_is_capped():
    event = {"side": "long", "zone_low": 99.0, "zone_high": 100.0, "atr": 1.0}
    stop_gap = _minute_path(100.0, 101.0, 99.5, 100.0)
    stop_gap["open"][1], stop_gap["high"][1], stop_gap["low"][1] = 98.0, 99.0, 97.0
    target_gap = _minute_path(100.0, 101.0, 99.5, 100.0)
    target_gap["open"][1], target_gap["high"][1], target_gap["low"][1] = 103.0, 104.0, 102.5

    stopped = score_path(event, stop_gap, minute_index=0)
    won = score_path(event, target_gap, minute_index=0)

    assert stopped["exit_reason"] == "STOP_GAP"
    assert stopped["exit_price"] == 98.0
    assert won["exit_reason"] == "TARGET_GAP"
    assert won["m2_hit"] is True
    assert won["exit_price"] == won["target"]


def test_m2_timeout_uses_last_minute_close_and_keeps_failure_label():
    event = {"side": "short", "zone_low": 99.0, "zone_high": 100.0, "atr": 1.0}
    path = _minute_path(100.0, 100.0, 99.9, 99.95)
    path["close"][-1] = 99.7

    result = score_path(event, path, minute_index=0)

    assert result["exit_reason"] == "TIMEOUT"
    assert result["exit_price"] == 99.7
    assert result["m2_hit"] is False


def test_incomplete_evaluation_path_is_retained_as_data_defect_failure():
    event = {"side": "long", "zone_low": 99.0, "zone_high": 100.0, "atr": 1.0}
    result = score_path(event, _minute_path(100.0, 100.5, 99.5, 100.1, count=99), 0)
    missing_entry = score_path(event, _minute_path(100.0, 100.5, 99.5, 100.1, count=99), 99)

    assert result["exit_reason"] == "DATA_DEFECT"
    assert result["m2_hit"] is False
    assert result["net_return_base"] is None
    assert missing_entry["exit_reason"] == "DATA_DEFECT"
    assert missing_entry["entry"] is None


def test_nonfinite_bar_inside_evaluation_path_is_data_defect_not_win_or_loss_pnl():
    event = {"side": "long", "zone_low": 99.0, "zone_high": 100.0, "atr": 1.0}
    path = _minute_path(100.0, 100.5, 99.5, 100.1)
    path["low"][23] = np.nan

    result = score_path(event, path, 0)

    assert result["exit_reason"] == "DATA_DEFECT"
    assert result["m2_hit"] is False
    assert result["net_return_base"] is None


def test_run_freeze_requires_exact_branch_parent_hashes_and_panel():
    freeze = {
        "code_commit_sha": "code-commit",
        "preregistration_sha256": "prereg-hash",
        "strategy_code_sha256": "code-hash",
        "input_fingerprint": FROZEN_INPUT_SHA256,
        "symbols": list(SYMBOLS),
        "code_tree_sha256": "tree-hash",
        "panel_verdicts": {"blue": "APPROVE", "data_methods": "APPROVE",
                           "execution_causality": "APPROVE", "red_judge": "APPROVE"},
    }
    validate_run_freeze(freeze, branch=EXPECTED_BRANCH, dirty="", parent="code-commit",
                        prereg_sha="prereg-hash", code_sha="code-hash",
                        input_sha=FROZEN_INPUT_SHA256, symbols=list(SYMBOLS),
                        code_tree="tree-hash",
                        freeze_commit_paths=["docs/research/inventory/crypto_ob_reclaim_freeze_20261122.json"])
    with pytest.raises(ValueError, match="symbol list"):
        validate_run_freeze(freeze, branch=EXPECTED_BRANCH, dirty="", parent="code-commit",
                            prereg_sha="prereg-hash", code_sha="code-hash",
                            input_sha=FROZEN_INPUT_SHA256, symbols=list(SYMBOLS[:-1]),
                            code_tree="tree-hash",
                            freeze_commit_paths=["docs/research/inventory/crypto_ob_reclaim_freeze_20261122.json"])


def test_incomplete_signal_anchor_is_not_eligible_or_coverage_denominator():
    times = CUTOFF_MS - np.array([120, 115, 110], dtype=np.int64) * 60_000
    perp = {key: np.ones(3, dtype=float)
            for key in ("open", "high", "low", "close", "volume")}
    spot = {key: value.copy() for key, value in perp.items()}
    perp["time"] = spot["time"] = times
    atr_values = np.ones(3, dtype=float)
    spot["close"][1] = np.nan

    eligible, _, invalid = eligible_anchor_mask(perp, spot, atr_values)

    assert eligible.tolist() == [False, False, True]
    assert invalid == 1


def test_cutoff_is_utc_first_day_boundary():
    assert CUTOFF_MS == int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000)
    signal_anchor = CUTOFF_MS - 105 * 60_000
    assert signal_anchor + 105 * 60_000 == CUTOFF_MS


def test_development_screen_boundaries_are_preregistered():
    metrics = {
        "issued_candidate_n": 200, "nonoverlap_candidate_n": 200,
        "candidate_m2_rate": .80, "candidate_m2_wilson_95": [.80, .90],
        "unfiltered_first_touch_m2": .79, "coverage_pct": 10.0,
        "net_return_per_issued_signal_base": .0001,
        "net_return_per_issued_signal_stress": .00001,
    }

    assert development_screen(metrics)["status"] == "PASS_DEV_ONLY"
    metrics["coverage_pct"] = 9.999
    assert development_screen(metrics)["checks"]["coverage_at_least_10pct"] is False
    metrics["nonoverlap_candidate_n"] = 199
    assert development_screen(metrics)["status"] == "INSUFFICIENT_SAMPLE"


def test_m1_direction_is_separate_and_uses_fixed_flat_band():
    assert score_m1("long", 100.0, 100.5, 1.0) == ("flat", False)
    assert score_m1("long", 100.0, 102.0, 1.0) == ("up", True)
    assert score_m1("short", 100.0, 98.0, 1.0) == ("down", True)
