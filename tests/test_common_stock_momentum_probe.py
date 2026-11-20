import numpy as np
import pandas as pd

from scripts.research.common_stock_momentum_probe import simulate


def test_equal_weight_baseline_buys_once_and_then_holds():
    dates = pd.date_range("2024-01-01", periods=12, freq="B", tz="UTC")
    close = np.column_stack((np.arange(10, 22), np.arange(20, 32), np.arange(30, 42))).astype(float)
    metrics, daily, events, round_trips = simulate(
        ["069500", "AAA", "BBB"], dates, close, "KR", 2, "monthly", False,
        {"fee": 0.0, "slippage": 0.0, "sell_tax": 0.0}, baseline=True)
    assert metrics["rebalance_events"] == 1
    assert len(events) == 1
    assert len(round_trips) == 3
    assert daily[-1]["nav"] > daily[0]["nav"]


def test_cash_scaling_prevents_leverage_under_high_costs():
    dates = pd.date_range("2024-01-01", periods=16, freq="B", tz="UTC")
    close = np.column_stack((np.linspace(10, 18, 16), np.linspace(20, 18, 16),
                             np.linspace(30, 35, 16))).astype(float)
    metrics, _, events, _ = simulate(
        ["069500", "AAA", "BBB"], dates, close, "KR", 2, "daily", False,
        {"fee": 0.02, "slippage": 0.03, "sell_tax": 0.01})
    assert metrics["ending_nav"] > 0
    assert all(event["cash_after"] >= -1e-10 for event in events)


def test_future_mutation_does_not_change_prior_nav():
    dates = pd.date_range("2024-01-01", periods=20, freq="B", tz="UTC")
    close = np.column_stack((np.linspace(10, 14, 20), np.linspace(20, 24, 20),
                             np.linspace(30, 25, 20))).astype(float)
    args = (["069500", "AAA", "BBB"], dates)
    costs = {"fee": 0.001, "slippage": 0.001, "sell_tax": 0.002}
    original = simulate(*args, close, "KR", 2, "daily", False, costs)[1]
    mutated_close = close.copy()
    cutoff = 12
    mutated_close[cutoff:] *= np.array([3.0, 0.5, 2.0])
    mutated = simulate(*args, mutated_close, "KR", 2, "daily", False, costs)[1]
    assert [row["nav"] for row in original if row["date"] <= dates[cutoff - 1].isoformat()] == [
        row["nav"] for row in mutated if row["date"] <= dates[cutoff - 1].isoformat()]
