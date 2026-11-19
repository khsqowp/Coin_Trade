#!/usr/bin/env python3
"""Summarize event-time density in pre-audited Binance raw-trade archives.

This source-resolution diagnostic reads only trade ID, timestamp, and the
buyer-maker flag from raw rows. It computes no prices, outcomes, signals, or
strategy metrics. Raw archives and result JSON must stay outside Git.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path

DAY_MS = 86_400_000
WIDTHS_MS = (1_000, 10_000, 60_000)
HEADER = ["id", "price", "qty", "quote_qty", "time", "is_buyer_maker"]
ALIASES = {"trade Id": "id", "quoteQty": "quote_qty", "isBuyerMaker": "is_buyer_maker"}


def nearest_rank(histogram: Counter[int], probability: float) -> int:
    """Return the one-indexed nearest-rank quantile from an integer histogram."""
    total = sum(histogram.values())
    if total <= 0 or not 0 < probability <= 1:
        raise ValueError("quantile needs nonempty data and 0 < probability <= 1")
    rank = math.ceil(probability * total)
    seen = 0
    for value, frequency in sorted(histogram.items()):
        seen += frequency
        if seen >= rank:
            return value
    raise AssertionError("histogram rank not reached")


def density_summary(bin_counts: Counter[int], expected_bins: int) -> dict[str, object]:
    """Summarize event counts, including empty bins in the all-bin statistics."""
    if (expected_bins < 1 or len(bin_counts) > expected_bins
            or any(index < 0 or index >= expected_bins for index in bin_counts)):
        raise ValueError("invalid expected-bin count")
    if any(count <= 0 for count in bin_counts.values()):
        raise ValueError("bin_counts must contain positive counts for active bins")
    all_bins = Counter(bin_counts.values())
    all_bins[0] += expected_bins - len(bin_counts)
    active_bins = Counter(bin_counts.values())
    return {
        "expected_bins": expected_bins,
        "active_bins": len(bin_counts),
        "active_fraction": len(bin_counts) / expected_bins,
        "all_bins": {
            "p50": nearest_rank(all_bins, 0.50),
            "p95": nearest_rank(all_bins, 0.95),
            "p99": nearest_rank(all_bins, 0.99),
            "max": max(all_bins),
        },
        "active_bins_only": {
            "p50": nearest_rank(active_bins, 0.50) if active_bins else None,
            "p95": nearest_rank(active_bins, 0.95) if active_bins else None,
            "p99": nearest_rank(active_bins, 0.99) if active_bins else None,
            "max": max(active_bins) if active_bins else None,
        },
        "_histogram": dict(sorted(all_bins.items())),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_source(path: Path, expected_hash: str) -> None:
    sidecar = Path(f"{path}.CHECKSUM")
    fields = sidecar.read_text(encoding="ascii").strip().split()
    if (len(fields) != 2 or fields[1].lstrip("*") != path.name
            or len(fields[0]) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in fields[0])):
        raise ValueError(f"malformed publisher checksum sidecar: {sidecar.name}")
    sidecar_hash = fields[0].lower()
    if _sha256(path) != expected_hash or sidecar_hash != expected_hash.lower():
        raise ValueError(f"archive hash differs from frozen manifest/sidecar: {path.name}")


def _bounds(utc_date: str) -> tuple[int, int]:
    day = date.fromisoformat(utc_date)
    start = int(datetime.combine(day, time(), timezone.utc).timestamp() * 1000)
    return start, start + DAY_MS


def audit_trade_archive(
    path: Path, symbol: str, utc_date: str, expected_hash: str,
) -> dict[str, object]:
    """Count timestamped trades per fixed bin; do not parse price/size values."""
    _verify_source(path, expected_hash)
    expected_name = f"{symbol}-trades-{utc_date}.csv"
    start_ms, end_ms = _bounds(utc_date)
    bins = {width: Counter() for width in WIDTHS_MS}
    buyer_initiated = seller_initiated = 0
    previous_id: int | None = None
    previous_timestamp: int | None = None
    trade_count = 0

    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1 or Path(members[0]).name != expected_name:
            raise ValueError(f"unexpected CSV member: {path.name}")
        with archive.open(members[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            reader = csv.reader(text, strict=True)
            header = next(reader, None)
            canonical = [ALIASES.get(name.strip(), name.strip()) for name in (header or [])]
            if canonical != HEADER:
                raise ValueError(f"unexpected trade schema: {path.name}")
            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(HEADER):
                    raise ValueError(f"wrong field count at {path.name}:{line_number}")
                trade_id = int(row[0], 10)
                timestamp = int(row[4], 10)
                maker = row[5].strip().lower()
                if maker not in {"true", "false"}:
                    raise ValueError(f"invalid buyer-maker flag at {path.name}:{line_number}")
                if previous_id is not None and trade_id <= previous_id:
                    raise ValueError(f"non-increasing trade ID at {path.name}:{line_number}")
                if previous_timestamp is not None and timestamp < previous_timestamp:
                    raise ValueError(f"non-monotone timestamp at {path.name}:{line_number}")
                if not start_ms <= timestamp < end_ms:
                    raise ValueError(f"timestamp outside UTC date at {path.name}:{line_number}")
                previous_id, previous_timestamp = trade_id, timestamp
                trade_count += 1
                if maker == "false":
                    buyer_initiated += 1
                else:
                    seller_initiated += 1
                for width in WIDTHS_MS:
                    bucket = (timestamp - start_ms) // width
                    bins[width][bucket] += 1
            text.close()

    if trade_count == 0:
        raise ValueError(f"empty trade file: {path.name}")
    if buyer_initiated + seller_initiated != trade_count:
        raise AssertionError("buyer/seller event conservation failed")
    per_width = {}
    pooled_bin_histograms = {}
    for width in WIDTHS_MS:
        if sum(bins[width].values()) != trade_count:
            raise AssertionError(f"event conservation failed for {width} ms")
        summary = density_summary(bins[width], DAY_MS // width)
        pooled_bin_histograms[str(width)] = summary.pop("_histogram")
        per_width[str(width)] = summary
    return {
        "symbol": symbol,
        "utc_date": utc_date,
        "trade_rows": trade_count,
        "buyer_initiated_rows": buyer_initiated,
        "seller_initiated_rows": seller_initiated,
        "widths_ms": per_width,
        "_pooled_bin_histograms": pooled_bin_histograms,
    }


def summarize_manifest(manifest: dict[str, object], trades_dir: Path) -> dict[str, object]:
    if manifest.get("classification") != "historical_source_integrity_only_no_strategy_or_signal_test":
        raise ValueError("input is not the frozen raw-trades integrity manifest")
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != 80:
        raise ValueError("expected the original 80 symbol-day integrity rows")
    # Fixed 80-row sample; prior cross-source volume mismatches do not select
    # the density sample. Validate each raw archive on trade-native fields.
    eligible = []
    seen = set()
    for row in rows:
        symbol, utc_date = row.get("symbol"), row.get("utc_date")
        digest = row.get("archive_sha256", {}).get("trades")
        if (not isinstance(symbol, str) or not isinstance(utc_date, str)
                or (symbol, utc_date) in seen or not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdefABCDEF" for char in digest)):
            raise ValueError("malformed or duplicate allowlisted manifest fields")
        seen.add((symbol, utc_date))
        eligible.append({"symbol": symbol, "utc_date": utc_date,
                         "archive_sha256": {"trades": digest},
                         "prior_failure_reasons": row.get("failure_reasons", [])})
    if len({row["symbol"] for row in eligible}) != 20 or len({row["utc_date"] for row in eligible}) != 4:
        raise ValueError("fixed sample must contain 20 symbols and four UTC dates")
    pooled_histograms = {width: Counter() for width in WIDTHS_MS}
    per_symbol_day = []
    total_trades = buyer_rows = seller_rows = 0
    for record in sorted(eligible, key=lambda item: (item["utc_date"], item["symbol"])):
        archive = trades_dir / f"{record['symbol']}-trades-{record['utc_date']}.zip"
        result = audit_trade_archive(
            archive, record["symbol"], record["utc_date"], record["archive_sha256"]["trades"]
        )
        total_trades += result["trade_rows"]
        buyer_rows += result["buyer_initiated_rows"]
        seller_rows += result["seller_initiated_rows"]
        for width in WIDTHS_MS:
            histogram = Counter({int(k): v for k, v in result["_pooled_bin_histograms"][str(width)].items()})
            pooled_histograms[width].update(histogram)
        result.pop("_pooled_bin_histograms")
        result["prior_cross_source_failure_reasons"] = record["prior_failure_reasons"]
        per_symbol_day.append(result)

    pooled = {}
    for width in WIDTHS_MS:
        expected = (DAY_MS // width) * len(eligible)
        histogram = pooled_histograms[width]
        if sum(count * frequency for count, frequency in histogram.items()) != total_trades:
            raise AssertionError(f"pooled event conservation failed for {width} ms")
        active_histogram = Counter({value: count for value, count in histogram.items() if value > 0})
        pooled[str(width)] = {
            "expected_bins": expected,
            "active_bins": expected - histogram.get(0, 0),
            "active_fraction": (expected - histogram.get(0, 0)) / expected,
            "all_bins": {
                "p50": nearest_rank(histogram, 0.50),
                "p95": nearest_rank(histogram, 0.95),
                "p99": nearest_rank(histogram, 0.99),
                "max": max(histogram),
            },
            "active_bins_only": {
                "p50": nearest_rank(active_histogram, 0.50) if active_histogram else None,
                "p95": nearest_rank(active_histogram, 0.95) if active_histogram else None,
                "p99": nearest_rank(active_histogram, 0.99) if active_histogram else None,
                "max": max(active_histogram) if active_histogram else None,
            },
        }
    return {
        "classification": "historical_source_resolution_only_not_a_strategy_or_signal_test",
        "sample": {"symbols": 20, "utc_dates": 4, "symbol_days": 80,
                   "utc_dates_used": sorted({row["utc_date"] for row in eligible})},
        "included_symbol_days": len(eligible),
        "trade_rows": total_trades,
        "buyer_initiated_rows": buyer_rows,
        "seller_initiated_rows": seller_rows,
        "symbol_days_with_prior_cross_source_mismatches": sum(
            bool(row["prior_cross_source_failure_reasons"]) for row in per_symbol_day
        ),
        "bin_widths_ms": list(WIDTHS_MS),
        "pooled_density": pooled,
        "per_symbol_day": per_symbol_day,
        "limitations": [
            "Four isolated UTC dates are not a continuous or regime-representative panel.",
            "Event density is not a candidate signal frequency or predictive result.",
            "No prices, outcomes, labels, returns, targets, stops, or costs were computed.",
        ],
        "attribution": "Derived from Binance Vision USD-M raw trades; preserve applicable attribution and CC BY-NC-SA 4.0 terms.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trades-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = summarize_manifest(manifest, args.trades_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "included_symbol_days": result["included_symbol_days"],
        "trade_rows": result["trade_rows"],
        "output": str(args.output),
        "classification": result["classification"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
