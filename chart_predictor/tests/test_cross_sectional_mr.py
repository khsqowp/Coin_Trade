import numpy as np
import pandas as pd
import sqlite3

from chart_predictor.cross_sectional_mr import (
    DEV_CUTOFF_MS,
    HOUR_MS,
    MINUTE_MS,
    START_MS,
    Signal,
    build_signals,
    load_market,
    load_universe,
    resolve_signal,
    simulate_portfolio,
)


def minute_frame(count=720):
    times = np.arange(count, dtype=np.int64) * MINUTE_MS
    return pd.DataFrame({
        "t_open_ms": times,
        "o": np.full(count, 100.0),
        "h": np.full(count, 100.1),
        "l": np.full(count, 99.9),
        "c": np.full(count, 100.0),
    })


def test_barrier_collision_is_scored_as_stop():
    frame = minute_frame()
    frame.loc[0, ["h", "l"]] = [101.0, 97.0]
    result = resolve_signal(Signal(0, "BTCUSDT", 1, -0.1, 1.0, "mean_reversion"), frame, 0.0005, 0.0)
    assert result["status"] == "scorable"
    assert result["reason"] == "stop"
    assert result["target_first"] is False


def test_stop_gap_fills_at_open_not_stop_level():
    frame = minute_frame()
    frame.loc[1, ["o", "h", "l", "c"]] = [95.0, 95.5, 94.5, 95.0]
    result = resolve_signal(Signal(0, "BTCUSDT", 1, -0.1, 1.0, "mean_reversion"), frame, 0.0, 0.001)
    assert result["reason"] == "stop"
    assert result["exit"] < 95.0


def test_missing_execution_minute_is_unscorable_not_timeout():
    frame = minute_frame()
    frame = frame.drop(index=120).reset_index(drop=True)
    result = resolve_signal(Signal(0, "BTCUSDT", 1, -0.1, 1.0, "mean_reversion"), frame, 0.0005, 0.0004)
    assert result == {"status": "unscorable", "reason": "incomplete_execution_path"}


def test_cross_sectional_signal_uses_only_anchor_rows_and_reverses_extremes():
    index = pd.Index([START_MS - 2 * HOUR_MS, START_MS - HOUR_MS], dtype="int64")
    hours = {}
    symbols = [f"S{i:02d}" for i in range(20)]
    for rank, symbol in enumerate(symbols):
        hours[symbol] = pd.DataFrame({
            "ret24": [0.0, float(rank)],
            "atr14": [1.0, 1.0],
        }, index=index)
    mr = build_signals(hours, "mean_reversion")
    mom = build_signals(hours, "cross_sectional_momentum")
    mr_at_anchor = [signal for signal in mr if signal.time_ms == START_MS]
    mom_at_anchor = [signal for signal in mom if signal.time_ms == START_MS]
    assert {s.symbol for s in mr_at_anchor if s.side == 1} == set(symbols[:4])
    assert {s.symbol for s in mr_at_anchor if s.side == -1} == set(symbols[-4:])
    assert {s.symbol for s in mom_at_anchor if s.side == 1} == set(symbols[-4:])
    assert {s.symbol for s in mom_at_anchor if s.side == -1} == set(symbols[:4])
    assert all(s.time_ms < DEV_CUTOFF_MS for s in mr)


def test_entry_minute_target_is_allowed_after_open_entry():
    frame = minute_frame()
    frame.loc[0, "h"] = 100.7
    result = resolve_signal(Signal(0, "BTCUSDT", 1, -0.1, 1.0, "mean_reversion"), frame, 0.0, 0.0)
    assert result["reason"] == "target"
    assert result["exit_ms"] == 0


def test_feature_prefix_is_unchanged_when_future_rows_are_added():
    index = pd.Index([START_MS - 2 * HOUR_MS, START_MS - HOUR_MS, START_MS], dtype="int64")
    hours = {}
    extended = {}
    for rank in range(20):
        symbol = f"S{rank:02d}"
        base = pd.DataFrame({"ret24": [rank / 10, rank / 9, rank / 8], "atr14": [1.0] * 3}, index=index)
        hours[symbol] = base.iloc[:2]
        extended[symbol] = base
    prefix_signals = [s for s in build_signals(hours, "mean_reversion") if s.time_ms < START_MS]
    full_signals = [s for s in build_signals(extended, "mean_reversion") if s.time_ms < START_MS]
    assert prefix_signals == full_signals


def test_loader_is_read_only_and_resamples_only_complete_hours(tmp_path):
    db_path = tmp_path / "candles.sqlite"
    universe_path = tmp_path / "universe.json"
    symbols = [f"S{i:02d}" for i in range(20)]
    universe_path.write_text(__import__("json").dumps(symbols))
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE candles(symbol TEXT,t_open_ms INTEGER,o REAL,h REAL,l REAL,c REAL,quote_v REAL)"
    )
    for symbol in symbols:
        connection.executemany(
            "INSERT INTO candles VALUES(?,?,?,?,?,?,?)",
            [(symbol, i * MINUTE_MS, 100, 101, 99, 100, 5) for i in range(120)],
        )
    connection.commit()
    before = db_path.stat().st_mtime_ns
    minutes, hours, fingerprint = load_market(db_path, load_universe(universe_path))
    after = db_path.stat().st_mtime_ns
    assert before == after
    assert len(minutes["S00"]) == 120
    assert len(hours["S00"]) == 2
    assert len(fingerprint) == 64
    connection.close()


def test_portfolio_respects_eight_slots_and_one_x_gross_cap():
    frame = minute_frame(721)
    frame["t_open_ms"] += START_MS
    minutes = {f"S{i:02d}": frame for i in range(20)}
    signals = [
        Signal(START_MS, symbol, 1 if i < 4 else -1, float(i), 1.0, "mean_reversion")
        for i, symbol in enumerate(minutes)
    ]
    result = simulate_portfolio(signals, minutes, fee=0.0, slippage=0.0)
    assert result["completed_positions"] == 8
    assert result["max_gross_to_nav"] <= 1.0000001

