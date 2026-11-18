"""One-step absolute-return forecast diagnostic; read-only and non-trading."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sqlite3
import time
from array import array
from pathlib import Path
from typing import Callable

import numpy as np

EXPECTED_SHA256 = "bb64efa272bab6c5bed258ec7284f9212165c8912cfcd824f51863ae5d88fafa"
MINUTE_MS = 60_000
TRAIN_START = 1_609_459_200_000  # 2021-01-01T00:00:00Z
TRAIN_END = 1_767_225_600_000    # 2026-01-01T00:00:00Z
EVAL_START = TRAIN_END
EVAL_END = 1_775_001_600_000     # 2026-04-01T00:00:00Z
MIN_TRAIN = 10_000
MIN_EVAL = 10_000
BOOTSTRAP_REPS = 5_000
BLOCK_DAYS = 7
SEED = 20261119
CHUNK_ROWS = 100_000


class RunInterrupted(Exception):
    """Raised after an interrupt has been recorded for safe resumption."""


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _checkpoint_path(directory: Path, symbol: str) -> Path:
    key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()
    return directory / f"{key}.json"


def sha256_file(
    path: Path,
    progress: Callable[[int], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> str:
    digest = hashlib.sha256()
    bytes_read = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024 * 1024), b""):
            digest.update(chunk)
            bytes_read += len(chunk)
            if progress is not None:
                progress(bytes_read)
            if stop_requested is not None and stop_requested():
                raise RunInterrupted(f"interrupted while hashing after {bytes_read} bytes")
    return digest.hexdigest()


def _valid_rows(rows: list[tuple]) -> tuple[np.ndarray, ...]:
    ms = np.fromiter((r[0] for r in rows), dtype=np.int64, count=len(rows))
    op = np.fromiter((r[1] for r in rows), dtype=np.float64, count=len(rows))
    hi = np.fromiter((r[2] for r in rows), dtype=np.float64, count=len(rows))
    lo = np.fromiter((r[3] for r in rows), dtype=np.float64, count=len(rows))
    cl = np.fromiter((r[4] for r in rows), dtype=np.float64, count=len(rows))
    vol = np.fromiter((r[5] for r in rows), dtype=np.float64, count=len(rows))
    valid = (
        np.isfinite(op) & np.isfinite(hi) & np.isfinite(lo) & np.isfinite(cl)
        & np.isfinite(vol) & (op > 0) & (hi > 0) & (lo > 0) & (cl > 0)
        & (vol >= 0) & (hi >= np.maximum(op, cl)) & (lo <= np.minimum(op, cl))
        & (hi >= lo) & (ms % MINUTE_MS == 0)
    )
    return ms, op, hi, lo, cl, vol, valid


def _append_returns(out: array, ms: np.ndarray, close: np.ndarray, valid: np.ndarray,
                    start: int, end: int, lower: int, upper: int) -> None:
    if end <= start:
        return
    idx = np.arange(start, end)
    good = (
        (ms[idx] + MINUTE_MS >= lower) & (ms[idx] + MINUTE_MS < upper)
        & (ms[idx - 1] + MINUTE_MS >= lower)
        & (ms[idx - 1] + MINUTE_MS < upper)
        & (ms[idx] - ms[idx - 1] == MINUTE_MS)
        & valid[idx] & valid[idx - 1]
    )
    if np.any(good):
        values = np.abs(np.log(close[idx[good]] / close[idx[good] - 1]))
        out.extend(array("d", values))


def _analyze_symbol(
    conn: sqlite3.Connection,
    symbol: str,
    *,
    score: bool = True,
    progress: Callable[[int], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> dict:
    train_values = array("d")
    n_eval = invalid_rows = offgrid_rows = adjacency_gaps = scanned_rows = 0
    # [candidate abs error, baseline abs error, candidate squared error,
    #  baseline squared error, count] for each of the 90 target UTC dates.
    n_days = (EVAL_END - EVAL_START + 86_400_000 - 1) // 86_400_000
    daily = np.zeros((n_days, 5), dtype=np.float64)
    carry: list[tuple] = []
    cur = conn.execute(
        "SELECT open_ms,open,high,low,close,volume FROM candles "
        "WHERE symbol=? AND open_ms>=? AND open_ms<? ORDER BY open_ms",
        (symbol, TRAIN_START - MINUTE_MS, EVAL_END - MINUTE_MS),
    )
    while True:
        if stop_requested is not None and stop_requested():
            raise RunInterrupted(f"interrupted while scanning {symbol}")
        batch = cur.fetchmany(CHUNK_ROWS)
        if not batch:
            break
        rows = carry + batch
        carry_count = len(carry)
        ms, op, hi, lo, cl, vol, valid = _valid_rows(rows)
        new_start = carry_count
        scanned_rows += len(batch)
        if progress is not None:
            progress(scanned_rows)
        invalid_rows += int(np.count_nonzero(~valid[new_start:]))
        offgrid_rows += int(np.count_nonzero(ms[new_start:] % MINUTE_MS != 0))
        if len(ms) > 1:
            pair_i = np.arange(max(1, new_start), len(ms))
            in_scope = (ms[pair_i] >= TRAIN_START) & (ms[pair_i] < EVAL_END)
            adjacency_gaps += int(np.count_nonzero(
                in_scope & (ms[pair_i] - ms[pair_i - 1] != MINUTE_MS)
            ))
        _append_returns(train_values, ms, cl, valid, max(1, new_start), len(ms),
                        TRAIN_START, TRAIN_END)

        # Anchor i uses i-1 as its sole feature; outcome is the next completed
        # candle i+1. Split membership is defined by candle close timestamps.
        first_anchor = max(1, new_start - 1) if carry_count else 1
        last_anchor = len(ms) - 1
        if last_anchor > first_anchor:
            idx = np.arange(first_anchor, last_anchor)
            previous_close_ms = ms[idx - 1] + MINUTE_MS
            anchor_close_ms = ms[idx] + MINUTE_MS
            target_close_ms = ms[idx + 1] + MINUTE_MS
            good = (
                (previous_close_ms >= EVAL_START) & (previous_close_ms < EVAL_END)
                & (anchor_close_ms >= EVAL_START) & (anchor_close_ms < EVAL_END)
                & (target_close_ms >= EVAL_START) & (target_close_ms < EVAL_END)
                & (ms[idx] - ms[idx - 1] == MINUTE_MS)
                & (ms[idx + 1] - ms[idx] == MINUTE_MS)
                & valid[idx - 1] & valid[idx] & valid[idx + 1]
            )
            if np.any(good):
                selected = idx[good]
                n_eval += len(selected)
                train_count = len(train_values)
                if score and train_count >= MIN_TRAIN:
                    candidate = np.abs(np.log(cl[selected] / cl[selected - 1]))
                    target = np.abs(np.log(cl[selected + 1] / cl[selected]))
                    target_dates = ((target_close_ms[good] - EVAL_START) // 86_400_000).astype(int)
                    np.clip(target_dates, 0, n_days - 1, out=target_dates)
                    median = float(np.median(np.frombuffer(train_values, dtype=np.float64)))
                    candidate_err = np.abs(candidate - target)
                    baseline_err = np.abs(median - target)
                    np.add.at(daily[:, 0], target_dates, candidate_err)
                    np.add.at(daily[:, 1], target_dates, baseline_err)
                    np.add.at(daily[:, 2], target_dates, np.square(candidate - target))
                    np.add.at(daily[:, 3], target_dates, np.square(median - target))
                    np.add.at(daily[:, 4], target_dates, 1)
        carry = rows[-2:]

    train_count = len(train_values)
    if train_count < MIN_TRAIN:
        return {"symbol": symbol, "eligible": False, "reason": "insufficient_train_returns",
                "train_returns": train_count, "eval_forecasts": n_eval,
                "rows_scanned": scanned_rows, "invalid_rows": invalid_rows,
                "offgrid_rows": offgrid_rows, "adjacency_gaps": adjacency_gaps}
    # If chunks were processed before enough train values accumulated (only
    # relevant to synthetic/tiny inputs), do not silently produce a partial score.
    if n_eval < MIN_EVAL:
        return {"symbol": symbol, "eligible": False, "reason": "insufficient_eval_forecasts",
                "train_returns": train_count, "eval_forecasts": n_eval,
                "rows_scanned": scanned_rows, "invalid_rows": invalid_rows,
                "offgrid_rows": offgrid_rows, "adjacency_gaps": adjacency_gaps}
    if not score:
        return {"symbol": symbol, "eligible": True, "train_returns": train_count,
                "eval_forecasts": n_eval, "rows_scanned": scanned_rows,
                "invalid_rows": invalid_rows, "offgrid_rows": offgrid_rows,
                "adjacency_gaps": adjacency_gaps}
    candidate_mae = float(daily[:, 0].sum() / daily[:, 4].sum())
    baseline_mae = float(daily[:, 1].sum() / daily[:, 4].sum())
    candidate_mse = float(daily[:, 2].sum() / daily[:, 4].sum())
    baseline_mse = float(daily[:, 3].sum() / daily[:, 4].sum())
    return {
        "symbol": symbol, "eligible": True, "train_returns": train_count,
        "eval_forecasts": n_eval, "train_median_abs_log_return": float(np.median(np.frombuffer(train_values, dtype=np.float64))),
        "candidate_mae": candidate_mae, "baseline_mae": baseline_mae,
        "relative_mae_improvement": 1.0 - candidate_mae / baseline_mae,
        "candidate_mse": candidate_mse, "baseline_mse": baseline_mse,
        "relative_mse_improvement": 1.0 - candidate_mse / baseline_mse,
        "rows_scanned": scanned_rows, "invalid_rows": invalid_rows,
        "offgrid_rows": offgrid_rows, "adjacency_gaps": adjacency_gaps,
        "daily_loss_sums": daily.tolist(),
    }


def _bootstrap(symbols: list[dict]) -> dict:
    n_days = (EVAL_END - EVAL_START + 86_400_000 - 1) // 86_400_000
    rng = np.random.default_rng(SEED)
    block_count = (n_days + BLOCK_DAYS - 1) // BLOCK_DAYS
    samples = np.empty(BOOTSTRAP_REPS, dtype=np.float64)
    mse_samples = np.empty(BOOTSTRAP_REPS, dtype=np.float64)
    for rep in range(BOOTSTRAP_REPS):
        starts = rng.integers(0, n_days, size=block_count)
        dates = np.concatenate([(s + np.arange(BLOCK_DAYS)) % n_days for s in starts])[:n_days]
        sym_mae, sym_mse = [], []
        for result in symbols:
            daily = np.asarray(result["daily_loss_sums"], dtype=np.float64)[dates]
            count = daily[:, 4].sum()
            if count <= 0:
                continue
            cand_mae, base_mae = daily[:, 0].sum() / count, daily[:, 1].sum() / count
            cand_mse, base_mse = daily[:, 2].sum() / count, daily[:, 3].sum() / count
            if base_mae > 0 and base_mse > 0:
                sym_mae.append(1.0 - cand_mae / base_mae)
                sym_mse.append(1.0 - cand_mse / base_mse)
        samples[rep] = float(np.mean(sym_mae))
        mse_samples[rep] = float(np.mean(sym_mse))
    return {
        "block_days": BLOCK_DAYS, "replicates": BOOTSTRAP_REPS, "seed": SEED,
        "relative_mae_improvement_95pct": np.quantile(samples, [0.025, 0.975]).tolist(),
        "relative_mse_improvement_95pct": np.quantile(mse_samples, [0.025, 0.975]).tolist(),
    }


def run(
    db_path: Path,
    output: Path,
    expected_sha256: str = EXPECTED_SHA256,
    stop_requested: Callable[[], bool] | None = None,
) -> dict:
    state_dir = output.with_name(output.name + ".state")
    preflight_dir = state_dir / "preflight_symbols"
    score_dir = state_dir / "score_symbols"
    preflight_path = state_dir / "preflight.json"
    status_path = state_dir / "status.json"
    if output.exists() and not state_dir.exists():
        raise FileExistsError(f"output already exists; choose a new output path: {output}")
    state_dir.mkdir(parents=True, exist_ok=True)
    size_bytes = db_path.stat().st_size
    print(f"verifying database SHA-256 ({size_bytes:,} bytes)", flush=True)

    last_hash_log = 0

    def hash_progress(bytes_read: int) -> None:
        nonlocal last_hash_log
        if bytes_read - last_hash_log >= 512 * 1024 * 1024:
            print(f"hash progress bytes={bytes_read}/{size_bytes}", flush=True)
            last_hash_log = bytes_read

    try:
        actual_sha = sha256_file(db_path, progress=hash_progress,
                                 stop_requested=stop_requested)
    except RunInterrupted:
        _atomic_json(status_path, {"state": "interrupted", "stage": "hash",
                                   "updated_unix": time.time()})
        raise
    if actual_sha != expected_sha256:
        raise ValueError(f"database hash mismatch: {actual_sha}")
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    config = {
        "train_start": TRAIN_START, "train_end": TRAIN_END,
        "eval_start": EVAL_START, "eval_end": EVAL_END,
        "min_train": MIN_TRAIN, "min_eval": MIN_EVAL,
        "chunk_rows": CHUNK_ROWS, "minute_ms": MINUTE_MS,
        "bootstrap_reps": BOOTSTRAP_REPS, "block_days": BLOCK_DAYS,
        "seed": SEED,
    }
    identity = {"database_sha256": actual_sha, "script_sha256": script_sha,
                "config": config}
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    if output.exists() and not preflight_path.exists():
        raise FileExistsError(f"output already exists without matching run state: {output}")
    if output.exists() and status_path.exists():
        saved_status = json.loads(status_path.read_text())
        if saved_status.get("state") == "complete" and saved_status.get("fingerprint") == fingerprint:
            raise FileExistsError(f"run is already complete; choose a new output path: {output}")
    print(f"hash verified: {actual_sha}; run={fingerprint[:12]}", flush=True)

    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        symbols = [row[0] for row in conn.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")]
        if preflight_path.exists():
            preflight = json.loads(preflight_path.read_text())
            if preflight.get("fingerprint") != fingerprint:
                raise ValueError("preflight fingerprint mismatch; use a new output path")
            preflight_results = preflight["symbols"]
        else:
            preflight_results = []
            completed = 0
            for symbol in symbols:
                if stop_requested is not None and stop_requested():
                    _atomic_json(status_path, {"state": "interrupted", "stage": "preflight",
                                               "completed_symbols": completed,
                                               "total_symbols": len(symbols),
                                               "fingerprint": fingerprint})
                    raise RunInterrupted("interrupted between preflight symbols")
                checkpoint = _checkpoint_path(preflight_dir, symbol)
                if checkpoint.exists():
                    saved = json.loads(checkpoint.read_text())
                    if saved.get("fingerprint") != fingerprint:
                        raise ValueError(f"preflight checkpoint fingerprint mismatch: {symbol}")
                    result = saved["result"]
                else:
                    def preflight_progress(rows: int, *, current=symbol) -> None:
                        _atomic_json(status_path, {
                            "state": "running", "stage": "preflight", "symbol": current,
                            "rows_scanned": rows, "completed_symbols": completed,
                            "total_symbols": len(symbols), "updated_unix": time.time(),
                            "fingerprint": fingerprint,
                        })

                    result = _analyze_symbol(
                        conn, symbol, score=False, progress=preflight_progress,
                        stop_requested=stop_requested,
                    )
                    _atomic_json(checkpoint, {"fingerprint": fingerprint, "result": result})
                preflight_results.append(result)
                completed += 1
                _atomic_json(status_path, {"state": "running", "stage": "preflight",
                                           "completed_symbols": completed,
                                           "total_symbols": len(symbols),
                                           "updated_unix": time.time(),
                                           "fingerprint": fingerprint})
                print(f"preflight symbols={completed}/{len(symbols)} latest={symbol}", flush=True)

            eligible_preflight = [item for item in preflight_results if item["eligible"]]
            quality = {key: sum(item[key] for item in preflight_results) for key in (
                "rows_scanned", "invalid_rows", "offgrid_rows", "adjacency_gaps")}
            preflight = {
                "fingerprint": fingerprint, "input_sha256": actual_sha,
                "script_sha256": script_sha, "config": config,
                "symbols": preflight_results,
                "eligible_symbols": len(eligible_preflight),
                "data_quality": quality, "outcome_scoring_started": False,
            }
            _atomic_json(preflight_path, preflight)

        eligible_symbols = [item["symbol"] for item in preflight_results if item["eligible"]]
        if len(eligible_symbols) < 20:
            _atomic_json(status_path, {"state": "preflight_failed", "stage": "eligibility",
                                       "eligible_symbols": len(eligible_symbols),
                                       "fingerprint": fingerprint})
            raise ValueError(f"eligibility gate failed: {len(eligible_symbols)} symbols")

        score_by_symbol = {}
        completed_scores = 0
        for symbol in eligible_symbols:
            if stop_requested is not None and stop_requested():
                _atomic_json(status_path, {"state": "interrupted", "stage": "scoring",
                                           "completed_symbols": completed_scores,
                                           "total_symbols": len(eligible_symbols),
                                           "fingerprint": fingerprint})
                raise RunInterrupted("interrupted between scoring symbols")
            checkpoint = _checkpoint_path(score_dir, symbol)
            if checkpoint.exists():
                saved = json.loads(checkpoint.read_text())
                if saved.get("fingerprint") != fingerprint:
                    raise ValueError(f"score checkpoint fingerprint mismatch: {symbol}")
                result = saved["result"]
            else:
                def score_progress(rows: int, *, current=symbol) -> None:
                    _atomic_json(status_path, {
                        "state": "running", "stage": "scoring", "symbol": current,
                        "rows_scanned": rows, "completed_symbols": completed_scores,
                        "total_symbols": len(eligible_symbols), "updated_unix": time.time(),
                        "fingerprint": fingerprint,
                    })

                result = _analyze_symbol(
                    conn, symbol, score=True, progress=score_progress,
                    stop_requested=stop_requested,
                )
                expected = next(item for item in preflight_results if item["symbol"] == symbol)
                for key in ("train_returns", "eval_forecasts", "rows_scanned",
                            "invalid_rows", "offgrid_rows", "adjacency_gaps"):
                    if result[key] != expected[key]:
                        raise ValueError(f"preflight/score mismatch for {symbol}: {key}")
                _atomic_json(checkpoint, {"fingerprint": fingerprint, "result": result})
            score_by_symbol[symbol] = result
            completed_scores += 1
            _atomic_json(status_path, {"state": "running", "stage": "scoring",
                                       "completed_symbols": completed_scores,
                                       "total_symbols": len(eligible_symbols),
                                       "updated_unix": time.time(),
                                       "fingerprint": fingerprint})
            print(f"scoring symbols={completed_scores}/{len(eligible_symbols)} latest={symbol}", flush=True)
    except RunInterrupted:
        if not status_path.exists() or json.loads(status_path.read_text()).get("state") != "interrupted":
            _atomic_json(status_path, {"state": "interrupted", "updated_unix": time.time(),
                                       "fingerprint": fingerprint})
        raise
    finally:
        conn.close()

    results = [score_by_symbol[item["symbol"]] if item["eligible"] else item
               for item in preflight_results]
    eligible = [score_by_symbol[symbol] for symbol in eligible_symbols]
    primary = float(np.mean([r["relative_mae_improvement"] for r in eligible]))
    positive_symbols = sum(r["relative_mae_improvement"] > 0 for r in eligible)
    report = {
        "study": "micro-magnitude-phase1",
        "status": "development_diagnostic_exposed_history_not_trading_or_M2",
        "database": {"path": str(db_path), "size_bytes": db_path.stat().st_size,
                     "sha256": actual_sha, "symbols": len(symbols)},
        "periods_utc": {"train_return_endpoints": ["2021-01-01T00:00:00Z", "2026-01-01T00:00:00Z"],
                        "evaluation_target_candle_closes": ["2026-01-01T00:00:00Z", "2026-04-01T00:00:00Z"]},
        "eligible_symbols": len(eligible), "positive_mae_symbols": positive_symbols,
        "primary_equal_symbol_relative_mae_improvement": primary,
        "equal_symbol_relative_mse_improvement": float(np.mean([r["relative_mse_improvement"] for r in eligible])),
        "pooled_relative_mae_improvement": 1.0 - sum(r["candidate_mae"] * r["eval_forecasts"] for r in eligible) / sum(r["baseline_mae"] * r["eval_forecasts"] for r in eligible),
        "bootstrap": _bootstrap(eligible),
        "data_quality": {"rows_scanned": sum(r["rows_scanned"] for r in results),
                         "invalid_rows": sum(r["invalid_rows"] for r in results),
                         "offgrid_rows": sum(r["offgrid_rows"] for r in results),
                         "adjacency_gaps": sum(r["adjacency_gaps"] for r in results)},
        "symbols": results,
        "advancement_gate": {
            "at_least_20_eligible_symbols": len(eligible) >= 20,
            "primary_ci_entirely_above_zero": False,
            "more_than_half_symbols_improve": positive_symbols > len(eligible) / 2,
            "m2_or_trading_claim": False,
        },
    }
    ci = report["bootstrap"]["relative_mae_improvement_95pct"]
    report["advancement_gate"]["primary_ci_entirely_above_zero"] = ci[0] > 0
    report["decision"] = "CONTINUE_MAGNITUDE_DIAGNOSTIC_ONLY" if all(
        report["advancement_gate"][k] for k in (
            "at_least_20_eligible_symbols", "primary_ci_entirely_above_zero",
            "more_than_half_symbols_improve")) else "STOP_MAGNITUDE_BRANCH"
    # Daily arrays are retained only in the intermediate calculation.
    for row in report["symbols"]:
        row.pop("daily_loss_sums", None)
    _atomic_json(output, report)
    _atomic_json(status_path, {"state": "complete", "stage": "complete",
                               "symbols": len(symbols), "scored_symbols": len(eligible),
                               "updated_unix": time.time(), "fingerprint": fingerprint})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stop = {"requested": False}

    def request_stop(signum, _frame) -> None:
        stop["requested"] = True
        print(f"received signal={signum}; saving resumable state", flush=True)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    try:
        report = run(args.db, args.output, stop_requested=lambda: stop["requested"])
    except RunInterrupted as exc:
        print(str(exc), flush=True)
        raise SystemExit(130)
    print(json.dumps({k: report[k] for k in (
        "status", "eligible_symbols", "positive_mae_symbols",
        "primary_equal_symbol_relative_mae_improvement", "bootstrap", "decision")}, indent=2))


if __name__ == "__main__":
    main()
