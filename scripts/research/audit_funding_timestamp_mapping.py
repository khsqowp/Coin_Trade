"""Cross-check archived USD-M funding rows against Binance's public REST history."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile

API = "https://fapi.binance.com/fapi/v1/fundingRate"
DATES = ("2023-03-24", "2024-03-24", "2025-02-28")


def _utc_day_ms(day: str) -> tuple[int, int]:
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _archive_rows(path: Path, day: str) -> list[tuple[int, str]]:
    start_ms, end_ms = _utc_day_ms(day)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError(f"corrupt archive: {path}")
        csv_members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_members) != 1:
            raise ValueError(f"expected one CSV member in {path}")
        with archive.open(csv_members[0]) as raw:
            rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")))
    selected = []
    for row in rows:
        stamp = int(row["calc_time"])
        if start_ms <= stamp < end_ms:
            selected.append((stamp, row["last_funding_rate"]))
    return selected


def _fetch(symbol: str, day: str) -> tuple[list[tuple[int, str]], str, int]:
    start_ms, end_ms = _utc_day_ms(day)
    query = urlencode({"symbol": symbol, "startTime": start_ms,
                       "endTime": end_ms - 1, "limit": 1000})
    request = Request(f"{API}?{query}", headers={"User-Agent": "CoinTradeHistoricalAudit/1.0"})
    with urlopen(request, timeout=20) as response:
        body = response.read()
        status = response.status
    payload = json.loads(body)
    if not isinstance(payload, list):
        raise ValueError(f"unexpected REST response for {symbol} {day}")
    rows = [(int(row["fundingTime"]), row["fundingRate"]) for row in payload]
    return rows, hashlib.sha256(body).hexdigest(), status


def compare_rows(archive_rows: list[tuple[int, str]], api_rows: list[tuple[int, str]]) -> dict:
    archive_by_time = dict(archive_rows)
    api_by_time = dict(api_rows)
    duplicate_archive = len(archive_by_time) != len(archive_rows)
    duplicate_api = len(api_by_time) != len(api_rows)
    shared = sorted(set(archive_by_time) & set(api_by_time))
    try:
        exact_rate_matches = sum(
            Decimal(archive_by_time[stamp]) == Decimal(api_by_time[stamp]) for stamp in shared
        )
    except InvalidOperation as exc:
        raise ValueError("invalid decimal funding rate") from exc
    return {
        "archive_rows": len(archive_rows), "api_rows": len(api_rows),
        "timestamp_matches": len(shared), "exact_rate_matches": exact_rate_matches,
        "archive_only_timestamps": sorted(set(archive_by_time) - set(api_by_time)),
        "api_only_timestamps": sorted(set(api_by_time) - set(archive_by_time)),
        "duplicate_archive_timestamps": duplicate_archive,
        "duplicate_api_timestamps": duplicate_api,
        "pass": (not duplicate_archive and not duplicate_api
                 and len(archive_rows) == len(api_rows)
                 and len(shared) == len(archive_rows)
                 and exact_rate_matches == len(archive_rows)),
    }


def run(archive_root: Path, symbols: list[str], dates: tuple[str, ...] = DATES) -> dict:
    records = []
    for symbol in symbols:
        for day in dates:
            month = day[:7]
            path = archive_root / "funding" / symbol / f"{symbol}-fundingRate-{month}.zip"
            record = {"symbol": symbol, "date_utc": day, "status": "FAIL"}
            try:
                archive_rows = _archive_rows(path, day)
                api_rows, response_hash, http_status = _fetch(symbol, day)
                compared = compare_rows(archive_rows, api_rows)
                record.update({"status": "PASS" if compared["pass"] and http_status == 200 else "FAIL",
                               "http_status": http_status, "response_sha256": response_hash,
                               **compared})
            except Exception as exc:  # audit retains per-case failures instead of hiding them
                record["error"] = f"{type(exc).__name__}: {exc}"
            records.append(record)
            time.sleep(0.15)
    passed = sum(row["status"] == "PASS" for row in records)
    return {
        "status": "PASS" if passed == len(records) else "FAIL",
        "endpoint": API, "symbols": symbols, "dates_utc": list(dates),
        "sample_count": len(records), "passed": passed,
        "timestamp_semantics": "archive calc_time compared with REST fundingTime",
        "rate_comparison": "exact Decimal equality",
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    coverage = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    symbols = coverage["cohorts_by_exact_run"]["2023-03..2026-05"]
    result = run(args.archive_root, symbols)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "sample_count", "passed", "dates_utc")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
