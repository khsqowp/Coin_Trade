from __future__ import annotations

import pandas as pd

from scripts.research.fixed_dual_thrust_sleeve import simulate_dual_thrust


def _frames():
    days = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    frame = pd.DataFrame({
        "Open": [100.0] * 5, "High": [100.0] * 5, "Low": [100.0] * 5,
        "Close": [100.0] * 5, "DIRECTION": [1, 0, 0, 0, 0],
        "SCORE": [0.5] * 5,
    }, index=days)
    return days, {"BTC": frame}


def test_entry_exit_fee_and_strict_funding_boundaries():
    days, frames = _frames()
    events = pd.DataFrame({
        "rate": [0.01, 0.01, 0.01], "markPrice": [100.0] * 3,
    }, index=pd.DatetimeIndex([
        days[1], days[1] + pd.Timedelta(hours=8), days[4],
    ]))
    result = simulate_dual_thrust(
        frames, {"BTC": events}, start=days[0], end_exclusive=days[-1] + pd.Timedelta(days=1),
        top_k=2, hold_days=2, cost=0.001,
    )
    assert result["trades"] == 1
    assert abs(result["fees"] - 0.001) < 1e-12
    assert abs(result["funding_pnl"] + 0.005) < 1e-12
    assert abs(result["terminal_nav"] - 0.994) < 1e-12


def test_expiry_day_slot_is_not_reused_before_close():
    days, frames = _frames()
    frames["BTC"].loc[days[1], "DIRECTION"] = 1
    frames["BTC"].loc[days[2], "DIRECTION"] = 1
    result = simulate_dual_thrust(
        frames, {}, start=days[0], end_exclusive=days[-1] + pd.Timedelta(days=1),
        top_k=2, hold_days=2, cost=0.0,
    )
    # First position enters day 1 and exits at day 3 close. A second signal on
    # day 2 is ignored while that position occupies the slot at day 3 open.
    assert result["trades"] == 1


def test_rejects_naive_timestamps():
    days, frames = _frames()
    try:
        simulate_dual_thrust(
            frames, {}, start=days[0].tz_localize(None), end_exclusive=days[-1] + pd.Timedelta(days=1),
        )
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("naive timestamp was accepted")
