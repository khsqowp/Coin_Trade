"""Count fixed R18 control-candidate attrition; never calculate outcomes."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import os
import subprocess
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r15 as r15
import search_crypto_r18_ob_matched_candle as r18
from crypto import r4_zones
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R19-coin"
PREREG_PATH = HERE / "PREREG_R19_R18_MATCHING_ATTRITION.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_675
EXPECTED_N = 1_676
DETAIL_PREREG_NAME = "PREREG_R19_R18_MATCHING_ATTRITION.md"
EXTRA_CODE_NAMES: tuple[str, ...] = ()
LOCK_NAME = ".ob_attrition_train_trials.lock"
CONFIG = {
    "experiment": "R19-R18-CONTROL-CANDIDATE-ATTRITION-ONLY",
    "timeframe": "4h", "definition": "bos_origin", "lag_bars": [25, 180],
    "prehistory": 252, "same_direction": True, "ema": "R18 exact EMA50/200",
    "recent_bos_exclusion": 48, "calipers": "R18 unchanged",
    "greedy_overlap": "R18 unchanged; no outcomes read",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()


def _funnel(bars, events, zones, states, occupied_outcomes=None):
    """Return candidate-pair and event counts at each preregistered filter."""
    stage_names = ("time_and_history", "same_candle_direction", "same_ema_state",
                   "no_bos_last_48", "feature_available", "calipers", "greedy_nonoverlap")
    pairs = {name: 0 for name in stage_names}
    events_kept = {name: 0 for name in stage_names}
    used_controls: set[int] = set()
    occupied = occupied_outcomes if occupied_outcomes is not None else set()
    bos_indices = sorted(zones)
    selected = 0
    raw_with_prehistory = feature_valid_events = 0

    events = sorted(events, key=lambda event: (event.timestamp, event.index))
    if len({event.index for event in events}) != len(events):
        raise ValueError("duplicate BOS event index")
    selected_controls = []
    for event in events:
        i = event.index
        if i < 252:
            continue
        raw_with_prehistory += 1
        if event.feature is not None and event.trend is not None:
            feature_valid_events += 1
        candidates = list(range(max(252, i - 180), i - 24))
        candidates = [j for j in candidates if 25 <= i - j <= 180]
        stages = [candidates]
        stages.append([j for j in stages[-1]
                       if bars[j].close != bars[j].open
                       and ("long" if bars[j].close > bars[j].open else "short") == event.direction])
        stages.append([j for j in stages[-1]
                       if event.trend is not None and states[j] == event.trend])
        stages.append([j for j in stages[-1]
                       if not any(j - 48 <= bos <= j for bos in bos_indices)])
        feature_cache = {j: r18._feature(bars, j) for j in stages[-1]}
        stages.append([j for j in stages[-1]
                       if event.feature is not None and feature_cache[j] is not None])
        distances = {j: r18._distance(event.feature, feature_cache[j]) for j in stages[-1]}
        stages.append([j for j in stages[-1] if distances[j] is not None])
        viable = [j for j in stages[-1]
                  if j not in used_controls
                  and not (set(r18._observed_window_timestamps(bars, j))
                           | set(r18._observed_window_timestamps(bars, i))) & occupied]
        stages.append(viable)

        for name, candidate_indices in zip(stage_names, stages):
            pairs[name] += len(candidate_indices)
            events_kept[name] += bool(candidate_indices)
        if viable:
            chosen = min(viable, key=lambda j: (distances[j], bars[j].timestamp))
            used_controls.add(chosen)
            occupied.update(r18._observed_window_timestamps(bars, chosen))
            occupied.update(r18._observed_window_timestamps(bars, i))
            selected += 1
            selected_controls.append((i, chosen))

    return {
        "candidate_pairs_by_stage": pairs,
        "events_with_candidate_by_stage": events_kept,
        "raw_bos_events": len(events),
        "events_with_252_prehistory": raw_with_prehistory,
        "events_with_feature_and_ema": feature_valid_events,
        "greedy_selected": selected,
        "selected_controls": selected_controls,
    }


def _funnel_symbol_segments(segment_inputs):
    occupied = set()
    results = []
    for bars, events, zones, states in segment_inputs:
        results.append(_funnel(bars, events, zones, states, occupied))
    return results


def _expected_symbols():
    return r18._expected_symbols()


def _ledger_rows():
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            return sum(1 for _ in csv.DictReader(stream))
    finally:
        csv.field_size_limit(old)


def _writable_ledger_pids(lsof_fields: str, current_pid: int) -> set[int]:
    writers = set()
    pid = None
    fd = ""
    for line in lsof_fields.splitlines():
        if line.startswith("p"):
            try:
                pid = int(line[1:])
            except ValueError:
                pid = None
        elif line.startswith("f"):
            fd = line[1:]
        elif line.startswith("n") and line[1:].endswith("TRAIN_TRIALS.csv"):
            if pid is not None and pid != current_pid and fd.endswith(("w", "u")):
                writers.add(pid)
    return writers


def _assert_no_ledger_writer():
    result = subprocess.run(["lsof", "-nP", "-Fpfn", str(common.CSV_PATH)],
                            capture_output=True, text=True, timeout=15, check=False)
    if result.returncode not in (0, 1) or "can't get" in result.stderr.lower():
        raise RuntimeError("cannot establish ledger writer absence")
    writers = _writable_ledger_pids(result.stdout, os.getpid())
    if writers:
        raise RuntimeError(f"ledger has another writable handle: {sorted(writers)}")


def _code_hash():
    names = ("crypto.py", "search_crypto.py", "search_crypto_r15.py",
             "search_crypto_r18_ob_matched_candle.py", "search_crypto_r19_match_attrition_audit.py",
             "data_access.py", "resource_guard.py", "PREREG.md",
             "PREREG_R18_OB_MATCHED_CANDLE_DIAGNOSTIC.md",
             "tests/test_search_crypto_r19_match_attrition_audit.py", "universe/CRYPTO_35.csv",
             DETAIL_PREREG_NAME, *EXTRA_CODE_NAMES)
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _append(metric, grid_sha, code_sha, fingerprint):
    _assert_no_ledger_writer()
    exists = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        if tuple(next(csv.reader(stream))) != common.FIELDS:
            raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    row = {
        "trial_id": f"R19-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**metric, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": f"{ROUND} descriptive attrition diagnostic; not strategy/G evidence",
    }
    if not exists:
        raise ValueError("ledger unexpectedly missing")
    payload_stream = io.StringIO(newline="")
    csv.DictWriter(payload_stream, fieldnames=common.FIELDS).writerow(row)
    payload = payload_stream.getvalue().encode()
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    before = os.fstat(fd).st_size
    try:
        written = os.write(fd, payload)
        if written != len(payload):
            raise OSError("short ledger append")
    except OSError:
        os.ftruncate(fd, before)
        raise
    finally:
        os.close(fd)


def run():
    data_root = Path(os.environ.get(
        "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    lock_path = data_root / "cache/orderblock/runs" / LOCK_NAME
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _run_locked()
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def _run_locked():
    import data_access

    if (hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError(f"{ROUND} prereg changed after import")
    if _ledger_rows() != EXPECTED_ROWS:
        raise RuntimeError(f"{ROUND} denominator mismatch before data access: {_ledger_rows()}")
    _assert_no_ledger_writer()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    result_written = False
    fingerprint = "UNAVAILABLE_BEFORE_INPUT"
    try:
        with heavy_task("R19"):
            aggregates = []
            all_bars = []
            for symbol, bars, _funding in data_access.iter_train_bars("4h"):
                closed = [bar for bar in bars if bar.complete]
                all_bars.append((symbol, closed, len(bars) - len(closed)))
            r18._assert_train_cutoff(all_bars)
            if ({row[0] for row in all_bars} != set(_expected_symbols())
                    or len(all_bars) != len({row[0] for row in all_bars})):
                raise ValueError("TRAIN symbols differ from frozen universe")
            fingerprint = common._train_input_fingerprint(
                "R19-R18-matching-attrition-4h",
                [(f"{symbol}:4h", bars, {}, excluded)
                 for symbol, bars, excluded in all_bars])
            for symbol, bars, _excluded in all_bars:
                segment_inputs = []
                for segment in r18._split_segments(bars)[0]:
                    events, zones, states = r18._events_for_segment(symbol, segment)
                    segment_inputs.append((segment, events, zones, states))
                aggregates.extend(_funnel_symbol_segments(segment_inputs))
            combined = {
                "status": "completed", "segments": len(aggregates),
                "symbols_with_bars": sum(bool(bars) for _, bars, _ in all_bars),
                "symbols_in_input": len(all_bars), "raw_bos_events": 0,
                "events_with_252_prehistory": 0, "events_with_feature_and_ema": 0,
                "greedy_selected": 0,
                "candidate_pairs_by_stage": defaultdict(int),
                "events_with_candidate_by_stage": defaultdict(int),
            }
            for item in aggregates:
                for key in ("raw_bos_events", "events_with_252_prehistory",
                            "events_with_feature_and_ema", "greedy_selected"):
                    combined[key] += item[key]
                for name, count in item["candidate_pairs_by_stage"].items():
                    combined["candidate_pairs_by_stage"][name] += count
                for name, count in item["events_with_candidate_by_stage"].items():
                    combined["events_with_candidate_by_stage"][name] += count
            combined["candidate_pairs_by_stage"] = dict(combined["candidate_pairs_by_stage"])
            combined["events_with_candidate_by_stage"] = dict(combined["events_with_candidate_by_stage"])
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R19 source/prereg changed during run")
            _assert_no_ledger_writer()
            _append(combined, grid_sha, code_sha, fingerprint)
            result_written = True
            try:
                _assert_no_ledger_writer()
            except Exception as postcheck_error:
                combined["post_append_writer_check"] = type(postcheck_error).__name__
                print(json.dumps({"R19_post_append_writer_check": type(postcheck_error).__name__}),
                      file=sys.stderr, flush=True)
    except Exception as exc:
        if not result_written:
            failure = {"status": "failed", "failure_stage": "r19_attrition",
                       "failure_type": type(exc).__name__,
                       "detail": "R19 diagnostic failed; no strategy result"}
            try:
                _append(failure, grid_sha, code_sha, fingerprint)
                try:
                    _assert_no_ledger_writer()
                except Exception as postcheck_error:
                    print(json.dumps({"R19_failure_row_postcheck": type(postcheck_error).__name__}),
                          file=sys.stderr, flush=True)
            except Exception as ledger_exc:
                print(json.dumps({"R19": "failed", "primary_error": type(exc).__name__,
                                  "ledger_error": type(ledger_exc).__name__,
                                  "ledger_recorded": False}), file=sys.stderr, flush=True)
                raise RuntimeError("R19 failed and failure row could not be recorded") from exc
        raise
    print(json.dumps(combined, sort_keys=True), flush=True)


if __name__ == "__main__":
    run()
