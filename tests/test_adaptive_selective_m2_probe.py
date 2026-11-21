import numpy as np
import pandas as pd
import pytest
import gzip
import json
from pathlib import Path

from scripts.research.adaptive_selective_m2_probe import (
    MINUTE_MS,
    DAY_MS,
    SYMBOLS,
    DataInvalid,
    _bootstrap_summary,
    _classifier,
    _fit_arrays,
    _score_week,
    _sha256,
    _verify_forecast_seal,
    _weekly_dates,
    _validate_schema_types,
    compute_features,
    evaluate_trade,
    funding_minute_indices,
    global_nonoverlap,
    label_first_touch,
    nearest_rank_quantile,
    refit_window,
    select_direction,
    _expected_month_grid,
    PREREG_PATH,
)


def bars(n=80):
    close = 100.0 + np.arange(n, dtype=float) * 0.01
    open_ = close - 0.005
    high = close + 0.02
    low = open_ - 0.02
    return pd.DataFrame({
        "open_time": np.arange(n, dtype=np.int64) * MINUTE_MS,
        "open": open_, "high": high, "low": low, "close": close,
        "volume": 10.0 + np.arange(n, dtype=float),
        "taker_buy_volume": np.full(n, 6.0),
    })


def test_features_are_prefix_invariant_and_have_exact_whitelist():
    frame = bars(130)
    features, ready = compute_features(frame)
    mutated = frame.copy()
    mutated.loc[60:, ["open", "high", "low", "close", "volume", "taker_buy_volume"]] *= 3
    changed, _ = compute_features(mutated)

    assert list(features.columns) == [
        "ret_1", "ret_3", "ret_5", "ret_10", "range_pct", "body_ratio",
        "upper_wick_ratio", "lower_wick_ratio", "atr14_pct", "rv20",
        "volume_z60", "taker_fraction_5",
    ]
    assert ready[:60].sum() == 1
    np.testing.assert_allclose(features.iloc[59].to_numpy(), changed.iloc[59].to_numpy())
    assert not ready[58]
    assert ready[59]


def test_feature_readiness_does_not_roll_across_timestamp_gap():
    frame = bars(130)
    frame.loc[60:, "open_time"] += MINUTE_MS
    _, ready = compute_features(frame)

    assert not ready[60]
    assert not ready[118]
    assert ready[119]


def test_formula_defined_missing_features_do_not_drop_ready_anchor():
    frame = bars(130)
    frame.loc[65, ["open", "high", "low", "close"]] = 100.0
    frame.loc[66, "volume"] = 0.0
    frame.loc[66, "taker_buy_volume"] = 0.0
    features, ready = compute_features(frame)
    assert ready[65]
    assert np.isnan(features.loc[65, "body_ratio"])
    assert np.isnan(features.loc[65, "upper_wick_ratio"])
    assert np.isnan(features.loc[65, "lower_wick_ratio"])
    assert ready[66]
    assert np.isnan(features.loc[66, "taker_fraction_5"])


def test_frozen_classifier_accepts_formula_defined_nan_features():
    x = np.arange(360, dtype=float).reshape(120, 3)
    x[0, 1] = np.nan
    y = np.repeat(np.array([0, 1, 2]), 40)
    model = _classifier().fit(x, y)
    assert model.predict_proba(x[:1]).shape == (1, 3)


def test_fit_rows_are_filtered_by_anchor_time_then_sorted_by_symbol():
    start = 1_700_000_000_000 // (5 * MINUTE_MS) * (5 * MINUTE_MS)
    series = {}
    selected_symbols = sorted(SYMBOLS)[-2:]
    for symbol_index, symbol in enumerate(SYMBOLS):
        frame = bars(20)
        frame["open_time"] += start
        features = np.zeros((20, 12), dtype=np.float32)
        features[:, 0] = symbol_index * 100 + np.arange(20)
        series[symbol] = {"times": frame["open_time"].to_numpy(np.int64),
                          "frame": frame, "atr": np.ones(20),
                          "features": features,
                          "ready": np.full(20, symbol in selected_symbols, dtype=bool)}
    x, _, _ = _fit_arrays(series, start, start + 20 * MINUTE_MS)
    sorted_indices = [SYMBOLS.index(symbol) for symbol in selected_symbols]
    expected = [value * 100 + index for index in (0, 5) for value in sorted_indices]
    np.testing.assert_array_equal(x[:, 0], expected)


def test_required_arrow_dtypes_are_enforced():
    import pyarrow as pa

    _validate_schema_types(pa.schema([("open_time", pa.int64()), ("open", pa.float64())]),
                           {"open_time": "int64", "open": "double"}, "test")
    with pytest.raises(DataInvalid, match="dtype mismatch"):
        _validate_schema_types(pa.schema([("open_time", pa.string())]),
                               {"open_time": "int64"}, "test")


def test_score_week_retains_every_raw_score_not_only_emitted_signals():
    timestamp = 1_750_000_000_000 // MINUTE_MS * MINUTE_MS
    series = {symbol: {"times": np.array([timestamp], dtype=np.int64),
                       "ready": np.array([True]),
                       "features": np.zeros((1, 12), dtype=np.float32)}
              for symbol in SYMBOLS}

    class FixedModel:
        classes_ = np.array([0, 1, 2])

        @staticmethod
        def predict_proba(features):
            return np.tile(np.array([[0.6, 0.2, 0.2]]), (len(features), 1))

    signals, raw_rows, scores, counts = _score_week(series, FixedModel(), timestamp, timestamp + MINUTE_MS)
    assert len(signals) == len(raw_rows) == len(scores) == len(SYMBOLS)
    assert sum(counts.values()) == len(SYMBOLS)
    assert raw_rows[0]["selective_score"] == pytest.approx(0.4)


def test_forecast_seal_rejects_any_ledger_mutation_before_score(tmp_path):
    forecast_ledger = tmp_path / "forecasts.jsonl"
    forecast_ledger.write_text('{"symbol":"BTCUSDT"}\n', encoding="utf-8")
    score_ledger = tmp_path / "prequential_scores.jsonl.gz"
    with gzip.open(score_ledger, "wt", encoding="utf-8") as stream:
        stream.write('{"symbol":"BTCUSDT","selective_score":0.4}\n')
    test_path = Path(__file__).resolve()
    module_path = test_path.parents[1] / "scripts/research/adaptive_selective_m2_probe.py"
    manifest = {"status": "FORECASTS_SEALED_NO_OUTCOMES", "issued": 1,
                "ledger_sha256": _sha256(forecast_ledger),
                "prequential_score_ledger_sha256": _sha256(score_ledger),
                "prequential_score_rows": 1,
                "prereg_sha256": _sha256(Path(PREREG_PATH)),
                "code_sha256": _sha256(module_path),
                "tests_sha256": _sha256(test_path)}
    (tmp_path / "forecast_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert _verify_forecast_seal(tmp_path)["issued"] == 1
    forecast_ledger.write_text('{"symbol":"ETHUSDT"}\n', encoding="utf-8")
    with pytest.raises(DataInvalid, match="forecast ledger hash"):
        _verify_forecast_seal(tmp_path)


def test_label_first_touch_up_down_nohit_and_same_bar_collision():
    frame = bars(20)
    frame.loc[2, ["high", "low"]] = [101.1, 99.9]
    assert label_first_touch(frame, 0, 1.0)["label"] == "UP_FIRST"

    frame.loc[2, ["high", "low"]] = [100.1, 98.9]
    assert label_first_touch(frame, 0, 1.0)["label"] == "DOWN_FIRST"

    frame.loc[2, ["high", "low"]] = [101.1, 98.9]
    result = label_first_touch(frame, 0, 1.0)
    assert result["label"] == "NO_HIT"
    assert result["status"] == "AMBIGUOUS_BOTH"


def test_label_timeout_and_missing_path_are_distinct():
    frame = bars(15)
    result = label_first_touch(frame, 0, 1.0)
    assert result["label"] == "NO_HIT"
    assert result["status"] == "TIMEOUT"

    frame.loc[7:, "open_time"] += MINUTE_MS
    result = label_first_touch(frame, 0, 1.0)
    assert result["status"] == "MISSING_PATH"
    assert result["label"] is None


@pytest.mark.parametrize("values,q,expected", [
    ([1.0, 2.0, 3.0, 4.0], 0.50, 2.0),
    ([1.0, 2.0, 3.0, 4.0], 0.90, 4.0),
    ([1.0, 1.0, 1.0, 1.0], 0.90, 1.0),
])
def test_nearest_rank_threshold_is_deterministic(values, q, expected):
    assert nearest_rank_quantile(values, q) == expected


def test_select_direction_requires_positive_edge_and_strict_class_winner():
    long_result = select_direction(0.60, 0.20, 0.20, 0.30)
    short_result = select_direction(0.20, 0.60, 0.20, 0.30)
    assert long_result is not None and long_result[0] == "long"
    assert long_result[1] == pytest.approx(0.40)
    assert short_result is not None and short_result[0] == "short"
    assert short_result[1] == pytest.approx(0.40)
    assert select_direction(0.30, 0.30, 0.40, -0.20) is None
    assert select_direction(0.40, 0.40, 0.20, 0.10) is None
    assert select_direction(0.45, 0.35, 0.20, 0.30) is None


def test_refit_training_window_is_180_days_with_28_day_embargo():
    t = 1_800_000_000_000
    start, end = refit_window(t)
    assert end == t - 28 * 24 * 60 * MINUTE_MS
    assert end - start == 180 * 24 * 60 * MINUTE_MS


def test_calibration_replay_is_exactly_four_weeks_before_evaluation():
    evaluation_start = 1_782_864_000_000
    starts = _weekly_dates(evaluation_start - 28 * DAY_MS, evaluation_start)
    assert len(starts) == 4
    assert starts[0] == evaluation_start - 28 * DAY_MS


def test_expected_month_grid_uses_utc_month_boundary_and_leap_year():
    feb = _expected_month_grid("2024-02")
    assert len(feb) == 29 * 24 * 60
    assert feb[0] == 1_706_745_600_000
    assert feb[-1] == feb[0] + (len(feb) - 1) * MINUTE_MS


def test_global_nonoverlap_keeps_missing_entry_scheduled_window():
    events = [
        {"anchor_ms": 0, "scheduled_entry_ms": MINUTE_MS, "symbol": "ETHUSDT",
         "score": 0.4, "entry_missing": True},
        {"anchor_ms": 0, "scheduled_entry_ms": MINUTE_MS, "symbol": "BTCUSDT",
         "score": 0.3, "entry_missing": False},
        {"anchor_ms": 5 * MINUTE_MS, "scheduled_entry_ms": 6 * MINUTE_MS,
         "symbol": "BTCUSDT", "score": 0.9, "entry_missing": False},
        {"anchor_ms": 11 * MINUTE_MS, "scheduled_entry_ms": 12 * MINUTE_MS,
         "symbol": "BTCUSDT", "score": 0.2, "entry_missing": False},
    ]
    selected = global_nonoverlap(events)

    assert [event["symbol"] for event in selected] == ["ETHUSDT", "BTCUSDT"]
    assert selected[0]["entry_missing"]
    assert selected[1]["anchor_ms"] == 11 * MINUTE_MS


def test_funding_timestamp_maps_to_exact_containing_mark_minute():
    mark_times = np.array([0, MINUTE_MS, 2 * MINUTE_MS], dtype=np.int64)
    funding_times = np.array([MINUTE_MS + 999, 2 * MINUTE_MS], dtype=np.int64)
    np.testing.assert_array_equal(
        funding_minute_indices(mark_times, funding_times), np.array([1, 2])
    )


def test_funding_timestamp_over_one_second_off_grid_is_rejected():
    mark_times = np.array([0, MINUTE_MS], dtype=np.int64)
    funding_times = np.array([MINUTE_MS + 1_001], dtype=np.int64)
    with pytest.raises(ValueError, match="off the UTC minute grid"):
        funding_minute_indices(mark_times, funding_times)


def test_trade_m2_uses_all_issued_signal_and_stop_first_collision():
    frame = bars(20)
    frame.loc[2, ["high", "low"]] = [101.1, 98.9]
    funding = {"times": np.array([], dtype=np.int64), "rates": np.array([]),
               "mark_open": np.array([])}
    result = evaluate_trade(frame, 0, 1.0, "long", funding, 0.001)

    assert result["executed"] is True
    assert result["m2_hit"] is False
    assert result["status"] == "AMBIGUOUS_BOTH"
    assert result["exit_price"] == pytest.approx(result["entry"] - 1.0)
    assert result["fee_return"] == pytest.approx(-0.001)


def test_trade_timeout_funding_and_round_trip_net_are_exact():
    frame = bars(20)
    mark_times = np.array([MINUTE_MS], dtype=np.int64)
    funding = {"times": np.array([MINUTE_MS + 500], dtype=np.int64),
               "rates": np.array([0.001]), "mark_open": np.array([100.0])}
    result = evaluate_trade(frame, 0, 1.0, "long", funding, 0.001)

    assert result["status"] == "TIMEOUT"
    assert result["m2_hit"] is False
    assert result["funding_return"] == pytest.approx(-0.001 * 100.0 / result["entry"])
    assert result["net_return"] == pytest.approx(
        result["gross_return"] + result["funding_return"] - 0.001
    )


def test_bootstrap_resamples_daily_panels_deterministically():
    rows = [{"anchor_ms": 1_782_864_000_000, "m2_hit": True,
             "net_10bp": 0.01, "net_30bp": 0.008}]
    first = _bootstrap_summary(rows, 92)
    second = _bootstrap_summary(rows, 92)
    assert first == second
    assert first["replicates_requested"] == 1_000
    assert first["seed"] == 20261121
