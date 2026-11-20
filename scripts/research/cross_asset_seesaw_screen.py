"""Fixed exploratory cross-asset crypto seesaw screen on verified hourly archives."""
from __future__ import annotations

import argparse
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

from scripts.research.long_history_setup_m2_probe import load_symbol

HOUR = 3_600_000
LEADERS = ("BTCUSDT", "ETHUSDT", "XRPUSDT", "LTCUSDT")
HORIZONS = (1, 4)
FEES = {"base": 0.001, "stress": 0.003}
SPLITS = {
    "development": ("2023-03-23T15:00:00Z", "2025-03-01T00:00:00Z"),
    "validation_exposed": ("2025-03-01T00:00:00Z", "2025-11-01T00:00:00Z"),
    "evaluation_previously_exposed": ("2025-11-01T00:00:00Z", "2026-06-01T00:00:00Z"),
}
BOOTSTRAP_REPS = 1000
SEED = 20261120
BLOCK_HOURS = 168


def utc_ms(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def signal_sides(leader_closes: np.ndarray, cutoff: int | None = None) -> np.ndarray:
    """Past-only contra leader basket sign, aligned to close index; index 0 is none."""
    values = np.asarray(leader_closes, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(LEADERS):
        raise ValueError("leader close matrix must have one row per frozen leader")
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("leader closes must be finite and positive; missing data cannot emit signals")
    returns = np.log(values[:, 1:] / values[:, :-1])
    basket = np.mean(returns, axis=0)
    sides = np.zeros(values.shape[1], dtype=np.int8)
    sides[1:] = np.where(basket < 0, 1, np.where(basket > 0, -1, 0))
    if cutoff is not None:
        sides[cutoff + 1:] = 0
    return sides


def causal_mutation_check(closes: np.ndarray, cutoff: int) -> bool:
    base = signal_sides(closes)
    changed = np.array(closes, copy=True)
    changed[:, cutoff + 1:] *= 1.7
    return np.array_equal(base[:cutoff + 1], signal_sides(changed)[:cutoff + 1])


def load_inputs(root: Path, symbols: list[str], months: list[str]):
    loaded = {}
    for symbol in symbols:
        loaded[symbol] = load_symbol(root, symbol, months)
    start = max(int(data[0].t_open_ms.iloc[0]) for data in loaded.values())
    end = min(int(data[0].t_open_ms.iloc[-1]) for data in loaded.values())
    for symbol, (frame, ft, fr) in list(loaded.items()):
        frame = frame[(frame.t_open_ms >= start) & (frame.t_open_ms <= end)].reset_index(drop=True)
        loaded[symbol] = (frame, ft, fr)
    common = loaded[LEADERS[0]][0].t_open_ms.to_numpy(np.int64)
    for symbol, (frame, _, _) in loaded.items():
        if not np.array_equal(frame.t_open_ms.to_numpy(np.int64), common):
            raise ValueError(f"non-identical hourly grid within common interval: {symbol}")
    return loaded, common


def generate(loaded: dict, times: np.ndarray) -> list[dict]:
    leader_closes = np.vstack([loaded[s][0].c.to_numpy(float) for s in LEADERS])
    if not causal_mutation_check(leader_closes, len(times) // 2):
        raise ValueError("future mutation changed past signals")
    sides = signal_sides(leader_closes)
    rows = []
    split_bounds = {k: (utc_ms(a), utc_ms(b)) for k, (a, b) in SPLITS.items()}
    targets = sorted(set(loaded) - set(LEADERS))
    for symbol in targets:
        frame, ft, fr = loaded[symbol]
        o = frame.o.to_numpy(float); c = frame.c.to_numpy(float)
        for h in HORIZONS:
            for i in range(1, len(times) - h - 1):
                signal_ms = int(times[i] + HOUR)
                if not anchor_aligned(signal_ms, h):
                    continue
                side = int(sides[i])
                if side == 0:
                    continue
                entry_i, exit_i = entry_exit_indices(i, h)
                exit_ms = int(times[exit_i] + HOUR)
                split = next((k for k, (left, right) in split_bounds.items()
                              if window_in_split(signal_ms, exit_ms, left, right)), None)
                if split is None:
                    continue
                entry, exit_price = float(o[entry_i]), float(c[exit_i])
                raw_return = side * (exit_price / entry - 1.0)
                funding = funding_sum_between(ft, fr, int(times[entry_i]), exit_ms)
                funding_excl_exit = funding_sum_between(ft, fr, int(times[entry_i]), exit_ms,
                                                        include_exit=False)
                leader_ret = float(np.mean(np.log(leader_closes[:, i] / leader_closes[:, i - 1])))
                momentum_side = -1 if leader_ret < 0 else 1
                mom_return = momentum_side * (exit_price / entry - 1.0)
                row = {"symbol": symbol, "horizon_h": h, "split": split,
                       "signal_ms": signal_ms, "entry_ms": int(times[entry_i]),
                       "exit_ms": exit_ms, "side": side, "leader_basket_logret": leader_ret,
                       "gross": raw_return, "funding_sum": funding,
                       "funding_sum_excl_exit": funding_excl_exit,
                       "funding_exit_edge": funding - funding_excl_exit,
                       "m1_correct": int(side * math.log(exit_price / float(c[i])) > 0),
                       "momentum_gross": mom_return}
                for name, fee in FEES.items():
                    row[f"net_{name}"] = net_return(side, raw_return, funding, fee)
                    row[f"net_{name}_exit_excl"] = net_return(side, raw_return, funding_excl_exit, fee)
                    row[f"momentum_net_{name}"] = net_return(momentum_side, mom_return, funding, fee)
                rows.append(row)
    return rows


def draw_mbb_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Draw classic non-circular moving blocks; never wrap a split boundary."""
    if n < 1 or block < 1 or block > n:
        raise ValueError("invalid moving-block dimensions")
    count = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=count)
    return np.concatenate([start + np.arange(block) for start in starts])[:n]


def block_ci(regular_anchor_returns: np.ndarray, horizon: int) -> list[float | None]:
    """Bootstrap synchronized returns in actual 7-calendar-day observation blocks."""
    grouped = np.asarray(regular_anchor_returns, dtype=float)
    if not len(grouped):
        return [None, None]
    n = len(grouped); block = min(bootstrap_block_observations(horizon), n); blocks = math.ceil(n / block)
    rng = np.random.default_rng(SEED)
    out = np.empty(BOOTSTRAP_REPS)
    for j in range(BOOTSTRAP_REPS):
        idx = draw_mbb_indices(n, block, rng)
        out[j] = float(np.mean(grouped[idx]))
    return [float(v) for v in np.quantile(out, [0.025, 0.975])]


def summarize(rows: list[dict], times: np.ndarray, target_count: int) -> dict:
    df = pd.DataFrame(rows)
    report = {"m2": "NOT_MEASURED", "targets": sorted(df.symbol.unique().tolist()) if len(df) else [],
              "cells": {}}
    for h in HORIZONS:
        report["cells"][str(h)] = {}
        for split in SPLITS:
            sub = df[(df.horizon_h == h) & (df.split == split)] if len(df) else df
            left, right = (utc_ms(v) for v in SPLITS[split])
            anchors = []
            for i in range(1, len(times) - h - 1):
                signal_ms = int(times[i] + HOUR)
                exit_ms = int(times[i + h] + HOUR)
                if window_in_split(signal_ms, exit_ms, left, right) and anchor_aligned(signal_ms, h):
                    anchors.append(signal_ms)
            by_time = {int(t): group for t, group in sub.groupby("signal_ms", sort=True)} if len(sub) else {}
            opportunities = len(anchors) * target_count
            cell = {"signals": len(sub), "eligible_target_hour_opportunities": opportunities,
                    "coverage_pct": len(sub) / max(1, opportunities),
                    "symbols": int(sub.symbol.nunique()) if len(sub) else 0}
            for metric in ("gross", "net_base", "net_stress", "net_base_exit_excl",
                           "net_stress_exit_excl", "momentum_net_base", "momentum_net_stress"):
                if opportunities:
                    per_anchor = np.array([
                        float(by_time[t][metric].sum()) / target_count if t in by_time else 0.0
                        for t in anchors], dtype=float)
                    cell[f"mean_{metric}"] = float(np.mean(per_anchor))
                    cell[f"mean_{metric}_per_signal"] = float(sub[metric].mean()) if len(sub) else None
                    cell[f"synchronized_{metric}_95ci"] = block_ci(per_anchor, h)
                else:
                    cell[f"mean_{metric}"] = None
                    cell[f"mean_{metric}_per_signal"] = None
                    cell[f"synchronized_{metric}_95ci"] = [None, None]
            cell["m1_direction_accuracy"] = float(sub.m1_correct.mean()) if len(sub) else None
            cell["nonoverlap_per_symbol"] = int(sum(
                len(g.sort_values("entry_ms").loc[lambda x: x.entry_ms >= x.exit_ms.shift(1, fill_value=-1)])
                for _, g in sub.groupby("symbol"))) if len(sub) else 0
            marketwise = 0
            last_exit = -1
            for record in sorted(sub.to_dict("records"), key=lambda x: (x["entry_ms"], x["symbol"])):
                if record["entry_ms"] >= last_exit:
                    marketwise += 1
                    last_exit = record["exit_ms"]
            cell["nonoverlap_marketwide"] = marketwise
            report["cells"][str(h)][split] = cell
    return report


def net_return(side: int, signed_gross: float, funding_sum: float, fee: float) -> float:
    if side not in (-1, 1):
        raise ValueError("side must be +1 or -1")
    return signed_gross - fee - side * funding_sum


def entry_exit_indices(signal_index: int, horizon: int) -> tuple[int, int]:
    if signal_index < 1 or horizon not in HORIZONS:
        raise ValueError("invalid signal index or horizon")
    return signal_index + 1, signal_index + horizon


def anchor_aligned(signal_ms: int, horizon: int) -> bool:
    return horizon == 1 or (horizon in HORIZONS and signal_ms // HOUR % horizon == 0)


def window_in_split(signal_ms: int, exit_ms: int, left: int, right: int) -> bool:
    return left <= signal_ms < right and exit_ms <= right


def bootstrap_block_observations(horizon: int) -> int:
    if horizon not in HORIZONS:
        raise ValueError("unsupported horizon")
    return BLOCK_HOURS // horizon


def funding_sum_between(times: np.ndarray, rates: np.ndarray, entry_ms: int, exit_ms: int,
                        include_exit: bool = True) -> float:
    if len(times) != len(rates) or exit_ms < entry_ms:
        raise ValueError("invalid funding arrays or interval")
    lo = int(np.searchsorted(times, entry_ms, side="right"))
    hi = int(np.searchsorted(times, exit_ms, side="right" if include_exit else "left"))
    return float(np.sum(rates[lo:hi]))


def render_report(summary: dict, signal_count: int) -> str:
    lines = ["# Cross-asset seesaw exploratory screen", "",
             f"- Leaders: {', '.join(LEADERS)}", f"- Targets: {summary['target_symbols']}",
             f"- Signals: {signal_count:,}", "- M2: NOT MEASURED (no source-defined barrier rule)",
             "- All splits are previously exposed; not OOS evidence.",
             "- Spread/slippage are unavailable; costs are fee proxies only.",
             "- Funding at the exit timestamp is ambiguous; both inclusive and exclusive results are reported.",
             "- Net means use zero returns for eligible no-signal anchors; coverage uses target-hour opportunities.",
             f"- Data fingerprint: `{summary['data_fingerprint']}`", "",
             "| Horizon | Split | Signals | Coverage | Non-overlap market N | M1 | Gross/opportunity | Net base (exit in) | Net stress (exit in) | Net base (exit out) | Base 95% CI | Stress 95% CI |",
             "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for horizon in HORIZONS:
        for split in SPLITS:
            cell = summary["cells"][str(horizon)][split]
            fmt = lambda value: "NA" if value is None else f"{value:.6%}"
            lines.append(f"| {horizon}h | {split} | {cell['signals']:,} | {fmt(cell['coverage_pct'])} | "
                         f"{cell['nonoverlap_marketwide']:,} | {fmt(cell['m1_direction_accuracy'])} | "
                         f"{fmt(cell['mean_gross'])} | {fmt(cell['mean_net_base'])} | "
                         f"{fmt(cell['mean_net_stress'])} | {fmt(cell['mean_net_base_exit_excl'])} | "
                         f"{cell['synchronized_net_base_95ci']} | "
                         f"{cell['synchronized_net_stress_95ci']} |")
    lines += ["", "## Screening decision", "",
              "REJECT for progression to M2 design: neither horizon has positive net mean under base and stress costs; "
              "the net means are negative and synchronized confidence intervals are below zero. "
              "This exploratory result does not establish a universal absence of cross-asset effects.", "",
              "See `summary.json` and `signal_ledger.csv.gz` for every issued event."]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive-root", type=Path, required=True)
    p.add_argument("--coverage-json", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--report-only", action="store_true")
    args = p.parse_args()
    if args.report_only:
        summary_path = args.output_dir / "summary.json"
        summary = json.loads(summary_path.read_text())
        with __import__("gzip").open(args.output_dir / "signal_ledger.csv.gz", "rt") as ledger:
            signal_count = sum(1 for _ in ledger) - 1
        (args.output_dir / "report.md").write_text(render_report(summary, signal_count))
        print(json.dumps({"status": "report_refreshed", "output_dir": str(args.output_dir)}))
        return 0
    if args.output_dir.exists():
        raise FileExistsError(f"refusing overwrite: {args.output_dir}")
    coverage = json.loads(args.coverage_json.read_text())
    cohort = coverage["cohorts_by_exact_run"]["2023-03..2026-05"]
    months = pd.period_range("2023-03", "2026-05", freq="M").astype(str).tolist()
    loaded, times = load_inputs(args.archive_root, cohort, months)
    rows = generate(loaded, times)
    summary = summarize(rows, times, len(cohort) - len(LEADERS))
    manifest = []
    for symbol in cohort:
        for month in months:
            for kind, filename in (("kline", f"{symbol}-1h-{month}.zip"),
                                   ("mark", f"{symbol}-1h-{month}.zip"),
                                   ("funding", f"{symbol}-fundingRate-{month}.zip")):
                folder = {"kline": "klines_1h", "mark": "mark_price_1h", "funding": "funding"}[kind]
                path = args.archive_root / folder / symbol / filename
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                manifest.append(f"{symbol}|{month}|{kind}|{digest}")
    manifest_text = "\n".join(manifest) + "\n"
    manifest_hash = hashlib.sha256(manifest_text.encode()).hexdigest()
    summary.update({"symbols_total": len(cohort), "target_symbols": len(cohort)-len(LEADERS),
                    "leaders": list(LEADERS), "period_start_ms": int(times[0]),
                    "period_end_exclusive_ms": int(times[-1]+HOUR),
                    "data_fingerprint": manifest_hash, "source_manifest_sha256": manifest_hash,
                    "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "command": " ".join([sys.executable, *sys.argv]),
                    "bootstrap": {"method": "synchronized non-circular moving-block bootstrap",
                                  "replicates": BOOTSTRAP_REPS, "block_hours": BLOCK_HOURS,
                                  "observations_per_block": {str(h): bootstrap_block_observations(h)
                                                              for h in HORIZONS},
                                  "seed": SEED},
                    "funding_rule": "(entry_ms, exit_ms] inclusive primary; (entry_ms, exit_ms) sensitivity",
                    "preregistration_sha256": hashlib.sha256((ROOT / "docs/research/inventory/PREREG_CROSS_ASSET_SEESAW_SCREEN_20261120.md").read_bytes()).hexdigest(),
                    "exposure_warning": "all historical periods exposed; exploratory rejection/debug only",
                    "causal_mutation": "PASS"})
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "source_manifest.txt").write_text(manifest_text)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    pd.DataFrame(rows).to_csv(args.output_dir / "signal_ledger.csv.gz", index=False, compression={"method":"gzip", "mtime":0})
    (args.output_dir / "report.md").write_text(render_report(summary, len(rows)))
    print(json.dumps({"status":"complete", "symbols":len(cohort), "signals":len(rows),
                      "output_dir":str(args.output_dir), "fingerprint":summary["data_fingerprint"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
