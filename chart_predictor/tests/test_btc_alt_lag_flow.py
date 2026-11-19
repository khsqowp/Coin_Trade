import pandas as pd

from chart_predictor.btc_alt_lag_flow import (
    build_symbol_features,
    rank_lagged_alts,
    resolve_bracket,
)


def test_resolve_bracket_stop_first_when_target_and_stop_touch_same_bar():
    bars = pd.DataFrame([{
        "open_ms": 60_000, "open": 100.0, "high": 101.0,
        "low": 99.0, "close": 100.2,
    }])
    result = resolve_bracket(1, 100.0, bars)
    assert result["label"] == "stop"
    assert result["exit_price"] == 99.7


def test_resolve_bracket_uses_adverse_gap_open_for_stop():
    bars = pd.DataFrame([{
        "open_ms": 60_000, "open": 99.0, "high": 99.5,
        "low": 98.8, "close": 99.2,
    }])
    result = resolve_bracket(1, 100.0, bars)
    assert result["label"] == "stop"
    assert result["exit_price"] == 99.0


def test_resolve_bracket_requires_contiguous_minutes():
    bars = pd.DataFrame([
        {"open_ms": 60_000, "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0},
        {"open_ms": 180_000, "open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0},
    ])
    assert resolve_bracket(1, 100.0, bars)["label"] == "unscorable"


def test_resolve_bracket_short_target_and_vertical_timeout():
    short_target = pd.DataFrame([{
        "open_ms": 60_000, "open": 100.0, "high": 100.2,
        "low": 99.3, "close": 99.5,
    }])
    assert resolve_bracket(-1, 100.0, short_target)["label"] == "target"
    quiet = pd.DataFrame([{
        "open_ms": 60_000 * i, "open": 100.0, "high": 100.1,
        "low": 99.9, "close": 100.0,
    } for i in range(1, 16)])
    assert resolve_bracket(1, 100.0, quiet)["label"] == "timeout"


def test_lag_rank_prefers_largest_same_direction_underperformance():
    btc_30m = 0.004
    alts = [
        {"symbol": "ETHUSDT", "ret_30m": 0.003, "imbalance_5m": 0.12},
        {"symbol": "SOLUSDT", "ret_30m": -0.002, "imbalance_5m": 0.22},
        {"symbol": "XRPUSDT", "ret_30m": 0.002, "imbalance_5m": 0.19},
    ]
    ranked = rank_lagged_alts(1, btc_30m, alts)
    assert [row["symbol"] for row in ranked] == ["SOLUSDT", "XRPUSDT", "ETHUSDT"]


def test_feature_prefix_is_unchanged_when_future_rows_are_appended():
    start = 1_700_000_040_000
    rows = []
    for i in range(24 * 60):
        price = 100.0 + i * 0.01
        rows.append({
            "open_ms": start + i * 60_000, "open": price, "high": price + 0.1,
            "low": price - 0.1, "close": price + 0.02,
            "quote_volume": 1000.0, "taker_buy_quote": 600.0,
        })
    frame = pd.DataFrame(rows)
    full = build_symbol_features(frame)
    prefix = build_symbol_features(frame.iloc[: 12 * 60])
    cols = ["ret_5m", "imbalance_5m", "ret_30m"]
    completed = prefix.index <= int(frame.iloc[12 * 60 - 1].open_ms) + 60_000
    pd.testing.assert_frame_equal(full.loc[prefix.index[completed], cols], prefix.loc[prefix.index[completed], cols])
