#!/usr/bin/env python3
"""Audit Vision 5m metrics timestamps against public OI REST and aggTrades.

This is a data-semantics diagnostic, not a strategy backtest. Inputs are
publisher-archive ZIPs and public OI REST JSON already downloaded by the user.
No network calls are made. All source rows are read-only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FIVE_MINUTES_MS = 5 * 60 * 1000
UTC = dt.timezone.utc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics-dir", type=Path, required=True)
    parser.add_argument("--rest-dir", type=Path, required=True)
    parser.add_argument("--aggtrades-dir", type=Path, required=True)
    return parser.parse_args()


def epoch_ms(value: str) -> int:
    parsed = dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)


def verify_publisher_checksum(path: Path) -> str:
    checksum_path = Path(f"{path}.CHECKSUM")
    fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if not fields or len(fields[0]) != 64:
        raise ValueError(f"invalid checksum file: {checksum_path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest.lower() != fields[0].lower():
        raise ValueError(f"SHA-256 mismatch: {path}")
    return digest


def read_metrics(path: Path) -> tuple[list[dict[str, str]], str]:
    checksum = verify_publisher_checksum(path)
    with zipfile.ZipFile(path) as archive:
        csv_files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_files) != 1:
            raise ValueError(f"expected one CSV in {path}, found {len(csv_files)}")
        with archive.open(csv_files[0]) as stream:
            rows = list(csv.DictReader(line.decode("utf-8") for line in stream))
    if not rows:
        raise ValueError(f"empty metrics archive: {path}")
    return rows, checksum


def grid_audit(rows: list[dict[str, str]], day: str) -> dict[str, int]:
    times = [epoch_ms(row["create_time"]) for row in rows]
    counts = Counter(times)
    start = int(dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
    expected = set(range(start, start + 24 * 60 * 60 * 1000, FIVE_MINUTES_MS))
    return {
        "rows": len(rows),
        "unique_timestamps": len(counts),
        "duplicate_rows": sum(count - 1 for count in counts.values() if count > 1),
        "missing_grid_slots": len(expected.difference(counts)),
        "off_grid_rows": sum(timestamp not in expected for timestamp in times),
    }


def error_summary(pairs: list[tuple[float, float]]) -> dict[str, float | int | None]:
    errors = [abs(left - right) / max(abs(left), 1e-15) for left, right in pairs]
    ordered = sorted(errors)
    quantile = lambda q: ordered[min(len(ordered) - 1, int((len(ordered) - 1) * q))] if ordered else None
    return {
        "matched": len(pairs),
        "median_relative_error": statistics.median(errors) if errors else None,
        "p95_relative_error": quantile(0.95),
        "p99_relative_error": quantile(0.99),
        "max_relative_error": max(errors) if errors else None,
        "count_relative_error_gt_1pct": sum(error > 0.01 for error in errors),
        "count_relative_error_gt_5pct": sum(error > 0.05 for error in errors),
    }


def audit_oi(rows: list[dict[str, str]], rest_path: Path) -> dict[str, Any]:
    rest_bytes = rest_path.read_bytes()
    observations = json.loads(rest_bytes.decode("utf-8"))
    if not isinstance(observations, list):
        raise ValueError(f"OI response is not an array: {rest_path}")
    rest: dict[int, float] = {}
    for row in observations:
        timestamp = int(row["timestamp"])
        if timestamp in rest:
            raise ValueError(f"duplicate REST timestamp {timestamp}: {rest_path}")
        rest[timestamp] = float(row["sumOpenInterest"])

    offsets = (-FIVE_MINUTES_MS, 0, FIVE_MINUTES_MS)
    summaries: dict[str, Any] = {
        "rest_rows": len(observations),
        "rest_response_sha256": hashlib.sha256(rest_bytes).hexdigest(),
    }
    for offset in offsets:
        pairs = []
        for row in rows:
            timestamp = epoch_ms(row["create_time"]) + offset
            if timestamp in rest:
                pairs.append((float(row["sum_open_interest"]), rest[timestamp]))
        summaries[f"offset_{offset // 60000:+d}m"] = error_summary(pairs)
    return summaries


def audit_flow(rows: list[dict[str, str]], agg_path: Path) -> dict[str, Any]:
    checksum = verify_publisher_checksum(agg_path)
    bins: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    with zipfile.ZipFile(agg_path) as archive:
        csv_files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_files) != 1:
            raise ValueError(f"expected one CSV in {agg_path}, found {len(csv_files)}")
        with archive.open(csv_files[0]) as stream:
            reader = csv.DictReader(line.decode("utf-8") for line in stream)
            required = {"transact_time", "price", "quantity", "is_buyer_maker"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"unexpected aggTrades schema: {reader.fieldnames}")
            for row in reader:
                timestamp = int(row["transact_time"])
                bucket = timestamp // FIVE_MINUTES_MS * FIVE_MINUTES_MS
                is_taker_buy = row["is_buyer_maker"].strip().lower() == "false"
                bins[bucket][0 if is_taker_buy else 1] += float(row["quantity"])

    offsets = (-FIVE_MINUTES_MS, 0, FIVE_MINUTES_MS)
    summaries: dict[str, Any] = {"aggtrades_sha256": checksum}
    for offset in offsets:
        pairs = []
        observations = []
        for row in rows:
            bucket = epoch_ms(row["create_time"]) + offset
            buy, sell = bins.get(bucket, (0.0, 0.0))
            if buy > 0 and sell > 0:
                metric_ratio = float(row["sum_taker_long_short_vol_ratio"])
                agg_ratio = buy / sell
                pairs.append((metric_ratio, agg_ratio))
                observations.append({
                    "create_time_utc": row["create_time"],
                    "metrics_ratio": metric_ratio,
                    "aggtrades_ratio": agg_ratio,
                    "taker_buy_base": buy,
                    "taker_sell_base": sell,
                })
        summaries[f"offset_{offset // 60000:+d}m"] = error_summary(pairs)
        if offset == 0:
            summaries["same_bin_worst_examples"] = sorted(
                observations,
                key=lambda item: abs(item["metrics_ratio"] - item["aggtrades_ratio"])
                / max(abs(item["metrics_ratio"]), 1e-15),
                reverse=True,
            )[:3]
    summaries["conservative_available_at_offset_ms"] = FIVE_MINUTES_MS
    return summaries


def main() -> None:
    args = parse_args()
    results: dict[str, Any] = {"classification": "data_semantics_diagnostic_not_strategy_backtest", "oi": [], "taker_flow": []}
    for metrics_path in sorted(args.metrics_dir.glob("*-metrics-????-??-??.zip")):
        symbol, _, day = metrics_path.name[:-4].split("-", 2)
        rows, metrics_sha256 = read_metrics(metrics_path)
        row_result: dict[str, Any] = {
            "symbol": symbol,
            "date_utc": day,
            "metrics_sha256": metrics_sha256,
            "grid": grid_audit(rows, day),
        }
        rest_path = args.rest_dir / f"{symbol}-{day}-rest.json"
        if rest_path.exists():
            row_result["oi_alignment"] = audit_oi(rows, rest_path)
            results["oi"].append(row_result)
        agg_path = args.aggtrades_dir / f"{symbol}-aggTrades-{day}.zip"
        if agg_path.exists():
            row_result["taker_flow_alignment"] = audit_flow(rows, agg_path)
            results["taker_flow"].append(row_result)
    if not results["oi"] and not results["taker_flow"]:
        raise SystemExit("no matching metrics archives with REST or aggTrades companions")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
