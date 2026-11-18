import json
import sqlite3
from urllib.parse import parse_qs, urlparse

import pytest

from chart_predictor.data_quality import audit_candles, write_report
from chart_predictor.store import connect_trials, cumulative_trial_count, record_trial
from chart_predictor import repair_vision_gaps
from chart_predictor.setup_backtest import _write
from chart_predictor.merge_vision_repair import merge


def _database(path):
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE candles(
        symbol TEXT NOT NULL, t_open_ms INTEGER NOT NULL, o REAL, h REAL, l REAL,
        c REAL, v REAL, quote_v REAL, trades INTEGER,
        PRIMARY KEY(symbol, t_open_ms))""")
    db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)", [
        ("BTCUSDT", 0, 10, 12, 9, 11, 1, 11, 2),
        ("BTCUSDT", 60_000, 11, 13, 10, 12, 2, 24, 3),
        # Missing minute at 120_000 is deliberately represented by a gap.
        ("BTCUSDT", 180_000, 12, 14, 11, 13, 3, 39, 4),
        ("ETHUSDT", 0, 10, 9, 11, 10, -1, 0, 0),
    ])
    db.commit()
    db.close()


def test_audit_counts_rows_gaps_and_invalid_ohlcv_without_writing(tmp_path):
    path = tmp_path / "candles.sqlite"
    _database(path)
    before = path.read_bytes()

    report = audit_candles(path)

    assert report["total_rows"] == 4
    assert report["symbol_count"] == 2
    assert report["window_missing_minutes"] == 1
    assert report["invalid_ohlcv_rows"] == 1
    assert report["duplicate_rows"] == 0
    assert path.read_bytes() == before


def test_audit_requested_window_includes_missing_leading_and_trailing_minutes(tmp_path):
    path = tmp_path / "candles.sqlite"
    _database(path)

    report = audit_candles(path, start_ms=0, end_ms=300_000)

    # BTC is missing one interior and one trailing minute; ETH four trailing minutes.
    assert report["window_missing_minutes"] == 6


def test_audit_rejects_wrong_schema(tmp_path):
    path = tmp_path / "wrong.sqlite"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE candles(symbol TEXT)")
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="missing columns"):
        audit_candles(path)


def test_off_grid_row_does_not_hide_missing_open(tmp_path):
    path = tmp_path / "off-grid.sqlite"
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE candles(
        symbol TEXT NOT NULL, t_open_ms INTEGER NOT NULL, o REAL, h REAL, l REAL,
        c REAL, v REAL, quote_v REAL, trades INTEGER,
        PRIMARY KEY(symbol, t_open_ms))""")
    db.executemany("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)", [
        ("BTCUSDT", 0, 10, 12, 9, 11, 1, 11, 2),
        ("BTCUSDT", 60_000, 11, 13, 10, 12, 2, 24, 3),
        ("BTCUSDT", 120_001, 12, 14, 11, 13, 3, 39, 4),
    ])
    db.commit()
    db.close()

    report = audit_candles(path)

    assert report["off_grid_rows"] == 1
    assert report["window_missing_minutes"] == 1


def test_report_is_parseable_and_lists_each_symbol(tmp_path):
    path = tmp_path / "candles.sqlite"
    _database(path)
    report = audit_candles(path)
    json_path, markdown_path = tmp_path / "audit.json", tmp_path / "audit.md"

    write_report(report, json_path, markdown_path)

    assert json.loads(json_path.read_text())["metadata_fingerprint"] == report["metadata_fingerprint"]
    assert "BTCUSDT" in markdown_path.read_text()
    assert "ETHUSDT" in markdown_path.read_text()


def test_identical_trial_reuses_record_but_changed_fingerprint_counts(tmp_path):
    db = connect_trials(tmp_path / "trials.sqlite")
    args = ("2026-11-15T00:00:00Z", "setups", "P9", "abc", "dev", "fixed hypothesis", 20)

    first = record_trial(db, *args, data_fingerprint="data-a")
    repeated = record_trial(db, *args, data_fingerprint="data-a")
    changed_data = record_trial(db, *args, data_fingerprint="data-b")

    assert first == repeated
    assert changed_data != first
    assert cumulative_trial_count(db) == 2
    db.close()


def test_setup_report_identity_changes_with_data_or_code(tmp_path):
    base = {"stage": "A", "split": "dev", "start_ms": 0, "cutoff_exclusive_ms": 60_000,
            "symbols": ["BTCUSDT"], "tested_setups": ["setup"], "timeframes": ["1m"],
            "fee_per_side": 0.0005, "slippage": "fixed", "runtime_seconds": 1,
            "cells_tested": 0, "results": [], "hypotheses": {}}
    _, _ = _write(dict(base), tmp_path / "first", "data-a", "A")
    _, _ = _write(dict(base), tmp_path / "second", "data-b", "A")
    first_path = next((tmp_path / "first").glob("report_*.json"))
    second_path = next((tmp_path / "second").glob("report_*.json"))
    first_report, second_report = json.loads(first_path.read_text()), json.loads(second_path.read_text())

    assert first_report["fingerprint"] != second_report["fingerprint"]
    assert first_report["data_fingerprint"] == "data-a"
    assert second_report["data_fingerprint"] == "data-b"


def test_gap_repair_is_idempotent_and_keeps_source_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(repair_vision_gaps, "GAPS", (("BTCUSDT", 0, 120_000),))

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return self.payload

    def opener(request, timeout):
        params = parse_qs(urlparse(request.full_url).query)
        start = int(params["startTime"][0])
        end = int(params["endTime"][0]) + 1
        rows = [[stamp, "10", "12", "9", "11", "1", stamp + 59_999,
                 "11", 2, "0.5", "5", "0"] for stamp in range(start, end, 60_000)]
        return Response(json.dumps(rows).encode())

    path = tmp_path / "repair.sqlite"
    first = repair_vision_gaps.repair(path, opener=opener, sleep=lambda _: None)
    second = repair_vision_gaps.repair(path, opener=opener, sleep=lambda _: None)
    db = sqlite3.connect(path)
    pages = db.execute("SELECT COUNT(*), length(payload) FROM repair_pages").fetchone()
    db.close()

    assert first["rows"] == second["rows"] == 2
    assert pages[0] == 1 and pages[1] > 0


def test_merge_builds_new_snapshot_and_preserves_repair_provenance(tmp_path):
    source, patch, output = (tmp_path / name for name in
                             ("source.sqlite", "patch.sqlite", "merged.sqlite"))
    schema = """CREATE TABLE candles(
      symbol TEXT NOT NULL, open_ms INTEGER NOT NULL, open REAL NOT NULL,
      high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
      volume REAL NOT NULL, close_ms INTEGER NOT NULL, quote_volume REAL NOT NULL,
      trade_count INTEGER NOT NULL, taker_buy_base REAL NOT NULL,
      taker_buy_quote REAL NOT NULL, PRIMARY KEY(symbol,open_ms))"""
    db = sqlite3.connect(source)
    db.execute(schema)
    db.execute("INSERT INTO candles VALUES('BTCUSDT',0,10,12,9,11,1,59999,11,1,0.5,5)")
    db.commit()
    db.close()
    db = sqlite3.connect(patch)
    db.execute(schema)
    db.execute("INSERT INTO candles VALUES('BTCUSDT',60000,11,13,10,12,1,119999,12,1,0.5,6)")
    db.execute("CREATE TABLE repair_pages(sha256 TEXT, payload BLOB)")
    db.execute("INSERT INTO repair_pages VALUES('digest',x'7b7d')")
    db.commit()
    db.close()
    original_bytes = source.read_bytes()

    report = merge(source, patch, output)
    merged = sqlite3.connect(output)
    rows = merged.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
    page_rows = merged.execute("SELECT COUNT(*) FROM repair_pages").fetchone()[0]
    merged.close()

    assert report["merged_rows"] == rows == 2
    assert report["retained_repair_pages"] == page_rows == 1
    assert report["observed_span_gaps"] == []
    assert source.read_bytes() == original_bytes
