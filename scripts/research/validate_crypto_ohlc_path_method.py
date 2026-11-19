#!/usr/bin/env python3
"""Run the preregistered synthetic OHLC execution-path method test."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from chart_predictor.crypto_divergence_engine import (  # noqa: E402
    Bars, MINUTE_MS, aggregate_complete_minutes, evaluate_divergence_event,
)
from chart_predictor.path_method_oracle import (  # noqa: E402
    aggregate_minutes, evaluate_scalar,
)

OUT_DIR = ROOT / "docs/research/crypto_m4_runs/2026-11-17-r019-block-multiplier"
SEED = 20261127
TIMEFRAMES = (1, 5, 15, 30, 60)
HORIZONS = (10, 20)
SIDES = ("long", "short")
ENTRY_MODES = ("next_open", "stop_entry")
TARGETS = (1.0, 1.5, 2.0, 3.0)
BUFFERS = (0.0, 0.25)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_path(rng: random.Random, tf_minutes: int, horizon: int):
    count = tf_minutes * (3 + horizon)
    times, opens, highs, lows, closes = [], [], [], [], []
    log_close = math.log(100.0)
    for minute in range(count):
        open_price = math.exp(log_close)
        u = rng.random()
        log_close = math.log(open_price) + 0.008 * (2 * u - 1)
        close_price = math.exp(log_close)
        v = rng.random()
        span = 0.001 + 0.009 * v
        times.append(minute * MINUTE_MS)
        opens.append(open_price)
        highs.append(max(open_price, close_price) * math.exp(span))
        lows.append(min(open_price, close_price) * math.exp(-span))
        closes.append(close_price)
    return times, opens, highs, lows, closes


def _production_bars(scalar_bars):
    return Bars(
        np.asarray(scalar_bars.open_ms, dtype=np.int64),
        np.asarray(scalar_bars.open, dtype=float),
        np.asarray(scalar_bars.high, dtype=float),
        np.asarray(scalar_bars.low, dtype=float),
        np.asarray(scalar_bars.close, dtype=float),
        np.ones(len(scalar_bars.open_ms), dtype=float),
    )


def _same_native_bars(actual, independent):
    fields = ("open_ms", "open", "high", "low", "close")
    return all(np.array_equal(getattr(actual, name), np.asarray(getattr(independent, name)))
               for name in fields)


def _kwargs(times, opens, highs, lows, closes, native, *, tf_minutes, side,
            horizon, entry_mode, target_r, stop_buffer_atr):
    signal_close = native.close[0]
    atr = 0.01 * signal_close
    effective_stop = signal_close * (1 - 0.005 if side == "long" else 1 + 0.005)
    pivot_stop = (effective_stop + stop_buffer_atr * atr if side == "long"
                  else effective_stop - stop_buffer_atr * atr)
    return dict(
        minute_open_ms=times, minute_opens=opens, minute_highs=highs,
        minute_lows=lows, minute_closes=closes, native_bars=native,
        native_tf_minutes=tf_minutes, signal_index=0, side=side,
        pivot_stop=pivot_stop, atr_at_signal=atr,
        stop_buffer_atr=stop_buffer_atr, target_r=target_r,
        horizon_bars=horizon, entry_mode=entry_mode,
    )


def _normalize(result):
    return {key: result.get(key) for key in (
        "status", "target_first", "entry_ms", "entry_price", "exit_ms",
        "exit_price", "trade_net_r")}


def _same_result(actual, expected):
    a, e = _normalize(actual), _normalize(expected)
    for key in ("status", "target_first", "entry_ms", "entry_price", "exit_ms", "exit_price"):
        if a[key] != e[key]:
            return False
    if a["trade_net_r"] is None or e["trade_net_r"] is None:
        return a["trade_net_r"] is e["trade_net_r"]
    return abs(a["trade_net_r"] - e["trade_net_r"]) <= 1e-12


def _canonical(side="long"):
    times = [i * MINUTE_MS for i in range(13)]
    opens = [100.0] * 13
    highs = [101.0] * 13
    lows = [99.0] * 13
    closes = [100.0] * 13
    if side == "long":
        highs[0] = 102.0
        stop = 90.0
    else:
        lows[0] = 98.0
        stop = 110.0
    production_native = aggregate_complete_minutes(
        np.asarray(times, dtype=np.int64), np.asarray(opens), np.asarray(highs),
        np.asarray(lows), np.asarray(closes), np.ones(len(times)), 1)
    native = _production_bars(production_native)
    return times, opens, highs, lows, closes, native, stop


def _sentinel(name, side, edit=None, *, entry_mode="next_open", pivot_stop=None,
              remove_time=None, duplicate_time=None, expected):
    times, opens, highs, lows, closes, native, default_stop = _canonical(side)
    stop = default_stop if pivot_stop is None else pivot_stop
    if edit:
        edit(opens, highs, lows, closes)
    if remove_time is not None:
        index = times.index(remove_time * MINUTE_MS)
        for array in (times, opens, highs, lows, closes):
            array.pop(index)
    if duplicate_time is not None:
        times[duplicate_time] = times[duplicate_time - 1]
    args = dict(minute_open_ms=times, minute_opens=opens, minute_highs=highs,
                minute_lows=lows, minute_closes=closes, native_bars=native,
                native_tf_minutes=1, signal_index=0, side=side, pivot_stop=stop,
                atr_at_signal=2.0, stop_buffer_atr=0.0, target_r=1.0,
                horizon_bars=10, entry_mode=entry_mode)
    actual = evaluate_divergence_event(**args)
    oracle = evaluate_scalar(**args)
    expected_dict = dict(zip(("status", "target_first", "entry_ms", "entry_price",
                              "exit_ms", "exit_price"), expected))
    actual_tuple = tuple(_normalize(actual)[k] for k in expected_dict)
    oracle_tuple = tuple(_normalize(oracle)[k] for k in expected_dict)
    return {"name": name, "expected": list(expected),
            "actual_match": actual_tuple == expected,
            "oracle_match": oracle_tuple == expected,
            "actual_oracle_match": _same_result(actual, oracle)}


def _run_sentinels():
    cases = []
    cases.append(_sentinel("long_adverse_gap", "long",
        lambda o,h,l,c: (o.__setitem__(2,89.0), h.__setitem__(2,100.0), l.__setitem__(2,88.0), c.__setitem__(2,95.0)),
        expected=("stop", False, MINUTE_MS, 100.0, 2*MINUTE_MS, 89.0)))
    cases.append(_sentinel("long_favorable_gap", "long",
        lambda o,h,l,c: (o.__setitem__(2,111.0), h.__setitem__(2,112.0), l.__setitem__(2,109.0), c.__setitem__(2,111.0)),
        expected=("target", True, MINUTE_MS, 100.0, 2*MINUTE_MS, 110.0)))
    cases.append(_sentinel("long_tie_stop_first", "long",
        lambda o,h,l,c: (h.__setitem__(2,111.0), l.__setitem__(2,89.0)),
        expected=("stop", False, MINUTE_MS, 100.0, 2*MINUTE_MS, 90.0)))
    cases.append(_sentinel("long_timeout", "long",
        expected=("timeout", False, MINUTE_MS, 100.0, 10*MINUTE_MS, 100.0)))
    cases.append(_sentinel("long_no_fill", "long", entry_mode="stop_entry",
        expected=("expired", False, None, None, None, None)))
    cases.append(_sentinel("long_stop_entry_gap", "long",
        lambda o,h,l,c: (o.__setitem__(2,103.0), h.__setitem__(2,104.0), l.__setitem__(2,102.0), c.__setitem__(2,103.0)),
        entry_mode="stop_entry",
        expected=("timeout", False, 2*MINUTE_MS, 103.0, 11*MINUTE_MS, 100.0)))
    cases.append(_sentinel("long_invalid_stop", "long", pivot_stop=100.0,
        expected=("invalid", False, None, None, None, None)))
    cases.append(_sentinel("long_malformed", "long",
        lambda o,h,l,c: h.__setitem__(2,98.0),
        expected=("unresolved", None, MINUTE_MS, 100.0, None, None)))
    cases.append(_sentinel("long_stop_entry_malformed", "long",
        lambda o,h,l,c: h.__setitem__(2,98.0), entry_mode="stop_entry",
        expected=("unresolved", None, None, None, None, None)))
    cases.append(_sentinel("long_duplicate_time", "long", duplicate_time=5,
        expected=("unresolved", None, MINUTE_MS, 100.0, None, None)))
    for missing in (1,5,10):
        missing_expected = (("unresolved", None, None, None, None, None) if missing == 1
                            else ("unresolved", None, MINUTE_MS, 100.0, None, None))
        cases.append(_sentinel(f"long_missing_t{missing}", "long", remove_time=missing,
            expected=missing_expected))
    cases.append(_sentinel("short_adverse_gap", "short",
        lambda o,h,l,c: (o.__setitem__(2,111.0), h.__setitem__(2,112.0), l.__setitem__(2,100.0), c.__setitem__(2,105.0)),
        expected=("stop", False, MINUTE_MS, 100.0, 2*MINUTE_MS, 111.0)))
    cases.append(_sentinel("short_favorable_gap", "short",
        lambda o,h,l,c: (o.__setitem__(2,89.0), h.__setitem__(2,91.0), l.__setitem__(2,88.0), c.__setitem__(2,89.0)),
        expected=("target", True, MINUTE_MS, 100.0, 2*MINUTE_MS, 90.0)))
    cases.append(_sentinel("short_tie_stop_first", "short",
        lambda o,h,l,c: (h.__setitem__(2,111.0), l.__setitem__(2,89.0)),
        expected=("stop", False, MINUTE_MS, 100.0, 2*MINUTE_MS, 110.0)))
    cases.append(_sentinel("short_stop_entry_gap", "short",
        lambda o,h,l,c: (o.__setitem__(2,97.0), h.__setitem__(2,98.0), l.__setitem__(2,96.0), c.__setitem__(2,97.0)),
        entry_mode="stop_entry",
        expected=("timeout", False, 2*MINUTE_MS, 97.0, 11*MINUTE_MS, 100.0)))
    if not all(c["actual_match"] and c["oracle_match"] and c["actual_oracle_match"] for c in cases):
        raise AssertionError("one or more fixed sentinel expectations failed")
    return cases


def run_suite():
    rng = random.Random(SEED)
    digest = hashlib.sha256()
    cell_rows = []
    status_counts = {}
    mismatch_count = 0
    error_count = 0
    aggregation_mismatches = 0
    scenarios = 0
    cost_schedules = ((0.0005, 0.00025), (0.0005, 0.0005))
    for tf in TIMEFRAMES:
        for horizon in HORIZONS:
            for side in SIDES:
                for entry_mode in ENTRY_MODES:
                    cell_mismatches = 0
                    for j in range(200):
                        times, opens, highs, lows, closes = _make_path(rng, tf, horizon)
                        production_native = aggregate_complete_minutes(
                            np.asarray(times, dtype=np.int64), np.asarray(opens),
                            np.asarray(highs), np.asarray(lows), np.asarray(closes),
                            np.ones(len(times)), tf)
                        native = _production_bars(production_native)
                        oracle_native = aggregate_minutes(times, opens, highs, lows, closes, tf)
                        aggregation_match = _same_native_bars(native, oracle_native)
                        if not aggregation_match:
                            aggregation_mismatches += 1
                            mismatch_count += 1
                            cell_mismatches += 1
                        target_r = TARGETS[j % 4]
                        buffer_atr = BUFFERS[(j // 4) % 2]
                        args = _kwargs(times, opens, highs, lows, closes, native,
                                       tf_minutes=tf, side=side, horizon=horizon,
                                       entry_mode=entry_mode, target_r=target_r,
                                       stop_buffer_atr=buffer_atr)
                        try:
                            for schedule_ix, (fee, slip) in enumerate(cost_schedules):
                                actual = evaluate_divergence_event(
                                    **args, fee_per_side=fee, slippage_per_side=slip)
                                oracle = evaluate_scalar(
                                    **args, fee_per_side=fee, slippage_per_side=slip)
                                good = _same_result(actual, oracle)
                                if not good:
                                    mismatch_count += 1
                                    cell_mismatches += 1
                                if schedule_ix == 0:
                                    status_counts[actual["status"]] = status_counts.get(actual["status"], 0) + 1
                                pair = {"tf": tf, "horizon": horizon, "side": side,
                                        "entry_mode": entry_mode, "scenario": j,
                                        "cost_schedule": schedule_ix,
                                        "actual": _normalize(actual),
                                        "oracle": _normalize(oracle), "match": good,
                                        "aggregation_match": aggregation_match}
                                digest.update(json.dumps(pair, sort_keys=True, separators=(",", ":"),
                                                         allow_nan=False).encode("utf-8") + b"\n")
                        except Exception as exc:  # preserve unexpected errors as failures
                            error_count += 1
                            mismatch_count += 1
                            cell_mismatches += 1
                            failure = {"tf": tf, "horizon": horizon, "side": side,
                                       "entry_mode": entry_mode, "scenario": j,
                                       "error_type": type(exc).__name__, "error": str(exc)}
                            digest.update(json.dumps(failure, sort_keys=True,
                                                     separators=(",", ":")).encode() + b"\n")
                        scenarios += 1
                    cell_rows.append({"tf_minutes": tf, "horizon_bars": horizon,
                                      "side": side, "entry_mode": entry_mode,
                                      "scenarios": 200, "mismatches": cell_mismatches})
    sentinels = _run_sentinels()
    return {
        "protocol": "r019_ohlc_path_method_prereg_20261119",
        "python": platform.python_version(), "numpy": np.__version__,
        "seed": SEED, "scenario_count": scenarios,
        "cost_evaluations": scenarios * len(cost_schedules),
        "mismatch_count": mismatch_count, "error_count": error_count,
        "aggregation_mismatches": aggregation_mismatches,
        "base_status_counts": dict(sorted(status_counts.items())),
        "cell_results": cell_rows, "sentinel_count": len(sentinels),
        "sentinels_passed": sum(
            c["actual_match"] and c["oracle_match"] and c["actual_oracle_match"]
            for c in sentinels),
        "sentinels": sentinels, "result_digest_sha256": digest.hexdigest(),
        "source_sha256": {
            "engine": _sha256(ROOT / "chart_predictor/crypto_divergence_engine.py"),
            "oracle": _sha256(ROOT / "chart_predictor/path_method_oracle.py"),
            "runner": _sha256(Path(__file__).resolve()),
        },
    }


def _write_outputs(summary, json_path, markdown_path):
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False) + "\n"
    json_path.write_text(payload, encoding="utf-8", newline="\n")
    rows = [
        "# R019 synthetic OHLC path-method validation",
        "",
        "This is a synthetic mechanics test only. No historical or live market rows or outcomes were read.",
        "",
        f"- Python / NumPy: {summary['python']} / {summary['numpy']}",
        f"- Seed: {summary['seed']}",
        f"- Scenarios: {summary['scenario_count']} / 8,000",
        f"- Cost evaluations: {summary['cost_evaluations']} / 16,000",
        f"- Mismatches / errors: {summary['mismatch_count']} / {summary['error_count']}",
        f"- Independent aggregation mismatches: {summary['aggregation_mismatches']}",
        f"- Sentinels: {summary['sentinels_passed']} / {summary['sentinel_count']}",
        f"- Result digest: `{summary['result_digest_sha256']}`",
        "",
        "## Fixed-case results",
        "",
        "| Case | Actual | Oracle | Both match |",
        "|---|---:|---:|---:|",
    ]
    for case in summary["sentinels"]:
        rows.append(f"| {case['name']} | {case['actual_match']} | {case['oracle_match']} | {case['actual_oracle_match']} |")
    rows.extend(["", "## Interpretation", "",
                 "A pass validates only tested synthetic path and cost arithmetic. It does not establish market performance, real execution quality, or signal accuracy.",
                 "", "## Source SHA-256", ""])
    for name, digest in summary["source_sha256"].items():
        rows.append(f"- {name}: `{digest}`")
    markdown_path.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=OUT_DIR / "r019_ohlc_path_method_2026-11-19.json")
    parser.add_argument("--markdown", type=Path, default=OUT_DIR / "r019_ohlc_path_method_2026-11-19.md")
    args = parser.parse_args()
    result = run_suite()
    _write_outputs(result, args.json, args.markdown)
    print(json.dumps({k: result[k] for k in (
        "python", "numpy", "scenario_count", "cost_evaluations", "mismatch_count",
        "error_count", "aggregation_mismatches", "sentinel_count", "sentinels_passed",
        "result_digest_sha256")},
        sort_keys=True))
    return 0 if result["scenario_count"] == 8000 and result["mismatch_count"] == 0 and result["sentinels_passed"] == result["sentinel_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
