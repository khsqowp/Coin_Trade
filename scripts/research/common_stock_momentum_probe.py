#!/usr/bin/env python3
"""Fixed-cost common-panel exploratory replay of existing KR/US momentum rules.

This reads the ignored local KIS CSV cache and writes only to a new explicit
output directory. It is descriptive historical evidence, not valid OOS proof.
"""
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

from scripts.research.equity_trend_gate_probe import KR_ETFS


EXPECTED = {
    "KR": {"count": 832, "start": "2023-01-05", "end": "2026-08-06"},
    "US": {"count": 1187, "start": "2021-07-29", "end": "2026-11-12"},
}
INVERSE_SYMBOLS = {"KR": {"114800"}, "US": {"SH"}}
COSTS = {
    "KR": {
        "base": {"fee": 0.00065, "slippage": 0.0005, "sell_tax": 0.002},
        "stress": {"fee": 0.00115, "slippage": 0.0005, "sell_tax": 0.002},
    },
    "US": {
        "base": {"fee": 0.0008, "slippage": 0.001, "sell_tax": 0.0},
        "stress": {"fee": 0.0036, "slippage": 0.0025, "sell_tax": 0.0},
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_panel(cache: Path, market: str, excluded: set[str] | None = None) -> tuple[list[str], pd.DatetimeIndex, np.ndarray, list[dict]]:
    excluded = excluded or set()
    frames: dict[str, pd.DataFrame] = {}
    inputs = []
    for path in sorted(cache.glob(f"{market}_*.csv")):
        symbol = path.stem[len(market) + 1:]
        if symbol in excluded:
            continue
        frame = pd.read_csv(path, parse_dates=["timestamp"])
        required = {"timestamp", "Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(frame.columns):
            raise ValueError(f"missing required columns: {path.name}")
        if frame.timestamp.duplicated().any():
            raise ValueError(f"duplicate timestamps: {path.name}")
        values = frame[["Open", "High", "Low", "Close", "Volume"]].to_numpy(float)
        open_, high, low, close, volume = values.T
        valid = (np.isfinite(values).all(axis=1) & (volume > 0) & (open_ > 0) &
                 (close > 0) & (high >= np.maximum(open_, close)) &
                 (low <= np.minimum(open_, close)) & (high >= low))
        clean = frame.loc[valid, ["timestamp", "Close"]].copy()
        clean = clean.set_index("timestamp").sort_index()
        frames[symbol] = clean
        inputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path),
                       "rows": int(len(frame)), "eligible_rows": int(valid.sum()),
                       "zero_or_invalid_rows": int((~valid).sum())})
    expected_files = 92 - len(excluded)
    if len(frames) != expected_files:
        raise ValueError(f"expected {expected_files} eligible {market} files, got {len(frames)}")
    symbols = sorted(frames)
    if market == "KR" and "069500" not in frames:
        raise ValueError("KR benchmark 069500 is absent")
    if market == "US" and "SPY" not in frames:
        raise ValueError("US benchmark SPY is absent")
    common = set(frames[symbols[0]].index)
    for frame in frames.values():
        common.intersection_update(frame.index)
    dates = pd.DatetimeIndex(sorted(common))
    if len(dates) != EXPECTED[market]["count"] or dates[0].date().isoformat() != EXPECTED[market]["start"] or dates[-1].date().isoformat() != EXPECTED[market]["end"]:
        raise ValueError(f"eligible common panel drifted: {market} {len(dates)} {dates[0]}..{dates[-1]}")
    close = np.column_stack([frames[symbol].reindex(dates).Close.to_numpy(float) for symbol in symbols])
    if not np.isfinite(close).all() or (close <= 0).any():
        raise ValueError(f"invalid price in common panel: {market}")
    return symbols, dates, close, inputs


def _daily_metrics(dates: pd.DatetimeIndex, nav: np.ndarray, returns: np.ndarray) -> dict:
    if len(nav) < 2 or not np.isfinite(nav).all() or (nav <= 0).any():
        raise ValueError("NAV is nonpositive, nonfinite, or too short")
    years = (dates[-1] - dates[0]).total_seconds() / (365.2425 * 86400)
    cagr = nav[-1] ** (1 / years) - 1 if years > 0 else math.nan
    peaks = np.maximum.accumulate(nav)
    mdd = float(np.max(1 - nav / peaks))
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * math.sqrt(252)) if std > 0 else 0.0
    annual = {}
    for year in sorted(set(d.year for d in dates[1:])):
        idx = [i for i, day in enumerate(dates) if day.year == year and i > 0]
        if idx:
            annual[str(year)] = float(np.prod(1 + returns[np.asarray(idx) - 1]) - 1)
    return {"start": dates[0].isoformat(), "end": dates[-1].isoformat(),
            "cagr": float(cagr), "mdd": mdd, "sharpe": sharpe,
            "annual_returns": annual, "ending_nav": float(nav[-1])}


def simulate(symbols: list[str], dates: pd.DatetimeIndex, close: np.ndarray,
             market: str, lookback: int, cadence: str, gate: bool,
             cost: dict, baseline: bool = False,
             start_index: int | None = None) -> tuple[dict, list[dict], list[dict], list[dict]]:
    name_to_col = {symbol: i for i, symbol in enumerate(symbols)}
    benchmark = "069500" if market == "KR" else "SPY"
    benchmark_col = name_to_col[benchmark]
    start = lookback + 1
    first_trade_index = start if start_index is None else start_index
    if first_trade_index < start or first_trade_index >= len(dates):
        raise ValueError(f"invalid first trade index={first_trade_index} for lookback={lookback}")
    if first_trade_index + 2 >= len(dates):
        raise ValueError(f"not enough sessions for {market} lookback={lookback}")
    month_periods = dates.tz_localize(None).to_period("M") if dates.tz is not None else dates.to_period("M")
    month = pd.Series(np.arange(len(dates)), index=dates).groupby(month_periods).last().to_numpy()
    month_ends = set(int(i) for i in month)
    rebalance = set(range(start, len(dates))) if cadence == "daily" else {
        int(i + 1) for i in month_ends if start <= i + 1 < len(dates)
    }
    nav_dates = [dates[first_trade_index - 1]]
    nav_values = [1.0]
    nav_returns: list[float] = []
    cash = 1.0
    shares = np.zeros(len(symbols), dtype=float)
    taxable = np.array([0.0 if market == "KR" and s in KR_ETFS else 1.0 for s in symbols])
    events: list[dict] = []
    round_trips: list[dict] = []
    open_dates: dict[str, str] = {}
    cumulative_turnover = 0.0
    exposure_values = []
    for i in range(first_trade_index, len(dates)):
        prices = close[i]
        nav_before_trade = cash + float(np.dot(shares, prices))
        target_weights = np.zeros(len(symbols), dtype=float)
        should_trade = i == first_trade_index if baseline else i in rebalance
        signal_idx = i - 1
        if should_trade:
            if baseline:
                selected = list(range(len(symbols)))
                target_weights[selected] = 1 / len(selected)
            else:
                risk_off = False
                if gate:
                    if signal_idx < 199:
                        risk_off = True
                    else:
                        sma = float(close[signal_idx - 199:signal_idx + 1, benchmark_col].mean())
                        risk_off = close[signal_idx, benchmark_col] <= sma
                if not risk_off:
                    momentum = close[signal_idx] / close[signal_idx - lookback] - 1
                    order = np.lexsort((np.asarray(symbols), -momentum))
                    selected = order[:10]
                    target_weights[selected] = 1 / len(selected)

            current_value = shares * prices

            def candidate(scale: float) -> tuple[np.ndarray, float, float, float, float]:
                desired = target_weights * nav_before_trade * scale
                delta = desired - current_value
                buys = np.maximum(delta, 0.0)
                sells = np.maximum(-delta, 0.0)
                buy_value, sell_value = float(buys.sum()), float(sells.sum())
                fee_rate = cost["fee"] + cost["slippage"]
                charges = fee_rate * (buy_value + sell_value) + cost["sell_tax"] * float(np.dot(sells, taxable))
                final_cash = cash + sell_value - buy_value - charges
                return desired, buy_value, sell_value, charges, final_cash

            desired, buy_value, sell_value, charges, final_cash = candidate(1.0)
            scale = 1.0
            if final_cash < -1e-12:
                lo, hi = 0.0, 1.0
                for _ in range(64):
                    mid = (lo + hi) / 2
                    if candidate(mid)[4] >= 0:
                        lo = mid
                    else:
                        hi = mid
                scale = lo
                desired, buy_value, sell_value, charges, final_cash = candidate(scale)
            old_shares = shares.copy()
            new_shares = desired / prices
            for j, symbol in enumerate(symbols):
                old_open, new_open = old_shares[j] > 1e-12, new_shares[j] > 1e-12
                if not old_open and new_open:
                    open_dates[symbol] = dates[i].date().isoformat()
                elif old_open and not new_open:
                    round_trips.append({"symbol": symbol, "entry_date": open_dates.pop(symbol),
                                        "exit_date": dates[i].date().isoformat(),
                                        "exit_reason": "rebalance_or_gate"})
            cash = final_cash
            shares = new_shares
            cumulative_turnover += (buy_value + sell_value) / 2
            events.append({"date": dates[i].isoformat(), "signal_date": dates[signal_idx].isoformat(),
                           "selected": ";".join(symbols[j] for j in np.flatnonzero(target_weights)),
                           "gate_cash": bool(gate and target_weights.sum() == 0),
                           "buy_notional": buy_value, "sell_notional": sell_value,
                           "costs": charges, "scale_for_cash": scale,
                           "cash_after": cash, "nav_before_trade": nav_before_trade})
        nav_after = cash + float(np.dot(shares, prices))
        if not math.isfinite(nav_after) or nav_after <= 0:
            raise ValueError(f"portfolio NAV invalid at {dates[i]}")
        prev_nav = nav_values[-1]
        nav_returns.append(nav_after / prev_nav - 1)
        nav_values.append(nav_after)
        nav_dates.append(dates[i])
        exposure_values.append(float(np.dot(shares, prices)) / nav_after)

    final_prices = close[-1]
    final_sell = shares * final_prices
    open_final = np.flatnonzero(shares > 1e-12)
    fee_rate = cost["fee"] + cost["slippage"]
    liquidation_cost = fee_rate * float(final_sell.sum()) + cost["sell_tax"] * float(np.dot(final_sell, taxable))
    final_nav = cash + float(final_sell.sum()) - liquidation_cost
    for j in open_final:
        symbol = symbols[j]
        round_trips.append({"symbol": symbol, "entry_date": open_dates.pop(symbol),
                            "exit_date": dates[-1].date().isoformat(), "exit_reason": "terminal_liquidation"})
    nav_values[-1] = final_nav
    cash = final_nav
    shares[:] = 0.0
    if nav_returns:
        nav_returns[-1] = final_nav / nav_values[-2] - 1
    cumulative_turnover += float(final_sell.sum()) / 2
    metric = _daily_metrics(pd.DatetimeIndex(nav_dates), np.asarray(nav_values), np.asarray(nav_returns))
    metric.update({"market": market, "lookback_sessions": lookback, "cadence": cadence,
                   "sma200_gate": gate, "buy_hold_baseline": baseline,
                   "cost": cost, "exposure_mean_pct": float(np.mean(exposure_values) * 100) if exposure_values else 0.0,
                   "cash_final_pct": 100.0,
                   "one_way_turnover_initial_nav": cumulative_turnover,
                   "completed_round_trips": len(round_trips),
                   "rebalance_events": len(events), "liquidation_cost": liquidation_cost})
    daily = [{"date": date.isoformat(), "nav": float(value),
              "return": (None if i == 0 else float(nav_returns[i - 1]))}
             for i, (date, value) in enumerate(zip(nav_dates, nav_values))]
    return metric, daily, events, round_trips


def run(args: argparse.Namespace) -> dict:
    if not args.preflight_only and args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite {args.output_dir}")
    prereg_hash = sha256_file(args.prereg)
    code_hash = sha256_file(Path(__file__))
    git_sha = __import__("subprocess").run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                           capture_output=True, text=True, check=True).stdout.strip()
    started = datetime.now(timezone.utc)
    results = {}
    daily_rows = []
    event_rows = []
    roundtrip_rows = []
    input_meta = {}
    for market, lookback, cadences in (("KR", 60, ("monthly",)), ("US", 126, ("daily", "monthly"))):
        excluded = INVERSE_SYMBOLS[market] if args.exclude_inverse else set()
        symbols, dates, close, files = load_panel(args.cache, market, excluded)
        input_meta[market] = {"symbols": symbols, "dates": {"start": dates[0].isoformat(), "end": dates[-1].isoformat()},
                              "sessions": len(dates), "files": files,
                              "excluded_inverse_symbols": sorted(excluded)}
        if args.preflight_only:
            continue
        for cadence in cadences:
            for gate in (False, True):
                for scenario, cost in COSTS[market].items():
                    key = f"{market}|mom{lookback}|{cadence}|sma200={int(gate)}|{scenario}"
                    metric, daily, events, round_trips = simulate(symbols, dates, close, market, lookback, cadence,
                                                                  gate, cost, baseline=False)
                    metric["scenario"] = scenario
                    results[key] = metric
                    for row in daily:
                        daily_rows.append({"cell": key, **row})
                    for row in events:
                        event_rows.append({"cell": key, **row})
                    for row in round_trips:
                        roundtrip_rows.append({"cell": key, **row})
                    if cadence == cadences[0] and not gate:
                        bmk, bmk_daily, bmk_events, bmk_round_trips = simulate(
                            symbols, dates, close, market, lookback, cadence, False, cost, baseline=True)
                        bmk["scenario"] = scenario
                        bmk_key = f"{market}|equal_weight_buy_hold|{scenario}"
                        results[bmk_key] = bmk
                        for row in bmk_daily:
                            daily_rows.append({"cell": bmk_key, **row})
                        for row in bmk_events:
                            event_rows.append({"cell": bmk_key, **row})
                        for row in bmk_round_trips:
                            roundtrip_rows.append({"cell": bmk_key, **row})
    input_fingerprint = hashlib.sha256("\n".join(
        f"{market}|{file['path']}|{file['sha256']}"
        for market in sorted(input_meta) for file in input_meta[market]["files"]
    ).encode()).hexdigest()
    if args.preflight_only:
        result = {"status": "PREFLIGHT_PASS", "markets": {
            market: {"symbols": len(meta["symbols"]), "sessions": meta["sessions"],
                     "start": meta["dates"]["start"], "end": meta["dates"]["end"],
                     "input_files": len(meta["files"]),
                     "excluded_inverse_symbols": meta["excluded_inverse_symbols"]}
            for market, meta in input_meta.items()}, "input_fingerprint_sha256": input_fingerprint,
            "preregistration_sha256": prereg_hash, "code_sha256": code_hash}
        print(json.dumps(result, ensure_ascii=False))
        return result
    args.output_dir.mkdir(parents=True)
    summary = {
        "schema_version": 1, "status": "exploratory_historical_exposed",
        "run_id": args.output_dir.name, "git_sha": git_sha,
        "started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
        "command_argv": [sys.executable, *sys.argv],
        "preregistration": str(args.prereg.resolve().relative_to(ROOT)), "preregistration_sha256": prereg_hash,
        "code": str(Path(__file__).relative_to(ROOT)), "code_sha256": code_hash,
        "input_fingerprint_sha256": input_fingerprint, "cache_root": str(args.cache),
        "markets": input_meta, "candidate_count": len(results), "results": results,
        "warnings": ["current-survivor cohort; not point-in-time", "corporate-action provenance unresolved",
                     "all source prices were previously inspected; no sealed/OOS claim",
                     "costs are legacy scenarios; execution friction may be understated"],
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(daily_rows).to_csv(args.output_dir / "daily_nav.csv", index=False, lineterminator="\n")
    pd.DataFrame(event_rows).to_csv(args.output_dir / "rebalance_and_roundtrip_ledger.csv", index=False, lineterminator="\n")
    pd.DataFrame(roundtrip_rows).to_csv(args.output_dir / "roundtrip_ledger.csv", index=False, lineterminator="\n")
    print(json.dumps({"status": summary["status"], "run_id": summary["run_id"],
                      "cells": len(results), "input_fingerprint": input_fingerprint,
                      "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".kis-cache-local")
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true",
                        help="validate fixed common panels and hashes without scoring or writing artifacts")
    parser.add_argument("--exclude-inverse", action="store_true",
                        help="exclude the predeclared inverse ETF tickers 114800 (KR) and SH (US)")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
