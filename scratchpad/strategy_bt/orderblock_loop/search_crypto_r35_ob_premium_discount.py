"""Single preregistered TRAIN test for OB range premium/discount location."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import math
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r27_bos_fvg_confluence as r27
import search_crypto_r29_bos_taker_flow as r29
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R35-coin"
PREREG_PATH = HERE / "PREREG_R35_OB_PREMIUM_DISCOUNT.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 4_191
EXPECTED_N = 4_192
BAR_MS = 4 * 3_600_000
LOOKBACK = 20
MIN_FREE_BYTES = 40 * 1024**3
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R35-BOS-OB-PREMIUM-DISCOUNT-LOCATION",
    "base": "R14-4h-bos_origin-1h-first-retest-midpoint-next-open",
    "lookback_completed_4h_bars": LOOKBACK,
    "range_window": "[bos_index-20,bos_index), excludes BOS candle",
    "long_rule": "zone_mid < prior20_range_mid",
    "short_rule": "zone_mid > prior20_range_mid",
    "entry_exit": "fixed R14; 0.50R;24x1h;12bp;adverse_only",
    "cutoff": "2023-11-06T16:00:00Z",
    "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py",
    "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "search_crypto_r35_ob_premium_discount.py",
    "tests/test_search_crypto_r35_ob_premium_discount.py",
    "universe/CRYPTO_35.csv",
)
_IMPORT_CODE_SHA = None


class AppendUncertainError(RuntimeError):
    """Append may be partial; reconcile the ledger before any retry."""


def _zone_location(bars, zone):
    index = zone.signal_index
    if index < LOOKBACK or index >= len(bars):
        return False, "insufficient_history"
    prior = bars[index - LOOKBACK:index]
    if len(prior) != LOOKBACK or any(not bar.complete for bar in prior):
        return False, "incomplete_window"
    if any(right.timestamp - left.timestamp != BAR_MS
           for left, right in zip(prior, prior[1:])) or (
            bars[index].timestamp - prior[-1].timestamp != BAR_MS):
        return False, "gap_window"
    values = [value for bar in prior for value in (bar.high, bar.low)]
    if any(not math.isfinite(value) for value in values):
        return False, "invalid_window"
    if (not math.isfinite(zone.low) or not math.isfinite(zone.high)
            or zone.low >= zone.high):
        return False, "invalid_zone"
    range_mid = (max(bar.high for bar in prior) + min(bar.low for bar in prior)) / 2
    zone_mid = (zone.low + zone.high) / 2
    if zone.direction == "long":
        return zone_mid < range_mid, "accepted" if zone_mid < range_mid else "not_discount"
    if zone.direction == "short":
        return zone_mid > range_mid, "accepted" if zone_mid > range_mid else "not_premium"
    return False, "invalid_direction"


def _filtered_zone_builder(stats):
    original = r14.r4_zones

    def build(bars, definition):
        zones = original(bars, definition)
        if definition != "bos_origin":
            return zones
        stats["raw_bos_zones"] += len(zones)
        accepted = []
        for zone in zones:
            qualifies, reason = _zone_location(bars, zone)
            stats[f"location_{reason}"] = stats.get(f"location_{reason}", 0) + 1
            if qualifies:
                accepted.append(zone)
        stats["qualified_zones"] += len(accepted)
        stats["rejected_zones"] += len(zones) - len(accepted)
        return accepted

    return original, build


def _trial_with_filter(barsets_1h, barsets_4h):
    stats = {"raw_bos_zones": 0, "qualified_zones": 0, "rejected_zones": 0}
    original, filtered = _filtered_zone_builder(stats)
    r14.r4_zones = filtered
    try:
        result = r14._trial(barsets_1h, barsets_4h)
    finally:
        r14.r4_zones = original
    result.update(stats)
    result["detail"] = "R35 prior-20-bar premium/discount OB filter + fixed R14; TRAIN only"
    return result


def _ledger_state():
    old_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            count = 0
            for row in reader:
                if row.get("round") == ROUND:
                    raise RuntimeError("R35 already exists; single attempt cannot repeat")
                count += 1
            return count
    finally:
        csv.field_size_limit(old_limit)


def _code_hash():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _grid_hash(config):
    payload = json.dumps([config], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, denominator, config):
    r19._assert_no_ledger_writer()
    row = {
        "trial_id": f"R35-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R35 TRAIN diagnostic; not independent or G approval",
    }
    buffer = io.StringIO(newline="")
    csv.DictWriter(buffer, fieldnames=common.FIELDS).writerow(row)
    payload = buffer.getvalue().encode()
    fd = None
    attempted = False
    try:
        fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
        attempted = True
        if os.write(fd, payload) != len(payload):
            raise AppendUncertainError("short append; reconcile ledger; do not retry")
        os.fsync(fd)
    except OSError as exc:
        if attempted:
            raise AppendUncertainError("append uncertain; reconcile ledger; do not retry") from exc
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError as exc:
                if attempted:
                    raise AppendUncertainError("close failed after append; do not retry") from exc
                raise


def _acquire_locks(data_root):
    lock_dir = data_root / "cache/orderblock/runs"
    if not lock_dir.is_dir():
        raise FileNotFoundError("research lock directory is absent")
    opened = []
    try:
        for name in (".cointrade_train_trials.lock", ".ob_attrition_train_trials.lock"):
            path = lock_dir / name
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            opened.append((path, fd))
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return opened
    except Exception:
        _release_locks(opened)
        raise


def _release_locks(opened):
    for path, fd in reversed(opened):
        os.close(fd)
        path.unlink(missing_ok=True)


def _run_locked(data_root):
    r19._assert_no_ledger_writer()
    rows = _ledger_state()
    denominator = rows + 1
    config = {**CONFIG, "bonferroni_n": denominator}
    if (rows != EXPECTED_ROWS or denominator != EXPECTED_N
            or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError(f"R35 prereg/denominator mismatch before price data: rows={rows}")
    code_sha = _code_hash()
    if _IMPORT_CODE_SHA is not None and code_sha != _IMPORT_CODE_SHA:
        raise RuntimeError("R35 source changed after import")
    if shutil.disk_usage(data_root).free < MIN_FREE_BYTES:
        raise RuntimeError("R35 requires at least 40 GiB free before TRAIN access")
    import data_access
    split_sha, split_mtime = r29._split_cache_state(data_root, data_access)
    fingerprint, written = "UNAVAILABLE_BEFORE_TRAIN_INPUT", False
    try:
        with heavy_task("R35"):
            bars1 = r14._load_barsets(data_access.iter_train_bars, "1h")
            bars4 = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R35-R14-OB-prior20-range-location",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in bars1]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in bars4],
            )
            usable = r27._usable_symbols(bars1, bars4)
            if len(usable) < 30:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols"}
            else:
                result = _trial_with_filter(bars1, bars4)
            result.update({"split_manifest_sha256": split_sha,
                           "cutoff_safe_symbols": len(usable)})
            if r29._split_cache_state(data_root, data_access) != (split_sha, split_mtime):
                raise RuntimeError("fixed TRAIN split cache changed during R35")
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R35 code or prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, _grid_hash(config), code_sha, fingerprint, denominator, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            failure = {"status": "failed", "failure_stage": "r35_train",
                       "failure_type": type(exc).__name__,
                       "detail": "single preregistered attempt failed; not G evidence"}
            _append(failure, _grid_hash(config), code_sha, fingerprint, denominator, config)
        raise
    print(json.dumps({"R35": result, "code_sha": code_sha,
                      "train_fingerprint": fingerprint,
                      "bonferroni_denominator": denominator}, sort_keys=True), flush=True)


def run():
    data_root = Path(os.environ.get(
        "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    opened = _acquire_locks(data_root)
    try:
        _run_locked(data_root)
    finally:
        _release_locks(opened)


if __name__ == "__main__":
    _IMPORT_CODE_SHA = _code_hash()
    run()
