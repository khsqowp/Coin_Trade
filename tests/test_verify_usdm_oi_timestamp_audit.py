import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.research.verify_usdm_oi_timestamp_audit import (
    alignments,
    parse_utc_ms,
    read_archive_rows,
    verify_crosscheck_dir,
)


def _archive_bytes(symbol="BTCUSDT", date="2026-11-04"):
    start = int(datetime.fromisoformat(date + "T00:00:00+00:00").timestamp() * 1000)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["create_time", "symbol", "sum_open_interest"])
    for index in range(288):
        stamp = start + index * 300_000
        dt = datetime.fromtimestamp(stamp / 1000, timezone.utc)
        writer.writerow([dt.strftime("%Y-%m-%d %H:%M:%S"), symbol,
                         str(Decimal("100") + index)])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{symbol}-metrics.csv", output.getvalue().encode())
    return buffer.getvalue()


def _rest_bytes(symbol="BTCUSDT", date="2026-11-04"):
    start = int(datetime.fromisoformat(date + "T00:00:00+00:00").timestamp() * 1000)
    rows = [{"symbol": symbol, "timestamp": start + (i + 1) * 300_000,
             "sumOpenInterest": str(Decimal("100") + i)} for i in range(288)]
    return json.dumps(rows).encode()


def test_parse_naive_archive_timestamp_as_utc():
    expected = int(datetime(2026, 11, 4, 0, 55, tzinfo=timezone.utc).timestamp() * 1000)
    assert parse_utc_ms("2026-11-04 00:55:00") == expected


def test_alignment_direction_and_denominator_are_explicit():
    archive_rows = [{"_timestamp_ms": 0, "_oi": Decimal("100")}]
    rest_rows = [{"timestamp": 300_000, "oi": Decimal("99")}]
    archive_base = alignments(archive_rows, rest_rows, denominator="archive")
    rest_base = alignments(archive_rows, rest_rows, denominator="rest")
    assert archive_base[5]["exact_values"] == 0
    assert archive_base[5]["max_relative_error"] == pytest.approx(0.01)
    assert rest_base[5]["max_relative_error"] == pytest.approx(1 / 99)
    assert archive_base[0]["matched"] == 0


def test_saved_crosscheck_verifies_hashes_and_recomputes_offset(tmp_path):
    metrics_dir = tmp_path / "metrics"
    rest_dir = tmp_path / "rest"
    metrics_dir.mkdir()
    rest_dir.mkdir()
    symbol, date = "BTCUSDT", "2026-11-04"
    archive = _archive_bytes(symbol)
    rest = _rest_bytes(symbol)
    zip_name = f"{symbol}-metrics-{date}.zip"
    rest_name = f"{symbol}-{date}-rest.json"
    (metrics_dir / zip_name).write_bytes(archive)
    (metrics_dir / (zip_name + ".CHECKSUM")).write_text(
        hashlib.sha256(archive).hexdigest() + "  " + zip_name + "\n")
    (rest_dir / rest_name).write_bytes(rest)
    parsed = read_archive_rows(archive, symbol)
    from scripts.research.verify_usdm_oi_timestamp_audit import read_rest_rows

    expected = alignments(parsed, read_rest_rows(rest, symbol), denominator="archive")
    record = {
        "symbol": symbol,
        "date": date,
        "zip_http": "200",
        "checksum_http": "200",
        "rest_file": rest_name,
        "rest_rows": 288,
        "metrics_sha256": hashlib.sha256(archive).hexdigest(),
        "grid": {"rows": 288, "off_grid_rows": 0, "missing_grid_slots": 0,
                 "duplicate_rows": 0},
        "oi_alignment": {
            "rest_response_sha256": hashlib.sha256(rest).hexdigest(),
            **{f"offset_{minutes:+d}m": {
                "matched": expected[minutes]["matched"],
                "max_relative_error": expected[minutes]["max_relative_error"],
            } for minutes in (-5, 0, 5)},
        },
    }
    (tmp_path / "audit.json").write_text(json.dumps({"records": [record]}))
    result = verify_crosscheck_dir(tmp_path)
    assert result["verified_numeric_pairs"] == 1
    assert result["exact_archive_to_rest_offset_pairs"] == {-5: 0, 0: 0, 5: 1}


def test_archive_reader_rejects_duplicate_timestamps():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("metrics.csv",
                         "create_time,symbol,sum_open_interest\n"
                         "2026-11-04 00:00:00,BTCUSDT,100\n"
                         "2026-11-04 00:00:00,BTCUSDT,101\n")
    with pytest.raises(ValueError, match="duplicate archive timestamps"):
        read_archive_rows(buffer.getvalue(), "BTCUSDT")


def test_crosscheck_verifies_saved_404_and_empty_rest_pair(tmp_path):
    metrics_dir = tmp_path / "metrics"
    rest_dir = tmp_path / "rest"
    metrics_dir.mkdir()
    rest_dir.mkdir()
    symbol, date = "OLDUSDT", "2026-11-04"
    zip_name = f"{symbol}-metrics-{date}.zip"
    (metrics_dir / zip_name).write_text("<Error><Code>NoSuchKey</Code></Error>")
    (metrics_dir / (zip_name + ".CHECKSUM")).write_text(
        "<Error><Code>NoSuchKey</Code></Error>")
    rest_name = f"{symbol}-{date}-rest.json"
    (rest_dir / rest_name).write_text("[]")
    record = {"symbol": symbol, "date": date, "zip_http": "404",
              "rest_file": rest_name, "rest_rows": 0}
    (tmp_path / "audit.json").write_text(json.dumps({"records": [record]}))
    assert verify_crosscheck_dir(tmp_path)["absent_oi_pairs"] == 1
