"""Fixed one-minute close-location triple-barrier study; read-only SQLite."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

MINUTE = 60_000
ATR_N = 14
BASE_COST = 0.0014
STRESS_COST = 0.0028
SEED = 20261118
DATA_SHA256 = "bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa"
WINDOWS = [
    ("2023-05-20", "2024-01-27"),
    ("2024-01-27", "2024-10-05"),
    ("2024-10-05", "2025-06-14"),
    ("2025-06-14", "2026-02-21"),
    ("2026-02-21", "2026-10-31"),
]


def ms(date: str) -> int:
    return int(pd.Timestamp(date, tz="UTC").timestamp() * 1000)


def load_symbol(db: sqlite3.Connection, symbol: str) -> tuple[np.ndarray, ...]:
    frame = pd.read_sql_query(
        "SELECT open_ms,open AS o,high AS h,low AS l,close AS c FROM candles WHERE symbol=? ORDER BY open_ms",
        db, params=(symbol,),
    )
    t = frame.open_ms.to_numpy(np.int64)
    o, h, l, c = (frame[k].to_numpy(np.float64) for k in ("o", "h", "l", "c"))
    valid = (np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c)
             & (l > 0) & (h >= np.maximum.reduce([o, c, l]))
             & (l <= np.minimum.reduce([o, c, h])))
    contiguous = np.r_[False, np.diff(t) == MINUTE]
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[np.nan, c[:-1]]),
                                       np.abs(l - np.r_[np.nan, c[:-1]])))
    atr = pd.Series(tr).rolling(ATR_N, min_periods=ATR_N).mean().to_numpy()
    atr_valid = np.zeros(len(t), dtype=bool)
    for i in range(ATR_N, len(t)):
        atr_valid[i] = (np.all(contiguous[i - ATR_N + 1:i + 1])
                        and np.all(valid[i - ATR_N + 1:i + 1]))
    atr[~atr_valid | ~valid] = np.nan
    feature_valid = valid & np.isfinite(atr) & (h > l) & contiguous
    clv = np.divide(c - l, h - l, out=np.full(len(c), np.nan), where=h > l)
    signal = np.zeros(len(c), dtype=np.int8)
    signal[feature_valid & (clv >= 0.8)] = 1
    signal[feature_valid & (clv <= 0.2)] = -1
    # Emission is fixed at anchor close. Entry/path availability is scored later;
    # do not erase issued signals merely because the next row is absent.
    return t, o, h, l, c, atr, signal, valid, contiguous


def sha_side(symbol: str, timestamp: int, tag: str) -> int:
    bit = hashlib.sha256(f"{SEED}|{tag}|{symbol}|{timestamp}".encode()).digest()[0] & 1
    return 1 if bit == 0 else -1


def score_signal(t, o, h, l, c, atr, index, side, horizon):
    entry_i = index + 1
    if entry_i + horizon > len(t) or not np.isfinite(atr[index]):
        return None
    if t[entry_i] != t[index] + MINUTE:
        return None
    path = np.arange(entry_i, entry_i + horizon)
    if np.any(np.diff(t[path]) != MINUTE):
        return None
    if not np.all(np.isfinite(np.r_[o[path], h[path], l[path], c[path]])):
        return None
    if (np.any(h[path] < np.maximum.reduce([o[path], c[path], l[path]]))
            or np.any(l[path] > np.minimum.reduce([o[path], c[path], h[path]]))
            or np.any(l[path] <= 0)):
        return None
    entry = float(o[entry_i])
    risk = float(atr[index])
    if entry <= 0 or risk <= 0:
        return (False, False, 0.0, False, 0.0)
    stop = entry - side * risk
    target = entry + side * risk
    # Any already-crossed barrier at entry is a resolved no-trade failure.
    if (side > 0 and (entry <= stop or entry >= target)) or (side < 0 and (entry >= stop or entry <= target)):
        return (False, False, 0.0, False, 0.0)
    outcome, exit_price = "TIMEOUT", float(c[path[-1]])
    for j in path:
        stop_hit = l[j] <= stop if side > 0 else h[j] >= stop
        target_hit = h[j] >= target if side > 0 else l[j] <= target
        if stop_hit:
            exit_price = min(float(o[j]), stop) if side > 0 else max(float(o[j]), stop)
            outcome = "STOP"
            break
        if target_hit:
            exit_price, outcome = target, "TARGET"
            break
    gross = side * (exit_price / entry - 1.0)
    net_r_base = (gross - BASE_COST) / (risk / entry)
    net_r_stress = (gross - STRESS_COST) / (risk / entry)
    direction = side * (float(c[path[-1]]) / entry - 1.0) > 0
    return (outcome == "TARGET", outcome == "TIMEOUT", net_r_base,
            bool(direction), net_r_stress)


def score_chunk(t, o, h, l, c, atr, indexes, sides, horizon, symbol):
    n = len(indexes)
    # Columns: resolved, target-first, timeout, deadline direction, base/stress net-R,
    # momentum/random target-first, UTC day, anchor index.
    result = np.zeros((n, 10), dtype=np.float64)
    result[:, 9] = indexes
    entry_i = indexes + 1
    complete = entry_i + horizon <= len(t)
    rows = np.flatnonzero(complete)
    if not len(rows):
        return result
    ii = indexes[rows]
    ee = entry_i[rows]
    side = sides[rows].astype(np.int8)
    path_i = ee[:, None] + np.arange(horizon, dtype=np.int64)[None, :]
    path_t = t[path_i]
    path_valid = ((t[ee] == t[indexes[rows]] + MINUTE)
                  & np.all(np.diff(path_t, axis=1) == MINUTE, axis=1))
    op, hi, lo, cl = o[path_i], h[path_i], l[path_i], c[path_i]
    candle_valid = (np.isfinite(op) & np.isfinite(hi) & np.isfinite(lo) & np.isfinite(cl)
                    & (lo > 0) & (hi >= np.maximum.reduce([op, cl, lo]))
                    & (lo <= np.minimum.reduce([op, cl, hi])))
    resolved = path_valid & np.all(candle_valid, axis=1)
    entry, risk = o[ee], atr[ii]
    resolved &= np.isfinite(entry) & (entry > 0) & np.isfinite(risk) & (risk > 0)
    active = np.flatnonzero(resolved)
    if not len(active):
        return result

    def barriers(direction):
        d = direction[active].astype(np.int8)
        ent, r = entry[active], risk[active]
        hh, ll, oo = hi[active], lo[active], op[active]
        stop = ent - d * r
        target = ent + d * r
        stop_hit = np.where(d[:, None] > 0, ll <= stop[:, None], hh >= stop[:, None])
        target_hit = np.where(d[:, None] > 0, hh >= target[:, None], ll <= target[:, None])
        any_hit = stop_hit | target_hit
        first = np.argmax(any_hit, axis=1)
        has_hit = np.any(any_hit, axis=1)
        row_ix = np.arange(len(active))
        stop_first = has_hit & stop_hit[row_ix, first]
        target_first = has_hit & target_hit[row_ix, first] & ~stop_first
        exit_price = cl[active, -1].copy()
        hit_price = np.where(d > 0,
                             np.where(oo[row_ix, first] <= stop, oo[row_ix, first], stop),
                             np.where(oo[row_ix, first] >= stop, oo[row_ix, first], stop))
        exit_price[stop_first] = hit_price[stop_first]
        exit_price[target_first] = target[target_first]
        gross = d * (exit_price / ent - 1.0)
        net_base = (gross - BASE_COST) / (r / ent)
        net_stress = (gross - STRESS_COST) / (r / ent)
        direction_hit = d * (cl[active, -1] / ent - 1.0) > 0
        return target_first, ~has_hit, direction_hit, net_base, net_stress

    cand = barriers(side)
    result[rows[active], 0] = 1
    result[rows[active], 1] = cand[0]
    result[rows[active], 2] = cand[1]
    result[rows[active], 3] = cand[2]
    result[rows[active], 4] = cand[3]
    result[rows[active], 5] = cand[4]
    mom = np.where(c[ii] > o[ii], 1, np.where(c[ii] < o[ii], -1,
                     np.fromiter((sha_side(symbol, int(x), "momentum-zero") for x in t[ii]), dtype=np.int8, count=len(ii))))
    rand = np.fromiter((sha_side(symbol, int(x), "random") for x in t[ii]), dtype=np.int8, count=len(ii))
    result[rows[active], 6] = barriers(mom)[0]
    result[rows[active], 7] = barriers(rand)[0]
    result[rows[active], 8] = t[ii[active]] // 86_400_000
    return result


def empty_agg() -> dict:
    return {"issued": 0, "resolved": 0, "wins": 0, "timeouts": 0,
            "directions": 0, "mom_wins": 0, "random_wins": 0,
            "base_r": 0.0, "stress_r": 0.0, "symbols": set()}


def add_agg(agg: dict, x: np.ndarray, symbol: str) -> None:
    if not len(x):
        return
    resolved = x[:, 0] == 1
    agg["issued"] += len(x)
    agg["resolved"] += int(resolved.sum())
    agg["wins"] += int(x[resolved, 1].sum())
    agg["timeouts"] += int(x[resolved, 2].sum())
    agg["directions"] += int(x[resolved, 3].sum())
    agg["mom_wins"] += int(x[resolved, 6].sum())
    agg["random_wins"] += int(x[resolved, 7].sum())
    agg["base_r"] += float(x[resolved, 4].sum())
    agg["stress_r"] += float(x[resolved, 5].sum())
    agg["symbols"].add(symbol)


def summarize(agg: dict) -> dict:
    nres, wins = agg["resolved"], agg["wins"]
    return {
        "n_issued": agg["issued"], "n_resolved": nres,
        "n_unresolved": agg["issued"] - nres,
        "path_resolution": nres / agg["issued"] if agg["issued"] else None,
        "target_first": wins / nres if nres else None,
        "target_first_all_issued_conservative": wins / agg["issued"] if agg["issued"] else None,
        "n_timeout": agg["timeouts"],
        "direction_at_deadline": agg["directions"] / nres if nres else None,
        "matched_momentum_target_first": agg["mom_wins"] / nres if nres else None,
        "matched_random_target_first": agg["random_wins"] / nres if nres else None,
        "mean_net_r_base": agg["base_r"] / nres if nres else None,
        "mean_net_r_stress": agg["stress_r"] / nres if nres else None,
        "n_symbols": len(agg["symbols"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path(__file__).parent / "data/vision_pit_dev_sample.sqlite")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--checkpoint", type=Path)
    ap.add_argument("--chunk-size", type=int, default=100_000)
    args = ap.parse_args()
    checkpoint = args.checkpoint or (args.output.with_suffix(".checkpoint.json") if args.output else None)
    db = sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True)
    symbols = [r[0] for r in db.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")]
    reports = {h: [empty_agg() for _ in range(5)] for h in (10, 20)}
    nonoverlap_reports = {h: [empty_agg() for _ in range(5)] for h in (10, 20)}
    coverage = {h: {f"fold_{i+1}": {"eligible": 0, "issued": 0, "symbols": set()}
                    for i in range(5)} for h in (10, 20)}
    pooled = {h: [] for h in (10, 20)}
    nonoverlap = {h: [] for h in (10, 20)}
    processed = set()
    if checkpoint and checkpoint.exists():
        saved = json.loads(checkpoint.read_text())
        if saved.get("data_sha256") != DATA_SHA256:
            raise ValueError("checkpoint data fingerprint mismatch")
        processed = set(saved["processed"])
        for h in (10, 20):
            for i in range(5):
                for target, source in ((reports, saved["reports"]),
                                       (nonoverlap_reports, saved["nonoverlap_reports"])):
                    target[h][i] = {**source[str(h)][i], "symbols": set(source[str(h)][i]["symbols"])}
        for h in (10, 20):
            for i in range(5):
                item = saved["coverage"][str(h)][i]
                coverage[h][f"fold_{i+1}"] = {**item, "symbols": set(item["symbols"])}
        print(f"resume checkpoint: completed={len(processed)}/{len(symbols)}", flush=True)
    for symbol in symbols:
        if symbol in processed:
            continue
        t, o, h, l, c, atr, signal, valid, contiguous = load_symbol(db, symbol)
        eligible = np.flatnonzero(np.isfinite(atr) & valid & contiguous)
        issued = np.flatnonzero(signal != 0)
        if not len(issued):
            continue
        for fi, (start, end) in enumerate(WINDOWS):
            lo, hi = ms(start), ms(end)
            for horizon in (10, 20):
                idx = issued[(t[issued] + MINUTE >= lo)
                             & (t[issued] + (horizon + 1) * MINUTE <= hi)]
                anchors = eligible[(t[eligible] + MINUTE >= lo)
                                   & (t[eligible] + (horizon + 1) * MINUTE <= hi)]
                coverage[horizon][f"fold_{fi+1}"]["eligible"] += len(anchors)
                coverage[horizon][f"fold_{fi+1}"]["issued"] += len(idx)
                if len(idx):
                    coverage[horizon][f"fold_{fi+1}"]["symbols"].add(symbol)
                nonoverlap_idx = []
                cursor = 0
                while cursor < len(idx):
                    nonoverlap_idx.append(idx[cursor])
                    cursor = int(np.searchsorted(idx, idx[cursor] + horizon, side="left"))
                for offset in range(0, len(idx), args.chunk_size):
                    batch = idx[offset:offset + args.chunk_size]
                    scored = score_chunk(t, o, h, l, c, atr, batch, signal[batch], horizon, symbol)
                    add_agg(reports[horizon][fi], scored, symbol)
                selected = np.asarray(nonoverlap_idx, dtype=np.int64)
                for offset in range(0, len(selected), args.chunk_size):
                    batch = selected[offset:offset + args.chunk_size]
                    scored = score_chunk(t, o, h, l, c, atr, batch, signal[batch], horizon, symbol)
                    add_agg(nonoverlap_reports[horizon][fi], scored, symbol)
        print(f"done {symbol}: rows={len(t):,} signals={len(issued):,}", flush=True)
        processed.add(symbol)
        if checkpoint:
            state = {
                "data_sha256": DATA_SHA256, "processed": sorted(processed),
                "reports": {str(h): [{**a, "symbols": sorted(a["symbols"])} for a in reports[h]] for h in (10, 20)},
                "nonoverlap_reports": {str(h): [{**a, "symbols": sorted(a["symbols"])} for a in nonoverlap_reports[h]] for h in (10, 20)},
                "coverage": {str(h): [{**coverage[h][f"fold_{i+1}"], "symbols": sorted(coverage[h][f"fold_{i+1}"]["symbols"])} for i in range(5)] for h in (10, 20)},
            }
            temporary = checkpoint.with_suffix(checkpoint.suffix + ".tmp")
            temporary.write_text(json.dumps(state, separators=(",", ":")))
            temporary.replace(checkpoint)
    db.close()
    out = {"protocol": "micro-candle-phase4-m2", "data_sha256": DATA_SHA256,
           "symbols": len(symbols), "signal": "1m close-location upper/lower 20%",
           "stop_target": "1 ATR14 each", "entry": "next contiguous 1m open",
           "costs_round_trip": {"base": BASE_COST, "stress": STRESS_COST},
           "coverage": {f"{h}m": {k: {"eligible": v["eligible"], "issued": v["issued"],
                            "rate": v["issued"] / v["eligible"] if v["eligible"] else None,
                            "symbols": len(v["symbols"])} for k, v in folds.items()}
                        for h, folds in coverage.items()},
           "claims": {}, "nonoverlap": {f"{h}m": {} for h in (10, 20)}}
    for horizon in (10, 20):
        hkey = f"{horizon}m"
        out["claims"][hkey] = {}
        for fold in range(5):
            out["claims"][hkey][f"fold_{fold+1}"] = summarize(reports[horizon][fold])
            out["nonoverlap"][hkey][f"fold_{fold+1}"] = summarize(nonoverlap_reports[horizon][fold])
        pooled_agg = empty_agg()
        for fold_agg in reports[horizon]:
            for key in ("issued", "resolved", "wins", "timeouts", "directions", "mom_wins", "random_wins", "base_r", "stress_r"):
                pooled_agg[key] += fold_agg[key]
            pooled_agg["symbols"].update(fold_agg["symbols"])
        out["claims"][hkey]["pooled_oos"] = summarize(pooled_agg)
        pooled_nonoverlap = empty_agg()
        for fold_agg in nonoverlap_reports[horizon]:
            for key in ("issued", "resolved", "wins", "timeouts", "directions", "mom_wins", "random_wins", "base_r", "stress_r"):
                pooled_nonoverlap[key] += fold_agg[key]
            pooled_nonoverlap["symbols"].update(fold_agg["symbols"])
        out["nonoverlap"][hkey]["pooled_oos"] = summarize(pooled_nonoverlap)
    encoded = json.dumps(out, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded)


if __name__ == "__main__":
    main()
