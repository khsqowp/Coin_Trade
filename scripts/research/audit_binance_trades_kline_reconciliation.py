#!/usr/bin/env python3
"""Audit Binance Vision USD-M daily raw trades against native 1m klines.

Historical source-integrity audit only. This module calculates no predictions,
market labels, strategy returns, or trading signals. Raw ZIP files and the JSON
report must be stored outside Git under the applicable Binance Vision terms.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, time as dt_time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "LINKUSDT", "DOTUSDT",
    "AVAXUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT", "UNIUSDT", "AAVEUSDT",
    "NEARUSDT", "APTUSDT",
)
DAYS = ("2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01")
MINUTE_MS = 60_000
DAY_MS = 86_400_000
FLOAT_REL_TOL = Decimal("1e-8")
FLOAT_ABS_TOL = Decimal("1e-10")
TRADES_BASE = "https://data.binance.vision/data/futures/um/daily/trades"
KLINES_BASE = "https://data.binance.vision/data/futures/um/daily/klines"
TRADE_HEADER = ["id", "price", "qty", "quote_qty", "time", "is_buyer_maker"]
TRADE_ALIASES = {
    "trade Id": "id", "quoteQty": "quote_qty", "isBuyerMaker": "is_buyer_maker",
}
KLINE_HEADER = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]
NUMERIC_FIELDS = (
    "open", "high", "low", "close", "base_volume", "quote_volume",
    "taker_buy_base", "taker_buy_quote",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _equal(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= max(FLOAT_ABS_TOL, FLOAT_REL_TOL * abs(right))


def _decimal(value: str, *, positive: bool = False, nonnegative: bool = False) -> Decimal:
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("nonfinite decimal")
    if positive and result <= 0:
        raise ValueError("expected positive decimal")
    if nonnegative and result < 0:
        raise ValueError("expected nonnegative decimal")
    return result


def _parse_checksum(path: Path) -> str:
    sidecar = Path(f"{path}.CHECKSUM")
    fields = sidecar.read_text(encoding="ascii").strip().split()
    if len(fields) != 2 or fields[1].lstrip("*") != path.name:
        raise ValueError(f"malformed checksum sidecar: {sidecar.name}")
    expected = fields[0].lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError(f"invalid SHA-256 in sidecar: {sidecar.name}")
    return expected


@contextmanager
def _verified_rows(path: Path, expected_csv: str) -> Iterator[tuple[str, list[str], Iterator[list[str]]]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing ZIP: {path.name}")
    sidecar = Path(f"{path}.CHECKSUM")
    if not sidecar.is_file():
        raise FileNotFoundError(f"missing CHECKSUM: {sidecar.name}")
    expected_hash = _parse_checksum(path)
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(f"publisher checksum mismatch: {path.name}")
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1 or Path(members[0]).name != expected_csv:
            raise ValueError(f"unexpected CSV member in {path.name}: {members}")
        with archive.open(members[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            try:
                reader = csv.reader(text, strict=True)
                try:
                    header = next(reader)
                except StopIteration as exc:
                    raise ValueError(f"empty CSV: {path.name}") from exc
                yield actual_hash, header, reader
            finally:
                text.close()


def _canonical_trade_header(header: list[str]) -> list[str]:
    return [TRADE_ALIASES.get(name.strip(), name.strip()) for name in header]


def download_archive(url: str, destination: Path, *, retries: int = 3) -> str:
    """Download one official archive/sidecar atomically; reuse verified files."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    sidecar = Path(f"{destination}.CHECKSUM")
    if destination.exists() and sidecar.exists():
        try:
            if _sha256(destination) == _parse_checksum(destination):
                return "reused"
        except (OSError, ValueError):
            pass
    destination.unlink(missing_ok=True)
    sidecar.unlink(missing_ok=True)
    for attempt in range(retries):
        try:
            for suffix, target in (("", destination), (".CHECKSUM", sidecar)):
                request = urllib.request.Request(
                    url + suffix,
                    headers={"User-Agent": "CoinTrade-Personal-Research/1.0"},
                )
                temporary = Path(f"{target}.partial")
                try:
                    with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                        while True:
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            if _sha256(destination) != _parse_checksum(destination):
                raise ValueError(f"downloaded archive checksum mismatch: {destination.name}")
            return "downloaded"
        except urllib.error.HTTPError as exc:
            destination.unlink(missing_ok=True)
            sidecar.unlink(missing_ok=True)
            if exc.code == 404:
                return "missing_404"
            if attempt + 1 == retries:
                return f"http_{exc.code}"
        except (OSError, ValueError, urllib.error.URLError) as exc:
            destination.unlink(missing_ok=True)
            sidecar.unlink(missing_ok=True)
            if attempt + 1 == retries:
                return f"download_error:{type(exc).__name__}"
        time.sleep(1.0 * (attempt + 1))
    return "download_error:retry_exhausted"


def _utc_bounds(day: str) -> tuple[int, int]:
    parsed = date.fromisoformat(day)
    start = int(datetime.combine(parsed, dt_time(), timezone.utc).timestamp() * 1000)
    return start, start + DAY_MS


def audit_pair(trades_dir: Path, klines_dir: Path, symbol: str, day: str) -> dict[str, Any]:
    start_ms, end_ms = _utc_bounds(day)
    trades_path = trades_dir / f"{symbol}-trades-{day}.zip"
    klines_path = klines_dir / f"{symbol}-1m-{day}.zip"
    failures: list[str] = []
    integrity: dict[str, int | None] = {
        "malformed_trade_rows": 0,
        "outside_utc_day_trades": 0,
        "duplicate_or_nonmonotone_trade_ids": 0,
        "trade_id_gaps": 0,
        "nonmonotone_trade_timestamps": 0,
        "malformed_kline_rows": 0,
        "outside_utc_day_klines": 0,
        "nonmonotone_kline_timestamps": 0,
        "trade_rows": 0,
        "kline_rows": 0,
        "first_trade_id": None,
        "last_trade_id": None,
    }
    buckets: dict[int, dict[str, Any]] = {}
    trade_hash: str | None = None
    kline_hash: str | None = None
    try:
        with _verified_rows(trades_path, f"{symbol}-trades-{day}.csv") as (trade_hash, header, rows):
            if _canonical_trade_header(header) != TRADE_HEADER:
                raise ValueError(f"unexpected trades header: {header}")
            previous_id: int | None = None
            previous_time: int | None = None
            for fields in rows:
                integrity["trade_rows"] = int(integrity["trade_rows"] or 0) + 1
                if len(fields) != len(TRADE_HEADER):
                    integrity["malformed_trade_rows"] = int(integrity["malformed_trade_rows"] or 0) + 1
                    continue
                try:
                    trade_id = int(fields[0], 10)
                    price = _decimal(fields[1], positive=True)
                    qty = _decimal(fields[2], positive=True)
                    quote_qty = _decimal(fields[3], positive=True)
                    timestamp = int(fields[4], 10)
                    buyer_maker_text = fields[5].strip().lower()
                    if buyer_maker_text not in {"true", "false"}:
                        raise ValueError("invalid buyer-maker flag")
                except (ValueError, InvalidOperation, OverflowError):
                    integrity["malformed_trade_rows"] = int(integrity["malformed_trade_rows"] or 0) + 1
                    continue
                if previous_id is not None:
                    if trade_id <= previous_id:
                        integrity["duplicate_or_nonmonotone_trade_ids"] = int(integrity["duplicate_or_nonmonotone_trade_ids"] or 0) + 1
                    elif trade_id != previous_id + 1:
                        integrity["trade_id_gaps"] = int(integrity["trade_id_gaps"] or 0) + trade_id - previous_id - 1
                if previous_time is not None and timestamp < previous_time:
                    integrity["nonmonotone_trade_timestamps"] = int(integrity["nonmonotone_trade_timestamps"] or 0) + 1
                previous_id, previous_time = trade_id, timestamp
                integrity["first_trade_id"] = trade_id if integrity["first_trade_id"] is None else integrity["first_trade_id"]
                integrity["last_trade_id"] = trade_id
                if not start_ms <= timestamp < end_ms:
                    integrity["outside_utc_day_trades"] = int(integrity["outside_utc_day_trades"] or 0) + 1
                    continue
                minute = timestamp // MINUTE_MS * MINUTE_MS
                bucket = buckets.setdefault(minute, {
                    "first_key": None, "last_key": None,
                    "open": None, "close": None, "high": None, "low": None,
                    "base_volume": Decimal(0), "quote_volume": Decimal(0),
                    "quote_price_times_qty": Decimal(0), "trade_count": 0,
                    "taker_buy_base": Decimal(0), "taker_buy_quote": Decimal(0),
                })
                key = (timestamp, trade_id)
                if bucket["first_key"] is None or key < bucket["first_key"]:
                    bucket["first_key"], bucket["open"] = key, price
                if bucket["last_key"] is None or key > bucket["last_key"]:
                    bucket["last_key"], bucket["close"] = key, price
                bucket["high"] = price if bucket["high"] is None else max(bucket["high"], price)
                bucket["low"] = price if bucket["low"] is None else min(bucket["low"], price)
                bucket["base_volume"] += qty
                bucket["quote_volume"] += quote_qty
                bucket["quote_price_times_qty"] += price * qty
                bucket["trade_count"] += 1
                if buyer_maker_text == "false":
                    bucket["taker_buy_base"] += qty
                    bucket["taker_buy_quote"] += quote_qty
    except (OSError, ValueError, csv.Error, zipfile.BadZipFile) as exc:
        failures.append(f"trades:{type(exc).__name__}:{exc}")

    klines: dict[int, dict[str, Any]] = {}
    try:
        with _verified_rows(klines_path, f"{symbol}-1m-{day}.csv") as (kline_hash, header, rows):
            if header != KLINE_HEADER:
                raise ValueError(f"unexpected kline header: {header}")
            previous_open: int | None = None
            for fields in rows:
                integrity["kline_rows"] = int(integrity["kline_rows"] or 0) + 1
                if len(fields) != len(KLINE_HEADER):
                    integrity["malformed_kline_rows"] = int(integrity["malformed_kline_rows"] or 0) + 1
                    continue
                try:
                    open_time = int(fields[0], 10)
                    values = {name: _decimal(fields[index], nonnegative=(name in {
                        "volume", "quote_volume", "taker_buy_volume", "taker_buy_quote_volume",
                    })) for name, index in (
                        ("open", 1), ("high", 2), ("low", 3), ("close", 4),
                        ("volume", 5), ("quote_volume", 7), ("taker_buy_volume", 9),
                        ("taker_buy_quote_volume", 10), ("ignore", 11),
                    )}
                    close_time = int(fields[6], 10)
                    count = int(fields[8], 10)
                    if count < 0 or close_time != open_time + MINUTE_MS - 1:
                        raise ValueError("invalid count or close time")
                except (ValueError, InvalidOperation, OverflowError):
                    integrity["malformed_kline_rows"] = int(integrity["malformed_kline_rows"] or 0) + 1
                    continue
                if previous_open is not None and open_time <= previous_open:
                    integrity["nonmonotone_kline_timestamps"] = int(integrity["nonmonotone_kline_timestamps"] or 0) + 1
                previous_open = open_time
                if not start_ms <= open_time < end_ms:
                    integrity["outside_utc_day_klines"] = int(integrity["outside_utc_day_klines"] or 0) + 1
                    continue
                if open_time % MINUTE_MS or open_time in klines:
                    integrity["malformed_kline_rows"] = int(integrity["malformed_kline_rows"] or 0) + 1
                    continue
                klines[open_time] = {
                    "open": values["open"], "high": values["high"], "low": values["low"], "close": values["close"],
                    "base_volume": values["volume"], "quote_volume": values["quote_volume"],
                    "trade_count": count, "taker_buy_base": values["taker_buy_volume"],
                    "taker_buy_quote": values["taker_buy_quote_volume"],
                }
    except (OSError, ValueError, csv.Error, zipfile.BadZipFile) as exc:
        failures.append(f"klines:{type(exc).__name__}:{exc}")

    expected_grid = set(range(start_ms, end_ms, MINUTE_MS))
    native_active = {minute for minute, bar in klines.items() if bar["trade_count"] > 0}
    raw_active = {minute for minute, bar in buckets.items() if bar["trade_count"] > 0}
    common_active = native_active & raw_active
    active_one_sided = len(native_active ^ raw_active)
    grid_complete = len(klines) == len(expected_grid) and set(klines) == expected_grid
    if not grid_complete:
        failures.append("native_kline_grid_not_exactly_1440")
    if active_one_sided:
        failures.append("active_minute_sets_differ")
    for minute, bar in klines.items():
        if bar["trade_count"] == 0 and any(bar[field] != 0 for field in (
            "base_volume", "quote_volume", "taker_buy_base", "taker_buy_quote",
        )):
            failures.append(f"inactive_native_minute_has_nonzero_volume:{minute}")
            break
    for key in (
        "malformed_trade_rows", "outside_utc_day_trades", "duplicate_or_nonmonotone_trade_ids",
        "malformed_kline_rows", "outside_utc_day_klines", "nonmonotone_kline_timestamps",
    ):
        if int(integrity[key] or 0):
            failures.append(f"integrity_{key}")

    mismatch: dict[str, dict[str, Any]] = {}
    max_abs: dict[str, float] = {}
    if len(native_active) == 0:
        failures.append("zero_native_active_minutes_ohlc_ineligible")
    for field in NUMERIC_FIELDS:
        minutes = common_active if field in {"open", "high", "low", "close"} else expected_grid
        bad = 0
        max_difference = Decimal(0)
        for minute in minutes:
            native = klines.get(minute)
            raw = buckets.get(minute)
            if native is None:
                bad += 1
                continue
            if field in {"open", "high", "low", "close"}:
                actual = raw[field] if raw else None
            else:
                raw_field = {"base_volume": "base_volume", "quote_volume": "quote_volume",
                             "taker_buy_base": "taker_buy_base", "taker_buy_quote": "taker_buy_quote"}.get(field)
                actual = raw[raw_field] if raw else Decimal(0)
            expected_value = native[field]
            if actual is None:
                bad += 1
                continue
            delta = abs(actual - expected_value)
            max_difference = max(max_difference, delta)
            equal = actual == expected_value if field == "trade_count" else _equal(actual, expected_value)
            if not equal:
                bad += 1
        mismatch[field] = {"count": bad, "denominator": len(minutes)}
        max_abs[field] = float(max_difference)

    # Trade counts are exact and use raw row counts on the full minute grid.
    count_mismatch = 0
    max_count_difference = 0
    for minute in expected_grid:
        native = klines.get(minute)
        actual_count = int(buckets.get(minute, {}).get("trade_count", 0))
        if native is None:
            count_mismatch += 1
            continue
        difference = abs(actual_count - native["trade_count"])
        max_count_difference = max(max_count_difference, difference)
        if difference:
            count_mismatch += 1
    mismatch["trade_count"] = {"count": count_mismatch, "denominator": len(expected_grid)}
    max_abs["trade_count"] = float(max_count_difference)

    # Compare sum(price * qty) as a non-gating diagnostic beside source quoteQty.
    diagnostic_quote_mismatch = 0
    diagnostic_quote_max_abs = Decimal(0)
    for minute in expected_grid:
        native = klines.get(minute)
        if native is None:
            diagnostic_quote_mismatch += 1
            continue
        raw = buckets.get(minute)
        calculated = raw["quote_price_times_qty"] if raw else Decimal(0)
        difference = abs(calculated - native["quote_volume"])
        diagnostic_quote_max_abs = max(diagnostic_quote_max_abs, difference)
        if not _equal(calculated, native["quote_volume"]):
            diagnostic_quote_mismatch += 1
    mismatch["quote_price_times_qty_diagnostic"] = {
        "count": diagnostic_quote_mismatch, "denominator": len(expected_grid), "gating": False,
    }
    max_abs["quote_price_times_qty_diagnostic"] = float(diagnostic_quote_max_abs)

    for field, record in mismatch.items():
        if field != "quote_price_times_qty_diagnostic" and record["count"]:
            failures.append(f"field_mismatch:{field}")
    daily_raw_base = sum((b["base_volume"] for b in buckets.values()), Decimal(0))
    daily_raw_quote = sum((b["quote_volume"] for b in buckets.values()), Decimal(0))
    daily_calc_quote = sum((b["quote_price_times_qty"] for b in buckets.values()), Decimal(0))
    daily_native_base = sum((b["base_volume"] for b in klines.values()), Decimal(0))
    daily_native_quote = sum((b["quote_volume"] for b in klines.values()), Decimal(0))
    if int(integrity["trade_rows"] or 0) == 0:
        failures.append("zero_trade_rows_ohlc_ineligible")
    if integrity["trade_id_gaps"]:
        pass  # Recorded diagnostic; preregistration does not classify gaps as automatic failure.
    return {
        "symbol": symbol,
        "utc_date": day,
        "archive_sha256": {"trades": trade_hash, "klines": kline_hash},
        "integrity": integrity,
        "grid": {
            "expected_minutes": len(expected_grid), "native_minutes": len(klines),
            "native_grid_complete": grid_complete, "native_active": len(native_active),
            "raw_active": len(raw_active), "common_active": len(common_active),
            "native_only_active": len(native_active - raw_active),
            "raw_only_active": len(raw_active - native_active),
        },
        "mismatches": mismatch,
        "max_absolute_difference": max_abs,
        "quote_price_times_qty_diagnostic": {
            "mismatches": diagnostic_quote_mismatch,
            "denominator": len(expected_grid),
            "max_absolute_difference": float(diagnostic_quote_max_abs),
            "gating": False,
        },
        "daily_totals": {
            "raw_base": float(daily_raw_base), "native_base": float(daily_native_base),
            "raw_quote": float(daily_raw_quote), "native_quote": float(daily_native_quote),
            "raw_price_times_qty_quote_diagnostic": float(daily_calc_quote),
        },
        "failure_reasons": sorted(set(failures)),
        "symbol_day_integrity_pass": not failures,
    }


def download_sample(trades_dir: Path, klines_dir: Path) -> list[dict[str, str]]:
    statuses: list[dict[str, str]] = []
    pairs = [(symbol, day) for day in DAYS for symbol in SYMBOLS]
    total = len(pairs) * 2
    for index, (symbol, day) in enumerate(pairs, 1):
        trade_path = trades_dir / f"{symbol}-trades-{day}.zip"
        trade_url = f"{TRADES_BASE}/{symbol}/{trade_path.name}"
        trade_status = download_archive(trade_url, trade_path)
        statuses.append({"symbol": symbol, "utc_date": day, "source": "trades", "status": trade_status})
        print(f"DOWNLOAD {index * 2 - 1}/{total} {symbol} {day} trades={trade_status}", flush=True)
        kline_path = klines_dir / f"{symbol}-1m-{day}.zip"
        kline_url = f"{KLINES_BASE}/{symbol}/1m/{kline_path.name}"
        kline_status = download_archive(kline_url, kline_path)
        statuses.append({"symbol": symbol, "utc_date": day, "source": "klines", "status": kline_status})
        print(f"DOWNLOAD {index * 2}/{total} {symbol} {day} klines={kline_status}", flush=True)
    return statuses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades-dir", type=Path, required=True)
    parser.add_argument("--klines-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download", action="store_true", help="download the fixed preregistered sample")
    args = parser.parse_args()
    download_status = download_sample(args.trades_dir, args.klines_dir) if args.download else []
    rows: list[dict[str, Any]] = []
    pairs = [(symbol, day) for day in DAYS for symbol in SYMBOLS]
    for index, (symbol, day) in enumerate(pairs, 1):
        rows.append(audit_pair(args.trades_dir, args.klines_dir, symbol, day))
        print(f"AUDITED {index}/{len(pairs)} {day} {symbol}", flush=True)
    fields = sorted({field for row in rows for field in row["mismatches"]})
    summary = {
        "classification": "historical_source_integrity_only_no_strategy_or_signal_test",
        "preregistration": "docs/research/binance-trades-kline-integrity-prereg-2026-11-19.md",
        "sample": {"symbols": list(SYMBOLS), "utc_dates": list(DAYS), "symbol_days": len(rows)},
        "license_note": "Historical source-integrity results derived from Binance Vision. Do not redistribute without attribution and applicable CC BY-NC-SA 4.0 compliance review.",
        "files": {"download_status": download_status},
        "symbol_days_passed_integrity": sum(row["symbol_day_integrity_pass"] for row in rows),
        "fields": {
            field: {
                "mismatches": sum(row["mismatches"].get(field, {}).get("count", 0) for row in rows),
                "denominator": sum(row["mismatches"].get(field, {}).get("denominator", 0) for row in rows),
            }
            for field in fields
        },
        "active_minute_set_mismatches": sum(
            row["grid"]["native_only_active"] + row["grid"]["raw_only_active"] for row in rows
        ),
        "rows": rows,
        "attribution": "Source: Binance Vision historical USD-M trades and klines. No raw archives included.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {args.output}", flush=True)
    print(f"SUMMARY symbol_days={len(rows)} passed={summary['symbol_days_passed_integrity']} "
          f"active_set_mismatches={summary['active_minute_set_mismatches']}", flush=True)


if __name__ == "__main__":
    main()
