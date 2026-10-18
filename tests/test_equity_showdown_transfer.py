import numpy as np
import pandas as pd

from app.rs_equity_showdown_transfer import configurations, simulate


def test_showdown_source_grid_has_all_112_filtered_combinations():
    grid = configurations()
    assert len(grid) == 112
    assert len({(x["regime"], x["mode"], x["stop_pct"], x["leverage"]) for x in grid}) == 112
    assert all((x["mode"] == "none") == (x["stop_pct"] == 0) for x in grid)


def test_equity_showdown_simulation_preserves_daily_returns_and_curve():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    returns = np.array([.01, -.02, .03])
    inputs = {"neutral": {
        "returns": returns,
        "turnover_by_symbol": np.zeros((3, 2)),
        "long_sell_by_symbol": np.zeros((3, 2)),
    }}
    config = {"regime": "neutral", "mode": "none", "stop_pct": 0., "leverage": 1.}
    row = simulate(inputs, dates, np.ones(3, bool), config,
                   ("test", 0., np.zeros(2), 0.), "US")
    net_returns = returns - .5 * .01 / 365
    expected = np.cumprod(1 + net_returns)
    np.testing.assert_allclose(row["daily_equity"], expected)
    np.testing.assert_allclose(row["daily_returns"], net_returns)
    assert row["metrics"]["final"] == expected[-1]
