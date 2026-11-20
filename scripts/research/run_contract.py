"""Pure validation for the version-1 comparable research run envelope.

This module does not read market data, write artifacts, execute trades, or
modify the append-only experiment registry. It checks that a completed run
record contains enough provenance to be compared under the research protocol.
"""
from __future__ import annotations

from datetime import datetime
import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


MARKETS = {"crypto", "kr", "us"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _mapping(value: Any) -> bool:
    return isinstance(value, dict)


def validate_run_record(record: Any) -> list[str]:
    """Return deterministic validation errors; an empty list means structurally valid.

    Structural validity is not a pass verdict. This function cannot establish
    that source data are true, fills are realistic, a split is untouched, or a
    strategy satisfies its market-specific performance threshold.
    """
    errors: list[str] = []
    if not _mapping(record):
        return ["record must be an object"]

    required = ("schema_version", "run_id", "market", "status", "frozen_at", "run_started_at",
                "preregistration_sha256", "code_sha", "inputs", "period",
                "code_files", "splits", "cost_scenarios", "execution", "counts", "metrics")
    for key in required:
        if key not in record:
            errors.append(f"missing {key}")

    if record.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(record.get("run_id"), str) or not record.get("run_id", "").strip():
        errors.append("run_id must be a non-empty string")
    if record.get("market") not in MARKETS:
        errors.append("market must be crypto, kr, or us")
    if record.get("status") not in {"complete", "blocked", "failed"}:
        errors.append("status must be complete, blocked, or failed")
    if not _is_iso_datetime(record.get("frozen_at")):
        errors.append("frozen_at must be an ISO-8601 timestamp with timezone")
    if not _is_iso_datetime(record.get("run_started_at")):
        errors.append("run_started_at must be an ISO-8601 timestamp with timezone")
    if _is_iso_datetime(record.get("frozen_at")) and _is_iso_datetime(record.get("run_started_at")):
        frozen = datetime.fromisoformat(record["frozen_at"].replace("Z", "+00:00"))
        started = datetime.fromisoformat(record["run_started_at"].replace("Z", "+00:00"))
        if frozen >= started:
            errors.append("preregistration must be frozen before the run starts")
    if not isinstance(record.get("preregistration_sha256"), str) or not SHA256_RE.fullmatch(
        record.get("preregistration_sha256", "")
    ):
        errors.append("preregistration_sha256 must be a lowercase SHA-256 hex digest")
    if not isinstance(record.get("code_sha"), str) or not re.fullmatch(
        r"[0-9a-f]{7,64}", record.get("code_sha", "")
    ):
        errors.append("code_sha must be a lowercase Git SHA")
    code_files = record.get("code_files")
    if not isinstance(code_files, list) or not code_files:
        errors.append("code_files must be a non-empty list")
    else:
        for index, item in enumerate(code_files):
            if not _mapping(item):
                errors.append(f"code_files[{index}] must be an object")
                continue
            if not isinstance(item.get("ref"), str) or not item["ref"].strip():
                errors.append(f"code_files[{index}].ref is required")
            digest = item.get("sha256")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"code_files[{index}].sha256 must be a lowercase SHA-256 digest")

    inputs = record.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        errors.append("inputs must be a non-empty list")
    else:
        for index, item in enumerate(inputs):
            if not _mapping(item):
                errors.append(f"inputs[{index}] must be an object")
                continue
            if not isinstance(item.get("role"), str) or not item["role"].strip():
                errors.append(f"inputs[{index}].role is required")
            if not isinstance(item.get("ref"), str) or not item["ref"].strip():
                errors.append(f"inputs[{index}].ref is required")
            digest = item.get("sha256")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"inputs[{index}].sha256 must be a lowercase SHA-256 digest")

    period = record.get("period")
    if not _mapping(period):
        errors.append("period must be an object")
    else:
        for key in ("start", "end"):
            if not _is_iso_datetime(period.get(key)):
                errors.append(f"period.{key} must be an ISO-8601 timestamp with timezone")
        if all(_is_iso_datetime(period.get(k)) for k in ("start", "end")):
            start = datetime.fromisoformat(period["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
            if start >= end:
                errors.append("period.start must precede period.end")

    splits = record.get("splits")
    split_names = ("development", "validation", "sealed")
    if not _mapping(splits):
        errors.append("splits must be an object")
    else:
        parsed: list[tuple[datetime, datetime]] = []
        for name in split_names:
            split = splits.get(name)
            if not _mapping(split):
                errors.append(f"splits.{name} must be an object")
                continue
            if split.get("reused_for_tuning") is not False:
                errors.append(f"splits.{name}.reused_for_tuning must be false")
            bounds = [split.get("start"), split.get("end")]
            if not all(_is_iso_datetime(value) for value in bounds):
                errors.append(f"splits.{name} needs timezone-aware start and end")
                continue
            left, right = (datetime.fromisoformat(v.replace("Z", "+00:00")) for v in bounds)
            if left >= right:
                errors.append(f"splits.{name}.start must precede end")
            parsed.append((left, right))
        for index in range(1, len(parsed)):
            if parsed[index - 1][1] > parsed[index][0]:
                errors.append("development, validation, and sealed splits must not overlap")
                break
        if _mapping(period) and all(_is_iso_datetime(period.get(k)) for k in ("start", "end")):
            period_start = datetime.fromisoformat(period["start"].replace("Z", "+00:00"))
            period_end = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
            if any(left < period_start or right > period_end for left, right in parsed):
                errors.append("all split bounds must be contained in period")

    costs = record.get("cost_scenarios")
    if not _mapping(costs) or not {"base", "stress"}.issubset(costs):
        errors.append("cost_scenarios must include base and stress")
    elif not all(_mapping(costs.get(name)) for name in ("base", "stress")):
        errors.append("base and stress cost scenarios must be objects")

    execution = record.get("execution")
    if not _mapping(execution):
        errors.append("execution must be an object")
    else:
        for key in ("fill_rule", "same_bar_rule", "funding_rule"):
            if not isinstance(execution.get(key), str) or not execution[key].strip():
                errors.append(f"execution.{key} must be documented")

    counts = record.get("counts")
    if not _mapping(counts):
        errors.append("counts must be an object")
    else:
        if record.get("market") in {"kr", "us"}:
            keys = ("oos_round_trips",)
        elif record.get("market") == "crypto":
            keys = ("oos_issued_signals", "oos_nonoverlap_signals")
        else:
            keys = ()
        for key in keys:
            value = counts.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"counts.{key} must be a non-negative integer")

    metrics = record.get("metrics")
    if not _mapping(metrics):
        errors.append("metrics must be an object")
    else:
        metric_keys = (("cagr", "mdd", "sharpe") if record.get("market") in {"kr", "us"}
                       else ("m2_target_first_rate", "m2_wilson_95_low",
                             "m2_wilson_95_high", "m1_direction_accuracy",
                             "net_expectancy"))
        for key in metric_keys:
            value = metrics.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                errors.append(f"metrics.{key} must be numeric")
        if record.get("market") == "crypto":
            for key in ("m2_target_first_rate", "m2_wilson_95_low", "m2_wilson_95_high",
                        "m1_direction_accuracy"):
                value = metrics.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    if not 0 <= value <= 1:
                        errors.append(f"metrics.{key} must be between 0 and 1")
            low, high = metrics.get("m2_wilson_95_low"), metrics.get("m2_wilson_95_high")
            if all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                   for v in (low, high)) and low > high:
                errors.append("M2 Wilson lower bound must not exceed upper bound")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path, help="JSON run envelope to validate; file is read-only")
    args = parser.parse_args()
    try:
        with args.record.open(encoding="utf-8") as stream:
            record = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INVALID: cannot read JSON run envelope: {exc}")
        return 2
    errors = validate_run_record(record)
    if errors:
        print("INVALID STRUCTURE")
        for error in errors:
            print(f"- {error}")
        return 1
    print("STRUCTURALLY VALID (not a data, performance, or strategy approval)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
