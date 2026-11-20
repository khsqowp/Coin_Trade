"""One frozen, exploratory contract-vs-mark deviation M2 diagnostic."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREREG = ROOT / "docs/research/inventory/PREREG_MARK_DEVIATION_M2_20261120.md"
DATA_ROOT = "binance"
MONTHS = tuple(f"2026-{month:02d}" for month in range(7, 11))
PRICE_KINDS = ("um_klines_1m", "um_markPriceKlines_1m")
FUNDING_KIND = "um_fundingRate"
PRICE_SYMBOLS = tuple("""1000PEPEUSDT 1000SHIBUSDT AAVEUSDT ADAUSDT APTUSDT ARBUSDT
ATOMUSDT AVAXUSDT BCHUSDT BNBUSDT BTCUSDT CRVUSDT DOGEUSDT DOTUSDT ENAUSDT
ETCUSDT ETHUSDT FILUSDT HBARUSDT INJUSDT LINKUSDT LTCUSDT NEARUSDT OPUSDT
POLUSDT RUNEUSDT SEIUSDT SOLUSDT SUIUSDT TIAUSDT TONUSDT TRXUSDT UNIUSDT
WLDUSDT XRPUSDT""".split())
SYMBOLS = tuple(symbol for symbol in PRICE_SYMBOLS if symbol != "TONUSDT")
HORIZONS = (10, 20)
BASE_FEE = 0.001
STRESS_FEE = 0.003
Z_THRESHOLD = 2.0
Z_LOOKBACK = 60
ATR_LOOKBACK = 14
ATR_MULTIPLE = 1.0
LOCKOUT_MINUTES = 20
BOOTSTRAP_DRAWS = 1_000
BOOTSTRAP_SEED = 20261120
MINUTE_MS = 60_000
SCORE_START = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
SCORE_END = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _month_grid(month: str) -> np.ndarray:
    year, number = map(int, month.split("-"))
    start = int(datetime(year, number, 1, tzinfo=timezone.utc).timestamp() * 1000)
    next_year, next_month = ((year + 1, 1) if number == 12 else (year, number + 1))
    end = int(datetime(next_year, next_month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    return np.arange(start, end, MINUTE_MS, dtype=np.int64)


def _funding_minute_indices(mark_times: np.ndarray, funding_times: np.ndarray) -> np.ndarray:
    """Map millisecond settlement timestamps to their containing UTC minute."""
    funding_times = np.asarray(funding_times, dtype=np.int64)
    offsets = funding_times % MINUTE_MS
    if np.any(offsets > 1_000):
        raise ValueError("funding timestamp is more than 1 second off the UTC minute grid")
    minute_times = funding_times - offsets
    indices = np.searchsorted(mark_times, minute_times)
    if (np.any(indices >= len(mark_times))
            or not np.array_equal(mark_times[indices], minute_times)):
        raise ValueError("funding event lacks a corresponding mark-price minute")
    return indices


def _target_paths(root: Path) -> list[Path]:
    base = root / DATA_ROOT
    paths = [base / kind / symbol / f"{month}.parquet"
             for kind in PRICE_KINDS for symbol in PRICE_SYMBOLS for month in MONTHS]
    paths.extend(base / FUNDING_KIND / symbol / f"{month}.parquet"
                 for symbol in SYMBOLS for month in MONTHS)
    return paths


def _manifest_snapshot(path: Path, target_paths: list[Path], root: Path) -> tuple[list[dict], int, str]:
    digest = sha256_file(path)
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    indexed = {row["path"]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("manifest contains duplicate paths")
    selected = []
    for target in target_paths:
        relative = target.relative_to(root).as_posix()
        row = indexed.get(relative)
        if row is None:
            raise ValueError(f"input absent from manifest: {relative}")
        selected.append({key: row.get(key, "") for key in
                         ("path", "bytes", "sha256", "source_url", "src_zip_bytes")})
    return selected, len(rows), digest


def _target_state(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def _validate_ohlc_arrays(times: np.ndarray, values: dict[str, np.ndarray],
                          expected: np.ndarray, label: str) -> None:
    if not np.array_equal(times, expected):
        raise ValueError(f"minute timestamp grid mismatch: {label}")
    arrays = [values[name] for name in ("open", "high", "low", "close")]
    if any(not np.all(np.isfinite(array)) or np.any(array <= 0) for array in arrays):
        raise ValueError(f"invalid OHLC values: {label}")
    opens, highs, lows, closes = arrays
    if (np.any(highs < np.maximum(opens, closes))
            or np.any(lows > np.minimum(opens, closes))
            or np.any(highs < lows)):
        raise ValueError(f"OHLC invariant failure: {label}")


def audit_inputs(root: Path) -> dict:
    """Verify the frozen file set, manifest hashes, and structure before scoring."""
    manifest_path = root / "MANIFEST.csv"
    paths = _target_paths(root)
    if len(paths) != 416 or len(set(paths)) != 416:
        raise ValueError("frozen target file list is not exactly 416 unique files")
    target_manifest_before, manifest_rows_before, before_digest = _manifest_snapshot(
        manifest_path, paths, root)
    manifest_rows = {row["path"]: row for row in target_manifest_before}
    file_records = []
    file_states = {}
    for path in paths:
        if not path.is_file():
            raise ValueError(f"missing frozen input: {path}")
        relative = path.relative_to(root).as_posix()
        row = manifest_rows.get(relative)
        if row is None:
            raise ValueError(f"input absent from manifest: {relative}")
        if (not row.get("sha256") or not row.get("source_url", "").startswith(
                "https://data.binance.vision/") or int(row.get("src_zip_bytes") or 0) <= 0):
            raise ValueError(f"source/hash metadata is incomplete: {relative}")
        state_before = _target_state(path)
        actual_bytes = state_before[0]
        actual_sha = sha256_file(path)
        if _target_state(path) != state_before:
            raise ValueError(f"input file changed during hash verification: {relative}")
        if actual_bytes != int(row["bytes"]) or actual_sha != row["sha256"]:
            raise ValueError(f"input hash/size differs from manifest: {relative}")
        file_records.append((relative, actual_bytes, actual_sha))
        file_states[path] = state_before

    for kind in PRICE_KINDS:
        for symbol in PRICE_SYMBOLS:
            monthly_times = []
            for month in MONTHS:
                path = root / DATA_ROOT / kind / symbol / f"{month}.parquet"
                table = pq.read_table(path, columns=["open_time", "open", "high", "low", "close"])
                times = table["open_time"].to_numpy(zero_copy_only=False).astype(np.int64)
                values = {name: table[name].to_numpy(zero_copy_only=False).astype(float)
                          for name in ("open", "high", "low", "close")}
                _validate_ohlc_arrays(times, values, _month_grid(month), f"{kind}/{symbol}/{month}")
                monthly_times.append(times)
            joined = np.concatenate(monthly_times)
            if np.any(np.diff(joined) != MINUTE_MS):
                raise ValueError(f"cross-month minute gap/duplicate: {kind}/{symbol}")

    for symbol in SYMBOLS:
        event_times = []
        event_intervals = []
        for month in MONTHS:
            path = root / DATA_ROOT / FUNDING_KIND / symbol / f"{month}.parquet"
            table = pq.read_table(path, columns=["calc_time", "funding_interval_hours",
                                                 "last_funding_rate"])
            times = table["calc_time"].to_numpy(zero_copy_only=False).astype(np.int64)
            intervals = table["funding_interval_hours"].to_numpy(zero_copy_only=False).astype(np.int64)
            rates = table["last_funding_rate"].to_numpy(zero_copy_only=False).astype(float)
            left, right = _month_grid(month)[[0, -1]]
            if (not len(times) or len(times) != len(np.unique(times))
                    or np.any(np.diff(times) <= 0) or np.any(times % MINUTE_MS > 1_000)
                    or np.any(intervals <= 0) or not np.all(np.isfinite(rates))
                    or times[0] < left or times[-1] >= right + MINUTE_MS):
                raise ValueError(f"invalid funding timestamps/rates: {symbol}/{month}")
            event_times.append(times)
            event_intervals.append(intervals)
        times = np.concatenate(event_times)
        intervals = np.concatenate(event_intervals)
        if len(times) != len(np.unique(times)) or np.any(np.diff(times) <= 0):
            raise ValueError(f"duplicate/out-of-order funding event: {symbol}")
        for index, delta in enumerate(np.diff(times)):
            permitted = {int(intervals[index]) * 3_600_000,
                         int(intervals[index + 1]) * 3_600_000}
            if not any(abs(int(delta) - value) <= 1_000 for value in permitted):
                raise ValueError(f"funding interval gap/mismatch: {symbol} at {index}")

    target_manifest_after, manifest_rows_after, after_digest = _manifest_snapshot(
        manifest_path, paths, root)
    if target_manifest_before != target_manifest_after:
        raise ValueError("target manifest rows changed during audit")
    if any(_target_state(path) != state for path, state in file_states.items()):
        raise ValueError("target file changed during structural audit")
    digest = hashlib.sha256()
    for record in sorted(file_records):
        digest.update(("\t".join(map(str, record)) + "\n").encode())
    state_digest = hashlib.sha256()
    for path, state in sorted(file_states.items(), key=lambda item: item[0].relative_to(root).as_posix()):
        state_digest.update((path.relative_to(root).as_posix() + "\t"
                             + "\t".join(map(str, state)) + "\n").encode())
    return {
        "status": "PASS",
        "manifest_rows": manifest_rows_after,
        "manifest_sha256_before": before_digest,
        "manifest_sha256_after": after_digest,
        "manifest_changed_during_audit": before_digest != after_digest,
        "target_manifest_sha256": hashlib.sha256(json.dumps(
            target_manifest_after, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "target_files": len(file_records),
        "sha256_size_matches": len(file_records),
        "price_grid_files": len(PRICE_KINDS) * len(PRICE_SYMBOLS) * len(MONTHS),
        "price_grid_gaps_or_duplicates": 0,
        "funding_symbols": len(SYMBOLS),
        "data_fingerprint_sha256": digest.hexdigest(),
        "target_file_state_sha256": state_digest.hexdigest(),
        "source_limit": "Target Parquet hashes match selected manifest rows; unrelated manifest appends are allowed. Original source ZIP hashes/response bodies are not retained.",
    }


def _arrays(path: Path, columns: tuple[str, ...]) -> dict[str, np.ndarray]:
    table = pq.read_table(path, columns=list(columns))
    return {name: table[name].to_numpy(zero_copy_only=False) for name in columns}


def load_symbol(root: Path, symbol: str) -> dict[str, np.ndarray]:
    pieces: dict[str, list[np.ndarray]] = {
        name: [] for name in ("times", "open", "high", "low", "close",
                              "mark_open", "mark_close", "funding_times", "funding_mark_opens",
                              "funding_rates", "funding_intervals")
    }
    for month in MONTHS:
        contract_path = root / DATA_ROOT / "um_klines_1m" / symbol / f"{month}.parquet"
        mark_path = root / DATA_ROOT / "um_markPriceKlines_1m" / symbol / f"{month}.parquet"
        funding_path = root / DATA_ROOT / FUNDING_KIND / symbol / f"{month}.parquet"
        contract = _arrays(contract_path, ("open_time", "open", "high", "low", "close"))
        mark = _arrays(mark_path, ("open_time", "open", "close"))
        funding = _arrays(funding_path, ("calc_time", "last_funding_rate",
                                          "funding_interval_hours"))
        if not np.array_equal(contract["open_time"], mark["open_time"]):
            raise ValueError(f"contract/mark timestamps differ: {symbol}/{month}")
        fund_times = funding["calc_time"].astype(np.int64)
        try:
            indices = _funding_minute_indices(mark["open_time"], fund_times)
        except ValueError as exc:
            raise ValueError(f"funding/mark minute alignment failed: {symbol}/{month}: {exc}") from exc
        mapping = {
            "times": contract["open_time"], "open": contract["open"],
            "high": contract["high"], "low": contract["low"],
            "close": contract["close"], "mark_open": mark["open"],
            "mark_close": mark["close"], "funding_times": funding["calc_time"],
            "funding_rates": funding["last_funding_rate"],
            "funding_intervals": funding["funding_interval_hours"],
            "funding_mark_opens": mark["open"][indices],
        }
        for key, values in mapping.items():
            pieces[key].append(values)
    result = {key: np.concatenate(parts) for key, parts in pieces.items()}
    if (np.any(np.diff(result["times"]) != MINUTE_MS)
            or np.any(np.diff(result["funding_times"]) <= 0)):
        raise ValueError(f"cross-month data discontinuity: {symbol}")
    if not np.all(np.isfinite(result["mark_close"])) or np.any(result["mark_close"] <= 0):
        raise ValueError(f"invalid mark prices: {symbol}")
    return result


def _rolling_z(basis: np.ndarray, lookback: int) -> np.ndarray:
    """Causal z score against the previous lookback values, excluding current."""
    z = np.full(len(basis), np.nan, dtype=float)
    sums = np.concatenate(([0.0], np.cumsum(basis, dtype=float)))
    sums2 = np.concatenate(([0.0], np.cumsum(basis * basis, dtype=float)))
    for index in range(lookback, len(basis)):
        total = sums[index] - sums[index - lookback]
        total2 = sums2[index] - sums2[index - lookback]
        mean = total / lookback
        variance = (total2 - lookback * mean * mean) / (lookback - 1)
        if variance > 0 and math.isfinite(variance):
            z[index] = (basis[index] - mean) / math.sqrt(variance)
    return z


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, lookback: int) -> np.ndarray:
    true_range = np.zeros(len(close), dtype=float)
    true_range[1:] = np.maximum.reduce((
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1]),
    ))
    prefix = np.concatenate(([0.0], np.cumsum(true_range, dtype=float)))
    values = np.full(len(close), np.nan, dtype=float)
    for index in range(lookback, len(close)):
        values[index] = (prefix[index + 1] - prefix[index + 1 - lookback]) / lookback
    return values


def signal_events(data: dict[str, np.ndarray], symbol: str) -> tuple[list[dict], int, int, int]:
    times = data["times"].astype(np.int64)
    close, high, low = (data[name].astype(float) for name in ("close", "high", "low"))
    basis = np.log(close / data["mark_close"].astype(float))
    z = _rolling_z(basis, Z_LOOKBACK)
    atr = _atr(high, low, close, ATR_LOOKBACK)
    records = []
    raw_triggers = 0
    suppressed = 0
    invalid = 0
    next_allowed_entry_ms = SCORE_START
    last_i = len(times) - max(HORIZONS) - 1
    eligible = 0
    for index in range(Z_LOOKBACK + 1, last_i + 1):
        signal_close_ms = int(times[index] + MINUTE_MS)
        entry_ms = signal_close_ms
        if signal_close_ms < SCORE_START or signal_close_ms + max(HORIZONS) * MINUTE_MS >= SCORE_END:
            continue
        eligible += 1
        if not math.isfinite(z[index]) or not math.isfinite(z[index - 1]):
            continue
        prior_inside = -Z_THRESHOLD <= z[index - 1] <= Z_THRESHOLD
        side = (-1 if z[index] > Z_THRESHOLD else
                1 if z[index] < -Z_THRESHOLD else 0)
        if not prior_inside or side == 0:
            continue
        raw_triggers += 1
        if not math.isfinite(atr[index]) or atr[index] <= 0:
            invalid += 1
            continue
        if entry_ms < next_allowed_entry_ms:
            suppressed += 1
            continue
        entry_i = index + 1
        if entry_i >= len(times) or int(times[entry_i]) != entry_ms:
            raise ValueError(f"next-minute entry timestamp mismatch: {symbol} {signal_close_ms}")
        entry = float(data["open"][entry_i])
        risk = float(atr[index] * ATR_MULTIPLE)
        if not math.isfinite(entry) or entry <= 0 or not math.isfinite(risk) or risk <= 0:
            invalid += 1
            continue
        records.append({
            "symbol": symbol, "signal_index": index, "entry_index": entry_i,
            "signal_close_ms": signal_close_ms, "entry_ms": entry_ms,
            "side": side, "z_score": float(z[index]), "basis": float(basis[index]),
            "signal_close": float(close[index]), "entry_price": entry, "risk": risk,
            "target_price": entry + side * risk, "stop_price": entry - side * risk,
        })
        next_allowed_entry_ms = entry_ms + LOCKOUT_MINUTES * MINUTE_MS
    return records, raw_triggers, suppressed, invalid


def barrier_outcome(data: dict[str, np.ndarray], event: dict, side: int,
                    horizon: int) -> dict:
    if horizon not in HORIZONS or side not in (-1, 1):
        raise ValueError("invalid preregistered horizon or side")
    entry_i = int(event["entry_index"])
    entry = float(event["entry_price"])
    risk = float(event["risk"])
    target = entry + side * risk
    stop = entry - side * risk
    exit_price = None
    exit_reason = "TIMEOUT"
    exit_i = entry_i + horizon - 1
    for index in range(entry_i, entry_i + horizon):
        bar_open = float(data["open"][index])
        bar_high = float(data["high"][index])
        bar_low = float(data["low"][index])
        stop_hit = bar_low <= stop if side == 1 else bar_high >= stop
        target_hit = bar_high >= target if side == 1 else bar_low <= target
        if stop_hit:
            exit_price = (min(bar_open, stop) if side == 1 else max(bar_open, stop))
            exit_reason = "STOP"
            exit_i = index
            break
        if target_hit:
            exit_price = target
            exit_reason = "TARGET"
            exit_i = index
            break
    if exit_price is None:
        exit_price = float(data["close"][exit_i])
    exit_ms = int(data["times"][exit_i]) + MINUTE_MS
    funding_times = data["funding_times"].astype(np.int64)
    left = int(np.searchsorted(funding_times, int(event["entry_ms"]), side="right"))
    right = int(np.searchsorted(funding_times, exit_ms, side="right"))
    event_times = funding_times[left:right]
    rates = data["funding_rates"].astype(float)[left:right]
    if len(event_times):
        mark_at_events = data["funding_mark_opens"].astype(float)[left:right]
        funding_return = float(np.sum(-side * rates * mark_at_events / entry))
    else:
        funding_return = 0.0
    gross = side * (exit_price / entry - 1.0)
    horizon_close = float(data["close"][entry_i + horizon - 1])
    m1_correct = int(side * math.log(horizon_close / float(event["signal_close"])) > 0)
    return {
        "exit_ms": exit_ms,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "m2_success": int(exit_reason == "TARGET"),
        "m1_correct": m1_correct,
        "gross_return": gross,
        "funding_return": funding_return,
        "net_base": gross + funding_return - BASE_FEE,
        "net_stress": gross + funding_return - STRESS_FEE,
    }


def _wilson(successes: int, total: int) -> list[float | None]:
    if total <= 0:
        return [None, None]
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [center - margin, center + margin]


def _random_side(symbol: str, signal_close_ms: int) -> int:
    raw = f"{BOOTSTRAP_SEED}:{symbol}:{signal_close_ms}".encode()
    return 1 if int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % 2 else -1


def _circular_day_sample(day_count: int, rng: np.random.Generator,
                        block_length: int = 7) -> np.ndarray:
    if day_count <= 0 or block_length <= 0:
        raise ValueError("day_count and block_length must be positive")
    blocks_needed = math.ceil(day_count / block_length)
    starts = rng.integers(0, day_count, size=blocks_needed)
    offsets = np.arange(block_length)
    return np.concatenate([(start + offsets) % day_count for start in starts])[:day_count]


def _block_bootstrap(records: list[dict], key: str, reps: int = BOOTSTRAP_DRAWS) -> list[float | None]:
    if not records:
        return [None, None]
    first_day = SCORE_START // 86_400_000
    day_count = (SCORE_END - SCORE_START) // 86_400_000
    by_day: list[list[float]] = [[] for _ in range(day_count)]
    for record in records:
        day_index = int(record["signal_close_ms"]) // 86_400_000 - first_day
        if day_index < 0 or day_index >= day_count:
            raise ValueError("bootstrap record falls outside frozen UTC calendar")
        by_day[day_index].append(float(record[key]))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    samples = np.empty(reps, dtype=float)
    for draw in range(reps):
        sampled_days = _circular_day_sample(day_count, rng, 7)
        values = [value for day_index in sampled_days for value in by_day[int(day_index)]]
        if not values:
            samples[draw] = np.nan
            continue
        samples[draw] = float(np.mean(values))
    finite = samples[np.isfinite(samples)]
    if len(finite) == 0:
        return [None, None]
    return [float(value) for value in np.quantile(finite, [0.025, 0.975])]


def score_symbol(data: dict[str, np.ndarray], symbol: str) -> tuple[list[dict], int, int, int, int]:
    events, raw_triggers, suppressed, invalid = signal_events(data, symbol)
    ledger = []
    for event in events:
        previous_return = float(data["close"][event["signal_index"]]
                                / data["close"][event["signal_index"] - 1] - 1.0)
        momentum_side = 1 if previous_return > 0 else -1 if previous_return < 0 else 0
        random_side = _random_side(symbol, int(event["signal_close_ms"]))
        for horizon in HORIZONS:
            candidate = barrier_outcome(data, event, int(event["side"]), horizon)
            momentum = (barrier_outcome(data, event, momentum_side, horizon)
                        if momentum_side else None)
            random = barrier_outcome(data, event, random_side, horizon)
            row = {key: value for key, value in event.items()
                   if key not in ("signal_index", "entry_index")}
            row.update({"horizon_min": horizon,
                        "momentum_side": momentum_side,
                        "random_side": random_side})
            for prefix, outcome in (("candidate", candidate), ("momentum", momentum),
                                    ("random", random)):
                if outcome is None:
                    row[f"{prefix}_m2_success"] = None
                    row[f"{prefix}_m1_correct"] = None
                    row[f"{prefix}_gross_return"] = None
                    row[f"{prefix}_funding_return"] = None
                    row[f"{prefix}_net_base"] = None
                    row[f"{prefix}_net_stress"] = None
                    row[f"{prefix}_exit_reason"] = "NO_TRADE"
                else:
                    for field, value in outcome.items():
                        row[f"{prefix}_{field}"] = value
            ledger.append(row)
    return ledger, len(events), raw_triggers, suppressed, invalid


def _overlap_cluster_count(rows: list[dict]) -> int:
    entries = sorted({int(row["entry_ms"]) for row in rows})
    if not entries:
        return 0
    clusters = 0
    cluster_end = -1
    for entry in entries:
        if entry >= cluster_end:
            clusters += 1
            cluster_end = entry + max(HORIZONS) * MINUTE_MS
    return clusters


def _metrics(rows: list[dict], horizon: int, opportunities: int) -> dict:
    subset = [row for row in rows if row["horizon_min"] == horizon]
    candidate = [row for row in subset if row["candidate_m2_success"] is not None]
    momentum = [row for row in subset if row["momentum_m2_success"] is not None]
    random = [row for row in subset if row["random_m2_success"] is not None]
    successes = sum(int(row["candidate_m2_success"]) for row in candidate)
    momentum_successes = sum(int(row["momentum_m2_success"]) for row in momentum)
    symbols = sorted({row["symbol"] for row in candidate})
    unique_times = {int(row["entry_ms"]) for row in candidate}
    daily_cluster_count = len({int(row["signal_close_ms"]) // 86_400_000 for row in candidate})
    lower, upper = _wilson(successes, len(candidate))
    momentum_rate = (momentum_successes / len(momentum)) if momentum else None
    output = {
        "horizon_min": horizon,
        "role": "primary" if horizon == 10 else "secondary",
        "eligible_symbol_minutes": opportunities,
        "signals": len(candidate),
        "nonoverlap_events_within_symbol": len(candidate),
        "symbols": len(symbols),
        "symbols_list": symbols,
        "unique_entry_minutes": len(unique_times),
        "overlapping_20m_cross_symbol_clusters": _overlap_cluster_count(candidate),
        "utc_day_clusters": daily_cluster_count,
        "coverage": len(candidate) / opportunities if opportunities else 0.0,
        "m2_target_first_hits": successes,
        "m2_rate": successes / len(candidate) if candidate else None,
        "m2_wilson_95": [lower, upper],
        "momentum_baseline_signals": len(momentum),
        "momentum_baseline_m2": momentum_rate,
        "random_baseline_signals": len(random),
        "random_baseline_m2": (sum(int(row["random_m2_success"]) for row in random) / len(random)
                                if random else None),
        "m1_direction_accuracy": (sum(int(row["candidate_m1_correct"]) for row in candidate)
                                   / len(candidate) if candidate else None),
        "timeouts": sum(row["candidate_exit_reason"] == "TIMEOUT" for row in candidate),
        "stop_exits": sum(row["candidate_exit_reason"] == "STOP" for row in candidate),
        "target_exits": sum(row["candidate_exit_reason"] == "TARGET" for row in candidate),
        "mean_gross_return": (float(np.mean([row["candidate_gross_return"] for row in candidate]))
                              if candidate else None),
        "mean_funding_return": (float(np.mean([row["candidate_funding_return"] for row in candidate]))
                                if candidate else None),
        "mean_net_base_fee_proxy": (float(np.mean([row["candidate_net_base"] for row in candidate]))
                                     if candidate else None),
        "mean_net_stress_fee_proxy": (float(np.mean([row["candidate_net_stress"] for row in candidate]))
                                       if candidate else None),
        "m2_7day_block_bootstrap_95": _block_bootstrap(candidate, "candidate_m2_success"),
        "net_base_7day_block_bootstrap_95": _block_bootstrap(candidate, "candidate_net_base"),
        "net_stress_7day_block_bootstrap_95": _block_bootstrap(candidate, "candidate_net_stress"),
        "flat_baseline": {"signals": 0, "coverage": 0.0, "m2": None},
        "iid_note": "Signals do not overlap within a symbol; cross-symbol and time clusters remain dependent.",
    }
    gates = {
        "m2_at_least_80pct": output["m2_rate"] is not None and output["m2_rate"] >= 0.80,
        "wilson_lower_above_momentum": (lower is not None and momentum_rate is not None
                                        and lower > momentum_rate),
        "nonoverlap_n_at_least_200": len(candidate) >= 200,
        "at_least_20_symbols": len(symbols) >= 20,
        "coverage_at_least_10pct": output["coverage"] >= 0.10,
        "positive_net_base_fee_proxy": (output["mean_net_base_fee_proxy"] is not None
                                         and output["mean_net_base_fee_proxy"] > 0),
        "positive_net_stress_fee_proxy": (output["mean_net_stress_fee_proxy"] is not None
                                           and output["mean_net_stress_fee_proxy"] > 0),
    }
    output["fixed_primary_gates"] = gates
    output["fixed_primary_pass"] = all(gates.values())
    return output


def _per_symbol_metrics(rows: list[dict], opportunities: dict[str, int],
                        audit_rows: dict[str, dict]) -> list[dict]:
    result = []
    for horizon in HORIZONS:
        for symbol in SYMBOLS:
            subset = [row for row in rows
                      if row["horizon_min"] == horizon and row["symbol"] == symbol]
            candidate = [row for row in subset if row["candidate_m2_success"] is not None]
            momentum = [row for row in subset if row["momentum_m2_success"] is not None]
            random = [row for row in subset if row["random_m2_success"] is not None]
            n = len(candidate)
            hits = sum(int(row["candidate_m2_success"]) for row in candidate)
            wilson = _wilson(hits, n)
            audit = audit_rows[symbol]
            result.append({
                "symbol": symbol,
                "horizon_min": horizon,
                "role": "primary" if horizon == 10 else "secondary",
                "eligible_symbol_minutes": opportunities[symbol],
                "raw_triggers": audit["raw_triggers"],
                "lockout_suppressed": audit["lockout_suppressed"],
                "invalid_triggers": audit["invalid_triggers"],
                "signals": n,
                "m2_hits": hits,
                "m2_rate": hits / n if n else None,
                "m2_wilson_95_lower": wilson[0],
                "m2_wilson_95_upper": wilson[1],
                "momentum_baseline_signals": len(momentum),
                "momentum_baseline_m2": (float(np.mean([row["momentum_m2_success"] for row in momentum]))
                                          if momentum else None),
                "random_baseline_signals": len(random),
                "random_baseline_m2": (float(np.mean([row["random_m2_success"] for row in random]))
                                        if random else None),
                "m1_direction_accuracy": (float(np.mean([row["candidate_m1_correct"] for row in candidate]))
                                           if candidate else None),
                "mean_gross_return": (float(np.mean([row["candidate_gross_return"] for row in candidate]))
                                      if candidate else None),
                "mean_funding_return": (float(np.mean([row["candidate_funding_return"] for row in candidate]))
                                         if candidate else None),
                "mean_net_base_fee_proxy": (float(np.mean([row["candidate_net_base"] for row in candidate]))
                                             if candidate else None),
                "mean_net_stress_fee_proxy": (float(np.mean([row["candidate_net_stress"] for row in candidate]))
                                               if candidate else None),
            })
    return result


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _report(summary: dict) -> str:
    lines = [
        "# Contract–mark deviation M2 diagnostic",
        "",
        "Status: **historical exploratory diagnostic; not untouched OOS, not an execution result, and not Core approval.**",
        "",
        f"- Trial: `{summary['trial_id']}`",
        f"- Data fingerprint: `{summary['data_audit']['data_fingerprint_sha256']}`",
        f"- Selected-target manifest SHA-256: `{summary['data_audit']['target_manifest_sha256']}`",
        f"- Whole-manifest snapshot SHA-256: `{summary['data_audit']['manifest_sha256_after']}` (rows={summary['data_audit']['manifest_rows']}; unrelated appends are outside the frozen input set)",
        f"- Scoring interval: `{summary['interval_utc']}`",
        f"- Scoring symbols: {len(SYMBOLS)} fixed symbols; the full list is in the preregistration.",
        f"- Preregistration SHA-256: `{summary['prereg_sha256']}`",
        f"- Runner SHA-256: `{summary['runner_sha256']}`",
        "",
        "| Horizon | Signals | Symbols | M2 target-first | Wilson 95% | 7d block M2 95% | M1 direction | Momentum M2 | Coverage | Net base fee proxy | Net stress fee proxy | Frozen gates |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for horizon in HORIZONS:
        row = summary["horizons"][str(horizon)]
        rate = "n/a" if row["m2_rate"] is None else f"{row['m2_rate']:.2%} ({row['m2_target_first_hits']}/{row['signals']})"
        wilson = row["m2_wilson_95"]
        wilson_text = "n/a" if wilson[0] is None else f"{wilson[0]:.2%}–{wilson[1]:.2%}"
        block = row["m2_7day_block_bootstrap_95"]
        block_text = "n/a" if block[0] is None else f"{block[0]:.2%}–{block[1]:.2%}"
        fmt = lambda value: "n/a" if value is None else f"{value:.3%}"
        lines.append(
            f"| {horizon}m ({row['role']}) | {row['signals']} | {row['symbols']} | {rate} | {wilson_text} | "
            f"{block_text} | {fmt(row['m1_direction_accuracy'])} | {fmt(row['momentum_baseline_m2'])} | {row['coverage']:.3%} | "
            f"{fmt(row['mean_net_base_fee_proxy'])} | {fmt(row['mean_net_stress_fee_proxy'])} | "
            f"{'PASS' if row['fixed_primary_pass'] else 'FAIL'} |"
        )
    primary = summary["horizons"]["10"]
    conclusion = "ADVANCE_TO_SEPARATE_RED_TEAM_ONLY" if primary["fixed_primary_pass"] else "REJECT_FIXED_CANDIDATE"
    lines += [
        "",
        f"Primary H=10 fixed-gate disposition: **{conclusion}**.",
        "H=20 is secondary and cannot rescue a failed primary. Results use contract OHLC proxies and legacy fee scenarios; no bid/ask, measured slippage, or proven fill simulation is available.",
        "",
        "## Audit limits",
        "",
        "The fixed primary H=10 gates fail: M2 >=80%, coverage >=10%, Wilson lower bound above the same-event momentum baseline, and positive mean net return under both fee proxies. Sample and symbol-count gates pass. H=20 is secondary and also fails the 80% and positive-net criteria.",
        "",
        "All 416 frozen files matched the current local data manifest by byte size and SHA-256; the minute-grid and funding timestamp checks passed. This does not reconstruct original ZIP response bodies or independently validate publisher hashes for those downloads. The test interval is historical and market-period overlap exists with earlier hourly research. The score is therefore exploratory only.",
        "",
        "## Reproduction",
        "",
        f"Scoring command (completed once; do not rerun): `{summary['command']}`",
        "",
    ]
    return "\n".join(lines)


def run(root: Path, out_dir: Path) -> dict:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {out_dir}")
    audit = audit_inputs(root)
    prereg_hash = sha256_file(PREREG)
    runner_hash = sha256_file(Path(__file__))
    all_rows: list[dict] = []
    triggers = suppressed = invalid = opportunities = 0
    opportunities_by_symbol: dict[str, int] = {}
    symbol_audits: dict[str, dict] = {}
    for symbol in SYMBOLS:
        data = load_symbol(root, symbol)
        rows, accepted_events, raw, skipped, invalid_count = score_symbol(data, symbol)
        all_rows.extend(rows)
        triggers += raw
        suppressed += skipped
        invalid += invalid_count
        eligible_mask = ((data["times"] + MINUTE_MS >= SCORE_START)
                         & (data["times"] + MINUTE_MS + max(HORIZONS) * MINUTE_MS < SCORE_END))
        eligible_mask[:Z_LOOKBACK + 1] = False
        eligible = int(np.sum(eligible_mask))
        opportunities += eligible
        opportunities_by_symbol[symbol] = eligible
        symbol_audits[symbol] = {"eligible_minutes": eligible,
                                 "raw_triggers": raw,
                                 "lockout_suppressed": skipped,
                                 "invalid_triggers": invalid_count,
                                 "accepted_events": accepted_events}
    current_state = hashlib.sha256()
    for path in sorted(_target_paths(root), key=lambda item: item.relative_to(root).as_posix()):
        current_state.update((path.relative_to(root).as_posix() + "\t"
                              + "\t".join(map(str, _target_state(path))) + "\n").encode())
    if current_state.hexdigest() != audit["target_file_state_sha256"]:
        raise ValueError("a target input changed between preflight and scoring")
    horizons = {str(horizon): _metrics(all_rows, horizon, opportunities)
                for horizon in HORIZONS}
    symbol_rows = _per_symbol_metrics(all_rows, opportunities_by_symbol, symbol_audits)
    summary = {
        "trial_id": "mark-deviation-m2-20261121-v1",
        "status": "SCORED_ONCE",
        "interval_utc": "[2026-07-01T00:00:00Z, 2026-11-01T00:00:00Z)",
        "universe": list(SYMBOLS),
        "horizon_roles": {"10": "primary", "20": "secondary"},
        "signal_rule": "log(contract_close/mark_close), prior-60 sample z, threshold crossing ±2, mean reversion side",
        "costs_round_trip": {"base_fee_proxy": BASE_FEE, "stress_fee_proxy": STRESS_FEE},
        "data_audit": audit,
        "prereg_sha256": prereg_hash,
        "runner_sha256": runner_hash,
        "eligible_symbol_minutes": opportunities,
        "raw_triggers": triggers,
        "lockout_suppressed_triggers": suppressed,
        "invalid_triggers": invalid,
        "accepted_events": len(all_rows) // len(HORIZONS),
        "horizons": horizons,
        "bootstrap": {"method": "circular 7-UTC-day blocks preserving cross-symbol day clusters",
                       "replicates": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED},
        "command": "PYTHONDONTWRITEBYTECODE=1 /Users/user/CODE/trading_data/external/crypto/.venv/bin/python scripts/research/mark_deviation_m2_probe.py --root /Volumes/home/mac/CODE/trading_data/external/crypto --out-dir docs/research/inventory/runs/mark_deviation_m2_20261121",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(out_dir / "by_symbol.csv", symbol_rows)
    with gzip.open(out_dir / "event_ledger.csv.gz", "wt", newline="", encoding="utf-8") as stream:
        fields = list(dict.fromkeys(key for row in all_rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)
    (out_dir / "report.md").write_text(_report(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        help="Read-only root containing MANIFEST.csv and binance/")
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="New, empty output directory inside the research checkout")
    parser.add_argument("--audit-only", action="store_true",
                        help="Verify inputs without reading price outcomes")
    parser.add_argument("--render-report-only", action="store_true",
                        help="Render report.md from an existing summary.json without reading market data")
    args = parser.parse_args()
    if args.render_report_only:
        summary_path = args.out_dir / "summary.json"
        if not summary_path.is_file():
            raise SystemExit(f"existing summary is missing: {summary_path}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("trial_id") != "mark-deviation-m2-20261121-v1":
            raise SystemExit("summary trial_id does not match the frozen diagnostic")
        (args.out_dir / "report.md").write_text(_report(summary), encoding="utf-8")
        print(json.dumps({"status": "REPORT_RENDERED_FROM_EXISTING_SUMMARY",
                          "trial_id": summary["trial_id"],
                          "scoring_rerun": False}, sort_keys=True))
        return 0
    if args.root is None:
        parser.error("--root is required unless --render-report-only is selected")
    if args.audit_only:
        print(json.dumps(audit_inputs(args.root), indent=2, sort_keys=True))
        return 0
    if not PREREG.is_file():
        raise SystemExit(f"frozen preregistration is missing: {PREREG}")
    result = run(args.root, args.out_dir)
    print(json.dumps({"trial_id": result["trial_id"],
                      "events": result["accepted_events"],
                      "primary": result["horizons"]["10"]["fixed_primary_pass"],
                      "report": str(args.out_dir / "report.md")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
