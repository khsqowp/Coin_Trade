"""One frozen, exploratory monthly short-term reversal test on US sector ETFs."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data_mirror" / "us_daily"
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
BENCHMARK = "SPY"
COST_RATE = 0.001
SLOTS = 3


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_ohlc_frame(frame: pd.DataFrame, ticker: str) -> None:
    required = ("open", "high", "low", "close", "adjclose")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{ticker}: missing columns {missing}")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates:
        raise ValueError(f"{ticker}: index must be a unique DatetimeIndex")
    if not frame.index.is_monotonic_increasing:
        raise ValueError(f"{ticker}: index must be ascending")
    values = frame.loc[:, required].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(f"{ticker}: OHLC and adjclose must all be finite and positive")
    open_, high, low, close, adjclose = values.T
    if (high < np.maximum(open_, close)).any() or (low > np.minimum(open_, close)).any():
        raise ValueError(f"{ticker}: invalid OHLC high/low bounds")
    adjusted_factor = adjclose / close
    adjusted_open = open_ * adjusted_factor
    if not np.isfinite(adjusted_open).all() or (adjusted_open <= 0).any():
        raise ValueError(f"{ticker}: adjusted open must be finite and positive")


def rank_bottom(month_returns: Mapping[str, float], slots: int = SLOTS) -> dict[str, float]:
    if not month_returns or slots < 1 or slots > len(month_returns):
        raise ValueError("slots must be between 1 and the number of available returns")
    if any(not math.isfinite(float(value)) for value in month_returns.values()):
        raise ValueError("monthly returns must all be finite")
    selected = sorted(month_returns, key=lambda ticker: (float(month_returns[ticker]), ticker))[:slots]
    return {ticker: 1.0 / slots for ticker in selected}


def build_monthly_targets(
    adjusted_close: pd.DataFrame, slots: int = SLOTS
) -> tuple[dict[pd.Timestamp, dict[str, float]], dict[str, int]]:
    if adjusted_close.empty or adjusted_close.index.has_duplicates or not adjusted_close.index.is_monotonic_increasing:
        raise ValueError("adjusted close panel must have nonempty unique ascending dates")
    values = adjusted_close.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("adjusted close panel must be finite and positive; no row repair is allowed")
    if slots < 1 or slots > adjusted_close.shape[1]:
        raise ValueError("invalid slot count")

    periods = adjusted_close.index.to_period("M")
    month_periods = list(pd.unique(periods))
    month_ends = {period: adjusted_close.index[np.flatnonzero(periods == period)[-1]] for period in month_periods}
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    terminal_censored = 0
    # The first observed month is used only as the prior month-end anchor; the last
    # observed month is never used as a signal month because it is not known complete.
    for month_idx in range(1, len(month_periods) - 1):
        prior_period = month_periods[month_idx - 1]
        signal_period = month_periods[month_idx]
        prior_end = month_ends[prior_period]
        signal_end = month_ends[signal_period]
        returns = adjusted_close.loc[signal_end] / adjusted_close.loc[prior_end] - 1.0
        target = rank_bottom({str(k): float(v) for k, v in returns.items()}, slots=slots)
        end_position = adjusted_close.index.get_loc(signal_end)
        entry_position = end_position + 1
        if entry_position >= len(adjusted_close.index):
            terminal_censored += 1
            continue
        entry_date = adjusted_close.index[entry_position]
        # Do not begin an investment month whose final session is absent from this snapshot.
        if entry_date.to_period("M") == month_periods[-1]:
            terminal_censored += 1
            continue
        targets[pd.Timestamp(entry_date)] = target
    return targets, {"rebalance_targets": len(targets), "terminal_censored": terminal_censored}


def drift_weights(weights: Mapping[str, float], asset_returns: Mapping[str, float]) -> dict[str, float]:
    if set(weights) - set(asset_returns):
        raise ValueError("asset returns are missing held symbols")
    gross_factor = sum(float(weight) * (1.0 + float(asset_returns[ticker])) for ticker, weight in weights.items())
    if not math.isfinite(gross_factor) or gross_factor <= 0:
        raise ValueError("portfolio gross factor must be finite and positive")
    return {ticker: float(weight) * (1.0 + float(asset_returns[ticker])) / gross_factor for ticker, weight in weights.items()}


def simulate_open_to_open(
    adjusted_open: pd.DataFrame,
    targets: Mapping[pd.Timestamp, Mapping[str, float]],
    cost_rate: float = COST_RATE,
) -> tuple[pd.Series, dict[str, float | int]]:
    if adjusted_open.empty or len(adjusted_open) < 2:
        raise ValueError("at least two adjusted-open rows are required")
    if adjusted_open.index.has_duplicates or not adjusted_open.index.is_monotonic_increasing:
        raise ValueError("adjusted-open panel dates must be unique and ascending")
    opens = adjusted_open.to_numpy(dtype=float)
    if not np.isfinite(opens).all() or (opens <= 0).any():
        raise ValueError("adjusted open must be finite and positive")
    if not math.isfinite(cost_rate) or cost_rate < 0 or cost_rate >= 1:
        raise ValueError("cost_rate must be a finite fraction in [0, 1)")
    symbols = list(adjusted_open.columns)
    unknown = {symbol for target in targets.values() for symbol in target} - set(symbols)
    if unknown:
        raise ValueError(f"targets contain unknown symbols: {sorted(unknown)}")

    normalized_targets = {pd.Timestamp(date): {str(k): float(v) for k, v in target.items()} for date, target in targets.items()}
    daily_net = np.empty(len(adjusted_open) - 1, dtype=float)
    weights: dict[str, float] = {}
    turnover_total = 0.0
    rebalance_count = 0
    for i, date in enumerate(adjusted_open.index[:-1]):
        factor = 1.0
        target = normalized_targets.get(pd.Timestamp(date))
        if target is not None:
            if any(not math.isfinite(w) or w < 0 for w in target.values()):
                raise ValueError(f"invalid target weights on {date}")
            if not math.isclose(sum(target.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"target weights must sum to 1 on {date}")
            turnover = sum(abs(target.get(symbol, 0.0) - weights.get(symbol, 0.0)) for symbol in symbols)
            if turnover > 2.0 + 1e-12:
                raise ValueError(f"impossible risky-asset turnover {turnover} on {date}")
            factor *= 1.0 - cost_rate * turnover
            turnover_total += turnover
            rebalance_count += 1
            weights = dict(target)

        interval_returns = adjusted_open.iloc[i + 1] / adjusted_open.iloc[i] - 1.0
        portfolio_return = sum(weights.get(symbol, 0.0) * float(interval_returns[symbol]) for symbol in symbols)
        if not math.isfinite(portfolio_return) or portfolio_return <= -1:
            raise ValueError(f"invalid portfolio return at {date}")
        factor *= 1.0 + portfolio_return
        daily_net[i] = factor - 1.0
        if weights:
            weights = drift_weights(weights, {symbol: float(interval_returns[symbol]) for symbol in weights})

    liquidation_turnover = sum(weights.values())
    if liquidation_turnover:
        daily_net[-1] = (1.0 + daily_net[-1]) * (1.0 - cost_rate * liquidation_turnover) - 1.0
    returns = pd.Series(daily_net, index=adjusted_open.index[1:], name="net_return")
    return returns, {
        "rebalance_count": rebalance_count,
        "turnover": turnover_total,
        "terminal_liquidation_turnover": liquidation_turnover,
    }


def calculate_metrics(returns: pd.Series) -> dict[str, float | int]:
    if returns.empty or not np.isfinite(returns.to_numpy(dtype=float)).all() or (returns <= -1).any():
        raise ValueError("metrics require nonempty finite returns greater than -100%")
    daily = returns.astype(float)
    std = float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
    sharpe = float(daily.mean() / std * np.sqrt(252.0)) if std > 0 else 0.0
    wealth = (1.0 + daily).cumprod()
    prior = np.concatenate(([1.0], wealth.to_numpy(dtype=float)[:-1]))
    peaks = np.maximum.accumulate(prior)
    drawdown = wealth.to_numpy(dtype=float) / peaks - 1.0
    elapsed_years = len(daily) / 252.0
    terminal_wealth = float(wealth.iloc[-1])
    cagr = terminal_wealth ** (1.0 / elapsed_years) - 1.0 if terminal_wealth > 0 else -1.0
    return {
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "max_drawdown": float(np.min(drawdown)),
        "terminal_wealth": terminal_wealth,
        "observations": int(len(daily)),
    }


def load_market_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    frames: dict[str, pd.DataFrame] = {}
    hashes: dict[str, str] = {}
    for symbol in (*SECTORS, BENCHMARK):
        path = DATA / f"{symbol}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"missing local market input: {path}")
        frames[symbol] = pd.read_parquet(path)
        validate_ohlc_frame(frames[symbol], symbol)
        hashes[symbol] = sha256_file(path)
    sector_index = frames[SECTORS[0]].index
    for symbol in SECTORS[1:]:
        if not frames[symbol].index.equals(sector_index):
            raise ValueError(f"sector date index mismatch: {symbol}")
    if not sector_index.isin(frames[BENCHMARK].index).all():
        raise ValueError("SPY benchmark is missing one or more sector dates")
    all_symbols = (*SECTORS, BENCHMARK)
    aligned = {symbol: frames[symbol].loc[sector_index] for symbol in all_symbols}
    adjusted_close = pd.DataFrame({symbol: aligned[symbol]["adjclose"] for symbol in SECTORS}, index=sector_index)
    adjusted_open = pd.DataFrame(
        {symbol: aligned[symbol]["open"] * aligned[symbol]["adjclose"] / aligned[symbol]["close"] for symbol in all_symbols},
        index=sector_index,
    )
    if not np.isfinite(adjusted_open.to_numpy(dtype=float)).all() or (adjusted_open <= 0).any().any():
        raise ValueError("aligned adjusted-open panel is invalid")
    return adjusted_close, adjusted_open, hashes


def _window(returns: pd.Series, start: str | None, end: str | None) -> pd.Series:
    selected = returns
    if start is not None:
        selected = selected.loc[selected.index >= pd.Timestamp(start)]
    if end is not None:
        selected = selected.loc[selected.index <= pd.Timestamp(end)]
    return selected


def run() -> dict:
    prereg = ROOT / "PREREG.md"
    run_id = datetime.now(timezone.utc).strftime("GEN11-%Y%m%dT%H%M%S-%f")[:-3]
    attempt_id = f"{run_id}-US_SECTOR_BOTTOM3_PREV_MONTH"
    started = datetime.now(timezone.utc).isoformat()
    attempt_path = ROOT / f"attempts_{run_id}.jsonl"
    try:
        if not prereg.is_file():
            raise FileNotFoundError("frozen PREREG.md not found")
        prereg_hash = sha256_file(prereg)
        test_hash = sha256_file(ROOT / "test_gen11.py")
        runner_hash = sha256_file(Path(__file__))
        adjusted_close, adjusted_open, data_hashes = load_market_data()
        targets, target_diagnostics = build_monthly_targets(adjusted_close, slots=SLOTS)
        sector_returns, portfolio_diagnostics = simulate_open_to_open(
            adjusted_open.loc[:, SECTORS], targets, cost_rate=COST_RATE
        )
        benchmark_targets = {adjusted_open.index[0]: {BENCHMARK: 1.0}}
        benchmark_returns, benchmark_diagnostics = simulate_open_to_open(
            adjusted_open.loc[:, [BENCHMARK]], benchmark_targets, cost_rate=COST_RATE
        )
        if not sector_returns.index.equals(benchmark_returns.index):
            raise ValueError("strategy and benchmark return dates are not identical")

        windows = {
            "full": (None, None),
            "2001_2016": ("2001-01-01", "2016-12-31"),
            "2017_plus": ("2017-01-01", "2026-11-02"),
        }
        results = {}
        for name, (start, end) in windows.items():
            strategy_slice = _window(sector_returns, start, end)
            benchmark_slice = _window(benchmark_returns, start, end)
            if strategy_slice.empty or benchmark_slice.empty or not strategy_slice.index.equals(benchmark_slice.index):
                raise ValueError(f"empty or unmatched descriptive window {name}")
            results[name] = {
                "strategy": calculate_metrics(strategy_slice),
                "spy_buy_hold": calculate_metrics(benchmark_slice),
            }
        manifest = {
            "run_id": run_id,
            "attempt_id": attempt_id,
            "status": "COMPLETED_EXPLORATORY",
            "started_utc": started,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "prereg_sha256": prereg_hash,
            "runner_sha256": runner_hash,
            "test_sha256": test_hash,
            "data_sha256": data_hashes,
            "universe": list(SECTORS),
            "benchmark": BENCHMARK,
            "date_start": str(adjusted_open.index[0].date()),
            "date_end": str(adjusted_open.index[-1].date()),
            "target_diagnostics": target_diagnostics,
            "portfolio_diagnostics": portfolio_diagnostics,
            "benchmark_diagnostics": benchmark_diagnostics,
            "windows": results,
            "data_scope": "local non-atomic Yahoo-derived mirror; exploratory only",
        }
        manifest_path = ROOT / f"manifest_{run_id}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        curves = pd.DataFrame({"sector_strategy_net": sector_returns, "spy_buy_hold_net": benchmark_returns})
        curves.to_csv(ROOT / f"equity_curves_{run_id}.csv.gz", compression="gzip", index_label="date")
        record = {
            "attempt_id": attempt_id,
            "run_id": run_id,
            "status": "COMPLETED_EXPLORATORY",
            "started_utc": started,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "candidate": "US_SECTOR_BOTTOM3_PREV_MONTH",
            "result": results,
        }
        attempt_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        return manifest
    except Exception as exc:
        attempt_path.write_text(
            json.dumps(
                {
                    "attempt_id": attempt_id,
                    "run_id": run_id,
                    "status": "FAILED",
                    "started_utc": started,
                    "finished_utc": datetime.now(timezone.utc).isoformat(),
                    "candidate": "US_SECTOR_BOTTOM3_PREV_MONTH",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
