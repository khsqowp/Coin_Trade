"""Single preregistered matched-candle diagnostic for BOS-origin direction value."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import random
import statistics
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r15 as r15
from crypto import Bar, Zone, _atr, r4_zones
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "PREREG_R18_OB_MATCHED_CANDLE_DIAGNOSTIC.md"
MASTER_PREREG_PATH = HERE / "PREREG.md"
UNIVERSE_PATH = HERE / "universe" / "CRYPTO_35.csv"
ROUND = "R18-coin"
BAR_MS = 4 * 3_600_000
RESULT_BARS = 24
BOOTSTRAPS = 10_000
SIGN_FLIPS = 100_000
BLOCK_MS = 30 * 24 * 3_600_000
EXPECTED_PRE_RUN_ROWS = 1_674
EXPECTED_TOTAL_N = 1_675
TRAIN_CLOSE_CUTOFF_MS = int(datetime(2023, 11, 6, 16, tzinfo=timezone.utc).timestamp() * 1000)
MIN_SYMBOLS = 30
CONFIG = {
    "experiment": "R18-BOS-ORIGIN-MATCHED-NON-BOS-DIRECTION-DIAGNOSTIC",
    "timeframe": "4h", "zone_definition": "bos_origin",
    "direction": "zone_direction_and_same_color_control",
    "control_lag_bars": [25, 180], "recent_bos_exclusion_bars": 48,
    "features": ["atr14_pct", "std_6_log_returns", "rel_volume20", "body_atr"],
    "trend_state": "EMA50_200_exact_match",
    "calipers": {"log_ratio_features": "ln(1.25)", "body_atr_abs": 0.25},
    "matching": "greedy_chronological_nearest_no_reuse_no_control_overlap",
    "outcome": "next_4h_open_to_close_after_24_completed_bars_direction_hit",
    "bootstrap": [10_000, 1801, "common_UTC_30d_blocks"],
    "sign_flip": [100_000, 1802, "one_sided_common_UTC_30d_blocks"],
    "minimum_complete_pairs": 200, "minimum_match_rate": 0.50,
    "continue_threshold_delta": 0.05, "train_cutoff": "2023-11-06T16:00:00Z",
}
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_PREREG_SHA = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Event:
    symbol: str
    index: int
    timestamp: int
    direction: str
    feature: tuple[float, float, float, float] | None
    trend: str | None


def _expected_symbols() -> frozenset[str]:
    with UNIVERSE_PATH.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(set(row) != {"symbol"} for row in rows):
        raise ValueError("invalid frozen universe schema")
    symbols = [row["symbol"].strip() for row in rows]
    if any(not value for value in symbols) or len(set(symbols)) != len(symbols):
        raise ValueError("invalid frozen universe symbols")
    return frozenset(symbols)


def _split_segments(bars: list[Bar]) -> tuple[list[list[Bar]], int]:
    segments: list[list[Bar]] = []
    if not bars:
        return segments, 0
    current = [bars[0]]
    gaps = 0
    for previous, bar in zip(bars, bars[1:]):
        delta = bar.timestamp - previous.timestamp
        if delta <= 0 or delta % BAR_MS:
            raise ValueError("non-monotonic or off-grid 4h timestamps")
        if delta == BAR_MS:
            current.append(bar)
        else:
            segments.append(current)
            gaps += delta // BAR_MS - 1
            current = [bar]
    segments.append(current)
    return segments, gaps


def _assert_train_cutoff(barsets) -> None:
    for symbol, bars, _excluded in barsets:
        if any(bar.timestamp + BAR_MS > TRAIN_CLOSE_CUTOFF_MS for bar in bars):
            raise ValueError(f"TRAIN cutoff violation: {symbol}")


def _feature(bars: list[Bar], index: int) -> tuple[float, float, float, float] | None:
    if index < 20:
        return None
    atr = _atr(bars, index, 14)
    previous_volumes = [bar.volume for bar in bars[index - 20:index]]
    median_volume = statistics.median(previous_volumes)
    if (atr is None or median_volume <= 0 or bars[index].close <= 0
            or bars[index].volume <= 0):
        return None
    returns = [math.log(bars[i].close / bars[i - 1].close)
               for i in range(index - 5, index + 1)]
    vol24 = statistics.pstdev(returns)
    if vol24 <= 0:
        return None
    row = bars[index]
    return (atr / row.close, vol24, row.volume / median_volume,
            abs(row.close - row.open) / atr)


def _outcome(bars: list[Bar], index: int, direction: str) -> tuple[int, float] | None:
    end = index + RESULT_BARS
    if index + 1 >= len(bars) or end >= len(bars):
        return None
    entry = bars[index + 1].open
    exit_price = bars[end].close
    if entry <= 0 or not all(bar.complete for bar in bars[index + 1:end + 1]):
        return None
    signed = (exit_price / entry - 1.0) * (1.0 if direction == "long" else -1.0)
    return int(signed > 0), signed


def _outcome_with_reason(bars: list[Bar], index: int, direction: str):
    end = index + RESULT_BARS
    if index + 1 >= len(bars):
        return None, "missing_next_open"
    if end >= len(bars):
        return None, "24_bar_window_outside_segment"
    if not all(bar.complete for bar in bars[index + 1:end + 1]):
        return None, "incomplete_result_bar"
    return _outcome(bars, index, direction), None


def _observed_window_timestamps(bars: list[Bar], index: int) -> tuple[int, ...]:
    end = min(index + RESULT_BARS + 1, len(bars))
    return tuple(bars[position].timestamp for position in range(index + 1, end))


def _events_for_segment(symbol: str, bars: list[Bar]):
    zones = r4_zones(bars, "bos_origin")
    states = r15._ema_regimes(bars)
    by_index = {zone.signal_index: zone for zone in zones}
    events: list[Event] = []
    for zone in zones:
        i = zone.signal_index
        events.append(Event(symbol, i, bars[i].timestamp, zone.direction,
                            _feature(bars, i), states[i]))
    return events, by_index, states


def _distance(left, right) -> float | None:
    log_diffs = [abs(math.log(a / b)) for a, b in zip(left[:3], right[:3])]
    body_diff = abs(left[3] - right[3])
    if max(log_diffs) > math.log(1.25) + 1e-12 or body_diff > 0.25 + 1e-12:
        return None
    return math.sqrt(sum(value * value for value in log_diffs)
                     + (body_diff / 0.25) ** 2)


def _match_segment(symbol: str, bars: list[Bar], events: list[Event],
                   zones: dict[int, Zone], states: list[str | None],
                   occupied_outcomes: set[int] | None = None):
    bos_indices = sorted(zones)
    used_controls: set[int] = set()
    occupied_outcomes = occupied_outcomes if occupied_outcomes is not None else set()
    feature_cache: dict[int, tuple[float, float, float, float] | None] = {}
    selected = []
    audit_rows = []
    unmatched_missing = unmatched_no_control = 0
    eligible = 0
    for event in events:
        i = event.index
        eligible += 1
        if i < 252:
            unmatched_missing += 1
            audit_rows.append({"symbol": symbol, "bos_index": i, "bos_ts": event.timestamp,
                               "direction": event.direction, "trend": event.trend,
                               "pair_status": "unmatched", "exclusion_reason": "insufficient_252_bar_prehistory",
                               "bos_feature": event.feature, "control_feature": None})
            continue
        if event.feature is None or event.trend is None:
            unmatched_missing += 1
            audit_rows.append({"symbol": symbol, "bos_index": i, "bos_ts": event.timestamp,
                               "direction": event.direction, "trend": event.trend,
                               "pair_status": "unmatched", "exclusion_reason": "missing_feature_or_trend_state",
                               "bos_feature": event.feature, "control_feature": None})
            continue
        choices = []
        for control_i in range(max(252, i - 180), i - 24):
            lag = i - control_i
            if not 25 <= lag <= 180 or control_i in used_controls:
                continue
            if bars[control_i].close == bars[control_i].open:
                continue
            control_direction = "long" if bars[control_i].close > bars[control_i].open else "short"
            if control_direction != event.direction or states[control_i] != event.trend:
                continue
            if any(control_i - 48 <= bos_i <= control_i for bos_i in bos_indices):
                continue
            proposed = (_observed_window_timestamps(bars, control_i),
                        _observed_window_timestamps(bars, i))
            if any(timestamp in occupied_outcomes for window in proposed for timestamp in window):
                continue
            if control_i not in feature_cache:
                feature_cache[control_i] = _feature(bars, control_i)
            control_feature = feature_cache[control_i]
            if control_feature is None:
                continue
            distance = _distance(event.feature, control_feature)
            if distance is None:
                continue
            choices.append((distance, bars[control_i].timestamp, control_i, control_feature))
        if not choices:
            unmatched_no_control += 1
            audit_rows.append({"symbol": symbol, "bos_index": i, "bos_ts": event.timestamp,
                               "direction": event.direction, "trend": event.trend,
                               "pair_status": "unmatched", "exclusion_reason": "no_eligible_control",
                               "bos_feature": event.feature, "control_feature": None})
            continue
        distance, _, control_i, control_feature = min(choices)
        used_controls.add(control_i)
        occupied_outcomes.update(_observed_window_timestamps(bars, control_i))
        occupied_outcomes.update(_observed_window_timestamps(bars, i))
        selected.append({
            "symbol": symbol, "bos_index": i, "bos_ts": event.timestamp,
            "control_index": control_i, "control_ts": bars[control_i].timestamp,
            "direction": event.direction, "trend": event.trend,
            "distance": distance, "bos_feature": event.feature,
            "control_feature": control_feature,
        })
    # Outcomes are evaluated only after the complete treatment/control selection is frozen.
    pairs, censored = [], 0
    for pair in selected:
        bos, bos_reason = _outcome_with_reason(bars, pair["bos_index"], pair["direction"])
        control, control_reason = _outcome_with_reason(
            bars, pair["control_index"], pair["direction"])
        if bos is None or control is None:
            censored += 1
            pair.update({"pair_status": "right_censored",
                         "exclusion_reason": f"bos={bos_reason};control={control_reason}"})
            audit_rows.append(pair)
            continue
        pair.update({"bos_hit": bos[0], "control_hit": control[0],
                     "delta": bos[0] - control[0], "bos_signed_return": bos[1],
                     "control_signed_return": control[1], "pair_status": "complete",
                     "exclusion_reason": ""})
        pairs.append(pair)
        audit_rows.append(pair)
    return pairs, audit_rows, {"eligible_bos": eligible, "unmatched_missing_prehistory": unmatched_missing,
                   "unmatched_no_control": unmatched_no_control,
                   "matched": len(selected), "complete_pairs": len(pairs),
                   "right_censored_pairs": censored}


def _block_key(timestamp: int) -> int:
    return timestamp // BLOCK_MS


def _block_stats(pairs: list[dict]):
    grouped: dict[int, list[int]] = defaultdict(list)
    for pair in pairs:
        grouped[_block_key(pair["bos_ts"])].append(pair["delta"])
    keys = sorted(grouped)
    block_sums = [sum(grouped[key]) for key in keys]
    block_counts = [len(grouped[key]) for key in keys]
    point = sum(block_sums) / sum(block_counts) if block_counts else None
    if len(keys) < 2:
        return {"delta": point, "ci95_low": None, "ci95_high": None,
                "p_one_sided": None, "blocks": len(keys)}
    rng = random.Random(1801)
    draws = []
    for _ in range(BOOTSTRAPS):
        selected = [rng.randrange(len(keys)) for _ in keys]
        den = sum(block_counts[j] for j in selected)
        draws.append(sum(block_sums[j] for j in selected) / den if den else 0.0)
    draws.sort()
    low = draws[int(0.025 * BOOTSTRAPS)]
    high = draws[int(0.975 * BOOTSTRAPS)]
    rng = random.Random(1802)
    observed_sum = sum(block_sums)
    exceed = 0
    for _ in range(SIGN_FLIPS):
        permuted = sum(value * (1 if rng.getrandbits(1) else -1)
                       for value in block_sums)
        exceed += permuted >= observed_sum
    return {"delta": point, "ci95_low": low, "ci95_high": high,
            "p_one_sided": (exceed + 1) / (SIGN_FLIPS + 1), "blocks": len(keys)}


def _summarize(pairs: list[dict], audit: dict, denominator: int) -> dict:
    matched = len(pairs)
    rate = audit["matched"] / audit["eligible_bos"] if audit["eligible_bos"] else 0.0
    stats = _block_stats(pairs)
    adjusted_p = min(1.0, stats["p_one_sided"] * denominator) if stats["p_one_sided"] is not None else None
    status = ("scorable" if audit["symbols"] >= MIN_SYMBOLS and matched >= 200
              and rate >= 0.50 else "unscorable")
    continue_flag = bool(status == "scorable" and stats["delta"] >= 0.05
                         and stats["ci95_low"] > 0 and adjusted_p < 0.05)
    return {
        "status": status, "symbols": audit["symbols"], "eligible_bos": audit["eligible_bos"],
        "matched_pairs": matched, "match_rate": rate,
        "bos_hit_rate": sum(p["bos_hit"] for p in pairs) / matched if matched else None,
        "control_hit_rate": sum(p["control_hit"] for p in pairs) / matched if matched else None,
        **stats, "bonferroni_denominator": denominator, "p_bonferroni": adjusted_p,
        "directional_return_net_12bp_bos_mean":
            (statistics.mean(p["bos_signed_return"] for p in pairs) - 0.0012) if matched else None,
        "directional_return_net_12bp_control_mean":
            (statistics.mean(p["control_signed_return"] for p in pairs) - 0.0012) if matched else None,
        "continue_ob_direction_study": continue_flag,
        **audit,
    }


def _code_hash() -> str:
    names = (
        "crypto.py", "search_crypto.py", "search_crypto_r14.py", "search_crypto_r15.py",
        "search_crypto_r18_ob_matched_candle.py", "data_access.py", "metrics.py",
        "resource_guard.py", "PREREG.md", "PREREG_R18_OB_MATCHED_CANDLE_DIAGNOSTIC.md",
        "tests/test_search_crypto_r18_ob_matched_candle.py", "universe/CRYPTO_35.csv",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _ledger_rows(path: Path) -> int:
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return sum(1 for _ in csv.DictReader(stream))
    finally:
        csv.field_size_limit(old)


def _already_recorded(grid_sha: str, code_sha: str, fingerprint: str,
                      prereg_sha: str) -> bool:
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if (row["round"] == ROUND and row["parameter_grid_hash"] == grid_sha
                        and row["code_sha256"] == code_sha):
                    metric = json.loads(row["metric"])
                    if (metric.get("train_input_fingerprint") == fingerprint
                            and metric.get("prereg_sha256") == prereg_sha):
                        return True
    finally:
        csv.field_size_limit(old)
    return False


def _append(result: dict, denominator: int, grid_sha: str, code_sha: str,
            prereg_sha: str, fingerprint: str) -> None:
    exists = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if exists:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    row = {
        "trial_id": f"R18-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                               "prereg_sha256": prereg_sha,
                               "master_prereg_sha256": _MASTER_PREREG_SHA},
                              sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "R18 one-time TRAIN mechanism diagnostic; not strategy/G approval",
    }
    if not exists:
        raise ValueError("ledger unexpectedly missing; refusing to create a new ledger")
    buffer = io.StringIO(newline="")
    csv.DictWriter(buffer, fieldnames=common.FIELDS).writerow(row)
    payload = buffer.getvalue().encode("utf-8")
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    try:
        original_size = os.fstat(fd).st_size
        written = os.write(fd, payload)
        if written != len(payload):
            os.ftruncate(fd, original_size)
            raise OSError("short append to TRAIN_TRIALS.csv; partial row rolled back")
    finally:
        try:
            os.close(fd)
        except OSError:
            # The complete append has already been checked; close failure does
            # not turn a recorded row into a second counted attempt.
            pass


def _write_event_csv(event_path: Path, event_rows: list[dict]) -> None:
    fields = ["symbol", "bos_index", "bos_ts", "control_index", "control_ts",
              "direction", "trend", "bos_hit", "control_hit", "delta",
              "bos_signed_return", "control_signed_return", "distance",
              "pair_status", "exclusion_reason", "bos_feature", "control_feature"]
    with event_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in event_rows:
            writer.writerow({key: json.dumps(item.get(key), separators=(",", ":"))
                             if key.endswith("feature") else item.get(key, "")
                             for key in fields})


def run() -> int:
    import data_access

    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    master_sha = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()
    if prereg_sha != _PREREG_SHA or master_sha != _MASTER_PREREG_SHA:
        raise RuntimeError("R18 prereg changed after import")
    ledger_rows = _ledger_rows(common.CSV_PATH)
    if ledger_rows != EXPECTED_PRE_RUN_ROWS or ledger_rows + 1 != EXPECTED_TOTAL_N:
        raise RuntimeError(f"R18 prereg denominator mismatch: rows={ledger_rows}; stop before data access")
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = "UNAVAILABLE_PRE_DATA_ACCESS"
    fingerprint = "UNAVAILABLE_BEFORE_DATA_FINGERPRINT"
    result_row_written = False
    duplicate_trial = False
    try:
        code_sha = _code_hash()
        with heavy_task("R18"):
            barsets = []
            for symbol, bars, _funding in data_access.iter_train_bars("4h"):
                closed = [bar for bar in bars if bar.complete]
                barsets.append((symbol, closed, len(bars) - len(closed)))
            _assert_train_cutoff(barsets)
            symbols = [row[0] for row in barsets]
            if set(symbols) != set(_expected_symbols()) or len(symbols) != len(set(symbols)):
                raise ValueError("TRAIN input symbols differ from frozen universe")
            fingerprint = common._train_input_fingerprint(
                "R18-4h-bos-matched-direction",
                [(f"{symbol}:4h", bars, {}, excluded)
                 for symbol, bars, excluded in barsets],
            )
            if _already_recorded(grid_sha, code_sha, fingerprint, prereg_sha):
                duplicate_trial = True
                raise RuntimeError("identical R18 run already exists; refusing duplicate")
            all_pairs, audit = [], {
                "symbols": sum(bool(bars) for _, bars, _ in barsets), "eligible_bos": 0,
                "matched": 0, "complete_pairs": 0, "unmatched_missing_prehistory": 0,
                "unmatched_no_control": 0, "right_censored_pairs": 0,
                "incomplete_bars_excluded": sum(excluded for _, _, excluded in barsets),
                "gap_bars": 0, "raw_bos_events": 0,
            }
            event_rows = []
            occupied_by_symbol: dict[str, set[int]] = defaultdict(set)
            for symbol, bars, _ in barsets:
                segments, gaps = _split_segments(bars)
                audit["gap_bars"] += gaps
                for segment in segments:
                    events, zones, states = _events_for_segment(symbol, segment)
                    audit["raw_bos_events"] += len(zones)
                    pairs, rows, counts = _match_segment(
                        symbol, segment, events, zones, states,
                        occupied_outcomes=occupied_by_symbol[symbol])
                    for key in ("eligible_bos", "matched", "complete_pairs",
                                "unmatched_missing_prehistory", "unmatched_no_control",
                                "right_censored_pairs"):
                        audit[key] += counts[key]
                    all_pairs.extend(pairs)
                    event_rows.extend(rows)
            result = _summarize(all_pairs, audit, ledger_rows + 1)
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != prereg_sha
                    or hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest() != master_sha):
                raise RuntimeError("R18 source/prereg changed during run")
            output_dir = Path(os.environ.get(
                "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
            output_dir = output_dir / "cache/orderblock/runs/r18"
            output_dir.mkdir(parents=True, exist_ok=True)
            event_path = output_dir / f"matched_events_{fingerprint[:12]}.csv"
            _write_event_csv(event_path, event_rows)
            _append(result, ledger_rows + 1, grid_sha, code_sha, prereg_sha, fingerprint)
            result_row_written = True
    except Exception as exc:
        if not result_row_written and not duplicate_trial:
            failure = {
                "status": "failed", "failure_stage": "r18_train_diagnostic",
                "failure_type": type(exc).__name__,
                "failure_fingerprint_available": fingerprint != "UNAVAILABLE_BEFORE_DATA_FINGERPRINT",
                "detail": "R18 preregistered attempt failed; no strategy approval",
            }
            _append(failure, ledger_rows + 1, grid_sha, code_sha, prereg_sha, fingerprint)
        raise
    print(json.dumps({"R18": result, "event_manifest": str(event_path)}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
