"""Run the preregistered R021 historical-only event study.

The candle database is opened read-only. Outputs are restricted to the
explicit run directory; the script has no network or account/order code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor import indicators
from chart_predictor.r021_funding_reentry import (
    first_reentry_breakout,
    funding_extreme_side,
    macro_side,
)


SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
TIMEFRAMES = (1, 3, 5, 10, 15, 30, 60)
START_MS = 1601510400000
END_MS = 1704067200000
LOOKBACK_MS = 180 * 86_400_000
FEE = 0.0005
SLIPPAGE = 0.0002


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_minutes(db: Path, symbol: str) -> pd.DataFrame:
    uri = f"file:{db.resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        frame = pd.read_sql_query(
            "SELECT open_ms,open,high,low,close FROM candles WHERE symbol=? AND open_ms>=? AND open_ms<? ORDER BY open_ms",
            connection,
            params=(symbol, START_MS - 180 * 86_400_000, END_MS),
        )
    return frame


def aggregate(frame: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if minutes == 1:
        return frame.copy().reset_index(drop=True)
    width = minutes * 60_000
    work = frame.copy()
    work["bucket"] = (work.open_ms // width) * width
    grouped = work.groupby("bucket", sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), count=("open_ms", "size"),
    )
    return grouped[grouped["count"] == minutes].drop(columns="count").reset_index(names="open_ms")


def load_funding(root: Path, symbol: str) -> list[dict]:
    records = []
    for path in sorted((root / symbol).glob("page_*.json")):
        records.extend(json.loads(path.read_text(encoding="utf-8")))
    unique = {int(row["fundingTime"]): row for row in records}
    return [unique[t] for t in sorted(unique) if START_MS <= t < END_MS]


def latest_closed_index(opens: np.ndarray, width_ms: int, timestamp: int) -> int:
    return int(np.searchsorted(opens + width_ms, timestamp, side="right") - 1)


def horizon_fits(split_end_ms: int, entry_time_ms: int, horizon_bars: int, width_ms: int) -> bool:
    """Require the full maximum outcome window to remain before split end."""
    return entry_time_ms + horizon_bars * width_ms <= split_end_ms


def wilson(successes: int, n: int) -> list[float | None]:
    if n == 0:
        return [None, None]
    z = 1.959963984540054
    p = successes / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(center - half), float(center + half)]


def walk_trade(minute: pd.DataFrame, funding: list[dict], entry_i: int, side: int,
               risk: float, width_ms: int, horizon_bars: int, stress: bool) -> dict:
    entry = float(minute.open.iloc[entry_i])
    if not np.isfinite(entry) or not np.isfinite(risk) or entry <= 0 or risk <= 0:
        raise ValueError("entry and risk must be positive finite values")
    stop = entry - side * risk
    target = entry + side * 1.5 * risk
    end_time = int(minute.open_ms.iloc[entry_i]) + horizon_bars * width_ms
    last_i = int(np.searchsorted(minute.open_ms.to_numpy(), end_time, side="left") - 1)
    last_i = min(last_i, len(minute) - 1)
    if last_i < entry_i:
        return {"censored": True}
    exit_i, reason, fill = last_i, "timeout", float(minute.close.iloc[last_i])
    for i in range(entry_i, last_i + 1):
        o, h, l = map(float, (minute.open.iloc[i], minute.high.iloc[i], minute.low.iloc[i]))
        stop_hit = l <= stop if side == 1 else h >= stop
        target_hit = h >= target if side == 1 else l <= target
        if stop_hit:
            exit_i, reason, fill = i, "stop", min(o, stop) if side == 1 else max(o, stop)
            break
        if target_hit:
            exit_i, reason, fill = i, "target", target
            break
    entry_time = int(minute.open_ms.iloc[entry_i])
    exit_time = int(minute.open_ms.iloc[exit_i]) + 60_000
    funding_pnl = 0.0
    rates = [x for x in funding if entry_time < int(x["fundingTime"]) <= exit_time]
    minute_opens = minute.open_ms.to_numpy(dtype=np.int64)
    for event in rates:
        t = int(event["fundingTime"])
        j = int(np.searchsorted(minute_opens, t, side="left") - 1)
        mark = float(event["markPrice"]) if event.get("markPrice") not in (None, "") else (float(minute.close.iloc[j]) if j >= 0 else entry)
        funding_pnl -= side * float(event["fundingRate"]) * mark / entry
    exit_r = side * (fill - entry) / risk
    friction = (2 * (FEE + SLIPPAGE) * entry) / risk
    if stress:
        friction *= 2
    return {
        "censored": False, "entry_ms": entry_time, "exit_ms": exit_time,
        "reason": reason, "target_first": reason == "target",
        "gross_r": float(exit_r), "funding_r": float(funding_pnl),
        "cost_r": float(friction), "net_r": float(exit_r + funding_pnl - friction),
    }


def summarize(rows: list[dict]) -> dict:
    usable = [r for r in rows if not r.get("censored")]
    targets = sum(r["target_first"] for r in usable)
    return {
        "signals": len(rows), "matured": len(usable), "censored": len(rows) - len(usable),
        "target_first": targets, "stop_first": sum(r["reason"] == "stop" for r in usable),
        "timeout": sum(r["reason"] == "timeout" for r in usable),
        "target_first_rate": targets / len(usable) if usable else None,
        "wilson95": wilson(targets, len(usable)),
        "mean_gross_r": float(np.mean([r["gross_r"] for r in usable])) if usable else None,
        "mean_funding_r": float(np.mean([r["funding_r"] for r in usable])) if usable else None,
        "mean_cost_r": float(np.mean([r["cost_r"] for r in usable])) if usable else None,
        "mean_net_r": float(np.mean([r["net_r"] for r in usable])) if usable else None,
        "positive_net_fraction": sum(r["net_r"] > 0 for r in usable) / len(usable) if usable else None,
        "by_symbol": {s: {"n": sum(r["symbol"] == s for r in usable),
                           "net_r": float(np.mean([r["net_r"] for r in usable if r["symbol"] == s]))
                           if any(r["symbol"] == s for r in usable) else None}
                       for s in SYMBOLS},
    }


def run(db: Path, funding_root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    funding_by_symbol = {s: load_funding(funding_root, s) for s in SYMBOLS}
    minutes_by_symbol = {s: read_minutes(db, s) for s in SYMBOLS}
    btc4 = aggregate(minutes_by_symbol["BTCUSDT"], 240)
    btc_close = btc4.close.to_numpy(dtype=float)
    btc_ema = indicators.ema(btc_close, 50)
    btc_opens = btc4.open_ms.to_numpy(dtype=np.int64)
    btc_closes_at = btc_opens + 240 * 60_000
    strategies = ("candidate", "no_macro", "no_funding_tail", "micro_only")
    all_rows = []
    funding_sides: dict[str, list[int | None]] = {}
    macro_sides: dict[str, list[int]] = {}
    for symbol, events in funding_by_symbol.items():
        times = np.asarray([int(x["fundingTime"]) for x in events], dtype=np.int64)
        rates = np.asarray([float(x["fundingRate"]) for x in events], dtype=float)
        sides = []
        for i, t in enumerate(times):
            left = int(np.searchsorted(times, t - LOOKBACK_MS, side="left"))
            sides.append(funding_extreme_side(rates[left:i], float(rates[i])))
        funding_sides[symbol] = sides
        macro_indices = np.searchsorted(btc_closes_at, times, side="right") - 1
        macro_sides[symbol] = [
            macro_side(float(btc_close[j]), float(btc_ema[j])) if j >= 0 else 0
            for j in macro_indices
        ]

    for tf in TIMEFRAMES:
        width = tf * 60_000
        for symbol in SYMBOLS:
            minute = minutes_by_symbol[symbol]
            bars = aggregate(minute, tf)
            opens = bars.open_ms.to_numpy(dtype=np.int64)
            hi, lo, cl = (bars[c].to_numpy(dtype=float) for c in ("high", "low", "close"))
            atr = indicators.atr(hi, lo, cl, 20)
            fund = funding_by_symbol[symbol]
            closes_at = opens + width
            minute_opens = minute.open_ms.to_numpy(dtype=np.int64)
            trigger_cache = {}
            outcome_cache = {}
            for variant in strategies:
                for horizon in (10, 20):
                    busy_until_ms = -1
                    for fi, event in enumerate(fund):
                        t = int(event["fundingTime"])
                        if t >= END_MS - horizon * width:
                            continue
                        ref = int(np.searchsorted(closes_at, t, side="right") - 1)
                        if ref < 20 or ref + 1 >= len(bars):
                            continue
                        start = int(np.searchsorted(opens, t, side="left"))
                        if start >= len(bars):
                            continue
                        extreme = funding_sides[symbol][fi]
                        rate = float(event["fundingRate"])
                        contrarian = 1 if rate < 0 else -1 if rate > 0 else None
                        regime = macro_sides[symbol][fi]
                        side = {
                            "candidate": extreme if extreme == regime else None,
                            "no_macro": extreme,
                            "no_funding_tail": contrarian if contrarian == regime else None,
                            "micro_only": contrarian,
                        }[variant]
                        if side is None:
                            continue
                        trigger_key = (fi, side)
                        if trigger_key not in trigger_cache:
                            trigger_cache[trigger_key] = first_reentry_breakout(
                                hi, lo, cl, atr, ref, side,
                                max_wait=20, pullback_atr=0.5, breakout_bars=3,
                                earliest_index=start,
                            )
                        trigger_i = trigger_cache[trigger_key]
                        if trigger_i is None:
                            continue
                        entry_time = int(opens[trigger_i] + width)
                        if not horizon_fits(END_MS, entry_time, horizon, width):
                            continue
                        entry_i = int(np.searchsorted(minute_opens, entry_time, side="left"))
                        if entry_i >= len(minute) or entry_time < busy_until_ms:
                            continue
                        risk = float(atr[trigger_i])
                        outcome_key = (trigger_i, side, horizon)
                        if outcome_key not in outcome_cache:
                            outcome_cache[outcome_key] = (
                                walk_trade(minute, fund, entry_i, side, risk, width, horizon, False),
                                walk_trade(minute, fund, entry_i, side, risk, width, horizon, True),
                            )
                        for stress, trade in zip((False, True), outcome_cache[outcome_key]):
                            if trade.get("censored"):
                                continue
                            record = dict(trade)
                            record.update({"symbol": symbol, "timeframe_min": tf, "variant": variant,
                                           "horizon_bars": horizon, "stress": stress,
                                           "side": side, "funding_time": t})
                            all_rows.append(record)
                            if not stress:
                                busy_until_ms = trade["exit_ms"]

    grouped = {}
    for variant in strategies:
        for tf in TIMEFRAMES:
            for horizon in (10, 20):
                for stress in (False, True):
                    subset = [r for r in all_rows if (r["variant"], r["timeframe_min"], r["horizon_bars"], r["stress"]) == (variant, tf, horizon, stress)]
                    grouped[f"{variant}|{tf}m|{horizon}bars|{'stress' if stress else 'base'}"] = summarize(subset)
    result = {
        "run_id": "2026-11-16-r021b-funding-macro-reentry-boundary-corrected", "phase": "exposed_development_only",
        "price_db": str(db), "price_db_sha256": sha256(db),
        "funding_root": str(funding_root), "funding_manifest_sha256": sha256(funding_root / "manifest.json"),
        "start_ms": START_MS, "end_ms_exclusive": END_MS, "symbols": list(SYMBOLS),
        "timeframes_min": list(TIMEFRAMES), "variants": list(strategies),
        "fees_per_side": FEE, "slippage_per_side": SLIPPAGE,
        "funding_mark_proxy": "latest prior 1m close if REST markPrice absent",
        "results": grouped,
    }
    (output / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "trades.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in all_rows), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--funding-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.db, args.funding_root, args.output)
    print(json.dumps({"run_id": result["run_id"], "result_cells": len(result["results"]),
                      "trades_file": str(args.output / "trades.jsonl")}, sort_keys=True))


if __name__ == "__main__":
    main()
