"""Single TRAIN test: require meaningful pre-BOS liquidity-sweep depth."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r14 as r14
from crypto import _atr
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R26-coin"
PREREG_PATH = HERE / "PREREG_R26_DEEP_SWEEP_ATR.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_682
EXPECTED_N = 1_683
BAR_4H_MS = 4 * 3_600_000
SWEEP_LOOKBACK = 20
BOS_CONFIRM_BARS = 3
MIN_SWEEP_DEPTH_ATR = 0.25
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R26-R21-PRE-BOS-SWEEP-MIN-DEPTH-ATR",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "bos_origin", "sweep_lookback_bars": SWEEP_LOOKBACK,
    "sweep_to_bos_bars": [1, BOS_CONFIRM_BARS],
    "min_sweep_depth_atr": MIN_SWEEP_DEPTH_ATR,
    "atr": "existing causal ATR14 at completed sweep bar",
    "entry": "unchanged R21/R14 first 1h retest midpoint reclaim then next open",
    "stop_buffer_atr": r14.STOP_BUFFER_ATR, "reward_r": r14.REWARD_R,
    "deadline_bars": r14.DEADLINE,
    "max_holding_bars": r14.MAX_HOLDING_BARS,
    "round_trip_cost_bps": 12,
    "funding_order_policy": r14.FUNDING_ORDER_POLICY,
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}


class AppendRollbackError(OSError):
    """A partial ledger append could not be safely rolled back."""


def _external_sweep(bars, index, direction):
    if index < SWEEP_LOOKBACK:
        return False
    prior = bars[index - SWEEP_LOOKBACK:index]
    level = (min(bar.low for bar in prior) if direction == "long"
             else max(bar.high for bar in prior))
    bar = bars[index]
    if direction == "long":
        return bar.low < level and bar.close > level
    return bar.high > level and bar.close < level


def _deep_sweep(bars, index, direction):
    return _deep_sweep_status(bars, index, direction) == "deep"


def _deep_sweep_status(bars, index, direction):
    if not _external_sweep(bars, index, direction):
        return "not_sweep"
    atr = _atr(bars, index, 14)
    if atr is None or atr <= 0:
        return "atr_unavailable"
    prior = bars[index - SWEEP_LOOKBACK:index]
    level = (min(bar.low for bar in prior) if direction == "long"
             else max(bar.high for bar in prior))
    depth = ((level - bars[index].low) if direction == "long"
             else (bars[index].high - level))
    return "deep" if depth / atr >= MIN_SWEEP_DEPTH_ATR else "shallow"


def _pre_bos_basic_sweep(bars, bos_index, direction):
    start = max(SWEEP_LOOKBACK, bos_index - BOS_CONFIRM_BARS)
    return any(_external_sweep(bars, index, direction)
               for index in range(start, bos_index))


def _pre_bos_deep_sweep(bars, bos_index, direction):
    start = max(SWEEP_LOOKBACK, bos_index - BOS_CONFIRM_BARS)
    return any(_deep_sweep(bars, index, direction)
               for index in range(start, bos_index))


def _pre_bos_sweep_funnel(bars, bos_index, direction):
    start = max(SWEEP_LOOKBACK, bos_index - BOS_CONFIRM_BARS)
    statuses = [_deep_sweep_status(bars, index, direction)
                for index in range(start, bos_index)]
    basic = any(status != "not_sweep" for status in statuses)
    deep = "deep" in statuses
    atr_rejected = basic and not deep and "atr_unavailable" in statuses
    shallow_rejected = basic and not deep and "shallow" in statuses
    return basic, deep, atr_rejected, shallow_rejected


def _filtered_zone_builder(stats):
    original = r14.r4_zones

    def build(bars, definition):
        zones = original(bars, definition)
        if definition != "bos_origin":
            return zones
        stats["raw_bos_zones"] += len(zones)
        kept = []
        for zone in zones:
            basic, deep, atr_rejected, shallow_rejected = _pre_bos_sweep_funnel(
                bars, zone.signal_index, zone.direction)
            if basic:
                stats["basic_sweep_zones"] += 1
            if atr_rejected:
                stats["atr_warmup_rejected_zones"] += 1
            if shallow_rejected:
                stats["shallow_rejected_zones"] += 1
            if deep:
                stats["deep_sweep_zones"] += 1
                kept.append(zone)
        return kept

    return original, build


def _trial_with_deep_sweep(barsets_1h, barsets_4h):
    stats = {"raw_bos_zones": 0, "basic_sweep_zones": 0,
             "deep_sweep_zones": 0, "atr_warmup_rejected_zones": 0,
             "shallow_rejected_zones": 0}
    original, filtered = _filtered_zone_builder(stats)
    r14.r4_zones = filtered
    try:
        result = r14._trial(barsets_1h, barsets_4h)
    finally:
        r14.r4_zones = original
    result.update(stats)
    return result


def _ledger_rows():
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            return sum(1 for _ in reader)
    finally:
        csv.field_size_limit(old)


def _code_hash():
    names = (
        "crypto.py", "search_crypto.py", "search_crypto_r14.py",
        "search_crypto_r19_match_attrition_audit.py",
        "search_crypto_r21_pre_bos_sweep.py", "data_access.py", "metrics.py",
        "resource_guard.py", "PREREG.md", PREREG_PATH.name,
        "search_crypto_r26_deep_sweep_atr.py",
        "tests/test_search_crypto_r26_deep_sweep_atr.py",
        "universe/CRYPTO_35.csv",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _append(result, grid_sha, code_sha, fingerprint):
    import search_crypto_r19_match_attrition_audit as r19
    r19._assert_no_ledger_writer()
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        if tuple(next(csv.reader(stream))) != common.FIELDS:
            raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    row = {
        "trial_id": f"R26-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R26 TRAIN sweep-depth test; not OOS or G approval",
    }
    out = io.StringIO(newline="")
    csv.DictWriter(out, fieldnames=common.FIELDS).writerow(row)
    payload = out.getvalue().encode()
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    before = os.fstat(fd).st_size
    try:
        if os.write(fd, payload) != len(payload):
            try:
                os.ftruncate(fd, before)
            except OSError as rollback_error:
                raise AppendRollbackError("ledger append rollback failed") from rollback_error
            raise OSError("short ledger append rolled back")
    finally:
        os.close(fd)


def _usable_symbols(barsets_1h, barsets_4h):
    symbols_1h = {symbol for symbol, bars, _funding, _excluded in barsets_1h if bars}
    symbols_4h = {symbol for symbol, bars, _funding, _excluded in barsets_4h if bars}
    return symbols_1h & symbols_4h


def _run_locked():
    import data_access
    import search_crypto_r19_match_attrition_audit as r19

    if (hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError("R26 prereg changed after import")
    actual_rows = _ledger_rows()
    if actual_rows != EXPECTED_ROWS:
        raise RuntimeError(f"R26 denominator mismatch before data access: {actual_rows}")
    r19._assert_no_ledger_writer()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    result_written = False
    try:
        with heavy_task("R26"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R26-4h-1h-train",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h])
            usable = _usable_symbols(barsets_1h, barsets_4h)
            if len(usable) < r14.MINIMUM_SYMBOLS:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 symbols have both cutoff-safe timeframes"}
            else:
                result = _trial_with_deep_sweep(barsets_1h, barsets_4h)
                result["detail"] = "R21 4h/1h entry/exit with 0.25 ATR pre-BOS sweep-depth filter; TRAIN only"
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R26 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint)
            result_written = True
        try:
            r19._assert_no_ledger_writer()
        except Exception as exc:
            print(json.dumps({"R26_post_append_writer_warning": type(exc).__name__}),
                  file=sys.stderr, flush=True)
    except Exception as exc:
        if not result_written and not isinstance(exc, AppendRollbackError):
            _append({"status": "failed", "failure_stage": "r26_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R26 preregistered attempt failed; no G approval"},
                    grid_sha, code_sha, fingerprint)
        raise
    print(json.dumps({"R26": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


def run():
    data_root = Path(os.environ.get(
        "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    lock_path = data_root / "cache/orderblock/runs/.cointrade_train_trials.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _run_locked()
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
