"""Train-only R13 funding-overheat support-breakdown short."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import search_crypto as common
from crypto import (Bar, FundingEvent, Setup, Zone, _atr, simulate_trade,
                    trade_daily_pnl)
from metrics import curve_metrics, trade_metrics, wilson_lower

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "PREREG_R13_FUNDING_OVERHEAT_SHORT.md"
UNIVERSE_PATH = HERE / "universe" / "CRYPTO_35.csv"
_LOADED_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
TIMEFRAME = "4h"
DURATION_MS = 14_400_000
SUPPORT_LOOKBACK = 20
FUNDING_EVENTS = 3
FUNDING_MEAN_MIN = 0.0003
STOP_BUFFER_ATR = 0.10
REWARD_R = 2.0
MAX_HOLDING_BARS = 48
MINIMUM_SYMBOLS = 30
FUNDING_ORDER_POLICY = "adverse_only"
EXPERIMENT = "R13-FUNDING-OVERHEAT-SUPPORT-BREAK-SHORT"
CONFIG = {
    "experiment": EXPERIMENT, "timeframe": TIMEFRAME, "direction": "short",
    "support_lookback_bars": SUPPORT_LOOKBACK,
    "funding_events": FUNDING_EVENTS, "funding_mean_min": FUNDING_MEAN_MIN,
    "stop_buffer_atr": STOP_BUFFER_ATR, "reward_r": REWARD_R,
    "max_holding_bars": MAX_HOLDING_BARS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
    "minimum_symbols": MINIMUM_SYMBOLS,
}
CONFIGS = (CONFIG,)


def _expected_symbols(path: Path = UNIVERSE_PATH) -> frozenset[str]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["symbol"]:
            raise ValueError("frozen crypto universe must have one symbol column")
        symbols = [row["symbol"].strip() for row in reader]
    if not symbols or any(not symbol for symbol in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("frozen crypto universe contains empty or duplicate symbols")
    return frozenset(symbols)


def _validate_symbols(actual: Sequence[str], expected: Sequence[str]) -> None:
    actual_set, expected_set = set(actual), set(expected)
    if len(actual) != len(actual_set) or actual_set != expected_set:
        raise ValueError(
            "R13 TRAIN symbols differ from exact frozen universe "
            f"(expected={len(expected_set)}, actual={len(actual_set)}, "
            f"missing={len(expected_set - actual_set)}, "
            f"unexpected={len(actual_set - expected_set)})"
        )


def _load_barsets(loader):
    result = []
    for symbol, bars, funding in loader(timeframe=TIMEFRAME):
        closed = [bar for bar in bars if bar.complete]
        result.append((symbol, closed, funding, len(bars) - len(closed)))
        common._check_memory()
    _validate_symbols([row[0] for row in result], _expected_symbols())
    return result


def _continuous_segments(bars: Sequence[Bar]):
    if not bars:
        return [], 0
    segments, current = [], [bars[0]]
    missing, previous = 0, bars[0].timestamp
    if previous % DURATION_MS:
        raise ValueError("bar open timestamp is not on a UTC 4h boundary")
    for bar in bars[1:]:
        delta = bar.timestamp - previous
        if bar.timestamp % DURATION_MS:
            raise ValueError("bar open timestamp is not on a UTC 4h boundary")
        if delta <= 0:
            raise ValueError("bar timestamps must be strictly increasing")
        if delta % DURATION_MS:
            raise ValueError("bar gap is not a whole number of UTC 4h intervals")
        if delta == DURATION_MS:
            current.append(bar)
        else:
            segments.append(current)
            missing += delta // DURATION_MS - 1
            current = [bar]
        previous = bar.timestamp
    segments.append(current)
    return segments, missing


def _overheated_funding(bars: Sequence[Bar], index: int,
                        funding: Mapping[int, FundingEvent]) -> bool:
    """Use the latest three settlements known by this completed bar's close."""
    close_ts = bars[index].timestamp + DURATION_MS
    prior = [event for timestamp, event in sorted(funding.items())
             if timestamp == event.timestamp and timestamp < close_ts]
    if len(prior) < FUNDING_EVENTS:
        return False
    latest = prior[-FUNDING_EVENTS:]
    return (all(event.rate > 0 for event in latest)
            and sum(event.rate for event in latest) / FUNDING_EVENTS >= FUNDING_MEAN_MIN)


def _setup_at(bars: Sequence[Bar], index: int,
              funding: Mapping[int, FundingEvent]):
    """Build a next-open short only from a closed-bar breakdown and prior history."""
    if index < SUPPORT_LOOKBACK or index >= len(bars) or not bars[index].complete:
        return None, "insufficient_history"
    previous = bars[index - SUPPORT_LOOKBACK:index]
    if len(previous) != SUPPORT_LOOKBACK or any(not bar.complete for bar in previous):
        return None, "insufficient_history"
    support = min(bar.low for bar in previous)
    signal = bars[index]
    if signal.close >= support:
        return None, "no_close_break"
    if not _overheated_funding(bars, index, funding):
        return None, "funding_filter"
    atr_value = _atr(bars, index, 14)
    if atr_value is None:
        return None, "no_atr"
    entry_index = index + 1
    if entry_index >= len(bars) or not bars[entry_index].complete:
        return None, "cutoff_entry_censored"
    entry = bars[entry_index].open
    stop = signal.high + STOP_BUFFER_ATR * atr_value
    risk = stop - entry
    target = entry - REWARD_R * risk
    if risk <= 0 or entry >= stop or target <= 0:
        return None, "invalid_risk"
    zone = Zone(index, index, "short", support, signal.close, atr_value)
    return Setup(zone, entry_index, entry, stop, target), "setup"


def _trades_for_segment(bars, funding, *, right_edge_reason="cutoff"):
    trades, audit, busy_until = [], {key: 0 for key in (
        "breakdown_candidates", "funding_rejected", "setup_count",
        "cutoff_entry_censored", "gap_skipped_setups", "right_censored_setups",
        "time_exit_censored_setups", "funding_coverage_censored_trades",
        "gap_censored_setups")}, -1
    for index in range(SUPPORT_LOOKBACK, len(bars)):
        if index <= busy_until:
            continue
        if bars[index].close < min(bar.low for bar in bars[index-SUPPORT_LOOKBACK:index]):
            audit["breakdown_candidates"] += 1
        setup, reason = _setup_at(bars, index, funding)
        if reason == "cutoff_entry_censored" and right_edge_reason == "gap":
            reason = "gap_censored"
        if reason == "funding_filter":
            audit["funding_rejected"] += 1
        if reason == "cutoff_entry_censored":
            audit["cutoff_entry_censored"] += 1
        if reason == "gap_censored":
            audit["gap_censored_setups"] += 1
        if reason == "invalid_risk":
            audit["gap_skipped_setups"] += 1
        if setup is None:
            continue
        trade = simulate_trade(
            bars, setup, funding=funding, max_holding_bars=MAX_HOLDING_BARS,
            bar_duration_ms=DURATION_MS, funding_order_policy=FUNDING_ORDER_POLICY,
        )
        if trade is None:
            audit["time_exit_censored_setups"] += 1
            audit["right_censored_setups"] += 1
            busy_until = len(bars)
            break
        if trade.net_return is None:
            audit["funding_coverage_censored_trades"] += 1
        audit["setup_count"] += 1
        trades.append(trade)
        busy_until = trade.exit_index
    return trades, audit


def _m2_metrics(events):
    hits = sum(event[3] for event in events)
    selected, last_exit = [], {}
    for symbol, entry, exit_end, target_first in sorted(events):
        if entry < last_exit.get(symbol, -1):
            continue
        selected.append(target_first)
        last_exit[symbol] = exit_end
    count, nonoverlap = len(events), len(selected)
    return {
        "m2_signal_count": count, "m2_target_hits": hits,
        "m2_target_first_rate": hits / count if count else None,
        "m2_wilson_lower_95": wilson_lower(hits, count),
        "m2_nonoverlap_signal_count": nonoverlap,
        "m2_nonoverlap_target_hits": sum(selected),
        "m2_nonoverlap_target_first_rate": sum(selected) / nonoverlap if nonoverlap else None,
        "m2_nonoverlap_wilson_lower_95": wilson_lower(sum(selected), nonoverlap),
    }


def _trial(barsets):
    returns, symbols, events = [], [], []
    daily_by_symbol = {}
    audit = {key: 0 for key in (
        "breakdown_candidates", "funding_rejected", "setup_count",
        "cutoff_entry_censored", "gap_skipped_setups", "right_censored_setups",
        "time_exit_censored_setups", "funding_coverage_censored_trades",
        "gap_censored_setups", "missing_gap_bars")}
    total_trades = unscorable = missing_bars = 0
    first_day = last_day = None
    for symbol, bars, funding, incomplete in barsets:
        missing_bars += incomplete
        if not bars:
            continue
        symbols.append(symbol)
        daily_by_symbol[symbol] = {}
        start, end = bars[0].timestamp // 86_400_000, bars[-1].timestamp // 86_400_000
        first_day = start if first_day is None else min(first_day, start)
        last_day = end if last_day is None else max(last_day, end)
        segments, missing = _continuous_segments(bars)
        audit["missing_gap_bars"] += missing
        for segment_index, segment in enumerate(segments):
            scoped_funding = common._funding_by_timestamp(segment, funding, DURATION_MS)
            edge = "gap" if segment_index < len(segments) - 1 else "cutoff"
            segment_trades, segment_audit = _trades_for_segment(
                segment, scoped_funding, right_edge_reason=edge
            )
            for key, value in segment_audit.items():
                audit[key] += value
            total_trades += len(segment_trades)
            for trade in segment_trades:
                entry_ts = segment[trade.setup.entry_index].timestamp
                exit_end = segment[trade.exit_index].timestamp + DURATION_MS
                events.append((symbol, entry_ts, exit_end, trade.exit_reason == "target"))
                if trade.net_return is None:
                    unscorable += 1
                    continue
                daily = trade_daily_pnl(segment, trade, funding=scoped_funding,
                                        bar_duration_ms=DURATION_MS)
                if daily is None:
                    unscorable += 1
                    continue
                returns.append(trade.net_return)
                for day, value in daily.items():
                    daily_by_symbol[symbol][day] = daily_by_symbol[symbol].get(day, 0.0) + value
        common._check_memory()
    daily = ([sum(daily_by_symbol[s].get(day, 0.0) for s in symbols) / len(symbols)
              for day in range(first_day, last_day + 1)] if symbols else [])
    stats, curve = trade_metrics(returns), curve_metrics(daily, 365)
    status = "unscorable" if len(symbols) < MINIMUM_SYMBOLS or unscorable else "completed"
    return {
        "status": status, "symbols": len(symbols), "trades": total_trades - unscorable,
        "total_trades": total_trades, "unscorable_funding_trades": unscorable,
        "incomplete_bars_excluded": missing_bars, **audit,
        "win_rate": stats.win_rate, "profit_factor": stats.profit_factor,
        "expectancy_bps": stats.expectancy_bps, "cumulative_return": curve.cumulative_return,
        "max_drawdown": curve.max_drawdown, "annualized_sharpe": curve.annualized_sharpe,
        "solvent": curve.solvent, **_m2_metrics(events),
        "detail": "TRAIN only; not a G decision",
    }


def _code_hash():
    digest = hashlib.sha256()
    for name in ("crypto.py", "search_crypto.py", "search_crypto_r13.py",
                 "data_access.py", "metrics.py", "resource_guard.py",
                 "universe/CRYPTO_35.csv"):
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _verified_prereg_hash():
    current = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    if current != _LOADED_PREREG_SHA:
        raise RuntimeError("R13 preregistration changed after import")
    return _LOADED_PREREG_SHA


def _append(result, grid_hash, code_sha, prereg_sha):
    config_json = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    record = {
        "trial_id": f"R13-crypto-{config_hash[:12]}-{uuid.uuid4().hex}",
        "round": "R13-coin", "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json, "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha,
        "train_period": "bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "prereg_sha256": prereg_sha},
                              sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": f"status={result['status']}; TRAIN only",
    }
    has_rows = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if has_rows:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch; R13 row not appended")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not has_rows:
            writer.writeheader()
        writer.writerow(record)


def _ledger_denominator(path: Path | None = None) -> int:
    path = path or common.CSV_PATH
    if not path.exists() or path.stat().st_size == 0:
        return 0
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def _already_recorded(grid_hash, code_sha, fingerprint, prereg_sha):
    if not common.CSV_PATH.exists():
        return False
    csv.field_size_limit(sys.maxsize)
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (row["round"] != "R13-coin" or row["parameter_grid_hash"] != grid_hash
                    or row["code_sha256"] != code_sha):
                continue
            try:
                metric = json.loads(row["metric"])
            except (json.JSONDecodeError, TypeError):
                continue
            if (isinstance(metric, dict)
                    and metric.get("train_input_fingerprint") == fingerprint
                    and metric.get("prereg_sha256") == prereg_sha
                    and metric.get("status") in {"completed", "unscorable"}):
                return True
    return False


def _run(loader):
    code_sha, prereg_sha = _code_hash(), _verified_prereg_hash()
    grid_hash = hashlib.sha256(json.dumps(CONFIGS, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
    denominator = _ledger_denominator() + 1
    barsets = _load_barsets(loader)
    if _code_hash() != code_sha or _verified_prereg_hash() != prereg_sha:
        raise RuntimeError("R13 source/prereg changed while TRAIN data was loading")
    fingerprint = common._train_input_fingerprint(TIMEFRAME, barsets)
    if _already_recorded(grid_hash, code_sha, fingerprint, prereg_sha):
        print("[1/1] already recorded; no duplicate row added", flush=True)
        return 1
    result = _trial(barsets)
    result["train_input_fingerprint"] = fingerprint
    result["bonferroni_denominator"] = denominator
    if _code_hash() != code_sha or _verified_prereg_hash() != prereg_sha:
        raise RuntimeError("R13 source/prereg changed before ledger append")
    _append(result, grid_hash, code_sha, prereg_sha)
    print(f"[1/1] {EXPERIMENT}: {result['status']} trades={result['trades']} "
          f"M2={result['m2_target_first_rate']}", flush=True)
    return 1


def run():
    import data_access
    from resource_guard import heavy_task

    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        raise RuntimeError("TRAIN-only data loader is unavailable")
    with heavy_task("R13"):
        return _run(loader)


if __name__ == "__main__":
    raise SystemExit(run())
