from __future__ import annotations

import numpy as np
import pytest

from scripts.research.lead_lag_1h_m2_probe import (
    HOUR_MS,
    atr14_sma,
    evaluate_path,
    market_time_nonoverlap,
    per_symbol_nonoverlap,
    signal_side,
)


def _bars(values: list[tuple[float, float, float, float]], start: int = 0) -> list[dict]:
    return [
        {"open_time_ms": start + i * HOUR_MS, "o": o, "h": h, "l": low, "c": c}
        for i, (o, h, low, c) in enumerate(values)
    ]


@pytest.mark.parametrize(
    "btc,eth,alt,expected",
    [
        (0.02, 0.01, 0.0, 1),
        (-0.02, -0.01, 0.0, -1),
        (0.02, -0.01, -0.2, 0),
        (0.02, 0.01, 0.02, 0),
        (-0.02, -0.01, -0.02, 0),
        (0.0, 0.01, -0.1, 0),
    ],
)
def test_signal_side_requires_consensus_and_strict_lag(btc, eth, alt, expected):
    assert signal_side(btc, eth, alt) == expected




def test_atr14_uses_exactly_14_completed_true_ranges_ending_at_signal_bar():
    high = np.full(16, 11.0)
    low = np.full(16, 9.0)
    close = np.full(16, 10.0)
    high[15] = 10000.0  # future bar must not enter the calculation at index 14
    assert atr14_sma(high, low, close, 14) == pytest.approx(2.0)
    assert atr14_sma(high, low, close, 13) is None


def test_target_hit_is_success_and_uses_conservative_target_price():
    bars = _bars([(100, 102, 100, 101)] + [(101, 102, 100, 101)] * 9)
    result = evaluate_path(1, 100.0, 1.0, bars, [], [], fee_rate=0.001)
    assert result["reason"] == "TARGET"
    assert result["m2_hit"] is True
    assert result["exit_price"] == 101.0
    assert result["net_return"] == pytest.approx(0.01 - 0.001)


def test_same_bar_double_touch_is_stop_first():
    bars = _bars([(100, 102, 98, 100)] + [(100, 100, 100, 100)] * 9)
    result = evaluate_path(1, 100.0, 1.0, bars, [], [])
    assert result["reason"] == "STOP"
    assert result["m2_hit"] is False
    assert result["exit_price"] == 99.0


def test_stop_gap_fills_at_adverse_open():
    bars = _bars([(97, 98, 96, 97)] + [(97, 97, 97, 97)] * 9)
    result = evaluate_path(1, 100.0, 1.0, bars, [], [])
    assert result["reason"] == "STOP_GAP"
    assert result["exit_price"] == 97.0
    assert result["gross_return"] == pytest.approx(-0.03)


def test_timeout_is_m2_failure_and_exits_at_tenth_close():
    bars = _bars([(100, 100.5, 99.5, 100.1)] * 9 + [(100, 100.5, 99.5, 100.2)])
    result = evaluate_path(1, 100.0, 2.0, bars, [], [])
    assert result["reason"] == "TIMEOUT"
    assert result["m2_hit"] is False
    assert result["exit_price"] == 100.2
    assert result["exit_index"] == 9


def test_funding_is_settlement_time_only_and_exit_bar_receipt_is_not_credited():
    start = 5_000_000
    bars = _bars([(100, 100.5, 99.5, 100)] * 9 + [(100, 101.1, 99.5, 101)], start)
    exit_bar_open = start + 9 * HOUR_MS
    funding_times = [start, start + HOUR_MS, exit_bar_open + 1, exit_bar_open + HOUR_MS]
    funding_rates = [0.02, 0.001, -0.002, -0.003]
    result = evaluate_path(1, 100.0, 1.0, bars, funding_times, funding_rates)
    assert result["reason"] == "TARGET"
    # Entry-time settlement is excluded; earlier payment included; exit-bar
    # payment is charged, but exit-bar receipt is not credited.
    assert result["funding_cost"] == pytest.approx(0.001)


def test_nonoverlap_is_outcome_blind_and_deterministic():
    rows = [
        {"symbol": "ETHUSDT", "signal_time_ms": 0, "entry_time_ms": 0},
        {"symbol": "BTCUSDT", "signal_time_ms": 0, "entry_time_ms": 0},
        {"symbol": "ETHUSDT", "signal_time_ms": 5 * HOUR_MS, "entry_time_ms": 5 * HOUR_MS},
        {"symbol": "ETHUSDT", "signal_time_ms": 10 * HOUR_MS, "entry_time_ms": 10 * HOUR_MS},
    ]
    per_symbol = per_symbol_nonoverlap(rows, HOUR_MS * 10)
    assert [(r["symbol"], r["signal_time_ms"]) for r in per_symbol] == [
        ("BTCUSDT", 0), ("ETHUSDT", 0), ("ETHUSDT", 10 * HOUR_MS)
    ]
    market = market_time_nonoverlap(rows, HOUR_MS * 10)
    assert [(r["symbol"], r["signal_time_ms"]) for r in market] == [
        ("BTCUSDT", 0), ("ETHUSDT", 10 * HOUR_MS)
    ]
