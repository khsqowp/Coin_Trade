"""Gen11 fixed sector-breadth gate. No market read occurs on import."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
ALL_SYMBOLS = (*SECTORS, "SPY")
WINDOW = 200
THRESHOLD = 5
COST_BPS = 10.0


def breadth_series(sector_closes: dict[str, list[float]], window: int = WINDOW) -> list[int | None]:
    """Return strict count above trailing SMA, including the decision close."""
    if set(sector_closes) != set(SECTORS):
        raise ValueError("sector panel must contain exactly the nine frozen sector ETFs")
    lengths = {len(values) for values in sector_closes.values()}
    if len(lengths) != 1:
        raise ValueError("sector series lengths differ")
    n = lengths.pop()
    result: list[int | None] = [None] * n
    for end in range(window - 1, n):
        count = 0
        for symbol in SECTORS:
            values = sector_closes[symbol][end - window + 1 : end + 1]
            if len(values) != window or any(not math.isfinite(x) or x <= 0 for x in values):
                raise ValueError(f"invalid/missing SMA window for {symbol} at row {end}")
            sma = sum(values) / window
            if values[-1] > sma:
                count += 1
        result[end] = count
    return result


def breadth_from_closes(sector_closes: dict[str, list[float]], window: int = WINDOW) -> int:
    """Return the final breadth count; fail if a complete final window is absent."""
    values = breadth_series(sector_closes, window)
    if not values or values[-1] is None:
        raise ValueError("no complete breadth observation")
    return int(values[-1])


def next_open_targets(close_signals: list[int | None]) -> list[int | None]:
    """Map each completed-close signal to the next session's open, never same-day."""
    return [None, *close_signals[:-1]] if close_signals else []


def net_open_interval_returns(
    adjusted_opens: list[float],
    open_targets: list[int | None],
    cost_bps: float = COST_BPS,
) -> list[float]:
    """Build daily net returns, charging exposure changes at opens and terminal exit.

    `open_targets[i]` is the known exposure at open i. A None at the first row
    represents the untradable pre-signal open. The target at the final open is
    intentionally ignored because no subsequent holding interval exists; any
    live exposure carried into that final open is liquidated there. No gaps are repaired.
    """
    if len(adjusted_opens) != len(open_targets) or len(adjusted_opens) < 2:
        raise ValueError("open prices and target schedule must have equal length >= 2")
    if any(not math.isfinite(x) or x <= 0 for x in adjusted_opens):
        raise ValueError("adjusted opens must be finite and positive")
    if any(x not in (None, 0, 1) for x in open_targets):
        raise ValueError("target exposure must be None, 0, or 1")
    first = next((i for i, target in enumerate(open_targets[:-1]) if target is not None), None)
    if first is None:
        raise ValueError("no tradable signal interval")
    if any(x is None for x in open_targets[first:-1]):
        raise ValueError("missing target inside measured schedule")
    cost = cost_bps / 10_000.0
    if not 0 <= cost < 1:
        raise ValueError("invalid transaction cost")
    targets = [int(x) for x in open_targets[first:-1]]
    opens = adjusted_opens[first:]
    net: list[float] = []
    previous = 0
    for i, (start_open, end_open) in enumerate(zip(opens, opens[1:])):
        target = targets[i]
        entry_factor = 1.0 - abs(target - previous) * cost
        gross_factor = 1.0 + target * (end_open / start_open - 1.0)
        end_factor = 1.0
        if i == len(opens) - 2 and targets[-1] == 1:
            end_factor -= cost
        net.append(entry_factor * gross_factor * end_factor - 1.0)
        previous = target
    return net


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_freeze(data_dir: Path, folder: Path) -> dict:
    """Fail closed unless reviewer GO and every prereg/code/data hash matches."""
    freeze_path = folder / "FREEZE.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("review_status") != "GO":
        raise RuntimeError("independent reviewer GO is required before market data access")
    expected = {
        "prereg_sha256": sha256(folder / "PREREG.md"),
        "addendum_sha256": sha256(folder / "ADDENDUM_A1.md"),
        "runner_sha256": sha256(folder / "run_gen11.py"),
        "tests_sha256": sha256(folder / "test_gen11.py"),
    }
    if freeze.get("artifacts") != expected:
        raise RuntimeError("preregistration, runner, or tests differ from frozen hashes")
    expected_inputs = freeze.get("inputs_sha256", {})
    if set(expected_inputs) != {f"{s}.parquet" for s in ALL_SYMBOLS}:
        raise RuntimeError("frozen data fingerprint does not cover all ten inputs")
    actual_inputs = {f"{s}.parquet": sha256(data_dir / f"{s}.parquet") for s in ALL_SYMBOLS}
    if actual_inputs != expected_inputs:
        raise RuntimeError("local market snapshot differs from frozen data hashes")
    return freeze


def _load_prices(data_dir: Path):
    # Import only when invoked: unit tests for the frozen rule use synthetic lists.
    import pandas as pd

    frames = {}
    for symbol in ALL_SYMBOLS:
        path = data_dir / f"{symbol}.parquet"
        frame = pd.read_parquet(path)
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise ValueError(f"{symbol}: index must be a pandas DatetimeIndex")
        required = {"open", "high", "low", "close", "adjclose"}
        if not required.issubset(frame.columns):
            raise ValueError(f"{symbol}: missing required columns {sorted(required-set(frame.columns))}")
        if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
            raise ValueError(f"{symbol}: date index must be unique and ascending")
        values = frame[["open", "high", "low", "close", "adjclose"]].astype(float)
        if not _finite_positive_frame(values):
            raise ValueError(f"{symbol}: non-finite/non-positive price")
        if not ((values["high"] >= values[["open", "close", "low"]].max(axis=1)).all()
                and (values["low"] <= values[["open", "close", "high"]].min(axis=1)).all()):
            raise ValueError(f"{symbol}: invalid raw OHLC bounds")
        frames[symbol] = values
    index = frames["SPY"].index
    for symbol in SECTORS:
        if not frames[symbol].index.equals(index):
            raise ValueError(f"{symbol}: date index differs from frozen common SPY/sector calendar")
    return index, frames


def _metrics(returns: list[float]) -> dict[str, float | int]:
    if not returns:
        raise ValueError("empty metric interval")
    wealth = 1.0
    peak = 1.0
    mdd = 0.0
    for value in returns:
        if not math.isfinite(value) or value <= -1:
            raise ValueError("invalid net return")
        wealth *= 1 + value
        peak = max(peak, wealth)
        mdd = min(mdd, wealth / peak - 1)
    mean = sum(returns) / len(returns)
    variance = sum((x - mean) ** 2 for x in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    stdev = math.sqrt(variance)
    years = len(returns) / 252.0
    return {
        "intervals": len(returns),
        "total_return": wealth - 1,
        "cagr": wealth ** (1 / years) - 1 if wealth > 0 and years > 0 else -1.0,
        "sharpe": mean / stdev * math.sqrt(252) if stdev > 0 else 0.0,
        "mdd": mdd,
    }


def append_attempt_event(path: Path, event: dict) -> None:
    """Append one durable JSONL event; never truncate an existing attempt log."""
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_manifest_atomic(path: Path, manifest: dict) -> None:
    """Create/update only this run's manifest using a same-directory atomic replace."""
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _finite_positive_frame(values) -> bool:
    """Check pandas-like numeric frame without removed DataFrame.applymap API."""
    matrix = values.to_numpy(dtype=float)
    return all(math.isfinite(float(value)) and float(value) > 0 for row in matrix for value in row)


def _activity_counts(targets: list[int]) -> dict[str, int | float]:
    previous = 0
    entries = 0
    exits = 0
    turnover = 0.0
    for target in targets:
        if previous == 0 and target == 1:
            entries += 1
        elif previous == 1 and target == 0:
            exits += 1
        turnover += abs(target - previous)
        previous = target
    terminal = int(previous == 1)
    turnover += terminal
    return {
        "entries_including_initial_if_invested": entries,
        "signal_driven_exits": exits,
        "terminal_liquidations": terminal,
        "turnover_units_including_entry_and_terminal_exit": turnover,
        "measured_open_to_open_intervals": len(targets),
        "mean_exposure": sum(targets) / len(targets) if targets else 0.0,
    }


def run(data_dir: Path, out_dir: Path, run_id: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", run_id):
        raise ValueError("run_id must be 1-101 safe ASCII letters, digits, dot, underscore, or hyphen")
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = out_dir / f"attempts_{run_id}.jsonl"
    manifest_path = out_dir / f"manifest_{run_id}.json"
    curve_path = out_dir / f"curve_{run_id}.csv.gz"
    rejected_ledger = out_dir / "attempts_rejected.jsonl"
    if any(path.exists() for path in (ledger, manifest_path, curve_path, manifest_path.with_suffix(".json.tmp"))):
        append_attempt_event(rejected_ledger, {
            "event": "REJECTED_DUPLICATE_RUN_ID", "run_id": run_id,
            "utc": datetime.now(timezone.utc).isoformat(),
        })
        raise FileExistsError(f"run ID already has artifacts; refusing to overwrite: {run_id}")

    started = datetime.now(timezone.utc).isoformat()
    append_attempt_event(ledger, {"event": "STARTED", "run_id": run_id, "utc": started})
    manifest = {"run_id": run_id, "status": "STARTED", "created_utc": started}
    try:
        write_manifest_atomic(manifest_path, manifest)
        # This verifies GO and immutable hashes before opening any parquet values.
        freeze = verify_freeze(data_dir, Path(__file__).parent)
        inputs = freeze["inputs_sha256"]
        import pandas as pd

        index, frames = _load_prices(data_dir)
        sector_closes = {s: frames[s]["adjclose"].tolist() for s in SECTORS}
        breadth = breadth_series(sector_closes)
        close_signals = [None if value is None else int(value >= THRESHOLD) for value in breadth]
        open_targets = next_open_targets(close_signals)
        spy = frames["SPY"]
        adj_open = (spy["open"] * spy["adjclose"] / spy["close"]).tolist()
        first_valid = next((i for i, target in enumerate(open_targets[:-1]) if target is not None), None)
        if first_valid is None:
            raise ValueError("no complete post-SMA200 SPY interval")
        measured_dates = index[first_valid:]
        strategy_returns = net_open_interval_returns(adj_open[first_valid:], open_targets[first_valid:])
        benchmark_returns = net_open_interval_returns(adj_open[first_valid:], [1] * len(adj_open[first_valid:]))
        interval_dates = measured_dates[:-1]
        windows = {
            "full": lambda d: True,
            "2001_2016_descriptive_contaminated": lambda d: "2001-01-01" <= d.strftime("%Y-%m-%d") <= "2016-12-31",
            "2017_plus_descriptive_contaminated": lambda d: d.strftime("%Y-%m-%d") >= "2017-01-01",
        }
        report = {name: {"strategy": _metrics([r for d, r in zip(interval_dates, strategy_returns) if predicate(d)]),
                         "spy_buy_hold": _metrics([r for d, r in zip(interval_dates, benchmark_returns) if predicate(d)])}
                  for name, predicate in windows.items()}
        targets = [int(x) for x in open_targets[first_valid:-1]]
        evaluated_breadth = breadth[first_valid - 1 : -2]
        activity = _activity_counts(targets)
        activity["valid_breadth_observations"] = sum(value is not None for value in evaluated_breadth)
        activity["risk_on_close_signals"] = sum(value == 1 for value in close_signals[first_valid - 1 : -2])
        result = {
            "run_id": run_id,
            "status": "COMPLETED_EXPLORATORY",
            "prereg_sha256": freeze["artifacts"]["prereg_sha256"],
            "addendum_sha256": freeze["artifacts"]["addendum_sha256"],
            "runner_sha256": freeze["artifacts"]["runner_sha256"],
            "tests_sha256": freeze["artifacts"]["tests_sha256"],
            "inputs_sha256": inputs,
            "snapshot_note": "local Yahoo-derived non-atomic snapshot; not authoritative/untouched OOS",
            "dates": {"first": str(interval_dates[0].date()), "last": str(interval_dates[-1].date()), "intervals": len(interval_dates)},
            "windows": report,
            "breadth": {"threshold": THRESHOLD, "window": WINDOW, **activity},
        }
        curve = pd.DataFrame({"date": [str(d.date()) for d in interval_dates], "breadth": evaluated_breadth,
                              "target_open_exposure": targets, "strategy_net_return": strategy_returns,
                              "spy_net_return": benchmark_returns})
        curve.to_csv(curve_path, index=False, compression="gzip")
        manifest = {"run_id": run_id, "status": "COMPLETED_EXPLORATORY", "created_utc": started,
                    "finished_utc": datetime.now(timezone.utc).isoformat(), "result": result}
        write_manifest_atomic(manifest_path, manifest)
        append_attempt_event(ledger, {"event": "FINISHED", "run_id": run_id,
                                      "utc": manifest["finished_utc"], "status": "COMPLETED_EXPLORATORY"})
        return result
    except BaseException as exc:
        failure = {"event": "FAILED", "run_id": run_id, "utc": datetime.now(timezone.utc).isoformat(),
                   "error_type": type(exc).__name__, "error": str(exc)}
        try:
            append_attempt_event(ledger, failure)
            manifest = {"run_id": run_id, "status": "FAILED", "created_utc": started,
                        "failed_utc": failure["utc"], "error_type": failure["error_type"],
                        "error": failure["error"]}
            write_manifest_atomic(manifest_path, manifest)
        except BaseException:
            # Preserve the original exception; STARTED is already durable.
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parents[1] / "data_mirror" / "us_daily")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    result = run(args.data_dir, Path(__file__).parent, args.run_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
