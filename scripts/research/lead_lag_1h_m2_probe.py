#!/usr/bin/env python3
"""One fixed, exposed-development-only BTC/ETH leader-lagger M2 screen."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.audit_usdm_timestamps import audit_cohort
from scripts.research.long_history_setup_m2_probe import load_symbol
from scripts.research.verify_usdm_archives import verify as verify_archives

HOUR_MS = 3_600_000
HORIZON = 10
ATR_PERIOD = 14
BASE_FEE_RT = 0.001
STRESS_FEE_RT = 0.003
COHORT = "2023-03..2026-05"
DEV_START = "2023-03-23T15:00:00Z"
DEV_END = "2025-03-01T00:00:00Z"
DEV_START_MS = 1_679_583_600_000
DEV_END_MS = 1_740_787_200_000
PREREG_DEFAULT = ROOT / "docs/research/inventory/PREREG_LEAD_LAG_1H_M2_ROUNDK_20261120.md"
LEDGER_FIELDS = [
    "signal_id", "symbol", "side", "signal_time_ms", "entry_time_ms",
    "exit_time_ms", "signal_return_btc", "signal_return_eth",
    "signal_return_alt", "risk", "risk_fraction", "entry", "target",
    "stop", "exit_price", "exit_reason", "m2_hit", "m1_actual", "m1_hit", "gross_return",
    "funding_cost", "net_base", "net_stress", "baseline_long_m2",
    "baseline_short_m2", "baseline_long_net_base", "baseline_short_net_base",
]


def signal_side(r_btc: float, r_eth: float, r_alt: float) -> int:
    """Return +1/-1 for the preregistered leader-consensus lagger rule."""
    values = (r_btc, r_eth, r_alt)
    if not all(math.isfinite(float(value)) for value in values):
        return 0
    leader_mean = (r_btc + r_eth) / 2.0
    if r_btc > 0.0 and r_eth > 0.0 and r_alt < leader_mean:
        return 1
    if r_btc < 0.0 and r_eth < 0.0 and r_alt > leader_mean:
        return -1
    return 0


def atr14_sma(
    high: Sequence[float], low: Sequence[float], close: Sequence[float], index: int
) -> float | None:
    """SMA of 14 completed true ranges ending at ``index`` inclusive."""
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    if not (high.ndim == low.ndim == close.ndim == 1 and len(high) == len(low) == len(close)):
        raise ValueError("OHLC arrays must be one-dimensional and equal length")
    if index < ATR_PERIOD or index >= len(close):
        return None
    start = index - ATR_PERIOD + 1
    prior_close = close[start - 1:index]
    highs, lows = high[start:index + 1], low[start:index + 1]
    tr = np.maximum.reduce((highs - lows, np.abs(highs - prior_close), np.abs(lows - prior_close)))
    if not np.isfinite(tr).all() or np.any(tr < 0.0):
        return None
    value = float(np.mean(tr))
    return value if math.isfinite(value) and value > 0.0 else None


def evaluate_path(
    side: int,
    entry: float,
    risk: float,
    bars: Sequence[Mapping[str, float]],
    funding_times: Sequence[int],
    funding_rates: Sequence[float],
    *,
    fee_rate: float = BASE_FEE_RT,
) -> dict[str, float | int | str | bool]:
    """Evaluate a fixed 1R/1R bracket over 10 contract-price hourly bars."""
    if side not in (-1, 1):
        raise ValueError("side must be -1 or +1")
    if not all(math.isfinite(float(x)) for x in (entry, risk, fee_rate)) or entry <= 0 or risk <= 0:
        raise ValueError("entry and risk must be positive and fee finite")
    if len(bars) != HORIZON:
        raise ValueError("exactly ten complete future bars are required")
    ft = np.asarray(funding_times, dtype=np.int64)
    fr = np.asarray(funding_rates, dtype=np.float64)
    if len(ft) != len(fr) or (len(ft) > 1 and np.any(np.diff(ft) <= 0)):
        raise ValueError("funding timestamps must be sorted, unique, and paired with rates")
    if not np.isfinite(fr).all():
        raise ValueError("funding rates must be finite")
    times = [int(row["open_time_ms"]) for row in bars]
    if any(times[i] - times[i - 1] != HOUR_MS for i in range(1, len(times))):
        return {"reason": "DATA_GAP", "m2_hit": False, "exit_price": math.nan,
                "exit_index": -1, "funding_cost": 0.0, "gross_return": math.nan,
                "net_return": math.nan, "risk_fraction": risk / entry}
    sign = int(side)
    stop = entry - sign * risk
    target = entry + sign * risk
    reason = "TIMEOUT"
    exit_price = float(bars[-1]["c"])
    exit_index = HORIZON - 1
    for i, bar in enumerate(bars):
        o, h, low, close = (float(bar[k]) for k in ("o", "h", "l", "c"))
        if not all(math.isfinite(x) for x in (o, h, low, close)) or low > min(o, close) or h < max(o, close) or low > h:
            raise ValueError("invalid contract OHLC bar")
        stop_gap = o <= stop if sign == 1 else o >= stop
        target_gap = o >= target if sign == 1 else o <= target
        stop_touch = stop_gap or (low <= stop if sign == 1 else h >= stop)
        target_touch = target_gap or (h >= target if sign == 1 else low <= target)
        if stop_touch:  # conservative stop-first ordering, including double touch
            reason = "STOP_GAP" if stop_gap else "STOP"
            exit_price = o if stop_gap else stop
            exit_index = i
            break
        if target_touch:
            reason = "TARGET"
            exit_price = target  # conservative target-price credit, even on a gap
            exit_index = i
            break

    entry_time = times[0]
    exit_bar_open = times[exit_index]
    exit_bar_close = exit_bar_open + HOUR_MS
    lo = int(np.searchsorted(ft, entry_time, side="right"))
    hi = int(np.searchsorted(ft, exit_bar_close, side="right"))
    funding_cost = 0.0
    for timestamp, rate in zip(ft[lo:hi], fr[lo:hi]):
        signed_cost = sign * float(rate)
        # Same-bar settlement/exit chronology is unknown: charge payments,
        # never credit receipts. Earlier settlements are fully included.
        if int(timestamp) >= exit_bar_open:
            signed_cost = max(signed_cost, 0.0)
        funding_cost += signed_cost
    gross = sign * (exit_price - entry) / entry
    return {
        "reason": reason,
        "m2_hit": reason == "TARGET",
        "exit_price": exit_price,
        "exit_index": exit_index,
        "entry_time_ms": entry_time,
        "exit_time_ms": exit_bar_close,
        "target": target,
        "stop": stop,
        "funding_cost": funding_cost,
        "gross_return": gross,
        "risk_fraction": risk / entry,
        "net_return": gross - fee_rate - funding_cost,
        "net_r": (gross - fee_rate - funding_cost) / (risk / entry),
    }


def per_symbol_nonoverlap(rows: Sequence[Mapping], horizon_ms: int) -> list[dict]:
    selected: list[dict] = []
    last_entry: dict[str, int] = {}
    for row in sorted(rows, key=lambda r: (int(r["signal_time_ms"]), str(r["symbol"]))):
        symbol, entry = str(row["symbol"]), int(row["entry_time_ms"])
        if entry < last_entry.get(symbol, -1):
            continue
        selected.append(dict(row))
        last_entry[symbol] = entry + horizon_ms
    return selected


def market_time_nonoverlap(rows: Sequence[Mapping], horizon_ms: int) -> list[dict]:
    selected: list[dict] = []
    last_entry = -1
    for row in sorted(rows, key=lambda r: (int(r["entry_time_ms"]), str(r["symbol"]))):
        entry = int(row["entry_time_ms"])
        if entry < last_entry:
            continue
        selected.append(dict(row))
        last_entry = entry + horizon_ms
    return selected


def _wilson(successes: int, count: int) -> list[float | None]:
    if count == 0:
        return [None, None]
    z = 1.959963984540054
    p = successes / count
    den = 1.0 + z * z / count
    center = (p + z * z / (2.0 * count)) / den
    margin = z * math.sqrt(p * (1.0 - p) / count + z * z / (4.0 * count * count)) / den
    return [center - margin, center + margin]


def _stats(rows: Sequence[Mapping]) -> dict:
    n = len(rows)
    hits = sum(bool(row["m2_hit"]) for row in rows)
    return {
        "signals": n,
        "m2_hits": hits,
        "m2_rate": hits / n if n else None,
        "m2_wilson_95": _wilson(hits, n),
        "m1_direction_accuracy": sum(bool(row.get("m1_hit")) for row in rows) / n if n else None,
        "exit_reasons": {reason: sum(row["exit_reason"] == reason for row in rows)
                         for reason in ("TARGET", "STOP", "STOP_GAP", "TIMEOUT", "DATA_GAP")},
        "mean_gross_return": float(np.mean([float(row["gross_return"]) for row in rows])) if n else None,
        "mean_net_base": float(np.mean([float(row["net_base"]) for row in rows])) if n else None,
        "mean_net_stress": float(np.mean([float(row["net_stress"]) for row in rows])) if n else None,
        "mean_net_base_r": float(np.mean([float(row["net_base_r"]) for row in rows])) if n else None,
        "mean_net_stress_r": float(np.mean([float(row["net_stress_r"]) for row in rows])) if n else None,
        "mean_funding_cost": float(np.mean([float(row["funding_cost"]) for row in rows])) if n else None,
        "symbols": len({str(row["symbol"]) for row in rows}),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _month_range(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    last_year, last_month = map(int, end.split("-"))
    result = []
    while (year, month) <= (last_year, last_month):
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _write_gzip_csv(path: Path, rows: Sequence[Mapping]) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            text = io.TextIOWrapper(compressed, encoding="utf-8", newline="")
            writer = csv.DictWriter(text, fieldnames=LEDGER_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            text.flush()
            text.detach()


def _signal_event(
    symbol: str,
    index: int,
    series: Mapping[str, np.ndarray],
    btc: Mapping[str, np.ndarray],
    eth: Mapping[str, np.ndarray],
    funding_times: np.ndarray,
    funding_rates: np.ndarray,
) -> dict | None:
    times = series["times"]
    if index < ATR_PERIOD or index + HORIZON >= len(times):
        return None
    # Signals use completed bar index; the next bar is the entry bar.
    r_btc = float(btc["c"][index] / btc["c"][index - 1] - 1.0)
    r_eth = float(eth["c"][index] / eth["c"][index - 1] - 1.0)
    r_alt = float(series["c"][index] / series["c"][index - 1] - 1.0)
    side = signal_side(r_btc, r_eth, r_alt)
    if side == 0:
        return None
    future_indices = np.arange(index + 1, index + HORIZON + 1, dtype=np.int64)
    if not np.array_equal(times[future_indices], times[index] + HOUR_MS * np.arange(1, HORIZON + 1)):
        return {"symbol": symbol, "signal_time_ms": int(times[index] + HOUR_MS),
                "entry_time_ms": int(times[index + 1]), "side": "long" if side == 1 else "short",
                "invalid_reason": "DATA_GAP", "m2_hit": False, "m1_actual": "UNSCORABLE",
                "m1_hit": False, "exit_reason": "DATA_GAP", "gross_return": 0.0,
                "funding_cost": 0.0, "net_base": 0.0, "net_stress": 0.0,
                "net_base_r": 0.0, "net_stress_r": 0.0}
    risk = atr14_sma(series["h"], series["l"], series["c"], index)
    if risk is None:
        return None
    bars = [
        {"open_time_ms": int(times[j]), "o": float(series["o"][j]),
         "h": float(series["h"][j]), "l": float(series["l"][j]), "c": float(series["c"][j])}
        for j in future_indices
    ]
    entry = float(bars[0]["o"])
    main = evaluate_path(side, entry, risk, bars, funding_times, funding_rates, fee_rate=BASE_FEE_RT)
    stress = evaluate_path(side, entry, risk, bars, funding_times, funding_rates, fee_rate=STRESS_FEE_RT)
    baseline_long = evaluate_path(1, entry, risk, bars, funding_times, funding_rates, fee_rate=BASE_FEE_RT)
    baseline_short = evaluate_path(-1, entry, risk, bars, funding_times, funding_rates, fee_rate=BASE_FEE_RT)
    close_signal = float(series["c"][index])
    close_exit = float(bars[-1]["c"])
    m1_delta = close_exit / close_signal - 1.0
    m1_band = 0.25 * risk / close_signal * math.sqrt(HORIZON)
    m1_actual = "flat" if abs(m1_delta) <= m1_band else ("up" if m1_delta > 0 else "down")
    m1_move = (m1_actual == "up" and side == 1) or (m1_actual == "down" and side == -1)
    signal_time = int(times[index] + HOUR_MS)
    return {
        "signal_id": f"{symbol}:{signal_time}:{'L' if side == 1 else 'S'}",
        "symbol": symbol,
        "side": "long" if side == 1 else "short",
        "signal_time_ms": signal_time,
        "entry_time_ms": int(times[index + 1]),
        "exit_time_ms": int(main["exit_time_ms"]),
        "signal_return_btc": r_btc,
        "signal_return_eth": r_eth,
        "signal_return_alt": r_alt,
        "risk": risk,
        "risk_fraction": float(main["risk_fraction"]),
        "entry": entry,
        "target": float(main["target"]),
        "stop": float(main["stop"]),
        "exit_price": float(main["exit_price"]),
        "exit_reason": str(main["reason"]),
        "m2_hit": bool(main["m2_hit"]),
        "m1_hit": bool(m1_move),
        "m1_actual": m1_actual,
        "gross_return": float(main["gross_return"]),
        "funding_cost": float(main["funding_cost"]),
        "net_base": float(main["net_return"]),
        "net_stress": float(stress["net_return"]),
        "net_base_r": float(main["net_r"]),
        "net_stress_r": float(stress["net_r"]),
        "baseline_long_m2": bool(baseline_long["m2_hit"]),
        "baseline_short_m2": bool(baseline_short["m2_hit"]),
        "baseline_long_net_base": float(baseline_long["net_return"]),
        "baseline_short_net_base": float(baseline_short["net_return"]),
    }


def run(args) -> dict:
    audit = json.loads(args.audit_json.read_text(encoding="utf-8"))
    coverage = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    prereg_text = args.prereg.read_text(encoding="utf-8")
    prereg_hash = hashlib.sha256(prereg_text.encode("utf-8")).hexdigest()
    symbols = coverage["cohorts_by_exact_run"].get(COHORT)
    if not symbols or "BTCUSDT" not in symbols or "ETHUSDT" not in symbols:
        raise ValueError("frozen common cohort is missing or lacks BTC/ETH leaders")
    target_symbols = [symbol for symbol in symbols if symbol not in {"BTCUSDT", "ETHUSDT"}]
    months = _month_range("2023-03", "2025-02")  # scoring never opens later outcome months
    dev_coverage = {"cohorts_by_exact_run": {"2023-03..2025-02": symbols}}
    dev_key = "2023-03..2025-02"
    timestamp_audit = audit_cohort(audit, dev_coverage, args.archive_root, dev_key)
    if timestamp_audit["status"] != "PASS":
        raise ValueError(f"development archive timestamp/mark/funding audit failed: {timestamp_audit}")
    selected_keys = {(symbol, month, kind) for symbol in symbols for month in months
                     for kind in ("klines_1h", "mark_price_1h", "funding")}
    selected_rows = [row for row in audit["archive_rows"]
                     if (row.get("symbol"), row.get("month"), row.get("kind")) in selected_keys]
    hash_audit = verify_archives({"archive_rows": selected_rows}, args.archive_root)
    if hash_audit["status"] != "PASS":
        raise ValueError(f"development archive SHA-256 audit failed: {hash_audit}")
    loaded: dict[str, dict] = {}
    for symbol in symbols:
        frame, funding_times, funding_rates = load_symbol(args.archive_root, symbol, months)
        frame = frame[(frame.t_open_ms >= DEV_START_MS - 21 * 24 * HOUR_MS)
                      & (frame.t_open_ms < DEV_END_MS)].reset_index(drop=True)
        times = frame.t_open_ms.to_numpy(dtype=np.int64)
        loaded[symbol] = {
            "times": times,
            "o": frame.o.to_numpy(dtype=np.float64),
            "h": frame.h.to_numpy(dtype=np.float64),
            "l": frame.l.to_numpy(dtype=np.float64),
            "c": frame.c.to_numpy(dtype=np.float64),
            "funding_times": funding_times,
            "funding_rates": funding_rates,
        }
    common_start = max(int(item["times"][0]) for item in loaded.values())
    common_end = min(int(item["times"][-1]) for item in loaded.values())
    times_ref = np.arange(common_start, common_end + HOUR_MS, HOUR_MS, dtype=np.int64)
    for symbol, item in loaded.items():
        positions = np.searchsorted(item["times"], times_ref)
        if np.any(positions >= len(item["times"])) or not np.array_equal(item["times"][positions], times_ref):
            raise ValueError(f"selected symbols have a missing hourly timestamp in common window: {symbol}")
        for key in ("o", "h", "l", "c"):
            item[key] = item[key][positions]
        item["times"] = times_ref
    btc, eth = loaded["BTCUSDT"], loaded["ETHUSDT"]
    eligible = 0
    rows: list[dict] = []
    invalid_rows: list[dict] = []
    for i, signal_open_ms in enumerate(times_ref):
        signal_close_ms = int(signal_open_ms) + HOUR_MS
        if signal_close_ms < DEV_START_MS or signal_close_ms >= DEV_END_MS:
            continue
        if i < ATR_PERIOD or i + HORIZON >= len(times_ref):
            continue
        if int(times_ref[i + HORIZON]) + HOUR_MS > DEV_END_MS:
            continue
        for symbol in target_symbols:
            series = loaded[symbol]
            # The full common timestamp grid, closed bars, feature warmup, and
            # complete ten-hour future path define one opportunity per symbol-hour.
            eligible += 1
            event = _signal_event(symbol, i, series, btc, eth,
                                  series["funding_times"], series["funding_rates"])
            if event is None:
                continue
            if event.get("invalid_reason"):
                event["signal_return_btc"] = float(btc["c"][i] / btc["c"][i - 1] - 1.0)
                event["signal_return_eth"] = float(eth["c"][i] / eth["c"][i - 1] - 1.0)
                event["signal_return_alt"] = float(series["c"][i] / series["c"][i - 1] - 1.0)
                event["risk"] = math.nan
                event["risk_fraction"] = math.nan
                event["entry"] = math.nan
                event["target"] = math.nan
                event["stop"] = math.nan
                event["exit_price"] = math.nan
                invalid_rows.append(event)
                continue
            rows.append(event)
    rows.sort(key=lambda row: (int(row["signal_time_ms"]), str(row["symbol"])))
    for row in rows:
        row["coverage_denominator"] = eligible
    per_symbol = per_symbol_nonoverlap(rows, HORIZON * HOUR_MS)
    market_nonoverlap = market_time_nonoverlap(rows, HORIZON * HOUR_MS)
    by_symbol = {}
    for symbol in target_symbols:
        symbol_rows = [row for row in rows if row["symbol"] == symbol]
        by_symbol[symbol] = _stats(symbol_rows)
        by_symbol[symbol]["eligible_opportunities"] = sum(
            1 for i, t in enumerate(times_ref)
            if i >= ATR_PERIOD
            and DEV_START_MS <= int(t) + HOUR_MS < DEV_END_MS
            and int(t) + HOUR_MS * (HORIZON + 1) <= DEV_END_MS
            and np.searchsorted(times_ref, int(t) + HOUR_MS * HORIZON, side="left") < len(times_ref)
        )
        by_symbol[symbol]["coverage"] = (
            by_symbol[symbol]["signals"] / by_symbol[symbol]["eligible_opportunities"]
            if by_symbol[symbol]["eligible_opportunities"] else 0.0
        )
    all_stats = _stats(rows)
    all_stats["eligible_opportunities"] = eligible
    all_stats["coverage"] = len(rows) / eligible if eligible else 0.0
    all_stats["per_symbol_nonoverlap"] = _stats(per_symbol)
    all_stats["market_time_nonoverlap"] = _stats(market_nonoverlap)
    all_stats["per_symbol_nonoverlap_symbols"] = len({row["symbol"] for row in per_symbol})
    all_stats["market_time_nonoverlap_symbols"] = len({row["symbol"] for row in market_nonoverlap})
    all_stats["baseline_long_m2"] = sum(bool(row["baseline_long_m2"]) for row in rows) / len(rows) if rows else None
    all_stats["baseline_long_m2_wilson_95"] = _wilson(
        sum(bool(row["baseline_long_m2"]) for row in rows), len(rows))
    all_stats["baseline_short_m2"] = sum(bool(row["baseline_short_m2"]) for row in rows) / len(rows) if rows else None
    all_stats["baseline_short_m2_wilson_95"] = _wilson(
        sum(bool(row["baseline_short_m2"]) for row in rows), len(rows))
    all_stats["baseline_long_net_base"] = float(np.mean([row["baseline_long_net_base"] for row in rows])) if rows else None
    all_stats["baseline_short_net_base"] = float(np.mean([row["baseline_short_net_base"] for row in rows])) if rows else None
    all_stats["baseline_stronger_m2_rate_report_only"] = max(
        [x for x in (all_stats["baseline_long_m2"], all_stats["baseline_short_m2"]) if x is not None],
        default=None,
    )
    numeric_gates = {
        "all_issued_m2_80pct": bool(all_stats["m2_rate"] is not None and all_stats["m2_rate"] >= 0.80),
        "per_symbol_nonoverlap_n_200": len(per_symbol) >= 200,
        "per_symbol_nonoverlap_at_least_20_symbols": all_stats["per_symbol_nonoverlap_symbols"] >= 20,
        "coverage_10pct": all_stats["coverage"] >= 0.10,
        "positive_net_base_and_stress": bool(all_stats["mean_net_base"] is not None
                                               and all_stats["mean_net_base"] > 0
                                               and all_stats["mean_net_stress"] > 0),
        "wilson_lower_above_stronger_same_event_baseline": bool(
            all_stats["m2_wilson_95"][0] is not None
            and all_stats["baseline_stronger_m2_rate_report_only"] is not None
            and all_stats["m2_wilson_95"][0] > all_stats["baseline_stronger_m2_rate_report_only"]
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    _write_gzip_csv(args.output_dir / "event_ledger.csv.gz", rows)
    _write_gzip_csv(args.output_dir / "invalid_events.csv.gz", invalid_rows)
    (args.output_dir / "summary.json").write_text(json.dumps({
        "status": "EXPLORATORY_DEVELOPMENT_ONLY",
        "strategy_verdict": "SCREEN_NUMERIC_GATES_MET_FORWARD_ONLY_REVIEW_REQUIRED"
        if all(numeric_gates.values()) else "REJECT_FIXED_SPECIFICATION",
        "numeric_screen_gates": numeric_gates,
        "trial_count": 1,
        "data_exposed": True,
        "core_eligible": False,
        "phase9_eligible": False,
        "window": {"start": DEV_START, "end_exclusive": DEV_END},
        "cohort": {"key": COHORT, "symbols": len(symbols), "target_symbols": target_symbols},
        "horizon_hours": HORIZON,
        "barrier_basis": "contract kline OHLC; mark archives used in integrity audit only",
        "base_fee_round_trip": BASE_FEE_RT,
        "stress_fee_round_trip": STRESS_FEE_RT,
        "slippage": "not measured or modeled",
        "timestamp_audit": timestamp_audit,
        "sha256_audit": hash_audit,
        "invalid_candidate_events_due_to_gap": len(invalid_rows),
        "all_issued": all_stats,
        "by_symbol": by_symbol,
        "prereg_sha256": prereg_hash,
        "runner_sha256": _sha256_file(Path(__file__)),
        "git_sha_at_run": _git_sha(),
        "input_archive_rows": len(selected_rows),
        "input_fingerprint_sha256": hashlib.sha256(json.dumps(
            sorted((row["kind"], row["symbol"], row["month"], row["sha256"]) for row in selected_rows),
            separators=(",", ":"),
        ).encode()).hexdigest(),
        "reproduction_command": " ".join(sys.argv),
        "limitations": [
            "Exposed development history; not sealed OOS, validation, or Core evidence.",
            "36-symbol cohort is not a point-in-time universe and may have survivorship bias.",
            "Legacy fee proxies do not include measured spread/slippage.",
            "Hourly OHLC cannot identify intrabar event order; stop-first is conservative.",
            "Signals across altcoins share market shocks; market-time clusters are separately reported.",
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return json.loads((args.output_dir / "summary.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, default=PREREG_DEFAULT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": summary["status"], "verdict": summary["strategy_verdict"],
                      "all_issued": summary["all_issued"],
                      "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
