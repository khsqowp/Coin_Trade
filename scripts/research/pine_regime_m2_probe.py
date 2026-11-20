"""Deterministic implementation of the preregistered Pine regime M2 screen.

This module contains indicator and path primitives only. It never places orders,
fetches data, edits source archives, or chooses parameters from outcomes.
"""

from __future__ import annotations

import math
import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import zipfile

import numpy as np

HOUR_MS = 3_600_000
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PREREG_SHA256 = "a12d3aa5e34ced5efc96cfc3361019c9920c529669bb9fe00be9b8ae09f84b74"
PINE_BLOB = "7fa6fe76631305448fa3526bef7bcaa8d56a6441"
PINE_SHA256 = "a65022e8abcfc38d82a9a8b31ab9abc75ee929e4e641c584a415c6e6b2e6f98b"
LICENSE_BLOB = "4693362ee10a94d2d8a9a02b55852d2c8f0d4e94"
LICENSE_SHA256 = "a468e9bc5c6a94a69f337a5ef276f065e778cd0170d7a7b8b3b71164a2e29d33"
DEV_START_MS = 1_679_583_600_000  # 2023-03-23 15:00:00 UTC
DEV_END_MS = 1_740_787_200_000    # 2025-03-01 00:00:00 UTC
BASE_FEE = 0.001
STRESS_FEE = 0.003


def _as_float_array(values: Sequence[float], name: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain only finite values")
    return result


def _rolling_extreme(values: np.ndarray, end: int, length: int, fn) -> float:
    # Pine ta.highest/ta.lowest operate on available history during warm-up.
    start = max(0, end - length + 1)
    return float(fn(values[start : end + 1]))


def _mapped(value: float, trend_anchor: float, range_anchor: float) -> float:
    span = trend_anchor - range_anchor
    if span == 0.0:
        return 0.5
    return min(1.0, max(0.0, (value - range_anchor) / span))


def compute_regime(
    high: Sequence[float], low: Sequence[float], close: Sequence[float]
) -> dict[str, np.ndarray]:
    """Reproduce the fixed v1.1.3 ER/FDI/CHOP mapping and label transitions."""
    high = _as_float_array(high, "high")
    low = _as_float_array(low, "low")
    close = _as_float_array(close, "close")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high, low, close lengths differ")
    if np.any(high < low):
        raise ValueError("high must be >= low")

    n = len(close)
    er = np.zeros(n, dtype=np.float64)
    fdi = np.full(n, 1.5, dtype=np.float64)
    chop = np.full(n, 50.0, dtype=np.float64)
    score = np.zeros(n, dtype=np.float64)
    labels = np.empty(n, dtype=object)
    to_trend = np.zeros(n, dtype=bool)
    tr = np.empty(n, dtype=np.float64)

    for i in range(n):
        tr[i] = high[i] - low[i] if i == 0 else max(
            high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])
        )

        # math.sum(source, 20) is unavailable until 20 non-na samples exist.
        if i >= 20:
            denominator = float(np.abs(np.diff(close[i - 20 : i + 1])).sum())
            er[i] = abs(close[i] - close[i - 20]) / denominator if denominator > 0 else 0.0

        half = 15
        r1 = (_rolling_extreme(high, i, half, np.max) -
              _rolling_extreme(low, i, half, np.min)) / half
        prior_end = i - half
        if prior_end >= 0:
            r2 = (_rolling_extreme(high, prior_end, half, np.max) -
                  _rolling_extreme(low, prior_end, half, np.min)) / half
            r3 = (_rolling_extreme(high, i, 30, np.max) -
                  _rolling_extreme(low, i, 30, np.min)) / 30
            if r1 + r2 > 0.0 and r3 > 0.0:
                candidate = (math.log(r1 + r2) - math.log(r3)) / math.log(2.0)
                fdi[i] = min(2.0, max(1.0, candidate))

        # First CHOP value requires 14 complete TR samples, as math.sum does.
        if i >= 13:
            sum_tr = float(tr[i - 13 : i + 1].sum())
            channel = (_rolling_extreme(high, i, 14, np.max) -
                       _rolling_extreme(low, i, 14, np.min))
            if channel > 0.0 and sum_tr > 0.0:
                chop[i] = min(100.0, max(
                    0.0, 100.0 * math.log10(sum_tr / channel) / math.log10(14.0)
                ))

        score[i] = (
            _mapped(er[i], 0.55, 0.20)
            + _mapped(fdi[i], 1.35, 1.55)
            + _mapped(chop[i], 38.2, 61.8)
        ) / 3.0

    state = 0
    previous_label = None
    for i in range(n):
        if score[i] >= 0.62:
            state = 1
        elif score[i] <= 0.38:
            state = -1
        elif state == 0:
            state = 1 if score[i] >= 0.5 else -1

        chaos = chop[i] >= 65.0 and er[i] <= 0.18 and fdi[i] >= 1.55
        label = "Chaos" if chaos else ("Trend" if state == 1 else "Range")
        labels[i] = label
        # Pine's `regimeLabel[1] != "Trend"` is na on the first bar, so its
        # boolean condition does not fire there.
        to_trend[i] = i > 0 and label == "Trend" and previous_label != "Trend"
        previous_label = label

    return {"er": er, "fdi": fdi, "chop": chop, "score": score,
            "labels": labels, "to_trend": to_trend}


def atr_wilder(
    high: Sequence[float], low: Sequence[float], close: Sequence[float], period: int = 14
) -> np.ndarray:
    """ATR with first-period simple-average seed, then Wilder recursion."""
    if period < 1:
        raise ValueError("period must be positive")
    high = _as_float_array(high, "high")
    low = _as_float_array(low, "low")
    close = _as_float_array(close, "close")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high, low, close lengths differ")
    tr = np.empty(len(close), dtype=np.float64)
    for i in range(len(close)):
        tr[i] = high[i] - low[i] if i == 0 else max(
            high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])
        )
    result = np.full(len(close), np.nan, dtype=np.float64)
    if len(close) >= period:
        result[period - 1] = float(tr[:period].mean())
        for i in range(period, len(close)):
            result[i] = (result[i - 1] * (period - 1) + tr[i]) / period
    return result


def evaluate_m2_path(
    side: str,
    entry: float,
    risk: float,
    bars: Sequence[Mapping[str, float]],
    funding_times: Sequence[int],
    funding_rates: Sequence[float],
    fee_rate: float = 0.001,
    horizon: int = 20,
) -> dict[str, float | bool | str | int]:
    """Evaluate a fixed 1R stop/2R target with path-first barrier semantics."""
    side = side.upper()
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")
    if not all(math.isfinite(x) for x in (entry, risk, fee_rate)) or entry <= 0 or risk <= 0:
        raise ValueError("entry/risk must be positive and fee finite")
    if len(funding_times) != len(funding_rates):
        raise ValueError("funding timestamp/rate lengths differ")
    if any(funding_times[i] >= funding_times[i + 1] for i in range(len(funding_times) - 1)):
        raise ValueError("funding timestamps must be strictly increasing")
    if any(not math.isfinite(float(rate)) for rate in funding_rates):
        raise ValueError("funding rates must be finite")
    sign = 1 if side == "LONG" else -1
    stop = entry - sign * risk
    target = entry + sign * 2.0 * risk
    if len(bars) < horizon:
        return {"reason": "TRUNCATED", "m2_hit": False, "exit_price": math.nan,
                "funding_cost_fraction": 0.0, "actual_signed_funding_rate_sum": 0.0,
                "fee_fraction": fee_rate, "exit_index": -1}

    reason, exit_price, exit_index = "TIMEOUT", float(bars[horizon - 1]["c"]), horizon - 1
    for i, bar in enumerate(bars[:horizon]):
        o, h, l = (float(bar[k]) for k in ("o", "h", "l"))
        if not all(math.isfinite(x) for x in (o, h, l, float(bar["c"]))):
            raise ValueError("bar prices must be finite")
        if i and int(bar["open_time_ms"]) != int(bars[i - 1]["open_time_ms"]) + HOUR_MS:
            reason, exit_price, exit_index = "DATA_GAP", math.nan, i
            break
        stop_touched = l <= stop if sign == 1 else h >= stop
        target_touched = h >= target if sign == 1 else l <= target
        if stop_touched:
            reason = "STOP_GAP" if (o < stop if sign == 1 else o > stop) else "STOP"
            exit_price = o if reason == "STOP_GAP" else stop
            exit_index = i
            break
        if target_touched:
            reason, exit_price, exit_index = "TARGET", target, i
            break

    m2_hit = reason == "TARGET"
    funding_cost = 0.0
    signed_cost = 0.0
    if reason != "DATA_GAP":
        entry_time = int(bars[0]["open_time_ms"])
        exit_close = int(bars[exit_index]["open_time_ms"]) + HOUR_MS
        exit_bar_open = int(bars[exit_index]["open_time_ms"])
        for timestamp, rate in zip(funding_times, funding_rates):
            timestamp, rate = int(timestamp), float(rate)
            if entry_time < timestamp <= exit_close:
                cost = sign * rate
                # In the exit candle the chronology is ambiguous: charge costs,
                # discard credits, as frozen in the preregistration.
                if timestamp >= exit_bar_open:
                    cost = max(cost, 0.0)
                funding_cost += cost
                signed_cost += cost
    return {"reason": reason, "m2_hit": m2_hit, "exit_price": exit_price,
            "funding_cost_fraction": funding_cost,
            "actual_signed_funding_rate_sum": signed_cost,
            "fee_fraction": fee_rate, "exit_index": exit_index,
            "net_return": (sign * (exit_price - entry) / entry - fee_rate - funding_cost)
            if math.isfinite(exit_price) else math.nan,
            "net_R": (sign * (exit_price - entry) / entry - fee_rate - funding_cost) / (risk / entry)
            if math.isfinite(exit_price) else math.nan}


def build_nonoverlap_clusters(
    events: Iterable[Mapping[str, object]], horizon_hours: int = 20
) -> list[dict[str, object]]:
    """Greedy fixed-time clusters; selection is independent of realized outcomes."""
    if horizon_hours <= 0:
        raise ValueError("horizon_hours must be positive")
    grouped: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for event in events:
        grouped[int(event["entry_open_ms"])].append(event)
    gap_ms = horizon_hours * HOUR_MS
    selected: list[dict[str, object]] = []
    last = None
    for timestamp in sorted(grouped):
        if last is None or timestamp - last >= gap_ms:
            selected.append({"entry_open_ms": timestamp, "events": grouped[timestamp]})
            last = timestamp
    return selected


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def _month_sequence(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    last_year, last_month = map(int, end.split("-"))
    result = []
    while (year, month) <= (last_year, last_month):
        result.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def _read_zip(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"corrupt archive member: {path.name}:{bad}")
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {path}")
        with archive.open(members[0]) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            first = text.readline()
            columns = ["open_time", "open", "high", "low", "close", "volume",
                       "close_time", "quote_volume", "count", "taker_buy_volume",
                       "taker_buy_quote_volume", "ignore"]
            if first[:1].isdigit():
                return list(csv.DictReader([first, *text], fieldnames=columns))
            return list(csv.DictReader([first, *text]))


def _wilson(successes: int, count: int) -> list[float | None]:
    if not count:
        return [None, None]
    z, p = 1.959963984540054, successes / count
    denominator = 1 + z * z / count
    center = (p + z * z / (2 * count)) / denominator
    margin = z * math.sqrt(p * (1 - p) / count + z * z / (4 * count * count)) / denominator
    return [center - margin, center + margin]


def _verify_pins(prereg: Path) -> dict:
    source = ROOT / "docs/research/inventory/sources/casoon_regime_classifier_v1.1.3.pine"
    license_path = ROOT / "docs/research/inventory/sources/CASOON_PINE_SCRIPTS_LICENSE.txt"
    actual = {
        "prereg_sha256": _sha256(prereg),
        "source_sha256": _sha256(source), "source_git_blob": _git_blob(source),
        "license_sha256": _sha256(license_path), "license_git_blob": _git_blob(license_path),
    }
    expected = {"prereg_sha256": PREREG_SHA256, "source_sha256": PINE_SHA256,
                "source_git_blob": PINE_BLOB, "license_sha256": LICENSE_SHA256,
                "license_git_blob": LICENSE_BLOB}
    if actual != expected:
        raise ValueError(f"frozen source/prereg pin mismatch: {actual}")
    return actual


def _load_months(root: Path, symbol: str, kline_months: Sequence[str],
                 funding_months: Sequence[str]) -> tuple[list[dict], list[int], list[float]]:
    bars, funding = [], []
    for month in kline_months:
        rows = _read_zip(root / "klines_1h" / symbol / f"{symbol}-1h-{month}.zip")
        for row in rows:
            bar = {"open_time_ms": int(row["open_time"]), "o": float(row["open"]),
                   "h": float(row["high"]), "l": float(row["low"]), "c": float(row["close"])}
            if not all(math.isfinite(bar[key]) for key in ("o", "h", "l", "c")):
                raise ValueError(f"non-finite OHLC: {symbol} {month}")
            if bar["h"] < max(bar["o"], bar["c"]) or bar["l"] > min(bar["o"], bar["c"]) or bar["h"] < bar["l"]:
                raise ValueError(f"invalid OHLC: {symbol} {month} {bar['open_time_ms']}")
            bars.append(bar)
    for month in funding_months:
        rows = _read_zip(root / "funding" / symbol / f"{symbol}-fundingRate-{month}.zip")
        for row in rows:
            stamp, rate = int(row["calc_time"]), float(row["last_funding_rate"])
            if not math.isfinite(rate):
                raise ValueError(f"non-finite funding: {symbol} {month}")
            funding.append((stamp, rate))
    bars.sort(key=lambda row: row["open_time_ms"])
    funding.sort()
    gaps = [i for i in range(1, len(bars))
            if bars[i]["open_time_ms"] - bars[i-1]["open_time_ms"] != HOUR_MS]
    pre_score_gaps = [i for i in gaps if bars[i]["open_time_ms"] < DEV_START_MS]
    post_start_gaps = [i for i in gaps if bars[i]["open_time_ms"] >= DEV_START_MS]
    if post_start_gaps:
        raise ValueError(f"non-contiguous scoring OHLC: {symbol} at {bars[post_start_gaps[0]]['open_time_ms']}")
    # Old monthly archives can contain pre-listing/discontinuous history. Start
    # Pine state at the first bar of the final contiguous suffix ending at the
    # fixed scoring window, rather than bridging a missing historical interval.
    if pre_score_gaps:
        bars = bars[pre_score_gaps[-1]:]
    if any(bars[i]["open_time_ms"] - bars[i-1]["open_time_ms"] != HOUR_MS
           for i in range(1, len(bars))):
        raise ValueError(f"warm-up suffix remains non-contiguous: {symbol}")
    if any(funding[i][0] == funding[i-1][0] for i in range(1, len(funding))):
        raise ValueError(f"duplicate funding timestamp: {symbol}")
    return bars, [item[0] for item in funding], [item[1] for item in funding]


def _causal_check(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict:
    cut = len(close) // 2
    prefix = compute_regime(high[:cut], low[:cut], close[:cut])
    full = compute_regime(high, low, close)
    mutated_high, mutated_low, mutated_close = high.copy(), low.copy(), close.copy()
    mutated_high[cut:] += 777.0
    mutated_low[cut:] -= 333.0
    mutated_close[cut:] *= 1.37
    mutated = compute_regime(mutated_high, mutated_low, mutated_close)
    for key in ("er", "fdi", "chop", "score", "labels", "to_trend"):
        equal_nan = key not in {"labels", "to_trend"}
        if not np.array_equal(prefix[key], full[key][:cut], equal_nan=equal_nan):
            raise ValueError(f"prefix causality failed: {key}")
        if not np.array_equal(prefix[key], mutated[key][:cut], equal_nan=equal_nan):
            raise ValueError(f"future mutation causality failed: {key}")
    return {"status": "PASS", "bars": len(close), "cut_index": cut}


def run_development(archive_root: Path, coverage_path: Path, audit_path: Path,
                    funding_audit_path: Path, prereg_path: Path, output_dir: Path) -> dict:
    """Run only the frozen exposed-history diagnostic; never qualifies a Core."""
    from scripts.research.audit_usdm_timestamps import audit_cohort
    from scripts.research.verify_usdm_archives import verify

    if output_dir.exists():
        raise FileExistsError(f"output path already exists; refusing overwrite: {output_dir}")
    pins = _verify_pins(prereg_path)
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    funding_audit = json.loads(funding_audit_path.read_text(encoding="utf-8"))
    if funding_audit.get("status") != "PASS" or funding_audit.get("passed") != funding_audit.get("sample_count"):
        raise ValueError("funding API timestamp/rate cross-check did not pass")
    cohort = "2023-03..2026-05"
    symbols = coverage.get("cohorts_by_exact_run", {}).get(cohort)
    if not isinstance(symbols, list) or len(symbols) != 36:
        raise ValueError("fixed 36-symbol cohort mismatch")
    timestamp_audit = audit_cohort(audit, coverage, archive_root, cohort)
    if timestamp_audit["status"] != "PASS":
        raise ValueError(f"fixed cohort timestamp audit failed: {timestamp_audit}")

    row_map = {(r.get("symbol"), r.get("month"), r.get("kind")): r
               for r in audit.get("archive_rows", []) if isinstance(r, dict)}
    scoring_months = _month_sequence("2023-03", "2025-02")
    selected_rows, symbol_months = [], {}
    for symbol in symbols:
        # Use the longest contiguous *verified-manifest-listed* kline suffix
        # ending in February 2023; symbols with no archive start at scoring start.
        warm = []
        for month in reversed(_month_sequence("2021-12", "2023-02")):
            if (symbol, month, "klines_1h") not in row_map:
                if warm:
                    break
                continue
            warm.append(month)
        warm.reverse()
        kline_months = warm + scoring_months
        symbol_months[symbol] = {"warmup_start": warm[0] if warm else "2023-03",
                                 "warmup_months": warm, "scoring_months": scoring_months}
        for month in kline_months:
            row = row_map.get((symbol, month, "klines_1h"))
            if row is None:
                raise ValueError(f"missing kline manifest entry: {symbol} {month}")
            selected_rows.append(row)
        for month in scoring_months:
            row = row_map.get((symbol, month, "funding"))
            if row is None:
                raise ValueError(f"missing funding manifest entry: {symbol} {month}")
            selected_rows.append(row)
    hash_audit = verify({"archive_rows": selected_rows}, archive_root)
    if hash_audit["status"] != "PASS":
        raise ValueError(f"selected archive checksum verification failed: {hash_audit}")
    fingerprint = hashlib.sha256("\n".join(
        f"{r['symbol']}|{r['month']}|{r['kind']}|{r['sha256']}"
        for r in sorted(selected_rows, key=lambda x: (x["symbol"], x["month"], x["kind"]))
    ).encode()).hexdigest()

    ledger, attempted, suppressed, no_direction = [], 0, 0, 0
    eligible_hours = 0
    per_symbol = {}
    causal = {}
    for symbol in symbols:
        spec = symbol_months[symbol]
        bars, funding_times, funding_rates = _load_months(
            archive_root, symbol, spec["warmup_months"] + scoring_months, scoring_months
        )
        spec["warmup_start"] = datetime.fromtimestamp(
            bars[0]["open_time_ms"] / 1000, timezone.utc
        ).isoformat().replace("+00:00", "Z")
        times = np.asarray([row["open_time_ms"] for row in bars], dtype=np.int64)
        op = np.asarray([row["o"] for row in bars], dtype=float)
        hi = np.asarray([row["h"] for row in bars], dtype=float)
        lo = np.asarray([row["l"] for row in bars], dtype=float)
        cl = np.asarray([row["c"] for row in bars], dtype=float)
        causal[symbol] = _causal_check(hi, lo, cl)
        regime = compute_regime(hi, lo, cl)
        atr = atr_wilder(hi, lo, cl, 14)
        for anchor_idx, anchor_time in enumerate(times):
            if not (DEV_START_MS <= int(anchor_time) + HOUR_MS < DEV_END_MS):
                continue
            last_bar = anchor_idx + 20
            if last_bar < len(times) and int(times[last_bar]) + HOUR_MS < DEV_END_MS:
                eligible_hours += 1
        issued = []
        last_exit_signal_index = -1
        symbol_counts = defaultdict(int)
        symbol_eligible_hours = sum(
            DEV_START_MS <= int(times[i]) + HOUR_MS < DEV_END_MS
            and i + 20 < len(times)
            and int(times[i + 20]) + HOUR_MS < DEV_END_MS
            for i in range(len(times))
        )
        for signal_idx in np.flatnonzero(regime["to_trend"]):
            signal_time = int(times[signal_idx]) + HOUR_MS
            if not (DEV_START_MS <= signal_time < DEV_END_MS):
                continue
            attempted += 1
            symbol_counts["attempted_to_trend"] += 1
            body = cl[signal_idx] - op[signal_idx]
            if body == 0:
                no_direction += 1
                symbol_counts["no_direction"] += 1
                continue
            if signal_idx < last_exit_signal_index:
                suppressed += 1
                symbol_counts["suppressed_in_position"] += 1
                continue
            entry_idx = signal_idx + 1
            if entry_idx >= len(bars) or times[entry_idx] >= DEV_END_MS:
                symbol_counts["missing_entry_bar"] += 1
                continue
            if not math.isfinite(float(atr[signal_idx])) or atr[signal_idx] <= 0:
                symbol_counts["invalid_atr"] += 1
                continue
            end_idx = entry_idx + 20
            if end_idx > len(bars) or int(times[end_idx - 1]) + HOUR_MS >= DEV_END_MS:
                symbol_counts["truncated_at_split"] += 1
                continue
            side = "LONG" if body > 0 else "SHORT"
            entry, risk = float(op[entry_idx]), float(atr[signal_idx])
            path = bars[entry_idx:end_idx]
            candidate = evaluate_m2_path(side, entry, risk, path, funding_times, funding_rates, BASE_FEE)
            stress = evaluate_m2_path(side, entry, risk, path, funding_times, funding_rates, STRESS_FEE)
            baseline_long = evaluate_m2_path("LONG", entry, risk, path, funding_times,
                                             funding_rates, BASE_FEE)
            baseline_short = evaluate_m2_path("SHORT", entry, risk, path, funding_times,
                                              funding_rates, BASE_FEE)
            if candidate["reason"] == "DATA_GAP":
                symbol_counts["data_gap"] += 1
            symbol_counts["issued"] += 1
            if candidate["reason"] not in {"DATA_GAP", "TRUNCATED"}:
                last_exit_signal_index = entry_idx + int(candidate["exit_index"])
            endpoint_close = float(path[-1]["c"])
            endpoint_direction = 1 if endpoint_close > entry else -1 if endpoint_close < entry else 0
            m1_hit = endpoint_direction == (1 if side == "LONG" else -1)
            record = {"symbol": symbol, "signal_close_ms": signal_time,
                      "entry_open_ms": int(times[entry_idx]), "side": side,
                      "signal_close": float(cl[signal_idx]), "entry": entry, "risk": risk,
                      "stop": entry - risk if side == "LONG" else entry + risk,
                      "target": entry + 2 * risk if side == "LONG" else entry - 2 * risk,
                      "reason": candidate["reason"], "exit_price": candidate["exit_price"],
                      "m2_hit": candidate["m2_hit"], "m1_hit": m1_hit,
                      "net_base": candidate["net_return"], "net_stress": stress["net_return"],
                      "net_r_base": candidate["net_R"], "net_r_stress": stress["net_R"],
                      "funding_cost_fraction": candidate["funding_cost_fraction"],
                      "baseline_long_m2": baseline_long["m2_hit"],
                      "baseline_short_m2": baseline_short["m2_hit"]}
            issued.append(record)
            ledger.append(record)
        per_symbol[symbol] = {**dict(symbol_counts),
                              "eligible_symbol_hours": int(symbol_eligible_hours),
                              "issued_signal_rate": symbol_counts["issued"] / symbol_eligible_hours
                              if symbol_eligible_hours else None,
                              "warmup_start": spec["warmup_start"]}

    clusters = build_nonoverlap_clusters(ledger, 20)
    selected_times = {int(cluster["entry_open_ms"]) for cluster in clusters}
    selected = [row for row in ledger if int(row["entry_open_ms"]) in selected_times]
    def arm_stats(rows: Sequence[Mapping[str, object]]) -> dict:
        n = len(rows)
        hits = sum(bool(row["m2_hit"]) for row in rows)
        evaluable = [row for row in rows if row["reason"] != "DATA_GAP"]
        return {"n": n, "m2_hits": hits, "m2_rate": hits / n if n else None,
                "evaluable_n": len(evaluable),
                "m2_wilson_95": _wilson(hits, n),
                "m1_rate": sum(bool(row["m1_hit"]) for row in rows) / n if n else None,
                "net_base_mean_return_fraction": float(np.mean([row["net_base"] for row in evaluable])) if evaluable else None,
                "net_stress_mean_return_fraction": float(np.mean([row["net_stress"] for row in evaluable])) if evaluable else None,
                "net_base_mean_R": float(np.mean([row["net_r_base"] for row in evaluable])) if evaluable else None,
                "net_stress_mean_R": float(np.mean([row["net_r_stress"] for row in evaluable])) if evaluable else None}
    exclusion_counts = {name: sum(int(record.get(name, 0)) for record in per_symbol.values())
                        for name in ("no_direction", "invalid_atr", "suppressed_in_position",
                                     "missing_entry_bar", "truncated_at_split", "data_gap")}
    strongest_baseline = max(summary_rate for summary_rate in (
        sum(bool(row["baseline_long_m2"]) for row in ledger) / len(ledger) if ledger else 0.0,
        sum(bool(row["baseline_short_m2"]) for row in ledger) / len(ledger) if ledger else 0.0
    ))
    candidate_lower = _wilson(sum(bool(row["m2_hit"]) for row in ledger), len(ledger))[0]
    core_gate_failures = []
    if arm_stats(ledger)["m2_rate"] is None or arm_stats(ledger)["m2_rate"] < 0.80:
        core_gate_failures.append("all_issued_M2_below_80_percent")
    if len(clusters) < 200:
        core_gate_failures.append("nonoverlap_timestamp_clusters_below_200")
    if len({row["symbol"] for row in selected}) < 20:
        core_gate_failures.append("nonoverlap_symbols_below_20")
    if eligible_hours == 0 or len(ledger) / eligible_hours < 0.10:
        core_gate_failures.append("coverage_below_10_percent")
    if arm_stats(ledger)["net_base_mean_R"] is None or arm_stats(ledger)["net_base_mean_R"] <= 0:
        core_gate_failures.append("base_net_expectancy_not_positive")
    if arm_stats(ledger)["net_stress_mean_R"] is None or arm_stats(ledger)["net_stress_mean_R"] <= 0:
        core_gate_failures.append("stress_net_expectancy_not_positive")
    if candidate_lower is None or candidate_lower <= strongest_baseline:
        core_gate_failures.append("M2_Wilson_lower_not_above_strongest_development_baseline")
    summary = {"status": "REJECTED_DEVELOPMENT_SCREEN", "core_eligible": False,
               "attempted_to_trend": attempted, "no_direction": no_direction,
               "suppressed_in_position": suppressed, "issued_executable": len(ledger),
               "exclusion_counts": exclusion_counts,
               "truncated_or_invalid_attempts_by_symbol": per_symbol,
               "all_issued": arm_stats(ledger), "nonoverlap_20h": arm_stats(selected),
               "nonoverlap_timestamp_clusters": len(clusters),
               "nonoverlap_distinct_symbols": len({row["symbol"] for row in selected}),
               "baseline_long_all_issued": sum(bool(row["baseline_long_m2"]) for row in ledger) / len(ledger) if ledger else None,
               "baseline_short_all_issued": sum(bool(row["baseline_short_m2"]) for row in ledger) / len(ledger) if ledger else None,
               "strongest_development_baseline_m2": strongest_baseline,
               "core_gate_failures": core_gate_failures,
               "mean_funding_cost_fraction": float(np.mean([row["funding_cost_fraction"] for row in ledger])) if ledger else None,
               "data_gaps": sum(row["reason"] == "DATA_GAP" for row in ledger),
               "coverage_denominator_complete_symbol_hours": eligible_hours,
               "coverage": len(ledger) / eligible_hours if eligible_hours else None,
               "symbols": len(symbols), "data_fingerprint_sha256": fingerprint,
               "preregistration_sha256": pins["prereg_sha256"], "source_pins": pins,
               "archive_hash_audit": {k: v for k, v in hash_audit.items() if k != "mismatch_refs"},
               "timestamp_audit": timestamp_audit, "causal_checks": causal,
               "funding_api_crosscheck": {k: funding_audit[k] for k in ("status", "sample_count", "passed")}}

    output_dir.mkdir(parents=True)
    code_path = Path(__file__).resolve()
    summary["code_sha256"] = _sha256(code_path)
    summary["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    summary["command"] = " ".join(sys.argv)
    summary["created_utc"] = datetime.now(timezone.utc).isoformat()
    ledger_path = output_dir / "signals.jsonl"
    ledger_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                                    for row in ledger), encoding="utf-8")
    summary["ledger_sha256"] = _sha256(ledger_path)
    from scripts.research.audit_pine_regime_ledger import audit as audit_ledger
    independent_audit = audit_ledger(archive_root, ledger_path, sample_size=100)
    summary["independent_sample_audit"] = {
        key: value for key, value in independent_audit.items() if key != "sample"
    }
    (output_dir / "independent_sample_audit.json").write_text(
        json.dumps(independent_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = ["# Pine Regime M2 development diagnostic", "",
              "Status: **REJECTED_DEVELOPMENT_SCREEN — not Core-eligible**", "",
              f"- Fixed candidate issued signals: {len(ledger)}; attempted transitions: {attempted}.",
              f"- M2 target-first rate: {summary['all_issued']['m2_rate']}; Wilson 95% descriptive interval: {summary['all_issued']['m2_wilson_95']}.",
              f"- M1 endpoint direction rate: {summary['all_issued']['m1_rate']}.",
              f"- 20h non-overlap: {summary['nonoverlap_20h']['n']} event rows in {len(clusters)} timestamps; symbols={summary['nonoverlap_distinct_symbols']}.",
              f"- Base/stress mean net return: {summary['all_issued']['net_base_mean_return_fraction'] * 100:.3f}% / {summary['all_issued']['net_stress_mean_return_fraction'] * 100:.3f}%.",
              f"- Base/stress mean net R: {summary['all_issued']['net_base_mean_R']} / {summary['all_issued']['net_stress_mean_R']}.",
              f"- Coverage: {len(ledger)}/{eligible_hours} = {summary['coverage']}.",
              f"- Data gaps: {summary['data_gaps']}; fixed baseline target-first rates long={summary['baseline_long_all_issued']}, short={summary['baseline_short_all_issued']}.",
              f"- Exclusions: {json.dumps(exclusion_counts, sort_keys=True)}; mean signed funding cost fraction={summary['mean_funding_cost_fraction']}.",
              f"- Failed core gates: {', '.join(core_gate_failures)}.",
              f"- Independent ledger audit: {independent_audit['status']} ({independent_audit['checked']} rows, {independent_audit['mismatches']} mismatches).",
              f"- Prereg SHA-256: `{pins['prereg_sha256']}`; data fingerprint: `{fingerprint}`.",
              "", "Spread and slippage are unmeasured; fee scenarios are incomplete. This history was exposed to earlier research. It is a development screen only; even a high score cannot establish independent OOS or Core status.", ""]
    (output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen Pine Regime Classifier M2 development diagnostic")
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--archive-audit", type=Path, required=True)
    parser.add_argument("--funding-audit", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--score-development", action="store_true")
    args = parser.parse_args()
    if not args.score_development:
        try:
            pins = _verify_pins(args.prereg)
            print(json.dumps({"status": "PIN_PREFLIGHT_PASS", "pins": pins}, indent=2))
            return 0
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, indent=2))
            return 2
    try:
        result = run_development(args.archive_root, args.coverage, args.archive_audit,
                                 args.funding_audit, args.prereg, args.output_dir)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
