"""One fixed, development-only BTC impulse / altcoin underreaction replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor.mtf_consensus import score_forecast

SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
DRIVER = "BTCUSDT"
EVAL_START_MS = 1577836800000  # 2020-01-01 UTC; feature warmup extends before each anchor.
CUTOFF_MS = 1782864000000      # 2026-07-01T00:00:00Z, exclusive.
DAY_MS = 86_400_000
MINUTE_MS = 60_000
FEE_BASE = 0.001
FEE_STRESS = 0.003
RANDOM_SEED = "btc-lead-alt-lag-v1"


def wilson(successes: int, trials: int, z: float = 1.959963984540054):
    if trials == 0:
        return None, None
    p = successes / trials
    den = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / den
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / den
    return center - half, center + half


def signal_side(btc_r5: float, threshold: float, residual: float,
                alt_r15_pre: float, alt_r60_pre: float) -> str | None:
    """Return a direction only for the preregistered impulse/underreaction rule."""
    if not all(math.isfinite(x) for x in
               (btc_r5, threshold, residual, alt_r15_pre, alt_r60_pre)):
        return None
    if threshold <= 0:
        return None
    if btc_r5 >= threshold and residual < 0 and alt_r15_pre > 0 and alt_r60_pre > 0:
        return "long"
    if btc_r5 <= -threshold and residual > 0 and alt_r15_pre < 0 and alt_r60_pre < 0:
        return "short"
    return None


def matched_forecast(forecast: dict, side: str, baseline: str) -> dict:
    entry = float(forecast["entry_price"])
    risk = abs(entry - float(forecast["stop"]))
    stop = entry - risk if side == "long" else entry + risk
    target = entry + (2 * risk if side == "long" else -2 * risk)
    return {**forecast, "event_id": f"{forecast['event_id']}:{baseline}",
            "side": side, "stop": stop, "target": target, "risk": risk}


def _read_symbol(db_path: Path, symbol: str, end_ms: int) -> pd.DataFrame:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        frame = pd.read_sql_query(
            "SELECT open_ms AS t_open_ms, open AS o, high AS h, low AS l, close AS c "
            "FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms",
            db, params=(symbol, end_ms),
        )
    if not frame.empty:
        frame = frame.astype({"t_open_ms": "int64"})
    return frame


def _valid_span(times: np.ndarray, start: int, end: int) -> bool:
    # Candle tables have a (symbol, open_ms) primary key and are sorted here.
    # Exact endpoint distance therefore proves every minute in the window exists.
    return start >= 0 and end < len(times) and end >= start and \
        int(times[end]) - int(times[start]) == (end - start) * MINUTE_MS


def _btc_daily_thresholds(btc: pd.DataFrame) -> dict[int, float]:
    """Use the prior 30 UTC days only; one threshold is frozen per UTC day."""
    t = btc.t_open_ms.to_numpy(dtype=np.int64)
    c = btc.c.to_numpy(dtype=np.float64)
    r5 = np.full(len(t), np.nan)
    five_minute_ok = (t[5:] - t[:-5]) == 5 * MINUTE_MS
    r5[5:] = np.where(five_minute_ok, np.log(c[5:] / c[:-5]), np.nan)
    day_ids = t // DAY_MS
    thresholds = {}
    for day in np.unique(day_ids):
        right = int(np.searchsorted(t, int(day) * DAY_MS, side="left"))
        left = int(np.searchsorted(t, int(day) * DAY_MS - 30 * DAY_MS, side="left"))
        hist = np.abs(r5[left:right])
        hist = hist[np.isfinite(hist)]
        if len(hist) >= 20_000:
            thresholds[int(day)] = float(np.quantile(hist, 0.95, method="linear"))
    return thresholds


def _features_for_alt(alt: pd.DataFrame, btc: pd.DataFrame,
                      thresholds: dict[int, float]) -> pd.DataFrame:
    """Causal features; beta ends before the five-minute impulse window."""
    joined = alt.merge(btc[["t_open_ms", "c"]].rename(columns={"c": "btc_c"}),
                       on="t_open_ms", how="inner", validate="one_to_one")
    t = joined.t_open_ms.to_numpy(dtype=np.int64)
    c = joined.c.to_numpy(dtype=np.float64)
    bc = joined.btc_c.to_numpy(dtype=np.float64)
    a_ret = np.full(len(t), np.nan)
    b_ret = np.full(len(t), np.nan)
    continuous = np.diff(t) == MINUTE_MS
    loga, logb = np.log(c), np.log(bc)
    a_ret[1:] = np.diff(loga)
    b_ret[1:] = np.diff(logb)
    a_ret[1:][~continuous] = np.nan
    b_ret[1:][~continuous] = np.nan
    ar = pd.Series(a_ret)
    br = pd.Series(b_ret)
    cov = ar.rolling(60, min_periods=60).cov(br)
    var = br.rolling(60, min_periods=60).var(ddof=1)
    beta = (cov / var).shift(5).to_numpy(dtype=np.float64)

    r5 = np.full(len(t), np.nan)
    r15_pre = np.full(len(t), np.nan)
    r60_pre = np.full(len(t), np.nan)
    r5[5:] = np.where(t[5:] - t[:-5] == 5 * MINUTE_MS,
                      loga[5:] - loga[:-5], np.nan)
    r15_pre[20:] = np.where(t[20:] - t[5:-15] == 15 * MINUTE_MS,
                            loga[15:-5] - loga[:-20], np.nan)
    r60_pre[65:] = np.where(t[65:] - t[5:-60] == 60 * MINUTE_MS,
                            loga[60:-5] - loga[:-65], np.nan)

    tr = np.full(len(t), np.nan)
    high = joined.h.to_numpy(dtype=np.float64)
    low = joined.l.to_numpy(dtype=np.float64)
    contiguous = np.r_[False, np.diff(t) == MINUTE_MS]
    tr[1:] = np.where(contiguous[1:], np.maximum.reduce((
        high[1:] - low[1:], np.abs(high[1:] - c[:-1]),
        np.abs(low[1:] - c[:-1]))), np.nan)
    atr14 = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy(dtype=np.float64)

    btc_aligned = btc.set_index("t_open_ms").reindex(t)
    btc_close = btc_aligned.c.to_numpy(dtype=np.float64)
    btc_r5 = np.full(len(t), np.nan)
    btc_r5[5:] = np.where(t[5:] - t[:-5] == 5 * MINUTE_MS,
                          np.log(btc_close[5:] / btc_close[:-5]), np.nan)

    day_ids = t // DAY_MS
    threshold = np.array([thresholds.get(int(day), np.nan) for day in day_ids])
    residual = r5 - beta * btc_r5
    side = [signal_side(float(x), float(q), float(e), float(r15), float(r60))
            for x, q, e, r15, r60 in zip(btc_r5, threshold, residual, r15_pre, r60_pre)]
    features = joined.copy()
    features["btc_r5"] = btc_r5
    features["btc_threshold"] = threshold
    features["beta_lagged"] = beta
    features["alt_r5"] = r5
    features["residual"] = residual
    features["alt_r15_pre"] = r15_pre
    features["alt_r60_pre"] = r60_pre
    features["atr14"] = atr14
    features["side"] = side
    return features


def _random_side(symbol: str, entry_ms: int) -> str:
    key = f"{RANDOM_SEED}|{symbol}|{entry_ms}".encode()
    return "long" if hashlib.sha256(key).digest()[0] % 2 == 0 else "short"


def _trade_record(forecast, side, baseline, minute_path):
    if baseline == "candidate":
        scored = score_forecast(forecast, minute_path, include_leverage=False)
    else:
        scored = score_forecast(matched_forecast(forecast, side, baseline), minute_path,
                                include_leverage=False)
    return scored


def _aggregate(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["strategy"], row["horizon_bars"])].append(row)
    out = []
    for (strategy, horizon), values in sorted(grouped.items()):
        results = [row for row in values if row["outcome"] in {"TARGET", "STOP", "TIMEOUT"}]
        targets = sum(row["outcome"] == "TARGET" for row in results)
        stops = sum(row["outcome"] == "STOP" for row in results)
        timeouts = sum(row["outcome"] == "TIMEOUT" for row in results)
        lo, hi = wilson(targets, len(results))
        risk_returns = [row["gross_return"] for row in results]
        risk_fraction = [row["risk_fraction"] for row in results]
        item = {"strategy": strategy, "horizon_minutes": horizon,
                "events": len(values), "scored": len(results), "target": targets,
                "stop": stops, "timeout": timeouts,
                "target_first_precision": targets / len(results) if results else None,
                "wilson95": [lo, hi],
                "net_positive_base": sum(g - FEE_BASE > 0 for g in risk_returns) / len(results)
                    if results else None,
                "mean_net_r_base": float(np.mean([(g - FEE_BASE) / r for g, r in
                                                   zip(risk_returns, risk_fraction)]))
                    if results else None,
                "net_positive_stress": sum(g - FEE_STRESS > 0 for g in risk_returns) / len(results)
                    if results else None,
                "mean_net_r_stress": float(np.mean([(g - FEE_STRESS) / r for g, r in
                                                     zip(risk_returns, risk_fraction)]))
                    if results else None,
                "symbols": len({row["symbol"] for row in values})}
        out.append(item)
    return out


def _moving_block_inference(rows: list[dict], *, replicates: int = 2000,
                           block_days: int = 7, seed: int = 20261115) -> list[dict]:
    """Post-hoc circular UTC-day block bootstrap for absolute and paired metrics."""
    scored = [row for row in rows if row["outcome"] in {"TARGET", "STOP", "TIMEOUT"}]
    if not scored:
        return []
    day_for = lambda row: int(row["entry_ms"] // DAY_MS)
    first_day = min(day_for(row) for row in scored)
    last_day = max(day_for(row) for row in scored)
    day_count = last_day - first_day + 1
    day_index = lambda row: day_for(row) - first_day
    strategies = sorted({row["strategy"] for row in scored})
    horizons = sorted({row["horizon_bars"] for row in scored})
    rng = np.random.default_rng(seed)
    output = []

    for horizon in horizons:
        per_strategy = {}
        lookup = {}
        for strategy in strategies:
            subset = [row for row in scored if row["horizon_bars"] == horizon
                      and row["strategy"] == strategy]
            target = np.zeros(day_count, dtype=np.float64)
            count = np.zeros(day_count, dtype=np.float64)
            sum_r_base = np.zeros(day_count, dtype=np.float64)
            sum_r_stress = np.zeros(day_count, dtype=np.float64)
            for row in subset:
                day = day_index(row)
                target[day] += row["outcome"] == "TARGET"
                count[day] += 1
                risk = row["risk_fraction"]
                sum_r_base[day] += (row["gross_return"] - FEE_BASE) / risk
                sum_r_stress[day] += (row["gross_return"] - FEE_STRESS) / risk
                lookup[(row["symbol"], row["entry_ms"], horizon, strategy)] = row
            per_strategy[strategy] = (target, count, sum_r_base, sum_r_stress)

        offsets = np.arange(block_days)
        # Re-draw the same block bootstrap for each replicate, preserving all symbols on each day.
        abs_draws = {name: {"precision": [], "mean_net_r_base": [], "mean_net_r_stress": []}
                     for name in strategies}
        diff_draws = {}
        pairs = [("candidate", name) for name in strategies
                 if name not in {"candidate"}]
        paired_arrays = {}
        for left, right in pairs:
            keys = [(row["symbol"], row["entry_ms"], horizon)
                    for row in scored if row["horizon_bars"] == horizon
                    and row["strategy"] == left]
            paired = [(lookup.get((*key, left)), lookup.get((*key, right))) for key in keys]
            paired = [(a, b) for a, b in paired if a is not None and b is not None]
            if not paired:
                continue
            ptarget_a = np.zeros(day_count, dtype=np.float64)
            ptarget_b = np.zeros(day_count, dtype=np.float64)
            pcount = np.zeros(day_count, dtype=np.float64)
            prdiff_base = np.zeros(day_count, dtype=np.float64)
            prdiff_stress = np.zeros(day_count, dtype=np.float64)
            for a, b in paired:
                day = day_index(a)
                ptarget_a[day] += a["outcome"] == "TARGET"
                ptarget_b[day] += b["outcome"] == "TARGET"
                pcount[day] += 1
                risk = a["risk_fraction"]
                prdiff_base[day] += ((a["gross_return"] - FEE_BASE) / risk
                                     - (b["gross_return"] - FEE_BASE) / risk)
                prdiff_stress[day] += ((a["gross_return"] - FEE_STRESS) / risk
                                       - (b["gross_return"] - FEE_STRESS) / risk)
            paired_arrays[right] = (ptarget_a, ptarget_b, pcount,
                                    prdiff_base, prdiff_stress, len(paired))
            diff_draws[right] = {"precision": [], "mean_net_r_base": [],
                                 "mean_net_r_stress": []}

        for _ in range(replicates):
            starts = rng.integers(0, day_count, size=math.ceil(day_count / block_days))
            days = ((starts[:, None] + offsets[None, :]) % day_count).ravel()[:day_count]
            multiplicity = np.bincount(days, minlength=day_count).astype(np.float64)
            for name, (target, count, r_base, r_stress) in per_strategy.items():
                n = float(np.dot(multiplicity, count))
                if n:
                    abs_draws[name]["precision"].append(
                        float(np.dot(multiplicity, target) / n))
                    abs_draws[name]["mean_net_r_base"].append(
                        float(np.dot(multiplicity, r_base) / n))
                    abs_draws[name]["mean_net_r_stress"].append(
                        float(np.dot(multiplicity, r_stress) / n))
            for name, (ta, tb, count, rd_base, rd_stress, _) in paired_arrays.items():
                n = float(np.dot(multiplicity, count))
                if n:
                    diff_draws[name]["precision"].append(
                        float(np.dot(multiplicity, ta - tb) / n))
                    diff_draws[name]["mean_net_r_base"].append(
                        float(np.dot(multiplicity, rd_base) / n))
                    diff_draws[name]["mean_net_r_stress"].append(
                        float(np.dot(multiplicity, rd_stress) / n))

        def interval(values):
            return [float(x) for x in np.quantile(values, [0.025, 0.975])] if values else None

        for name in strategies:
            output.append({"horizon_minutes": horizon, "strategy": name,
                           "bootstrap_method": "circular_7_UTC_day_block",
                           "replicates": replicates,
                           "precision_ci95": interval(abs_draws[name]["precision"]),
                           "mean_net_r_base_ci95": interval(abs_draws[name]["mean_net_r_base"]),
                           "mean_net_r_stress_ci95": interval(abs_draws[name]["mean_net_r_stress"])})
        for name, arrays in paired_arrays.items():
            output.append({"horizon_minutes": horizon, "paired_difference":
                           f"candidate_minus_{name}", "paired_events": arrays[-1],
                           "bootstrap_method": "circular_7_UTC_day_block",
                           "replicates": replicates,
                           "precision_difference_ci95": interval(diff_draws[name]["precision"]),
                           "mean_net_r_base_difference_ci95": interval(
                               diff_draws[name]["mean_net_r_base"]),
                           "mean_net_r_stress_difference_ci95": interval(
                               diff_draws[name]["mean_net_r_stress"])})
    return output


def run(db_path: Path, output: Path, *, start_ms: int = EVAL_START_MS,
        cutoff_ms: int = CUTOFF_MS) -> dict:
    started = time.perf_counter()
    # Never load rows at/after the exclusive cutoff, including outcome candles.
    btc = _read_symbol(db_path, DRIVER, cutoff_ms)
    if btc.empty:
        raise ValueError("BTC driver candles are missing")
    thresholds = _btc_daily_thresholds(btc)
    records: list[dict] = []
    eligible_total = 0
    signal_total = 0
    symbols_used = []

    for symbol in SYMBOLS:
        if symbol == DRIVER:
            continue
        alt = _read_symbol(db_path, symbol, cutoff_ms)
        if alt.empty:
            continue
        f = _features_for_alt(alt, btc, thresholds)
        times = f.t_open_ms.to_numpy(dtype=np.int64)
        eligible = ((times >= start_ms) & (times < cutoff_ms - 21 * MINUTE_MS)
                    & np.isfinite(f.atr14.to_numpy(dtype=np.float64))
                    & np.isfinite(f.btc_r5.to_numpy(dtype=np.float64))
                    & np.isfinite(f.btc_threshold.to_numpy(dtype=np.float64))
                    & np.isfinite(f.beta_lagged.to_numpy(dtype=np.float64))
                    & np.isfinite(f.alt_r15_pre.to_numpy(dtype=np.float64))
                    & np.isfinite(f.alt_r60_pre.to_numpy(dtype=np.float64)))
        eligible_total += int(eligible.sum())
        blocked_until = -1
        emitted = 0
        for i in np.flatnonzero(eligible):
            side = f.iloc[i].side
            if side not in {"long", "short"} or int(times[i]) < blocked_until:
                continue
            if i + 20 >= len(f) or not _valid_span(times, i + 1, i + 20):
                continue
            entry_ms = int(times[i + 1])
            entry = float(f.iloc[i + 1].o)
            risk = float(f.iloc[i].atr14)
            stop = entry - risk if side == "long" else entry + risk
            target = entry + 2 * risk if side == "long" else entry - 2 * risk
            if stop <= 0 or target <= 0 or not all(map(math.isfinite, (entry, risk, stop, target))):
                continue
            forecast = {"event_id": f"{symbol}:{entry_ms}", "symbol": symbol,
                        "timeframe": "1m", "side": side, "entry_ms": entry_ms,
                        "entry_price": entry, "stop": stop, "target": target,
                        "risk": risk, "risk_fraction": risk / entry}
            path = f.iloc[i + 1:i + 21][["t_open_ms", "o", "h", "l", "c"]].reset_index(drop=True)
            alt_r5 = float(f.iloc[i].alt_r5)
            momentum_side = "long" if alt_r5 > 0 else "short" if alt_r5 < 0 else None
            baseline_sides = {"momentum_5m": momentum_side,
                              "fixed_seed_random": _random_side(symbol, entry_ms)}
            for strategy, baseline_side in [("candidate", side), *baseline_sides.items()]:
                if baseline_side is None:
                    continue
                score = _trade_record(forecast, baseline_side, strategy, path)
                for bars in (10, 20):
                    outcome = score[f"{bars}_bars"]
                    records.append({"symbol": symbol, "entry_ms": entry_ms,
                                    "strategy": strategy, "side": baseline_side,
                                    "horizon_bars": bars, "outcome": outcome["outcome"],
                                    "gross_return": outcome.get("gross_return"),
                                    "risk_fraction": risk / entry})
            emitted += 1
            signal_total += 1
            blocked_until = entry_ms + 20 * MINUTE_MS
        symbols_used.append({"symbol": symbol, "eligible_anchors": int(eligible.sum()),
                             "accepted_signals": emitted,
                             "coverage": emitted / int(eligible.sum()) if eligible.sum() else 0.0})
        print(f"finished {symbol}: eligible={int(eligible.sum())} signals={emitted}", flush=True)

    summaries = _aggregate(records)
    per_symbol_outcomes = []
    for symbol in sorted({row["symbol"] for row in records}):
        for item in _aggregate([row for row in records if row["symbol"] == symbol]):
            per_symbol_outcomes.append({"symbol": symbol, **item})
    result = {
        "stage": "EXPLORATORY_DEVELOPMENT_ONLY",
        "hypothesis": "BTC 5m extreme impulse plus lagged-beta alt underreaction and aligned prior 15m/60m trend",
        "trial_count": 1,
        "start_ms": start_ms, "cutoff_exclusive_ms": cutoff_ms,
        "start_utc": datetime.fromtimestamp(start_ms / 1000, timezone.utc).isoformat(),
        "cutoff_utc": datetime.fromtimestamp(cutoff_ms / 1000, timezone.utc).isoformat(),
        "symbols": [item["symbol"] for item in symbols_used],
        "driver": DRIVER, "eligible_anchor_count": eligible_total,
        "candidate_signal_count": signal_total,
        "coverage": signal_total / eligible_total if eligible_total else 0.0,
        "per_symbol": symbols_used,
        "outcomes": summaries,
        "per_symbol_outcomes": per_symbol_outcomes,
        "clustered_inference": _moving_block_inference(records),
        "elapsed_seconds": time.perf_counter() - started,
        "input": {"database": str(db_path), "database_size_bytes": db_path.stat().st_size},
        "limitations": [
            "Historical development data have been inspected by prior research; this is not OOS or forward validation.",
            "Only five altcoins are present; the 20-symbol research gate cannot be met.",
            "Current cache universe is not point-in-time and has survivorship/listing bias.",
            "The 95th percentile uses overlapping 1m-anchored five-minute returns; dependence makes naive Wilson intervals optimistic.",
            "No funding cashflows, bid-ask spread, depth, slippage, latency, or account-specific liquidation is modeled.",
            "Results by horizon and baseline share the same events and are not independent tests.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="read-only development candle DB")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.db, args.output)
    print(json.dumps({"output": str(args.output), "eligible": result["eligible_anchor_count"],
                      "signals": result["candidate_signal_count"],
                      "coverage": result["coverage"], "outcomes": result["outcomes"]}, indent=2))


if __name__ == "__main__":
    main()
