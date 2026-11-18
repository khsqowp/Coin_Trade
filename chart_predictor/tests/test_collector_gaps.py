import json
import sqlite3
import sys
import pytest
from chart_predictor import cli
from chart_predictor.collector import collect_symbol, connect


def kline(open_ms):
    """Return one already-completed Binance kline payload."""
    return [open_ms, "10", "11", "9", "10.5", "3", open_ms+59_999, "31.5", 7, "0", "0", "0"]


class Response:
    """Minimal HTTP response for offline collector tests."""
    status_code = 200
    headers = {}
    def __init__(self, rows): self.rows = rows
    def json(self): return self.rows
    def raise_for_status(self): pass


class Session:
    """Capture requested ranges and return one mocked page per missing range."""
    def __init__(self, pages): self.pages, self.calls = list(pages), []
    def get(self, url, **kwargs):
        self.calls.append(kwargs["params"])
        return Response(self.pages.pop(0))


def test_collector_fills_leading_internal_and_trailing_gaps(tmp_path):
    db = connect(tmp_path / "candles.sqlite")
    start = 1_700_000_000_000 // 60_000 * 60_000
    for minute in (2, 5):
        row = kline(start + minute*60_000)
        db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)",
                   ("BTCUSDT", row[0], 10, 11, 9, 10.5, 3, 31.5, 7))
    db.commit()
    pages = [[kline(start+i*60_000) for i in (0, 1)],
             [kline(start+i*60_000) for i in (3, 4)],
             [kline(start+i*60_000) for i in (6, 7)]]
    session = Session(pages)
    inserted = collect_symbol("BTCUSDT", start, start+8*60_000, db=db, session=session, sleep=lambda _: None)
    assert inserted == 6
    assert [p["startTime"] for p in session.calls] == [start, start+3*60_000, start+6*60_000]
    assert [p["endTime"] for p in session.calls] == [start+2*60_000-1, start+5*60_000-1, start+8*60_000-1]
    assert db.execute("SELECT COUNT(*) FROM candles WHERE symbol='BTCUSDT'").fetchone()[0] == 8
    run = db.execute("SELECT status,inserted_rows FROM collection_runs").fetchone()
    page_rows = db.execute("SELECT COUNT(*),SUM(response_row_count),SUM(inserted_row_count) FROM collection_pages").fetchone()
    assert run == ("complete", 6)
    assert page_rows == (3, 6, 6)
    assert db.execute("SELECT COUNT(DISTINCT response_payload_sha256) FROM collection_pages").fetchone()[0] == 3
    db.close()


def test_collector_rerun_is_idempotent_and_makes_no_request(tmp_path):
    db = connect(tmp_path / "candles.sqlite")
    start = 1_700_000_000_000 // 60_000 * 60_000
    for minute in range(4):
        row = kline(start + minute*60_000)
        db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)",
                   ("ETHUSDT", row[0], 10, 11, 9, 10.5, 3, 31.5, 7))
    db.commit()
    session = Session([])
    assert collect_symbol("ETHUSDT", start, start+4*60_000, db=db, session=session) == 0
    assert session.calls == []
    assert db.execute("SELECT COUNT(*) FROM candles WHERE symbol='ETHUSDT'").fetchone()[0] == 4
    assert db.execute("SELECT status,inserted_rows FROM collection_runs").fetchone() == ("complete", 0)
    assert db.execute("SELECT COUNT(*) FROM collection_pages").fetchone()[0] == 0
    db.close()


def test_collector_records_incomplete_response_coverage(tmp_path):
    db = connect(tmp_path / "candles.sqlite")
    start = 1_700_000_000_000 // 60_000 * 60_000
    session = Session([[]])

    assert collect_symbol("BTCUSDT", start, start+2*60_000, db=db,
                          session=session, sleep=lambda _: None) == 0
    assert db.execute("SELECT status,inserted_rows,error_class FROM collection_runs").fetchone() == (
        "incomplete", 0, None)
    assert db.execute("SELECT requested_start_ms,requested_end_ms_exclusive,response_row_count "
                      "FROM collection_pages").fetchone() == (start, start+2*60_000, 0)
    db.close()


def test_collector_empty_page_advances_page_number_across_multiple_gaps(tmp_path):
    db = connect(tmp_path / "candles.sqlite")
    start = 1_700_000_000_000 // 60_000 * 60_000
    for minute in (1, 3):
        row = kline(start + minute*60_000)
        db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)",
                   ("BTCUSDT", row[0], 10, 11, 9, 10.5, 3, 31.5, 7))
    db.commit()
    session = Session([[], [kline(start+2*60_000)],
                       [kline(start+4*60_000), kline(start+5*60_000)]])

    inserted = collect_symbol("BTCUSDT", start, start+6*60_000, db=db,
                              session=session, sleep=lambda _: None)

    assert inserted == 3
    assert db.execute("SELECT status,inserted_rows FROM collection_runs").fetchone() == (
        "incomplete", 3)
    pages = db.execute(
        "SELECT page_number,response_row_count,inserted_row_count "
        "FROM collection_pages ORDER BY page_number").fetchall()
    assert pages == [(1, 0, 0), (2, 1, 1), (3, 2, 2)]
    assert len(session.calls) == 3
    db.close()


def test_collector_records_failed_request_class_without_suppressing_error(tmp_path):
    class BrokenSession:
        def get(self, url, **kwargs):
            raise ConnectionError("mocked network failure")

    db = connect(tmp_path / "candles.sqlite")
    start = 1_700_000_000_000 // 60_000 * 60_000
    with pytest.raises(ConnectionError, match="mocked network failure"):
        collect_symbol("BTCUSDT", start, start+2*60_000, db=db,
                       session=BrokenSession(), sleep=lambda _: None)
    assert db.execute("SELECT status,error_class FROM collection_runs").fetchone() == (
        "failed", "ConnectionError")
    db.close()


def test_verify_cli_reports_all_gaps_and_honors_tolerance(tmp_path, monkeypatch, capsys):
    dbpath = tmp_path / "verify.sqlite"
    db = connect(dbpath)
    start = 1_700_000_000_000 // 60_000 * 60_000
    for minute in (2, 5):
        row = kline(start + minute*60_000)
        db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?)",
                   ("BTCUSDT", row[0], 10, 11, 9, 10.5, 3, 31.5, 7))
    db.commit(); db.close()
    monkeypatch.setattr(cli, "connect", lambda: connect(dbpath))
    argv = ["chart_predictor.cli", "verify", "--verify-symbol", "BTCUSDT",
            "--start-ms", str(start), "--end-ms", str(start+8*60_000), "--max-gap-minutes", "5"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as err: cli.main()
    assert err.value.code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["symbols"][0] == {"symbol": "BTCUSDT", "row_count": 2,
        "first_t_open_ms": start+2*60_000, "last_t_open_ms": start+5*60_000,
        "internal_gaps": 1, "missing_minutes": 6, "duplicates": 0}
    argv[-1] = "6"
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    assert json.loads(capsys.readouterr().out)["ok"] is True
