"""Fixed one-candidate funding-tail reversal audit on archived USD-M data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chart_predictor import indicators
from scripts.research.audit_usdm_timestamps import audit_cohort
from scripts.research.long_history_setup_m2_probe import (
    BASE_FEE_RT, STRESS_FEE_RT, SPLITS, _m2_path, _nonoverlap, _sha256,
    _wilson, load_symbol,
)
from scripts.research.run_contract import validate_run_record
from scripts.research.verify_usdm_archives import verify as verify_archives

HORIZON = 10
WINDOW = 180 * 24 * 60 * 60 * 1000
MIN_HISTORY = 30


def funding_events(times: np.ndarray, rates: np.ndarray) -> list[dict]:
    """Current funding event is excluded from its trailing quantile."""
    result = []
    for i, (ts, rate) in enumerate(zip(times, rates)):
        left = int(np.searchsorted(times, int(ts) - WINDOW, side="left"))
        history = rates[left:i]
        if len(history) < MIN_HISTORY:
            continue
        q10, q90 = (float(np.quantile(history, q, method="linear")) for q in (.10, .90))
        # Strict tails avoid classifying a whole tied/zero-funding distribution as signals.
        side = "long" if rate < q10 else "short" if rate > q90 else None
        result.append({"signal_time_ms": int(ts), "funding_index": i, "side": side,
                       "funding_rate": float(rate), "q10": q10, "q90": q90})
    return result


def funding_signals(times: np.ndarray, rates: np.ndarray) -> list[dict]:
    return [event for event in funding_events(times, rates) if event["side"]]


def causal_future_mutation_check(times: np.ndarray, rates: np.ndarray) -> dict:
    if len(times) < 80:
        raise ValueError("causal fixture requires at least 80 events")
    cut = len(times) // 2
    full = [r for r in funding_signals(times, rates) if r["funding_index"] < cut]
    prefix = [r for r in funding_signals(times[:cut], rates[:cut]) if r["funding_index"] < cut]
    mutated_rates = rates.copy()
    mutated_rates[cut:] = mutated_rates[cut:] * 1000 + 7
    mutated = [r for r in funding_signals(times, mutated_rates) if r["funding_index"] < cut]
    keys = lambda rs: [(r["funding_index"], r["side"], r["q10"], r["q90"]) for r in rs]
    return {"status": "PASS" if keys(full) == keys(prefix) == keys(mutated) else "FAIL",
            "cut_index": cut, "prefix_signals": len(full)}


def _ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def _split(ts: int) -> str | None:
    for name, (left, right) in SPLITS.items():
        if _ms(left) <= ts < _ms(right):
            return name
    return None


def score_symbol(symbol: str, frame: pd.DataFrame, ft: np.ndarray,
                 fr: np.ndarray) -> tuple[list[dict], dict]:
    times = frame.t_open_ms.to_numpy(dtype=np.int64)
    highs, lows, closes = (frame[c].to_numpy(float) for c in ("h", "l", "c"))
    true_range = indicators.true_range(highs, lows, closes)
    atr = pd.Series(true_range).rolling(14, min_periods=14).mean().to_numpy()
    records, opportunities = [], {name: 0 for name in SPLITS}
    for event in funding_events(ft, fr):
        split = _split(event["signal_time_ms"])
        if split is None:
            continue
        entry_i = int(np.searchsorted(times, event["signal_time_ms"], side="right"))
        if entry_i + HORIZON > len(frame):
            continue
        future = frame.iloc[entry_i:entry_i + HORIZON]
        if int(future.t_open_ms.iloc[-1]) + 3_600_000 > _ms(SPLITS[split][1]):
            continue
        opportunities[split] += 1
        if not event["side"]:
            continue
        # The last fully closed candle at funding time; never use the open event candle's future OHLC.
        atr_i = int(np.searchsorted(times, event["signal_time_ms"] - 3_600_000, side="right")) - 1
        valid = atr_i >= 0 and math.isfinite(float(atr[atr_i])) and float(atr[atr_i]) > 0
        entry = float(frame.o.iloc[entry_i])
        risk = float(atr[atr_i]) if valid else math.nan
        stop = entry - risk if event["side"] == "long" else entry + risk
        if valid:
            out = _m2_path(event["side"], entry, stop, future, HORIZON, ft, fr)
            risk_distance = abs(entry - stop)
            baseline_long = _m2_path("long", entry, entry - risk_distance, future,
                                     HORIZON, ft, fr)
            baseline_short = _m2_path("short", entry, entry + risk_distance, future,
                                      HORIZON, ft, fr)
        else:
            out = {"m2_hit": False, "reason": "INVALID_ATR", "exit_price": float(future.c.iloc[-1]),
                   "exit_time_ms": int(future.t_open_ms.iloc[-1]) + 3_600_000,
                   "funding_sum": 0.0, "risk_pct": None, "target": None}
            baseline_long = baseline_short = {"m2_hit": False}
        sign = 1 if event["side"] == "long" else -1
        gross = sign * (out["exit_price"] / entry - 1) if valid else None
        funding_pnl = -sign * out["funding_sum"]
        net_base = gross - BASE_FEE_RT + funding_pnl if gross is not None else None
        net_stress = gross - STRESS_FEE_RT + funding_pnl if gross is not None else None
        records.append({**event, "setup": "funding_tail_reversal", "symbol": symbol, "split": split,
            "entry_time_ms": int(times[entry_i]), "window_end_ms": int(times[entry_i + HORIZON - 1]) + 3_600_000,
            "entry": entry, "stop": stop if valid else None, "target": out["target"],
            "risk_pct": out["risk_pct"], "exit_time_ms": out["exit_time_ms"],
            "exit_price": out["exit_price"], "m2_hit": bool(out["m2_hit"]),
            "baseline_long_hit": bool(baseline_long["m2_hit"]),
            "baseline_short_hit": bool(baseline_short["m2_hit"]),
            "exit_reason": out["reason"], "funding_sum": out["funding_sum"], "gross_return": gross,
            "net_base": net_base, "net_stress": net_stress,
            "r_base": net_base / out["risk_pct"] if net_base is not None and out["risk_pct"] else None,
            "r_stress": net_stress / out["risk_pct"] if net_stress is not None and out["risk_pct"] else None,
            "m1_hit": sign * (float(future.c.iloc[-1]) / entry - 1) > 0 if valid else None})
    return records, opportunities


def summarize(rows: list[dict], opportunities: int) -> dict:
    hits = sum(bool(r["m2_hit"]) for r in rows)
    valid = [r for r in rows if r["net_base"] is not None]
    m1 = [r for r in rows if r["m1_hit"] is not None]
    return {"signals": len(rows), "m2_hits": hits, "m2_rate": hits / len(rows) if rows else None,
        "m2_wilson_95": _wilson(hits, len(rows)), "m1_scored": len(m1),
        "same_signal_baseline_long_m2": (sum(r["baseline_long_hit"] for r in rows) / len(rows)) if rows else None,
        "same_signal_baseline_short_m2": (sum(r["baseline_short_hit"] for r in rows) / len(rows)) if rows else None,
        "m1_direction_accuracy": sum(bool(r["m1_hit"]) for r in m1) / len(m1) if m1 else None,
        "coverage_pct": 100 * len(rows) / max(1, opportunities),
        "symbols": len({r["symbol"] for r in rows}),
        "nonoverlap_symbol_n": len(_nonoverlap(rows, False)),
        "nonoverlap_market_n": len(_nonoverlap(rows, True)),
        "mean_net_base": float(np.mean([r["net_base"] for r in valid])) if valid else None,
        "mean_net_stress": float(np.mean([r["net_stress"] for r in valid])) if valid else None,
        "mean_r_base": float(np.mean([r["r_base"] for r in valid if r["r_base"] is not None])) if valid else None,
        "mean_r_stress": float(np.mean([r["r_stress"] for r in valid if r["r_stress"] is not None])) if valid else None,
        "exit_reasons": {k: sum(r["exit_reason"] == k for r in rows)
                         for k in sorted({r["exit_reason"] for r in rows})}}


def run(args) -> dict:
    audit, coverage = json.loads(args.audit_json.read_text()), json.loads(args.coverage_json.read_text())
    symbols = coverage["cohorts_by_exact_run"].get(args.cohort)
    if not symbols:
        raise ValueError(f"unknown exact cohort: {args.cohort}")
    first, last = args.cohort.split("..")
    y, m = map(int, first.split("-")); ey, em = map(int, last.split("-"))
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    selected = [r for r in audit["archive_rows"] if r.get("symbol") in symbols and r.get("month") in months
                and r.get("kind") in {"klines_1h", "mark_price_1h", "funding"}]
    timestamp_audit = audit_cohort(audit, coverage, args.archive_root, args.cohort)
    hash_audit = verify_archives({"archive_rows": selected}, args.archive_root)
    if timestamp_audit["status"] != "PASS" or hash_audit["status"] != "PASS":
        raise ValueError("raw timestamp or archive hash audit failed")
    fingerprint = hashlib.sha256("\n".join(
        f"{r['symbol']}|{r['month']}|{r['kind']}|{r['sha256']}"
        for r in sorted(selected, key=lambda x: (x["symbol"], x["month"], x["kind"]))
    ).encode()).hexdigest()
    all_records, opp_counts, causal, expected_times = [], {k: 0 for k in SPLITS}, [], None
    for symbol in symbols:
        frame, ft, fr = load_symbol(args.archive_root, symbol, months)
        frame = frame[(frame.t_open_ms >= _ms("2023-03-23T15:00:00Z")) &
                      (frame.t_open_ms < _ms("2026-06-01T00:00:00Z"))].reset_index(drop=True)
        times = frame.t_open_ms.to_numpy(np.int64)
        if expected_times is None:
            expected_times = times
        elif not np.array_equal(expected_times, times):
            raise ValueError(f"hourly timestamp mismatch: {symbol}")
        guard = causal_future_mutation_check(ft, fr)
        causal.append({"symbol": symbol, **guard})
        if guard["status"] != "PASS":
            raise ValueError(f"future funding mutation failed: {symbol}")
        rows, counts = score_symbol(symbol, frame, ft, fr)
        all_records.extend(rows)
        for split, count in counts.items():
            opp_counts[split] += count
    grouped = {split: [r for r in all_records if r["split"] == split] for split in SPLITS}
    metrics = {split: summarize(grouped[split], opp_counts[split]) for split in SPLITS}
    oos = grouped["validation"] + grouped["sealed"]
    metrics["validation_plus_previously_exposed_sealed"] = summarize(
        oos, opp_counts["validation"] + opp_counts["sealed"])
    if args.output_dir.exists():
        raise FileExistsError(f"refusing overwrite: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.strip()
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    files = [Path(__file__), Path(__file__).with_name("long_history_setup_m2_probe.py"),
             ROOT / "chart_predictor/indicators.py"]
    record = {"schema_version": 1, "run_id": f"funding-tail-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
        "market": "crypto", "status": "complete",
        "frozen_at": datetime.fromtimestamp(args.prereg.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_started_at": started, "preregistration_sha256": _sha256(args.prereg), "code_sha": git_sha,
        "code_files": [{"ref": str(p.relative_to(ROOT)), "sha256": _sha256(p)} for p in files],
        "inputs": [{"role": "audited historical Binance USD-M 1h candles/funding",
                    "ref": str(args.archive_root), "sha256": fingerprint}],
        "period": {"start": "2023-03-23T15:00:00Z", "end": "2026-06-01T00:00:00Z"},
        "splits": {k: {"start": v[0], "end": v[1], "reused_for_tuning": False,
                       "previously_exposed": k != "development"} for k, v in SPLITS.items()},
        "cost_scenarios": {"base": {"fee_round_trip": BASE_FEE_RT, "slippage": "not modeled"},
                           "stress": {"fee_round_trip": STRESS_FEE_RT, "slippage": "not modeled"}},
        "execution": {"fill_rule": "first hourly open strictly after funding calc_time",
            "same_bar_rule": "stop first; target gap credited at target; timeout fails M2",
            "funding_rule": "archived signed funding after entry through exit"},
        "counts": {"oos_issued_signals": len(oos),
                   "oos_nonoverlap_signals": metrics["validation_plus_previously_exposed_sealed"]["nonoverlap_symbol_n"]},
        "metrics": {"m2_target_first_rate": metrics["validation_plus_previously_exposed_sealed"]["m2_rate"] or 0,
            "m2_wilson_95_low": metrics["validation_plus_previously_exposed_sealed"]["m2_wilson_95"][0] or 0,
            "m2_wilson_95_high": metrics["validation_plus_previously_exposed_sealed"]["m2_wilson_95"][1] or 1,
            "m1_direction_accuracy": metrics["validation_plus_previously_exposed_sealed"]["m1_direction_accuracy"] or 0,
            "net_expectancy": metrics["validation_plus_previously_exposed_sealed"]["mean_net_stress"] or 0},
        "note": "Exploratory only: source periods were previously exposed; no promotion possible."}
    errors = validate_run_record(record)
    if errors:
        raise ValueError(f"run contract failed: {errors}")
    (args.output_dir / "summary.json").write_text(json.dumps({"data_fingerprint": fingerprint,
        "timestamp_audit": timestamp_audit, "hash_audit": hash_audit, "causal_future_mutation": causal,
        "opportunities": opp_counts, "results": metrics}, indent=2) + "\n")
    (args.output_dir / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    pd.DataFrame(all_records).to_csv(args.output_dir / "event_ledger.csv.gz", index=False,
                                     compression={"method": "gzip", "mtime": 0})
    lines = ["# Funding-tail reversal: exploratory historical result", "",
        f"- Validation + previously exposed sealed signals: {len(oos)}",
        "- Previously exposed dates are exploratory, not untouched OOS. Spread/slippage are absent.", "",
        "| Split | N | M2 | Wilson 95% | Same-event long / short M2 | Symbol N | Market N | Coverage | Net base | Net stress | M1 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in (*SPLITS, "validation_plus_previously_exposed_sealed"):
        x = metrics[name]
        lines.append(f"| {name} | {x['signals']} | {x['m2_rate']} | {x['m2_wilson_95']} | "
            f"{x['same_signal_baseline_long_m2']} / {x['same_signal_baseline_short_m2']} | "
            f"{x['nonoverlap_symbol_n']} | {x['nonoverlap_market_n']} | {x['coverage_pct']}% | "
            f"{x['mean_net_base']} | {x['mean_net_stress']} | {x['m1_direction_accuracy']} |")
    (args.output_dir / "report.md").write_text("\n".join(lines) + "\n")
    return {"status": "complete", "output_dir": str(args.output_dir),
            "signals": len(all_records), "data_fingerprint": fingerprint}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--cohort", default="2023-03..2026-05")
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
