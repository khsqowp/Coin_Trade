from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
import zipfile
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from scripts.research import binance_vision_klines as vision


def archive_bytes(symbol: str = "BTCUSDT", month: str = "2025-01", header: bool = False) -> bytes:
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    rows = [
        [start, "100", "102", "99", "101", "3", start + 59_999,
         "301", "5", "1.5", "150", "0"],
        [start + 60_000, "101", "103", "100", "102", "4", start + 119_999,
         "406", "6", "2", "204", "0"],
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    if header:
        writer.writerow(["open_time", "open", "high", "low", "close", "volume",
                         "close_time", "quote_volume", "count", "taker_buy_volume",
                         "taker_buy_quote_volume", "ignore"])
    writer.writerows(rows)
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr(f"{symbol}-1m-{month}.csv", stream.getvalue())
    return payload.getvalue()


def test_month_sequence_and_url_are_half_open_and_exact():
    assert [m.isoformat() for m in vision.months_between(date(2025, 1, 1), date(2025, 4, 1))] == [
        "2025-01-01", "2025-02-01", "2025-03-01"
    ]
    assert vision.archive_url("BTCUSDT", date(2025, 1, 1)) == (
        "https://data.binance.vision/data/futures/um/monthly/klines/"
        "BTCUSDT/1m/BTCUSDT-1m-2025-01.zip"
    )
    assert vision.archive_url("BTCUSDT", date(2025, 1, 1), checksum=True).endswith(
        "BTCUSDT-1m-2025-01.zip.CHECKSUM"
    )


def test_checksum_sidecar_requires_exact_name_and_sha256():
    digest = "a" * 64
    assert vision.parse_checksum(f"{digest}  BTCUSDT-1m-2025-01.zip\n".encode(),
                                 "BTCUSDT-1m-2025-01.zip") == digest
    with pytest.raises(ValueError):
        vision.parse_checksum(f"{digest}  other.zip\n".encode(), "BTCUSDT-1m-2025-01.zip")


def test_archive_parser_validates_rows_and_preserves_taker_volume():
    payload = archive_bytes(header=True)
    parsed = vision.parse_archive("BTCUSDT", date(2025, 1, 1), payload)
    assert len(parsed.rows) == 2
    expected_start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    assert parsed.rows[0][0:2] == ("BTCUSDT", expected_start)
    assert parsed.rows[0][-2:] == (1.5, 150.0)
    assert parsed.sha256 == hashlib.sha256(payload).hexdigest()
    assert parsed.missing_minutes == 0


def test_archive_parser_reports_missing_minutes_without_interpolating():
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    rows = [
        [start, "100", "102", "99", "101", "3", start + 59_999, "301", "5", "1.5", "150", "0"],
        [start + 180_000, "101", "103", "100", "102", "4", start + 239_999, "406", "6", "2", "204", "0"],
    ]
    source = io.BytesIO()
    csv_text = io.StringIO(newline="")
    csv.writer(csv_text).writerows(rows)
    with zipfile.ZipFile(source, "w") as zipped:
        zipped.writestr("BTCUSDT-1m-2025-01.csv", csv_text.getvalue())
    parsed = vision.parse_archive("BTCUSDT", date(2025, 1, 1), source.getvalue())
    assert len(parsed.rows) == 2
    assert parsed.missing_minutes == 2


@pytest.mark.parametrize(
    "replacement,match",
    [
        (("nan", "102", "99", "101", "3", "301", "5", "1.5", "150"), "non-finite"),
        (("100", "98", "99", "101", "3", "301", "5", "1.5", "150"), "OHLC bounds"),
        (("100", "102", "99", "101", "-3", "301", "5", "1.5", "150"), "negative"),
        (("100", "102", "99", "101", "3", "301", "5", "4", "150"), "exceeds total"),
    ],
)
def test_archive_parser_rejects_invalid_ohlcv(replacement, match):
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    open_price, high, low, close, volume, quote, trades, taker_base, taker_quote = replacement
    row = [start, open_price, high, low, close, volume, start + 59_999,
           quote, trades, taker_base, taker_quote, "0"]
    source = io.BytesIO()
    csv_text = io.StringIO(newline="")
    csv.writer(csv_text).writerow(row)
    with zipfile.ZipFile(source, "w") as zipped:
        zipped.writestr("BTCUSDT-1m-2025-01.csv", csv_text.getvalue())
    with pytest.raises(ValueError, match=match):
        vision.parse_archive("BTCUSDT", date(2025, 1, 1), source.getvalue())


def test_archive_parser_rejects_duplicate_or_wrong_month_rows():
    valid = archive_bytes()
    source = io.BytesIO()
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    row = [start, "1", "1", "1", "1", "1", start + 59_999, "1", "1", "1", "1", "0"]
    csv_text = io.StringIO(newline="")
    writer = csv.writer(csv_text)
    writer.writerow(row)
    writer.writerow(row)
    with zipfile.ZipFile(source, "w") as zipped:
        zipped.writestr("BTCUSDT-1m-2025-01.csv", csv_text.getvalue())
    with pytest.raises(ValueError, match="duplicated or out of order"):
        vision.parse_archive("BTCUSDT", date(2025, 1, 1), source.getvalue())
    assert valid


def test_fetch_checks_archive_hash_and_paces_each_request():
    payload = archive_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = f"{digest}  BTCUSDT-1m-2025-01.zip\n".encode()
    calls = []
    sleeps = []

    def fake_request(url):
        calls.append(url)
        return sidecar if url.endswith(".CHECKSUM") else payload

    with patch.object(vision, "request_bytes", side_effect=fake_request):
        result = vision.fetch_month("BTCUSDT", date(2025, 1, 1), sleep=sleeps.append)
    assert result is not None and len(result.rows) == 2
    assert len(calls) == 2
    assert sleeps == [vision.MIN_REQUEST_INTERVAL_SECONDS] * 2


def test_fetch_wraps_checksum_verified_row_validation_failure():
    bad_source = io.StringIO(newline="")
    csv.writer(bad_source).writerow([
        int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),
        "100", "102", "99", "101", "3", 1735689659999,
        "301", "5", "4", "150", "0",
    ])
    bad_zip = io.BytesIO()
    with zipfile.ZipFile(bad_zip, "w") as zipped:
        zipped.writestr("BTCUSDT-1m-2025-01.csv", bad_source.getvalue())
    bad_payload = bad_zip.getvalue()
    bad_digest = hashlib.sha256(bad_payload).hexdigest()
    bad_sidecar = f"{bad_digest}  BTCUSDT-1m-2025-01.zip\n".encode()

    with patch.object(vision, "request_bytes", side_effect=[bad_sidecar, bad_payload]):
        with pytest.raises(vision.ArchiveValidationError) as caught:
            vision.fetch_month("BTCUSDT", date(2025, 1, 1), sleep=lambda _: None)
    assert caught.value.symbol == "BTCUSDT"
    assert caught.value.month == "2025-01"
    assert caught.value.sha256 == bad_digest
    assert "exceeds total" in caught.value.reason


def test_backfill_quarantines_invalid_archive_once_and_never_inserts_it():
    db = sqlite3.connect(":memory:")
    db.executescript(vision.SCHEMA)
    rejected = vision.ArchiveValidationError(
        "BTCUSDT", "2025-01", "a" * 64, 123, "ValueError: bad taker volume"
    )
    output = []
    with patch.object(vision, "fetch_month", side_effect=rejected) as fetch:
        first = vision.backfill(
            db, ("BTCUSDT",), [date(2025, 1, 1)], sleep=lambda _: None,
            progress=output.append,
        )
        assert fetch.call_count == 1
        second = vision.backfill(
            db, ("BTCUSDT",), [date(2025, 1, 1)], sleep=lambda _: None,
            progress=output.append,
        )
        assert fetch.call_count == 1

    assert first["rejected_months"] == 1
    assert first["skipped_previously_rejected_months"] == 0
    assert second["rejected_months"] == 0
    assert second["skipped_previously_rejected_months"] == 1
    assert db.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 0
    assert db.execute(
        "SELECT symbol,month,sha256,reason FROM rejected_archives"
    ).fetchone() == ("BTCUSDT", "2025-01", "a" * 64, "ValueError: bad taker volume")
    assert any(line.startswith("rejected BTCUSDT 2025-01") for line in output)
    db.close()


def test_insert_is_idempotent_and_writes_manifest():
    db = sqlite3.connect(":memory:")
    db.executescript(vision.SCHEMA)
    parsed = vision.parse_archive("BTCUSDT", date(2025, 1, 1), archive_bytes())
    vision.insert_month(db, parsed)
    vision.insert_month(db, parsed)
    assert db.execute("SELECT COUNT(*) FROM candles").fetchone()[0] == 2
    assert db.execute("SELECT rows FROM archive_manifest").fetchone()[0] == 2
    db.close()


def test_insert_refuses_unmanifested_or_changed_month_data():
    db = sqlite3.connect(":memory:")
    db.executescript(vision.SCHEMA)
    parsed = vision.parse_archive("BTCUSDT", date(2025, 1, 1), archive_bytes())
    db.execute("INSERT INTO candles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", parsed.rows[0])
    with pytest.raises(ValueError, match="unmanifested"):
        vision.insert_month(db, parsed)
    db.close()

    db = sqlite3.connect(":memory:")
    db.executescript(vision.SCHEMA)
    vision.insert_month(db, parsed)
    changed = vision.ArchiveMonth(
        parsed.symbol, parsed.month, "0" * 64, parsed.rows, parsed.archive_bytes, parsed.missing_minutes
    )
    with pytest.raises(ValueError, match="changed source archive"):
        vision.insert_month(db, changed)
    db.close()
