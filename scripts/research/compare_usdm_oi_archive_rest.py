"""Compare one preregistered USD-M OI archive day to the public REST history endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.audit_usdm_metrics_sample import parse_checksum, sha256

SYMBOL = "BTCUSDT"
DAY = "2026-11-19"
PERIOD_MS = 300_000
ARCHIVE_URL = f"https://data.binance.vision/data/futures/um/daily/metrics/{SYMBOL}/{SYMBOL}-metrics-{DAY}.zip"
REST_URL = "https://fapi.binance.com/futures/data/openInterestHist"
OFFSETS_MS = (-PERIOD_MS, 0, PERIOD_MS)
FIELDS = {"sum_open_interest": "sumOpenInterest",
          "sum_open_interest_value": "sumOpenInterestValue"}


def get(url: str) -> tuple[bytes, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": "CoinTradeResearchAudit/1.0"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read(), {k.lower(): v for k, v in response.headers.items()}
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"request failed: {url}: {last_error}")


def _error_stats(left: np.ndarray, right: np.ndarray) -> dict:
    relative = np.abs(left - right) / np.maximum(np.abs(right), 1e-12)
    return {"matched_rows": int(len(relative)),
            "median_absolute_relative_error": float(np.median(relative)) if len(relative) else None,
            "p95_absolute_relative_error": float(np.quantile(relative, 0.95)) if len(relative) else None}


def compare(archive_bytes: bytes, rest_bytes: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"corrupt archive member: {bad_member}")
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"expected one CSV, got {csv_names}")
        with archive.open(csv_names[0]) as member:
            metrics = pd.read_csv(member)
    required = {"create_time", "symbol", *FIELDS.keys()}
    if not required.issubset(metrics.columns) or set(metrics.symbol.astype(str)) != {SYMBOL}:
        raise ValueError("archive schema or symbol mismatch")
    archive_time = pd.to_datetime(metrics.create_time, utc=True, errors="coerce")
    if archive_time.isna().any():
        raise ValueError("invalid archive create_time")
    metrics["timestamp_ms"] = archive_time.astype("int64") // 1_000_000
    if metrics.timestamp_ms.duplicated().any():
        raise ValueError("duplicate archive timestamps")
    response = json.loads(rest_bytes)
    if not isinstance(response, list) or not response:
        raise ValueError("REST response is not a non-empty JSON array")
    rest = pd.DataFrame(response)
    if not {"timestamp", *FIELDS.values()}.issubset(rest.columns):
        raise ValueError("REST schema mismatch")
    rest["timestamp"] = pd.to_numeric(rest.timestamp, errors="raise").astype("int64")
    if rest.timestamp.duplicated().any():
        raise ValueError("duplicate REST timestamps")

    by_offset = {}
    for offset in OFFSETS_MS:
        candidate = metrics.copy()
        candidate["rest_timestamp"] = candidate.timestamp_ms + offset
        joined = candidate.merge(rest, left_on="rest_timestamp", right_on="timestamp", how="inner")
        fields = {}
        for archive_field, rest_field in FIELDS.items():
            left = pd.to_numeric(joined[archive_field], errors="coerce").to_numpy(dtype=float)
            right = pd.to_numeric(joined[rest_field], errors="coerce").to_numpy(dtype=float)
            valid = np.isfinite(left) & np.isfinite(right)
            fields[archive_field] = _error_stats(left[valid], right[valid])
        by_offset[str(offset // 60_000)] = {
            "offset_minutes": offset // 60_000,
            "matched_rows": len(joined),
            "coverage": len(joined) / len(metrics),
            "fields": fields,
        }
    plus = by_offset["5"]
    passes = plus["coverage"] >= 0.95
    for field in FIELDS:
        stats = plus["fields"][field]
        passes = passes and stats["median_absolute_relative_error"] is not None
        passes = passes and stats["median_absolute_relative_error"] <= 1e-4
        passes = passes and stats["p95_absolute_relative_error"] <= 1e-3
        passes = passes and all(
            stats["median_absolute_relative_error"] < by_offset[key]["fields"][field]["median_absolute_relative_error"]
            for key in ("-5", "0")
        )
    return {
        "symbol": SYMBOL, "date": DAY, "archive_rows": len(metrics), "rest_rows": len(rest),
        "archive_min_utc": archive_time.min().isoformat(),
        "archive_max_utc": archive_time.max().isoformat(),
        "rest_min_utc": pd.to_datetime(rest.timestamp.min(), unit="ms", utc=True).isoformat(),
        "rest_max_utc": pd.to_datetime(rest.timestamp.max(), unit="ms", utc=True).isoformat(),
        "mapping_results": by_offset,
        "predeclared_plus_5m_alignment_screen": "PASS" if passes else "FAIL",
        "interpretation_limit": "One BTCUSDT day only; cannot validate older data, publication latency, or strategy feature eligibility.",
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite: {args.output_dir}")
    start_ms = int(datetime.fromisoformat(DAY).replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = start_ms + 24 * 60 * 60 * 1000
    query = urllib.parse.urlencode({"symbol": SYMBOL, "period": "5m",
                                    "startTime": start_ms - PERIOD_MS,
                                    "endTime": end_ms + PERIOD_MS, "limit": 500})
    archive_bytes, archive_headers = get(ARCHIVE_URL)
    checksum_bytes, checksum_headers = get(ARCHIVE_URL + ".CHECKSUM")
    expected_hash = parse_checksum(checksum_bytes)
    if sha256(archive_bytes) != expected_hash:
        raise ValueError("publisher archive checksum mismatch")
    rest_url = REST_URL + "?" + query
    rest_bytes, rest_headers = get(rest_url)
    result = compare(archive_bytes, rest_bytes)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "archive.zip").write_bytes(archive_bytes)
    (args.output_dir / "archive.zip.CHECKSUM").write_bytes(checksum_bytes)
    (args.output_dir / "rest.json").write_bytes(rest_bytes)
    metadata = {
        "archive_url": ARCHIVE_URL, "archive_sha256": sha256(archive_bytes),
        "publisher_sha256": expected_hash, "archive_response_headers": archive_headers,
        "checksum_response_headers": checksum_headers,
        "rest_url": rest_url, "rest_response_sha256": hashlib.sha256(rest_bytes).hexdigest(),
        "rest_response_headers": rest_headers,
        "official_docs": "https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data",
        "result": result,
    }
    (args.output_dir / "comparison.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["predeclared_plus_5m_alignment_screen"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
