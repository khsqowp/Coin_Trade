#!/usr/bin/env python3
"""Check timestamp continuity and checksum integrity of daily Vision ZIPs.

This is an archive-quality diagnostic only. It does not score strategy signals
or infer when an archived metric was available to a historical trader.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

UTC = dt.timezone.utc
DAY_MS = 24 * 60 * 60 * 1000


def _epoch_ms(value: str, is_metrics: bool) -> int:
    if is_metrics:
        parsed = dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        return int(parsed.timestamp() * 1000)
    return int(value)


def audit(path: Path, interval_minutes: int) -> dict[str, Any]:
    checksum_path = Path(f"{path}.CHECKSUM")
    expected_hash = checksum_path.read_text(encoding="utf-8").split()[0].lower()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise ValueError(f"publisher checksum mismatch: {path}")

    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {path}, found {len(members)}")
        with archive.open(members[0]) as stream:
            rows = list(csv.DictReader(line.decode("utf-8") for line in stream))
    if not rows:
        raise ValueError(f"empty archive: {path}")

    columns = list(rows[0])
    is_metrics = "create_time" in columns
    timestamp_column = "create_time" if is_metrics else "open_time"
    if timestamp_column not in columns:
        raise ValueError(f"unrecognized timestamp column in {path}: {columns}")

    timestamps = [_epoch_ms(row[timestamp_column], is_metrics) for row in rows]
    counts = Counter(timestamps)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})\.zip$", path.name)
    if not date_match:
        raise ValueError(f"expected a daily archive filename ending YYYY-MM-DD.zip: {path}")
    sample_day = dt.date.fromisoformat(date_match.group(1))
    day_start = int(dt.datetime.combine(sample_day, dt.time(), tzinfo=UTC).timestamp() * 1000)
    step = interval_minutes * 60 * 1000
    expected = set(range(day_start, day_start + DAY_MS, step))
    missing = sorted(expected - set(timestamps))
    off_grid = sorted(set(timestamps) - expected)
    numeric_columns = [column for column in columns if column not in {timestamp_column, "symbol"}]
    blank_values = {
        column: sum(not row.get(column, "").strip() for row in rows)
        for column in columns
    }
    numeric_errors: dict[str, int] = {}
    for column in numeric_columns:
        failures = 0
        for row in rows:
            try:
                if not math.isfinite(float(row[column])):
                    failures += 1
            except (TypeError, ValueError):
                failures += 1
        numeric_errors[column] = failures

    to_utc = lambda value: dt.datetime.fromtimestamp(value / 1000, UTC).isoformat()
    return {
        "path": str(path),
        "sha256": digest,
        "publisher_checksum_match": True,
        "dataset": "metrics" if is_metrics else "price_kline",
        "timestamp_column": timestamp_column,
        "rows": len(rows),
        "unique_timestamps": len(counts),
        "duplicate_rows": sum(count - 1 for count in counts.values() if count > 1),
        "expected_grid_rows": len(expected),
        "missing_grid_slots": len(missing),
        "missing_ranges_utc": [
            {"first": to_utc(missing[0]), "last": to_utc(missing[-1]), "count": len(missing)}
        ] if missing else [],
        "off_grid_timestamps": [to_utc(value) for value in off_grid],
        "min_timestamp_utc": to_utc(min(timestamps)),
        "max_timestamp_utc": to_utc(max(timestamps)),
        "columns": columns,
        "blank_values_by_column": blank_values,
        "nonfinite_or_non_numeric_by_column": numeric_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-minutes", type=int, default=5)
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()
    if args.interval_minutes < 1:
        parser.error("--interval-minutes must be positive")
    print(json.dumps({"classification": "archive_quality_only", "archives": [
        audit(path, args.interval_minutes) for path in args.archives
    ]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
