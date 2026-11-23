#!/usr/bin/env python3
"""Summarize the shared TRAIN_TRIALS.csv ledger without running searches."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


LEDGER = Path(__file__).with_name("TRAIN_TRIALS.csv")


def _metric(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _number(metric: dict[str, Any]) -> float | None:
    for key in ("expectancy_net_bps", "expectancy_bps", "expectancy"):
        try:
            value = float(metric[key])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(value):
            return value
    return None


def summarize(path: Path, round_filter: str | None = None,
              market_filter: str | None = None) -> dict[tuple[str, str], list[dict[str, Any]]]:
    csv.field_size_limit(__import__("sys").maxsize)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            round_name = (row.get("round") or "(missing)").strip() or "(missing)"
            market = (row.get("market_group") or row.get("market") or "(missing)").strip() or "(missing)"
            if round_filter and round_name != round_filter:
                continue
            if market_filter and market != market_filter:
                continue
            metric = _metric(row.get("metric"))
            status = str(metric.get("status") or "(missing)")
            expectancy = _number(metric)
            groups[(round_name, market)].append({
                "trial_id": row.get("trial_id") or "(missing)",
                "definition": row.get("definition") or "",
                "trades": metric.get("trades"),
                "expectancy": expectancy,
                "status": status,
                "no_metric": expectancy is None,
            })
    return groups


def _label(row: dict[str, Any]) -> str:
    try:
        definition = json.loads(row["definition"])
    except (json.JSONDecodeError, TypeError):
        definition = None
    if isinstance(definition, dict):
        strategy = definition.get("strategy") or definition.get("candidate") or definition.get("definition")
        if strategy:
            return f"{strategy} ({row['trial_id']})"
    return row["trial_id"]


def print_summary(groups: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
    if not groups:
        print("조건에 맞는 시도가 없습니다.")
        return
    for (round_name, market), rows in sorted(groups.items()):
        positive = sum(row["expectancy"] is not None and row["expectancy"] > 0 for row in rows)
        statuses = Counter(row["status"] for row in rows)
        no_metric = sum(row["no_metric"] for row in rows)
        if no_metric:
            statuses["no_metric"] += no_metric
        print(f"\n[{round_name} / {market}] 시도 {len(rows)} | 양수 기대값 {positive} | 상태 {dict(sorted(statuses.items()))}")
        print("전략/설정 | 거래 수 | 기대값(bp) | 상태")
        ranked = sorted((row for row in rows if row["expectancy"] is not None),
                        key=lambda row: row["expectancy"], reverse=True)[:5]
        for row in ranked:
            trades = row["trades"] if row["trades"] is not None else "-"
            print(f"{_label(row)} | {trades} | {row['expectancy']:.4f} | {row['status']}")
        if not ranked:
            print("(기대값 기록 없음)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=LEDGER, help="요약할 TRAIN_TRIALS.csv 경로")
    parser.add_argument("--round", dest="round_filter", help="라운드 필터")
    parser.add_argument("--market", dest="market_filter", help="시장 필터 (예: crypto, US, KR)")
    args = parser.parse_args()
    print_summary(summarize(args.csv, args.round_filter, args.market_filter))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
