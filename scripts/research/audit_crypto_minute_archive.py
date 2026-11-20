"""Read-only timestamp-grid audit for archived Binance minute Parquet files."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


DATASETS = {
    "spot_klines_1m": ("open_time", "minute"),
    "um_klines_1m": ("open_time", "minute"),
    "um_markPriceKlines_1m": ("open_time", "minute"),
    "um_fundingRate": ("calc_time", "funding"),
}


def _months(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    if (year, month) > (end_year, end_month):
        raise ValueError("start month must be <= end month")
    result = []
    while (year, month) <= (end_year, end_month):
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def _expected_minute_count(month: str) -> int:
    year, number = map(int, month.split("-"))
    start = datetime(year, number, 1, tzinfo=timezone.utc)
    end = datetime(year + (number == 12), 1 if number == 12 else number + 1, 1, tzinfo=timezone.utc)
    return int((end - start).total_seconds() // 60)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_times(path: Path, column: str, kind: str) -> tuple[np.ndarray, int]:
    table = pq.read_table(path, columns=[column])
    values = table[column].to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
    divisor = 1000 if kind == "minute" and values.size and int(values.max()) > 10**14 else 1
    if divisor != 1:
        values = values // divisor
    return values, divisor


def audit(root: Path, start: str, end: str, with_hashes: bool = False) -> dict:
    months = _months(start, end)
    per_dataset = {}
    symbol_sets = {}
    files_by_key = {}
    records_by_key = {}
    for dataset, (column, kind) in DATASETS.items():
        folder = root / dataset
        symbols = sorted(path.name for path in folder.iterdir() if path.is_dir()) if folder.is_dir() else []
        symbol_sets[dataset] = set(symbols)
        records = []
        for symbol in symbols:
            for month in months:
                path = folder / symbol / f"{month}.parquet"
                if not path.is_file():
                    records.append({"symbol": symbol, "month": month, "status": "MISSING"})
                    continue
                errors = []
                try:
                    times, divisor = _load_times(path, column, kind)
                    if len(times) == 0:
                        errors.append("EMPTY")
                    if any(right <= left for left, right in zip(times, times[1:])):
                        errors.append("DUPLICATE_OR_UNSORTED")
                    if kind == "minute":
                        if any(right - left != 60_000 for left, right in zip(times, times[1:])):
                            errors.append("MINUTE_GAP_OR_BAD_STEP")
                        if len(times) != _expected_minute_count(month):
                            errors.append("CALENDAR_ROW_COUNT_MISMATCH")
                    else:
                        rates = pq.read_table(path, columns=["funding_interval_hours"])["funding_interval_hours"].to_pylist()
                        if not rates or len(rates) != len(times) or any(int(rate) not in {4, 8} for rate in rates):
                            errors.append("FUNDING_INTERVAL_VALUE_INVALID")
                        elif any(not any(abs((right - left) - hours * 3_600_000) <= 1_000
                                         for hours in {int(rates[index]), int(rates[index + 1])})
                                 for index, (left, right) in enumerate(zip(times, times[1:]))):
                            errors.append("FUNDING_TIME_STEP_MISMATCH")
                    record = {"symbol": symbol, "month": month, "status": "FAIL" if errors else "PASS",
                              "rows": len(times), "first_ms": int(times[0]) if len(times) else None,
                              "last_ms": int(times[-1]) if len(times) else None, "timestamp_divisor": divisor,
                              "size_bytes": path.stat().st_size, "errors": errors}
                    if with_hashes:
                        record["sha256"] = _sha256(path)
                    if kind == "minute" and len(times):
                        files_by_key[(symbol, month, dataset)] = times
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    record = {"symbol": symbol, "month": month, "status": "ERROR",
                              "errors": [f"{type(exc).__name__}: {exc}"]}
                records.append(record)
                records_by_key[(dataset, symbol, month)] = record
        per_dataset[dataset] = {"symbol_directories": len(symbols), "files": records,
                                "missing_count": sum(r["status"] == "MISSING" for r in records),
                                "failed_count": sum(r["status"] in {"FAIL", "ERROR"} for r in records)}

    alignment = []
    minute_datasets = tuple(name for name, (_, kind) in DATASETS.items() if kind == "minute")
    all_symbols = sorted(set.union(*symbol_sets.values()) if symbol_sets else set())
    for symbol in all_symbols:
        for month in months:
            arrays = [files_by_key.get((symbol, month, dataset)) for dataset in minute_datasets]
            present = [array for array in arrays if array is not None]
            mismatch = bool(present) and (len(present) != len(arrays) or any(
                not np.array_equal(array, present[0]) for array in present[1:]))
            if mismatch:
                alignment.append({"symbol": symbol, "month": month,
                                  "present_price_datasets": [dataset for dataset, array in zip(minute_datasets, arrays) if array is not None],
                                  "timestamp_arrays_equal": False})
    complete_file_cohort = sorted(symbol for symbol in set.intersection(*symbol_sets.values())
                                  if all(records_by_key.get((dataset, symbol, month), {}).get("status")
                                         in {"PASS", "FAIL"}
                                         for dataset in DATASETS for month in months))
    cohort_alignment = [row for row in alignment
                        if row["symbol"] in complete_file_cohort]
    spot_perp_mismatches = []
    for symbol in complete_file_cohort:
        for month in months:
            spot = files_by_key.get((symbol, month, "spot_klines_1m"))
            perp = files_by_key.get((symbol, month, "um_klines_1m"))
            if spot is not None and perp is not None and not np.array_equal(spot, perp):
                spot_perp_mismatches.append({"symbol": symbol, "month": month})
    return {"root": str(root), "start_month": start, "end_month": end,
            "hashes_computed": with_hashes, "dataset_order": list(DATASETS),
            "datasets": per_dataset, "price_timestamp_alignment_failures": alignment,
            "complete_file_cohort": complete_file_cohort,
            "complete_file_cohort_symbol_count": len(complete_file_cohort),
            "complete_file_cohort_month_count": len(months),
            "complete_file_cohort_price_alignment_failures": cohort_alignment,
            "complete_file_cohort_spot_perp_alignment_failures": spot_perp_mismatches,
            "status": "PASS" if not alignment and all(
                item["failed_count"] == 0 and item["missing_count"] == 0
                for item in per_dataset.values()) else "FAIL",
            "limitations": ["timestamp and file-integrity audit only; no OHLC value, licensing, survivorship, execution, or strategy validation",
                            "funding timestamps are checked against archive interval labels, not first-publication availability"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--start-month", required=True)
    parser.add_argument("--end-month", required=True)
    parser.add_argument("--output", type=Path, required=True, help="JSON output; never written under the source root")
    parser.add_argument("--sha256", action="store_true", help="hash every present Parquet file; potentially I/O intensive")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"archive root does not exist: {args.root}")
    if args.output.resolve().is_relative_to(args.root.resolve()):
        parser.error("output must be outside the read-only archive root")
    result = audit(args.root, args.start_month, args.end_month, args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(args.output),
                      "alignment_failures": len(result["price_timestamp_alignment_failures"]),
                      "sha256": args.sha256}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
