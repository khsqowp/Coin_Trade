"""Descriptive attribution of R21's fixed TRAIN trades by direction and UTC year."""
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
from metrics import trade_metrics, wilson_lower
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R23-coin"
PREREG_PATH = HERE / "PREREG_R23_R21_ATTRIBUTION.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_679
EXPECTED_N = 1_680
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R23-R21-TRADE-ATTRIBUTION-BY-DIRECTION-AND-UTC-ENTRY-YEAR",
    "strategy": "unchanged R21 pre-BOS external sweep + R14 fixed execution",
    "groups": ["direction", "utc_entry_year"],
    "cutoff": "2023-11-06T16:00:00Z",
    "bonferroni_n": EXPECTED_N,
    "diagnostic_only": True,
}


def _summarize(records):
    result = {"by_direction": {}, "by_utc_entry_year": {}}
    for axis, key_name in (("by_direction", "direction"),
                           ("by_utc_entry_year", "year")):
        keys = sorted({row[key_name] for row in records})
        for key in keys:
            group = [row for row in records if row[key_name] == key]
            hits = sum(bool(row["target_hit"]) for row in group)
            returns = [row["net_return"] for row in group
                       if row["net_return"] is not None]
            stats = trade_metrics(returns)
            result[axis][str(key)] = {
                "signals": len(group), "target_hits": hits,
                "m2_target_first_rate": hits / len(group),
                "m2_wilson_lower_95": wilson_lower(hits, len(group)),
                "scoreable_trades": len(returns),
                "win_rate": stats.win_rate,
                "expectancy_bps": stats.expectancy_bps,
                "profit_factor": stats.profit_factor,
            }
    return result


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
        "search_crypto_r21_pre_bos_sweep.py",
        "search_crypto_r22_bos_acceptance.py", "data_access.py", "metrics.py",
        "resource_guard.py", "PREREG.md", PREREG_PATH.name,
        "search_crypto_r23_r21_attribution.py",
        "tests/test_search_crypto_r23_r21_attribution.py",
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
        "trial_id": f"R23-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "R23 descriptive attribution only; not a G candidate",
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
                raise RuntimeError("ledger append rollback failed") from rollback_error
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
        raise RuntimeError("R23 prereg changed after import")
    actual_rows = _ledger_rows()
    if actual_rows != EXPECTED_ROWS:
        raise RuntimeError(f"R23 denominator mismatch before data access: {actual_rows}")
    r19._assert_no_ledger_writer()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    result_written = False
    try:
        with heavy_task("R23"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R23-R21-direction-year-attribution",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h])
            captured = []
            original_simulator = r14._simulate_segment

            def capture_segment(bars, funding, zones_by_index):
                trades, audit = original_simulator(bars, funding, zones_by_index)
                for trade in trades:
                    entry_ms = bars[trade.setup.entry_index].timestamp
                    year = datetime.fromtimestamp(entry_ms / 1000, timezone.utc).year
                    captured.append({
                        "direction": trade.setup.zone.direction, "year": year,
                        "target_hit": trade.exit_reason == "target",
                        "net_return": trade.net_return,
                    })
                return trades, audit

            try:
                r14._simulate_segment = capture_segment
                stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
                total = r21._trial_with_filtered_zones(barsets_1h, barsets_4h, stats)
            finally:
                r14._simulate_segment = original_simulator
            grouped = _summarize(captured)
            flat_returns = [row["net_return"] for row in captured
                            if row["net_return"] is not None]
            exact = {
                "trades": len(captured) == total["total_trades"],
                "m2_hits": sum(row["target_hit"] for row in captured) == total["m2_target_hits"],
                "scoreable": len(flat_returns) == total["trades"],
                "ev": trade_metrics(flat_returns).expectancy_bps == total["expectancy_bps"],
                "profit_factor": trade_metrics(flat_returns).profit_factor == total["profit_factor"],
            }
            result = {
                "status": "completed" if all(exact.values()) else "failed/inconsistent",
                "diagnostic_only": True, "total_r21_result": total,
                "zone_funnel": stats, "groups": grouped,
                "reconciliation": exact,
                "captured_trade_count": len(captured),
                "captured_m2_hits": sum(row["target_hit"] for row in captured),
            }
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R23 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint)
            result_written = True
        try:
            r19._assert_no_ledger_writer()
        except Exception as exc:
            print(json.dumps({"R23_post_append_writer_warning": type(exc).__name__}),
                  file=sys.stderr, flush=True)
    except Exception as exc:
        if not result_written:
            _append({"status": "failed", "failure_stage": "r23_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R23 preregistered diagnostic failed; no candidate promotion"},
                    grid_sha, code_sha, fingerprint)
        raise
    print(json.dumps({"R23": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
