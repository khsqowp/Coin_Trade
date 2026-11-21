"""One frozen adaptive selective-prediction M2 diagnostic.

The CLI is deliberately phase-separated: data preflight, forecast generation,
then outcome scoring. It is historical research only and never places orders.
"""

from __future__ import annotations

import argparse
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
    ready = continuity & np.isfinite(features.to_numpy(dtype=float)).all(axis=1)
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
    next_month = datetime(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1,
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
                    "schema": table.schema.names, "rows": table.num_rows})


def _validate_kline_table(table: Any, symbol: str, month: str,
                          require_full_grid: bool) -> pd.DataFrame:
    names = set(table.schema.names)
    if missing := REQUIRED_KLINE_COLUMNS - names:
        raise DataInvalid(f"{symbol}/{month} missing kline columns: {sorted(missing)}")
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
        "funding_helper_sha256": _sha256(Path(__file__).with_name("mark_deviation_m2_probe.py")),
        "runtime": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                    "numpy": np.__version__, "pandas": pd.__version__,
                    "pyarrow": pq.__version__ if hasattr(pq, "__version__") else "unknown"},
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
    feature_parts, label_parts = [], []
    class_counts = {"UP_FIRST": 0, "DOWN_FIRST": 0, "NO_HIT": 0}
    for symbol in SYMBOLS:
        item = series[symbol]
        times = item["times"]
        close_times = times + MINUTE_MS
        mask = ((close_times >= fit_start) & (close_times < fit_end)
                & (times // MINUTE_MS % TRAIN_GRID_MINUTES == 0) & item["ready"])
        indices = np.flatnonzero(mask)
        codes, valid = _vectorized_labels(item["frame"], indices, item["atr"], fit_end)
        indices, codes = indices[valid], codes[valid]
        if len(indices):
            feature_parts.append(item["features"][indices])
            label_parts.append(codes)
            for code, label in CODE_TO_LABEL.items():
                class_counts[label] += int(np.sum(codes == code))
    if not feature_parts:
        return np.empty((0, len(FEATURE_COLUMNS)), np.float32), np.empty(0, np.int8), class_counts
    return np.concatenate(feature_parts), np.concatenate(label_parts), class_counts


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
        _, manifest = audit_inputs(args.root)
        _atomic_json(args.run_dir / "preflight.json", manifest)
        print(json.dumps({"phase": "preflight", "status": "PASS",
                          "input_files": len(manifest["records"]),
                          "records_sha256": manifest["records_sha256"]}))
        return 0
    raise NotImplementedError(f"phase {args.phase} implementation is pending")


if __name__ == "__main__":
    sys.exit(main())
