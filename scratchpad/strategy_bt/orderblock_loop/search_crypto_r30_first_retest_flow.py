"""One preregistered TRAIN test for flow on the first OB retest candle."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import math
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r19_match_attrition_audit as r19
import search_crypto_r29_bos_taker_flow as r29
from metrics import trade_metrics, wilson_lower
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R30-coin"
PREREG_PATH = HERE / "PREREG_R30_FIRST_RETEST_FLOW.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_686
EXPECTED_N = 1_687
CUTOFF_MS = 1_699_286_400_000
HOUR_MS = 3_600_000
MINUTE_MS = 60_000
FLOW_COLUMNS = r29.FLOW_COLUMNS
_PREREG_SHA = "f7af6923a9a38c797d03780b3c76d4c9009d2b755125de8d7736722465ca91e6"
_MASTER_SHA = "57a921ec273a619bfd065ed9892dc8b5185ba3c8e7f79d7f3c1f1d585477c5a4"
CONFIG = {
    "experiment": "R30-FIRST-RETEST-1H-TAKER-BUY-QUOTE-FLOW",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "R14 bos_origin first-touch midpoint reclaim",
    "long_buy_share_min_exclusive": 0.50,
    "short_buy_share_max_exclusive": 0.50, "tie": "reject",
    "aggregate": "60_consecutive_1m_rows_same_1h_confirmation_interval",
    "entry_exit": "fixed_R14_next_open_stop_target_horizon_cost_funding",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py", "search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r29_bos_taker_flow.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "PREREG_R14_FIRST_RETEST_MIDPOINT_CONFIRM.md",
    "PREREG_R29_BOS_TAKER_FLOW.md", "search_crypto_r30_first_retest_flow.py",
    "tests/test_search_crypto_r27_bos_fvg_confluence.py",
    "tests/test_search_crypto_r29_bos_taker_flow.py",
    "tests/test_search_crypto_r30_first_retest_flow.py", "universe/CRYPTO_35.csv",
)


class AppendUncertainError(RuntimeError):
    """Append may be partial; never retry automatically."""


def _aggregate_hour_group(frame: pd.DataFrame, bar, *, cutoff_ms: int = CUTOFF_MS):
    start, end = int(bar.timestamp), int(bar.timestamp) + HOUR_MS
    if end > cutoff_ms:
        raise ValueError("confirmation hour closes after the preregistered cutoff")
    if not set(FLOW_COLUMNS).issubset(frame.columns):
        raise ValueError("one-minute Kline is missing required flow/OHLC columns")
    times = [r29._minute_timestamp(value) for value in frame["open_time"].tolist()]
    selected_idx = [i for i, ts in enumerate(times)
                    if start <= ts < end and ts < cutoff_ms]
    selected = frame.iloc[selected_idx]
    selected_times = [times[i] for i in selected_idx]
    if selected_times != list(range(start, end, MINUTE_MS)):
        raise ValueError("1h confirmation requires exactly 60 ordered consecutive minutes")
    values = {name: [float(v) for v in selected[name].tolist()]
              for name in FLOW_COLUMNS[1:]}
    if any(not math.isfinite(value) for col in values.values() for value in col):
        raise ValueError("non-finite one-minute input")
    for i, (open_, high, low, close) in enumerate(zip(
            values["open"], values["high"], values["low"], values["close"])):
        if low <= 0 or not low <= min(open_, close) <= max(open_, close) <= high:
            raise ValueError(f"inconsistent one-minute OHLC at offset {i}")
        if values["volume"][i] < 0 or values["quote_volume"][i] < 0:
            raise ValueError(f"negative volume at offset {i}")
        if not 0 <= values["taker_buy_quote_volume"][i] <= values["quote_volume"][i]:
            raise ValueError(f"taker-buy quote outside total at offset {i}")
    aggregate = {
        "open": values["open"][0], "high": max(values["high"]),
        "low": min(values["low"]), "close": values["close"][-1],
        "volume": sum(values["volume"]), "quote_volume": sum(values["quote_volume"]),
        "taker_buy_quote_volume": sum(values["taker_buy_quote_volume"]),
    }
    if aggregate["quote_volume"] <= 0:
        raise ValueError("1h quote volume must be positive")
    for field in ("open", "high", "low", "close", "volume"):
        if not r29._close(aggregate[field], float(getattr(bar, field))):
            raise ValueError(f"one-minute reaggregation disagrees with cached 1h {field}")
    aggregate["buy_share"] = aggregate["taker_buy_quote_volume"] / aggregate["quote_volume"]
    return aggregate


def _build_flow_map(data_root: Path, barsets_1h):
    source = data_root / "external/crypto/binance/um_klines_1m"
    by_id: dict[int, float] = {}
    digest = hashlib.sha256()
    stats = {"flow_symbols": 0, "flow_1h_bars_expected": 0,
             "flow_1h_bars_validated": 0, "flow_minutes_read": 0,
             "flow_source_files": 0}
    for symbol, bars, _funding, _excluded in barsets_1h:
        if not bars:
            continue
        stats["flow_symbols"] += 1
        stats["flow_1h_bars_expected"] += len(bars)
        months: dict[str, list] = defaultdict(list)
        for bar in bars:
            month = datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc).strftime("%Y-%m")
            months[month].append(bar)
        for month, month_bars in sorted(months.items()):
            if month > "2023-11":
                raise ValueError("post-cutoff monthly file requested by TRAIN bars")
            path = source / symbol / f"{month}.parquet"
            if not path.is_file():
                raise FileNotFoundError(f"one-minute source missing for {symbol} {month}")
            frame = pd.read_parquet(path, columns=list(FLOW_COLUMNS),
                                    filters=[("open_time", "<", CUTOFF_MS)])
            stats["flow_source_files"] += 1
            if frame.empty:
                raise ValueError(f"empty TRAIN one-minute source for {symbol} {month}")
            parsed = [r29._minute_timestamp(value) for value in frame["open_time"].tolist()]
            if any(ts >= CUTOFF_MS for ts in parsed):
                raise ValueError("post-cutoff minute returned by parquet reader")
            if len(set(parsed)) != len(parsed):
                raise ValueError(f"duplicate one-minute timestamp for {symbol} {month}")
            stats["flow_minutes_read"] += len(frame)
            for bar in month_bars:
                values = _aggregate_hour_group(frame, bar)
                by_id[id(bar)] = values["buy_share"]
                stats["flow_1h_bars_validated"] += 1
                digest.update(symbol.encode())
                digest.update(str(bar.timestamp).encode())
                for key in ("open", "high", "low", "close", "volume",
                            "quote_volume", "taker_buy_quote_volume"):
                    digest.update(float(values[key]).hex().encode())
    if stats["flow_1h_bars_validated"] != stats["flow_1h_bars_expected"]:
        raise ValueError("not every fixed TRAIN 1h bar has validated minute data")
    return by_id, digest.hexdigest(), stats


def _flow_passes(share: float, direction: str) -> bool:
    if not math.isfinite(share) or not 0 <= share <= 1:
        raise ValueError("buy_share must be finite in [0, 1]")
    if direction == "long":
        return share > 0.50
    if direction == "short":
        return share < 0.50
    return False


def _attribution(trades):
    scoreable = [trade for trade in trades if trade.net_return is not None]
    hits = sum(trade.exit_reason == "target" for trade in trades)
    stats = trade_metrics([trade.net_return for trade in scoreable])
    return {"trades": len(trades), "scoreable_trades": len(scoreable),
            "m2_target_hits": hits, "m2_rate": hits / len(trades) if trades else None,
            "m2_wilson_lower_95": wilson_lower(hits, len(trades)),
            "win_rate": stats.win_rate, "profit_factor": stats.profit_factor,
            "expectancy_bps": stats.expectancy_bps}


def _trial_with_flow(barsets_1h, barsets_4h, flow_by_bar_id):
    counts = {"flow_setups_evaluated": 0, "flow_qualified_setups": 0,
              "flow_rejected_setups": 0}
    captured, symbol_by_bar_id = [], {}
    for symbol, bars, *_ in barsets_1h:
        for bar in bars:
            symbol_by_bar_id[id(bar)] = symbol
    original_setup, original_segment = r14._make_setup, r14._simulate_segment

    def filtered_setup(zone, confirmation_bar, next_bar, index):
        setup, reason = original_setup(zone, confirmation_bar, next_bar, index)
        if setup is None:
            return None, reason
        share = flow_by_bar_id.get(id(confirmation_bar))
        if share is None:
            raise ValueError("R14 setup has no validated first-retest flow feature")
        counts["flow_setups_evaluated"] += 1
        if _flow_passes(share, zone.direction):
            counts["flow_qualified_setups"] += 1
            return setup, reason
        counts["flow_rejected_setups"] += 1
        return None, "flow_mismatch"

    def capture_segment(bars, funding, zones):
        trades, audit = original_segment(bars, funding, zones)
        symbol = symbol_by_bar_id.get(id(bars[0])) if bars else None
        if symbol is None:
            raise ValueError("R14 segment cannot be mapped to fixed symbol")
        for trade in trades:
            captured.append((symbol, bars[trade.setup.entry_index].timestamp,
                             trade.setup.zone.direction, trade))
        return trades, audit

    r14._make_setup, r14._simulate_segment = filtered_setup, capture_segment
    try:
        result = r14._trial(barsets_1h, barsets_4h)
    finally:
        r14._make_setup, r14._simulate_segment = original_setup, original_segment
    result.update(counts)
    by_direction, by_year = defaultdict(list), defaultdict(list)
    for _symbol, timestamp, direction, trade in captured:
        by_direction[direction].append(trade)
        by_year[str(datetime.fromtimestamp(timestamp / 1000, timezone.utc).year)].append(trade)
    result["direction_attribution"] = {
        key: _attribution(value) for key, value in sorted(by_direction.items())}
    result["entry_year_attribution"] = {
        key: _attribution(value) for key, value in sorted(by_year.items())}
    result["detail"] = "R14 first-retest lifecycle with confirmation-candle flow; TRAIN only"
    return result


def _ledger_state() -> int:
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
                    raise RuntimeError("R30 already exists; single attempt cannot repeat")
                count += 1
            return count
    finally:
        csv.field_size_limit(old_limit)


def _code_hash() -> str:
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _grid_hash(config):
    return hashlib.sha256(json.dumps([config], sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, denominator, config):
    r19._assert_no_ledger_writer()
    row = {
        "trial_id": f"R30-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "1h/4h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R30 TRAIN test; not OOS or G approval",
    }
    buffer = io.StringIO(newline="")
    csv.DictWriter(buffer, fieldnames=common.FIELDS).writerow(row)
    payload = buffer.getvalue().encode()
    fd = None
    attempted = False
    try:
        fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
        attempted = True
        written = os.write(fd, payload)
        if written != len(payload):
            raise AppendUncertainError("short append; inspect ledger, never retry")
        os.fsync(fd)
    except OSError as exc:
        if attempted:
            raise AppendUncertainError("append uncertain; inspect ledger, never retry") from exc
        raise
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError as exc:
                if attempted:
                    raise AppendUncertainError(
                        "close failed after append; inspect ledger, never retry"
                    ) from exc
                raise


def _split_cache_state(data_root: Path, data_access):
    return r29._split_cache_state(data_root, data_access)


def _run_locked(data_root: Path):
    import data_access

    r19._assert_no_ledger_writer()
    rows = _ledger_state()
    config = {**CONFIG, "bonferroni_n": rows + 1}
    grid_sha, code_sha = _grid_hash(config), _code_hash()
    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    master_sha = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
    if (rows != EXPECTED_ROWS or rows + 1 != EXPECTED_N
            or prereg_sha != _PREREG_SHA or master_sha != _MASTER_SHA):
        raise RuntimeError(f"R30 preflight mismatch before market data access: rows={rows}")
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    written = False
    try:
        split_sha, split_mtime = _split_cache_state(data_root, data_access)
        with heavy_task("R30"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R30-first-retest-flow",
                [(f"{s}:1h", b, f, x) for s, b, f, x in barsets_1h]
                + [(f"{s}:4h", b, {}, x) for s, b, _f, x in barsets_4h])
            usable = r29.r27._usable_symbols(barsets_1h, barsets_4h)
            if len(usable) < r14.MINIMUM_SYMBOLS:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols"}
            else:
                flow, flow_sha, flow_stats = _build_flow_map(data_root, barsets_1h)
                result = _trial_with_flow(barsets_1h, barsets_4h, flow)
                result.update(flow_stats)
                result["flow_feature_sha256"] = flow_sha
            result["split_manifest_sha256"] = split_sha
            if _split_cache_state(data_root, data_access) != (split_sha, split_mtime):
                raise RuntimeError("fixed split cache changed during R30")
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R30 code or prereg changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint, EXPECTED_N, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r30_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R30 preregistered TRAIN attempt failed; not G evidence"},
                    grid_sha, code_sha, fingerprint, EXPECTED_N, config)
        raise
    print(json.dumps({"R30": result, "grid_sha": grid_sha,
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
