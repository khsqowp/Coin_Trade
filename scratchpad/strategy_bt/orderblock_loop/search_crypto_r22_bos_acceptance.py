"""Single preregistered TRAIN test: R21 sweep plus next-4h BOS acceptance."""
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
import search_crypto_r21_pre_bos_sweep as r21
from crypto import Zone
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R22-coin"
PREREG_PATH = HERE / "PREREG_R22_BOS_ACCEPTANCE.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_678
EXPECTED_N = 1_679
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R22-R21-SWEEP-NEXT-4H-BOS-ACCEPTANCE",
    "source": "R21 fixed pre-BOS external sweep and R14 fixed execution",
    "acceptance": "next completed 4h close > zone.high long; < zone.low short",
    "activation_delay_4h_bars": 1,
    "entry": "first 1h retest midpoint reclaim then next open",
    "stop_buffer_atr": r14.STOP_BUFFER_ATR,
    "reward_r": r14.REWARD_R,
    "max_holding_bars": r14.MAX_HOLDING_BARS,
    "round_trip_cost_bps": 12,
    "funding_order_policy": r14.FUNDING_ORDER_POLICY,
    "cutoff": "2023-11-06T16:00:00Z",
    "bonferroni_n": EXPECTED_N,
}


class AppendRollbackError(OSError):
    """Ledger append was partial and could not be safely rolled back."""


def _zones_for_acceptance(stats):
    original = r14.r4_zones

    def build(bars, definition):
        zones = original(bars, definition)
        if definition != "bos_origin":
            return zones
        stats["raw_bos_zones"] += len(zones)
        accepted_zones = []
        for zone in zones:
            if not r21._pre_bos_sweep(bars, zone.signal_index, zone.direction):
                continue
            stats["pre_bos_sweep_zones"] += 1
            confirm_index = zone.signal_index + 1
            if confirm_index >= len(bars):
                stats["acceptance_confirmation_unavailable"] += 1
                continue
            close = bars[confirm_index].close
            accepted = (close > zone.high if zone.direction == "long"
                        else close < zone.low)
            if not accepted:
                stats["acceptance_rejected_zones"] += 1
                continue
            stats["acceptance_confirmed_zones"] += 1
            accepted_zones.append(Zone(confirm_index, zone.origin_index,
                                       zone.direction, zone.low, zone.high,
                                       zone.atr_at_signal))
        return accepted_zones

    return original, build


def _trial_with_acceptance(barsets_1h, barsets_4h, stats):
    original, filtered = _zones_for_acceptance(stats)
    r14.r4_zones = filtered
    try:
        return r14._trial(barsets_1h, barsets_4h)
    finally:
        r14.r4_zones = original


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
        "search_crypto_r22_bos_acceptance.py",
        "tests/test_search_crypto_r22_bos_acceptance.py",
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
        "trial_id": f"R22-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R22 TRAIN candidate; not OOS or G approval",
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
                raise AppendRollbackError("short append; rollback failed") from rollback_error
            raise OSError("short append rolled back")
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


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


def _run_locked():
    import data_access
    import search_crypto_r19_match_attrition_audit as r19

    if (hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError("R22 prereg changed after import")
    actual_rows = _ledger_rows()
    if actual_rows != EXPECTED_ROWS:
        raise RuntimeError(f"R22 denominator mismatch before data access: {actual_rows}")
    r19._assert_no_ledger_writer()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    result_written = False
    try:
        with heavy_task("R22"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R22-sweep-bos-acceptance-4h-ob-1h-entry",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h])
            stats = {
                "raw_bos_zones": 0, "pre_bos_sweep_zones": 0,
                "acceptance_confirmed_zones": 0,
                "acceptance_rejected_zones": 0,
                "acceptance_confirmation_unavailable": 0,
            }
            result = _trial_with_acceptance(barsets_1h, barsets_4h, stats)
            result.update(stats)
            result["detail"] = "R22 R21 sweep + next completed 4h BOS acceptance; activation delayed; TRAIN only"
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R22 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint)
            result_written = True
        try:
            r19._assert_no_ledger_writer()
        except Exception as exc:
            print(json.dumps({"R22_post_append_writer_warning": type(exc).__name__}),
                  file=sys.stderr, flush=True)
    except Exception as exc:
        if not result_written and not isinstance(exc, AppendRollbackError):
            _append({"status": "failed", "failure_stage": "r22_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R22 preregistered attempt failed; no strategy approval"},
                    grid_sha, code_sha, fingerprint)
        raise
    print(json.dumps({"R22": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
