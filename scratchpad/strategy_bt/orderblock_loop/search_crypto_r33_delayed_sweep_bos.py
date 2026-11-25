"""Single preregistered TRAIN test: delayed external sweep-to-BOS setups."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND = "R33-coin"
PREREG_PATH = HERE / "PREREG_R33_DELAYED_SWEEP_BOS.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 4_189
EXPECTED_N = 4_190
BAR_MS = 4 * 3_600_000
SWEEP_LOOKBACK = 20
MIN_DELAY = 4
MAX_DELAY = 6
MIN_FREE_BYTES = 40 * 1024**3
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R33-DELAYED-EXTERNAL-SWEEP-TO-BOS-OB",
    "base": "R21-PRE-BOS-SWEEP-R14-FIRST-RETEST",
    "sweep_lookback_bars": SWEEP_LOOKBACK,
    "sweep_to_bos_completed_4h_bars": [MIN_DELAY, MAX_DELAY],
    "selection_if_multiple": "latest qualifying sweep only",
    "entry_exit": "fixed R14 first-retest midpoint recovery next 1h open",
    "round_trip_cost_bps": 12, "funding_order_policy": "adverse_only",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py",
    "search_crypto_r21_pre_bos_sweep.py",
    "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "tests/test_search_crypto_r21_pre_bos_sweep.py",
    "search_crypto_r33_delayed_sweep_bos.py",
    "tests/test_search_crypto_r33_delayed_sweep_bos.py",
    "universe/CRYPTO_35.csv",
)


def _code_hash():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


# Snapshot sources before importing project modules; _run_locked rechecks both
# the snapshot and current bytes before any TRAIN data reader is called.
_IMPORT_CODE_SHA = _code_hash()

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r21_pre_bos_sweep as r21
import search_crypto_r27_bos_fvg_confluence as r27
import search_crypto_r29_bos_taker_flow as r29
from resource_guard import heavy_task


class AppendUncertainError(RuntimeError):
    """Ledger append may be partial; inspect state and never retry."""


def _external_sweep(bars, index, direction):
    if index < SWEEP_LOOKBACK or index >= len(bars):
        return False
    prior = bars[index - SWEEP_LOOKBACK:index]
    level = (min(bar.low for bar in prior) if direction == "long"
             else max(bar.high for bar in prior))
    bar = bars[index]
    if direction == "long":
        return bar.low < level and bar.close > level
    return bar.high > level and bar.close < level


def _latest_qualifying_sweep(bars, bos_index, direction):
    """Return the latest completed sweep 4-6 bars before BOS, if any."""
    if bos_index < 0 or bos_index >= len(bars):
        return None
    first_relevant = max(1, bos_index - MAX_DELAY - SWEEP_LOOKBACK)
    if any(bars[k].timestamp - bars[k - 1].timestamp != BAR_MS
           for k in range(first_relevant, bos_index + 1)):
        return None
    candidates = range(max(SWEEP_LOOKBACK, bos_index - MAX_DELAY),
                       bos_index - MIN_DELAY + 1)
    matches = [j for j in candidates if _external_sweep(bars, j, direction)]
    return matches[-1] if matches else None


def _pre_bos_sweep(bars, bos_index, direction):
    return _latest_qualifying_sweep(bars, bos_index, direction) is not None


def _trial_with_filtered_zones(barsets_1h, barsets_4h, stats):
    original_pre_bos_sweep = r21._pre_bos_sweep
    r21._pre_bos_sweep = _pre_bos_sweep
    try:
        return r21._trial_with_filtered_zones(barsets_1h, barsets_4h, stats)
    finally:
        r21._pre_bos_sweep = original_pre_bos_sweep


def _ledger_state():
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            rows = 0
            for row in reader:
                if row.get("round") == ROUND:
                    raise RuntimeError("R33 already exists; single attempt cannot repeat")
                rows += 1
            return rows
    finally:
        csv.field_size_limit(old)


def _grid_hash(config):
    raw = json.dumps([config], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, config):
    r19._assert_no_ledger_writer()
    record = {
        "trial_id": f"R33-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "1h/4h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R33 TRAIN test; not OOS or G approval",
    }
    buffer = io.StringIO(newline="")
    csv.DictWriter(buffer, fieldnames=common.FIELDS).writerow(record)
    payload = buffer.getvalue().encode()
    fd = None
    attempted = False
    try:
        fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
        attempted = True
        if os.write(fd, payload) != len(payload):
            raise AppendUncertainError("short append; inspect ledger; do not retry")
        os.fsync(fd)
    except OSError as exc:
        if attempted:
            raise AppendUncertainError("append uncertain; inspect ledger; do not retry") from exc
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


def run():
    data_root = Path(os.environ.get(
        "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    opened = _acquire_locks(data_root)
    try:
        _run_locked(data_root)
    finally:
        _release_locks(opened)


def _run_locked(data_root):
    r19._assert_no_ledger_writer()
    rows = _ledger_state()
    config = {**CONFIG, "bonferroni_n": rows + 1}
    if (rows != EXPECTED_ROWS or rows + 1 != EXPECTED_N
            or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError(f"R33 preflight mismatch before data access: rows={rows}")
    grid_sha, code_sha = _grid_hash(config), _code_hash()
    if code_sha != _IMPORT_CODE_SHA:
        raise RuntimeError("R33 source bytes changed after import; refuse stale-code execution")
    if shutil.disk_usage(data_root).free < MIN_FREE_BYTES:
        raise RuntimeError("R33 requires at least 40 GiB free disk before TRAIN access")
    import data_access
    if _code_hash() != code_sha:
        raise RuntimeError("R33 source bytes changed during dependency import")
    fingerprint, written = "UNAVAILABLE_BEFORE_TRAIN_INPUT", False
    try:
        split_sha, split_mtime = r29._split_cache_state(data_root, data_access)
        with heavy_task("R33"):
            bars1 = r14._load_barsets(data_access.iter_train_bars, "1h")
            bars4 = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R33-delayed-sweep-bos-4h-ob-1h-entry",
                [(f"{s}:1h", b, f, x) for s, b, f, x in bars1]
                + [(f"{s}:4h", b, {}, x) for s, b, _f, x in bars4])
            usable = r27._usable_symbols(bars1, bars4)
            if len(usable) < 30:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols"}
            else:
                stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
                result = _trial_with_filtered_zones(bars1, bars4, stats)
                result.update(stats)
                result["detail"] = "R33 delayed 4-6 bar pre-BOS sweep + fixed R14; TRAIN only"
            result["split_manifest_sha256"] = split_sha
            if r29._split_cache_state(data_root, data_access) != (split_sha, split_mtime):
                raise RuntimeError("fixed split cache changed during R33")
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R33 code or prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r33_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R33 preregistered attempt failed; not G evidence"},
                    grid_sha, code_sha, fingerprint, config)
        raise
    print(json.dumps({"R33": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
