"""One frozen downside-semivariance exposure-control experiment; no tuning."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[4]
DATA = REPO_ROOT / "trading/docs/research/kr_us_loop_v1/data_mirror/us_daily/SPY.parquet"
PREREG = HERE / "PREREG.md"
ADDENDUM = HERE / "ADDENDUM_A1.md"
ADDENDUM_A2 = HERE / "ADDENDUM_A2.md"
RUN_ID = "GEN12-20261106-US-SPY_DOWNSIDE_RMS63_TARGET10"
WINDOW = 63
TARGET_RISK = 0.10
FEE = 0.001
PERIODS_PER_YEAR = 252
FREEZE = HERE / "FREEZE.json"
ATTEMPTS = HERE / f"attempts_{RUN_ID}.jsonl"
MANIFEST = HERE / f"manifest_{RUN_ID}.json"
RESULTS = HERE / f"results_{RUN_ID}.json"
CURVE = HERE / f"curve_{RUN_ID}.csv.gz"


class DataBlockedError(RuntimeError):
    """Raised for missing or invalid research inputs, not a strategy result."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _write_json(path: Path, value: dict) -> None:
    _atomic_write(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n")


def _append_event(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, sort_keys=True, allow_nan=False, default=str) + "\n"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _create_attempt(path: Path, value: dict) -> None:
    """Atomically consume the one-attempt budget before any input processing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, sort_keys=True, allow_nan=False, default=str) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _series_values(close: pd.Series) -> np.ndarray:
    if not isinstance(close, pd.Series) or not isinstance(close.index, pd.DatetimeIndex):
        raise ValueError("close series must use a DatetimeIndex")
    if close.empty or close.index.has_duplicates or not close.index.is_monotonic_increasing:
        raise ValueError("dates must be nonempty, unique, and strictly increasing")
    values = close.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("adjusted close values must be finite and positive")
    return values


def downside_rms(returns: np.ndarray | list[float]) -> np.ndarray:
    """Return trailing zero-threshold downside RMS over exactly 63 intervals."""
    values = np.asarray(returns, dtype=float)
    if values.ndim != 1:
        raise ValueError("returns must be one-dimensional")
    out = np.full(values.shape, np.nan, dtype=float)
    for end in range(WINDOW, len(values)):
        sample = values[end - WINDOW + 1 : end + 1]
        if not np.isfinite(sample).all() or (sample <= -1).any():
            continue
        negatives = np.minimum(sample, 0.0)
        out[end] = math.sqrt(float(np.mean(negatives * negatives)))
    return out


def build_targets(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Compute close-time target exposures and annualized downside RMS forecasts."""
    values = _series_values(close)
    returns = np.full(len(values), np.nan, dtype=float)
    returns[1:] = values[1:] / values[:-1] - 1.0
    if not np.isfinite(returns[1:]).all() or (returns[1:] <= -1).any():
        raise ValueError("invalid adjusted-close return")
    rms = downside_rms(returns)
    annualized = rms * math.sqrt(PERIODS_PER_YEAR)
    target = np.full(len(values), np.nan, dtype=float)
    for index in range(WINDOW, len(values)):
        sigma = annualized[index]
        if not math.isfinite(float(sigma)):
            raise ValueError(f"nonfinite downside forecast at index {index}")
        if sigma <= 0:
            raise ValueError(f"zero downside forecast at index {index}; fail closed")
        target[index] = min(1.0, TARGET_RISK / float(sigma))
    return (
        pd.Series(target, index=close.index, name="target_exposure"),
        pd.Series(annualized, index=close.index, name="annualized_downside_rms"),
    )


def _validate_prices(raw: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "adjclose"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"missing required price columns: {sorted(missing)}")
    if not isinstance(raw.index, pd.DatetimeIndex):
        raise ValueError("price index must be a DatetimeIndex")
    if raw.empty or raw.index.has_duplicates or not raw.index.is_monotonic_increasing:
        raise ValueError("dates must be nonempty, unique, and strictly increasing")
    values = raw[["open", "high", "low", "close", "adjclose"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("raw OHLC and adjusted close must be finite and positive")
    if (raw["high"] < raw[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid raw high/low ordering")
    if (raw["low"] > raw[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("invalid raw high/low ordering")
    factor = raw["adjclose"] / raw["close"]
    adjusted = raw[["open", "high", "low", "close"]].multiply(factor, axis=0)
    if not np.isfinite(adjusted.to_numpy(dtype=float)).all() or (adjusted <= 0).any().any():
        raise ValueError("adjusted OHLC must be finite and positive")
    if (adjusted["high"] < adjusted[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("invalid adjusted high/low ordering")
    if (adjusted["low"] > adjusted[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("invalid adjusted low/high ordering")


def _normalize_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    normalized = index
    if normalized.tz is not None:
        normalized = normalized.tz_localize(None)
    return normalized.normalize()


def validate_session_calendar(index: pd.DatetimeIndex, calendar_path: Path) -> None:
    """Require exact equality with a pinned session_date calendar; never repair."""
    if not isinstance(index, pd.DatetimeIndex) or index.empty:
        raise DataBlockedError("SPY date index is unavailable for exchange-calendar validation")
    if index.has_duplicates or not index.is_monotonic_increasing:
        raise DataBlockedError("SPY dates are duplicate or unsorted; session-completeness check cannot proceed")
    try:
        calendar = pd.read_csv(calendar_path, usecols=["session_date"])
        expected_values = pd.to_datetime(calendar["session_date"], errors="raise")
    except Exception as exc:
        raise DataBlockedError(f"pinned NYSE Arca session calendar cannot be read: {type(exc).__name__}: {exc}") from exc
    expected = pd.DatetimeIndex(expected_values)
    if expected.tz is not None:
        expected = expected.tz_localize(None)
    expected = expected.normalize()
    if expected.empty or expected.has_duplicates or not expected.is_monotonic_increasing:
        raise DataBlockedError("pinned NYSE Arca calendar dates must be nonempty, unique, and ascending")
    actual = _normalize_dates(index)
    if actual.has_duplicates:
        raise DataBlockedError("SPY index contains multiple timestamps for one session date")
    lower, upper = actual.min(), actual.max()
    expected = expected[(expected >= lower) & (expected <= upper)]
    missing = expected.difference(actual)
    unexpected = actual.difference(expected)
    if len(missing) or len(unexpected):
        missing_sample = [str(value.date()) for value in missing[:5]]
        unexpected_sample = [str(value.date()) for value in unexpected[:5]]
        raise DataBlockedError(
            "SPY dates do not exactly match pinned NYSE Arca sessions; "
            f"missing_count={len(missing)} missing_sample={missing_sample} "
            f"unexpected_count={len(unexpected)} unexpected_sample={unexpected_sample}"
        )


def simulate(raw: pd.DataFrame, targets: pd.Series, fee: float = FEE) -> dict:
    """Simulate next-open target changes, open-to-open PnL and one-way costs."""
    _validate_prices(raw)
    if not 0 <= fee < 1:
        raise ValueError("fee must be in [0, 1)")
    if not targets.index.equals(raw.index):
        raise ValueError("target index must exactly match price index")
    target_values = targets.to_numpy(dtype=float)
    finite = np.isfinite(target_values)
    if finite.any():
        first_valid = int(np.flatnonzero(finite)[0])
        if not finite[first_valid:].all():
            raise ValueError("target forecast cannot become unavailable after warm-up")
        if ((target_values[finite] < 0) | (target_values[finite] > 1)).any():
            raise ValueError("target exposure must remain in [0, 1]")

    adjusted_open = raw["open"] * raw["adjclose"] / raw["close"]
    opens = adjusted_open.to_numpy(dtype=float)
    if not np.isfinite(opens).all() or (opens <= 0).any():
        raise ValueError("adjusted open must be finite and positive")
    asset_returns = opens[1:] / opens[:-1] - 1.0
    if not np.isfinite(asset_returns).all() or (asset_returns <= -1).any():
        raise ValueError("invalid adjusted-open return")

    returns = np.zeros(len(asset_returns), dtype=float)
    gross_returns = np.zeros(len(asset_returns), dtype=float)
    benchmark = np.empty(len(asset_returns), dtype=float)
    interval_exposure = np.zeros(len(asset_returns), dtype=float)
    turnover = np.zeros(len(asset_returns), dtype=float)
    wealth = 1.0
    gross_wealth = 1.0
    held_weight = 0.0
    terminal_target_ignored = 0.0

    # Matched SPY buy-and-hold: enter at the first eligible target open and liquidate
    # at the last observed open. Entry/exit costs are attached to the first and
    # final open-to-open intervals, respectively, without changing their dates.
    valid_targets = np.flatnonzero(finite)
    if not len(valid_targets):
        raise ValueError("no valid target exposure exists")
    first_target_close = int(valid_targets[0])
    entry_open_index = first_target_close + 1
    if entry_open_index >= len(raw) - 1:
        raise ValueError("first valid target has no subsequent holding interval")
    benchmark_wealth = 1.0
    benchmark_weight = 0.0
    benchmark_exposure = np.zeros(len(asset_returns), dtype=float)
    for interval, asset_return in enumerate(asset_returns):
        open_index = interval + 1
        benchmark_previous = benchmark_wealth
        benchmark_exposure[interval] = benchmark_weight
        if open_index < entry_open_index:
            pass  # shared cash warm-up; no interval return or transaction cost
        elif open_index == entry_open_index:
            benchmark_wealth *= 1.0 - fee
            benchmark_weight = 1.0
        else:
            benchmark_wealth *= 1.0 + float(asset_return)
            if open_index == len(raw) - 1:
                benchmark_wealth *= 1.0 - fee
                benchmark_weight = 0.0
        benchmark[interval] = benchmark_wealth / benchmark_previous - 1.0

    for interval, asset_return_value in enumerate(asset_returns):
        open_index = interval + 1
        asset_return = float(asset_return_value)
        wealth_before = wealth
        gross_wealth_before = gross_wealth
        portfolio_factor = 1.0 + held_weight * asset_return
        if portfolio_factor <= 0 or not math.isfinite(portfolio_factor):
            raise ValueError(f"invalid portfolio wealth factor at open index {open_index}")
        wealth *= portfolio_factor
        gross_wealth *= portfolio_factor
        drifted_weight = held_weight * (1.0 + asset_return) / portfolio_factor
        interval_exposure[interval] = held_weight

        if open_index == len(raw) - 1:
            # A close-time forecast cannot establish a fresh terminal holding;
            # any carried exposure is liquidated at this final observed open.
            source_close = open_index - 1
            terminal_target_ignored = (
                float(target_values[source_close]) if math.isfinite(float(target_values[source_close])) else 0.0
            )
            next_weight = 0.0
        else:
            source_close = open_index - 1
            proposed = target_values[source_close]
            if not math.isfinite(float(proposed)):
                if finite.any() and source_close >= int(np.flatnonzero(finite)[0]):
                    raise ValueError(f"missing target after warm-up at close index {source_close}")
                next_weight = 0.0
            else:
                next_weight = float(proposed)

        traded_notional = abs(next_weight - drifted_weight)
        cost_fraction = fee * traded_notional
        if not math.isfinite(cost_fraction) or cost_fraction >= 1:
            raise ValueError(f"invalid transaction cost at open index {open_index}")
        wealth *= 1.0 - cost_fraction
        turnover[interval] = traded_notional
        held_weight = next_weight
        returns[interval] = wealth / wealth_before - 1.0
        gross_returns[interval] = gross_wealth / gross_wealth_before - 1.0

    if not np.isfinite(returns).all() or not np.isfinite(benchmark).all():
        raise ValueError("nonfinite simulated return")
    return {
        "returns": pd.Series(returns, index=raw.index[1:], name="strategy_return"),
        "gross_returns": pd.Series(gross_returns, index=raw.index[1:], name="gross_strategy_return"),
        "benchmark_returns": pd.Series(benchmark, index=raw.index[1:], name="benchmark_return"),
        "benchmark_exposure": pd.Series(benchmark_exposure, index=raw.index[1:], name="benchmark_exposure"),
        "exposure": pd.Series(interval_exposure, index=raw.index[1:], name="exposure"),
        "turnover_series": pd.Series(turnover, index=raw.index[1:], name="traded_notional"),
        "turnover": turnover,
        "total_traded_notional": float(turnover.sum()),
        "rebalance_events": int(np.count_nonzero(turnover)),
        "average_exposure": float(interval_exposure.mean()) if len(interval_exposure) else 0.0,
        "completed_open_to_open_holding_intervals": int(np.count_nonzero(interval_exposure > 0)),
        "terminal_target_ignored": terminal_target_ignored,
        "first_entry_open_index": entry_open_index,
        "first_entry_open_date": str(raw.index[entry_open_index].date()),
    }


def metrics(returns: pd.Series) -> dict:
    values = returns.to_numpy(dtype=float)
    if len(values) == 0 or not np.isfinite(values).all() or (values <= -1).any():
        raise ValueError("invalid metric return vector")
    wealth = np.cumprod(1.0 + values)
    if not np.isfinite(wealth).all() or (wealth <= 0).any():
        raise ValueError("invalid cumulative wealth")
    years = len(values) / PERIODS_PER_YEAR
    cagr = float(wealth[-1] ** (1.0 / years) - 1.0) if years > 0 else 0.0
    standard_deviation = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    sharpe = float(np.mean(values) / standard_deviation * math.sqrt(PERIODS_PER_YEAR)) if standard_deviation > 0 else 0.0
    peaks = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
    max_drawdown = float(np.min(wealth / peaks - 1.0)) if len(wealth) else 0.0
    return {
        "observations": int(len(values)),
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "total_return": float(wealth[-1] - 1.0),
    }


def _verify_freeze(
    prereg: Path, addendum: Path, addendum_a2: Path, runner_path: Path, tests_path: Path, freeze_path: Path
) -> dict:
    if not freeze_path.exists():
        raise RuntimeError("missing FREEZE.json; performance run is not authorized")
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    if frozen.get("data_gate_status") == "DATA_BLOCKED":
        raise DataBlockedError(frozen.get("data_gate_reason", "authoritative NYSE Arca session calendar is unavailable"))
    if frozen.get("data_gate_status") != "READY":
        raise RuntimeError("data gate must be READY after authoritative calendar review")
    if frozen.get("review_status") != "GO":
        raise RuntimeError("root GO is required before reading market data")
    for key, path in (("prereg_sha256", prereg), ("addendum_sha256", addendum),
                      ("addendum_a2_sha256", addendum_a2),
                      ("runner_sha256", runner_path), ("test_sha256", tests_path)):
        if frozen.get(key) != sha256(path):
            raise RuntimeError(f"freeze hash mismatch for {key}")
    expected_data_hash = frozen.get("data_sha256")
    if not isinstance(expected_data_hash, str) or len(expected_data_hash) != 64:
        raise RuntimeError("root GO freeze must pin the input data SHA-256")
    calendar_path_value = frozen.get("calendar_path")
    calendar_source = frozen.get("calendar_source")
    expected_calendar_hash = frozen.get("calendar_sha256")
    if not isinstance(calendar_path_value, str) or not calendar_path_value:
        raise RuntimeError("freeze must pin an authoritative NYSE Arca calendar path")
    if not isinstance(calendar_source, str) or not calendar_source:
        raise RuntimeError("freeze must record authoritative NYSE Arca calendar provenance")
    if not isinstance(expected_calendar_hash, str) or len(expected_calendar_hash) != 64:
        raise RuntimeError("freeze must pin the authoritative session calendar SHA-256")
    calendar_path = Path(calendar_path_value)
    if not calendar_path.is_absolute():
        calendar_path = REPO_ROOT / calendar_path
    if sha256(calendar_path) != expected_calendar_hash:
        raise RuntimeError("freeze hash mismatch for calendar_sha256")
    frozen["_resolved_calendar_path"] = str(calendar_path)
    return frozen


def execute_attempt(
    *,
    prereg: Path,
    addendum: Path,
    addendum_a2: Path,
    runner_path: Path,
    tests_path: Path,
    freeze_path: Path,
    data_path: Path,
    attempts_path: Path,
    manifest_path: Path,
    reader: Callable[[Path], pd.DataFrame] = pd.read_parquet,
) -> dict:
    """Execute at most once; persist STARTED/FAILED/FINISHED before returning."""
    related_artifacts = [manifest_path, RESULTS if attempts_path == ATTEMPTS else attempts_path.with_name("results.json"),
                         CURVE if attempts_path == ATTEMPTS else attempts_path.with_name("curve.csv.gz")]
    if attempts_path.exists() or any(path.exists() for path in related_artifacts):
        raise RuntimeError("one-attempt budget already consumed; refusing overwrite or rerun")

    start = {
        "run_id": RUN_ID,
        "status": "STARTED",
        "prereg_sha256": sha256(prereg) if prereg.exists() else None,
        "addendum_sha256": sha256(addendum) if addendum.exists() else None,
        "addendum_a2_sha256": sha256(addendum_a2) if addendum_a2.exists() else None,
        "runner_sha256": sha256(runner_path) if runner_path.exists() else None,
        "test_sha256": sha256(tests_path) if tests_path.exists() else None,
        "market_values_opened": False,
    }
    try:
        _create_attempt(attempts_path, start)
    except FileExistsError as exc:
        raise RuntimeError("one-attempt budget already consumed; refusing overwrite or rerun") from exc
    market_values_opened = False
    try:
        _write_json(manifest_path, start)
        frozen = _verify_freeze(prereg, addendum, addendum_a2, runner_path, tests_path, freeze_path)
        actual_data_hash = sha256(data_path)
        if frozen.get("data_sha256") != actual_data_hash:
            raise RuntimeError("freeze hash mismatch for data_sha256")
        started_with_input = {**start, "data_sha256": actual_data_hash, "market_values_opened": False}
        _write_json(manifest_path, started_with_input)

        # Persist the boundary immediately before the reader opens/parses prices.
        market_values_opened = True
        data_read_event = {"run_id": RUN_ID, "status": "DATA_READ_STARTED", "market_values_opened": True,
                           "data_sha256": actual_data_hash}
        _append_event(attempts_path, data_read_event)
        _write_json(manifest_path, data_read_event)
        raw = reader(data_path)
        validate_session_calendar(raw.index, Path(frozen["_resolved_calendar_path"]))
        _validate_prices(raw)
        targets, forecasts = build_targets(raw["adjclose"])
        run = simulate(raw, targets, fee=FEE)
        curve = pd.DataFrame(
            {
                "strategy_return": run["returns"],
                "gross_strategy_return": run["gross_returns"],
                "benchmark_return": run["benchmark_returns"],
                "benchmark_exposure": run["benchmark_exposure"],
                "equity_strategy": (1.0 + run["returns"]).cumprod(),
                "equity_gross": (1.0 + run["gross_returns"]).cumprod(),
                "equity_benchmark": (1.0 + run["benchmark_returns"]).cumprod(),
                "exposure": run["exposure"],
                "traded_notional": run["turnover_series"],
                "downside_rms_forecast": forecasts.shift(1).reindex(run["returns"].index),
            }
        )
        core_curve = curve.drop(columns=["downside_rms_forecast"])
        if core_curve.isna().any().any() or not np.isfinite(core_curve.to_numpy(dtype=float)).all():
            raise ValueError("curve contains missing or nonfinite return/accounting values")
        forecast_values = curve["downside_rms_forecast"].to_numpy(dtype=float)
        valid_forecasts = np.flatnonzero(np.isfinite(forecast_values))
        if not len(valid_forecasts) or not np.isfinite(forecast_values[valid_forecasts[0] :]).all():
            raise ValueError("downside forecast must be present after its fixed warm-up")

        windows = {
            "full": (curve.index.min(), curve.index.max()),
            "2001_2016": (pd.Timestamp("2001-01-02"), pd.Timestamp("2016-12-30")),
            "2017_plus_contaminated": (pd.Timestamp("2017-01-03"), curve.index.max()),
        }
        report: dict = {}
        for name, (start_date, end_date) in windows.items():
            subset = curve.loc[start_date:end_date]
            if subset.empty:
                raise ValueError(f"empty metric window: {name}")
            report[name] = {
                "start": str(subset.index.min().date()),
                "end": str(subset.index.max().date()),
                "strategy": metrics(subset["strategy_return"]),
                "gross_strategy": metrics(subset["gross_strategy_return"]),
                "benchmark": metrics(subset["benchmark_return"]),
                "completed_open_to_open_holding_intervals": int((subset["exposure"] > 0).sum()),
                "total_traded_notional_as_fraction_of_wealth": float(subset["traded_notional"].sum()),
                "fee_per_traded_notional": FEE,
                "cost_drag": {
                    "net_minus_gross_total_return": float(
                        metrics(subset["strategy_return"])["total_return"]
                        - metrics(subset["gross_strategy_return"])["total_return"]
                    ),
                    "net_minus_gross_cagr": float(
                        metrics(subset["strategy_return"])["cagr"]
                        - metrics(subset["gross_strategy_return"])["cagr"]
                    ),
                    "terminal_wealth_shortfall_fraction": float(
                        1.0
                        - (1.0 + metrics(subset["strategy_return"])["total_return"])
                        / (1.0 + metrics(subset["gross_strategy_return"])["total_return"])
                    ),
                },
                "drawdown_scope": "recomputed from a fresh within-window baseline; portfolio path remains continuous",
            }
        report["activity"] = {
            "average_exposure": run["average_exposure"],
            "completed_open_to_open_holding_intervals": run["completed_open_to_open_holding_intervals"],
            "benchmark_average_exposure": float(run["benchmark_exposure"].mean()),
            "first_entry_open_index": run["first_entry_open_index"],
            "first_entry_open_date": run["first_entry_open_date"],
            "rebalance_events_including_entry_and_terminal_exit": run["rebalance_events"],
            "total_traded_notional_as_fraction_of_wealth": run["total_traded_notional"],
            "fee_per_traded_notional": FEE,
            "target_risk_annualized": TARGET_RISK,
            "downside_lookback_intervals": WINDOW,
        }
        report["provenance"] = {
            "run_id": RUN_ID,
            "prereg_sha256": sha256(prereg),
            "runner_sha256": sha256(runner_path),
            "test_sha256": sha256(tests_path),
            "data_sha256": actual_data_hash,
            "data_path": str(data_path),
            "row_count": int(len(raw)),
            "first_date": str(raw.index.min().date()),
            "last_date": str(raw.index.max().date()),
            "root_review_status": frozen["review_status"],
            "evidence_status": "exploratory historical screen; not untouched OOS",
        }
        result_text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False, default=str) + "\n"
        curve_text_path = CURVE if attempts_path == ATTEMPTS else attempts_path.with_name("curve.csv.gz")
        # Write compressed curve through pandas to a temporary path, then replace.
        fd, temporary_curve = tempfile.mkstemp(prefix=f".{curve_text_path.name}.", dir=curve_text_path.parent)
        os.close(fd)
        try:
            curve.to_csv(temporary_curve, compression="gzip", index_label="date")
            os.replace(temporary_curve, curve_text_path)
        except Exception:
            try:
                os.unlink(temporary_curve)
            except FileNotFoundError:
                pass
            raise
        results_path = RESULTS if attempts_path == ATTEMPTS else attempts_path.with_name("results.json")
        _atomic_write(results_path, result_text)
        finish = {"run_id": RUN_ID, "status": "FINISHED_EXPLORATORY", **report}
        _write_json(manifest_path, finish)
        _append_event(attempts_path, finish)
        return report
    except Exception as exc:
        blocked = isinstance(exc, DataBlockedError)
        failure = {
            "run_id": RUN_ID,
            "status": "DATA_BLOCKED" if blocked else "FAILED",
            "stage": "input_calendar_or_data" if blocked else "preflight_or_execution",
            "reason": f"{type(exc).__name__}: {exc}",
            "market_values_opened": market_values_opened,
            "strategy_result": False,
        }
        _append_event(attempts_path, failure)
        _write_json(manifest_path, failure)
        raise


def main() -> None:
    execute_attempt(
        prereg=PREREG,
        addendum=ADDENDUM,
        addendum_a2=ADDENDUM_A2,
        runner_path=Path(__file__),
        tests_path=HERE / "test_gen12_volatility.py",
        freeze_path=FREEZE,
        data_path=DATA,
        attempts_path=ATTEMPTS,
        manifest_path=MANIFEST,
    )


if __name__ == "__main__":
    main()
