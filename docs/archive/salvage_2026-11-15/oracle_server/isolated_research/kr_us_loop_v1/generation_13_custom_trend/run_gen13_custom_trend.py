"""One frozen SPY DMI/Choppiness trend-state experiment; no tuning."""
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
RESEARCH_ROOT = HERE.parent
REPO_ROOT = RESEARCH_ROOT.parents[2]
RUN_ID = "GEN13-SPY-DMI14-CHOP14-HYSTERESIS-382-618-A1"
PERIOD = 14
ENTRY_CHOP = 38.2
EXIT_CHOP = 61.8
FEE = 0.001
PERIODS_PER_YEAR = 252
PREREG = HERE / "PREREG.md"
FREEZE = HERE / "FREEZE.json"
DATA = RESEARCH_ROOT / "data_mirror/us_daily/SPY.parquet"
ATTEMPTS = HERE / f"attempts_{RUN_ID}.jsonl"
MANIFEST = HERE / f"manifest_{RUN_ID}.json"
RESULTS = HERE / f"results_{RUN_ID}.json"
CURVE = HERE / f"curve_{RUN_ID}.csv.gz"


class DataBlockedError(RuntimeError):
    """Input integrity or provenance is insufficient for this run."""


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
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, allow_nan=False, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _create_attempt(path: Path, value: dict) -> None:
    """Atomically consume the single run allowance and durably record STARTED."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, allow_nan=False, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def validate_prices(raw: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "adjclose"}
    missing = required - set(raw.columns)
    if missing:
        raise DataBlockedError(f"missing required price columns: {sorted(missing)}")
    if not isinstance(raw.index, pd.DatetimeIndex):
        raise DataBlockedError("price index must be a DatetimeIndex")
    if raw.empty or raw.index.has_duplicates or not raw.index.is_monotonic_increasing:
        raise DataBlockedError("price dates must be nonempty, unique, and strictly increasing")
    values = raw[["open", "high", "low", "close", "adjclose"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise DataBlockedError("raw OHLC and adjusted close must be finite and positive")
    if (raw["high"] < raw[["open", "close", "low"]].max(axis=1)).any():
        raise DataBlockedError("invalid raw OHLC ordering")
    if (raw["low"] > raw[["open", "close", "high"]].min(axis=1)).any():
        raise DataBlockedError("invalid raw OHLC ordering")
    factor = raw["adjclose"] / raw["close"]
    adjusted = raw[["open", "high", "low", "close"]].multiply(factor, axis=0)
    adjusted_values = adjusted.to_numpy(dtype=float)
    if not np.isfinite(adjusted_values).all() or (adjusted_values <= 0).any():
        raise DataBlockedError("adjusted OHLC must be finite and positive")
    if (adjusted["high"] < adjusted[["open", "close", "low"]].max(axis=1)).any():
        raise DataBlockedError("invalid adjusted OHLC ordering")
    if (adjusted["low"] > adjusted[["open", "close", "high"]].min(axis=1)).any():
        raise DataBlockedError("invalid adjusted OHLC ordering")


def adjust_ohlc(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate raw input and apply each row's AdjClose/Close factor to OHLC."""
    validate_prices(raw)
    factor = raw["adjclose"] / raw["close"]
    adjusted = raw[["open", "high", "low", "close"]].multiply(factor, axis=0)
    adjusted.columns = ["open", "high", "low", "close"]
    return adjusted


def wilder_smooth(values: np.ndarray | list[float], period: int = PERIOD) -> np.ndarray:
    """Wilder smoothing seeded by an arithmetic mean of period consecutive values."""
    data = np.asarray(values, dtype=float)
    if data.ndim != 1:
        raise ValueError("Wilder input must be one-dimensional")
    if period <= 0:
        raise ValueError("Wilder period must be positive")
    result = np.full(data.shape, np.nan, dtype=float)
    run_start: int | None = None
    previous = math.nan
    valid_run = 0
    for index, value in enumerate(data):
        if not math.isfinite(float(value)):
            run_start = None
            previous = math.nan
            valid_run = 0
            continue
        if run_start is None:
            run_start = index
            valid_run = 1
        else:
            valid_run += 1
        if valid_run == period:
            previous = float(np.mean(data[index - period + 1 : index + 1]))
            result[index] = previous
        elif valid_run > period:
            previous = ((period - 1) * previous + float(value)) / period
            result[index] = previous
    return result


def calculate_features(adjusted: pd.DataFrame) -> pd.DataFrame:
    """Calculate only causal DMI14 and CHOP14 features from adjusted OHLC."""
    required = {"open", "high", "low", "close"}
    if required - set(adjusted.columns):
        raise ValueError(f"adjusted frame missing columns: {sorted(required - set(adjusted.columns))}")
    if not isinstance(adjusted.index, pd.DatetimeIndex) or adjusted.index.has_duplicates or not adjusted.index.is_monotonic_increasing:
        raise ValueError("adjusted OHLC dates must be unique and strictly ascending")
    values = adjusted[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("adjusted OHLC must be finite and positive")

    high = adjusted["high"].to_numpy(dtype=float)
    low = adjusted["low"].to_numpy(dtype=float)
    close = adjusted["close"].to_numpy(dtype=float)
    tr = np.empty(len(adjusted), dtype=float)
    plus_dm = np.zeros(len(adjusted), dtype=float)
    minus_dm = np.zeros(len(adjusted), dtype=float)
    if len(adjusted):
        tr[0] = high[0] - low[0]
    if len(adjusted) > 1:
        up = high[1:] - high[:-1]
        down = low[:-1] - low[1:]
        tr[1:] = np.maximum.reduce(
            (high[1:] - low[1:], np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1]))
        )
        plus_dm[1:] = np.where((up > down) & (up > 0.0), up, 0.0)
        minus_dm[1:] = np.where((down > up) & (down > 0.0), down, 0.0)

    smooth_tr = wilder_smooth(tr, PERIOD)
    smooth_plus = wilder_smooth(plus_dm, PERIOD)
    smooth_minus = wilder_smooth(minus_dm, PERIOD)
    di_plus = np.full(len(adjusted), np.nan, dtype=float)
    di_minus = np.full(len(adjusted), np.nan, dtype=float)
    denominators_valid = np.isfinite(smooth_tr) & (smooth_tr > 0.0)
    di_plus[denominators_valid] = 100.0 * smooth_plus[denominators_valid] / smooth_tr[denominators_valid]
    di_minus[denominators_valid] = 100.0 * smooth_minus[denominators_valid] / smooth_tr[denominators_valid]

    tr_series = pd.Series(tr, index=adjusted.index, name="tr")
    rolling_tr = tr_series.rolling(PERIOD, min_periods=PERIOD).sum().to_numpy(dtype=float)
    rolling_high = adjusted["high"].rolling(PERIOD, min_periods=PERIOD).max().to_numpy(dtype=float)
    rolling_low = adjusted["low"].rolling(PERIOD, min_periods=PERIOD).min().to_numpy(dtype=float)
    ranges = rolling_high - rolling_low
    chop = np.full(len(adjusted), np.nan, dtype=float)
    valid_chop = np.isfinite(rolling_tr) & (rolling_tr > 0.0) & np.isfinite(ranges) & (ranges > 0.0)
    chop[valid_chop] = 100.0 * np.log10(rolling_tr[valid_chop] / ranges[valid_chop]) / np.log10(float(PERIOD))

    return pd.DataFrame(
        {"tr": tr, "di_plus": di_plus, "di_minus": di_minus, "chop14": chop},
        index=adjusted.index,
    )


def indicator_validity(features: pd.DataFrame) -> pd.Series:
    columns = ["di_plus", "di_minus", "chop14"]
    missing = set(columns) - set(features.columns)
    if missing:
        raise ValueError(f"indicator feature columns missing: {sorted(missing)}")
    return pd.Series(np.isfinite(features[columns].to_numpy(dtype=float)).all(axis=1), index=features.index, name="valid")


def build_state(features: pd.DataFrame, valid: pd.Series) -> pd.Series:
    """Close-time binary trend state with fixed entry/exit Choppiness hysteresis."""
    if not features.index.equals(valid.index):
        raise ValueError("feature and validity indices must match exactly")
    validity = valid.to_numpy(dtype=bool)
    values = features[["di_plus", "di_minus", "chop14"]].to_numpy(dtype=float)
    if validity.any():
        first = int(np.flatnonzero(validity)[0])
        if not validity[first:].all():
            raise ValueError("indicator features cannot become unavailable after warm-up")
    state = np.zeros(len(features), dtype=np.int8)
    current = 0
    for index in range(len(features)):
        if not validity[index]:
            if index and validity[:index].any():
                raise ValueError("indicator features became unavailable after warm-up")
            state[index] = 0
            continue
        di_plus, di_minus, chop = map(float, values[index])
        if not all(math.isfinite(value) for value in (di_plus, di_minus, chop)):
            raise ValueError(f"validity mask marks non-finite feature at index {index}")
        if current == 0:
            if di_plus > di_minus and chop < ENTRY_CHOP:
                current = 1
        elif di_plus <= di_minus or chop >= EXIT_CHOP:
            current = 0
        state[index] = current
    return pd.Series(state, index=features.index, name="target_state", dtype=float)


def _finite_returns(values: np.ndarray, label: str) -> None:
    if values.ndim != 1 or not np.isfinite(values).all() or (values <= -1.0).any():
        raise ValueError(f"invalid {label} return vector")


def validate_session_calendar(index: pd.DatetimeIndex, calendar_path: Path) -> None:
    """Require exact normalized date equality with an authoritative pinned calendar."""
    if not isinstance(index, pd.DatetimeIndex) or index.empty:
        raise DataBlockedError("SPY date index unavailable for session-calendar check")
    if index.has_duplicates or not index.is_monotonic_increasing:
        raise DataBlockedError("SPY dates must be unique and ascending before calendar comparison")
    try:
        dates = pd.to_datetime(pd.read_csv(calendar_path, usecols=["session_date"])["session_date"], errors="raise")
    except Exception as exc:
        raise DataBlockedError(f"pinned NYSE Arca calendar cannot be read: {type(exc).__name__}: {exc}") from exc
    expected = pd.DatetimeIndex(dates)
    actual = index
    if expected.tz is not None:
        expected = expected.tz_localize(None)
    if actual.tz is not None:
        actual = actual.tz_localize(None)
    expected = expected.normalize()
    actual = actual.normalize()
    if (
        expected.empty
        or expected.has_duplicates
        or not expected.is_monotonic_increasing
    ):
        raise DataBlockedError("pinned NYSE Arca calendar dates must be nonempty, unique, and ascending")
    if actual.has_duplicates or not actual.is_monotonic_increasing:
        raise DataBlockedError("SPY rows must map to unique, ascending session dates after normalization")
    lower, upper = actual.min(), actual.max()
    expected = expected[(expected >= lower) & (expected <= upper)]
    missing, unexpected = expected.difference(actual), actual.difference(expected)
    if len(missing) or len(unexpected):
        raise DataBlockedError(
            "SPY dates do not exactly match pinned NYSE Arca sessions; "
            f"missing_count={len(missing)} unexpected_count={len(unexpected)}"
        )


def simulate_open_to_open(
    raw: pd.DataFrame,
    states: pd.Series,
    valid: pd.Series,
    fee: float = FEE,
) -> dict:
    """Simulate close-t state at open t+1, open-to-open returns, and fee events."""
    validate_prices(raw)
    if not 0.0 <= fee < 1.0:
        raise ValueError("fee must be in [0, 1)")
    if not states.index.equals(raw.index) or not valid.index.equals(raw.index):
        raise ValueError("state/validity indices must exactly match price index")
    if not valid.to_numpy(dtype=bool).any():
        raise ValueError("no valid indicator state exists")
    state_values = states.to_numpy(dtype=float)
    valid_values = valid.to_numpy(dtype=bool)
    if not np.isfinite(state_values).all() or not np.isin(state_values, [0.0, 1.0]).all():
        raise ValueError("state must be a finite binary vector")
    first_valid_close = int(np.flatnonzero(valid_values)[0])
    if not valid_values[first_valid_close:].all():
        raise ValueError("validity cannot become false after warm-up")
    first_eligible_open = first_valid_close + 1
    if first_eligible_open >= len(raw) - 1:
        raise ValueError("first eligible open has no subsequent holding interval")

    adjusted_open = raw["open"] * raw["adjclose"] / raw["close"]
    opens = adjusted_open.to_numpy(dtype=float)
    if not np.isfinite(opens).all() or (opens <= 0.0).any():
        raise DataBlockedError("adjusted open must be finite and positive")
    asset_returns = opens[1:] / opens[:-1] - 1.0
    _finite_returns(asset_returns, "adjusted-open")

    # Curve observations are intervals ending at each subsequent eligible open.
    end_indices = np.arange(first_eligible_open + 1, len(raw), dtype=int)
    curve_index = raw.index[end_indices]
    count = len(end_indices)
    strategy_returns = np.zeros(count, dtype=float)
    gross_returns = np.zeros(count, dtype=float)
    benchmark_returns = np.zeros(count, dtype=float)
    exposure = np.zeros(count, dtype=float)
    benchmark_exposure = np.ones(count, dtype=float)
    turnover = np.zeros(count, dtype=float)
    costs = np.zeros(count, dtype=float)

    strategy_wealth = 1.0
    strategy_gross_wealth = 1.0
    strategy_weight = float(state_values[first_valid_close])
    initial_turnover = abs(strategy_weight)
    initial_cost = fee * initial_turnover
    strategy_wealth *= 1.0 - initial_cost
    turnover[0] += initial_turnover
    costs[0] += initial_cost

    benchmark_wealth = 1.0 * (1.0 - fee)
    benchmark_weight = 1.0

    for output_index, ending_open in enumerate(end_indices):
        starting_open = int(ending_open - 1)
        interval_return = float(asset_returns[starting_open])
        exposure[output_index] = strategy_weight

        strategy_before = strategy_wealth
        gross_before = strategy_gross_wealth
        strategy_factor = 1.0 + strategy_weight * interval_return
        if not math.isfinite(strategy_factor) or strategy_factor <= 0.0:
            raise ValueError(f"invalid strategy wealth factor for interval ending {ending_open}")
        strategy_wealth *= strategy_factor
        strategy_gross_wealth *= strategy_factor

        benchmark_before = benchmark_wealth
        benchmark_factor = 1.0 + benchmark_weight * interval_return
        if not math.isfinite(benchmark_factor) or benchmark_factor <= 0.0:
            raise ValueError(f"invalid benchmark wealth factor for interval ending {ending_open}")
        benchmark_wealth *= benchmark_factor

        is_terminal_open = ending_open == len(raw) - 1
        if is_terminal_open:
            desired = 0.0
        else:
            source_close = ending_open - 1
            if not valid_values[source_close]:
                raise ValueError(f"missing close-time state after warm-up at index {source_close}")
            desired = float(state_values[source_close])
        drifted = strategy_weight * (1.0 + interval_return) / strategy_factor
        # For a fully invested or flat binary strategy, drifted weight remains
        # exactly binary after an interval. Keep the general portfolio formula
        # explicit so future accidental target changes cannot hide turnover.
        if strategy_weight not in (0.0, 1.0):
            raise ValueError("only binary long-or-cash exposure is permitted")
        traded = abs(desired - drifted)
        cost = fee * traded
        if not math.isfinite(cost) or cost >= 1.0:
            raise ValueError(f"invalid strategy transaction cost at open {ending_open}")
        strategy_wealth *= 1.0 - cost
        turnover[output_index] += traded
        costs[output_index] += cost
        strategy_weight = desired

        if is_terminal_open:
            benchmark_cost = fee * abs(0.0 - benchmark_weight)
            benchmark_wealth *= 1.0 - benchmark_cost
            benchmark_weight = 0.0
        else:
            benchmark_cost = 0.0
        # Attribute entry at the first curve open to the first interval and
        # terminal liquidation to the final interval.
        benchmark_returns[output_index] = benchmark_wealth / (1.0 if output_index == 0 else benchmark_before) - 1.0
        strategy_returns[output_index] = strategy_wealth / (1.0 if output_index == 0 else strategy_before) - 1.0
        gross_returns[output_index] = strategy_gross_wealth / gross_before - 1.0

    _finite_returns(strategy_returns, "net strategy")
    _finite_returns(gross_returns, "gross strategy")
    _finite_returns(benchmark_returns, "benchmark")
    return {
        "returns": pd.Series(strategy_returns, index=curve_index, name="strategy_return"),
        "gross_returns": pd.Series(gross_returns, index=curve_index, name="gross_strategy_return"),
        "benchmark_returns": pd.Series(benchmark_returns, index=curve_index, name="benchmark_return"),
        "exposure": pd.Series(exposure, index=curve_index, name="exposure"),
        "benchmark_exposure": pd.Series(benchmark_exposure, index=curve_index, name="benchmark_exposure"),
        "turnover_series": pd.Series(turnover, index=curve_index, name="traded_notional"),
        "cost_series": pd.Series(costs, index=curve_index, name="cost_fraction"),
        "first_eligible_open_index": first_eligible_open,
        "first_eligible_open_date": str(raw.index[first_eligible_open].date()),
        "completed_open_to_open_holding_intervals": int(np.count_nonzero(exposure > 0.0)),
        "average_exposure": float(exposure.mean()),
        "exposure_transitions": int(np.count_nonzero(turnover)),
        "total_traded_notional": float(turnover.sum()),
        "total_cost_fraction": float(costs.sum()),
        "terminal_close_state_ignored": float(state_values[-1]),
    }


def metrics(returns: pd.Series) -> dict:
    values = returns.to_numpy(dtype=float)
    _finite_returns(values, "metric")
    if len(values) == 0:
        raise ValueError("metric return vector cannot be empty")
    wealth = np.cumprod(1.0 + values)
    if not np.isfinite(wealth).all() or (wealth <= 0.0).any():
        raise ValueError("invalid cumulative wealth")
    years = len(values) / PERIODS_PER_YEAR
    cagr = float(wealth[-1] ** (1.0 / years) - 1.0)
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    sharpe = float(np.mean(values) / std * math.sqrt(PERIODS_PER_YEAR)) if std > 0.0 else 0.0
    peaks = np.maximum.accumulate(np.r_[1.0, wealth])
    mdd = float(np.min(wealth / peaks[1:] - 1.0))
    return {"observations": int(len(values)), "cagr": cagr, "sharpe": sharpe,
            "max_drawdown": mdd, "total_return": float(wealth[-1] - 1.0)}


def _verify_freeze(freeze_path: Path, prereg_path: Path, runner_path: Path, tests_path: Path) -> dict:
    if not freeze_path.exists():
        raise RuntimeError("root GO freeze is missing")
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    if frozen.get("status") == "DATA_BLOCKED":
        raise DataBlockedError(frozen.get("data_gate_reason", "authoritative NYSE Arca session calendar is unavailable"))
    if frozen.get("status") != "GO":
        raise RuntimeError("root GO is required before reading market data")
    if frozen.get("candidate_id") != RUN_ID:
        raise RuntimeError("root GO freeze candidate ID does not match this runner")
    for key, path in (("preregistration_sha256", prereg_path),
                      ("runner_sha256", runner_path), ("test_sha256", tests_path)):
        expected = frozen.get(key)
        if not isinstance(expected, str) or expected != sha256(path):
            raise RuntimeError(f"root GO freeze hash mismatch for {key}")
    expected_data_hash = frozen.get("market_input_sha256")
    if not isinstance(expected_data_hash, str) or len(expected_data_hash) != 64:
        raise RuntimeError("root GO freeze must pin the exact SPY input SHA-256")
    calendar_value = frozen.get("calendar_path")
    calendar_source = frozen.get("calendar_source")
    expected_calendar_hash = frozen.get("calendar_sha256")
    if not isinstance(calendar_value, str) or not calendar_value:
        raise DataBlockedError("root GO requires an authoritative NYSE Arca session-calendar path")
    if not isinstance(calendar_source, str) or not calendar_source:
        raise DataBlockedError("root GO requires authoritative session-calendar provenance")
    if not isinstance(expected_calendar_hash, str) or len(expected_calendar_hash) != 64:
        raise DataBlockedError("root GO requires a pinned NYSE Arca session-calendar SHA-256")
    calendar_path = Path(calendar_value)
    if not calendar_path.is_absolute():
        calendar_path = REPO_ROOT / calendar_path
    if not calendar_path.is_file() or sha256(calendar_path) != expected_calendar_hash:
        raise DataBlockedError("pinned authoritative NYSE Arca session calendar is missing or hash-mismatched")
    frozen["_resolved_calendar_path"] = str(calendar_path)
    return frozen


def _write_curve(path: Path, curve: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    try:
        curve.to_csv(temporary, compression="gzip", index_label="date")
        with open(temporary, "rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def execute_attempt(
    *,
    freeze_path: Path = FREEZE,
    prereg_path: Path = PREREG,
    runner_path: Path | None = None,
    tests_path: Path | None = None,
    data_path: Path = DATA,
    attempts_path: Path = ATTEMPTS,
    manifest_path: Path = MANIFEST,
    results_path: Path = RESULTS,
    curve_path: Path = CURVE,
    reader: Callable[[Path], pd.DataFrame] = pd.read_parquet,
) -> dict:
    """Execute once only, requiring root GO and matching prereg/source/data hashes."""
    runner_path = runner_path or Path(__file__).resolve()
    tests_path = tests_path or HERE / "test_gen13_custom_trend.py"
    frozen = _verify_freeze(freeze_path, prereg_path, runner_path, tests_path)
    related = (manifest_path, results_path, curve_path)
    if attempts_path.exists() or any(path.exists() for path in related):
        raise RuntimeError("one-attempt budget already consumed; refusing overwrite or rerun")

    started = {"run_id": RUN_ID, "status": "STARTED", "market_values_opened": False,
               "preregistration_sha256": sha256(prereg_path), "runner_sha256": sha256(runner_path),
               "test_sha256": sha256(tests_path)}
    try:
        _create_attempt(attempts_path, started)
    except FileExistsError as exc:
        raise RuntimeError("one-attempt budget already consumed; refusing overwrite or rerun") from exc

    market_values_opened = False
    try:
        _write_json(manifest_path, started)
        actual_data_hash = sha256(data_path)
        if actual_data_hash != frozen["market_input_sha256"]:
            raise DataBlockedError("SPY input hash differs from the root GO freeze")
        read_started = {"run_id": RUN_ID, "status": "DATA_READ_STARTED", "market_values_opened": True,
                        "market_input_sha256": actual_data_hash}
        _append_event(attempts_path, read_started)
        _write_json(manifest_path, read_started)
        market_values_opened = True

        raw = reader(data_path)
        validate_session_calendar(raw.index, Path(frozen["_resolved_calendar_path"]))
        validate_prices(raw)
        adjusted = adjust_ohlc(raw)
        features = calculate_features(adjusted)
        valid = indicator_validity(features)
        states = build_state(features, valid)
        run = simulate_open_to_open(raw, states, valid, fee=FEE)
        curve = pd.DataFrame({
            "strategy_return": run["returns"],
            "gross_strategy_return": run["gross_returns"],
            "benchmark_return": run["benchmark_returns"],
            "strategy_equity": (1.0 + run["returns"]).cumprod(),
            "gross_strategy_equity": (1.0 + run["gross_returns"]).cumprod(),
            "benchmark_equity": (1.0 + run["benchmark_returns"]).cumprod(),
            "exposure": run["exposure"],
            "benchmark_exposure": run["benchmark_exposure"],
            "traded_notional": run["turnover_series"],
            "cost_fraction": run["cost_series"],
            "di_plus_close_t_minus_1": features["di_plus"].shift(1).reindex(run["returns"].index),
            "di_minus_close_t_minus_1": features["di_minus"].shift(1).reindex(run["returns"].index),
            "chop14_close_t_minus_1": features["chop14"].shift(1).reindex(run["returns"].index),
        })
        account_columns = ["strategy_return", "gross_strategy_return", "benchmark_return",
                           "strategy_equity", "gross_strategy_equity", "benchmark_equity",
                           "exposure", "benchmark_exposure", "traded_notional", "cost_fraction"]
        if curve[account_columns].isna().any().any() or not np.isfinite(curve[account_columns].to_numpy(dtype=float)).all():
            raise ValueError("curve accounting fields contain missing or non-finite values")
        if not curve.index.equals(run["benchmark_returns"].index) or not run["returns"].index.equals(run["benchmark_returns"].index):
            raise ValueError("strategy and benchmark curve dates do not match exactly")

        windows = {
            "full": (curve.index.min(), curve.index.max()),
            "2001_2016": (pd.Timestamp("2001-01-02"), pd.Timestamp("2016-12-30")),
            "2017_plus_contaminated": (pd.Timestamp("2017-01-03"), curve.index.max()),
        }
        report: dict[str, dict] = {}
        for name, (start_date, end_date) in windows.items():
            subset = curve.loc[start_date:end_date]
            if subset.empty:
                raise ValueError(f"required descriptive window is empty: {name}")
            strategy_metrics = metrics(subset["strategy_return"])
            benchmark_metrics = metrics(subset["benchmark_return"])
            report[name] = {
                "start": str(subset.index.min().date()), "end": str(subset.index.max().date()),
                "strategy_net": strategy_metrics,
                "strategy_gross": metrics(subset["gross_strategy_return"]),
                "benchmark_net": benchmark_metrics,
                "mean_exposure": float(subset["exposure"].mean()),
                "completed_holding_intervals": int((subset["exposure"] > 0.0).sum()),
                "traded_notional": float(subset["traded_notional"].sum()),
                "cost_fraction_sum": float(subset["cost_fraction"].sum()),
                "drawdown_scope": "window-only reporting baseline; portfolio path remains continuous",
                "cagr_exceeds_benchmark": strategy_metrics["cagr"] > benchmark_metrics["cagr"],
                "sharpe_exceeds_benchmark": strategy_metrics["sharpe"] > benchmark_metrics["sharpe"],
            }
        windows_pass = all(
            row["cagr_exceeds_benchmark"] and row["sharpe_exceeds_benchmark"]
            for row in report.values()
        )
        report["decision"] = {
            "status": "RETAIN_EXPLORATORY_LEAD" if windows_pass else "REJECT_FIXED_CANDIDATE",
            "rule": "net CAGR and net Sharpe must each exceed matched SPY buy-and-hold in every required display window",
            "confirmatory": False,
            "oos_claim": False,
            "statistical_significance_claim": False,
        }
        report["activity"] = {
            "first_eligible_open_index": run["first_eligible_open_index"],
            "first_eligible_open_date": run["first_eligible_open_date"],
            "average_exposure": run["average_exposure"],
            "exposure_transitions_including_entry_and_terminal_exit": run["exposure_transitions"],
            "completed_open_to_open_holding_intervals": run["completed_open_to_open_holding_intervals"],
            "total_traded_notional": run["total_traded_notional"],
            "total_cost_fraction": run["total_cost_fraction"],
            "fee_per_traded_notional": FEE,
            "entry_choppiness_threshold": ENTRY_CHOP,
            "exit_choppiness_threshold": EXIT_CHOP,
            "directional_period": PERIOD,
        }
        report["provenance"] = {
            "run_id": RUN_ID, "preregistration_sha256": sha256(prereg_path),
            "runner_sha256": sha256(runner_path), "test_sha256": sha256(tests_path),
            "market_input_sha256": actual_data_hash, "market_input_path": str(data_path),
            "row_count": int(len(raw)), "first_date": str(raw.index.min().date()),
            "last_date": str(raw.index.max().date()), "evidence_status": "exploratory historical screen; not untouched OOS",
        }
        _write_curve(curve_path, curve)
        _write_json(results_path, report)
        completed = {"run_id": RUN_ID, "status": report["decision"]["status"],
                     "market_values_opened": True, "results_sha256": sha256(results_path),
                     "curve_sha256": sha256(curve_path)}
        _append_event(attempts_path, completed)
        _write_json(manifest_path, {**completed, "results_path": str(results_path), "curve_path": str(curve_path),
                                    "provenance": report["provenance"]})
        return report
    except Exception as exc:
        failed = {"run_id": RUN_ID, "status": "FAILED", "market_values_opened": market_values_opened,
                  "error_type": type(exc).__name__, "error": str(exc)}
        _append_event(attempts_path, failed)
        _write_json(manifest_path, failed)
        raise


def main() -> None:
    report = execute_attempt()
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
