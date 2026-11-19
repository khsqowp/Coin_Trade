#!/usr/bin/env python3
"""Audit locally staged Binance USD-M bookDepth archives under the preregistration.

Historical archive data only. This script performs no network access; it checks
locally staged archives and publisher checksums, then reports source diagnostics. It does
not calculate trading signals, labels, M2, TP/SL, or returns.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any

SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "LINKUSDT", "DOTUSDT",
    "AVAXUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT", "UNIUSDT", "AAVEUSDT",
    "NEARUSDT", "APTUSDT",
)
MAIN_DAYS = ("2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01")
DIAGNOSTIC_SYMBOLS = ("SOLUSDT", "BTCUSDT", "ETHUSDT", "AVAXUSDT")
DIAGNOSTIC_DAYS = tuple(f"2026-09-{day:02d}" for day in range(2, 7))
BANDS = (-5.0, -3.0, -2.0, -1.0, -0.2, 0.2, 1.0, 2.0, 3.0, 5.0)
ISSUE_BANDS = (-5.0, -1.0, -0.2, 0.2, 1.0, 2.0, 3.0, 5.0)
EXPECTED_SOL_COUNTS = {
    "2026-09-02": (2878, 2878, 2877, 2879, 2880, 2878, 2879, 2880),
    "2026-09-03": (2878, 2879, 2832, 1455, 1744, 2155, 2878, 2875),
    "2026-09-04": (2876, 2877, 2873, 50, 1380, 2873, 2880, 2879),
    "2026-09-05": (2876, 2876, 2878, 3, 1259, 2875, 2876, 2876),
    "2026-09-06": (2878, 2877, 2878, 4, 4, 396, 2697, 2879),
}
EXPECTED_CROSS_COUNTS = {"SOLUSDT": 4, "BTCUSDT": 3, "ETHUSDT": 2, "AVAXUSDT": 1}
EXPECTED_HEADER = ("timestamp", "percentage", "depth", "notional")
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _obtain_archive(root: Path, symbol: str, day: str) -> tuple[Path, str, str]:
    directory = root / symbol
    filename = f"{symbol}-bookDepth-{day}.zip"
    archive_path = directory / filename
    checksum_path = directory / f"{filename}.CHECKSUM"
    if not archive_path.is_file() or not checksum_path.is_file():
        raise FileNotFoundError(f"missing locally staged archive or checksum: {filename}")
    checksum_text = checksum_path.read_text(encoding="ascii").strip()
    expected = checksum_text.split()[0].lower() if checksum_text else ""
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise ValueError(f"invalid SHA-256 sidecar for {filename}: {checksum_text!r}")
    actual = _sha256(archive_path)
    return archive_path, expected, actual


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.strip())
    if parsed.tzinfo is not None:
        raise ValueError("timezone-aware timestamp is outside the preregistered naive-UTC assumption")
    return parsed.replace(tzinfo=timezone.utc)


def _parse_archive(root: Path, symbol: str, day: str, frozen_bands: tuple[float, ...] | None,
                   http_status: dict[tuple[str, str], tuple[int, int]]) -> dict[str, Any]:
    item: dict[str, Any] = {"symbol": symbol, "date_utc": day, "sample": "main" if day in MAIN_DAYS else "known_issue_diagnostic"}
    filename = f"{symbol}-bookDepth-{day}.zip"
    errors: list[str] = []
    try:
        archive_path, expected_hash, actual_hash = _obtain_archive(root, symbol, day)
        if expected_hash != actual_hash:
            errors.append("publisher_checksum_mismatch")
        status_pair = http_status.get((symbol, day))
        if status_pair is None:
            errors.append("missing_http_status_manifest_entry")
            checksum_status = archive_status = None
        else:
            checksum_status, archive_status = status_pair
            if checksum_status != 200 or archive_status != 200:
                errors.append("http_status_not_200")
        item["archive"] = {"filename": filename, "bytes": archive_path.stat().st_size,
                           "publisher_sha256": expected_hash, "local_sha256": actual_hash,
                           "checksum_pass": expected_hash == actual_hash,
                           "http_status": {"checksum_sidecar": checksum_status, "archive": archive_status},
                           "url": f"https://data.binance.vision/data/futures/um/daily/bookDepth/{symbol}/{filename}"}
        archive = zipfile.ZipFile(archive_path)
    except Exception as exc:  # Record a failed fixed sample cell and continue the allowlist.
        item["download_or_checksum_error"] = f"{type(exc).__name__}: {exc}"
        item["integrity_errors"] = ["archive_missing_or_checksum_failure"]
        item["structural_pass"] = False
        return item

    try:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1 or Path(members[0]).name != f"{symbol}-bookDepth-{day}.csv":
            item["csv_members"] = members
            errors.append("csv_member_identity_or_count")
            return _failed_item(item, errors)
        with archive.open(members[0]) as binary, io.TextIOWrapper(binary, encoding="utf-8", newline="") as text:
            reader = csv.DictReader(text)
            header = tuple(reader.fieldnames or ())
            item["header"] = list(header)
            if header != EXPECTED_HEADER:
                errors.append("unexpected_csv_header")
                return _failed_item(item, errors)
            counts_by_time: dict[datetime, Counter[float]] = defaultdict(Counter)
            band_values: dict[float, list[tuple[datetime, float, float]]] = defaultdict(list)
            seen: set[tuple[datetime, float]] = set()
            duplicate_keys = 0
            malformed = 0
            nulls = Counter()
            nonfinite = Counter()
            nonpositive = Counter()
            row_count = 0
            for row in reader:
                row_count += 1
                missing_fields = [name for name in EXPECTED_HEADER if row.get(name) is None or not row[name].strip()]
                for name in missing_fields:
                    nulls[name] += 1
                if missing_fields:
                    malformed += 1
                    continue
                try:
                    timestamp = _parse_timestamp(row["timestamp"])
                    percentage = float(row["percentage"])
                    depth = float(row["depth"])
                    notional = float(row["notional"])
                except (KeyError, TypeError, ValueError, OverflowError):
                    malformed += 1
                    continue
                if not all(math.isfinite(value) for value in (percentage, depth, notional)):
                    for name, value in (("percentage", percentage), ("depth", depth), ("notional", notional)):
                        if not math.isfinite(value):
                            nonfinite[name] += 1
                    continue
                if timestamp.date().isoformat() != day:
                    item.setdefault("timestamps_outside_filename_day", 0)
                    item["timestamps_outside_filename_day"] += 1
                if depth == 0 or notional == 0 or depth < 0 or notional < 0:
                    nonpositive["depth"] += int(depth <= 0)
                    nonpositive["notional"] += int(notional <= 0)
                key = (timestamp, percentage)
                if key in seen:
                    duplicate_keys += 1
                seen.add(key)
                counts_by_time[timestamp][percentage] += 1
                band_values[percentage].append((timestamp, depth, notional))
            timestamps = sorted(counts_by_time)
            observed_bands = tuple(sorted(band_values))
            item["row_count"] = row_count
            item["malformed_rows"] = malformed
            item["duplicate_timestamp_band_keys"] = duplicate_keys
            item["distinct_timestamps"] = len(timestamps)
            item["observed_bands"] = list(observed_bands)
            item["null_counts"] = dict(nulls)
            item["nonfinite_counts"] = dict(nonfinite)
            item["nonpositive_counts"] = dict(nonpositive)
            if malformed:
                errors.append("malformed_rows")
            if duplicate_keys:
                errors.append("duplicate_timestamp_band_key")
            if item.get("timestamps_outside_filename_day", 0):
                errors.append("timestamp_outside_filename_day")
            if nonfinite or nonpositive:
                errors.append("nonfinite_or_nonpositive_depth_notional")
            if len(timestamps) != 2880:
                errors.append("distinct_timestamp_count_not_2880")
            if timestamps:
                first = timestamps[0]
                last = timestamps[-1]
                day_start = datetime.combine(date.fromisoformat(day), datetime_time(), timezone.utc)
                phase_ok = day_start <= first < day_start + timedelta(seconds=30)
                cadence_ok = all((right - left) == timedelta(seconds=30) for left, right in zip(timestamps, timestamps[1:]))
                final_ok = day_start + timedelta(days=1, seconds=-30) <= last < day_start + timedelta(days=1)
                item["timestamp_bounds_and_cadence"] = {
                    "first": first.isoformat(), "last": last.isoformat(),
                    "phase_in_first_30s": phase_ok, "all_intervals_exactly_30s": cadence_ok,
                    "last_in_final_30s": final_ok,
                    "max_gap_seconds": max(((right - left).total_seconds() for left, right in zip(timestamps, timestamps[1:])), default=None),
                }
                if not (phase_ok and cadence_ok and final_ok):
                    errors.append("timestamp_cadence_or_day_bounds")
            if frozen_bands is not None and observed_bands != frozen_bands:
                errors.append("percentage_band_set_mismatch")
            if frozen_bands is None:
                item["band_set_template_frozen_from_this_file"] = True
                frozen_bands = observed_bands
            expected_band_set = frozen_bands or ()
            incomplete_timestamps = sum(counts != Counter({band: 1 for band in expected_band_set}) for counts in counts_by_time.values())
            item["timestamps_with_missing_or_duplicate_bands"] = incomplete_timestamps
            if incomplete_timestamps:
                errors.append("incomplete_timestamp_band_matrix")

            if not malformed and not nonfinite and not nonpositive and not duplicate_keys:
                item["bands"] = _band_diagnostics(band_values, timestamps, day, symbol)
            item["cumulative_depth_semantics"] = _monotonicity(band_values, timestamps)
            item["integrity_errors"] = errors
            item["structural_pass"] = not errors
            return item
    except (OSError, zipfile.BadZipFile, UnicodeError, csv.Error) as exc:
        errors.append(f"parse_error:{type(exc).__name__}:{exc}")
        return _failed_item(item, errors)
    finally:
        archive.close()


def _failed_item(item: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    item["integrity_errors"] = errors
    item["structural_pass"] = False
    return item


def _band_diagnostics(values: dict[float, list[tuple[datetime, float, float]]], timestamps: list[datetime], day: str, symbol: str) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for band, rows in values.items():
        pairs = [(depth, notional) for _, depth, notional in rows]
        pair_counts = Counter(pairs)
        most_common_count = pair_counts.most_common(1)[0][1] if pair_counts else 0
        longest = run = 0
        previous: tuple[float, float] | None = None
        for _, depth, notional in sorted(rows):
            current = (depth, notional)
            run = run + 1 if current == previous else 1
            longest = max(longest, run)
            previous = current
        ratio_unique: int | None = None
        if all(math.isfinite(depth) and math.isfinite(notional) and depth > 0 for _, depth, notional in rows):
            ratio_unique = len({round(notional / depth, 6) for _, depth, notional in rows})
        diagnostics[str(band)] = {
            "rows": len(rows), "distinct_depth_notional_pairs": len(pair_counts),
            "most_frequent_pair_occupancy": most_common_count / len(rows) if rows else None,
            "longest_repeated_pair_run": longest, "distinct_round_notional_over_depth_6": ratio_unique,
        }
    return diagnostics


def _monotonicity(values: dict[float, list[tuple[datetime, float, float]]], timestamps: list[datetime]) -> dict[str, Any]:
    bands = sorted(values)
    if not bands or any(band == 0 for band in bands):
        return {"status": "UNRESOLVED", "reason": "empty bands or zero-distance band"}
    sides = {"negative": [band for band in bands if band < 0], "positive": [band for band in bands if band > 0]}
    if not sides["negative"] or not sides["positive"]:
        return {"status": "UNRESOLVED", "reason": "both negative and positive signed bands are required"}
    depth_by_key = {(timestamp, band): depth for band, rows in values.items() for timestamp, depth, _ in rows}
    violations = 0
    comparisons = 0
    for side_bands in sides.values():
        ordered = sorted(side_bands, key=abs)
        for timestamp in timestamps:
            present = [band for band in ordered if (timestamp, band) in depth_by_key]
            for narrow, wide in zip(present, present[1:]):
                comparisons += 1
                narrow_depth = depth_by_key[(timestamp, narrow)]
                wide_depth = depth_by_key[(timestamp, wide)]
                if wide_depth + max(1e-10, 1e-8 * abs(narrow_depth)) < narrow_depth:
                    violations += 1
    return {"status": "PASS" if comparisons and violations == 0 else ("FAIL" if violations else "UNRESOLVED"),
            "comparisons": comparisons, "monotonicity_violations": violations,
            "interpretation_note": "Signed percentage sides treated separately; side identity is inferred from sign and remains an archive semantic assumption."}


def _known_issue_comparison(items: list[dict[str, Any]]) -> dict[str, Any]:
    lookup = {(item["symbol"], item["date_utc"]): item for item in items}
    comparisons: list[dict[str, Any]] = []
    for day, counts in EXPECTED_SOL_COUNTS.items():
        item = lookup.get(("SOLUSDT", day), {})
        bands = item.get("bands", {})
        for band, expected in zip(ISSUE_BANDS, counts):
            observed = bands.get(str(band), {}).get("distinct_round_notional_over_depth_6")
            comparisons.append({"symbol": "SOLUSDT", "date_utc": day, "percentage": band,
                                "expected": expected, "observed": observed,
                                "match": observed == expected if observed is not None else False,
                                "status": "COMPUTED" if observed is not None else "UNCOMPUTABLE"})
    for symbol, expected in EXPECTED_CROSS_COUNTS.items():
        item = lookup.get((symbol, "2026-09-06"), {})
        observed = item.get("bands", {}).get("0.2", {}).get("distinct_round_notional_over_depth_6")
        comparisons.append({"symbol": symbol, "date_utc": "2026-09-06", "percentage": 0.2,
                            "expected": expected, "observed": observed,
                            "match": observed == expected if observed is not None else False,
                            "status": "COMPUTED" if observed is not None else "UNCOMPUTABLE"})
    return {"expected_cells": 44, "matching_cells": sum(bool(cell["match"]) for cell in comparisons),
            "all_44_exactly_reproduced": len(comparisons) == 44 and all(cell["match"] for cell in comparisons),
            "disposition": "EXACTLY REPRODUCED" if len(comparisons) == 44 and all(cell["match"] for cell in comparisons) else "NOT EXACTLY REPRODUCED",
            "cells": comparisons}


def _read_http_manifest(path: Path) -> dict[tuple[str, str], tuple[int, int]]:
    statuses: dict[tuple[str, str], tuple[int, int]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        expected = ("symbol", "date_utc", "checksum_http_status", "archive_http_status")
        if tuple(reader.fieldnames or ()) != expected:
            raise ValueError(f"invalid HTTP status manifest header: {reader.fieldnames}")
        for row in reader:
            key = (row["symbol"], row["date_utc"])
            if key in statuses:
                raise ValueError(f"duplicate HTTP status manifest cell: {key}")
            statuses[key] = (int(row["checksum_http_status"]), int(row["archive_http_status"]))
    return statuses


def run_audit(root: Path, output: Path, http_manifest: Path) -> dict[str, Any]:
    http_status = _read_http_manifest(http_manifest)
    samples = [(symbol, day, "main") for day in MAIN_DAYS for symbol in SYMBOLS]
    samples += [(symbol, day, "known_issue_diagnostic") for day in DIAGNOSTIC_DAYS for symbol in DIAGNOSTIC_SYMBOLS]
    results: list[dict[str, Any]] = []
    frozen_bands: tuple[float, ...] | None = None
    for index, (symbol, day, sample) in enumerate(samples, 1):
        item = _parse_archive(root, symbol, day, frozen_bands, http_status)
        if index == 1:
            frozen_bands = tuple(item.get("observed_bands", ()))
            item["band_set_template_frozen_from_this_file"] = True
        item["sample"] = sample
        results.append(item)
        print(f"progress {index}/{len(samples)} symbol={symbol} date={day} sample={sample} pass={item.get('structural_pass', False)}", flush=True)
    main = [item for item in results if item["sample"] == "main"]
    diagnostics = [item for item in results if item["sample"] == "known_issue_diagnostic"]
    semantics = [item.get("cumulative_depth_semantics", {}).get("status", "UNRESOLVED") for item in main]
    payload = {
        "audit": "Binance USD-M bookDepth historical archive structure only",
        "preregistration": "docs/research/binance-bookdepth-archive-feasibility-prereg-2026-11-19.md",
        "http_status_manifest": str(http_manifest),
        "registered_sample_symbol_days": len(samples), "main_sample_symbol_days": len(main),
        "main_structure_pass_count": sum(bool(item.get("structural_pass")) for item in main),
        "main_structure_disposition": "MAIN_STRUCTURE_PASS" if len(main) == 80 and all(item.get("structural_pass") for item in main) else "MAIN_STRUCTURE_FAIL",
        "cumulative_depth_semantics_disposition": "FAIL" if "FAIL" in semantics else ("UNRESOLVED" if "UNRESOLVED" in semantics else "PASS"),
        "diagnostic_symbol_days": len(diagnostics),
        "known_issue_replication": _known_issue_comparison(diagnostics),
        "strategy_or_outcome_testing_performed": False,
        "archives": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/private/tmp/binance-bookdepth-audit-20261119"), help="Raw archives/checksums outside Git")
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/binance-bookdepth-audit-20261119/results.json"), help="Machine-readable output; keep raw run output outside Git")
    parser.add_argument("--http-status-manifest", type=Path, default=Path("/private/tmp/binance-bookdepth-audit-20261119/http_status.tsv"), help="HTTP statuses recorded by the allowlist downloader")
    args = parser.parse_args()
    payload = run_audit(args.root, args.output, args.http_status_manifest)
    print(json.dumps({key: payload[key] for key in (
        "registered_sample_symbol_days", "main_structure_pass_count", "main_structure_disposition",
        "cumulative_depth_semantics_disposition", "diagnostic_symbol_days",
    )}, sort_keys=True))
    print(f"known_issue={payload['known_issue_replication']['disposition']} matching={payload['known_issue_replication']['matching_cells']}/44")
    print(f"report={args.output}")
    return 0 if payload["main_structure_disposition"] == "MAIN_STRUCTURE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
