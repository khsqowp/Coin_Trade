"""One preregistered UTC weekday-hour direction-persistence M2 evaluation.

The runner has three gates: audit (no market outcomes), baseline (development
only), and score (the fixed 2026-06..2026-09 extension). Source archives are
read-only. Results are exploratory and cannot establish Core eligibility.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.verify_usdm_archives import verify as verify_archives

PREREG = ROOT / "docs/research/inventory/PREREG_UTC_WEEKDAY_HOUR_SIGN_M2_20261120.md"
COHORT_KEY = "2023-03..2026-05"
SYMBOLS_EXCLUDED = {"IMXUSDT"}
INPUT_MONTHS = tuple(
    f"{year:04d}-{month:02d}"
    for year, month in ((y, m) for y in range(2024, 2027) for m in range(1, 13))
    if "2024-06" <= f"{year:04d}-{month:02d}" <= "2026-09"
)
DEV_START = "2025-06-01T00:00:00Z"
SCORE_START = "2026-06-01T00:00:00Z"
SCORE_END = "2026-10-01T00:00:00Z"
HOUR_MS = 3_600_000
LOOKBACK_OCCURRENCES = 52
LOOKBACK_BARS = 7 * 24 * LOOKBACK_OCCURRENCES
HORIZON_BARS = 4
ATR_BARS = 14
BASE_FEE_RT = 0.001
STRESS_FEE_RT = 0.003
BOOTSTRAP_SEED = 20261120
BOOTSTRAP_DRAWS = 2000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_rows(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _read_zip_csv(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV member in {path.name}")
        with archive.open(members[0]) as binary:
            with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
                return list(csv.DictReader(text))


def _month_grid(month: str) -> np.ndarray:
    start = int(datetime.strptime(month + "-01", "%Y-%m-%d").replace(
        tzinfo=timezone.utc).timestamp() * 1000)
    year, mon = map(int, month.split("-"))
    next_year, next_mon = ((year + 1, 1) if mon == 12 else (year, mon + 1))
    end = int(datetime(next_year, next_mon, 1, tzinfo=timezone.utc).timestamp() * 1000)
    return np.arange(start, end, HOUR_MS, dtype=np.int64)


def _archive_path(root: Path, kind: str, symbol: str, month: str) -> Path:
    filename = (f"{symbol}-fundingRate-{month}.zip" if kind == "funding"
                else f"{symbol}-1h-{month}.zip")
    return root / kind / symbol / filename


def _daily_mark_path(root: Path, symbol: str, date: str) -> Path:
    return root / "mark_price_1h_daily" / symbol / f"{symbol}-1h-{date}.zip"


def _validate_ohlc(rows: list[dict[str, str]], time_key: str,
                   require_contiguous: bool = True) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    times = np.asarray([int(row[time_key]) for row in rows], dtype=np.int64)
    values = {key: np.asarray([float(row[key]) for row in rows], dtype=float)
              for key in ("open", "high", "low", "close")}
    if (not len(times) or len(np.unique(times)) != len(times)
            or np.any(np.diff(times) <= 0)
            or (require_contiguous and np.any(np.diff(times) != HOUR_MS))):
        raise ValueError("hourly timestamp grid has missing, duplicate, or unordered rows")
    if not all(np.all(np.isfinite(col)) for col in values.values()):
        raise ValueError("non-finite OHLC value")
    o, h, l, c = (values[key] for key in ("open", "high", "low", "close"))
    if np.any(h < np.maximum(o, c)) or np.any(l > np.minimum(o, c)) or np.any(h < l):
        raise ValueError("OHLC invariants failed")
    if np.any(np.minimum.reduce((o, h, l, c)) <= 0):
        raise ValueError("non-positive OHLC value")
    return times, values


def _check_funding(rows: list[dict[str, str]], month: str) -> tuple[np.ndarray, np.ndarray]:
    times = np.asarray([int(row["calc_time"]) for row in rows], dtype=np.int64)
    rates = np.asarray([float(row["last_funding_rate"]) for row in rows], dtype=float)
    intervals = np.asarray([int(row["funding_interval_hours"]) for row in rows], dtype=np.int64)
    if not len(times) or len(np.unique(times)) != len(times) or np.any(np.diff(times) <= 0):
        raise ValueError("funding timestamps are empty, duplicate, or unordered")
    if np.any(intervals <= 0) or not np.all(np.isfinite(rates)):
        raise ValueError("funding intervals/rates are invalid")
    if any(not any(abs(int(right - left) - int(hours) * 3_600_000) <= 1000
                    for hours in (intervals[i], intervals[i + 1]))
           for i, (left, right) in enumerate(zip(times, times[1:]))):
        raise ValueError("funding timestamps disagree with adjacent declared intervals")
    year, mon = map(int, month.split("-"))
    start = int(datetime(year, mon, 1, tzinfo=timezone.utc).timestamp() * 1000)
    next_year, next_mon = ((year + 1, 1) if mon == 12 else (year, mon + 1))
    end = int(datetime(next_year, next_mon, 1, tzinfo=timezone.utc).timestamp() * 1000)
    if times[0] < start or times[-1] >= end:
        raise ValueError("funding timestamp outside its UTC month")
    return times, rates


def preflight(audit_path: Path, coverage_path: Path, recovery_manifest: Path,
              root: Path) -> dict:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    full_symbols = coverage.get("cohorts_by_exact_run", {}).get(COHORT_KEY)
    if not isinstance(full_symbols, list) or len(full_symbols) != 36:
        raise ValueError("frozen 36-symbol cohort unavailable")
    selected = set(full_symbols)
    archive_rows = [row for row in audit.get("archive_rows", [])
                    if row.get("symbol") in selected and row.get("month") in INPUT_MONTHS]
    expected_rows = len(full_symbols) * len(INPUT_MONTHS) * 3
    if len(archive_rows) != expected_rows:
        raise ValueError(f"archive audit row count {len(archive_rows)} != {expected_rows}")
    hash_result = verify_archives({"archive_rows": archive_rows}, root)
    if hash_result["status"] != "PASS":
        raise ValueError(f"archive hash audit failed: {hash_result}")
    row_map = {(r["symbol"], r["month"], r["kind"]): r for r in archive_rows}
    recovery = [json.loads(line) for line in recovery_manifest.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    recovery_map = {(r.get("symbol"), r.get("date")): r for r in recovery}
    recovery_checks = 0
    recovered_times: dict[str, set[int]] = {}
    for symbol in sorted(selected):
        rec = recovery_map.get((symbol, "2026-06-29"))
        path = _daily_mark_path(root, symbol, "2026-06-29")
        if not rec or rec.get("status") != "recovered" or _sha256(path) != rec.get("sha256"):
            raise ValueError(f"missing or mismatched mark recovery archive: {symbol}")
        rows = _read_zip_csv(path)
        day_times, _ = _validate_ohlc(rows, "open_time")
        times = set(map(int, day_times))
        expected = set(range(1782691200000, 1782777600000, HOUR_MS))
        if len(rows) != 24 or times != expected or int(rec.get("rows", -1)) != 24:
            raise ValueError(f"mark recovery does not contain exact UTC day: {symbol}")
        recovered_times[symbol] = times
        recovery_checks += 1

    monthly_issues = []
    funding_issues = []
    loaded_hours = 0
    for symbol in sorted(selected):
        for month in INPUT_MONTHS:
            kl = _read_zip_csv(_archive_path(root, "klines_1h", symbol, month))
            kt, kv = _validate_ohlc(kl, "open_time")
            expected = _month_grid(month)
            if not np.array_equal(kt, expected):
                raise ValueError(f"contract kline month grid mismatch: {symbol} {month}")
            mr = _read_zip_csv(_archive_path(root, "mark_price_1h", symbol, month))
            mt, _ = _validate_ohlc(mr, "open_time", require_contiguous=False)
            if month == "2026-06":
                mt = np.sort(np.concatenate([mt, np.fromiter(recovered_times[symbol], dtype=np.int64)]))
            if not np.array_equal(mt, kt):
                monthly_issues.append({"symbol": symbol, "month": month,
                                       "issue": "mark rows do not exactly match klines after recovery overlay"})
            loaded_hours += len(kt)
            fr = _read_zip_csv(_archive_path(root, "funding", symbol, month))
            try:
                _check_funding(fr, month)
            except ValueError as exc:
                funding_issues.append({"symbol": symbol, "month": month, "issue": str(exc)})
    expected_funding_issues = [{"symbol": "IMXUSDT", "month": "2026-06",
                                "issue": "funding timestamps disagree with adjacent declared intervals"}]
    if monthly_issues or funding_issues != expected_funding_issues:
        raise ValueError(f"unexpected monthly/funding data issues: mark={monthly_issues[:3]}, funding={funding_issues}")
    prereg_hash = _sha256(PREREG)
    source_fingerprint = _digest_rows(sorted(
        [{"kind": r["kind"], "symbol": r["symbol"], "month": r["month"], "sha256": r["sha256"]}
         for r in archive_rows], key=lambda x: (x["kind"], x["symbol"], x["month"])))
    recovery_fingerprint = _digest_rows(sorted(
        [{"symbol": symbol, "date": "2026-06-29", "sha256": recovery_map[(symbol, "2026-06-29")]["sha256"]}
         for symbol in selected], key=lambda x: x["symbol"]))
    return {
        "status": "PASS", "symbol_count_input": len(full_symbols),
        "symbol_count_scored": len(full_symbols) - len(SYMBOLS_EXCLUDED),
        "symbols": sorted(full_symbols), "excluded_symbols": sorted(SYMBOLS_EXCLUDED),
        "input_months": [INPUT_MONTHS[0], INPUT_MONTHS[-1]],
        "archive_hash_audit": hash_result, "archive_fingerprint_sha256": source_fingerprint,
        "archive_rows": len(archive_rows), "recovery_checks": recovery_checks,
        "recovery_fingerprint_sha256": recovery_fingerprint,
        "hourly_contract_rows_checked": loaded_hours,
        "mark_gaps_after_read_only_overlay": 0,
        "funding_integrity_exclusions": funding_issues,
        "audit_metadata_sha256": _sha256(audit_path),
        "coverage_metadata_sha256": _sha256(coverage_path),
        "recovery_manifest_sha256": _sha256(recovery_manifest),
        "preregistration_sha256": prereg_hash,
        "limitations": ["manifest hash equality is not proof of exchange-source truth",
                        "price archive validation does not establish executable fills",
                        "spread/slippage are unmeasured; selected universe has survivorship risk"],
    }


def _load_symbol(root: Path, symbol: str, months: tuple[str, ...]) -> dict:
    candles: list[dict[str, float | int]] = []
    funding_times: list[int] = []
    funding_rates: list[float] = []
    for month in months:
        for row in _read_zip_csv(_archive_path(root, "klines_1h", symbol, month)):
            candles.append({"t": int(row["open_time"]), "o": float(row["open"]),
                            "h": float(row["high"]), "l": float(row["low"]),
                            "c": float(row["close"])})
        for row in _read_zip_csv(_archive_path(root, "funding", symbol, month)):
            funding_times.append(int(row["calc_time"]))
            funding_rates.append(float(row["last_funding_rate"]))
    candles.sort(key=lambda x: int(x["t"]))
    times = np.asarray([int(r["t"]) for r in candles], dtype=np.int64)
    if not len(times) or np.any(np.diff(times) != HOUR_MS):
        raise ValueError(f"cross-month kline sequence has gap/duplicate: {symbol}")
    arrays = {key: np.asarray([float(r[key]) for r in candles], dtype=float)
              for key in ("o", "h", "l", "c")}
    ft = np.asarray(funding_times, dtype=np.int64)
    fr = np.asarray(funding_rates, dtype=float)
    order = np.argsort(ft)
    ft, fr = ft[order], fr[order]
    if len(np.unique(ft)) != len(ft):
        raise ValueError(f"duplicate funding timestamp across months: {symbol}")
    return {"times": times, **arrays, "funding_times": ft, "funding_rates": fr}


def _utc_slot_ids(times: np.ndarray) -> np.ndarray:
    dt = pd.to_datetime(times, unit="ms", utc=True)
    return (dt.dayofweek.to_numpy(dtype=np.int64) * 24 + dt.hour.to_numpy(dtype=np.int64))


def _calendar_sides(open_: np.ndarray, close: np.ndarray) -> np.ndarray:
    """At each bar open, use exactly 52 earlier same-weekday/hour close signs."""
    n = len(open_)
    side = np.zeros(n, dtype=np.int8)
    signs = np.sign(close / open_ - 1.0).astype(np.int8)
    lags = 168 * np.arange(1, LOOKBACK_OCCURRENCES + 1, dtype=np.int64)
    for i in range(LOOKBACK_BARS, n):
        prior = signs[i - lags]
        total = int(prior.sum())
        side[i] = 1 if total > 0 else (-1 if total < 0 else 0)
    return side


def _atr14_prior(high: np.ndarray, low: np.ndarray, close: np.ndarray, index: int) -> float:
    if index < ATR_BARS + 1:
        return math.nan
    prev = close[index - ATR_BARS - 1:index - 1]
    tr = np.maximum.reduce((high[index - ATR_BARS:index] - low[index - ATR_BARS:index],
                            np.abs(high[index - ATR_BARS:index] - prev),
                            np.abs(low[index - ATR_BARS:index] - prev)))
    return float(np.mean(tr))


def _path(data: dict, index: int, side: int, risk: float) -> dict:
    """Score barriers on contract-price OHLC; a same-bar double touch is a stop."""
    if side not in (-1, 1) or not math.isfinite(risk) or risk <= 0:
        raise ValueError("invalid side/risk")
    times, opens, highs, lows, closes = (data[k] for k in ("times", "o", "h", "l", "c"))
    if index < 0 or index + HORIZON_BARS > len(times):
        raise ValueError("incomplete four-bar outcome window")
    expected = times[index] + HOUR_MS * np.arange(HORIZON_BARS, dtype=np.int64)
    if not np.array_equal(times[index:index + HORIZON_BARS], expected):
        return {"m2_hit": False, "reason": "DATA_GAP", "exit_index": index + HORIZON_BARS - 1,
                "exit_price": float(closes[min(index + HORIZON_BARS - 1, len(times) - 1)])}
    entry = float(opens[index])
    stop = entry - side * risk
    target = entry + side * risk
    reason, hit, exit_price, exit_index = "TIMEOUT", False, float(closes[index + 3]), index + 3
    for j in range(index, index + HORIZON_BARS):
        if side == 1:
            stop_gap, target_gap = opens[j] <= stop, opens[j] >= target
            stop_hit = stop_gap or lows[j] <= stop
            target_hit = target_gap or highs[j] >= target
        else:
            stop_gap, target_gap = opens[j] >= stop, opens[j] <= target
            stop_hit = stop_gap or highs[j] >= stop
            target_hit = target_gap or lows[j] <= target
        if stop_hit:
            reason, exit_price, exit_index = "STOP", float(opens[j] if stop_gap else stop), j
            break
        if target_hit:
            reason, hit, exit_price, exit_index = "TARGET", True, float(target), j
            break
    # Settlement in earlier bars is fully known. In the barrier-exit bar,
    # charge only a possible payment; do not credit an unorderable receipt.
    entry_ms = int(times[index])
    exit_bar_open = int(times[exit_index])
    exit_bar_close = exit_bar_open + HOUR_MS
    ft = data["funding_times"]
    fr = data["funding_rates"]
    lo = int(np.searchsorted(ft, entry_ms, side="right"))
    hi = int(np.searchsorted(ft, exit_bar_close, side="right"))
    funding_cost = 0.0
    for funding_time, rate in zip(ft[lo:hi], fr[lo:hi]):
        signed_cost = side * float(rate)
        if int(funding_time) <= exit_bar_open or reason == "TIMEOUT":
            funding_cost += signed_cost
        elif signed_cost > 0:
            funding_cost += signed_cost
    gross = side * (exit_price - entry) / entry
    return {"m2_hit": hit, "reason": reason, "exit_index": exit_index,
            "entry_time_ms": entry_ms, "exit_time_ms": exit_bar_close,
            "entry": entry, "stop": stop, "target": target,
            "exit_price": exit_price, "risk_pct": risk / entry,
            "funding_cost": funding_cost, "gross_return": gross,
            "net_base": gross - BASE_FEE_RT - funding_cost,
            "net_stress": gross - STRESS_FEE_RT - funding_cost,
            "m1_hit": (side * (float(closes[index]) - entry) > 0)}


def _simulate_symbol(symbol: str, data: dict, start_ms: int, end_ms: int) -> tuple[list[dict], dict]:
    times = data["times"]
    sides = _calendar_sides(data["o"], data["c"])
    left = int(np.searchsorted(times, start_ms, side="left"))
    right = int(np.searchsorted(times, end_ms, side="left"))
    eligible = raw_forecasts = suppressed = 0
    records = []
    next_allowed = left
    for i in range(max(left, LOOKBACK_BARS + ATR_BARS + 1), min(right, len(times) - HORIZON_BARS + 1)):
        if times[i] + HORIZON_BARS * HOUR_MS > end_ms:
            continue
        atr = _atr14_prior(data["h"], data["l"], data["c"], i)
        if not math.isfinite(atr) or atr <= 0:
            continue
        eligible += 1
        side = int(sides[i])
        if side == 0:
            continue
        raw_forecasts += 1
        if i < next_allowed:
            suppressed += 1
            continue
        out = _path(data, i, side, atr)
        record = {"symbol": symbol, "side": "long" if side == 1 else "short",
                  "signal_time_ms": int(times[i]), "signal_index": i, "atr": atr, **out}
        records.append(record)
        next_allowed = int(out["exit_index"]) + 1
    return records, {"eligible_anchors": eligible, "raw_directional_forecasts": raw_forecasts,
                     "suppressed_open_position": suppressed}


def _wilson(successes: int, count: int) -> list[float | None]:
    if not count:
        return [None, None]
    z = 1.959963984540054
    p = successes / count
    den = 1 + z * z / count
    center = (p + z * z / (2 * count)) / den
    margin = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / den
    return [center - margin, center + margin]


def _nonoverlap_market(records: list[dict]) -> list[dict]:
    result = []
    last_end = -1
    for row in sorted(records, key=lambda x: (x["entry_time_ms"], x["symbol"])):
        if row["entry_time_ms"] <= last_end:
            continue
        result.append(row)
        last_end = row["exit_time_ms"]
    return result


def _bootstrap_weekly(records: list[dict], draws: int = BOOTSTRAP_DRAWS) -> dict:
    if not records:
        return {"draws": draws, "ci95": [None, None], "valid_draws": 0}
    start = min(row["entry_time_ms"] for row in records)
    end = max(row["exit_time_ms"] for row in records)
    week_ms = 7 * 24 * HOUR_MS
    n_weeks = (end - start) // week_ms + 1
    hit = np.zeros(n_weeks, dtype=np.int64)
    count = np.zeros(n_weeks, dtype=np.int64)
    for row in records:
        b = min(n_weeks - 1, (row["entry_time_ms"] - start) // week_ms)
        count[b] += 1
        hit[b] += bool(row["m2_hit"])
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    block = min(2, n_weeks)
    max_start = max(1, n_weeks - block + 1)
    rates = []
    for _ in range(draws):
        ix = []
        while len(ix) < n_weeks:
            s = int(rng.integers(0, max_start))
            ix.extend(range(s, min(s + block, n_weeks)))
        ix = np.asarray(ix[:n_weeks], dtype=np.int64)
        denom = int(count[ix].sum())
        if denom:
            rates.append(float(hit[ix].sum() / denom))
    if not rates:
        return {"draws": draws, "valid_draws": 0, "ci95": [None, None],
                "block_weeks": block, "seed": BOOTSTRAP_SEED}
    return {"draws": draws, "valid_draws": len(rates), "ci95": [float(x) for x in np.quantile(rates, [0.025, 0.975])],
            "block_weeks": block, "seed": BOOTSTRAP_SEED, "prng": "PCG64"}


def _metrics(records: list[dict], opportunities: int, baseline_side: int | None = None) -> dict:
    n = len(records)
    hits = sum(bool(r["m2_hit"]) for r in records)
    reasons: dict[str, int] = {}
    for row in records:
        reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    output = {
        "signals": n, "m2_hits": hits, "m2_rate": hits / n if n else None,
        "m2_wilson_95": _wilson(hits, n),
        "m1_direction_accuracy": sum(bool(r["m1_hit"]) for r in records) / n if n else None,
        "coverage_pct": 100 * n / opportunities if opportunities else 0.0,
        "eligible_anchors": opportunities,
        "symbols": len({r["symbol"] for r in records}),
        "nonoverlap_symbol_events": n,
        "net_mean_base": float(np.mean([r["net_base"] for r in records])) if n else None,
        "net_mean_stress": float(np.mean([r["net_stress"] for r in records])) if n else None,
        "gross_mean": float(np.mean([r["gross_return"] for r in records])) if n else None,
        "funding_cost_mean": float(np.mean([r["funding_cost"] for r in records])) if n else None,
        "exit_reasons": reasons,
        "market_time_nonoverlap_events": len(_nonoverlap_market(records)),
        "weekly_block_bootstrap": _bootstrap_weekly(records),
    }
    if baseline_side is not None and n:
        base = [_path_from_record(r, baseline_side) for r in records]
        base_hits = sum(bool(r["m2_hit"]) for r in base)
        output["frozen_baseline_side"] = "long" if baseline_side == 1 else "short"
        output["frozen_baseline_m2"] = base_hits / n
        output["m2_wilson_lower_above_baseline"] = output["m2_wilson_95"][0] > output["frozen_baseline_m2"]
        output["baseline_net_mean_base"] = float(np.mean([r["net_base"] for r in base]))
        output["baseline_net_mean_stress"] = float(np.mean([r["net_stress"] for r in base]))
    return output


def _path_from_record(record: dict, side: int) -> dict:
    # Caller attaches the full arrays under this private field only in memory.
    data = record["_data"]
    return _path(data, int(record["signal_index"]), side, float(record["atr"]))


def _load_window(root: Path, symbols: list[str], months: tuple[str, ...]) -> dict[str, dict]:
    return {symbol: _load_symbol(root, symbol, months) for symbol in symbols if symbol not in SYMBOLS_EXCLUDED}


def _bounds(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def run_stage(args: argparse.Namespace) -> int:
    out = args.output.resolve()
    audit_result = preflight(args.audit_json, args.coverage_json, args.recovery_manifest, args.archive_root)
    if args.stage == "audit":
        _save_json(out / "preflight.json", audit_result)
        print(json.dumps({"stage": "audit", "status": "PASS", "archive_rows": audit_result["archive_rows"],
                          "archive_fingerprint_sha256": audit_result["archive_fingerprint_sha256"],
                          "recovery_checks": audit_result["recovery_checks"],
                          "funding_integrity_exclusions": audit_result["funding_integrity_exclusions"]}, sort_keys=True))
        return 0

    if not (out / "preflight.json").is_file():
        raise ValueError("run --stage audit first")
    saved_preflight = json.loads((out / "preflight.json").read_text(encoding="utf-8"))
    if saved_preflight["archive_fingerprint_sha256"] != audit_result["archive_fingerprint_sha256"]:
        raise ValueError("current archive fingerprint differs from audited preflight")
    symbols = audit_result["symbols"]
    dev_start, score_start, score_end = map(_bounds, (DEV_START, SCORE_START, SCORE_END))
    months = tuple(m for m in INPUT_MONTHS if m <= "2026-05") if args.stage == "baseline" else INPUT_MONTHS
    loaded = _load_window(args.archive_root, symbols, months)

    if args.stage == "baseline":
        all_records = []
        opportunities = 0
        for symbol, data in loaded.items():
            records, counts = _simulate_symbol(symbol, data, dev_start, score_start)
            opportunities += counts["eligible_anchors"]
            for row in records:
                row["_data"] = data
            all_records.extend(records)
        if not all_records:
            raise ValueError("development produced no candidate entries")
        long_rate = sum(_path_from_record(r, 1)["m2_hit"] for r in all_records) / len(all_records)
        short_rate = sum(_path_from_record(r, -1)["m2_hit"] for r in all_records) / len(all_records)
        baseline_side = 1 if long_rate >= short_rate else -1
        baseline = {
            "status": "FROZEN", "development_interval": [DEV_START, SCORE_START],
            "candidate_development_metrics": _metrics(all_records, opportunities),
            "baseline_development_m2": {"always_long": long_rate, "always_short": short_rate},
            "frozen_baseline_side": "long" if baseline_side == 1 else "short",
            "archive_fingerprint_sha256": audit_result["archive_fingerprint_sha256"],
            "preregistration_sha256": audit_result["preregistration_sha256"],
            "runner_sha256": _sha256(Path(__file__)),
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "note": "Exposed development data; baseline-selection only, not an OOS result.",
        }
        _save_json(out / "baseline.json", baseline)
        print(json.dumps({"stage": "baseline", "status": "FROZEN",
                          "candidate_dev_signals": len(all_records),
                          "always_long_m2": long_rate, "always_short_m2": short_rate,
                          "frozen_baseline": baseline["frozen_baseline_side"]}, sort_keys=True))
        return 0

    baseline_path = out / "baseline.json"
    if not baseline_path.is_file():
        raise ValueError("run --stage baseline and freeze control before score")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline["archive_fingerprint_sha256"] != audit_result["archive_fingerprint_sha256"]:
        raise ValueError("baseline input fingerprint differs")
    if baseline["preregistration_sha256"] != audit_result["preregistration_sha256"]:
        raise ValueError("preregistration changed after baseline freeze")
    side = 1 if baseline["frozen_baseline_side"] == "long" else -1
    records = []
    opportunities = 0
    symbol_counts = {}
    for symbol, data in loaded.items():
        rows, counts = _simulate_symbol(symbol, data, score_start, score_end)
        opportunities += counts["eligible_anchors"]
        symbol_counts[symbol] = counts | {"issued_entries": len(rows)}
        for row in rows:
            row["_data"] = data
        records.extend(rows)
    metrics = _metrics(records, opportunities, side)
    for row in records:
        row.pop("_data", None)
    run = {
        "status": "EXPLORATORY_COMPLETE", "candidate": "UTC weekday-hour prior-52 sign majority",
        "score_interval": [SCORE_START, SCORE_END], "baseline_path": str(baseline_path),
        "baseline_sha256": _sha256(baseline_path), "preregistration_sha256": audit_result["preregistration_sha256"],
        "runner_sha256": _sha256(Path(__file__)), "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "archive_fingerprint_sha256": audit_result["archive_fingerprint_sha256"],
        "full_preflight": audit_result, "metric": metrics, "by_symbol": symbol_counts,
        "core_eligible": False,
        "non_promotion_reasons": ["window was source-audited, not sealed or live-forward",
                                  "spread/slippage unmeasured", "point-in-time universe survivorship unresolved",
                                  "candidate-family multiplicity and independent red-team replay remain"],
    }
    _save_json(out / "summary.json", run)
    ledger_path = out / "event_ledger.csv"
    if ledger_path.exists():
        raise FileExistsError(f"refusing to overwrite {ledger_path}")
    columns = ["symbol", "side", "signal_time_ms", "entry_time_ms", "exit_time_ms", "entry",
               "stop", "target", "exit_price", "m2_hit", "m1_hit", "reason", "gross_return",
               "funding_cost", "net_base", "net_stress"]
    with ledger_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(json.dumps({"stage": "score", "status": "EXPLORATORY_COMPLETE",
                      "signals": metrics["signals"], "m2_hits": metrics["m2_hits"],
                      "m2_rate": metrics["m2_rate"], "coverage_pct": metrics["coverage_pct"],
                      "symbols": metrics["symbols"], "core_eligible": False,
                      "output": str(out)}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("audit", "baseline", "score"), required=True)
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--coverage-json", type=Path, required=True)
    parser.add_argument("--recovery-manifest", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run_stage(args)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, csv.Error) as exc:
        print(json.dumps({"stage": args.stage, "status": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
