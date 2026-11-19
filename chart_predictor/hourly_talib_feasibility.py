#!/usr/bin/env python3
"""Outcome-blind hourly TA-Lib pattern frequency screen.

Reads only 1-minute OHLC columns and archive metadata from a read-only SQLite
database. It never reads prices after a signal to label or score an outcome.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
import talib
from talib import abstract


START_MS = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
END_MS = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000)
MINUTE_MS = 60_000
HOUR_MS = 60 * MINUTE_MS
DEADLINES_HOURS = (10, 20)
START_MONTH = datetime.fromtimestamp(START_MS / 1000, tz=timezone.utc).strftime("%Y-%m")
END_MONTH = datetime.fromtimestamp(END_MS / 1000, tz=timezone.utc).strftime("%Y-%m")
ANY_BULLISH = "ANY: all 30 bullish reversal patterns"
ANY_BEARISH = "ANY: all 25 bearish reversal patterns"
ANY_TWO_SIDED = "ANY: two-sided bullish+bearish union"
EXPECTED_MANIFEST_SHA256 = "63dd2082c07279f4e2aa8b36df5b6a8dd17512a097f1f4babb73e4a9ef97d45d"
EXPECTED_SYMBOL_COUNT = 86

# The labels and direction memberships are transcribed from Table 2 of
# Moser & Brauneis (2026). One TA-Lib function can serve both signs.
BULLISH = {
    "Abandoned Baby": "CDLABANDONEDBABY",
    "Breakaway": "CDLBREAKAWAY",
    "Concealing Baby Swallow": "CDLCONCEALBABYSWALL",
    "Counterattack": "CDLCOUNTERATTACK",
    "Doji Star Bullish": "CDLDOJISTAR",
    "Dragonfly Doji": "CDLDRAGONFLYDOJI",
    "Engulfing Pattern": "CDLENGULFING",
    "Hammer": "CDLHAMMER",
    "Harami Pattern": "CDLHARAMI",
    "Harami Cross Pattern": "CDLHARAMICROSS",
    "Hikkake Pattern": "CDLHIKKAKE",
    "Homing Pigeon": "CDLHOMINGPIGEON",
    "Inverted Hammer": "CDLINVERTEDHAMMER",
    "Kicking": "CDLKICKING",
    "Kicking by Length": "CDLKICKINGBYLENGTH",
    "Ladder Bottom": "CDLLADDERBOTTOM",
    "Matching Low": "CDLMATCHINGLOW",
    "Modified Hikkake Pattern": "CDLHIKKAKEMOD",
    "Morning Doji Star": "CDLMORNINGDOJISTAR",
    "Morning Star": "CDLMORNINGSTAR",
    "Piercing Pattern": "CDLPIERCING",
    "Stick Sandwich": "CDLSTICKSANDWICH",
    "Takuri": "CDLTAKURI",
    "Tasuki Gap": "CDLTASUKIGAP",
    "Three Inside Up": "CDL3INSIDE",
    "Three Outside Up": "CDL3OUTSIDE",
    "Three Stars in the South": "CDL3STARSINSOUTH",
    "Three Advancing White Soldiers": "CDL3WHITESOLDIERS",
    "Tristar Pattern": "CDLTRISTAR",
    "Unique 3 River": "CDLUNIQUE3RIVER",
}
BEARISH = {
    "Abandoned Baby": "CDLABANDONEDBABY",
    "Advance Block": "CDLADVANCEBLOCK",
    "Breakaway": "CDLBREAKAWAY",
    "Counterattack": "CDLCOUNTERATTACK",
    "Dark Cloud Cover": "CDLDARKCLOUDCOVER",
    "Doji Star Bearish": "CDLDOJISTAR",
    "Engulfing Pattern": "CDLENGULFING",
    "Evening Doji Star": "CDLEVENINGDOJISTAR",
    "Evening Star": "CDLEVENINGSTAR",
    "Hanging Man": "CDLHANGINGMAN",
    "Harami Pattern": "CDLHARAMI",
    "Hikkake Pattern": "CDLHIKKAKE",
    "Modified Hikkake Pattern": "CDLHIKKAKEMOD",
    "Identical Three Crows": "CDLIDENTICAL3CROWS",
    "Kicking": "CDLKICKING",
    "Kicking by Length": "CDLKICKINGBYLENGTH",
    "Harami Cross Pattern": "CDLHARAMICROSS",
    "Shooting Star": "CDLSHOOTINGSTAR",
    "Stalled Pattern": "CDLSTALLEDPATTERN",
    "Tasuki Gap": "CDLTASUKIGAP",
    "Two Crows": "CDL2CROWS",
    "Three Black Crows": "CDL3BLACKCROWS",
    "Three Inside Down": "CDL3INSIDE",
    "Three Outside Down": "CDL3OUTSIDE",
    "Tristar Pattern": "CDLTRISTAR",
}


def validate_pattern_contract() -> None:
    groups = talib.get_function_groups()["Pattern Recognition"]
    assert len(BULLISH) == 30 and len(BEARISH) == 25
    assert len(set(BULLISH.values()) & set(BEARISH.values())) == 15
    assert len(set(BULLISH.values()) | set(BEARISH.values())) == 40
    missing = (set(BULLISH.values()) | set(BEARISH.values())) - set(groups)
    if missing:
        raise RuntimeError(f"TA-Lib pattern functions unavailable: {sorted(missing)}")


def manifest_identity(db: sqlite3.Connection) -> tuple[list[str], str, int, int, dict[str, int], dict[tuple[str, str], int]]:
    rows = db.execute(
        "SELECT symbol, month, sha256, rows, archive_bytes, retrieved_utc "
        "FROM archive_manifest ORDER BY symbol, month"
    )
    digest = hashlib.sha256()
    count = 0
    research_month_rows = 0
    symbols: set[str] = set()
    expected_rows: Counter = Counter()
    expected_month_rows: dict[tuple[str, str], int] = {}
    seen_months: set[tuple[str, str]] = set()
    for row in rows:
        symbol, month, _sha256, row_count, _archive_bytes, _retrieved_utc = row
        month_key = (symbol, month)
        if month_key in seen_months:
            raise RuntimeError(f"duplicate archive manifest entry: {symbol} {month}")
        seen_months.add(month_key)
        try:
            parsed_month = datetime.strptime(month, "%Y-%m").strftime("%Y-%m")
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid archive manifest month: {month!r}") from exc
        if parsed_month != month:
            raise RuntimeError(f"non-canonical archive manifest month: {month!r}")
        digest.update(json.dumps(row, separators=(",", ":")).encode())
        digest.update(b"\n")
        symbols.add(symbol)
        if START_MONTH <= month < END_MONTH:
            expected_rows[symbol] += row_count
            expected_month_rows[month_key] = row_count
            research_month_rows += 1
        count += 1
    if not count:
        raise RuntimeError("archive_manifest is empty")
    research_symbols = sorted(expected_rows)
    if not research_symbols:
        raise RuntimeError("archive_manifest has no rows in the frozen research interval")
    return research_symbols, digest.hexdigest(), count, research_month_rows, dict(expected_rows), expected_month_rows


def _research_months() -> tuple[str, ...]:
    current = datetime.strptime(START_MONTH, "%Y-%m")
    end = datetime.strptime(END_MONTH, "%Y-%m")
    months = []
    while current < end:
        months.append(current.strftime("%Y-%m"))
        current = current.replace(year=current.year + (current.month == 12), month=1 if current.month == 12 else current.month + 1)
    return tuple(months)


def _research_month_starts_ms() -> tuple[int, ...]:
    return tuple(int(datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc).timestamp() * 1000)
                 for month in _research_months())


def flush_hour(bucket: int | None, rows: list[tuple[int, float, float, float, float]]):
    if bucket is None or len(rows) != 60:
        return None
    if rows[0][0] != bucket or rows[-1][0] != bucket + 59 * MINUTE_MS:
        return None
    if any(rows[i][0] != bucket + i * MINUTE_MS for i in range(60)):
        return None
    return (bucket, rows[0][1], max(r[2] for r in rows), min(r[3] for r in rows), rows[-1][4])


def calculate_signal_arrays(op: np.ndarray, hi: np.ndarray, lo: np.ndarray,
                            close: np.ndarray) -> dict[tuple[str, str], np.ndarray]:
    """Return fixed paper-pattern claims at or before each supplied bar."""
    functions = sorted(set(BULLISH.values()) | set(BEARISH.values()))
    max_lookback = max(abstract.Function(name).lookback for name in functions)
    first = max(149, max_lookback)
    ma = talib.SMA(close, timeperiod=144)
    delta = np.diff(ma)
    downtrend = np.zeros(len(close), dtype=bool)
    uptrend = np.zeros(len(close), dtype=bool)
    for last_delta_idx in range(5, len(delta)):
        changes = delta[last_delta_idx - 5 : last_delta_idx + 1]
        t = last_delta_idx + 1
        downtrend[t] = bool(np.all(changes < 0))
        uptrend[t] = bool(np.all(changes > 0))
    eligible = np.arange(len(close)) >= first
    results = {}
    raw_bullish = np.zeros(len(close), dtype=bool)
    raw_bearish = np.zeros(len(close), dtype=bool)
    raw_outputs = {}
    for name in functions:
        raw = getattr(talib, name)(op, hi, lo, close)
        raw_outputs[name] = raw
        if name in set(BULLISH.values()):
            raw_bullish |= raw > 0
        if name in set(BEARISH.values()):
            raw_bearish |= raw < 0
    for label, name in BULLISH.items():
        results[(label, "long")] = eligible & downtrend & (raw_outputs[name] > 0)
    for label, name in BEARISH.items():
        results[(label, "short")] = eligible & uptrend & (raw_outputs[name] < 0)
    results[("__feature_eligible__", "none")] = eligible
    results[("__raw_bullish__", "none")] = raw_bullish
    results[("__raw_bearish__", "none")] = raw_bearish
    return results


def assert_prefix_invariant(compute, arrays: tuple[np.ndarray, ...], cutoffs: tuple[int, ...]) -> None:
    full = compute(*arrays)
    for cutoff in cutoffs:
        prefix = compute(*(array[:cutoff] for array in arrays))
        for key, values in prefix.items():
            if not np.array_equal(values, full[key][:cutoff]):
                raise AssertionError(f"future-sensitive output {key} at prefix {cutoff}")


def scan_symbol(db: sqlite3.Connection, symbol: str, counters: dict, anchors: Counter,
                complete_hours: Counter, collisions: Counter, observed_minutes: Counter,
                observed_month_minutes: Counter) -> None:
    warmup_ms = 500 * HOUR_MS
    cur = db.execute(
        "SELECT open_ms, open, high, low, close FROM candles "
        "WHERE symbol=? AND open_ms>=? AND open_ms<? ORDER BY open_ms",
        (symbol, START_MS - warmup_ms, END_MS),
    )
    # One symbol is buffered as hourly bars, not minute rows. This keeps peak
    # memory bounded and lets gaps break pattern context explicitly.
    segments: list[list[tuple[int, float, float, float, float]]] = []
    segment: list[tuple[int, float, float, float, float]] = []
    current_bucket = None
    minute_rows: list[tuple[int, float, float, float, float]] = []
    previous_hour = None
    months = _research_months()
    month_starts = _research_month_starts_ms()
    month_index = 0
    month_rows = 0

    def accept(hour):
        nonlocal segment, previous_hour
        if hour is None:
            if segment:
                segments.append(segment)
                segment = []
            previous_hour = None
            return
        bucket = hour[0]
        if previous_hour is not None and bucket != previous_hour + HOUR_MS:
            if segment:
                segments.append(segment)
            segment = []
        segment.append(hour)
        previous_hour = bucket
        if START_MS <= bucket < END_MS:
            complete_hours[symbol] += 1

    for open_ms, op, hi, lo, close in cur:
        if START_MS <= open_ms < END_MS:
            observed_minutes[symbol] += 1
            while month_index + 1 < len(months) and open_ms >= month_starts[month_index + 1]:
                observed_month_minutes[(symbol, months[month_index])] = month_rows
                month_index += 1
                month_rows = 0
            month_rows += 1
        bucket = open_ms // HOUR_MS * HOUR_MS
        if current_bucket is None:
            current_bucket = bucket
        elif bucket != current_bucket:
            accept(flush_hour(current_bucket, minute_rows))
            minute_rows = []
            current_bucket = bucket
        minute_rows.append((open_ms, op, hi, lo, close))
    accept(flush_hour(current_bucket, minute_rows))
    if segment:
        segments.append(segment)
    if month_rows:
        observed_month_minutes[(symbol, months[month_index])] = month_rows

    for bars in segments:
        times = np.asarray([r[0] for r in bars], dtype=np.int64)
        op = np.asarray([r[1] for r in bars], dtype=np.float64)
        hi = np.asarray([r[2] for r in bars], dtype=np.float64)
        lo = np.asarray([r[3] for r in bars], dtype=np.float64)
        close = np.asarray([r[4] for r in bars], dtype=np.float64)
        signal_arrays = calculate_signal_arrays(op, hi, lo, close)
        for i in range(len(times)):
            ts = int(times[i])
            if not START_MS <= ts < END_MS or not signal_arrays[("__feature_eligible__", "none")][i]:
                continue
            anchors[symbol] += 1
            bullish_at_bar = []
            bearish_at_bar = []
            for label in BULLISH:
                if signal_arrays[(label, "long")][i]:
                    bullish_at_bar.append(label)
                    _record_signal(counters, symbol, ts, label, "long")
            for label in BEARISH:
                if signal_arrays[(label, "short")][i]:
                    bearish_at_bar.append(label)
                    _record_signal(counters, symbol, ts, label, "short")
            if bullish_at_bar:
                _record_signal(counters, symbol, ts, ANY_BULLISH, "long")
            if bearish_at_bar:
                _record_signal(counters, symbol, ts, ANY_BEARISH, "short")
            if bullish_at_bar or bearish_at_bar:
                _record_signal(counters, symbol, ts, ANY_TWO_SIDED, "both")
            if len(bullish_at_bar) > 1:
                collisions["same_direction_multi_long"] += 1
            if len(bearish_at_bar) > 1:
                collisions["same_direction_multi_short"] += 1
            if signal_arrays[("__raw_bullish__", "none")][i] and signal_arrays[("__raw_bearish__", "none")][i]:
                collisions["opposing_direction_same_hour"] += 1


def _record_signal(counters: dict, symbol: str, ts: int, label: str, side: str) -> None:
    key = (label, side)
    item = counters.setdefault(key, {"count": 0, "symbols": set(), "last": {10: {}, 20: {}}})
    item["count"] += 1
    item["symbols"].add(symbol)
    for deadline in DEADLINES_HOURS:
        accepted_at = item["last"][deadline].get(symbol)
        if accepted_at is None or ts >= accepted_at + deadline * HOUR_MS:
            item["last"][deadline][symbol] = ts
            item.setdefault("nonoverlap", Counter())[deadline] += 1


def scan_database(db_path: Path, expected_manifest_sha256: str | None = None,
                  expected_symbol_count: int | None = None) -> dict:
    uri = "file:" + quote(str(db_path.resolve())) + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.execute("PRAGMA query_only=ON")
    try:
        cols = {r[1] for r in db.execute("PRAGMA table_info(candles)")}
        required = {"symbol", "open_ms", "open", "high", "low", "close"}
        if not required <= cols:
            raise RuntimeError(f"candles schema missing: {sorted(required - cols)}")
        (symbols, manifest_sha256, manifest_rows, manifest_research_month_rows,
         expected_minutes, expected_month_minutes) = manifest_identity(db)
        if expected_manifest_sha256 and manifest_sha256 != expected_manifest_sha256:
            raise RuntimeError(f"manifest SHA-256 mismatch: expected {expected_manifest_sha256}, got {manifest_sha256}")
        if expected_symbol_count is not None and len(symbols) != expected_symbol_count:
            raise RuntimeError(f"research cohort size mismatch: expected {expected_symbol_count}, got {len(symbols)}")
        counters = {}
        anchors = Counter()
        complete_hours = Counter()
        collisions = Counter()
        observed_minutes = Counter()
        observed_month_minutes = Counter()
        for idx, symbol in enumerate(symbols, start=1):
            scan_symbol(db, symbol, counters, anchors, complete_hours, collisions, observed_minutes,
                        observed_month_minutes)
            if idx % 10 == 0 or idx == len(symbols):
                print(f"scan symbols={idx}/{len(symbols)} eligible_anchors={sum(anchors.values())}", flush=True)
        scheduled_per_symbol = (END_MS - START_MS) // HOUR_MS
        scheduled_total = scheduled_per_symbol * len(symbols)
        scheduled_month_keys = {(symbol, month) for symbol in symbols for month in _research_months()}
        absent_manifest_month_keys = scheduled_month_keys - set(expected_month_minutes)
        month_count_mismatches = {
            f"{symbol}/{month}": {
                "manifest_rows": expected_month_minutes[(symbol, month)],
                "observed_rows": observed_month_minutes.get((symbol, month), 0),
            }
            for (symbol, month), expected_rows in expected_month_minutes.items()
            if expected_rows != observed_month_minutes.get((symbol, month), 0)
        }
        for key, observed_rows in observed_month_minutes.items():
            if key in expected_month_minutes or observed_rows == 0:
                continue
            month_count_mismatches[f"{key[0]}/{key[1]}"] = {
                "manifest_rows": None, "observed_rows": observed_rows,
            }
        manifest_month_row_counts_match = not month_count_mismatches
        resolved_db_path = db_path.resolve()
        try:
            display_db_path = resolved_db_path.relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            display_db_path = resolved_db_path.name
        rows = []
        claim_specs = ([(k, "long") for k in BULLISH]
                       + [(k, "short") for k in BEARISH]
                       + [(ANY_BULLISH, "long"), (ANY_BEARISH, "short"), (ANY_TWO_SIDED, "both")])
        for label, side in claim_specs:
            item = counters.get((label, side), {"count": 0, "symbols": set(), "nonoverlap": Counter()})
            for deadline in DEADLINES_HOURS:
                count = item["count"]
                nonoverlap = item.get("nonoverlap", {}).get(deadline, 0)
                scheduled_coverage = count / scheduled_total if scheduled_total else 0.0
                feature_coverage = count / sum(anchors.values()) if sum(anchors.values()) else 0.0
                frequency_gate_pass = scheduled_coverage >= 0.10 and nonoverlap >= 200 and len(item["symbols"]) >= 20
                rows.append({
                    "pattern": label,
                    "side": side,
                    "deadline_hours": deadline,
                    "all_issued_signals": count,
                    "coverage_of_scheduled_symbol_hours": scheduled_coverage,
                    "coverage_of_feature_eligible_anchors": feature_coverage,
                    "nonoverlap_count": nonoverlap,
                    "distinct_symbols": len(item["symbols"]),
                    "frequency_gate_pass": frequency_gate_pass,
                    "claim_type": "all_pattern_union_exploratory" if label.startswith("ANY:") else "individual_pattern",
                    "eligible": manifest_month_row_counts_match and frequency_gate_pass,
                })
        return {
            "status": "outcome_blind_feasibility_only",
            "talib_python_version": talib.__version__,
            "talib_core_version": getattr(talib, "__ta_version__", b"unknown").decode(errors="replace"),
            "database_path": display_db_path,
            "db_bytes": db_path.stat().st_size,
            "manifest_sha256": manifest_sha256,
            "manifest_rows": manifest_rows,
            "manifest_research_month_rows": manifest_research_month_rows,
            "manifest_research_month_range": [START_MONTH, END_MONTH],
            "manifest_absent_scheduled_symbol_months": len(absent_manifest_month_keys),
            "manifest_absent_scheduled_symbol_months_list": [f"{s}/{m}" for s, m in sorted(absent_manifest_month_keys)],
            "expected_minute_rows": sum(expected_minutes.values()),
            "observed_minute_rows": sum(observed_minutes.values()),
            "manifest_month_row_counts_match": manifest_month_row_counts_match,
            "manifest_month_count_mismatches": month_count_mismatches,
            "symbols": symbols,
            "start_utc": "2021-01-01T00:00:00Z",
            "end_utc_exclusive": "2026-11-01T00:00:00Z",
            "scheduled_symbol_hours": scheduled_total,
            "complete_hours": sum(complete_hours.values()),
            "feature_eligible_anchors": sum(anchors.values()),
            "complete_hour_availability": sum(complete_hours.values()) / scheduled_total,
            "collisions": dict(collisions),
            "claims": rows,
            "eligible_claims": sum(r["eligible"] for r in rows),
        }
    finally:
        db.close()


def write_report(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    fields = list(result["claims"][0]) if result["claims"] else []
    with (out_dir / "claims.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result["claims"])
    passed = [r for r in result["claims"] if r["eligible"]]
    individual = [r for r in result["claims"] if r.get("claim_type", "all_pattern_union_exploratory" if r["pattern"].startswith("ANY:") else "individual_pattern") == "individual_pattern"]
    unions = [r for r in result["claims"] if r.get("claim_type", "all_pattern_union_exploratory" if r["pattern"].startswith("ANY:") else "individual_pattern") == "all_pattern_union_exploratory"]
    max_individual_scheduled_coverage = max((r["coverage_of_scheduled_symbol_hours"] for r in individual), default=0.0)
    max_individual_feature_coverage = max((r["coverage_of_feature_eligible_anchors"] for r in individual), default=0.0)
    lines = [
        "# Hourly TA-Lib pattern feasibility screen",
        "",
        "**Outcome-blind frequency screen only. No M2 outcomes or future price paths were read.**",
        "",
        f"- TA-Lib: Python {result['talib_python_version']} / core {result['talib_core_version']}",
        f"- Window: [{result['start_utc']}, {result['end_utc_exclusive']})",
        f"- Cohort: {len(result['symbols'])} archive-manifest symbols; all manifest rows={result['manifest_rows']}; research-range manifest rows={result['manifest_research_month_rows']}; manifest SHA-256={result['manifest_sha256']}",
        f"- Present-manifest symbol/month row-count check: expected={result['expected_minute_rows']:,}, observed={result['observed_minute_rows']:,}, count check={'PASS' if result['manifest_month_row_counts_match'] else 'FAIL'}; absent scheduled symbol-months={result['manifest_absent_scheduled_symbol_months']:,} are explicitly unavailable (check does not verify archived-file SHA-256 or row content)",
        f"- Scheduled symbol-hours: {result['scheduled_symbol_hours']:,}",
        f"- Complete hourly bars: {result['complete_hours']:,} ({result['complete_hour_availability']:.4%} of scheduled slots)",
        f"- Feature-eligible anchors: {result['feature_eligible_anchors']:,}",
        f"- Individual claims passing all frequency gates: {sum(r['eligible'] for r in individual)} / {len(individual)}; maximum individual scheduled coverage={max_individual_scheduled_coverage:.3%}; feature-eligible diagnostic={max_individual_feature_coverage:.3%}",
        f"- Post-hoc union claims passing all frequency gates: {sum(r['eligible'] for r in unions)} / {len(unions)}",
        f"- Same-hour collisions: {json.dumps(result['collisions'], sort_keys=True)}",
        "",
        "Individual pattern rows are preregistered. `ANY:` rows are post-hoc, deterministic unions added after individual frequency counts; they are exploratory and not independent or confirmatory evidence. Any pass only permits a separate, prospectively preregistered performance study. This exposed development panel cannot be confirmatory OOS.",
        "See `claims.csv` for all directional claims and both deadlines; see `summary.json` for the frozen input identity. The `ANY:` union rows are the only exploratory aggregates.",
        "",
        "| Exploratory union | Side | Deadline | Signals | Scheduled coverage | Feature-eligible coverage | Non-overlap N | Symbols | Frequency gate |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in unions:
        lines.append(
            f"| {row['pattern']} | {row['side']} | {row['deadline_hours']}h | {row['all_issued_signals']:,} | "
            f"{row['coverage_of_scheduled_symbol_hours']:.3%} | {row['coverage_of_feature_eligible_anchors']:.3%} | {row['nonoverlap_count']:,} | "
            f"{row['distinct_symbols']} | {'PASS' if row['eligible'] else 'FAIL'} |"
        )
    if passed:
        lines.extend(["", "Frequency-eligible claims:", ""])
        lines.extend(f"- {r['pattern']} ({r['side']}), {r['deadline_hours']}h" for r in passed)
    else:
        lines.extend(["", "No claim passed all preregistered frequency gates."])
    if not result["manifest_month_row_counts_match"]:
        lines.extend(["", f"Manifest/month row-count mismatches exist for {len(result['manifest_month_count_mismatches'])} symbol-months. Do not treat any frequency gate as passed."])
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    (out_dir / "DATA_LICENSE.md").write_text(
        "# Data attribution and licence\n\n"
        "This directory contains aggregate research results derived from historical Binance Vision USDⓈ-M market data; it does not include raw market-data rows.\n\n"
        "Source attribution: Binance Vision, https://data.binance.vision/ .\n\n"
        "These redistributed derivative results are provided under CC BY-NC-SA 4.0, consistent with Binance Vision Dataset Terms v1.0 (updated 2026-08-26), clauses 3.1, 4.1, and 4.5: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md .\n\n"
        "For personal, non-commercial, non-production historical research only. These results are not live or manual trading signals and do not authorize trading use.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", default=EXPECTED_MANIFEST_SHA256)
    parser.add_argument("--expected-symbol-count", default=EXPECTED_SYMBOL_COUNT, type=int)
    args = parser.parse_args()
    validate_pattern_contract()
    result = scan_database(args.db, args.expected_manifest_sha256, args.expected_symbol_count)
    write_report(result, args.out)
    print(f"complete eligible_claims={result['eligible_claims']} output={args.out}")


if __name__ == "__main__":
    main()
