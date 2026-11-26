#!/usr/bin/env python3
"""Run the preregistered ETF regime hedge grid on TRAIN-only local data."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds


ROOT = Path(__file__).resolve().parents[3]
LOOP = Path(__file__).resolve().parent
EXPECTED_DATA_DIR = "/Users/user/CODE/Coin_Trade/trading_data"
ETF_REL = "external/equities/us/yahoo_daily_us_etf.parquet"
CBOE_REL = "external/equities/vix/cboe_index_history.parquet"
FRED_REL = "external/equities/macro/fred_series.parquet"
LEDGER = LOOP / "TRAIN_TRIALS.csv"
CUTOFF = "2026-06-01"
START = "2002-07-30"
ROUND = "ETF-REGIME-HEDGE-V1"
THRESHOLDS = (20.0, 25.0, 30.0)
EXPECTED_LEDGER_ROWS = 4201
COST_PER_SIDE = 0.0006


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def grid_hash() -> str:
    payload = {
        "risk_assets": {"SPY": 0.5, "QQQ": 0.5},
        "safe_asset": "SHY",
        "signal": "CBOE:VIX daily close; FRED:VIXCLS cross-check only",
        "thresholds": list(THRESHOLDS),
        "start": START,
        "cutoff_inclusive": CUTOFF,
        "one_session_signal_lag": True,
        "round_trip_bps": 12,
        "execution": "next_SPY_session_open",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def ledger_ids_and_count() -> tuple[set[str], int, list[str]]:
    csv.field_size_limit(sys.maxsize)
    with LEDGER.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = [
            "trial_id", "round", "market_group", "utc_timestamp", "definition",
            "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes",
        ]
        if reader.fieldnames != fields:
            raise RuntimeError("TRAIN_TRIALS.csv header does not match the registered 11-column format")
        ids: set[str] = set()
        count = 0
        for row in reader:
            count += 1
            ids.add(row["trial_id"])
    return ids, count, fields


def read_training_data(data_root: Path) -> tuple[list[dict[str, object]], dict[str, float], dict[str, str]]:
    cutoff = pa.scalar(datetime.fromisoformat(CUTOFF), type=pa.timestamp("ns"))
    start = pa.scalar(datetime.fromisoformat(START), type=pa.timestamp("ns"))
    prices_ds = ds.dataset(data_root / ETF_REL, format="parquet")
    needed = {"ticker", "date", "open", "close", "adj_close", "dividends", "stock_splits", "capital_gains"}
    missing = sorted(needed - set(prices_ds.schema.names))
    if missing:
        raise RuntimeError(f"ETF price schema missing required columns: {missing}")
    price_filter = (
        (ds.field("date") >= start)
        & (ds.field("date") <= cutoff)
        & ds.field("ticker").isin(["SPY", "QQQ", "SHY"])
    )
    prices = prices_ds.to_table(filter=price_filter, columns=sorted(needed)).to_pylist()
    prices_by_ticker: dict[str, dict[str, dict[str, object]]] = {x: {} for x in ("SPY", "QQQ", "SHY")}
    for row in prices:
        date = row["date"].date().isoformat()
        ticker = row["ticker"]
        if row["open"] is None or row["close"] in (None, 0) or row["adj_close"] is None:
            raise RuntimeError(f"Invalid price/corporate-action input for {ticker} {date}")
        prices_by_ticker[ticker][date] = row

    sessions = sorted(prices_by_ticker["SPY"])
    if not sessions:
        raise RuntimeError("No SPY TRAIN rows in the preregistered period")
    for session in sessions:
        for ticker in ("QQQ", "SHY"):
            if session not in prices_by_ticker[ticker]:
                raise RuntimeError(f"Missing {ticker} price on SPY session {session}; no fill/interpolation allowed")

    vix_ds = ds.dataset(data_root / CBOE_REL, format="parquet")
    required_vix = {"index", "date", "close"}
    if not required_vix.issubset(vix_ds.schema.names):
        raise RuntimeError(f"CBOE VIX input schema missing {sorted(required_vix - set(vix_ds.schema.names))}")
    vix_table = vix_ds.to_table(
        filter=(ds.field("index") == "VIX") & (ds.field("date") <= cutoff),
        columns=["date", "close"],
    )
    vix = {
        row["date"].date().isoformat(): float(row["close"])
        for row in vix_table.to_pylist()
        if row["close"] is not None
    }

    fred_ds = ds.dataset(data_root / FRED_REL, format="parquet")
    if not {"series", "date", "value"}.issubset(fred_ds.schema.names):
        raise RuntimeError("FRED input lacks series/date/value columns needed for the local cross-check")
    fred_table = fred_ds.to_table(
        filter=(ds.field("series") == "VIXCLS") & (ds.field("date") <= cutoff),
        columns=["date", "value"],
    )
    fred = {
        row["date"].date().isoformat(): float(row["value"])
        for row in fred_table.to_pylist()
        if row["value"] is not None
    }
    overlap = sorted(set(vix) & set(fred))
    mismatch = [(date, vix[date], fred[date]) for date in overlap if abs(vix[date] - fred[date]) > 0.01]
    if mismatch:
        raise RuntimeError(f"CBOE/FRED TRAIN cross-check has {len(mismatch)} mismatches; first={mismatch[:5]}")
    if not overlap:
        raise RuntimeError("CBOE VIX and FRED VIXCLS have no overlapping TRAIN observations")

    prices_by_date: list[dict[str, object]] = []
    for session in sessions:
        row: dict[str, object] = {"date": session}
        for ticker in ("SPY", "QQQ", "SHY"):
            item = prices_by_ticker[ticker][session]
            adjusted_open = float(item["open"]) * float(item["adj_close"]) / float(item["close"])
            if adjusted_open <= 0:
                raise RuntimeError(f"Non-positive adjusted open for {ticker} {session}")
            row[ticker] = adjusted_open
        prices_by_date.append(row)

    return prices_by_date, vix, {
        "price_rows": str(len(prices)),
        "sessions": str(len(sessions)),
        "vix_train_rows": str(len(vix)),
        "fred_vix_train_rows": str(len(fred)),
        "vix_fred_overlap": str(len(overlap)),
        "vix_fred_mismatches": str(len(mismatch)),
        "first_session": sessions[0],
        "last_session": sessions[-1],
    }


def target_weights(signal: float, threshold: float) -> dict[str, float]:
    if signal >= threshold:
        return {"SPY": 0.0, "QQQ": 0.0, "SHY": 1.0}
    return {"SPY": 0.5, "QQQ": 0.5, "SHY": 0.0}


def regime(signal: float, threshold: float) -> str:
    return "safe" if signal >= threshold else "risk"


def signal_for_session(session: str, vix_dates: list[str], vix: dict[str, float]) -> float:
    position = bisect_left(vix_dates, session) - 1
    if position < 0:
        raise RuntimeError(f"No completed VIX close before execution session {session}")
    return vix[vix_dates[position]]


def drawdown(nav: list[float]) -> float:
    peak = nav[0]
    worst = 0.0
    for value in nav:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def run_one(
    rows: list[dict[str, object]], vix_dates: list[str], vix: dict[str, float], threshold: float
) -> dict[str, object]:
    tickers = ("SPY", "QQQ", "SHY")
    first_signal = signal_for_session(str(rows[0]["date"]), vix_dates, vix)
    current_regime = regime(first_signal, threshold)
    weights = target_weights(first_signal, threshold)
    nav = 100.0 * (1.0 - COST_PER_SIDE * sum(weights.values()))
    curve = [nav]
    switches = 0
    order_fills = sum(1 for value in weights.values() if value > 0)
    total_cost = 100.0 - nav
    last_weights = weights.copy()

    for index in range(1, len(rows)):
        previous = rows[index - 1]
        current = rows[index]
        returns = {
            ticker: float(current[ticker]) / float(previous[ticker]) - 1.0
            for ticker in tickers
        }
        pretrade_weights = {
            ticker: last_weights[ticker] * (1.0 + returns[ticker])
            for ticker in tickers
        }
        growth = sum(pretrade_weights.values())
        if growth <= 0:
            raise RuntimeError(f"Portfolio NAV became non-positive at {current['date']}")
        nav *= growth
        current_weights = {ticker: pretrade_weights[ticker] / growth for ticker in tickers}

        signal = signal_for_session(str(current["date"]), vix_dates, vix)
        new_regime = regime(signal, threshold)
        if new_regime != current_regime:
            new_weights = target_weights(signal, threshold)
            turnover = sum(abs(new_weights[t] - current_weights[t]) for t in tickers)
            changed = [t for t in tickers if abs(new_weights[t] - current_weights[t]) > 1e-8]
            switches += 1
            order_fills += len(changed)
            cost = COST_PER_SIDE * turnover
            cost_amount = nav * cost
            nav -= cost_amount
            total_cost += cost_amount
            last_weights = new_weights
            current_regime = new_regime
        else:
            last_weights = current_weights
        curve.append(nav)

    end_turnover = sum(last_weights.values())
    end_cost = COST_PER_SIDE * end_turnover
    end_cost_amount = nav * end_cost
    nav -= end_cost_amount
    total_cost += end_cost_amount
    order_fills += sum(1 for value in last_weights.values() if value > 0)

    annual: dict[str, float] = {}
    for year in sorted({str(row["date"])[:4] for row in rows}):
        indexes = [i for i, row in enumerate(rows) if str(row["date"]).startswith(year)]
        first_i, last_i = indexes[0], indexes[-1]
        start_nav = curve[first_i - 1] if first_i > 0 else 100.0
        annual[year] = curve[last_i] / start_nav - 1.0

    return {
        "threshold": threshold,
        "status": "scorable_train_only",
        "trade_count": switches,
        "regime_switches": switches,
        "order_fill_count_including_initial_and_final": order_fills,
        "total_return": nav / 100.0 - 1.0,
        "mdd": drawdown(curve + [nav]),
        "annual_returns": annual,
        "return_2018": annual.get("2018"),
        "return_2022": annual.get("2022"),
        "total_cost_nav_units": total_cost,
    }


def spy_buy_hold(rows: list[dict[str, object]]) -> dict[str, object]:
    nav = 100.0 * (1.0 - COST_PER_SIDE)
    curve = [nav]
    for previous, current in zip(rows, rows[1:]):
        nav *= float(current["SPY"]) / float(previous["SPY"])
        curve.append(nav)
    nav *= 1.0 - COST_PER_SIDE
    annual: dict[str, float] = {}
    for year in sorted({str(row["date"])[:4] for row in rows}):
        indexes = [i for i, row in enumerate(rows) if str(row["date"]).startswith(year)]
        first_i, last_i = indexes[0], indexes[-1]
        start_nav = curve[first_i - 1] if first_i > 0 else 100.0
        annual[year] = curve[last_i] / start_nav - 1.0
    return {"total_return": nav / 100.0 - 1.0, "mdd": drawdown(curve + [nav]), "annual_returns": annual}


def append_rows(metrics: list[dict[str, object]], code_hash: str, digest: str, fields: list[str], data: dict[str, str]) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    rows = []
    best = max(metrics, key=lambda item: float(item["excess_return"]))
    excess_values = [float(item["excess_return"]) for item in metrics]
    for index, item in enumerate(metrics, start=4):
        threshold = float(item["threshold"])
        if threshold == 25.0:
            neighbor_results = [excess_values[0], excess_values[2]]
            plateau = (
                "pass" if float(best["excess_return"]) > 0
                and all(x >= 0.5 * float(best["excess_return"]) for x in neighbor_results)
                else "fail"
            )
        elif item is best:
            plateau = "grid_edge"
        else:
            plateau = "not_winner"
        item["grid_robustness"] = plateau
        definition = {
            "experiment": "ETF_REGIME_HEDGE_V1",
            "signal": "CBOE:VIX_daily_close",
            "fred_crosscheck": "VIXCLS_exact_match_on_observed_overlap",
            "risk_assets": {"SPY": 0.5, "QQQ": 0.5},
            "safe_asset": "SHY",
            "threshold": threshold,
            "execution": "next_SPY_session_open_after_prior_session_close_signal",
            "cutoff_inclusive": CUTOFF,
            "round_trip_bps": 12,
        }
        item["spy_total_return"] = metrics[0].get("spy_total_return")
        metric = {
            **item,
            "train_only": True,
            "test_rows_accessed": False,
            "performance_metrics_computed": True,
            "data_audit": data,
            "flatness_rule": "middle cell: both neighbors >=50% of winning excess return; edge winner cannot claim plateau",
        }
        rows.append({
            "trial_id": f"ETF-REGIME-HEDGE-{index + 3:02d}",
            "round": ROUND,
            "market_group": "us_equities",
            "utc_timestamp": now,
            "definition": json.dumps(definition, sort_keys=True, separators=(",", ":")),
            "parameter_grid_hash": digest,
            "code_sha256": code_hash,
            "train_period": f"{data['first_session']}/{data['last_session']} inclusive; TRAIN-only",
            "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
            "rank": "",
            "notes": "TRAIN_ONLY; CBOE VIX daily close; one-session lag; no TEST rows accessed",
        })
    with LEDGER.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    configured = os.environ.get("TRADING_DATA_DIR")
    if configured != EXPECTED_DATA_DIR:
        raise RuntimeError("TRADING_DATA_DIR must exactly match the preregistered repository data directory")
    ids, ledger_count, fields = ledger_ids_and_count()
    planned_ids = {f"ETF-REGIME-HEDGE-{i:02d}" for i in range(7, 10)}
    if ids.intersection(planned_ids):
        raise RuntimeError("A new trial ID already exists; refusing duplicate append")
    if ledger_count != EXPECTED_LEDGER_ROWS:
        raise RuntimeError(f"Ledger row count changed before run: expected {EXPECTED_LEDGER_ROWS}, found {ledger_count}")

    data_root = Path(configured)
    rows, vix, audit = read_training_data(data_root)
    if rows[0]["date"] != START or rows[-1]["date"] != CUTOFF:
        raise RuntimeError(f"Observed TRAIN coverage {rows[0]['date']}..{rows[-1]['date']} differs from registered {START}..{CUTOFF}")
    baseline = spy_buy_hold(rows)
    vix_dates = sorted(vix)
    metrics = [run_one(rows, vix_dates, vix, threshold) for threshold in THRESHOLDS]
    for item in metrics:
        item["spy_total_return"] = baseline["total_return"]
        item["spy_mdd"] = baseline["mdd"]
        item["excess_return"] = float(item["total_return"]) - baseline["total_return"]
        item["mdd_improvement"] = float(item["mdd"]) - baseline["mdd"]
        item["spy_annual_returns"] = baseline["annual_returns"]
        item["train_screen_result"] = "fail_lt_200_regime_switches" if int(item["trade_count"]) < 200 else "not_fully_evaluated"
    append_rows(metrics, sha256_file(Path(__file__)), grid_hash(), fields, audit)
    print(json.dumps({"status": "complete", "rows_appended": 3, "data_audit": audit,
                      "spy_buy_hold": baseline, "trials": metrics}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
