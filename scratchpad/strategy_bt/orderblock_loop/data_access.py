"""Read cutoff-safe, chronologically split market bars.

Parquet is read in row groups with an open-time predicate so post-freeze rows
are not returned to the caller unless ``final_freeze=True`` is explicit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, Literal

import pandas as pd
import pyarrow.dataset as ds

from crypto import Bar, FundingEvent

UTC_CUTOFF = pd.Timestamp("2026-05-31 23:59:00", tz="UTC")
UTC_CUTOFF_MS = int(UTC_CUTOFF.timestamp() * 1000)
Window = Literal["train", "test"]
TIMEFRAME_MS = {"15m": 15 * 60_000, "1h": 60 * 60_000, "4h": 240 * 60_000}
# Market-wide common 60/40 boundary (PREREG v1.1).
CRYPTO_COMMON_SPLIT_MS = 1699272000000
EQUITY_COMMON_SPLIT_MS = int(pd.Timestamp("2018-10-26 23:59:00", tz="UTC").timestamp() * 1000)


def split_timestamp(frame: pd.DataFrame) -> int:
    """Return the last open-time in the first 60% of a sorted series."""
    if frame.empty:
        raise ValueError("cannot split an empty bar series")
    if "open_time" not in frame:
        raise ValueError("bars require open_time column")
    times = frame["open_time"]
    if times.isna().any() or not times.is_monotonic_increasing:
        raise ValueError("open_time must be non-null and chronological")
    if times.duplicated().any():
        raise ValueError("open_time must be unique")
    train_count = int(len(frame) * 0.60)
    if train_count < 1 or train_count >= len(frame):
        raise ValueError("series must contain at least two rows for 60/40 split")
    return int(times.iloc[train_count - 1])


def load_bars(path: str | Path, *, window: Window, split_file: str | Path,
              start_ms: int | None = None, end_ms: int | None = None,
              final_freeze: bool = False, symbol: str | None = None,
              fixed_split_ms: int | None = None,
              bar_duration_ms: int | None = None,
              split_at_bar_close: bool = False) -> pd.DataFrame:
    """Load a train-only or test-only range from one symbol/timeframe file.

    The split timestamp is persisted per file identity. All times are UTC epoch
    milliseconds and represent bar open times. End bounds are inclusive.
    """
    if window not in ("train", "test"):
        raise ValueError("window must be 'train' or 'test'")
    if bar_duration_ms is not None and bar_duration_ms <= 0:
        raise ValueError("bar_duration_ms must be positive")
    if split_at_bar_close and (fixed_split_ms is None or bar_duration_ms is None):
        raise ValueError("close-aligned split requires fixed boundary and bar duration")
    if end_ms is not None and end_ms > UTC_CUTOFF_MS and not final_freeze:
        raise ValueError("post-2026-05-31 data requires final_freeze=True")
    source = Path(path)
    split_path = Path(split_file)
    # Predicate pushdown ensures later row groups are not materialized in normal mode.
    filters = []
    effective_end = end_ms
    frozen_open_cutoff = UTC_CUTOFF_MS - (bar_duration_ms or 0)
    if not final_freeze:
        effective_end = min(effective_end, frozen_open_cutoff) if effective_end is not None else frozen_open_cutoff
    if start_ms is not None:
        filters.append(("open_time", ">=", start_ms))
    if split_at_bar_close and window == "test":
        filters.append(("open_time", ">=", fixed_split_ms))
    if effective_end is not None:
        filters.append(("open_time", "<=", effective_end))
    if split_at_bar_close and window == "train":
        effective_train_end = fixed_split_ms - bar_duration_ms
        filters.append(("open_time", "<=", effective_train_end))
    if symbol is None:
        frame = pd.read_parquet(source, filters=filters or None)
        key = str(source.resolve())
    else:
        import pyarrow.parquet as pq

        schema = pq.read_schema(source)
        symbol_column = next((name for name in ("ticker", "code", "symbol")
                              if name in schema.names), None)
        if symbol_column is None:
            raise ValueError("symbol-filtered panel needs ticker, code, or symbol column")
        date_column = "open_time" if "open_time" in schema.names else "date"
        if date_column not in schema.names:
            raise ValueError("symbol-filtered panel needs open_time or date column")
        panel_filters = [(symbol_column, "=", symbol)]
        if date_column == "open_time":
            panel_filters.extend(filters)
        else:
            date_type = schema.field(date_column).type

            def as_panel_timestamp(value: int) -> pd.Timestamp:
                stamp = pd.to_datetime(value, unit="ms", utc=True)
                return stamp if getattr(date_type, "tz", None) is not None else stamp.tz_localize(None)

            date_filters = [("date", ">=", as_panel_timestamp(start_ms))] if start_ms is not None else []
            date_end = effective_end
            if date_end is not None:
                date_filters.append(("date", "<=", as_panel_timestamp(date_end)))
            panel_filters.extend(date_filters)
        columns = [symbol_column, date_column, "open", "high", "low", "close"]
        if "volume" in schema.names:
            columns.append("volume")
        if "complete" in schema.names:
            columns.append("complete")
        frame = pd.read_parquet(source, columns=columns, filters=panel_filters)
        if date_column == "date":
            dates = pd.to_datetime(frame.pop("date"), utc=True)
            frame["open_time"] = (dates.astype("int64") // 1_000_000).astype("int64")
        frame = frame.drop(columns=[symbol_column])
        key = f"{source.resolve()}::{symbol}"
    frame = frame.sort_values("open_time", kind="stable").reset_index(drop=True)
    split_data = {}
    if split_path.exists():
        split_data = json.loads(split_path.read_text(encoding="utf-8"))
    record = split_data.get(key)
    if fixed_split_ms is not None:
        fixed_record = {"split_timestamp": int(fixed_split_ms), "fixed": True}
        if record is not None and int(record.get("split_timestamp", -1)) != int(fixed_split_ms):
            raise ValueError(f"cached split conflicts with preregistered fixed split: {key}")
        if record is None or record.get("fixed") is not True:
            split_data[key] = fixed_record
            split_path.parent.mkdir(parents=True, exist_ok=True)
            split_path.write_text(json.dumps(split_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        record = fixed_record
    if record is None:
        # Compute a stable full-series split without returning post-cutoff rows.
        # Even a final-freeze request cannot move the original 60/40 boundary.
        if start_ms is not None or (end_ms is not None and end_ms < frozen_open_cutoff):
            raise ValueError("first split computation requires full frozen-series range")
        if symbol is None:
            frozen = pd.read_parquet(
                source,
                filters=[("open_time", "<=", frozen_open_cutoff)],
            )
        else:
            frozen = frame.copy()
        frozen = frozen.sort_values("open_time", kind="stable").reset_index(drop=True)
        record = {"split_timestamp": split_timestamp(frozen), "rows": len(frozen)}
        split_data[key] = record
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_path.write_text(json.dumps(split_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    split_ms = int(record["split_timestamp"])
    if split_at_bar_close:
        if window == "train":
            frame = frame[frame["open_time"] + bar_duration_ms <= split_ms]
        else:
            frame = frame[frame["open_time"] >= split_ms]
    elif window == "train":
        frame = frame[frame["open_time"] <= split_ms]
    else:
        frame = frame[frame["open_time"] > split_ms]
    if start_ms is not None:
        frame = frame[frame["open_time"] >= start_ms]
    if end_ms is not None:
        frame = frame[frame["open_time"] <= end_ms]
    return frame.reset_index(drop=True)


def _month_key(timestamp_ms: int) -> str:
    return pd.to_datetime(timestamp_ms, unit="ms", utc=True).strftime("%Y-%m")


def _settlement_bar_ms(timestamp_ms: int) -> int:
    """Map exchange settlement millisecond jitter to its containing minute bar."""
    return timestamp_ms - timestamp_ms % 60_000


def _funding_cadence_gaps(rows: list[tuple[int, float, int]],
                          through_ms: int) -> list[int]:
    """Return interior and trailing missing settlements through the required cutoff."""
    gaps = []
    for (previous_ts, _, previous_hours), (timestamp, _, hours) in zip(rows, rows[1:]):
        if previous_hours <= 0 or hours <= 0:
            raise ValueError(f"invalid funding interval at {timestamp}")
        expected_deltas = (previous_hours * 3_600_000, hours * 3_600_000)
        if not any(abs(timestamp - previous_ts - delta) <= 1_000
                   for delta in expected_deltas):
            gaps.append(previous_ts + previous_hours * 3_600_000)
    final_ts, _, final_hours = rows[-1]
    if final_hours <= 0:
        raise ValueError(f"invalid funding interval at {final_ts}")
    expected = final_ts + final_hours * 3_600_000
    while expected <= through_ms:
        gaps.append(expected)
        expected += final_hours * 3_600_000
    return gaps


def _funding_events(base: Path, symbol: str, through_ms: int) -> dict[int, FundingEvent]:
    """Read pre-cutoff funding rows and preceding-minute mark/close prices."""
    funding_root = base / "external/crypto/binance/um_fundingRate" / symbol
    mark_root = base / "external/crypto/binance/um_markPriceKlines_1m" / symbol
    bar_root = base / "external/crypto/binance/um_klines_1m" / symbol
    rows: list[tuple[int, float, int]] = []
    through_month = pd.Timestamp(through_ms, unit="ms", tz="UTC").strftime("%Y-%m")
    for path in sorted(funding_root.glob("????-??.parquet")):
        # Do not even open a post-cutoff monthly file during a train run.
        # A row predicate is not an access boundary: the file itself may
        # contain frozen OOS data even when filtered rows are empty.
        if path.stem > through_month:
            continue
        through_with_jitter = min(through_ms + 1_000, UTC_CUTOFF_MS)
        frame = pd.read_parquet(path, columns=["calc_time", "last_funding_rate",
                                               "funding_interval_hours"],
                                filters=[("calc_time", "<=", through_with_jitter)])
        rows.extend((int(row.calc_time), float(row.last_funding_rate),
                     int(row.funding_interval_hours))
                    for row in frame.itertuples(index=False))
    if not rows:
        raise ValueError(f"no funding rows available for {symbol} through train cutoff")
    rows.sort()
    if len({timestamp for timestamp, _, _ in rows}) != len(rows):
        raise ValueError(f"duplicate funding timestamp for {symbol}")
    gaps = _funding_cadence_gaps(rows, through_ms)
    settlements = [(timestamp, _settlement_bar_ms(timestamp), rate)
                   for timestamp, rate, _ in rows]
    wanted = {minute - 60_000 for _, minute, _ in settlements}
    marks: dict[int, float] = {}
    fallback_prices: dict[int, float] = {}
    by_month: dict[str, set[int]] = {}
    for timestamp in wanted:
        by_month.setdefault(_month_key(timestamp), set()).add(timestamp)
    for month, timestamps in by_month.items():
        path = mark_root / f"{month}.parquet"
        if path.exists():
            table = ds.dataset(path, format="parquet").to_table(
                columns=["open_time", "close"],
                filter=ds.field("open_time").isin(sorted(timestamps))
                & (ds.field("open_time") < UTC_CUTOFF_MS),
            )
            marks.update((int(ts), float(price))
                         for ts, price in zip(table["open_time"].to_pylist(),
                                              table["close"].to_pylist()))
        missing = timestamps.difference(marks)
        if missing:
            bar_path = bar_root / f"{month}.parquet"
            if bar_path.exists():
                candles = ds.dataset(bar_path, format="parquet").to_table(
                    columns=["open_time", "close"],
                    filter=ds.field("open_time").isin(sorted(missing))
                    & (ds.field("open_time") < UTC_CUTOFF_MS),
                )
                fallback_prices.update(
                    (int(ts), float(price))
                    for ts, price in zip(candles["open_time"].to_pylist(),
                                         candles["close"].to_pylist())
                )
    events: dict[int, FundingEvent] = {}
    for timestamp, minute, rate in settlements:
        mark_timestamp = minute - 60_000
        mark = marks.get(mark_timestamp)
        used_fallback = mark is None or pd.isna(mark) or mark <= 0
        if used_fallback:
            mark = fallback_prices.get(mark_timestamp)
        valid_mark = float(mark) if mark is not None and pd.notna(mark) and mark > 0 else None
        events[timestamp] = FundingEvent(timestamp, rate, valid_mark,
                                         used_candle_close_fallback=used_fallback and valid_mark is not None)
    for timestamp in gaps:
        events[timestamp] = FundingEvent(timestamp, 0.0, None, coverage_gap=True)
    return events


# Market-wide common 60/40 anchor (PREREG v1.1): first-60% boundary at the BTCUSDT 4h
# bar open 2023-11-06 12:00 UTC. Every timeframe's train candles close by 16:00 UTC.


def iter_train_bars(timeframe: str, *, shard_index: int = 0, shard_count: int = 1,
                    data_dir: str | Path | None = None,
                    split_file: str | Path | None = None,
                    common_split_ms: int | None = CRYPTO_COMMON_SPLIT_MS) -> Iterator[tuple[str, list[Bar], dict[int, FundingEvent]]]:
    """Yield one symbol at a time, with post-cutoff rows inaccessible to caller.

    Files are assigned deterministically to shards. Inputs are only read; split
    metadata is written under the designated cache directory.
    """
    if timeframe not in TIMEFRAME_MS:
        raise ValueError(f"unsupported timeframe: {timeframe!r}")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard must satisfy 0 <= index < count")
    base = Path(data_dir or os.environ.get("TRADING_DATA_DIR", Path.home() / "CODE/Coin_Trade/trading_data")).expanduser()
    split_path = Path(split_file).expanduser() if split_file else base / "cache/orderblock/crypto_splits_close_boundary.json"
    source_dir = base / "cache/orderblock/bars" / timeframe
    paths = sorted(source_dir.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(f"no preregistered bars found at {source_dir}")
    for path in paths[shard_index::shard_count]:
        symbol = path.stem
        split_boundary_ms = (common_split_ms + max(TIMEFRAME_MS.values())
                             if common_split_ms is not None else None)
        frame = load_bars(path, window="train", split_file=split_path,
                          fixed_split_ms=split_boundary_ms,
                          bar_duration_ms=TIMEFRAME_MS[timeframe],
                          split_at_bar_close=common_split_ms is not None)
        if frame.empty:
            yield symbol, [], {}
            continue
        bars = [Bar(int(row.open_time), float(row.open), float(row.high),
                    float(row.low), float(row.close), float(row.volume),
                    bool(row.complete))
                for row in frame.itertuples(index=False)]
        through_ms = min(bars[-1].timestamp + TIMEFRAME_MS[timeframe],
                         split_boundary_ms if split_boundary_ms is not None else UTC_CUTOFF_MS)
        funding = _funding_events(base, symbol, through_ms)
        yield symbol, bars, funding
