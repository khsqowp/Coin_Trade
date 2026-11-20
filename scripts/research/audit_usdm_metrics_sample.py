"""Download and validate the preregistered small USD-M metrics archive sample."""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import hashlib
import io
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
AUDIT_INVENTORY = Path("/private/tmp/cointrade-oi-archive-inventory.json")
FIXED_DATES = ("2023-03-24", "2024-03-24", "2025-03-24", "2026-05-30", "2026-05-31")
BOUNDARY_DATES = ("2026-06-24", "2026-06-25")
EXPECTED_COLUMNS = (
    "create_time", "symbol", "sum_open_interest", "sum_open_interest_value",
    "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
    "count_long_short_ratio", "sum_taker_long_short_vol_ratio",
)
VALUE_COLUMNS = EXPECTED_COLUMNS[2:]
BASE_URL = "https://data.binance.vision/data/futures/um/daily/metrics"
GRID_MS = 300_000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sample_requests(symbols: list[str], missing: list[dict]) -> dict[tuple[str, str], set[str]]:
    requests: dict[tuple[str, str], set[str]] = {}
    known_missing = {(item["symbol"], day) for item in missing for day in item["zip_missing"]}

    def add(symbol: str, day: str, reason: str) -> None:
        requests.setdefault((symbol, day), set()).add(reason)

    for symbol in symbols:
        for day in FIXED_DATES:
            add(symbol, day, "fixed_in_period")
        for day in BOUNDARY_DATES:
            add(symbol, day, "label_boundary_outside_cohort")
    for item in missing:
        for missing_day in item["zip_missing"]:
            day = date.fromisoformat(missing_day)
            for neighbor in (day - timedelta(days=1), day + timedelta(days=1)):
                neighbor_text = neighbor.isoformat()
                if (item["symbol"], neighbor_text) not in known_missing:
                    add(item["symbol"], neighbor_text, "neighbor_of_prelisted_missing_day")
    return requests


def parse_and_validate_zip(content: bytes, expected_symbol: str, day: str) -> dict:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"corrupt ZIP member: {bad_member}")
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"expected one CSV member, got {csv_names}")
        with archive.open(csv_names[0]) as member:
            frame = pd.read_csv(member)
    missing_columns = [column for column in EXPECTED_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"missing columns: {missing_columns}")
    if frame.empty:
        raise ValueError("empty daily metrics file")
    if set(frame["symbol"].astype(str)) != {expected_symbol}:
        raise ValueError("symbol field does not match archive path")
    raw_stamps = frame["create_time"]
    numeric_stamps = pd.to_numeric(raw_stamps, errors="coerce")
    if numeric_stamps.notna().all():
        stamps = numeric_stamps.astype("int64")
    else:
        parsed_stamps = pd.to_datetime(raw_stamps, utc=True, errors="coerce")
        if parsed_stamps.isna().any():
            raise ValueError("invalid create_time value")
        stamps = (parsed_stamps.astype("int64") // 1_000_000).astype("int64")
    if stamps.duplicated().any():
        raise ValueError("duplicate timestamp within file")
    if (stamps % GRID_MS != 0).any():
        raise ValueError("timestamp is off the 5-minute UTC grid")
    null_counts = {}
    for column in VALUE_COLUMNS:
        values = pd.to_numeric(frame[column], errors="coerce")
        null_counts[column] = int(values.isna().sum())
        if not np.isfinite(values.dropna().to_numpy(dtype=float)).all():
            raise ValueError(f"non-finite value in {column}")
    return {
        "row_count": len(frame),
        "timestamp_min_ms": int(stamps.min()),
        "timestamp_max_ms": int(stamps.max()),
        "timestamp_min_utc": pd.to_datetime(int(stamps.min()), unit="ms", utc=True).isoformat(),
        "timestamp_max_utc": pd.to_datetime(int(stamps.max()), unit="ms", utc=True).isoformat(),
        "null_counts": null_counts,
        "timestamps": stamps.astype(int).tolist(),
    }


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "CoinTradeResearchAudit/1.0"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(url, response.status, "unexpected status", response.headers, None)
                return response.read()
        except Exception as exc:  # retain the concrete failure in the returned audit record
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last_error}")


def parse_checksum(payload: bytes) -> str:
    match = re.search(rb"\b([0-9a-fA-F]{64})\b", payload)
    if not match:
        raise ValueError("publisher CHECKSUM does not contain a SHA-256 digest")
    return match.group(1).decode("ascii").lower()


def audit_sample(coverage_path: Path, inventory_path: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite: {output_dir}")
    coverage = json.loads(coverage_path.read_text())
    cohort = coverage["cohorts_by_exact_run"]["2023-03..2026-05"]
    previous = json.loads(inventory_path.read_text())
    if len(cohort) != 36 or previous["symbols"] != 36:
        raise ValueError("frozen input cohort is not 36 symbols")
    absent = [row for row in previous["results"] if row["zip_missing"]]
    requests = sample_requests(cohort, absent)
    output_dir.mkdir(parents=True)
    records = []
    timestamp_map = {}
    for index, ((symbol, day), reasons) in enumerate(sorted(requests.items()), start=1):
        stem = f"{symbol}-metrics-{day}.zip"
        base = f"{BASE_URL}/{symbol}/{stem}"
        row = {"symbol": symbol, "date": day, "reasons": sorted(reasons), "status": "failed"}
        try:
            content = fetch(base)
            check_payload = fetch(base + ".CHECKSUM")
            expected_hash = parse_checksum(check_payload)
            observed_hash = sha256(content)
            if observed_hash != expected_hash:
                raise ValueError(f"SHA-256 mismatch expected={expected_hash} observed={observed_hash}")
            (output_dir / stem).write_bytes(content)
            (output_dir / (stem + ".CHECKSUM")).write_bytes(check_payload)
            parsed = parse_and_validate_zip(content, symbol, day)
            row.update({"status": "pass", "bytes": len(content), "sha256": observed_hash,
                        "publisher_sha256": expected_hash, **parsed})
            timestamp_map[(symbol, day)] = set(parsed["timestamps"])
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        records.append(row)
        if index % 20 == 0 or index == len(requests):
            print(f"audited {index}/{len(requests)} records", flush=True)
        time.sleep(0.025)

    boundary_pairs = []
    days_by_symbol: dict[str, list[str]] = {}
    for symbol, day in requests:
        days_by_symbol.setdefault(symbol, []).append(day)
    for symbol, days in days_by_symbol.items():
        ordered = sorted(set(days))
        for left, right in zip(ordered, ordered[1:]):
            if date.fromisoformat(right) - date.fromisoformat(left) != timedelta(days=1):
                continue
            a = timestamp_map.get((symbol, left))
            b = timestamp_map.get((symbol, right))
            if a is None or b is None:
                continue
            shared = sorted(a & b)
            boundary_pairs.append({"symbol": symbol, "left_date": left, "right_date": right,
                                   "shared_timestamp_count": len(shared),
                                   "shared_timestamps_utc": [pd.to_datetime(x, unit="ms", utc=True).isoformat()
                                                              for x in shared]})
    output = {
        "audit_id": "usdm-metrics-sample-audit-20261120",
        "status": "PASS" if all(row["status"] == "pass" for row in records) else "FAIL",
        "request_count": len(requests),
        "passed": sum(row["status"] == "pass" for row in records),
        "failed": sum(row["status"] != "pass" for row in records),
        "fixed_in_period_dates": list(FIXED_DATES),
        "boundary_diagnostic_dates": list(BOUNDARY_DATES),
        "prelisted_missing_days": [{"symbol": r["symbol"], "dates": r["zip_missing"]} for r in absent],
        "records": records,
        "adjacent_sample_boundary_checks": boundary_pairs,
        "decision_limit": "Structural sample pass does not establish field-specific observation/publication time or strategy eligibility.",
    }
    (output_dir / "audit.json").write_text(json.dumps(output, indent=2) + "\n")
    with (output_dir / "audit.csv").open("w", newline="") as handle:
        fields = ("symbol", "date", "reasons", "status", "bytes", "sha256", "row_count",
                  "timestamp_min_utc", "timestamp_max_utc", "error")
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in records:
            writer.writerow({**row, "reasons": ";".join(row["reasons"])})
    print(json.dumps({k: output[k] for k in ("status", "request_count", "passed", "failed")}, indent=2))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--inventory-json", type=Path, default=AUDIT_INVENTORY)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = audit_sample(args.coverage_json, args.inventory_json, args.output_dir)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
