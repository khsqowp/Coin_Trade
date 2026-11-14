"""Single fixed exploratory transfer of the source volatility-breakout signal."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DATA = ROOT / "trading/docs/research/kr_us_loop_v1/data_mirror/us_daily/SPY.parquet"
PREREG = HERE / "PREREG.md"
RUN_ID = "GEN11A1-20261106-SPY_VOL_BURST_MOM5_H5"
FEE = 0.001
HOLD = 5
FREEZE = HERE / "FREEZE_A1.json"
ATTEMPTS = HERE / f"attempts_{RUN_ID}.jsonl"
MANIFEST = HERE / f"manifest_{RUN_ID}.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_adjusted_ordering(adj: pd.DataFrame) -> None:
    required_high = adj[["open", "close", "low"]].max(axis=1).to_numpy()
    high = adj["high"].to_numpy()
    high_tol = 1e-12 * np.maximum.reduce([np.ones(len(adj)), np.abs(high), np.abs(required_high)])
    if (high + high_tol < required_high).any():
        raise ValueError("invalid adjusted high/low ordering")
    required_low = adj[["open", "close", "high"]].min(axis=1).to_numpy()
    low = adj["low"].to_numpy()
    low_tol = 1e-12 * np.maximum.reduce([np.ones(len(adj)), np.abs(low), np.abs(required_low)])
    if (low - low_tol > required_low).any():
        raise ValueError("invalid adjusted low/high ordering")


def build_signal(raw: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    needed = {"open", "high", "low", "close", "adjclose"}
    if not needed.issubset(raw.columns):
        raise ValueError(f"missing required columns: {sorted(needed - set(raw.columns))}")
    if raw.empty or raw.index.has_duplicates or not raw.index.is_monotonic_increasing:
        raise ValueError("dates must be nonempty, unique, and strictly increasing")
    values = raw[["open", "high", "low", "close", "adjclose"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("all raw OHLC and adjusted close values must be finite and positive")
    if (raw["high"] < raw[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid raw high/low ordering")
    if (raw["low"] > raw[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("invalid raw low/high ordering")

    factor = raw["adjclose"] / raw["close"]
    adj = pd.DataFrame(index=raw.index)
    for col in ("open", "high", "low", "close"):
        adj[col] = raw[col] * factor
    if not np.isfinite(adj.to_numpy()).all() or (adj <= 0).any().any():
        raise ValueError("adjusted OHLC must be finite and positive")
    _validate_adjusted_ordering(adj)

    prev_close = adj["close"].shift(1)
    tr = pd.concat([
        adj["high"] - adj["low"],
        (adj["high"] - prev_close).abs(),
        (adj["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr20 = tr.rolling(20, min_periods=20).mean()
    vol = atr20 / adj["close"]
    threshold = vol.shift(1).rolling(100, min_periods=100).quantile(0.8, interpolation="linear")
    momentum = adj["close"].pct_change(5)
    signal = (vol > threshold) & (momentum > 0)
    signal = signal.fillna(False).astype(bool)
    features = pd.DataFrame({"atr20_over_close": vol, "threshold": threshold, "momentum": momentum}, index=raw.index)
    return signal, features


def simulate(raw: pd.DataFrame, signal: pd.Series, hold_intervals: int, cost: float) -> dict:
    if hold_intervals < 1 or not 0 <= cost < 1:
        raise ValueError("hold must be positive and cost must be in [0, 1)")
    if not signal.index.equals(raw.index):
        raise ValueError("signal index must exactly match the price index")
    factor = raw["adjclose"] / raw["close"]
    adj_open = raw["open"] * factor
    if not np.isfinite(adj_open.to_numpy()).all() or (adj_open <= 0).any():
        raise ValueError("adjusted open must be finite and positive")
    returns = pd.Series(0.0, index=raw.index[1:], name="strategy_return")
    exposure = pd.Series(False, index=raw.index[1:], name="exposure")
    trades = suppressed = censored = 0
    next_decision = 0
    for t in np.flatnonzero(signal.to_numpy(dtype=bool)):
        if t < next_decision:
            suppressed += 1
            continue
        entry = t + 1
        exit_ = entry + hold_intervals
        if exit_ >= len(raw):
            censored += 1
            continue
        for interval_end in range(entry + 1, exit_ + 1):
            value = adj_open.iloc[interval_end] / adj_open.iloc[interval_end - 1]
            if interval_end == entry + 1:
                value *= 1 - cost
            if interval_end == exit_:
                value *= 1 - cost
            returns.iloc[interval_end - 1] = value - 1
            exposure.iloc[interval_end - 1] = True
        trades += 1
        next_decision = exit_

    benchmark = adj_open.iloc[1:].to_numpy() / adj_open.iloc[:-1].to_numpy() - 1
    if len(benchmark):
        benchmark[0] = (1 + benchmark[0]) * (1 - cost) - 1
        benchmark[-1] = (1 + benchmark[-1]) * (1 - cost) - 1
    benchmark = pd.Series(benchmark, index=returns.index, name="benchmark_return")
    if not np.isfinite(returns.to_numpy()).all() or not np.isfinite(benchmark.to_numpy()).all():
        raise ValueError("nonfinite simulated return")
    return {"strategy_returns": returns, "benchmark_returns": benchmark, "exposure": exposure, "trades": trades,
            "suppressed": suppressed, "censored": censored}


def metrics(returns: pd.Series) -> dict:
    x = returns.to_numpy(dtype=float)
    if len(x) == 0 or not np.isfinite(x).all() or (x <= -1).any():
        raise ValueError("invalid metric return vector")
    wealth = np.cumprod(1 + x)
    years = len(x) / 252
    cagr = float(wealth[-1] ** (1 / years) - 1) if years > 0 else 0.0
    sd = float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
    sharpe = float(np.mean(x) / sd * math.sqrt(252)) if sd > 0 else 0.0
    peaks = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
    mdd = float(np.min(wealth / peaks - 1)) if len(wealth) else 0.0
    return {"observations": int(len(x)), "cagr": cagr, "sharpe": sharpe, "max_drawdown": mdd,
            "total_return": float(wealth[-1] - 1)}


def main() -> None:
    start = {"run_id": RUN_ID, "status": "STARTED", "prereg_sha256": sha256(PREREG),
             "addendum_sha256": sha256(HERE / "ADDENDUM_A1.md"),
             "runner_sha256": sha256(Path(__file__)), "test_sha256": sha256(HERE / "test_gen11.py")}
    ATTEMPTS.write_text(json.dumps(start) + "\n")
    MANIFEST.write_text(json.dumps(start, indent=2) + "\n")
    try:
        if not FREEZE.exists():
            raise RuntimeError("missing immutable FREEZE.json; performance run not authorized")
        frozen = json.loads(FREEZE.read_text())
        for key, path in (("prereg_sha256", PREREG), ("addendum_sha256", HERE / "ADDENDUM_A1.md"),
                          ("runner_sha256", Path(__file__)),
                          ("test_sha256", HERE / "test_gen11.py"), ("data_sha256", DATA)):
            actual = sha256(path)
            if frozen.get(key) != actual:
                raise RuntimeError(f"freeze hash mismatch for {key}")
        raw = pd.read_parquet(DATA)
        signal, _ = build_signal(raw)
        run = simulate(raw, signal, HOLD, FEE)
        rows = pd.DataFrame({"strategy_return": run["strategy_returns"],
                             "benchmark_return": run["benchmark_returns"]})
        windows = {
            "full": (rows.index.min(), rows.index.max()),
            "2001_2016": (pd.Timestamp("2001-01-02"), pd.Timestamp("2016-12-30")),
            "2017_plus_contaminated": (pd.Timestamp("2017-01-03"), rows.index.max()),
        }
        report = {}
        for name, (window_start, window_end) in windows.items():
            subset = rows.loc[window_start:window_end]
            report[name] = {"start": str(subset.index.min().date()), "end": str(subset.index.max().date()),
                            "strategy": metrics(subset.strategy_return),
                            "benchmark": metrics(subset.benchmark_return),
                            "drawdown_scope": "recomputed from a fresh within-window baseline"}
        report["activity"] = {"signals": int(signal.sum()), "trades": run["trades"],
                               "suppressed": run["suppressed"], "censored": run["censored"],
                               "exposure_fraction": float(run["exposure"].mean())}
        report["provenance"] = {"run_id": RUN_ID, "prereg_sha256": sha256(PREREG),
                                "addendum_sha256": sha256(HERE / "ADDENDUM_A1.md"),
                                "runner_sha256": sha256(Path(__file__)), "test_sha256": sha256(HERE / "test_gen11.py"),
                                "data_sha256": sha256(DATA), "row_count": len(raw),
                                "first_date": str(raw.index.min().date()), "last_date": str(raw.index.max().date())}
        (HERE / f"results_{RUN_ID}.json").write_text(json.dumps(report, indent=2) + "\n")
        curve = rows.copy()
        curve["equity_strategy"] = (1 + curve.strategy_return).cumprod()
        curve["equity_benchmark"] = (1 + curve.benchmark_return).cumprod()
        curve["exposure"] = run["exposure"]
        curve.to_csv(HERE / f"curve_{RUN_ID}.csv.gz", compression="gzip", index_label="date")
        finish = {"run_id": RUN_ID, "status": "COMPLETED_EXPLORATORY", **report}
        with ATTEMPTS.open("a") as stream:
            stream.write(json.dumps(finish, default=str) + "\n")
        MANIFEST.write_text(json.dumps({**report["provenance"], "status": "COMPLETED_EXPLORATORY"}, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    except Exception as exc:
        failure = {"run_id": RUN_ID, "status": "FAILED", "reason": f"{type(exc).__name__}: {exc}"}
        with ATTEMPTS.open("a") as stream:
            stream.write(json.dumps(failure) + "\n")
        MANIFEST.write_text(json.dumps(failure, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
