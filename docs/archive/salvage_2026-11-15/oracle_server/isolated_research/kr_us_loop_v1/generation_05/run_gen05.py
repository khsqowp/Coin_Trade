"""Generation 05 fixed low-MAX21 long-only exploratory screen."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PREREG = HERE / "PREREG.md"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g1 = load("gen01", ROOT / "generation_01" / "run_gen01.py")
g3 = load("gen03", ROOT / "generation_03" / "run_gen03.py")
g4 = load("gen04", ROOT / "generation_04" / "run_gen04.py")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def log_event(path: Path, event: dict) -> None:
    row = {"ts_utc": pd.Timestamp.now(tz="UTC").isoformat(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def max21(close: pd.DataFrame) -> pd.DataFrame:
    """Max of trailing 21 close-to-close simple returns, requiring 18 finite values."""
    returns = close.astype(float).pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return returns.rolling(21, min_periods=18).max()


def select_low_max(score_row: pd.Series | pd.DataFrame, eligible_row: pd.Series | pd.DataFrame, k: int) -> list[str]:
    """Return stable ticker-sorted ties among the k lowest eligible finite scores."""
    if isinstance(score_row, pd.DataFrame):
        score_row = score_row.iloc[0]
    if isinstance(eligible_row, pd.DataFrame):
        eligible_row = eligible_row.iloc[0]
    valid = eligible_row.fillna(False).astype(bool) & np.isfinite(score_row.astype(float))
    names = sorted(score_row.index[valid].tolist(), key=lambda s: (float(score_row[s]), str(s)))
    return names[:k]


def targets(score: pd.DataFrame, eligible: pd.DataFrame, month_days: np.ndarray, k: int) -> np.ndarray:
    if not score.index.equals(eligible.index) or not score.columns.equals(eligible.columns):
        raise ValueError("score and eligibility axes differ")
    out = np.zeros(score.shape, dtype=np.float32)
    for i in month_days:
        names = select_low_max(score.iloc[i], eligible.iloc[i], k)
        if names:
            out[i, score.columns.get_indexer(names)] = 1.0 / len(names)
    # Sparse close-t target instructions: only a month-end row is a new order.
    # Between month-ends, the portfolio simulator lets weights drift naturally.
    non_rebalance = np.ones(len(score), dtype=bool)
    non_rebalance[month_days] = False
    out[non_rebalance] = np.nan
    return out


def simulate_monthly_strict(data: dict, desired_at_close: np.ndarray) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Execute sparse month-end target orders; allow weights to drift between trades."""
    O, H, L, C = (data[k].to_numpy(float) for k in ("O", "H", "L", "C"))
    T, N = C.shape
    desired = np.vstack([np.full((1, N), np.nan), desired_at_close[:-1]])
    desired[0] = 0.0
    returns, turnover, exposure = np.zeros(T), np.zeros(T), np.zeros(T)
    prev_w = np.zeros(N, dtype=float)
    symbols = list(data["C"].columns)
    for i in range(1, T):
        prev_close, open_i, high_i, low_i, close_i = C[i - 1], O[i], H[i], L[i], C[i]
        valid_bar = (np.isfinite(open_i) & np.isfinite(high_i) & np.isfinite(low_i) & np.isfinite(close_i) &
                     (open_i > 0) & (high_i > 0) & (low_i > 0) & (close_i > 0) &
                     (high_i >= np.maximum(open_i, close_i)) &
                     (low_i <= np.minimum(open_i, close_i)) & (high_i >= low_i))
        bad_held = (prev_w > 1e-8) & (~valid_bar | ~np.isfinite(prev_close) | (prev_close <= 0))
        instruction = desired[i]
        rebalance = np.isfinite(instruction).all()
        target = instruction.astype(float, copy=True) if rebalance else None
        bad_entry = ((target > 1e-8) & ~valid_bar) if target is not None else np.zeros(N, bool)
        bad = bad_held | bad_entry
        if bad.any():
            j = int(np.flatnonzero(bad)[0])
            reason = "held position has an invalid or missing OHLC bar" if bad_held[j] else "entry target has an invalid or missing OHLC bar"
            raise ValueError(f"strict OHLC integrity failure on {data['cal'][i].date()} {symbols[j]}: {reason}")
        valid_gap = np.isfinite(open_i) & (open_i > 0) & np.isfinite(prev_close) & (prev_close > 0)
        gap = np.zeros(N, dtype=float)
        gap[valid_gap] = open_i[valid_gap] / prev_close[valid_gap] - 1.0
        overnight = float(np.dot(prev_w, gap))
        post_gap = prev_w * (1.0 + gap) / max(1.0 + overnight, 1e-12)
        if target is None:
            target = post_gap.copy()  # no order: preserve holdings and their drifted weights
        else:
            total = target.sum()
            if total > 1.0:
                target /= total
            sells = np.maximum(post_gap - target, 0).sum()
            buys = np.maximum(target - post_gap, 0).sum()
            turnover[i] = sells + buys
            fees = buys * data["fee_buy"] + sells * data["fee_sell"]
        if target is None:
            raise AssertionError("target must be set")
        if not rebalance:
            fees = 0.0
        intraday = np.zeros(N, dtype=float)
        intraday[valid_bar] = close_i[valid_bar] / open_i[valid_bar] - 1.0
        portfolio_intraday = float(np.dot(target, intraday))
        returns[i] = (1.0 + overnight) * (1.0 - fees) * (1.0 + portfolio_intraday) - 1.0
        exposure[i] = target.sum()
        prev_w = target * (1.0 + intraday) / max(1.0 + portfolio_intraday, 1e-12)
        prev_w = np.maximum(prev_w, 0.0)
        if prev_w.sum() > 1.0:
            prev_w /= prev_w.sum()
    idx = data["cal"]
    return pd.Series(returns, index=idx), pd.Series(turnover, index=idx), pd.Series(exposure, index=idx)


def market_snapshot_hash(market: str, data: dict) -> dict:
    folder = g1.DATA / "kr_daily_v2" / "data" if market == "KR" else g1.DATA / "us_daily"
    if market == "KR":
        paths = [folder / "005930.parquet", g1.DATA / "kr_daily_v2" / "universe" / "universe_raw.csv"]
        paths += [folder / f"{symbol}.parquet" for symbol in data["C"].columns]
    else:
        paths = [folder / "SPY.parquet", folder / "pit" / "sp500_ticker_start_end.csv"]
        for symbol in data["C"].columns:
            paths.append(folder / f"{symbol}.parquet")
            meta = folder / f"{symbol}.meta.json"
            if meta.exists():
                paths.append(meta)
    h, files = hashlib.sha256(), []
    for path in sorted(set(paths)):
        if not path.is_file():
            raise FileNotFoundError(f"snapshot input disappeared: {path}")
        digest = sha256(path)
        rel = str(path.relative_to(g1.DATA))
        h.update(f"{rel}\0{digest}\n".encode())
        files.append(rel)
    return {"sha256": h.hexdigest(), "files": len(files), "scope": "files actually used plus universe/calendar inputs"}


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN05-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger, curves_path, manifest_path = (HERE / f"attempts_{run_id}.jsonl",
                                           HERE / f"equity_curves_{run_id}.csv.gz",
                                           HERE / f"manifest_{run_id}.json")
    manifest = {"run_id": run_id, "prereg_sha256": sha256(PREREG),
                "runner_sha256": sha256(Path(__file__)),
                "gen01_runner_sha256": sha256(ROOT / "generation_01" / "run_gen01.py"),
                "gen03_runner_sha256": sha256(ROOT / "generation_03" / "run_gen03.py"),
                "gen04_runner_sha256": sha256(ROOT / "generation_04" / "run_gen04.py"),
                "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
                "started_utc": started.isoformat(), "data_root": str(g1.DATA),
                "attempts_file": str(ledger), "planned_attempts": 2, "status": "RUNNING",
                "evidence_status": "EXPLORATORY_ONLY_HISTORIC_WINDOWS_AND_TRIALS_UNRESOLVED"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    curves = []
    for market in ("US", "KR"):
        attempt_id = f"{run_id}-{market}-LOW_MAX21_LONG_ONLY"
        log_event(ledger, {"event": "attempt_start", "attempt_id": attempt_id, "market": market,
                           "candidate": "LOW_MAX21_LONG_ONLY", "status": "STARTED",
                           "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
        start = time.monotonic()
        try:
            data = g1.load_market(market)
            snapshot = market_snapshot_hash(market, data)
            months = g1.month_ends(data["cal"])
            benchmark_returns, benchmark_turnover, benchmark_exposure = g1.benchmark_returns(data)
            benchmark = g3.metric_for(benchmark_returns, benchmark_turnover, benchmark_exposure, market, months)
            if benchmark["IS"].get("status") != "OK":
                raise ValueError(f"benchmark preflight failed: {benchmark['IS']}")
            score = max21(data["C"])
            weights = targets(score, data["eligible"], months, int(data["k"]))
            order_rows = np.isfinite(weights).all(axis=1)
            no_order_rows = np.isnan(weights).all(axis=1)
            if not np.all(order_rows | no_order_rows):
                raise ValueError("target rows must be complete order vectors or all-NaN no-order markers")
            if ((weights[order_rows] < 0).any() or
                    (weights[order_rows].sum(axis=1) > 1.000001).any()):
                raise ValueError("portfolio weights violate finite/long-only/gross-exposure bounds")
            returns, turnover, exposure = simulate_monthly_strict(data, weights)
            strategy = g3.metric_for(returns, turnover, exposure, market, months)
            if not np.isfinite(returns.to_numpy()).all():
                raise ValueError("strategy returns contain non-finite values")
            for date, value in returns.items():
                curves.append({"attempt_id": attempt_id, "market": market,
                               "candidate": "LOW_MAX21_LONG_ONLY", "date": date.date().isoformat(),
                               "daily_return_net": float(value), "turnover": float(turnover.loc[date]),
                               "exposure": float(exposure.loc[date])})
            manifest.setdefault("markets", {})[market] = {"sessions": len(data["cal"]),
                "symbols": len(data["C"].columns), "benchmark": benchmark,
                "data_note": data["data_note"], "input_snapshot": snapshot}
            log_event(ledger, {"event": "attempt_finish", "attempt_id": attempt_id, "market": market,
                "candidate": "LOW_MAX21_LONG_ONLY", "status": "COMPLETED_EXPLORATORY",
                "strategy": strategy, "benchmark": benchmark, "input_snapshot": snapshot,
                "runtime_seconds": round(time.monotonic() - start, 3),
                "nonconfirmatory_reason": "previously inspected partitions, incomplete PIT coverage and unresolved global historical trials"})
            print(f"{attempt_id}: {json.dumps(strategy, ensure_ascii=False, allow_nan=False)}", flush=True)
        except Exception as exc:
            log_event(ledger, {"event": "attempt_fail", "attempt_id": attempt_id, "market": market,
                "candidate": "LOW_MAX21_LONG_ONLY", "status": "FAILED", "error_type": type(exc).__name__,
                "error": str(exc), "traceback": traceback.format_exc(limit=8),
                "runtime_seconds": round(time.monotonic() - start, 3),
                "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
            print(f"{attempt_id}: FAILED {type(exc).__name__}: {exc}", flush=True)
    if curves:
        pd.DataFrame(curves).to_csv(curves_path, index=False, compression="gzip")
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest["attempt_events_sha256"] = sha256(ledger)
    manifest["attempt_events"] = sum(1 for _ in ledger.open(encoding="utf-8"))
    manifest["curve_file"] = str(curves_path) if curves else None
    if curves:
        manifest["curve_file_sha256"] = sha256(curves_path)
    manifest["status"] = "FINISHED"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
