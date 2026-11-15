import numpy as np
import pandas as pd

from scripts.research.equity_kr_compression_breakout import (
    COSTS,
    signals_and_features,
    load_bars,
    simulate_breakout,
)


def test_cutoff_stops_before_parsing_future_ohlcv(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text(
        "timestamp,Open,High,Low,Close,Volume\n"
        "2024-11-11 00:00:00+00:00,10,11,9,10,100\n"
        "2024-11-12 00:00:00+00:00,not-a-number\n",
        encoding="utf-8",
    )
    dates, opens, closes, digest = load_bars(path)
    assert len(dates) == 1
    assert opens.tolist() == [10.0]
    assert closes.tolist() == [10.0]
    assert len(digest) == 64


def test_features_are_prefix_invariant_under_future_mutation():
    rng = np.random.default_rng(17)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 900)))
    prefix = 700
    original = signals_and_features(close)
    mutated = close.copy()
    mutated[prefix:] *= np.exp(np.linspace(0, 5, len(mutated) - prefix))
    changed = signals_and_features(mutated)
    for left, right in zip(original, changed):
        np.testing.assert_allclose(left[:prefix], right[:prefix], equal_nan=True)


def test_entry_and_time_exit_use_next_session_open():
    n = 32
    dates = pd.date_range("2024-01-01", periods=n, freq="B", tz="UTC")
    opens = np.full(n, 100.0)
    closes = np.full(n, 100.0)
    closes[1] = 101.0
    signals = np.zeros(n, dtype=bool)
    signals[0] = True
    sma20 = np.zeros(n)
    row, trades, _ = simulate_breakout(
        dates, opens, closes, signals, sma20, 0, COSTS["base"], "base",
        np.ones(n),
    )
    assert len(trades) == 1
    assert trades[0]["entry_date"] == dates[1].isoformat()
    assert trades[0]["exit_date"] == dates[11].isoformat()
    assert trades[0]["exit_reason"] == "10_session_expiry"
    assert row["trades"] == 1


def test_compression_threshold_excludes_current_volatility_observation():
    close = np.linspace(100, 200, 600)
    _, _, _, threshold = signals_and_features(close)
    assert np.isnan(threshold[261])
    assert np.isfinite(threshold[262])
