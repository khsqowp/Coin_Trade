"""Frozen-rule, development-only 5m OB / 1m confirmed-pivot BOS screen."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
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
from scripts.research.fingerprint_crypto_candidate_inputs import fingerprint
from scripts.research.spot_perp_ob_first_touch import (
    BASE_FEE, CUTOFF_MS, DATASETS, MONTHS, START_MS, STRESS_FEE, SYMBOLS,
    aggregate_5m, first_touch_events, normalize_month_grid, wilson,
)

PREREG_PATH = ROOT / "docs/research/inventory/PREREG_SPOT_PERP_OB_PIVOT_BOS_DEV_20261122.md"
FINGERPRINT_PATH = ROOT / "docs/research/inventory/crypto_ob_reclaim_input_fingerprint_20261122.json"
FREEZE_PATH = ROOT / "docs/research/inventory/crypto_ob_pivot_bos_freeze_20261122.json"
SUPPORTING_COST_AUDIT_PATH = ROOT / "docs/research/inventory/crypto_ob_pivot_bos_cost_input_audit_20261122.json"
EXPECTED_BRANCH = "research/bat-harmonic-validation-20261120"
ARM_WINDOW = 10
HORIZON = 20
BOOTSTRAP_REPS = 1_000
BOOTSTRAP_SEED = 20_261_122
WEEK_MS = 7 * 24 * 60 * 60 * 1000
PANEL_REVIEWER_IDS = {"BANACH", "RAMAN", "HARVEY", "SINGER"}
EXPECTED_COST_AUDIT_SHA256 = "8f04890b1b52444bec9453f00618dae4bc05fe9173640342306dfad13ee42a1c"


def validate_supporting_cost_audit(audit: dict) -> None:
    """Fail closed unless the recorded fee/funding/mark audit is the reviewed snapshot."""
    funding = audit.get("funding", {})
    mark = audit.get("mark_price_june_2026", {})
    gaps = funding.get("interval_gap_anomalies", [])
    mark_gaps = mark.get("grid_gap_anomalies", [])
    expected_gap_symbols = {"ENAUSDT", "POLUSDT", "TIAUSDT"}
    if (audit.get("audit_id") != "CRYPTO-OB-PIVOT-BOS-COST-INPUTS-20261122" or
            audit.get("status") != "KNOWN_COST_INPUT_GAPS" or
            funding.get("expected_files") != 800 or funding.get("present_files") != 800 or
            funding.get("missing_files") != [] or funding.get("rows") != 79902 or
            funding.get("null_or_nonfinite_rates") != 0 or len(gaps) != 3 or
            {row.get("symbol") for row in gaps} != expected_gap_symbols or
            any(row.get("estimated_missing_events") != 1 or row.get("interval_hours") != 4
                for row in gaps) or mark.get("expected_files") != 32 or
            mark.get("present_files") != 32 or mark.get("missing_files") != [] or
            len(mark_gaps) != 32 or
            any(row.get("missing_minutes") != 1440 for row in mark_gaps)):
        raise ValueError("supporting cost-input audit differs from reviewed evidence")


def load_supporting_cost_audit() -> tuple[dict, str]:
    raw = SUPPORTING_COST_AUDIT_PATH.read_bytes()
    content = json.loads(raw)
    validate_supporting_cost_audit(content)
    return content, hashlib.sha256(raw).hexdigest()


def _committed_blob_sha(commit: str, relative_path: str) -> str:
    result = subprocess.run(["git", "show", f"{commit}:{relative_path}"], cwd=ROOT,
                            check=True, capture_output=True)
    return hashlib.sha256(result.stdout).hexdigest()


def is_confirmed_pivot(high: np.ndarray, low: np.ndarray, center: int,
                       side: str, arm_start: int) -> bool:
    """A strict 2-left/2-right pivot, wholly after the 5m arm close."""
    if side not in {"long", "short"}:
        raise ValueError("side must be long or short")
    if center - 2 < arm_start or center + 2 >= len(high):
        return False
    if not np.all(np.isfinite(high[center - 2:center + 3])) or not np.all(
            np.isfinite(low[center - 2:center + 3])):
        return False
    if side == "long":
        return all(high[center] > high[j] for j in (center - 2, center - 1,
                                                      center + 1, center + 2))
    return all(low[center] < low[j] for j in (center - 2, center - 1,
                                               center + 1, center + 2))


def find_bos(event: dict, one: dict[str, np.ndarray], five: dict[str, np.ndarray]) -> dict:
    """Return first post-touch pivot BOS in the fixed 10-close window, if any."""
    arm_start = (int(event["index"]) + 1) * 5
    arm_end = arm_start + ARM_WINDOW
    if arm_end > len(one["open"]) or arm_end + HORIZON > len(one["open"]):
        return {"status": "DATA_DEFECT", "signal_index": None, "stop": None}
    side = event["side"]
    long_side = side == "long"
    pending_pivot = None
    pending_confirm = None
    for index in range(arm_start, arm_end):
        if not all(math.isfinite(float(one[key][index])) for key in ("open", "high", "low", "close", "volume")):
            return {"status": "DATA_DEFECT", "signal_index": None, "stop": None}
        # Invalidation at the same completed 5m close takes priority over BOS.
        if index % 5 == 4:
            five_index = index // 5
            close = float(five["close"][five_index])
            if not math.isfinite(close):
                return {"status": "DATA_DEFECT", "signal_index": None, "stop": None}
            invalid = (close < event["zone_low"] if long_side
                       else close > event["zone_high"])
            if invalid:
                return {"status": "INVALIDATED", "signal_index": None, "stop": None}
        if pending_pivot is not None:
            if index > pending_confirm:
                close = float(one["close"][index])
                crossed = close > pending_pivot if long_side else close < pending_pivot
                if crossed:
                    extreme = (float(five["low"][event["index"]]) if long_side
                               else float(five["high"][event["index"]]))
                    section = one["low"][arm_start:index + 1] if long_side else one["high"][arm_start:index + 1]
                    if not np.all(np.isfinite(section)) or not math.isfinite(extreme):
                        return {"status": "DATA_DEFECT", "signal_index": None, "stop": None}
                    extreme = min(extreme, float(np.min(section))) if long_side else max(
                        extreme, float(np.max(section)))
                    return {"status": "BOS", "signal_index": index, "stop": extreme}
        else:
            center = index - 2
            if is_confirmed_pivot(one["high"], one["low"], center, side, arm_start):
                pending_pivot = float(one["high"][center] if long_side else one["low"][center])
                pending_confirm = index
    return {"status": "NO_BOS", "signal_index": None, "stop": None}


def score_trade(event: dict, one: dict[str, np.ndarray], *, entry_index: int,
                stop: float, signal_index: int | None) -> dict:
    """Score a fixed 2R/20m triple barrier with gap and stop-first rules."""
    side = event["side"]
    long_side = side == "long"
    if entry_index < 0 or entry_index + HORIZON > len(one["open"]):
        return {"entry": None, "stop": stop, "target": None, "m2_hit": False,
                "exit_reason": "DATA_DEFECT", "exit_price": None,
                "net_return_base": None, "net_return_stress": None,
                "path_complete": False, "m1_hit": None}
    anchor_index = signal_index if signal_index is not None else entry_index - 1
    signal_close = float(one["close"][anchor_index])
    signal_atr = float(event.get("signal_atr_1m", event["atr_1m"]))
    horizon_close = float(one["close"][entry_index + HORIZON - 1])
    movement = horizon_close - signal_close
    flat_band = .25 * signal_atr * math.sqrt(HORIZON)
    actual = "flat" if abs(movement) <= flat_band else "up" if movement > 0 else "down"
    m1_hit = actual == ("up" if long_side else "down")
    entry = float(one["open"][entry_index])
    risk = abs(entry - stop) if math.isfinite(entry) and math.isfinite(stop) else math.nan
    result = {"entry": entry, "stop": stop, "target": None, "m2_hit": False,
              "exit_reason": "NON_EXECUTABLE", "exit_price": entry,
              "net_return_base": 0.0, "net_return_stress": 0.0,
              "path_complete": True, "m1_hit": m1_hit}
    if not math.isfinite(entry) or entry <= 0 or not math.isfinite(risk) or risk <= 0:
        return result
    if (long_side and entry <= stop) or (not long_side and entry >= stop):
        return result
    target = entry + 2 * risk if long_side else entry - 2 * risk
    result["target"] = target
    exit_reason = "TIMEOUT"
    exit_price = float(one["close"][entry_index + HORIZON - 1])
    for index in range(entry_index, entry_index + HORIZON):
        op, high, low, close = (float(one[key][index]) for key in ("open", "high", "low", "close"))
        if not all(math.isfinite(value) for value in (op, high, low, close)):
            return {**result, "m2_hit": False, "exit_reason": "DATA_DEFECT",
                    "exit_price": None, "net_return_base": None,
                    "net_return_stress": None, "path_complete": False}
        if (long_side and op <= stop) or (not long_side and op >= stop):
            exit_reason, exit_price = "STOP_GAP", op
            break
        if (long_side and op >= target) or (not long_side and op <= target):
            exit_reason, exit_price = "TARGET_GAP", target
            break
        stop_hit = low <= stop if long_side else high >= stop
        target_hit = high >= target if long_side else low <= target
        if stop_hit:
            exit_reason, exit_price = "STOP", stop
            break
        if target_hit:
            exit_reason, exit_price = "TARGET", target
            break
    gross_return = (exit_price / entry - 1) * (1 if long_side else -1)
    result.update({"m2_hit": exit_reason in {"TARGET", "TARGET_GAP"},
                   "exit_reason": exit_reason, "exit_price": exit_price,
                   "m1_hit": m1_hit})
    for label, fee in (("base", BASE_FEE), ("stress", STRESS_FEE)):
        result[f"net_return_{label}"] = gross_return - fee
    return result


def global_nonoverlap_count(rows: list[dict]) -> int:
    """Select the earliest signal, then one market-wide signal per 20 minutes."""
    ordered = sorted(rows, key=lambda row: (row["signal_time_ms"], row["symbol"],
                                           0 if row["side"] == "long" else 1))
    selected = 0
    last_end = -1
    for row in ordered:
        start = int(row["signal_time_ms"])
        if start >= last_end:
            selected += 1
            last_end = start + HORIZON * 60_000
    return selected


def unique_signal_anchor_count(rows: list[dict]) -> int:
    """Count each symbol's 5m eligible anchor once, even if rows ever duplicate."""
    return len({(row["symbol"], int(row["anchor_time_ms"])) for row in rows})


def signal_anchor_coverage(rows: list[dict], eligible_anchor_count: int) -> tuple[int, float | None]:
    """Return unique issued opportunity anchors and their diagnostic bar density."""
    count = unique_signal_anchor_count(rows)
    return count, 100 * count / eligible_anchor_count if eligible_anchor_count else None


def first_touch_conversion_metrics(arms: list[dict]) -> dict:
    """Keep zone-arm conversion separate from distinct first-touch-anchor coverage."""
    issued = [row for row in arms if row.get("candidate_signal")]
    arm_count = len(arms)
    opportunity_anchor_count = unique_signal_anchor_count(arms)
    issued_anchor_count = unique_signal_anchor_count(issued)
    return {
        "issued_arm_n": len(issued),
        "directional_arm_n": arm_count,
        "issuance_per_first_touch_pct": 100 * len(issued) / arm_count if arm_count else None,
        "issued_signal_anchor_n": issued_anchor_count,
        "first_touch_anchor_n": opportunity_anchor_count,
        "issued_anchor_coverage_per_first_touch_pct": (
            100 * issued_anchor_count / opportunity_anchor_count
            if opportunity_anchor_count else None),
    }


def block_bootstrap(arms: list[dict], *, reps: int = BOOTSTRAP_REPS,
                    seed: int = BOOTSTRAP_SEED) -> dict:
    """Circular 2-week moving-block bootstrap of paired arm-level policy outcomes."""
    if not arms:
        return {"replicates": reps, "seed": seed, "weeks": 0,
                "candidate_minus_baseline_arm_m2_ci95": [None, None],
                "candidate_minus_baseline_arm_net_base_ci95": [None, None],
                "candidate_minus_baseline_arm_net_stress_ci95": [None, None]}
    first_week = min(int(row["anchor_time_ms"]) // WEEK_MS for row in arms)
    last_week = max(int(row["anchor_time_ms"]) // WEEK_MS for row in arms)
    count_weeks = last_week - first_week + 1
    sums = np.zeros((count_weeks, 7), dtype=np.float64)
    for row in arms:
        week = int(row["anchor_time_ms"]) // WEEK_MS - first_week
        # columns: event count, candidate arm M2, baseline M2, candidate base/stress, baseline base/stress
        sums[week, 0] += 1
        sums[week, 1] += bool(row["candidate_arm_m2"])
        sums[week, 2] += bool(row["baseline_m2"])
        sums[week, 3] += float(row["candidate_arm_net_base"])
        sums[week, 4] += float(row["candidate_arm_net_stress"])
        sums[week, 5] += float(row["baseline_net_base"])
        sums[week, 6] += float(row["baseline_net_stress"])
    rng = np.random.default_rng(seed)
    m2_diffs, base_diffs, stress_diffs = [], [], []
    blocks = math.ceil(count_weeks / 2)
    for _ in range(reps):
        starts = rng.integers(0, count_weeks, size=blocks)
        indices = np.concatenate([(start + np.arange(2)) % count_weeks for start in starts])[:count_weeks]
        sampled = sums[indices].sum(axis=0)
        if sampled[0] == 0:
            continue
        m2_diffs.append((sampled[1] - sampled[2]) / sampled[0])
        base_diffs.append((sampled[3] - sampled[5]) / sampled[0])
        stress_diffs.append((sampled[4] - sampled[6]) / sampled[0])
    def quantiles(values):
        return [float(value) for value in np.quantile(values, [.025, .975])] if values else [None, None]
    return {"replicates": reps, "seed": seed, "weeks": count_weeks,
            "candidate_minus_baseline_arm_m2_ci95": quantiles(m2_diffs),
            "candidate_minus_baseline_arm_net_base_ci95": quantiles(base_diffs),
            "candidate_minus_baseline_arm_net_stress_ci95": quantiles(stress_diffs),
            "block_definition": "circular moving blocks of 2 consecutive UTC calendar weeks"}


def _write_gzip_jsonl(path: Path, records: list[dict]) -> None:
    import gzip
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
            for row in records:
                stream.write((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())


def development_screen(metrics: dict) -> dict:
    checks = {
        "issued_m2_at_least_80pct": metrics["issued_m2_rate"] is not None and metrics["issued_m2_rate"] >= .80,
        "issued_n_at_least_200": metrics["issued_n"] >= 200,
        "symbol_nonoverlap_n_at_least_200": metrics["symbol_nonoverlap_n"] >= 200,
        "market_time_nonoverlap_n_at_least_200": metrics["market_time_nonoverlap_n"] >= 200,
        "issuance_per_first_touch_at_least_10pct": metrics["issuance_per_first_touch_pct"] is not None and metrics["issuance_per_first_touch_pct"] >= 10,
        "issued_anchor_coverage_per_first_touch_at_least_10pct": (
            metrics["issued_anchor_coverage_per_first_touch_pct"] is not None and
            metrics["issued_anchor_coverage_per_first_touch_pct"] >= 10),
        "at_least_20_issued_symbols": metrics["issued_symbol_count"] >= 20,
        "no_symbol_over_20pct_of_issued": metrics["max_symbol_issued_share"] is not None and metrics["max_symbol_issued_share"] <= .20,
        "invalid_5m_bars_zero": metrics["invalid_5m_bars"] == 0,
        "fee_only_arm_mean_base_positive": metrics["arm_mean_net_base"] is not None and metrics["arm_mean_net_base"] > 0,
        "fee_only_arm_mean_stress_positive": metrics["arm_mean_net_stress"] is not None and metrics["arm_mean_net_stress"] > 0,
        "arm_m2_block_bootstrap_lower_above_baseline": (
            metrics["block_bootstrap"]["candidate_minus_baseline_arm_m2_ci95"][0] is not None and
            metrics["block_bootstrap"]["candidate_minus_baseline_arm_m2_ci95"][0] > 0),
        "arm_net_base_block_bootstrap_lower_above_baseline": (
            metrics["block_bootstrap"]["candidate_minus_baseline_arm_net_base_ci95"][0] is not None and
            metrics["block_bootstrap"]["candidate_minus_baseline_arm_net_base_ci95"][0] > 0),
        "arm_net_stress_block_bootstrap_lower_above_baseline": (
            metrics["block_bootstrap"]["candidate_minus_baseline_arm_net_stress_ci95"][0] is not None and
            metrics["block_bootstrap"]["candidate_minus_baseline_arm_net_stress_ci95"][0] > 0),
        "data_defects_zero": metrics["data_defects"] == 0,
    }
    status = "REJECT_DEV" if not all(checks.values()) else "HOLD_FUNDING_AND_OOS"
    return {"status": status, "checks": checks,
            "funding_economic_gate": "BLOCKED_INCOMPLETE_EVENT_AND_MARK_PRICE_COVERAGE",
            "sealed_oos_gate": "BLOCKED_EXPOSED_DEVELOPMENT_HISTORY"}


def _eligible_mask(perp5: dict[str, np.ndarray], atr5: np.ndarray) -> tuple[np.ndarray, int, int, int]:
    warmed = np.isfinite(np.r_[np.nan, atr5[:-1]])
    full_path = perp5["time"] + 35 * 60_000 < CUTOFF_MS
    complete = np.ones(len(perp5["time"]), dtype=bool)
    for name in ("open", "high", "low", "close", "volume"):
        complete &= np.isfinite(perp5[name])
    eligible = warmed & full_path & complete
    tail = int(np.count_nonzero(warmed & ~full_path))
    pre_cutoff = perp5["time"] < CUTOFF_MS
    invalid = int(np.count_nonzero(warmed & pre_cutoff & ~complete))
    return eligible, tail, invalid, int(np.count_nonzero(warmed))


def _to_5m(one: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return aggregate_5m(one["time"], one["open"], one["high"], one["low"],
                        one["close"], one["volume"])


def _read_perp_symbol(root: Path, symbol: str,
                      expected_files: dict[str, dict]) -> dict[str, np.ndarray]:
    """Read only the perpetual bars used by this strategy; spot is fingerprint-only."""
    parts = []
    dataset = DATASETS["perp"]
    for month in MONTHS:
        relative = f"{dataset}/{symbol}/{month}.parquet"
        path = root / relative
        before = path.stat()
        table = pq.read_table(path, columns=["open_time", "open", "high", "low", "close", "volume"])
        after = path.stat()
        expected = expected_files.get(relative)
        before_id = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        after_id = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if (expected is None or before_id != after_id or
                after.st_size != expected["size_bytes"] or after.st_mtime_ns != expected["mtime_ns"]):
            raise RuntimeError(f"market file changed while scoring: {relative}")
        timestamps = table["open_time"].to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        divisor = 1000 if len(timestamps) and int(timestamps.max()) > 10**14 else 1
        columns = {name: table[name].to_numpy(zero_copy_only=False).astype(np.float64, copy=False)
                   for name in ("open", "high", "low", "close", "volume")}
        parts.append(normalize_month_grid(month, timestamps // divisor, columns))
    minute = {key: np.concatenate([part[key] for part in parts])
              for key in ("time", "open", "high", "low", "close", "volume")}
    if minute["time"][0] != START_MS or minute["time"][-1] + 60_000 != CUTOFF_MS:
        raise ValueError(f"perpetual symbol does not cover frozen whole-month range: {symbol}")
    return minute


def _preflight_incomplete_bars(root: Path, expected_files: dict[str, dict]) -> dict:
    """Validate the full cohort before any trade outcome or economic score is computed."""
    invalid_by_symbol = {}
    invalid_ohlc_by_symbol = {}
    eligible_by_symbol = {}
    for symbol in SYMBOLS:
        minute = _read_perp_symbol(root, symbol, expected_files)
        invalid_ohlc_by_symbol[symbol] = _invalid_ohlc_bar_count(minute)
        five = _to_5m(minute)
        atr5 = wilder_atr(five["high"], five["low"], five["close"], 14)
        eligible, _, invalid, _ = _eligible_mask(five, atr5)
        invalid_by_symbol[symbol] = invalid
        eligible_by_symbol[symbol] = int(np.count_nonzero(eligible))
    return {"invalid_5m_bars": sum(invalid_by_symbol.values()),
            "invalid_5m_bars_by_symbol": invalid_by_symbol,
            "invalid_ohlc_bars": sum(invalid_ohlc_by_symbol.values()),
            "invalid_ohlc_bars_by_symbol": invalid_ohlc_by_symbol,
            "eligible_anchors_by_symbol": eligible_by_symbol,
            "eligible_anchors": sum(eligible_by_symbol.values())}


def _invalid_ohlc_bar_count(minute: dict[str, np.ndarray]) -> int:
    """Count finite pre-cutoff 1m bars violating price envelope invariants."""
    open_, high, low, close = (np.asarray(minute[name], dtype=np.float64)
                               for name in ("open", "high", "low", "close"))
    in_period = np.asarray(minute["time"]) < CUTOFF_MS
    finite = np.isfinite(open_) & np.isfinite(high) & np.isfinite(low) & np.isfinite(close)
    invalid = finite & in_period & (
        (open_ <= 0) | (high <= 0) | (low <= 0) | (close <= 0) |
        (high < np.maximum(open_, close)) | (low > np.minimum(open_, close)) |
        (high < low))
    return int(np.count_nonzero(invalid))


def _write_data_invalid(args, *, input_sha: str, prereg_sha: str,
                        code_sha: str, freeze: dict, preflight: dict,
                        additional_defects: int = 0) -> dict:
    """Persist only integrity evidence; never emit economic metrics or trade ledgers."""
    result = {
        "experiment_id": "CRYPTO-OB-PIVOT-BOS-002",
        "status": "DATA_INVALID",
        "economic_scoring": "NOT_RUN_OR_SUPPRESSED",
        "trade_ledgers_written": False,
        "data_defects": int(preflight["invalid_5m_bars"] +
                             preflight["invalid_ohlc_bars"] + additional_defects),
        "preflight": preflight,
        "input_fingerprint": input_sha,
        "preregistration_sha256": prereg_sha,
        "code_sha256": code_sha,
        "supporting_cost_input_audit_sha256": getattr(args, "support_audit_sha", None),
        "code_commit_sha": freeze["code_commit_sha"],
        "freeze_commit_sha": freeze["_observed_freeze_commit_sha"],
    }
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "metrics.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _check_freeze(args, prereg_sha: str, code_sha: str, input_sha: str,
                  fingerprint_json: dict, support_audit_sha: str) -> dict:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    parent = subprocess.run(["git", "rev-parse", "HEAD^"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    audit_relative = SUPPORTING_COST_AUDIT_PATH.relative_to(ROOT).as_posix()
    if _committed_blob_sha(parent, audit_relative) != support_audit_sha:
        raise ValueError("supporting cost-input audit is absent or differs in the frozen code tree")
    tree = subprocess.run(["git", "rev-parse", f"{parent}^{{tree}}"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()
    paths = subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, check=True,
                           capture_output=True, text=True).stdout
    if branch != EXPECTED_BRANCH or dirty.strip() or parent != freeze.get("code_commit_sha"):
        raise ValueError("clean branch or immediate parent does not match the preregistered code commit")
    if paths != [FREEZE_PATH.relative_to(ROOT).as_posix()]:
        raise ValueError("freeze commit must contain only its manifest")
    expected = {
        "prereg_sha256": prereg_sha, "scorer_sha256": code_sha,
        "code_tree_sha256": tree, "input_fingerprint": input_sha,
        "supporting_cost_input_audit_sha256": support_audit_sha,
    }
    if any(freeze.get(key) != value for key, value in expected.items()):
        raise ValueError("prereg/code/tree/input does not match committed freeze")
    if freeze.get("panel_verdicts", {}).keys() != PANEL_REVIEWER_IDS:
        raise ValueError("freeze manifest must contain the four actual reviewer identifiers")
    if not all(value == "APPROVE" for value in freeze["panel_verdicts"].values()):
        raise ValueError("all four reviewers must approve the frozen rule")
    if fingerprint_json.get("aggregate_sha256") != input_sha or input_sha != "de5c87e883f4c3e00b818c541a0e36d1320f08a2577dc063d2bb9ff519ab9036":
        raise ValueError("data fingerprint differs from the previously frozen selected cohort")
    freeze["_observed_freeze_commit_sha"] = head
    return freeze


def run(args) -> dict:
    if args.output_dir.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output_dir}")
    prereg_bytes = args.prereg.read_bytes()
    prereg_sha = hashlib.sha256(prereg_bytes).hexdigest()
    if args.prereg.resolve() != PREREG_PATH.resolve() or args.fingerprint.resolve() != FINGERPRINT_PATH.resolve():
        raise ValueError("preregistration or fingerprint path differs from the frozen contract")
    saved_fp = json.loads(args.fingerprint.read_text(encoding="utf-8"))
    _, support_audit_sha = load_supporting_cost_audit()
    if support_audit_sha != EXPECTED_COST_AUDIT_SHA256:
        raise ValueError("supporting cost-input audit hash differs from reviewed snapshot")
    args.support_audit_sha = support_audit_sha
    audit = fingerprint(args.root, args.audit_json)
    if audit.get("aggregate_sha256") != saved_fp.get("aggregate_sha256"):
        raise ValueError("live input fingerprint differs from saved fingerprint")
    code_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    freeze = _check_freeze(args, prereg_sha, code_sha, audit["aggregate_sha256"], saved_fp,
                           support_audit_sha)
    expected_files = {row["path"]: row for row in audit["files"]}
    preflight = _preflight_incomplete_bars(args.root, expected_files)
    if preflight["invalid_5m_bars"] or preflight["invalid_ohlc_bars"]:
        return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                   prereg_sha=prereg_sha, code_sha=code_sha,
                                   freeze=freeze, preflight=preflight)
    arms: list[dict] = []
    baseline_rows: list[dict] = []
    eligible_total = warmed_total = tail_total = invalid_total = ambiguous_total = 0
    data_defects = 0
    for symbol in SYMBOLS:
        minute = _read_perp_symbol(args.root, symbol, expected_files)
        ohlc_defects = _invalid_ohlc_bar_count(minute)
        if ohlc_defects:
            return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                       prereg_sha=prereg_sha, code_sha=code_sha,
                                       freeze=freeze, preflight=preflight,
                                       additional_defects=ohlc_defects)
        five = _to_5m(minute)
        atr5 = wilder_atr(five["high"], five["low"], five["close"], 14)
        eligible, tail, invalid, warmed = _eligible_mask(five, atr5)
        if invalid:
            return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                       prereg_sha=prereg_sha, code_sha=code_sha,
                                       freeze=freeze, preflight=preflight,
                                       additional_defects=invalid)
        eligible_total += int(np.count_nonzero(eligible)); tail_total += tail
        invalid_total += invalid; warmed_total += warmed
        # Reuse causal zone-consumption logic; spot is not a strategy feature.
        events, ambiguous, _ = first_touch_events(five, five, atr5, eligible)
        ambiguous_total += ambiguous
        atr1 = wilder_atr(minute["high"], minute["low"], minute["close"], 14)
        for event in events:
            i = int(event["index"])
            arm_start = (i + 1) * 5
            if arm_start < 1 or arm_start >= len(atr1) or not np.isfinite(atr1[arm_start - 1]):
                return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                           prereg_sha=prereg_sha, code_sha=code_sha,
                                           freeze=freeze, preflight=preflight,
                                           additional_defects=1)
            enriched = {**event, "symbol": symbol, "atr_1m": float(atr1[arm_start - 1]),
                        "anchor_time_ms": int(five["time"][i] + 300_000),
                        "signal_time_ms": None}
            bos = find_bos(enriched, minute, five)
            if bos["status"] == "DATA_DEFECT":
                return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                           prereg_sha=prereg_sha, code_sha=code_sha,
                                           freeze=freeze, preflight=preflight,
                                           additional_defects=1)
            candidate = None
            if bos["status"] == "BOS":
                signal_index = int(bos["signal_index"])
                entry_index = signal_index + 1
                enriched["signal_time_ms"] = int(minute["time"][signal_index] + 60_000)
                if not np.isfinite(atr1[signal_index]):
                    return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                               prereg_sha=prereg_sha, code_sha=code_sha,
                                               freeze=freeze, preflight=preflight,
                                               additional_defects=1)
                enriched["signal_atr_1m"] = float(atr1[signal_index])
                candidate = score_trade(enriched, minute, entry_index=entry_index,
                                        stop=float(bos["stop"]), signal_index=signal_index)
                if not candidate["path_complete"]:
                    return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                               prereg_sha=prereg_sha, code_sha=code_sha,
                                               freeze=freeze, preflight=preflight,
                                               additional_defects=1)
            base_stop = (float(event["zone_low"] - .1 * event["atr"]) if event["side"] == "long"
                         else float(event["zone_high"] + .1 * event["atr"]))
            baseline = score_trade(enriched, minute, entry_index=arm_start, stop=base_stop,
                                   signal_index=None)
            if not baseline["path_complete"]:
                return _write_data_invalid(args, input_sha=audit["aggregate_sha256"],
                                           prereg_sha=prereg_sha, code_sha=code_sha,
                                           freeze=freeze, preflight=preflight,
                                           additional_defects=1)
            row = {**enriched, "arm_status": bos["status"],
                   "candidate_signal": candidate is not None,
                   "candidate_m2": bool(candidate and candidate["m2_hit"]),
                   "candidate_m1": candidate.get("m1_hit") if candidate else None,
                   "candidate_exit_reason": candidate.get("exit_reason") if candidate else "NO_SIGNAL",
                   "candidate_arm_m2": bool(candidate and candidate["m2_hit"]),
                   "candidate_arm_net_base": float(candidate["net_return_base"] or 0.0) if candidate else 0.0,
                   "candidate_arm_net_stress": float(candidate["net_return_stress"] or 0.0) if candidate else 0.0,
                   "candidate": candidate,
                   "baseline_m2": bool(baseline["m2_hit"]),
                   "baseline_net_base": float(baseline["net_return_base"] or 0.0),
                   "baseline_net_stress": float(baseline["net_return_stress"] or 0.0),
                   "baseline": baseline}
            arms.append(row)
            baseline_rows.append({**enriched, **baseline})
    issued = [row for row in arms if row.get("candidate_signal")]
    issued_anchor_n, eligible_bar_coverage_pct = signal_anchor_coverage(issued, eligible_total)
    duplicate_anchor_signal_n = len(issued) - issued_anchor_n
    conversion = first_touch_conversion_metrics(arms)
    baseline_hits = sum(bool(row["baseline_m2"]) for row in arms)
    candidate_hits = sum(bool(row["candidate_m2"]) for row in issued)
    bootstrap = block_bootstrap(arms)
    reasons = Counter(row["candidate_exit_reason"] for row in issued)
    metrics = {
        "experiment_id": "CRYPTO-OB-PIVOT-BOS-002", "status": "complete_dev_only",
        "period_start_utc": "2024-10-01T00:00:00Z", "period_end_exclusive_utc": "2026-11-01T00:00:00Z",
        "symbols": list(SYMBOLS), "eligible_anchors": eligible_total, "warmed_anchors": warmed_total,
        "tail_excluded_anchors": tail_total, "invalid_anchors": invalid_total,
        "invalid_5m_bars": invalid_total,
        "invalid_ohlc_bars": preflight["invalid_ohlc_bars"],
        "ambiguous_touch_anchors": ambiguous_total, "first_touch_arm_n": len(arms),
        "issued_n": len(issued), "no_signal_arm_n": len(arms) - len(issued),
        "issuance_per_first_touch_pct": conversion["issuance_per_first_touch_pct"],
        "issued_plus_ambiguous_n": len(arms) + ambiguous_total,
        "issuance_per_directional_or_ambiguous_touch_pct": (
            100 * len(issued) / (len(arms) + ambiguous_total) if arms or ambiguous_total else None),
        "issued_signal_anchor_n": issued_anchor_n,
        "first_touch_anchor_n": conversion["first_touch_anchor_n"],
        "issued_anchor_coverage_per_first_touch_pct": conversion["issued_anchor_coverage_per_first_touch_pct"],
        "duplicate_signal_anchor_n": duplicate_anchor_signal_n,
        "coverage_per_eligible_5m_anchor_pct": eligible_bar_coverage_pct,
        "signal_density_per_eligible_5m_anchor_pct": 100 * len(issued) / eligible_total if eligible_total else None,
        "issued_m2_hits": candidate_hits, "issued_m2_rate": candidate_hits / len(issued) if issued else None,
        "issued_m2_wilson_descriptive_95": wilson(candidate_hits, len(issued)),
        "issued_m1_rate": (sum(bool(row["candidate_m1"]) for row in issued if row["candidate_m1"] is not None) /
                           sum(row["candidate_m1"] is not None for row in issued)
                           if any(row["candidate_m1"] is not None for row in issued) else None),
        "baseline_first_touch_m2_rate": baseline_hits / len(arms) if arms else None,
        "symbol_nonoverlap_n": 0,
        "market_time_nonoverlap_n": global_nonoverlap_count([
            {"signal_time_ms": row["signal_time_ms"], "symbol": row["symbol"], "side": row["side"]}
            for row in issued]),
        "m2_outcomes": dict(reasons),
        "arm_status_counts": dict(Counter(row.get("arm_status", "UNKNOWN") for row in arms)),
        "arm_mean_net_base": float(np.mean([row["candidate_arm_net_base"] for row in arms])) if arms else None,
        "arm_mean_net_stress": float(np.mean([row["candidate_arm_net_stress"] for row in arms])) if arms else None,
        "issued_mean_net_base": (float(np.mean([row["candidate"]["net_return_base"] for row in issued
                                                  if row["candidate"]["net_return_base"] is not None]))
                                 if any(row["candidate"]["net_return_base"] is not None for row in issued) else None),
        "issued_mean_net_stress": (float(np.mean([row["candidate"]["net_return_stress"] for row in issued
                                                    if row["candidate"]["net_return_stress"] is not None]))
                                   if any(row["candidate"]["net_return_stress"] is not None for row in issued) else None),
        "baseline_arm_mean_net_base": float(np.mean([row["baseline_net_base"] for row in arms])) if arms else None,
        "baseline_arm_mean_net_stress": float(np.mean([row["baseline_net_stress"] for row in arms])) if arms else None,
        "block_bootstrap": bootstrap, "data_defects": data_defects,
        "funding_costs_included": False,
        "funding_economic_gate": "BLOCKED_INCOMPLETE_EVENT_AND_MARK_PRICE_COVERAGE",
        "oos_status": "BLOCKED_EXPOSED_DEVELOPMENT_HISTORY",
        "input_fingerprint": audit["aggregate_sha256"],
        "input_content_fingerprint": audit["aggregate_sha256"],
        "preregistration_sha256": prereg_sha, "code_sha256": code_sha,
        "supporting_cost_input_audit_sha256": support_audit_sha,
        "code_commit_sha": freeze["code_commit_sha"],
        "freeze_commit_sha": freeze["_observed_freeze_commit_sha"],
        "trial_family_total": "UNRESOLVED_FROM_HISTORICAL_REGISTRY; no adjusted-approval claim",
    }
    symbol_selected = []
    for symbol in SYMBOLS:
        symbol_rows = sorted((row for row in issued if row["symbol"] == symbol),
                             key=lambda row: row["signal_time_ms"])
        last_end = -1
        for row in symbol_rows:
            if row["signal_time_ms"] >= last_end:
                symbol_selected.append(row)
                last_end = row["signal_time_ms"] + HORIZON * 60_000
    metrics["symbol_nonoverlap_n"] = len(symbol_selected)
    issued_per_symbol = Counter(row["symbol"] for row in issued)
    metrics["issued_symbol_count"] = len(issued_per_symbol)
    metrics["max_symbol_issued_share"] = (
        max(issued_per_symbol.values()) / len(issued) if issued else None)
    metrics["per_symbol"] = {
        symbol: {"first_touch_arms": sum(row["symbol"] == symbol for row in arms),
                 "issued": sum(row["symbol"] == symbol for row in issued),
                 "m2_hits": sum(bool(row["candidate_m2"]) for row in issued if row["symbol"] == symbol),
                 "m2_rate": (sum(bool(row["candidate_m2"]) for row in issued if row["symbol"] == symbol) /
                             sum(row["symbol"] == symbol for row in issued)
                             if any(row["symbol"] == symbol for row in issued) else None)}
        for symbol in SYMBOLS}
    def group_period(period: str) -> dict:
        groups = {}
        for row in arms:
            dt = datetime.fromtimestamp(row["anchor_time_ms"] / 1000, tz=timezone.utc)
            key = f"{dt.year:04d}" if period == "year" else f"{dt.year:04d}-{dt.month:02d}"
            groups.setdefault(key, []).append(row)
        return {key: {
            "first_touch_arms": len(rows),
            "issued": sum(bool(row.get("candidate_signal")) for row in rows),
            "candidate_arm_m2_rate": float(np.mean([bool(row["candidate_arm_m2"]) for row in rows])),
            "baseline_arm_m2_rate": float(np.mean([bool(row["baseline_m2"]) for row in rows])),
            "candidate_arm_mean_net_base": float(np.mean([row["candidate_arm_net_base"] for row in rows])),
            "candidate_arm_mean_net_stress": float(np.mean([row["candidate_arm_net_stress"] for row in rows])),
        } for key, rows in sorted(groups.items())}
    metrics["by_utc_year"] = group_period("year")
    metrics["by_utc_month"] = group_period("month")
    metrics["baseline_m1_direction_accuracy"] = (
        float(np.mean([bool(row["m1_hit"])
                       for row in baseline_rows if row.get("m1_hit") is not None]))
        if any(row.get("m1_hit") is not None for row in baseline_rows) else None)
    metrics["development_screen"] = development_screen(metrics) if not data_defects else {
        "status": "DATA_INVALID", "checks": {}, "economic_gate": "NOT_RUN"}
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n",
                                                   encoding="utf-8")
    _write_gzip_jsonl(args.output_dir / "arm_ledger.jsonl.gz", arms)
    _write_gzip_jsonl(args.output_dir / "baseline_ledger.jsonl.gz", baseline_rows)
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
        parser.error("data root not found")
    if args.output_dir.resolve().is_relative_to(args.root.resolve()):
        parser.error("output must be outside immutable data root")
    print(json.dumps(run(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
