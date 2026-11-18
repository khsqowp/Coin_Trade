from chart_predictor.micro_sweep_feasibility import candidate_side


def test_lower_extreme_sweep_and_midpoint_reclaim_is_long():
    first = (100.0, 110.0, 90.0, 95.0)
    second = (95.0, 105.0, 89.0, 101.0)
    assert candidate_side(first, second) == 1


def test_upper_extreme_sweep_and_midpoint_rejection_is_short():
    first = (100.0, 110.0, 90.0, 105.0)
    second = (105.0, 111.0, 95.0, 99.0)
    assert candidate_side(first, second) == -1


def test_double_extreme_sweep_and_close_outside_prior_range_do_not_signal():
    first = (100.0, 110.0, 90.0, 100.0)
    double_sweep = (100.0, 111.0, 89.0, 100.0)
    close_outside = (100.0, 111.0, 89.0, 112.0)
    assert candidate_side(first, double_sweep) == 0
    assert candidate_side(first, close_outside) == 0


def test_malformed_candle_does_not_emit():
    first = (100.0, 110.0, 90.0, 95.0)
    malformed_second = (95.0, 88.0, 89.0, 101.0)
    assert candidate_side(first, malformed_second) == 0
