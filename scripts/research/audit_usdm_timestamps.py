"""Read-only raw-CSV timestamp alignment audit for one USD-M archive cohort."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import zipfile


def _read_csv(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV member in {path.name}")
        with archive.open(members[0]) as binary:
            with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
                return list(csv.DictReader(text))


def audit_cohort(audit: dict, coverage: dict, root: Path, cohort: str) -> dict:
    symbols = coverage.get("cohorts_by_exact_run", {}).get(cohort)
    if not isinstance(symbols, list) or not symbols:
        raise ValueError(f"coverage summary has no symbols for cohort {cohort}")
    try:
        start, end = cohort.split("..", 1)
    except ValueError as exc:
        raise ValueError("cohort must be START_MONTH..END_MONTH") from exc
    months = []
    year, number = map(int, start.split("-"))
    last_year, last_number = map(int, end.split("-"))
    while (year, number) <= (last_year, last_number):
        months.append(f"{year:04d}-{number:02d}")
        year, number = ((year + 1, 1) if number == 12 else (year, number + 1))

    rows = audit.get("archive_rows", [])
    row_map = {(r.get("symbol"), r.get("month"), r.get("kind")): r for r in rows if isinstance(r, dict)}
    checked = missing = malformed = candle_mark_mismatches = duplicate_times = funding_bad = 0
    mark_hours_outside_kline_window = 0
    examples = []
    for symbol in symbols:
        for month in months:
            monthly_rows = {kind: row_map.get((symbol, month, kind))
                            for kind in ("klines_1h", "mark_price_1h", "funding")}
            if any(row is None for row in monthly_rows.values()):
                missing += 1
                continue
            try:
                kline = _read_csv(root / "klines_1h" / symbol / f"{symbol}-1h-{month}.zip")
                mark = _read_csv(root / "mark_price_1h" / symbol / f"{symbol}-1h-{month}.zip")
                funding = _read_csv(root / "funding" / symbol / f"{symbol}-fundingRate-{month}.zip")
                k_times = [int(row["open_time"]) for row in kline]
                m_times = [int(row["open_time"]) for row in mark]
                f_times = [int(row["calc_time"]) for row in funding]
                intervals = [int(row["funding_interval_hours"]) for row in funding]
                rates = [float(row["last_funding_rate"]) for row in funding]
            except (OSError, ValueError, KeyError, zipfile.BadZipFile, csv.Error):
                malformed += 1
                continue
            checked += 1
            errors = []
            expected_k_hours = ((int(monthly_rows["klines_1h"]["last_ms"])
                                  - int(monthly_rows["klines_1h"]["first_ms"])) // 3_600_000 + 1)
            expected_m_hours = ((int(monthly_rows["mark_price_1h"]["last_ms"])
                                  - int(monthly_rows["mark_price_1h"]["first_ms"])) // 3_600_000 + 1)
            if (not k_times or len(k_times) != expected_k_hours or len(set(k_times)) != expected_k_hours
                    or any(right - left != 3_600_000 for left, right in zip(k_times, k_times[1:]))
                    or k_times[0] != int(monthly_rows["klines_1h"]["first_ms"])
                    or k_times[-1] != int(monthly_rows["klines_1h"]["last_ms"])):
                duplicate_times += 1
                errors.append("kline archive has missing/duplicate hours or endpoint mismatch")
            if (not m_times or len(m_times) != expected_m_hours or len(set(m_times)) != expected_m_hours
                    or any(right - left != 3_600_000 for left, right in zip(m_times, m_times[1:]))
                    or m_times[0] != int(monthly_rows["mark_price_1h"]["first_ms"])
                    or m_times[-1] != int(monthly_rows["mark_price_1h"]["last_ms"])):
                duplicate_times += 1
                errors.append("mark archive has missing/duplicate hours or endpoint mismatch")
            k_set, m_set = set(k_times), set(m_times)
            missing_mark = k_set - m_set
            unexpected_inside = {value for value in m_set - k_set
                                 if k_times and k_times[0] <= value <= k_times[-1]}
            if missing_mark or unexpected_inside:
                candle_mark_mismatches += 1
                errors.append("mark data missing or adds timestamps inside the tradable kline window")
            mark_hours_outside_kline_window += sum(
                value < k_times[0] or value > k_times[-1] for value in m_set - k_set
            ) if k_times else 0
            if len(f_times) != len(set(f_times)) or f_times != sorted(f_times):
                funding_bad += 1
                errors.append("funding timestamps duplicated or unordered")
            if not f_times or len(intervals) != len(f_times) or any(v <= 0 for v in intervals):
                funding_bad += 1
                errors.append("funding interval missing or non-positive")
            year, number = map(int, month.split("-"))
            month_start = int(datetime(year, number, 1, tzinfo=timezone.utc).timestamp() * 1000)
            next_year, next_number = ((year + 1, 1) if number == 12 else (year, number + 1))
            month_end = int(datetime(next_year, next_number, 1, tzinfo=timezone.utc).timestamp() * 1000)
            if f_times and (f_times[0] < month_start or f_times[-1] >= month_end):
                funding_bad += 1
                errors.append("funding timestamp outside archive month")
            # Funding intervals may change by symbol and over time. Exchange
            # timestamps jitter by milliseconds, so accept either adjacent row's
            # declared interval with a 1-second tolerance.
            if any(not any(abs((right - left) - hours * 60 * 60 * 1000) <= 1000
                           for hours in (intervals[index], intervals[index + 1]))
                   for index, (left, right) in enumerate(zip(f_times, f_times[1:]))):
                funding_bad += 1
                errors.append("funding timestamps disagree with adjacent declared intervals")
            if any(not math.isfinite(rate) for rate in rates):
                funding_bad += 1
                errors.append("non-finite funding rate")
            if errors and len(examples) < 20:
                examples.append({"symbol": symbol, "month": month, "errors": errors})

    return {"cohort": cohort, "symbols": len(symbols), "months": len(months),
            "symbol_months_expected": len(symbols) * len(months), "checked": checked,
            "missing": missing, "malformed": malformed,
            "candle_mark_timestamp_mismatches": candle_mark_mismatches,
            "mark_hours_outside_kline_window": mark_hours_outside_kline_window,
            "duplicate_or_incomplete_hour_sets": duplicate_times,
            "funding_integrity_failures": funding_bad, "failure_examples": examples,
            "status": "PASS" if checked == len(symbols) * len(months) and not any(
                (missing, malformed, candle_mark_mismatches, duplicate_times, funding_bad)) else "FAIL",
            "limitations": ["raw archive timestamps only; does not validate price accuracy or strategy fills",
                            "funding timestamps are checked against the interval carried in adjacent archive rows"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", type=Path)
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("archive_root", type=Path)
    parser.add_argument("--cohort", required=True, help="exact key from coverage JSON, e.g. 2023-03..2026-05")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
        coverage = json.loads(args.coverage_json.read_text(encoding="utf-8"))
        result = audit_cohort(audit, coverage, args.archive_root, args.cohort)
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
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
