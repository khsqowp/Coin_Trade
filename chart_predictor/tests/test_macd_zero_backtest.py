import json

import numpy as np
import pandas as pd

from chart_predictor.macd_zero_backtest import (
    atr_wilder,
    block_bootstrap,
    ema,
    holm,
    load_funding,
    resample_minutes,
    resolve_long_bar,
    rsi_wilder,
    signal_arrays,
    simulate_symbol,
    trade_net_fraction,
    _select_policy,
)


def test_ema_is_recursive_and_prefix_invariant():
    x = np.array([10.0, 11.0, 8.0, 13.0, 20.0, 18.0])
    full = ema(x, 3)
    altered = x.copy()
    altered[4:] = [500.0, -100.0]
    changed = ema(altered, 3)
    assert np.allclose(full[:4], changed[:4])
    assert full[0] == x[0]
    assert full[1] == 0.5 * x[1] + 0.5 * x[0]


def test_rsi_and_atr_do_not_change_when_future_rows_change():
    close = np.linspace(100.0, 120.0, 80)
    high, low = close + 1, close - 1
    mutated = close.copy()
    mutated[60:] *= 0.25
    r1, r2 = rsi_wilder(close), rsi_wilder(mutated)
    a1 = atr_wilder(high, low, close)
    a2 = atr_wilder(high[:60], low[:60], mutated[:60])
    assert np.allclose(r1[:60], r2[:60], equal_nan=True)
    assert np.allclose(a1[:60], a2, equal_nan=True)


def test_zero_line_signal_is_closed_bar_cross_and_rsi_above_50():
    close = np.r_[np.full(80, 100.0), np.linspace(100.0, 160.0, 120)]
    bars = pd.DataFrame({"open_ms": np.arange(len(close), dtype=np.int64) * 60_000,
                         "open": close, "high": close + 1, "low": close - 1, "close": close})
    macd, _, signal, _ = signal_arrays(bars)
    idx = np.flatnonzero(signal)
    assert len(idx) > 0
    for i in idx:
        assert macd[i - 1] <= 0 < macd[i]
        assert rsi_wilder(close)[i] > 50


def test_resampler_discards_incomplete_utc_bucket():
    t = np.arange(11, dtype=np.int64) * 60_000
    close = np.arange(11, dtype=np.float64) + 100
    frame = pd.DataFrame({"open_ms": t, "open": close, "high": close + 1, "low": close - 1, "close": close})
    out = resample_minutes(frame, 5)
    assert out.open_ms.tolist() == [0, 300_000]
    assert out.open.tolist() == [100.0, 105.0]
    assert out.close.tolist() == [104.0, 109.0]


def test_ambiguous_stop_and_target_bar_uses_stop_and_gap_is_adverse():
    assert resolve_long_bar(100.0, 120.0, 80.0, 90.0, 110.0) == ("stop", 90.0)
    assert resolve_long_bar(85.0, 120.0, 80.0, 90.0, 110.0) == ("stop", 85.0)
    assert resolve_long_bar(100.0, 109.0, 95.0, 90.0, 110.0) == (None, None)


def test_trade_uses_next_bar_open_and_stops_scanning_after_target():
    close = np.r_[np.full(80, 100.0), np.linspace(100.0, 130.0, 120)]
    minute = pd.DataFrame({"open_ms": np.arange(close.size, dtype=np.int64) * 60_000,
                           "open": close, "high": close + 0.1, "low": close - 0.1, "close": close})
    trades = simulate_symbol(minute, minute, [], 1, 0, close.size * 60_000, "tp_2r")
    assert len(trades) == 1
    assert trades[0]["signal_time"] == 82 * 60_000
    assert trades[0]["entry_time"] == 82 * 60_000
    assert trades[0]["exit_reason"] == "target"
    assert trades[0]["target_first"] is True
    assert trades[0]["exit_time"] < trades[0]["entry_time"] + 20 * 60_000


def test_costs_are_applied_to_both_trade_sides_and_funding():
    trade = {"entry": 100.0, "exit": 110.0, "funding_raw_price_units": 0.25}
    net = trade_net_fraction(trade, fee=0.0005, slippage=0.0002)
    no_friction = (110.0 - 100.0) / 100.0
    assert net < no_friction
    np.testing.assert_allclose(net, 0.09603, atol=1e-6)


def test_missing_historical_funding_mark_uses_settlement_minute_open(tmp_path):
    base = tmp_path / "funding" / "snapshot" / "BTCUSDT"
    base.mkdir(parents=True)
    (base / "page_0000.json").write_text(json.dumps([
        {"fundingTime": 60_011, "fundingRate": "0.001", "markPrice": "", "rateType": "Regular"},
        {"fundingTime": 120_009, "fundingRate": "0.002", "markPrice": "105", "rateType": "Regular"},
    ]))
    minute = pd.DataFrame({"open_ms": [60_000, 120_000], "open": [101.0, 104.0]})
    events = load_funding(tmp_path, "snapshot", "BTCUSDT", 0, 180_000, minute)
    assert events == [{"time": 60_011, "rate": 0.001, "mark": 101.0},
                      {"time": 120_009, "rate": 0.002, "mark": 105.0}]


def test_validation_selection_enforces_minimum_trade_count():
    row = {"split": "validation", "timeframe_min": 60, "exit_policy": "tp_2r",
           "base": {"strategy": {"cagr": 0.2, "mdd_pct": 10},
                    "buy_hold": {"cagr": 0.1, "mdd_pct": 20},
                    "mean_net_trade_pct": 0.01, "trade_count": 29, "turnover": 1}}
    assert _select_policy([row]) == []
    row["base"]["trade_count"] = 30
    assert _select_policy([row])[0]["exit_policy"] == "tp_2r"


def test_holm_and_bootstrap_are_deterministic_and_bounded():
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    x = np.linspace(0.001, 0.01, 60)
    a = block_bootstrap(x, seed=7)
    b = block_bootstrap(x, seed=7)
    assert a == b
    assert a["ci95"][0] <= a["mean_daily_excess"] <= a["ci95"][1]
    assert 0 <= a["p_one_sided"] <= 1
