#!/usr/bin/env python3
"""Frozen robustness diagnostics for the exposed stock momentum v2 run."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.common_stock_momentum_probe import (  # noqa: E402
    COSTS, INVERSE_SYMBOLS, load_panel, simulate,
)

PREREG = ROOT / "docs/research/inventory/PREREG_STOCK_MOMENTUM_ROBUSTNESS_20261120.md"
SOURCE_RUN = ROOT / "docs/research/inventory/runs/stock_common_momentum_20261120_inverse_excluded"
SOURCE_SUMMARY = SOURCE_RUN / "summary.json"
TRAIN_SESSIONS = 504
WARMUP_SESSIONS = 200
BOOTSTRAP_BLOCK = 20
PATHS = 1000
SEED = 20261120


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def drawdown(nav: np.ndarray) -> float:
    peak = np.maximum.accumulate(np.r_[1.0, nav])
    full = np.r_[1.0, nav]
    return float(np.max(1.0 - full / peak))


def summarize_path(returns: np.ndarray) -> tuple[float, float, float]:
    nav = np.cumprod(1.0 + returns)
    terminal = float(nav[-1])
    years = len(returns) / 252.0
    cagr = terminal ** (1.0 / years) - 1.0 if terminal > 0 and years > 0 else -1.0
    return drawdown(nav), terminal - 1.0, cagr


def path_resampling() -> list[dict]:
    frame = pd.read_csv(SOURCE_RUN / "daily_nav.csv")
    rows = []
    for cell, group in frame.groupby("cell", sort=True):
        if "|mom" not in cell:
            continue
        returns = group["return"].dropna().to_numpy(float)
        if len(returns) < BOOTSTRAP_BLOCK or not np.isfinite(returns).all() or (returns <= -1).any():
            raise ValueError(f"invalid or too-short daily return path: {cell}")
        rng = np.random.default_rng(SEED + sum(cell.encode("utf-8")))
        shuffled = np.empty(PATHS)
        shuffled_cagr = np.empty(PATHS)
        for i in range(PATHS):
            permuted = rng.permutation(returns)
            shuffled[i], _, shuffled_cagr[i] = summarize_path(permuted)
        boot_mdd = np.empty(PATHS)
        boot_terminal = np.empty(PATHS)
        boot_cagr = np.empty(PATHS)
        starts_max = len(returns) - BOOTSTRAP_BLOCK + 1
        blocks_needed = math.ceil(len(returns) / BOOTSTRAP_BLOCK)
        for i in range(PATHS):
            starts = rng.integers(0, starts_max, size=blocks_needed)
            sampled = np.concatenate([returns[s:s + BOOTSTRAP_BLOCK] for s in starts])[:len(returns)]
            boot_mdd[i], boot_terminal[i], boot_cagr[i] = summarize_path(sampled)
        rows.append({
            "cell": cell, "observations": len(returns), "seed": SEED,
            "permutation_paths": PATHS, "permutation_mdd_median": float(np.median(shuffled)),
            "permutation_mdd_p95": float(np.quantile(shuffled, .95)),
            "permutation_cagr_median": float(np.median(shuffled_cagr)),
            "permutation_cagr_p05": float(np.quantile(shuffled_cagr, .05)),
            "block_size": BOOTSTRAP_BLOCK, "block_paths": PATHS,
            "block_mdd_median": float(np.median(boot_mdd)),
            "block_mdd_p95": float(np.quantile(boot_mdd, .95)),
            "block_terminal_return_median": float(np.median(boot_terminal)),
            "block_terminal_return_p05": float(np.quantile(boot_terminal, .05)),
            "block_cagr_median": float(np.median(boot_cagr)),
            "block_cagr_p05": float(np.quantile(boot_cagr, .05)),
        })
    if len(rows) != 12:
        raise ValueError(f"expected 12 momentum portfolio/cost cells, got {len(rows)}")
    return rows


def parameter_sensitivity() -> list[dict]:
    rows = []
    cache = ROOT / ".kis-cache-local"
    for market, lookbacks, cadences in (("KR", (48, 60, 72), ("monthly",)),
                                        ("US", (101, 126, 151), ("daily", "monthly"))):
        symbols, dates, close, _ = load_panel(cache, market, INVERSE_SYMBOLS[market])
        for cadence in cadences:
            for lookback in lookbacks:
                for gate in (False, True):
                    for cost_name, cost in COSTS[market].items():
                        metric, _, _, _ = simulate(symbols, dates, close, market, lookback,
                                                   cadence, gate, cost)
                        rows.append({"market": market, "cadence": cadence,
                                     "lookback": lookback, "sma200_gate": gate,
                                     "cost_case": cost_name, **metric})
    if len(rows) != 36:
        raise ValueError(f"expected 36 preregistered parameter cells, got {len(rows)}")
    return rows


def month_boundaries(dates: pd.DatetimeIndex, minimum: int) -> list[int]:
    periods = dates.tz_localize(None).to_period("M") if dates.tz is not None else dates.to_period("M")
    first = [i for i in range(1, len(dates)) if periods[i] != periods[i - 1] and i >= minimum]
    return first


def walk_forward() -> tuple[list[dict], list[dict]]:
    rows = []
    daily_rows = []
    specs = (("KR", (48, 60, 72), ("monthly",)),
             ("US", (101, 126, 151), ("daily", "monthly")))
    for market, lookbacks, cadences in specs:
        symbols, dates, close, _ = load_panel(ROOT / ".kis-cache-local", market,
                                              INVERSE_SYMBOLS[market])
        for cadence in cadences:
            # Advance six calendar months after each test. This prevents
            # overlapping pseudo-OOS windows while keeping month-start fills.
            boundaries = month_boundaries(dates, WARMUP_SESSIONS + TRAIN_SESSIONS)[::6]
            folds = []
            combined_returns: dict[str, list[float]] = {name: [] for name in COSTS[market]}
            combined_return_dates: dict[str, list[pd.Timestamp]] = {name: [] for name in COSTS[market]}
            combined_start_date: str | None = None
            combined_round_trips: dict[str, int] = {name: 0 for name in COSTS[market]}
            for fold_index, start in enumerate(boundaries, start=1):
                target_period = (dates[start].tz_localize(None) if dates.tz is not None else dates[start]).to_period("M") + 6
                end_candidates = [i for i in range(start + 1, len(dates))
                                  if (dates[i].tz_localize(None) if dates.tz is not None else dates[i]).to_period("M") >= target_period]
                if not end_candidates:
                    continue
                end = end_candidates[0]
                train_start = start - TRAIN_SESSIONS
                input_start = train_start - WARMUP_SESSIONS
                train_dates = dates[input_start:start]
                train_close = close[input_start:start]
                candidates = []
                for lookback in lookbacks:
                    for gate in (False, True):
                        metric, _, _, _ = simulate(symbols, train_dates, train_close, market,
                                                   lookback, cadence, gate, COSTS[market]["base"],
                                                   start_index=WARMUP_SESSIONS)
                        candidates.append((metric["sharpe"], metric["cagr"], lookback,
                                           not gate, gate))
                chosen = max(candidates, key=lambda x: (x[0], x[1], -x[2], x[3]))
                lookback, gate = chosen[2], chosen[4]
                test_start = start - WARMUP_SESSIONS
                test_dates = dates[test_start:end]
                test_close = close[test_start:end]
                for cost_name, cost in COSTS[market].items():
                    metric, daily, _, round_trips = simulate(
                        symbols, test_dates, test_close, market, lookback, cadence,
                        gate, cost, start_index=WARMUP_SESSIONS)
                    for point in daily:
                        daily_rows.append({"market": market, "cadence": cadence,
                                           "fold": fold_index, "cost_case": cost_name,
                                           "selected_lookback": lookback,
                                           "selected_sma200_gate": gate, **point})
                    if combined_start_date is None:
                        combined_start_date = daily[0]["date"][:10]
                    for point in daily:
                        if point["return"]:
                            combined_returns[cost_name].append(float(point["return"]))
                            combined_return_dates[cost_name].append(pd.Timestamp(point["date"]))
                    combined_round_trips[cost_name] += len(round_trips)
                    folds.append({"market": market, "cadence": cadence,
                                  "fold": fold_index,
                                  "train_start": dates[train_start].date().isoformat(),
                                  "train_end": dates[start - 1].date().isoformat(),
                                  "test_start": dates[start].date().isoformat(),
                                  "test_end": dates[end - 1].date().isoformat(),
                                  "selected_lookback": lookback, "selected_sma200_gate": gate,
                                  "training_sharpe_base": chosen[0], "cost_case": cost_name,
                                  "test_cagr": metric["cagr"], "test_mdd": metric["mdd"],
                                  "test_sharpe": metric["sharpe"],
                                  "test_round_trips": len(round_trips),
                                  "test_sessions": len(test_dates) - WARMUP_SESSIONS,
                                  "interpretation": "pseudo-OOS only; cache and family previously exposed"})
            rows.extend(folds)
            for cost_name in COSTS[market]:
                returns = np.asarray(combined_returns[cost_name], dtype=float)
                if not len(returns):
                    continue
                nav = np.cumprod(1.0 + returns)
                nav_with_initial = np.r_[1.0, nav]
                return_dates = combined_return_dates[cost_name]
                first_date = pd.Timestamp(combined_start_date)
                last_date = return_dates[-1]
                last_date_naive = last_date.tz_localize(None) if last_date.tzinfo else last_date
                years = (last_date_naive - first_date).total_seconds() / (365.2425 * 86400)
                standard_deviation = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
                rows.append({"market": market, "cadence": cadence, "fold": "COMBINED",
                             "train_start": "rolling per fold", "train_end": "rolling per fold",
                             "test_start": return_dates[0].date().isoformat(),
                             "test_end": last_date.date().isoformat(),
                             "selected_lookback": "selected per fold",
                             "selected_sma200_gate": "selected per fold",
                             "training_sharpe_base": "not applicable", "cost_case": cost_name,
                             "test_cagr": float(nav[-1] ** (1 / years) - 1) if years > 0 else math.nan,
                             "test_mdd": drawdown(nav),
                             "test_sharpe": float(np.mean(returns) / standard_deviation * math.sqrt(252)) if standard_deviation else 0.0,
                             "test_round_trips": combined_round_trips[cost_name],
                             "test_sessions": len(returns),
                             "interpretation": "combined non-overlapping pseudo-OOS slices; raw round trips are not proven independent"})
    if not rows:
        raise ValueError("no complete walk-forward folds met the frozen boundaries")
    return rows, daily_rows


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, sensitivity: list[dict], wf: list[dict], mc: list[dict]) -> None:
    sensitivity_frame = pd.DataFrame(sensitivity)
    wf_frame = pd.DataFrame(wf)
    mc_frame = pd.DataFrame(mc)
    lines = [
        "# Stock momentum robustness diagnostics — exploratory only", "",
        "This is a post-exposure diagnostic on a current-survivor cache. It is not",
        "untouched OOS evidence, a live readiness assessment, or a strategy approval.",
        "The initial overlapping-window attempt is retained separately and excluded;",
        "the canonical analysis is the non-overlapping v5 run.", "",
        "## Parameter neighborhood", "",
        "Frozen lookback neighbors were KR 48/60/72 and US 101/126/151, with",
        "the predeclared cadence, SMA200 on/off, and base/stress costs.", "",
        "| Market | Cadence | Cells | CAGR min / median / max | MDD min / max | All numeric hard gates |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for (market, cadence), group in sensitivity_frame.groupby(["market", "cadence"], sort=True):
        hard = ((group.cagr >= .20) & (group.mdd <= .30) & (group.sharpe >= 1.0)).sum()
        lines.append(f"| {market} | {cadence} | {len(group)} | "
                     f"{group.cagr.min():.1%} / {group.cagr.median():.1%} / {group.cagr.max():.1%} | "
                     f"{group.mdd.min():.1%} / {group.mdd.max():.1%} | {hard}/{len(group)} |")
    lines.extend(["", "All 36 cells fail the MDD <=30% gate; no parameter plateau meets the",
                  "numeric stock thresholds. Each cell remains exposed exploratory history.",
                  "", "## Non-overlapping walk-forward pseudo-OOS", "",
                  "Each fold trains on 504 sessions, chooses lookback/gate by training",
                  "Sharpe, then tests on the next six calendar months from fresh cash.",
                  "Tests advance by six months and do not overlap. The input and strategy",
                  "family were already inspected, so these are pseudo-OOS only.", "",
                  "| Market | Cadence | Fold tests | Combined cost | CAGR | MDD | Sharpe | Raw round trips | Sessions |",
                  "|---|---|---:|---|---:|---:|---:|---:|---:|"])
    combined = wf_frame[wf_frame.fold.astype(str) == "COMBINED"]
    fold_counts = wf_frame[wf_frame.fold.astype(str) != "COMBINED"].groupby(["market", "cadence"]).fold.nunique()
    for _, row in combined.sort_values(["market", "cadence", "cost_case"]).iterrows():
        nfolds = int(fold_counts.get((row.market, row.cadence), 0))
        lines.append(f"| {row.market} | {row.cadence} | {nfolds} | {row.cost_case} | "
                     f"{row.test_cagr:.1%} | {row.test_mdd:.1%} | {row.test_sharpe:.3f} | "
                     f"{int(row.test_round_trips)} | {int(row.test_sessions)} |")
    lines.extend(["", "Raw round trips are counts, not proof of independent trades. No combined",
                  "walk-forward cell establishes the required 200 independent OOS trades",
                  "together with CAGR/MDD/Sharpe gates.", "", "## Path resampling", "",
                  "Daily portfolio returns were permuted 1,000 times and moving-block",
                  "bootstrapped 1,000 times with 20-session blocks. Permutation is not",
                  "trade-level Monte Carlo because the strategy has overlapping holdings.", "",
                  "| Market | Worst cell permutation MDD p95 | Worst cell block MDD p95 | Lowest block CAGR p05 |",
                  "|---|---:|---:|---:|"])
    for market, group in mc_frame.groupby(mc_frame.cell.str.split("|").str[0], sort=True):
        lines.append(f"| {market} | {group.permutation_mdd_p95.max():.1%} | "
                     f"{group.block_mdd_p95.max():.1%} | {group.block_cagr_p05.min():.1%} |")
    lines.extend(["", "## Decision", "",
                  "**No strategy passes.** The parameter neighborhood has zero numeric-gate",
                  "passes, all sampled paths are high drawdown, and the walk-forward slices",
                  "are too short and too exposed to establish independent OOS validation.",
                  "The current cache still lacks point-in-time constituents and certified",
                  "corporate-action/price provenance. Do not combine these candidates in a",
                  "Phase 9 portfolio; none is an individually validated core strategy.", "",
                  "Reproduction command:", "", "```bash",
                  "PYTHONPATH=. /opt/anaconda3/bin/python3 scripts/research/stock_momentum_robustness.py \\",
                  "  --output-dir docs/research/inventory/runs/stock_momentum_robustness_20261120_v5",
                  "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    source_summary = json.loads(SOURCE_SUMMARY.read_text(encoding="utf-8"))
    current_inputs = {}
    for market in ("KR", "US"):
        _, _, _, files = load_panel(ROOT / ".kis-cache-local", market, INVERSE_SYMBOLS[market])
        current_inputs[market] = files
    current_fingerprint = hashlib.sha256("\n".join(
        f"{market}|{entry['path']}|{entry['sha256']}"
        for market in sorted(current_inputs) for entry in current_inputs[market]
    ).encode()).hexdigest()
    if current_fingerprint != source_summary["input_fingerprint_sha256"]:
        raise SystemExit("source cache fingerprint differs from the canonical v2 replay; refusing robustness run")
    sensitivity = parameter_sensitivity()
    wf, wf_daily = walk_forward()
    monte_carlo = path_resampling()
    write_csv(out / "parameter_sensitivity.csv", sensitivity)
    write_csv(out / "walk_forward.csv", wf)
    write_csv(out / "walk_forward_daily.csv", wf_daily)
    write_csv(out / "path_resampling.csv", monte_carlo)
    write_report(out / "report.md", sensitivity, wf, monte_carlo)
    summary = {
        "schema_version": 1, "status": "completed_exploratory_robustness_diagnostic",
        "started_at": started_at,
        "preregistration": str(PREREG.relative_to(ROOT)),
        "preregistration_sha256": sha256(PREREG),
        "code": str(Path(__file__).relative_to(ROOT)), "code_sha256": sha256(Path(__file__)),
        "source_run_id": source_summary["run_id"],
        "source_run_summary_sha256": sha256(SOURCE_SUMMARY),
        "input_fingerprint_sha256": current_fingerprint,
        "seed": SEED, "paths_per_method_per_cell": PATHS,
        "parameter_cells": len(sensitivity),
        "walk_forward_fold_cost_cells": sum(row["fold"] != "COMBINED" for row in wf),
        "walk_forward_combined_cost_cells": sum(row["fold"] == "COMBINED" for row in wf),
        "walk_forward_daily_rows": len(wf_daily),
        "path_resampling_cells": len(monte_carlo),
        "walk_forward_train_sessions": TRAIN_SESSIONS,
        "walk_forward_test_horizon_calendar_months": 6,
        "path_block_sessions": BOOTSTRAP_BLOCK,
        "limitations": ["source cache and strategy family already exposed; no untouched OOS",
                        "current-survivor universe and corporate-action provenance unresolved",
                        "daily return path permutation is not trade-level permutation",
                        "legacy fee/slippage scenarios do not establish account-specific fills"],
        "supersedes_attempts": [
            "stock_momentum_robustness_20261120: initial diagnostic emitted overlapping monthly-start six-month test windows; excluded from canonical inference",
            "stock_momentum_robustness_20261120_v2: correct non-overlapping folds but omitted combined walk-forward path metrics; superseded by v3",
            "stock_momentum_robustness_20261120_v3: combined paths were sound but fold identifiers advanced per cost row; v4 corrects the fold labels for auditable counts",
            "stock_momentum_robustness_20261120_v4: no per-session selected-rule OOS NAV ledger; v5 adds that reproducibility artifact",
        ],
    }
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
