"""Bounded, public-only Binance USD-M L2 data-integrity pilot (no signals/orders)."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets

from chart_predictor.l2_book import LocalBook, SequenceGap


SYMBOLS = ("BTCUSDT", "ETHUSDT")
BASE = Path(__file__).resolve().parents[2]
DATA_ROOT = BASE / "chart_predictor" / "data" / "crypto_l2_pilots"
MAX_BYTES = 512 * 1024 * 1024
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

    def __init__(self, path: Path, max_bytes: int = MAX_BYTES):
        self.path = Path(path)
        self.partial_path = self.path.with_suffix(self.path.suffix + ".partial")
        self.max_bytes = int(max_bytes)
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
        if self.bytes_written + len(line) > self.max_bytes:
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
        payload_path = self.partial_path
        if complete:
            os.replace(self.partial_path, self.path)
            payload_path = self.path
        digest = _sha256(payload_path)
        segment = {
            "path": payload_path.name,
            "complete": bool(complete),
            "sha256": digest,
            "record_count": self.record_count,
            "bytes": self.bytes_written,
            "first_receive_ms": self.first_receive_ms,
            "last_receive_ms": self.last_receive_ms,
        }
        manifest = {**run_manifest, "segment": segment}
        manifest_path = self.path.parent / ("manifest.json" if complete else "incomplete.json")
        _write_exclusive_json(manifest_path, manifest)
        if complete:
            verify_segment(payload_path, digest, self.record_count)
        return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")
    with Path(path).open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


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
    def __init__(self, output_dir: Path, *, capture_seconds: int = CAPTURE_SECONDS,
                 max_wall_seconds: int = MAX_WALL_SECONDS, max_bytes: int = MAX_BYTES):
        self.output_dir = Path(output_dir)
        self.capture_seconds = int(capture_seconds)
        self.max_wall_seconds = int(max_wall_seconds)
        self.started_wall = time.monotonic()
        self.capture_start: float | None = None
        self.stop = asyncio.Event()
        self.books = {symbol: LocalBook() for symbol in SYMBOLS}
        self.buffers: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in SYMBOLS}
        self.snapshots: dict[str, dict[str, Any] | None] = {symbol: None for symbol in SYMBOLS}
        self.snapshot_tasks: dict[str, asyncio.Task] = {}
        self.depth_online = False
        self.trades_online = False
        self.reconnects = {"depth": 0, "trades": 0}
        self.fault_since: dict[str, float | None] = {symbol: None for symbol in SYMBOLS}
        self.recovery_s: dict[str, list[float]] = defaultdict(list)
        self.event_latency_ms: dict[str, list[int]] = defaultdict(list)
        self.event_counts: dict[str, int] = defaultdict(int)
        self.first_last_trade_id: dict[str, dict[str, int | None]] = {
            symbol: {"first": None, "last": None} for symbol in SYMBOLS
        }
        self.total_s = {symbol: 0.0 for symbol in SYMBOLS}
        self.valid_s = {symbol: 0.0 for symbol in SYMBOLS}
        self.invalid_run_s = {symbol: 0.0 for symbol in SYMBOLS}
        self.longest_invalid_s = {symbol: [0.0] for symbol in SYMBOLS}
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        self.run_dir = self.output_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.segment = JsonlSegment(self.run_dir / "capture.jsonl", max_bytes=max_bytes)
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
            if latency is not None and symbol is not None:
                self.event_latency_ms[symbol].append(latency)
        self.segment.write(record)

    def _invalidate(self, symbol: str, reason: str) -> None:
        was_valid = self.books[symbol].valid
        self.books[symbol].invalidate(reason)
        if was_valid and self.fault_since[symbol] is None:
            self.fault_since[symbol] = time.monotonic()

    def _try_bridge(self, symbol: str) -> None:
        snapshot = self.snapshots[symbol]
        if snapshot is None or not self.buffers[symbol]:
            return
        try:
            if not self.books[symbol].install_snapshot(snapshot, self.buffers[symbol]):
                return
        except SequenceGap:
            self.books[symbol].invalidate("snapshot_buffer_sequence_gap")
            self.snapshots[symbol] = None
            self.buffers[symbol].clear()
            self._start_snapshot(symbol, force=True)
            return
        self.buffers[symbol].clear()
        self.snapshots[symbol] = None
        recovered = self.fault_since[symbol]
        if recovered is not None:
            self.recovery_s[symbol].append(max(0.0, time.monotonic() - recovered))
            self.fault_since[symbol] = None
        if all(book.valid for book in self.books.values()) and self.capture_start is None:
            self.capture_start = time.monotonic()
            self.capture_started_at = datetime.now(timezone.utc).isoformat()

    def _start_snapshot(self, symbol: str, *, force: bool = False) -> None:
        if symbol in self.snapshot_tasks and not self.snapshot_tasks[symbol].done():
            return
        if self.snapshots[symbol] is not None and not force:
            return
        self.snapshot_tasks[symbol] = asyncio.create_task(asyncio.to_thread(_fetch_snapshot, symbol))

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
                await asyncio.sleep(1.0)
                self._start_snapshot(symbol, force=True)
                continue
            self.snapshots[symbol] = snapshot
            self._write("depth_snapshot", symbol, snapshot, now_ms, mono)
            self._try_bridge(symbol)

    async def _depth_loop(self) -> None:
        delay = 1.0
        while not self.stop.is_set():
            try:
                async with websockets.connect(DEPTH_URL, ping_interval=20, ping_timeout=60,
                                              close_timeout=5, max_size=4 * 1024 * 1024) as ws:
                    self.depth_online = True
                    if self.reconnects["depth"]:
                        for symbol in SYMBOLS:
                            self._invalidate(symbol, "depth_reconnect")
                            self.snapshots[symbol] = None
                            self.buffers[symbol].clear()
                    self.reconnects["depth"] += 1
                    now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                    self._write("connection", None, None, now_ms, mono,
                                stream="depth", state="connected", attempt=self.reconnects["depth"])
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
                                self._start_snapshot(symbol, force=True)
                        else:
                            self.buffers[symbol].append(event)
                            if len(self.buffers[symbol]) > MAX_BUFFERED_DEPTH_EVENTS:
                                raise CaptureLimit("depth resync buffer exceeded hard event cap")
                            self._try_bridge(symbol)
            except CaptureLimit:
                raise
            except Exception as exc:
                self.depth_online = False
                for symbol in SYMBOLS:
                    self._invalidate(symbol, "depth_disconnect")
                    self.snapshots[symbol] = None
                    self.buffers[symbol].clear()
                now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                self._write("connection", None, None, now_ms, mono,
                            stream="depth", state="disconnected", error=type(exc).__name__)
                await asyncio.sleep(delay)
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
                    self.reconnects["trades"] += 1
                    now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                    self._write("connection", None, None, now_ms, mono,
                                stream="aggTrade", state="connected", attempt=self.reconnects["trades"])
                    delay = 1.0
                    async for message in ws:
                        received_ms, received_mono = time.time_ns() // 1_000_000, time.monotonic()
                        wrapper = json.loads(message)
                        event = wrapper.get("data", wrapper)
                        symbol = str(event.get("s", "")).upper()
                        if symbol not in self.first_last_trade_id or event.get("e") != "aggTrade":
                            continue
                        self.event_counts[f"aggTrade:{symbol}"] += 1
                        trade_id = event.get("a")
                        if isinstance(trade_id, int):
                            bounds = self.first_last_trade_id[symbol]
                            bounds["first"] = trade_id if bounds["first"] is None else min(bounds["first"], trade_id)
                            bounds["last"] = trade_id if bounds["last"] is None else max(bounds["last"], trade_id)
                        self._write("aggTrade", symbol, event, received_ms, received_mono,
                                    stream_name=wrapper.get("stream"))
            except CaptureLimit:
                raise
            except Exception as exc:
                self.trades_online = False
                now_ms, mono = time.time_ns() // 1_000_000, time.monotonic()
                self._write("connection", None, None, now_ms, mono,
                            stream="aggTrade", state="disconnected", error=type(exc).__name__)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
            finally:
                self.trades_online = False

    async def _monitor(self) -> None:
        previous = time.monotonic()
        wall_offset = (time.time_ns() / 1_000_000_000) - previous
        while not self.stop.is_set():
            await asyncio.sleep(0.25)
            now = time.monotonic()
            delta = max(0.0, now - previous)
            previous = now
            current_offset = (time.time_ns() / 1_000_000_000) - now
            self.last_wall_mono_offset_ms = abs(current_offset - wall_offset) * 1000
            if self.capture_start is not None:
                remaining = max(0.0, self.capture_seconds - (now - self.capture_start))
                observed = min(delta, remaining)
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
            for task in self.snapshot_tasks.values():
                task.cancel()
            await asyncio.gather(*self.snapshot_tasks.values(), return_exceptions=True)
            for symbol in SYMBOLS:
                self.longest_invalid_s[symbol].append(self.invalid_run_s[symbol])
            coverage = coverage_summary(self.total_s, self.valid_s,
                                        self.longest_invalid_s, self.recovery_s)
            latency = {}
            for symbol in SYMBOLS:
                values = sorted(self.event_latency_ms[symbol])
                latency[symbol] = {
                    "samples": len(values),
                    "p50_ms": values[len(values) // 2] if values else None,
                    "p95_ms": values[min(len(values) - 1, int(len(values) * .95))] if values else None,
                    "negative_clock_offset_samples": sum(x < 0 for x in values),
                }
            manifest = {
                "run_id": self.run_dir.name,
                "status": status,
                "reason": failure,
                "started_at": datetime.fromtimestamp(self.started_wall + (time.time() - time.monotonic()),
                                                       timezone.utc).isoformat(),
                "capture_started_at": self.capture_started_at,
                "capture_seconds_target": self.capture_seconds,
                "max_wall_seconds": self.max_wall_seconds,
                "hard_byte_cap": self.segment.max_bytes,
                "symbols": list(SYMBOLS),
                "streams": ["depth@500ms", "aggTrade"],
                "credentials_used": False,
                "signals_or_orders": False,
                "reconnects": self.reconnects,
                "events": dict(sorted(self.event_counts.items())),
                "trade_aggregate_id_bounds": self.first_last_trade_id,
                "event_to_receive_latency_ms": latency,
                "wall_clock_step_max_ms": self.last_wall_mono_offset_ms,
                "coverage": coverage,
                "acceptance": {
                    "coverage_ge_99pct_both": all(coverage[s]["coverage"] >= .99 for s in SYMBOLS),
                    "injected_faults": "see deterministic unit tests; this live run is not fault injection",
                    "recovery_le_30s": all(coverage[s]["max_recovery_seconds"] <= 30 for s in SYMBOLS),
                    "complete_60m": status == "completed",
                },
                "software": {"script": "scripts/research/crypto_l2_pilot.py", "python": __import__("sys").version},
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
    output_root = _validated_output_root(args.output_root)
    pilot = Pilot(output_root)
    try:
        result = asyncio.run(pilot.run())
    except CaptureLimit as exc:
        print(json.dumps({"status": "failed", "reason": str(exc), "run_dir": str(pilot.run_dir)}, indent=2))
        return 10
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 10


if __name__ == "__main__":
    raise SystemExit(main())
