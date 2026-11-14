"""Generation 11 dual-momentum ETF allocation; exploratory research only."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data_mirror" / "us_daily"
SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")
FEE_PER_SIDE = 0.001
LOOKBACK = 252
SKIP = 21
ANNUAL_SESSIONS = 252
ATTEMPT_ID = "GEN11A1-DUALMOM-US_INDEX_ETF_12_1_CASH"


def momentum_score(adjusted_closes: list[float], t: int) -> float:
    """12-1 momentum at zero-based row t: adjclose[t-21] / adjclose[t-252] - 1."""
    if t < LOOKBACK or t >= len(adjusted_closes):
        raise ValueError("t must have the full 252-row lookback")
    old, recent = adjusted_closes[t - LOOKBACK], adjusted_closes[t - SKIP]
    if old is None or recent is None or not math.isfinite(old) or not math.isfinite(recent) or old <= 0:
        raise ValueError("momentum endpoints must be finite and denominator positive")
    return recent / old - 1.0


def validate_ordered_dates(dates) -> None:
    """Fail closed on unsorted/duplicate source dates; never repair input order."""
    values = list(dates)
    if any(values[i] <= values[i - 1] for i in range(1, len(values))):
        raise ValueError("source dates must already be strictly increasing and unique")


def choose_target(scores: dict[str, float | None]) -> str | None:
    """Hold the highest 12-1 ETF only if its score is positive; None means cash."""
    if set(scores) != set(SYMBOLS):
        raise ValueError(f"scores must cover fixed universe {SYMBOLS}")
    if any(v is None or not math.isfinite(float(v)) for v in scores.values()):
        raise ValueError("all four ETF scores must be finite; do not shrink the universe")
    # Sorting the symbols first makes exact ties deterministic without using future data.
    leader = max(sorted(SYMBOLS), key=lambda symbol: float(scores[symbol]))
    return leader if float(scores[leader]) > 0 else None


def rebalance_cost(previous: str | None, target: str | None, fee_per_side: float = FEE_PER_SIDE) -> float:
    """Portfolio-level multiplicative fee estimate; switches pay one sell and one buy."""
    if not math.isfinite(fee_per_side) or fee_per_side < 0 or fee_per_side >= 1:
        raise ValueError("fee must be finite and in [0, 1)")
    if previous == target:
        return 0.0
    if previous is None or target is None:
        return fee_per_side
    return 2.0 * fee_per_side


def rebalance_turnover(previous: str | None, target: str | None) -> float:
    if previous == target:
        return 0.0
    if previous is None or target is None:
        return 1.0
    return 2.0


def apply_open_interval(nav: float, previous: str | None, target: str | None,
                        gross_return: float, fee_per_side: float = FEE_PER_SIDE) -> tuple[float, float]:
    """Apply open-time turnover costs and gross open-to-open P&L to prior NAV."""
    if not math.isfinite(nav) or nav <= 0 or not math.isfinite(gross_return) or gross_return <= 0:
        raise ValueError("NAV and gross return must be finite and positive")
    next_nav = nav * (1.0 - rebalance_cost(previous, target, fee_per_side)) * gross_return
    return next_nav, next_nav / nav - 1.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_freeze_and_review() -> tuple[dict, Path]:
    """Check all frozen byte-level inputs and independent review before price decoding."""
    freeze_path = HERE / "FREEZE_A1.json"
    review_path = HERE / "INDEPENDENT_REVIEW_GO_A1.json"
    if not freeze_path.is_file() or not review_path.is_file():
        raise RuntimeError("FREEZE_A1.json and independent reviewer GO_A1 are required")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    prior_freeze = HERE / "FREEZE.json"
    if freeze.get("supersedes_freeze_sha256") != sha256(prior_freeze):
        raise RuntimeError("replacement freeze does not bind the preserved pre-A1 freeze")
    if review.get("decision") != "GO" or review.get("freeze_sha256") != sha256(freeze_path):
        raise RuntimeError("review GO must bind the exact frozen manifest")
    artifacts = freeze.get("artifacts", {})
    required = {
        "prereg": HERE / "PREREG.md",
        "addendum": HERE / "ADDENDUM_A1.md",
        "source": Path(__file__).resolve().parents[4] / "app" / "new_strategy_screening.py",
        "runner": Path(__file__).resolve(),
        "tests": HERE / "test_gen11.py",
        **{f"data_{s}": DATA / f"{s}.parquet" for s in SYMBOLS},
        **{f"metadata_{s}": DATA / f"{s}.meta.json" for s in SYMBOLS},
    }
    for name, path in required.items():
        actual = sha256(path)
        if artifacts.get(name) != actual:
            raise RuntimeError(f"frozen hash mismatch for {name}: expected {artifacts.get(name)}, got {actual}")
    return freeze, review_path


def append_event(path: Path, event: dict) -> None:
    row = {"ts_utc": datetime.now(timezone.utc).isoformat(), **event}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def assert_single_run_unstarted(attempt_path: Path, output_paths: tuple[Path, ...]) -> None:
    """Reject a second run or any run after an outcome has been recorded."""
    terminal_states = {"STARTED", "COMPLETED", "FAILED"}
    if attempt_path.exists():
        for line_no, line in enumerate(attempt_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("state") in terminal_states:
                raise RuntimeError(f"single-run gate: previous performance attempt at line {line_no}")
    for path in output_paths:
        if path.exists():
            raise RuntimeError(f"single-run gate: output already exists: {path.name}")


def load_inputs():
    import numpy as np
    import pandas as pd

    frames = {}
    for symbol in SYMBOLS:
        path = DATA / f"{symbol}.parquet"
        if not path.is_file():
            raise FileNotFoundError(path)
        frame = pd.read_parquet(path)
        if not isinstance(frame.index, pd.DatetimeIndex):
            if "date" in frame:
                frame = frame.set_index("date")
                frame.index = pd.to_datetime(frame.index, errors="raise")
            else:
                raise ValueError(f"{symbol}: parquet must have DatetimeIndex or date column")
        required = {"open", "close", "adjclose"}
        if not required.issubset(frame.columns):
            raise ValueError(f"{symbol}: required columns missing: {sorted(required - set(frame.columns))}")
        try:
            validate_ordered_dates(frame.index)
        except ValueError as exc:
            raise ValueError(f"{symbol}: {exc}") from exc
        raw = frame[["open", "close", "adjclose"]].to_numpy(dtype=float)
        if not np.isfinite(raw).all() or (raw <= 0).any():
            raise ValueError(f"{symbol}: non-finite/non-positive open-close-adjusted close")
        frames[symbol] = frame
    common = frames[SYMBOLS[0]].index
    for symbol in SYMBOLS[1:]:
        common = common.intersection(frames[symbol].index, sort=False)
    common = common.sort_values()
    if len(common) <= LOOKBACK + 2:
        raise ValueError("insufficient complete common history")
    aligned = {symbol: frames[symbol].reindex(common) for symbol in SYMBOLS}
    for symbol, frame in aligned.items():
        if frame[["open", "close", "adjclose"]].isna().any().any():
            raise ValueError(f"{symbol}: missing values remain on common calendar")
    return pd, np, common, aligned


def build_schedule(common, aligned):
    """Compute month-end signals, then schedule them at the following common-session open."""
    import pandas as pd

    # Per instrument, adjust raw open by the session-specific vendor adjustment factor.
    adj_close = {s: aligned[s]["adjclose"].astype(float).to_numpy() for s in SYMBOLS}
    adj_open = {
        s: (aligned[s]["open"].astype(float) * aligned[s]["adjclose"].astype(float) / aligned[s]["close"].astype(float)).to_numpy()
        for s in SYMBOLS
    }
    month_ends = pd.Series(range(len(common)), index=common).groupby(common.to_period("M")).last().astype(int).to_list()
    targets = {}
    for signal_i in month_ends:
        execute_i = signal_i + 1
        if execute_i >= len(common) or signal_i < LOOKBACK:
            continue
        scores = {s: momentum_score(adj_close[s].tolist(), signal_i) for s in SYMBOLS}
        targets[execute_i] = choose_target(scores)
    first_eligible = next((i for i in month_ends if i >= LOOKBACK and i + 1 < len(common)), None)
    if first_eligible is None:
        raise ValueError("no complete month-end signal after 252-session warmup")
    return adj_open, targets, first_eligible + 1


def simulate(common, adj_open, targets, first_i):
    import numpy as np
    import pandas as pd

    nav = 1.0
    prior = None
    rows = []
    total_turnover = 0.0
    target_change_count = 0
    for i in range(first_i, len(common) - 1):
        previous = prior
        if i in targets:
            target = targets[i]
            total_turnover += rebalance_turnover(prior, target)
            target_change_count += int(prior != target)
            prior = target
        gross = adj_open[prior][i + 1] / adj_open[prior][i] if prior is not None else 1.0
        nav, interval_return = apply_open_interval(nav, previous, prior, gross)
        rows.append({"date": common[i + 1], "return": interval_return, "target": prior})
    curve = pd.DataFrame(rows).set_index("date")
    # The final held position is liquidated at the terminal open; charge that exit once.
    if len(curve) and curve["target"].iloc[-1] is not None:
        curve.iloc[-1, curve.columns.get_loc("return")] = (1.0 + curve["return"].iloc[-1]) * (1.0 - FEE_PER_SIDE) - 1.0
        total_turnover += 1.0
    terminal_liquidation_count = int(bool(len(curve)) and curve["target"].iloc[-1] is not None)
    # Cost-matched SPY B&H uses exactly the strategy curve's open-to-open intervals.
    spy = adj_open["SPY"]
    bh = pd.Series(index=curve.index, dtype=float)
    for date in curve.index:
        i = common.get_loc(date) - 1
        gross = spy[i + 1] / spy[i]
        bh.loc[date] = gross
    if len(bh):
        bh.iloc[0] *= 1.0 - FEE_PER_SIDE
        bh.iloc[-1] *= 1.0 - FEE_PER_SIDE
    curve["benchmark_return"] = bh
    curve["exposure"] = curve["target"].notna().astype(float)
    curve.attrs["scheduled_rebalance_count"] = len(targets)
    curve.attrs["target_change_count"] = target_change_count
    curve.attrs["terminal_liquidation_count"] = terminal_liquidation_count
    curve.attrs["one_way_turnover"] = total_turnover
    return curve


def metrics(returns, exposure, start=None, end=None):
    import numpy as np
    import pandas as pd

    subset = pd.DataFrame({"r": returns, "e": exposure}).dropna()
    if start:
        subset = subset.loc[subset.index >= pd.Timestamp(start)]
    if end:
        subset = subset.loc[subset.index <= pd.Timestamp(end)]
    if len(subset) < 2:
        raise ValueError("metric window has fewer than two return observations")
    r = subset["r"].to_numpy(dtype=float)
    equity = np.cumprod(1.0 + r)
    peaks = np.maximum.accumulate(np.r_[1.0, equity])[1:]
    mdd = float(np.min(equity / peaks - 1.0))
    years = len(r) / ANNUAL_SESSIONS
    cagr = float(equity[-1] ** (1.0 / years) - 1.0)
    std = float(np.std(r, ddof=1))
    sharpe = float(np.mean(r) / std * math.sqrt(ANNUAL_SESSIONS)) if std else 0.0
    return {"start": subset.index[0].date().isoformat(), "end": subset.index[-1].date().isoformat(),
            "observations": len(r), "cagr": cagr, "sharpe": sharpe, "max_drawdown": mdd,
            "exposure": float(subset["e"].mean())}


def main() -> int:
    attempt_file = HERE / f"attempts_{ATTEMPT_ID}.jsonl"
    manifest_file = HERE / f"manifest_{ATTEMPT_ID}.json"
    try:
        assert_single_run_unstarted(attempt_file, tuple(HERE / f"{prefix}_{ATTEMPT_ID}.{suffix}"
            for prefix, suffix in (("manifest", "json"), ("results", "json"), ("curve", "csv.gz"))))
        # Hash verification reads bytes only; no parquet prices are decoded before review GO.
        freeze, review_path = verify_freeze_and_review()
        prereg = HERE / "PREREG.md"
        event = {"attempt_id": ATTEMPT_ID, "state": "STARTED", "prereg_sha256": sha256(prereg),
                 "addendum_sha256": sha256(HERE / "ADDENDUM_A1.md"),
                 "inputs": {s: {"parquet": sha256(DATA / f"{s}.parquet"),
                                "metadata": sha256(DATA / f"{s}.meta.json")} for s in SYMBOLS}}
        append_event(attempt_file, event)
        pd, np, common, aligned = load_inputs()
        adj_open, targets, first_i = build_schedule(common, aligned)
        curve = simulate(common, adj_open, targets, first_i)
        windows = {
            "full": (None, None),
            "2001_2016": ("2001-01-01", "2016-12-31"),
            "2017_plus": ("2017-01-01", None),
        }
        results = {}
        for name, (start, end) in windows.items():
            results[name] = {
                "strategy": metrics(curve["return"], curve["exposure"], start, end),
                "benchmark": metrics(curve["benchmark_return"], pd.Series(1.0, index=curve.index), start, end),
            }
        result_path = HERE / f"results_{ATTEMPT_ID}.json"
        result_path.write_text(json.dumps({"attempt_id": ATTEMPT_ID, "first_curve_date": curve.index[0].date().isoformat(),
                                           "last_curve_date": curve.index[-1].date().isoformat(),
                                           "months_with_targets": len(targets),
                                           "scheduled_rebalance_count": curve.attrs["scheduled_rebalance_count"],
                                           "target_change_count": curve.attrs["target_change_count"],
                                           "terminal_liquidation_count": curve.attrs["terminal_liquidation_count"],
                                           "one_way_turnover_units": curve.attrs["one_way_turnover"],
                                           "results": results}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        curve.to_csv(HERE / f"curve_{ATTEMPT_ID}.csv.gz", compression="gzip")
        manifest = {"attempt_id": ATTEMPT_ID, "state": "COMPLETED", "prereg_sha256": sha256(prereg),
                    "addendum_sha256": sha256(HERE / "ADDENDUM_A1.md"),
                    "runner_sha256": sha256(Path(__file__)), "test_sha256": sha256(HERE / "test_gen11.py"),
                    "review_sha256": sha256(review_path),
                    "inputs": {s: {"parquet": sha256(DATA / f"{s}.parquet"),
                                   "metadata": sha256(DATA / f"{s}.meta.json")} for s in SYMBOLS},
                    "freeze_sha256": sha256(HERE / "FREEZE_A1.json"),
                    "result_sha256": sha256(result_path), "curve_sha256": sha256(HERE / f"curve_{ATTEMPT_ID}.csv.gz")}
        manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        append_event(attempt_file, {"attempt_id": ATTEMPT_ID, "state": "COMPLETED", "result_sha256": manifest["result_sha256"]})
        return 0
    except Exception as exc:
        append_event(attempt_file, {"attempt_id": ATTEMPT_ID, "state": "FAILED", "error": str(exc), "traceback": traceback.format_exc()})
        if not manifest_file.exists():
            manifest_file.write_text(json.dumps({"attempt_id": ATTEMPT_ID, "state": "FAILED", "error": str(exc)}, indent=2) + "\n", encoding="utf-8")
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
