import pandas as pd
import pytest

from chart_predictor.short_term_pressure import (
    Signal,
    pressure_score,
    pressure_scores,
    resolve_signal,
    select_cross_sectional_sides,
)


def test_pressure_score_is_quote_volume_weighted_close_location():
    frame = pd.DataFrame({
        "h": [11.0, 12.0, 13.0],
        "l": [9.0, 10.0, 11.0],
        "c": [10.0, 11.0, 11.5],
        "quote_v": [1.0, 2.0, 1.0],
    })

    score = pressure_score(frame)

    # Per-bar locations are 0, 0, -0.5; quote-volume weighted over 3 bars.
    assert score == pytest.approx(-0.125)


def test_zero_range_bar_contributes_zero_without_division_error():
    frame = pd.DataFrame({
        "h": [10.0, 10.0, 10.0],
        "l": [10.0, 10.0, 10.0],
        "c": [10.0, 10.0, 10.0],
        "quote_v": [1.0, 1.0, 1.0],
    })
    assert pressure_score(frame) == pytest.approx(0.0)


def test_appending_future_bars_does_not_change_prefix_scores():
    prefix = pd.DataFrame({
        "h": [11.0, 12.0, 13.0, 12.0],
        "l": [9.0, 10.0, 11.0, 10.0],
        "c": [10.0, 11.0, 12.0, 11.0],
        "quote_v": [1.0, 2.0, 3.0, 4.0],
    })
    suffix = pd.DataFrame({
        "h": [100.0, 200.0], "l": [1.0, 1.0],
        "c": [99.0, 2.0], "quote_v": [1000.0, 2000.0],
    })
    original = pressure_scores(prefix)
    extended = pressure_scores(pd.concat([prefix, suffix], ignore_index=True))
    assert extended[:len(prefix)] == pytest.approx(original, nan_ok=True)


def test_selection_uses_descending_top_two_and_ascending_bottom_two_with_ties():
    scores = {f"S{i:02d}": float(i) for i in range(20)}

    selected = select_cross_sectional_sides(scores)

    assert [(symbol, side) for symbol, side in selected] == [
        ("S19", 1), ("S18", 1), ("S00", -1), ("S01", -1)
    ]


def test_same_bar_target_and_stop_is_scored_as_stop():
    signal = Signal(time_ms=60_000, symbol="X", side=1, pressure=1.0)
    bars = pd.DataFrame({
        "t_open_ms": [60_000], "o": [100.0], "h": [101.0],
        "l": [99.0], "c": [100.0],
    })

    result = resolve_signal(signal, bars, fee_per_side=0.0005,
                            slippage_per_side=0.0004,
                            target_pct=0.0045, stop_pct=0.002, horizon_bars=1)

    assert result["status"] == "scorable"
    assert result["reason"] == "stop"
    assert result["target_first"] is False
    assert result["net_return"] < -0.002
    assert result["horizon_close_return"] == pytest.approx(-0.00039984, abs=1e-8)


def test_timeout_is_m2_failure_and_missing_path_is_unscorable():
    signal = Signal(time_ms=60_000, symbol="X", side=-1, pressure=-1.0)
    bars = pd.DataFrame({
        "t_open_ms": [60_000, 120_000],
        "o": [100.0, 100.0], "h": [100.01, 100.01],
        "l": [99.99, 99.99], "c": [100.0, 100.0],
    })

    timeout = resolve_signal(signal, bars, 0.0005, 0.0004, 0.0045, 0.002, 2)
    assert timeout["reason"] == "timeout"
    assert timeout["target_first"] is False
    assert timeout["net_return"] < 0

    missing = resolve_signal(signal, bars.iloc[:1], 0.0005, 0.0004,
                             0.0045, 0.002, 2)
    assert missing["status"] == "unscorable"


def test_signal_anchor_cannot_be_filled_at_an_earlier_bar():
    signal = Signal(time_ms=120_000, symbol="X", side=1, pressure=0.5)
    bars = pd.DataFrame({
        "t_open_ms": [60_000], "o": [100.0], "h": [101.0],
        "l": [99.0], "c": [100.0],
    })
    result = resolve_signal(signal, bars, 0.0005, 0.0004,
                            0.0045, 0.002, 1)
    assert result["status"] == "unscorable"
    assert result["reason"] == "missing_entry_minute"
