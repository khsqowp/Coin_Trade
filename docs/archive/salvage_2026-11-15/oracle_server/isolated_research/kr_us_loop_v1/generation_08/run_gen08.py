"""Generation 08 US market-model residual-skew exploratory screen."""
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
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def validate_membership_intervals(membership: pd.DataFrame) -> None:
    ordered = membership.sort_values(["ticker", "start_date", "end_date"])
    prior_end = ordered.groupby("ticker", sort=False)["end_date"].shift(1)
    overlap = prior_end.notna() & (ordered["start_date"] <= prior_end)
    if overlap.any():
        row = ordered.loc[overlap].iloc[0]
        raise ValueError(f"overlapping PIT membership intervals for ticker {row['ticker']}")


def completed_month_ends(index: pd.DatetimeIndex) -> np.ndarray:
    ends = g1.month_ends(index)
    if len(index) == 0:
        return ends
    last_period = index[-1].to_period("M")
    return np.asarray([i for i in ends if index[i].to_period("M") < last_period], dtype=int)


def residual_skew_at(stock_returns: pd.DataFrame, market_returns: pd.Series, end_i: int,
                     window: int = 252, min_obs: int = 200) -> np.ndarray:
    """Population skewness of in-window OLS residuals, fitted only through end_i."""
    if not stock_returns.index.equals(market_returns.index):
        raise ValueError("stock and market return dates differ")
    if end_i < 0 or end_i >= len(stock_returns) or window < min_obs or min_obs < 3:
        raise ValueError("invalid end index or regression window")
    left = max(0, end_i - window + 1)
    y = stock_returns.iloc[left:end_i + 1].to_numpy(dtype=float)
    x = market_returns.iloc[left:end_i + 1].to_numpy(dtype=float)[:, None]
    valid = np.isfinite(y) & np.isfinite(x)
    n = valid.sum(axis=0)
    denom_n = np.where(n > 0, n, 1)
    x_sum = np.where(valid, x, 0.0).sum(axis=0)
    y_sum = np.where(valid, y, 0.0).sum(axis=0)
    x_mean, y_mean = x_sum / denom_n, y_sum / denom_n
    xc = np.where(valid, x - x_mean, 0.0)
    yc = np.where(valid, y - y_mean, 0.0)
    x_var = np.sum(xc * xc, axis=0) / denom_n
    cov = np.sum(xc * yc, axis=0) / denom_n
    beta = np.divide(cov, x_var, out=np.full_like(cov, np.nan), where=x_var > 0)
    residual = np.where(valid, y - y_mean - xc * beta, np.nan)
    res_mean = np.nansum(residual, axis=0) / denom_n
    centered = np.where(valid, residual - res_mean, 0.0)
    var = np.sum(centered ** 2, axis=0) / denom_n
    third = np.sum(centered ** 3, axis=0) / denom_n
    skew = np.divide(third, var ** 1.5, out=np.full_like(third, np.nan), where=var > 1e-20)
    skew[(n < min_obs) | ~np.isfinite(skew)] = np.nan
    return skew


def membership_state(data: dict) -> tuple[pd.DataFrame, np.ndarray, list[dict]]:
    """Build active loaded-member mask and full PIT member count, including absent prices."""
    folder = g1.DATA / "us_daily"
    path = folder / "pit" / "sp500_ticker_start_end.csv"
    m = pd.read_csv(path, dtype={"ticker": str})
    m["ticker"] = m["ticker"].str.replace(".", "-", regex=False)
    m["start_date"] = pd.to_datetime(m["start_date"], errors="coerce").dt.normalize()
    m["end_date"] = pd.to_datetime(m["end_date"].fillna("2099-12-31"), errors="coerce").dt.normalize()
    if m[["ticker", "start_date", "end_date"]].isna().any().any():
        raise ValueError("invalid PIT membership row")
    if (m["end_date"] < m["start_date"]).any():
        raise ValueError("PIT membership end precedes start")
    validate_membership_intervals(m)
    idx = data["cal"]
    diff = np.zeros(len(idx) + 1, dtype=np.int32)
    names = set(m["ticker"])
    columns = set(data["C"].columns)
    member = pd.DataFrame(False, index=idx, columns=data["C"].columns)
    availability = []
    for symbol in sorted(names):
        rows = m.loc[m["ticker"] == symbol]
        intervals = []
        for row in rows.itertuples(index=False):
            start = int(idx.searchsorted(row.start_date, side="left"))
            stop = int(idx.searchsorted(row.end_date, side="right"))
            if start < stop:
                diff[start] += 1
                diff[stop] -= 1
                intervals.append((start, stop))
                if symbol in columns:
                    member.iloc[start:stop, member.columns.get_loc(symbol)] = True
        price_path = folder / f"{symbol}.parquet"
        meta_path = folder / f"{symbol}.meta.json"
        price_exists, meta_exists = price_path.is_file(), meta_path.is_file()
        price_hash = sha256(price_path) if price_exists else ""
        meta_hash = sha256(meta_path) if meta_exists else ""
        availability.append({"ticker": symbol, "price_file_present": price_exists,
                             "price_sha256": price_hash, "metadata_present": meta_exists,
                             "metadata_sha256": meta_hash, "loaded_by_market_loader": symbol in columns,
                             "membership_intervals": len(intervals)})
    counts = np.cumsum(diff[:-1]).astype(np.int32)
    if (counts < 0).any():
        raise ValueError("PIT full-member count became negative")
    return member, counts, availability


def month_end_targets(scores: pd.DataFrame, members: pd.DataFrame, month_days: np.ndarray,
                      full_member_counts: np.ndarray, min_coverage: float = 0.85,
                      k: int = 50) -> tuple[np.ndarray, list[dict]]:
    if not scores.index.equals(members.index) or not scores.columns.equals(members.columns):
        raise ValueError("scores and membership axes differ")
    if len(full_member_counts) != len(scores) or k < 1 or not 0 < min_coverage <= 1:
        raise ValueError("invalid coverage alignment or selection parameters")
    weights = np.zeros(scores.shape, dtype=np.float32)
    audit = []
    for i in month_days:
        eligible = members.iloc[i].fillna(False).astype(bool)
        row = scores.iloc[i].astype(float)
        valid = eligible & np.isfinite(row)
        total = int(full_member_counts[i])
        count = int(valid.sum())
        coverage = count / total if total else 0.0
        item = {"decision_date": scores.index[i].date().isoformat(),
                "full_pit_members": total, "loaded_pit_members": int(eligible.sum()),
                "valid_score_count": count, "coverage": coverage,
                "selected_count": 0, "cash_due_to_coverage": coverage < min_coverage}
        if coverage >= min_coverage:
            ranked = sorted(row.index[valid].tolist(), key=lambda s: (float(row[s]), str(s)))
            selected = ranked[:k]
            if selected:
                weights[i, scores.columns.get_indexer(selected)] = 1.0 / len(selected)
                item["selected"] = selected
                item["selected_count"] = len(selected)
        audit.append(item)
    no_order = np.ones(len(scores), dtype=bool)
    no_order[month_days] = False
    weights[no_order] = np.nan
    return weights, audit


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN08-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger = HERE / f"attempts_{run_id}.jsonl"
    curve_path = HERE / f"equity_curves_{run_id}.csv.gz"
    selection_path = HERE / f"selection_audit_{run_id}.csv.gz"
    coverage_path = HERE / f"coverage_audit_{run_id}.csv"
    availability_path = HERE / f"availability_audit_{run_id}.csv.gz"
    manifest_path = HERE / f"manifest_{run_id}.json"
    manifest = {"run_id": run_id, "prereg_sha256": sha256(PREREG),
        "runner_sha256": sha256(Path(__file__)), "test_sha256": sha256(HERE / "test_gen08.py"),
        "gen01_runner_sha256": sha256(ROOT / "generation_01" / "run_gen01.py"),
        "gen03_runner_sha256": sha256(ROOT / "generation_03" / "run_gen03.py"),
        "gen05_runner_sha256": sha256(ROOT / "generation_05" / "run_gen05.py"),
        "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
        "started_utc": started.isoformat(), "data_root": str(g1.DATA),
        "planned_attempts": 1, "status": "RUNNING",
        "evidence_status": "EXPLORATORY_ONLY_PREVIOUSLY_INSPECTED_WINDOWS_AND_UNRESOLVED_PIT_TRIAL_HISTORY"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    aid = f"{run_id}-US-LOW_RESIDUAL_SKEW"
    log_event(ledger, {"event": "attempt_start", "attempt_id": aid, "market": "US",
        "candidate": "LOW_SPY_MARKET_MODEL_RESIDUAL_SKEW_TOP50", "status": "STARTED",
        "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
    tic = time.monotonic()
    failed = False
    curves, selected_rows, coverage_rows = [], [], []
    try:
        data = g1.load_market("US")
        member, counts, availability = membership_state(data)
        months = completed_month_ends(data["cal"])
        if not len(months):
            raise ValueError("no completed formation months")
        close_ret = data["C"].astype(float).pct_change(fill_method=None)
        market_ret = data["benchmark"].astype(float).pct_change(fill_method=None)
        scores = pd.DataFrame(np.nan, index=data["cal"], columns=data["C"].columns, dtype=float)
        for i in months:
            scores.iloc[i] = residual_skew_at(close_ret, market_ret, int(i), 252, 200)
        current_close_valid = np.isfinite(data["C"]) & (data["C"] > 0)
        scores = scores.where(current_close_valid)
        weights, audit = month_end_targets(scores, member, months, counts, 0.85, 50)
        passing = sum(item["coverage"] >= 0.85 for item in audit)
        if passing == 0:
            raise ValueError("no completed decision month meets 85% full-PIT score coverage")
        order_rows = np.isfinite(weights).all(axis=1)
        if ((weights[order_rows] < 0).any() or
                (weights[order_rows].sum(axis=1) > 1.000001).any()):
            raise ValueError("portfolio weights violate long-only/gross-exposure bounds")
        bench_r, bench_tv, bench_ex = g1.benchmark_returns(data)
        benchmark = g3.metric_for(bench_r, bench_tv, bench_ex, "US", months)
        if benchmark["IS"].get("status") != "OK":
            raise ValueError(f"benchmark preflight failed: {benchmark['IS']}")
        returns, turnover, exposure = g5.simulate_monthly_strict(data, weights)
        if not np.isfinite(returns.to_numpy()).all():
            raise ValueError("strategy returns contain non-finite values")
        strategy = g3.metric_for(returns, turnover, exposure, "US", months)
        for date, value in returns.items():
            curves.append({"attempt_id": aid, "market": "US", "candidate": "LOW_SPY_MARKET_MODEL_RESIDUAL_SKEW_TOP50",
                "date": date.date().isoformat(), "daily_return_net": float(value),
                "turnover": float(turnover.loc[date]), "exposure": float(exposure.loc[date])})
        for item in audit:
            coverage_rows.append(item)
            decision_i = data["cal"].get_loc(pd.Timestamp(item["decision_date"]))
            for symbol in item.get("selected", []):
                pos = data["C"].columns.get_loc(symbol)
                selected_rows.append({"attempt_id": aid, **item, "ticker": symbol,
                    "residual_skew": float(scores.iloc[decision_i, pos]),
                    "target_weight": float(weights[decision_i, pos])})
        availability_df = pd.DataFrame(availability)
        membership_file = g1.DATA / "us_daily" / "pit" / "sp500_ticker_start_end.csv"
        spy_file = g1.DATA / "us_daily" / "SPY.parquet"
        membership_sha, spy_sha = sha256(membership_file), sha256(spy_file)
        hash_builder = hashlib.sha256()
        hash_builder.update(availability_df.to_csv(index=False).encode())
        hash_builder.update(f"membership\0{membership_sha}\nSPY\0{spy_sha}\n".encode())
        availability_hash = hash_builder.hexdigest()
        manifest["market"] = {"sessions": len(data["cal"]), "loaded_symbols": len(data["C"].columns),
            "unique_pit_symbols": len(availability), "benchmark": benchmark,
            "data_note": data["data_note"], "input_availability_sha256": availability_hash,
            "membership_file_sha256": membership_sha, "spy_parquet_sha256": spy_sha,
            "decisions": len(audit), "coverage_passing_decisions": passing,
            "trailing_partial_month_excluded": str(data["cal"][-1].to_period("M")),
            "data_hash_scope": "all PIT ticker price/meta file presence and hashes, plus membership intervals; price snapshot is non-atomic"}
        log_event(ledger, {"event": "attempt_finish", "attempt_id": aid, "market": "US",
            "candidate": "LOW_SPY_MARKET_MODEL_RESIDUAL_SKEW_TOP50", "status": "COMPLETED_EXPLORATORY",
            "strategy": strategy, "benchmark": benchmark, "input_availability_sha256": availability_hash,
            "runtime_seconds": round(time.monotonic() - tic, 3),
            "nonconfirmatory_reason": "historical partitions already inspected; PIT prices, corporate actions, delisting proceeds and global trial count unresolved"})
        print(json.dumps({"strategy": strategy, "benchmark": benchmark}, ensure_ascii=False, allow_nan=False), flush=True)
    except Exception as exc:
        failed = True
        log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": "US",
            "candidate": "LOW_SPY_MARKET_MODEL_RESIDUAL_SKEW_TOP50", "status": "FAILED",
            "error_type": type(exc).__name__, "error": str(exc),
            "traceback": traceback.format_exc(limit=10), "runtime_seconds": round(time.monotonic() - tic, 3),
            "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
        print(f"FAILED {type(exc).__name__}: {exc}", flush=True)
    artifact_failure = False
    try:
        if curves:
            pd.DataFrame(curves).to_csv(curve_path, index=False, compression="gzip")
        if selected_rows:
            pd.DataFrame(selected_rows).to_csv(selection_path, index=False, compression="gzip")
        if coverage_rows:
            pd.DataFrame(coverage_rows).to_csv(coverage_path, index=False)
        if "availability" in locals():
            pd.DataFrame(availability).to_csv(availability_path, index=False, compression="gzip")
            manifest["availability_audit_file"] = str(availability_path)
            manifest["availability_audit_sha256"] = sha256(availability_path)
    except Exception as exc:
        artifact_failure = True
        failed = True
        log_event(ledger, {"event": "artifact_write_fail", "attempt_id": aid,
            "status": "FAILED_ARTIFACT_FINALIZATION", "error_type": type(exc).__name__,
            "error": str(exc), "traceback": traceback.format_exc(limit=8)})
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest["attempt_events_sha256"] = sha256(ledger)
    manifest["attempt_status"] = "FAILED" if failed else "COMPLETED_EXPLORATORY"
    manifest["artifact_status"] = "FAILED" if artifact_failure else "WRITTEN"
    manifest["status"] = ("FAILED_ARTIFACT_FINALIZATION" if artifact_failure else
                           "FINISHED_WITH_FAILED_ATTEMPT" if failed else "COMPLETED_EXPLORATORY")
    for key, path in (("curve_file", curve_path), ("selection_audit_file", selection_path),
                      ("coverage_audit_file", coverage_path)):
        manifest[key] = str(path) if path.exists() else None
        if path.exists():
            manifest[f"{key}_sha256"] = sha256(path)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
