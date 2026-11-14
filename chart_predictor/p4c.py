"""Walk-forward and day-cluster analysis for the cached P4 feature set."""
import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

from . import probe
from .collector import DB_PATH
from .p3a import TIMEFRAMES, WIDTH
from .schema import HORIZON
from .splits import symbol_split
from .store import connect_trials, record_trial

BOOTSTRAPS = 1000
MODELS = ("logistic_l2", "hist_gradient_boosting")
LABELS = ("up_down", "expansion", "continuation")


def _load(cache, fingerprint, tf, target):
    db = sqlite3.connect(cache)
    query = "SELECT symbol,anchor,label,ret_atr,cont_label,cont_eligible,features FROM rows WHERE fingerprint=? AND tf=? ORDER BY anchor,symbol"
    rows = db.execute(query, (fingerprint, tf)).fetchall()
    db.close()
    names, times, returns, labels, vectors, atrs, keys = [], [], [], [], [], [], None
    h = HORIZON[tf] // (WIDTH[tf] // 60_000)
    for symbol, stamp, direction, ret, cont, eligible, encoded in rows:
        feat = json.loads(encoded)
        if keys is None: keys = sorted(feat)
        if target == "up_down":
            if direction not in probe.LABELS: continue
            y = probe.LABELS[direction]
        elif target == "continuation":
            if not eligible: continue
            y = int(cont)
        else: y = int(abs(ret) / math.sqrt(h))
        names.append(symbol); times.append(stamp); returns.append(ret); labels.append(y)
        atrs.append(float(feat.get("atr_pct", 0.0)))
        vectors.append([feat.get(k, 0.0) for k in keys])
    meta = {"symbols": np.asarray(names), "times": np.asarray(times, dtype=np.int64),
            "returns": np.asarray(returns, dtype=float), "atrs": np.asarray(atrs), "features": keys, "horizon": h}
    return meta, np.asarray(vectors, dtype=float), np.asarray(labels)


def _existing_cache(root):
    candidates = []
    for path in sorted(root.glob("features_*.sqlite")):
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            rows = db.execute("SELECT fingerprint,symbol,features FROM rows WHERE tf='60m' LIMIT 200").fetchall()
            if rows and all(symbol_split(row[1]) == "dev" for row in rows):
                feature = json.loads(rows[0][2])
                if "btcusdt_ret_1_atr" in feature: candidates.append((path, rows[0][0]))
        except sqlite3.Error:
            continue
        finally: db.close()
    if len(candidates) != 1: raise RuntimeError(f"expected one P4b market-context cache, found {len(candidates)}")
    return candidates[0]


def _fold_masks(times, fold, mode, symbols, held, purge_ms):
    edges = np.quantile(np.unique(times), np.linspace(.4, 1, 6))
    start, stop = edges[fold], edges[fold + 1]
    test = (times >= start) & (times <= stop if fold == 4 else times < stop)
    train = times < start - purge_ms
    if mode == "double_holdout":
        held_mask = np.isin(symbols, tuple(held))
        train &= ~held_mask
        test &= held_mask
    return train, test


def _holm(p_values):
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values); adjusted = np.empty(len(values)); running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (len(values) - rank) * values[idx]))
        adjusted[idx] = running
    return adjusted.tolist()


def _fast_weighted_auc(y, p, weights):
    order = np.argsort(p, kind="mergesort"); ys, ps, ws = y[order], p[order], weights[order]
    neg_before = 0.0; wins = 0.0; i = 0
    while i < len(ys):
        j = i + 1
        while j < len(ys) and ps[j] == ps[i]: j += 1
        pos = float(np.sum(ws[i:j][ys[i:j] == 1])); neg = float(np.sum(ws[i:j][ys[i:j] == 0]))
        wins += pos * (neg_before + .5 * neg); neg_before += neg; i = j
    positives = float(np.sum(weights[y == 1])); negatives = float(np.sum(weights[y == 0]))
    return wins / (positives * negatives) if positives and negatives else .5


def _cluster_bootstrap(y, p, days, baseline, seed, n=BOOTSTRAPS):
    rng = np.random.default_rng(seed); unique, inverse = np.unique(days, return_inverse=True)
    draws = rng.multinomial(len(unique), np.full(len(unique), 1/len(unique)), size=n)
    hit_by_day = np.bincount(inverse, weights=((p >= .5) == y).astype(float), minlength=len(unique))
    rows_per_day = np.bincount(inverse, minlength=len(unique))
    deltas = draws @ hit_by_day / (draws @ rows_per_day) - baseline
    _, score_group = np.unique(np.round(p, 3), return_inverse=True); groups = int(score_group.max()) + 1
    day_pos = np.zeros((len(unique), groups)); day_neg = np.zeros_like(day_pos)
    np.add.at(day_pos, (inverse[y == 1], score_group[y == 1]), 1)
    np.add.at(day_neg, (inverse[y == 0], score_group[y == 0]), 1)
    pos = draws @ day_pos; neg = draws @ day_neg
    negative_before = np.cumsum(neg, axis=1) - neg
    aucs = np.sum(pos * (negative_before + .5 * neg), axis=1) / (pos.sum(axis=1) * neg.sum(axis=1))
    return {"independent_days": int(len(unique)), "accuracy_minus_baseline_ci95": np.quantile(deltas, [.025, .975]).tolist(),
            "auc_ci95": np.quantile(aucs, [.025, .975]).tolist(),
            "auc_p": float((1 + np.sum(np.asarray(aucs) <= .5)) / (n + 1)),
            "bootstrap_resamples": n}


def _metrics(y, p, days, seed, bootstrap=True):
    pred = (p >= .5).astype(int); baseline = max(np.mean(y), 1 - np.mean(y))
    auc = float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None
    inference = _cluster_bootstrap(y, p, days, baseline, seed) if bootstrap else {"independent_days": int(len(np.unique(days)))}
    return {"n": len(y), "accuracy": float(np.mean(pred == y)), "auc": auc,
            "majority_baseline": float(baseline), "cluster_inference": inference}


def _expansion_target(scores, train, test):
    cutoff = float(np.median(scores[train]))
    return (scores[train] >= cutoff).astype(int), (scores[test] >= cutoff).astype(int), cutoff


def _fit_models(x_train, y_train, x_test, seed, limit=8000):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if len(y_train) > limit:
        indices = np.random.default_rng(seed).choice(len(y_train), limit, replace=False)
        x_train, y_train = x_train[indices], y_train[indices]
    models = {"logistic_l2": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
        LogisticRegression(C=1.0, max_iter=400, random_state=seed)),
        "hist_gradient_boosting": make_pipeline(SimpleImputer(strategy="median"),
        HistGradientBoostingClassifier(max_iter=30, learning_rate=.08, max_leaf_nodes=15,
                                       l2_regularization=1.0, random_state=seed))}
    return {name: (model.fit(x_train, y_train), model.predict_proba(x_test)[:, 1])
            for name, model in models.items()}


def _run_fold(meta, x, y, target, fold, mode, seed):
    times, symbols = meta["times"], meta["symbols"]
    unique = sorted(set(symbols)); held = set(unique[int(len(unique) * .7):])
    train, test = _fold_masks(times, fold, mode, symbols, held, meta["horizon"] * meta["width"])
    if target == "expansion":
        yt, yv, cutoff = _expansion_target(y.astype(float), train, test)
    else: yt, yv, cutoff = y[train], y[test], None
    result = {"n_train": int(min(train.sum(), 8000)), "n_train_available": int(train.sum()),
              "n_test": int(test.sum()), "expansion_train_threshold": cutoff,
              "expansion_train_positive_rate": float(np.mean(yt)) if target == "expansion" else None,
              "models": {}}
    if train.sum() < 10 or test.sum() < 2 or len(np.unique(yt)) < 2: return result
    fitted = _fit_models(x[train], yt, x[test], seed + fold)
    days = times[test] // 86_400_000
    for name, (_, p) in fitted.items():
        stats = _metrics(yv, p, days, seed + fold, bootstrap=False)
        stats["high_confidence"] = {str(t): probe._coverage(yv, p, t) for t in (.05, .10, .15, .20)}
        result["models"][name] = stats
    result["_target_y"] = yv.tolist()
    result["_test_days"] = days.tolist()
    result["_probabilities"] = {name: p.tolist() for name, (_, p) in fitted.items()}
    result["test_label_balance"] = {str(k): float(np.mean(yv == k)) for k in np.unique(yv)}
    return result


def _strategy_trade(frame, anchor_idx, direction, atr, horizon, threshold=2.0):
    entry_idx = anchor_idx + 1
    if entry_idx + horizon > len(frame): return None
    entry = float(frame.iloc[entry_idx].o); sign = 1 if direction > 0 else -1
    stop = entry - sign * threshold * atr; path = frame.iloc[entry_idx:entry_idx + horizon]
    exit_price = float(path.c.iloc[-1]); mae = 0.0; reason = "horizon"
    for row in path.itertuples():
        adverse = (entry - row.l) if sign > 0 else (row.h - entry)
        mae = max(mae, adverse / entry)
        crossed = row.l <= stop if sign > 0 else row.h >= stop
        if crossed:
            gap = row.o <= stop if sign > 0 else row.o >= stop
            exit_price = float(row.o if gap else stop); reason = "stop"; break
    net = sign * (exit_price / entry - 1) - 2 * (.0005 + .0002)
    return {"net": net, "mae": mae, "reason": reason}


def _strategy_summary(trades):
    values = np.asarray([r["net"] for r in trades], dtype=float)
    if not len(values): return {"n_trades": 0}
    losses = -values[values < 0]; gains = values[values > 0]
    return {"n_trades": len(values), "win_rate": float(np.mean(values > 0)),
            "mean_net_return": float(values.mean()), "median_net_return": float(np.median(values)),
            "profit_factor": float(gains.sum() / losses.sum()) if losses.sum() else None,
            "sharpe_like": float(values.mean() / values.std(ddof=1)) if len(values) > 1 and values.std(ddof=1) else None,
            "max_adverse_excursion": float(max(r["mae"] for r in trades))}


def _strategy_fold(meta, x, target, fold, mode, seed, candles_db, threshold):
    symbols, times = meta["symbols"], meta["times"]
    y = target.copy(); held = set(sorted(set(symbols))[int(len(set(symbols))*.7):])
    masks = _fold_masks(times, fold, mode, symbols, held, meta["horizon"] * meta["width"])
    train, test = masks
    if train.sum() < 10 or test.sum() < 2 or len(np.unique(y[train])) < 2: return {}
    models = probe._fit_models(x[train], y[train], x[test], seed + fold)
    probs = {name: pair[1] for name, pair in models.items()}
    return _strategy_account(meta, test, probs, fold, threshold, candles_db, seed, symbols, times)


def _strategy_account(meta, test, probs, fold, thresholds, candles_db, seed, symbols, times):
    from .p3a import _frame
    db = sqlite3.connect(Path(candles_db).resolve().as_uri() + "?mode=ro", uri=True)
    by_symbol = {}
    try:
        for symbol in sorted(set(symbols[test])): by_symbol[symbol] = _frame(db, symbol, meta["tf"])
    finally: db.close()
    strategies = {f"{model}_t{threshold:.2f}": [] for model in probs for threshold in thresholds}
    strategies.update({"prior_move": [], "random_direction": []})
    last_exit = {}; candidate_indices = np.flatnonzero(test)
    for rank, row_idx in enumerate(candidate_indices):
        symbol = symbols[row_idx]; frame = by_symbol[symbol]
        pos = int(np.searchsorted(frame.t_open_ms.to_numpy(), times[row_idx] - meta["width"]))
        if pos < 5 or pos + meta["horizon"] + 1 > len(frame): continue
        previous = float(frame.c.iloc[pos-1] - frame.c.iloc[pos-5]); direction = 1 if previous > 0 else -1
        atr = float(meta["atrs"][row_idx] * frame.c.iloc[pos-1])
        if abs(previous) <= atr: continue
        entry_idx = pos + 1; exit_idx = entry_idx + meta["horizon"] - 1
        if entry_idx <= last_exit.get(symbol, -1): continue
        for model, p in probs.items():
            for threshold in thresholds:
                if abs(float(p[rank]) - .5) >= threshold:
                    trade = _strategy_trade(frame, pos, direction, atr, meta["horizon"])
                    if trade: strategies[f"{model}_t{threshold:.2f}"].append(trade)
        strategies["prior_move"].append(_strategy_trade(frame, pos, direction, atr, meta["horizon"]))
        random_side = 1 if np.random.default_rng(seed + int(times[row_idx]) + rank).integers(2) else -1
        strategies["random_direction"].append(_strategy_trade(frame, pos, random_side, atr, meta["horizon"]))
        last_exit[symbol] = exit_idx
    return {name: {"summary": _strategy_summary([trade for trade in trades if trade]),
                   "raw": [trade for trade in trades if trade]} for name, trades in strategies.items()}


def _pooled(y_parts, p_parts, day_parts, seed):
    return _metrics(np.concatenate(y_parts), np.concatenate(p_parts), np.concatenate(day_parts), seed)


def _evaluate_target(meta, x, y, target, mode, seed):
    folds, ys, days, probabilities = {}, {m: [] for m in MODELS}, {m: [] for m in MODELS}, {m: [] for m in MODELS}
    held = set(sorted(set(meta["symbols"]))[int(len(set(meta["symbols"]))*.7):])
    for fold in range(5):
        train, test = _fold_masks(meta["times"], fold, mode, meta["symbols"], held, meta["horizon"]*meta["width"])
        result = _run_fold(meta, x, y, target, fold, mode, seed)
        folds[f"fold_{fold+1}"] = result
        if not result["models"]: continue
        yt = np.asarray(result.pop("_target_y")); fold_days = np.asarray(result.pop("_test_days"))
        fold_probabilities = result.pop("_probabilities")
        for name, p in fold_probabilities.items():
            ys[name].append(yt); probabilities[name].append(np.asarray(p)); days[name].append(fold_days)
    pooled = {name: _pooled(ys[name], probabilities[name], days[name], seed) for name in MODELS if ys[name]}
    return {"folds": folds, "pooled": pooled}


def _evaluate_strategy(meta, x, y, mode, seed, data_db):
    output = {}
    held = set(sorted(set(meta["symbols"]))[int(len(set(meta["symbols"]))*.7):])
    for fold in range(5):
        train, test = _fold_masks(meta["times"], fold, mode, meta["symbols"], held, meta["horizon"]*meta["width"])
        if train.sum() < 10 or test.sum() < 2 or len(np.unique(y[train])) < 2: continue
        fitted = _fit_models(x[train], y[train], x[test], seed+fold)
        probs = {name: pair[1] for name, pair in fitted.items()}
        output[f"fold_{fold+1}"] = _strategy_account(meta, test, probs, fold, (.10, .20), data_db, seed, meta["symbols"], meta["times"])
    keys = sorted({key for fold_data in output.values() for key in fold_data})
    output["pooled"] = {key: _strategy_summary([trade for fold_data in output.values()
                          if isinstance(fold_data, dict) and key in fold_data
                          for trade in fold_data[key]["raw"]]) for key in keys}
    for fold_name in list(output):
        if fold_name != "pooled":
            output[fold_name] = {key: value["summary"] for key, value in output[fold_name].items()}
    return output


def _adjust_holm(report):
    refs = []
    for timeframes in report["timeframes"].values():
        for labels in timeframes.values():
            for split in labels.values():
                for metric in split["pooled"].values(): refs.append(metric["cluster_inference"])
    corrected = _holm([metric["auc_p"] for metric in refs])
    for metric, value in zip(refs, corrected): metric["auc_p_holm"] = value


def _render(report):
    lines = ["# P4c walk-forward and clustered inference", "", f"Fingerprint: `{report['fingerprint']}`", "",
             "Five consecutive test folds use expanding training data and a one-horizon purge. Each fit uses at most 8,000 deterministic sampled training rows; all test rows remain included. The design has 12 timeframe/label cells, two splits, and two models (48 pooled model evaluations). Bootstrap resamples calendar days and all symbols within each day, 1,000 times; AUC probabilities are grouped to 0.001 for the bootstrap calculation. Holm correction covers all 48 pooled evaluations. Strategy: next candle open, 2 ATR stop, 1x, fee 0.05% and slippage 0.02% per side.", ""]
    for tf, labels in report["timeframes"].items():
        lines += [f"## {tf}", ""]
        for label, splits in labels.items():
            lines += [f"### {label}", "", "| Split | Fold | Model | n train/test | Accuracy | AUC | Majority | Days | Acc-baseline 95% CI | AUC 95% CI | AUC p | Holm p |", "|---|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|"]
            for split_name, data in splits.items():
                for fold_name, result in data["folds"].items():
                    for model, m in result.get("models", {}).items():
                        ci = m["cluster_inference"]
                        lines.append(f"| {split_name} | {fold_name} | {model} | {result['n_train']}/{result['n_test']} | {m['accuracy']:.4f} | {m['auc']} | {m['majority_baseline']:.4f} | {ci['independent_days']} | - | - | pooled only | - |")
                for model, m in data["pooled"].items():
                    ci = m["cluster_inference"]
                    acc_ci = ci["accuracy_minus_baseline_ci95"]; auc_ci = ci["auc_ci95"]
                    lines.append(f"| {split_name} | pooled | {model} | - | {m['accuracy']:.4f} | {m['auc']:.4f} | {m['majority_baseline']:.4f} | {ci['independent_days']} | [{acc_ci[0]:.4f},{acc_ci[1]:.4f}] | [{auc_ci[0]:.4f},{auc_ci[1]:.4f}] | {ci['auc_p']:.4f} | {ci['auc_p_holm']:.4f} |")
                lines += ["", "High confidence (threshold, coverage, n, accuracy):", "", "| Split | Fold | Model | Threshold | Coverage | n | Accuracy |", "|---|---|---|---:|---:|---:|---:|"]
                for split_name, data in splits.items():
                    for fold_name, result in data["folds"].items():
                        for model, m in result.get("models", {}).items():
                            for threshold, subset in m.get("high_confidence", {}).items():
                                lines.append(f"| {split_name} | {fold_name} | {model} | {threshold} | {subset['coverage']:.4f} | {subset['n']} | {subset['accuracy']} |")
                if label == "continuation":
                    lines += ["", "Strategy results (returns in fractional units; stop/fee/slippage applied):", "", "| Split | Fold | Rule | Trades | Win rate | Mean net | Median net | Profit factor | Sharpe-like | Max MAE |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
                    for split_name, data in splits.items():
                        for fold_name, result in data.get("strategy", {}).items():
                            if fold_name == "pooled": continue
                            for rule, item in result.items():
                                lines.append(_strategy_line(split_name, fold_name, rule, item))
                        for rule, item in data.get("strategy", {}).get("pooled", {}).items():
                            lines.append(_strategy_line(split_name, "pooled", rule, item))
            lines.append("")
    return "\n".join(lines)


def _strategy_line(split, fold, rule, item):
    return f"| {split} | {fold} | {rule} | {item.get('n_trades', 0)} | {item.get('win_rate')} | {item.get('mean_net_return')} | {item.get('median_net_return')} | {item.get('profit_factor')} | {item.get('sharpe_like')} | {item.get('max_adverse_excursion')} |"


def run_p4c(data_db=DB_PATH, output_dir=None, trials_db=None, seed=1):
    """Run five-fold walk-forward over the existing P4 feature cache."""
    started = time.monotonic(); root = Path(output_dir or Path(__file__).parent / "data" / "probe")
    root.mkdir(parents=True, exist_ok=True)
    cache, fingerprint = _existing_cache(root)
    cache_db = sqlite3.connect(f"file:{cache.resolve()}?mode=ro", uri=True)
    try: dataset_rows = cache_db.execute("SELECT COUNT(*) FROM rows WHERE fingerprint=?", (fingerprint,)).fetchone()[0]
    finally: cache_db.close()
    report = {"fingerprint": fingerprint, "seed": seed, "folds": 5, "bootstrap_resamples": BOOTSTRAPS,
              "feature_cache": str(cache), "dataset_rows": dataset_rows,
              "base_label_timeframe_cells": 12, "inference_cells": 24,
              "model_inference_cells": 48, "training_sample_cap_per_fold": 8000,
              "bootstrap_auc_probability_rounding_decimals": 3,
              "strategy_parameters": {"entry_delay_candles": 1, "stop_atr": 2.0, "leverage": 1,
                  "taker_fee_per_side": .0005, "slippage_per_side": .0002,
                  "confidence_thresholds": [.10, .20]}, "timeframes": {}}
    for tf in TIMEFRAMES:
        report["timeframes"][tf] = {}
        for target in LABELS:
            meta, x, y = _load(cache, fingerprint, tf, target)
            if not len(y): continue
            meta["width"] = WIDTH[tf]
            meta["tf"] = tf
            if target == "expansion": y = np.abs(meta["returns"]) / math.sqrt(meta["horizon"])
            report["timeframes"][tf][target] = {}
            for mode in ("temporal", "double_holdout"):
                report["timeframes"][tf][target][mode] = _evaluate_target(meta, x, y, target, mode, seed)
                if target == "continuation":
                    report["timeframes"][tf][target][mode]["strategy"] = _evaluate_strategy(meta, x, y, mode, seed, data_db)
    _adjust_holm(report)
    report["runtime_seconds"] = time.monotonic() - started
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    json_path = root / f"report_p4c_{fingerprint}.json"; md_path = root / f"report_p4c_{fingerprint}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False)); md_path.write_text(_render(report) + "\n")
    trials = connect_trials(trials_db)
    try: record_trial(trials, report["created_at"], "probe", "p4c", "p4c", "dev", "P4c walk-forward + cluster bootstrap + strategy test", dataset_rows, fingerprint)
    finally: trials.close()
    return {"report_json": str(json_path), "report_md": str(md_path), "runtime_seconds": report["runtime_seconds"], "fingerprint": fingerprint}
