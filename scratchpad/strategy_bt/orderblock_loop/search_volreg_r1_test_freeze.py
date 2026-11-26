#!/usr/bin/env python3
"""Single frozen TEST evaluation for VOLREG-R1."""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import volreg_r1_lib as research


EXPECTED_DATA_DIR = "/Users/user/CODE/Coin_Trade/trading_data"
EXPECTED_LEDGER_ROWS = 4269
TRIAL_ID = "VOLREG-R1-TESTFREEZE-01"
ROUND = "VOLREG-R1-TESTFREEZE"
ENTRY = -2.5
EXIT = 2.5
TEST_CUTOFF = "2026-06-01"
SENTINEL_CUTOFF = "2099-12-31"
ROUND_TRIP_COST = research.COST
LEDGER = Path(__file__).resolve().with_name("TRAIN_TRIALS.csv")


def ledger_snapshot() -> tuple[set[str], int, list[str]]:
    csv.field_size_limit(sys.maxsize)
    with LEDGER.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
                  "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]
        if reader.fieldnames != fields:
            raise RuntimeError("TRAIN_TRIALS.csv header differs from registered 11-column format")
        ids, count = set(), 0
        for row in reader:
            count += 1
            ids.add(row["trial_id"])
    return ids, count, fields


def bucket_returns(dates: list[str], strategy: np.ndarray, spy: np.ndarray) -> list[dict[str, object]]:
    if len(dates) < 2:
        raise RuntimeError("TEST window must contain at least two sessions for return measurement")
    first_year = int(dates[0][:4])
    last_year = int(dates[-1][:4])
    if (last_year - first_year) < 1:
        buckets = [("TEST 전체", 0, len(dates) - 1)]
    else:
        keys = sorted({(day[:4], "상" if int(day[5:7]) <= 6 else "하") for day in dates})
        buckets = []
        for year, half in keys:
            indexes = [i for i, day in enumerate(dates)
                       if day.startswith(year) and ((int(day[5:7]) <= 6) == (half == "상"))]
            buckets.append((f"{year} {half}반기", indexes[0], indexes[-1]))
    results = []
    for label, first, last in buckets:
        base_strategy = 100.0 if first == 0 else float(strategy[first - 1])
        base_spy = 100.0 if first == 0 else float(spy[first - 1])
        strategy_return = float(strategy[last] / base_strategy - 1.0)
        spy_return = float(spy[last] / base_spy - 1.0)
        results.append({"bucket": label, "start": dates[first], "end": dates[last],
                        "strategy_return_pct": strategy_return * 100.0,
                        "spy_return_pct": spy_return * 100.0,
                        "relative_pp": (strategy_return - spy_return) * 100.0})
    return results


def main() -> int:
    configured = os.environ.get("TRADING_DATA_DIR")
    if configured != EXPECTED_DATA_DIR:
        raise RuntimeError("TRADING_DATA_DIR must exactly match the preregistered repository data directory")
    ids, count, fields = ledger_snapshot()
    if count != EXPECTED_LEDGER_ROWS:
        raise RuntimeError(f"Ledger row count changed before run: expected {EXPECTED_LEDGER_ROWS}, found {count}")
    if TRIAL_ID in ids:
        raise RuntimeError(f"{TRIAL_ID} already exists; refusing a second TEST execution")

    research.CUTOFF = SENTINEL_CUTOFF
    research.RUNNER_PATH = Path(__file__).resolve()
    dates, panel, vix = research.read_training(Path(configured))
    if not dates or dates[0] != research.START:
        raise RuntimeError("Loaded ETF data does not begin at the preregistered start date")
    last_available_date = max(dates)
    if last_available_date <= TEST_CUTOFF:
        raise RuntimeError("No post-cutoff TEST sessions are available")

    start_i = dates.index(research.START)
    _, spread = research.indicators(dates, panel, vix)
    raw = research.make_targets(spread, ENTRY, EXIT, start_i)
    causal = research.causal_assertions(dates, panel, vix, spread, raw, ENTRY, EXIT)
    if not (causal["lookahead_shift_assert"] and causal["prefix_invariance_assert"]):
        raise RuntimeError("Lookahead or prefix-invariance assertion failed; ledger unchanged")

    full = research.run_one(dates, panel, raw, cost=ROUND_TRIP_COST, delay=1)
    test_offset = next((i for i, day in enumerate(dates[start_i:]) if day > TEST_CUTOFF), None)
    if test_offset is None or test_offset == 0:
        raise RuntimeError("Could not locate a valid post-cutoff TEST boundary")
    test_start_index = start_i + test_offset
    test_dates = dates[test_start_index:]
    test_strategy = np.asarray(full["strategy_curve"], dtype=float)[test_offset - 1:]
    test_spy = np.asarray(full["spy_curve"], dtype=float)[test_offset - 1:]
    # Index zero is the last TRAIN close and anchors TEST start assets at 100.
    strategy_base, spy_base = float(test_strategy[0]), float(test_spy[0])
    strategy_curve = test_strategy[1:] / strategy_base * 100.0
    spy_curve = test_spy[1:] / spy_base * 100.0
    strategy_return = float(strategy_curve[-1] / 100.0 - 1.0)
    spy_return = float(spy_curve[-1] / 100.0 - 1.0)
    excess_pp = (strategy_return - spy_return) * 100.0
    strategy_mdd = research._mdd(strategy_curve)

    execution = research.shifted_target(raw, 1, start_i)
    switches = int(np.count_nonzero(execution[test_start_index:] != execution[test_start_index - 1:-1]))
    buckets = bucket_returns(test_dates, strategy_curve, spy_curve)
    passed = excess_pp > 0.0 and all(float(item["relative_pp"]) >= 0.0 for item in buckets)
    decision = "PASS" if passed else "REJECT"

    after_ids, after_count, after_fields = ledger_snapshot()
    if after_count != EXPECTED_LEDGER_ROWS or TRIAL_ID in after_ids or after_fields != fields:
        raise RuntimeError("Ledger changed during evaluation; refusing append")
    code_sha = research.sha256_file(Path(__file__).resolve())
    definition = {
        "experiment": "VOLREG-R1 frozen TEST evaluation",
        "entry": ENTRY, "exit": EXIT, "benchmark": "SPY buy-and-hold",
        "execution": "next_session_adjusted_open", "round_trip_bps": 12,
        "test_window": {"strictly_after": TEST_CUTOFF, "start": test_dates[0],
                        "end": last_available_date},
        "continuous_state_from": research.START,
    }
    metric = {
        "entry": ENTRY, "exit": EXIT, "test_rows_accessed": True,
        "last_available_date": last_available_date,
        "test_window": {"start": test_dates[0], "end": last_available_date,
                        "sessions": len(test_dates)},
        "test_strategy_return_pct": strategy_return * 100.0,
        "test_spy_return_pct": spy_return * 100.0,
        "test_excess_return_pp": excess_pp,
        "test_strategy_mdd_pct": strategy_mdd * 100.0,
        "test_switches": switches, "period_buckets": buckets,
        "lookahead_assertions": causal,
        "round_trip_bps": 12, "cost_stress_rerun": False,
        "decision": decision, "pass": passed,
    }
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    row = {
        "trial_id": TRIAL_ID, "round": ROUND, "market_group": "us_equities",
        "utc_timestamp": now,
        "definition": json.dumps(definition, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": research.canonical_hash({"entry": ENTRY, "exit": EXIT}),
        "code_sha256": code_sha,
        "train_period": f"TEST_FREEZE: {test_dates[0]}/{last_available_date}; one fixed parameter pair",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "Single frozen TEST observation; continuous state from START; no rerun",
    }
    with LEDGER.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())

    summary = {
        "status": "complete", "trial_id": TRIAL_ID,
        "ledger_rows_before": count, "ledger_rows_after": count + 1,
        "n_train_after_append": count + 1,
        "bonferroni_reference": 0.05 / (count + 1),
        "last_available_date": last_available_date,
        "test_window": {"start": test_dates[0], "end": last_available_date,
                        "sessions": len(test_dates)},
        "entry": ENTRY, "exit": EXIT, "round_trip_bps": 12,
        "test_strategy_return_pct": strategy_return * 100.0,
        "test_spy_return_pct": spy_return * 100.0,
        "test_excess_return_pp": excess_pp,
        "test_strategy_mdd_pct": strategy_mdd * 100.0,
        "test_switches": switches, "period_buckets": buckets,
        "lookahead_assertions": causal, "decision": decision, "pass": passed,
        "test_rows_accessed": True, "code_sha256": code_sha,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
