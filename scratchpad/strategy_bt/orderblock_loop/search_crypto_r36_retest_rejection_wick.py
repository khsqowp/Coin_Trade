"""Single preregistered TRAIN test for retest-candle rejection wicks."""
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
ROUND = "R36-coin"
PREREG_PATH = HERE / "PREREG_R36_RETEST_REJECTION_WICK.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 4_192
EXPECTED_N = 4_193
MIN_FREE_BYTES = 40 * 1024**3
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R36-R14-RETEST-DIRECTIONAL-WICK-GTE-BODY",
    "base": "R14-4h-bos_origin-1h-first-retest-midpoint-next-open",
    "long": "min(open,close)-low >= abs(close-open)",
    "short": "high-max(open,close) >= abs(close-open)",
    "flat_range": "reject", "doji": "accept_if_directional_wick_positive",
    "entry_exit": "fixed R14; 0.50R;24x1h;12bp;adverse_only",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py",
    "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "search_crypto_r36_retest_rejection_wick.py",
    "tests/test_search_crypto_r36_retest_rejection_wick.py",
    "universe/CRYPTO_35.csv",
)
_IMPORT_CODE_SHA = None


class AppendUncertainError(RuntimeError):
    """Append may be partial; reconcile the ledger before any retry."""


def _wick_pass(bar, direction):
    values = (bar.open, bar.high, bar.low, bar.close)
    if any(not math.isfinite(value) for value in values):
        return False, "invalid_ohlc"
    if (bar.high < max(bar.open, bar.close, bar.low)
            or bar.low > min(bar.open, bar.close, bar.high)):
        return False, "invalid_ohlc"
    if bar.high == bar.low:
        return False, "flat_range"
    body = abs(bar.close - bar.open)
    wick = (min(bar.open, bar.close) - bar.low if direction == "long"
            else bar.high - max(bar.open, bar.close))
    if direction not in ("long", "short") or wick < 0:
        return False, "invalid_direction_or_wick"
    if wick == 0 or wick < body:
        return False, "wick_shorter_than_body"
    return True, "accepted"


def _filtered_setup_builder(stats):
    original = r14._make_setup

    def build(zone, confirmation_bar, next_bar, confirmation_index):
        setup, reason = original(zone, confirmation_bar, next_bar, confirmation_index)
        if setup is None:
            return setup, reason
        stats["valid_r14_setups"] += 1
        qualifies, why = _wick_pass(confirmation_bar, zone.direction)
        stats[f"wick_{why}"] = stats.get(f"wick_{why}", 0) + 1
        if not qualifies:
            stats["wick_rejected_setups"] += 1
            return None, "retest_wick_failed"
        stats["wick_accepted_setups"] += 1
        return setup, reason

    return original, build


def _trial_with_filter(barsets_1h, barsets_4h):
    stats = {"valid_r14_setups": 0, "wick_accepted_setups": 0,
             "wick_rejected_setups": 0}
    original, filtered = _filtered_setup_builder(stats)
    r14._make_setup = filtered
    try:
        result = r14._trial(barsets_1h, barsets_4h)
    finally:
        r14._make_setup = original
    result.update(stats)
    result["detail"] = "R36 retest directional-wick/body filter + fixed R14; TRAIN only"
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
                    raise RuntimeError("R36 already exists; single attempt cannot repeat")
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
        "trial_id": f"R36-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R36 TRAIN diagnostic; R14-dependent; not G approval",
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
        raise RuntimeError(f"R36 prereg/denominator mismatch before price data: rows={rows}")
    code_sha = _code_hash()
    if _IMPORT_CODE_SHA is not None and code_sha != _IMPORT_CODE_SHA:
        raise RuntimeError("R36 source changed after import")
    if shutil.disk_usage(data_root).free < MIN_FREE_BYTES:
        raise RuntimeError("R36 requires at least 40 GiB free before TRAIN access")
    import data_access
    split_sha, split_mtime = r29._split_cache_state(data_root, data_access)
    fingerprint, written = "UNAVAILABLE_BEFORE_TRAIN_INPUT", False
    try:
        with heavy_task("R36"):
            bars1 = r14._load_barsets(data_access.iter_train_bars, "1h")
            bars4 = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R36-R14-retest-directional-wick-body",
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
                raise RuntimeError("fixed TRAIN split cache changed during R36")
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R36 code or prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, _grid_hash(config), code_sha, fingerprint, denominator, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            failure = {"status": "failed", "failure_stage": "r36_train",
                       "failure_type": type(exc).__name__,
                       "detail": "single preregistered attempt failed; not G evidence"}
            _append(failure, _grid_hash(config), code_sha, fingerprint, denominator, config)
        raise
    print(json.dumps({"R36": result, "code_sha": code_sha,
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
