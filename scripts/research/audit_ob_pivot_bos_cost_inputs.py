"""Fingerprint and audit the funding/mark inputs blocking OB cost validation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.spot_perp_ob_first_touch import MONTHS, SYMBOLS

HOUR_MS = 60 * 60 * 1000
MINUTE_MS = 60 * 1000
FUNDING_MONTH = "2026-06"
MARK_MONTH = "2026-06"
FUNDING_INTERVAL_TOLERANCE_MS = 2 * MINUTE_MS


def digest_stable(path: Path) -> tuple[str, int]:
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file changed while auditing: {path}")
    return digest.hexdigest(), before.st_size


def funding_interval_gaps(times_ms: np.ndarray, intervals_hours: np.ndarray,
                          tolerance_ms: int = FUNDING_INTERVAL_TOLERANCE_MS) -> list[dict]:
    gaps = []
    times = np.asarray(times_ms, dtype=np.int64)
    intervals = np.asarray(intervals_hours, dtype=np.int64)
    if len(times) != len(intervals):
        raise ValueError("funding timestamp and interval arrays differ in length")
    if np.any(np.diff(times) <= 0):
        raise ValueError("funding timestamps are not strictly increasing")
    for index in range(1, len(times)):
        expected = int(intervals[index]) * HOUR_MS
        actual = int(times[index] - times[index - 1])
        if actual > expected + tolerance_ms:
            missing = max(0, int(round(actual / expected)) - 1)
            gaps.append({"previous_calc_time_ms": int(times[index - 1]),
                         "calc_time_ms": int(times[index]),
                         "interval_hours": int(intervals[index]),
                         "actual_gap_ms": actual,
                         "expected_gap_ms": expected,
                         "estimated_missing_events": missing})
    return gaps


def minute_grid_gaps(times_ms: np.ndarray) -> list[dict]:
    times = np.asarray(times_ms, dtype=np.int64)
    if not len(times):
        raise ValueError("mark-price timestamp array is empty")
    if np.any(np.diff(times) <= 0):
        raise ValueError("mark-price timestamps are not strictly increasing")
    gaps = []
    for index, actual in enumerate(np.diff(times)):
        if int(actual) != MINUTE_MS:
            gaps.append({"previous_open_time_ms": int(times[index]),
                         "next_open_time_ms": int(times[index + 1]),
                         "actual_gap_ms": int(actual),
                         "missing_minutes": max(0, int(round(int(actual) / MINUTE_MS)) - 1)})
    return gaps


def audit(root: Path) -> dict:
    funding_files = []
    funding_rows = 0
    funding_null_rates = 0
    funding_gap_rows = []
    funding_intervals_by_symbol = {}
    missing_funding_files = []

    for symbol in SYMBOLS:
        chunks = []
        interval_chunks = []
        for month in MONTHS:
            relative = f"um_fundingRate/{symbol}/{month}.parquet"
            path = root / relative
            if not path.is_file():
                missing_funding_files.append(relative)
                continue
            table = pq.read_table(path, columns=["calc_time", "funding_interval_hours",
                                                 "last_funding_rate"])
            if table["last_funding_rate"].null_count:
                funding_null_rates += table["last_funding_rate"].null_count
            month_times = table["calc_time"].to_numpy(zero_copy_only=False).astype(np.int64)
            month_intervals = table["funding_interval_hours"].to_numpy(zero_copy_only=False).astype(np.int64)
            month_rates = table["last_funding_rate"].to_numpy(zero_copy_only=False).astype(np.float64)
            if not np.all(np.isfinite(month_rates)):
                funding_null_rates += int(np.count_nonzero(~np.isfinite(month_rates)))
            chunks.append(month_times)
            interval_chunks.append(month_intervals)
            funding_rows += table.num_rows
            file_sha, size = digest_stable(path)
            funding_files.append({"path": relative, "size_bytes": size, "sha256": file_sha,
                                  "rows": table.num_rows})
        if len(chunks) == len(MONTHS):
            all_times = np.concatenate(chunks)
            all_intervals = np.concatenate(interval_chunks)
            intervals_seen = sorted(int(x) for x in np.unique(all_intervals))
            funding_intervals_by_symbol[symbol] = intervals_seen
            gaps = funding_interval_gaps(all_times, all_intervals)
            for gap in gaps:
                funding_gap_rows.append({"symbol": symbol, **gap})

    mark_files = []
    mark_gap_rows = []
    missing_mark_files = []
    mark_timestamp_rows = 0
    mark_month_start = root / "um_markPriceKlines_1m"
    for symbol in SYMBOLS:
        relative = f"um_markPriceKlines_1m/{symbol}/{MARK_MONTH}.parquet"
        path = root / relative
        if not path.is_file():
            missing_mark_files.append(relative)
            continue
        table = pq.read_table(path, columns=["open_time"])
        values = table["open_time"].to_numpy(zero_copy_only=False).astype(np.int64, copy=True)
        if len(values) and int(values.max()) > 10**14:
            values //= 1000
        gaps = minute_grid_gaps(values)
        file_sha, size = digest_stable(path)
        mark_timestamp_rows += len(values)
        mark_files.append({"path": relative, "size_bytes": size, "sha256": file_sha,
                           "timestamp_rows": len(values), "grid_gaps": len(gaps)})
        for gap in gaps:
            mark_gap_rows.append({"symbol": symbol, **gap})

    expected_funding_files = len(SYMBOLS) * len(MONTHS)
    if missing_funding_files or missing_mark_files or funding_null_rates:
        status = "DATA_INVALID"
    elif funding_gap_rows or mark_gap_rows:
        status = "KNOWN_COST_INPUT_GAPS"
    else:
        status = "NO_OBSERVED_GAPS_IN_AUDITED_WINDOW"
    return {
        "audit_id": "CRYPTO-OB-PIVOT-BOS-COST-INPUTS-20261122",
        "source_root_label": "TRADING_DATA_DIR/external/crypto/binance",
        "window": {"start_month": MONTHS[0], "end_month": MONTHS[-1],
                   "funding_symbols": len(SYMBOLS), "funding_months_per_symbol": len(MONTHS)},
        "status": status,
        "funding": {"expected_files": expected_funding_files,
                    "present_files": len(funding_files), "missing_files": missing_funding_files,
                    "rows": funding_rows, "null_or_nonfinite_rates": funding_null_rates,
                    "interval_hours_by_symbol": funding_intervals_by_symbol,
                    "interval_gap_anomalies": funding_gap_rows,
                    "files": sorted(funding_files, key=lambda row: row["path"])},
        "mark_price_june_2026": {"expected_files": len(SYMBOLS),
                                  "present_files": len(mark_files),
                                  "missing_files": missing_mark_files,
                                  "timestamp_rows": mark_timestamp_rows,
                                  "grid_gap_anomalies": mark_gap_rows,
                                  "files": sorted(mark_files, key=lambda row: row["path"])},
        "limitations": [
            "Funding and mark-price records are not used by the fee-only development scorer.",
            "The audit does not establish the first time a historical funding rate was knowable.",
            "Historical price/funding archives are exposed development data, not untouched OOS.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"input root does not exist: {args.root}")
    if args.output.resolve().is_relative_to(args.root.resolve()):
        parser.error("audit output must be outside immutable input root")
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"audit_id": result["audit_id"], "status": result["status"],
                      "funding_files": result["funding"]["present_files"],
                      "funding_rows": result["funding"]["rows"],
                      "funding_gaps": len(result["funding"]["interval_gap_anomalies"]),
                      "mark_files": result["mark_price_june_2026"]["present_files"],
                      "mark_gaps": len(result["mark_price_june_2026"]["grid_gap_anomalies"])},
                     sort_keys=True))
    return 2 if result["status"] == "DATA_INVALID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
