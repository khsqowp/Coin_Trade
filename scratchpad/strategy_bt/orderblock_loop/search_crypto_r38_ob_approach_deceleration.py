"""Single preregistered TRAIN test for a directional three-bar approach filter."""
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
ROUND = "R38-coin"
PREREG_PATH = HERE / "PREREG_R38_OB_APPROACH_DECELERATION.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 4_194
EXPECTED_N = 4_195
EXPECTED_SPLIT_SHA = "5873762fedc42ce05025ea76a91b2b2870a5693a0b5bbdc6dd7f7e571d96b1dd"
CUTOFF_MS = 1_699_286_400_000
MIN_FREE_BYTES = 40 * 1024**3
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R38-R14-THREE-BAR-DIRECTIONAL-APPROACH-NONINCREASING-BODY",
    "base": "R14-4h-bos_origin-1h-first-retest-midpoint-next-open",
    "lookback_bars": 3,
    "zone_activation": "first_lookback_index >= zone.signal_index",
    "long": "all_low_gt_zone_high; closes_strictly_descend; abs_body_nonincreasing",
    "short": "all_high_lt_zone_low; closes_strictly_ascend; abs_body_nonincreasing",
    "same_segment_complete_only": True,
    "touch_confirmation_bar_must_be_hourly_contiguous": True,
    "split_manifest_sha256": EXPECTED_SPLIT_SHA,
    "completed_bar_close_cutoff_ms": CUTOFF_MS,
    "entry_exit": "fixed R14; 0.50R;24x1h;12bp;adverse_only",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py",
    "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "search_crypto_r38_ob_approach_deceleration.py",
    "tests/test_search_crypto_r38_ob_approach_deceleration.py",
    "universe/CRYPTO_35.csv",
)
_IMPORT_CODE_SHA = None


class AppendUncertainError(RuntimeError):
    """Append may be partial or durable; reconcile before any retry."""


def _valid_ohlc(bar):
    values = (bar.open, bar.high, bar.low, bar.close)
    return (bar.complete and all(math.isfinite(value) for value in values)
            and bar.low <= min(bar.open, bar.close)
            <= max(bar.open, bar.close) <= bar.high)


def _approach_pass(zone, bars, confirmation_index):
    start = confirmation_index - 3
    if start < zone.signal_index or start < 0:
        return False, "insufficient_post_activation_history"
    approach = bars[start:confirmation_index]
    if (len(approach) != 3 or confirmation_index >= len(bars)
            or any(not _valid_ohlc(bar) for bar in approach)
            or not _valid_ohlc(bars[confirmation_index])):
        return False, "incomplete_or_invalid_approach"
    sequence = [*approach, bars[confirmation_index]]
    if any(b.timestamp - a.timestamp != r14.DURATION_MS
           for a, b in zip(sequence, sequence[1:])):
        return False, "approach_gap"
    bodies = [abs(bar.close - bar.open) for bar in approach]
    closes = [bar.close for bar in approach]
    if zone.direction == "long":
        if any(bar.low <= zone.high for bar in approach):
            return False, "approach_touched_or_entered_zone"
        if not (closes[0] > closes[1] > closes[2]):
            return False, "approach_not_strictly_descending"
    elif zone.direction == "short":
        if any(bar.high >= zone.low for bar in approach):
            return False, "approach_touched_or_entered_zone"
        if not (closes[0] < closes[1] < closes[2]):
            return False, "approach_not_strictly_ascending"
    else:
        return False, "invalid_direction"
    if not (bodies[0] >= bodies[1] >= bodies[2]):
        return False, "approach_body_increased"
    return True, "accepted"


def _trial_with_filter(barsets_1h, barsets_4h):
    stats = {"valid_r14_setups": 0, "approach_accepted_setups": 0,
             "approach_rejected_setups": 0, "approach_rejection_reasons": {}}
    original_segment = r14._simulate_segment

    def simulate_segment(bars, funding, zones_by_index):
        original_setup = r14._make_setup

        def make_setup(zone, confirmation_bar, next_bar, confirmation_index):
            setup, reason = original_setup(
                zone, confirmation_bar, next_bar, confirmation_index)
            if setup is None:
                return setup, reason
            stats["valid_r14_setups"] += 1
            accepted, why = _approach_pass(zone, bars, confirmation_index)
            if not accepted:
                stats["approach_rejected_setups"] += 1
                reasons = stats["approach_rejection_reasons"]
                reasons[why] = reasons.get(why, 0) + 1
                return None, "pre_retest_approach_failed"
            stats["approach_accepted_setups"] += 1
            return setup, reason

        r14._make_setup = make_setup
        try:
            return original_segment(bars, funding, zones_by_index)
        finally:
            r14._make_setup = original_setup

    r14._simulate_segment = simulate_segment
    try:
        result = r14._trial(barsets_1h, barsets_4h)
    finally:
        r14._simulate_segment = original_segment
    result.update(stats)
    _validate_result_contract(result)
    result["detail"] = (
        "R38 three-bar directional close sequence with nonincreasing absolute bodies; "
        "fixed R14; TRAIN exploratory filter, not measured velocity/absorption"
    )
    return result


def _validate_result_contract(result):
    total = result.get("total_trades")
    scoreable = result.get("trades")
    unscorable = result.get("unscorable_funding_trades")
    signals = result.get("m2_signal_count")
    hits = result.get("m2_target_hits")
    if not all(isinstance(value, int) and value >= 0
               for value in (total, scoreable, unscorable, signals, hits)):
        raise ValueError("R38 returned missing/invalid trade scoring counts")
    if (total != signals or total != scoreable + unscorable
            or hits > signals):
        raise ValueError("R38 M2 and scoreable-trade denominators do not reconcile")
    result["scoreable_trade_count"] = scoreable
    result["m2_completed_trade_count"] = signals
    return result


def _assert_cutoff_bars(barsets, timeframe):
    duration = r14.ZONE_DURATION_MS if timeframe == "4h" else r14.DURATION_MS
    for symbol, bars, _funding, _excluded in barsets:
        if any(not bar.complete or bar.timestamp + duration > CUTOFF_MS
               for bar in bars):
            raise ValueError(f"{timeframe} input has incomplete/post-cutoff bar: {symbol}")


def _metadata_has_complete_cutoff_bar(path, timeframe, parquet_reader=None):
    """Read only time/completeness columns; never materialize OHLCV columns."""
    if parquet_reader is None:
        import pyarrow.parquet as pq
        parquet_reader = pq.read_table
    duration = r14.ZONE_DURATION_MS if timeframe == "4h" else r14.DURATION_MS
    table = parquet_reader(
        path, columns=["open_time", "complete"],
        filters=[("open_time", "<=", CUTOFF_MS - duration)],
    )
    names = list(table.schema.names)
    if "open_time" not in names or "complete" not in names:
        return False
    return any(bool(value) for value in table.column("complete").to_pylist())


def _metadata_usable_symbols(data_root, parquet_file_factory=None):
    """Find symbols with at least one all-complete pre-cutoff row group in both TFs."""
    base = Path(data_root) / "cache/orderblock/bars"
    expected = r14._expected_symbols()
    usable_by_timeframe = []
    for timeframe in ("1h", "4h"):
        present = set()
        for symbol in expected:
            path = base / timeframe / f"{symbol}.parquet"
            if path.is_file() and _metadata_has_complete_cutoff_bar(
                    path, timeframe, parquet_file_factory):
                present.add(symbol)
        usable_by_timeframe.append(present)
    return usable_by_timeframe[0] & usable_by_timeframe[1]


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
                    raise RuntimeError("R38 already exists; single attempt cannot repeat")
                count += 1
            return count
    finally:
        csv.field_size_limit(old_limit)


def _source_manifest():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in CODE_FILES}


def _code_hash(manifest=None):
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _grid_hash(config):
    payload = json.dumps([config], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _append(result, grid_sha, code_sha, code_manifest, fingerprint, denominator, config):
    r19._assert_no_ledger_writer()
    row = {
        "trial_id": f"R38-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA,
                              "code_file_sha256": code_manifest},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R38 TRAIN diagnostic; R14-dependent; not G approval",
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
        raise RuntimeError(f"R38 prereg/denominator mismatch before price data: rows={rows}")
    code_manifest = _source_manifest()
    code_sha = _code_hash(code_manifest)
    if _IMPORT_CODE_SHA is not None and code_sha != _IMPORT_CODE_SHA:
        raise RuntimeError("R38 source changed after import")
    if shutil.disk_usage(data_root).free < MIN_FREE_BYTES:
        raise RuntimeError("R38 requires at least 40 GiB free before TRAIN access")
    import data_access
    split_sha, split_mtime = r29._split_cache_state(data_root, data_access)
    if split_sha != EXPECTED_SPLIT_SHA:
        raise RuntimeError("fixed TRAIN split fingerprint differs from preregistration")
    metadata_usable = _metadata_usable_symbols(data_root)
    if len(metadata_usable) < 30:
        raise RuntimeError(
            "fewer than 30 metadata-verified cutoff-safe symbols before candle access")
    fingerprint, written = "UNAVAILABLE_BEFORE_TRAIN_INPUT", False
    try:
        with heavy_task("R38"):
            bars1 = r14._load_barsets(data_access.iter_train_bars, "1h")
            bars4 = r14._load_barsets(data_access.iter_train_bars, "4h")
            _assert_cutoff_bars(bars1, "1h")
            _assert_cutoff_bars(bars4, "4h")
            fingerprint = common._train_input_fingerprint(
                "R38-R14-three-bar-directional-approach-nonincreasing-body",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in bars1]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in bars4],
            )
            usable = r27._usable_symbols(bars1, bars4)
            if len(usable) < 30:
                result = {"status": "unscorable", "symbols": len(usable),
                          "metadata_eligible_symbols": len(metadata_usable),
                          "detail": "loaded complete cutoff-safe symbols fell below 30"}
            else:
                result = _trial_with_filter(bars1, bars4)
            result.update({"split_manifest_sha256": split_sha,
                           "cutoff_safe_symbols": len(usable)})
            if (r29._split_cache_state(data_root, data_access)
                    != (split_sha, split_mtime) or split_sha != EXPECTED_SPLIT_SHA):
                raise RuntimeError("fixed TRAIN split cache changed during R38")
            if (_source_manifest() != code_manifest
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R38 code or prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, _grid_hash(config), code_sha, code_manifest,
                    fingerprint, denominator, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            failure = {"status": "failed", "failure_stage": "r38_train",
                       "failure_type": type(exc).__name__,
                       "detail": "single preregistered attempt failed; not G evidence"}
            _append(failure, _grid_hash(config), code_sha, code_manifest,
                    fingerprint, denominator, config)
        raise
    print(json.dumps({"R38": result, "code_sha": code_sha,
                      "code_file_sha256": code_manifest,
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
