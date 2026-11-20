"""Audit frozen hourly kline and funding inputs for the CVD study; never scores signals."""
from __future__ import annotations

import argparse
import calendar
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

HOUR_MS = 3_600_000
KLINE_COLUMNS = {
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore",
}
FUNDING_COLUMNS = {"calc_time", "funding_interval_hours", "last_funding_rate"}


def _month_bounds(month: str) -> tuple[int, int, int]:
    parsed = datetime.strptime(month, "%Y-%m").replace(day=1, tzinfo=timezone.utc)
    start_ms = int(parsed.timestamp() * 1000)
    days = calendar.monthrange(parsed.year, parsed.month)[1]
    return start_ms, start_ms + days * 86_400_000, days


def _finite(row: dict[str, str], key: str, line: int) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {key} at row {line}") from exc
    if not math.isfinite(value):
        raise ValueError(f"non-finite {key} at row {line}")
    return value


def validate_kline_rows(rows: list[dict[str, str]], symbol: str, month: str,
                        allow_partial_start: bool = False) -> dict:
    start_ms, end_ms, days = _month_bounds(month)
    expected_count = days * 24
    if not rows:
        raise ValueError("empty hourly archive")
    if len(rows) != expected_count and not allow_partial_start:
        raise ValueError(f"expected {expected_count} hourly rows, got {len(rows)}")
    try:
        first_open_ms = int(rows[0]["open_time"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid first candle timestamp") from exc
    if (first_open_ms < start_ms or first_open_ms >= end_ms or first_open_ms % HOUR_MS
            or (first_open_ms != start_ms and not allow_partial_start)):
        raise ValueError("invalid or unapproved partial-month start")
    expected_from_first = (end_ms - first_open_ms) // HOUR_MS
    if len(rows) != expected_from_first:
        raise ValueError(f"hourly time gap or unexpected endpoint: expected {expected_from_first} rows from first observed bar, got {len(rows)}")
    previous = None
    taker_values = []
    for line, row in enumerate(rows, start=2):
        if not KLINE_COLUMNS.issubset(row):
            raise ValueError(f"required kline columns missing at row {line}")
        try:
            open_ms = int(row["open_time"])
            close_ms = int(row["close_time"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid candle timestamp at row {line}") from exc
        expected_ms = first_open_ms + (line - 2) * HOUR_MS
        if not start_ms <= open_ms < end_ms or open_ms != expected_ms:
            reason = "duplicate or off-grid candle timestamp" if previous == open_ms else "hourly time gap or unexpected endpoint"
            raise ValueError(f"{reason} at row {line}")
        if close_ms != open_ms + HOUR_MS - 1:
            raise ValueError(f"close_time does not end the declared hour at row {line}")
        values = {key: _finite(row, key, line) for key in (
            "open", "high", "low", "close", "volume", "quote_volume",
            "taker_buy_volume", "taker_buy_quote_volume",
        )}
        if min(values["open"], values["high"], values["low"], values["close"]) <= 0:
            raise ValueError(f"non-positive price at row {line}")
        if values["volume"] < 0 or values["quote_volume"] < 0:
            raise ValueError(f"negative volume at row {line}")
        if values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]) or values["high"] < values["low"]:
            raise ValueError(f"invalid OHLC relationship at row {line}")
        taker = values["taker_buy_volume"]
        tolerance = max(1e-12, values["volume"] * 1e-10)
        if taker < -tolerance or taker > values["volume"] + tolerance:
            raise ValueError(f"taker-buy volume outside [0, total volume] at row {line}")
        taker_values.append(taker)
        previous = open_ms
    return {"row_count": len(rows), "first_open_ms": first_open_ms,
            "last_open_ms": end_ms - HOUR_MS,
            "leading_unobserved_hours": (first_open_ms - start_ms) // HOUR_MS,
            "gap_count": 0,
            "taker_buy_base_min": min(taker_values), "taker_buy_base_max": max(taker_values)}


def validate_funding_rows(rows: list[dict[str, str]], symbol: str, month: str, *,
                          expected_start_ms: int | None = None,
                          expected_end_ms: int | None = None,
                          allow_partial_start: bool = False) -> dict:
    month_start_ms, month_end_ms, _ = _month_bounds(month)
    start_ms = month_start_ms if expected_start_ms is None else expected_start_ms
    end_ms = month_end_ms - 1 if expected_end_ms is None else expected_end_ms
    if not rows:
        raise ValueError("empty funding archive")
    times, intervals, rates = [], [], []
    for line, row in enumerate(rows, start=2):
        if not FUNDING_COLUMNS.issubset(row):
            raise ValueError(f"required funding columns missing at row {line}")
        try:
            stamp = int(row["calc_time"])
            interval = int(row["funding_interval_hours"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid funding timestamp/interval at row {line}") from exc
        rate = _finite(row, "last_funding_rate", line)
        if not month_start_ms <= stamp < month_end_ms:
            raise ValueError(f"funding timestamp outside {month} at row {line}")
        if interval <= 0:
            raise ValueError(f"non-positive funding interval at row {line}")
        times.append(stamp)
        intervals.append(interval)
        rates.append(rate)
    if times != sorted(times) or len(times) != len(set(times)):
        raise ValueError("funding timestamps duplicated or unordered")
    _validate_funding_steps(times, intervals)
    for line, (stamp, interval) in enumerate(zip(times, intervals), start=2):
        interval_ms = interval * HOUR_MS
        aligned = ((stamp + interval_ms // 2) // interval_ms) * interval_ms
        if abs(stamp - aligned) > 1_000:
            raise ValueError(f"funding timestamp is off its UTC settlement grid at row {line}")
    first_interval_ms = intervals[0] * HOUR_MS
    first_expected = ((start_ms + first_interval_ms - 1) // first_interval_ms) * first_interval_ms
    first_matches = abs(times[0] - first_expected) <= 1_000
    listing_edge = (allow_partial_start and times[0] < start_ms
                    and start_ms - times[0] <= first_interval_ms + 1_000)
    if not first_matches and not listing_edge:
        raise ValueError("missing first expected UTC funding settlement at coverage boundary")
    last_interval_ms = intervals[-1] * HOUR_MS
    last_expected = (end_ms // last_interval_ms) * last_interval_ms
    if abs(times[-1] - last_expected) > 1_000:
        raise ValueError("missing last expected UTC funding settlement at coverage boundary")
    return {"row_count": len(rows), "first_calc_ms": times[0], "last_calc_ms": times[-1],
            "interval_hours": sorted(set(intervals)), "utc_grid_checked": True,
            "boundary_checked": True}


def _validate_funding_steps(times: list[int], intervals: list[int]) -> None:
    for index, (left, right) in enumerate(zip(times, times[1:])):
        if not any(abs(right - left - hours * 3_600_000) <= 1_000
                   for hours in (intervals[index], intervals[index + 1])):
            raise ValueError(f"funding timestamps disagree with adjacent intervals at row {index + 2}")


def _read_zip_csv(path: Path) -> tuple[list[dict[str, str]], str]:
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"corrupt ZIP member {bad_member}")
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected exactly one CSV member, found {len(members)}")
        with archive.open(members[0]) as binary:
            rows = list(csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")))
    return rows, members[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_inputs(root: Path, manifest_path: Path, symbols: list[str], start_month: str,
                 end_month_exclusive: str) -> dict:
    start = datetime.strptime(start_month, "%Y-%m").date().replace(day=1)
    end = datetime.strptime(end_month_exclusive, "%Y-%m").date().replace(day=1)
    if start >= end:
        raise ValueError("start-month must precede end-month-exclusive")
    months = []
    year, month = start.year, start.month
    while (year, month) < (end.year, end.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = ((year + 1, 1) if month == 12 else (year, month + 1))

    manifest: dict[tuple[str, str, str], list[dict]] = {}
    with manifest_path.open(encoding="utf-8") as source:
        for line_no, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("kind"), row.get("symbol"), row.get("month"))
            manifest.setdefault(key, []).append(row)

    records, errors = [], []
    fund_series: dict[str, list[tuple[int, int]]] = {symbol: [] for symbol in symbols}
    kline_bounds: dict[tuple[str, str], tuple[int, int]] = {}
    for symbol in symbols:
        for month_text in months:
            for kind, folder, filename, validator in (
                ("klines_1h", "klines_1h", f"{symbol}-1h-{month_text}.zip", validate_kline_rows),
                ("funding", "funding", f"{symbol}-fundingRate-{month_text}.zip", validate_funding_rows),
            ):
                key = (kind, symbol, month_text)
                row = {"kind": kind, "symbol": symbol, "month": month_text, "status": "FAIL"}
                try:
                    entries = manifest.get(key, [])
                    if len(entries) != 1:
                        raise ValueError(f"manifest must contain exactly one entry, found {len(entries)}")
                    entry = entries[0]
                    if entry.get("status") not in {"downloaded", "cached_verified"}:
                        raise ValueError(f"manifest status is not verified: {entry.get('status')}")
                    path = root / folder / symbol / filename
                    observed_hash = _sha256(path)
                    if observed_hash != entry.get("sha256"):
                        raise ValueError("current file SHA-256 differs from preserved manifest")
                    parsed, member = _read_zip_csv(path)
                    if kind == "klines_1h":
                        validated = validate_kline_rows(
                            parsed, symbol, month_text, allow_partial_start=(month_text == months[0]))
                        kline_bounds[(symbol, month_text)] = (
                            int(parsed[0]["open_time"]), int(parsed[-1]["close_time"]))
                    else:
                        first_open, last_close = kline_bounds[(symbol, month_text)]
                        validated = validator(
                            parsed, symbol, month_text, expected_start_ms=first_open,
                            expected_end_ms=last_close,
                            allow_partial_start=(month_text == months[0]
                                                 and first_open > _month_bounds(month_text)[0]))
                    row.update({"status": "PASS", "sha256": observed_hash,
                                "archive_bytes": path.stat().st_size, "csv_member": member, **validated})
                    if kind == "funding":
                        fund_series[symbol].extend(
                            (int(item["calc_time"]), int(item["funding_interval_hours"])) for item in parsed
                        )
                except Exception as exc:
                    row["error"] = f"{type(exc).__name__}: {exc}"
                    errors.append({"kind": kind, "symbol": symbol, "month": month_text, "error": row["error"]})
                records.append(row)

    funding_boundary_checks = 0
    for symbol, points in fund_series.items():
        ordered = sorted(points)
        if len({stamp for stamp, _ in ordered}) != len(ordered):
            errors.append({"kind": "funding", "symbol": symbol, "error": "duplicate timestamp across month files"})
            continue
        try:
            _validate_funding_steps([p[0] for p in ordered], [p[1] for p in ordered])
            funding_boundary_checks += max(0, len(months) - 1)
        except ValueError as exc:
            errors.append({"kind": "funding", "symbol": symbol, "error": str(exc)})

    summary = {
        "status": "PASS" if not errors and all(r["status"] == "PASS" for r in records) else "FAIL",
        "symbols": len(symbols), "months": months, "archive_records": len(records),
        "passed_archives": sum(r["status"] == "PASS" for r in records),
        "failed_archives": sum(r["status"] != "PASS" for r in records),
        "funding_boundary_symbol_checks": funding_boundary_checks,
        "funding_month_boundary_checks": sum(
            1 for row in records if row.get("kind") == "funding" and row.get("boundary_checked") is True),
        "errors": errors,
        "limitations": ["archive/schema/timestamp integrity only; does not prove source publication latency",
                        "does not calculate or inspect any strategy outcome", "static symbol universe has survivorship/selection risk"],
        "records": records,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--start-month", default="2023-03")
    parser.add_argument("--end-month-exclusive", default="2025-03")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    coverage = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    symbols = coverage["cohorts_by_exact_run"]["2023-03..2026-05"]
    result = audit_inputs(args.archive_root, args.manifest, symbols,
                          args.start_month, args.end_month_exclusive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "status", "symbols", "archive_records", "passed_archives", "failed_archives",
        "funding_boundary_symbol_checks", "errors",
    )}, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
