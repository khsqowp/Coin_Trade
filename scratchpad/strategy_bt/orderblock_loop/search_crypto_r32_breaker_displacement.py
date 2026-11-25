"""Single preregistered TRAIN test for decisive breaker invalidation closes."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r27_bos_fvg_confluence as r27
import search_crypto_r29_bos_taker_flow as r29
import search_crypto_r31_breaker_flip_retest as r31
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R32-coin"
PREREG_PATH = HERE / "PREREG_R32_BREAKER_DISPLACEMENT.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_688
EXPECTED_N = 1_689
DEPTH_ATR = 0.25
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R32-BREAKER-DECISIVE-CLOSE-DEPTH",
    "base": "R31-OB-INVALIDATION-BREAKER-FIRST-RETEST",
    "minimum_distal_close_overshoot_atr": DEPTH_ATR,
    "shallow_close_break": "do_not_invalidate;continue_original_24bar_wait",
    "zone_atr": "4h_BOS_signal_ATR14",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py",
    "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py",
    "search_crypto_r31_breaker_flip_retest.py",
    "data_access.py", "metrics.py", "resource_guard.py", "PREREG.md",
    PREREG_PATH.name, "PREREG_R31_BREAKER_FLIP_RETEST.md",
    "tests/test_search_crypto_r31_breaker_flip_retest.py",
    "search_crypto_r32_breaker_displacement.py",
    "tests/test_search_crypto_r32_breaker_displacement.py",
    "universe/CRYPTO_35.csv",
)


class AppendUncertainError(RuntimeError):
    """Ledger append may be partial; inspect state and do not retry."""


def _advance_with_depth(state, bar, index, rejected, base_advance=None):
    """Only a decisive close can invalidate the source order block."""
    base_advance = base_advance or r31._advance
    zone = state["zone"]
    if state["phase"] == "ob_wait":
        age = index - zone.signal_index
        if age > r31.BREAK_DEADLINE or not bar.complete:
            return base_advance(state, bar, index)
    atr = zone.atr_at_signal
    if not math.isfinite(atr) or atr <= 0:
        raise ValueError("R32 zone ATR must be finite and positive")
    if state["phase"] == "ob_wait" and index > zone.signal_index:
        if zone.direction == "long":
            overshoot = (zone.low - bar.close) / atr if bar.close < zone.low else 0.0
        else:
            overshoot = (bar.close - zone.high) / atr if bar.close > zone.high else 0.0
        if 0.0 < overshoot < DEPTH_ATR:
            rejected["shallow_close_break_rejected"] += 1
            return "wait"
    return base_advance(state, bar, index)


def _trial_with_depth(barsets_1h, barsets_4h):
    rejected = {"shallow_close_break_rejected": 0}
    original = r31._advance
    r31._advance = lambda state, bar, index: _advance_with_depth(
        state, bar, index, rejected, base_advance=original)
    try:
        result = r31._trial(barsets_1h, barsets_4h)
    finally:
        r31._advance = original
    result.update(rejected)
    result["detail"] = (
        "R31 breaker retest with >=0.25 source-zone ATR distal close overshoot; TRAIN only"
    )
    return result


def _ledger_state() -> int:
    old_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            rows = 0
            for row in reader:
                if row.get("round") == ROUND:
                    raise RuntimeError("R32 already exists; single attempt cannot repeat")
                rows += 1
            return rows
    finally:
        csv.field_size_limit(old_limit)


def _code_hash() -> str:
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _grid_hash(config) -> str:
    raw = json.dumps([config], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, config):
    r19._assert_no_ledger_writer()
    record = {
        "trial_id": f"R32-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "1h/4h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R32 TRAIN test; not OOS or G approval",
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


def _split_cache_state(data_root, data_access):
    return r29._split_cache_state(data_root, data_access)


def _assert_snapshot(code_sha, prereg_sha, master_sha):
    if (_code_hash() != code_sha
            or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != prereg_sha
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != master_sha):
        raise RuntimeError("R32 code or prereg changed during run")


def _run_locked(data_root: Path):
    import data_access

    r19._assert_no_ledger_writer()
    rows = _ledger_state()
    config = {**CONFIG, "bonferroni_n": rows + 1}
    if (rows != EXPECTED_ROWS or rows + 1 != EXPECTED_N
            or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError(f"R32 preflight mismatch before market data access: rows={rows}")
    grid_sha, code_sha = _grid_hash(config), _code_hash()
    fingerprint, written = "UNAVAILABLE_BEFORE_TRAIN_INPUT", False
    try:
        split_sha, split_mtime = _split_cache_state(data_root, data_access)
        with heavy_task("R32"):
            bars1 = r14._load_barsets(data_access.iter_train_bars, "1h")
            bars4 = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R32-breaker-decisive-close",
                [(f"{s}:1h", b, f, x) for s, b, f, x in bars1]
                + [(f"{s}:4h", b, {}, x) for s, b, _f, x in bars4])
            usable = r27._usable_symbols(bars1, bars4)
            if len(usable) < r31.MINIMUM_SYMBOLS:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols"}
            else:
                result = _trial_with_depth(bars1, bars4)
            result["split_manifest_sha256"] = split_sha
            if _split_cache_state(data_root, data_access) != (split_sha, split_mtime):
                raise RuntimeError("fixed split cache changed during R32")
            _assert_snapshot(code_sha, _PREREG_SHA, _MASTER_SHA)
            _append(result, grid_sha, code_sha, fingerprint, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r32_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R32 preregistered TRAIN attempt failed; not G evidence"},
                    grid_sha, code_sha, fingerprint, config)
        raise
    print(json.dumps({"R32": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


def _acquire_run_locks(data_root: Path):
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
        _release_run_locks(opened)
        raise


def _release_run_locks(opened):
    for path, fd in reversed(opened):
        os.close(fd)
        path.unlink(missing_ok=True)


def run():
    data_root = Path(os.environ.get(
        "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    opened = _acquire_run_locks(data_root)
    try:
        _run_locked(data_root)
    finally:
        _release_run_locks(opened)


if __name__ == "__main__":
    run()
