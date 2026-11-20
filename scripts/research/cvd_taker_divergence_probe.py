"""One-shot exploratory 1h taker-CVD divergence scoring, locked to prereg v2-v8."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import platform
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.cvd_block_bootstrap import (
    BLOCK_DAYS, REPLICATES, SEED, bootstrap_contrast, bootstrap_m2, event_weighted_m2,
)
from scripts.research.cvd_divergence_engine import (
    DAY_MS, HOUR_MS, MarketSeries, causal_prefix_check, generate_events, resolve_barrier,
)

START_MS = int(datetime(2023, 3, 23, tzinfo=timezone.utc).timestamp() * 1000)
END_MS = int(datetime(2025, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)
BASE_FEE = 0.001
STRESS_FEE = 0.003
HORIZONS = (10, 20)
DATES = np.arange(START_MS // DAY_MS, END_MS // DAY_MS, dtype=np.int64)
PRE_REGS = tuple(ROOT / "docs/research/inventory" / f"PREREG_CVD_TAKER_DIVERGENCE_1H_20261120{suffix}.md"
                 for suffix in ("", "_v2", "_v3", "_v4", "_v5", "_v6", "_v7", "_v8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_archive(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"corrupt ZIP member: {path.name}:{bad}")
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected exactly one CSV in {path}")
        with archive.open(members[0]) as raw:
            return list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")))


def load_symbol(root: Path, symbol: str, months: list[str]) -> tuple[MarketSeries, np.ndarray, np.ndarray]:
    candles, funding = [], []
    for month in months:
        kline_path = root / "klines_1h" / symbol / f"{symbol}-1h-{month}.zip"
        funding_path = root / "funding" / symbol / f"{symbol}-fundingRate-{month}.zip"
        for row in _read_archive(kline_path):
            candles.append((int(row["open_time"]), float(row["open"]), float(row["high"]),
                            float(row["low"]), float(row["close"]), float(row["volume"]),
                            float(row["taker_buy_volume"])))
        for row in _read_archive(funding_path):
            funding.append((int(row["calc_time"]), float(row["last_funding_rate"])))
    candles.sort(key=lambda row: row[0])
    funding.sort(key=lambda row: row[0])
    values = np.asarray(candles, dtype=float)
    times = values[:, 0].astype(np.int64)
    if len(times) < 21 or np.any(np.diff(times) <= 0):
        raise ValueError(f"duplicate or unordered hourly timestamps: {symbol}")
    funding_values = np.asarray(funding, dtype=float)
    ft = funding_values[:, 0].astype(np.int64)
    fr = funding_values[:, 1]
    if len(ft) != len(np.unique(ft)) or np.any(np.diff(ft) <= 0):
        raise ValueError(f"funding timestamps are not unique/sorted: {symbol}")
    return MarketSeries(times, *(values[:, column].copy() for column in range(1, 7))), ft, fr


def _sha_side(symbol: str, entry_open_ms: int) -> str:
    value = f"20261120|{symbol}|{entry_open_ms}".encode("utf-8")
    return "long" if hashlib.sha256(value).digest()[0] & 1 == 0 else "short"


def _wilson(successes: int, count: int) -> list[float | None]:
    if count == 0:
        return [None, None]
    z = 1.959963984540054
    p = successes / count
    denom = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denom
    margin = z * np.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denom
    return [float(center - margin), float(center + margin)]


def _market_indices(data: MarketSeries, event: dict) -> tuple[int, int]:
    entry_idx = int(event["entry_idx"])
    if entry_idx >= len(data.times) or int(data.times[entry_idx]) != int(event["entry_open_ms"]):
        raise ValueError("event entry index/time mismatch")
    return entry_idx, entry_idx + HOUR_MS


def _candidate_anchor_invalid(data: MarketSeries, event: dict) -> bool:
    if event.get("entry_idx") is None:
        return True
    idx = int(event["entry_idx"])
    entry = float(data.open[idx])
    stop = (float(event["pivot2_price"]) - 0.25 * float(event["atr_at_confirmation"])
            if event["side"] == "long" else
            float(event["pivot2_price"]) + 0.25 * float(event["atr_at_confirmation"]))
    return (event["side"] == "long" and stop >= entry) or (event["side"] == "short" and stop <= entry)


def score_event(data: MarketSeries, funding_times: np.ndarray, funding_rates: np.ndarray,
                event: dict, *, side: str, horizon: int) -> dict:
    if event.get("entry_idx") is None:
        return {"m2_hit": False, "reason": "MISSING_ENTRY_BAR", "net_base": None,
                "net_stress": None, "net_base_ex_exit_candle_funding": None,
                "r_base": None, "r_stress": None, "m1_hit": None,
                "entry": None, "stop": None, "target": None}
    entry_idx, _ = _market_indices(data, event)
    entry = float(data.open[entry_idx])
    raw_candidate_stop = (float(event["pivot2_price"]) - 0.25 * float(event["atr_at_confirmation"])
                          if event["side"] == "long" else
                          float(event["pivot2_price"]) + 0.25 * float(event["atr_at_confirmation"]))
    candidate_invalid = ((event["side"] == "long" and raw_candidate_stop >= entry)
                         or (event["side"] == "short" and raw_candidate_stop <= entry))
    risk_distance = abs(entry - raw_candidate_stop)
    if side == event["side"] and candidate_invalid:
        last_idx = entry_idx + horizon - 1
        m1 = None
        if last_idx < len(data.times) and np.array_equal(
                data.times[entry_idx:last_idx + 1],
                int(event["entry_open_ms"]) + np.arange(horizon, dtype=np.int64) * HOUR_MS):
            sign = 1 if side == "long" else -1
            m1 = sign * (float(data.close[last_idx]) / entry - 1.0) > 0
        return {"m2_hit": False, "reason": "INVALID_ENTRY", "net_base": 0.0,
                "net_stress": 0.0, "net_base_ex_exit_candle_funding": 0.0,
                "m1_hit": m1, "entry": entry, "stop": raw_candidate_stop,
                "target": None, "risk_distance": risk_distance, "risk_pct": risk_distance / entry,
                "r_base": 0.0, "r_stress": 0.0, "funding_signed": 0.0}
    stop = entry - risk_distance if side == "long" else entry + risk_distance
    expected_times = int(data.times[entry_idx]) + np.arange(horizon, dtype=np.int64) * HOUR_MS
    if entry_idx + horizon > len(data.times) or not np.array_equal(data.times[entry_idx:entry_idx + horizon], expected_times):
        return {"m2_hit": False, "reason": "DATA_GAP", "net_base": None,
                "net_stress": None, "net_base_ex_exit_candle_funding": None,
                "r_base": None, "r_stress": None,
                "m1_hit": None, "entry": entry,
                "stop": stop, "target": None, "risk_distance": risk_distance}
    entry_open = entry_idx
    path = slice(entry_idx, entry_idx + horizon)
    if (side == "long" and stop >= entry) or (side == "short" and stop <= entry):
        last_close = float(data.close[entry_idx + horizon - 1])
        sign = 1 if side == "long" else -1
        m1 = sign * (last_close / entry - 1.0) > 0
        return {"m2_hit": False, "reason": "INVALID_ENTRY", "net_base": 0.0,
                "net_stress": 0.0, "net_base_ex_exit_candle_funding": 0.0,
                "m1_hit": m1, "entry": entry, "stop": stop,
                "target": None, "risk_distance": risk_distance, "exit_price": entry,
                "funding_signed": 0.0, "risk_pct": risk_distance / entry,
                "r_base": 0.0, "r_stress": 0.0}
    result = resolve_barrier(
        side, entry, stop, data.open[path], data.high[path], data.low[path], data.close[path],
        data.times[path], funding_times, funding_rates, horizon,
    )
    sign = 1 if side == "long" else -1
    last_close = float(data.close[entry_idx + horizon - 1])
    net_before_fee = result["gross_return"] - result["funding_signed"]
    risk_pct = risk_distance / entry
    net_base = net_before_fee - BASE_FEE
    net_stress = net_before_fee - STRESS_FEE
    net_base_ex_exit = (result["gross_return"] - BASE_FEE
                        - (result["funding_signed"] - result["funding_exit_candle_charged"]))
    return {**result, "side": side, "entry": entry, "stop": stop,
            "risk_pct": risk_pct,
            "m1_hit": sign * (last_close / entry - 1.0) > 0,
            "net_base": net_base,
            "net_base_ex_exit_candle_funding": net_base_ex_exit,
            "net_stress": net_stress,
            "r_base": net_base / risk_pct if risk_pct > 0 else None,
            "r_stress": net_stress / risk_pct if risk_pct > 0 else None,
            "risk_distance": risk_distance}


def score_baseline_anchor(data: MarketSeries, funding_times: np.ndarray,
                          funding_rates: np.ndarray, event: dict, *,
                          side: str | None, horizon: int) -> dict:
    """Paired direction baselines inherit candidate missing/invalid-anchor misses."""
    if event.get("entry_idx") is None:
        return {"m2_hit": False, "reason": "MISSING_ENTRY_BAR", "net_base": None,
                "net_stress": None, "r_base": None, "r_stress": None, "m1_hit": None,
                "entry": None, "stop": None, "target": None}
    if _candidate_anchor_invalid(data, event):
        return {"m2_hit": False, "reason": "INVALID_ENTRY", "net_base": 0.0,
                "net_stress": 0.0, "r_base": 0.0, "r_stress": 0.0,
                "m1_hit": None, "entry": float(data.open[event["entry_idx"]]),
                "stop": None, "target": None, "risk_distance": None}
    if side is None:
        return {"m2_hit": False, "reason": "ABSTAIN", "net_base": 0.0,
                "net_stress": 0.0, "r_base": 0.0, "r_stress": 0.0,
                "m1_hit": False, "entry": float(data.open[event["entry_idx"]]),
                "stop": None, "target": None, "risk_distance": None}
    result = score_event(data, funding_times, funding_rates, event, side=side, horizon=horizon)
    candidate_stop = (float(event["pivot2_price"]) - 0.25 * float(event["atr_at_confirmation"])
                      if event["side"] == "long" else
                      float(event["pivot2_price"]) + 0.25 * float(event["atr_at_confirmation"]))
    expected_distance = abs(float(data.open[event["entry_idx"]]) - candidate_stop)
    if result.get("risk_distance") != expected_distance:
        raise AssertionError("baseline risk distance differs from candidate anchor")
    return result


def _daily_labels(rows: list[dict], outcome_key: str) -> list[list[int]]:
    result = [[] for _ in DATES]
    offset = int(DATES[0])
    for row in rows:
        index = int(row["entry_open_ms"]) // DAY_MS - offset
        if 0 <= index < len(result):
            value = row[outcome_key]
            result[index].append(int(bool(value)))
    return result


def _fixed_clusters(events_by_arm: dict[str, list[dict]]) -> list[int]:
    stamps = sorted({int(row["entry_open_ms"]) for rows in events_by_arm.values() for row in rows})
    retained, previous = [], None
    for stamp in stamps:
        if previous is None or stamp >= previous + 20 * HOUR_MS:
            retained.append(stamp)
            previous = stamp
    return retained


def _net_summary(rows: list[dict], field: str) -> dict:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    reasons = {}
    for row in rows:
        reason = row.get("reason", "UNKNOWN")
        reasons[reason] = reasons.get(reason, 0) + 1
    return {"mean": float(np.mean(values)) if values else None,
            "median": float(np.median(values)) if values else None,
            "positive_rate": float(np.mean(np.asarray(values) > 0)) if values else None,
            "n_with_net": len(values), "exit_reasons": reasons}


def _path_data_complete(rows: list[dict]) -> bool:
    return not any(row.get("reason") in {"DATA_GAP", "MISSING_ENTRY_BAR"} for row in rows)


def _mark_incomplete_path_cell(result: dict, *row_groups: list[dict]) -> dict:
    if not all(_path_data_complete(rows) for rows in row_groups):
        return {**result, "status": "NOT_EVALUABLE",
                "reason": "one or more issued anchors have a missing hourly path or next-open bar"}
    return result


def _arm_metrics(rows: list[dict], eligible_bars: int, retained_clusters: list[int]) -> dict:
    hits = sum(bool(row["m2_hit"]) for row in rows)
    m1_rows = [row for row in rows if row.get("m1_hit") is not None]
    retained_set = set(retained_clusters)
    nonoverlap = [row for row in rows if int(row["entry_open_ms"]) in retained_set]
    symbols = sorted({row["symbol"] for row in rows})
    nonoverlap_symbols = sorted({row["symbol"] for row in nonoverlap})
    return {
        "issued_n": len(rows), "m2_hits": hits,
        "m2_rate": hits / len(rows) if rows else None,
        "m2_wilson95_independence_assuming": _wilson(hits, len(rows)),
        "m1_n": len(m1_rows),
        "m1_direction_accuracy": (sum(bool(row["m1_hit"]) for row in m1_rows) / len(m1_rows)) if m1_rows else None,
        "coverage_pct": 100 * len(rows) / eligible_bars if eligible_bars else None,
        "eligible_bar_denominator": eligible_bars, "symbols": symbols, "symbol_count": len(symbols),
        "nonoverlap_cluster_n": len({int(row["entry_open_ms"]) for row in nonoverlap}),
        "nonoverlap_event_n": len(nonoverlap), "nonoverlap_symbols": nonoverlap_symbols,
        "nonoverlap_symbol_count": len(nonoverlap_symbols),
        "net_base": _net_summary(rows, "net_base"), "net_stress": _net_summary(rows, "net_stress"),
        "net_base_ex_exit_candle_funding": _net_summary(rows, "net_base_ex_exit_candle_funding"),
        "funding_cost_primary": _net_summary(rows, "funding_signed"),
        "net_r_base": _net_summary(rows, "r_base"), "net_r_stress": _net_summary(rows, "r_stress"),
    }


def _validate_gate_inputs(input_audit: dict, funding_audit: dict, symbols: list[str],
                          months: list[str]) -> None:
    if input_audit.get("status") != "PASS" or input_audit.get("archive_records") != 1728:
        raise ValueError("pre-score CVD archive audit is not a PASS over 1,728 required archives")
    required_archive_keys = {(kind, symbol, month) for kind in ("klines_1h", "funding")
                             for symbol in symbols for month in months}
    audit_records = input_audit.get("records", [])
    observed_archive_keys = [(row.get("kind"), row.get("symbol"), row.get("month"))
                             for row in audit_records]
    if (len(observed_archive_keys) != len(set(observed_archive_keys))
            or set(observed_archive_keys) != required_archive_keys):
        raise ValueError("input audit records do not equal the exact frozen symbol/month/kind set")
    if funding_audit.get("status") != "PASS" or funding_audit.get("sample_count") != len(symbols) * 3:
        raise ValueError("pre-score funding mapping audit is not a PASS over the fixed cohort/date grid")
    if funding_audit.get("dates_utc") != ["2023-03-24", "2024-03-24", "2025-02-28"]:
        raise ValueError("funding audit dates differ from the frozen v6 sample")
    if sorted(funding_audit.get("symbols", [])) != sorted(symbols):
        raise ValueError("funding audit symbol cohort differs from the frozen exact cohort")
    if funding_audit.get("endpoint") != "https://fapi.binance.com/fapi/v1/fundingRate":
        raise ValueError("funding audit endpoint differs from the frozen official USD-M REST endpoint")
    cases = funding_audit.get("records", [])
    case_keys = [(row.get("symbol"), row.get("date_utc")) for row in cases]
    expected_case_keys = {(symbol, day) for symbol in symbols
                          for day in ("2023-03-24", "2024-03-24", "2025-02-28")}
    if len(case_keys) != len(set(case_keys)) or set(case_keys) != expected_case_keys:
        raise ValueError("funding audit records do not equal the exact frozen symbol/date set")
    for record in cases:
        response_hash = record.get("response_sha256", "")
        if (record.get("http_status") != 200 or len(response_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in response_hash)
                or record.get("archive_rows") != record.get("api_rows")
                or record.get("timestamp_matches") != record.get("archive_rows")
                or record.get("exact_rate_matches") != record.get("archive_rows")
                or record.get("archive_only_timestamps") or record.get("api_only_timestamps")
                or record.get("duplicate_archive_timestamps") or record.get("duplicate_api_timestamps")):
            raise ValueError(f"funding audit detail failed: {record.get('symbol')} {record.get('date_utc')}")
    if any(record.get("status") != "PASS" for record in input_audit.get("records", [])):
        raise ValueError("failed CVD input archive exists")
    funding_archive_records = [r for r in input_audit.get("records", [])
                               if r.get("kind") == "funding"]
    if (input_audit.get("funding_month_boundary_checks") != len(symbols) * len(months)
            or len(funding_archive_records) != len(symbols) * len(months)
            or any(r.get("boundary_checked") is not True or r.get("utc_grid_checked") is not True
                   for r in funding_archive_records)):
        raise ValueError("funding archive UTC-grid/month-boundary completeness audit is missing or incomplete")
    if any(record.get("status") != "PASS" for record in funding_audit.get("records", [])):
        raise ValueError("failed funding mapping sample exists")


def _validate_review_gate(gate: dict, source_hashes: dict, prereg_hashes: dict,
                          input_audit_hash: str, funding_audit_hash: str,
                          source_commit: str) -> None:
    if gate.get("source_commit") != source_commit:
        raise ValueError("review gate source commit differs from the current checkout")
    expected_roles = {"BLUE", "RED", "METHODS", "JUDGE"}
    reviews = gate.get("reviews", [])
    roles = [review.get("role") for review in reviews]
    if len(roles) != len(set(roles)) or set(roles) != expected_roles:
        raise ValueError("review gate must contain exactly one review per required role")
    for review in reviews:
        if review.get("verdict") != "PASS" or review.get("scoring_approval") is not True:
            raise ValueError(f"review gate lacks scoring approval from {review.get('role')}")
        if review.get("source_hashes") != source_hashes:
            raise ValueError(f"reviewed source hashes differ for role {review.get('role')}")
        if review.get("preregistration_hashes") != prereg_hashes:
            raise ValueError(f"reviewed preregistration hashes differ for role {review.get('role')}")
        if review.get("input_audit_sha256") != input_audit_hash:
            raise ValueError(f"reviewed input-audit hash differs for role {review.get('role')}")
        if review.get("funding_audit_sha256") != funding_audit_hash:
            raise ValueError(f"reviewed funding-audit hash differs for role {review.get('role')}")


def _require_clean_worktree(status: str) -> None:
    if status.strip():
        raise ValueError("worktree is not clean; refusing to score an uncommitted source state")


def run(archive_root: Path, coverage_path: Path, manifest_path: Path,
        input_audit_path: Path, funding_audit_path: Path, review_gate_path: Path,
        output_dir: Path) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output_dir}")
    try:
        source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        dirty_state = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    except Exception as exc:
        raise ValueError("source commit/worktree provenance unavailable; refusing to score") from exc
    if not source_commit:
        raise ValueError("source commit provenance unavailable; refusing to score")
    _require_clean_worktree(dirty_state)
    input_audit = json.loads(input_audit_path.read_text(encoding="utf-8"))
    funding_audit = json.loads(funding_audit_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    symbols = coverage["cohorts_by_exact_run"]["2023-03..2026-05"]
    months = []
    year, month = 2023, 3
    while (year, month) <= (2025, 2):
        months.append(f"{year:04d}-{month:02d}")
        year, month = ((year + 1, 1) if month == 12 else (year, month + 1))
    _validate_gate_inputs(input_audit, funding_audit, symbols, months)

    # Bind the run to exactly the prescored archive manifests and all fixed rules.
    manifest_rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected_keys = {(r["kind"], r["symbol"], r["month"]) for r in input_audit["records"]}
    relevant_manifest = [row for row in manifest_rows
                         if (row.get("kind"), row.get("symbol"), row.get("month")) in expected_keys]
    relevant_keys = [(row.get("kind"), row.get("symbol"), row.get("month")) for row in relevant_manifest]
    if len(relevant_keys) != len(set(relevant_keys)) or set(relevant_keys) != expected_keys:
        raise ValueError("preserved manifest does not contain the exact unique pre-scored archive set")
    manifest_map = {(row.get("kind"), row.get("symbol"), row.get("month")): row.get("sha256")
                    for row in relevant_manifest if row.get("status") in {"downloaded", "cached_verified"}}
    expected_records = {(r["kind"], r["symbol"], r["month"]): r["sha256"]
                        for r in input_audit["records"] if r["status"] == "PASS"}
    if expected_records != {key: digest for key, digest in manifest_map.items() if key in expected_records}:
        raise ValueError("pre-score input audit fingerprint differs from preserved manifest")
    manifest_fingerprint = hashlib.sha256("\n".join(
        f"{kind}|{symbol}|{month}|{digest}" for (kind, symbol, month), digest in sorted(expected_records.items())
    ).encode()).hexdigest()
    source_files = [Path(__file__), ROOT / "scripts/research/cvd_divergence_engine.py",
                    ROOT / "scripts/research/cvd_block_bootstrap.py",
                    ROOT / "scripts/research/audit_cvd_inputs.py",
                    ROOT / "scripts/research/audit_funding_timestamp_mapping.py",
                    ROOT / "tests/test_audit_cvd_inputs.py",
                    ROOT / "tests/test_audit_funding_timestamp_mapping.py",
                    ROOT / "tests/test_cvd_divergence_engine.py",
                    ROOT / "tests/test_cvd_block_bootstrap.py",
                    ROOT / "tests/test_cvd_taker_divergence_probe.py"]
    source_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in source_files}
    prereg_hashes = {path.name: sha256_file(path) for path in PRE_REGS}
    input_audit_hash = sha256_file(input_audit_path)
    funding_audit_hash = sha256_file(funding_audit_path)
    review_gate = json.loads(review_gate_path.read_text(encoding="utf-8"))
    _validate_review_gate(review_gate, source_hashes, prereg_hashes, input_audit_hash,
                          funding_audit_hash, source_commit)

    # Re-hash every required archive before reading features or labels.
    for record in input_audit["records"]:
        symbol, month, kind = record["symbol"], record["month"], record["kind"]
        filename = (f"{symbol}-1h-{month}.zip" if kind == "klines_1h"
                    else f"{symbol}-fundingRate-{month}.zip")
        current = archive_root / kind / symbol / filename
        if sha256_file(current) != record["sha256"]:
            raise ValueError(f"archive changed after pre-score QA: {kind}/{symbol}/{month}")

    arms: dict[str, list[dict]] = {"price_only": [], "cvd": []}
    eligible_bars_total = 0
    causal_checks = []
    union_clusters = None
    for symbol in symbols:
        data, funding_times, funding_rates = load_symbol(archive_root, symbol, months)
        # Strictly discard all bars outside the frozen development interval before feature generation.
        mask = (data.times < END_MS)
        data = MarketSeries(*(np.asarray(value)[mask] for value in (
            data.times, data.open, data.high, data.low, data.close, data.volume, data.taker_buy_volume)))
        funding_mask = funding_times < END_MS
        funding_times, funding_rates = funding_times[funding_mask], funding_rates[funding_mask]
        for arm in arms:
            check = causal_prefix_check(symbol, data, arm=arm, eligible_start_ms=START_MS,
                                        eligible_end_ms=END_MS)
            causal_checks.append({"symbol": symbol, "arm": arm, **check})
            if check["status"] != "PASS":
                raise ValueError(f"causal prefix/future mutation check failed: {symbol} {arm}")
        for arm in arms:
            events, eligible = generate_events(symbol, data, arm=arm, eligible_start_ms=START_MS,
                                                eligible_end_ms=END_MS)
            if arm == "price_only":
                eligible_bars_total += eligible
            for event in events:
                event["funding_times"] = funding_times
                event["funding_rates"] = funding_rates
                event["data"] = data
            arms[arm].extend(events)

    # Freeze outcome-independent overlap clusters immediately after signal generation.
    union_clusters = _fixed_clusters({arm: events for arm, events in arms.items()})

    # Resolve candidate and price-only streams for both preregistered horizons.
    scored: dict[tuple[str, int], list[dict]] = {}
    for arm, events in arms.items():
        for horizon in HORIZONS:
            scored[(arm, horizon)] = []
            for event in events:
                data = event["data"]
                result = score_event(data, event["funding_times"], event["funding_rates"], event,
                                     side=event["side"], horizon=horizon)
                scored[(arm, horizon)].append({**{k: v for k, v in event.items()
                                                  if k not in {"data", "funding_times", "funding_rates"}},
                                               **result, "horizon_hours": horizon})

    # Four fixed direction controls are evaluated at each candidate CVD anchor, same horizon and risk distance.
    baseline_rows: dict[tuple[str, int], list[dict]] = {}
    for horizon in HORIZONS:
        for name in ("always_long", "always_short", "previous_hour_momentum", "sha256_random"):
            baseline_rows[(name, horizon)] = []
            for event in arms["cvd"]:
                if name == "always_long":
                    side = "long"
                elif name == "always_short":
                    side = "short"
                elif name == "previous_hour_momentum":
                    side = event["baseline_momentum_side"]
                else:
                    side = _sha_side(event["symbol"], event["entry_open_ms"])
                result = score_baseline_anchor(
                    event["data"], event["funding_times"], event["funding_rates"],
                    event, side=side, horizon=horizon)
                baseline_rows[(name, horizon)].append({
                    "symbol": event["symbol"], "arm": name, "side": side,
                    "entry_open_ms": event["entry_open_ms"], "horizon_hours": horizon, **result,
                })

    summary = {"arms": {}, "baselines": {}, "inference": {}, "causal_checks": causal_checks,
               "development_only": True}
    for arm in arms:
        summary["arms"][arm] = {}
        for horizon in HORIZONS:
            rows = scored[(arm, horizon)]
            labels = _daily_labels(rows, "m2_hit")
            inference = _mark_incomplete_path_cell(bootstrap_m2(labels), rows)
            summary["arms"][arm][str(horizon)] = {
                **_arm_metrics(rows, eligible_bars_total, union_clusters),
                "m2_block_bootstrap": inference,
                "side_metrics": {
                    side: _arm_metrics([r for r in rows if r["side"] == side], eligible_bars_total,
                                       union_clusters)
                    for side in ("long", "short")
                },
            }
    for name in ("always_long", "always_short", "previous_hour_momentum", "sha256_random"):
        summary["baselines"][name] = {}
        for horizon in HORIZONS:
            rows = baseline_rows[(name, horizon)]
            paired_candidate = scored[("cvd", horizon)]
            paired_daily_left, paired_daily_right = ([[] for _ in DATES], [[] for _ in DATES])
            date_offset = int(DATES[0])
            if len(paired_candidate) != len(rows):
                raise AssertionError("paired baseline anchor count differs from candidate")
            for candidate, baseline in zip(paired_candidate, rows):
                di = int(candidate["entry_open_ms"]) // DAY_MS - date_offset
                paired_daily_left[di].append(int(bool(candidate["m2_hit"])))
                paired_daily_right[di].append(int(bool(baseline["m2_hit"])))
            contrast = _mark_incomplete_path_cell(
                bootstrap_contrast(paired_daily_left, paired_daily_right, paired=True),
                paired_candidate, rows)
            baseline_summary = _arm_metrics(rows, eligible_bars_total, union_clusters)
            issued_side_n = sum(row.get("side") is not None for row in rows)
            baseline_summary["standalone_issued_n"] = issued_side_n
            baseline_summary["standalone_m2_rate_excluding_abstentions"] = (
                sum(bool(row["m2_hit"]) for row in rows if row.get("side") is not None) / issued_side_n
                if issued_side_n else None)
            baseline_summary["coverage_pct"] = 100 * issued_side_n / eligible_bars_total if eligible_bars_total else None
            summary["baselines"][name][str(horizon)] = baseline_summary
            summary["inference"][f"cvd_vs_{name}_{horizon}h"] = contrast

    for horizon in HORIZONS:
        left = _daily_labels(scored[("cvd", horizon)], "m2_hit")
        right = _daily_labels(scored[("price_only", horizon)], "m2_hit")
        summary["inference"][f"cvd_vs_price_only_{horizon}h"] = _mark_incomplete_path_cell(
            bootstrap_contrast(left, right, paired=False),
            scored[("cvd", horizon)], scored[("price_only", horizon)])

    summary["cvd_incremental_claim_supported_both_horizons"] = all(
        summary["inference"][f"cvd_vs_price_only_{horizon}h"].get("status") == "PASS"
        and
        summary["inference"][f"cvd_vs_price_only_{horizon}h"].get("simultaneous_lower") is not None
        and summary["inference"][f"cvd_vs_price_only_{horizon}h"]["simultaneous_lower"] > 0
        for horizon in HORIZONS)

    summary["development_threshold_check"] = {}
    for horizon in HORIZONS:
        candidate = summary["arms"]["cvd"][str(horizon)]
        baseline_cells = {name: summary["baselines"][name][str(horizon)]
                          for name in ("always_long", "always_short", "previous_hour_momentum", "sha256_random")}
        eligible_baselines = {
            name: cell["standalone_m2_rate_excluding_abstentions"]
            for name, cell in baseline_cells.items()
            if cell["coverage_pct"] is not None and cell["coverage_pct"] >= candidate["coverage_pct"]
            and cell["standalone_m2_rate_excluding_abstentions"] is not None
        }
        strongest_baseline = max(eligible_baselines.values()) if eligible_baselines else None
        baseline_lcbs = [summary["inference"][f"cvd_vs_{name}_{horizon}h"].get("simultaneous_lower")
                         if summary["inference"][f"cvd_vs_{name}_{horizon}h"].get("status") == "PASS"
                         else None for name in baseline_cells]
        no_gaps = (candidate["net_base"]["n_with_net"] == candidate["issued_n"]
                   and candidate["net_stress"]["n_with_net"] == candidate["issued_n"]
                   and candidate["net_base"]["exit_reasons"].get("DATA_GAP", 0) == 0
                   and candidate["net_base"]["exit_reasons"].get("MISSING_ENTRY_BAR", 0) == 0)
        checks = {
            "point_m2_at_least_80pct": candidate["m2_rate"] is not None and candidate["m2_rate"] >= 0.80,
            "wilson_lower_above_strongest_valid_baseline": (
                strongest_baseline is not None and candidate["m2_wilson95_independence_assuming"][0] > strongest_baseline),
            "all_four_simultaneous_baseline_lowers_positive": (
                len(baseline_lcbs) == 4 and all(value is not None and value > 0 for value in baseline_lcbs)),
            "coverage_at_least_10pct": candidate["coverage_pct"] is not None and candidate["coverage_pct"] >= 10,
            "total_n_at_least_200": candidate["issued_n"] >= 200,
            "total_symbol_count_at_least_20": candidate["symbol_count"] >= 20,
            "nonoverlap_cluster_n_at_least_200": candidate["nonoverlap_cluster_n"] >= 200,
            "nonoverlap_event_n_at_least_200": candidate["nonoverlap_event_n"] >= 200,
            "nonoverlap_symbol_count_at_least_20": candidate["nonoverlap_symbol_count"] >= 20,
            "base_and_stress_net_expectancy_positive": (
                candidate["net_base"]["mean"] is not None and candidate["net_base"]["mean"] > 0
                and candidate["net_stress"]["mean"] is not None and candidate["net_stress"]["mean"] > 0),
            "all_required_path_cost_data_complete": no_gaps,
        }
        checks["all_quantitative_checks_pass"] = all(checks.values())
        summary["development_threshold_check"][str(horizon)] = {
            "checks": checks, "strongest_valid_baseline_m2": strongest_baseline,
            "valid_baseline_m2": eligible_baselines,
            "historical_core_eligibility": False,
            "reason": "previously exposed development sample; no OOS/core claim permitted",
        }

    # Full per-event records are written to a separate JSONL file; output contains no source candles.
    output_dir.mkdir(parents=True, exist_ok=False)
    records_path = output_dir / "event_results.jsonl"
    with records_path.open("x", encoding="utf-8") as sink:
        for key, rows in sorted(scored.items()):
            for row in rows:
                sink.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
        for key, rows in sorted(baseline_rows.items()):
            for row in rows:
                sink.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")

    result = {
        "status": "EXPLORATORY_SCORED",
        "preregistration": "v2-v8; historical development sample only; not OOS/core",
        "period_utc": ["2023-03-23T00:00:00Z", "2025-03-01T00:00:00Z"],
        "symbols": symbols, "symbol_count": len(symbols), "eligible_bars": eligible_bars_total,
        "daily_grid_utc": [datetime.fromtimestamp(int(DATES[0]) * 86400, timezone.utc).date().isoformat(),
                           datetime.fromtimestamp(int(DATES[-1]) * 86400, timezone.utc).date().isoformat()],
        "input_audit_sha256": input_audit_hash,
        "funding_audit_sha256": funding_audit_hash,
        "review_gate_sha256": sha256_file(review_gate_path),
        "manifest_file_sha256": sha256_file(manifest_path),
        "manifest_fingerprint": manifest_fingerprint,
        "preregistration_sha256": prereg_hashes,
        "source_hashes": source_hashes, "source_commit": source_commit,
        "worktree_dirty_at_scoring": bool(dirty_state),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "bootstrap": {"seed": SEED, "prng": "NumPy PCG64", "replicates": REPLICATES,
                      "block_days": BLOCK_DAYS, "method": "synchronized non-circular moving blocks",
                      "simultaneous_family_size": 10,
                      "sampled_date_indices_sha256_by_metric": {
                          key: value.get("indices_sha256") for key, value in summary["inference"].items()},
                      "candidate_m2_indices_sha256_by_horizon": {
                          horizon: summary["arms"]["cvd"][horizon]["m2_block_bootstrap"].get("indices_sha256")
                          for horizon in ("10", "20")}},
        "fee_round_trip": {"base": BASE_FEE, "stress": STRESS_FEE},
        "fixed_cluster_count_union": len(union_clusters),
        "signal_counts": {arm: len(events) for arm, events in arms.items()},
        "summary": summary,
        "event_results_sha256": sha256_file(records_path),
        "limitations": ["Previously exposed historical development interval; reject/debug only.",
                        "Funding timestamp mapping validated on 36 symbols x 3 days, not every historical row.",
                        "Contract OHLC barriers are not mark-price/liquidation-trigger fills.",
                        "Fee proxies omit spread/market impact; historical symbol universe has survivorship/selection risk.",
                        "Seven-day block inference is approximate under regimes/dependence longer than block length."],
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--input-audit", type=Path, required=True)
    parser.add_argument("--funding-audit", type=Path, required=True)
    parser.add_argument("--review-gate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.archive_root, args.coverage, args.manifest, args.input_audit,
                 args.funding_audit, args.review_gate, args.output_dir)
    print(json.dumps({"status": result["status"], "signal_counts": result["signal_counts"],
                      "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
