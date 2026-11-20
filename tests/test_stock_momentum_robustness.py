import pandas as pd

from scripts.research.stock_momentum_robustness import month_boundaries


def test_walk_forward_boundary_starts_are_monthly_and_minimum_respected():
    dates = pd.date_range("2020-01-01", periods=900, freq="B", tz="UTC")
    boundaries = month_boundaries(dates, 300)
    assert boundaries
    assert all(index >= 300 for index in boundaries)
    periods = [dates[index].tz_localize(None).to_period("M") for index in boundaries]
    assert all(periods[i] != periods[i - 1] for i in range(1, len(periods)))


def test_six_month_stride_produces_non_overlapping_calendar_windows():
    dates = pd.date_range("2020-01-01", periods=900, freq="B", tz="UTC")
    boundaries = month_boundaries(dates, 300)[::6]
    periods = [dates[index].tz_localize(None).to_period("M") for index in boundaries]
    assert all((periods[i] - periods[i - 1]).n == 6 for i in range(1, len(periods)))
