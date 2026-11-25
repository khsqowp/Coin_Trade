"""Single preregistered R14 first-retest midpoint-confirmation diagnostic."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
from crypto import (Bar, FundingEvent, Setup, Trade, Zone, r4_zones,
                    simulate_trade, trade_daily_pnl)
from metrics import curve_metrics, trade_metrics, wilson_lower

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "PREREG_R14_FIRST_RETEST_MIDPOINT_CONFIRM.md"
MASTER_PREREG_PATH = HERE / "PREREG.md"
UNIVERSE_PATH = HERE / "universe" / "CRYPTO_35.csv"
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_PREREG_SHA = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()
DURATION_MS = 3_600_000
ZONE_DURATION_MS = 4 * DURATION_MS
DEADLINE = 24
REWARD_R = 0.5
MAX_HOLDING_BARS = 24
STOP_BUFFER_ATR = 0.10
MINIMUM_SYMBOLS = 30
FUNDING_ORDER_POLICY = "adverse_only"
EXPERIMENT = "R14-OB-FIRST-RETEST-MIDPOINT-CONFIRM"
CONFIG = {
    "experiment": EXPERIMENT, "zone_timeframe": "4h",
    "confirmation_timeframe": "1h", "definition": "bos_origin",
    "directions": ["long", "short"], "deadline_bars": DEADLINE,
    "confirmation": "first_touch_close_beyond_zone_midpoint",
    "distal_sweep_required": False, "reward_r": REWARD_R,
    "stop_buffer_atr": STOP_BUFFER_ATR, "max_holding_bars": MAX_HOLDING_BARS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
}


def _expected_symbols(path: Path = UNIVERSE_PATH) -> frozenset[str]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["symbol"]:
            raise ValueError("frozen universe must contain exactly one symbol column")
        symbols = [row["symbol"].strip() for row in reader]
    if not symbols or any(not item for item in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("frozen universe has empty or duplicate symbols")
    return frozenset(symbols)


def _validate_symbols(actual, expected) -> None:
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("TRAIN symbols do not exactly match frozen universe")


def _validate_barset(symbol, bars, funding, duration_ms):
    if any(bar.timestamp % duration_ms for bar in bars):
        raise ValueError(f"non-UTC bar boundary: {symbol}")
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError(f"non-chronological bars: {symbol}")
    if any(ts != event.timestamp for ts, event in funding.items()):
        raise ValueError(f"funding key mismatch: {symbol}")


def _load_barsets(loader, timeframe):
    barsets = []
    duration = ZONE_DURATION_MS if timeframe == "4h" else DURATION_MS
    for symbol, bars, funding in loader(timeframe=timeframe):
        closed = [bar for bar in bars if bar.complete]
        _validate_barset(symbol, closed, funding, duration)
        barsets.append((symbol, closed, funding, len(bars) - len(closed)))
    _validate_symbols([row[0] for row in barsets], _expected_symbols())
    return barsets


def _make_setup(zone: Zone, confirmation_bar: Bar, next_bar: Bar,
                confirmation_index: int):
    midpoint = (zone.low + zone.high) / 2
    if zone.direction == "long":
        if confirmation_bar.low <= zone.low:
            return None, "invalidated"
        if confirmation_bar.close <= midpoint:
            return None, "midpoint_failed"
        stop = zone.low - STOP_BUFFER_ATR * zone.atr_at_signal
    else:
        if confirmation_bar.high >= zone.high:
            return None, "invalidated"
        if confirmation_bar.close >= midpoint:
            return None, "midpoint_failed"
        stop = zone.high + STOP_BUFFER_ATR * zone.atr_at_signal
    entry = next_bar.open
    if (zone.direction == "long" and entry <= zone.low) or (
            zone.direction == "short" and entry >= zone.high):
        return None, "entry_gapped_past_zone"
    risk = entry - stop if zone.direction == "long" else stop - entry
    if risk <= 0:
        return None, "nonpositive_risk"
    target = entry + REWARD_R * risk if zone.direction == "long" else entry - REWARD_R * risk
    return Setup(zone, confirmation_index + 1, entry, stop, target), "setup"


def _zones_on_confirmation_segments(segments_1h, segments_4h):
    by_timestamp = [{bar.timestamp: i for i, bar in enumerate(segment)}
                    for segment in segments_1h]
    mapped = [{} for _ in segments_1h]
    unaligned = 0
    for segment_4h in segments_4h:
        for zone in r4_zones(segment_4h, "bos_origin"):
            available_at = segment_4h[zone.signal_index].timestamp + ZONE_DURATION_MS
            target = next((i for i, lookup in enumerate(by_timestamp)
                           if available_at in lookup), None)
            if target is None:
                unaligned += 1
                continue
            signal_index = by_timestamp[target][available_at]
            if signal_index in mapped[target]:
                raise ValueError("multiple R14 zones share a 1h activation bar")
            mapped[target][signal_index] = Zone(
                signal_index, zone.origin_index, zone.direction, zone.low,
                zone.high, zone.atr_at_signal,
            )
    return mapped, unaligned


def _simulate_segment(bars, funding, zones_by_index):
    trades: list[Trade] = []
    audit = {key: 0 for key in (
        "zones", "first_touches", "midpoint_failures", "invalidated_zones",
        "expired_zones", "invalid_setups", "right_censored_setups",
        "superseding_zones_dropped",
        "funding_unscorable_trades",
    )}
    audit["zones"] = len(zones_by_index)
    active: Zone | None = None
    i = 0
    while i < len(bars):
        zone = zones_by_index.get(i)
        if active is None:
            if zone is not None:
                active = zone
            i += 1
            continue
        if zone is not None and zone.signal_index != active.signal_index:
            audit["superseding_zones_dropped"] += 1
        age = i - active.signal_index
        if age > DEADLINE:
            audit["expired_zones"] += 1
            active = None
            continue
        if age == 0:
            i += 1
            continue
        bar = bars[i]
        invalid = (bar.low <= active.low if active.direction == "long"
                   else bar.high >= active.high)
        overlaps = bar.low <= active.high and bar.high >= active.low
        if invalid:
            audit["invalidated_zones"] += 1
            active = None
            i += 1
            continue
        if not overlaps:
            i += 1
            continue
        audit["first_touches"] += 1
        if i + 1 >= len(bars) or not bars[i + 1].complete:
            audit["right_censored_setups"] += 1
            break
        setup, reason = _make_setup(active, bar, bars[i + 1], i)
        if setup is None:
            if reason == "midpoint_failed":
                audit["midpoint_failures"] += 1
            else:
                audit["invalid_setups"] += 1
            active = None
            i += 1
            continue
        trade = simulate_trade(
            bars, setup, funding=funding,
            max_holding_bars=MAX_HOLDING_BARS,
            bar_duration_ms=DURATION_MS,
            funding_order_policy=FUNDING_ORDER_POLICY,
        )
        if trade is None:
            audit["right_censored_setups"] += 1
            break
        if trade.net_return is None:
            audit["funding_unscorable_trades"] += 1
        trades.append(trade)
        active = None
        i = max(i + 1, trade.exit_index)
    return trades, audit


def _segments(bars, duration_ms):
    if not bars:
        return [], 0
    result, current, gaps = [], [bars[0]], 0
    for prev, bar in zip(bars, bars[1:]):
        delta = bar.timestamp - prev.timestamp
        if delta <= 0 or delta % duration_ms:
            raise ValueError("invalid timeframe gap")
        if delta == duration_ms:
            current.append(bar)
        else:
            result.append(current)
            gaps += delta // duration_ms - 1
            current = [bar]
    result.append(current)
    return result, gaps


def _trial(barsets_1h, barsets_4h):
    returns, events, daily_by_symbol = [], [], {}
    symbols, total_trades = [], 0
    unscorable = incomplete = gap_bars = 0
    alignment_failures = 0
    bars_4h_by_symbol = {symbol: bars for symbol, bars, _funding, _excluded in barsets_4h}
    _validate_symbols([symbol for symbol, *_ in barsets_4h], _expected_symbols())
    segments_by_symbol = {}
    segments_4h_by_symbol = {}
    for symbol, bars, funding, excluded in barsets_1h:
        segments_by_symbol[symbol], gaps = _segments(bars, DURATION_MS)
        gap_bars += gaps
        incomplete += excluded
    for symbol, bars, _funding, excluded in barsets_4h:
        segments_4h_by_symbol[symbol], gaps = _segments(bars, ZONE_DURATION_MS)
        gap_bars += gaps
        incomplete += excluded
    first_day = last_day = None
    audit_totals = {}
    for symbol, bars, funding, _excluded in barsets_1h:
        if not bars or not bars_4h_by_symbol.get(symbol):
            continue
        symbols.append(symbol)
        daily_by_symbol[symbol] = {}
        first = bars[0].timestamp // 86_400_000
        last = bars[-1].timestamp // 86_400_000
        first_day = first if first_day is None else min(first_day, first)
        last_day = last if last_day is None else max(last_day, last)
        segments = segments_by_symbol[symbol]
        segments_4h = segments_4h_by_symbol[symbol]
        zones_by_segment, unaligned = _zones_on_confirmation_segments(segments, segments_4h)
        alignment_failures += unaligned
        for segment, zones_by_index in zip(segments, zones_by_segment):
            segment_funding = common._funding_by_timestamp(segment, funding, DURATION_MS)
            trades, audit = _simulate_segment(segment, segment_funding, zones_by_index)
            for key, value in audit.items():
                audit_totals[key] = audit_totals.get(key, 0) + value
            total_trades += len(trades)
            for trade in trades:
                entry = segment[trade.setup.entry_index].timestamp
                exit_end = segment[trade.exit_index].timestamp + DURATION_MS
                events.append((symbol, entry, exit_end, trade.exit_reason == "target"))
                if trade.net_return is None:
                    unscorable += 1
                    continue
                daily = trade_daily_pnl(segment, trade, funding=segment_funding,
                                        bar_duration_ms=DURATION_MS)
                if daily is None:
                    unscorable += 1
                    continue
                returns.append(trade.net_return)
                for day, value in daily.items():
                    daily_by_symbol[symbol][day] = daily_by_symbol[symbol].get(day, 0.0) + value
    daily = ([sum(daily_by_symbol[s].get(day, 0.0) for s in symbols) / len(symbols)
              for day in range(first_day, last_day + 1)] if symbols else [])
    stats, curve = trade_metrics(returns), curve_metrics(daily, 365)
    hits = sum(event[3] for event in events)
    nonoverlap, last_exit = [], {}
    for symbol, entry, exit_end, hit in sorted(events):
        if entry < last_exit.get(symbol, -1):
            continue
        nonoverlap.append(hit)
        last_exit[symbol] = exit_end
    return {
        "status": "unscorable" if len(symbols) < MINIMUM_SYMBOLS else "completed",
        "symbols": len(symbols), "total_trades": total_trades,
        "trades": total_trades - unscorable, "unscorable_funding_trades": unscorable,
        "incomplete_bars_excluded": incomplete, "missing_gap_bars": gap_bars,
        "unaligned_4h_zones": alignment_failures,
        **audit_totals, "win_rate": stats.win_rate,
        "profit_factor": stats.profit_factor, "expectancy_bps": stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return, "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe, "solvent": curve.solvent,
        "m2_signal_count": len(events), "m2_target_hits": hits,
        "m2_target_first_rate": hits / len(events) if events else None,
        "m2_wilson_lower_95": wilson_lower(hits, len(events)),
        "m2_nonoverlap_signal_count": len(nonoverlap),
        "m2_nonoverlap_target_hits": sum(nonoverlap),
        "m2_nonoverlap_target_first_rate": sum(nonoverlap) / len(nonoverlap) if nonoverlap else None,
        "m2_nonoverlap_wilson_lower_95": wilson_lower(sum(nonoverlap), len(nonoverlap)),
        "detail": "4h BOS-origin zones with 1h first-retest confirmation; TRAIN only; not a G decision",
    }


def _code_hash():
    digest = hashlib.sha256()
    for name in ("crypto.py", "search_crypto.py", "search_crypto_r14.py",
                 "data_access.py", "metrics.py", "resource_guard.py", "PREREG.md",
                 "universe/CRYPTO_35.csv"):
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _append(result, grid_hash, code_sha, prereg_sha):
    config_json = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    record = {
        "trial_id": f"R14-crypto-{uuid.uuid4().hex}", "round": "R14-coin",
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json, "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "prereg_sha256": prereg_sha,
                               "master_prereg_sha256": _MASTER_PREREG_SHA},
                              sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": (
            "R14 pre-data infrastructure failure sentinel; code hash unavailable; "
            "no market rows loaded"
            if result.get("status") == "failed_before_data_access"
            else "R14 single preregistered TRAIN diagnostic; not a G decision"
        ),
    }
    exists = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if exists:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(record)


def _ledger_row_count(path: Path) -> int:
    previous_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return sum(1 for _ in csv.DictReader(stream))
    finally:
        csv.field_size_limit(previous_limit)


def _record_preflight_failure():
    grid_hash = hashlib.sha256(json.dumps(
        [CONFIG], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    _append({"status": "failed_before_data_access",
             "failure": "CSV field-size limit while counting prior ledger rows"},
            grid_hash, "UNAVAILABLE_PRE_DATA_ACCESS", prereg_sha)


def run():
    import data_access
    from resource_guard import heavy_task

    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    master_prereg_sha = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()
    if prereg_sha != _PREREG_SHA or master_prereg_sha != _MASTER_PREREG_SHA:
        raise RuntimeError("R14 prereg changed after import")
    code_sha = _code_hash()
    denominator = _ledger_row_count(common.CSV_PATH) + 1
    grid_hash = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                          separators=(",", ":")).encode()).hexdigest()
    with heavy_task("R14"):
        barsets_1h = _load_barsets(data_access.iter_train_bars, "1h")
        barsets_4h = _load_barsets(data_access.iter_train_bars, "4h")
        fingerprint = common._train_input_fingerprint(
            "R14-4h-zones-1h-confirmation",
            [(f"{symbol}:1h", bars, funding, excluded)
             for symbol, bars, funding, excluded in barsets_1h]
            + [(f"{symbol}:4h", bars, {}, excluded)
               for symbol, bars, _funding, excluded in barsets_4h],
        )
        result = _trial(barsets_1h, barsets_4h)
        result.update({"train_input_fingerprint": fingerprint,
                       "bonferroni_denominator": denominator})
        if (_code_hash() != code_sha
                or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != prereg_sha
                or hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest() != master_prereg_sha):
            raise RuntimeError("R14 code/prereg changed during the run")
        _append(result, grid_hash, code_sha, prereg_sha)
    print(f"R14 completed status={result['status']} trades={result['trades']} "
          f"M2={result['m2_target_first_rate']} N={denominator}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
