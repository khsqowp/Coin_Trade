"""One frozen adaptive selective-prediction M2 diagnostic.

The CLI is deliberately phase-separated: data preflight, forecast generation,
then outcome scoring. It is historical research only and never places orders.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import platform
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

MINUTE_MS = 60_000
HOUR_MS = 60 * MINUTE_MS
DAY_MS = 24 * HOUR_MS
HORIZON = 10
FIT_DAYS = 180
EMBARGO_DAYS = 28
TRAIN_GRID_MINUTES = 5
CALIBRATION_QUANTILE = 0.90
MIN_CALIBRATION_ANCHORS = 1_000
MIN_FIT_ROWS = 200_000
MIN_CLASS_ROWS = 5_000
FEE_BASE = 0.001
FEE_STRESS = 0.003
BOOTSTRAP_REPLICATES = 1_000
BOOTSTRAP_SEED = 20261121
RUN_ID = "adaptive-selective-m2-20261121-v1"
PREREG_PATH = Path(__file__).resolve().parents[2] / "docs/research/inventory/PREREG_ADAPTIVE_SELECTIVE_M2_20261121.md"
FUNDING_HELPER_SHA256 = "c1c4e2fd8a27a2a2d9ad430855d115682b9ca749bb15d87ce19e9fd736bf7a69"

SYMBOLS = (
    "AAVEUSDT", "ADAUSDT", "APTUSDT", "ARBUSDT", "ATOMUSDT", "AVAXUSDT",
    "BCHUSDT", "BNBUSDT", "BTCUSDT", "CRVUSDT", "DOGEUSDT", "DOTUSDT",
    "ENAUSDT", "ETCUSDT", "ETHUSDT", "FILUSDT", "HBARUSDT", "INJUSDT",
    "LINKUSDT", "LTCUSDT", "NEARUSDT", "OPUSDT", "POLUSDT", "RUNEUSDT",
    "SEIUSDT", "SOLUSDT", "SUIUSDT", "TIAUSDT", "TRXUSDT", "UNIUSDT",
    "WLDUSDT", "XRPUSDT",
)

FEATURE_COLUMNS = (
    "ret_1", "ret_3", "ret_5", "ret_10", "range_pct", "body_ratio",
    "upper_wick_ratio", "lower_wick_ratio", "atr14_pct", "rv20",
    "volume_z60", "taker_fraction_5",
)
LABEL_TO_CODE = {"UP_FIRST": 0, "DOWN_FIRST": 1, "NO_HIT": 2}
CODE_TO_LABEL = {value: key for key, value in LABEL_TO_CODE.items()}
REQUIRED_KLINE_COLUMNS = {
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume",
}
REQUIRED_MARK_COLUMNS = {"open_time", "open", "high", "low", "close"}
REQUIRED_FUNDING_COLUMNS = {"calc_time", "last_funding_rate", "funding_interval_hours"}
KLINE_TYPES = {"open_time": "int64", "close_time": "int64", "count": "int64",
               "open": "double", "high": "double", "low": "double", "close": "double",
               "volume": "double", "quote_volume": "double", "taker_buy_volume": "double",
               "taker_buy_quote_volume": "double"}
MARK_TYPES = {"open_time": "int64", "open": "double", "high": "double",
              "low": "double", "close": "double"}
FUNDING_TYPES = {"calc_time": "int64", "funding_interval_hours": "int64",
                 "last_funding_rate": "double"}


class DataInvalid(RuntimeError):
    """Raised when a preregistered data-integrity gate fails."""


def compute_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Compute the frozen trailing feature set and feature-ready mask."""
    required = {"open_time", "open", "high", "low", "close", "volume", "taker_buy_volume"}
    if missing := required - set(frame.columns):
        raise ValueError(f"missing feature columns: {sorted(missing)}")
    times = frame["open_time"].to_numpy(dtype=np.int64)
    if np.any(np.diff(times) <= 0):
        raise ValueError("open_time must be strictly increasing")

    o = frame["open"].to_numpy(dtype=float)
    h = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    c = frame["close"].to_numpy(dtype=float)
    volume = frame["volume"].to_numpy(dtype=float)
    taker = frame["taker_buy_volume"].to_numpy(dtype=float)
    previous_close = np.r_[np.nan, c[:-1]]
    true_range = np.maximum.reduce((h - low, np.abs(h - previous_close), np.abs(low - previous_close)))
    candle_range = h - low

    data: dict[str, Any] = {}
    log_close = np.log(c)
    for lag in (1, 3, 5, 10):
        data[f"ret_{lag}"] = log_close - np.roll(log_close, lag)
        data[f"ret_{lag}"][:lag] = np.nan
    data["range_pct"] = candle_range / c
    data["body_ratio"] = np.divide(c - o, candle_range, out=np.full_like(c, np.nan), where=candle_range != 0)
    data["upper_wick_ratio"] = np.divide(
        h - np.maximum(o, c), candle_range, out=np.full_like(c, np.nan), where=candle_range != 0
    )
    data["lower_wick_ratio"] = np.divide(
        np.minimum(o, c) - low, candle_range, out=np.full_like(c, np.nan), where=candle_range != 0
    )
    atr_abs = pd.Series(true_range).rolling(14, min_periods=14).mean().to_numpy()
    data["atr14_pct"] = atr_abs / c
    returns = pd.Series(log_close).diff()
    data["rv20"] = returns.rolling(20, min_periods=20).std(ddof=1).to_numpy()
    log_volume = np.log1p(volume)
    volume_series = pd.Series(log_volume)
    volume_mean = volume_series.rolling(60, min_periods=60).mean()
    volume_std = volume_series.rolling(60, min_periods=60).std(ddof=1)
    data["volume_z60"] = ((volume_series - volume_mean) / volume_std).to_numpy()
    taker_fraction = np.divide(
        taker, volume, out=np.full_like(volume, np.nan), where=volume > 0
    )
    data["taker_fraction_5"] = (
        pd.Series(taker_fraction).rolling(5, min_periods=5).mean().to_numpy()
    )

    features = pd.DataFrame(data, columns=FEATURE_COLUMNS)
    continuity = _rolling_minute_continuity(times, 60)
    # NaN is retained only where a frozen formula is undefined (for example,
    # zero candle range or zero volume). HistGradientBoosting handles NaN;
    # infinity is never a valid feature and therefore makes the row ineligible.
    ready = continuity & ~np.isinf(features.to_numpy(dtype=float)).any(axis=1)
    return features, ready


def _rolling_minute_continuity(times: np.ndarray, window: int) -> np.ndarray:
    """Require a complete minute grid across the full feature lookback."""
    result = np.zeros(len(times), dtype=bool)
    if len(times) < window:
        return result
    breaks = (np.diff(times) != MINUTE_MS).astype(np.int64)
    cumulative = np.r_[0, np.cumsum(breaks)]
    indices = np.arange(window - 1, len(times))
    result[indices] = cumulative[indices] == cumulative[indices - window + 1]
    return result


def label_first_touch(
    frame: pd.DataFrame, anchor_index: int, risk: float, horizon: int = HORIZON
) -> dict[str, Any]:
    """Label a next-open symmetric barrier path; same-bar dual touch is NO_HIT."""
    times = frame["open_time"].to_numpy(dtype=np.int64)
    entry_index = anchor_index + 1
    if entry_index >= len(frame) or times[entry_index] != times[anchor_index] + MINUTE_MS:
        return {"label": None, "status": "ENTRY_MISSING", "entry_index": None}
    entry = float(frame["open"].iloc[entry_index])
    if not math.isfinite(entry) or entry <= 0 or not math.isfinite(risk) or risk <= 0:
        return {"label": None, "status": "INVALID_ENTRY_OR_RISK", "entry_index": entry_index}
    upper, lower = entry + risk, entry - risk
    for offset in range(1, horizon + 1):
        index = anchor_index + offset
        if index >= len(frame) or times[index] != times[anchor_index] + offset * MINUTE_MS:
            return {"label": None, "status": "MISSING_PATH", "entry_index": entry_index}
        high, low = float(frame["high"].iloc[index]), float(frame["low"].iloc[index])
        hit_up, hit_down = high >= upper, low <= lower
        if hit_up and hit_down:
            return {"label": "NO_HIT", "status": "AMBIGUOUS_BOTH", "entry_index": entry_index,
                    "exit_index": index, "entry": entry, "upper": upper, "lower": lower}
        if hit_up:
            return {"label": "UP_FIRST", "status": "TARGET_SIDE_UP", "entry_index": entry_index,
                    "exit_index": index, "entry": entry, "upper": upper, "lower": lower}
        if hit_down:
            return {"label": "DOWN_FIRST", "status": "TARGET_SIDE_DOWN", "entry_index": entry_index,
                    "exit_index": index, "entry": entry, "upper": upper, "lower": lower}
    exit_index = anchor_index + horizon
    return {"label": "NO_HIT", "status": "TIMEOUT", "entry_index": entry_index,
            "exit_index": exit_index, "entry": entry, "upper": upper, "lower": lower}


def evaluate_trade(
    frame: pd.DataFrame,
    anchor_index: int,
    risk: float,
    side: str,
    funding: dict[str, np.ndarray],
    fee_rate: float,
) -> dict[str, Any]:
    """Score one issued forecast under the preregistered path/fill rules."""
    if side not in {"long", "short"}:
        raise ValueError("side must be long or short")
    if not math.isfinite(risk) or risk <= 0 or not math.isfinite(fee_rate) or fee_rate < 0:
        raise ValueError("risk must be positive and fee_rate non-negative")
    times = frame["open_time"].to_numpy(dtype=np.int64)
    entry_index = anchor_index + 1
    base = {"executed": False, "m2_hit": False, "status": "ENTRY_MISSING",
            "entry_index": None, "exit_index": None, "entry": None,
            "exit_price": None, "gross_return": 0.0, "funding_return": 0.0,
            "fee_return": 0.0, "net_return": 0.0}
    if (anchor_index < 0 or entry_index >= len(frame)
            or times[entry_index] != times[anchor_index] + MINUTE_MS):
        return base

    entry = float(frame["open"].iloc[entry_index])
    if not math.isfinite(entry) or entry <= 0:
        base["status"] = "INVALID_ENTRY"
        return base
    base.update(executed=True, entry_index=entry_index, entry=entry,
                fee_return=-fee_rate)
    target = entry + risk if side == "long" else entry - risk
    stop = entry - risk if side == "long" else entry + risk
    stop_sign = 1.0 if side == "long" else -1.0
    for offset in range(1, HORIZON + 1):
        index = anchor_index + offset
        if index >= len(frame) or times[index] != times[anchor_index] + offset * MINUTE_MS:
            raise DataInvalid("evaluation path has a missing post-entry candle")
        high = float(frame["high"].iloc[index])
        low = float(frame["low"].iloc[index])
        open_price = float(frame["open"].iloc[index])
        stop_hit = low <= stop if side == "long" else high >= stop
        target_hit = high >= target if side == "long" else low <= target
        if stop_hit:
            # A stop gap gets the worse of the stop price and the candle open.
            exit_price = min(stop, open_price) if side == "long" else max(stop, open_price)
            status = "AMBIGUOUS_BOTH" if target_hit else "STOP_FIRST"
            exit_index = index
            m2_hit = False
            break
        if target_hit:
            exit_price, status, exit_index, m2_hit = target, "TARGET_FIRST", index, True
            break
    else:
        exit_index = anchor_index + HORIZON
        exit_price = float(frame["close"].iloc[exit_index])
        status, m2_hit = "TIMEOUT", False

    exit_close_ms = int(times[exit_index] + MINUTE_MS - 1)
    gross = (1.0 if side == "long" else -1.0) * (exit_price - entry) / entry
    ft = np.asarray(funding["times"], dtype=np.int64)
    rates = np.asarray(funding["rates"], dtype=float)
    mark_open = np.asarray(funding["mark_open"], dtype=float)
    if not (len(ft) == len(rates) == len(mark_open)):
        raise DataInvalid("funding arrays have inconsistent lengths")
    first = int(np.searchsorted(ft, times[entry_index], side="right"))
    last = int(np.searchsorted(ft, exit_close_ms, side="right"))
    funding_return = float(np.sum(-stop_sign * rates[first:last] * mark_open[first:last] / entry))
    base.update(m2_hit=m2_hit, status=status, exit_index=exit_index,
                exit_price=float(exit_price), gross_return=float(gross),
                funding_return=funding_return, net_return=float(gross + funding_return - fee_rate))
    return base


def nearest_rank_quantile(values: list[float] | np.ndarray, quantile: float) -> float:
    """Return the 1-based ceil(q*n) nearest-rank statistic, retaining ties."""
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if len(array) == 0 or not 0 < quantile <= 1:
        raise ValueError("quantile requires finite values and 0 < q <= 1")
    rank = math.ceil(quantile * len(array))
    return float(np.partition(array, rank - 1)[rank - 1])


def select_direction(
    p_up: float, p_down: float, p_no_hit: float, threshold: float
) -> tuple[str, float] | None:
    """Select the strict directional class winner above a positive score threshold."""
    values = (p_up, p_down, p_no_hit)
    if not all(math.isfinite(value) for value in values):
        return None
    score = max(p_up, p_down) - p_no_hit
    if score <= 0 or score < threshold or p_up == p_down:
        return None
    if p_up > p_down and p_up > p_no_hit:
        return "long", score
    if p_down > p_up and p_down > p_no_hit:
        return "short", score
    return None


def refit_window(refit_ms: int) -> tuple[int, int]:
    """Return the frozen 180-day training interval ending 28 days before refit."""
    end_ms = refit_ms - EMBARGO_DAYS * DAY_MS
    return end_ms - FIT_DAYS * DAY_MS, end_ms


def global_nonoverlap(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose top-scoring simultaneous event, then enforce scheduled 10m windows."""
    by_anchor: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_anchor[int(event["anchor_ms"])].append(event)
    selected: list[dict[str, Any]] = []
    next_allowed = -1
    for anchor_ms in sorted(by_anchor):
        choices = sorted(by_anchor[anchor_ms], key=lambda row: (-float(row["score"]), row["symbol"]))
        winner = choices[0]
        scheduled_entry = int(winner["scheduled_entry_ms"])
        if scheduled_entry < next_allowed:
            continue
        selected.append(winner)
        next_allowed = scheduled_entry + HORIZON * MINUTE_MS
    return selected


def funding_minute_indices(mark_times: np.ndarray, funding_times: np.ndarray) -> np.ndarray:
    """Map settlement times <=1s after minute start to an exact mark candle."""
    mark_times = np.asarray(mark_times, dtype=np.int64)
    funding_times = np.asarray(funding_times, dtype=np.int64)
    offsets = funding_times % MINUTE_MS
    if np.any(offsets > 1_000):
        raise ValueError("funding timestamp is more than 1 second off the UTC minute grid")
    minute_times = funding_times - offsets
    indices = np.searchsorted(mark_times, minute_times)
    if np.any(indices >= len(mark_times)) or not np.array_equal(mark_times[indices], minute_times):
        raise ValueError("funding event lacks an exact corresponding mark-price minute")
    return indices


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    """Wilson score interval for a binomial target-first proportion."""
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return center - margin, center + margin


def _ym_range(start_month: str, end_month: str) -> list[str]:
    """Inclusive YYYY-MM range."""
    start_year, start_number = map(int, start_month.split("-"))
    end_year, end_number = map(int, end_month.split("-"))
    result = []
    year, month = start_year, start_number
    while (year, month) <= (end_year, end_number):
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_state(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "inode": stat.st_ino}


def _expected_month_grid(month: str) -> np.ndarray:
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    next_month = datetime(start.year + (start.month == 12),
                          1 if start.month == 12 else start.month + 1, 1,
                          tzinfo=timezone.utc)
    left = int(start.timestamp() * 1000)
    right = int(next_month.timestamp() * 1000)
    return np.arange(left, right, MINUTE_MS, dtype=np.int64)


def _record_file(path: Path, kind: str, symbol: str, month: str,
                 table: Any, records: list[dict[str, Any]],
                 state_before: dict[str, int], hash_before: str) -> None:
    state_after = _file_state(path)
    hash_after = _sha256(path)
    if state_before != state_after or hash_before != hash_after:
        raise DataInvalid(f"input changed while reading: {path}")
    records.append({"kind": kind, "symbol": symbol, "month": month,
                    **state_before, "sha256": hash_before,
                    "schema": [{"name": field.name, "type": str(field.type)}
                               for field in table.schema], "rows": table.num_rows})


def _validate_schema_types(schema: Any, expected: dict[str, str], context: str) -> None:
    actual = {field.name: str(field.type) for field in schema}
    mismatched = {name: {"expected": dtype, "actual": actual.get(name)}
                  for name, dtype in expected.items() if actual.get(name) != dtype}
    if mismatched:
        raise DataInvalid(f"{context} schema dtype mismatch: {mismatched}")


def _validate_kline_table(table: Any, symbol: str, month: str,
                          require_full_grid: bool) -> pd.DataFrame:
    names = set(table.schema.names)
    if missing := REQUIRED_KLINE_COLUMNS - names:
        raise DataInvalid(f"{symbol}/{month} missing kline columns: {sorted(missing)}")
    _validate_schema_types(table.schema, KLINE_TYPES, f"{symbol}/{month} contract kline")
    frame = table.select(sorted(REQUIRED_KLINE_COLUMNS)).to_pandas()
    times = frame["open_time"].to_numpy(dtype=np.int64)
    if len(times) == 0 or np.any(np.diff(times) <= 0) or np.any(times % MINUTE_MS != 0):
        raise DataInvalid(f"{symbol}/{month} timestamps are empty, duplicate, unsorted, or off-grid")
    expected = _expected_month_grid(month)
    if np.any(times < expected[0]) or np.any(times >= expected[-1] + MINUTE_MS):
        raise DataInvalid(f"{symbol}/{month} contains timestamps outside its UTC month")
    if require_full_grid and not np.array_equal(times, expected):
        raise DataInvalid(f"{symbol}/{month} does not have the complete expected minute grid")
    o, h = frame["open"].to_numpy(float), frame["high"].to_numpy(float)
    low, c = frame["low"].to_numpy(float), frame["close"].to_numpy(float)
    volume = frame["volume"].to_numpy(float)
    taker = frame["taker_buy_volume"].to_numpy(float)
    values = np.column_stack((o, h, low, c, volume, taker))
    if not np.isfinite(values).all() or np.any(values[:, :4] <= 0) or np.any(volume < 0):
        raise DataInvalid(f"{symbol}/{month} contains non-finite or invalid OHLCV")
    if np.any(h < np.maximum(o, c)) or np.any(low > np.minimum(o, c)) or np.any(h < low):
        raise DataInvalid(f"{symbol}/{month} violates OHLC envelope")
    if np.any(taker < 0) or np.any(taker > volume):
        raise DataInvalid(f"{symbol}/{month} taker-buy volume is outside [0, volume]")
    close_time = frame["close_time"].to_numpy(dtype=np.int64)
    if np.any(close_time - times != MINUTE_MS - 1):
        raise DataInvalid(f"{symbol}/{month} has invalid candle close times")
    return frame


def _load_kline_month(root: Path, symbol: str, month: str,
                      records: list[dict[str, Any]], require_full_grid: bool) -> pd.DataFrame:
    path = root / "um_klines_1m" / symbol / f"{month}.parquet"
    if not path.is_file():
        raise DataInvalid(f"missing required kline file: {path}")
    before = _file_state(path)
    hash_before = _sha256(path)
    table = pq.read_table(path)
    frame = _validate_kline_table(table, symbol, month, require_full_grid)
    _record_file(path, "um_klines_1m", symbol, month, table, records, before, hash_before)
    return frame


def _validate_mark_and_funding(
    root: Path, symbol: str, months: list[str],
    contract_times: np.ndarray, records: list[dict[str, Any]],
) -> dict[str, np.ndarray]:
    mark_frames = []
    funding_frames = []
    for month in months:
        mark_path = root / "um_markPriceKlines_1m" / symbol / f"{month}.parquet"
        funding_path = root / "um_fundingRate" / symbol / f"{month}.parquet"
        for path in (mark_path, funding_path):
            if not path.is_file():
                raise DataInvalid(f"missing required settlement file: {path}")
        before, hash_before = _file_state(mark_path), _sha256(mark_path)
        mark_table = pq.read_table(mark_path)
        if missing := REQUIRED_MARK_COLUMNS - set(mark_table.schema.names):
            raise DataInvalid(f"{symbol}/{month} missing mark columns: {sorted(missing)}")
        _validate_schema_types(mark_table.schema, MARK_TYPES, f"{symbol}/{month} mark kline")
        mark = mark_table.select(sorted(REQUIRED_MARK_COLUMNS)).to_pandas()
        mark_times = mark["open_time"].to_numpy(np.int64)
        mark_open = mark["open"].to_numpy(float)
        if not np.array_equal(mark_times, _expected_month_grid(month)):
            raise DataInvalid(f"{symbol}/{month} mark grid is incomplete or misaligned")
        if not np.isfinite(mark_open).all() or np.any(mark_open <= 0):
            raise DataInvalid(f"{symbol}/{month} mark open is invalid")
        _record_file(mark_path, "um_markPriceKlines_1m", symbol, month,
                     mark_table, records, before, hash_before)

        before, hash_before = _file_state(funding_path), _sha256(funding_path)
        funding_table = pq.read_table(funding_path)
        if missing := REQUIRED_FUNDING_COLUMNS - set(funding_table.schema.names):
            raise DataInvalid(f"{symbol}/{month} missing funding columns: {sorted(missing)}")
        _validate_schema_types(funding_table.schema, FUNDING_TYPES, f"{symbol}/{month} funding")
        funding = funding_table.select(sorted(REQUIRED_FUNDING_COLUMNS)).to_pandas()
        ft = funding["calc_time"].to_numpy(np.int64)
        rates = funding["last_funding_rate"].to_numpy(float)
        intervals = funding["funding_interval_hours"].to_numpy(np.int64)
        if not len(ft) or np.any(np.diff(ft) <= 0) or not np.isfinite(rates).all() or np.any(intervals <= 0):
            raise DataInvalid(f"{symbol}/{month} funding timestamps/rates/intervals are invalid")
        if np.any(ft < _expected_month_grid(month)[0]) or np.any(ft >= _expected_month_grid(month)[-1] + MINUTE_MS):
            raise DataInvalid(f"{symbol}/{month} funding event outside UTC month")
        funding_frames.append(funding)
        _record_file(funding_path, "um_fundingRate", symbol, month,
                     funding_table, records, before, hash_before)
        mark_frames.append(mark)

    mark_all = pd.concat(mark_frames, ignore_index=True).sort_values("open_time")
    funding_all = pd.concat(funding_frames, ignore_index=True).sort_values("calc_time")
    mt = mark_all["open_time"].to_numpy(np.int64)
    mo = mark_all["open"].to_numpy(float)
    ft = funding_all["calc_time"].to_numpy(np.int64)
    fr = funding_all["last_funding_rate"].to_numpy(float)
    fi = funding_all["funding_interval_hours"].to_numpy(np.int64)
    if np.any(np.diff(ft) <= 0):
        raise DataInvalid(f"{symbol} funding timestamps duplicate across month boundary")
    if len(ft) > 1:
        deltas = np.diff(ft)
        expected_a = fi[:-1] * HOUR_MS
        expected_b = fi[1:] * HOUR_MS
        if np.any(np.minimum(np.abs(deltas - expected_a), np.abs(deltas - expected_b)) > 1_000):
            raise DataInvalid(f"{symbol} funding interval differs from declared schedule")
    indices = funding_minute_indices(mt, ft)
    if len(contract_times) and not np.array_equal(mt, contract_times):
        raise DataInvalid(f"{symbol} mark and contract minute grids differ")
    return {"times": ft, "rates": fr, "mark_open": mo[indices]}


def _input_months() -> tuple[list[str], list[str]]:
    return _ym_range("2025-10", "2026-09"), _ym_range("2026-07", "2026-09")


def audit_inputs(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Hash and validate every frozen input without computing candidate outcomes."""
    records: list[dict[str, Any]] = []
    series: dict[str, dict[str, Any]] = {}
    price_months, settlement_months = _input_months()
    eval_left = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    eval_right = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
    for symbol in SYMBOLS:
        frames = []
        for month in price_months:
            full_grid = month in settlement_months
            frames.append(_load_kline_month(root, symbol, month, records, full_grid))
        frame = pd.concat(frames, ignore_index=True).sort_values("open_time").reset_index(drop=True)
        times = frame["open_time"].to_numpy(np.int64)
        if np.any(np.diff(times) <= 0):
            raise DataInvalid(f"{symbol} duplicate or unsorted timestamps across month files")
        eval_mask = (times >= eval_left) & (times < eval_right)
        expected_eval = np.arange(eval_left, eval_right, MINUTE_MS, dtype=np.int64)
        if not np.array_equal(times[eval_mask], expected_eval):
            raise DataInvalid(f"{symbol} evaluation interval has a missing/extra minute")
        features, ready = compute_features(frame)
        atr_abs = features["atr14_pct"].to_numpy(float) * frame["close"].to_numpy(float)
        settle = _validate_mark_and_funding(root, symbol, settlement_months,
                                            expected_eval, records)
        series[symbol] = {
            "frame": frame, "times": times,
            "features": features.to_numpy(dtype=np.float32), "ready": ready,
            "atr": atr_abs.astype(np.float32), "funding": settle,
        }
    records.sort(key=lambda row: (row["kind"], row["symbol"], row["month"]))
    digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {
        "run_id": RUN_ID, "symbols": list(SYMBOLS), "evaluation": [
            "2026-07-01T00:00:00Z", "2026-10-01T00:00:00Z"],
        "records": records, "records_sha256": digest,
        "prereg_sha256": _sha256(PREREG_PATH),
        "code_sha256": _sha256(Path(__file__)),
        "tests_sha256": _sha256(Path(__file__).resolve().parents[2] / "tests/test_adaptive_selective_m2_probe.py"),
        "funding_helper_sha256": _sha256(Path(__file__).with_name("mark_deviation_m2_probe.py")),
        "runtime": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                    "numpy": np.__version__, "pandas": pd.__version__,
                    "pyarrow": pa.__version__},
    }
    if manifest["funding_helper_sha256"] != FUNDING_HELPER_SHA256:
        raise DataInvalid("pinned funding mapping helper changed")
    return series, manifest


def _classifier() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        loss="log_loss", learning_rate=0.05, max_iter=100,
        max_leaf_nodes=7, max_depth=None, min_samples_leaf=20,
        l2_regularization=1.0, max_bins=255, max_features=1.0,
        early_stopping=False, random_state=20261121,
    )


def _fit_arrays(series: dict[str, dict[str, Any]], fit_start: int,
                fit_end: int) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    feature_parts, label_parts, anchor_parts, symbol_parts = [], [], [], []
    class_counts = {"UP_FIRST": 0, "DOWN_FIRST": 0, "NO_HIT": 0}
    symbol_order = {symbol: index for index, symbol in enumerate(sorted(SYMBOLS))}
    for symbol in SYMBOLS:
        item = series[symbol]
        times = item["times"]
        mask = ((times >= fit_start) & (times < fit_end)
                & (times // MINUTE_MS % TRAIN_GRID_MINUTES == 0) & item["ready"])
        indices = np.flatnonzero(mask)
        codes, valid = _vectorized_labels(item["frame"], indices, item["atr"], fit_end)
        indices, codes = indices[valid], codes[valid]
        if len(indices):
            feature_parts.append(item["features"][indices])
            label_parts.append(codes)
            anchor_parts.append(times[indices])
            symbol_parts.append(np.full(len(indices), symbol_order[symbol], dtype=np.int8))
            for code, label in CODE_TO_LABEL.items():
                class_counts[label] += int(np.sum(codes == code))
    if not feature_parts:
        return np.empty((0, len(FEATURE_COLUMNS)), np.float32), np.empty(0, np.int8), class_counts
    x, y = np.concatenate(feature_parts), np.concatenate(label_parts)
    anchors, symbols = np.concatenate(anchor_parts), np.concatenate(symbol_parts)
    order = np.lexsort((symbols, anchors))
    return x[order], y[order], class_counts


def _vectorized_labels(frame: pd.DataFrame, indices: np.ndarray,
                       atr: np.ndarray, cutoff_ms: int) -> tuple[np.ndarray, np.ndarray]:
    """Create causal training labels only for paths resolved before cutoff."""
    times = frame["open_time"].to_numpy(np.int64)
    max_index = len(times) - HORIZON - 1
    in_bounds = (indices >= 0) & (indices <= max_index)
    candidates = indices[in_bounds]
    valid = np.isfinite(atr[candidates]) & (atr[candidates] > 0)
    valid &= times[candidates] + (HORIZON + 1) * MINUTE_MS < cutoff_ms
    for offset in range(1, HORIZON + 1):
        valid &= times[candidates + offset] == times[candidates] + offset * MINUTE_MS
    entry = frame["open"].to_numpy(float)[candidates + 1]
    valid &= np.isfinite(entry) & (entry > 0)
    labels = np.full(len(candidates), LABEL_TO_CODE["NO_HIT"], dtype=np.int8)
    unresolved = valid.copy()
    upper, lower = entry + atr[candidates], entry - atr[candidates]
    highs = frame["high"].to_numpy(float)
    lows = frame["low"].to_numpy(float)
    for offset in range(1, HORIZON + 1):
        hit_up = highs[candidates + offset] >= upper
        hit_down = lows[candidates + offset] <= lower
        first = unresolved & (hit_up | hit_down)
        labels[first & hit_up & ~hit_down] = LABEL_TO_CODE["UP_FIRST"]
        labels[first & hit_down & ~hit_up] = LABEL_TO_CODE["DOWN_FIRST"]
        unresolved[first] = False
    output = np.full(len(indices), LABEL_TO_CODE["NO_HIT"], dtype=np.int8)
    output[in_bounds] = labels
    valid_output = np.zeros(len(indices), dtype=bool)
    valid_output[in_bounds] = valid
    return output, valid_output


def _class_scores(model: HistGradientBoostingClassifier, features: np.ndarray) -> np.ndarray:
    probabilities = model.predict_proba(features)
    output = np.full((len(features), 3), np.nan, dtype=np.float64)
    for column, label_code in enumerate(model.classes_):
        output[:, int(label_code)] = probabilities[:, column]
    return output


def _utc_ms(text: str) -> int:
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)


def _atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _assert_run_phase(run_dir: Path, required: Path, outputs: list[str]) -> None:
    if not required.is_file():
        raise DataInvalid(f"required prior phase artifact is missing: {required}")
    existing = [name for name in outputs if (run_dir / name).exists()]
    if existing:
        raise DataInvalid(f"refusing to overwrite phase artifacts: {existing}")


def _verify_forecast_seal(run_dir: Path) -> dict[str, Any]:
    """Verify the prediction ledger and all non-market freezes before loading prices."""
    manifest_path = run_dir / "forecast_manifest.json"
    ledger_path = run_dir / "forecasts.jsonl"
    score_ledger_path = run_dir / "prequential_scores.jsonl.gz"
    if not manifest_path.is_file() or not ledger_path.is_file() or not score_ledger_path.is_file():
        raise DataInvalid("sealed forecast manifest or required ledgers are missing")
    frozen = json.loads(manifest_path.read_text(encoding="utf-8"))
    if frozen.get("status") != "FORECASTS_SEALED_NO_OUTCOMES":
        raise DataInvalid("forecast artifact is not sealed for scoring")
    if _sha256(ledger_path) != frozen.get("ledger_sha256"):
        raise DataInvalid("forecast ledger hash differs from sealed forecast manifest")
    if _sha256(score_ledger_path) != frozen.get("prequential_score_ledger_sha256"):
        raise DataInvalid("prequential score ledger hash differs from sealed forecast manifest")
    expected_hashes = {
        "prereg_sha256": _sha256(PREREG_PATH),
        "code_sha256": _sha256(Path(__file__)),
        "tests_sha256": _sha256(Path(__file__).resolve().parents[2] / "tests/test_adaptive_selective_m2_probe.py"),
    }
    if any(frozen.get(key) != value for key, value in expected_hashes.items()):
        raise DataInvalid("current preregistration/code/tests differ from sealed forecast")
    line_count = sum(1 for line in ledger_path.open("rb") if line.strip())
    if line_count != frozen.get("issued"):
        raise DataInvalid("forecast ledger row count differs from sealed count")
    with gzip.open(score_ledger_path, "rt", encoding="utf-8") as stream:
        score_count = sum(1 for line in stream if line.strip())
    if score_count != frozen.get("prequential_score_rows"):
        raise DataInvalid("prequential score ledger row count differs from sealed count")
    return frozen


def _weekly_dates(start_ms: int, end_ms: int) -> list[int]:
    return list(range(start_ms, end_ms, 7 * DAY_MS))


def _fit_model(series: dict[str, dict[str, Any]], refit_ms: int) -> tuple[Any | None, dict[str, Any]]:
    fit_start, fit_end = refit_window(refit_ms)
    x, y, counts = _fit_arrays(series, fit_start, fit_end)
    ready = len(y) >= MIN_FIT_ROWS and all(counts[name] >= MIN_CLASS_ROWS for name in counts)
    audit = {"refit_ms": refit_ms, "fit_start_ms": fit_start, "fit_end_ms": fit_end,
             "fit_rows": len(y), "class_rows": counts, "fit_eligible": ready}
    if not ready:
        return None, audit
    model = _classifier()
    model.fit(x, y)
    audit["estimator_params"] = model.get_params(deep=False)
    return model, audit


def _score_week(series: dict[str, dict[str, Any]], model: Any,
                left_ms: int, right_ms: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[float], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    ready_counts: dict[str, int] = {}
    for symbol in SYMBOLS:
        item = series[symbol]
        times = item["times"]
        indices = np.flatnonzero((times >= left_ms) & (times < right_ms) & item["ready"])
        if left_ms >= _utc_ms("2026-07-01T00:00:00Z"):
            indices = indices[times[indices] + (HORIZON + 1) * MINUTE_MS < _utc_ms("2026-10-01T00:00:00Z")]
        ready_counts[symbol] = len(indices)
        if model is None or not len(indices):
            continue
        class_scores = _class_scores(model, item["features"][indices])
        batch_scores = np.maximum(class_scores[:, 0], class_scores[:, 1]) - class_scores[:, 2]
        scores.extend(batch_scores[np.isfinite(batch_scores)].tolist())
        score_rows.extend({"symbol": symbol, "anchor_ms": int(times[index]),
                           "p_up": float(values[0]), "p_down": float(values[1]),
                           "p_no_hit": float(values[2]), "selective_score": float(score)}
                          for index, values, score in zip(indices, class_scores, batch_scores)
                          if np.isfinite(values).all() and math.isfinite(float(score)))
        rows.extend({"symbol": symbol, "anchor_ms": int(times[index]),
                     "side": side, "score": float(score),
                     "scheduled_entry_ms": int(times[index] + MINUTE_MS)}
                    for index, values in zip(indices, class_scores)
                    if (choice := select_direction(*values, threshold=-math.inf)) is not None
                    for side, score in [choice])
    return rows, score_rows, scores, ready_counts


def forecast_phase(series: dict[str, dict[str, Any]], manifest: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Create and seal forecasts without computing any evaluation outcomes."""
    preflight_path = run_dir / "preflight.json"
    _assert_run_phase(run_dir, preflight_path, ["forecasts.jsonl", "forecast_manifest.json",
                                                "prequential_scores.jsonl.gz",
                                                "prequential_scores.jsonl.gz.tmp"])
    saved = json.loads(preflight_path.read_text(encoding="utf-8"))
    freeze_fields = ("records_sha256", "prereg_sha256", "code_sha256", "tests_sha256")
    if any(saved.get(key) != manifest.get(key) for key in freeze_fields):
        raise DataInvalid("current inputs/preregistration/code/tests differ from frozen preflight")

    eval_left = _utc_ms("2026-07-01T00:00:00Z")
    eval_right = _utc_ms("2026-10-01T00:00:00Z")
    calibration_left = eval_left - 28 * DAY_MS
    replay_left = calibration_left
    week_starts = _weekly_dates(replay_left, eval_right)
    history: list[tuple[int, list[float]]] = []
    issued: list[dict[str, Any]] = []
    weekly: list[dict[str, Any]] = []
    score_path = run_dir / "prequential_scores.jsonl.gz"
    score_tmp = run_dir / "prequential_scores.jsonl.gz.tmp"
    score_count = 0

    with gzip.open(score_tmp, "wt", encoding="utf-8", newline="", compresslevel=6) as score_stream:
        for refit_ms in week_starts:
            model, fit_audit = _fit_model(series, refit_ms)
            block_end = min(refit_ms + 7 * DAY_MS, eval_right)
            rows, score_rows, raw_scores, ready_counts = _score_week(series, model, refit_ms, block_end)
            threshold = None
            is_eval = refit_ms >= eval_left
            if is_eval:
                calibration_scores = [score for stamp, batch in history
                                      if stamp >= refit_ms - 28 * DAY_MS for score in batch]
                if len(calibration_scores) >= MIN_CALIBRATION_ANCHORS:
                    threshold = nearest_rank_quantile(calibration_scores, CALIBRATION_QUANTILE)
                    issued.extend({**row, "week_start_ms": refit_ms}
                                  for row in rows if row["score"] >= threshold)
            candidates = {(row["symbol"], row["anchor_ms"]): row for row in rows}
            for row in sorted(score_rows, key=lambda item: (item["anchor_ms"], item["symbol"])):
                candidate = candidates.get((row["symbol"], row["anchor_ms"]))
                emit = bool(is_eval and threshold is not None and candidate is not None
                            and candidate["score"] >= threshold)
                record = {**row, "refit_ms": refit_ms,
                          "period": "evaluation" if is_eval else "calibration",
                          "threshold": threshold,
                          "side": candidate["side"] if emit else None,
                          "issued": emit}
                score_stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                score_count += 1
            weekly.append({**fit_audit, "week_end_ms": block_end,
                           "feature_ready_by_symbol": ready_counts,
                           "feature_ready_total": sum(ready_counts.values()),
                           "score_count": len(raw_scores),
                           "score_sha256": hashlib.sha256(np.asarray(raw_scores, dtype="<f8").tobytes()).hexdigest(),
                           "calibration_n": (len(calibration_scores) if is_eval and threshold is not None else 0),
                           "threshold": threshold, "issued": sum(
                               row.get("week_start_ms") == refit_ms for row in issued)})
            history.append((refit_ms, raw_scores))
            history = history[-4:]
    score_tmp.replace(score_path)
    score_sha = _sha256(score_path)

    ledger_path = run_dir / "forecasts.jsonl"
    payload = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                      for row in sorted(issued, key=lambda row: (row["anchor_ms"], row["symbol"])))
    ledger_path.write_text(payload, encoding="utf-8")
    ledger_sha = _sha256(ledger_path)
    result = {"run_id": RUN_ID, "status": "FORECASTS_SEALED_NO_OUTCOMES",
              "prereg_sha256": manifest["prereg_sha256"],
              "records_sha256": manifest["records_sha256"],
              "code_sha256": manifest["code_sha256"],
              "tests_sha256": manifest["tests_sha256"],
              "ledger_sha256": ledger_sha, "issued": len(issued),
              "prequential_score_ledger_sha256": score_sha,
              "prequential_score_rows": score_count,
              "weekly": weekly, "symbols": list(SYMBOLS),
              "evaluation": ["2026-07-01T00:00:00Z", "2026-10-01T00:00:00Z"]}
    _atomic_json(run_dir / "forecast_manifest.json", result)
    return result


def _digest_random_side(symbol: str, anchor_ms: int) -> str:
    digest = hashlib.sha256(f"20261121|{symbol}|{anchor_ms}".encode()).digest()
    return "long" if digest[0] & 0x80 else "short"


def _trade_set_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    hits = sum(bool(row["m2_hit"]) for row in rows)
    net10 = [float(row["net_10bp"]) for row in rows]
    net30 = [float(row["net_30bp"]) for row in rows]
    interval = wilson_interval(hits, count)
    return {"n": count, "m2_hits": hits, "m2": hits / count if count else None,
            "wilson95": list(interval) if interval else None,
            "executed": sum(bool(row["executed"]) for row in rows),
            "entry_missing": sum(row["status"] == "ENTRY_MISSING" for row in rows),
            "mean_net_10bp": statistics.fmean(net10) if net10 else None,
            "mean_net_30bp": statistics.fmean(net30) if net30 else None,
            "mean_net_10bp_executed": statistics.fmean(
                [row["net_10bp"] for row in rows if row["executed"]]) if any(row["executed"] for row in rows) else None,
            "mean_net_30bp_executed": statistics.fmean(
                [row["net_30bp"] for row in rows if row["executed"]]) if any(row["executed"] for row in rows) else None}


def score_phase(series: dict[str, dict[str, Any]], manifest: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Open outcome paths only after the forecast ledger is immutable and verified."""
    forecast_path = run_dir / "forecast_manifest.json"
    ledger_path = run_dir / "forecasts.jsonl"
    _assert_run_phase(run_dir, forecast_path, ["scores.jsonl", "summary.json", "by_symbol.csv", "report.md"])
    forecast_manifest = _verify_forecast_seal(run_dir)
    for key in ("records_sha256", "prereg_sha256", "code_sha256", "tests_sha256"):
        if forecast_manifest.get(key) != manifest.get(key):
            raise DataInvalid(f"score {key} differs from forecast freeze")
    issued = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line]
    if len(issued) != forecast_manifest.get("issued"):
        raise DataInvalid("forecast ledger row count differs from sealed count")

    evaluated: list[dict[str, Any]] = []
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    momentum_rows: list[dict[str, Any]] = []
    random_rows: list[dict[str, Any]] = []
    no_signal_rows: list[dict[str, Any]] = []
    expiry_correct = 0
    expiry_missing = 0
    for event in issued:
        symbol = event["symbol"]
        item = series[symbol]
        frame, times = item["frame"], item["times"]
        anchor_index = int(np.searchsorted(times, int(event["anchor_ms"])))
        if anchor_index >= len(times) or int(times[anchor_index]) != int(event["anchor_ms"]):
            raise DataInvalid("forecast anchor not found in frozen candle series")
        atr = float(item["atr"][anchor_index])
        if not math.isfinite(atr) or atr <= 0:
            raise DataInvalid("issued forecast lacks its frozen ATR risk distance")
        side = event["side"]
        base = evaluate_trade(frame, anchor_index, atr, side, item["funding"], FEE_BASE)
        stress = evaluate_trade(frame, anchor_index, atr, side, item["funding"], FEE_STRESS)
        score_row = {**event, **base, "net_10bp": base["net_return"],
                     "net_30bp": stress["net_return"]}
        evaluated.append(score_row)
        by_symbol[symbol].append(score_row)

        entry_idx = anchor_index + 1
        if entry_idx >= len(times) or times[entry_idx] != times[anchor_index] + MINUTE_MS:
            expiry_missing += 1
        else:
            expiry_index = anchor_index + HORIZON
            anchor_close = float(frame["close"].iloc[anchor_index])
            expiry_close = float(frame["close"].iloc[expiry_index])
            move = expiry_close - anchor_close
            expiry_correct += int((move > 0 and side == "long") or (move < 0 and side == "short"))

        prior = max(0, anchor_index - 10)
        momentum = float(frame["close"].iloc[anchor_index] - frame["close"].iloc[prior])
        momentum_side = "long" if momentum > 0 else "short" if momentum < 0 else None
        if momentum_side:
            m = evaluate_trade(frame, anchor_index, atr, momentum_side, item["funding"], FEE_BASE)
            m30 = evaluate_trade(frame, anchor_index, atr, momentum_side, item["funding"], FEE_STRESS)
            momentum_rows.append({"m2_hit": m["m2_hit"], "executed": m["executed"],
                                  "status": m["status"], "net_10bp": m["net_return"],
                                  "net_30bp": m30["net_return"]})
        else:
            momentum_rows.append({"m2_hit": False, "executed": False,
                                  "status": "ZERO_MOMENTUM_NO_SIDE", "net_10bp": 0.0,
                                  "net_30bp": 0.0})
        random_side = _digest_random_side(symbol, int(event["anchor_ms"]))
        rr = evaluate_trade(frame, anchor_index, atr, random_side, item["funding"], FEE_BASE)
        rr30 = evaluate_trade(frame, anchor_index, atr, random_side, item["funding"], FEE_STRESS)
        random_rows.append({"m2_hit": rr["m2_hit"], "executed": rr["executed"],
                            "status": rr["status"], "net_10bp": rr["net_return"],
                            "net_30bp": rr30["net_return"]})
        no_signal_rows.append({"m2_hit": False, "executed": False, "status": "NO_SIGNAL",
                               "net_10bp": 0.0, "net_30bp": 0.0})

    selected_global = global_nonoverlap(issued)
    selected_keys = {(row["symbol"], row["anchor_ms"]) for row in selected_global}
    global_rows = [row for row in evaluated if (row["symbol"], row["anchor_ms"]) in selected_keys]
    per_symbol_nonoverlap: dict[str, list[dict[str, Any]]] = {}
    for symbol in SYMBOLS:
        selected = global_nonoverlap(by_symbol[symbol])
        keys = {(row["symbol"], row["anchor_ms"]) for row in selected}
        per_symbol_nonoverlap[symbol] = [row for row in by_symbol[symbol]
                                         if (row["symbol"], row["anchor_ms"]) in keys]

    feature_ready_total = sum(sum(week["feature_ready_by_symbol"].values())
                              for week in forecast_manifest["weekly"]
                              if week["refit_ms"] >= _utc_ms("2026-07-01T00:00:00Z"))
    # The final weekly block can be shorter; count its actual evaluation anchors from the saved ledger's
    # model-week metadata only for issued rows. The forecast artifact records ready counts for full blocks.
    eval_days = 92
    bootstrap = _bootstrap_summary(evaluated, eval_days)
    by_symbol_summary = {symbol: {"all": _trade_set_metrics(by_symbol[symbol]),
                                  "nonoverlap": _trade_set_metrics(per_symbol_nonoverlap[symbol])}
                         for symbol in SYMBOLS}
    baseline_summary = {"same_event_momentum": _trade_set_metrics(momentum_rows),
                        "deterministic_random": _trade_set_metrics(random_rows),
                        "no_signal": _trade_set_metrics(no_signal_rows)}
    main = _trade_set_metrics(evaluated)
    global_summary = _trade_set_metrics(global_rows)
    coverage = len(issued) / feature_ready_total if feature_ready_total else 0.0
    active_symbols = sum(bool(by_symbol[symbol]) for symbol in SYMBOLS)
    gates = {
        "m2_at_least_80pct": main["m2"] is not None and main["m2"] >= 0.80,
        "issued_n_at_least_200": main["n"] >= 200,
        "global_nonoverlap_n_at_least_200": global_summary["n"] >= 200,
        "at_least_20_symbols": active_symbols >= 20,
        "coverage_at_least_10pct": coverage >= 0.10,
        "wilson_lower_above_momentum": bool(main["wilson95"] and baseline_summary["same_event_momentum"]["m2"] is not None
                                              and main["wilson95"][0] > baseline_summary["same_event_momentum"]["m2"]),
        "positive_net_10bp": main["mean_net_10bp"] is not None and main["mean_net_10bp"] > 0,
        "positive_net_30bp": main["mean_net_30bp"] is not None and main["mean_net_30bp"] > 0,
    }
    verdict = "PASS_HISTORICAL_DIAGNOSTIC_GATES" if all(gates.values()) else "REJECT_HISTORICAL_DIAGNOSTIC"
    summary = {"run_id": RUN_ID, "status": "SCORED_HISTORICAL_EXPOSED_NOT_OOS",
               "verdict": verdict, "prereg_sha256": manifest["prereg_sha256"],
               "records_sha256": manifest["records_sha256"],
               "code_sha256": manifest["code_sha256"],
               "tests_sha256": manifest["tests_sha256"],
               "forecast_ledger_sha256": forecast_manifest["ledger_sha256"],
               "issued": main, "global_nonoverlap": global_summary,
               "coverage": coverage, "feature_ready_total": feature_ready_total,
               "active_symbols": active_symbols, "expiry_direction_accuracy":
                   expiry_correct / len(evaluated) if evaluated else None,
               "expiry_missing": expiry_missing, "baselines": baseline_summary,
               "by_symbol": by_symbol_summary, "bootstrap": bootstrap,
               "gates": gates, "limitations": [
                   "Historical interval was exposed during strategy selection; this is not sealed OOS or Core evidence.",
                   "10bp and 30bp are total round-trip fee proxies; measured spread/slippage is unavailable.",
                   "No point-in-time universe or original source ZIP/vintage proof.",
                   "A 92-day diagnostic cannot establish performance across market regimes."]}
    score_path = run_dir / "scores.jsonl"
    score_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                                         for row in evaluated), encoding="utf-8")
    _atomic_json(run_dir / "summary.json", summary)
    with (run_dir / "by_symbol.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["symbol", "issued_n", "m2", "wilson_low", "wilson_high",
                         "net_mean_10bp", "net_mean_30bp", "nonoverlap_n", "nonoverlap_m2"])
        for symbol in SYMBOLS:
            a, n = by_symbol_summary[symbol]["all"], by_symbol_summary[symbol]["nonoverlap"]
            writer.writerow([symbol, a["n"], a["m2"], *(a["wilson95"] or [None, None]),
                             a["mean_net_10bp"], a["mean_net_30bp"], n["n"], n["m2"]])
    (run_dir / "report.md").write_text(_render_report(summary), encoding="utf-8")
    return summary


def _bootstrap_summary(rows: list[dict[str, Any]], day_count: int) -> dict[str, Any]:
    if day_count != 92:
        raise ValueError("frozen bootstrap requires 92 UTC dates")
    first_day = _utc_ms("2026-07-01T00:00:00Z")
    per_day = [{"n": 0, "hits": 0, "net10": 0.0, "net30": 0.0} for _ in range(day_count)]
    for row in rows:
        day = (int(row["anchor_ms"]) - first_day) // DAY_MS
        if not 0 <= day < day_count:
            raise DataInvalid("issued forecast outside frozen bootstrap dates")
        bucket = per_day[int(day)]
        bucket["n"] += 1
        bucket["hits"] += int(bool(row["m2_hit"]))
        bucket["net10"] += float(row["net_10bp"])
        bucket["net30"] += float(row["net_30bp"])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    m2_values, net10_values, net30_values = [], [], []
    for _ in range(BOOTSTRAP_REPLICATES):
        starts = rng.integers(0, day_count, size=14)
        sampled = [(int(start) + offset) % day_count
                   for start in starts for offset in range(7)][:day_count]
        n = sum(per_day[index]["n"] for index in sampled)
        hits = sum(per_day[index]["hits"] for index in sampled)
        if not n:
            continue
        m2_values.append(hits / n)
        net10_values.append(sum(per_day[index]["net10"] for index in sampled) / n)
        net30_values.append(sum(per_day[index]["net30"] for index in sampled) / n)
    def percentiles(values: list[float]) -> list[float] | None:
        return [float(value) for value in np.quantile(values, [0.025, 0.5, 0.975])] if values else None
    return {"replicates_requested": BOOTSTRAP_REPLICATES, "replicates_scored": len(m2_values),
            "seed": BOOTSTRAP_SEED, "m2_percentiles_2_5_50_97_5": percentiles(m2_values),
            "mean_net_10bp_percentiles": percentiles(net10_values),
            "mean_net_30bp_percentiles": percentiles(net30_values)}


def _render_report(summary: dict[str, Any]) -> str:
    main = summary["issued"]
    lines = ["# Adaptive selective M2 historical diagnostic", "",
             f"- Verdict: **{summary['verdict']}**", f"- Issued forecasts: {main['n']}",
             f"- M2 target-first rate: {main['m2']}", f"- Wilson 95%: {main['wilson95']}",
             f"- Global non-overlap: {summary['global_nonoverlap']['n']} events, M2={summary['global_nonoverlap']['m2']}",
             f"- Coverage: {summary['coverage']:.6%} ({summary['issued']['n']}/{summary['feature_ready_total']} feature-ready anchors)",
             f"- Mean net return per issued forecast: 10bp={main['mean_net_10bp']}, 30bp={main['mean_net_30bp']}",
             f"- Expiry direction accuracy: {summary['expiry_direction_accuracy']}",
             "", "## Preregistered gates", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}" for name, passed in summary["gates"].items())
    lines.extend(["", "## Baselines", "",
                  f"- Same-event momentum: {summary['baselines']['same_event_momentum']}",
                  f"- Deterministic random: {summary['baselines']['deterministic_random']}",
                  f"- No signal: {summary['baselines']['no_signal']}", "",
                  "## Interpretation and limitations", ""])
    lines.extend(f"- {item}" for item in summary["limitations"])
    lines.extend(["", "This is a historical exposed diagnostic, not sealed OOS, live execution evidence, or a Core strategy.", ""])
    return "\n".join(lines)


def _cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="explicit Binance archive root; read-only")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=("preflight", "forecast", "score"), required=True)
    return parser.parse_args()


def main() -> int:
    args = _cli()
    if args.phase == "preflight":
        _assert_run_phase(args.run_dir, Path(__file__), ["preflight.json"])
        _, manifest = audit_inputs(args.root)
        _atomic_json(args.run_dir / "preflight.json", manifest)
        print(json.dumps({"phase": "preflight", "status": "PASS",
                          "input_files": len(manifest["records"]),
                          "records_sha256": manifest["records_sha256"]}))
        return 0
    if args.phase == "forecast":
        _assert_run_phase(args.run_dir, args.run_dir / "preflight.json",
                          ["forecasts.jsonl", "forecast_manifest.json"])
        series, manifest = audit_inputs(args.root)
        forecast = forecast_phase(series, manifest, args.run_dir)
        print(json.dumps({"phase": "forecast", "status": forecast["status"],
                          "issued": forecast["issued"],
                          "ledger_sha256": forecast["ledger_sha256"]}))
        return 0
    if args.phase == "score":
        _assert_run_phase(args.run_dir, args.run_dir / "forecast_manifest.json",
                          ["scores.jsonl", "summary.json", "by_symbol.csv", "report.md"])
        _verify_forecast_seal(args.run_dir)
        series, manifest = audit_inputs(args.root)
        summary = score_phase(series, manifest, args.run_dir)
        print(json.dumps({"phase": "score", "verdict": summary["verdict"],
                          "issued": summary["issued"]["n"],
                          "m2": summary["issued"]["m2"]}))
        return 0
    raise NotImplementedError(f"phase {args.phase} implementation is pending")


if __name__ == "__main__":
    sys.exit(main())
