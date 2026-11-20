"""Independent arithmetic and event-order audit for the calendar M2 ledger."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

HOUR_MS = 3_600_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wilson(hits: int, count: int) -> list[float | None]:
    if not count:
        return [None, None]
    z = 1.959963984540054
    p = hits / count
    den = 1 + z * z / count
    center = (p + z * z / (2 * count)) / den
    margin = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / den
    return [center - margin, center + margin]


def audit(ledger_path: Path, summary_path: Path, baseline_path: Path) -> tuple[dict, list[dict]]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    with ledger_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    problems: list[str] = []
    per_symbol: dict[str, list[dict]] = {}
    exits: dict[str, int] = {}
    for number, row in enumerate(rows, 2):
        symbol = row["symbol"]
        per_symbol.setdefault(symbol, []).append(row)
        side = 1 if row["side"] == "long" else (-1 if row["side"] == "short" else 0)
        if not side:
            problems.append(f"row {number}: invalid side")
        entry_ms, signal_ms, exit_ms = (int(row[key]) for key in
                                        ("entry_time_ms", "signal_time_ms", "exit_time_ms"))
        if entry_ms != signal_ms:
            problems.append(f"row {number}: entry does not equal signal bar open")
        if not HOUR_MS <= exit_ms - entry_ms <= 4 * HOUR_MS:
            problems.append(f"row {number}: holding horizon outside one-to-four hours")
        reason = row["reason"]
        hit = row["m2_hit"] == "True"
        if hit != (reason == "TARGET"):
            problems.append(f"row {number}: M2 label contradicts exit reason")
        numbers = {key: float(row[key]) for key in
                   ("entry", "stop", "target", "exit_price", "gross_return", "funding_cost",
                    "net_base", "net_stress")}
        if not all(math.isfinite(value) for value in numbers.values()):
            problems.append(f"row {number}: non-finite monetary value")
        if side == 1 and not (numbers["stop"] < numbers["entry"] < numbers["target"]):
            problems.append(f"row {number}: long barrier order invalid")
        if side == -1 and not (numbers["target"] < numbers["entry"] < numbers["stop"]):
            problems.append(f"row {number}: short barrier order invalid")
        expected_gross = side * (numbers["exit_price"] - numbers["entry"]) / numbers["entry"]
        if abs(expected_gross - numbers["gross_return"]) > 1e-12:
            problems.append(f"row {number}: gross return arithmetic mismatch")
        if abs(numbers["net_base"] - (expected_gross - 0.001 - numbers["funding_cost"])) > 1e-12:
            problems.append(f"row {number}: base-cost arithmetic mismatch")
        if abs(numbers["net_stress"] - (expected_gross - 0.003 - numbers["funding_cost"])) > 1e-12:
            problems.append(f"row {number}: stress-cost arithmetic mismatch")
        if hit and abs(numbers["exit_price"] - numbers["target"]) > 1e-10:
            problems.append(f"row {number}: target exit price mismatch")
        exits[reason] = exits.get(reason, 0) + 1

    symbol_overlap = []
    for symbol, events in per_symbol.items():
        events.sort(key=lambda row: int(row["entry_time_ms"]))
        for left, right in zip(events, events[1:]):
            if int(right["entry_time_ms"]) < int(left["exit_time_ms"]):
                symbol_overlap.append(symbol)
                break
    ordered = sorted(rows, key=lambda row: (int(row["entry_time_ms"]), row["symbol"]))
    global_events = []
    last_exit = -1
    for row in ordered:
        if int(row["entry_time_ms"]) <= last_exit:
            continue
        global_events.append(row)
        last_exit = int(row["exit_time_ms"])

    hits = sum(row["m2_hit"] == "True" for row in rows)
    count = len(rows)
    expected = summary["metric"]
    calculated = {
        "signals": count, "m2_hits": hits, "m2_rate": hits / count if count else None,
        "m2_wilson_95": _wilson(hits, count), "symbols": len(per_symbol),
        "market_time_nonoverlap_events": len(global_events),
        "exit_reasons": exits,
        "m1_direction_accuracy": (sum(row["m1_hit"] == "True" for row in rows) / count if count else None),
        "coverage_pct": 100 * count / expected["eligible_anchors"] if expected["eligible_anchors"] else 0,
        "gross_mean": statistics.fmean(float(row["gross_return"]) for row in rows) if rows else None,
        "net_mean_base": statistics.fmean(float(row["net_base"]) for row in rows) if rows else None,
        "net_mean_stress": statistics.fmean(float(row["net_stress"]) for row in rows) if rows else None,
        "funding_cost_mean": statistics.fmean(float(row["funding_cost"]) for row in rows) if rows else None,
        "symbol_overlap_errors": symbol_overlap,
    }
    keys = ("signals", "m2_hits", "symbols", "market_time_nonoverlap_events", "exit_reasons")
    for key in keys:
        if calculated[key] != expected[key]:
            problems.append(f"summary mismatch: {key}")
    float_map = {"m2_rate": "m2_rate", "m1_direction_accuracy": "m1_direction_accuracy",
                 "coverage_pct": "coverage_pct", "gross_mean": "gross_mean",
                 "net_mean_base": "net_mean_base", "net_mean_stress": "net_mean_stress",
                 "funding_cost_mean": "funding_cost_mean"}
    for computed, reported in float_map.items():
        if abs(float(calculated[computed]) - float(expected[reported])) > 1e-12:
            problems.append(f"summary mismatch: {computed}")
    if any(a is None or b is None or abs(a - b) > 1e-12
           for a, b in zip(calculated["m2_wilson_95"], expected["m2_wilson_95"])):
        problems.append("summary mismatch: Wilson interval")
    if baseline["frozen_baseline_side"] != expected["frozen_baseline_side"]:
        problems.append("summary baseline side differs from frozen development baseline")

    symbol_rows = []
    run_by_symbol = summary["by_symbol"]
    for symbol in sorted(per_symbol):
        events = per_symbol[symbol]
        symbol_hits = sum(row["m2_hit"] == "True" for row in events)
        prior = run_by_symbol[symbol]
        symbol_rows.append({
            "symbol": symbol, "eligible_anchors": prior["eligible_anchors"],
            "raw_directional_forecasts": prior["raw_directional_forecasts"],
            "suppressed_open_position": prior["suppressed_open_position"],
            "issued_events": len(events), "m2_hits": symbol_hits,
            "m2_rate": symbol_hits / len(events) if events else None,
            "mean_net_base": statistics.fmean(float(row["net_base"]) for row in events),
            "mean_net_stress": statistics.fmean(float(row["net_stress"]) for row in events),
        })
    result = {
        "status": "PASS" if not problems and not symbol_overlap else "FAIL",
        "checks": {"ledger_rows": count, "same_symbol_overlaps": len(symbol_overlap),
                   "market_time_nonoverlap_events": len(global_events),
                   "monetary_formula_errors": sum("arithmetic mismatch" in p for p in problems),
                   "summary_crosscheck_errors": len(problems) - sum("arithmetic mismatch" in p for p in problems)},
        "recomputed": calculated, "problems": problems,
        "ledger_sha256": _sha256(ledger_path), "summary_sha256": _sha256(summary_path),
        "baseline_sha256": _sha256(baseline_path),
    }
    return result, symbol_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    result, symbol_rows = audit(args.ledger, args.summary, args.baseline)
    root = args.ledger.parent
    audit_path, symbol_path = root / "independent_ledger_audit.json", root / "by_symbol.csv"
    if audit_path.exists() or symbol_path.exists():
        raise FileExistsError("refusing to overwrite independent audit outputs")
    audit_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with symbol_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(symbol_rows[0]))
        writer.writeheader()
        writer.writerows(symbol_rows)
    print(json.dumps({"status": result["status"], "checks": result["checks"],
                      "problems": result["problems"]}, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
