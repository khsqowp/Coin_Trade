from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.research import audit_binance_trades_kline_reconciliation as audit
from scripts.research.audit_binance_trades_kline_reconciliation import audit_pair


def _write_zip(path: Path, member: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, content)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(f"{path}.CHECKSUM").write_text(f"{digest}  {path.name}\n", encoding="utf-8")


def _fixture(tmp_path: Path, *, trade_rows: str | None = None, active_count: int = 2):
    day = "2025-01-01"
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    trades_dir = tmp_path / "trades"
    klines_dir = tmp_path / "klines"
    if trade_rows is None:
        trade_rows = (
            "1,100,1,100,1735689601000,true\n"
            "2,102,2,204,1735689601000,false\n"
        )
    _write_zip(
        trades_dir / f"BTCUSDT-trades-{day}.zip",
        f"BTCUSDT-trades-{day}.csv",
        "id,price,qty,quote_qty,time,is_buyer_maker\n" + trade_rows,
    )
    lines = [
        "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore"
    ]
    for minute_index in range(1440):
        open_time = start + minute_index * 60_000
        if minute_index == 0:
            row = [open_time, "100", "102", "100", "102", "3", open_time + 59_999,
                   "304", active_count, "2", "204", "0"]
        else:
            row = [open_time, "102", "102", "102", "102", "0", open_time + 59_999,
                   "0", "0", "0", "0", "0"]
        lines.append(",".join(map(str, row)))
    _write_zip(
        klines_dir / f"BTCUSDT-1m-{day}.zip",
        f"BTCUSDT-1m-{day}.csv",
        "\n".join(lines) + "\n",
    )
    return trades_dir, klines_dir, day


def test_exact_trade_rows_reconstruct_native_full_day(tmp_path: Path) -> None:
    trades_dir, klines_dir, day = _fixture(tmp_path)

    result = audit_pair(trades_dir, klines_dir, "BTCUSDT", day)

    assert result["grid"]["native_grid_complete"] is True
    assert result["grid"]["native_active"] == result["grid"]["raw_active"] == 1
    assert result["symbol_day_integrity_pass"] is True
    assert result["failure_reasons"] == []
    assert all(value["count"] == 0 for value in result["mismatches"].values())
    assert result["mismatches"]["trade_count"]["denominator"] == 1440


def test_active_minute_mismatch_fails_closed(tmp_path: Path) -> None:
    trades_dir, klines_dir, day = _fixture(tmp_path, trade_rows="", active_count=2)

    result = audit_pair(trades_dir, klines_dir, "BTCUSDT", day)

    assert result["grid"]["native_only_active"] == 1
    assert "active_minute_sets_differ" in result["failure_reasons"]
    assert result["symbol_day_integrity_pass"] is False


def test_duplicate_or_nonmonotone_ids_and_bad_header_are_recorded(tmp_path: Path) -> None:
    trades_dir, klines_dir, day = _fixture(
        tmp_path,
        trade_rows=(
            "2,100,1,100,1735689601000,true\n"
            "2,102,2,204,1735689602000,false\n"
        ),
    )
    result = audit_pair(trades_dir, klines_dir, "BTCUSDT", day)
    assert result["integrity"]["duplicate_or_nonmonotone_trade_ids"] == 1
    assert "integrity_duplicate_or_nonmonotone_trade_ids" in result["failure_reasons"]

    trade_archive = trades_dir / f"BTCUSDT-trades-{day}.zip"
    _write_zip(
        trade_archive,
        f"BTCUSDT-trades-{day}.csv",
        "unexpected,header\n1,2\n",
    )
    bad_header = audit_pair(trades_dir, klines_dir, "BTCUSDT", day)
    assert any(reason.startswith("trades:ValueError:unexpected trades header")
               for reason in bad_header["failure_reasons"])


def test_publisher_checksum_mismatch_is_not_repaired(tmp_path: Path) -> None:
    trades_dir, klines_dir, day = _fixture(tmp_path)
    trade_archive = trades_dir / f"BTCUSDT-trades-{day}.zip"
    Path(f"{trade_archive}.CHECKSUM").write_text("0" * 64 + f"  {trade_archive.name}\n")

    result = audit_pair(trades_dir, klines_dir, "BTCUSDT", day)

    assert result["archive_sha256"]["trades"] is None
    assert any(reason.startswith("trades:ValueError:publisher checksum mismatch")
               for reason in result["failure_reasons"])


def test_malformed_csv_quoting_fails_symbol_day(tmp_path: Path) -> None:
    trades_dir, klines_dir, day = _fixture(
        tmp_path,
        trade_rows='1,"100,1,100,1735689601000,true\n',
    )

    result = audit_pair(trades_dir, klines_dir, "BTCUSDT", day)

    assert any(reason.startswith("trades:Error:") for reason in result["failure_reasons"])
    assert result["symbol_day_integrity_pass"] is False


def test_downloader_replaces_existing_archive_with_bad_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "BTCUSDT-trades-2025-01-01.zip"
    _write_zip(destination, "BTCUSDT-trades-2025-01-01.csv", "old\n")
    Path(f"{destination}.CHECKSUM").write_text("0" * 64 + f"  {destination.name}\n")

    payload_stream = io.BytesIO()
    with zipfile.ZipFile(payload_stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-trades-2025-01-01.csv", "new\n")
    payload = payload_stream.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    sidecar = f"{digest}  {destination.name}\n".encode("ascii")

    def fake_urlopen(request, timeout=0):
        url = request.full_url
        return io.BytesIO(sidecar if url.endswith(".CHECKSUM") else payload)

    monkeypatch.setattr(audit.urllib.request, "urlopen", fake_urlopen)

    result = audit.download_archive("https://example.invalid/archive.zip", destination)

    assert result == "downloaded"
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
