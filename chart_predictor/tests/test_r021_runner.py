import pandas as pd

from chart_predictor.run_r021_funding_reentry import horizon_fits, walk_trade


def minute_frame(open_, high, low, close, start=0):
    return pd.DataFrame({
        "open_ms": [start + i * 60_000 for i in range(len(open_))],
        "open": open_, "high": high, "low": low, "close": close,
    })


def test_full_maximum_horizon_must_fit_before_exclusive_split_end():
    assert horizon_fits(1_000, 400, 10, 60)
    assert not horizon_fits(1_000, 401, 10, 60)


def test_same_minute_stop_and_target_touch_is_counted_as_stop():
    frame = minute_frame([100, 100], [101, 120], [99, 80], [100, 100])
    trade = walk_trade(frame, [], 1, 1, 10, 60_000, 10, False)
    assert trade["reason"] == "stop"
    assert trade["gross_r"] == -1


def test_target_fill_is_capped_at_limit_and_stress_cost_doubles():
    frame = minute_frame([100, 100], [101, 120], [99, 99], [100, 110])
    base = walk_trade(frame, [], 1, 1, 10, 60_000, 10, False)
    stress = walk_trade(frame, [], 1, 1, 10, 60_000, 10, True)
    assert base["reason"] == "target"
    assert base["gross_r"] == 1.5
    assert stress["cost_r"] == 2 * base["cost_r"]


def test_funding_cashflow_uses_side_and_prior_close_proxy():
    frame = minute_frame([100, 100, 101], [101, 102, 102], [99, 99, 100], [100, 101, 101])
    event = {"fundingTime": 120_000, "fundingRate": 0.001, "markPrice": ""}
    long = walk_trade(frame, [event], 1, 1, 10, 180_000, 1, False)
    short = walk_trade(frame, [event], 1, -1, 10, 180_000, 1, False)
    assert long["funding_r"] < 0
    assert short["funding_r"] > 0
