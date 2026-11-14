#!/usr/bin/env python3
"""Backfill monthly Binance Vision USD-M 1m klines into a separate local DB.

This tool is for personal, non-production research only. It never accesses the
existing live collector database. Binance Vision's dataset terms apply.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zipfile
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/klines"
DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT")
DEFAULT_DB = Path(__file__).parents[2] / "chart_predictor" / "data" / "vision_dev.sqlite"
MAX_ARCHIVE_BYTES = 20_000_000
MIN_REQUEST_INTERVAL_SECONDS = 1.0
SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
  symbol TEXT NOT NULL,
  open_ms INTEGER NOT NULL,
  open REAL NOT NULL,
  high REAL NOT NULL,
  low REAL NOT NULL,
  close REAL NOT NULL,
  volume REAL NOT NULL,
  close_ms INTEGER NOT NULL,
  quote_volume REAL NOT NULL,
  trade_count INTEGER NOT NULL,
  taker_buy_base REAL NOT NULL,
  taker_buy_quote REAL NOT NULL,
  PRIMARY KEY (symbol, open_ms)
);
CREATE TABLE IF NOT EXISTS archive_manifest (
  symbol TEXT NOT NULL,
  month TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  rows INTEGER NOT NULL,
  archive_bytes INTEGER NOT NULL,
  retrieved_utc TEXT NOT NULL,
  PRIMARY KEY (symbol, month)
);
"""


@dataclass(frozen=True)
class ArchiveMonth:
    symbol: str
    month: str
    sha256: str
    rows: tuple[tuple[object, ...], ...]
    archive_bytes: int


def parse_month(value: str) -> date:
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("month must use YYYY-MM") from exc
    return parsed.replace(day=1)


def months_between(start: date, end_exclusive: date) -> list[date]:
    if start.day != 1 or end_exclusive.day != 1 or start >= end_exclusive:
        raise ValueError("month boundaries must be first-of-month and start < end")
    result = []
    year, month = start.year, start.month
    while (year, month) < (end_exclusive.year, end_exclusive.month):
        result.append(date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def archive_url(symbol: str, month: date, checksum: bool = False) -> str:
    key = f"{symbol}-1m-{month:%Y-%m}.zip"
    if checksum:
        key += ".CHECKSUM"
    return f"{BASE_URL}/{symbol}/1m/{key}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_checksum(sidecar: bytes, expected_name: str) -> str:
    fields = sidecar.decode("ascii").strip().split()
    if len(fields) != 2 or fields[1].lstrip("*") != expected_name:
        raise ValueError("checksum sidecar filename is malformed or unexpected")
    digest = fields[0].lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("checksum sidecar does not contain a SHA-256 digest")
    return digest


def parse_archive(symbol: str, month: date, archive: bytes) -> ArchiveMonth:
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise ValueError(f"archive exceeds {MAX_ARCHIVE_BYTES} byte safety limit")
    expected = month.strftime("%Y-%m")
    month_start_ms = int(datetime(month.year, month.month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    days = monthrange(month.year, month.month)[1]
    month_end_ms = month_start_ms + days * 86_400_000
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        csv_names = [name for name in zipped.namelist() if name.endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError("archive must contain exactly one CSV")
        expected_csv = f"{symbol}-1m-{expected}.csv"
        if Path(csv_names[0]).name != expected_csv:
            raise ValueError("archive CSV filename does not match requested symbol/month")
        records = []
        previous_open_ms = -1
        with zipped.open(csv_names[0]) as member:
            reader = csv.reader(io.TextIOWrapper(member, encoding="utf-8", newline=""))
            for line_no, row in enumerate(reader, start=1):
                if line_no == 1 and row and row[0].strip().lower() in {"open_time", "open time"}:
                    continue
                if len(row) != 12:
                    raise ValueError(f"CSV row {line_no} has {len(row)} columns, expected 12")
                open_ms = int(row[0])
                close_ms = int(row[6])
                if not month_start_ms <= open_ms < month_end_ms or close_ms < open_ms:
                    raise ValueError(f"CSV row {line_no} is outside its declared month")
                if open_ms % 60_000 or close_ms != open_ms + 59_999:
                    raise ValueError(f"CSV row {line_no} does not match a 1m candle interval")
                if open_ms <= previous_open_ms:
                    raise ValueError(f"CSV row {line_no} is duplicated or out of order")
                previous_open_ms = open_ms
                records.append((
                    symbol, open_ms, float(row[1]), float(row[2]), float(row[3]),
                    float(row[4]), float(row[5]), close_ms, float(row[7]),
                    int(row[8]), float(row[9]), float(row[10]),
                ))
    return ArchiveMonth(symbol, expected, sha256_hex(archive), tuple(records), len(archive))


def request_bytes(url: str, timeout: float = 45.0) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "CoinTrade-Personal-Research/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_ARCHIVE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"archive request failed with HTTP {exc.code}") from exc
    if len(data) > MAX_ARCHIVE_BYTES:
        raise RuntimeError(f"response exceeds {MAX_ARCHIVE_BYTES} byte safety limit")
    return data


def fetch_month(symbol: str, month: date, sleep=time.sleep) -> ArchiveMonth | None:
    name = f"{symbol}-1m-{month:%Y-%m}.zip"
    try:
        sidecar = request_bytes(archive_url(symbol, month, checksum=True))
    finally:
        sleep(MIN_REQUEST_INTERVAL_SECONDS)
    if sidecar is None:
        return None
    expected_digest = parse_checksum(sidecar, name)
    try:
        archive = request_bytes(archive_url(symbol, month))
    finally:
        sleep(MIN_REQUEST_INTERVAL_SECONDS)
    if archive is None:
        raise RuntimeError(f"checksum exists but archive is missing: {name}")
    actual_digest = sha256_hex(archive)
    if actual_digest != expected_digest:
        raise RuntimeError(f"SHA-256 mismatch for {name}")
    return parse_archive(symbol, month, archive)


def open_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def insert_month(db: sqlite3.Connection, month: ArchiveMonth) -> None:
    retrieved = datetime.now(timezone.utc).isoformat()
    with db:
        db.executemany(
            "INSERT OR IGNORE INTO candles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", month.rows
        )
        db.execute(
            "INSERT OR REPLACE INTO archive_manifest VALUES(?,?,?,?,?,?)",
            (month.symbol, month.month, month.sha256, len(month.rows), month.archive_bytes, retrieved),
        )


def backfill(
    db: sqlite3.Connection,
    symbols: tuple[str, ...],
    months: list[date],
    sleep=time.sleep,
    progress=print,
) -> dict[str, object]:
    completed = missing = skipped = 0
    for symbol in symbols:
        if not symbol.isalnum() or symbol.upper() != symbol:
            raise ValueError(f"invalid symbol syntax: {symbol!r}")
        for month in months:
            month_text = month.strftime("%Y-%m")
            prior = db.execute(
                "SELECT 1 FROM archive_manifest WHERE symbol=? AND month=?",
                (symbol, month_text),
            ).fetchone()
            if prior:
                skipped += 1
                continue
            archive_month = fetch_month(symbol, month, sleep=sleep)
            if archive_month is None:
                missing += 1
                progress(f"missing {symbol} {month_text}")
                continue
            insert_month(db, archive_month)
            completed += 1
            progress(f"stored {symbol} {month_text} rows={len(archive_month.rows)} sha256={archive_month.sha256}")
    totals = []
    for symbol, count, first_ms, last_ms in db.execute(
        "SELECT symbol,COUNT(*),MIN(open_ms),MAX(open_ms) "
        "FROM candles GROUP BY symbol ORDER BY symbol"
    ):
        gaps = db.execute(
            "SELECT COALESCE(SUM((open_ms-prev_ms)/60000-1),0) FROM ("
            "SELECT open_ms,LAG(open_ms) OVER(ORDER BY open_ms) AS prev_ms "
            "FROM candles WHERE symbol=?) WHERE prev_ms IS NOT NULL AND open_ms-prev_ms>60000",
            (symbol,),
        ).fetchone()[0]
        totals.append((symbol, count, first_ms, last_ms, gaps))
    return {"completed_months": completed, "missing_months": missing,
            "skipped_existing_months": skipped, "database_rows_by_symbol": totals}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-month", type=parse_month, default=parse_month("2020-01"))
    parser.add_argument("--end-month-exclusive", type=parse_month, default=parse_month("2026-07"))
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    months = months_between(args.start_month, args.end_month_exclusive)
    db = open_database(args.db)
    try:
        result = backfill(db, tuple(args.symbols), months)
        print(json.dumps({"db": str(args.db), "start_month": args.start_month.isoformat(),
                          "end_month_exclusive": args.end_month_exclusive.isoformat(),
                          "symbols": args.symbols, **result}, default=str, sort_keys=True))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
