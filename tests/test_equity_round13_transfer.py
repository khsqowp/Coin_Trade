import pandas as pd
import numpy as np

from app.rs_equity_round13_transfer import (
    completed_reference_scales,
    posterior_trade_scale,
    round13_configs,
)
from app.rs_equity_round14_transfer import round14_configs
from app.round13_costs import simulate_cost_portfolio
from app.crypto_round16_liquidation_research import plans as round16_plans


def test_round13_group_inventory_covers_declared_sections():
    configs = round13_configs()
    counts = {}
    for config in configs:
        counts[config["phase"]] = counts.get(config["phase"], 0) + 1
    assert counts == {
        "R13-69": 12,
        "R13-70": 8,
        "R13-71": 9,
        "R13-72": 6,
        "R13-73": 12,
        "R13-74": 9,
        "R13-75": 9,
        "R13-76": 6,
    }


def test_round14_predeclared_plan_inventory_is_complete():
    configs = round14_configs()
    assert len(configs) == 44
    assert len({config["phase"] for config in configs}) == 44
    assert all(config["family"] == "donchian" for config in configs)


def test_completed_reference_scale_uses_only_exited_trades():
    dates = pd.date_range("2024-01-01", periods=4, freq="D")
    records = [
        {"id": 0, "exit": 1, "return_pct": 10.0},
        {"id": 1, "exit": 3, "return_pct": -5.0},
    ]

    scale = completed_reference_scales(dates, records, "win", window=40)

    assert scale[dates[0]] == posterior_trade_scale([], "win", 40)
    assert scale[dates[1]] == posterior_trade_scale([0.10], "win", 40)
    assert scale[dates[2]] == posterior_trade_scale([0.10], "win", 40)
    assert scale[dates[3]] == posterior_trade_scale([0.10, -0.05], "win", 40)


def test_payoff_scale_is_bounded_and_validates_mode():
    assert 0.25 <= posterior_trade_scale([0.1, -0.03], "payoff", 40) <= 1.0

    try:
        posterior_trade_scale([], "unknown", 40)
    except ValueError as exc:
        assert "mode" in str(exc)
    else:
        raise AssertionError("unknown sizing mode must be rejected")


def test_cost_engine_exposes_net_completed_trade_ledger():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    frame = pd.DataFrame(
        {
            "Open": [100, 100, 105, 105, 105],
            "High": [101, 106, 106, 106, 106],
            "Low": [99, 99, 104, 104, 104],
            "Close": [100, 105, 105, 105, 105],
            "SIGNAL": [1, 0, 0, 0, 0],
            "VOL_RATIO": [1.0] * 5,
            "ATR14": [1.0] * 5,
            "STOP_LEVEL": [99.0] * 5,
        },
        index=dates,
    )

    result = simulate_cost_portfolio(
        {"AAA": frame}, hold_days=1, top_k=1, fee_pct_one_way=0.1,
        sell_tax=0.2, return_trace=True,
    )

    assert len(result["records"]) == 1
    trade = result["records"][0]
    assert trade["entry_date"].startswith("2024-01-02")
    assert trade["exit_date"].startswith("2024-01-03")
    assert np.isfinite(trade["return_pct"])
    assert trade["return_pct"] < 5.0


def test_round16_grid_contains_397_source_declared_configurations():
    configs = round16_plans()
    assert len(configs) == 397
    assert len({repr(sorted(config.items())) for config in configs}) == 397


def test_cost_engine_executes_prior_close_exit_signal_at_next_open():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    frame = pd.DataFrame(
        {
            "Open": [100, 100, 105, 103, 103],
            "High": [101, 106, 106, 104, 104],
            "Low": [99, 99, 104, 102, 102],
            "Close": [100, 105, 105, 103, 103],
            "SIGNAL": [1, 0, 0, 0, 0],
            "VOL_RATIO": [1.0] * 5,
            "ATR14": [1.0] * 5,
            "STOP_LEVEL": [99.0] * 5,
        },
        index=dates,
    )
    exits = np.array([[0], [0], [1], [0], [0]], dtype=bool)

    result = simulate_cost_portfolio(
        {"AAA": frame}, hold_days=10, top_k=1, fee_pct_one_way=0,
        exit_signals=exits, return_trace=True,
    )

    trade = result["records"][0]
    assert trade["entry_date"].startswith("2024-01-02")
    assert trade["exit_date"].startswith("2024-01-04")
    assert trade["proceeds"] == trade["qty"] * 103
