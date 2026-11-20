"""Fixed 1h M2 re-evaluation of existing chart setups on verified USD-M archives.

The command reads staged ZIPs and audit JSONs. It writes only to a new explicit
output directory; it never opens or modifies chart_predictor/data/.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chart_predictor import indicators
from chart_predictor.setups import SETUPS, generate_signals
from scripts.research.audit_usdm_timestamps import audit_cohort
from scripts.research.verify_usdm_archives import verify as verify_archives
from scripts.research.run_contract import validate_run_record


HORIZONS = (10, 20)
SPLITS = {
    "development": ("2023-03-23T15:00:00Z", "2025-03-01T00:00:00Z"),
    "validation": ("2025-03-01T00:00:00Z", "2025-11-01T00:00:00Z"),
    "sealed": ("2025-11-01T00:00:00Z", "2026-06-01T00:00:00Z"),
}
BASE_FEE_RT = 0.001
STRESS_FEE_RT = 0.003
TRADE_COLUMNS = (
    "setup", "horizon_hours", "split", "symbol", "side", "signal_index",
    "signal_time_ms", "entry_time_ms", "window_end_ms", "exit_time_ms",
    "entry", "stop", "target", "risk_pct", "exit_price", "m2_hit",
    "exit_reason", "m1_actual", "m1_hit", "funding_rate_sum",
    "net_base", "net_stress", "r_base", "r_stress", "baseline_long_m2",
    "baseline_short_m2",
)


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_zip_csv(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {path.name}")
        with archive.open(members[0]) as binary:
            with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
                return list(csv.DictReader(text))


def _paths(root: Path, symbol: str, month: str) -> dict[str, Path]:
    return {
        "klines_1h": root / "klines_1h" / symbol / f"{symbol}-1h-{month}.zip",
        "mark_price_1h": root / "mark_price_1h" / symbol / f"{symbol}-1h-{month}.zip",
        "funding": root / "funding" / symbol / f"{symbol}-fundingRate-{month}.zip",
    }


def load_symbol(root: Path, symbol: str, months: list[str]) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    candles: list[dict] = []
    fund_times: list[int] = []
    fund_rates: list[float] = []
    for month in months:
        files = _paths(root, symbol, month)
        kline_rows = _read_zip_csv(files["klines_1h"])
        mark_rows = _read_zip_csv(files["mark_price_1h"])
        funding_rows = _read_zip_csv(files["funding"])
        kline_times = [int(row["open_time"]) for row in kline_rows]
        mark_times = [int(row["open_time"]) for row in mark_rows]
        if not set(kline_times).issubset(set(mark_times)):
            raise ValueError(f"mark-price coverage does not include tradable kline hours: {symbol} {month}")
        mark_map = {int(row["open_time"]): row for row in mark_rows}
        for row in kline_rows:
            timestamp = int(row["open_time"])
            prices = [float(row[key]) for key in ("open", "high", "low", "close")]
            volume = float(row["volume"])
            mark = mark_map[timestamp]
            mark_values = [float(mark[key]) for key in ("open", "high", "low", "close")]
            if not all(math.isfinite(value) for value in (*prices, volume, *mark_values)) or volume < 0:
                raise ValueError(f"non-finite or invalid market row: {symbol} {month} {timestamp}")
            o, high, low, close = prices
            if high < max(o, close) or low > min(o, close) or high < low:
                raise ValueError(f"OHLC invariant failed: {symbol} {month} {timestamp}")
            mo, mh, ml, mc = mark_values
            if min(mark_values) <= 0 or mh < max(mo, mc) or ml > min(mo, mc) or mh < ml:
                raise ValueError(f"invalid mark-price OHLC: {symbol} {month} {timestamp}")
            candles.append({"t_open_ms": timestamp, "o": o, "h": high, "l": low,
                            "c": close, "v": volume})
        for row in funding_rows:
            fund_times.append(int(row["calc_time"]))
            rate = float(row["last_funding_rate"])
            if not math.isfinite(rate):
                raise ValueError(f"non-finite funding rate: {symbol} {month}")
            fund_rates.append(rate)

    frame = pd.DataFrame(candles).sort_values("t_open_ms").reset_index(drop=True)
    times = frame.t_open_ms.to_numpy(dtype=np.int64)
    if len(times) < 21 or np.any(np.diff(times) != 3_600_000):
        raise ValueError(f"hourly series has duplicate/gap: {symbol}")
    ordered = np.argsort(np.asarray(fund_times, dtype=np.int64))
    ft = np.asarray(fund_times, dtype=np.int64)[ordered]
    fr = np.asarray(fund_rates, dtype=float)[ordered]
    if len(ft) != len(np.unique(ft)):
        raise ValueError(f"duplicate funding timestamps: {symbol}")
    return frame, ft, fr


def causal_future_mutation_check(frame: pd.DataFrame, setups=SETUPS) -> dict:
    """Require full-series prefix signals to match both truncated and future-mutated runs."""
    if len(frame) < 200:
        raise ValueError("causal mutation fixture requires at least 200 hourly bars")
    cutoff = len(frame) // 2
    mutated = frame.copy(deep=True)
    for column in ("o", "h", "l", "c"):
        mutated.loc[cutoff:, column] = mutated.loc[cutoff:, column].to_numpy(float) * 1.7
    mutated.loc[cutoff:, "v"] = mutated.loc[cutoff:, "v"].to_numpy(float) * 2.0
    failures = []
    for setup in setups:
        try:
            full = [(s.index, s.side, s.stop) for s in generate_signals(frame, setup) if s.index < cutoff]
            prefix = [(s.index, s.side, s.stop) for s in generate_signals(frame.iloc[:cutoff + 1], setup)
                      if s.index < cutoff]
            changed = [(s.index, s.side, s.stop) for s in generate_signals(mutated, setup)
                       if s.index < cutoff]
        except Exception as exc:
            failures.append({"setup": setup, "error": str(exc)})
            continue
        if full != prefix or full != changed:
            failures.append({"setup": setup, "error": "prefix signals changed under truncation/future mutation"})
    return {"status": "PASS" if not failures else "FAIL", "setup_count": len(setups),
            "cutoff_index": cutoff, "failures": failures}


def _m2_path(side: str, entry: float, stop: float, future: pd.DataFrame,
             horizon: int, funding_times: np.ndarray, funding_rates: np.ndarray) -> dict:
    long_side = side == "long"
    if (long_side and stop >= entry) or (not long_side and stop <= entry):
        return {"m2_hit": False, "reason": "INVALID_ENTRY", "exit_price": entry,
                "exit_time_ms": int(future.t_open_ms.iloc[0]), "funding_sum": 0.0,
                "risk_pct": None, "target": None}
    risk = abs(entry - stop)
    risk_pct = risk / entry
    target = entry + (2 * risk if long_side else -2 * risk)
    reason = "TIMEOUT"
    exit_price = float(future.c.iloc[horizon - 1])
    exit_time = int(future.t_open_ms.iloc[horizon - 1]) + 3_600_000
    m2_hit = False
    for row in future.itertuples(index=False):
        stop_hit = (row.o <= stop or row.l <= stop) if long_side else (row.o >= stop or row.h >= stop)
        target_hit = (row.o >= target or row.h >= target) if long_side else (row.o <= target or row.l <= target)
        if stop_hit:
            reason = "STOP"
            gap_stop = row.o <= stop if long_side else row.o >= stop
            exit_price = float(row.o if gap_stop else stop)
            exit_time = int(row.t_open_ms) if gap_stop else int(row.t_open_ms) + 3_600_000
            break
        if target_hit:
            reason, m2_hit, exit_price = "TARGET", True, target
            gap_target = row.o >= target if long_side else row.o <= target
            exit_time = int(row.t_open_ms) if gap_target else int(row.t_open_ms) + 3_600_000
            break
    lo = np.searchsorted(funding_times, int(future.t_open_ms.iloc[0]), side="right")
    hi = np.searchsorted(funding_times, exit_time, side="right")
    funding_sum = float(np.sum(funding_rates[lo:hi]))
    return {"m2_hit": m2_hit, "reason": reason, "exit_price": exit_price,
            "exit_time_ms": exit_time, "funding_sum": funding_sum,
            "risk_pct": risk_pct, "target": target}


def _wilson(successes: int, count: int) -> list[float | None]:
    if count == 0:
        return [None, None]
    z = 1.959963984540054
    p = successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    margin = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [center - margin, center + margin]


def _summarize(records: list[dict], frozen_baseline: str | None = None) -> dict:
    if not records:
        return {"signals": 0, "m2_rate": None, "m2_wilson_95": [None, None],
                "m1_direction_accuracy": None, "coverage_pct": 0.0, "symbols": 0}
    hits = sum(bool(row["m2_hit"]) for row in records)
    interval = _wilson(hits, len(records))
    m1 = [row for row in records if row["m1_hit"] is not None]
    opportunities = records[0]["opportunity_count"] if records else 0
    coverage = 100 * len({(row["symbol"], row["signal_time_ms"]) for row in records}) / max(1, opportunities)
    out = {
        "signals": len(records), "m2_hits": hits, "m2_rate": hits / len(records),
        "m2_wilson_95": interval,
        "m1_direction_accuracy": (sum(bool(row["m1_hit"]) for row in m1) / len(m1) if m1 else None),
        "m1_scored": len(m1), "coverage_pct": coverage,
        "symbols": len({row["symbol"] for row in records}),
        "nonoverlap_symbol": 0, "nonoverlap_market": 0,
        "mean_net_base": float(np.mean([row["net_base"] for row in records if row["net_base"] is not None]))
        if any(row["net_base"] is not None for row in records) else None,
        "mean_net_stress": float(np.mean([row["net_stress"] for row in records if row["net_stress"] is not None]))
        if any(row["net_stress"] is not None for row in records) else None,
        "mean_r_base": float(np.mean([row["r_base"] for row in records if row["r_base"] is not None]))
        if any(row["r_base"] is not None for row in records) else None,
        "mean_r_stress": float(np.mean([row["r_stress"] for row in records if row["r_stress"] is not None]))
        if any(row["r_stress"] is not None for row in records) else None,
        "exit_reasons": {},
    }
    for row in records:
        out["exit_reasons"][row["exit_reason"]] = out["exit_reasons"].get(row["exit_reason"], 0) + 1
    for mode in ("base", "stress"):
        values = [row[f"net_{mode}"] for row in records if row[f"net_{mode}"] is not None]
        out[f"positive_net_{mode}_rate"] = sum(value > 0 for value in values) / len(values) if values else None
    if frozen_baseline:
        key = f"baseline_{frozen_baseline}_m2"
        out["frozen_baseline_direction"] = frozen_baseline
        out["frozen_baseline_m2_rate"] = sum(bool(row[key]) for row in records) / len(records)
        out["m2_lower_above_frozen_baseline"] = interval[0] > out["frozen_baseline_m2_rate"]
    return out


def _nonoverlap(records: list[dict], market_wide: bool) -> list[dict]:
    ordered = sorted(records, key=lambda row: (row["entry_time_ms"], row["symbol"], row["setup"]))
    result = []
    symbol_end: dict[str, int] = {}
    market_end = -1
    for row in ordered:
        if market_wide:
            if row["entry_time_ms"] <= market_end:
                continue
            market_end = row["window_end_ms"]
        else:
            if row["entry_time_ms"] <= symbol_end.get(row["symbol"], -1):
                continue
            symbol_end[row["symbol"]] = row["window_end_ms"]
        result.append(row)
    return result


def _iso_ms_to_index(times: np.ndarray, value: str) -> int:
    timestamp = int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    return int(np.searchsorted(times, timestamp, side="left"))


def _eligible_opportunities(times: np.ndarray, left: int, right: int, horizon: int) -> int:
    return sum(1 for index in range(max(0, len(times) - horizon))
               if left <= int(times[index]) < right and int(times[index + horizon]) < right)


def _score_symbol(symbol: str, frame: pd.DataFrame, funding_times: np.ndarray,
                  funding_rates: np.ndarray, split_bounds: dict[str, tuple[int, int]]) -> tuple[dict, int]:
    times = frame.t_open_ms.to_numpy(dtype=np.int64)
    closes = frame.c.to_numpy(dtype=float)
    atr = indicators.atr(frame.h.to_numpy(float), frame.l.to_numpy(float), closes, 14)
    result = {setup: {horizon: {split: [] for split in SPLITS} for horizon in HORIZONS}
              for setup in SETUPS}
    opportunities = {}
    for horizon in HORIZONS:
        for split, (left, right) in split_bounds.items():
            opportunities[(horizon, split)] = _eligible_opportunities(times, left, right, horizon)
    for setup in SETUPS:
        signals = generate_signals(frame, setup)
        for signal in signals:
            signal_index = int(signal.index)
            signal_ms = int(times[signal_index])
            split = next((name for name, (left, right) in split_bounds.items()
                          if left <= signal_ms < right), None)
            if split is None:
                continue
            for horizon in HORIZONS:
                if signal_index + horizon >= len(frame):
                    continue
                future = frame.iloc[signal_index + 1:signal_index + horizon + 1]
                if len(future) != horizon or int(future.t_open_ms.iloc[-1]) >= split_bounds[split][1]:
                    continue
                entry = float(future.o.iloc[0])
                side = str(signal.side)
                outcome = _m2_path(side, entry, float(signal.stop), future, horizon,
                                   funding_times, funding_rates)
                anchor = float(closes[signal_index])
                move = float(future.c.iloc[-1]) - anchor
                atr_value = float(atr[signal_index]) if np.isfinite(atr[signal_index]) else math.nan
                flat_band = .25 * atr_value * math.sqrt(horizon) if math.isfinite(atr_value) else math.inf
                actual = "flat" if abs(move) <= flat_band else "up" if move > 0 else "down"
                m1_hit = (actual == "up" if side == "long" else actual == "down")
                sign = 1 if side == "long" else -1
                if outcome["risk_pct"] is None:
                    gross = fee_base = fee_stress = None
                    r_base = r_stress = None
                    reason = outcome["reason"]
                    hit = False
                    net_base = net_stress = 0.0
                else:
                    gross = sign * (outcome["exit_price"] / entry - 1)
                    fee_base, fee_stress = BASE_FEE_RT, STRESS_FEE_RT
                    funding_pnl = -sign * outcome["funding_sum"]
                    net_base = gross - fee_base + funding_pnl
                    net_stress = gross - fee_stress + funding_pnl
                    r_base, r_stress = net_base / outcome["risk_pct"], net_stress / outcome["risk_pct"]
                    reason, hit = outcome["reason"], bool(outcome["m2_hit"])
                row = {
                    "setup": setup, "horizon_hours": horizon, "split": split,
                    "symbol": symbol, "side": side, "signal_index": signal_index,
                    "signal_time_ms": signal_ms, "entry_time_ms": int(times[signal_index + 1]),
                    "window_end_ms": int(times[signal_index + horizon]),
                    "exit_time_ms": int(outcome["exit_time_ms"]), "entry": entry,
                    "stop": float(signal.stop), "target": outcome["target"],
                    "risk_pct": outcome["risk_pct"], "exit_price": outcome["exit_price"],
                    "m2_hit": hit, "exit_reason": reason, "m1_actual": actual,
                    "m1_hit": bool(m1_hit) if math.isfinite(atr_value) else None,
                    "funding_rate_sum": outcome["funding_sum"],
                    "net_base": net_base, "net_stress": net_stress,
                    "r_base": r_base, "r_stress": r_stress,
                    "baseline_long_m2": None, "baseline_short_m2": None,
                    "opportunity_count": max(1, opportunities[(horizon, split)]),
                }
                for baseline_side, key in (("long", "baseline_long_m2"), ("short", "baseline_short_m2")):
                    baseline_stop = entry - abs(entry - float(signal.stop)) if baseline_side == "long" else entry + abs(entry - float(signal.stop))
                    baseline = _m2_path(baseline_side, entry, baseline_stop, future, horizon,
                                        funding_times, funding_rates)
                    row[key] = bool(baseline["m2_hit"])
                result[setup][horizon][split].append(row)
    return result, opportunities


def _write_ledger(path: Path, records: list[dict]) -> None:
    with path.open("wb") as binary:
        import gzip
        with gzip.GzipFile(fileobj=binary, mode="wb", mtime=0) as compressed:
            text = io.TextIOWrapper(compressed, encoding="utf-8", newline="")
            writer = csv.DictWriter(text, fieldnames=TRADE_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in records:
                writer.writerow(row)
            text.flush()
            text.detach()


def run(args) -> dict:
    started = datetime.now(timezone.utc)
    audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
    coverage = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    prereg_text = args.prereg.read_text(encoding="utf-8")
    prereg_hash = hashlib.sha256(prereg_text.encode("utf-8")).hexdigest()
    cohort = args.cohort
    symbols = coverage["cohorts_by_exact_run"].get(cohort)
    if not symbols:
        raise ValueError(f"coverage summary has no symbols for {cohort}")
    start_month, end_month = cohort.split("..", 1)
    y1, m1 = map(int, start_month.split("-")); y2, m2 = map(int, end_month.split("-"))
    months = []
    y, m = y1, m1
    while (y, m) <= (y2, m2):
        months.append(f"{y:04d}-{m:02d}")
        y, m = ((y + 1, 1) if m == 12 else (y, m + 1))

    selected_keys = {(symbol, month, kind) for symbol in symbols for month in months
                     for kind in ("klines_1h", "mark_price_1h", "funding")}
    selected_rows = [row for row in audit["archive_rows"]
                     if (row.get("symbol"), row.get("month"), row.get("kind")) in selected_keys]
    timestamp_audit = audit_cohort(audit, coverage, args.archive_root, cohort)
    if timestamp_audit["status"] != "PASS":
        raise ValueError(f"raw timestamp audit failed: {timestamp_audit}")
    hash_audit = verify_archives({"archive_rows": selected_rows}, args.archive_root)
    if hash_audit["status"] != "PASS":
        raise ValueError(f"selected archive hash audit failed: {hash_audit}")

    row_map = {(row["symbol"], row["month"], row["kind"]): row for row in selected_rows}
    first_values = [int(row_map[(symbol, start_month, "klines_1h")]["first_ms"])
                    for symbol in symbols]
    last_values = [int(row_map[(symbol, end_month, "klines_1h")]["last_ms"]) + 3_600_000
                   for symbol in symbols]
    common_start, common_end = max(first_values), min(last_values)
    all_rows: dict[str, dict[int, dict[str, list]]] = {}
    expected_times = None
    for symbol in symbols:
        frame, ft, fr = load_symbol(args.archive_root, symbol, months)
        frame = frame[(frame.t_open_ms >= common_start) & (frame.t_open_ms < common_end)].reset_index(drop=True)
        times = frame.t_open_ms.to_numpy(dtype=np.int64)
        if expected_times is None:
            expected_times = times
        elif not np.array_equal(expected_times, times):
            raise ValueError(f"symbols do not share a complete timestamp series: {symbol}")
        all_rows[symbol] = {"frame": frame, "funding_times": ft, "funding_rates": fr}
    if expected_times is None or not len(expected_times):
        raise ValueError("common cohort has no hourly bars")
    causal_audit = causal_future_mutation_check(all_rows[symbols[0]]["frame"])
    if causal_audit["status"] != "PASS":
        raise ValueError(f"causal future-mutation gate failed: {causal_audit}")

    selected_fingerprint = hashlib.sha256("\n".join(
        f"{row['symbol']}|{row['month']}|{row['kind']}|{row['sha256']}"
        for row in sorted(selected_rows, key=lambda item: (item["symbol"], item["month"], item["kind"]))
    ).encode()).hexdigest()
    if args.preflight_only:
        return {"status": "PREFLIGHT_PASS", "cohort": cohort, "symbols": len(symbols),
                "bars_per_symbol": len(expected_times), "period_start": _iso(common_start),
                "period_end_exclusive": _iso(common_end), "cells": len(SETUPS) * len(HORIZONS),
                "archive_hash_audit": hash_audit, "timestamp_audit": timestamp_audit,
                "causal_future_mutation": causal_audit,
                "preregistration_sha256": prereg_hash, "data_fingerprint": selected_fingerprint}

    split_bounds = {}
    for name, (left, right) in SPLITS.items():
        li, ri = _iso_ms_to_index(expected_times, left), _iso_ms_to_index(expected_times, right)
        if li >= ri:
            raise ValueError(f"empty split: {name}")
        split_bounds[name] = (int(expected_times[li]), int(expected_times[ri]) if ri < len(expected_times)
                              else common_end)
    aggregate = {setup: {horizon: {split: [] for split in SPLITS} for horizon in HORIZONS}
                 for setup in SETUPS}
    total_opportunities = {horizon: {split: 0 for split in SPLITS} for horizon in HORIZONS}
    for symbol in symbols:
        scored, opportunities = _score_symbol(symbol, all_rows[symbol]["frame"],
                                               all_rows[symbol]["funding_times"],
                                               all_rows[symbol]["funding_rates"], split_bounds)
        for setup in SETUPS:
            for horizon in HORIZONS:
                for split in SPLITS:
                    aggregate[setup][horizon][split].extend(scored[setup][horizon][split])
        for (horizon, split), count in opportunities.items():
            total_opportunities[horizon][split] += count
    for setup in SETUPS:
        for horizon in HORIZONS:
            for split in SPLITS:
                for row in aggregate[setup][horizon][split]:
                    row["opportunity_count"] = total_opportunities[horizon][split]

    # Select a single always-direction baseline using development only, equally weighting setups.
    frozen_baselines = {}
    baseline_development = {}
    for horizon in HORIZONS:
        per_setup = {side: [] for side in ("long", "short")}
        for setup in SETUPS:
            rows = aggregate[setup][horizon]["development"]
            if rows:
                for side in per_setup:
                    per_setup[side].append(sum(bool(row[f"baseline_{side}_m2"]) for row in rows) / len(rows))
        means = {side: float(np.mean(values)) if values else 0.0 for side, values in per_setup.items()}
        frozen_baselines[horizon] = max(means, key=lambda side: (means[side], side == "long"))
        baseline_development[horizon] = {"rates_equal_weighted_by_setup": means,
                                         "frozen_direction": frozen_baselines[horizon]}

    summary = {"cohort": cohort, "symbols": symbols, "bar_count_per_symbol": len(expected_times),
               "period_start": _iso(common_start), "period_end_exclusive": _iso(common_end),
               "splits": {name: {"start": _iso(bounds[0]), "end": _iso(bounds[1])}
                          for name, bounds in split_bounds.items()},
               "setups": list(SETUPS), "horizons_hours": list(HORIZONS),
               "causal_future_mutation": causal_audit,
               "baseline_development": baseline_development, "results": {}}
    ledger = []
    for setup in SETUPS:
        for horizon in HORIZONS:
            cell = {}
            for split in SPLITS:
                records = aggregate[setup][horizon][split]
                baseline = frozen_baselines[horizon] if split != "development" else None
                cell[split] = _summarize(records, baseline)
                cell[split]["nonoverlap_symbol"] = len(_nonoverlap(records, False))
                cell[split]["nonoverlap_market"] = len(_nonoverlap(records, True))
                for row in records:
                    ledger.append(row)
            oos = aggregate[setup][horizon]["validation"] + aggregate[setup][horizon]["sealed"]
            cell["combined_oos"] = _summarize(oos, frozen_baselines[horizon])
            cell["combined_oos"]["nonoverlap_symbol"] = len(_nonoverlap(oos, False))
            cell["combined_oos"]["nonoverlap_market"] = len(_nonoverlap(oos, True))
            summary["results"][f"{setup}|H{horizon}"] = cell

    code_paths = [Path(__file__), ROOT / "chart_predictor/setups.py",
                  ROOT / "chart_predictor/indicators.py", ROOT / "chart_predictor/scorer.py"]
    code_files = [{"ref": str(path.relative_to(ROOT)), "sha256": _sha256(path)} for path in code_paths]
    git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.strip()
    run_started = started.isoformat().replace("+00:00", "Z")
    frozen_at = datetime.fromtimestamp(args.prereg.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
    run_id = f"usdm1h-m2-{started.strftime('%Y%m%dT%H%M%SZ')}-{selected_fingerprint[:10]}"
    run_record = {
        "schema_version": 1, "run_id": run_id, "market": "crypto", "status": "complete",
        "frozen_at": frozen_at, "run_started_at": run_started,
        "preregistration_sha256": prereg_hash, "code_sha": git_sha, "code_files": code_files,
        "inputs": [{"role": "verified Binance USD-M 1h klines/mark/funding",
                    "ref": str(args.archive_root), "sha256": selected_fingerprint}],
        "period": {"start": _iso(common_start), "end": _iso(common_end)},
        "splits": {name: {"start": _iso(bounds[0]), "end": _iso(bounds[1]),
                           "reused_for_tuning": False} for name, bounds in split_bounds.items()},
        "cost_scenarios": {"base": {"fee_round_trip": BASE_FEE_RT, "slippage": "not modeled"},
                           "stress": {"fee_round_trip": STRESS_FEE_RT, "slippage": "not modeled"}},
        "execution": {"fill_rule": "next 1h open; unit notional; no leverage",
                      "same_bar_rule": "stop first; target-first event path; timeout is M2 failure",
                      "funding_rule": "signed archived funding after entry through exit, timestamp-aligned"},
        "counts": {"oos_issued_signals": sum(len(aggregate[setup][h][split])
                                               for setup in SETUPS for h in HORIZONS
                                               for split in ("validation", "sealed")),
                   "oos_nonoverlap_signals": sum(
                       len(_nonoverlap(aggregate[setup][h][split], False))
                       for setup in SETUPS for h in HORIZONS for split in ("validation", "sealed"))},
        "metrics": {},
        "note": "see summary.json for setup-by-horizon metrics; run-envelope aggregate metrics are computed below",
    }
    all_oos = [row for setup in SETUPS for horizon in HORIZONS
               for split in ("validation", "sealed")
               for row in aggregate[setup][horizon][split]]
    if not all_oos:
        raise ValueError("no complete OOS signals were emitted; no result artifact is written")
    m2_successes = sum(bool(row["m2_hit"]) for row in all_oos)
    m2_interval = _wilson(m2_successes, len(all_oos))
    m1_rows = [row for row in all_oos if row["m1_hit"] is not None]
    net_values = [row["net_stress"] for row in all_oos if row["net_stress"] is not None]
    run_record["metrics"] = {
        "m2_target_first_rate": m2_successes / len(all_oos) if all_oos else 0.0,
        "m2_wilson_95_low": m2_interval[0] if m2_interval[0] is not None else 0.0,
        "m2_wilson_95_high": m2_interval[1] if m2_interval[1] is not None else 1.0,
        "m1_direction_accuracy": (sum(bool(row["m1_hit"]) for row in m1_rows) / len(m1_rows)
                                   if m1_rows else 0.0),
        "net_expectancy": float(np.mean(net_values)) if net_values else 0.0,
    }
    run_record["note"] = ("study-wide descriptive aggregate across all setup/horizon cells; "
                          "not a candidate-level pass metric; see summary.json")
    contract_errors = validate_run_record(run_record)
    if contract_errors:
        raise ValueError(f"run envelope failed contract: {contract_errors}")
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists; refusing overwrite: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    summary["run_id"] = run_id
    summary["hash_audit"] = hash_audit
    summary["timestamp_audit"] = timestamp_audit
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "run.json").write_text(json.dumps(run_record, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    _write_ledger(args.output_dir / "trade_ledger.csv.gz", ledger)
    report_lines = ["# USD-M 1h setup M2 extension", "", f"Run ID: `{run_id}`", "",
                    f"- Symbols: {len(symbols)}", f"- Period: {_iso(common_start)} – {_iso(common_end)}",
                    f"- Setup × horizon cells: {len(SETUPS)} × {len(HORIZONS)} = {len(SETUPS)*len(HORIZONS)}",
                    "- Slippage/spread: not modeled; do not infer execution realism.", "",
                    "| Setup | H | Sealed M2 | Wilson 95% | N | Symbol non-overlap | Market non-overlap | Base net | Stress net | Baseline rate |",
                    "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for key, result in summary["results"].items():
        sealed = result["sealed"]
        interval = sealed["m2_wilson_95"]
        report_lines.append(
            f"| {key.rsplit('|H', 1)[0]} | {key.rsplit('H', 1)[1]} | "
            f"{sealed['m2_rate'] if sealed['m2_rate'] is not None else 'NA'} | "
            f"{interval} | {sealed['signals']} | {sealed['nonoverlap_symbol']} | "
            f"{sealed['nonoverlap_market']} | {sealed['mean_net_base']} | "
            f"{sealed['mean_net_stress']} | {sealed.get('frozen_baseline_m2_rate')} |"
        )
    (args.output_dir / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return {"run_id": run_id, "output_dir": str(args.output_dir), "symbols": len(symbols),
            "bars_per_symbol": len(expected_times), "cells": len(SETUPS) * len(HORIZONS),
            "ledger_rows": len(ledger), "status": "complete"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true",
                        help="verify archives and causal setup logic without scoring or writing results")
    args = parser.parse_args()
    try:
        result = run(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
