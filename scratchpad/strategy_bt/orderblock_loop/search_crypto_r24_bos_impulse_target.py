"""Single TRAIN strategy test with target fixed at the completed BOS impulse extreme."""
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
from crypto import Setup
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R24-coin"
PREREG_PATH = HERE / "PREREG_R24_BOS_IMPULSE_EXTREME_TARGET.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_680
EXPECTED_N = 1_681
HOUR_MS = r14.DURATION_MS
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R24-R21-SWEEP-BOS-IMPULSE-EXTREME-TARGET",
    "entry": "R21/R14 first 1h retest midpoint reclaim; marketable limit at next open capped by structural target; cancel if open is at/past target",
    "target": "max high / min low of four complete 1h bars before mapped R14 activation index",
    "target_invalid": ["missing_or_nonconsecutive_four_bars", "not_ahead_of_entry"],
    "stop_buffer_atr": r14.STOP_BUFFER_ATR,
    "max_holding_bars": r14.MAX_HOLDING_BARS,
    "round_trip_cost_bps": 12,
    "funding_order_policy": r14.FUNDING_ORDER_POLICY,
    "cutoff": "2023-11-06T16:00:00Z",
    "bonferroni_n": EXPECTED_N,
}


class AppendRollbackError(OSError):
    """A partial ledger append could not be safely rolled back."""


def _structure_target(bars, zone, entry_price):
    """Return the BOS 4h candle extreme from its four completed 1h constituents."""
    end = zone.signal_index
    start = end - 4
    if start < 0:
        return None, "structure_target_unavailable"
    impulse = bars[start:end]
    if (len(impulse) != 4 or not all(bar.complete for bar in impulse)
            or any(b.timestamp - a.timestamp != HOUR_MS
                   for a, b in zip(impulse, impulse[1:]))):
        return None, "structure_target_unavailable"
    target = (max(bar.high for bar in impulse) if zone.direction == "long"
              else min(bar.low for bar in impulse))
    if ((zone.direction == "long" and target <= entry_price)
            or (zone.direction == "short" and target >= entry_price)):
        return None, "structure_target_not_ahead"
    return target, None


def _make_setup_with_structure_target(base_make_setup, bars, zone,
                                      confirmation_bar, next_bar,
                                      confirmation_index, stats, target_r_values):
    setup, reason = base_make_setup(zone, confirmation_bar, next_bar,
                                    confirmation_index)
    if setup is None:
        return None, reason
    target, invalid = _structure_target(bars, zone, setup.entry_price)
    if invalid:
        stats[invalid] += 1
        return None, invalid
    risk = abs(setup.entry_price - setup.stop)
    if risk <= 0:
        stats["structure_target_unavailable"] += 1
        return None, "structure_target_unavailable"
    target_r_values.append(abs(target - setup.entry_price) / risk)
    return Setup(setup.zone, setup.entry_index, setup.entry_price,
                 setup.stop, target), "setup"


def _trial_with_structure_target(barsets_1h, barsets_4h, stats, target_r_values):
    original_simulator = r14._simulate_segment
    original_setup_builder = r14._make_setup

    def simulate_with_structural_target(bars, funding, zones_by_index):
        def build_setup(zone, confirmation_bar, next_bar, confirmation_index):
            return _make_setup_with_structure_target(
                original_setup_builder, bars, zone, confirmation_bar, next_bar,
                confirmation_index, stats, target_r_values)

        r14._make_setup = build_setup
        try:
            return original_simulator(bars, funding, zones_by_index)
        finally:
            r14._make_setup = original_setup_builder

    r14._simulate_segment = simulate_with_structural_target
    try:
        zone_stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
        result = r21._trial_with_filtered_zones(barsets_1h, barsets_4h, zone_stats)
        result.update(zone_stats)
        result.update(stats)
        result["structure_target_distance_r_min"] = min(target_r_values) if target_r_values else None
        result["structure_target_distance_r_max"] = max(target_r_values) if target_r_values else None
        result["structure_target_distance_r_mean"] = (
            sum(target_r_values) / len(target_r_values) if target_r_values else None)
        return result
    finally:
        r14._simulate_segment = original_simulator
        r14._make_setup = original_setup_builder


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
        "search_crypto_r24_bos_impulse_target.py",
        "tests/test_search_crypto_r24_bos_impulse_target.py",
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
        "trial_id": f"R24-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R24 TRAIN candidate; not OOS or G approval",
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
        raise RuntimeError("R24 prereg changed after import")
    actual_rows = _ledger_rows()
    if actual_rows != EXPECTED_ROWS:
        raise RuntimeError(f"R24 denominator mismatch before data access: {actual_rows}")
    r19._assert_no_ledger_writer()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    result_written = False
    try:
        with heavy_task("R24"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R24-R21-BOS-impulse-extreme-target-4h-1h",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h])
            stats = {"structure_target_unavailable": 0,
                     "structure_target_not_ahead": 0}
            target_r_values = []
            result = _trial_with_structure_target(
                barsets_1h, barsets_4h, stats, target_r_values)
            result["detail"] = "R24 R21 sweep/entry with prior completed BOS impulse extreme target; TRAIN only"
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R24 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint)
            result_written = True
        try:
            r19._assert_no_ledger_writer()
        except Exception as exc:
            print(json.dumps({"R24_post_append_writer_warning": type(exc).__name__}),
                  file=sys.stderr, flush=True)
    except Exception as exc:
        if not result_written and not isinstance(exc, AppendRollbackError):
            _append({"status": "failed", "failure_stage": "r24_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R24 preregistered strategy attempt failed; no G approval"},
                    grid_sha, code_sha, fingerprint)
        raise
    print(json.dumps({"R24": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
