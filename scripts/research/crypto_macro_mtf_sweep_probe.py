#!/usr/bin/env python3
"""One frozen BTC-4h-regime / 5m-sweep-MSS development probe."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
import sqlite3
import struct
import subprocess
from pathlib import Path

import numpy as np

WIDTH_1M = 60_000
WIDTH_5M = 5 * WIDTH_1M
WIDTH_4H = 240 * WIDTH_1M
START_MS = 1_784_246_400_000  # 2026-07-17T00:00:00Z
CUTOFF_MS = 1_791_504_000_000  # 2026-10-09T00:00:00Z, exclusive
BASE_COST = 0.001
STRESS_COST = 0.003
BOOTSTRAPS = 1000
SEED = 20261115


def complete_bars(times, opens, highs, lows, closes, width_ms):
    """UTC-aligned OHLC aggregation; incomplete/missing-minute buckets vanish."""
    expected = width_ms // WIDTH_1M
    if not len(times):
        return {k: np.array([], dtype=np.int64 if k == "t" else float)
                for k in ("t", "o", "h", "l", "c")}
    buckets = times // width_ms * width_ms
    _, starts, counts = np.unique(buckets, return_index=True, return_counts=True)
    keep = []
    for start, count in zip(starts, counts):
        if count != expected:
            continue
        end = start + expected
        if times[start] != buckets[start] or times[end - 1] != buckets[start] + width_ms - WIDTH_1M:
            continue
        if expected > 1 and np.any(np.diff(times[start:end]) != WIDTH_1M):
            continue
        keep.append(start)
    if not keep:
        return {k: np.array([], dtype=np.int64 if k == "t" else float)
                for k in ("t", "o", "h", "l", "c")}
    starts = np.asarray(keep, dtype=np.int64)
    ends = starts + expected
    return {
        "t": times[starts] // width_ms * width_ms,
        "o": opens[starts],
        "h": np.maximum.reduceat(highs, starts),
        "l": np.minimum.reduceat(lows, starts),
        "c": closes[ends - 1],
    }


def macro_structure(four_hour):
    """Return causal {-1,0,1} regime known at each completed 4h close."""
    t, high, low = four_hour["t"], four_hour["h"], four_hour["l"]
    state = np.zeros(len(t), dtype=np.int8)
    piv_hi, piv_lo = [], []
    for k in range(len(t)):
        if k and t[k] - t[k - 1] != WIDTH_4H:
            piv_hi.clear()
            piv_lo.clear()
        center = k - 2
        if center >= 2 and t[k] - t[k - 4] == 4 * WIDTH_4H:
            neighbors = [center - 2, center - 1, center + 1, center + 2]
            if all(high[center] > high[n] for n in neighbors):
                piv_hi.append(float(high[center]))
            if all(low[center] < low[n] for n in neighbors):
                piv_lo.append(float(low[center]))
        if len(piv_hi) >= 2 and len(piv_lo) >= 2:
            if piv_hi[-1] > piv_hi[-2] and piv_lo[-1] > piv_lo[-2]:
                state[k] = 1
            elif piv_hi[-1] < piv_hi[-2] and piv_lo[-1] < piv_lo[-2]:
                state[k] = -1
    return state


def regimes_for_micro(micro, four_hour, macro_state):
    """Map only completed 4h regime bars to each completed 5m decision bar."""
    if not len(four_hour["t"]):
        return np.zeros(len(micro["t"]), dtype=np.int8)
    h4_close = four_hour["t"] + WIDTH_4H
    m5_close = micro["t"] + WIDTH_5M
    indices = np.searchsorted(h4_close, m5_close, side="right") - 1
    result = np.zeros(len(m5_close), dtype=np.int8)
    valid = indices >= 0
    ix = indices[valid]
    age = m5_close[valid] - h4_close[ix]
    fresh = age <= WIDTH_4H
    positions = np.flatnonzero(valid)[fresh]
    result[positions] = macro_state[ix[fresh]]
    return result


def find_first_mss(micro, regime, sweep_i, side):
    """First strictly later, continuous MSS within 12 completed bars."""
    t, high, low, close = (micro[k] for k in ("t", "h", "l", "c"))
    expected_regime = 1 if side == "long" else -1
    for j in range(sweep_i + 1, min(sweep_i + 13, len(t))):
        if t[j] - t[j - 1] != WIDTH_5M or regime[j] != expected_regime:
            return None
        if j < 4 or np.any(np.diff(t[j - 4:j + 1]) != WIDTH_5M):
            continue
        if side == "long" and close[j] > np.max(high[j - 4:j]):
            return j
        if side == "short" and close[j] < np.min(low[j - 4:j]):
            return j
    return None


def scan_events(symbol, micro, regime, raw):
    """Emit one non-overlapping event per armed sweep/MSS candidate."""
    t, high, low, close, op = (micro[k] for k in ("t", "h", "l", "c", "o"))
    eligible_mask = np.zeros(len(t), dtype=bool)
    for anchor in range(12, len(t)):
        eligible_mask[anchor] = (regime[anchor] != 0 and
                                 np.all(np.diff(t[anchor - 12:anchor + 1]) == WIDTH_5M))
    eligible = int(eligible_mask.sum())
    events = []
    i = 12
    blocked_before = -1
    raw_t = raw["t"]
    while i < len(t) - 11:
        if i < blocked_before:
            i += 1
            continue
        if eligible_mask[i]:
            side = "long" if regime[i] == 1 else "short"
            support, resistance = np.min(low[i - 12:i]), np.max(high[i - 12:i])
            if side == "long":
                swept = low[i] < support and support < close[i] < resistance
            else:
                swept = high[i] > resistance and support < close[i] < resistance
            if swept:
                mss_i = find_first_mss(micro, regime, i, side)
                if mss_i is None:
                    i += 13
                    continue
                entry_i = mss_i + 1
                if entry_i >= len(t) or t[entry_i] - t[mss_i] != WIDTH_5M:
                    i = entry_i + 10
                    continue
                entry_ms, entry = int(t[entry_i]), float(op[entry_i])
                stop = float(low[i] if side == "long" else high[i])
                risk = (entry - stop) if side == "long" else (stop - entry)
                if not np.isfinite(risk) or risk <= 0 or entry <= 0:
                    i = entry_i + 10
                    continue
                minute_start = int(np.searchsorted(raw_t, entry_ms, side="left"))
                minute_end = minute_start + 50
                path_t = raw_t[minute_start:minute_end]
                if len(path_t) != 50 or path_t[0] != entry_ms or np.any(np.diff(path_t) != WIDTH_1M):
                    events.append({"symbol": symbol, "sweep_ms": int(t[i]), "mss_ms": int(t[mss_i]),
                                   "entry_ms": entry_ms, "side": side, "status": "UNSCORABLE"})
                    i = entry_i + 10
                    continue
                base = score_path(side, entry, stop, path_t,
                                  raw["o"][minute_start:minute_end],
                                  raw["h"][minute_start:minute_end],
                                  raw["l"][minute_start:minute_end],
                                  raw["c"][minute_start:minute_end])
                mom_side = "long" if close[mss_i] > close[mss_i - 1] else (
                    "short" if close[mss_i] < close[mss_i - 1] else None)
                random_side = "long" if hashlib.sha256(
                    f"{SEED}|{symbol}|{entry_ms}".encode()).digest()[0] & 1 == 0 else "short"
                baseline = {}
                for name, baseline_side in (("momentum_5m", mom_side), ("fixed_random", random_side)):
                    baseline[name] = score_path(baseline_side, entry,
                        entry - risk if baseline_side == "long" else entry + risk,
                        path_t, raw["o"][minute_start:minute_end],
                        raw["h"][minute_start:minute_end], raw["l"][minute_start:minute_end],
                        raw["c"][minute_start:minute_end]) if baseline_side else None
                events.append({"symbol": symbol, "sweep_ms": int(t[i]), "mss_ms": int(t[mss_i]),
                               "entry_ms": entry_ms, "side": side, "entry": entry, "stop": stop,
                               "target": entry + (2 * risk if side == "long" else -2 * risk),
                               "risk": risk, "status": "SCORED", "candidate": base,
                               "baselines": baseline})
                blocked_before = entry_i + 10
                i = blocked_before
                continue
        i += 1
    return eligible, events


def score_path(side, entry, stop, times, opens, highs, lows, closes):
    """Stop-first OHLC barrier resolution and conservative adverse stop gaps."""
    risk = entry - stop if side == "long" else stop - entry
    if risk <= 0 or entry <= 0 or len(times) != 50:
        raise ValueError("invalid trade path")
    sign = 1 if side == "long" else -1
    target = entry + sign * 2 * risk
    exit_price, outcome = float(closes[-1]), "TIMEOUT"
    for j in range(len(times)):
        stop_hit = lows[j] <= stop if sign > 0 else highs[j] >= stop
        target_hit = highs[j] >= target if sign > 0 else lows[j] <= target
        if stop_hit:
            gap = opens[j] <= stop if sign > 0 else opens[j] >= stop
            exit_price = float(opens[j] if gap else stop)
            outcome = "STOP"
            break
        if target_hit:
            exit_price, outcome = float(target), "TARGET"
            break
    gross = sign * (exit_price / entry - 1)
    risk_pct = risk / entry
    result = {"outcome": outcome, "exit_price": exit_price, "gross_return": gross,
              "gross_r": gross / risk_pct}
    for case, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
        net = gross - cost
        result[f"net_return_{case}"] = net
        result[f"net_r_{case}"] = net / risk_pct
        result[f"net_positive_{case}"] = net > 0
    return result


def wilson(successes, trials, z=1.959963984540054):
    if not trials:
        return None
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    radius = z * np.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return [float(center - radius), float(center + radius)]


def bootstrap(events, seed=SEED):
    scored = [e for e in events if e["status"] == "SCORED"]
    if not scored:
        return {}
    days = np.asarray([e["entry_ms"] // 86_400_000 for e in scored], dtype=np.int64)
    first, last = int(days.min()), int(days.max())
    span = last - first + 1
    metrics = np.zeros((span, 18), dtype=float)
    for e, day in zip(scored, days):
        row = metrics[int(day - first)]
        c, b = e["candidate"], e["baselines"]
        row[0] += c["outcome"] == "TARGET"
        row[1] += 1
        row[2] += c["net_r_base"]
        row[3] += c["net_r_stress"]
        cand_hit = c["outcome"] == "TARGET"
        for target_col, n_col, net_col, name, delta_target_col in (
                (4, 5, 6, "momentum_5m", 12),
                (8, 9, 10, "fixed_random", 15)):
            base = b[name]
            if base is None:
                continue
            base_hit = base["outcome"] == "TARGET"
            row[target_col] += base_hit
            row[n_col] += 1
            row[net_col] += base["net_r_base"]
            pair_n_col = delta_target_col + 1
            delta_net_col = delta_target_col + 2
            row[delta_target_col] += cand_hit - base_hit
            row[pair_n_col] += 1
            row[delta_net_col] += c["net_r_base"] - base["net_r_base"]
    block = min(7, span)
    n_blocks = int(np.ceil(span / block))
    rng = np.random.default_rng(seed)
    stats = np.empty((BOOTSTRAPS, 9), dtype=float)
    extended = np.concatenate((metrics, metrics[:block - 1]), axis=0)
    prefix = np.vstack((np.zeros(metrics.shape[1]), np.cumsum(extended, axis=0)))
    starts_n = span
    for n in range(BOOTSTRAPS):
        starts = rng.integers(0, starts_n, size=n_blocks)
        ends = starts + block
        sampled = (prefix[ends] - prefix[starts]).sum(axis=0)
        stats[n] = [sampled[0] / sampled[1], sampled[2] / sampled[1],
                    sampled[3] / sampled[1], sampled[4] / sampled[5] if sampled[5] else np.nan,
                    sampled[8] / sampled[9] if sampled[9] else np.nan,
                    sampled[12] / sampled[13] if sampled[13] else np.nan,
                    sampled[14] / sampled[13] if sampled[13] else np.nan,
                    sampled[15] / sampled[16] if sampled[16] else np.nan,
                    sampled[17] / sampled[16] if sampled[16] else np.nan]
    names = ("target_first", "mean_net_r_base", "mean_net_r_stress",
             "momentum_target_first", "random_target_first",
             "paired_delta_precision_vs_momentum", "paired_delta_net_r_vs_momentum",
             "paired_delta_precision_vs_random", "paired_delta_net_r_vs_random")
    return {name: [float(x) for x in np.nanquantile(stats[:, i], [0.025, 0.975])]
            for i, name in enumerate(names)}


def summarize(events, eligible, eligible_by_symbol):
    scored = [e for e in events if e["status"] == "SCORED"]
    unscorable = sum(e["status"] == "UNSCORABLE" for e in events)
    out = {"eligible_decision_anchors": int(eligible), "events_emitted": len(events),
           "scored_events": len(scored), "unscorable_events": unscorable,
           "coverage": len(scored) / eligible if eligible else 0.0}
    for label, key in (("candidate", "candidate"), ("momentum_5m", "momentum_5m"),
                       ("fixed_random", "fixed_random")):
        rows = [e[key] for e in scored] if label == "candidate" else [
            e["baselines"][label] for e in scored if e["baselines"][label] is not None]
        targets = sum(r["outcome"] == "TARGET" for r in rows)
        out[label] = {"n": len(rows), "target": targets,
                      "stop": sum(r["outcome"] == "STOP" for r in rows),
                      "timeout": sum(r["outcome"] == "TIMEOUT" for r in rows),
                      "target_first": targets / len(rows) if rows else None,
                      "wilson95": wilson(targets, len(rows)),
                      "net_positive_base": float(np.mean([r["net_positive_base"] for r in rows])) if rows else None,
                      "net_positive_stress": float(np.mean([r["net_positive_stress"] for r in rows])) if rows else None,
                      "mean_net_r_base": float(np.mean([r["net_r_base"] for r in rows])) if rows else None,
                      "mean_net_r_stress": float(np.mean([r["net_r_stress"] for r in rows])) if rows else None}
    out["candidate"]["block_95_7d"] = bootstrap(events)
    symbols = {}
    for symbol in sorted(eligible_by_symbol):
        sub = [e for e in scored if e["symbol"] == symbol]
        n = len(sub)
        signals = [e for e in events if e["symbol"] == symbol]
        symbols[symbol] = {"eligible_decision_anchors": eligible_by_symbol[symbol],
                           "events_emitted": len(signals), "scored_n": n,
                           "coverage": n / eligible_by_symbol[symbol] if eligible_by_symbol[symbol] else 0.0,
                           "target_first": sum(e["candidate"]["outcome"] == "TARGET" for e in sub) / n if n else None,
                           "mean_net_r_base": float(np.mean([e["candidate"]["net_r_base"] for e in sub])) if n else None}
    out["per_symbol"] = symbols
    out["symbol_count"] = len({e["symbol"] for e in scored})
    out["largest_symbol_share"] = max((v["n"] for v in symbols.values()), default=0) / len(scored) if scored else None
    return out


def render_markdown(report):
    s = report["summary"]
    lines = [
        "# Crypto BTC 4h macro / 5m sweep-MSS: development probe", "",
        "**Status: exploratory development only.** The input interval was previously exposed; this result is not a sealed/OOS evaluation, calibrated M4 result, or trading recommendation.", "",
        f"- Hypothesis trials: {report['hypothesis_trial_count']}",
        f"- Window: `{report['start_utc']}` to exclusive `{report['cutoff_exclusive_utc']}` UTC",
        f"- Symbols in frozen cohort: {len(report['symbols'])}; scored source rows: {report['source_row_count']:,}",
        f"- BTC-only pre-window warm-up rows: {report['btc_macro_warmup_rows']:,}",
        f"- Fingerprint of used timestamp/OHLC rows: `{report['input_fingerprint_sha256']}`",
        f"- Coverage: {s['coverage']:.4%} ({s['scored_events']:,} scored / {s['eligible_decision_anchors']:,} eligible anchors)",
        f"- Events emitted: {s['events_emitted']:,}; scored: {s['scored_events']:,}; unscorable: {s['unscorable_events']:,}; symbols with scored events: {s['symbol_count']}; largest-symbol share: {s['largest_symbol_share'] if s['largest_symbol_share'] is not None else 'N/A'}",
        f"- Assumed round-trip cost cases: base {report['cost_assumptions_round_trip']['base']:.2%}, stress {report['cost_assumptions_round_trip']['stress']:.2%}. These are scenarios, not measured fills.",
        "- Not modeled: funding, slippage, spread, depth, fill probability, leverage, liquidation.", "",
        "## Candidate and matched baselines", "",
        "|Rule|N|Target|Stop|Timeout|Target-first|Wilson 95%|Net-positive base|Mean net R base|Mean net R stress|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("candidate", "momentum_5m", "fixed_random"):
        r = s[name]
        precision = "N/A" if r["target_first"] is None else f"{r['target_first']:.2%}"
        wilson_ci = "N/A" if r["wilson95"] is None else f"{r['wilson95'][0]:.2%}–{r['wilson95'][1]:.2%}"
        netpos = "N/A" if r["net_positive_base"] is None else f"{r['net_positive_base']:.2%}"
        base_r = "N/A" if r["mean_net_r_base"] is None else f"{r['mean_net_r_base']:.3f}"
        stress_r = "N/A" if r["mean_net_r_stress"] is None else f"{r['mean_net_r_stress']:.3f}"
        lines.append(f"|{name}|{r['n']}|{r['target']}|{r['stop']}|{r['timeout']}|{precision}|{wilson_ci}|{netpos}|{base_r}|{stress_r}|")
    lines.extend(["", "## Dependence-aware interval", ""])
    for metric, interval in s["candidate"].get("block_95_7d", {}).items():
        lines.append(f"- `{metric}`: {interval[0]:.5f} to {interval[1]:.5f}")
    lines.extend(["", "## Per-symbol outcomes", "",
                  "|Symbol|Eligible anchors|Emitted|Scored|Coverage|Target-first|Mean base net R|",
                  "|---|---:|---:|---:|---:|---:|---:|"])
    for symbol, r in s["per_symbol"].items():
        precision = "N/A" if r["target_first"] is None else f"{r['target_first']:.2%}"
        mean_r = "N/A" if r["mean_net_r_base"] is None else f"{r['mean_net_r_base']:.3f}"
        lines.append(f"|{symbol}|{r['eligible_decision_anchors']}|{r['events_emitted']}|{r['scored_n']}|{r['coverage']:.4%}|{precision}|{mean_r}|")
    lines.extend(["", "## Interpretation", "",
                  "This single fixed rule can be rejected as a development candidate if its target-first performance or fee-only expectancy is clearly inferior to matched controls. A favorable development result only permits consideration of prospective collection; it does not pass the user's goal. The final target still requires calibrated M4, at least 80% point precision, at least 10% coverage, N≥200 across at least 20 symbols, a dependence-aware lower bound above baselines, and positive expectancy after realistic costs. This run has no independent holdout and omits funding and execution friction.", "",
                  "Raw per-event outcomes and baseline scores are in the adjacent JSON artifact. No rule or parameter change is allowed on this interval after inspecting results.", ""])
    return "\n".join(lines)


def synthetic_checks():
    # Strict, confirmed 4h pivots: the second lower low is not known until bar 11 closes.
    n = 16
    t = np.arange(n, dtype=np.int64) * WIDTH_4H
    h, l = np.full(n, 10.0), np.full(n, 9.0)
    h[2], h[7], l[4], l[9] = 12, 14, 7, 8
    bars = {"t": t, "h": h, "l": l}
    state = macro_structure(bars)
    assert state[10] == 0 and state[11] == 1
    mutated = {k: v.copy() for k, v in bars.items()}
    mutated["h"][12:] *= 100
    mutated["l"][12:] /= 100
    assert np.array_equal(macro_structure(mutated)[:12], state[:12])

    # Complete aggregation rejects a missing-minute UTC bucket.
    times = np.arange(10, dtype=np.int64) * WIDTH_1M
    times = np.delete(times, 7)
    values = np.arange(len(times), dtype=float) + 100
    agg = complete_bars(times, values, values + 1, values - 1, values, 5 * WIDTH_1M)
    assert list(agg["t"]) == [0]

    # Strictly later MSS; same-bar confirmation is impossible.
    micro_t = np.arange(20, dtype=np.int64) * WIDTH_5M
    m = {"t": micro_t, "o": np.full(20, 100.0), "h": np.full(20, 101.0),
         "l": np.full(20, 99.0), "c": np.full(20, 100.0)}
    m["l"][12], m["c"][12] = 98.0, 100.0
    m["h"][13], m["c"][13] = 102.0, 101.5
    reg = np.ones(20, dtype=np.int8)
    assert find_first_mss(m, reg, 12, "long") == 13
    reg[13] = -1
    assert find_first_mss(m, reg, 12, "long") is None

    path_t = np.arange(50, dtype=np.int64) * WIDTH_1M
    op = np.full(50, 100.0); hi = np.full(50, 100.2); lo = np.full(50, 99.8); cl = np.full(50, 100.0)
    hi[0], lo[0] = 103.0, 97.0
    both = score_path("long", 100.0, 99.0, path_t, op, hi, lo, cl)
    assert both["outcome"] == "STOP" and both["exit_price"] == 99.0
    op[0], hi[0], lo[0] = 98.0, 99.0, 97.0
    gap = score_path("long", 100.0, 99.0, path_t, op, hi, lo, cl)
    assert gap["outcome"] == "STOP" and gap["exit_price"] == 98.0
    op[0], hi[0], lo[0] = 100.0, 100.2, 99.8
    timeout = score_path("long", 100.0, 99.0, path_t, op, hi, lo, cl)
    assert timeout["outcome"] == "TIMEOUT"
    print("HTF confirmation/future mutation/gap aggregation/sequential MSS/stop-first/gap-fill/timeout: PASS")


def load_run(db_path):
    db_path = Path(db_path).resolve()
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    try:
        symbols = [r[0] for r in db.execute(
            "SELECT DISTINCT symbol FROM candles WHERE t_open_ms>=? AND t_open_ms<? ORDER BY symbol",
            (START_MS, CUTOFF_MS))]
        btc_rows = db.execute(
            "SELECT t_open_ms,o,h,l,c FROM candles WHERE symbol='BTCUSDT' AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",
            (START_MS - 3 * 86_400_000, CUTOFF_MS)).fetchall()
        if not btc_rows:
            raise RuntimeError("BTC rows missing in frozen window")
        b = np.asarray(btc_rows, dtype=float)
        btc_1m = {"t": b[:, 0].astype(np.int64), "o": b[:, 1], "h": b[:, 2], "l": b[:, 3], "c": b[:, 4]}
        h4 = complete_bars(*(btc_1m[k] for k in ("t", "o", "h", "l", "c")), WIDTH_4H)
        macro = macro_structure(h4)
        digest = hashlib.sha256()
        btc_warmup = [row for row in btc_rows if int(row[0]) < START_MS]
        digest.update(b"BTC_WARMUP\0")
        for row in btc_warmup:
            digest.update(struct.pack("<q4d", int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4])))
        all_events, eligible_total, eligible_by_symbol, row_count = [], 0, {}, 0
        for number, symbol in enumerate(symbols, 1):
            rows = db.execute(
                "SELECT t_open_ms,o,h,l,c FROM candles WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",
                (symbol, START_MS, CUTOFF_MS)).fetchall()
            if not rows:
                continue
            a = np.asarray(rows, dtype=float)
            raw = {"t": a[:, 0].astype(np.int64), "o": a[:, 1], "h": a[:, 2], "l": a[:, 3], "c": a[:, 4]}
            digest.update(symbol.encode() + b"\0")
            for row in rows:
                digest.update(struct.pack("<q4d", int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4])))
            row_count += len(rows)
            micro = complete_bars(*(raw[k] for k in ("t", "o", "h", "l", "c")), WIDTH_5M)
            regime = regimes_for_micro(micro, h4, macro)
            eligible, events = scan_events(symbol, micro, regime, raw)
            eligible_total += eligible
            eligible_by_symbol[symbol] = eligible
            all_events.extend(events)
            print(f"symbols={number}/{len(symbols)} {symbol} bars5m={len(micro['t'])} eligible={eligible} events={len(events)}", flush=True)
    finally:
        db.close()
    report = {
        "title": "Crypto BTC 4h macro / 5m sweep-MSS fixed exploratory probe",
        "classification": "development-only; not sealed; not M4 calibrated; no live-trading claim",
        "hypothesis_trial_count": 1,
        "run_time_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                cwd=Path(__file__).resolve().parents[2],
                                                text=True).strip(),
        "python_version": platform.python_version(), "numpy_version": np.__version__,
        "start_utc": "2026-07-17T00:00:00Z", "cutoff_exclusive_utc": "2026-10-09T00:00:00Z",
        "source_db": str(db_path), "source_row_count": row_count,
        "btc_macro_warmup_rows": len(btc_warmup),
        "input_fingerprint_sha256": digest.hexdigest(), "symbols": symbols,
        "cost_assumptions_round_trip": {"base": BASE_COST, "stress": STRESS_COST},
        "causal_checks": ["complete-bar gap rejection", "confirmed HTF pivot and future-mutation invariance",
                          "negative-control premature pivot detected", "HTF completion-time alignment",
                          "strictly later MSS and cancellation on regime change", "1m stop-first ambiguity",
                          "adverse stop gap", "10-bar timeout"],
        "omitted": ["funding", "slippage", "spread", "depth", "fills", "leverage", "liquidation"],
        "summary": summarize(all_events, eligible_total, eligible_by_symbol), "events": all_events,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="SQLite candle database (read-only)")
    parser.add_argument("--out", type=Path, help="output JSON path")
    parser.add_argument("--md-out", type=Path, help="Markdown report path; defaults beside JSON")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        synthetic_checks()
        return
    if not args.db or not args.out:
        parser.error("--db and --out required")
    synthetic_checks()
    report = load_run(args.db)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    md_path = args.md_out or args.out.with_suffix(".md")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(report))
    print(f"report={args.out.resolve()}")
    print(f"markdown={md_path.resolve()}")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
