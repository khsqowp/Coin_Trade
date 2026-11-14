"""Deterministic P3a baseline and agent-task workflows."""
import hashlib
import json
import math
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .baselines import emit_baseline
from .collector import DB_PATH
from .features import build_features, _digest
from .schema import HORIZON, validate_prediction
from .scorer import score_prediction
from .splits import split_anchors, symbol_split
from .stats import wilson
from .store import append_prediction, connect_store, connect_trials, record_score, record_trial

TIMEFRAMES = ("1m", "5m", "30m", "60m")
WIDTH = {"1m": 60_000, "5m": 300_000, "30m": 1_800_000, "60m": 3_600_000}
COLS = "t_open_ms,o,h,l,c,v,quote_v,trades"
BASELINES = ("momentum", "random", "flat", "always_up", "always_down")
FLAT_MULT = 0.25
BASELINE_VERSION = "p3a-flat025-v3"


def _readonly(path):
    """Open an existing candle DB without permitting SQLite writes."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _data_fingerprint(db, path):
    """Hash per-symbol aggregate coverage while recording file metadata separately."""
    aggregates = [list(row) for row in db.execute(
        "SELECT symbol,COUNT(*),MIN(t_open_ms),MAX(t_open_ms) FROM candles GROUP BY symbol ORDER BY symbol")]
    canonical = json.dumps(aggregates, separators=(",", ":"), ensure_ascii=False)
    stat = Path(path).stat()
    return {"sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "symbols": aggregates, "file_size_bytes": stat.st_size, "file_mtime_ns": stat.st_mtime_ns}


def _symbols(db, split, limit):
    """Return deterministically ordered symbols belonging to a split."""
    names = [r[0] for r in db.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")]
    selected = [name for name in names if symbol_split(name) == ("heldout" if split == "validation" else "dev")]
    return selected[:limit] if limit else selected


def _frame(db, symbol, tf):
    """Load one symbol and aggregate complete time buckets where needed."""
    from .resample import resample_frame
    raw = pd.read_sql_query(f"SELECT {COLS} FROM candles WHERE symbol=? ORDER BY t_open_ms", db, params=(symbol,))
    if tf == "1m":
        return raw
    return resample_frame(raw, tf, now_ms=int(raw.t_open_ms.iloc[-1]) + 60_000 if len(raw) else 0)


def _cell_anchors(frame, tf, split):
    """Produce horizon-spaced completed anchors for a temporal split."""
    if frame.empty:
        return frame.copy()
    stride = HORIZON[tf] // (WIDTH[tf] // 60_000)
    anchors = frame.iloc[14::stride].copy().reset_index(drop=True)
    anchors["anchor_time_ms"] = anchors.t_open_ms + WIDTH[tf]
    return split_anchors(anchors, split).reset_index(drop=True)


def _sample_indices(count, per_cell, seed, symbol, tf):
    """Sample stable positions independently in each symbol/timeframe cell."""
    token = int(hashlib.sha256(f"{symbol}:{tf}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), token]))
    return sorted(rng.choice(count, min(count, per_cell), replace=False).tolist()) if count else []


def _prefix(frame, index):
    """Return only candles through the selected anchor candle."""
    return frame.iloc[:index + 1].reset_index(drop=True)


class _PrefixDigester:
    """Stream candle CSV rows once and snapshot exact feature digests at anchors."""
    def __init__(self, frame):
        self.columns = [c for c in ("t_open_ms", "o", "h", "l", "c", "v", "quote_v", "trades") if c in frame]
        self.state = hashlib.sha256()
        self.state.update(frame[self.columns].iloc[:0].to_csv(index=False, float_format="%.12g",
                                                                lineterminator="\n").encode())
        self.cursor = 0

    def digest(self, prefix):
        """Advance through newly included rows and return the current prefix hash."""
        end = len(prefix)
        if end > self.cursor:
            chunk = prefix.iloc[self.cursor:end][self.columns].to_csv(index=False, header=False,
                          float_format="%.12g", lineterminator="\n")
            self.state.update(chunk.encode())
            self.cursor = end
        return self.state.copy().hexdigest()


def _selected(db, split, per_cell, seed, limit, counts=None):
    """Yield selected prefixes only from cells able to fill the requested sample."""
    for symbol in _symbols(db, split, limit):
        for tf in TIMEFRAMES:
            frame = _frame(db, symbol, tf)
            anchors = _cell_anchors(frame, tf, split)
            if len(anchors) < per_cell:
                if counts is not None:
                    counts["excluded"][tf] += 1
                continue
            if counts is not None:
                counts["eligible"][tf] += 1
            for index in _sample_indices(len(anchors), per_cell, seed, symbol, tf):
                anchor_row = anchors.iloc[index]
                pos = int(np.flatnonzero(frame.t_open_ms.to_numpy() == anchor_row.t_open_ms)[0])
                yield symbol, tf, int(anchor_row.anchor_time_ms), _prefix(frame, pos), frame


def _base_summary(rows, emitted, binary_allowed):
    """Summarize baseline scores and date clusters."""
    n = len(rows)
    hits = sum(bool(row["m1_hit"]) for row in rows)
    active = [row for row in rows if row["side"] != "none"]
    labels = [row["m1_actual"] for row in rows]
    up = labels.count("up")
    down = labels.count("down")
    flat = labels.count("flat")
    shares = {"up": up / n if n else None, "down": down / n if n else None,
              "flat": flat / n if n else None}
    binary_rows = [row for row in rows if row["m1_actual"] in {"up", "down"}]
    binary_hits = sum(row["m1_hit"] for row in binary_rows)
    result = {"n": n, "m1_hits": hits, "m1_accuracy": hits / n if n else None,
              "m1_wilson95": wilson(hits, n), "coverage": n / emitted if emitted else 0.0,
              "trade_coverage": len(active) / n if n else 0.0,
              "long_net_return_mean": _mean([r["net_return"] for r in active if r["side"] == "long"]),
              "short_net_return_mean": _mean([r["net_return"] for r in active if r["side"] == "short"]),
              "liquidation_count": sum(r["exit_reason"] == "LIQUIDATION" for r in active),
              "label_shares": shares, "flat_label_prevalence": shares["flat"],
              "binary_n": len(binary_rows) if binary_allowed else None,
              "binary_accuracy": binary_hits / len(binary_rows) if binary_allowed and binary_rows else None,
              "binary_wilson95": wilson(binary_hits, len(binary_rows)) if binary_allowed else None}
    result["anchor_day_clusters"] = _clusters(rows)
    return result


def _mean(values):
    """Return a JSON-safe arithmetic mean or null."""
    return float(np.mean(values)) if values else None


def _clusters(rows):
    """Report M1 and coverage by anchor day to expose correlated anchors."""
    groups = {}
    for row in rows:
        day = pd.to_datetime(row["anchor_time"], unit="ms", utc=True).date().isoformat()
        groups.setdefault(day, []).append(row)
    return {day: {"n": len(items), "m1_accuracy": sum(bool(x["m1_hit"]) for x in items) / len(items),
                  "coverage": sum(x["side"] != "none" for x in items) / len(items)}
            for day, items in sorted(groups.items())}


def _markdown(report):
    """Render concise per-timeframe baseline metrics and day cluster counts."""
    fingerprint = report["data_fingerprint"]
    lines = ["# Baseline floor", "", f"Data fingerprint: `{fingerprint['sha256']}`",
             f"Database metadata: size `{fingerprint['file_size_bytes']}` bytes, mtime_ns `{fingerprint['file_mtime_ns']}`", "",
             "| TF | Baseline | n | M1 3-class (95% CI) | Binary up/down | Labels up/down/flat | Coverage | Trade coverage | Long net mean | Short net mean | Liquidations |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for tf, baselines in report["timeframes"].items():
        for name, item in baselines.items():
            ci = item["m1_wilson95"]
            accuracy = "n/a" if item["m1_accuracy"] is None else f"{item['m1_accuracy']:.4f} [{ci['low']:.4f}, {ci['high']:.4f}]"
            binary = "n/a" if item["binary_accuracy"] is None else f"{item['binary_accuracy']:.4f}"
            fmt = lambda v: "n/a" if v is None else f"{v:.6f}"
            labels = "/".join(fmt(item["label_shares"][k]) for k in ("up", "down", "flat"))
            lines.append(f"| {tf} | {name} | {item['n']} | {accuracy} | {binary} | {labels} | {item['coverage']:.4f} | {item['trade_coverage']:.4f} | {fmt(item['long_net_return_mean'])} | {fmt(item['short_net_return_mean'])} | {item['liquidation_count']} |")
    lines += ["", "Anchor-day clusters (n / M1 accuracy / coverage):", ""]
    for tf, baselines in report["timeframes"].items():
        for name, item in baselines.items():
            values = ", ".join(f"{day}: {v['n']}/{v['m1_accuracy']:.3f}/{v['coverage']:.3f}" for day, v in item["anchor_day_clusters"].items())
            lines.append(f"- {tf} {name}: {values or 'none'}")
    return "\n".join(lines) + "\n"


def _persist_baselines(pending, predictions_db, trials_db, split, total, fingerprint):
    """Persist completed baseline outputs and register the experiment trial."""
    store, trials = connect_store(predictions_db), connect_trials(trials_db)
    try:
        for pred, score in pending:
            pred_id = append_prediction(store, pred)
            record_score(store, pred_id, score)
        hypothesis = ("baseline floor; pre-LLM label definition change: flat when "
                      "abs(move) <= 0.25 * ATR14 * sqrt(H_candles), H_candles=horizon_minutes/timeframe_minutes")
        record_trial(trials, datetime.now(timezone.utc).isoformat(), "baseline", BASELINE_VERSION, BASELINE_VERSION,
                     split, hypothesis, total, data_fingerprint=fingerprint)
    finally:
        store.close()
        trials.close()


def _run_identity(split, seed, per_cell, symbols, flat_mult, fingerprint):
    """Build deterministic run ID and immutable settings payload."""
    config = {"split": split, "seed": int(seed), "per_cell": int(per_cell), "symbols": symbols,
              "flat_mult": float(flat_mult), "code_version": BASELINE_VERSION,
              "data_fingerprint": fingerprint["sha256"]}
    token = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
    return f"baseline_{split}_{token}", config


def _existing_run(run_dir, config):
    """Reuse only a fully materialized run matching the same configuration."""
    if not run_dir.exists():
        return None
    manifest = run_dir / "run.json"
    report = run_dir / "report.json"
    if not manifest.exists() or not report.exists() or not (run_dir / "pred.sqlite").exists() or not (run_dir / "report.md").exists():
        raise FileExistsError(f"incomplete run directory exists: {run_dir}")
    if json.loads(manifest.read_text()) != config:
        raise FileExistsError(f"run directory configuration mismatch: {run_dir}")
    return {"run_id": run_dir.name, "report": str(report), "markdown": str(run_dir / "report.md"),
            "n_predictions": json.loads(report.read_text())["n_predictions"], "reused": True}


def _score_cells(db, split, per_cell, seed, symbols, flat_mult, counts):
    """Generate and score every requested baseline on full-size eligible cells."""
    grouped = {tf: {f"baseline_{name}": [] for name in BASELINES} for tf in TIMEFRAMES}
    emitted = {tf: {name: 0 for name in grouped[tf]} for tf in TIMEFRAMES}
    pending = []
    active_cell, digester = None, None
    for symbol, tf, anchor, prefix, frame in _selected(db, split, per_cell, seed, symbols, counts):
        cell = (symbol, tf)
        if cell != active_cell:
            active_cell, digester = cell, _PrefixDigester(frame)
        input_hash = digester.digest(prefix)
        for name in BASELINES:
            model = f"baseline_{name}"
            emitted[tf][model] += 1
            stable_seed = int(hashlib.sha256(f"{seed}:{symbol}:{tf}:{anchor}:{name}".encode()).hexdigest()[:8], 16)
            pred = emit_baseline(name, prefix, symbol, tf, anchor, stable_seed, input_hash)
            score = score_prediction(pred, frame, flat_mult=flat_mult)
            pending.append((pred, score))
            if score["status"] == "SCORED":
                grouped[tf][model].append({**score, "side": pred["side"], "anchor_time": anchor})
    return grouped, emitted, pending


def _write_run(run_dir, report, config, pending, trials_db):
    """Materialize one run's prediction store, report and markdown exactly once."""
    run_dir.mkdir(parents=True, exist_ok=False)
    report_path = run_dir / "report.json"
    _persist_baselines(pending, run_dir / "pred.sqlite", trials_db, report["split"], report["n_predictions"],
                       report["data_fingerprint"]["sha256"])
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (run_dir / "report.md").write_text(_markdown(report))
    (run_dir / "run.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    return report_path


def run_baselines(split="dev", per_cell=30, seed=1, symbols=None, data_db=DB_PATH,
                  trials_db=None, flat_mult=FLAT_MULT, force=False):
    """Sample, score and persist deterministic baseline runs in isolated folders."""
    started = time.monotonic()
    if (split not in {"dev", "validation"} or per_cell < 1 or isinstance(flat_mult, bool)
            or not isinstance(flat_mult, (int, float)) or not math.isfinite(flat_mult) or flat_mult <= 0):
        raise ValueError("invalid split, per_cell or flat_mult")
    root = Path(data_db).parent
    db = _readonly(data_db)
    try:
        fingerprint = _data_fingerprint(db, data_db)
    finally:
        db.close()
    run_id, config = _run_identity(split, seed, per_cell, symbols, flat_mult, fingerprint)
    if force:
        run_id = _force_run_id(root / "runs", run_id)
        config["forced"] = True
    run_dir = root / "runs" / run_id
    existing = None if force else _existing_run(run_dir, config)
    if existing:
        return existing
    trials_db = trials_db or root / "trials.sqlite"
    counts = {key: {tf: 0 for tf in TIMEFRAMES} for key in ("eligible", "excluded")}
    db = _readonly(data_db)
    try:
        grouped, emitted, pending = _score_cells(db, split, per_cell, seed, symbols, flat_mult, counts)
    finally:
        db.close()
    return _finish_run(run_dir, config, fingerprint, grouped, emitted, pending, counts, trials_db, started)


def _force_run_id(runs_dir, run_id):
    """Choose a fresh directory for an explicitly forced run."""
    suffix = 1
    candidate = f"{run_id}_force_{suffix:03d}"
    while (runs_dir / candidate).exists():
        suffix += 1
        candidate = f"{run_id}_force_{suffix:03d}"
    return candidate


def _finish_run(run_dir, config, fingerprint, grouped, emitted, pending, counts, trials_db, started):
    """Create deterministic result content and persist one finished run."""
    baselines_per_cell = len(BASELINES)
    n_cells = sum(counts["eligible"].values())
    total = n_cells * config["per_cell"] * baselines_per_cell
    report = {"run_id": run_dir.name, **config, "data_fingerprint": fingerprint, "n_cells": n_cells,
              "cells_by_timeframe": counts["eligible"], "excluded_cells_by_timeframe": counts["excluded"],
              "baseline_count": baselines_per_cell, "n_predictions": total,
              "prediction_count_check": f"{n_cells} x {config['per_cell']} x {baselines_per_cell} = {total}",
              "fee_per_side": 0.0005, "slippage_per_side": 0.0002, "entry_delay_candles": 1,
              "flat_mult": config["flat_mult"],
              "flat_band_formula": "flat_mult * ATR14 * sqrt(H_candles)",
              "coverage_definition": "scored predictions divided by emitted predictions",
              "timeframes": {tf: {name: _base_summary(rows, emitted[tf][name],
                               name in {"baseline_momentum", "baseline_always_up", "baseline_always_down"})
                               for name, rows in groups.items()} for tf, groups in grouped.items()}}
    report_path = _write_run(run_dir, report, config, pending, trials_db)
    return {"run_id": run_dir.name, "report": str(report_path), "markdown": str(run_dir / "report.md"),
            "n_predictions": total, "runtime_seconds": time.monotonic() - started, "reused": False}


def _task_prompt(run_dir):
    """Write the model-facing output contract without naming the split."""
    text = ("# Prediction task\n\nFor each item in a task JSON file, write ONE JSON array of Prediction objects "
            "to `out_<model>_task_XXXX.json` in this directory. Use the exact fields defined by `chart_predictor/schema.py`. "
            "Each prediction must copy `symbol`, `timeframe`, `anchor_time`, and `input_sha256` from its task item, and include "
            "`created_at`, `model`, and `prompt_version`. If there is no clear edge, use `side=none` and confidence near 0.5. "
            "Do not add fields or infer outcomes beyond the supplied features.\n")
    (run_dir / "PROMPT.md").write_text(text)


def make_agent_tasks(split="dev", per_cell=30, seed=1, batch_size=20, symbols=None,
                     data_db=DB_PATH, tasks_root=None):
    """Write shuffled-size feature-only batches for an external agent."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    root = Path(tasks_root or Path(data_db).parent / "agent_tasks")
    run_dir = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True, exist_ok=False)
    db, items = _readonly(data_db), []
    try:
        for symbol, tf, anchor, prefix, _ in _selected(db, split, per_cell, seed, symbols):
            features = build_features(prefix, tf)
            items.append({"symbol": symbol, "timeframe": tf, "anchor_time": anchor,
                          "input_sha256": features["input_sha256"], "features": features})
    finally:
        db.close()
    for start in range(0, len(items), batch_size):
        index = start // batch_size + 1
        (run_dir / f"task_{index:04d}.json").write_text(json.dumps(items[start:start + batch_size], allow_nan=False))
    _task_prompt(run_dir)
    return {"run_dir": str(run_dir), "tasks": len(items), "files": (len(items) + batch_size - 1) // batch_size}


def _task_index(run_dir):
    """Read feature tasks into an anchor-to-prefix lookup for ingestion."""
    lookup = {}
    for path in sorted(Path(run_dir).glob("task_*.json")):
        for item in json.loads(path.read_text()):
            lookup[(item["symbol"], item["timeframe"], int(item["anchor_time"]))] = item
    return lookup


def _validate_output_file(path, model, task_index, db, store):
    """Ingest predictions from one agent response file or return its failure reason."""
    try:
        payload = json.loads(path.read_text())
        if not isinstance(payload, list):
            raise ValueError("file must contain a JSON array")
        accepted = 0
        for item in payload:
            if item.get("model") != model:
                raise ValueError("model does not match requested model")
            key = (item.get("symbol"), item.get("timeframe"), int(item.get("anchor_time", -1)))
            task = task_index.get(key)
            if task is None or item.get("input_sha256") != task["input_sha256"]:
                raise ValueError("prediction does not match a task item")
            frame = _frame(db, item["symbol"], item["timeframe"])
            validate_prediction(item, frame)
            append_prediction(store, item)
            accepted += 1
        return {"file": path.name, "ingested": accepted, "rejected": False}
    except Exception as exc:
        return {"file": path.name, "ingested": 0, "rejected": True, "reason": f"{type(exc).__name__}: {exc}"}


def ingest_dir(run_dir, model, data_db=DB_PATH, predictions_db=None):
    """Ingest every model response independently and preserve per-file errors."""
    if model not in {"claude", "codex"}:
        raise ValueError("model must be claude or codex")
    root = Path(data_db).parent
    db = _readonly(data_db)
    store = connect_store(predictions_db or root / "pred_llm.sqlite")
    index = _task_index(run_dir)
    paths = sorted(Path(run_dir).glob(f"out_{model}_task_*.json"))
    try:
        results = [_validate_output_file(path, model, index, db, store) for path in paths]
    finally:
        db.close()
        store.close()
    return {"files": results, "ingested": sum(x["ingested"] for x in results),
            "rejected_files": sum(x["rejected"] for x in results)}
