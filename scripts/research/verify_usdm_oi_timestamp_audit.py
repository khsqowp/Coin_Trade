"""Offline integrity and timestamp-alignment verifier for saved USD-M OI audits.

This tool makes no network requests. It verifies saved archive/checksum/REST
bytes, recomputes T-5/T/T+5 OI alignments, and compares those results with the
saved audit JSON. A matching REST timestamp is not evidence of first
availability or point-in-time provenance.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import zipfile

PERIOD_MS = 300_000
OFFSETS = (-PERIOD_MS, 0, PERIOD_MS)
CSV_OI = "sum_open_interest"
REST_OI = "sumOpenInterest"
SHA256_RE = re.compile(r"\b([0-9a-fA-F]{64})\b")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_utc_ms(value: str) -> int:
    """Parse Binance CSV timestamps; naive CSV strings are defined as UTC."""
    value = str(value).strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def read_archive_rows(archive_bytes: bytes, expected_symbol: str) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"corrupt ZIP member: {bad}")
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV member; found {members!r}")
        with archive.open(members[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            rows = list(csv.DictReader(text))
    required = {"create_time", "symbol", CSV_OI}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("archive CSV is empty or missing required OI columns")
    for row in rows:
        if row["symbol"] != expected_symbol:
            raise ValueError(f"archive symbol mismatch: {row['symbol']!r}")
        row["_timestamp_ms"] = parse_utc_ms(row["create_time"])
        try:
            row["_oi"] = Decimal(row[CSV_OI])
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f"invalid archive OI value: {row[CSV_OI]!r}") from exc
        if not row["_oi"].is_finite():
            raise ValueError(f"non-finite archive OI value: {row[CSV_OI]!r}")
    timestamps = [row["_timestamp_ms"] for row in rows]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate archive timestamps")
    return rows


def read_rest_rows(rest_bytes: bytes, expected_symbol: str) -> list[dict]:
    payload = json.loads(rest_bytes)
    if not isinstance(payload, list) or not payload:
        raise ValueError("REST payload is not a non-empty JSON array")
    rows = []
    for source in payload:
        if source.get("symbol", expected_symbol) != expected_symbol:
            raise ValueError("REST symbol mismatch")
        if "timestamp" not in source or REST_OI not in source:
            raise ValueError("REST payload missing timestamp or OI")
        try:
            oi = Decimal(str(source[REST_OI]))
            if not oi.is_finite():
                raise ValueError("non-finite REST OI")
            rows.append({"timestamp": int(source["timestamp"]), "oi": oi})
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("invalid REST timestamp/OI") from exc
    timestamps = [row["timestamp"] for row in rows]
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate REST timestamps")
    return rows


def alignments(archive_rows: list[dict], rest_rows: list[dict],
               denominator: str = "archive") -> dict:
    """Compare each archive label T against REST labels T + offset."""
    if denominator not in {"archive", "rest"}:
        raise ValueError("denominator must be 'archive' or 'rest'")
    by_time = {row["timestamp"]: row["oi"] for row in rest_rows}
    result = {}
    for offset in OFFSETS:
        relative_errors = []
        exact = 0
        for row in archive_rows:
            right = by_time.get(row["_timestamp_ms"] + offset)
            if right is None:
                continue
            left = row["_oi"]
            base = left if denominator == "archive" else right
            relative_errors.append(abs(left - right) / max(abs(base), Decimal("1e-30")))
            exact += left == right
        floats = [float(value) for value in relative_errors]
        result[offset // 60_000] = {
            "matched": len(floats),
            "coverage": len(floats) / len(archive_rows),
            "exact_values": exact,
            "median_relative_error": statistics.median(floats) if floats else None,
            "p95_relative_error": _quantile(floats, 0.95),
            "max_relative_error": max(floats) if floats else None,
        }
    return result


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _publisher_hash(checksum_bytes: bytes) -> str:
    match = SHA256_RE.search(checksum_bytes.decode("utf-8", errors="replace"))
    if not match:
        raise ValueError("cannot parse publisher SHA-256")
    return match.group(1).lower()


def verify_crosscheck_dir(root: Path) -> dict:
    audit = json.loads((root / "audit.json").read_text())
    records = audit.get("records", [])
    verified = []
    absent = 0
    for record in records:
        symbol, date = record["symbol"], record["date"]
        zip_path = root / "metrics" / f"{symbol}-metrics-{date}.zip"
        checksum_path = zip_path.with_name(zip_path.name + ".CHECKSUM")
        rest_path = root / "rest" / record["rest_file"]
        if not record.get("oi_alignment"):
            absent += 1
            if record.get("zip_http") == "404":
                if not zip_path.exists() or not checksum_path.exists():
                    raise ValueError(f"missing saved 404 response body: {symbol} {date}")
                for response_path in (zip_path, checksum_path):
                    if b"<Code>NoSuchKey</Code>" not in response_path.read_bytes():
                        raise ValueError(f"404 body is not NoSuchKey: {symbol} {date}")
                if not rest_path.exists() or json.loads(rest_path.read_text()) != []:
                    raise ValueError(f"unexpected REST rows for absent pair: {symbol} {date}")
                if record.get("rest_rows") != 0:
                    raise ValueError(f"absent pair row-count mismatch: {symbol} {date}")
            elif zip_path.exists() and rest_path.exists():
                # A missing OI series is valid only if the raw inputs confirm it.
                archive_rows = read_archive_rows(zip_path.read_bytes(), symbol)
                rest_payload = json.loads(rest_path.read_text())
                if not isinstance(rest_payload, list):
                    raise ValueError(f"invalid REST body for absent pair: {symbol} {date}")
                if rest_payload:
                    rest_rows = read_rest_rows(rest_path.read_bytes(), symbol)
                    if any(row["_oi"].is_finite() for row in archive_rows) and any(
                            row["oi"].is_finite() for row in rest_rows):
                        raise ValueError(f"audit skips numeric OI unexpectedly: {symbol} {date}")
            else:
                raise ValueError(f"missing raw files for non-404 absent pair: {symbol} {date}")
            continue
        if record.get("zip_http") != "200" or record.get("checksum_http") != "200":
            raise ValueError(f"unexpected archive/checksum HTTP status: {symbol} {date}")
        archive_bytes = zip_path.read_bytes()
        checksum_bytes = checksum_path.read_bytes()
        rest_bytes = rest_path.read_bytes()
        archive_hash, rest_hash = sha256_bytes(archive_bytes), sha256_bytes(rest_bytes)
        if archive_hash != record["metrics_sha256"]:
            raise ValueError(f"archive hash mismatch: {symbol} {date}")
        if _publisher_hash(checksum_bytes) != archive_hash:
            raise ValueError(f"publisher checksum mismatch: {symbol} {date}")
        if rest_hash != record["oi_alignment"]["rest_response_sha256"]:
            raise ValueError(f"REST response hash mismatch: {symbol} {date}")
        archive_rows = read_archive_rows(archive_bytes, symbol)
        rest_rows = read_rest_rows(rest_bytes, symbol)
        if len(archive_rows) != record["grid"]["rows"]:
            raise ValueError(f"archive row count mismatch: {symbol} {date}")
        if len(rest_rows) != record["rest_rows"]:
            raise ValueError(f"REST row count mismatch: {symbol} {date}")
        day_start = parse_utc_ms(date + "T00:00:00Z")
        expected_grid = set(range(day_start, day_start + 86_400_000, PERIOD_MS))
        archive_times = {row["_timestamp_ms"] for row in archive_rows}
        off_grid = archive_times - expected_grid
        missing_grid = expected_grid - archive_times
        if len(off_grid) != record["grid"]["off_grid_rows"]:
            raise ValueError(f"off-grid count mismatch: {symbol} {date}")
        if len(missing_grid) != record["grid"]["missing_grid_slots"]:
            raise ValueError(f"missing-grid count mismatch: {symbol} {date}")
        if record["grid"]["duplicate_rows"] != 0:
            raise ValueError(f"saved audit reports duplicate timestamps: {symbol} {date}")
        actual = alignments(archive_rows, rest_rows, denominator="archive")
        for minutes in (-5, 0, 5):
            expected = record["oi_alignment"][f"offset_{minutes:+d}m"]
            got = actual[minutes]
            if got["matched"] != expected["matched"]:
                raise ValueError(f"matched-row mismatch at {minutes}m: {symbol} {date}")
            if not _close(got["max_relative_error"], expected["max_relative_error"]):
                raise ValueError(f"max-error mismatch at {minutes}m: {symbol} {date}")
        verified.append({"symbol": symbol, "date": date, "alignments": actual})

    exact_counts = {minutes: sum(
        row["alignments"][minutes]["max_relative_error"] == 0 for row in verified)
        for minutes in (-5, 0, 5)}
    return {"requested_records": len(records), "verified_numeric_pairs": len(verified),
            "absent_oi_pairs": absent, "exact_archive_to_rest_offset_pairs": exact_counts,
            "per_date": _date_summary(verified)}


def verify_single_day_dir(root: Path) -> dict:
    metadata = json.loads((root / "comparison.json").read_text())
    archive_bytes = (root / "archive.zip").read_bytes()
    checksum_bytes = (root / "archive.zip.CHECKSUM").read_bytes()
    rest_bytes = (root / "rest.json").read_bytes()
    archive_hash, rest_hash = sha256_bytes(archive_bytes), sha256_bytes(rest_bytes)
    if archive_hash != metadata["archive_sha256"] or archive_hash != metadata["publisher_sha256"]:
        raise ValueError("single-day archive/publisher checksum mismatch")
    if rest_hash != metadata["rest_response_sha256"]:
        raise ValueError("single-day REST response hash mismatch")
    if _publisher_hash(checksum_bytes) != archive_hash:
        raise ValueError("single-day checksum file mismatch")
    symbol = metadata["result"]["symbol"]
    archive_rows = read_archive_rows(archive_bytes, symbol)
    rest_rows = read_rest_rows(rest_bytes, symbol)
    actual = alignments(archive_rows, rest_rows, denominator="rest")
    for minutes in (-5, 0, 5):
        expected = metadata["result"]["mapping_results"][str(minutes)]["fields"][CSV_OI]
        got = actual[minutes]
        if got["matched"] != expected["matched_rows"]:
            raise ValueError(f"single-day matched-row mismatch at {minutes}m")
        if not _close(got["median_relative_error"], expected["median_absolute_relative_error"]):
            raise ValueError(f"single-day median mismatch at {minutes}m")
        if not _close(got["p95_relative_error"], expected["p95_absolute_relative_error"]):
            raise ValueError(f"single-day p95 mismatch at {minutes}m")
    return {"symbol": symbol, "date": metadata["result"]["date"],
            "archive_rows": len(archive_rows), "rest_rows": len(rest_rows),
            "exact_archive_to_rest_offset_pairs": {
                minutes: actual[minutes]["max_relative_error"] == 0 for minutes in (-5, 0, 5)},
            "alignments": actual}


def _close(actual: float | None, expected: float | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return abs(actual - expected) <= max(1e-12, abs(expected) * 1e-9)


def _date_summary(verified: list[dict]) -> dict:
    summary = {}
    for date in sorted({row["date"] for row in verified}):
        subset = [row for row in verified if row["date"] == date]
        summary[date] = {"pairs": len(subset), "exact_T": sum(
            row["alignments"][0]["max_relative_error"] == 0 for row in subset),
            "exact_T_plus_5m": sum(
                row["alignments"][5]["max_relative_error"] == 0 for row in subset)}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosscheck-dir", type=Path, required=True,
                        help="saved r031-style directory with audit.json, metrics/, rest/")
    parser.add_argument("--single-day-dir", type=Path,
                        help="optional saved comparison directory with comparison.json and raw bytes")
    args = parser.parse_args()
    report = {"crosscheck": verify_crosscheck_dir(args.crosscheck_dir)}
    if args.single_day_dir:
        report["single_day"] = verify_single_day_dir(args.single_day_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
