"""Gen11 A2: frozen sector-breadth candidate on a strict common calendar."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from run_gen11 import (
    ALL_SYMBOLS,
    COST_BPS,
    SECTORS,
    THRESHOLD,
    WINDOW,
    _activity_counts,
    _metrics,
    append_attempt_event,
    breadth_series,
    net_open_interval_returns,
    next_open_targets,
    sha256,
    write_manifest_atomic,
)


def align_common_calendar(frames: dict[str, pd.DataFrame]) -> tuple[pd.DatetimeIndex, dict[str, pd.DataFrame]]:
    """Intersect the ten source calendars and align by exact dates only.

    Source date indexes must each be DatetimeIndex, unique, and ascending.
    No reindex fill, forward-fill, or interpolation is permitted. The returned
    frames all carry exactly the ten-way intersection in the same order.
    """
    if set(frames) != set(ALL_SYMBOLS):
        raise ValueError("frames must contain exactly the nine sectors and SPY")
    for symbol in ALL_SYMBOLS:
        index = frames[symbol].index
        if not isinstance(index, pd.DatetimeIndex):
            raise ValueError(f"{symbol}: index must be a pandas DatetimeIndex")
        if index.has_duplicates:
            raise ValueError(f"{symbol}: date index must be unique")
        if not index.is_monotonic_increasing:
            raise ValueError(f"{symbol}: date index must be strictly ascending")

    common = frames[ALL_SYMBOLS[0]].index
    for symbol in ALL_SYMBOLS[1:]:
        common = common.intersection(frames[symbol].index)
    common = common.sort_values()
    if len(common) == 0:
        raise ValueError("empty common calendar across the ten frozen instruments")
    aligned = {symbol: frames[symbol].loc[common].copy() for symbol in ALL_SYMBOLS}
    for symbol, frame in aligned.items():
        if not frame.index.equals(common):
            raise ValueError(f"{symbol}: aligned index does not equal the common calendar")
    return common, aligned


def verify_freeze_a2(data_dir: Path, folder: Path) -> dict:
    """Require independent GO and exact source, test, and input fingerprints."""
    freeze = json.loads((folder / "FREEZE_A2.json").read_text(encoding="utf-8"))
    if freeze.get("review_status") != "GO":
        raise RuntimeError("independent reviewer GO is required before market data access")
    expected = {
        "prereg_sha256": sha256(folder / "PREREG.md"),
        "addendum_a1_sha256": sha256(folder / "ADDENDUM_A1.md"),
        "addendum_a2_sha256": sha256(folder / "ADDENDUM_A2.md"),
        "addendum_a3_sha256": sha256(folder / "ADDENDUM_A3.md"),
        "runner_a1_sha256": sha256(folder / "run_gen11.py"),
        "tests_a1_sha256": sha256(folder / "test_gen11.py"),
        "runner_a2_sha256": sha256(folder / "run_gen11_a2.py"),
        "tests_a2_sha256": sha256(folder / "test_gen11_a2.py"),
    }
    if freeze.get("artifacts") != expected:
        raise RuntimeError("A2 preregistration, runner, tests, or dependency differs from frozen hashes")
    expected_inputs = freeze.get("inputs_sha256", {})
    if set(expected_inputs) != {f"{symbol}.parquet" for symbol in ALL_SYMBOLS}:
        raise RuntimeError("frozen data fingerprint does not cover all ten inputs")
    actual_inputs = {f"{symbol}.parquet": sha256(data_dir / f"{symbol}.parquet") for symbol in ALL_SYMBOLS}
    if actual_inputs != expected_inputs:
        raise RuntimeError("local market snapshot differs from frozen data hashes")
    return freeze


def _load_prices_a2(data_dir: Path) -> tuple[pd.DatetimeIndex, dict[str, pd.DataFrame]]:
    raw_frames = {symbol: pd.read_parquet(data_dir / f"{symbol}.parquet") for symbol in ALL_SYMBOLS}
    required = {"open", "high", "low", "close", "adjclose"}
    # Keep the original preregistered integrity gate on every source row, even
    # when a date is later excluded by the ten-way calendar intersection.
    for symbol, frame in raw_frames.items():
        if not required.issubset(frame.columns):
            raise ValueError(f"{symbol}: missing required columns {sorted(required - set(frame.columns))}")
        values = frame[["open", "high", "low", "close", "adjclose"]].astype(float)
        matrix = values.to_numpy(dtype=float)
        if not all(math.isfinite(float(value)) and float(value) > 0 for row in matrix for value in row):
            raise ValueError(f"{symbol}: non-finite/non-positive price in source data")
        if not (
            (values["high"] >= values[["open", "close", "low"]].max(axis=1)).all()
            and (values["low"] <= values[["open", "close", "high"]].min(axis=1)).all()
        ):
            raise ValueError(f"{symbol}: invalid raw OHLC bounds in source data")
    common, frames = align_common_calendar(raw_frames)
    for symbol, frame in frames.items():
        frames[symbol] = frame[["open", "high", "low", "close", "adjclose"]].astype(float)
    return common, frames


def run_a2(data_dir: Path, out_dir: Path, run_id: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", run_id):
        raise ValueError("run_id must be 1-101 safe ASCII letters, digits, dot, underscore, or hyphen")
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = out_dir / f"attempts_{run_id}.jsonl"
    manifest_path = out_dir / f"manifest_{run_id}.json"
    curve_path = out_dir / f"curve_{run_id}.csv.gz"
    if any(path.exists() for path in (ledger, manifest_path, curve_path, manifest_path.with_suffix(".json.tmp"))):
        raise FileExistsError(f"run ID already has artifacts; refusing to overwrite: {run_id}")

    started = datetime.now(timezone.utc).isoformat()
    append_attempt_event(ledger, {"event": "STARTED", "run_id": run_id, "utc": started})
    try:
        write_manifest_atomic(manifest_path, {"run_id": run_id, "status": "STARTED", "created_utc": started})
        freeze = verify_freeze_a2(data_dir, Path(__file__).parent)
        index, frames = _load_prices_a2(data_dir)
        if len(index) < WINDOW + 1:
            raise ValueError("common calendar needs at least 200 closes and one subsequent interval")

        sector_closes = {symbol: frames[symbol]["adjclose"].tolist() for symbol in SECTORS}
        breadth = breadth_series(sector_closes)
        close_signals = [None if count is None else int(count >= THRESHOLD) for count in breadth]
        open_targets = next_open_targets(close_signals)
        spy = frames["SPY"]
        adjusted_open = (spy["open"] * spy["adjclose"] / spy["close"]).tolist()
        first_valid = next((i for i, target in enumerate(open_targets[:-1]) if target is not None), None)
        if first_valid is None:
            raise ValueError("common calendar has no complete post-SMA200 SPY interval")
        measured_dates = index[first_valid:]
        strategy_returns = net_open_interval_returns(adjusted_open[first_valid:], open_targets[first_valid:])
        benchmark_returns = net_open_interval_returns(adjusted_open[first_valid:], [1] * len(adjusted_open[first_valid:]))
        interval_dates = measured_dates[:-1]
        windows = {
            "full": lambda date: True,
            "2001_2016_descriptive_contaminated": lambda date: "2001-01-01" <= date.strftime("%Y-%m-%d") <= "2016-12-31",
            "2017_plus_descriptive_contaminated": lambda date: date.strftime("%Y-%m-%d") >= "2017-01-01",
        }
        report = {
            name: {
                "strategy": _metrics([value for date, value in zip(interval_dates, strategy_returns) if predicate(date)]),
                "spy_buy_hold": _metrics([value for date, value in zip(interval_dates, benchmark_returns) if predicate(date)]),
            }
            for name, predicate in windows.items()
        }
        targets = [int(value) for value in open_targets[first_valid:-1]]
        evaluated_breadth = breadth[first_valid - 1 : -2]
        activity = _activity_counts(targets)
        activity["valid_breadth_observations"] = sum(value is not None for value in evaluated_breadth)
        activity["risk_on_close_signals"] = sum(value == 1 for value in close_signals[first_valid - 1 : -2])
        result = {
            "run_id": run_id,
            "status": "COMPLETED_EXPLORATORY",
            "revision": "A2-common-calendar",
            "prereg_sha256": freeze["artifacts"]["prereg_sha256"],
            "addendum_a1_sha256": freeze["artifacts"]["addendum_a1_sha256"],
            "addendum_a2_sha256": freeze["artifacts"]["addendum_a2_sha256"],
            "addendum_a3_sha256": freeze["artifacts"]["addendum_a3_sha256"],
            "runner_a2_sha256": freeze["artifacts"]["runner_a2_sha256"],
            "tests_a2_sha256": freeze["artifacts"]["tests_a2_sha256"],
            "inputs_sha256": freeze["inputs_sha256"],
            "snapshot_note": "local Yahoo-derived non-atomic snapshot; not authoritative/untouched OOS",
            "calendar": {
                "alignment": "exact ten-way date intersection; no fill or interpolation",
                "first": str(interval_dates[0].date()),
                "last": str(interval_dates[-1].date()),
                "common_sessions": len(index),
                "measured_intervals": len(interval_dates),
            },
            "windows": report,
            "breadth": {"threshold": THRESHOLD, "window": WINDOW, **activity},
        }
        curve = pd.DataFrame({
            "date": [str(date.date()) for date in interval_dates],
            "breadth": evaluated_breadth,
            "target_open_exposure": targets,
            "strategy_net_return": strategy_returns,
            "spy_net_return": benchmark_returns,
        })
        curve.to_csv(curve_path, index=False, compression="gzip")
        finished = datetime.now(timezone.utc).isoformat()
        write_manifest_atomic(manifest_path, {
            "run_id": run_id,
            "status": "COMPLETED_EXPLORATORY",
            "created_utc": started,
            "finished_utc": finished,
            "result": result,
        })
        append_attempt_event(ledger, {"event": "FINISHED", "run_id": run_id, "utc": finished, "status": "COMPLETED_EXPLORATORY"})
        return result
    except BaseException as exc:
        failed = {
            "event": "FAILED",
            "run_id": run_id,
            "utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        try:
            append_attempt_event(ledger, failed)
            write_manifest_atomic(manifest_path, {
                "run_id": run_id,
                "status": "FAILED",
                "created_utc": started,
                "failed_utc": failed["utc"],
                "error_type": failed["error_type"],
                "error": failed["error"],
            })
        except BaseException:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent.parent / "data_mirror" / "us_daily")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(run_a2(args.data_dir, Path(__file__).parent, args.run_id), indent=2))


if __name__ == "__main__":
    main()
