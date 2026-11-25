"""Single cutoff-safe TRAIN test for BOS-candle close-location filtering."""
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
import search_crypto_r27_bos_fvg_confluence as r27
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R28-coin"
PREREG_PATH = HERE / "PREREG_R28_BOS_CLOSE_LOCATION.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_684
EXPECTED_N = 1_685
_PREREG_SHA = "68b02d0b6e97d22326afc2baa801868fc05c57581388a27173863b7137432de7"
_MASTER_SHA = "34de50d5dc0b4ba5c12766f678ef6286e0b43d5fa844177513ba67f8623712b7"
CONFIG = {
    "experiment": "R28-BOS-DIRECTIONAL-CLOSE-LOCATION",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "bos_origin", "long_close_location_min": 0.75,
    "short_close_location_max": 0.25, "zero_range": "reject",
    "entry_exit": "fixed_R14_first_retest_midpoint_next_open_0.50R",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "PREREG_R14_FIRST_RETEST_MIDPOINT_CONFIRM.md",
    "search_crypto_r27_bos_fvg_confluence.py",
    "PREREG_R27_BOS_FVG_CONFLUENCE.md",
    "tests/test_search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r28_bos_close_location.py",
    "tests/test_search_crypto_r28_bos_close_location.py",
    "universe/CRYPTO_35.csv",
)


class AppendUncertainError(RuntimeError):
    """An append may be partial or durable state could not be confirmed."""


def _close_location_passes(bars, index: int, direction: str) -> bool:
    if direction not in ("long", "short") or index < 0 or index >= len(bars):
        return False
    bar = bars[index]
    values = (bar.open, bar.high, bar.low, bar.close)
    if not bar.complete:
        return False
    if (any(not isinstance(value, (int, float)) for value in values)
            or not all(math.isfinite(value) for value in values)):
        raise ValueError("BOS candle OHLC must be finite numeric values")
    span = bar.high - bar.low
    if span <= 0:
        raise ValueError("BOS candle range must be positive")
    if not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high:
        raise ValueError("BOS candle OHLC is inconsistent")
    location = (bar.close - bar.low) / span
    return location >= 0.75 if direction == "long" else location <= 0.25


def _trial_with_close_location(barsets_1h, barsets_4h):
    original = r27._has_directional_fvg
    r27._has_directional_fvg = _close_location_passes
    try:
        result = r27._trial_with_fvg(barsets_1h, barsets_4h)
    finally:
        r27._has_directional_fvg = original
    result["close_location_qualified_zones"] = result.pop("fvg_qualified_zones")
    result["close_location_rejected_zones"] = result.pop("fvg_rejected_zones")
    result["detail"] = "R14 lifecycle after completed BOS close-location filter; TRAIN only"
    return result


def _ledger_state() -> int:
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
                    raise RuntimeError("R28 already exists; single attempt must not repeat")
                count += 1
            return count
    finally:
        csv.field_size_limit(old_limit)


def _code_hash() -> str:
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _config_for_prior_rows(prior_rows: int) -> dict[str, object]:
    return {**CONFIG, "bonferroni_n": prior_rows + 1}


def _grid_hash(config: dict[str, object]) -> str:
    payload = json.dumps([config], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, denominator, config):
    import search_crypto_r19_match_attrition_audit as r19
    r19._assert_no_ledger_writer()
    row = {
        "trial_id": f"R28-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R28 TRAIN close-location filter; not OOS or G approval",
    }
    output = io.StringIO(newline="")
    csv.DictWriter(output, fieldnames=common.FIELDS).writerow(row)
    payload = output.getvalue().encode()
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    attempted = False
    try:
        attempted = True
        written = os.write(fd, payload)
        if written != len(payload):
            raise AppendUncertainError("short append; inspect ledger tail, never retry")
        os.fsync(fd)
    except OSError as exc:
        raise AppendUncertainError("append durability uncertain; inspect ledger tail, never retry") from exc
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            if attempted:
                raise AppendUncertainError("close failed after append; inspect ledger tail") from exc
            raise


def _split_cache_state(data_root: Path, data_access) -> tuple[str, int]:
    split_path = data_root / "cache/orderblock/crypto_splits_close_boundary.json"
    if not split_path.is_file():
        raise FileNotFoundError("fixed split manifest is missing")
    content = split_path.read_bytes()
    records = json.loads(content)
    symbols = r14._expected_symbols()
    expected_split = (data_access.CRYPTO_COMMON_SPLIT_MS
                      + max(data_access.TIMEFRAME_MS.values()))
    expected_keys = {
        str((data_root / "cache/orderblock/bars" / timeframe / f"{symbol}.parquet").resolve())
        for timeframe in ("1h", "4h") for symbol in symbols
    }
    for key in expected_keys:
        record = records.get(key)
        if (not isinstance(record, dict) or record.get("fixed") is not True
                or int(record.get("split_timestamp", -1)) != expected_split):
            raise ValueError("fixed TRAIN split record missing or inconsistent")
    for timeframe in ("1h", "4h"):
        actual_symbols = {
            path.stem for path in (data_root / "cache/orderblock/bars" / timeframe).glob("*.parquet")
        }
        if actual_symbols != set(symbols):
            raise ValueError(f"{timeframe} input file set differs from frozen universe")
    return hashlib.sha256(content).hexdigest(), split_path.stat().st_mtime_ns


def _run_locked(data_root: Path):
    import data_access
    import search_crypto_r19_match_attrition_audit as r19

    r19._assert_no_ledger_writer()
    actual_rows = _ledger_state()
    grid_sha = _grid_hash(CONFIG)
    code_sha = _code_hash()
    prereg_changed = (
        hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
        or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA
    )
    if prereg_changed or actual_rows != EXPECTED_ROWS:
        reason = ("R28 prereg hash differs from the pinned version" if prereg_changed else
                  f"R28 expected {EXPECTED_ROWS} prior rows, observed {actual_rows}")
        actual_config = _config_for_prior_rows(actual_rows)
        actual_grid_sha = _grid_hash(actual_config)
        _append({"status": "failed_before_data_access", "failure_stage": "preflight",
                 "failure_type": "PreregMismatch" if prereg_changed else "DenominatorMismatch",
                 "detail": reason}, actual_grid_sha, code_sha,
                "UNAVAILABLE_BEFORE_TRAIN_INPUT", actual_rows + 1, actual_config)
        raise RuntimeError(reason)
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    wrote = False
    try:
        try:
            split_sha, split_mtime = _split_cache_state(data_root, data_access)
        except Exception as exc:
            _append({"status": "failed_before_data_access", "failure_stage": "split_cache_preflight",
                     "failure_type": type(exc).__name__,
                     "detail": "fixed split cache missing/inconsistent; price files not read"},
                    grid_sha, code_sha, fingerprint, EXPECTED_N, CONFIG)
            wrote = True
            raise
        with heavy_task("R28"):
            from functools import partial
            loader = partial(data_access.iter_train_bars, data_dir=data_root)
            barsets_1h = r14._load_barsets(loader, "1h")
            barsets_4h = r14._load_barsets(loader, "4h")
            fingerprint = common._train_input_fingerprint(
                "R28-4h-1h-train",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h],
            )
            usable = r27._usable_symbols(barsets_1h, barsets_4h)
            if len(usable) < r14.MINIMUM_SYMBOLS:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols across both timeframes"}
            else:
                result = _trial_with_close_location(barsets_1h, barsets_4h)
            result["split_manifest_sha256"] = split_sha
            split_sha_after, split_mtime_after = _split_cache_state(data_root, data_access)
            if split_sha_after != split_sha or split_mtime_after != split_mtime:
                raise RuntimeError("split cache changed during R28; cache writes are forbidden")
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R28 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint, EXPECTED_N, CONFIG)
            wrote = True
    except Exception as exc:
        if not wrote and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r28_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R28 preregistered attempt failed; not G evidence"},
                    grid_sha, code_sha, fingerprint, EXPECTED_N, CONFIG)
        raise
    print(json.dumps({"R28": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


def _acquire_run_locks(data_root: Path):
    lock_dir = data_root / "cache/orderblock/runs"
    paths = [lock_dir / name for name in (
        ".cointrade_train_trials.lock", ".ob_attrition_train_trials.lock")]
    opened = []
    try:
        for path in paths:
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
