"""One-rule exploratory test of prior-hour contrarian returns on audited USD-M data."""
from __future__ import annotations

import argparse
from datetime import datetime
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

HOUR_MS = 3_600_000
SPLITS = {
    "development": ("2023-03-23T15:00:00Z", "2025-03-01T00:00:00Z"),
    "validation_exposed": ("2025-03-01T00:00:00Z", "2025-11-01T00:00:00Z"),
    "evaluation_previously_exposed": ("2025-11-01T00:00:00Z", "2026-06-01T00:00:00Z"),
}
SPLIT_BOUNDS = {name: tuple(int(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() * 1000)
                            for x in bounds) for name, bounds in SPLITS.items()}
FEE = {"base": 0.001, "stress": 0.003}
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 20261120
BLOCK_HOURS = 168


def _utc_ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


SCREEN_BOUNDS = (_utc_ms("2023-03-23T15:00:00Z"), _utc_ms("2026-06-01T00:00:00Z"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def signal_side(closes: np.ndarray, index: int) -> int:
    """Return +1 long, -1 short, or 0 for an exact-zero prior close return."""
    r = math.log(float(closes[index]) / float(closes[index - 1]))
    return -1 if r > 0 else 1 if r < 0 else 0


def generate_records(symbol: str, frame: pd.DataFrame, funding_times: np.ndarray,
                     funding_rates: np.ndarray, horizon: int) -> list[dict]:
    if horizon not in (1, 4):
        raise ValueError("only preregistered horizons H=1 and H=4 are allowed")
    times = frame.t_open_ms.to_numpy(dtype=np.int64)
    opens = frame.o.to_numpy(dtype=float)
    closes = frame.c.to_numpy(dtype=float)
    if len(times) != len(np.unique(times)) or np.any(np.diff(times) != HOUR_MS):
        raise ValueError(f"hourly timestamps are not unique and contiguous: {symbol}")
    records = []
    for i in range(1, len(frame) - horizon):
        signal_close_ms = int(times[i] + HOUR_MS)
        if horizon == 4 and (signal_close_ms // HOUR_MS) % 4 != 0:
            continue
        prior_return = math.log(closes[i] / closes[i - 1])
        if prior_return == 0:
            records.append({"symbol": symbol, "horizon_h": horizon,
                            "signal_close_ms": signal_close_ms, "entry_ms": int(times[i + 1]),
                            "exit_ms": int(times[i + horizon] + HOUR_MS),
                            "prior_return": 0.0, "side": 0, "issued_signal": 0,
                            "signal_close": float(closes[i]), "entry_price": float(opens[i + 1]),
                            "exit_price": float(closes[i + horizon]), "m1_correct": None,
                            "executable_gross": 0.0, "executable_win": None,
                            "funding_rate_sum": 0.0, "funding_pnl_base": 0.0,
                            "funding_pnl_stress": 0.0,
                            "net_base": 0.0, "net_stress": 0.0,
                            "momentum_net_base": 0.0, "momentum_net_stress": 0.0,
                            "long_net_base": 0.0, "long_net_stress": 0.0,
                            "short_net_base": 0.0, "short_net_stress": 0.0})
            continue
        side = -1 if prior_return > 0 else 1
        entry_i = i + 1
        exit_i = entry_i + horizon - 1
        entry_ms = int(times[entry_i])
        exit_ms = int(times[exit_i] + HOUR_MS)
        entry_price = float(opens[entry_i])
        exit_price = float(closes[exit_i])
        signal_close = float(closes[i])
        signal_to_exit = side * math.log(exit_price / signal_close)
        executable_gross = side * (exit_price / entry_price - 1.0)
        f0 = int(np.searchsorted(funding_times, entry_ms, side="right"))
        f1 = int(np.searchsorted(funding_times, exit_ms, side="right"))
        funding_sum = float(np.sum(funding_rates[f0:f1]))
        record = {
            "symbol": symbol,
            "horizon_h": horizon,
            "signal_close_ms": signal_close_ms,
            "entry_ms": entry_ms,
            "exit_ms": exit_ms,
            "prior_return": prior_return,
            "side": side,
            "issued_signal": 1,
            "signal_close": signal_close,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "m1_correct": int(signal_to_exit > 0),
            "executable_gross": executable_gross,
            "executable_win": int(executable_gross > 0),
            "funding_rate_sum": funding_sum,
        }
        for cost, fee in FEE.items():
            record[f"funding_pnl_{cost}"] = -side * funding_sum
            record[f"net_{cost}"] = executable_gross - fee - side * funding_sum
            record[f"momentum_net_{cost}"] = -executable_gross - fee + side * funding_sum
            record[f"long_net_{cost}"] = (exit_price / entry_price - 1.0) - fee - funding_sum
            record[f"short_net_{cost}"] = -(exit_price / entry_price - 1.0) - fee + funding_sum
        records.append(record)
    return records


def _bootstrap_ci(values: np.ndarray, block_len: int, seed: int) -> list[float | None]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return [None, None]
    n = len(values)
    block = min(max(1, block_len), n)
    rng = np.random.default_rng(seed)
    samples = np.empty(BOOTSTRAP_REPS, dtype=float)
    blocks_needed = math.ceil(n / block)
    offsets = np.arange(block)
    for b in range(BOOTSTRAP_REPS):
        starts = rng.integers(0, n, size=blocks_needed)
        indices = np.concatenate([(start + offsets) % n for start in starts])[:n]
        samples[b] = float(np.mean(values[indices]))
    return [float(x) for x in np.quantile(samples, [0.025, 0.975])]


def _wilson(successes: int, total: int) -> list[float | None]:
    if total == 0:
        return [None, None]
    z = 1.959963984540054
    p = successes / total
    d = 1 + z * z / total
    center = (p + z * z / (2 * total)) / d
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return [center - margin, center + margin]


def _split_name(signal_ms: int) -> str | None:
    for name, (left, right) in SPLIT_BOUNDS.items():
        if left <= signal_ms < right:
            return name
    return None


def causal_signature(records: list[dict], cutoff_ms: int) -> list[tuple[int, int, float]]:
    return [(int(r["signal_close_ms"]), int(r["side"]), float(r["prior_return"]))
            for r in records if int(r["signal_close_ms"]) <= cutoff_ms]


def summarize(records: list[dict], horizon: int, split_name: str) -> tuple[dict, list[dict]]:
    if split_name == "all_exposed":
        left, right = SCREEN_BOUNDS
        opportunities = [r for r in records if left <= r["signal_close_ms"] < right
                         and r["exit_ms"] <= right]
    else:
        opportunities = [r for r in records if _split_name(r["signal_close_ms"]) == split_name
                         and r["exit_ms"] <= _utc_ms(SPLITS[split_name][1])]
    if not opportunities:
        return {"horizon_h": horizon, "split": split_name, "opportunities": 0,
                "signals": 0, "coverage": 0.0}, []
    all_df = pd.DataFrame(opportunities)
    df = all_df[all_df.issued_signal == 1].copy()
    if df.empty:
        return {"horizon_h": horizon, "split": split_name, "opportunities": len(all_df),
                "signals": 0, "coverage": 0.0}, []
    per_symbol = []
    for symbol, group in df.groupby("symbol", sort=True):
        row = {"symbol": symbol, "signals": len(group),
               "m1_accuracy": float(group.m1_correct.mean()),
               "exec_win_rate": float(group.executable_win.mean()),
               "gross_mean": float(group.executable_gross.mean()),
               "funding_mean": float(group.funding_rate_sum.mean())}
        for cost in FEE:
            row[f"net_{cost}_mean"] = float(group[f"net_{cost}"].mean())
        per_symbol.append(row)
    # Cross-sectionally average simultaneous signals first, then resample time blocks.
    time = df.groupby("signal_close_ms", sort=True).agg(
        m1_correct=("m1_correct", "mean"),
        executable_gross=("executable_gross", "mean"),
        net_base=("net_base", "mean"),
        net_stress=("net_stress", "mean"),
        momentum_net_base=("momentum_net_base", "mean"),
        momentum_net_stress=("momentum_net_stress", "mean"),
        long_net_base=("long_net_base", "mean"),
        long_net_stress=("long_net_stress", "mean"),
        short_net_base=("short_net_base", "mean"),
        short_net_stress=("short_net_stress", "mean"),
    )
    block_len = max(1, BLOCK_HOURS // horizon)
    summary = {
        "horizon_h": horizon,
        "split": split_name,
        "opportunities": len(all_df),
        "signals": len(df),
        "symbols": int(df.symbol.nunique()),
        "unique_market_times": len(time),
        "coverage": len(df) / len(all_df),
        "m1_accuracy": float(df.m1_correct.mean()),
        "m1_wilson_iid_descriptive": _wilson(int(df.m1_correct.sum()), len(df)),
        "executable_win_rate": float(df.executable_win.mean()),
        "mean_gross_return": float(df.executable_gross.mean()),
        "mean_signed_funding_cashflow": float((-df.side * df.funding_rate_sum).mean()),
        "overlap_note": "Per-symbol holding windows do not overlap at the fixed signal cadence; simultaneous symbols are correlated.",
        "m2": "NOT_MEASURED: the source hypothesis has no target/stop barrier specification.",
        "block_bootstrap": {"block_hours": block_len * horizon,
                            "replicates": BOOTSTRAP_REPS,
                            "seed": BOOTSTRAP_SEED,
                            "m1_accuracy_ci": _bootstrap_ci(time.m1_correct.to_numpy(), block_len, BOOTSTRAP_SEED),
                            "gross_mean_ci": _bootstrap_ci(time.executable_gross.to_numpy(), block_len, BOOTSTRAP_SEED + 1)},
        "baseline_net_means": {},
    }
    for cost in FEE:
        key = f"net_{cost}"
        summary[key] = float(df[key].mean())
        summary[f"{key}_market_time_ci"] = _bootstrap_ci(time[key].to_numpy(), block_len,
                                                           BOOTSTRAP_SEED + (10 if cost == "base" else 20))
        summary["baseline_net_means"][cost] = {
            name: float(df[f"{name}_net_{cost}"].mean())
            for name in ("momentum", "long", "short")
        }
        summary[f"{key}_positive_symbol_fraction"] = float(
            (df.groupby("symbol")[key].mean() > 0).mean())
    positive_gross_by_symbol = df.assign(
        positive_gross=df.executable_gross.clip(lower=0)
    ).groupby("symbol").positive_gross.sum()
    total_positive_gross = float(positive_gross_by_symbol.sum())
    summary["top_symbol_positive_gross_share"] = (
        float(positive_gross_by_symbol.max() / total_positive_gross)
        if total_positive_gross > 0 else None
    )
    summary["flat_net_mean"] = 0.0
    return summary, per_symbol


def screening_decisions(metrics: list[dict]) -> dict:
    decisions = {}
    pooled = [row for row in metrics if row["split"] == "all_exposed"]
    for horizon in (1, 4):
        row = next((item for item in pooled if item["horizon_h"] == horizon), {})
        checks = {
            "positive_base_net_mean": row.get("net_base", 0) > 0,
            "positive_stress_net_mean": row.get("net_stress", 0) > 0,
            "positive_base_95pct_lower_ci": bool(row.get("net_base_market_time_ci")
                                                  and row["net_base_market_time_ci"][0] > 0),
            "positive_stress_95pct_lower_ci": bool(row.get("net_stress_market_time_ci")
                                                    and row["net_stress_market_time_ci"][0] > 0),
            "no_symbol_over_25pct_positive_gross": bool(
                row.get("top_symbol_positive_gross_share") is not None
                and row["top_symbol_positive_gross_share"] <= 0.25),
        }
        decisions[str(horizon)] = {"checks": checks,
                                   "progress_to_separate_m2_design": all(checks.values())}
    return {"horizons": decisions,
            "overall": "PROGRESS_TO_M2_DESIGN" if any(
                item["progress_to_separate_m2_design"] for item in decisions.values()
            ) else "REJECT_SOURCE_INSPIRED_SETUP"}


def run_self_checks() -> dict:
    closes = np.asarray([100.0, 110.0, 100.0])
    if signal_side(closes, 1) != -1 or signal_side(closes, 2) != 1:
        raise AssertionError("contrarian sign convention failed")
    if signal_side(np.asarray([1.0, 1.0]), 1) != 0:
        raise AssertionError("exact-zero return must abstain")
    frame = pd.DataFrame({
        "t_open_ms": np.arange(24, dtype=np.int64) * HOUR_MS,
        "o": 100.0 + np.arange(24), "h": 101.0 + np.arange(24),
        "l": 99.0 + np.arange(24), "c": 100.5 + np.arange(24),
        "v": np.ones(24),
    })
    cutoff_index = 16
    causal_passes = True
    for horizon in (1, 4):
        causal_cutoff_ms = int(frame.t_open_ms.iloc[cutoff_index - horizon + 1])
        full = generate_records("TEST", frame, np.array([], dtype=np.int64),
                                np.array([], dtype=float), horizon)
        prefix = generate_records("TEST", frame.iloc[:cutoff_index + 1].copy(),
                                  np.array([], dtype=np.int64), np.array([], dtype=float), horizon)
        mutated = frame.copy(deep=True)
        for col in ("o", "h", "l", "c"):
            mutated.loc[cutoff_index:, col] *= 1.7
        mutated.loc[cutoff_index:, "v"] *= 2.0
        changed = generate_records("TEST", mutated, np.array([], dtype=np.int64),
                                   np.array([], dtype=float), horizon)
        if not (causal_signature(full, causal_cutoff_ms)
                == causal_signature(prefix, causal_cutoff_ms)
                == causal_signature(changed, causal_cutoff_ms)):
            causal_passes = False
    if not causal_passes:
        raise AssertionError("prefix or future-mutation causal check failed")
    return {"status": "PASS", "exact_zero_abstains": True,
            "positive_prior_return_short": True, "negative_prior_return_long": True,
            "prefix_invariance": "PASS", "future_mutation": "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing run directory: {args.output_dir}")
    checks = run_self_checks()
    coverage = json.loads(args.coverage_json.read_text())
    symbols = coverage["cohorts_by_exact_run"]["2023-03..2026-05"]
    months = [f"{year:04d}-{month:02d}" for year in range(2023, 2027)
              for month in range(1, 13) if "2023-03" <= f"{year:04d}-{month:02d}" <= "2026-05"]
    if len(symbols) != 36 or len(months) != 39:
        raise ValueError("unexpected frozen cohort or monthly span")
    all_records: dict[int, list[dict]] = {1: [], 4: []}
    for index, symbol in enumerate(symbols):
        frame, funding_times, funding_rates = load_symbol(args.archive_root, symbol, months)
        for horizon in (1, 4):
            records = generate_records(symbol, frame, funding_times, funding_rates, horizon)
            all_records[horizon].extend(records)
        if (index + 1) % 6 == 0:
            print(f"loaded {index + 1}/{len(symbols)} symbols", flush=True)

    args.output_dir.mkdir(parents=True)
    metrics = []
    symbol_rows = []
    for horizon, records in all_records.items():
        for split in ("all_exposed", *SPLITS):
            summary, rows = summarize(records, horizon, split)
            metrics.append(summary)
            symbol_rows.extend({**r, "horizon_h": horizon, "split": split} for r in rows)
    ledger_path = args.output_dir / "event_ledger.csv.gz"
    pd.concat([pd.DataFrame(rows) for rows in all_records.values()], ignore_index=True).to_csv(
        ledger_path, index=False, compression="gzip")
    pd.DataFrame(metrics).to_json(args.output_dir / "summary.json", orient="records", indent=2)
    pd.DataFrame(symbol_rows).to_csv(args.output_dir / "per_symbol.csv", index=False)
    manifest_path = args.archive_root / "manifest.jsonl"
    run = {
        "schema_version": 1,
        "run_id": "hourly-return-reversal-screen-20261120",
        "status": "complete_exploratory",
        "candidate": "contra_sign_of_previous_closed_hourly_return",
        "candidate_count": 1,
        "horizons_h": [1, 4],
        "symbols": symbols,
        "archive_months": [months[0], months[-1]],
        "pre_registration_sha256": sha256(args.prereg),
        "code_sha256": sha256(Path(__file__)),
        "source_manifest_sha256": sha256(manifest_path),
        "input_root": str(args.archive_root),
        "command": " ".join(sys.argv),
        "coverage_file_sha256": sha256(args.coverage_json),
        "costs_round_trip": FEE,
        "m2": "NOT_MEASURED",
        "data_status": "archive loader validates hourly continuity, mark coverage, OHLC and funding timestamps; prior cohort audit verified archive hashes",
        "historical_exposure": "all listed periods and source history were previously exposed; no OOS promotion permitted",
        "self_checks": checks,
        "results": metrics,
        "screening_decision": screening_decisions(metrics),
    }
    (args.output_dir / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    print(json.dumps({"run_id": run["run_id"], "records": len(pd.concat(
        [pd.DataFrame(x) for x in all_records.values()], ignore_index=True)),
        "summary_rows": len(metrics), "self_checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
