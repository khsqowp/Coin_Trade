import pandas as pd

from chart_predictor.mtf_dev_experiment import (
    fixed_seed_random_side,
    matched_risk_forecast,
    momentum_1m_side,
    summarize_baseline_confidence_slices,
    summarize_confidence_slices,
    wilson_interval,
)


def test_wilson_interval_handles_empty_and_computes_bounds():
    assert wilson_interval(0, 0) == (None, None)
    low, high = wilson_interval(8, 10)
    assert 0.4 < low < 0.6
    assert 0.9 < high < 1.0


def test_confidence_slices_report_threshold_precision_coverage_and_concentration():
    exact = {
        ("1m", "long", 20, 2): {"events": 2, "target": 1, "stop": 1,
                                  "timeout": 0, "unscorable": 0, "sum_net_r": 0.5},
        ("1m", "long", 20, 3): {"events": 1, "target": 1, "stop": 0,
                                  "timeout": 0, "unscorable": 0, "sum_net_r": 1.9},
    }
    symbols = {
        ("1m", "long", 20, 2): {"BTCUSDT": 1, "ETHUSDT": 1},
        ("1m", "long", 20, 3): {"BTCUSDT": 1},
    }
    rows = summarize_confidence_slices(exact, symbols)
    q2 = next(row for row in rows if row["min_votes"] == 2)
    q3 = next(row for row in rows if row["min_votes"] == 3)
    assert q2["events"] == 3
    assert q2["coverage"] == 1
    assert q2["target_first_precision"] == 2 / 3
    assert q2["symbols"] == 2
    assert q3["events"] == 1
    assert q3["coverage"] == 1 / 3
    assert q3["target_first_precision"] == 1
    assert q3["symbols"] == 1
    assert q3["largest_symbol_share"] == 1


def test_momentum_baseline_uses_only_contiguous_completed_minutes():
    candles = pd.DataFrame([
        {"t_open_ms": 0, "c": 100.0},
        {"t_open_ms": 60_000, "c": 101.0},
        {"t_open_ms": 120_000, "c": 99.0},
    ])
    assert momentum_1m_side(candles, 2) == "long"
    candles.loc[2, "t_open_ms"] = 180_000
    assert momentum_1m_side(candles, 2) is None


def test_random_direction_is_reproducible_and_risk_is_matched():
    side = fixed_seed_random_side("BTCUSDT", 1_800_000, "5m")
    assert side == fixed_seed_random_side("BTCUSDT", 1_800_000, "5m")
    assert side in {"long", "short"}
    forecast = {"event_id": "event", "symbol": "BTCUSDT", "timeframe": "5m",
                "entry_ms": 1_800_000, "entry_price": 100.0, "side": "long",
                "stop": 98.0, "target": 104.0}
    short = matched_risk_forecast(forecast, "short", "random")
    assert short["stop"] == 102.0
    assert short["target"] == 96.0
    assert short["risk"] == 2.0


def test_matched_baseline_rejects_nonpositive_short_target():
    forecast = {"event_id": "event", "symbol": "BTCUSDT", "timeframe": "5m",
                "entry_ms": 1_800_000, "entry_price": 100.0, "side": "long",
                "stop": 20.0, "target": 260.0}
    assert matched_risk_forecast(forecast, "short", "random") is None


def test_baseline_slices_use_the_same_confidence_threshold_cohort():
    exact = {
        ("1m", "long", "momentum_1m", 20, 2): {
            "events": 2, "directional": 2, "flat": 0, "target": 1,
            "stop": 1, "timeout": 0, "unscorable": 0, "sum_net_r": 0.8},
        ("1m", "long", "momentum_1m", 20, 3): {
            "events": 1, "directional": 1, "flat": 0, "target": 0,
            "stop": 1, "timeout": 0, "unscorable": 0, "sum_net_r": -1.1},
    }
    rows = summarize_baseline_confidence_slices(exact)
    q2 = next(row for row in rows if row["min_votes"] == 2)
    q3 = next(row for row in rows if row["min_votes"] == 3)
    assert q2["events"] == 3
    assert q2["cohort_coverage"] == 1
    assert q2["target_first_precision"] == 1 / 3
    assert q3["events"] == 1
    assert q3["cohort_coverage"] == 1 / 3
    assert q3["target_first_precision"] == 0
