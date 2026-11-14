"""Generation 10: one preregistered NR7 SPY exploratory test."""
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
FEE_PER_SIDE = 0.001
HOLDING_INTERVALS = 10
ANNUAL_SESSIONS = 252


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


def validate_raw_ohlc(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "adjclose"}
    if not isinstance(frame, pd.DataFrame) or not required.issubset(frame.columns):
        raise ValueError(f"OHLC frame must include {sorted(required)}")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("OHLC index must be a unique increasing DatetimeIndex")
    values = frame[["open", "high", "low", "close", "adjclose"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("OHLC/adjusted-close contains non-finite or non-positive values")
    open_, high, low, close, _ = values.T
    valid = (high >= np.maximum(open_, close)) & (low <= np.minimum(open_, close)) & (high >= low)
    if not valid.all():
        first_bad = frame.index[np.flatnonzero(~valid)[0]].date().isoformat()
        raise ValueError(f"raw OHLC relationship failure on {first_bad}")
    return frame.copy()


def adjusted_ohlc(frame: pd.DataFrame) -> pd.DataFrame:
    """Return adjusted O/H/L/C; used only by tests/data diagnostics, not the signal."""
    raw = validate_raw_ohlc(frame)
    factor = raw["adjclose"] / raw["close"]
    adjusted = raw[["open", "high", "low", "close"]].mul(factor, axis=0)
    if not np.isfinite(adjusted.to_numpy(dtype=float)).all() or (adjusted.to_numpy(dtype=float) <= 0).any():
        raise ValueError("adjusted OHLC is invalid")
    return adjusted


def build_signal(frame: pd.DataFrame) -> pd.Series:
    """At close t: prior range is tied-minimum over prior 7 bars and close breaks prior high."""
    raw = validate_raw_ohlc(frame)
    prior_ranges = raw["high"] - raw["low"]
    seven_bar_prior_min = prior_ranges.shift(1).rolling(window=7, min_periods=7).min()
    prior_range = prior_ranges.shift(1)
    signal = prior_range.eq(seven_bar_prior_min) & raw["close"].gt(raw["high"].shift(1))
    return signal.fillna(False).astype(bool)


def simulate(frame: pd.DataFrame, signal: pd.Series, fee: float = FEE_PER_SIDE) -> dict:
    """Close-t signal, next-open entry, exit after ten full open-to-open intervals."""
    raw = validate_raw_ohlc(frame)
    if not isinstance(signal, pd.Series) or not signal.index.equals(raw.index):
        raise ValueError("signal must be a Series aligned exactly to the OHLC index")
    if signal.isna().any() or not signal.isin([True, False]).all():
        raise ValueError("signal must contain only booleans")
    if not np.isfinite(fee) or fee < 0 or fee >= 1:
        raise ValueError("fee must be finite and in [0, 1)")
    if len(raw) <= HOLDING_INTERVALS + 2:
        raise ValueError("not enough rows for scheduled holding intervals")

    adjusted_open = raw["open"] * raw["adjclose"] / raw["close"]
    prices = adjusted_open.to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("adjusted-open series is invalid")
    n = len(raw)
    returns = np.zeros(n, dtype=float)
    turnover = np.zeros(n, dtype=float)
    exposure = np.zeros(n, dtype=float)
    entries: list[int] = []
    exits: list[int] = []
    overlap_suppressed = 0
    terminal_censored = 0
    last_exit = -1

    for signal_index in np.flatnonzero(signal.to_numpy(dtype=bool)):
        entry = int(signal_index + 1)
        exit_ = entry + HOLDING_INTERVALS
        if exit_ >= n:
            terminal_censored += 1
            continue
        if entry < last_exit:
            overlap_suppressed += 1
            continue
        entries.append(entry)
        exits.append(exit_)
        last_exit = exit_
        for interval_end in range(entry + 1, exit_ + 1):
            gross_factor = prices[interval_end] / prices[interval_end - 1]
            entry_factor = (1.0 - fee) if interval_end == entry + 1 else 1.0
            exit_factor = (1.0 - fee) if interval_end == exit_ else 1.0
            returns[interval_end] = gross_factor * entry_factor * exit_factor - 1.0
            exposure[interval_end] = 1.0
            turnover[interval_end] = float(interval_end == entry + 1) + float(interval_end == exit_)

    index = raw.index
    return {"returns": pd.Series(returns, index=index), "turnover": pd.Series(turnover, index=index),
            "exposure": pd.Series(exposure, index=index), "entry_indices": entries,
            "exit_indices": exits, "trades": len(entries),
            "overlap_suppressed": overlap_suppressed, "terminal_censored": terminal_censored}


def simulate_buy_hold(frame: pd.DataFrame, fee: float = FEE_PER_SIDE) -> dict:
    raw = validate_raw_ohlc(frame)
    adjusted_open = (raw["open"] * raw["adjclose"] / raw["close"]).to_numpy(dtype=float)
    if not np.isfinite(fee) or fee < 0 or fee >= 1:
        raise ValueError("fee must be finite and in [0, 1)")
    returns = np.zeros(len(raw), dtype=float)
    turnover = np.zeros(len(raw), dtype=float)
    exposure = np.zeros(len(raw), dtype=float)
    for interval_end in range(1, len(raw)):
        entry_factor = (1.0 - fee) if interval_end == 1 else 1.0
        exit_factor = (1.0 - fee) if interval_end == len(raw) - 1 else 1.0
        returns[interval_end] = adjusted_open[interval_end] / adjusted_open[interval_end - 1] * entry_factor * exit_factor - 1.0
        turnover[interval_end] = float(interval_end == 1) + float(interval_end == len(raw) - 1)
        exposure[interval_end] = 1.0
    return {"returns": pd.Series(returns, index=raw.index), "turnover": pd.Series(turnover, index=raw.index),
            "exposure": pd.Series(exposure, index=raw.index)}


def descriptive_metrics(returns: pd.Series, turnover: pd.Series, exposure: pd.Series,
                        start: str | None = None, end: str | None = None) -> dict:
    if not returns.index.equals(turnover.index) or not returns.index.equals(exposure.index):
        raise ValueError("metric series indexes must match")
    sample = returns.iloc[1:]
    if start or end:
        sample = sample.loc[start:end]
    if len(sample) < 100:
        return {"status": "INSUFFICIENT", "observations": int(len(sample))}
    values = sample.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= -1.0).any():
        raise ValueError("invalid return data for metric window")
    equity = (1.0 + sample).cumprod()
    years = len(sample) / ANNUAL_SESSIONS
    std = float(sample.std(ddof=1))
    highwater = equity.cummax()
    # Include initial capital in drawdown calculation.
    prior_peak = pd.Series(np.maximum.accumulate(np.r_[1.0, equity.to_numpy()])[1:], index=sample.index)
    drawdown = equity / prior_peak - 1.0
    return {"status": "OK", "start": sample.index[0].date().isoformat(),
            "end": sample.index[-1].date().isoformat(), "observations": int(len(sample)),
            "total_return": float(equity.iloc[-1] - 1.0),
            "cagr": float(equity.iloc[-1] ** (1.0 / years) - 1.0) if equity.iloc[-1] > 0 else -1.0,
            "sharpe": float(sample.mean() / std * np.sqrt(ANNUAL_SESSIONS)) if std > 0 else 0.0,
            "mdd": float(drawdown.min()),
            "annual_turnover": float(turnover.loc[sample.index].sum() / years),
            "mean_exposure": float(exposure.loc[sample.index].mean()),
            "exposure_sessions": int((exposure.loc[sample.index] > 0).sum())}


def load_spy() -> tuple[pd.DataFrame, dict]:
    path = DATA / "SPY.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = pd.read_parquet(path)
    raw.index = pd.to_datetime(raw.index).tz_localize(None).normalize()
    if raw.index.has_duplicates:
        raise ValueError("SPY parquet contains duplicate normalized session dates")
    raw = raw.sort_index()
    raw = validate_raw_ohlc(raw)
    raw = raw[["open", "high", "low", "close", "adjclose"]].copy()
    adjusted_ohlc(raw)
    info = {"rows": len(raw), "first_date": raw.index[0].date().isoformat(),
            "last_date": raw.index[-1].date().isoformat(), "sha256": sha256(path),
            "adjusted_open_rule": "raw open * adjclose / raw close",
            "signal_price_rule": "raw vendor OHLC; no corporate-action reconstruction performed"}
    return raw, info


def main() -> int:
    started = pd.Timestamp.now(tz="UTC")
    run_id = f"GEN10-{started.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ledger = HERE / f"attempts_{run_id}.jsonl"
    curves_path = HERE / f"equity_curves_{run_id}.csv.gz"
    manifest_path = HERE / f"manifest_{run_id}.json"
    manifest = {"run_id": run_id, "status": "RUNNING", "started_utc": started.isoformat(),
                "prereg_sha256": sha256(PREREG), "runner_sha256": sha256(Path(__file__)),
                "python": sys.version, "numpy": np.__version__, "pandas": pd.__version__,
                "fee_per_side": FEE_PER_SIDE, "holding_intervals": HOLDING_INTERVALS,
                "planned_attempts": 1,
                "evidence_status": "EXPLORATORY_ONLY_PRIOR_HISTORY_INSPECTED_FAMILY_OVERLAP_AND_GLOBAL_TRIAL_COUNT_UNRESOLVED"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    attempt_id = f"{run_id}-US-SPY_NR7_CLOSE_BREAK_H10"
    append_event(ledger, {"event": "attempt_start", "attempt_id": attempt_id,
                         "candidate": "US_SPY_NR7_PRIOR_RANGE_BREAK_H10", "status": "STARTED",
                         "prereg_sha256": manifest["prereg_sha256"], "runner_sha256": manifest["runner_sha256"]})
    try:
        frame, data_info = load_spy()
        signal = build_signal(frame)
        strategy = simulate(frame, signal)
        benchmark = simulate_buy_hold(frame)
        windows = {"full": (None, None), "is_2001_2016": ("2001-01-01", "2016-12-31"),
                   "later_inspected_2017_plus": ("2017-01-01", None)}
        metrics = {}
        for name, (start, end) in windows.items():
            metrics[name] = {
                "strategy": descriptive_metrics(strategy["returns"], strategy["turnover"], strategy["exposure"], start, end),
                "benchmark": descriptive_metrics(benchmark["returns"], benchmark["turnover"], benchmark["exposure"], start, end)}
        if any(row[side].get("status") != "OK" for row in metrics.values() for side in ("strategy", "benchmark")):
            raise ValueError("one or more fixed metric windows were insufficient")
        curves = pd.DataFrame({"date": frame.index.date.astype(str), "signal_at_close": signal.to_numpy(dtype=bool),
                               "strategy_return_net": strategy["returns"].to_numpy(),
                               "benchmark_return_net": benchmark["returns"].to_numpy(),
                               "strategy_exposure": strategy["exposure"].to_numpy(),
                               "strategy_turnover": strategy["turnover"].to_numpy()})
        curves.to_csv(curves_path, index=False, compression="gzip")
        summary = {"metrics": metrics, "signals": int(signal.sum()), "trades": strategy["trades"],
                   "overlap_suppressed": strategy["overlap_suppressed"],
                   "terminal_censored": strategy["terminal_censored"],
                   "first_trade_entry": frame.index[strategy["entry_indices"][0]].date().isoformat() if strategy["trades"] else None,
                   "last_trade_exit": frame.index[strategy["exit_indices"][-1]].date().isoformat() if strategy["trades"] else None}
        beats = all(metrics[key]["strategy"]["cagr"] > metrics[key]["benchmark"]["cagr"] and
                    metrics[key]["strategy"]["sharpe"] > metrics[key]["benchmark"]["sharpe"] for key in windows)
        summary["decision"] = "LEAD_ONLY_REQUIRES_INDEPENDENT_VALIDATION" if beats else "REJECT_FIXED_RULE_FOR_OBJECTIVE"
        manifest.update({"data": data_info, "session_count": len(frame), "result": summary,
                         "attempt_status": "COMPLETED_EXPLORATORY",
                         "curve_sha256": sha256(curves_path), "finished_utc": pd.Timestamp.now(tz="UTC").isoformat()})
        append_event(ledger, {"event": "attempt_finish", "attempt_id": attempt_id,
                              "candidate": "US_SPY_NR7_PRIOR_RANGE_BREAK_H10",
                              "status": "COMPLETED_EXPLORATORY", "data": data_info, "result": summary,
                              "nonconfirmatory_reason": manifest["evidence_status"]})
        print(json.dumps({"run_id": run_id, "status": manifest["attempt_status"], "result": summary},
                         ensure_ascii=False, indent=2))
        code = 0
    except Exception as exc:
        manifest.update({"attempt_status": "FAILED", "error_type": type(exc).__name__, "error": str(exc),
                         "traceback": traceback.format_exc(limit=10), "finished_utc": pd.Timestamp.now(tz="UTC").isoformat()})
        append_event(ledger, {"event": "attempt_fail", "attempt_id": attempt_id,
                              "candidate": "US_SPY_NR7_PRIOR_RANGE_BREAK_H10", "status": "FAILED",
                              "error_type": type(exc).__name__, "error": str(exc),
                              "traceback": traceback.format_exc(limit=10)})
        print(f"{run_id}: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        code = 1
    manifest["ledger_sha256"] = sha256(ledger)
    manifest["ledger_events"] = sum(1 for _ in ledger.open(encoding="utf-8"))
    manifest["ledger_path"] = str(ledger)
    manifest["curve_path"] = str(curves_path) if curves_path.exists() else None
    manifest["run_lifecycle_status"] = "FINISHED"
    manifest["status"] = manifest.get("attempt_status", "FAILED")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
