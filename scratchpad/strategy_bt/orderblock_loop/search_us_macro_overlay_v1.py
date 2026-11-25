"""Preregistered SPY macro overlays with fail-closed input checks.

This module never downloads data or writes the shared trial ledger. Callers
pass normalized rows; optional result artifacts go under TRADING_DATA_DIR.
Real-data callers must register frozen trial IDs in the shared ledger first.
"""

from __future__ import annotations

import json
import os
import csv
import hashlib
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from math import isfinite, sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Iterable, Mapping, Sequence

FREEZE_CUTOFF = date(2026, 5, 31)
US_ONE_WAY_COST_BPS = 10.0
DEFAULT_OUTPUT_ROOT = "cache/orderblock/us_macro_overlay_v1"
LEDGER_ROUND = "US-MACRO-OVERLAY-V1"
SHARED_LEDGER_PATH = Path(__file__).with_name("TRAIN_TRIALS.csv")
LEDGER_FIELDS = ("trial_id", "round", "market_group", "definition",
                 "parameter_grid_hash", "code_sha256")
SOURCE_META_FIELDS = ("manifest_path", "manifest_sha256", "normalized_sha256",
                      "transform_path", "transform_sha256")
SOURCE_NAMES = ("spy", "vix", "cot", "calendar")
SOURCE_MANIFEST_MAX_BYTES = 1_000_000
# A real run stays blocked until the exact, cutoff-only manifest digest is
# pinned here and in the run's preregistration before its trial IDs are used.
EXPECTED_SOURCE_MANIFEST_SHA256 = ""
RESULT_FIELDS = (
    "trial_id", "window", "parameters", "common_rows", "train_rows",
    "train_first_signal_date", "train_last_signal_date", "common_dates_sha256",
    "train_prefix_sha256", "sessions", "strategy_annualized_simple_return_on_initial_capital",
    "strategy_total_return", "strategy_yearly_returns", "buy_hold_total_return",
    "active_return", "annualized_sharpe", "max_drawdown", "daily_path",
    "candidate_status", "input_sha256", "source_metadata", "transform_sha256",
    "code_sha256", "preregistration_sha256",
)


@dataclass(frozen=True)
class Trial:
    trial_id: str
    hypothesis: str
    threshold: float
    persistence: int


def frozen_trials() -> tuple[Trial, ...]:
    """Return all 12 preregistered cells in stable order."""
    return tuple(
        [Trial(f"US-VIX-{i:02d}", "vix_curve", threshold, persistence)
         for i, (threshold, persistence) in enumerate(
             ((threshold, days) for threshold in (0.00, 0.05, 0.10)
              for days in (1, 3)), start=1)]
        + [Trial(f"US-COT-{i:02d}", "cot_crowding", threshold, persistence)
           for i, (threshold, persistence) in enumerate(
               ((threshold, reports) for threshold in (0.70, 0.80, 0.90)
                for reports in (1, 2)), start=1)]
    )


def parse_day(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise ValueError(f"invalid ISO date: {value!r}") from exc
    raise ValueError(f"unsupported date value: {value!r}")


def parse_aware_timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"invalid {field}: {value!r}") from exc
    else:
        raise ValueError(f"{field} must be an ISO-8601 timestamp with timezone")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return timestamp


def validate_spy_rows(rows: Iterable[Mapping[str, object]], *,
                      session_calendar: Mapping[date, object] | None = None) -> list[dict[str, object]]:
    """Validate normalized raw SPY OHLC and explicit corporate-action rows."""
    if session_calendar is None:
        raise ValueError("verified NYSE regular/early-close calendar is required")
    calendar = {parse_day(day): parse_aware_timestamp(close, "calendar close_at")
                for day, close in session_calendar.items()}
    required = ("date", "session_close_at", "open", "close", "dividends",
                "stock_splits", "capital_gains")
    result: list[dict[str, object]] = []
    for source in rows:
        if any(key not in source for key in required):
            raise ValueError(f"SPY row missing required fields: {required}")
        row = dict(source)
        row["date"] = parse_day(row["date"])
        if row["date"] > FREEZE_CUTOFF:
            raise ValueError("post-cutoff SPY row supplied; final freeze is not enabled")
        row["session_close_at"] = parse_aware_timestamp(row["session_close_at"], "session_close_at")
        if row["session_close_at"].date() != row["date"]:
            raise ValueError("SPY session_close_at date does not match date")
        if row["date"] not in calendar:
            raise ValueError(f"NYSE session close is missing for SPY session {row['date']}")
        if row["session_close_at"] != calendar[row["date"]]:
            raise ValueError(f"SPY close timestamp disagrees with NYSE calendar on {row['date']}")
        for key in ("open", "close", "dividends", "stock_splits", "capital_gains"):
            try:
                row[key] = float(row[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"SPY {key} must be numeric") from exc
            if not isfinite(row[key]):
                raise ValueError(f"SPY {key} must be finite")
        if (row["open"] <= 0 or row["close"] <= 0 or row["dividends"] < 0
                or row["stock_splits"] < 0 or row["capital_gains"] < 0):
            raise ValueError("SPY prices must be positive; distributions and split ratios nonnegative")
        result.append(row)
    if len(result) < 2:
        raise ValueError("at least two SPY rows are required")
    if any(a["date"] >= b["date"] for a, b in zip(result, result[1:])):
        raise ValueError("SPY dates must be unique and strictly chronological")
    if {row["date"] for row in result} != set(calendar):
        raise ValueError("NYSE calendar and SPY session coverage must match exactly")
    return result


def validate_vx_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Validate unadjusted, dated VX contracts; no stitched continuous series."""
    required = ("trade_date", "expiry_date", "settle", "available_at")
    result: list[dict[str, object]] = []
    seen: set[tuple[date, date]] = set()
    for source in rows:
        if any(key not in source for key in required):
            raise ValueError(f"VX rows require normalized fields: {required}")
        row = dict(source)
        row["trade_date"] = parse_day(row["trade_date"])
        row["expiry_date"] = parse_day(row["expiry_date"])
        if row["trade_date"] > FREEZE_CUTOFF:
            raise ValueError("post-cutoff VX row supplied; final freeze is not enabled")
        if row["expiry_date"] <= row["trade_date"]:
            raise ValueError("expired VX contracts cannot enter the front curve")
        row["available_at"] = parse_aware_timestamp(row["available_at"], "available_at")
        if row["available_at"].date() < row["trade_date"]:
            raise ValueError("VX availability timestamp cannot precede its trade date")
        if row["available_at"].date() > FREEZE_CUTOFF:
            raise ValueError("post-cutoff VX availability timestamp supplied")
        try:
            row["settle"] = float(row["settle"])
        except (TypeError, ValueError) as exc:
            raise ValueError("VX settle must be numeric") from exc
        if not isfinite(row["settle"]) or row["settle"] <= 0:
            raise ValueError("VX settle must be a finite positive value")
        key = (row["trade_date"], row["expiry_date"])
        if key in seen:
            raise ValueError("duplicate VX contract settlement")
        seen.add(key)
        result.append(row)
    return sorted(result, key=lambda row: (row["trade_date"], row["expiry_date"]))


def validate_cot_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    """Validate CFTC S&P E-mini TFF reports with point-in-time release stamps."""
    required = ("report_date", "published_at", "market", "leveraged_long",
                "leveraged_short", "open_interest")
    result: list[dict[str, object]] = []
    seen: set[tuple[date, str]] = set()
    for source in rows:
        if any(key not in source for key in required):
            raise ValueError(f"COT rows require normalized fields: {required}")
        row = dict(source)
        row["report_date"] = parse_day(row["report_date"])
        row["published_at"] = parse_aware_timestamp(row["published_at"], "published_at")
        if row["published_at"].date() > FREEZE_CUTOFF:
            raise ValueError("post-cutoff COT row supplied; final freeze is not enabled")
        if row["report_date"] > row["published_at"].date():
            raise ValueError("COT report date cannot occur after publication date")
        market = str(row["market"]).strip().lower()
        if market != "s&p 500 consolidated":
            raise ValueError("COT input must be exactly the preregistered S&P 500 Consolidated series")
        row["market"] = market
        for key in ("leveraged_long", "leveraged_short", "open_interest"):
            try:
                row[key] = float(row[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"COT {key} must be numeric") from exc
            if not isfinite(row[key]) or row[key] < 0:
                raise ValueError(f"COT {key} must be finite and nonnegative")
        if row["open_interest"] <= 0:
            raise ValueError("COT open_interest must be positive")
        key = (row["report_date"], str(row["market"]))
        if key in seen:
            raise ValueError("duplicate COT report")
        seen.add(key)
        row["net_oi"] = (row["leveraged_long"] - row["leveraged_short"]) / row["open_interest"]
        result.append(row)
    return sorted(result, key=lambda row: row["published_at"])


def build_vix_signals(spy_rows: Sequence[Mapping[str, object]],
                      vx_rows: Sequence[Mapping[str, object]], *,
                      session_calendar: Mapping[date, object]) -> dict[date, float]:
    """Map SPY close dates to the eligible same-day VX2/VX1 settlement ratio."""
    spy_rows = validate_spy_rows(spy_rows, session_calendar=session_calendar)
    vx_rows = validate_vx_rows(vx_rows)
    by_day: dict[date, list[Mapping[str, object]]] = {}
    for row in vx_rows:
        by_day.setdefault(row["trade_date"], []).append(row)
    if not by_day:
        raise ValueError("VX settlement input is empty")
    if max(by_day) > spy_rows[-1]["date"]:
        raise ValueError("VX input contains sessions beyond the frozen TRAIN boundary")
    first_vx, last_vx = min(by_day), max(by_day)
    signals: dict[date, float] = {}
    for spy in spy_rows:
        day = spy["date"]
        if day < first_vx or day > last_vx:
            continue
        contracts = sorted((row for row in by_day.get(day, [])
                            if row["expiry_date"] > day
                            and row["available_at"] <= spy["session_close_at"]),
                           key=lambda row: row["expiry_date"])
        if len(contracts) < 2:
            raise ValueError(f"missing two point-in-time VX expiries for SPY session {day}")
        signals[day] = contracts[1]["settle"] / contracts[0]["settle"] - 1.0
    return signals


def build_cot_signals(spy_rows: Sequence[Mapping[str, object]],
                      cot_rows: Sequence[Mapping[str, object]], *,
                      session_calendar: Mapping[date, object]) -> dict[date, float]:
    """Create prior-only rolling crowding percentiles available by SPY close.

    The threshold is compared with the prior 156 reports, requiring at least
    52 prior reports. Reports published after a SPY close cannot affect it.
    """
    spy_rows = validate_spy_rows(spy_rows, session_calendar=session_calendar)
    reports = validate_cot_rows(cot_rows)
    if reports and reports[-1]["published_at"] > spy_rows[-1]["session_close_at"]:
        raise ValueError("COT input contains reports beyond the frozen TRAIN boundary")
    signals: dict[date, float] = {}
    for spy in spy_rows:
        known = [row for row in reports if row["published_at"] <= spy["session_close_at"]]
        if not known:
            continue
        current = known[-1]
        prior = [row["net_oi"] for row in reports if row["published_at"] < current["published_at"]][-156:]
        if len(prior) < 52:
            continue
        if (spy["date"] - current["report_date"]).days > 14:
            raise ValueError(f"COT report is stale at SPY close {spy['date']}")
        # The value is paired with the report date; percent-rank is calculated
        # against prior observations only and then carried until next release.
        rank = sum(value <= current["net_oi"] for value in prior) / len(prior)
        signals[spy["date"]] = rank
    return signals


def expected_train_rows(common_rows: int) -> int:
    """Compute the registered 60% prefix size without loading TEST values."""
    if common_rows < 5:
        raise ValueError("at least five common sessions are required for 60/40 split")
    return int(common_rows * 0.60)


def _validate_train_split(spy_rows: Sequence[Mapping[str, object]],
                          split_metadata: Mapping[str, object]) -> None:
    required = ("common_rows", "train_rows", "train_first_date", "train_last_date",
                "common_session_dates", "common_dates_sha256", "train_prefix_sha256")
    if any(key not in split_metadata for key in required):
        raise ValueError(f"split metadata must include {required}")
    common_rows = int(split_metadata["common_rows"])
    train_rows = int(split_metadata["train_rows"])
    common_dates = [parse_day(day) for day in split_metadata["common_session_dates"]]
    if any(a >= b for a, b in zip(common_dates, common_dates[1:])):
        raise ValueError("common-session dates must be unique and chronological")
    common_hash = hashlib.sha256(_canonical_json(
        [day.isoformat() for day in common_dates]).encode()).hexdigest()
    prefix_dates = common_dates[:train_rows]
    prefix_hash = hashlib.sha256(_canonical_json(
        [day.isoformat() for day in prefix_dates]).encode()).hexdigest()
    if train_rows != expected_train_rows(common_rows) or len(spy_rows) != train_rows:
        raise ValueError("loaded SPY rows do not match the preregistered 60% TRAIN prefix")
    if (len(common_dates) != common_rows
            or common_hash != split_metadata["common_dates_sha256"]
            or prefix_hash != split_metadata["train_prefix_sha256"]):
        raise ValueError("common-session date manifest or TRAIN prefix hash is invalid")
    actual_dates = [row["date"] for row in spy_rows]
    if actual_dates != prefix_dates:
        raise ValueError("loaded SPY rows are not the exact beginning of the common-session series")
    if (not spy_rows
            or spy_rows[0]["date"] != parse_day(split_metadata["train_first_date"])
            or spy_rows[-1]["date"] != parse_day(split_metadata["train_last_date"])):
        raise ValueError("TRAIN prefix end date does not match frozen split metadata")


def _confirmed(values: Sequence[float], index: int, threshold: float,
               persistence: int, *, high_is_risk_off: bool) -> bool:
    if index + 1 < persistence:
        return False
    tail = values[index - persistence + 1:index + 1]
    if len(tail) != persistence:
        return False
    if high_is_risk_off:
        return all(value >= threshold for value in tail)
    return all(value < threshold for value in tail)


def _rebalance(cash: float, shares: float, target: float,
               price: float, cost_rate: float) -> tuple[float, float]:
    """Switch between cash and SPY while charging cost on traded notional."""
    if target == 1.0 and shares == 0.0:
        nav = cash
        fee = nav * cost_rate
        return 0.0, max(nav - fee, 0.0) / price
    if target == 0.0 and shares > 0.0:
        proceeds = shares * price
        return cash + proceeds * (1.0 - cost_rate), 0.0
    return cash, shares


def _apply_actions(cash: float, shares: float,
                   distribution_cash: float,
                   row: Mapping[str, object]) -> tuple[float, float, float]:
    """Apply splits and collect dividends/capital gains without reinvestment."""
    split = float(row["stock_splits"])
    if split > 0:
        shares *= split
    distribution_cash += shares * (float(row["dividends"]) + float(row["capital_gains"]))
    return cash, distribution_cash, shares


def _daily_returns(nav: Sequence[float]) -> list[float]:
    return [current / previous - 1.0 if previous > 0 else 0.0
            for previous, current in zip(nav, nav[1:])]


def _yearly_nav_returns(nav: Sequence[float], dates: Sequence[date]) -> dict[str, float]:
    results: dict[str, float] = {}
    for year in sorted({day.year for day in dates}):
        indices = [index for index, day in enumerate(dates) if day.year == year]
        start_nav = nav[indices[0]]
        end_nav = nav[indices[-1] + 1]
        results[str(year)] = end_nav / start_nav - 1.0 if start_nav > 0 else 0.0
    return results


def _evaluate_train(spy_source: Iterable[Mapping[str, object]],
                    signal_values: Mapping[date, float], trial: Trial, *,
                    session_calendar: Mapping[date, object],
                    split_metadata: Mapping[str, object],
                    double_cost: bool = False, delay_sessions: int = 0) -> dict[str, object]:
    """Evaluate only the preregistered TRAIN prefix, against same-window B&H.

    ``signal_values`` are VIX spreads for ``vix_curve`` and prior-only COT
    percent-ranks for ``cot_crowding``. No TEST-scoring API is provided here.
    """
    if trial.hypothesis not in ("vix_curve", "cot_crowding"):
        raise ValueError("unsupported macro hypothesis")
    if trial not in frozen_trials():
        raise ValueError("trial parameters do not match a frozen grid cell")
    if delay_sessions not in (0, 1):
        raise ValueError("stress delay must be 0 or 1 session")
    train = validate_spy_rows(spy_source, session_calendar=session_calendar)
    _validate_train_split(train, split_metadata)
    signal_dates = set(signal_values)
    if len(train) < 5:
        raise ValueError("too few sessions in TRAIN prefix")
    if signal_dates != {row["date"] for row in train}:
        raise ValueError("macro signal inputs must exactly cover TRAIN and contain no TEST dates")
    values = [float(signal_values[row["date"]]) for row in train]
    if not all(isfinite(value) for value in values):
        raise ValueError("macro signals must be finite")
    cost_bps = US_ONE_WAY_COST_BPS * (2.0 if double_cost else 1.0)
    cost_rate = cost_bps / 10_000.0
    strategy_cash, strategy_distribution_cash, strategy_shares = 1.0, 0.0, 0.0
    benchmark_cash, benchmark_distribution_cash, benchmark_shares = 1.0, 0.0, 0.0
    strategy_nav = [1.0]
    benchmark_nav = [1.0]
    strategy_pnl: list[float] = []
    benchmark_pnl: list[float] = []
    return_dates: list[date] = []
    prior_target = 0.0
    fills: list[dict[str, object]] = []
    turnover = 0
    # Signal at close[i], execute at open[i+1], then mark open[i+1] to open[i+2].
    for i in range(len(train) - 2):
        signal_i = i - delay_sessions
        if signal_i < 0:
            target = 0.0
        else:
            if trial.hypothesis == "vix_curve":
                risk_off = _confirmed(values, signal_i, trial.threshold, trial.persistence,
                                      high_is_risk_off=False)
            else:
                risk_off = _confirmed(values, signal_i, trial.threshold, trial.persistence,
                                      high_is_risk_off=True)
            target = 0.0 if risk_off else 1.0
        if target != prior_target:
            strategy_cash, strategy_shares = _rebalance(
                strategy_cash, strategy_shares, target, float(train[i + 1]["open"]), cost_rate)
            turnover += 1
            fills.append({"signal_date": train[max(signal_i, 0)]["date"].isoformat(),
                          "execution_date": train[i + 1]["date"].isoformat(),
                          "target_exposure": target})
        if i == 0:
            benchmark_cash, benchmark_shares = _rebalance(
                benchmark_cash, benchmark_shares, 1.0, float(train[i + 1]["open"]), cost_rate)
        strategy_cash, strategy_distribution_cash, strategy_shares = _apply_actions(
            strategy_cash, strategy_shares, strategy_distribution_cash, train[i + 2])
        benchmark_cash, benchmark_distribution_cash, benchmark_shares = _apply_actions(
            benchmark_cash, benchmark_shares, benchmark_distribution_cash, train[i + 2])
        equity = (strategy_cash + strategy_distribution_cash
                  + strategy_shares * float(train[i + 2]["open"]))
        benchmark = (benchmark_cash + benchmark_distribution_cash
                     + benchmark_shares * float(train[i + 2]["open"]))
        strategy_pnl.append(equity - strategy_nav[-1])
        benchmark_pnl.append(benchmark - benchmark_nav[-1])
        strategy_nav.append(equity)
        benchmark_nav.append(benchmark)
        return_dates.append(train[i + 2]["date"])
        prior_target = target
    if prior_target == 1.0:
        strategy_cash, strategy_shares = _rebalance(
            strategy_cash, strategy_shares, 0.0, float(train[-1]["open"]), cost_rate)
        turnover += 1
        equity = strategy_cash + strategy_distribution_cash
        strategy_pnl[-1] += equity - strategy_nav[-1]
        strategy_nav[-1] = equity
    benchmark_cash, benchmark_shares = _rebalance(
        benchmark_cash, benchmark_shares, 0.0, float(train[-1]["open"]), cost_rate)
    benchmark = benchmark_cash + benchmark_distribution_cash
    benchmark_pnl[-1] += benchmark - benchmark_nav[-1]
    benchmark_nav[-1] = benchmark
    strategy_daily_returns = _daily_returns(strategy_nav)
    benchmark_daily_returns = _daily_returns(benchmark_nav)
    yearly_returns = _yearly_nav_returns(strategy_nav, return_dates)
    return {
        "trial_id": trial.trial_id,
        "window": "train",
        "train_first_signal_date": train[0]["date"].isoformat(),
        "train_last_signal_date": train[-1]["date"].isoformat(),
        "common_rows": int(split_metadata["common_rows"]),
        "train_rows": len(train),
        "common_dates_sha256": split_metadata["common_dates_sha256"],
        "train_prefix_sha256": split_metadata["train_prefix_sha256"],
        "sessions": len(strategy_pnl),
        "strategy_total_return": equity - 1.0,
        "strategy_annualized_simple_return_on_initial_capital": (
            (equity - 1.0) * 252.0 / len(strategy_pnl) if strategy_pnl else None),
        "strategy_yearly_returns": yearly_returns,
        "buy_hold_total_return": benchmark - 1.0,
        "active_return": equity / benchmark - 1.0,
        "annualized_sharpe": _sharpe(strategy_daily_returns),
        "max_drawdown": _max_drawdown(strategy_nav),
        "position_changes": turnover,
        "fills": fills,
        "cost_bps_per_side": cost_bps,
        "delay_sessions": delay_sessions,
        "candidate_status": "exploratory_challenger_not_G_eligible",
        "daily_path": [
            {"date": day.isoformat(),
             "strategy_daily_pnl_on_initial_capital": strategy_pnl[index],
             "buy_hold_daily_pnl_on_initial_capital": benchmark_pnl[index],
             "strategy_daily_return_on_prior_nav": strategy_return,
             "buy_hold_daily_return_on_prior_nav": benchmark_return,
             "strategy_nav": strategy_nav[index + 1],
             "buy_hold_nav": benchmark_nav[index + 1]}
            for index, (day, strategy_return, benchmark_return) in enumerate(
                zip(return_dates, strategy_daily_returns, benchmark_daily_returns))
        ],
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _json_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _calendar_rows(session_calendar: Mapping[date, object]) -> list[tuple[str, str]]:
    return sorted((parse_day(day).isoformat(),
                   parse_aware_timestamp(close, "calendar close_at").isoformat())
                  for day, close in session_calendar.items())


def _signal_rows(signal_values: Mapping[date, float]) -> list[tuple[str, float]]:
    return sorted((parse_day(day).isoformat(), float(value))
                  for day, value in signal_values.items())


def _trial_definition(trial: Trial) -> dict[str, object]:
    return {"hypothesis": trial.hypothesis, "threshold": trial.threshold,
            "persistence": trial.persistence}


def _registered_trials(required_trials: Sequence[Trial]) -> set[str]:
    """Verify exact preregistered configs and code/doc hashes in a ledger snapshot."""
    path = SHARED_LEDGER_PATH
    if not path.is_file():
        raise ValueError("shared trial ledger snapshot is missing")
    prereg_path = Path(__file__).with_name("PREREG_US_MACRO_OVERLAY_V1.md")
    expected_prereg_hash = _sha256(prereg_path)
    expected_code_hash = _sha256(Path(__file__))
    expected = {trial.trial_id: trial for trial in required_trials}
    found: dict[str, dict[str, str]] = {}
    before = path.stat()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or any(field not in reader.fieldnames for field in LEDGER_FIELDS):
            raise ValueError("trial ledger snapshot does not match required schema")
        for row in reader:
            trial_id = row.get("trial_id", "")
            if trial_id not in expected:
                continue
            if trial_id in found:
                raise ValueError(f"duplicate trial ledger ID: {trial_id}")
            found[trial_id] = row
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("trial ledger snapshot changed while it was being validated")
    for trial_id, trial in expected.items():
        row = found.get(trial_id)
        if row is None:
            raise ValueError(f"trial {trial_id} is absent from the shared trial ledger")
        try:
            definition = json.loads(row["definition"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid ledger definition for {trial_id}") from exc
        if (row["round"] != LEDGER_ROUND or row["market_group"] != "US"
                or definition != _trial_definition(trial)
                or row["parameter_grid_hash"] != expected_prereg_hash
                or row["code_sha256"] != expected_code_hash):
            raise ValueError(f"ledger registration does not match frozen trial {trial_id}")
    return set(found)


def _validate_source_metadata(
        metadata: Mapping[str, Mapping[str, object]], *,
        normalized_sha256: Mapping[str, str] | None = None) -> dict[str, dict[str, object]]:
    """Validate a pinned cutoff-only manifest without opening source snapshots.

    The manifest is small metadata created before this run and its digest must
    already be pinned in this module. Snapshot contents are not scanned or
    hashed here: doing so could read post-cutoff rows. The exact normalized
    TRAIN inputs supplied to this module are checked against hashes in the
    pinned manifest instead.
    """
    data_root = Path(os.path.realpath(os.path.expanduser(
        os.environ.get("TRADING_DATA_DIR", "~/CODE/trading_data"))))
    if set(metadata) != set(SOURCE_NAMES):
        raise ValueError(f"source metadata must contain exactly {SOURCE_NAMES}")
    if (len(EXPECTED_SOURCE_MANIFEST_SHA256) != 64
            or any(char not in "0123456789abcdef" for char in
                   EXPECTED_SOURCE_MANIFEST_SHA256.lower())):
        raise ValueError("cutoff source manifest hash is not preregistered")

    first = metadata[SOURCE_NAMES[0]]
    if any(field not in first for field in SOURCE_META_FIELDS):
        raise ValueError("source provenance missing fields for spy")
    manifest_path = Path(str(first["manifest_path"])).expanduser().resolve()
    if os.path.commonpath((str(data_root), str(manifest_path))) != str(data_root):
        raise ValueError("cutoff source manifest is outside TRADING_DATA_DIR")
    if not manifest_path.is_file() or manifest_path.stat().st_size > SOURCE_MANIFEST_MAX_BYTES:
        raise ValueError("cutoff source manifest is missing or exceeds metadata size limit")
    manifest_bytes = manifest_path.read_bytes()
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_digest != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise ValueError("cutoff source manifest does not match preregistered hash")
    if any(source.get("manifest_path") != str(manifest_path)
           or source.get("manifest_sha256") != manifest_digest
           for source in metadata.values()):
        raise ValueError("source metadata does not reference one pinned manifest")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cutoff source manifest is not valid UTF-8 JSON") from exc
    if (not isinstance(manifest, dict)
            or manifest.get("schema_version") != 1
            or manifest.get("snapshot_kind") != "cutoff_only"
            or manifest.get("freeze_cutoff") != FREEZE_CUTOFF.isoformat()
            or not isinstance(manifest.get("sources"), dict)
            or set(manifest["sources"]) != set(SOURCE_NAMES)):
        raise ValueError("source manifest is not an exact cutoff-only snapshot manifest")

    required_summary = {"source_path", "snapshot_path", "snapshot_stat", "rows", "bytes", "sha256",
                        "schema", "date_min", "date_max", "normalized_sha256",
                        "rights_status", "transform_sha256"}
    verified: dict[str, dict[str, object]] = {}
    for source_name in SOURCE_NAMES:
        source = metadata[source_name]
        if any(field not in source for field in SOURCE_META_FIELDS):
            raise ValueError(f"source provenance missing fields for {source_name}")
        summary = manifest["sources"][source_name]
        if not isinstance(summary, dict) or not required_summary.issubset(summary):
            raise ValueError(f"cutoff manifest summary is incomplete for {source_name}")
        for key in ("source_path", "snapshot_path"):
            path = Path(str(summary[key])).expanduser().resolve()
            if os.path.commonpath((str(data_root), str(path))) != str(data_root):
                raise ValueError(f"{source_name} {key} is outside TRADING_DATA_DIR")
            summary[key] = str(path)
        snapshot_path = Path(str(summary["snapshot_path"]))
        if not snapshot_path.is_file():
            raise ValueError(f"cutoff-only snapshot is missing for {source_name}")
        snapshot_stat = snapshot_path.stat()
        expected_stat = summary["snapshot_stat"]
        if (not isinstance(expected_stat, dict)
                or expected_stat.get("device") != snapshot_stat.st_dev
                or expected_stat.get("inode") != snapshot_stat.st_ino
                or expected_stat.get("mtime_ns") != snapshot_stat.st_mtime_ns
                or expected_stat.get("size") != snapshot_stat.st_size
                or expected_stat.get("mode") != snapshot_stat.st_mode
                or int(summary["bytes"]) != snapshot_stat.st_size):
            raise ValueError(f"cutoff-only snapshot stat mismatch for {source_name}")
        if snapshot_stat.st_mode & 0o222:
            raise ValueError(f"cutoff-only snapshot must be read-only for {source_name}")
        if (summary["rights_status"] != "confirmed"
                or int(summary["rows"]) < 1 or int(summary["bytes"]) < 1
                or not isinstance(summary["schema"], list)
                or not summary["schema"]
                or len(set(summary["schema"])) != len(summary["schema"])):
            raise ValueError(f"source rights or snapshot metadata is invalid for {source_name}")
        for key in ("sha256", "normalized_sha256", "transform_sha256"):
            digest = str(summary[key]).lower()
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError(f"invalid {key} in cutoff manifest for {source_name}")
        try:
            first_date = parse_day(summary["date_min"])
            last_date = parse_day(summary["date_max"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid date range in cutoff manifest for {source_name}") from exc
        if first_date > last_date or last_date > FREEZE_CUTOFF:
            raise ValueError(f"source snapshot contains dates outside cutoff for {source_name}")
        if _file_sha256(snapshot_path) != summary["sha256"]:
            raise ValueError(f"cutoff-only snapshot content hash mismatch for {source_name}")
        if source["normalized_sha256"] != summary["normalized_sha256"]:
            raise ValueError(f"normalized input hash mismatch for {source_name}")
        if normalized_sha256 is not None and source_name in normalized_sha256:
            if normalized_sha256[source_name] != summary["normalized_sha256"]:
                raise ValueError(f"supplied TRAIN input does not match frozen {source_name} snapshot")

        transform_path = Path(str(source["transform_path"])).expanduser().resolve()
        if not transform_path.is_file():
            raise ValueError(f"normalization transform file is missing for {source_name}")
        transform_digest = _file_sha256(transform_path)
        if (source["transform_sha256"] != transform_digest
                or transform_digest != summary["transform_sha256"]):
            raise ValueError(f"normalization transform hash mismatch for {source_name}")
        verified[source_name] = {
            "manifest_path": str(manifest_path),
            "manifest_sha256": manifest_digest,
            "snapshot": dict(summary),
            "normalized_sha256": summary["normalized_sha256"],
            "transform_path": str(transform_path),
            "transform_sha256": transform_digest,
        }
    if normalized_sha256 is not None and not set(normalized_sha256).issubset(SOURCE_NAMES):
        raise ValueError("normalized input hash map contains an unknown source")
    return verified


def _add_provenance(result: dict[str, object], trial: Trial,
                    spy_rows: Sequence[Mapping[str, object]],
                    signal_values: Mapping[date, float],
                    source_metadata: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    prereg_path = Path(__file__).with_name("PREREG_US_MACRO_OVERLAY_V1.md")
    result["parameters"] = _trial_definition(trial)
    result["input_sha256"] = {
        "spy_normalized": _json_sha256(list(spy_rows)),
        "macro_normalized": _json_sha256(_signal_rows(signal_values)),
        "calendar_normalized": source_metadata["calendar"]["normalized_sha256"],
    }
    result["source_metadata"] = dict(source_metadata)
    result["transform_sha256"] = {
        name: source_metadata[name]["transform_sha256"]
        for name in ("spy", "vix", "cot", "calendar")
    }
    result["preregistration_sha256"] = _sha256(prereg_path)
    result["code_sha256"] = _sha256(Path(__file__))
    return result


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evaluate_train(spy_source: Iterable[Mapping[str, object]],
                   signal_values: Mapping[date, float], trial: Trial, *,
                   session_calendar: Mapping[date, object],
                   split_metadata: Mapping[str, object],
                   source_metadata: Mapping[str, Mapping[str, object]],
                   double_cost: bool = False, delay_sessions: int = 0) -> dict[str, object]:
    """Evaluate one TRAIN cell after verifying its exact shared-ledger row."""
    _registered_trials([trial])
    spy = validate_spy_rows(spy_source, session_calendar=session_calendar)
    _validate_train_split(spy, split_metadata)
    normalized_inputs = {
        "spy": _json_sha256(spy),
        "calendar": _json_sha256(_calendar_rows(session_calendar)),
        "vix" if trial.hypothesis == "vix_curve" else "cot":
            _json_sha256(_signal_rows(signal_values)),
    }
    verified_metadata = _validate_source_metadata(
        source_metadata, normalized_sha256=normalized_inputs)
    result = _evaluate_train(spy, signal_values, trial, session_calendar=session_calendar,
                             split_metadata=split_metadata,
                             double_cost=double_cost, delay_sessions=delay_sessions)
    return _add_provenance(result, trial, spy, signal_values, verified_metadata)


def run_train_grid(spy_rows: Iterable[Mapping[str, object]],
                   vix_signals: Mapping[date, float],
                   cot_signals: Mapping[date, float], *,
                   session_calendar: Mapping[date, object],
                   split_metadata: Mapping[str, object],
                   source_metadata: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    """Run the 12 frozen TRAIN cells plus registered execution stresses.

    This does not score TEST or append to TRAIN_TRIALS.csv. The owner must
    register every trial ID in the shared ledger before real-data use.
    """
    rows = validate_spy_rows(spy_rows, session_calendar=session_calendar)
    _validate_train_split(rows, split_metadata)
    _registered_trials(frozen_trials())
    normalized_inputs = {
        "spy": _json_sha256(rows),
        "calendar": _json_sha256(_calendar_rows(session_calendar)),
        "vix": _json_sha256(_signal_rows(vix_signals)),
        "cot": _json_sha256(_signal_rows(cot_signals)),
    }
    verified_metadata = _validate_source_metadata(
        source_metadata, normalized_sha256=normalized_inputs)
    outputs: list[dict[str, object]] = []
    for trial in frozen_trials():
        source = vix_signals if trial.hypothesis == "vix_curve" else cot_signals
        outputs.append(_add_provenance(
            _evaluate_train(rows, source, trial, session_calendar=session_calendar,
                            split_metadata=split_metadata),
            trial, rows, source, verified_metadata))
        stress_cost = _add_provenance(
            _evaluate_train(rows, source, trial, session_calendar=session_calendar,
                            split_metadata=split_metadata,
                            double_cost=True),
            trial, rows, source, verified_metadata)
        stress_cost["stress"] = "double_cost"
        outputs.append(stress_cost)
        stress_delay = _add_provenance(
            _evaluate_train(rows, source, trial, session_calendar=session_calendar,
                            split_metadata=split_metadata,
                            delay_sessions=1),
            trial, rows, source, verified_metadata)
        stress_delay["stress"] = "one_session_signal_delay"
        outputs.append(stress_delay)
    return outputs


def write_train_results(results: Sequence[Mapping[str, object]], *,
                        output_path: str | None = None) -> str:
    """Write a new, non-overwriting JSON artifact below TRADING_DATA_DIR."""
    if not results:
        raise ValueError("cannot write an empty TRAIN result artifact")
    for result in results:
        missing = [field for field in RESULT_FIELDS if field not in result]
        if missing:
            raise ValueError(f"result row is missing required provenance: {missing}")
        if result["window"] != "train" or len(result["daily_path"]) != result["sessions"]:
            raise ValueError("result artifact must contain complete TRAIN daily paths only")
        if not isinstance(result["input_sha256"], Mapping) or not isinstance(
                result["transform_sha256"], Mapping):
            raise ValueError("result artifact is missing input/transform hash maps")
        hypothesis = result["parameters"].get("hypothesis")
        if hypothesis not in ("vix_curve", "cot_crowding"):
            raise ValueError("result artifact has an unknown hypothesis")
        normalized_hashes = {
            "spy": result["input_sha256"].get("spy_normalized"),
            "calendar": result["input_sha256"].get("calendar_normalized"),
            "vix" if hypothesis == "vix_curve" else "cot":
                result["input_sha256"].get("macro_normalized"),
        }
        _validate_source_metadata(result["source_metadata"],
                                  normalized_sha256=normalized_hashes)
        digests = [*result["input_sha256"].values(), *result["transform_sha256"].values(),
                   result["code_sha256"], result["preregistration_sha256"]]
        if any(len(str(digest)) != 64
               or any(char not in "0123456789abcdef" for char in str(digest).lower())
               for digest in digests):
            raise ValueError("result artifact contains an invalid reproducibility hash")
    data_root = os.path.realpath(os.path.expanduser(
        os.environ.get("TRADING_DATA_DIR", "~/CODE/trading_data")))
    if output_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = os.path.join(data_root, DEFAULT_OUTPUT_ROOT, f"train_{stamp}.json")
    else:
        target = os.path.realpath(os.path.expanduser(output_path))
    if os.path.commonpath((data_root, target)) != data_root or target == data_root:
        raise ValueError("result output must be below TRADING_DATA_DIR")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    payload = {"schema_version": 1, "window": "train", "results": list(results)}
    encoded = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    # Exclusive creation preserves prior research artifacts and rejects a
    # timestamp collision rather than replacing an earlier run.
    with open(target, "x", encoding="utf-8") as handle:
        handle.write(encoded)
    return target


def _sharpe(returns: Sequence[float]) -> float | None:
    if len(returns) < 2:
        return None
    deviation = stdev(returns)
    if deviation == 0:
        return None
    return mean(returns) / deviation * sqrt(252.0)


def _max_drawdown(nav: Sequence[float]) -> float:
    peak = nav[0]
    worst = 0.0
    for value in nav:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def preregistration_rows() -> list[dict[str, object]]:
    """JSON-friendly frozen grid intended for the isolated preregistration."""
    return [asdict(trial) for trial in frozen_trials()]


__all__ = [
    "DEFAULT_OUTPUT_ROOT", "FREEZE_CUTOFF", "Trial", "build_cot_signals",
    "build_vix_signals", "evaluate_train", "frozen_trials", "parse_aware_timestamp",
    "expected_train_rows", "preregistration_rows", "validate_cot_rows", "validate_spy_rows",
    "validate_vx_rows", "run_train_grid", "write_train_results",
]
