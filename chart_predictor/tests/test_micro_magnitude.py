import sqlite3

from chart_predictor import micro_magnitude as mm


def test_symbol_scan_is_chunk_invariant_and_excludes_invalid_three_bar_windows(tmp_path, monkeypatch):
    db = tmp_path / "candles.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE candles (symbol TEXT, open_ms INTEGER, open REAL, high REAL, "
        "low REAL, close REAL, volume REAL, PRIMARY KEY(symbol,open_ms))"
    )
    price = 100.0
    rows = []
    for index in range(30):
        open_price = price
        price *= 1.001 if index % 2 else 0.999
        close_price = price
        high = max(open_price, close_price) * 1.001
        low = min(open_price, close_price) * 0.999
        if index == 15:
            high = low / 2  # invalid OHLC; adjacent prediction triples are ineligible
        rows.append(("TEST", index * mm.MINUTE_MS, open_price, high, low, close_price, 1.0))
    conn.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    monkeypatch.setattr(mm, "TRAIN_START", 0)
    monkeypatch.setattr(mm, "TRAIN_END", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_START", 10 * mm.MINUTE_MS)
    monkeypatch.setattr(mm, "EVAL_END", mm.EVAL_START + 2 * 86_400_000)
    monkeypatch.setattr(mm, "MIN_TRAIN", 2)
    monkeypatch.setattr(mm, "MIN_EVAL", 2)
    monkeypatch.setattr(mm, "CHUNK_ROWS", 4)

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    result = mm._analyze_symbol(conn, "TEST")
    conn.close()

    assert result["eligible"] is True
    assert result["train_returns"] == 9
    assert result["eval_forecasts"] == 15
    assert result["invalid_rows"] == 1
    assert result["offgrid_rows"] == 0
    assert result["adjacency_gaps"] == 0
