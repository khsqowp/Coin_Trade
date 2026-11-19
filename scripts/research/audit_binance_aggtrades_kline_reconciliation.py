#!/usr/bin/env python3
"""Reconcile Binance Vision USD-M daily aggTrades with native 1m klines.

This is a historical source-integrity audit only; it computes no forecasts,
labels, strategy returns, or trading signals.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
    "DOGEUSDT", "TRXUSDT", "LTCUSDT", "BCHUSDT", "LINKUSDT", "DOTUSDT",
    "AVAXUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT", "UNIUSDT", "AAVEUSDT",
    "NEARUSDT", "APTUSDT",
)
DAYS = ("2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01")
MINUTE_MS = 60_000
DAY_MS = 86_400_000
FLOAT_REL_TOL = 1e-8
FLOAT_ABS_TOL = 1e-10
DAILY_REL_TOL = 1e-10
DAILY_ABS_TOL = 1e-8


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_csv(path: Path) -> tuple[str, list[str], Any]:
    sidecar = Path(f"{path}.CHECKSUM")
    if not path.is_file() or not sidecar.is_file():
        raise ValueError(f"missing archive or checksum sidecar: {path.name}")
    expected = sidecar.read_text(encoding="utf-8").split()[0].lower()
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"publisher checksum mismatch: {path.name}")
    archive = zipfile.ZipFile(path)
    members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if len(members) != 1:
        archive.close()
        raise ValueError(f"expected exactly one CSV in {path.name}, found {len(members)}")
    if Path(members[0]).name != f"{path.stem}.csv":
        archive.close()
        raise ValueError(f"CSV identity does not match archive name: {members[0]} in {path.name}")
    text = io.TextIOWrapper(archive.open(members[0]), encoding="utf-8", newline="")
    reader = csv.DictReader(text)
    if not reader.fieldnames:
        archive.close()
        raise ValueError(f"missing CSV header: {path.name}")
    return actual, list(reader.fieldnames), (archive, text, reader)


def _close_csv(resources: Any) -> None:
    archive, text, _reader = resources
    text.close()
    archive.close()


def _equal(left: float, right: float, rel: float, absolute: float) -> bool:
    return abs(left - right) <= max(absolute, rel * abs(right))


def audit_pair(root: Path, symbol: str, day: str) -> dict[str, Any]:
    agg_path = root / f"{symbol}-aggTrades-{day}.zip"
    kline_path = root / f"{symbol}-1m-{day}.zip"
    agg_hash, agg_header, agg_resources = _verified_csv(agg_path)
    kline_hash, kline_header, kline_resources = _verified_csv(kline_path)
    agg_archive, agg_text, agg_reader = agg_resources
    kline_archive, kline_text, kline_reader = kline_resources
    from datetime import date, datetime, time, timezone
    parsed_day = date.fromisoformat(day)
    start_ms = int(datetime.combine(parsed_day, time(), timezone.utc).timestamp() * 1000)
    end_ms = start_ms + DAY_MS

    agg_required = {"agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "transact_time", "is_buyer_maker"}
    kline_required = {"open_time", "open", "high", "low", "close", "volume", "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume"}
    if not agg_required.issubset(agg_header):
        raise ValueError(f"unexpected aggTrades columns for {symbol} {day}: {agg_header}")
    if not kline_required.issubset(kline_header):
        raise ValueError(f"unexpected kline columns for {symbol} {day}: {kline_header}")

    buckets: dict[int, dict[str, float | int]] = {}
    agg_rows = 0
    malformed = 0
    outside_day = 0
    duplicate_or_nonmonotonic_ids = 0
    id_gaps = 0
    previous_id: int | None = None
    previous_timestamp: int | None = None
    nonmonotonic_agg_timestamps = 0
    agg_daily_base = 0.0
    agg_daily_quote = 0.0
    try:
        for row in agg_reader:
            agg_rows += 1
            try:
                trade_id = int(row["agg_trade_id"])
                first_id = int(row["first_trade_id"])
                last_id = int(row["last_trade_id"])
                timestamp = int(row["transact_time"])
                price = float(row["price"])
                quantity = float(row["quantity"])
                buyer_maker = row["is_buyer_maker"].strip().lower()
                if not all(math.isfinite(v) for v in (price, quantity)) or price <= 0 or quantity <= 0 or buyer_maker not in {"true", "false"} or last_id < first_id:
                    raise ValueError("invalid numeric or side value")
            except (KeyError, TypeError, ValueError, OverflowError):
                malformed += 1
                continue
            if previous_id is not None:
                if trade_id <= previous_id:
                    duplicate_or_nonmonotonic_ids += 1
                elif trade_id != previous_id + 1:
                    id_gaps += trade_id - previous_id - 1
            previous_id = trade_id
            if previous_timestamp is not None and timestamp < previous_timestamp:
                nonmonotonic_agg_timestamps += 1
            previous_timestamp = timestamp
            if not start_ms <= timestamp < end_ms:
                outside_day += 1
                continue
            minute = timestamp // MINUTE_MS * MINUTE_MS
            sort_key = (timestamp, trade_id)
            bucket = buckets.get(minute)
            if bucket is None:
                bucket = {"open": price, "high": price, "low": price, "close": price, "base": 0.0, "quote": 0.0, "taker_base": 0.0, "taker_quote": 0.0, "underlying_trade_count": 0, "first_sort_key": sort_key, "last_sort_key": sort_key}
                buckets[minute] = bucket
            bucket["high"] = max(float(bucket["high"]), price)
            bucket["low"] = min(float(bucket["low"]), price)
            if sort_key < bucket["first_sort_key"]:
                bucket["first_sort_key"] = sort_key
                bucket["open"] = price
            if sort_key > bucket["last_sort_key"]:
                bucket["last_sort_key"] = sort_key
                bucket["close"] = price
            bucket["base"] = float(bucket["base"]) + quantity
            quote = price * quantity
            bucket["quote"] = float(bucket["quote"]) + quote
            if buyer_maker == "false":
                bucket["taker_base"] = float(bucket["taker_base"]) + quantity
                bucket["taker_quote"] = float(bucket["taker_quote"]) + quote
            bucket["underlying_trade_count"] = int(bucket["underlying_trade_count"]) + last_id - first_id + 1
            agg_daily_base += quantity
            agg_daily_quote += quote

        klines: dict[int, dict[str, float | int]] = {}
        kline_rows = 0
        kline_malformed = 0
        kline_outside_day = 0
        kline_nonmonotonic_timestamps = 0
        previous_kline_timestamp: int | None = None
        kline_daily_base = 0.0
        kline_daily_quote = 0.0
        for row in kline_reader:
            kline_rows += 1
            try:
                timestamp = int(row["open_time"])
                values = {name: float(row[name]) for name in ("open", "high", "low", "close", "volume", "quote_volume", "taker_buy_volume", "taker_buy_quote_volume")}
                count = int(row["count"])
                if not all(math.isfinite(v) for v in values.values()) or count < 0:
                    raise ValueError("invalid kline numeric")
            except (KeyError, TypeError, ValueError, OverflowError):
                kline_malformed += 1
                continue
            if previous_kline_timestamp is not None and timestamp < previous_kline_timestamp:
                kline_nonmonotonic_timestamps += 1
            previous_kline_timestamp = timestamp
            if not start_ms <= timestamp < end_ms:
                kline_outside_day += 1
                continue
            if timestamp % MINUTE_MS != 0 or timestamp in klines:
                kline_malformed += 1
                continue
            values["count"] = count
            klines[timestamp] = values
            kline_daily_base += values["volume"]
            kline_daily_quote += values["quote_volume"]
    finally:
        _close_csv(agg_resources)
        _close_csv(kline_resources)

    expected_minutes = set(range(start_ms, end_ms, MINUTE_MS))
    agg_minutes = set(buckets)
    kline_minutes = set(klines)
    both = agg_minutes & kline_minutes
    metric_names = ("open", "high", "low", "close", "base", "quote", "taker_base", "taker_quote", "underlying_trade_count")
    mismatch_counts = {name: 0 for name in metric_names}
    max_abs = {name: 0.0 for name in metric_names}
    for minute in both:
        agg = buckets[minute]
        native = klines[minute]
        reconstructed = {
            "open": float(agg["open"]), "high": float(agg["high"]), "low": float(agg["low"]), "close": float(agg["close"]),
            "base": float(agg["base"]), "quote": float(agg["quote"]), "taker_base": float(agg["taker_base"]), "taker_quote": float(agg["taker_quote"]),
            "underlying_trade_count": int(agg["underlying_trade_count"]),
        }
        expected = {
            "open": native["open"], "high": native["high"], "low": native["low"], "close": native["close"],
            "base": native["volume"], "quote": native["quote_volume"], "taker_base": native["taker_buy_volume"], "taker_quote": native["taker_buy_quote_volume"],
            "underlying_trade_count": native["count"],
        }
        for name in metric_names:
            difference = abs(float(reconstructed[name]) - float(expected[name]))
            max_abs[name] = max(max_abs[name], difference)
            equal = reconstructed[name] == expected[name] if name == "underlying_trade_count" else _equal(float(reconstructed[name]), float(expected[name]), FLOAT_REL_TOL, FLOAT_ABS_TOL)
            if not equal:
                mismatch_counts[name] += 1

    daily_base_diff = agg_daily_base - kline_daily_base
    daily_quote_diff = agg_daily_quote - kline_daily_quote
    return {
        "symbol": symbol,
        "utc_date": day,
        "archives": {
            "aggTrades_sha256": agg_hash,
            "kline_sha256": kline_hash,
            "publisher_checksums_passed": True,
        },
        "row_counts": {"aggTrades": agg_rows, "klines": kline_rows},
        "minutes": {
            "expected": len(expected_minutes),
            "aggTrades": len(agg_minutes),
            "klines": len(kline_minutes),
            "both": len(both),
            "aggTrades_only": len(agg_minutes - kline_minutes),
            "kline_only": len(kline_minutes - agg_minutes),
        },
        "integrity": {
            "agg_malformed_rows": malformed,
            "kline_malformed_rows": kline_malformed,
            "agg_timestamps_outside_utc_day": outside_day,
            "kline_timestamps_outside_utc_day": kline_outside_day,
            "nonmonotonic_agg_timestamps": nonmonotonic_agg_timestamps,
            "nonmonotonic_kline_timestamps": kline_nonmonotonic_timestamps,
            "duplicate_or_nonmonotonic_agg_trade_ids": duplicate_or_nonmonotonic_ids,
            "agg_trade_id_missing_values_between_rows": id_gaps,
            "agg_trade_id_last": previous_id,
        },
        "minute_mismatch_count": mismatch_counts,
        "minute_max_absolute_difference": max_abs,
        "daily_totals": {
            "agg_base": agg_daily_base,
            "kline_base": kline_daily_base,
            "base_difference_agg_minus_kline": daily_base_diff,
            "base_match": _equal(agg_daily_base, kline_daily_base, DAILY_REL_TOL, DAILY_ABS_TOL),
            "agg_quote_price_times_qty": agg_daily_quote,
            "kline_quote": kline_daily_quote,
            "quote_difference_agg_minus_kline": daily_quote_diff,
            "quote_match": _equal(agg_daily_quote, kline_daily_quote, DAILY_REL_TOL, DAILY_ABS_TOL),
        },
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = tuple(rows[0]["minute_mismatch_count"])
    totals = {name: sum(row["minute_mismatch_count"][name] for row in rows) for name in metric_names}
    denominators = {name: sum(row["minutes"]["both"] for row in rows) for name in metric_names}
    return {
        "classification": "historical_source_integrity_only_no_strategy_or_signal_test",
        "sample": {"symbols": list(SYMBOLS), "utc_dates": list(DAYS), "symbol_days": len(rows), "zip_archives": 2 * len(rows), "checksum_sidecars": 2 * len(rows)},
        "files": {"publisher_checksum_failures": sum(not r["archives"]["publisher_checksums_passed"] for r in rows)},
        "integrity_totals": {
            key: sum(r["integrity"][key] for r in rows)
            for key in ("agg_malformed_rows", "kline_malformed_rows", "agg_timestamps_outside_utc_day", "kline_timestamps_outside_utc_day", "nonmonotonic_agg_timestamps", "nonmonotonic_kline_timestamps", "duplicate_or_nonmonotonic_agg_trade_ids", "agg_trade_id_missing_values_between_rows")
        },
        "minute_comparison": {
            "expected_minutes_per_archive": 1440,
            "both_source_minutes_total": sum(r["minutes"]["both"] for r in rows),
            "aggTrades_only_minutes_total": sum(r["minutes"]["aggTrades_only"] for r in rows),
            "kline_only_minutes_total": sum(r["minutes"]["kline_only"] for r in rows),
            "mismatches_by_metric": {name: {"count": totals[name], "compared_minutes": denominators[name], "rate": totals[name] / denominators[name] if denominators[name] else None} for name in metric_names},
        },
        "daily_reconciliation": {
            "base_volume_match_count": sum(r["daily_totals"]["base_match"] for r in rows),
            "base_volume_unresolved": [{"symbol": r["symbol"], "utc_date": r["utc_date"], "difference": r["daily_totals"]["base_difference_agg_minus_kline"]} for r in rows if not r["daily_totals"]["base_match"]],
            "quote_volume_match_count": sum(r["daily_totals"]["quote_match"] for r in rows),
            "quote_volume_unresolved": [{"symbol": r["symbol"], "utc_date": r["utc_date"], "difference": r["daily_totals"]["quote_difference_agg_minus_kline"]} for r in rows if not r["daily_totals"]["quote_match"]],
        },
        "rows": rows,
        "attribution": "Source: Binance Vision historical data. Derived summary is subject to CC BY-NC-SA 4.0; no raw archives are included.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", help="optional single SYMBOL:YYYY-MM-DD pair for a smoke test")
    args = parser.parse_args()
    pairs = [(symbol, day) for day in DAYS for symbol in SYMBOLS]
    if args.only:
        symbol, day = args.only.split(":", 1)
        if symbol not in SYMBOLS or day not in DAYS:
            parser.error("--only must name a preregistered SYMBOL:YYYY-MM-DD pair")
        pairs = [(symbol, day)]
    rows = []
    for index, (symbol, day) in enumerate(pairs, 1):
        rows.append(audit_pair(args.data_dir, symbol, day))
        print(f"AUDITED {index}/{len(pairs)} {day} {symbol}", flush=True)
    result = summarize(rows)
    result["sample"]["symbol_days"] = len(rows)
    result["sample"]["zip_archives"] = 2 * len(rows)
    result["sample"]["checksum_sidecars"] = 2 * len(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {args.output}", flush=True)


if __name__ == "__main__":
    main()
