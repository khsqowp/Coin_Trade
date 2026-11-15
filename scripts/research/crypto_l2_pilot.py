"""Bounded, public-only Binance USD-M L2 data-integrity pilot (no signals/orders)."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import resource
import shutil
import sys
import time
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYMBOLS = ("BTCUSDT", "ETHUSDT")
BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import websockets  # noqa: E402
from chart_predictor.l2_book import LocalBook, SequenceGap  # noqa: E402


DATA_ROOT = BASE / "chart_predictor" / "data" / "crypto_l2_pilots"
MAX_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_RESERVE_BYTES = 1024 * 1024
CAPTURE_SECONDS = 60 * 60
MAX_WALL_SECONDS = 75 * 60
MAX_BUFFERED_DEPTH_EVENTS = 50_000
DEPTH_URL = "wss://fstream.binance.com/public/stream?streams=" + "/".join(
    f"{symbol.lower()}@depth@500ms" for symbol in SYMBOLS
)
TRADES_URL = "wss://fstream.binance.com/market/stream?streams=" + "/".join(
    f"{symbol.lower()}@aggTrade" for symbol in SYMBOLS
)


class CaptureLimit(RuntimeError):
    """Raised before writing beyond the hard output cap."""


class JsonlSegment:
    """Exclusive-create JSONL spool; incomplete runs remain explicitly partial."""

    def __init__(self, path: Path, max_bytes: int = MAX_BYTES,
                 manifest_reserve_bytes: int = 0):
        self.path = Path(path)
        self.partial_path = self.path.with_suffix(self.path.suffix + ".partial")
        self.max_bytes = int(max_bytes)
        self.manifest_reserve_bytes = int(manifest_reserve_bytes)
        if self.max_bytes <= self.manifest_reserve_bytes:
            raise ValueError("total output cap must exceed the manifest reserve")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.partial_path.open("xb")
        self.bytes_written = 0
        self.record_count = 0
        self.first_receive_ms: int | None = None
        self.last_receive_ms: int | None = None
        self.closed = False

    def write(self, record: dict[str, Any]) -> None:
        if self.closed:
            raise RuntimeError("capture segment is closed")
        line = (json.dumps(record, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        if self.bytes_written + len(line) > self.max_bytes - self.manifest_reserve_bytes:
            raise CaptureLimit(f"hard output cap reached ({self.max_bytes} bytes)")
        self._handle.write(line)
        self.bytes_written += len(line)
        self.record_count += 1
        stamp = record.get("received_at_ms")
        if isinstance(stamp, int):
            self.first_receive_ms = stamp if self.first_receive_ms is None else min(self.first_receive_ms, stamp)
            self.last_receive_ms = stamp if self.last_receive_ms is None else max(self.last_receive_ms, stamp)

    def close(self, *, complete: bool, run_manifest: dict[str, Any]) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("capture segment already closed")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self.closed = True
        digest = _sha256(self.partial_path)
        segment = {
            "path": self.path.name if complete else self.partial_path.name,
            "complete": bool(complete),
            "sha256": digest,
            "record_count": self.record_count,
            "bytes": self.bytes_written,
            "first_receive_ms": self.first_receive_ms,
            "last_receive_ms": self.last_receive_ms,
        }
        manifest = {**run_manifest, "segment": segment}
        manifest_path = self.path.parent / ("manifest.json" if complete else "incomplete.json")
        metrics = manifest.setdefault("resource_metrics", {})
        metrics["metadata_bytes"] = 0
        metrics["total_output_bytes"] = self.bytes_written
        for _ in range(8):
            data = _json_bytes(manifest, pretty=True)
            total = self.bytes_written + len(data)
            elapsed = float(metrics.get("capture_elapsed_seconds") or 0.0)
            previous = (metrics["metadata_bytes"], metrics["total_output_bytes"])
            metrics["metadata_bytes"] = len(data)
            metrics["total_output_bytes"] = total
            metrics["metadata_bytes_per_hour"] = round(len(data) * 3600 / elapsed, 3) if elapsed > 0 else None
            metrics["total_output_bytes_per_hour"] = round(total * 3600 / elapsed, 3) if elapsed > 0 else None
            if previous == (len(data), total):
                break
        data = _json_bytes(manifest, pretty=True)
        if self.bytes_written + len(data) > self.max_bytes:
            raise CaptureLimit("capture plus manifest would exceed the total output cap")
        if self.bytes_written + len(data) != metrics["total_output_bytes"]:
            raise RuntimeError("manifest size did not stabilize")
        if complete:
            os.replace(self.partial_path, self.path)
        with manifest_path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if complete:
            verify_segment(self.path, digest, self.record_count)
        return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: dict[str, Any], *, pretty: bool = False) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2 if pretty else None,
                       separators=None if pretty else (",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def verify_segment(path: Path, digest: str, expected_records: int) -> None:
    if _sha256(path) != digest:
        raise IOError("capture segment hash mismatch")
    count = 0
    with Path(path).open("rb") as handle:
        for line in handle:
            if not line.endswith(b"\n"):
                raise IOError("capture has an incomplete JSONL record")
            json.loads(line)
            count += 1
    if count != expected_records:
        raise IOError(f"capture record count mismatch: {count} != {expected_records}")


def stream_event_latency_ms(event: dict[str, Any], received_at_ms: int) -> int | None:
    event_ms = event.get("E")
    if isinstance(event_ms, bool) or not isinstance(event_ms, int):
        return None
    return int(received_at_ms - event_ms)


def interval_overlap(start: float, end: float, window_start: float,
                     window_end: float) -> float:
    return max(0.0, min(end, window_end) - max(start, window_start))


def recovery_acceptance(recovery_s: dict[str, list[float]]) -> dict[str, Any]:
    observed = all(recovery_s.get(symbol) for symbol in SYMBOLS)
    return {
        "observed_both_symbols": observed,
        "within_30_seconds": (
            all(max(recovery_s[symbol]) <= 30 for symbol in SYMBOLS) if observed else None
        ),
        "no_recovery_observed_is_not_a_pass": True,
    }


def coverage_summary(total_s: dict[str, float], valid_s: dict[str, float],
                     invalid_runs_s: dict[str, list[float]],
                     recovery_s: dict[str, list[float]]) -> dict[str, dict[str, Any]]:
    result = {}
    for symbol in SYMBOLS:
        denominator = float(total_s.get(symbol, 0.0))
        valid = float(valid_s.get(symbol, 0.0))
        result[symbol] = {
            "valid_seconds": round(valid, 3),
            "invalid_seconds": round(max(0.0, denominator - valid), 3),
            "coverage": valid / denominator if denominator else 0.0,
            "longest_invalid_seconds": round(max(invalid_runs_s.get(symbol, [0.0])), 3),
            "recovery_seconds": [round(float(x), 3) for x in recovery_s.get(symbol, [])],
            "max_recovery_seconds": round(max(recovery_s.get(symbol) or [0.0]), 3),
        }
    return result


def _fetch_snapshot(symbol: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"symbol": symbol, "limit": 1000})
    request = urllib.request.Request(
        f"https://fapi.binance.com/fapi/v1/depth?{query}",
        headers={"User-Agent": "CoinTrade-L2-research-pilot/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict) or "lastUpdateId" not in payload:
        raise ValueError(f"invalid depth snapshot response for {symbol}")
    return payload


class Pilot:
    def __init__(self, output_dir: Path, *, capture_seconds: float = CAPTURE_SECONDS,
                 max_wall_seconds: float = MAX_WALL_SECONDS, max_bytes: int = MAX_BYTES):
        self.output_dir = Path(output_dir)
        self.capture_seconds = float(capture_seconds)
        self.max_wall_seconds = float(max_wall_seconds)
        if self.capture_seconds <= 0 or self.max_wall_seconds <= 0:
            raise ValueError("capture and wall-clock limits must be positive")
        self.started_wall = time.monotonic()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.cpu_started = resource.getrusage(resource.RUSAGE_SELF)
        free_path = self.output_dir if self.output_dir.exists() else self.output_dir.parent
        while not free_path.exists() and free_path != free_path.parent:
            free_path = free_path.parent
        self.free_space_before = shutil.disk_usage(free_path).free
        self.capture_start: float | None = None
        self.stop = asyncio.Event()
        self.books = {symbol: LocalBook() for symbol in SYMBOLS}
        initialized_ms = time.time_ns() // 1_000_000
        initialized_mono = time.monotonic()
        self.book_validity_intervals: dict[str, list[dict[str, Any]]] = {
            symbol: [{
                "state": "invalid",
                "start_received_at_ms": initialized_ms,
                "start_monotonic_s": round(initialized_mono, 6),
                "end_received_at_ms": None,
                "end_monotonic_s": None,
                "duration_seconds": None,
                "reason": "startup_unsynchronized",
            }]
            for symbol in SYMBOLS
        }
        self.buffers: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in SYMBOLS}
        self.snapshots: dict[str, dict[str, Any] | None] = {symbol: None for symbol in SYMBOLS}
        self.snapshot_tasks: dict[str, asyncio.Task] = {}
        self.snapshot_retry_tasks: dict[str, asyncio.Task] = {}
        self.snapshot_retry_delay_s = {symbol: 1.0 for symbol in SYMBOLS}
        self.retired_snapshot_tasks: list[asyncio.Task] = []
        self.depth_online = False
        self.trades_online = False
        self.connection_attempts = {"depth": 0, "trades": 0}
        self.reconnects = {"depth": 0, "trades": 0}
        self.capture_connection_baseline = {"depth": 0, "trades": 0}
        self.capture_reconnect_baseline = {"depth": 0, "trades": 0}
        self.fault_since: dict[str, float | None] = {symbol: None for symbol in SYMBOLS}
        self.recovery_s: dict[str, list[float]] = defaultdict(list)
        self.event_latency_ms: dict[str, list[int]] = defaultdict(list)
        self.event_counts: dict[str, int] = defaultdict(int)
        self.first_last_trade_id: dict[str, dict[str, int | None]] = {
            symbol: {"first": None, "last": None, "possible_id_jumps": 0,
                     "possible_missing_ids": 0} for symbol in SYMBOLS
        }
        self.total_s = {symbol: 0.0 for symbol in SYMBOLS}
        self.valid_s = {symbol: 0.0 for symbol in SYMBOLS}
        self.trade_valid_s = {symbol: 0.0 for symbol in SYMBOLS}
        self.invalid_run_s = {symbol: 0.0 for symbol in SYMBOLS}
        self.longest_invalid_s = {symbol: [0.0] for symbol in SYMBOLS}
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        self.run_dir = self.output_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.segment = JsonlSegment(
            self.run_dir / "capture.jsonl",
            max_bytes=max_bytes,
            manifest_reserve_bytes=MAX_MANIFEST_RESERVE_BYTES,
        )
        self.capture_started_at: str | None = None
        self.last_wall_mono_offset_ms: float | None = None
        self._last_clock_sample: tuple[float, float] | None = None

    def _write(self, kind: str, symbol: str | None, event: dict[str, Any] | None,
               received_ms: int, received_mono: float, **extra: Any) -> None:
        record = {"kind": kind, "symbol": symbol, "received_at_ms": received_ms,
                  "received_monotonic_s": round(received_mono, 6), **extra}
        if event is not None:
            record["event"] = event
            latency = stream_event_latency_ms(event, received_ms)
            if (latency is not None and symbol is not None
                    and self._inside_capture(received_mono)):
                self.event_latency_ms[symbol].append(latency)
        self.segment.write(record)

    def _inside_capture(self, received_mono: float) -> bool:
        return (self.capture_start is not None
                and self.capture_start <= received_mono < self.capture_start + self.capture_seconds)

    def _invalidate(self, symbol: str, reason: str) -> None:
        was_valid = self.books[symbol].valid
        self.books[symbol].invalidate(reason)
        if was_valid and self.fault_since[symbol] is None:
            self.fault_since[symbol] = time.monotonic()
        if was_valid:
            now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
            self._close_book_interval(symbol, now_ms, mono, reason)
            self._open_book_interval(symbol, "invalid", now_ms, mono, reason)
            self._write("book_state", symbol, None, now_ms, mono,
                        state="invalid", reason=reason)

    def _close_book_interval(self, symbol: str, end_ms: int, end_mono: float,
                             reason: str | None = None) -> None:
        intervals = self.book_validity_intervals[symbol]
        if not intervals or intervals[-1]["end_monotonic_s"] is not None:
            return
        interval = intervals[-1]
        interval["end_received_at_ms"] = end_ms
        interval["end_monotonic_s"] = round(end_mono, 6)
        interval["duration_seconds"] = round(max(0.0, end_mono - interval["start_monotonic_s"]), 6)
        if reason is not None and interval["state"] == "valid":
            interval["end_reason"] = reason

    def _open_book_interval(self, symbol: str, state: str, start_ms: int,
                            start_mono: float, reason: str | None = None) -> None:
        self.book_validity_intervals[symbol].append({
            "state": state,
            "start_received_at_ms": start_ms,
            "start_monotonic_s": round(start_mono, 6),
            "end_received_at_ms": None,
            "end_monotonic_s": None,
            "duration_seconds": None,
            "reason": reason,
        })

    def _depth_connected(self) -> int:
        self.depth_online = True
        if self.connection_attempts["depth"]:
            self.reconnects["depth"] += 1
            for symbol in SYMBOLS:
                self._invalidate(symbol, "depth_reconnect")
                self.snapshots[symbol] = None
                self.buffers[symbol].clear()
        self.connection_attempts["depth"] += 1
        return self.connection_attempts["depth"]

    def _depth_disconnected(self) -> None:
        self.depth_online = False
        for task in (*self.snapshot_tasks.values(), *self.snapshot_retry_tasks.values()):
            task.cancel()
            self.retired_snapshot_tasks.append(task)
        self.snapshot_tasks.clear()
        self.snapshot_retry_tasks.clear()
        for symbol in SYMBOLS:
            self._invalidate(symbol, "depth_disconnect")
            self.snapshots[symbol] = None
            self.buffers[symbol].clear()

    def _try_bridge(self, symbol: str) -> None:
        snapshot = self.snapshots[symbol]
        if snapshot is None or not self.buffers[symbol]:
            return
        try:
            if not self.books[symbol].install_snapshot(snapshot, self.buffers[symbol]):
                snapshot_id = snapshot.get("lastUpdateId")
                newer_buffer = (
                    isinstance(snapshot_id, int)
                    and any(isinstance(event.get("U"), int) and event["U"] > snapshot_id
                            for event in self.buffers[symbol])
                )
                if newer_buffer:
                    self.snapshots[symbol] = None
                    self._schedule_snapshot_retry(symbol)
                return
        except SequenceGap:
            self.books[symbol].invalidate("snapshot_buffer_sequence_gap")
            self.snapshots[symbol] = None
            self.buffers[symbol].clear()
            self._schedule_snapshot_retry(symbol)
            return
        self.buffers[symbol].clear()
        self.snapshots[symbol] = None
        now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
        self._close_book_interval(symbol, now_ms, mono)
        self._open_book_interval(symbol, "valid", now_ms, mono, "snapshot_bridged")
        self._write("book_state", symbol, None, now_ms, mono,
                    state="valid", last_update_id=self.books[symbol].last_update_id)
        recovered = self.fault_since[symbol]
        if recovered is not None:
            self.recovery_s[symbol].append(max(0.0, time.monotonic() - recovered))
            self.fault_since[symbol] = None
        self.snapshot_retry_delay_s[symbol] = 1.0
        if all(book.valid for book in self.books.values()) and self.capture_start is None:
            self.capture_start = time.monotonic()
            self.capture_started_at = datetime.now(timezone.utc).isoformat()
            self.event_counts.clear()
            self.recovery_s.clear()
            self.capture_connection_baseline = dict(self.connection_attempts)
            self.capture_reconnect_baseline = dict(self.reconnects)
            for bounds in self.first_last_trade_id.values():
                bounds.update(first=None, last=None, possible_id_jumps=0, possible_missing_ids=0)

    def _start_snapshot(self, symbol: str, *, force: bool = False) -> None:
        if symbol in self.snapshot_tasks and not self.snapshot_tasks[symbol].done():
            return
        if self.snapshots[symbol] is not None and not force:
            return
        self.snapshot_tasks[symbol] = asyncio.create_task(asyncio.to_thread(_fetch_snapshot, symbol))

    def _schedule_snapshot_retry(self, symbol: str) -> None:
        task = self.snapshot_retry_tasks.get(symbol)
        if task is None or task.done():
            delay = self.snapshot_retry_delay_s[symbol]
            self.snapshot_retry_delay_s[symbol] = min(delay * 2, 8.0)
            self.snapshot_retry_tasks[symbol] = asyncio.create_task(
                self._retry_snapshot(symbol, delay)
            )

    async def _retry_snapshot(self, symbol: str, delay: float) -> None:
        current = asyncio.current_task()
        try:
            await self._retry_delay(delay)
            if not self.stop.is_set() and self.depth_online:
                self._start_snapshot(symbol, force=True)
        finally:
            if self.snapshot_retry_tasks.get(symbol) is current:
                del self.snapshot_retry_tasks[symbol]

    async def _collect_snapshots(self) -> None:
        now_ms = time.time_ns() // 1_000_000
        mono = time.monotonic()
        for symbol, task in list(self.snapshot_tasks.items()):
            if not task.done():
                continue
            del self.snapshot_tasks[symbol]
            try:
                snapshot = task.result()
            except Exception as exc:
                self._write("snapshot_error", symbol, None, now_ms, mono,
                            error=type(exc).__name__)
                self._schedule_snapshot_retry(symbol)
                continue
            self.snapshots[symbol] = snapshot
            self._write("depth_snapshot", symbol, snapshot, now_ms, mono)
            self._try_bridge(symbol)

    async def _retry_delay(self, delay: float) -> None:
        try:
            await asyncio.wait_for(self.stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass

    async def _depth_loop(self) -> None:
        delay = 1.0
        while not self.stop.is_set():
            try:
                async with websockets.connect(DEPTH_URL, ping_interval=20, ping_timeout=60,
                                              close_timeout=5, max_size=4 * 1024 * 1024) as ws:
                    attempt = self._depth_connected()
                    now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                    self._write("connection", None, None, now_ms, mono,
                                stream="depth", state="connected", attempt=attempt)
                    for symbol in SYMBOLS:
                        self._start_snapshot(symbol, force=True)
                    delay = 1.0
                    async for message in ws:
                        await self._collect_snapshots()
                        received_ms, received_mono = time.time_ns() // 1_000_000, time.monotonic()
                        wrapper = json.loads(message)
                        event = wrapper.get("data", wrapper)
                        symbol = str(event.get("s", "")).upper()
                        if symbol not in self.books or event.get("e") != "depthUpdate":
                            self._write("invalid_depth_message", symbol or None,
                                        wrapper if isinstance(wrapper, dict) else None,
                                        received_ms, received_mono)
                            continue
                        if self._inside_capture(received_mono):
                            self.event_counts[f"depth:{symbol}"] += 1
                        self._write("depth_delta", symbol, event, received_ms, received_mono,
                                    stream_name=wrapper.get("stream"))
                        book = self.books[symbol]
                        if book.valid:
                            try:
                                book.apply_diff(event)
                            except SequenceGap:
                                self._invalidate(symbol, "sequence_gap")
                                self._write("book_invalid", symbol, None, received_ms,
                                            received_mono, reason="sequence_gap")
                                self.buffers[symbol] = [event]
                                self.snapshots[symbol] = None
                                self._schedule_snapshot_retry(symbol)
                        else:
                            self.buffers[symbol].append(event)
                            if len(self.buffers[symbol]) > MAX_BUFFERED_DEPTH_EVENTS:
                                raise CaptureLimit("depth resync buffer exceeded hard event cap")
                            self._try_bridge(symbol)
            except CaptureLimit:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._depth_disconnected()
                now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                self._write("connection", None, None, now_ms, mono,
                            stream="depth", state="disconnected", error=type(exc).__name__)
                await self._retry_delay(delay)
                delay = min(delay * 2, 30.0)
            finally:
                self.depth_online = False

    async def _trades_loop(self) -> None:
        delay = 1.0
        while not self.stop.is_set():
            try:
                async with websockets.connect(TRADES_URL, ping_interval=20, ping_timeout=60,
                                              close_timeout=5, max_size=4 * 1024 * 1024) as ws:
                    self.trades_online = True
                    if self.connection_attempts["trades"]:
                        self.reconnects["trades"] += 1
                    self.connection_attempts["trades"] += 1
                    now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                    self._write("connection", None, None, now_ms, mono,
                                stream="aggTrade", state="connected",
                                attempt=self.connection_attempts["trades"])
                    delay = 1.0
                    async for message in ws:
                        received_ms, received_mono = time.time_ns() // 1_000_000, time.monotonic()
                        wrapper = json.loads(message)
                        event = wrapper.get("data", wrapper)
                        symbol = str(event.get("s", "")).upper()
                        if symbol not in self.first_last_trade_id or event.get("e") != "aggTrade":
                            continue
                        if self._inside_capture(received_mono):
                            self.event_counts[f"aggTrade:{symbol}"] += 1
                        trade_id = event.get("a")
                        if (isinstance(trade_id, int) and not isinstance(trade_id, bool)
                                and self._inside_capture(received_mono)):
                            bounds = self.first_last_trade_id[symbol]
                            previous_id = bounds["last"]
                            if isinstance(previous_id, int) and trade_id > previous_id + 1:
                                bounds["possible_id_jumps"] += 1
                                bounds["possible_missing_ids"] += trade_id - previous_id - 1
                            bounds["first"] = trade_id if bounds["first"] is None else min(bounds["first"], trade_id)
                            bounds["last"] = trade_id if bounds["last"] is None else max(bounds["last"], trade_id)
                        self._write("aggTrade", symbol, event, received_ms, received_mono,
                                    stream_name=wrapper.get("stream"))
            except CaptureLimit:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.trades_online = False
                now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                self._write("connection", None, None, now_ms, mono,
                            stream="aggTrade", state="disconnected", error=type(exc).__name__)
                await self._retry_delay(delay)
                delay = min(delay * 2, 30.0)
            finally:
                self.trades_online = False

    async def _monitor(self) -> None:
        previous = time.monotonic()
        wall_offset = (time.time_ns() / 1_000_000_000) - previous
        while not self.stop.is_set():
            await asyncio.sleep(0.25)
            now = time.monotonic()
            interval_start = previous
            previous = now
            current_offset = (time.time_ns() / 1_000_000_000) - now
            self.last_wall_mono_offset_ms = abs(current_offset - wall_offset) * 1000
            if self.capture_start is not None:
                capture_end = self.capture_start + self.capture_seconds
                observed = interval_overlap(interval_start, now, self.capture_start, capture_end)
                for symbol in SYMBOLS:
                    self.total_s[symbol] += observed
                    valid = self.depth_online and self.books[symbol].valid
                    if valid:
                        self.valid_s[symbol] += observed
                        if self.invalid_run_s[symbol] > 0:
                            self.longest_invalid_s[symbol].append(self.invalid_run_s[symbol])
                            self.invalid_run_s[symbol] = 0.0
                    else:
                        self.invalid_run_s[symbol] += observed
                    if self.trades_online:
                        self.trade_valid_s[symbol] += observed
                if now - self.capture_start >= self.capture_seconds:
                    self.stop.set()
            if now - self.started_wall >= self.max_wall_seconds:
                self.stop.set()

    async def run(self) -> dict[str, Any]:
        status = "incomplete"
        failure: str | None = None
        tasks = [asyncio.create_task(self._depth_loop()),
                 asyncio.create_task(self._trades_loop()),
                 asyncio.create_task(self._monitor())]
        stop_task = asyncio.create_task(self.stop.wait())
        try:
            done, _ = await asyncio.wait([*tasks, stop_task], return_when=asyncio.FIRST_COMPLETED)
            failed = next((task for task in done if task is not stop_task), None)
            if failed is not None:
                exception = failed.exception()
                if exception is not None:
                    raise exception
                if not self.stop.is_set():
                    raise RuntimeError("collector task exited before the pilot stop condition")
            if self.capture_start is not None and time.monotonic() - self.capture_start >= self.capture_seconds:
                status = "completed"
            else:
                failure = "maximum wall time reached before full synchronized capture"
        except CaptureLimit as exc:
            failure = str(exc)
        except asyncio.CancelledError:
            failure = "run cancelled before clean completion"
        except Exception as exc:
            failure = f"unexpected {type(exc).__name__}"
        finally:
            self.stop.set()
            stop_task.cancel()
            for task in tasks:
                task.cancel()
            await asyncio.gather(stop_task, *tasks, return_exceptions=True)
            snapshot_tasks = [*self.snapshot_tasks.values(), *self.snapshot_retry_tasks.values(),
                              *self.retired_snapshot_tasks]
            for task in snapshot_tasks:
                task.cancel()
            await asyncio.gather(*snapshot_tasks, return_exceptions=True)
            for symbol in SYMBOLS:
                self.longest_invalid_s[symbol].append(self.invalid_run_s[symbol])
                self._close_book_interval(
                    symbol, time.time_ns() // 1_000_000, time.monotonic(), "capture_ended"
                )
            coverage = coverage_summary(self.total_s, self.valid_s,
                                        self.longest_invalid_s, self.recovery_s)
            latency = {}
            for symbol in SYMBOLS:
                values = sorted(self.event_latency_ms[symbol])
                latency[symbol] = {
                    "samples": len(values),
                    "p50_ms": values[len(values) // 2] if values else None,
                    "p95_ms": values[max(0, math.ceil(len(values) * .95) - 1)] if values else None,
                    "negative_event_to_receive_latency_samples": sum(x < 0 for x in values),
                }
            self.segment._handle.flush()
            os.fsync(self.segment._handle.fileno())
            cpu_finished = resource.getrusage(resource.RUSAGE_SELF)
            capture_elapsed = (time.monotonic() - self.capture_start
                               if self.capture_start is not None
                               else time.monotonic() - self.started_wall)
            peak_rss = cpu_finished.ru_maxrss
            if sys.platform != "darwin":
                peak_rss *= 1024
            manifest = {
                "run_id": self.run_dir.name,
                "status": status,
                "reason": failure,
                "started_at": self.started_at,
                "capture_started_at": self.capture_started_at,
                "capture_seconds_target": self.capture_seconds,
                "max_wall_seconds": self.max_wall_seconds,
                "hard_byte_cap": self.segment.max_bytes,
                "symbols": list(SYMBOLS),
                "streams": ["depth@500ms", "aggTrade"],
                "credentials_used": False,
                "signals_or_orders": False,
                "connection_attempts_during_capture": {
                    key: (self.connection_attempts[key] - self.capture_connection_baseline[key]
                          if self.capture_start is not None else None)
                    for key in self.connection_attempts
                },
                "reconnects_during_capture": {
                    key: (self.reconnects[key] - self.capture_reconnect_baseline[key]
                          if self.capture_start is not None else None)
                    for key in self.reconnects
                },
                "events": dict(sorted(self.event_counts.items())),
                "trade_aggregate_id_bounds": self.first_last_trade_id,
                "aggregate_trade_gap_note": (
                    "ID jumps are possible missing-event indicators only; they do not prove "
                    "exchange-side completeness and may span reconnect gaps."
                ),
                "event_to_receive_latency_ms": latency,
                "wall_clock_step_max_ms": self.last_wall_mono_offset_ms,
                "coverage": coverage,
                "aggtrade_connection_coverage": {
                    symbol: {
                        "connected_seconds": round(self.trade_valid_s[symbol], 3),
                        "capture_seconds": round(self.total_s[symbol], 3),
                        "coverage": (self.trade_valid_s[symbol] / self.total_s[symbol]
                                     if self.total_s[symbol] else 0.0),
                        "meaning": "socket-connected time only; not proof of event completeness",
                    }
                    for symbol in SYMBOLS
                },
                "book_validity_intervals": self.book_validity_intervals,
                "resource_metrics": {
                    "capture_elapsed_seconds": round(capture_elapsed, 3),
                    "capture_bytes": self.segment.bytes_written,
                    "capture_bytes_per_hour": round(
                        self.segment.bytes_written * 3600 / capture_elapsed, 3
                    ) if capture_elapsed > 0 else None,
                    "process_user_cpu_seconds": round(cpu_finished.ru_utime - self.cpu_started.ru_utime, 3),
                    "process_system_cpu_seconds": round(cpu_finished.ru_stime - self.cpu_started.ru_stime, 3),
                    "process_peak_rss_bytes": peak_rss,
                    "output_directory_free_bytes_before": self.free_space_before,
                    "output_directory_free_bytes_before_manifest": shutil.disk_usage(self.run_dir).free,
                },
                "acceptance": {
                    "coverage_ge_99pct_both": all(coverage[s]["coverage"] >= .99 for s in SYMBOLS),
                    "injected_faults": "not measured by live run; local deterministic tests required",
                    "recovery": recovery_acceptance(self.recovery_s),
                    "complete_60m": status == "completed",
                },
                "configuration": {
                    "symbols": list(SYMBOLS),
                    "depth_stream": "depth@500ms",
                    "trade_stream": "aggTrade",
                    "capture_seconds": self.capture_seconds,
                    "max_wall_seconds": self.max_wall_seconds,
                    "hard_total_bytes": self.segment.max_bytes,
                    "max_buffered_depth_events": MAX_BUFFERED_DEPTH_EVENTS,
                },
                "software": {
                    "script": "scripts/research/crypto_l2_pilot.py",
                    "script_sha256": _sha256(Path(__file__)),
                    "python": sys.version,
                },
            }
            closed = self.segment.close(complete=(status == "completed"), run_manifest=manifest)
            manifest = closed
        return manifest


def _validated_output_root(path: Path) -> Path:
    root = Path(path).resolve()
    data = (BASE / "chart_predictor" / "data").resolve()
    try:
        relative = root.relative_to(data)
    except ValueError as exc:
        raise ValueError("pilot output must stay inside chart_predictor/data") from exc
    if relative.parts[:1] != ("crypto_l2_pilots",):
        raise ValueError("pilot output must use chart_predictor/data/crypto_l2_pilots")
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="connect to public Binance streams for the bounded pilot")
    parser.add_argument("--output-root", type=Path, default=DATA_ROOT)
    args = parser.parse_args()
    if not args.run:
        parser.error("network access requires explicit --run")
    pilot: Pilot | None = None
    try:
        output_root = _validated_output_root(args.output_root)
        pilot = Pilot(output_root)
        result = asyncio.run(pilot.run())
    except CaptureLimit as exc:
        print(json.dumps({
            "status": "failed", "reason": str(exc),
            "run_dir": str(pilot.run_dir) if pilot is not None else None,
        }, indent=2))
        return 10
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": type(exc).__name__}, indent=2))
        return 10
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 10


if __name__ == "__main__":
    raise SystemExit(main())
