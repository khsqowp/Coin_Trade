"""Single preregistered TRAIN diagnostic: R14 OB plus opposite funding polarity."""
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

import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROUND = "R34-coin"
PREREG_PATH = HERE / "PREREG_R34_OB_FUNDING_POLARITY.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 4_190
EXPECTED_N = 4_191
HOUR_MS = 3_600_000
MAX_FUNDING_AGE_MS = 12 * HOUR_MS
MIN_FREE_BYTES = 40 * 1024**3
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R34-R14-FIRST-RETEST-OPPOSITE-FUNDING-POLARITY",
    "base": "R14-4h-bos_origin-1h-first-retest-midpoint-next-open",
    "funding_asof": "latest settlement timestamp <= confirmation close minus 1h",
    "funding_freshness_ms_inclusive": MAX_FUNDING_AGE_MS,
    "long_requires_rate_lt": 0.0,
    "short_requires_rate_gt": 0.0,
    "require_actual_mark_no_close_fallback": True,
    "entry_exit_cost_funding": "fixed R14; 0.50R;24x1h;12bp;adverse_only",
    "cutoff": "2023-11-06T16:00:00Z",
    "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py",
    "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "search_crypto_r34_ob_funding_polarity.py",
    "tests/test_search_crypto_r34_ob_funding_polarity.py",
    "universe/CRYPTO_35.csv",
)


def _code_hash():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


_IMPORT_CODE_SHA = _code_hash()

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r27_bos_fvg_confluence as r27
import search_crypto_r29_bos_taker_flow as r29
from resource_guard import heavy_task


class AppendUncertainError(RuntimeError):
    """Append may be partial; reconcile the ledger and never retry."""


_ACTIVE_FUNDING = None
_ACTIVE_AUDIT = None


def _funding_filter(zone, confirmation_bar, funding):
    close_ts = confirmation_bar.timestamp + HOUR_MS
    latest_eligible_ts = close_ts - HOUR_MS
    prior = [timestamp for timestamp in funding if timestamp <= latest_eligible_ts]
    if not prior:
        return False, "no_prior_event"
    timestamp = max(prior)
    event = funding[timestamp]
    if timestamp != event.timestamp:
        raise ValueError("funding key and event timestamp differ")
    age = close_ts - timestamp
    if age < HOUR_MS:
        raise ValueError("funding event violates one-hour publication buffer")
    if age > MAX_FUNDING_AGE_MS:
        return False, "stale"
    if event.coverage_gap:
        return False, "coverage_gap"
    rate = event.rate
    if not math.isfinite(rate) or abs(rate) >= 1:
        return False, "invalid_rate"
    if rate == 0:
        return False, "neutral_rate"
    mark = event.mark_price
    if (mark is None or not math.isfinite(mark) or mark <= 0
            or event.used_candle_close_fallback):
        return False, "invalid_or_fallback_mark"
    if zone.direction == "long" and rate >= 0:
        return False, "polarity_mismatch"
    if zone.direction == "short" and rate <= 0:
        return False, "polarity_mismatch"
    return True, "accepted"


def _validate_funding_schema(schema, catalog_text, prereg_text):
    expected = {
        "calc_time": pa.int64(),
        "last_funding_rate": pa.float64(),
        "funding_interval_hours": pa.int64(),
    }
    actual = {field.name: field.type for field in schema}
    if any(actual.get(name) != dtype for name, dtype in expected.items()):
        raise RuntimeError("funding parquet schema contract mismatch")
    if "um_fundingRate" not in catalog_text:
        raise RuntimeError("funding dataset absent from local source catalog")
    if "rate becomes eligible only at its recorded settlement timestamp" not in prereg_text:
        raise RuntimeError("archived funding timestamp contract is not documented")


def _validate_funding_contract(data_root):
    schema_path = (data_root / "external/crypto/binance/um_fundingRate"
                   / "BTCUSDT/2023-11.parquet")
    if not schema_path.is_file():
        raise RuntimeError("funding schema sample is missing; stop before price data")
    schema = pq.read_schema(schema_path)
    catalog = (HERE.parents[2] / "data_sources/CRYPTO_SOURCES.md").read_text(encoding="utf-8")
    timestamp_prereg = (HERE.parents[2] / "docs/research/inventory"
                        / "PREREG_FUNDING_TAIL_REVERSAL_20261120.md").read_text(encoding="utf-8")
    _validate_funding_schema(schema, catalog, timestamp_prereg)
    return hashlib.sha256(schema.serialize().to_pybytes()).hexdigest()


def _trial_with_funding_filter(barsets_1h, barsets_4h):
    """Wrap only setup admission; R14's entry, exits and holding funding stay intact."""
    global _ACTIVE_FUNDING, _ACTIVE_AUDIT
    audit = {
        "funding_filter_candidates": 0, "funding_filter_accepted": 0,
        "funding_filter_no_prior_event": 0, "funding_filter_stale": 0,
        "funding_filter_coverage_gap": 0, "funding_filter_invalid_rate": 0,
        "funding_filter_neutral_rate": 0,
        "funding_filter_invalid_or_fallback_mark": 0,
        "funding_filter_polarity_mismatch": 0,
    }
    funding_by_first_id = {}
    for _symbol, bars, funding, _excluded in barsets_1h:
        for segment in r14._segments(bars, HOUR_MS)[0]:
            key = id(segment[0])
            if key in funding_by_first_id:
                raise ValueError("R34 segment identity collision")
            funding_by_first_id[key] = funding

    original_make_setup = r14._make_setup
    original_simulate_segment = r14._simulate_segment

    def filtered_make_setup(zone, confirmation_bar, next_bar, confirmation_index):
        setup, reason = original_make_setup(zone, confirmation_bar, next_bar,
                                            confirmation_index)
        if setup is None:
            return setup, reason
        if _ACTIVE_FUNDING is None or _ACTIVE_AUDIT is None:
            raise RuntimeError("R34 funding context missing at setup")
        audit["funding_filter_candidates"] += 1
        accepted, status = _funding_filter(zone, confirmation_bar, _ACTIVE_FUNDING)
        audit[f"funding_filter_{status}"] += 1
        if not accepted:
            return None, "funding_polarity"
        return setup, reason

    def contextual_simulate_segment(bars, segment_funding, zones_by_index):
        global _ACTIVE_FUNDING, _ACTIVE_AUDIT
        if not bars or id(bars[0]) not in funding_by_first_id:
            raise RuntimeError("R34 could not map segment to full symbol funding history")
        previous_funding, previous_audit = _ACTIVE_FUNDING, _ACTIVE_AUDIT
        _ACTIVE_FUNDING = funding_by_first_id[id(bars[0])]
        _ACTIVE_AUDIT = audit
        try:
            return original_simulate_segment(bars, segment_funding, zones_by_index)
        finally:
            _ACTIVE_FUNDING, _ACTIVE_AUDIT = previous_funding, previous_audit

    try:
        r14._make_setup = filtered_make_setup
        r14._simulate_segment = contextual_simulate_segment
        result = r14._trial(barsets_1h, barsets_4h)
    finally:
        r14._make_setup = original_make_setup
        r14._simulate_segment = original_simulate_segment
        _ACTIVE_FUNDING = _ACTIVE_AUDIT = None
    if audit["funding_filter_candidates"] != (
            audit["funding_filter_accepted"]
            + sum(value for key, value in audit.items()
                  if key.startswith("funding_filter_")
                  and key not in ("funding_filter_candidates", "funding_filter_accepted"))):
        raise AssertionError("R34 funding-filter funnel does not reconcile")
    result.update(audit)
    result["detail"] = "R34 opposite latest pre-close funding polarity + fixed R14; TRAIN only"
    return result


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
                    raise RuntimeError("R34 already exists; single attempt cannot repeat")
                rows += 1
            return rows
    finally:
        csv.field_size_limit(old)


def _grid_hash(config):
    return hashlib.sha256(json.dumps([config], sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, config):
    r19._assert_no_ledger_writer()
    record = {
        "trial_id": f"R34-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R34 TRAIN diagnostic; not independent or G approval",
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
        raise FileNotFoundError("research lock directory is absent; refusing to create it")
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
        raise RuntimeError(f"R34 preflight mismatch before market data access: rows={rows}")
    code_sha = _code_hash()
    if code_sha != _IMPORT_CODE_SHA:
        raise RuntimeError("R34 source changed after import; refusing stale-code execution")
    if shutil.disk_usage(data_root).free < MIN_FREE_BYTES:
        raise RuntimeError("R34 requires at least 40 GiB free before TRAIN access")
    funding_schema_sha = _validate_funding_contract(data_root)
    import data_access
    if _code_hash() != code_sha:
        raise RuntimeError("R34 source changed during dependency import")
    fingerprint, written = "UNAVAILABLE_BEFORE_TRAIN_INPUT", False
    try:
        split_sha, split_mtime = r29._split_cache_state(data_root, data_access)
        with heavy_task("R34"):
            bars1 = r14._load_barsets(data_access.iter_train_bars, "1h")
            bars4 = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R34-R14-OB-opposite-funding-polarity",
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
                result = _trial_with_funding_filter(bars1, bars4)
            result.update({"split_manifest_sha256": split_sha,
                           "cutoff_safe_symbols": len(usable),
                           "funding_schema_sample_sha256": funding_schema_sha,
                           "funding_publication_latency": "unknown; 1h buffer is conservative assumption"})
            if r29._split_cache_state(data_root, data_access) != (split_sha, split_mtime):
                raise RuntimeError("fixed TRAIN split cache changed during R34")
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R34 code or prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, _grid_hash(config), code_sha, fingerprint, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r34_train",
                     "failure_type": type(exc).__name__,
                     "detail": "single preregistered attempt failed; not G evidence"},
                    _grid_hash(config), code_sha, fingerprint, config)
        raise
    print(json.dumps({"R34": result, "code_sha": code_sha,
                      "train_fingerprint": fingerprint,
                      "bonferroni_denominator": EXPECTED_N},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
