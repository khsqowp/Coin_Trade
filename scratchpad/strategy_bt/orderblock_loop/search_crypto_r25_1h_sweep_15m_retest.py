"""Single TRAIN transfer test for 1h pre-BOS sweeps and 15m first retests."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r14 as r14
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R25-coin"
PREREG_PATH = HERE / "PREREG_R25_1H_SWEEP_15M_RETEST.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_681
EXPECTED_N = 1_682
BAR_15M_MS = 15 * 60_000
BAR_1H_MS = 60 * 60_000
SWEEP_LOOKBACK = 20
BOS_CONFIRM_BARS = 3
DEADLINE_15M_BARS = 24
MAX_HOLDING_15M_BARS = 24
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_SHA = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
CONFIG = {
    "experiment": "R25-1H-PRE-BOS-SWEEP-15M-FIRST-RETEST",
    "zone_timeframe": "1h", "confirmation_timeframe": "15m",
    "definition": "bos_origin", "sweep_lookback_bars": SWEEP_LOOKBACK,
    "sweep_to_bos_bars": [1, BOS_CONFIRM_BARS],
    "long_sweep": "low < prior20_min_low and close > prior20_min_low",
    "short_sweep": "high > prior20_max_high and close < prior20_max_high",
    "entry": "first 15m retest midpoint reclaim then next 15m open",
    "stop_buffer_atr": r14.STOP_BUFFER_ATR,
    "reward_r": r14.REWARD_R,
    "deadline_15m_bars": DEADLINE_15M_BARS,
    "max_holding_15m_bars": MAX_HOLDING_15M_BARS,
    "round_trip_cost_bps": 12,
    "funding_order_policy": r14.FUNDING_ORDER_POLICY,
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}


class AppendRollbackError(OSError):
    """A partial ledger append could not be safely rolled back."""


def _external_sweep(bars, index, direction):
    if index < SWEEP_LOOKBACK:
        return False
    prior = bars[index - SWEEP_LOOKBACK:index]
    level = (min(bar.low for bar in prior) if direction == "long"
             else max(bar.high for bar in prior))
    bar = bars[index]
    if direction == "long":
        return bar.low < level and bar.close > level
    return bar.high > level and bar.close < level


def _pre_bos_sweep(bars, bos_index, direction):
    start = max(SWEEP_LOOKBACK, bos_index - BOS_CONFIRM_BARS)
    return any(_external_sweep(bars, index, direction)
               for index in range(start, bos_index))


@contextmanager
def _r14_15m_1h_clock():
    names = ("DURATION_MS", "ZONE_DURATION_MS", "DEADLINE",
             "MAX_HOLDING_BARS", "REWARD_R", "STOP_BUFFER_ATR")
    before = {name: getattr(r14, name) for name in names}
    try:
        r14.DURATION_MS = BAR_15M_MS
        r14.ZONE_DURATION_MS = BAR_1H_MS
        r14.DEADLINE = DEADLINE_15M_BARS
        r14.MAX_HOLDING_BARS = MAX_HOLDING_15M_BARS
        yield
    finally:
        for name, value in before.items():
            setattr(r14, name, value)


def _filtered_zone_builder(stats):
    original = r14.r4_zones

    def build(bars, definition):
        zones = original(bars, definition)
        if definition != "bos_origin":
            return zones
        stats["raw_bos_zones"] += len(zones)
        kept = [zone for zone in zones
                if _pre_bos_sweep(bars, zone.signal_index, zone.direction)]
        stats["pre_bos_sweep_zones"] += len(kept)
        return kept

    return original, build


def _trial_with_pre_bos_sweep(barsets_15m, barsets_1h):
    stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
    original_builder, filtered_builder = _filtered_zone_builder(stats)
    with _r14_15m_1h_clock():
        r14.r4_zones = filtered_builder
        try:
            result = r14._trial(barsets_15m, barsets_1h)
        finally:
            r14.r4_zones = original_builder
    result.update(stats)
    return result


def _usable_symbols(barsets_15m, barsets_1h):
    symbols_15m = {symbol for symbol, bars, _funding, _excluded in barsets_15m if bars}
    symbols_1h = {symbol for symbol, bars, _funding, _excluded in barsets_1h if bars}
    return symbols_15m & symbols_1h


def _unscorable_result(symbol_count):
    return {"status": "unscorable", "symbols": symbol_count,
            "detail": "fewer than 30 symbols have both cutoff-safe timeframes"}


def _validate_cutoff(barsets, duration_ms, cutoff_ms):
    for symbol, bars, _funding, _excluded in barsets:
        if any(bar.timestamp + duration_ms > cutoff_ms for bar in bars):
            raise ValueError(f"post-cutoff completed bar found for {symbol}")


def _ledger_rows():
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            return sum(1 for _ in reader)
    finally:
        csv.field_size_limit(old)


def _code_hash():
    names = (
        "crypto.py", "search_crypto.py", "search_crypto_r14.py",
        "search_crypto_r19_match_attrition_audit.py", "data_access.py",
        "metrics.py", "resource_guard.py", "PREREG.md", PREREG_PATH.name,
        "search_crypto_r25_1h_sweep_15m_retest.py",
        "tests/test_search_crypto_r25_1h_sweep_15m_retest.py",
        "universe/CRYPTO_35.csv",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _append(result, grid_sha, code_sha, fingerprint):
    import search_crypto_r19_match_attrition_audit as r19
    r19._assert_no_ledger_writer()
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        if tuple(next(csv.reader(stream))) != common.FIELDS:
            raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    row = {
        "trial_id": f"R25-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "1h/15m bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": EXPECTED_N,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R25 TRAIN timeframe-transfer test; not OOS or G approval",
    }
    out = io.StringIO(newline="")
    csv.DictWriter(out, fieldnames=common.FIELDS).writerow(row)
    payload = out.getvalue().encode()
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    before = os.fstat(fd).st_size
    try:
        if os.write(fd, payload) != len(payload):
            try:
                os.ftruncate(fd, before)
            except OSError as rollback_error:
                raise AppendRollbackError("ledger append rollback failed") from rollback_error
            raise OSError("short ledger append rolled back")
    finally:
        os.close(fd)


def _load_fixed_universe(loader, timeframe, expected_symbols):
    if timeframe not in ("15m", "1h"):
        raise ValueError(f"unsupported R25 timeframe: {timeframe}")
    duration = BAR_15M_MS if timeframe == "15m" else BAR_1H_MS
    loaded = {}
    for symbol, bars, funding in loader(timeframe=timeframe):
        if symbol not in expected_symbols or symbol in loaded:
            raise ValueError(f"unexpected or duplicate {timeframe} symbol: {symbol}")
        loaded[symbol] = (bars, funding)
    barsets = []
    for symbol in sorted(expected_symbols):
        bars, funding = loaded.get(symbol, ([], {}))
        closed = [bar for bar in bars if bar.complete]
        r14._validate_barset(symbol, closed, funding, duration)
        barsets.append((symbol, closed, funding, len(bars) - len(closed)))
    return barsets


def _load_pair(data_access):
    expected_symbols = r14._expected_symbols()
    with _r14_15m_1h_clock():
        bars_15m = _load_fixed_universe(
            data_access.iter_train_bars, "15m", expected_symbols)
        bars_1h = _load_fixed_universe(
            data_access.iter_train_bars, "1h", expected_symbols)
    cutoff = (data_access.CRYPTO_COMMON_SPLIT_MS
              + max(data_access.TIMEFRAME_MS.values()))
    _validate_cutoff(bars_15m, BAR_15M_MS, cutoff)
    _validate_cutoff(bars_1h, BAR_1H_MS, cutoff)
    return bars_15m, bars_1h, _usable_symbols(bars_15m, bars_1h)


def _run_locked():
    import data_access
    import search_crypto_r19_match_attrition_audit as r19

    if (hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        raise RuntimeError("R25 prereg changed after import")
    actual_rows = _ledger_rows()
    if actual_rows != EXPECTED_ROWS:
        raise RuntimeError(f"R25 denominator mismatch before data access: {actual_rows}")
    r19._assert_no_ledger_writer()
    grid_sha = hashlib.sha256(json.dumps([CONFIG], sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    code_sha = _code_hash()
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    result_written = False
    try:
        with heavy_task("R25"):
            barsets_15m, barsets_1h, usable = _load_pair(data_access)
            fingerprint = common._train_input_fingerprint(
                "R25-1h-15m-train",
                [(f"{symbol}:15m", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_15m]
                + [(f"{symbol}:1h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_1h])
            if len(usable) < r14.MINIMUM_SYMBOLS:
                result = _unscorable_result(len(usable))
            else:
                result = _trial_with_pre_bos_sweep(barsets_15m, barsets_1h)
                result["detail"] = "1h pre-BOS external sweep + 15m first retest; TRAIN only"
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R25 source/prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint)
            result_written = True
        try:
            r19._assert_no_ledger_writer()
        except Exception as exc:
            print(json.dumps({"R25_post_append_writer_warning": type(exc).__name__}),
                  file=sys.stderr, flush=True)
    except Exception as exc:
        if not result_written and not isinstance(exc, AppendRollbackError):
            _append({"status": "failed", "failure_stage": "r25_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R25 preregistered attempt failed; no G approval"},
                    grid_sha, code_sha, fingerprint)
        raise
    print(json.dumps({"R25": result, "grid_sha": grid_sha,
                      "code_sha": code_sha, "train_fingerprint": fingerprint},
                     sort_keys=True), flush=True)


def run():
    data_root = Path(os.environ.get(
        "TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    lock_path = data_root / "cache/orderblock/runs/.cointrade_train_trials.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _run_locked()
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    run()
