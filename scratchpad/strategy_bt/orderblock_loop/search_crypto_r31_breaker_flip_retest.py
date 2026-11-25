"""Single preregistered TRAIN test for invalidated OB breaker retests."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r29_bos_taker_flow as r29
import search_crypto_r27_bos_fvg_confluence as r27
from crypto import Setup, Trade, Zone, simulate_trade, trade_daily_pnl
from metrics import curve_metrics, trade_metrics, wilson_lower
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R31-coin"
PREREG_PATH = HERE / "PREREG_R31_BREAKER_FLIP_RETEST.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_687
EXPECTED_N = 1_688
CUTOFF_MS = 1_699_286_400_000
HOUR_MS = 3_600_000
BREAK_DEADLINE = 24
RETEST_DEADLINE = 24
STOP_BUFFER_ATR = 0.10
TARGET_R = 0.50
MAX_HOLDING_BARS = 24
FUNDING_ORDER_POLICY = "adverse_only"
MINIMUM_SYMBOLS = 30
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R31-OB-INVALIDATION-BREAKER-FIRST-RETEST",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "R14_bos_origin", "break": "completed_1h_close_beyond_distal",
    "break_deadline_bars": BREAK_DEADLINE,
    "retest": "first_post_break_touch_close_outside_in_break_direction",
    "retest_deadline_bars": RETEST_DEADLINE,
    "stop_buffer_atr": STOP_BUFFER_ATR, "target_r": TARGET_R,
    "max_holding_bars": MAX_HOLDING_BARS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py",
    "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "PREREG_R14_FIRST_RETEST_MIDPOINT_CONFIRM.md",
    "search_crypto_r31_breaker_flip_retest.py",
    "tests/test_search_crypto_r31_breaker_flip_retest.py",
    "universe/CRYPTO_35.csv",
)


class AppendUncertainError(RuntimeError):
    """The ledger append may have partially succeeded; never retry it."""


def _advance(state: dict, bar, index: int):
    """Advance one closed bar; return a causal transition label."""
    if not bar.complete:
        raise ValueError("R31 state machine accepts completed bars only")
    if state["phase"] == "ob_wait":
        age = index - state["zone"].signal_index
        if age > BREAK_DEADLINE:
            return "expire_break"
        if age == 0:
            return "wait"
        zone = state["zone"]
        broke = (bar.close < zone.low if zone.direction == "long"
                 else bar.close > zone.high)
        if broke:
            state["phase"] = "breaker_wait"
            state["break_index"] = index
            return "broken"
        return "wait"

    age = index - state["break_index"]
    if age == 0:
        return "wait"
    if age > RETEST_DEADLINE:
        return "expire_retest"
    zone = state["zone"]
    if zone.direction == "long":  # invalidated bullish zone becomes short resistance
        if bar.close >= zone.low or bar.high >= zone.high:
            return "cancel_reentered"
        if bar.open < zone.low and bar.high >= zone.low and bar.close < zone.low:
            return "confirm_short"
    else:  # invalidated bearish zone becomes long support
        if bar.close <= zone.high or bar.low <= zone.low:
            return "cancel_reentered"
        if bar.open > zone.high and bar.low <= zone.high and bar.close > zone.high:
            return "confirm_long"
    return "wait"


def _make_setup(zone: Zone, bars, confirmation_index: int):
    entry_index = confirmation_index + 1
    if entry_index >= len(bars) or not bars[entry_index].complete:
        return None, "right_censored"
    direction = "short" if zone.direction == "long" else "long"
    entry = bars[entry_index].open
    if direction == "short":
        if entry >= zone.low:
            return None, "entry_gapped_into_zone"
        stop = zone.high + STOP_BUFFER_ATR * zone.atr_at_signal
        if entry >= stop:
            return None, "entry_gapped_past_stop"
        risk = stop - entry
        target = entry - TARGET_R * risk
    else:
        if entry <= zone.high:
            return None, "entry_gapped_into_zone"
        stop = zone.low - STOP_BUFFER_ATR * zone.atr_at_signal
        if entry <= stop:
            return None, "entry_gapped_past_stop"
        risk = entry - stop
        target = entry + TARGET_R * risk
    flipped = Zone(zone.signal_index, zone.origin_index, direction,
                   zone.low, zone.high, zone.atr_at_signal)
    return Setup(flipped, entry_index, entry, stop, target), "setup"


def _simulate_segment(bars, funding, zones_by_index):
    trades: list[Trade] = []
    audit = {key: 0 for key in (
        "zones", "activated_zones", "superseding_zones_dropped", "breaks",
        "confirmed_retests", "cancelled_reentered", "expired_break_wait",
        "expired_retest_wait", "entry_gapped_into_zone", "entry_gapped_past_stop",
        "invalid_risk", "right_censored_setups", "funding_unscorable_trades",
    )}
    audit["zones"] = len(zones_by_index)
    state = None
    index = 0
    while index < len(bars):
        candidate = zones_by_index.get(index)
        if state is None:
            if candidate is not None:
                state = {"zone": candidate, "phase": "ob_wait", "break_index": None}
                audit["activated_zones"] += 1
            index += 1
            continue
        if candidate is not None and candidate.signal_index != state["zone"].signal_index:
            audit["superseding_zones_dropped"] += 1
        transition = _advance(state, bars[index], index)
        if transition == "expire_break":
            audit["expired_break_wait"] += 1
            state = None
            continue
        if transition == "expire_retest":
            audit["expired_retest_wait"] += 1
            state = None
            continue
        if transition == "broken":
            audit["breaks"] += 1
            index += 1
            continue
        if transition == "cancel_reentered":
            audit["cancelled_reentered"] += 1
            state = None
            index += 1
            continue
        if transition not in ("confirm_short", "confirm_long"):
            index += 1
            continue
        audit["confirmed_retests"] += 1
        setup, reason = _make_setup(state["zone"], bars, index)
        if setup is None:
            audit["right_censored_setups" if reason == "right_censored" else reason] += 1
            state = None
            if reason == "right_censored":
                break
            index += 1
            continue
        if ((setup.zone.direction == "long" and setup.entry_price <= setup.stop)
                or (setup.zone.direction == "short" and setup.entry_price >= setup.stop)):
            audit["entry_gapped_past_stop"] += 1
            state = None
            index += 1
            continue
        risk = (setup.entry_price - setup.stop if setup.zone.direction == "long"
                else setup.stop - setup.entry_price)
        if risk <= 0:
            audit["invalid_risk"] += 1
            state = None
            index += 1
            continue
        trade = simulate_trade(
            bars, setup, funding=funding, max_holding_bars=MAX_HOLDING_BARS,
            bar_duration_ms=HOUR_MS, funding_order_policy=FUNDING_ORDER_POLICY,
        )
        if trade is None:
            audit["right_censored_setups"] += 1
            state = None
            break
        if trade.net_return is None:
            audit["funding_unscorable_trades"] += 1
        trades.append(trade)
        state = None
        index = max(index + 1, trade.exit_index)
    return trades, audit


def _trial(barsets_1h, barsets_4h):
    bars_4h_by_symbol = {symbol: bars for symbol, bars, _funding, _excluded in barsets_4h}
    r14._validate_symbols([row[0] for row in barsets_4h], r14._expected_symbols())
    segments_1h, segments_4h = {}, {}
    total_gaps = incomplete = 0
    for symbol, bars, _funding, excluded in barsets_1h:
        segments_1h[symbol], gaps = r14._segments(bars, HOUR_MS)
        total_gaps += gaps
        incomplete += excluded
    for symbol, bars, _funding, excluded in barsets_4h:
        segments_4h[symbol], gaps = r14._segments(bars, r14.ZONE_DURATION_MS)
        total_gaps += gaps
        incomplete += excluded

    returns, events, daily_by_symbol = [], [], {}
    direction_trades, yearly_trades = defaultdict(list), defaultdict(list)
    symbols, audit_total = [], defaultdict(int)
    first_day, last_day = None, None
    unscorable = 0
    for symbol, bars, funding, _excluded in barsets_1h:
        if not bars or not bars_4h_by_symbol.get(symbol):
            continue
        symbols.append(symbol)
        daily_by_symbol[symbol] = {}
        first = bars[0].timestamp // 86_400_000
        last = bars[-1].timestamp // 86_400_000
        first_day = first if first_day is None else min(first_day, first)
        last_day = last if last_day is None else max(last_day, last)
        mapped, unaligned = r14._zones_on_confirmation_segments(
            segments_1h[symbol], segments_4h[symbol])
        audit_total["unaligned_4h_zones"] += unaligned
        for segment, zones in zip(segments_1h[symbol], mapped):
            seg_funding = common._funding_by_timestamp(segment, funding, HOUR_MS)
            trades, audit = _simulate_segment(segment, seg_funding, zones)
            for key, value in audit.items():
                audit_total[key] += value
            for trade in trades:
                entry_ts = segment[trade.setup.entry_index].timestamp
                exit_end = segment[trade.exit_index].timestamp + HOUR_MS
                events.append((symbol, entry_ts, exit_end,
                               trade.exit_reason == "target"))
                direction_trades[trade.setup.zone.direction].append(trade)
                year = datetime.fromtimestamp(entry_ts / 1000, timezone.utc).year
                yearly_trades[str(year)].append(trade)
                if trade.net_return is None:
                    unscorable += 1
                    continue
                pnl = trade_daily_pnl(segment, trade, funding=seg_funding,
                                      bar_duration_ms=HOUR_MS)
                if pnl is None:
                    unscorable += 1
                    continue
                returns.append(trade.net_return)
                for day, value in pnl.items():
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
    result = {
        "status": "unscorable" if len(symbols) < MINIMUM_SYMBOLS else "completed",
        "symbols": len(symbols), "total_trades": len(events),
        "trades": len(returns), "unscorable_funding_trades": unscorable,
        "incomplete_bars_excluded": incomplete, "missing_gap_bars": total_gaps,
        **dict(audit_total), "win_rate": stats.win_rate,
        "profit_factor": stats.profit_factor, "expectancy_bps": stats.expectancy_bps,
        "cumulative_return": curve.cumulative_return,
        "max_drawdown": curve.max_drawdown,
        "annualized_sharpe": curve.annualized_sharpe, "solvent": curve.solvent,
        "m2_signal_count": len(events), "m2_target_hits": hits,
        "m2_target_first_rate": hits / len(events) if events else None,
        "m2_wilson_lower_95": wilson_lower(hits, len(events)),
        "m2_nonoverlap_signal_count": len(nonoverlap),
        "m2_nonoverlap_target_hits": sum(nonoverlap),
        "m2_nonoverlap_target_first_rate": sum(nonoverlap) / len(nonoverlap)
        if nonoverlap else None,
        "m2_nonoverlap_wilson_lower_95": wilson_lower(sum(nonoverlap), len(nonoverlap)),
        "detail": "4h BOS-origin zone invalidation followed by opposite-side first retest; TRAIN only",
    }
    result["direction_attribution"] = {
        direction: _attribution(items) for direction, items in sorted(direction_trades.items())
    }
    result["entry_year_attribution"] = {
        year: _attribution(items) for year, items in sorted(yearly_trades.items())
    }
    return result


def _attribution(trades):
    scoreable = [trade for trade in trades if trade.net_return is not None]
    hits = sum(trade.exit_reason == "target" for trade in trades)
    stats = trade_metrics([trade.net_return for trade in scoreable])
    return {"trades": len(trades), "scoreable_trades": len(scoreable),
            "m2_target_hits": hits, "m2_rate": hits / len(trades) if trades else None,
            "m2_wilson_lower_95": wilson_lower(hits, len(trades)),
            "win_rate": stats.win_rate, "profit_factor": stats.profit_factor,
            "expectancy_bps": stats.expectancy_bps}


def _ledger_state() -> int:
    old_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            rows = 0
            for row in reader:
                if row.get("round") == ROUND:
                    raise RuntimeError("R31 already exists; never rerun the single attempt")
                rows += 1
            return rows
    finally:
        csv.field_size_limit(old_limit)


def _code_hash() -> str:
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _grid_hash(config) -> str:
    raw = json.dumps([config], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, config):
    r19._assert_no_ledger_writer()
    record = {
        "trial_id": f"R31-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "1h/4h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R31 TRAIN test; not OOS or G approval",
    }
    buffer = io.StringIO(newline="")
    csv.DictWriter(buffer, fieldnames=common.FIELDS).writerow(record)
    payload = buffer.getvalue().encode()
    fd = None
    attempted = False
    try:
        fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
        attempted = True
        if os.write(fd, payload) != len(payload):
            raise AppendUncertainError("short append; inspect ledger; do not retry")
        os.fsync(fd)
    except OSError as exc:
        if attempted:
            raise AppendUncertainError("append uncertain; inspect ledger; do not retry") from exc
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError as exc:
                if attempted:
                    raise AppendUncertainError("close failed after append; do not retry") from exc
                raise


def _split_cache_state(data_root, data_access):
    return r29._split_cache_state(data_root, data_access)


def _assert_snapshot(code_sha: str, prereg_sha: str, master_sha: str) -> None:
    if (_code_hash() != code_sha
            or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != prereg_sha
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != master_sha):
        raise RuntimeError("R31 code or prereg changed during run")


def _run_locked(data_root: Path):
    import data_access

    r19._assert_no_ledger_writer()
    rows = _ledger_state()
    config = {**CONFIG, "bonferroni_n": rows + 1}
    if (rows != EXPECTED_ROWS or rows + 1 != EXPECTED_N
            or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError(f"R31 preflight mismatch before market data access: rows={rows}")
    grid_sha, code_sha = _grid_hash(config), _code_hash()
    fingerprint, written = "UNAVAILABLE_BEFORE_TRAIN_INPUT", False
    try:
        split_sha, split_mtime = _split_cache_state(data_root, data_access)
        with heavy_task("R31"):
            bars1 = r14._load_barsets(data_access.iter_train_bars, "1h")
            bars4 = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R31-breaker-flip-retest",
                [(f"{s}:1h", b, f, x) for s, b, f, x in bars1]
                + [(f"{s}:4h", b, {}, x) for s, b, _f, x in bars4])
            usable = r27._usable_symbols(bars1, bars4)
            if len(usable) < MINIMUM_SYMBOLS:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols"}
            else:
                result = _trial(bars1, bars4)
            result["split_manifest_sha256"] = split_sha
            if _split_cache_state(data_root, data_access) != (split_sha, split_mtime):
                raise RuntimeError("fixed split cache changed during R31")
            _assert_snapshot(code_sha, _PREREG_SHA, _MASTER_SHA)
            _append(result, grid_sha, code_sha, fingerprint, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r31_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R31 preregistered TRAIN attempt failed; not G evidence"},
                    grid_sha, code_sha, fingerprint, config)
        raise
    print(json.dumps({"R31": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


def _acquire_run_locks(data_root: Path):
    lock_dir = data_root / "cache/orderblock/runs"
    opened = []
    try:
        for name in (".cointrade_train_trials.lock", ".ob_attrition_train_trials.lock"):
            path = lock_dir / name
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            opened.append((path, fd))
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return opened
    except Exception:
        _release_run_locks(opened)
        raise


def _release_run_locks(opened):
    for path, fd in reversed(opened):
        os.close(fd)
        path.unlink(missing_ok=True)


def run():
    data_root = Path(os.environ.get(
        "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    opened = _acquire_run_locks(data_root)
    try:
        _run_locked(data_root)
    finally:
        _release_run_locks(opened)


if __name__ == "__main__":
    run()
