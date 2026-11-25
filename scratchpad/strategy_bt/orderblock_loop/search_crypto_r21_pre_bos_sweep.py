"""Single TRAIN test: external liquidity sweep before BOS-origin OB formation."""
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
from crypto import r4_zones
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R21-coin"
PREREG_PATH = HERE / "PREREG_R21_PRE_BOS_LIQUIDITY_SWEEP.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_677
EXPECTED_N = 1_678
BAR_MS = 4 * 3_600_000
SWEEP_LOOKBACK = 20
BOS_CONFIRM_BARS = 3
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R21-OB-PRE-FORMATION-EXTERNAL-LIQUIDITY-SWEEP",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "bos_origin", "sweep_lookback": SWEEP_LOOKBACK,
    "sweep_to_bos_bars": [1, BOS_CONFIRM_BARS],
    "long_sweep": "low < prior20_min_low and close > prior20_min_low",
    "short_sweep": "high > prior20_max_high and close < prior20_max_high",
    "entry": "R14 first retest close beyond midpoint then next 1h open",
    "stop_buffer_atr": r14.STOP_BUFFER_ATR,
    "reward_r": r14.REWARD_R, "max_holding_bars": r14.MAX_HOLDING_BARS,
    "deadline_bars": r14.DEADLINE, "round_trip_cost_bps": 12,
    "funding_order_policy": r14.FUNDING_ORDER_POLICY,
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}


class AppendRollbackError(OSError):
    """A partial ledger append could not be safely rolled back."""


def _external_sweep(bars, index, direction):
    """Detect a completed-bar sweep of the previous 20-bar external extreme."""
    if index < SWEEP_LOOKBACK:
        return False
    prior = bars[index - SWEEP_LOOKBACK:index]
    level = (min(bar.low for bar in prior) if direction == "long"
             else max(bar.high for bar in prior))
    bar = bars[index]
    if direction == "long":
        return bar.low < level and bar.close > level
    return bar.high > level and bar.close < level


def _pre_bos_sweep(bars, bos_index, direction):
    start = max(SWEEP_LOOKBACK, bos_index - BOS_CONFIRM_BARS)
    return any(_external_sweep(bars, index, direction)
               for index in range(start, bos_index))


def _filtered_zone_builder(stats):
    original = r14.r4_zones

    def build(bars, definition):
        zones = original(bars, definition)
        if definition != "bos_origin":
            return zones
        stats["raw_bos_zones"] += len(zones)
        selected = [zone for zone in zones
                    if _pre_bos_sweep(bars, zone.signal_index, zone.direction)]
        stats["pre_bos_sweep_zones"] += len(selected)
        return selected

    return original, build


def _trial_with_filtered_zones(barsets_1h, barsets_4h, stats):
    original, filtered = _filtered_zone_builder(stats)
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
            return sum(1 for _ in csv.DictReader(stream))
    finally:
        csv.field_size_limit(old)


def _code_hash():
    names = ("crypto.py", "search_crypto.py", "search_crypto_r14.py",
             "search_crypto_r19_match_attrition_audit.py",
             "data_access.py", "metrics.py", "resource_guard.py", "PREREG.md",
             PREREG_PATH.name, "search_crypto_r21_pre_bos_sweep.py",
             "tests/test_search_crypto_r21_pre_bos_sweep.py", "universe/CRYPTO_35.csv")
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
        "trial_id": f"R21-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R21 TRAIN candidate; not OOS or G approval",
    }
    payload_stream = io.StringIO(newline="")
    csv.DictWriter(payload_stream, fieldnames=common.FIELDS).writerow(row)
    payload = payload_stream.getvalue().encode()
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    before = os.fstat(fd).st_size
    try:
        if os.write(fd, payload) != len(payload):
            try:
                os.ftruncate(fd, before)
            except OSError as rollback_error:
                raise AppendRollbackError("short append; rollback failed") from rollback_error
            raise OSError("short append rolled back")
    except OSError:
        raise
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
        raise RuntimeError("R21 prereg changed after import")
    if _ledger_rows() != EXPECTED_ROWS:
        raise RuntimeError(f"R21 denominator mismatch before data access: {_ledger_rows()}")
    r19._assert_no_ledger_writer()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    result_written = False
    try:
        with heavy_task("R21"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R21-pre-bos-sweep-4h-ob-1h-entry",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h])
            stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
            result = _trial_with_filtered_zones(barsets_1h, barsets_4h, stats)
            result.update(stats)
            result["detail"] = "R21 pre-BOS external sweep + fixed R14 entry/exit; TRAIN only"
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R21 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint)
            result_written = True
        try:
            r19._assert_no_ledger_writer()
        except Exception as exc:
            print(json.dumps({"R21_post_append_writer_warning": type(exc).__name__}),
                  file=sys.stderr, flush=True)
    except Exception as exc:
        if not result_written and not isinstance(exc, AppendRollbackError):
            failure = {"status": "failed", "failure_stage": "r21_train",
                       "failure_type": type(exc).__name__,
                       "detail": "R21 preregistered attempt failed; no strategy approval"}
            _append(failure, grid_sha, code_sha, fingerprint)
        raise
    print(json.dumps({"R21": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
