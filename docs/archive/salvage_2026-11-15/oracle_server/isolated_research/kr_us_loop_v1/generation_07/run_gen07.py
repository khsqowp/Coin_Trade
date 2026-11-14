"""Generation 07 US AB_NR screen. Local snapshot only; exploratory, never live."""
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


def monthly_nr(daytime: pd.DataFrame, overnight: pd.DataFrame,
               min_sessions: int = 15) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monthly reversal frequency and valid-session counts from aligned returns."""
    if not daytime.index.equals(overnight.index) or not daytime.columns.equals(overnight.columns):
        raise ValueError("daytime and overnight axes differ")
    if min_sessions < 1:
        raise ValueError("min_sessions must be positive")
    d = daytime.astype(float).replace([np.inf, -np.inf], np.nan)
    n = overnight.astype(float).replace([np.inf, -np.inf], np.nan)
    valid = d.notna() & n.notna()
    reversal = ((n > 0) & (d < 0)).where(valid)
    periods = daytime.index.to_period("M")
    counts = valid.groupby(periods).sum().astype("int32")
    hits = reversal.groupby(periods).sum(min_count=1)
    nr = hits.div(counts.where(counts >= min_sessions)).where(counts >= min_sessions)
    nr.index = pd.PeriodIndex(nr.index, freq="M")
    counts.index = pd.PeriodIndex(counts.index, freq="M")
    return nr.astype(float), counts


def abnormal_nr(nr: pd.DataFrame, prior_months: int = 12,
                min_prior: int = 10) -> pd.DataFrame:
    """Current NR divided by its prior-only valid monthly mean."""
    if not isinstance(nr.index, pd.PeriodIndex) or nr.index.freqstr != "M":
        raise ValueError("nr index must be monthly PeriodIndex")
    if prior_months < min_prior or min_prior < 1:
        raise ValueError("invalid prior-month requirements")
    values = nr.astype(float).replace([np.inf, -np.inf], np.nan)
    out = pd.DataFrame(np.nan, index=values.index, columns=values.columns, dtype=float)
    for i in range(len(values.index)):
        if i < prior_months:
            continue
        current = values.iloc[i]
        prior = values.iloc[i - prior_months:i]
        n = prior.notna().sum(axis=0)
        mean = prior.mean(axis=0, skipna=True)
        ok = current.notna() & (n >= min_prior) & np.isfinite(mean) & (mean > 0)
        out.iloc[i] = (current / mean).where(ok)
    return out


def completed_month_ends(index: pd.DatetimeIndex) -> np.ndarray:
    """Month-end sessions excluding the final observed (possibly partial) month."""
    ends = g1.month_ends(index)
    if len(index) == 0:
        return ends
    final_period = index[-1].to_period("M")
    return np.asarray([i for i in ends if index[i].to_period("M") < final_period], dtype=int)


def month_end_targets(score_daily: pd.DataFrame, eligible: pd.DataFrame,
                      month_days: np.ndarray, coverage_min: float = 0.85,
                      full_member_counts: np.ndarray | None = None) -> tuple[np.ndarray, list[dict]]:
    """Sparse month-end weights, with 100% cash when score coverage is low."""
    if not score_daily.index.equals(eligible.index) or not score_daily.columns.equals(eligible.columns):
        raise ValueError("score and eligibility axes differ")
    if not 0 < coverage_min <= 1:
        raise ValueError("coverage_min must be in (0, 1]")
    if full_member_counts is not None and len(full_member_counts) != len(score_daily):
        raise ValueError("full_member_counts must align with daily rows")
    weights = np.zeros(score_daily.shape, dtype=np.float32)
    audit: list[dict] = []
    monthly = score_daily.copy()
    monthly.index = monthly.index.to_period("M")
    for i in month_days:
        period = score_daily.index[i].to_period("M")
        row = score_daily.iloc[i].astype(float)
        elig = eligible.iloc[i].fillna(False).astype(bool)
        available_eligible_count = int(elig.sum())
        eligible_count = (int(full_member_counts[i]) if full_member_counts is not None
                          else available_eligible_count)
        valid = elig & np.isfinite(row)
        valid_count = int(valid.sum())
        coverage = valid_count / eligible_count if eligible_count else 0.0
        decision = {"decision_date": score_daily.index[i].date().isoformat(),
                    "month": str(period), "eligible_count": eligible_count,
                    "available_eligible_count": available_eligible_count,
                    "valid_score_count": valid_count, "coverage": coverage,
                    "selected_count": 0, "cash_due_to_coverage": coverage < coverage_min}
        if coverage >= coverage_min and valid_count:
            ranked = sorted(row.index[valid].tolist(), key=lambda s: (-float(row[s]), str(s)))
            k = max(1, int(np.ceil(valid_count * 0.10)))
            selected = ranked[:k]
            weights[i, score_daily.columns.get_indexer(selected)] = 1.0 / len(selected)
            decision["selected_count"] = len(selected)
            decision["selected"] = selected
        audit.append(decision)
    non_rebalance = np.ones(len(score_daily), dtype=bool)
    non_rebalance[month_days] = False
    weights[non_rebalance] = np.nan
    return weights, audit


def market_snapshot_hash(data: dict) -> dict:
    folder = g1.DATA / "us_daily"
    paths = [folder / "SPY.parquet", folder / "pit" / "sp500_ticker_start_end.csv"]
    for symbol in data["C"].columns:
        p = folder / f"{symbol}.parquet"
        paths.append(p)
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
    return {"sha256": h.hexdigest(), "files": len(files),
            "scope": "all loaded ticker parquet files, available metadata, PIT membership, and SPY",
            "atomic": False, "note": "hash is computed after loading; concurrent file mutation is not excluded"}


def full_member_counts(index: pd.DatetimeIndex) -> np.ndarray:
    """Count all PIT members, including members missing local price files."""
    path = g1.DATA / "us_daily" / "pit" / "sp500_ticker_start_end.csv"
    membership = pd.read_csv(path, dtype={"ticker": str})
    membership["start_date"] = pd.to_datetime(membership["start_date"], errors="coerce").dt.normalize()
    membership["end_date"] = pd.to_datetime(membership["end_date"].fillna("2099-12-31"), errors="coerce").dt.normalize()
    if membership[["start_date", "end_date"]].isna().any().any():
        raise ValueError("PIT membership contains invalid dates")
    result = np.zeros(len(index), dtype=np.int32)
    starts = membership["start_date"].to_numpy(dtype="datetime64[ns]")
    ends = membership["end_date"].to_numpy(dtype="datetime64[ns]")
    for i, date in enumerate(index):
        ts = date.to_datetime64()
        result[i] = int(((starts <= ts) & (ends >= ts)).sum())
    return result


def build_signal(data: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    O, C = data["O"].astype(float), data["C"].astype(float)
    valid_ohlc = np.isfinite(O) & np.isfinite(C) & (O > 0) & (C > 0)
    daytime = (C / O - 1.0).where(valid_ohlc)
    cc = C.pct_change(fill_method=None)
    overnight = ((1.0 + cc) / (1.0 + daytime) - 1.0)
    overnight = overnight.where(valid_ohlc & np.isfinite(cc) & (C.shift(1) > 0))
    nr, counts = monthly_nr(daytime, overnight)
    scores_m = abnormal_nr(nr)
    scores_d = pd.DataFrame(np.nan, index=data["cal"], columns=C.columns, dtype=float)
    # Assign only at actual month-end session rows. Signals do not propagate into future rows.
    for i in g1.month_ends(data["cal"]):
        period = data["cal"][i].to_period("M")
        if period in scores_m.index:
            scores_d.iloc[i] = scores_m.loc[period].reindex(C.columns).to_numpy(float)
    return scores_d, nr, counts


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN07-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger = HERE / f"attempts_{run_id}.jsonl"
    curve_path = HERE / f"equity_curves_{run_id}.csv.gz"
    selection_path = HERE / f"selection_audit_{run_id}.csv.gz"
    coverage_path = HERE / f"coverage_audit_{run_id}.csv"
    manifest_path = HERE / f"manifest_{run_id}.json"
    manifest = {"run_id": run_id, "prereg_sha256": sha256(PREREG),
        "addendum_sha256": sha256(HERE / "ADDENDUM_A1.md"),
        "runner_sha256": sha256(Path(__file__)), "test_sha256": sha256(HERE / "test_gen07.py"),
        "gen01_runner_sha256": sha256(ROOT / "generation_01" / "run_gen01.py"),
        "gen03_runner_sha256": sha256(ROOT / "generation_03" / "run_gen03.py"),
        "gen05_runner_sha256": sha256(ROOT / "generation_05" / "run_gen05.py"),
        "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
        "started_utc": started.isoformat(), "data_root": str(g1.DATA),
        "planned_attempts": 1, "status": "RUNNING",
        "evidence_status": "EXPLORATORY_ONLY_PREVIOUSLY_INSPECTED_WINDOWS_AND_UNRESOLVED_PIT_TRIAL_HISTORY"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    aid = f"{run_id}-US-AB_NR_LONG"
    log_event(ledger, {"event": "attempt_start", "attempt_id": aid, "market": "US",
        "candidate": "AB_NR_TOP_DECILE_LONG", "status": "STARTED",
        "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
    tic = time.monotonic()
    curves, selections, coverage_rows = [], [], []
    snapshot = None
    failed = False
    try:
        data = g1.load_market("US")
        snapshot = market_snapshot_hash(data)
        months = completed_month_ends(data["cal"])
        if len(months) == 0:
            raise ValueError("no completed formation months in snapshot")
        bench_r, bench_tv, bench_ex = g1.benchmark_returns(data)
        benchmark = g3.metric_for(bench_r, bench_tv, bench_ex, "US", months)
        if benchmark["IS"].get("status") != "OK":
            raise ValueError(f"benchmark preflight failed: {benchmark['IS']}")
        score, monthly_nr_values, monthly_counts = build_signal(data)
        all_members = full_member_counts(data["cal"])
        weights, audit = month_end_targets(score, data["eligible"], months, 0.85,
                                           full_member_counts=all_members)
        passed_months = sum(x["coverage"] >= 0.85 for x in audit)
        if passed_months == 0:
            raise ValueError("no completed decision month meets 85% full-PIT-member signal coverage")
        if not (np.isfinite(weights).all(axis=1) | np.isnan(weights).all(axis=1)).all():
            raise ValueError("target rows must be complete finite vectors or all-NaN no-order markers")
        order_rows = np.isfinite(weights).all(axis=1)
        if (weights[order_rows] < 0).any() or (weights[order_rows].sum(axis=1) > 1.000001).any():
            raise ValueError("target weights violate long-only or gross-exposure bounds")
        returns, turnover, exposure = g5.simulate_monthly_strict(data, weights)
        if not np.isfinite(returns.to_numpy()).all():
            raise ValueError("strategy return series contains non-finite values")
        strategy = g3.metric_for(returns, turnover, exposure, "US", months)
        for date, value in returns.items():
            curves.append({"attempt_id": aid, "market": "US", "candidate": "AB_NR_TOP_DECILE_LONG",
                "date": date.date().isoformat(), "daily_return_net": float(value),
                "turnover": float(turnover.loc[date]), "exposure": float(exposure.loc[date])})
        for item in audit:
            coverage_rows.append(item)
            for symbol in item.get("selected", []):
                pos = data["C"].columns.get_loc(symbol)
                decision_i = data["cal"].get_loc(pd.Timestamp(item["decision_date"]))
                selections.append({"attempt_id": aid, **item, "ticker": symbol,
                    "ab_nr": float(score.iloc[decision_i, pos]),
                    "target_weight": float(weights[decision_i, pos])})
        manifest["market"] = {"sessions": len(data["cal"]), "symbols": len(data["C"].columns),
            "benchmark": benchmark, "data_note": data["data_note"], "input_snapshot": snapshot,
            "decision_months": len(audit), "months_coverage_passed": sum(x["coverage"] >= 0.85 for x in audit),
            "trailing_partial_month_excluded": str(data["cal"][-1].to_period("M")),
            "monthly_signal_values": int(monthly_nr_values.notna().sum().sum()),
            "valid_daily_decompositions": int(monthly_counts.sum().sum())}
        log_event(ledger, {"event": "attempt_finish", "attempt_id": aid, "market": "US",
            "candidate": "AB_NR_TOP_DECILE_LONG", "status": "COMPLETED_EXPLORATORY",
            "strategy": strategy, "benchmark": benchmark, "input_snapshot": snapshot,
            "runtime_seconds": round(time.monotonic() - tic, 3),
            "nonconfirmatory_reason": "historical periods already inspected; PIT coverage, corporate-action semantics and global trial count remain unresolved"})
        print(json.dumps({"strategy": strategy, "benchmark": benchmark}, ensure_ascii=False, allow_nan=False), flush=True)
    except Exception as exc:
        failed = True
        log_event(ledger, {"event": "attempt_fail", "attempt_id": aid, "market": "US",
            "candidate": "AB_NR_TOP_DECILE_LONG", "status": "FAILED", "error_type": type(exc).__name__,
            "error": str(exc), "traceback": traceback.format_exc(limit=10),
            "runtime_seconds": round(time.monotonic() - tic, 3), "input_snapshot": snapshot,
            "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
        print(f"FAILED {type(exc).__name__}: {exc}", flush=True)
    if curves:
        pd.DataFrame(curves).to_csv(curve_path, index=False, compression="gzip")
    if selections:
        pd.DataFrame(selections).to_csv(selection_path, index=False, compression="gzip")
    if coverage_rows:
        pd.DataFrame(coverage_rows).to_csv(coverage_path, index=False)
    manifest["finished_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    manifest["attempt_events_sha256"] = sha256(ledger)
    manifest["attempt_events"] = sum(1 for _ in ledger.open(encoding="utf-8"))
    for key, path in (("curve_file", curve_path), ("selection_audit_file", selection_path),
                      ("coverage_audit_file", coverage_path)):
        manifest[key] = str(path) if path.exists() else None
        if path.exists():
            manifest[f"{key}_sha256"] = sha256(path)
    manifest["attempt_status"] = "FAILED" if failed else "COMPLETED_EXPLORATORY"
    manifest["status"] = "FINISHED_WITH_FAILED_ATTEMPT" if failed else "COMPLETED_EXPLORATORY"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
