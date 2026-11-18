import sqlite3
from pathlib import Path

import pytest

from chart_predictor.micro_maru_feasibility import _screen


def run_screen(path, completed_through_ms=180_000):
    return _screen(path, expected_sha256=None, completed_through_ms=completed_through_ms)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "candles.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE candles(symbol TEXT,t_open_ms INTEGER,o REAL,h REAL,l REAL,c REAL)")
        # 0.80 body fraction is included; the next candle is never read as a label.
        db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?)", [
            ("AAA", 0, 100, 110, 100, 108),
            ("AAA", 60_000, 110, 110, 100, 102),
            ("AAA", 120_000, 101, 101, 101, 101),
            ("AAA", 180_000, 100, 110, 100, 108),
            ("LATE", 180_000, 100, 110, 100, 108),
        ])
    return path


def test_screen_is_read_only_and_counts_exact_boundary(db_path):
    before = db_path.read_bytes()
    result = run_screen(db_path)
    after = db_path.read_bytes()

    assert before == after
    assert result["scheduled_anchors"] == 2
    assert result["symbols"] == 1
    assert result["raw_events"] == 2
    assert result["long_events"] == 1
    assert result["short_events"] == 1
    assert result["outcome_rows_read"] == 0
    assert result["target_stop_labels_read"] == 0


def test_rejects_gaps_and_invalid_ohlc(db_path):
    with sqlite3.connect(db_path) as db:
        db.execute("DELETE FROM candles WHERE t_open_ms=60000")
    with pytest.raises(ValueError, match="non-contiguous"):
        run_screen(db_path)


def test_rejects_nonfinite_and_offgrid_rows(db_path):
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE candles SET h=? WHERE t_open_ms=0", (float("inf"),))
    with pytest.raises(ValueError, match="non-finite"):
        run_screen(db_path)

    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE candles SET h=110,t_open_ms=1 WHERE t_open_ms=0")
    with pytest.raises(ValueError, match="off-grid"):
        run_screen(db_path)


def test_rejects_fractional_timestamp_before_integer_coercion(db_path):
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE candles SET t_open_ms=60000.5 WHERE t_open_ms=60000")
    with pytest.raises(ValueError, match="non-integer timestamp"):
        run_screen(db_path)


def test_rejects_sqlite_sidecars(db_path):
    Path(str(db_path) + "-wal").write_bytes(b"uncommitted-sidecar")
    with pytest.raises(ValueError, match="SQLite sidecar present"):
        run_screen(db_path)


def test_cooldown_accepts_signal_exactly_at_horizon_boundary(tmp_path):
    path = tmp_path / "cooldown.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE candles(symbol TEXT,t_open_ms INTEGER,o REAL,h REAL,l REAL,c REAL)")
        rows = []
        for index in range(21):
            close = 108 if index % 2 == 0 else 102
            rows.append(("AAA", index * 60_000, 100, 110, 100, close))
        db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?)", rows)

    result = run_screen(path, completed_through_ms=1_260_000)
    assert result["per_symbol"][0]["cooldown_events_10m"] == 3
    assert result["per_symbol"][0]["cooldown_events_20m"] == 2
