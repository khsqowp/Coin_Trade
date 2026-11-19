#!/usr/bin/env python3
"""Fixed exploratory OHLCV vs OHLCV+taker-flow next-1m comparison."""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss, precision_recall_fscore_support
from sklearn.preprocessing import StandardScaler

SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
MINUTE = 60_000
TRAIN_START = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
TRAIN_END = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
EVAL_END = int(datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp() * 1000)
SEED = 20261119


def _load_symbol(db: sqlite3.Connection, symbol: str):
    start = TRAIN_START - 21 * MINUTE
    end = EVAL_END + MINUTE
    return db.execute(
        "SELECT open_ms,open,high,low,close,quote_volume,taker_buy_quote "
        "FROM candles WHERE symbol=? AND open_ms>=? AND open_ms<? ORDER BY open_ms",
        (symbol, start, end),
    ).fetchall()


def _make_rows(rows, symbol, quality_only=False):
    output = []
    audit = defaultdict(int)
    for i in range(20, len(rows) - 1):
        ts = rows[i][0]
        if not (TRAIN_START <= ts < EVAL_END):
            continue
        split = "train" if ts < TRAIN_END else "eval"
        audit[f"{split}_anchors"] += 1
        window = rows[i - 20 : i + 2]
        if any(window[j + 1][0] - window[j][0] != MINUTE for j in range(len(window) - 1)):
            audit[f"{split}_gap_excluded"] += 1
            continue
        if (split == "train" and rows[i + 1][0] >= TRAIN_END) or (split == "eval" and rows[i + 1][0] >= EVAL_END):
            audit[f"{split}_split_boundary_excluded"] += 1
            continue
        prev_close = rows[i - 1][4]
        o, h, low, c, qv, tq = rows[i][1:7]
        prev_volumes = [r[5] for r in rows[i - 20 : i]]
        if not all(np.isfinite(x) for x in (prev_close, o, h, low, c, qv, tq, *prev_volumes)):
            audit[f"{split}_nonfinite_excluded"] += 1
            continue
        if min(prev_close, o, h, low, c) <= 0 or h < max(o, c, low) or low > min(o, c, h):
            audit[f"{split}_ohlc_invalid_excluded"] += 1
            continue
        median_qv = float(np.median(prev_volumes))
        candle_range = h - low
        if qv <= 0 or min(prev_volumes) <= 0 or median_qv <= 0 or tq < 0 or tq > qv or candle_range <= 0:
            audit[f"{split}_flow_or_range_invalid_excluded"] += 1
            continue
        feature_base = [
            np.log(c / prev_close),
            candle_range / prev_close,
            (c - o) / candle_range,
            (h - max(o, c)) / candle_range,
            (min(o, c) - low) / candle_range,
            np.log(qv / median_qv),
        ]
        feature_flow = feature_base + [2.0 * tq / qv - 1.0]
        if not np.isfinite(feature_base).all() or not np.isfinite(feature_flow).all():
            audit[f"{split}_feature_nonfinite_excluded"] += 1
            continue
        if quality_only:
            output.append((symbol, ts, split, None, feature_base, feature_flow))
            audit[f"{split}_feature_eligible"] += 1
            continue
        target_close = rows[i + 1][4]
        if not np.isfinite(target_close) or target_close <= 0:
            audit[f"{split}_target_invalid_excluded"] += 1
            continue
        direction = int(target_close > c) - int(target_close < c)
        if direction == 0:
            audit[f"{split}_exact_flat_excluded"] += 1
            continue
        output.append((symbol, ts, split, direction, feature_base, feature_flow))
        audit[f"{split}_eligible"] += 1
        audit[f"{split}_{'up' if direction > 0 else 'down'}"] += 1
    return output, dict(audit)


def _metrics(y, pred, prob):
    pr, rc, _, support = precision_recall_fscore_support(y, pred, labels=[-1, 1], zero_division=0)
    return {
        "n": int(len(y)),
        "accuracy_pct": float(accuracy_score(y, pred) * 100),
        "balanced_accuracy_pct": float(balanced_accuracy_score(y, pred) * 100),
        "brier": float(brier_score_loss(y, prob, pos_label=1)),
        "log_loss": float(log_loss(y, np.column_stack([1 - prob, prob]), labels=[-1, 1])),
        "down_precision_pct": float(pr[0] * 100),
        "up_precision_pct": float(pr[1] * 100),
        "down_recall_pct": float(rc[0] * 100),
        "up_recall_pct": float(rc[1] * 100),
        "down_support": int(support[0]),
        "up_support": int(support[1]),
        "predicted_up_pct": float(np.mean(pred == 1) * 100),
    }


def run(db_path: Path, quality_only: bool):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    all_rows, audits = [], {}
    for symbol in SYMBOLS:
        rows, audit = _make_rows(_load_symbol(db, symbol), symbol, quality_only)
        all_rows.extend(rows)
        audits[symbol] = audit
    db.close()
    result = {
        "protocol": "micro-candle-flow-incremental-2026-11-19",
        "status": "outcome-blind-quality-only" if quality_only else "exploratory-exposed-history",
        "database": str(db_path),
        "symbols": list(SYMBOLS),
        "train_utc": ["2025-10-01T00:00:00Z", "2026-01-01T00:00:00Z"],
        "eval_utc": ["2026-01-01T00:00:00Z", "2026-04-01T00:00:00Z"],
        "quality_counts": audits,
        "eligible_rows": {
            part: sum(a.get(f"{part}_{'feature_eligible' if quality_only else 'eligible'}", 0) for a in audits.values())
            for part in ("train", "eval")
        },
    }
    if quality_only:
        return result

    rows_train = [r for r in all_rows if r[2] == "train"]
    rows_eval = [r for r in all_rows if r[2] == "eval"]
    if len(rows_train) < 1000 or len(rows_eval) < 1000:
        raise RuntimeError("eligible sample unexpectedly small")

    predictions = {"ohlcv": {}, "flow": {}}
    per_symbol = {}
    for symbol in SYMBOLS:
        tr = [r for r in rows_train if r[0] == symbol]
        ev = [r for r in rows_eval if r[0] == symbol]
        ytr = np.array([r[3] for r in tr])
        y = np.array([r[3] for r in ev])
        per_symbol[symbol] = {"train_n": int(len(tr)), "eval_n": int(len(ev))}
        for name, idx in (("ohlcv", 4), ("flow", 5)):
            xtr = np.asarray([r[idx] for r in tr], dtype=float)
            x = np.asarray([r[idx] for r in ev], dtype=float)
            scaler = StandardScaler().fit(xtr)
            model = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, random_state=SEED)
            model.fit(scaler.transform(xtr), ytr)
            prob_up = model.predict_proba(scaler.transform(x))[:, list(model.classes_).index(1)]
            pred = np.where(prob_up >= 0.5, 1, -1)
            predictions[name][symbol] = (y, pred, prob_up)
            per_symbol[symbol][name] = _metrics(y, pred, prob_up)
        # Non-model baselines use the same paired eligible anchors.
        majority = 1 if np.sum(ytr == 1) >= np.sum(ytr == -1) else -1
        persistence_pred = np.array([1 if r[4][0] >= 0 else -1 for r in ev])
        # Reversal is the inverse of the anchor close-to-close return.
        reversal_pred = -persistence_pred
        per_symbol[symbol]["baselines"] = {
            "train_majority_accuracy_pct": float(np.mean(y == majority) * 100),
            "persistence_accuracy_pct": float(np.mean(y == persistence_pred) * 100),
            "reversal_accuracy_pct": float(np.mean(y == reversal_pred) * 100),
        }

    pooled = {}
    for name in ("ohlcv", "flow"):
        yy = np.concatenate([predictions[name][s][0] for s in SYMBOLS])
        pp = np.concatenate([predictions[name][s][1] for s in SYMBOLS])
        probs = np.concatenate([predictions[name][s][2] for s in SYMBOLS])
        pooled[name] = _metrics(yy, pp, probs)
    paired = []
    for symbol in SYMBOLS:
        y1, p1, _ = predictions["ohlcv"][symbol]
        y2, p2, _ = predictions["flow"][symbol]
        if not np.array_equal(y1, y2):
            raise AssertionError("model comparison rows differ")
        for j, row in enumerate(r for r in rows_eval if r[0] == symbol):
            paired.append((symbol, row[1], int(y1[j]), int(p1[j]), int(p2[j]), 0))
    primary = {
        "paired_accuracy_delta_flow_minus_ohlcv_pp": float((pooled["flow"]["accuracy_pct"] - pooled["ohlcv"]["accuracy_pct"])),
        "log_loss_delta_flow_minus_ohlcv": pooled["flow"]["log_loss"] - pooled["ohlcv"]["log_loss"],
        "balanced_accuracy_delta_flow_minus_ohlcv_pp": pooled["flow"]["balanced_accuracy_pct"] - pooled["ohlcv"]["balanced_accuracy_pct"],
    }
    # Same-date pooled metric block bootstrap. Pair each model's correctness on each common UTC date.
    by_date = defaultdict(lambda: [0, 0, 0])
    for row in paired:
        day = datetime.fromtimestamp(row[1] / 1000, tz=timezone.utc).date().isoformat()
        by_date[day][0] += 1
        by_date[day][1] += int(row[3] == row[2])
        by_date[day][2] += int(row[4] == row[2])
    dates = sorted(by_date)
    contributions = np.asarray([by_date[day] for day in dates], dtype=np.int64)
    blocks = [np.arange(i, i + 7) for i in range(len(dates) - 6)]
    rng = np.random.default_rng(SEED)
    deltas = np.empty(5000)
    for b in range(len(deltas)):
        chosen = []
        while len(chosen) < len(dates):
            chosen.extend(blocks[int(rng.integers(len(blocks)))].tolist())
        counts = contributions[np.asarray(chosen[:len(dates)], dtype=int)].sum(axis=0)
        deltas[b] = counts[2] / counts[0] - counts[1] / counts[0]
    primary["paired_accuracy_bootstrap"] = {
        "dates": len(dates), "draws": 5000, "seed": SEED, "block_days": 7,
        "accuracy_delta_ci95_pp": [float(v * 100) for v in np.quantile(deltas, [0.025, 0.975])],
    }
    total_eval = sum(per_symbol[s]["eval_n"] for s in SYMBOLS)
    pooled_baselines = {
        key: float(sum(per_symbol[s]["eval_n"] * per_symbol[s]["baselines"][key] for s in SYMBOLS) / total_eval)
        for key in ("train_majority_accuracy_pct", "persistence_accuracy_pct", "reversal_accuracy_pct")
    }
    result.update({"per_symbol": per_symbol, "pooled": pooled, "pooled_baselines": pooled_baselines, "primary_comparison": primary})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("chart_predictor/data/vision_pit_dev_sample.sqlite"))
    parser.add_argument("--quality-only", action="store_true", help="do not compute or emit next-candle direction labels")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.db, args.quality_only)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
