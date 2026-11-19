import numpy as np
import pytest

from chart_predictor.ts_momentum_market import (
    load_daily,
    market_close_index,
    signal_series,
    simulate,
)


def make_closes(n=400):
    t = np.arange(n, dtype=float)
    return np.column_stack([100 * np.exp(0.0005 * t + 0.00001 * t**2 + j * 0.0001 * t)
                            for j in range(6)])


def test_market_index_is_equal_weight_daily_rebalanced():
    closes = np.array([[100] * 6, [110, 100, 100, 100, 100, 100]], dtype=float)
    np.testing.assert_allclose(market_close_index(closes), [1.0, 1.0 + 0.1 / 6])


def test_signal_threshold_excludes_current_and_future_data():
    closes = make_closes()
    signal, eligible, exposure = signal_series(closes, lookback=10, holding=5, min_history=30)
    t = 100
    future_changed = closes.copy()
    future_changed[t + 1:] *= 2.0
    signal2, eligible2, exposure2 = signal_series(future_changed, lookback=10, holding=5, min_history=30)
    np.testing.assert_array_equal(signal[:t + 1], signal2[:t + 1])
    np.testing.assert_array_equal(eligible[:t + 1], eligible2[:t + 1])
    np.testing.assert_allclose(exposure[:t + 2], exposure2[:t + 2])


def test_signal_warmup_and_exposure_are_causal_and_bounded():
    signal, eligible, exposure = signal_series(make_closes(360), lookback=10, holding=5, min_history=30)
    assert not eligible[:40].any()
    assert eligible[40]
    assert np.all((exposure >= 0) & (exposure <= 1))
    assert exposure[40] == np.mean(signal[35:40])


def test_zero_exposure_stays_cash_and_charges_nothing():
    opens = np.full((4, 6), 100.0)
    closes = np.full((4, 6), 100.0)
    result = simulate(opens, closes, np.zeros(4), cost_per_side=0.0009)
    assert result["nav"] == pytest.approx(1.0)
    assert result["turnover"].sum() == pytest.approx(0.0)
    assert result["cost"].sum() == pytest.approx(0.0)


def test_entry_exit_costs_and_growth_reconcile_to_manual_example():
    opens = np.full((3, 6), 100.0)
    closes = np.full((3, 6), 100.0)
    closes[1] = 110.0
    opens[2] = 110.0
    closes[2] = 110.0
    exposure = np.array([0.0, 1.0, 0.0])
    result = simulate(opens, closes, exposure, cost_per_side=0.001)
    # Entry costs 10 bp at day 1 open; a 10% intraday gain; exit costs 10 bp at day 2 open.
    expected = (1 - 0.001) * 1.10 * (1 - 0.001)
    assert result["nav"] == pytest.approx(expected)
    assert np.all((result["exposure"] >= 0) & (result["exposure"] <= 1))


def test_loader_refuses_missing_minutes_and_keeps_database_read_only(tmp_path):
    import sqlite3
    from chart_predictor.ts_momentum_market import DAY_MS, MINUTE_MS, SYMBOLS

    db = tmp_path / "candles.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE candles(symbol TEXT, open_ms INTEGER, open REAL, high REAL, low REAL, close REAL)")
    start = 20 * DAY_MS
    for symbol in SYMBOLS:
        for i in range(1440):
            if symbol == SYMBOLS[0] and i == 25:
                continue
            price = 100.0 + i / 10000
            conn.execute("INSERT INTO candles VALUES(?,?,?,?,?,?)",
                         (symbol, start + i * MINUTE_MS, price, price + 1, price - 1, price))
    conn.commit(); conn.close()
    with pytest.raises(ValueError, match="Incomplete/invalid"):
        load_daily(db, start, start + DAY_MS)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 8639
    conn.close()


def test_loader_refuses_off_grid_minute_that_preserves_count_and_endpoints(tmp_path):
    import sqlite3
    from chart_predictor.ts_momentum_market import DAY_MS, MINUTE_MS, SYMBOLS

    db = tmp_path / "offgrid.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE candles(symbol TEXT, open_ms INTEGER, open REAL, high REAL, low REAL, close REAL, PRIMARY KEY(symbol,open_ms))")
    start = 30 * DAY_MS
    for symbol in SYMBOLS:
        for i in range(1440):
            minute = i
            if symbol == SYMBOLS[0] and i == 25:
                minute = 25.5
            price = 100.0 + i / 10000
            conn.execute("INSERT INTO candles VALUES(?,?,?,?,?,?)",
                         (symbol, start + int(minute * MINUTE_MS), price, price + 1, price - 1, price))
    conn.commit(); conn.close()
    with pytest.raises(ValueError, match="Incomplete/invalid"):
        load_daily(db, start, start + DAY_MS)


def test_loader_fingerprints_aggregated_panel_deterministically(tmp_path):
    import sqlite3
    from chart_predictor.ts_momentum_market import DAY_MS, MINUTE_MS, SYMBOLS

    db = tmp_path / "complete.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE candles(symbol TEXT, open_ms INTEGER, open REAL, high REAL, low REAL, close REAL, PRIMARY KEY(symbol,open_ms))")
    start = 40 * DAY_MS
    for symbol in SYMBOLS:
        for i in range(1440):
            price = 100.0 + i / 10000
            conn.execute("INSERT INTO candles VALUES(?,?,?,?,?,?)",
                         (symbol, start + i * MINUTE_MS, price, price + 1, price - 1, price + .5))
    conn.commit(); conn.close()
    first = load_daily(db, start, start + DAY_MS)
    second = load_daily(db, start, start + DAY_MS)
    assert first.source_rows == 8640
    assert len(first.panel_sha256) == 64
    assert first.panel_sha256 == second.panel_sha256
