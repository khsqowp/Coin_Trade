"""Single preregistered TRAIN test for BOS-aligned taker-buy quote flow."""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import math
import numbers
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import search_crypto as common
import search_crypto_r14 as r14
import search_crypto_r27_bos_fvg_confluence as r27
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
ROUND = "R29-coin"
PREREG_PATH = HERE / "PREREG_R29_BOS_TAKER_FLOW.md"
MASTER_PATH = HERE / "PREREG.md"
EXPECTED_ROWS = 1_685
EXPECTED_N = 1_686
CUTOFF_MS = 1_699_286_400_000
BAR_MS = 4 * 60 * 60_000
MINUTE_MS = 60_000
FLOW_COLUMNS = (
    "open_time", "open", "high", "low", "close", "volume",
    "quote_volume", "taker_buy_quote_volume",
)
_PREREG_SHA = "065c152b5898d691f0278c37b2ee5ecc9a54a43dc88716afb717c39bcf5773ab"
_MASTER_SHA = "fa77fa8fa539ddf6880b53cdfbdf9365937579ea1eb603024322b1166f2cb46a"
CONFIG = {
    "experiment": "R29-BOS-4H-TAKER-BUY-QUOTE-FLOW",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "bos_origin", "long_buy_share_min_exclusive": 0.50,
    "short_buy_share_max_exclusive": 0.50, "tie": "reject",
    "aggregate": "240_consecutive_1m_rows_same_4h_interval",
    "entry_exit": "fixed_R14_first_retest_midpoint_next_open_0.50R",
    "cutoff": "2023-11-06T16:00:00Z", "bonferroni_n": EXPECTED_N,
}
CODE_FILES = (
    "crypto.py", "search_crypto.py", "search_crypto_r14.py",
    "search_crypto_r19_match_attrition_audit.py", "data_access.py", "metrics.py",
    "resource_guard.py", "PREREG.md", PREREG_PATH.name,
    "PREREG_R14_FIRST_RETEST_MIDPOINT_CONFIRM.md",
    "PREREG_R27_BOS_FVG_CONFLUENCE.md", "PREREG_R28_BOS_CLOSE_LOCATION.md",
    "search_crypto_r27_bos_fvg_confluence.py",
    "tests/test_search_crypto_r27_bos_fvg_confluence.py",
    "search_crypto_r28_bos_close_location.py",
    "tests/test_search_crypto_r28_bos_close_location.py",
    "search_crypto_r29_bos_taker_flow.py",
    "tests/test_search_crypto_r29_bos_taker_flow.py", "universe/CRYPTO_35.csv",
)


class AppendUncertainError(RuntimeError):
    """The append may be partial and must not be retried automatically."""


def _close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)


def _minute_timestamp(value) -> int:
    if (isinstance(value, bool) or not isinstance(value, numbers.Real)
            or not math.isfinite(float(value)) or not float(value).is_integer()):
        raise ValueError("one-minute open_time must be a finite integer millisecond")
    return int(value)


def _aggregate_4h_group(frame: pd.DataFrame, bar, *, cutoff_ms: int = CUTOFF_MS):
    """Validate one complete four-hour candle and return its quote-flow ratio."""
    start = int(bar.timestamp)
    end = start + BAR_MS
    if end > cutoff_ms:
        raise ValueError("4h candle closes after the preregistered TRAIN cutoff")
    if not set(FLOW_COLUMNS).issubset(frame.columns):
        raise ValueError("one-minute Kline is missing required flow/OHLC columns")
    times = [_minute_timestamp(value) for value in frame["open_time"].tolist()]
    eligible = [(index, timestamp) for index, timestamp in enumerate(times)
                if start <= timestamp < end and timestamp < cutoff_ms]
    selected = frame.iloc[[index for index, _ in eligible]].copy()
    selected_times = [timestamp for _, timestamp in eligible]
    expected_times = list(range(start, end, MINUTE_MS))
    if selected_times != expected_times:
        raise ValueError("4h flow input must contain exactly 240 ordered consecutive minutes")

    columns = {}
    for name in FLOW_COLUMNS[1:]:
        values = [float(value) for value in selected[name].tolist()]
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"non-finite one-minute {name}")
        columns[name] = values
    for index, (open_, high, low, close) in enumerate(zip(
            columns["open"], columns["high"], columns["low"], columns["close"])):
        if low <= 0 or not low <= min(open_, close) <= max(open_, close) <= high:
            raise ValueError(f"inconsistent one-minute OHLC at offset {index}")
        if columns["volume"][index] < 0 or columns["quote_volume"][index] < 0:
            raise ValueError(f"negative one-minute volume at offset {index}")
        if not 0 <= columns["taker_buy_quote_volume"][index] <= columns["quote_volume"][index]:
            raise ValueError(f"taker-buy quote volume outside total quote volume at offset {index}")

    aggregate = {
        "open": columns["open"][0], "high": max(columns["high"]),
        "low": min(columns["low"]), "close": columns["close"][-1],
        "volume": sum(columns["volume"]),
        "quote_volume": sum(columns["quote_volume"]),
        "taker_buy_quote_volume": sum(columns["taker_buy_quote_volume"]),
    }
    if aggregate["quote_volume"] <= 0:
        raise ValueError("4h total quote volume must be positive")
    for field in ("open", "high", "low", "close", "volume"):
        if not _close(aggregate[field], float(getattr(bar, field))):
            raise ValueError(f"one-minute reaggregation disagrees with cached 4h {field}")
    aggregate["buy_share"] = (
        aggregate["taker_buy_quote_volume"] / aggregate["quote_volume"]
    )
    return aggregate


def _flow_passes(share: float, direction: str) -> bool:
    if not math.isfinite(share) or not 0 <= share <= 1:
        raise ValueError("buy_share must be a finite ratio in [0, 1]")
    if direction == "long":
        return share > 0.50
    if direction == "short":
        return share < 0.50
    return False


def _months_for_bars(bars) -> list[str]:
    return sorted({datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc).strftime("%Y-%m")
                   for bar in bars})


def _build_flow_map(data_root: Path, barsets_4h):
    source = data_root / "external/crypto/binance/um_klines_1m"
    flow_by_bar_id: dict[int, float] = {}
    digest = hashlib.sha256()
    stats = {"symbols": 0, "four_hour_bars": 0, "matched_flow_bars": 0,
             "minutes_read": 0, "source_files": 0}
    for symbol, bars, _funding, _excluded in barsets_4h:
        if not bars:
            continue
        stats["symbols"] += 1
        by_month: dict[str, list] = defaultdict(list)
        for bar in bars:
            by_month[datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc)
                     .strftime("%Y-%m")].append(bar)
        for month, month_bars in sorted(by_month.items()):
            if month > "2023-11":
                raise ValueError("post-cutoff monthly file requested by TRAIN bars")
            path = source / symbol / f"{month}.parquet"
            if not path.is_file():
                raise FileNotFoundError(f"one-minute source missing for {symbol} {month}")
            frame = pd.read_parquet(path, columns=list(FLOW_COLUMNS),
                                    filters=[("open_time", "<", CUTOFF_MS)])
            stats["source_files"] += 1
            if frame.empty:
                raise ValueError(f"one-minute source has no TRAIN rows for {symbol} {month}")
            frame = frame.sort_values("open_time", kind="stable").reset_index(drop=True)
            if frame["open_time"].duplicated().any():
                raise ValueError(f"duplicate one-minute timestamps for {symbol} {month}")
            stats["minutes_read"] += len(frame)
            for bar in month_bars:
                flow = _aggregate_4h_group(frame, bar)
                flow_by_bar_id[id(bar)] = flow["buy_share"]
                stats["matched_flow_bars"] += 1
                stats["four_hour_bars"] += 1
                digest.update(symbol.encode())
                digest.update(str(bar.timestamp).encode())
                for key in ("open", "high", "low", "close", "volume",
                            "quote_volume", "taker_buy_quote_volume"):
                    digest.update(float(flow[key]).hex().encode())
    if stats["matched_flow_bars"] != sum(len(bars) for _, bars, *_ in barsets_4h):
        raise ValueError("not every completed TRAIN 4h candle has validated one-minute flow")
    return flow_by_bar_id, digest.hexdigest(), stats


def _flow_filter(flow_by_bar_id, stats):
    def predicate(bars, index: int, direction: str) -> bool:
        if direction not in ("long", "short") or index < 0 or index >= len(bars):
            return False
        bar = bars[index]
        share = flow_by_bar_id.get(id(bar))
        if share is None:
            raise ValueError("BOS candle has no validated taker-flow record")
        stats["flow_evaluated_zones"] += 1
        passed = _flow_passes(share, direction)
        if passed:
            stats["flow_qualified_zones"] += 1
        else:
            stats["flow_rejected_zones"] += 1
        return passed
    return predicate


def _trial_with_flow(barsets_1h, barsets_4h, flow_by_bar_id):
    stats = {"flow_evaluated_zones": 0, "flow_qualified_zones": 0,
             "flow_rejected_zones": 0}
    original = r27._has_directional_fvg
    r27._has_directional_fvg = _flow_filter(flow_by_bar_id, stats)
    try:
        result = r27._trial_with_fvg(barsets_1h, barsets_4h)
    finally:
        r27._has_directional_fvg = original
    result["flow_evaluated_zones"] = stats["flow_evaluated_zones"]
    result["flow_qualified_zones"] = stats["flow_qualified_zones"]
    result["flow_rejected_zones"] = stats["flow_rejected_zones"]
    result.pop("fvg_qualified_zones", None)
    result.pop("fvg_rejected_zones", None)
    result["detail"] = "R14 lifecycle after completed BOS taker-buy quote-flow filter; TRAIN only"
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
                    raise RuntimeError("R29 already exists; single attempt must not repeat")
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


def _grid_hash(config: dict[str, object]) -> str:
    payload = json.dumps([config], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _append(result, grid_sha, code_sha, fingerprint, denominator, config):
    import search_crypto_r19_match_attrition_audit as r19
    r19._assert_no_ledger_writer()
    row = {
        "trial_id": f"R29-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(config, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": _PREREG_SHA,
                              "master_prereg_sha256": _MASTER_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "single R29 TRAIN taker-flow filter; not OOS or G approval",
    }
    output = io.StringIO(newline="")
    csv.DictWriter(output, fieldnames=common.FIELDS).writerow(row)
    payload = output.getvalue().encode()
    fd = os.open(common.CSV_PATH, os.O_WRONLY | os.O_APPEND)
    attempted = False
    try:
        attempted = True
        written = os.write(fd, payload)
        if written != len(payload):
            raise AppendUncertainError("short append; inspect ledger tail, never retry")
        os.fsync(fd)
    except OSError as exc:
        raise AppendUncertainError("append durability uncertain; inspect ledger tail, never retry") from exc
    finally:
        try:
            os.close(fd)
        except OSError as exc:
            if attempted:
                raise AppendUncertainError("close failed after append; inspect ledger tail") from exc
            raise


def _split_cache_state(data_root: Path, data_access) -> tuple[str, int]:
    split_path = data_root / "cache/orderblock/crypto_splits_close_boundary.json"
    if not split_path.is_file():
        raise FileNotFoundError("fixed split manifest is missing")
    content = split_path.read_bytes()
    records = json.loads(content)
    symbols = r14._expected_symbols()
    expected_split = data_access.CRYPTO_COMMON_SPLIT_MS + max(data_access.TIMEFRAME_MS.values())
    expected_keys = {
        str((data_root / "cache/orderblock/bars" / timeframe / f"{symbol}.parquet").resolve())
        for timeframe in ("1h", "4h") for symbol in symbols
    }
    for key in expected_keys:
        record = records.get(key)
        if (not isinstance(record, dict) or record.get("fixed") is not True
                or int(record.get("split_timestamp", -1)) != expected_split):
            raise ValueError("fixed TRAIN split record missing or inconsistent")
    for timeframe in ("1h", "4h"):
        actual_symbols = {
            path.stem for path in (data_root / "cache/orderblock/bars" / timeframe).glob("*.parquet")
        }
        if actual_symbols != set(symbols):
            raise ValueError(f"{timeframe} input file set differs from frozen universe")
    return hashlib.sha256(content).hexdigest(), split_path.stat().st_mtime_ns


def _run_locked(data_root: Path):
    import data_access
    import search_crypto_r19_match_attrition_audit as r19

    r19._assert_no_ledger_writer()
    actual_rows = _ledger_state()
    config = {**CONFIG, "bonferroni_n": actual_rows + 1}
    grid_sha = _grid_hash(config)
    code_sha = _code_hash()
    if (actual_rows != EXPECTED_ROWS or config["bonferroni_n"] != EXPECTED_N
            or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
            or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
        reason = f"R29 prereg/hash/denominator mismatch before data access: rows={actual_rows}"
        _append({"status": "failed_before_data_access", "failure_stage": "preflight",
                 "failure_type": "PreregOrDenominatorMismatch", "detail": reason},
                grid_sha, code_sha, "UNAVAILABLE_BEFORE_TRAIN_INPUT", actual_rows + 1, config)
        raise RuntimeError(reason)
    fingerprint = "UNAVAILABLE_BEFORE_TRAIN_INPUT"
    written = False
    try:
        split_sha, split_mtime = _split_cache_state(data_root, data_access)
        with heavy_task("R29"):
            barsets_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
            barsets_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
            fingerprint = common._train_input_fingerprint(
                "R29-4h-1h-train",
                [(f"{symbol}:1h", bars, funding, excluded)
                 for symbol, bars, funding, excluded in barsets_1h]
                + [(f"{symbol}:4h", bars, {}, excluded)
                   for symbol, bars, _funding, excluded in barsets_4h],
            )
            usable = r27._usable_symbols(barsets_1h, barsets_4h)
            if len(usable) < r14.MINIMUM_SYMBOLS:
                result = {"status": "unscorable", "symbols": len(usable),
                          "detail": "fewer than 30 cutoff-safe symbols across both timeframes"}
            else:
                flow_by_bar_id, flow_sha, flow_stats = _build_flow_map(data_root, barsets_4h)
                result = _trial_with_flow(barsets_1h, barsets_4h, flow_by_bar_id)
                result.update(flow_stats)
                result["flow_feature_sha256"] = flow_sha
                result["detail"] = (
                    "R14 lifecycle after validated 1m taker-buy quote-flow filter; TRAIN only"
                )
            result["split_manifest_sha256"] = split_sha
            split_after, mtime_after = _split_cache_state(data_root, data_access)
            if (split_after, mtime_after) != (split_sha, split_mtime):
                raise RuntimeError("fixed split cache changed during R29; writes are forbidden")
            if (_code_hash() != code_sha
                    or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != _PREREG_SHA
                    or hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest() != _MASTER_SHA):
                raise RuntimeError("R29 source or preregistration changed during run")
            r19._assert_no_ledger_writer()
            _append(result, grid_sha, code_sha, fingerprint, EXPECTED_N, config)
            written = True
    except Exception as exc:
        if not written and not isinstance(exc, AppendUncertainError):
            _append({"status": "failed", "failure_stage": "r29_train",
                     "failure_type": type(exc).__name__,
                     "detail": "R29 preregistered TRAIN attempt failed; not G evidence"},
                    grid_sha, code_sha, fingerprint, EXPECTED_N, config)
        raise
    print(json.dumps({"R29": result, "grid_sha": grid_sha,
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
        _run_locked(data_root)
    finally:
        _release_run_locks(opened)


if __name__ == "__main__":
    run()
