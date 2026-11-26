#!/usr/bin/env python3
"""Formal TRAIN-only preregistered VOLREG-R1 evaluation."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds


LOOP = Path(__file__).resolve().parent
EXPECTED_DATA_DIR = "/Users/user/CODE/Coin_Trade/trading_data"
ETF_REL = "external/equities/us/yahoo_daily_us_etf.parquet"
VIX_REL = "external/equities/vix/cboe_index_history.parquet"
LEDGER = LOOP / "TRAIN_TRIALS.csv"
START = "2002-07-30"
CUTOFF = "2026-06-01"
ROUND = "VOLREG-R1-PREREG-V2"
ENTRY = (-1.0, -1.5, -2.0, -2.5, -3.0)
EXIT = (1.0, 1.5, 2.0, 2.5, 3.0)
ASSETS = ("SPY", "QQQ", "SHY")
COST = 0.0006
PLACEMENT_RUNS = 200
PLACEMENT_SEED = 20261126
SHIFT_RUNS = 1000
SHIFT_SEED = 20261127
EXPECTED_LEDGER_ROWS = 4244
PLANNED_IDS = tuple(f"VOLREG-R1-PREREG-V2-{i:02d}" for i in range(1, 26))
RUNNER_PATH = Path(__file__)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def grid_definition() -> dict[str, object]:
    return {
        "entry": list(ENTRY), "exit": list(EXIT), "iteration": "entry_outer_exit_inner",
        "risk_assets": {"SPY": 0.5, "QQQ": 0.5}, "safe_asset": "SHY",
        "signal": "CBOE:VIX_close_minus_SPY_RV20_annualized_pct",
        "rv20": "std_20_SPY_adjusted_close_log_returns_sample*sqrt(252)*100",
        "start": START, "cutoff_inclusive": CUTOFF,
        "execution": "next_session_adjusted_open", "round_trip_bps": 12,
        "stress_round_trip_bps": 24, "delay_extra_sessions": 1,
    }


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


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


def _assert_cutoff(table: pa.Table, label: str) -> None:
    values = table.column("date").to_pylist()
    if not values:
        raise RuntimeError(f"No {label} rows in filtered TRAIN input")
    maximum = max(values)
    assert maximum.date().isoformat() <= CUTOFF, f"{label} read exceeded fixed cutoff"


def read_training(data_root: Path) -> tuple[list[str], dict[str, dict[str, float]], dict[str, float]]:
    cutoff = pa.scalar(datetime.fromisoformat(CUTOFF), type=pa.timestamp("ns"))
    start = pa.scalar(datetime.fromisoformat(START), type=pa.timestamp("ns"))
    etf_ds = ds.dataset(data_root / ETF_REL, format="parquet")
    price_cols = {"ticker", "date", "open", "close", "adj_close"}
    if not price_cols.issubset(etf_ds.schema.names):
        raise RuntimeError(f"ETF input lacks columns: {sorted(price_cols - set(etf_ds.schema.names))}")
    price_table = etf_ds.to_table(
        filter=(ds.field("date") >= start) & (ds.field("date") <= cutoff)
        & ds.field("ticker").isin(list(ASSETS)), columns=sorted(price_cols))
    _assert_cutoff(price_table, "ETF price")
    price_rows = price_table.to_pylist()
    by_asset: dict[str, dict[str, dict[str, float]]] = {asset: {} for asset in ASSETS}
    for row in price_rows:
        day, asset = row["date"].date().isoformat(), row["ticker"]
        if row["open"] is None or row["close"] in (None, 0) or row["adj_close"] is None:
            raise RuntimeError(f"Invalid price at {asset} {day}")
        by_asset[asset][day] = {"close": float(row["adj_close"]),
                                "open": float(row["open"]) * float(row["adj_close"]) / float(row["close"])}
    first = {asset: min(by_asset[asset]) for asset in ASSETS if by_asset[asset]}
    if len(first) != len(ASSETS):
        raise RuntimeError("One or more fixed ETFs have no filtered TRAIN observations")
    common_start = max(first.values())
    if common_start != START:
        raise RuntimeError(f"Observed common start {common_start} differs from preregistered {START}")
    dates = sorted(by_asset["SPY"])
    dates = [day for day in dates if START <= day <= CUTOFF]
    for day in dates:
        if any(day not in by_asset[asset] for asset in ASSETS):
            raise RuntimeError(f"Missing fixed ETF observation on SPY session {day}")

    vix_ds = ds.dataset(data_root / VIX_REL, format="parquet")
    if not {"index", "date", "close"}.issubset(vix_ds.schema.names):
        raise RuntimeError("CBOE VIX input lacks index/date/close")
    vix_table = vix_ds.to_table(
        filter=(ds.field("index") == "VIX") & (ds.field("date") <= cutoff),
        columns=["date", "close"])
    _assert_cutoff(vix_table, "CBOE VIX")
    vix = {row["date"].date().isoformat(): float(row["close"])
           for row in vix_table.to_pylist() if row["close"] is not None}
    prices = {day: {asset: by_asset[asset][day]["open"] for asset in ASSETS} for day in dates}
    closes = {day: {asset: by_asset[asset][day]["close"] for asset in ASSETS} for day in dates}
    panel = {day: {"open": prices[day], "close": closes[day]} for day in dates}
    return dates, panel, vix


def indicators(dates: list[str], panel: dict[str, dict[str, object]], vix: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    spy_close = np.array([panel[d]["close"]["SPY"] for d in dates], dtype=float)
    logret = np.full(len(dates), np.nan)
    logret[1:] = np.log(spy_close[1:] / spy_close[:-1])
    rv = np.full(len(dates), np.nan)
    for i in range(20, len(dates)):
        values = logret[i - 19:i + 1]
        if np.isfinite(values).all():
            rv[i] = np.std(values, ddof=1) * np.sqrt(252.0) * 100.0
    spread = np.array([vix.get(day, np.nan) for day in dates]) - rv
    return rv, spread


def make_targets(spread: np.ndarray, entry: float, exit_: float, start_index: int = 0) -> np.ndarray:
    target = np.ones(len(spread), dtype=float)
    state = 1.0
    for i in range(start_index, len(spread)):
        value = spread[i]
        if np.isfinite(value):
            if value <= entry:
                state = 0.0
            elif value >= exit_:
                state = 1.0
        target[i] = state
    return target


def shifted_target(raw: np.ndarray, delay: int, start_index: int) -> np.ndarray:
    execution = np.ones(len(raw), dtype=float)
    if delay < len(raw):
        execution[delay:] = raw[:-delay]
    execution[:start_index + delay] = 1.0
    return execution


def _annual(curve: np.ndarray, dates: list[str], start_index: int) -> dict[str, float]:
    result: dict[str, float] = {}
    years = sorted({day[:4] for day in dates[start_index:]})
    for year in years:
        indexes = [i for i in range(start_index, len(dates)) if dates[i].startswith(year)]
        first_i, last_i = indexes[0], indexes[-1]
        base = 100.0 if first_i == start_index else curve[first_i - 1]
        result[year] = float(curve[last_i] / base - 1.0)
    return result


def _mdd(curve: np.ndarray) -> float:
    peaks = np.maximum.accumulate(curve)
    return float(np.min(curve / peaks - 1.0))


def run_one(dates: list[str], panel: dict[str, dict[str, object]], target: np.ndarray,
            cost: float = COST, delay: int = 1) -> dict[str, object]:
    start_i = dates.index(START)
    execution = shifted_target(target, delay, start_i)
    nav, spy = 100.0, 100.0
    weights = np.zeros(3, dtype=float)
    prior_close = np.array([panel[dates[start_i - 1]]["close"][a] for a in ASSETS], dtype=float)
    curve = np.full(len(dates) - start_i, np.nan)
    spy_curve = np.full(len(dates) - start_i, np.nan)
    switches = 0
    previous_state: float | None = None
    for i in range(start_i, len(dates)):
        day = dates[i]
        opn = np.array([panel[day]["open"][a] for a in ASSETS], dtype=float)
        close = np.array([panel[day]["close"][a] for a in ASSETS], dtype=float)
        if i > start_i:
            overnight = opn / prior_close - 1.0
            nav *= 1.0 + float(np.dot(weights, overnight))
            spy *= opn[0] / prior_close[0]
        else:
            spy *= 1.0 - cost
        state = float(execution[i])
        desired = np.array([state / 2.0, state / 2.0, 1.0 - state])
        if previous_state is None or state != previous_state:
            nav *= 1.0 - cost * float(np.abs(desired - weights).sum())
            if previous_state is not None:
                switches += 1
            weights = desired
            previous_state = state
        nav *= 1.0 + float(np.dot(weights, close / opn - 1.0))
        spy *= close[0] / opn[0]
        curve[i - start_i] = nav
        spy_curve[i - start_i] = spy
        prior_close = close
    nav *= 1.0 - cost * float(np.abs(weights).sum())
    spy *= 1.0 - cost
    curve[-1] = nav
    spy_curve[-1] = spy
    eval_dates = dates[start_i:]
    strategy_return = nav / 100.0 - 1.0
    spy_return = spy / 100.0 - 1.0
    annual = _annual(curve, eval_dates, 0)
    spy_annual = _annual(spy_curve, eval_dates, 0)
    return {"switches": switches, "total_return": strategy_return,
            "spy_total_return": spy_return, "excess_return": strategy_return - spy_return,
            "mdd": _mdd(curve), "spy_mdd": _mdd(spy_curve),
            "mdd_improvement": _mdd(curve) - _mdd(spy_curve),
            "annual_returns": annual, "spy_annual_returns": spy_annual,
            "strategy_curve": curve.tolist(), "spy_curve": spy_curve.tolist()}


def causal_assertions(dates: list[str], panel: dict[str, dict[str, object]], vix: dict[str, float],
                      spread: np.ndarray, raw: np.ndarray, entry: float, exit_: float) -> dict[str, bool]:
    start_i = dates.index(START)
    execution = shifted_target(raw, 1, start_i)
    shift_ok = bool(np.array_equal(execution[start_i + 1:], raw[start_i:-1])
                    and np.all(np.arange(start_i + 1, len(raw)) > np.arange(start_i, len(raw) - 1)))
    pivot = max(start_i + 30, len(dates) // 2)
    altered = {day: {"open": dict(panel[day]["open"]), "close": dict(panel[day]["close"])} for day in dates}
    altered_vix = dict(vix)
    for i, day in enumerate(dates):
        if i > pivot:
            altered[day]["close"]["SPY"] *= 1.37
            altered_vix[day] = altered_vix.get(day, 20.0) * 1.41
    _, spread2 = indicators(dates, altered, altered_vix)
    raw2 = make_targets(spread2, entry, exit_, start_i)
    prefix_ok = bool(np.allclose(spread[:pivot + 1], spread2[:pivot + 1], equal_nan=True)
                     and np.array_equal(raw[:pivot + 1], raw2[:pivot + 1]))
    assert shift_ok, "execution target does not equal prior-session raw target"
    assert prefix_ok, "future mutation changed a signal/target at or before pivot"
    return {"lookahead_shift_assert": shift_ok, "prefix_invariance_assert": prefix_ok,
            "pivot_date": dates[pivot]}


def _flatness(metrics: list[dict[str, object]], winner_index: int) -> tuple[str, dict[str, object]]:
    row, col = divmod(winner_index, len(EXIT))
    if row in (0, len(ENTRY) - 1) or col in (0, len(EXIT) - 1):
        return "grid_edge", {"neighbors_pass": None, "neighbors_total": 0, "fraction": None}
    winner_excess = float(metrics[winner_index]["excess_return"])
    neighbors = [metrics[r * len(EXIT) + c] for r in range(row - 1, row + 2)
                 for c in range(col - 1, col + 2) if (r, c) != (row, col)]
    passed = sum(float(item["excess_return"]) >= 0.5 * winner_excess for item in neighbors)
    fraction = passed / len(neighbors)
    return ("pass" if fraction >= 0.70 else "fail"), {
        "neighbors_pass": passed, "neighbors_total": len(neighbors), "fraction": fraction}


def random_placement_null(dates: list[str], panel: dict[str, dict[str, object]], switches: int,
                          observed: float) -> dict[str, object]:
    rng = np.random.default_rng(PLACEMENT_SEED)
    start_i = dates.index(START)
    eligible = np.arange(start_i + 1, len(dates))
    if switches > len(eligible):
        raise RuntimeError("Winner switch count exceeds eligible sessions")
    values = []
    for _ in range(PLACEMENT_RUNS):
        points = np.sort(rng.choice(eligible, size=switches, replace=False))
        target = np.ones(len(dates), dtype=float)
        state = 1.0
        for point in points:
            state = 1.0 - state
            target[point:] = state
        values.append(float(run_one(dates, panel, target)["excess_return"]) * 100.0)
    return _null_summary(values, observed * 100.0, PLACEMENT_SEED, PLACEMENT_RUNS)


def circular_shift_null(dates: list[str], panel: dict[str, dict[str, object]], spread: np.ndarray,
                        entry: float, exit_: float, observed: float) -> dict[str, object]:
    rng = np.random.default_rng(SHIFT_SEED)
    start_i = dates.index(START)
    raw = make_targets(spread, entry, exit_, start_i)
    enter = np.zeros(len(raw), dtype=bool)
    leave = np.zeros(len(raw), dtype=bool)
    for i in range(start_i, len(raw)):
        if i == start_i:
            enter[i] = False
            leave[i] = False
        else:
            enter[i] = np.isfinite(spread[i]) and spread[i] <= entry
            leave[i] = np.isfinite(spread[i]) and spread[i] >= exit_
    values, length = [], len(raw)
    for offset in rng.integers(1, length, size=SHIFT_RUNS):
        shifted_enter = np.roll(enter, int(offset))
        shifted_leave = np.roll(leave, int(offset))
        target = np.ones(length, dtype=float)
        state = 1.0
        for i in range(start_i, length):
            if shifted_enter[i]:
                state = 0.0
            elif shifted_leave[i]:
                state = 1.0
            target[i] = state
        values.append(float(run_one(dates, panel, target)["excess_return"]) * 100.0)
    return _null_summary(values, observed * 100.0, SHIFT_SEED, SHIFT_RUNS)


def _null_summary(values: list[float], observed: float, seed: int, runs: int) -> dict[str, object]:
    ordered = sorted(values)
    percentile = 100.0 * sum(value <= observed for value in values) / len(values)
    return {"runs": runs, "seed": seed, "percentile": percentile,
            "range_min_pp": min(ordered), "range_max_pp": max(ordered),
            "observed_excess_pp": observed}


def _decision(look: dict[str, object], flatness: str, cost2: float, delay: float,
              placement: dict[str, object], circular: dict[str, object],
              annual: dict[str, float], spy_annual: dict[str, float]) -> dict[str, object]:
    checks = {
        "lookahead_and_causality": bool(look["lookahead_shift_assert"] and look["prefix_invariance_assert"]),
        "flatness": flatness == "pass",
        "cost_2x_excess_positive": cost2 > 0,
        "delay_plus_1_excess_positive": delay > 0,
        "random_placement_at_least_95th": float(placement["percentile"]) >= 95.0,
        "circular_shift_at_least_95th": float(circular["percentile"]) >= 95.0,
        "bear_2018_strategy_ge_spy": annual.get("2018", -1e9) >= spy_annual.get("2018", 1e9),
        "bear_2022_strategy_ge_spy": annual.get("2022", -1e9) >= spy_annual.get("2022", 1e9),
    }
    return {"checks": checks, "train_battery_pass": all(checks.values()),
            "g_gate_status": "not_full_g_gate_test_closed_structural_items_unscored"}


def append_ledger(metrics: list[dict[str, object]], winner_index: int, code_hash: str,
                  grid_hash: str, fields: list[str], train_period: str) -> None:
    ids, count, current_fields = ledger_snapshot()
    if current_fields != fields or count != EXPECTED_LEDGER_ROWS:
        raise RuntimeError(f"Ledger changed before append: expected {EXPECTED_LEDGER_ROWS}, found {count}")
    if ids.intersection(PLANNED_IDS):
        raise RuntimeError("One or more preregistered trial IDs already exist; refusing append")
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    rows = []
    best_excess = float(metrics[winner_index]["excess_return"])
    for index, item in enumerate(metrics):
        entry, exit_ = item["entry"], item["exit"]
        metric: dict[str, object] = {
            "train_only": True, "test_rows_accessed": False,
            "entry": entry, "exit": exit_, "switches": item["switches"],
            "total_return": item["total_return"], "spy_total_return": item["spy_total_return"],
            "excess_return_pp": float(item["excess_return"]) * 100.0,
            "mdd": item["mdd"], "spy_mdd": item["spy_mdd"],
            "mdd_improvement": item["mdd_improvement"],
            "return_2018": item["annual_returns"].get("2018"),
            "spy_return_2018": item["spy_annual_returns"].get("2018"),
            "relative_2018_pp": (item["annual_returns"].get("2018", 0.0)
                                 - item["spy_annual_returns"].get("2018", 0.0)) * 100.0,
            "return_2022": item["annual_returns"].get("2022"),
            "spy_return_2022": item["spy_annual_returns"].get("2022"),
            "relative_2022_pp": (item["annual_returns"].get("2022", 0.0)
                                 - item["spy_annual_returns"].get("2022", 0.0)) * 100.0,
            "return_2008": item["annual_returns"].get("2008"),
            "spy_return_2008": item["spy_annual_returns"].get("2008"),
            "relative_2008_pp": (item["annual_returns"].get("2008", 0.0)
                                 - item["spy_annual_returns"].get("2008", 0.0)) * 100.0,
            "grid_robustness": item["grid_robustness"],
            "performance_metrics_computed": True,
        }
        if index == winner_index:
            metric["winner"] = True
            metric["robustness_battery"] = item["robustness_battery"]
            metric["decision"] = item["decision"]
        definition = {"experiment": ROUND, "grid_cell": {"entry": entry, "exit": exit_},
                      "parameter_grid": grid_definition(), "benchmark": "SPY_buy_and_hold",
                      "execution": "next_session_adjusted_open", "cutoff_inclusive": CUTOFF}
        rows.append({"trial_id": PLANNED_IDS[index], "round": ROUND, "market_group": "us_equities",
                     "utc_timestamp": now, "definition": json.dumps(definition, sort_keys=True, separators=(",", ":")),
                     "parameter_grid_hash": grid_hash, "code_sha256": code_hash,
                     "train_period": f"{START}/{CUTOFF} inclusive; TRAIN-only",
                     "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
                     "rank": "", "notes": "TRAIN_ONLY; CBOE VIX-RV20; next-session open; no TEST rows accessed"})
    with LEDGER.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    configured = os.environ.get("TRADING_DATA_DIR")
    if configured != EXPECTED_DATA_DIR:
        raise RuntimeError("TRADING_DATA_DIR must exactly match the preregistered repository data directory")
    ids, count, fields = ledger_snapshot()
    if ids.intersection(PLANNED_IDS):
        raise RuntimeError("A planned VOLREG-R1 trial ID already exists")
    if count != EXPECTED_LEDGER_ROWS:
        raise RuntimeError(f"Ledger row count changed before run: expected {EXPECTED_LEDGER_ROWS}, found {count}")
    dates, panel, vix = read_training(Path(configured))
    rv, spread = indicators(dates, panel, vix)
    start_i = dates.index(START)
    causal_cells = {}
    for entry in ENTRY:
        for exit_ in EXIT:
            candidate = make_targets(spread, entry, exit_, start_i)
            causal_cells[f"{entry:.1f}/{exit_:.1f}"] = causal_assertions(
                dates, panel, vix, spread, candidate, entry, exit_)
    causal_ok = all(item["lookahead_shift_assert"] and item["prefix_invariance_assert"]
                    for item in causal_cells.values())
    assert causal_ok, "one or more grid cells failed lookahead/causality assertions"
    causal = {"lookahead_shift_assert": all(item["lookahead_shift_assert"] for item in causal_cells.values()),
              "prefix_invariance_assert": all(item["prefix_invariance_assert"] for item in causal_cells.values()),
              "per_cell": causal_cells}

    metrics: list[dict[str, object]] = []
    for entry in ENTRY:
        for exit_ in EXIT:
            target = make_targets(spread, entry, exit_, start_i)
            result = run_one(dates, panel, target)
            result.update({"entry": entry, "exit": exit_})
            metrics.append(result)
    winner_index = max(range(len(metrics)), key=lambda i: float(metrics[i]["excess_return"]))
    winner = metrics[winner_index]
    flatness, flat_info = _flatness(metrics, winner_index)
    winner["grid_robustness"] = flatness
    for i, item in enumerate(metrics):
        if i != winner_index:
            item["grid_robustness"] = "not_winner"
    target = make_targets(spread, float(winner["entry"]), float(winner["exit"]), start_i)
    cost2 = run_one(dates, panel, target, cost=0.0012)
    delay2 = run_one(dates, panel, target, delay=2)
    placement = random_placement_null(dates, panel, int(winner["switches"]), float(winner["excess_return"]))
    circular = circular_shift_null(dates, panel, spread, float(winner["entry"]),
                                   float(winner["exit"]), float(winner["excess_return"]))
    annual, spy_annual = winner["annual_returns"], winner["spy_annual_returns"]
    decision = _decision(causal, flatness, float(cost2["excess_return"]),
                         float(delay2["excess_return"]), placement, circular, annual, spy_annual)
    switch_reliable = int(winner["switches"]) >= 5
    decision["switch_reliability"] = (
        "reliable_5_or_more" if switch_reliable
        else "unreliable_fewer_than_5_no_further_grid_expansion")
    decision["checks"]["winner_switches_at_least_5"] = switch_reliable
    decision["train_battery_pass"] = all(decision["checks"].values())
    concentration = {"annual_excess_pp": {year: (annual[year] - spy_annual[year]) * 100.0
                                           for year in annual},
                     "largest_year_share_of_positive_annual_excess": None}
    positive = [max(0.0, value) for value in concentration["annual_excess_pp"].values()]
    total_positive = sum(positive)
    if total_positive > 0:
        concentration["largest_year_share_of_positive_annual_excess"] = max(positive) / total_positive
    battery = {"lookahead_causality": causal, "flatness": {"verdict": flatness, **flat_info},
               "cost_2x_excess_pp": float(cost2["excess_return"]) * 100.0,
               "delay_plus_1_excess_pp": float(delay2["excess_return"]) * 100.0,
               "random_placement": placement, "circular_shift": circular,
               "relative_years": {year: {"strategy_pct": annual.get(year), "spy_pct": spy_annual.get(year),
                                          "relative_pp": (annual[year] - spy_annual[year]) * 100.0}
                                  for year in ("2008", "2018", "2022")},
               "return_concentration": concentration,
               "null_resolution_caveat": {"placement_min_p": 1 / 201, "shift_min_p": 1 / 1001,
                                          "bonferroni_bound": 0.05 / (count + len(metrics)),
                                          "formal_bonferroni_supported_by_null_draws": False},
               "decision": decision}
    winner["robustness_battery"] = battery
    winner["decision"] = decision
    code_hash, digest = sha256_file(RUNNER_PATH), canonical_hash(grid_definition())
    append_ledger(metrics, winner_index, code_hash, digest, fields, f"{START}/{CUTOFF}")
    summary = {"status": "complete", "rows_appended": len(metrics), "train_only": True,
               "test_rows_accessed": False, "data_window": {"start": START, "cutoff_inclusive": CUTOFF,
                                                               "sessions": len(dates)},
               "ledger_rows_before": count, "ledger_rows_after": count + len(metrics),
               "n_train_after_append": count + len(metrics), "bonferroni_reference": 0.05 / (count + len(metrics)),
               "parameter_grid_hash": digest, "code_sha256": code_hash,
               "winner_index": winner_index, "winner": {k: v for k, v in winner.items()
                                                            if k not in ("strategy_curve", "spy_curve")},
               "trials": [{k: v for k, v in item.items() if k not in ("strategy_curve", "spy_curve")}
                          for item in metrics]}
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
