from chart_predictor.mtf_dev_experiment import summarize_confidence_slices, wilson_interval


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
