"""Train-only test of invalidated bullish OBs flipping into short resistance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
from crypto import (Setup, Zone, _atr, r4_zones, simulate_trade,
                    trade_daily_pnl)
from metrics import curve_metrics, trade_metrics, wilson_lower

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "PREREG.md"
_LOADED_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
TIMEFRAME = "4h"
DURATION_MS = 14_400_000
MAX_HOLDING_BARS = 48
FUNDING_ORDER_POLICY = "adverse_only"
MINIMUM_SYMBOLS = 30
EXPERIMENT = "R8-OB-POLARITY-FLIP"
CONFIG = {
    "experiment": EXPERIMENT,
    "definition": "bos_origin",
    "timeframe": TIMEFRAME,
    "source_zone_direction": "long",
    "trade_direction": "short",
    "total_deadline_bars": 48,
    "stop_buffer_atr": 0.10,
    "reward_r": 2.0,
    "max_holding_bars": MAX_HOLDING_BARS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
    "minimum_symbols": MINIMUM_SYMBOLS,
}
CONFIGS = (CONFIG,)


def _load_barsets(loader):
    barsets = []
    for symbol, bars, funding in loader(timeframe=TIMEFRAME):
        closed = [bar for bar in bars if bar.complete]
        barsets.append((symbol, closed, funding, len(bars) - len(closed)))
        common._check_memory()
    return barsets


def _continuous_segments(bars):
    """Split bars at missing 4h intervals; reject malformed timestamps."""
    if not bars:
        return [], 0

    segments = []
    current = [bars[0]]
    missing_bars = 0
    previous = bars[0].timestamp
    if previous % DURATION_MS:
        raise ValueError("bar open timestamp is not on a UTC 4h boundary")

    for bar in bars[1:]:
        timestamp = bar.timestamp
        if timestamp % DURATION_MS:
            raise ValueError("bar open timestamp is not on a UTC 4h boundary")
        delta = timestamp - previous
        if delta <= 0:
            raise ValueError("bar timestamps must be strictly increasing")
        if delta % DURATION_MS:
            raise ValueError("bar gap is not a whole number of UTC 4h intervals")
        if delta == DURATION_MS:
            current.append(bar)
        else:
            segments.append(current)
            missing_bars += delta // DURATION_MS - 1
            current = [bar]
        previous = timestamp

    segments.append(current)
    return segments, missing_bars


def _flip_setup(bars, bullish_zone, *, deadline=48, stop_buffer_atr=0.10,
                reward_r=2.0):
    """Return first causal rejection setup and consumed bar for one bullish OB."""
    if bullish_zone.direction != "long":
        raise ValueError("polarity flip source zone must be bullish")
    if deadline != 48 or stop_buffer_atr != 0.10 or reward_r != 2.0:
        raise ValueError("R8 settings are fixed by preregistration")

    last = min(len(bars) - 1, bullish_zone.signal_index + deadline)
    invalidation_index = None
    for index in range(bullish_zone.signal_index + 1, last + 1):
        bar = bars[index]
        if not bar.complete:
            break
        if invalidation_index is None:
            if bar.close < bullish_zone.low:
                invalidation_index = index
            continue

        if bar.close > bullish_zone.high:
            return None, index, "recovered"
        overlaps = bar.high >= bullish_zone.low and bar.low <= bullish_zone.high
        if not overlaps:
            continue
        if bar.close >= bullish_zone.low:
            return None, index, "first_retest_failed"

        entry_index = index + 1
        if entry_index >= len(bars) or not bars[entry_index].complete:
            return None, index, "right_censored"
        entry = bars[entry_index].open
        atr_value = _atr(bars, index, 14)
        if atr_value is None:
            return None, index, "no_atr"
        stop = bar.high + stop_buffer_atr * atr_value
        risk = stop - entry
        target = entry - reward_r * risk
        if risk <= 0 or entry >= stop or target <= 0:
            return None, index, "gap_skipped"
        flipped_zone = Zone(
            index, bullish_zone.origin_index, "short", bullish_zone.low,
            bullish_zone.high, atr_value,
        )
        return Setup(flipped_zone, entry_index, entry, stop, target), index, "setup"

    consumed = max(bullish_zone.signal_index, last)
    reason = "expired" if invalidation_index is not None else "not_invalidated"
    return None, consumed, reason


def _trades_for_symbol(bars, funding, config, zones):
    audit = {
        "source_zones": 0,
        "invalidated_zones": 0,
        "rejection_setups": 0,
        "recovered_zones": 0,
        "first_retest_failed_zones": 0,
        "expired_zones": 0,
        "gap_skipped_setups": 0,
        "right_censored_setups": 0,
        "time_exit_censored_setups": 0,
    }
    bullish = sorted((zone for zone in zones if zone.direction == "long"),
                     key=lambda zone: zone.signal_index)
    audit["source_zones"] = len(bullish)
    trades = []
    busy_until = -1
    for zone in bullish:
        if zone.signal_index <= busy_until:
            continue
        setup, consumed, reason = _flip_setup(
            bars, zone, deadline=config["total_deadline_bars"],
            stop_buffer_atr=config["stop_buffer_atr"], reward_r=config["reward_r"],
        )
        if reason != "not_invalidated":
            audit["invalidated_zones"] += 1
        if reason == "recovered":
            audit["recovered_zones"] += 1
        elif reason == "first_retest_failed":
            audit["first_retest_failed_zones"] += 1
        elif reason == "expired":
            audit["expired_zones"] += 1
        elif reason == "gap_skipped":
            audit["gap_skipped_setups"] += 1
        elif reason == "right_censored":
            audit["right_censored_setups"] += 1
        if setup is None:
            busy_until = max(busy_until, consumed)
            continue

        audit["rejection_setups"] += 1
        trade = simulate_trade(
            bars, setup, funding=funding,
            max_holding_bars=config["max_holding_bars"],
            bar_duration_ms=DURATION_MS,
            funding_order_policy=FUNDING_ORDER_POLICY,
        )
        if trade is None:
            audit["time_exit_censored_setups"] += 1
            busy_until = len(bars)
            break
        trades.append(trade)
        busy_until = trade.exit_index
    return trades, audit


def _m2_metrics(events):
    hits = sum(event[3] for event in events)
    selected = []
    last_exit = {}
    for symbol, entry, exit_end, target_first in sorted(events):
        if entry < last_exit.get(symbol, -1):
            continue
        selected.append(target_first)
        last_exit[symbol] = exit_end
    count = len(events)
    nonoverlap_count = len(selected)
    nonoverlap_hits = sum(selected)
    return {
        "m2_signal_count": count,
        "m2_target_hits": hits,
        "m2_target_first_rate": hits / count if count else None,
        "m2_wilson_lower_95": wilson_lower(hits, count),
        "m2_nonoverlap_signal_count": nonoverlap_count,
        "m2_nonoverlap_target_hits": nonoverlap_hits,
        "m2_nonoverlap_target_first_rate": (
            nonoverlap_hits / nonoverlap_count if nonoverlap_count else None
        ),
        "m2_nonoverlap_wilson_lower_95": wilson_lower(
            nonoverlap_hits, nonoverlap_count
        ),
    }


def _trial(barsets, config=CONFIG):
    returns = []
    symbol_daily = {}
    events = []
    symbols = []
    total_trades = unscorable = 0
    incomplete_excluded = 0
    audits = {key: 0 for key in (
        "source_zones", "invalidated_zones", "rejection_setups",
        "recovered_zones", "first_retest_failed_zones", "expired_zones",
        "gap_skipped_setups",
        "right_censored_setups", "time_exit_censored_setups",
    )}
    continuity_segments = missing_bars = 0
    first_day = last_day = None

    for symbol, bars, funding, incomplete in barsets:
        if symbol.upper() in ("BTCUSDT", "BTC-USDT", "BTC/USDT"):
            continue
        incomplete_excluded += incomplete
        if not bars:
            continue
        symbols.append(symbol)
        symbol_daily[symbol] = {}
        first_day = bars[0].timestamp // 86_400_000 if first_day is None else min(
            first_day, bars[0].timestamp // 86_400_000
        )
        last_day = bars[-1].timestamp // 86_400_000 if last_day is None else max(
            last_day, bars[-1].timestamp // 86_400_000
        )
        segments, missing = _continuous_segments(bars)
        continuity_segments += len(segments)
        missing_bars += missing
        for segment in segments:
            scoped_funding = common._funding_by_timestamp(
                segment, funding, DURATION_MS
            )
            zones = r4_zones(segment, "bos_origin")
            trades, audit = _trades_for_symbol(
                segment, scoped_funding, config, zones
            )
            for key, value in audit.items():
                audits[key] += value
            total_trades += len(trades)
            for trade in trades:
                entry_ts = segment[trade.setup.entry_index].timestamp
                exit_end = segment[trade.exit_index].timestamp + DURATION_MS
                events.append((symbol, entry_ts, exit_end,
                               trade.exit_reason == "target"))
                if trade.net_return is None:
                    unscorable += 1
                    continue
                daily = trade_daily_pnl(
                    segment, trade, funding=scoped_funding,
                    bar_duration_ms=DURATION_MS,
                )
                if daily is None:
                    unscorable += 1
                    continue
                returns.append(trade.net_return)
                for day, value in daily.items():
                    symbol_daily[symbol][day] = (
                        symbol_daily[symbol].get(day, 0.0) + value
                    )
        common._check_memory()

    daily_returns = []
    if symbols and first_day is not None and last_day is not None:
        daily_returns = [
            sum(symbol_daily[symbol].get(day, 0.0) for symbol in symbols) / len(symbols)
            for day in range(first_day, last_day + 1)
        ]
    stats = trade_metrics(returns)
    curve = curve_metrics(daily_returns, 365)
    status = "completed"
    reasons = []
    if len(symbols) < MINIMUM_SYMBOLS:
        status = "unscorable"
        reasons.append(f"symbols={len(symbols)}<{MINIMUM_SYMBOLS}")
    if unscorable:
        status = "unscorable"
        reasons.append(f"funding_unscorable={unscorable}")
    return {
        "status": status,
        "symbols": len(symbols),
        "trades": len(returns),
        "total_trades": total_trades,
        "unscorable_funding_trades": unscorable,
        "win_rate": stats.win_rate,
        "wilson_95_lower": stats.wilson_lower_95,
        "payoff_ratio": (
            stats.average_win / stats.average_loss
            if stats.average_win and stats.average_loss else None
        ),
        "profit_factor": stats.profit_factor,
        "expectancy_bps": stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return,
        "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe,
        "solvent": curve.solvent,
        "incomplete_bars_excluded": incomplete_excluded,
        "continuity_segments": continuity_segments,
        "missing_4h_bars": missing_bars,
        **audits,
        **_m2_metrics(events),
        "train_input_fingerprint": common._train_input_fingerprint(TIMEFRAME, barsets),
        "detail": "; ".join(reasons) if reasons else "TRAIN only; not a G decision",
    }


def _code_hash():
    digest = hashlib.sha256()
    for name in ("crypto.py", "search_crypto.py", "search_crypto_r8.py",
                 "data_access.py", "metrics.py", "resource_guard.py"):
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _verified_loaded_prereg_hash():
    current = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    if current != _LOADED_PREREG_SHA:
        raise RuntimeError("R8 preregistration changed after import; restart before TRAIN")
    return _LOADED_PREREG_SHA


def _append(result, grid_hash, code_sha, prereg_sha):
    config_json = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    record = {
        "trial_id": f"R8-crypto-{config_hash[:12]}-{uuid.uuid4().hex}",
        "round": "R8-coin",
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json,
        "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha,
        "train_period": "bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "prereg_sha256": prereg_sha},
                              sort_keys=True, separators=(",", ":")),
        "rank": "",
        "notes": f"status={result['status']}; TRAIN only",
    }
    has_rows = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if has_rows:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch; R8 row not appended")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not has_rows:
            writer.writeheader()
        writer.writerow(record)


def _already_recorded(grid_hash, code_sha, fingerprint, prereg_sha):
    if not common.CSV_PATH.exists():
        return False
    csv.field_size_limit(sys.maxsize)
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (row["round"] != "R8-coin"
                    or row["parameter_grid_hash"] != grid_hash
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


def run():
    import data_access

    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        raise RuntimeError("TRAIN-only data loader is unavailable")
    code_sha = _code_hash()
    prereg_sha = _verified_loaded_prereg_hash()
    grid_hash = hashlib.sha256(json.dumps(
        CONFIGS, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    barsets = _load_barsets(loader)
    if _code_hash() != code_sha or _verified_loaded_prereg_hash() != prereg_sha:
        raise RuntimeError("R8 source/prereg changed while TRAIN data was loading")
    fingerprint = common._train_input_fingerprint(TIMEFRAME, barsets)
    if _already_recorded(grid_hash, code_sha, fingerprint, prereg_sha):
        print("[1/1] already recorded; no duplicate row added", flush=True)
        return 1
    result = _trial(barsets)
    if _code_hash() != code_sha or _verified_loaded_prereg_hash() != prereg_sha:
        raise RuntimeError("R8 source/prereg changed before ledger append")
    _append(result, grid_hash, code_sha, prereg_sha)
    print(f"[1/1] {EXPERIMENT}: {result['status']} "
          f"trades={result['trades']} M2={result['m2_target_first_rate']}", flush=True)
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    from resource_guard import heavy_task
    with heavy_task("B-R8-coin"):
        count = run()
    if count != 1:
        raise RuntimeError(f"expected one R8 trial, ran {count}")


if __name__ == "__main__":
    main()
