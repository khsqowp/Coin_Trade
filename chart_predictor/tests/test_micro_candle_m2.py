import importlib.util
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).parents[1] / "micro_candle_m2.py"
SPEC = importlib.util.spec_from_file_location("micro_candle_m2", MODULE_PATH)
m2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m2)


def fixture_path():
    t = np.arange(50, dtype=np.int64) * m2.MINUTE
    o = np.full(50, 100.0)
    h = np.full(50, 100.5)
    l = np.full(50, 99.5)
    c = np.full(50, 100.0)
    atr = np.ones(50)
    return t, o, h, l, c, atr


def test_target_first_on_future_bar():
    t, o, h, l, c, atr = fixture_path()
    h[11] = 101.1
    scored = m2.score_chunk(t, o, h, l, c, atr, np.array([10]),
                            np.array([1], dtype=np.int8), 10, "BTCUSDT")
    assert scored[0, 0] == 1
    assert scored[0, 1] == 1


def test_same_bar_target_stop_tie_is_stop_first():
    t, o, h, l, c, atr = fixture_path()
    h[11], l[11] = 101.1, 98.9
    scored = m2.score_chunk(t, o, h, l, c, atr, np.array([10]),
                            np.array([1], dtype=np.int8), 10, "BTCUSDT")
    assert scored[0, 0] == 1
    assert scored[0, 1] == 0


def test_missing_path_is_unresolved():
    t, o, h, l, c, atr = fixture_path()
    t[15] += 1
    scored = m2.score_chunk(t, o, h, l, c, atr, np.array([10]),
                            np.array([1], dtype=np.int8), 10, "BTCUSDT")
    assert scored[0, 0] == 0


def test_missing_first_entry_bar_is_unresolved_not_silently_dropped():
    t, o, h, l, c, atr = fixture_path()
    t[11] += 1
    scored = m2.score_chunk(t, o, h, l, c, atr, np.array([10]),
                            np.array([1], dtype=np.int8), 10, "BTCUSDT")
    assert scored[0, 0] == 0


def test_timeout_is_resolved_failure():
    t, o, h, l, c, atr = fixture_path()
    scored = m2.score_chunk(t, o, h, l, c, atr, np.array([10]),
                            np.array([1], dtype=np.int8), 10, "BTCUSDT")
    assert scored[0, 0] == 1
    assert scored[0, 1] == 0
    assert scored[0, 2] == 1


def test_execution_label_does_not_read_beyond_registered_horizon():
    for horizon in (10, 20):
        t, o, h, l, c, atr = fixture_path()
        anchor = 10
        side = np.array([1], dtype=np.int8)
        baseline = m2.score_chunk(t, o, h, l, c, atr, np.array([anchor]),
                                  side, horizon, "BTCUSDT")

        # The next-open entry is anchor+1; the final scored bar is anchor+horizon.
        first_unscored = anchor + horizon + 1
        o[first_unscored:] += 25.0
        h[first_unscored:] += 25.0
        l[first_unscored:] += 25.0
        c[first_unscored:] += 25.0
        changed_after_deadline = m2.score_chunk(
            t, o, h, l, c, atr, np.array([anchor]), side, horizon, "BTCUSDT"
        )

        np.testing.assert_array_equal(changed_after_deadline, baseline)


def test_malformed_ohlc_path_is_unresolved():
    t, o, h, l, c, atr = fixture_path()
    h[11] = 98.0
    scored = m2.score_chunk(t, o, h, l, c, atr, np.array([10]),
                            np.array([1], dtype=np.int8), 10, "BTCUSDT")
    assert scored[0, 0] == 0


def test_adverse_long_stop_gap_fills_at_open():
    t, o, h, l, c, atr = fixture_path()
    o[12], h[12], l[12], c[12] = 98.0, 98.5, 97.5, 98.2
    result = m2.score_signal(t, o, h, l, c, atr, 10, 1, 10)
    assert result is not None
    assert result[0] is False and result[1] is False
    assert result[2] < -1.9


def test_adverse_short_stop_gap_fills_at_open():
    t, o, h, l, c, atr = fixture_path()
    o[12], h[12], l[12], c[12] = 102.0, 102.5, 101.5, 101.8
    result = m2.score_signal(t, o, h, l, c, atr, 10, -1, 10)
    assert result is not None
    assert result[0] is False and result[1] is False
    assert result[2] < -1.9


def test_single_candle_features_are_prefix_invariant_with_future_peek_control(tmp_path):
    import sqlite3

    def make_db(path, future_shift):
        db = sqlite3.connect(path)
        db.execute("""CREATE TABLE candles(
            symbol TEXT, open_ms INTEGER, open REAL, high REAL, low REAL, close REAL,
            volume REAL, quote_volume REAL, trade_count INTEGER,
            PRIMARY KEY(symbol,open_ms))""")
        rows = []
        for i in range(40):
            shift = future_shift if i >= 25 else 0.0
            op = 100.0 + shift
            rows.append(("TESTUSDT", i*m2.MINUTE, op, op+1.0, op-1.0,
                         op+0.5, 1.0, op+0.5, 1))
        db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)", rows)
        db.commit()
        return db

    base_db = make_db(tmp_path / "base.sqlite", 0.0)
    changed_db = make_db(tmp_path / "future_changed.sqlite", 20.0)
    try:
        base = m2.load_symbol(base_db, "TESTUSDT")
        changed = m2.load_symbol(changed_db, "TESTUSDT")
    finally:
        base_db.close()
        changed_db.close()

    cutoff = 25
    for feature_index in (5, 6):  # ATR and emitted one-candle signal
        np.testing.assert_array_equal(base[feature_index][:cutoff],
                                      changed[feature_index][:cutoff])

    # Negative control: a feature that reads the next candle must be changed
    # when only data after the cutoff are mutated.
    def leaking_next_close(close):
        out = np.zeros(len(close), dtype=np.int8)
        out[:-1] = np.sign(np.diff(close)).astype(np.int8)
        return out

    assert leaking_next_close(base[4])[cutoff-1] != leaking_next_close(changed[4])[cutoff-1]
