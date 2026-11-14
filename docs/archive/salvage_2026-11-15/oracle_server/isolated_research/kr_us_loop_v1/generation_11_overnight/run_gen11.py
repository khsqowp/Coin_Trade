"""Generation 11: one fixed SPY overnight-only exposure comparison."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data_mirror" / "us_daily" / "SPY.parquet"
META = HERE.parent / "data_mirror" / "us_daily" / "SPY.meta.json"
EVENTS = HERE.parent / "data_mirror" / "us_daily" / "SPY.events.json"
PREREG = HERE / "PREREG.md"
FEE_PER_SIDE = 0.0002
ANNUAL_SESSIONS = 252


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def append_event(path: Path, event: dict) -> None:
    row = {"ts_utc": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_market_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "adjclose"}
    if not isinstance(frame, pd.DataFrame) or not required.issubset(frame.columns):
        raise ValueError(f"market frame must include {sorted(required)}")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("date index must be unique and increasing")
    if len(frame) < 2:
        raise ValueError("at least two observed sessions are required")
    values = frame[["open", "high", "low", "close", "adjclose"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("OHLC and adjusted close must be finite and positive")
    op, hi, lo, cl, _ = values.T
    if not ((hi >= np.maximum(op, cl)) & (lo <= np.minimum(op, cl)) & (hi >= lo)).all():
        raise ValueError("OHLC bounds are invalid")
    return frame.copy()


def adjusted_prices(frame: pd.DataFrame) -> pd.DataFrame:
    raw = validate_market_frame(frame)
    factor = raw["adjclose"] / raw["close"]
    adjusted = pd.DataFrame({"open": raw["open"] * factor, "close": raw["adjclose"]}, index=raw.index)
    values = adjusted.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("adjusted open/close must be finite and positive")
    return adjusted


def simulate_overnight(frame: pd.DataFrame, fee_per_side: float = FEE_PER_SIDE) -> dict:
    """Compound close[t-1]->open[t] returns, with two actual boundary costs per night."""
    raw = validate_market_frame(frame)
    if not np.isfinite(fee_per_side) or fee_per_side < 0 or fee_per_side >= 1:
        raise ValueError("fee must be finite and in [0, 1)")
    prices = adjusted_prices(raw)
    op = prices["open"].to_numpy(dtype=float)
    cl = prices["close"].to_numpy(dtype=float)
    n = len(raw)
    strategy = np.zeros(n, dtype=float)
    benchmark = np.zeros(n, dtype=float)
    overnight_gross = np.zeros(n, dtype=float)
    strategy_cost_sides = np.zeros(n, dtype=int)
    benchmark_cost_sides = np.zeros(n, dtype=int)

    for i in range(1, n):
        overnight_gross[i] = op[i] / cl[i - 1] - 1.0
        # Every observed overnight is a complete round trip: MOC buy then next MOO sell.
        strategy[i] = (op[i] / cl[i - 1]) * (1.0 - fee_per_side) ** 2 - 1.0
        strategy_cost_sides[i] = 2

        # Matched benchmark starts at close[0] and ends at open[-1].
        benchmark_factor = (cl[i] / cl[i - 1]) if i < n - 1 else (op[i] / cl[i - 1])
        cost_factor = 1.0
        if i == 1:  # initial buy at close[0]
            cost_factor *= 1.0 - fee_per_side
            benchmark_cost_sides[i] += 1
        if i == n - 1:  # final sale at open[-1], same endpoint as strategy
            cost_factor *= 1.0 - fee_per_side
            benchmark_cost_sides[i] += 1
        benchmark[i] = benchmark_factor * cost_factor - 1.0

    idx = raw.index
    return {
        "strategy_returns": pd.Series(strategy, index=idx),
        "benchmark_returns": pd.Series(benchmark, index=idx),
        "overnight_gross_returns": pd.Series(overnight_gross, index=idx),
        "strategy_cost_sides": pd.Series(strategy_cost_sides, index=idx),
        "benchmark_cost_sides": pd.Series(benchmark_cost_sides, index=idx),
        "overnight_intervals": n - 1,
    }


def metrics(returns: pd.Series, start: str | None = None, end: str | None = None) -> dict:
    sample = returns.iloc[1:]
    if start is not None:
        sample = sample.loc[start:]
    if end is not None:
        sample = sample.loc[:end]
    values = sample.to_numpy(dtype=float)
    if len(values) < 100 or not np.isfinite(values).all() or (values <= -1).any():
        return {"status": "INSUFFICIENT_OR_INVALID", "observations": int(len(values))}
    equity = np.cumprod(1.0 + values)
    years = len(values) / ANNUAL_SESSIONS
    std = float(sample.std(ddof=1))
    peaks = np.maximum.accumulate(np.r_[1.0, equity])[1:]
    return {
        "status": "OK", "start": sample.index[0].date().isoformat(), "end": sample.index[-1].date().isoformat(),
        "observations": int(len(values)), "total_return": float(equity[-1] - 1.0),
        "cagr": float(equity[-1] ** (1.0 / years) - 1.0) if equity[-1] > 0 else -1.0,
        "sharpe": float(sample.mean() / std * np.sqrt(ANNUAL_SESSIONS)) if std > 0 else 0.0,
        "mdd": float(np.min(equity / peaks - 1.0)),
        "mean_exposure_per_overnight_interval": 1.0,
    }


def run() -> None:
    run_id = datetime.now(timezone.utc).strftime("GEN11-%Y%m%dT%H%M%S")
    ledger = HERE / f"attempts_{run_id}.jsonl"
    manifest = HERE / f"manifest_{run_id}.json"
    curves = HERE / f"equity_curves_{run_id}.csv.gz"
    append_event(ledger, {"event": "setup_start", "run_id": run_id, "candidate": "SPY_OVERNIGHT_ONLY_MOC_MOO"})
    try:
        prereg_hash = sha256(PREREG)
        freeze = json.loads((HERE / "FREEZE.json").read_text(encoding="utf-8"))
        if freeze.get("prereg_sha256") != prereg_hash:
            raise ValueError("preregistration hash differs from frozen hash")
        if not DATA.is_file() or not META.is_file() or not EVENTS.is_file():
            raise ValueError("SPY parquet, vendor metadata, or corporate-action event file missing")
        append_event(ledger, {"event": "data_load_start", "run_id": run_id, "candidate": "SPY_OVERNIGHT_ONLY_MOC_MOO"})
        meta = json.loads(META.read_text(encoding="utf-8"))
        event_payload = json.loads(EVENTS.read_text(encoding="utf-8"))
        frame = pd.read_parquet(DATA)
        frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
        frame = validate_market_frame(frame)
        # Event presence is a diagnostic only; adjusted-price convention is not reconstructed from it.
        event_summary = {"top_level_type": type(event_payload).__name__,
                         "top_level_keys": sorted(event_payload.keys()) if isinstance(event_payload, dict) else None}
        data_hashes = {"parquet": sha256(DATA), "vendor_meta": sha256(META), "events": sha256(EVENTS)}
        append_event(ledger, {"event": "integrity_gate_pass", "run_id": run_id, "rows": len(frame),
                              "first_date": frame.index[0].date().isoformat(), "last_date": frame.index[-1].date().isoformat(),
                              "data_hashes": data_hashes, "vendor": meta.get("source"), "events_diagnostic": event_summary})
        result = simulate_overnight(frame)
        r_strategy, r_benchmark = result["strategy_returns"], result["benchmark_returns"]
        windows = {
            "full": (None, None),
            "2001_2016": ("2001-01-01", "2016-12-31"),
            "2017_plus_previously_inspected": ("2017-01-01", None),
        }
        scored = {}
        for name, (start, end) in windows.items():
            scored[name] = {"strategy": metrics(r_strategy, start, end), "benchmark": metrics(r_benchmark, start, end)}
        passed = all(v["strategy"]["status"] == "OK" and v["benchmark"]["status"] == "OK"
                     and v["strategy"]["cagr"] > v["benchmark"]["cagr"]
                     and v["strategy"]["sharpe"] > v["benchmark"]["sharpe"] for v in scored.values())
        decision = "DESCRIPTIVE_LEAD_ONLY" if passed else "REJECT_FIXED_RULE"
        curve = pd.DataFrame({
            "date": frame.index,
            "overnight_gross_return": result["overnight_gross_returns"],
            "overnight_net_return": r_strategy,
            "benchmark_matched_endpoint_net_return": r_benchmark,
            "strategy_cost_sides": result["strategy_cost_sides"],
            "benchmark_cost_sides": result["benchmark_cost_sides"],
            "strategy_equity": (1.0 + r_strategy).cumprod(),
            "benchmark_equity": (1.0 + r_benchmark).cumprod(),
        })
        curve.to_csv(curves, index=False, compression="gzip")
        append_event(ledger, {"event": "attempt_finish", "run_id": run_id, "candidate": "SPY_OVERNIGHT_ONLY_MOC_MOO",
                              "status": decision, "metrics": scored, "overnight_intervals": result["overnight_intervals"]})
        payload = {
            "run_id": run_id, "candidate": "SPY_OVERNIGHT_ONLY_MOC_MOO", "decision": decision,
            "prereg_sha256": prereg_hash, "runner_sha256": sha256(Path(__file__)),
            "data_hashes": data_hashes, "vendor_metadata": meta, "events_diagnostic": event_summary,
            "rows": len(frame), "first_date": frame.index[0].date().isoformat(), "last_date": frame.index[-1].date().isoformat(),
            "fee_per_side": FEE_PER_SIDE, "metrics": scored, "curve_path": str(curves),
            "curve_sha256": sha256(curves), "ledger_path": str(ledger), "python": sys.version,
            "numpy": np.__version__, "pandas": pd.__version__,
            "limitations": ["unofficial vendor history", "corporate-action adjustment not independently verified",
                            "auction fills/slippage not observable in daily bars", "calendar not independently verified",
                            "all historical SPY results previously inspected", "no untouched OOS or full global trial count"],
        }
        manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"run_id": run_id, "decision": decision, "metrics": scored}, indent=2))
    except Exception as exc:
        append_event(ledger, {"event": "attempt_finish", "run_id": run_id, "candidate": "SPY_OVERNIGHT_ONLY_MOC_MOO",
                              "status": "FAILED", "error": str(exc), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    run()
