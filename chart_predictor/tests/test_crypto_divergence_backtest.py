from chart_predictor.crypto_divergence_backtest import (
    ENTRIES, HORIZONS, LAGS, MINUTE_MS, OSCILLATORS, STOP_BUFFERS, TARGETS,
    TIMEFRAMES, _claim_decision, _empty_cell, _event_metric, _scheduled_opportunities,
    _select, expected_grid, frozen_windows,
)


def test_frozen_wfa_matches_registered_half_open_utc_windows():
    windows = frozen_windows()
    assert len(windows) == 5
    assert windows[0]["train_start_ms"] == 1640995200000
    assert windows[0]["train_end_ms"] == 1684540800000
    assert windows[-1]["test_end_ms"] == 1793404800000
    for left, right in zip(windows, windows[1:]):
        assert right["train_start_ms"] - left["train_start_ms"] == 252 * 86_400_000
        assert left["test_end_ms"] == right["test_start_ms"]


def test_grid_has_all_and_only_48_preregistered_cells():
    grid = expected_grid()
    assert len(grid) == 48
    assert {x["lag"] for x in grid} == set(LAGS)
    assert {x["entry"] for x in grid} == set(ENTRIES)
    assert {x["stop_buffer_atr"] for x in grid} == set(STOP_BUFFERS)
    assert {x["target_r"] for x in grid} == set(TARGETS)


def test_train_selection_is_deterministic_and_records_all_4800_cells():
    windows = frozen_windows()
    cells, opportunities = {}, {}
    for w in windows:
        fold = w["fold"]
        for tf in TIMEFRAMES:
            opportunities[(tf, fold)] = 1000
        for osc in OSCILLATORS:
            for tf in TIMEFRAMES:
                for horizon in HORIZONS:
                    for p in expected_grid():
                        key = (fold, osc, tf, horizon, p["lag"], p["entry"],
                               p["stop_buffer_atr"], p["target_r"])
                        row = _empty_cell()
                        row.update(emitted=50, resolved=50, wins=45, filled=50,
                                   net_r_base_sum=5.0)
                        cells[key] = row
    selected, rows = _select(cells, opportunities, windows)
    assert len(selected) == 5 * len(OSCILLATORS) * len(TIMEFRAMES) * len(HORIZONS)
    assert len(rows) == 5 * len(OSCILLATORS) * len(TIMEFRAMES) * len(HORIZONS) * 48
    assert all(p == {"lag": 2, "entry": "next_open",
                     "stop_buffer_atr": 0.0, "target_r": 1.0}
               for p in selected.values())


def test_scheduled_opportunity_denominator_includes_missing_bars():
    start = 1_700_000_000_000 // (5 * MINUTE_MS) * (5 * MINUTE_MS)
    end = start + 120 * MINUTE_MS
    # Counts 24 five-minute slots per symbol, regardless of observed candle count.
    assert _scheduled_opportunities(3, start, end, 5) == 72


def test_claim_decision_separates_insufficient_evidence_from_observed_failure():
    complete = {
        "nonoverlap_n_200": True,
        "nonoverlap_symbols_20": True,
        "resolved_path_coverage_95pct": True,
        "m2_point_80pct": True,
        "issue_coverage_spec_10pct": True,
        "filled_trade_net_expectancy_positive": True,
    }
    assert _claim_decision({**complete, "nonoverlap_n_200": False}) == "INCONCLUSIVE"
    assert _claim_decision({**complete, "resolved_path_coverage_95pct": False}) == "INCONCLUSIVE"
    assert _claim_decision({**complete, "m2_point_80pct": False}) == "REJECT"
    assert _claim_decision(complete) == "INCONCLUSIVE"
    assert _claim_decision(complete, exact_family_calibrated=True) == "PASS"


def test_invalid_signal_is_not_counted_as_a_resolved_path():
    row = _empty_cell()
    _event_metric(row, {"status": "invalid", "target_first": False,
                        "trade_net_r": None})
    assert row["emitted"] == 1
    assert row["invalid"] == 1
    assert row["resolved"] == 0
    assert row["wins"] == 0
