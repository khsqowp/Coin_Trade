"""CLI for collection, causal replay, immutable ingest and deterministic scoring."""
import argparse
import json
import sqlite3
from pathlib import Path
import pandas as pd
from .collector import collect_symbols, connect, verify_symbol
from .features import build_features
from .resample import load_resampled
from .store import append_prediction, connect_store, connect_trials, record_trial
from .schema import validate_prediction
from .scorer import score_prediction
from .stats import report as make_report
from .replay import replay
from .universe import fetch_universe


def _args():
    """Parse all P1/P2 command options."""
    parser = argparse.ArgumentParser(prog="python -m chart_predictor.cli")
    parser.add_argument("command", choices=("universe", "collect", "update", "features", "replay", "ingest", "score", "report", "verify", "baselines", "make-agent-tasks", "ingest-dir", "probe", "probe-p4c"))
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--symbols", type=int)
    parser.add_argument("--tf", default="1m", choices=("1m", "5m", "30m", "60m"))
    parser.add_argument("--anchor")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--split", choices=("dev", "validation"), default="dev")
    parser.add_argument("--file")
    parser.add_argument("--input")
    parser.add_argument("--db")
    parser.add_argument("--trials-db")
    parser.add_argument("--data-db")
    parser.add_argument("--verify-symbol", action="append")
    parser.add_argument("--max-gap-minutes", type=int, default=5)
    parser.add_argument("--start-ms", type=int)
    parser.add_argument("--end-ms", type=int)
    parser.add_argument("--per-cell", type=int, default=30)
    parser.add_argument("--force", action="store_true", help="create a fresh baseline run directory")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--dir")
    parser.add_argument("--tasks-dir")
    parser.add_argument("--model", choices=("claude", "codex"))
    return parser.parse_args()


def _load_candles(symbol, tf, data_db):
    """Load raw 1m candles or completed resampled timeframe candles."""
    db = sqlite3.connect(data_db) if data_db else connect()
    try:
        if tf == "1m":
            return pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles WHERE symbol=? ORDER BY t_open_ms",
                                     db, params=(symbol,))
        return load_resampled(db, symbol, tf)
    finally:
        db.close()


def _ingest(args):
    """Validate external prediction JSON against its exact causal candle prefix."""
    source = Path(args.file)
    items = json.loads(source.read_text())
    items = items if isinstance(items, list) else [items]
    store = connect_store(args.db)
    trial = connect_trials(args.trials_db)
    ids = []
    try:
        for item in items:
            candles = _load_candles(item["symbol"], item["timeframe"], args.data_db)
            validate_prediction(item, candles)
            ids.append(append_prediction(store, item))
            record_trial(trial, item["created_at"], item["model"], item["prompt_version"],
                         item["code_sha"], args.split, "prediction ingest", 1)
    finally:
        store.close()
        trial.close()
    print(json.dumps({"ingested": len(ids), "ids": ids}))


def _score(args):
    """Score every not-yet-scored prediction using completed local candles."""
    store = connect_store(args.db)
    done = {row[0] for row in store.execute("SELECT prediction_id,payload FROM scores")
            if json.loads(row[1]).get("status") == "SCORED"}
    rows = store.execute("SELECT id,payload FROM predictions").fetchall()
    results = []
    for pred_id, payload in rows:
        if pred_id in done:
            continue
        pred = json.loads(payload)
        candles = _load_candles(pred["symbol"], pred["timeframe"], args.data_db)
        result = score_prediction(pred, candles)
        result.update({"prediction_id": pred_id, "symbol": pred["symbol"], "timeframe": pred["timeframe"],
                       "model": pred["model"], "confidence": pred["confidence"], "anchor_time": pred["anchor_time"]})
        store.execute("INSERT INTO scores VALUES(?,?)", (pred_id, json.dumps(result, allow_nan=False)))
        results.append(result)
    store.commit()
    store.close()
    print(json.dumps({"scored": len(results), "unscorable": sum(x["status"] == "UNSCORABLE" for x in results)}))


def _report(args):
    """Print the deterministic report from stored score rows."""
    store = connect_store(args.db)
    latest = {}
    for row in store.execute("SELECT prediction_id,payload FROM scores ORDER BY rowid"):
        latest[row[0]] = json.loads(row[1])
    scores = list(latest.values())
    store.close()
    print(json.dumps(make_report(scores), indent=2, allow_nan=False))


def _features(args):
    """Preserve P1 feature command for one symbol and optional anchor."""
    frame = _load_candles(args.symbol, args.tf, args.data_db)
    if args.anchor:
        anchor = pd.Timestamp(args.anchor)
        anchor = anchor.tz_localize("UTC") if anchor.tzinfo is None else anchor.tz_convert("UTC")
        width = {"1m": 60_000, "5m": 300_000, "30m": 1_800_000, "60m": 3_600_000}[args.tf]
        frame = frame[frame.t_open_ms + width - 1 <= int(anchor.timestamp() * 1000)]
    print(json.dumps(build_features(frame, args.tf), indent=2))


def _verify(args):
    """Print per-symbol requested-window coverage and fail beyond gap tolerance."""
    end_ms = args.end_ms if args.end_ms is not None else int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    start_ms = args.start_ms if args.start_ms is not None else end_ms - int(args.days * 86_400_000)
    db = sqlite3.connect(args.data_db) if args.data_db else connect()
    symbols = args.verify_symbol or [args.symbol]
    reports = [verify_symbol(db, symbol, start_ms, end_ms) for symbol in symbols]
    db.close()
    failed = any(row["missing_minutes"] > args.max_gap_minutes or row["duplicates"] for row in reports)
    print(json.dumps({"symbols": reports, "ok": not failed}, indent=2))
    if failed:
        raise SystemExit(1)


def main():
    """Dispatch P1 and P2 commands without model or network calls."""
    args = _args()
    if args.command == "universe":
        print(json.dumps(fetch_universe(args.top), indent=2))
    elif args.command in {"collect", "update"}:
        days = args.days if args.command == "collect" else min(args.days, 1)
        print(json.dumps(collect_symbols([args.symbol], days=days), indent=2))
    elif args.command == "features":
        _features(args)
    elif args.command == "replay":
        db = sqlite3.connect(args.data_db) if args.data_db else connect()
        syms = [row[0] for row in db.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol LIMIT ?", (args.symbols or 10,))]
        db.close()
        print(json.dumps(replay(args.split, syms, args.tf, args.data_db or __import__("chart_predictor.collector", fromlist=["DB_PATH"]).DB_PATH)))
    elif args.command == "ingest":
        _ingest(args)
    elif args.command == "score":
        _score(args)
    elif args.command == "report":
        _report(args)
    elif args.command == "verify":
        _verify(args)
    elif args.command == "baselines":
        from .p3a import run_baselines
        result = run_baselines(args.split, args.per_cell, args.seed, args.symbols,
                               args.data_db or __import__("chart_predictor.collector", fromlist=["DB_PATH"]).DB_PATH,
                               args.trials_db, force=args.force)
        print(json.dumps(result, allow_nan=False))
    elif args.command == "make-agent-tasks":
        from .p3a import make_agent_tasks
        result = make_agent_tasks(args.split, args.per_cell, args.seed, args.batch_size, args.symbols,
                                  args.data_db or __import__("chart_predictor.collector", fromlist=["DB_PATH"]).DB_PATH,
                                  args.tasks_dir)
        print(json.dumps(result, allow_nan=False))
    elif args.command == "ingest-dir":
        from .p3a import ingest_dir
        if not args.dir:
            raise SystemExit("ingest-dir requires --dir")
        result = ingest_dir(args.dir, args.model, args.data_db or __import__("chart_predictor.collector", fromlist=["DB_PATH"]).DB_PATH, args.db)
        print(json.dumps(result, allow_nan=False))
    elif args.command == "probe":
        from .probe import run_probe
        result = run_probe(args.data_db or __import__("chart_predictor.collector", fromlist=["DB_PATH"]).DB_PATH,
                           trials_db=args.trials_db, seed=args.seed)
        print(json.dumps(result, allow_nan=False))
    elif args.command == "probe-p4c":
        from .p4c import run_p4c
        result = run_p4c(args.data_db or __import__("chart_predictor.collector", fromlist=["DB_PATH"]).DB_PATH,
                         trials_db=args.trials_db, seed=args.seed)
        print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
