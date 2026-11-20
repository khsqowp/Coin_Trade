"""Summarize validated continuous USD-M archive coverage from audit metadata."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


REQUIRED_KINDS = {"klines_1h", "mark_price_1h", "funding"}


def _next_month(month: str) -> str:
    year, number = map(int, month.split("-"))
    return f"{year + (number == 12):04d}-{1 if number == 12 else number + 1:02d}"


def _longest_consecutive(months: list[str]) -> list[str]:
    runs: list[list[str]] = []
    current: list[str] = []
    for month in sorted(set(months)):
        if current and month != _next_month(current[-1]):
            runs.append(current)
            current = []
        current.append(month)
    if current:
        runs.append(current)
    return max(runs, key=len, default=[])


def summarize(audit: dict) -> dict:
    rows = audit.get("archive_rows")
    if not isinstance(rows, list):
        raise ValueError("audit metadata must contain archive_rows list")
    by_symbol_month: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    kind_months: dict[str, list[str]] = defaultdict(list)
    malformed = 0
    for row in rows:
        if not isinstance(row, dict):
            malformed += 1
            continue
        kind, symbol, month = row.get("kind"), row.get("symbol"), row.get("month")
        if not isinstance(kind, str) or not isinstance(symbol, str) or not isinstance(month, str):
            malformed += 1
            continue
        kind_months[kind].append(month)
        if kind in REQUIRED_KINDS:
            by_symbol_month[symbol][month][kind] = row

    per_symbol = {}
    for symbol, month_rows in sorted(by_symbol_month.items()):
        good = []
        for month, kinds in month_rows.items():
            if not REQUIRED_KINDS.issubset(kinds):
                continue
            if any(kinds[k].get("gap_count", 0) != 0 or kinds[k].get("missing_hours", 0) != 0
                   for k in REQUIRED_KINDS):
                continue
            if kinds["funding"].get("funding_interval_disagreement_count", 0) != 0:
                continue
            good.append(month)
        run = _longest_consecutive(good)
        per_symbol[symbol] = {"clean_consecutive_months": len(run),
                              "start_month": run[0] if run else None,
                              "end_month": run[-1] if run else None}

    intersections: dict[str, list[str]] = defaultdict(list)
    for symbol, result in per_symbol.items():
        if result["start_month"] and result["end_month"]:
            intersections[result["start_month"] + ".." + result["end_month"]].append(symbol)
    cohort_counts = defaultdict(int)
    for result in per_symbol.values():
        if result["clean_consecutive_months"]:
            cohort_counts[str(result["clean_consecutive_months"])] += 1

    return {
        "required_kinds": sorted(REQUIRED_KINDS),
        "archive_month_ranges": {kind: [min(months), max(months)]
                                 for kind, months in sorted(kind_months.items()) if months},
        "symbols_with_valid_rows": len(per_symbol),
        "symbols_with_at_least_36_clean_consecutive_months": sum(
            item["clean_consecutive_months"] >= 36 for item in per_symbol.values()),
        "clean_month_run_distribution": dict(sorted(cohort_counts.items(), key=lambda p: int(p[0]))),
        "cohorts_by_exact_run": {key: sorted(value) for key, value in sorted(intersections.items())},
        "symbols": per_symbol,
        "funding_interval_disagreement_archives": audit.get(
            "funding_archives_with_interval_metadata_disagreements"),
        "unresolved_mark_gap_archives": audit.get("unresolved_mark_gap_archives"),
        "malformed_archive_rows": malformed,
        "limitations": ["metadata audit only; does not hash/reopen source archives",
                        "continuous monthly status does not prove intra-month timestamps are causally usable",
                        "current-symbol cohort may contain survivorship bias"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", type=Path, help="existing archive audit JSON; read-only")
    parser.add_argument("--output", type=Path, help="optional destination for the JSON summary")
    args = parser.parse_args()
    try:
        audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
        result = summarize(audit)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        try:
            args.output.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"error": f"cannot write summary: {exc}"}, ensure_ascii=False))
            return 2
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
