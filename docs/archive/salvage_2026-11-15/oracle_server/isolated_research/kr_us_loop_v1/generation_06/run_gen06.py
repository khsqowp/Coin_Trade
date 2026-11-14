"""Generation 06 fixed cross-sectional low-beta exploratory screen."""
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
g5 = load("gen05", ROOT / "generation_05" / "run_gen05.py")


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


def rolling_market_beta(asset_returns: pd.DataFrame, market_returns: pd.Series | pd.DataFrame,
                        window: int = 252, min_periods: int = 200) -> pd.DataFrame:
    """Trailing paired-observation OLS slope with intercept, ending on each row.

    A Series is the shared market factor (US); a DataFrame supplies a per-name
    factor (KR leave-one-out equal-weight proxy).
    """
    clean = asset_returns.astype(float).replace([np.inf, -np.inf], np.nan)
    market_frame = (market_returns.reindex(asset_returns.index).astype(float).to_frame("__market__")
                    if isinstance(market_returns, pd.Series)
                    else market_returns.reindex(index=asset_returns.index, columns=asset_returns.columns).astype(float))
    market_frame = market_frame.replace([np.inf, -np.inf], np.nan)
    betas = {}
    for symbol in clean.columns:
        market = market_frame["__market__"] if "__market__" in market_frame else market_frame[symbol]
        paired = clean[symbol].notna() & market.notna()
        paired_asset = clean[symbol].where(paired)
        paired_market = market.where(paired)
        cov = paired_asset.rolling(window, min_periods=min_periods).cov(paired_market)
        variance = paired_market.rolling(window, min_periods=min_periods).var(ddof=1)
        betas[symbol] = cov / variance.where(variance > 0)
    result = pd.DataFrame(betas, index=asset_returns.index, columns=asset_returns.columns)
    # Require a contemporaneous valid paired observation at decision close t;
    # otherwise an old beta must not be treated as current.
    latest_valid = clean.notna() & market_frame.notna().to_numpy() if "__market__" not in market_frame else clean.notna().mul(market_frame["__market__"].notna(), axis=0)
    return result.where(latest_valid)


def rolling_paired_count(asset_returns: pd.DataFrame, market_returns: pd.Series | pd.DataFrame,
                         window: int = 252) -> pd.DataFrame:
    clean = asset_returns.astype(float).replace([np.inf, -np.inf], np.nan)
    market_frame = (market_returns.reindex(asset_returns.index).astype(float).to_frame("__market__")
                    if isinstance(market_returns, pd.Series)
                    else market_returns.reindex(index=asset_returns.index, columns=asset_returns.columns).astype(float))
    market_frame = market_frame.replace([np.inf, -np.inf], np.nan)
    counts = {}
    for symbol in clean.columns:
        market = market_frame["__market__"] if "__market__" in market_frame else market_frame[symbol]
        valid = clean[symbol].notna() & market.notna()
        counts[symbol] = valid.astype(np.int16).rolling(window, min_periods=1).sum()
    return pd.DataFrame(counts, index=asset_returns.index, columns=asset_returns.columns)


def market_factor_returns(data: dict, stock_returns: pd.DataFrame, market: str) -> pd.Series | pd.DataFrame:
    if market == "US":
        return data["benchmark"].astype(float).pct_change(fill_method=None)
    active_returns = stock_returns.where(data["eligible"].fillna(False))
    counts = active_returns.notna().sum(axis=1)
    sums = active_returns.sum(axis=1, min_count=1)
    # Per-name leave-one-out market return avoids each asset mechanically
    # entering its own factor. Names absent from that day's eligible set are
    # not used to estimate their own factor.
    out = pd.DataFrame(np.nan, index=stock_returns.index, columns=stock_returns.columns, dtype=float)
    for symbol in stock_returns.columns:
        own = active_returns[symbol]
        denom = counts - own.notna().astype(int)
        valid = own.notna() & (denom > 0)
        out.loc[valid, symbol] = ((sums[valid] - own[valid]) / denom[valid]).astype(float)
        # When the evaluated ticker is not a member of the eligible proxy on
        # that date, use the full eligible-universe average; its stock return
        # remains a valid paired observation for its own beta estimate.
        not_member = stock_returns[symbol].notna() & ~own.notna() & (counts > 0)
        out.loc[not_member, symbol] = (sums[not_member] / counts[not_member]).astype(float)
    return out


def month_end_targets(beta: pd.DataFrame, eligible: pd.DataFrame,
                      month_days: np.ndarray, k: int) -> np.ndarray:
    if not beta.index.equals(eligible.index) or not beta.columns.equals(eligible.columns):
        raise ValueError("beta and eligibility axes differ")
    out = np.zeros(beta.shape, dtype=np.float32)
    for i in month_days:
        names = g5.select_low_max(beta.iloc[i], eligible.iloc[i], k)
        if names:
            out[i, beta.columns.get_indexer(names)] = 1.0 / len(names)
    non_rebalance = np.ones(len(beta), dtype=bool)
    non_rebalance[month_days] = False
    out[non_rebalance] = np.nan
    return out


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
    run_id = f"GEN06-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger, curve_path, selection_path, manifest_path = (HERE / f"attempts_{run_id}.jsonl",
                                         HERE / f"equity_curves_{run_id}.csv.gz",
                                         HERE / f"selection_audit_{run_id}.csv.gz",
                                         HERE / f"manifest_{run_id}.json")
    manifest = {"run_id": run_id, "prereg_sha256": sha256(PREREG),
                "runner_sha256": sha256(Path(__file__)),
                "gen01_runner_sha256": sha256(ROOT / "generation_01" / "run_gen01.py"),
                "gen03_runner_sha256": sha256(ROOT / "generation_03" / "run_gen03.py"),
                "gen05_runner_sha256": sha256(ROOT / "generation_05" / "run_gen05.py"),
                "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
                "started_utc": started.isoformat(), "data_root": str(g1.DATA),
                "attempts_file": str(ledger), "planned_attempts": 2, "status": "RUNNING",
                "evidence_status": "EXPLORATORY_ONLY_HISTORIC_WINDOWS_AND_TRIALS_UNRESOLVED"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    curves, selection_audit = [], []
    for market in ("US", "KR"):
        aid = f"{run_id}-{market}-LOW_BETA_LONG_ONLY"
        log_event(ledger, {"event": "attempt_start", "attempt_id": aid, "market": market,
                           "candidate": "LOW_BETA_LONG_ONLY", "status": "STARTED",
                           "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
        tic = time.monotonic()
        snapshot = None
        try:
            data = g1.load_market(market)
            snapshot = market_snapshot_hash(market, data)
            months = g1.month_ends(data["cal"])
            bench_r, bench_tv, bench_ex = g1.benchmark_returns(data)
            benchmark = g3.metric_for(bench_r, bench_tv, bench_ex, market, months)
            if benchmark["IS"].get("status") != "OK":
                raise ValueError(f"benchmark preflight failed: {benchmark['IS']}")
            close_returns = data["C"].astype(float).pct_change(fill_method=None)
            market_returns = market_factor_returns(data, close_returns, market)
            beta = rolling_market_beta(close_returns, market_returns)
            paired_counts = rolling_paired_count(close_returns, market_returns)
            weights = month_end_targets(beta, data["eligible"], months, int(data["k"]))
            order_rows = np.isfinite(weights).all(axis=1)
            no_order_rows = np.isnan(weights).all(axis=1)
            if not np.all(order_rows | no_order_rows):
                raise ValueError("target rows must be complete finite vectors or all-NaN no-order markers")
            if (weights[order_rows] < 0).any() or (weights[order_rows].sum(axis=1) > 1.000001).any():
                raise ValueError("target weights violate long-only or gross-exposure bounds")
            returns, turnover, exposure = g5.simulate_monthly_strict(data, weights)
            strategy = g3.metric_for(returns, turnover, exposure, market, months)
            if not np.isfinite(returns.to_numpy()).all():
                raise ValueError("strategy return series contains non-finite values")
            for date, value in returns.items():
                curves.append({"attempt_id": aid, "market": market, "candidate": "LOW_BETA_LONG_ONLY",
                               "date": date.date().isoformat(), "daily_return_net": float(value),
                               "turnover": float(turnover.loc[date]), "exposure": float(exposure.loc[date])})
            for i in months:
                selected = np.flatnonzero(weights[i] > 0)
                for j in selected:
                    symbol = data["C"].columns[j]
                    selection_audit.append({"attempt_id": aid, "market": market,
                        "decision_date": data["cal"][i].date().isoformat(), "ticker": symbol,
                        "beta": float(beta.iloc[i, j]), "paired_observations": int(paired_counts.iloc[i, j]),
                        "target_weight": float(weights[i, j])})
            manifest.setdefault("markets", {})[market] = {"sessions": len(data["cal"]),
                "symbols": len(data["C"].columns), "benchmark": benchmark, "data_note": data["data_note"],
                "market_proxy_note": "KR equal-weight eligible-universe proxy, not official total-return index" if market == "KR" else "SPY adjusted close",
                "input_snapshot": snapshot}
            log_event(ledger, {"event": "attempt_finish", "attempt_id": aid, "market": market,
                "candidate": "LOW_BETA_LONG_ONLY", "status": "COMPLETED_EXPLORATORY",
                "strategy": strategy, "benchmark": benchmark, "input_snapshot": snapshot,
                "runtime_seconds": round(time.monotonic() - tic, 3),
                "nonconfirmatory_reason": "historical partitions previously inspected; PIT/corporate-action coverage and full historical trial count unresolved"})
            print(f"{aid}: {json.dumps(strategy, ensure_ascii=False, allow_nan=False)}", flush=True)
        except Exception as exc:
            log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": market,
                "candidate": "LOW_BETA_LONG_ONLY", "status": "FAILED", "error_type": type(exc).__name__,
                "error": str(exc), "traceback": traceback.format_exc(limit=8),
                "runtime_seconds": round(time.monotonic() - tic, 3),
                "input_snapshot": snapshot,
                "input_snapshot_status": "COMPUTED" if snapshot is not None else "UNAVAILABLE_BEFORE_MARKET_LOAD_COMPLETED",
                "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
            print(f"{aid}: FAILED {type(exc).__name__}: {exc}", flush=True)
    if curves:
        pd.DataFrame(curves).to_csv(curve_path, index=False, compression="gzip")
    if selection_audit:
        pd.DataFrame(selection_audit).to_csv(selection_path, index=False, compression="gzip")
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest["attempt_events_sha256"] = sha256(ledger)
    manifest["attempt_events"] = sum(1 for _ in ledger.open(encoding="utf-8"))
    manifest["curve_file"] = str(curve_path) if curves else None
    if curves:
        manifest["curve_file_sha256"] = sha256(curve_path)
    manifest["selection_audit_file"] = str(selection_path) if selection_audit else None
    if selection_audit:
        manifest["selection_audit_sha256"] = sha256(selection_path)
    manifest["status"] = "FINISHED"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
