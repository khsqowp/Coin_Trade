"""Frozen first-touch spot/perpetual OB falsification screen for development data only."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chart_predictor.indicators import atr as wilder_atr
from scripts.research.audit_crypto_minute_archive import _months
from scripts.research.fingerprint_crypto_candidate_inputs import fingerprint

DATASETS = {"spot": "spot_klines_1m", "perp": "um_klines_1m"}
SYMBOLS = (
    "AAVEUSDT", "ADAUSDT", "APTUSDT", "ARBUSDT", "ATOMUSDT", "AVAXUSDT", "BCHUSDT",
    "BNBUSDT", "BTCUSDT", "CRVUSDT", "DOGEUSDT", "DOTUSDT", "ENAUSDT", "ETCUSDT",
    "ETHUSDT", "FILUSDT", "HBARUSDT", "INJUSDT", "LINKUSDT", "LTCUSDT", "NEARUSDT",
    "OPUSDT", "POLUSDT", "RUNEUSDT", "SEIUSDT", "SOLUSDT", "SUIUSDT", "TIAUSDT",
    "TRXUSDT", "UNIUSDT", "WLDUSDT", "XRPUSDT",
)
MONTHS = tuple(_months("2024-10", "2026-10"))
START_MS = int(datetime(2024, 10, 1, tzinfo=timezone.utc).timestamp() * 1000)
CUTOFF_MS = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000)
HORIZON_MINUTES = 100
BASE_FEE = 0.001
STRESS_FEE = 0.003
FROZEN_INPUT_SHA256 = "de5c87e883f4c3e00b818c541a0e36d1320f08a2577dc063d2bb9ff519ab9036"
PREREG_PATH = ROOT / "docs/research/inventory/PREREG_SPOT_PERP_OB_RECLAIM_DEV_20261122.md"
FINGERPRINT_PATH = ROOT / "docs/research/inventory/crypto_ob_reclaim_input_fingerprint_20261122.json"
FREEZE_PATH = ROOT / "docs/research/inventory/crypto_ob_reclaim_freeze_20261122.json"
EXPECTED_BRANCH = "research/bat-harmonic-validation-20261120"


def aggregate_5m(times: np.ndarray, opened: np.ndarray, high: np.ndarray,
                 low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> dict[str, np.ndarray]:
    """Aggregate a complete, sorted 1m UTC series; reject holes and partial buckets."""
    arrays = [np.asarray(x) for x in (times, opened, high, low, close, volume)]
    if not arrays[0].size or any(x.ndim != 1 or len(x) != len(arrays[0]) for x in arrays):
        raise ValueError("minute arrays must be nonempty and equally sized")
    t = arrays[0].astype(np.int64, copy=False)
    if np.any(np.diff(t) != 60_000):
        raise ValueError("minute timestamps contain a gap, duplicate, or bad step")
    if np.any(t % 60_000 != 0):
        raise ValueError("minute timestamps are not UTC minute boundaries")
    if len(t) % 5:
        raise ValueError("minute series ends with a partial 5m bucket")
    groups = len(t) // 5
    m = t.reshape(groups, 5)
    expected = m[:, :1] + np.arange(5, dtype=np.int64)[None, :] * 60_000
    if np.any(m != expected) or np.any(m[:, 0] % 300_000 != 0):
        raise ValueError("incomplete or misaligned UTC 5m bucket")
    o, h, l, c, v = (np.asarray(x, dtype=np.float64).reshape(groups, 5)
                  for x in arrays[1:])
    valid = np.all(np.isfinite(o) & np.isfinite(h) & np.isfinite(l) &
                   np.isfinite(c) & np.isfinite(v), axis=1)
    result = {"time": m[:, 0].copy(), "open": o[:, 0].copy(), "high": h.max(axis=1),
              "low": l.min(axis=1), "close": c[:, -1].copy(), "volume": v.sum(axis=1)}
    for name in ("open", "high", "low", "close", "volume"):
        result[name][~valid] = np.nan
    return result


def first_touch_events(perp: dict[str, np.ndarray], spot: dict[str, np.ndarray],
                       atr_values: np.ndarray, eligible: np.ndarray) -> tuple[list[dict], int, int]:
    """Return candidate and unfiltered first-touch rows using causal 5m bars only."""
    n = len(perp["time"])
    if any(len(values) != n for values in (*perp.values(), *spot.values(), atr_values, eligible)):
        raise ValueError("5m input lengths differ")
    zones: list[dict] = []
    events = []
    ambiguous = 0
    anchors = int(np.count_nonzero(eligible))
    for i in range(n):
        current = [bars[name][i] for bars in (perp, spot)
                   for name in ("open", "high", "low", "close", "volume")]
        if not all(np.isfinite(value) for value in current):
            zones = []
            continue
        contacts: dict[str, list[dict]] = {"long": [], "short": []}
        remaining = []
        for zone in zones:
            age = i - zone["born"]
            if age <= 0:
                remaining.append(zone)
                continue
            if age > 60:
                continue
            invalid = (perp["close"][i] < zone["low"] if zone["side"] == "long"
                       else perp["close"][i] > zone["high"])
            if invalid:
                continue
            touched = (perp["low"][i] <= zone["high"] and perp["high"][i] >= zone["low"])
            if touched:
                contacts[zone["side"]].append(zone)
            else:
                remaining.append(zone)
        zones = remaining
        if eligible[i]:
            sides = [side for side, rows in contacts.items() if rows]
            if len(sides) == 2:
                ambiguous += 1
            elif sides:
                side = sides[0]
                zone = max(contacts[side], key=lambda row: row["born"])
                signal_atr = float(atr_values[i - 1]) if i > 0 else math.nan
                baseline = {"index": i, "side": side, "zone_low": zone["low"],
                            "zone_high": zone["high"], "atr": signal_atr}
                candidate = ((spot["close"][i] > zone["high"] and
                              zone["low"] <= perp["close"][i] <= zone["high"])
                             if side == "long" else
                             (spot["close"][i] < zone["low"] and
                              zone["low"] <= perp["close"][i] <= zone["high"]))
                baseline["candidate"] = bool(candidate)
                events.append(baseline)
        if i >= 14 and i > 0 and np.isfinite(atr_values[i - 1]):
            if (perp["close"][i] - perp["open"][i] > 1.5 * atr_values[i - 1]
                    and perp["close"][i] > perp["high"][i - 1]):
                for j in range(i - 1, max(-1, i - 6), -1):
                    if perp["close"][j] < perp["open"][j]:
                        zones.append({"low": float(perp["low"][j]),
                                      "high": float(perp["high"][j]),
                                      "born": i, "side": "long"})
                        break
            if (perp["open"][i] - perp["close"][i] > 1.5 * atr_values[i - 1]
                    and perp["close"][i] < perp["low"][i - 1]):
                for j in range(i - 1, max(-1, i - 6), -1):
                    if perp["close"][j] > perp["open"][j]:
                        zones.append({"low": float(perp["low"][j]),
                                      "high": float(perp["high"][j]),
                                      "born": i, "side": "short"})
                        break
    return events, ambiguous, anchors


def normalize_month_grid(month: str, times: np.ndarray,
                         columns: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Reindex a sorted monthly minute series; missing candles become NaN rows."""
    year, month_number = map(int, month.split("-"))
    month_start = int(datetime(year, month_number, 1, tzinfo=timezone.utc).timestamp() * 1000)
    next_year, next_month = ((year + 1, 1) if month_number == 12 else
                             (year, month_number + 1))
    month_end = int(datetime(next_year, next_month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    expected_times = np.arange(month_start, month_end, 60_000, dtype=np.int64)
    ts = np.asarray(times, dtype=np.int64)
    values = {name: np.asarray(value, dtype=np.float64) for name, value in columns.items()}
    if any(value.ndim != 1 or len(value) != len(ts) for value in values.values()):
        raise ValueError(f"column length mismatch for month {month}")
    if (np.any(np.diff(ts) <= 0) or (len(ts) and
            (ts[0] < month_start or ts[-1] >= month_end or np.any(ts % 60_000)))):
        raise ValueError(f"invalid timestamp order/bounds for month {month}")
    positions = ((ts - month_start) // 60_000).astype(np.int64)
    if len(ts) and np.any(expected_times[positions] != ts):
        raise ValueError(f"unaligned minute timestamps for month {month}")
    result = {"time": expected_times}
    for name, value in values.items():
        normalized = np.full(len(expected_times), np.nan, dtype=np.float64)
        normalized[positions] = value
        result[name] = normalized
    return result


def eligible_anchor_mask(perp: dict[str, np.ndarray], spot: dict[str, np.ndarray],
                         atr_values: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Use only complete aligned 5m anchors; count tail and data exclusions separately."""
    warmed = np.isfinite(np.r_[np.nan, atr_values[:-1]])
    full_window = perp["time"] + 105 * 60_000 < CUTOFF_MS
    complete = np.ones(len(perp["time"]), dtype=bool)
    for bars in (perp, spot):
        for name in ("open", "high", "low", "close", "volume"):
            complete &= np.isfinite(bars[name])
    eligible = warmed & full_window & complete
    tail_excluded = int(np.count_nonzero(warmed & ~full_window & complete))
    invalid_anchor_excluded = int(np.count_nonzero(warmed & full_window & ~complete))
    return eligible, tail_excluded, invalid_anchor_excluded


def score_path(event: dict, perp_1m: dict[str, np.ndarray], minute_index: int) -> dict:
    """Score a 100-minute first-touch trade; all levels are fixed at signal close."""
    side = event["side"]
    long_side = side == "long"
    if minute_index < 0 or minute_index >= len(perp_1m["open"]):
        return {"side": side, "entry": None, "stop": None, "target": None,
                "m2_hit": False, "exit_reason": "DATA_DEFECT", "exit_price": None,
                "net_return_base": None, "net_return_stress": None,
                "net_r_base": None, "net_r_stress": None, "path_complete": False}
    entry = float(perp_1m["open"][minute_index])
    atr_value = event["atr"]
    stop = (event["zone_low"] - .1 * atr_value if long_side
            else event["zone_high"] + .1 * atr_value)
    risk = abs(entry - stop)
    base = {"side": side, "entry": entry, "stop": stop, "target": None,
            "m2_hit": False, "exit_reason": "NON_EXECUTABLE", "exit_price": entry,
            "net_return_base": 0.0, "net_return_stress": 0.0,
            "net_r_base": None, "net_r_stress": None, "path_complete": False}
    if not math.isfinite(atr_value) or not math.isfinite(entry) or entry <= 0 or risk <= 0:
        return base
    if (long_side and entry <= stop) or (not long_side and entry >= stop):
        return base
    target = entry + 2 * risk if long_side else entry - 2 * risk
    end = minute_index + HORIZON_MINUTES
    if end > len(perp_1m["open"]):
        base["exit_reason"] = "DATA_DEFECT"
        base["net_return_base"] = base["net_return_stress"] = None
        return base
    ret = {**base, "target": target, "path_complete": True}
    reason, exit_price = "TIMEOUT", float(perp_1m["close"][end - 1])
    for i in range(minute_index, end):
        op, hi, lo, close = (float(perp_1m[key][i])
                             for key in ("open", "high", "low", "close"))
        if not all(math.isfinite(value) for value in (op, hi, lo, close)):
            ret.update({"m2_hit": False, "exit_reason": "DATA_DEFECT", "exit_price": None,
                        "net_return_base": None, "net_return_stress": None,
                        "net_r_base": None, "net_r_stress": None, "path_complete": False})
            return ret
        if long_side and op <= stop or not long_side and op >= stop:
            reason, exit_price = "STOP_GAP", op
            break
        if long_side and op >= target or not long_side and op <= target:
            reason, exit_price = "TARGET_GAP", target
            break
        stop_hit = lo <= stop if long_side else hi >= stop
        target_hit = hi >= target if long_side else lo <= target
        if stop_hit:
            reason, exit_price = "STOP", stop
            break
        if target_hit:
            reason, exit_price = "TARGET", target
            break
    gross_return = (exit_price / entry - 1) * (1 if long_side else -1)
    ret.update({"m2_hit": reason in {"TARGET", "TARGET_GAP"}, "exit_reason": reason,
                "exit_price": exit_price})
    for label, fee in (("base", BASE_FEE), ("stress", STRESS_FEE)):
        net_return = gross_return - fee
        ret[f"net_return_{label}"] = net_return
        ret[f"net_r_{label}"] = net_return / (risk / entry)
    return ret


def wilson(successes: int, count: int) -> list[float | None]:
    if count == 0:
        return [None, None]
    z = 1.959963984540054
    p = successes / count
    d = 1 + z * z / count
    center = (p + z * z / (2 * count)) / d
    margin = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / d
    return [center - margin, center + margin]


def score_m1(side: str, signal_close: float, horizon_close: float,
             atr_value: float) -> tuple[str, bool]:
    """Report the 100-minute direction separately from target-first M2."""
    movement = horizon_close - signal_close
    flat_band = .25 * atr_value * math.sqrt(20)
    actual = "flat" if abs(movement) <= flat_band else "up" if movement > 0 else "down"
    return actual, actual == ("up" if side == "long" else "down")


def nonoverlap_count(rows: list[dict], horizon_ms: int = 100 * 60_000) -> int:
    selected = []
    ends: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: (item["symbol"], item["signal_time_ms"])):
        end = row["signal_time_ms"] + horizon_ms
        if row["signal_time_ms"] < ends.get(row["symbol"], -1):
            continue
        selected.append(row)
        ends[row["symbol"]] = end
    return len(selected)


def development_screen(metrics: dict) -> dict:
    """Apply the preregistered development-only falsification gates once."""
    n = int(metrics["issued_candidate_n"])
    nonoverlap = int(metrics["nonoverlap_candidate_n"])
    if n == 0 or nonoverlap < 200:
        return {"status": "INSUFFICIENT_SAMPLE", "checks": {}}
    lower = metrics["candidate_m2_wilson_95"][0]
    baseline = metrics["unfiltered_first_touch_m2"]
    checks = {
        "all_issued_m2_at_least_80pct": metrics["candidate_m2_rate"] >= .80,
        "cohort_nonoverlap_at_least_200": nonoverlap >= 200,
        "coverage_at_least_10pct": metrics["coverage_pct"] >= 10,
        "base_net_return_per_issued_signal_positive": (
            metrics["net_return_per_issued_signal_base"] > 0),
        "stress_net_return_per_issued_signal_positive": (
            metrics["net_return_per_issued_signal_stress"] > 0),
        "candidate_wilson_lower_above_fixed_unfiltered_baseline": (
            baseline is not None and lower is not None and lower > baseline),
    }
    return {"status": "PASS_DEV_ONLY" if all(checks.values()) else "REJECT",
            "checks": checks}


def validate_run_freeze(freeze: dict, *, branch: str, dirty: str, parent: str,
                        prereg_sha: str, code_sha: str, input_sha: str,
                        symbols: list[str], code_tree: str,
                        freeze_commit_paths: list[str]) -> None:
    """Refuse scoring unless exact reviewed inputs/code are at the frozen commit."""
    if branch != EXPECTED_BRANCH or dirty.strip() or parent != freeze.get("code_commit_sha"):
        raise ValueError("repository branch, clean state, or parent does not match the committed freeze")
    if prereg_sha != freeze.get("preregistration_sha256"):
        raise ValueError("preregistration hash differs from the committed freeze")
    if code_sha != freeze.get("strategy_code_sha256"):
        raise ValueError("strategy code hash differs from the committed freeze")
    if code_tree != freeze.get("code_tree_sha256"):
        raise ValueError("reviewed source tree differs from the committed freeze")
    if freeze_commit_paths != ["docs/research/inventory/crypto_ob_reclaim_freeze_20261122.json"]:
        raise ValueError("freeze commit must contain only the freeze manifest")
    if input_sha != freeze.get("input_fingerprint") or input_sha != FROZEN_INPUT_SHA256:
        raise ValueError("data fingerprint differs from the committed freeze")
    if symbols != list(SYMBOLS) or freeze.get("symbols") != list(SYMBOLS):
        raise ValueError("fingerprint symbol list differs from the fixed scorer cohort")
    if set(freeze.get("panel_verdicts", {}).values()) != {"APPROVE"}:
        raise ValueError("four-role panel freeze does not contain unanimous approval")


def _read_symbol(root: Path, symbol: str, expected_files: dict[str, dict]) -> dict:
    parts = {"spot": [], "perp": []}
    for month in MONTHS:
        for label, dataset in DATASETS.items():
            path = root / dataset / symbol / f"{month}.parquet"
            relative = f"{dataset}/{symbol}/{month}.parquet"
            before = path.stat()
            table = pq.read_table(path, columns=["open_time", "open", "high", "low", "close", "volume"])
            after = path.stat()
            expected = expected_files.get(relative)
            identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            if (expected is None or identity_before != identity_after or
                    after.st_size != expected["size_bytes"] or after.st_mtime_ns != expected["mtime_ns"]):
                raise RuntimeError(f"market file changed while scoring: {relative}")
            ts = table["open_time"].to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
            divisor = 1000 if len(ts) and int(ts.max()) > 10**14 else 1
            ts = ts // divisor
            columns = {name: table[name].to_numpy(zero_copy_only=False).astype(np.float64, copy=False)
                       for name in ("open", "high", "low", "close", "volume")}
            parts[label].append(normalize_month_grid(month, ts, columns))
    minute = {}
    for label in DATASETS:
        minute[label] = {key: np.concatenate([part[key] for part in parts[label]])
                         for key in ("time", "open", "high", "low", "close", "volume")}
    if not np.array_equal(minute["spot"]["time"], minute["perp"]["time"]):
        raise ValueError(f"spot/perpetual timestamp mismatch: {symbol}")
    if minute["perp"]["time"][0] != START_MS or minute["perp"]["time"][-1] + 60_000 != CUTOFF_MS:
        raise ValueError(f"symbol does not cover the frozen whole-month range: {symbol}")
    return minute


def _write_ledger(path: Path, records: list[dict]) -> None:
    import csv
    keys = list(records[0]) if records else [
        "symbol", "signal_time_ms", "side", "zone_low", "zone_high", "candidate",
        "m1_actual", "m1_hit",
        "eligible_anchors", "entry", "stop", "target", "m2_hit", "exit_reason",
        "exit_price", "net_return_base", "net_return_stress", "net_r_base",
        "net_r_stress", "path_complete",
    ]
    with path.open("wb") as binary:
        with gzip.GzipFile(fileobj=binary, mode="wb", mtime=0) as compressed:
            import io
            text = io.TextIOWrapper(compressed, encoding="utf-8", newline="")
            writer = csv.DictWriter(text, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)
            text.flush()
            text.detach()


def run(args) -> dict:
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {args.output_dir}")
    if args.prereg.resolve() != PREREG_PATH.resolve() or args.fingerprint.resolve() != FINGERPRINT_PATH.resolve():
        raise ValueError("preregistration/fingerprint paths differ from the frozen run contract")
    prereg = args.prereg.read_bytes()
    prereg_sha = hashlib.sha256(prereg).hexdigest()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    parent = subprocess.run(["git", "rev-parse", "HEAD^"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    code_tree = subprocess.run(["git", "rev-parse", f"{parent}^{{tree}}"], cwd=ROOT, check=True,
                               capture_output=True, text=True).stdout.strip()
    freeze_commit_paths = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout
    saved_fingerprint = json.loads(args.fingerprint.read_text(encoding="utf-8"))
    if saved_fingerprint.get("aggregate_sha256") != FROZEN_INPUT_SHA256:
        raise ValueError("saved data fingerprint differs from the frozen approved cohort")
    if saved_fingerprint.get("symbols") != list(SYMBOLS):
        raise ValueError("saved fingerprint symbol list differs from the fixed scorer cohort")
    current = fingerprint(args.root, args.audit_json)
    if current["aggregate_sha256"] != saved_fingerprint.get("aggregate_sha256"):
        raise ValueError("candidate input fingerprint changed; refusing to score")
    if current.get("symbols") != list(SYMBOLS):
        raise ValueError("current audit symbol list differs from the fixed scorer cohort")
    validate_run_freeze(freeze, branch=branch, dirty=dirty, parent=parent,
                        prereg_sha=prereg_sha, code_sha=code_sha256,
                        input_sha=current["aggregate_sha256"], symbols=current["symbols"],
                        code_tree=code_tree, freeze_commit_paths=freeze_commit_paths)
    if saved_fingerprint.get("file_count") != 1600 or saved_fingerprint.get("all_files_stable") is not True:
        raise ValueError("saved candidate fingerprint is incomplete or unstable")
    expected_files = {item["path"]: item for item in current["files"]}
    records = []
    baseline = []
    ambiguous_total = 0
    opportunities_total = 0
    data_defects = 0
    administrative_tail_excluded = 0
    invalid_anchor_total = 0
    for symbol in SYMBOLS:
        minute = _read_symbol(args.root, symbol, expected_files)
        def to_5m(bars):
            return aggregate_5m(bars["time"], bars["open"], bars["high"], bars["low"],
                                bars["close"], bars["volume"])
        perp = to_5m(minute["perp"])
        spot = to_5m(minute["spot"])
        if not np.array_equal(perp["time"], spot["time"]):
            raise ValueError(f"5m spot/perpetual grid mismatch: {symbol}")
        atr_values = wilder_atr(perp["high"], perp["low"], perp["close"], 14)
        eligible, tail_excluded, invalid_anchor_excluded = eligible_anchor_mask(
            perp, spot, atr_values)
        administrative_tail_excluded += tail_excluded
        invalid_anchor_total += invalid_anchor_excluded
        events, ambiguous, anchors = first_touch_events(perp, spot, atr_values, eligible)
        opportunities_total += anchors
        ambiguous_total += ambiguous
        for event in events:
            i = event["index"]
            minute_index = (i + 1) * 5
            scored = score_path(event, minute["perp"], minute_index)
            data_defects += scored["exit_reason"] == "DATA_DEFECT"
            if scored["exit_reason"] == "DATA_DEFECT":
                scored["net_return_base"] = scored["net_return_stress"] = None
                scored["net_r_base"] = scored["net_r_stress"] = None
                m1_actual, m1_hit = None, None
            else:
                horizon_close = float(minute["perp"]["close"][minute_index + HORIZON_MINUTES - 1])
                m1_actual, m1_hit = score_m1(event["side"], float(perp["close"][i]),
                                             horizon_close, float(event["atr"]))
            row = {"symbol": symbol, "signal_time_ms": int(perp["time"][i] + 300_000),
                   "side": event["side"], "zone_low": event["zone_low"],
                   "zone_high": event["zone_high"], "candidate": event["candidate"],
                   "m1_actual": m1_actual, "m1_hit": m1_hit,
                   "eligible_anchors": anchors, **scored}
            baseline.append(row)
            if event["candidate"]:
                records.append(row)
    if not opportunities_total:
        raise ValueError("no eligible anchors")
    successes = sum(bool(row["m2_hit"]) for row in records)
    interval = wilson(successes, len(records))
    baseline_successes = sum(bool(row["m2_hit"]) for row in baseline)
    filtered_failures = [row for row in baseline if not row["candidate"]]
    filtered_failure_successes = sum(bool(row["m2_hit"]) for row in filtered_failures)
    candidate_times = Counter(row["signal_time_ms"] for row in records)
    per_symbol = {}
    for symbol in SYMBOLS:
        selected = [row for row in records if row["symbol"] == symbol]
        all_touches = [row for row in baseline if row["symbol"] == symbol]
        per_symbol[symbol] = {
            "first_touch_n": len(all_touches), "candidate_n": len(selected),
            "m2_hits": sum(bool(row["m2_hit"]) for row in selected),
            "m2_rate": (sum(bool(row["m2_hit"]) for row in selected) / len(selected)
                        if selected else None),
            "m1_direction_accuracy": (
                sum(bool(row["m1_hit"]) for row in selected if row["m1_hit"] is not None) /
                sum(row["m1_hit"] is not None for row in selected)
                if any(row["m1_hit"] is not None for row in selected) else None),
            "net_return_base_mean": (
                float(np.mean([row["net_return_base"] for row in selected
                               if row["net_return_base"] is not None]))
                if any(row["net_return_base"] is not None for row in selected) else None),
            "net_return_stress_mean": (
                float(np.mean([row["net_return_stress"] for row in selected
                               if row["net_return_stress"] is not None]))
                if any(row["net_return_stress"] is not None for row in selected) else None),
        }
    metrics = {
        "experiment_id": "CRYPTO-OB-SPOTPERP-SAMEBAR-001",
        "status": "BLOCKED_DATA_DEFECT" if data_defects else "complete_dev_only",
        "cohort_symbols": len(SYMBOLS), "period_start_utc": "2024-10-01T00:00:00Z",
        "period_end_exclusive_utc": "2026-11-01T00:00:00Z",
        "eligible_anchors": opportunities_total,
        "administrative_tail_excluded_anchors": administrative_tail_excluded,
        "invalid_anchor_excluded_anchors": invalid_anchor_total,
        "ambiguous_anchors": ambiguous_total,
        "unfiltered_first_touch_n": len(baseline),
        "unfiltered_first_touch_m2": baseline_successes / len(baseline) if baseline else None,
        "unfiltered_first_touch_m2_wilson_95": wilson(baseline_successes, len(baseline)),
        "issued_candidate_n": len(records), "candidate_m2_hits": successes,
        "candidate_m2_rate": successes / len(records) if records else None,
        "candidate_m2_wilson_95": interval,
        "candidate_m1_direction_accuracy": (
            sum(bool(row["m1_hit"]) for row in records if row["m1_hit"] is not None) /
            sum(row["m1_hit"] is not None for row in records)
            if any(row["m1_hit"] is not None for row in records) else None),
        "candidate_m1_scored": sum(row["m1_hit"] is not None for row in records),
        "filter_failure_n": len(filtered_failures),
        "filter_failure_m2": (filtered_failure_successes / len(filtered_failures)
                               if filtered_failures else None),
        "filter_failure_m2_wilson_95": wilson(filtered_failure_successes, len(filtered_failures)),
        "filter_failure_m1_direction_accuracy": (
            sum(bool(row["m1_hit"]) for row in filtered_failures if row["m1_hit"] is not None) /
            sum(row["m1_hit"] is not None for row in filtered_failures)
            if any(row["m1_hit"] is not None for row in filtered_failures) else None),
        "unfiltered_first_touch_m1_direction_accuracy": (
            sum(bool(row["m1_hit"]) for row in baseline if row["m1_hit"] is not None) /
            sum(row["m1_hit"] is not None for row in baseline)
            if any(row["m1_hit"] is not None for row in baseline) else None),
        "coverage_pct": 100 * len(records) / opportunities_total,
        "candidate_issuance_pct_of_first_touches": (
            100 * len(records) / len(baseline) if baseline else None),
        "nonoverlap_candidate_n": nonoverlap_count(records),
        "issued_symbol_count": len({row["symbol"] for row in records}),
        "same_5m_anchor_cluster_count": sum(1 for count in candidate_times.values() if count > 1),
        "max_symbols_same_5m_anchor": max(candidate_times.values(), default=0),
        "per_symbol": per_symbol,
        "m2_outcomes": {}, "net_return_per_issued_signal_base": {},
        "net_return_per_issued_signal_stress": {}, "mean_net_r_executed_base": {},
        "mean_net_r_executed_stress": {}, "no_entry_count": 0,
        "unresolved_data_defects": data_defects,
        "wilson_intervals_are_cluster_adjusted": False,
        "input_fingerprint": saved_fingerprint["aggregate_sha256"],
        "preregistration_sha256": prereg_sha,
    }
    for row in records:
        metrics["m2_outcomes"][row["exit_reason"]] = metrics["m2_outcomes"].get(row["exit_reason"], 0) + 1
        metrics["no_entry_count"] += row["exit_reason"] == "NON_EXECUTABLE"
    for label in ("base", "stress"):
        if data_defects:
            metrics[f"net_return_per_issued_signal_{label}"] = None
            metrics[f"mean_net_r_executed_{label}"] = None
        else:
            metrics[f"net_return_per_issued_signal_{label}"] = (
                float(np.mean([row[f"net_return_{label}"] for row in records])) if records else None)
            executed = [row[f"net_r_{label}"] for row in records if row[f"net_r_{label}"] is not None]
            metrics[f"mean_net_r_executed_{label}"] = float(np.mean(executed)) if executed else None
    metrics["development_screen"] = (
        {"status": "NOT_RUN_DATA_DEFECT", "checks": {}}
        if data_defects else development_screen(metrics))
    metrics["code_commit_sha"] = freeze["code_commit_sha"]
    metrics["freeze_commit_sha"] = head
    metrics["code_file_sha256"] = code_sha256
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_ledger(args.output_dir / "candidate_ledger.csv.gz", records)
    _write_ledger(args.output_dir / "all_first_touch_ledger.csv.gz", baseline)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--fingerprint", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"data root not found: {args.root}")
    if args.output_dir.resolve().is_relative_to(args.root.resolve()):
        parser.error("output must be outside the immutable data root")
    result = run(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
