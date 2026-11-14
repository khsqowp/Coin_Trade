"""Generation 09: one fixed US early-month exposure experiment."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data_mirror" / "us_daily"
PREREG = HERE / "PREREG.md"
ANNUAL_SESSIONS = 252
FEE_PER_SIDE = 0.001


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def append_event(path: Path, event: dict) -> None:
    row = {"ts_utc": pd.Timestamp.now(tz="UTC").isoformat(), **event}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def first_three_session_mask(index: pd.DatetimeIndex) -> np.ndarray:
    """Mark first three observed sessions, excluding partial file-boundary months."""
    if not isinstance(index, pd.DatetimeIndex) or index.has_duplicates or not index.is_monotonic_increasing:
        raise ValueError("session index must be a unique, increasing DatetimeIndex")
    if len(index) < 3:
        raise ValueError("too few sessions for a calendar-window experiment")
    period = index.to_period("M")
    first_period, last_period = period[0], period[-1]
    ordinal = pd.Series(np.arange(len(index)), index=index).groupby(period, sort=False).cumcount().to_numpy()
    complete_in_sample_month = (period > first_period) & (period < last_period)
    return (ordinal < 3) & complete_in_sample_month


def simulate_open_to_open(adjusted_open: pd.Series, target: np.ndarray,
                          fee: float = FEE_PER_SIDE) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Apply open-time binary exposure changes, costs, and open-to-open returns."""
    if not isinstance(adjusted_open, pd.Series) or not isinstance(adjusted_open.index, pd.DatetimeIndex):
        raise ValueError("adjusted open must be a dated Series")
    if adjusted_open.index.has_duplicates or not adjusted_open.index.is_monotonic_increasing:
        raise ValueError("adjusted-open index must be unique and increasing")
    prices = adjusted_open.to_numpy(dtype=float)
    target = np.asarray(target, dtype=float)
    if len(prices) != len(target) or len(prices) < 3:
        raise ValueError("adjusted-open and target lengths must match and contain at least 3 rows")
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("invalid adjusted open")
    if not np.isfinite(target).all() or not np.isin(target, [0.0, 1.0]).all():
        raise ValueError("target must contain only finite 0/1 exposures")
    if not np.isfinite(fee) or fee < 0 or fee >= 1:
        raise ValueError("fee must be finite and in [0, 1)")

    returns = np.zeros(len(prices), dtype=float)
    turnover = np.zeros(len(prices), dtype=float)
    exposure = np.zeros(len(prices), dtype=float)
    prior_exposure = 0.0
    for i in range(1, len(prices)):
        active = target[i - 1]
        traded = abs(active - prior_exposure)
        gross_return = prices[i] / prices[i - 1] - 1.0
        returns[i] = (1.0 + gross_return) * (1.0 - fee * traded) - 1.0
        turnover[i] = traded
        exposure[i] = active
        prior_exposure = active

    # Liquidate the exposure earned through the final open; target[-1] has no following interval.
    if target[-2] == 1.0:
        returns[-1] = (1.0 + returns[-1]) * (1.0 - fee) - 1.0
        turnover[-1] += 1.0
    idx = adjusted_open.index
    return (pd.Series(returns, index=idx), pd.Series(turnover, index=idx),
            pd.Series(exposure, index=idx))


def summarize(returns: pd.Series, turnover: pd.Series, exposure: pd.Series,
              start: str | None = None, end: str | None = None) -> dict:
    # The intentional zero is only the global first row; later report windows must retain
    # their first actual in-window return, transaction, and exposure observation.
    usable = returns.iloc[1:]
    sample = usable.loc[start:end] if start or end else usable
    if len(sample) < 100:
        return {"status": "INSUFFICIENT", "observations": int(len(sample))}
    if not np.isfinite(sample.to_numpy()).all() or (sample <= -1.0).any():
        raise ValueError("invalid return series in metric window")
    equity = (1.0 + sample).cumprod()
    years = len(sample) / ANNUAL_SESSIONS
    std = float(sample.std(ddof=1))
    high_water = pd.concat([pd.Series([1.0], index=[sample.index[0] - pd.Timedelta(days=1)]), equity])
    drawdown = high_water / high_water.cummax() - 1.0
    return {
        "status": "OK",
        "start": sample.index[0].date().isoformat(),
        "end": sample.index[-1].date().isoformat(),
        "observations": int(len(sample)),
        "total_return": float(equity.iloc[-1] - 1.0),
        "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0) if equity.iloc[-1] > 0 else -1.0,
        "sharpe": float(sample.mean() / std * np.sqrt(ANNUAL_SESSIONS)) if std > 0 else 0.0,
        "mdd": float(drawdown.min()),
        "annual_turnover": float(turnover.loc[sample.index].sum() / years),
        "mean_exposure": float(exposure.loc[sample.index].mean()),
        "exposure_sessions": int((exposure.loc[sample.index] > 0).sum()),
    }


def load_spy() -> tuple[pd.DatetimeIndex, pd.Series, dict]:
    path = DATA / "SPY.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = pd.read_parquet(path)
    required = {"open", "high", "low", "close", "adjclose"}
    if not required.issubset(raw.columns):
        raise ValueError(f"SPY parquet missing required columns: {sorted(required - set(raw.columns))}")
    raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
    if raw.index.has_duplicates:
        raise ValueError("SPY parquet contains duplicate normalized session dates")
    raw = raw.sort_index()
    values = raw[["open", "high", "low", "close", "adjclose"]].to_numpy(dtype=float)
    valid = np.isfinite(values).all(axis=1) & (values > 0).all(axis=1)
    valid &= values[:, 1] >= np.maximum(values[:, 0], values[:, 3])
    valid &= values[:, 2] <= np.minimum(values[:, 0], values[:, 3])
    valid &= values[:, 1] >= values[:, 2]
    if not valid.all():
        bad = raw.index[np.flatnonzero(~valid)[0]].date().isoformat()
        raise ValueError(f"SPY OHLC/adjusted-close integrity failure on {bad}")
    factor = raw["adjclose"] / raw["close"]
    adjusted_open = raw["open"] * factor
    if not np.isfinite(adjusted_open.to_numpy()).all() or (adjusted_open <= 0).any():
        raise ValueError("SPY adjusted-open series is invalid")
    info = {"rows": len(raw), "first_date": raw.index[0].date().isoformat(),
            "last_date": raw.index[-1].date().isoformat(), "sha256": sha256(path),
            "adjusted_open_rule": "open * adjclose / close"}
    return pd.DatetimeIndex(raw.index), adjusted_open.astype(float), info


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN09-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger = HERE / f"attempts_{run_id}.jsonl"
    curves_path = HERE / f"equity_curves_{run_id}.csv.gz"
    manifest_path = HERE / f"manifest_{run_id}.json"
    manifest = {"run_id": run_id, "status": "RUNNING", "started_utc": started.isoformat(),
                "prereg_sha256": sha256(PREREG), "runner_sha256": sha256(Path(__file__)),
                "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
                "fee_per_side": FEE_PER_SIDE, "planned_attempts": 1,
                "evidence_status": "EXPLORATORY_ONLY_PREVIOUSLY_INSPECTED_HISTORY_AND_UNRESOLVED_GLOBAL_TRIALS"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attempt_id = f"{run_id}-US-SPY_FIRST3_CALENDAR"
    append_event(ledger, {"event": "attempt_start", "attempt_id": attempt_id,
                          "candidate": "US_SPY_FIRST_THREE_SESSIONS_MONTHLY", "status": "STARTED",
                          "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
    try:
        index, adjusted_open, data_info = load_spy()
        target = first_three_session_mask(index).astype(float)
        strategy_returns, strategy_turnover, strategy_exposure = simulate_open_to_open(adjusted_open, target)
        benchmark_target = np.ones(len(index), dtype=float)
        benchmark_returns, benchmark_turnover, benchmark_exposure = simulate_open_to_open(adjusted_open, benchmark_target)
        periods = {"full": (None, None), "is_2001_2016": ("2001-01-01", "2016-12-31"),
                   "later_inspected_2017_plus": ("2017-01-01", None)}
        result = {}
        for name, (start, end) in periods.items():
            result[name] = {"strategy": summarize(strategy_returns, strategy_turnover, strategy_exposure, start, end),
                            "benchmark": summarize(benchmark_returns, benchmark_turnover, benchmark_exposure, start, end)}
        if any(v["strategy"].get("status") != "OK" or v["benchmark"].get("status") != "OK" for v in result.values()):
            raise ValueError("one or more fixed metric windows were insufficient")
        if not np.isfinite(strategy_returns.to_numpy()).all() or not np.isfinite(benchmark_returns.to_numpy()).all():
            raise ValueError("non-finite returns produced")
        curves = pd.DataFrame({"date": index.date.astype(str),
                               "strategy_return_net": strategy_returns.to_numpy(),
                               "benchmark_return_net": benchmark_returns.to_numpy(),
                               "target_at_open": target,
                               "strategy_turnover": strategy_turnover.to_numpy(),
                               "strategy_exposure": strategy_exposure.to_numpy()})
        curves.to_csv(curves_path, index=False, compression="gzip")
        manifest.update({"data": data_info, "session_count": len(index),
                         "first_three_month_sessions": int(target.sum()),
                         "result": result, "attempt_status": "COMPLETED_EXPLORATORY",
                         "curve_sha256": sha256(curves_path), "finished_utc": pd.Timestamp.now(tz="UTC").isoformat()})
        append_event(ledger, {"event": "attempt_finish", "attempt_id": attempt_id,
                              "candidate": "US_SPY_FIRST_THREE_SESSIONS_MONTHLY",
                              "status": "COMPLETED_EXPLORATORY", "data": data_info,
                              "result": result,
                              "nonconfirmatory_reason": "historical_partitions_already_inspected_and_global_trial_count_unresolved"})
        print(json.dumps({"run_id": run_id, "status": manifest["attempt_status"], "result": result},
                         ensure_ascii=False, indent=2))
        return_code = 0
    except Exception as exc:
        manifest.update({"attempt_status": "FAILED", "error_type": type(exc).__name__, "error": str(exc),
                         "traceback": traceback.format_exc(limit=10),
                         "finished_utc": pd.Timestamp.now(tz="UTC").isoformat()})
        append_event(ledger, {"event": "attempt_fail", "attempt_id": attempt_id,
                              "candidate": "US_SPY_FIRST_THREE_SESSIONS_MONTHLY", "status": "FAILED",
                              "error_type": type(exc).__name__, "error": str(exc),
                              "traceback": traceback.format_exc(limit=10)})
        print(f"{run_id}: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        return_code = 1
    manifest["ledger_sha256"] = sha256(ledger)
    manifest["ledger_events"] = sum(1 for _ in ledger.open(encoding="utf-8"))
    manifest["ledger_path"] = str(ledger)
    manifest["curve_path"] = str(curves_path) if curves_path.exists() else None
    manifest["run_lifecycle_status"] = "FINISHED"
    manifest["status"] = manifest.get("attempt_status", "FAILED")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
