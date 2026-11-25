"""Single cutoff-safe TRAIN test for BOS-origin zones with same-way FVG."""
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
from crypto import (Trade, _atr, _confirmed_pivot_levels, _validate)
from metrics import trade_metrics, wilson_lower
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R27-coin"
PREREG_PATH = HERE / "PREREG_R27_BOS_FVG_CONFLUENCE.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_683
EXPECTED_N = 1_684
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R27-BOS-DIRECTIONAL-3BAR-FVG",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "bos_origin", "fvg": "long:low[i]>high[i-2];short:high[i]<low[i-2]",
    "fvg_at": "completed_BOS_bar_close", "fvg_min_gap": None,
    "entry_exit": "fixed_R14_first_retest_midpoint_next_open_0.50R",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "search_crypto_r27_bos_fvg_confluence.py",
    "tests/test_search_crypto_r27_bos_fvg_confluence.py",
    "universe/CRYPTO_35.csv",
)


class AppendUncertainError(RuntimeError):
    """An append may be partial or durable state could not be confirmed."""


def _has_directional_fvg(bars, index: int, direction: str) -> bool:
    if direction not in ("long", "short") or index < 2 or index >= len(bars):
        return False
    prior, middle, bos = bars[index - 2], bars[index - 1], bars[index]
    if (not prior.complete or not middle.complete or not bos.complete
            or middle.timestamp - prior.timestamp != r14.ZONE_DURATION_MS
            or bos.timestamp - middle.timestamp != r14.ZONE_DURATION_MS):
        return False
    if direction == "long":
        return bos.low > prior.high
    return bos.high < prior.low


def _filtered_zone_builder(stats):
    original = r14.r4_zones

    def build(bars, definition):
        zones = original(bars, definition)
        if definition != "bos_origin":
            return zones
        stats["raw_bos_events"] += _raw_bos_events(bars)
        stats["bos_origin_zones"] += len(zones)
        accepted = []
        for zone in zones:
            if _has_directional_fvg(bars, zone.signal_index, zone.direction):
                stats["fvg_qualified_zones"] += 1
                accepted.append(zone)
            else:
                stats["fvg_rejected_zones"] += 1
        return accepted

    return original, build


def _raw_bos_events(bars) -> int:
    eligible = _validate(bars)
    pivots = _confirmed_pivot_levels(bars, eligible)
    count = 0
    for index in eligible:
        if index < 20 or _atr(bars, index) is None:
            continue
        pivot_high, pivot_low = pivots[index]
        up = pivot_high is not None and bars[index].close > pivot_high
        down = pivot_low is not None and bars[index].close < pivot_low
        count += up != down
    return count


def _attribution_row(trades: list[Trade]):
    scoreable = [trade for trade in trades if trade.net_return is not None]
    hits = sum(trade.exit_reason == "target" for trade in trades)
    metrics = trade_metrics([trade.net_return for trade in scoreable])
    return {
        "trades": len(trades), "scoreable_trades": len(scoreable),
        "m2_hits": hits, "m2_rate": hits / len(trades) if trades else None,
        "m2_wilson_lower_95": wilson_lower(hits, len(trades)),
        "win_rate": metrics.win_rate, "profit_factor": metrics.profit_factor,
        "expectancy_bps": metrics.expectancy_bps,
    }


def _count_activated_zones(bars, funding, zones_by_index) -> int:
    """Replay only R14 lifecycle transitions and count actual activations."""
    active = None
    activated = index = 0
    while index < len(bars):
        zone = zones_by_index.get(index)
        if active is None:
            if zone is not None:
                active = zone
                activated += 1
            index += 1
            continue
        age = index - active.signal_index
        if age > r14.DEADLINE:
            active = None
            continue
        if age == 0:
            index += 1
            continue
        bar = bars[index]
        invalid = (bar.low <= active.low if active.direction == "long"
                   else bar.high >= active.high)
        overlaps = bar.low <= active.high and bar.high >= active.low
        if invalid:
            active = None
            index += 1
            continue
        if not overlaps:
            index += 1
            continue
        if index + 1 >= len(bars) or not bars[index + 1].complete:
            break
        setup, _reason = r14._make_setup(active, bar, bars[index + 1], index)
        if setup is None:
            active = None
            index += 1
            continue
        trade = r14.simulate_trade(
            bars, setup, funding=funding,
            max_holding_bars=r14.MAX_HOLDING_BARS,
            bar_duration_ms=r14.DURATION_MS,
            funding_order_policy=r14.FUNDING_ORDER_POLICY,
        )
        if trade is None:
            break
        active = None
        index = max(index + 1, trade.exit_index)
    return activated


def _trial_with_fvg(barsets_1h, barsets_4h):
    funnel = {"raw_bos_events": 0, "bos_origin_zones": 0,
              "fvg_qualified_zones": 0, "fvg_rejected_zones": 0,
              "mapped_zones": 0, "activated_zones": 0}
    captured = []
    original_builder, filtered_builder = _filtered_zone_builder(funnel)
    original_segment = r14._simulate_segment
    original_mapper = r14._zones_on_confirmation_segments

    def capture_mapping(segments_1h, segments_4h):
        mapped, unaligned = original_mapper(segments_1h, segments_4h)
        funnel["mapped_zones"] += sum(len(zones) for zones in mapped)
        return mapped, unaligned

    def capture_segment(bars, funding, zones):
        trades, audit = original_segment(bars, funding, zones)
        funnel["activated_zones"] += _count_activated_zones(bars, funding, zones)
        for trade in trades:
            captured.append((bars[trade.setup.entry_index].timestamp,
                             trade.setup.zone.direction, trade))
        return trades, audit

    r14.r4_zones = filtered_builder
    r14._zones_on_confirmation_segments = capture_mapping
    r14._simulate_segment = capture_segment
    try:
        result = r14._trial(barsets_1h, barsets_4h)
    finally:
        r14.r4_zones = original_builder
        r14._zones_on_confirmation_segments = original_mapper
        r14._simulate_segment = original_segment
    result.update(funnel)
    by_direction = defaultdict(list)
    by_year = defaultdict(list)
    for timestamp, direction, trade in captured:
        by_direction[direction].append(trade)
        year = datetime.fromtimestamp(timestamp / 1000, timezone.utc).year
        by_year[str(year)].append(trade)
    result["direction_attribution"] = {
        key: _attribution_row(value) for key, value in sorted(by_direction.items())
    }
    result["entry_year_attribution"] = {
        key: _attribution_row(value) for key, value in sorted(by_year.items())
    }
    return result


def _ledger_state():
    old_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            count = 0
            for row in reader:
                if row.get("round") == ROUND:
                    raise RuntimeError("R27 already exists; preregistered single attempt must not repeat")
                count += 1
    finally:
        csv.field_size_limit(old_limit)
    return count


def _code_hash():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, denominator=EXPECTED_N):
    import search_crypto_r19_match_attrition_audit as r19
    r19._assert_no_ledger_writer()
    row = {
        "trial_id": f"R27-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R27 TRAIN FVG filter; not OOS or G approval",
    }
    output = io.StringIO(newline="")
    csv.DictWriter(output, fieldnames=common.FIELDS).writerow(row)
    payload = output.getvalue().encode()
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    write_attempted = False
    try:
        try:
            write_attempted = True
            written = os.write(fd, payload)
        except OSError as exc:
            raise AppendUncertainError("write outcome uncertain; inspect ledger tail") from exc
        if written != len(payload):
            raise AppendUncertainError("short append; ledger tail requires inspection")
        try:
            os.fsync(fd)
        except OSError as exc:
            raise AppendUncertainError("row may be present but fsync failed; inspect ledger") from exc
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            if write_attempted:
                raise AppendUncertainError("close failed after append attempt; inspect ledger tail") from exc
            raise


def _usable_symbols(barsets_1h, barsets_4h):
    symbols_1h = {symbol for symbol, bars, *_ in barsets_1h if bars}
    symbols_4h = {symbol for symbol, bars, *_ in barsets_4h if bars}
    return symbols_1h & symbols_4h


def _run_locked():
    import data_access
    import search_crypto_r19_match_attrition_audit as r19

    r19._assert_no_ledger_writer()
    actual_rows = _ledger_state()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    prereg_changed = (
        hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
        or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA
    )
    if prereg_changed or actual_rows != EXPECTED_ROWS:
        reason = ("R27 prereg changed after import" if prereg_changed else
                  f"R27 denominator mismatch before data access: {actual_rows}")
        _append({"status": "failed_before_data_access", "failure_stage": "preflight",
                 "failure_type": "PreregMismatch" if prereg_changed else "DenominatorMismatch",
                 "detail": reason}, grid_sha, code_sha,
                "UNAVAILABLE_BEFORE_TRAIN_INPUT", actual_rows + 1)
        raise RuntimeError(reason)
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    written = False
    try:
        with heavy_task("R27"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R27-4h-1h-train",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h],
            )
            usable = _usable_symbols(barsets_1h, barsets_4h)
            if len(usable) < r14.MINIMUM_SYMBOLS:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols across both timeframes"}
            else:
                result = _trial_with_fvg(barsets_1h, barsets_4h)
                result["detail"] = "R14 unchanged lifecycle after BOS-close FVG filter; TRAIN only"
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R27 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r27_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R27 preregistered attempt failed; not G evidence"},
                    grid_sha, code_sha, fingerprint)
        raise
    print(json.dumps({"R27": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


def _acquire_run_locks(data_root: Path):
    lock_dir = data_root / "cache/orderblock/runs"
    paths = [lock_dir / name for name in (
        ".cointrade_train_trials.lock", ".ob_attrition_train_trials.lock")]
    opened = []
    try:
        for path in paths:
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
        _run_locked()
    finally:
        _release_run_locks(opened)


if __name__ == "__main__":
    run()
