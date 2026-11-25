"""Preregistered final-round BTC daily-regime filter for crypto order blocks."""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import search_crypto as common
import search_crypto_r4 as r4
from crypto import first_retest

ROUND = "R12-btc-daily-alignment"
TIMEFRAME = "4h"
DEFINITIONS = ("displacement", "bos_origin", "volume_displacement")
DIRECTIONS = ("long", "short")
DEADLINE = 24
REWARD_R = 1.5
MINIMUM_SYMBOLS = 30
EMA_PERIOD = 100
EMA_SLOPE_DAYS = 20
PREREG_PATH = HERE / "PREREG_R12_TECHNICAL_RETRY.md"
PREREG_SHA256 = "089c24fc57e63e1dc7d0d838e2badc6426641f18a2960db50d74f81fbab9c969"
BAR_MS = 4 * 60 * 60 * 1000
DAY_MS = 24 * 60 * 60 * 1000
DAILY_BARS_PER_DAY = 6
ALPHA = 2.0 / (EMA_PERIOD + 1)

CONFIGS = tuple({
    "definition": definition,
    "timeframe": TIMEFRAME,
    "direction": direction,
    "deadline": DEADLINE,
    "reward_r": REWARD_R,
    "minimum_symbols": MINIMUM_SYMBOLS,
    "funding_order_policy": "adverse_only",
    "filter": "BTCUSDT_completed_1d_close_vs_EMA100_and_20d_slope",
} for definition in DEFINITIONS for direction in DIRECTIONS)


def _grid_hash() -> str:
    encoded = json.dumps(CONFIGS, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _code_hash() -> str:
    names = (
        "crypto.py", "search_crypto.py", "search_crypto_r4.py",
        "search_crypto_r12_btc_daily_alignment.py", "data_access.py",
        "metrics.py", "resource_guard.py", "universe/CRYPTO_35.csv",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def build_daily_regimes(btc_bars) -> dict[int, str | None]:
    """Map complete UTC daily close timestamps to causal trend states."""
    by_day: dict[int, dict[int, float]] = {}
    for bar in btc_bars:
        if not bar.complete:
            continue
        day = (bar.timestamp // DAY_MS) * DAY_MS
        slot = bar.timestamp - day
        if slot < 0 or slot >= DAY_MS or slot % BAR_MS:
            continue
        by_day.setdefault(day, {})[slot // BAR_MS] = bar.close

    daily = []
    for day in sorted(by_day):
        values = by_day[day]
        if set(values) == set(range(DAILY_BARS_PER_DAY)):
            daily.append((day, values[5]))

    result: dict[int, str | None] = {}
    segment: list[tuple[int, float]] = []

    def flush() -> None:
        if len(segment) < EMA_PERIOD + EMA_SLOPE_DAYS:
            return
        closes = [close for _, close in segment]
        ema = [0.0] * len(closes)
        ema[EMA_PERIOD - 1] = sum(closes[:EMA_PERIOD]) / EMA_PERIOD
        for i in range(EMA_PERIOD, len(closes)):
            ema[i] = ALPHA * closes[i] + (1.0 - ALPHA) * ema[i - 1]
        for i in range(EMA_PERIOD + EMA_SLOPE_DAYS - 1, len(closes)):
            close_time = segment[i][0] + DAY_MS
            state = None
            if closes[i] > ema[i] and ema[i] > ema[i - EMA_SLOPE_DAYS]:
                state = "long"
            elif closes[i] < ema[i] and ema[i] < ema[i - EMA_SLOPE_DAYS]:
                state = "short"
            result[close_time] = state

    for item in daily:
        if segment and item[0] != segment[-1][0] + DAY_MS:
            flush()
            segment = []
        segment.append(item)
    flush()
    return result


def regime_before(entry_timestamp: int, regimes: dict[int, str | None]) -> str | None:
    """Use only the latest daily close strictly earlier than the entry open."""
    closes = sorted(regimes)
    index = bisect.bisect_left(closes, entry_timestamp) - 1
    return regimes[closes[index]] if index >= 0 else None


def _filtered_zones(bars, definition: str, regimes: dict[int, str | None],
                    zone_builder):
    zones = zone_builder(bars, definition)
    kept = []
    for zone in zones:
        setup = first_retest(
            bars, zone, deadline=DEADLINE, reward_r=REWARD_R,
        )
        if setup is None:
            continue
        entry_timestamp = bars[setup.entry_index].timestamp
        if regime_before(entry_timestamp, regimes) == zone.direction:
            kept.append(zone)
    return kept


def _install_regime_filter(regimes):
    original_zones = r4.r4_zones
    r4.r4_zones = lambda bars, definition: _filtered_zones(
        bars, definition, regimes, original_zones,
    )
    return original_zones


def _registered(grid_hash: str, code_sha: str, fingerprint: str) -> set[str]:
    if not common.CSV_PATH.exists() or common.CSV_PATH.stat().st_size == 0:
        return set()
    csv.field_size_limit(sys.maxsize)
    found = set()
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (row["round"] != ROUND or row["parameter_grid_hash"] != grid_hash
                    or row["code_sha256"] != code_sha):
                continue
            try:
                config = json.loads(row["definition"])
                metric = json.loads(row["metric"])
            except (json.JSONDecodeError, TypeError):
                continue
            if (isinstance(config, dict) and isinstance(metric, dict)
                    and metric.get("train_input_fingerprint") == fingerprint
                    and metric.get("preregistration_sha256") == PREREG_SHA256):
                found.add(row["definition"])
    return found


def _append(config: dict, result: dict, fingerprint: str,
            grid_hash: str, code_sha: str) -> None:
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    config_sha = hashlib.sha256(config_json.encode()).hexdigest()
    metric = {
        **result,
        "train_input_fingerprint": fingerprint,
        "preregistration_sha256": PREREG_SHA256,
    }
    record = {
        "trial_id": f"{ROUND}-{config_sha[:12]}-{uuid.uuid4().hex}",
        "round": ROUND,
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json,
        "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha,
        "train_period": "bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": "",
        "notes": f"status={result['status']}; prereg={PREREG_SHA256}",
    }
    has_rows = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if has_rows:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch; R12 row not appended")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not has_rows:
            writer.writeheader()
        writer.writerow(record)
        stream.flush()


def run() -> int:
    if PREREG_SHA256 == "PENDING_PREREG_SHA256":
        raise RuntimeError("R12 preregistration hash is not pinned")
    if hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != PREREG_SHA256:
        raise RuntimeError("R12 preregistration hash changed; no trials were run")
    if shutil.disk_usage("/").free < 40 * 1024**3:
        raise RuntimeError("less than 40 GiB free; no trials were run")

    import data_access

    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        raise RuntimeError("TRAIN-only data loader is unavailable")
    grid_hash, code_sha = _grid_hash(), _code_hash()
    barsets = r4._load_timeframe(loader, TIMEFRAME)
    btc = next((bars for symbol, bars, _, _ in barsets if symbol == "BTCUSDT"), None)
    if not btc:
        raise RuntimeError("BTCUSDT TRAIN bars absent; no R12 trials were run")
    regimes = build_daily_regimes(btc)
    if not regimes:
        raise RuntimeError("BTC daily regime warm-up unavailable; no R12 trials were run")
    fingerprint = common._train_input_fingerprint(TIMEFRAME, barsets)
    registered = _registered(grid_hash, code_sha, fingerprint)
    original_zones = _install_regime_filter(regimes)
    zone_cache = {}
    completed = 0
    try:
        for config in CONFIGS:
            config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
            if config_json in registered:
                completed += 1
                continue
            try:
                result = r4._trial(config, barsets, zone_cache)
            except MemoryError as exc:
                result = {"status": "failed", "detail": f"MemoryError: {exc}"}
                _append(config, result, fingerprint, grid_hash, code_sha)
                raise
            except Exception as exc:
                result = {"status": "failed", "detail": f"{type(exc).__name__}: {exc}"}
            _append(config, result, fingerprint, grid_hash, code_sha)
            registered.add(config_json)
            completed += 1
            print(
                f"[{completed}/{len(CONFIGS)}] {config['definition']} "
                f"{config['direction']}: {result['status']} "
                f"M2={result.get('m2_target_first_rate')} "
                f"EV={result.get('expectancy_bps')}bp "
                f"PF={result.get('profit_factor')}",
                flush=True,
            )
    finally:
        r4.r4_zones = original_zones
    return completed


def main() -> None:
    from resource_guard import heavy_task

    with heavy_task(ROUND):
        completed = run()
    if completed != len(CONFIGS):
        raise RuntimeError(f"expected {len(CONFIGS)} R12 trials, completed {completed}")


if __name__ == "__main__":
    main()
