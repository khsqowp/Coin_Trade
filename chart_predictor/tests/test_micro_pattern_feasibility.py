import sqlite3

from chart_predictor.micro_pattern_feasibility import screen


def test_two_bar_pattern_is_counted_without_forward_outcomes(tmp_path):
    db_path = tmp_path / "micro.sqlite"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE candles(symbol TEXT,t_open_ms INTEGER,o REAL,h REAL,l REAL,c REAL,PRIMARY KEY(symbol,t_open_ms))")
    rows = []
    for i in range(30):
        stamp = i * 60_000
        rows.append(("TESTUSDT", stamp, 100.0, 100.5, 99.5, 100.1))
    # One large bearish impulse followed by a contained close in its upper quartile.
    rows[21] = ("TESTUSDT", 21 * 60_000, 100.8, 101.0, 99.0, 99.4)
    rows[22] = ("TESTUSDT", 22 * 60_000, 99.5, 100.8, 99.3, 100.6)
    db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?)", rows)
    db.commit()
    db.close()

    result = screen(db_path)

    assert result["scheduled_anchors"] == 8
    assert result["raw_events"] == 1
    assert result["per_symbol"][0]["long_events"] == 1
    assert result["per_symbol"][0]["short_events"] == 0
    assert result["outcome_rows_read"] == 0
    assert result["target_stop_labels_read"] == 0
