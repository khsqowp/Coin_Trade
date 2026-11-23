"""CSV/JSON orchestrator for the preregistered G gate."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import NormalDist, mean, stdev
from typing import Any

from crypto import Bar
from metrics import (CORE_REQUIRED_KEYS, ROBUSTNESS_REQUIRED_KEYS, GateEvidence,
                     _issue_gate_evidence, core_gate, curve_metrics, full_gate,
                     trade_metrics)
from stats import (bonferroni, concentration_by_year, data_integrity_evidence,
                   deflated_sharpe, gate_decision, hansen_spa,
                   monte_carlo_reorder_evidence, plateau_evidence,
                   reality_check, walk_forward_evidence)

UNKNOWN = "undetermined"
TRADE_FIELDS = ("symbol", "entry_date", "exit_date", "net_return")


def _csv(path: str | Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not set(required).issubset(reader.fieldnames):
            raise ValueError(f"{path}: CSV requires columns {', '.join(required)}")
        rows = list(reader)
    return rows


def _float_rows(rows: list[dict[str, str]], field: str) -> list[float]:
    values = [float(row[field]) for row in rows]
    if any(not math.isfinite(value) for value in values):
        raise ValueError(f"{field} values must be finite")
    return values


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _daily_map(rows: list[dict[str, str]]) -> dict[date, float]:
    result: dict[date, float] = {}
    for row in rows:
        key = _day(row["date"])
        if key in result:
            raise ValueError(f"duplicate daily PnL date: {key}")
        result[key] = float(row["net_return"])
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError("daily PnL values must be finite")
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, GateEvidence):
        return {"passed": value.passed, "method": value.method,
                "sample_count": value.sample_count,
                "diagnostics": _jsonable(dict(value.diagnostics))}
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _evidence(passed: bool, method: str, n: int, diagnostics: dict[str, Any]):
    return _issue_gate_evidence(passed, method, max(1, n), diagnostics)


def _final_gate(core: dict[str, bool], evidence: dict[str, Any]) -> tuple[bool | str, bool]:
    complete = set(evidence) == set(ROBUSTNESS_REQUIRED_KEYS)
    return (full_gate(core, evidence) if complete else "incomplete"), complete


def _year_gate(daily: dict[date, float], year: int):
    values = [value for day, value in daily.items() if day.year == year]
    if not values:
        return None
    return _evidence(sum(values) >= 0, f"daily PnL calendar-year sum {year}",
                     len(values), {"year": year, "net_return": sum(values)})


def _walk_forward(trades: list[dict[str, str]]):
    ordered = sorted(trades, key=lambda row: (_day(row["entry_date"]), row["symbol"], _day(row["exit_date"])))
    if not ordered:
        return None
    folds: list[list[float]] = [[] for _ in range(5)]
    quotient, remainder = divmod(len(ordered), 5)
    offset = 0
    for index in range(5):
        size = quotient + (index < remainder)
        folds[index] = [float(row["net_return"]) for row in ordered[offset:offset + size]]
        offset += size
    return walk_forward_evidence(folds)


def _companion_trade_evidence(path: str | None, method: str):
    if path is None:
        return None
    rows = _csv(path, TRADE_FIELDS)
    returns = _float_rows(rows, "net_return")
    if method in ("cost_stress_2x", "delay_1_bar"):
        passed = sum(returns) > 0
        return _evidence(passed, method, len(rows), {"net_return": sum(returns), "trades": len(rows)})
    if method == "untouched_symbols":
        by_symbol: dict[str, float] = defaultdict(float)
        for row, ret in zip(rows, returns):
            by_symbol[row["symbol"]] += ret
        fraction = sum(value > 0 for value in by_symbol.values()) / len(by_symbol) if by_symbol else 0.0
        return _evidence(fraction >= 0.60, method, len(rows),
                         {"positive_symbol_fraction": fraction, "symbols": len(by_symbol)})
    raise ValueError(method)


def _family_tests(path: str | None, trades: list[dict[str, str]]):
    if path is None:
        return None, None
    rows = _csv(path, ("date", "candidate_id", "net_return"))
    candidates = sorted({row["candidate_id"] for row in rows})
    dates = sorted({_day(row["date"]) for row in rows})
    values = {(row["candidate_id"], _day(row["date"])): float(row["net_return"]) for row in rows}
    if len(values) != len(rows) or set(values) != {(candidate, day) for candidate in candidates for day in dates}:
        raise ValueError("family daily returns must contain one value per candidate and aligned date")
    matrix = [[values[candidate, day] for day in dates] for candidate in candidates]
    if any(not math.isfinite(value) for row in matrix for value in row):
        raise ValueError("family daily returns must be finite")
    # Count observed family trading dates spanned by each trade, inclusive.
    trade_days = sorted({day for row in rows for day in [_day(row["date"])]})
    holds = [sum(_day(t["entry_date"]) <= day <= _day(t["exit_date"]) for day in trade_days)
             for t in trades]
    block_length = float(max(1, max(holds, default=1)))
    return (reality_check(matrix, block_length=block_length),
            hansen_spa(matrix, block_length=block_length))


def _plateau(grid_path: str | None, winner_path: str | None):
    if not grid_path or not winner_path:
        return None
    rows = _csv(grid_path, ("definition_json", "net_return"))
    configs = [json.loads(row["definition_json"]) for row in rows]
    returns = [None if row["net_return"].strip() == "" else float(row["net_return"]) for row in rows]
    winner = json.loads(Path(winner_path).read_text(encoding="utf-8"))
    return plateau_evidence(winner, configs, returns)


def _integrity(args: argparse.Namespace):
    paths = (args.bars, args.cutoff_ms is not None, args.source_fingerprint,
             args.funding_complete, args.source_unchanged)
    if not all(paths):
        return None
    rows = _csv(args.bars, ("timestamp", "open", "high", "low", "close"))
    bars = [Bar(int(row["timestamp"]), float(row["open"]), float(row["high"]),
                float(row["low"]), float(row["close"]), float(row.get("volume", "0") or 0))
            for row in rows]
    return data_integrity_evidence(bars, cutoff_ms=args.cutoff_ms,
                                   source_fingerprint=args.source_fingerprint,
                                   funding_complete=args.funding_complete,
                                   source_unchanged=args.source_unchanged)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    trades = _csv(args.oos_trades, TRADE_FIELDS)
    trade_returns = _float_rows(trades, "net_return")
    daily_rows = _csv(args.daily_pnl, ("date", "net_return"))
    daily = _daily_map(daily_rows)
    daily_returns = [daily[key] for key in sorted(daily)]

    metrics = trade_metrics(trade_returns)
    curve = curve_metrics(daily_returns, {"crypto": 365, "US": 252, "KR": 252}[args.market])
    core = core_gate(metrics, daily_returns, market=args.market)
    evidences: dict[str, Any] = {
        "monte_carlo": monte_carlo_reorder_evidence(trade_returns),
        "walk_forward": _walk_forward(trades),
        "regime_2018": _year_gate(daily, 2018),
        "regime_2022": _year_gate(daily, 2022),
        "profit_concentration": None,
        "plateau": _plateau(args.grid_returns, args.winner_config),
        "cost_stress_2x": _companion_trade_evidence(args.cost_2x_trades, "cost_stress_2x"),
        "delay_1_bar": _companion_trade_evidence(args.delay_1bar_trades, "delay_1_bar"),
        "untouched_symbols": _companion_trade_evidence(args.untouched_symbol_trades, "untouched_symbols"),
        "independent_reimplementation": None,
        "data_integrity": _integrity(args),
        "random_entry": None,
        "circular_shift": None,
    }
    concentration = concentration_by_year(daily)
    share = concentration.get("max_year_share")
    if share is not None:
        evidences["profit_concentration"] = _evidence(share < 0.5, "annual profit concentration",
                                                       len(daily), concentration)
    if args.reimplementation_return is not None:
        delta = abs(args.reimplementation_return - curve.cumulative_return)
        evidences["independent_reimplementation"] = _evidence(
            delta <= 0.01, "independent cumulative net return comparison", len(trades),
            {"candidate_net_return": curve.cumulative_return,
             "reimplementation_net_return": args.reimplementation_return,
             "absolute_difference": delta})

    bonf_p = None
    bonf_detail = None
    if len(daily_returns) >= 60:
        deviation = stdev(daily_returns)
        if deviation > 0:
            z = mean(daily_returns) / (deviation / math.sqrt(len(daily_returns)))
            bonf_p = 1 - NormalDist().cdf(z)
            bonf_detail = bonferroni(bonf_p, args.frozen_test_count)
    dsr = deflated_sharpe(daily_returns, args.train_trials_count)
    candidate_metrics: dict[str, Any] = dict(core)
    candidate_metrics.update({key: (ev.passed if ev is not None else None)
                              for key, ev in evidences.items()})
    candidate_metrics.update({"bonferroni_p": bonf_p,
                              "reality_check_p": None, "spa_p": None,
                              "deflated_sharpe_probability": dsr})

    rc_detail = spa_detail = None
    try:
        rc_detail, spa_detail = _family_tests(args.family_daily_returns, trades)
    except RuntimeError as exc:
        if "arch.bootstrap" not in str(exc):
            raise
        rc_detail = spa_detail = {"unavailable": str(exc)}
    if isinstance(rc_detail, dict) and "p_value" in rc_detail:
        candidate_metrics["reality_check_p"] = rc_detail["p_value"]
        candidate_metrics["spa_p"] = spa_detail["p_value"]

    decisions = gate_decision(candidate_metrics,
                              {"train_trials": args.train_trials_count,
                               "frozen_test_candidates": args.frozen_test_count})
    statuses: dict[str, str] = {key: ("pass" if value else "fail") for key, value in core.items()}
    for key, ev in evidences.items():
        statuses[key] = ("pass" if ev.passed else "fail") if ev is not None else UNKNOWN
    statuses["bonferroni"] = decisions["bonferroni"]
    statuses["reality_check"] = decisions["reality_check"]
    statuses["spa"] = decisions["spa"]
    statuses["deflated_sharpe"] = decisions["deflated_sharpe"]

    # ROBUSTNESS_REQUIRED_KEYS are issued only where an actual measurement exists.
    robust_evidence = {key: ev for key, ev in evidences.items() if ev is not None}
    statistical_values = {
        "bonferroni": (bonf_detail, bonf_p),
        "reality_check": (rc_detail, candidate_metrics["reality_check_p"]),
        "spa": (spa_detail, candidate_metrics["spa_p"]),
        "deflated_sharpe": (dsr, dsr),
    }
    for key, (detail, value) in statistical_values.items():
        if value is not None and not (isinstance(detail, dict) and "unavailable" in detail):
            passed = decisions[key] == "pass"
            robust_evidence[key] = _evidence(passed, key, max(1, len(daily_returns)),
                                             {"raw_value": value, "decision": decisions[key]})
    final, complete = _final_gate(core, robust_evidence)

    sources = {key: ("--oos-trades" if key in ("monte_carlo", "walk_forward") else
                     "--daily-pnl" if key.startswith("regime_") or key == "profit_concentration" else
                     "--family-daily-returns" if key in ("reality_check", "spa") else
                     "--daily-pnl + --frozen-test-count" if key == "bonferroni" else
                     "--daily-pnl + --train-trials-count" if key == "deflated_sharpe" else
                     "--grid-returns + --winner-config" if key == "plateau" else
                     "--cost-2x-trades" if key == "cost_stress_2x" else
                     "--delay-1bar-trades" if key == "delay_1_bar" else
                     "--untouched-symbol-trades" if key == "untouched_symbols" else
                     "--reimplementation-return" if key == "independent_reimplementation" else
                     "--bars and integrity flags" if key == "data_integrity" else
                     "permanently outside this CLI; simulator callback required"
                     if key in ("random_entry", "circular_shift") else "unavailable")
               for key in statuses}
    unknown_reasons = {key: ("simulator callback is required" if key in ("random_entry", "circular_shift") else
                             "required companion input was not supplied or evidence could not be measured")
                       for key, status in statuses.items() if status == UNKNOWN}
    result = {
        "market": args.market,
        "counts": {"oos_trades": len(trades), "daily_observations": len(daily_returns),
                   "train_trials": args.train_trials_count, "frozen_test_candidates": args.frozen_test_count},
        "metrics": {"trade": asdict(metrics), "curve": asdict(curve)},
        "core": statuses_for_core(core),
        "gates": statuses,
        "evidence": {key: _jsonable(ev) if ev is not None else None for key, ev in robust_evidence.items()},
        "statistical_details": {"bonferroni": bonf_detail, "bonferroni_raw_p": bonf_p,
                                "p_value_method": "one-sided z approximation to one-sample t-test (n >= 60)",
                                "reality_check": rc_detail, "spa": spa_detail,
                                "deflated_sharpe_probability": dsr},
        "sources": sources,
        "unknown_reasons": unknown_reasons,
        "full_gate_complete": complete,
        "final": final,
    }
    return result


def statuses_for_core(core: dict[str, bool]) -> dict[str, str]:
    return {key: "pass" if value else "fail" for key, value in core.items()}


def _markdown(result: dict[str, Any]) -> str:
    lines = ["# G 게이트 판정", "", f"- 시장: {result['market']}",
             f"- 최종: {result['final']}", "", "## CORE 8항목", "",
             "| 항목 | 판정 |", "|---|---|"]
    lines.extend(f"| {key} | {value.upper()} |" for key, value in result["core"].items())
    lines.extend(["", "## ROBUST 및 통계 항목", "", "| 항목 | 판정 | 입력 |", "|---|---|---|"])
    lines.extend(f"| {key} | {value.upper()} | {result['sources'][key]} |" for key, value in result["gates"].items())
    if result["unknown_reasons"]:
        lines.extend(["", "## UNKNOWN 사유", ""])
        lines.extend(f"- {key}: {reason}" for key, reason in result["unknown_reasons"].items())
    lines.append("")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oos-trades", required=True)
    parser.add_argument("--daily-pnl", required=True)
    parser.add_argument("--market", required=True, choices=("crypto", "US", "KR"))
    parser.add_argument("--train-trials-count", required=True, type=int)
    parser.add_argument("--frozen-test-count", required=True, type=int)
    parser.add_argument("--grid-returns")
    parser.add_argument("--winner-config")
    parser.add_argument("--family-daily-returns")
    parser.add_argument("--cost-2x-trades")
    parser.add_argument("--delay-1bar-trades")
    parser.add_argument("--untouched-symbol-trades")
    parser.add_argument("--reimplementation-return", type=float)
    parser.add_argument("--bars")
    parser.add_argument("--cutoff-ms", type=int)
    parser.add_argument("--source-fingerprint")
    parser.add_argument("--funding-complete", action="store_true")
    parser.add_argument("--source-unchanged", action="store_true")
    parser.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.train_trials_count < 1 or args.frozen_test_count < 1:
        parser.error("trial and frozen TEST counts must be positive")
    if bool(args.grid_returns) != bool(args.winner_config):
        parser.error("--grid-returns and --winner-config must be supplied together")
    result = evaluate(args)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_jsonable(result), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                      encoding="utf-8")
    output.with_suffix(".md").write_text(_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
