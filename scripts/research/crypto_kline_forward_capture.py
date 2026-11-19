#!/usr/bin/env python3
"""Append-only capture of completed USDⓈ-M 1m klines for forward research.

This program records public market data only. It emits no prediction, alert, or
order. It selects the top eligible COIN-underlying USDT perpetuals once at
startup, then receives candle updates from the public WebSocket stream.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

import requests

from chart_predictor.universe import BASE_URL, select_universe

MAX_DURATION_SECONDS = 24 * 60 * 60
MAX_CAPTURE_BYTES = 128 * 1024 * 1024
DATA_DIR = Path(__file__).resolve().parents[2] / "chart_predictor" / "data" / "crypto_kline_forward"


def _integer(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _number(value, field):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def parse_closed_kline(envelope, expected_symbols):
    """Validate and normalize a closed 1m futures kline; return None if open."""
    if not isinstance(envelope, dict):
        raise ValueError("websocket message must be an object")
    event = envelope.get("data", envelope)
    if not isinstance(event, dict) or event.get("e") != "kline":
        return None
    kline = event.get("k")
    if not isinstance(kline, dict):
        raise ValueError("kline payload is missing")
    symbol = event.get("s", kline.get("s"))
    if symbol not in expected_symbols:
        raise ValueError("unexpected symbol")
    if kline.get("i") != "1m":
        raise ValueError("unexpected kline interval")
    if kline.get("x") is not True:
        if kline.get("x") is False:
            return None
        raise ValueError("closed flag must be boolean")

    open_ms = _integer(kline.get("t"), "open time")
    close_ms = _integer(kline.get("T"), "close time")
    if open_ms % 60_000 != 0:
        raise ValueError("open time is off the UTC minute grid")
    if close_ms != open_ms + 59_999:
        raise ValueError("close time does not match a one-minute candle")
    prices = {name: _number(kline.get(key), name) for name, key in
              (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))}
    if min(prices.values()) <= 0 or prices["high"] < max(prices["open"], prices["close"], prices["low"]):
        raise ValueError("invalid OHLC prices")
    if prices["low"] > min(prices["open"], prices["close"], prices["high"]):
        raise ValueError("invalid OHLC prices")

    volume = _number(kline.get("v"), "base volume")
    quote_volume = _number(kline.get("q"), "quote volume")
    taker_base = _number(kline.get("V"), "taker-buy base volume")
    taker_quote = _number(kline.get("Q"), "taker-buy quote volume")
    trade_count = _integer(kline.get("n"), "trade count")
    if min(volume, quote_volume, taker_base, taker_quote) < 0:
        raise ValueError("volume fields must be non-negative")
    if taker_base > volume + 1e-10 or taker_quote > quote_volume + max(1e-10, quote_volume * 1e-10):
        raise ValueError("taker-buy volume exceeds total volume")
    empty_volume = volume == 0 or quote_volume == 0
    if empty_volume and (volume != 0 or quote_volume != 0 or taker_base != 0
                         or taker_quote != 0 or trade_count != 0):
        raise ValueError("inconsistent empty-volume candle")
    return {
        "kind": "closed_kline", "symbol": symbol, "interval": "1m",
        "open_ms": open_ms, "close_ms": close_ms,
        **{key: str(kline[field]) for key, field in (("open", "o"), ("high", "h"),
          ("low", "l"), ("close", "c"), ("base_volume", "v"),
          ("quote_volume", "q"), ("taker_buy_base", "V"),
          ("taker_buy_quote", "Q"))},
        "trade_count": trade_count,
        "source_event_ms": _integer(event.get("E"), "event time"),
        "is_closed": True,
        "feature_eligible": not empty_volume,
        "feature_exclusion_reason": "zero_volume" if empty_volume else None,
    }


def fetch_top_universe(top_n=20, session=requests):
    """Use two one-off public REST reads to freeze the P1-eligible cohort."""
    info_response = session.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=20)
    info_response.raise_for_status()
    ticker_response = session.get(f"{BASE_URL}/fapi/v1/ticker/24hr", timeout=20)
    ticker_response.raise_for_status()
    selected = select_universe(info_response.json(), ticker_response.json(), top_n)
    if len(selected) != top_n or len({row["symbol"] for row in selected}) != top_n:
        raise RuntimeError(f"expected {top_n} distinct eligible symbols, got {len(selected)}")
    return selected


class JsonlCapture:
    def __init__(self, output_dir, symbols, universe_rows, max_bytes=MAX_CAPTURE_BYTES):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"{stamp}-{uuid.uuid4().hex[:10]}"
        self.partial = self.output_dir / f"{self.run_id}.jsonl.partial"
        self.final = self.output_dir / f"{self.run_id}.jsonl"
        self.manifest = self.output_dir / f"{self.run_id}.manifest.json"
        self.handle = self.partial.open("xb")
        self.max_bytes = max_bytes
        self.digest = hashlib.sha256()
        self.bytes_written = 0
        self.symbols = tuple(symbols)
        self.last_open_ms = {}
        self.rows_by_symbol = {symbol: 0 for symbol in symbols}
        self.duplicates = 0
        self.out_of_order = 0
        self.missing_minutes = {symbol: 0 for symbol in symbols}
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.closed = False
        self._write({"kind": "capture_start", "run_id": self.run_id,
                     "started_at": self.started_at, "source": "Binance USD-M public kline WebSocket",
                     "symbols": list(symbols), "universe_snapshot": universe_rows,
                     "interval": "1m", "records_are_closed_only": True})

    def _write(self, row):
        payload = (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if self.bytes_written + len(payload) > self.max_bytes:
            raise OSError("capture file size limit reached")
        self.handle.write(payload)
        self.digest.update(payload)
        self.bytes_written += len(payload)

    def append_kline(self, row, received_at_ms):
        symbol, open_ms = row["symbol"], row["open_ms"]
        previous = self.last_open_ms.get(symbol)
        if previous is not None:
            if open_ms == previous:
                self.duplicates += 1
                return False
            if open_ms < previous:
                self.out_of_order += 1
                self._write({"kind": "integrity_event", "category": "out_of_order",
                             "symbol": symbol, "previous_open_ms": previous,
                             "observed_open_ms": open_ms})
                return False
            if open_ms > previous + 60_000:
                missing = (open_ms - previous) // 60_000 - 1
                self.missing_minutes[symbol] += missing
                self._write({"kind": "integrity_event", "category": "minute_gap",
                             "symbol": symbol, "previous_open_ms": previous,
                             "observed_open_ms": open_ms, "missing_minutes": missing})
        row = dict(row)
        row["received_at_ms"] = received_at_ms
        self._write(row)
        self.last_open_ms[symbol] = open_ms
        self.rows_by_symbol[symbol] += 1
        if sum(self.rows_by_symbol.values()) % 100 == 0:
            self.handle.flush()
        return True

    def connection_event(self, state, error_type=None):
        self._write({"kind": "connection_event", "state": state,
                     "received_at_ms": int(time.time() * 1000), "error_type": error_type})
        self.handle.flush()

    def finalize(self, complete, reconnects, started_monotonic):
        if self.closed:
            return
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.handle.close()
        self.closed = True
        digest = self.digest.hexdigest()
        if complete:
            os.replace(self.partial, self.final)
            data_path = self.final
        else:
            data_path = self.partial
        report = {
            "run_id": self.run_id, "complete": bool(complete),
            "started_at": self.started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
            "data_path": data_path.name, "sha256": digest,
            "bytes": self.bytes_written, "symbol_count": len(self.symbols),
            "symbols": list(self.symbols), "rows_by_symbol": self.rows_by_symbol,
            "duplicates_skipped": self.duplicates, "out_of_order_skipped": self.out_of_order,
            "missing_minutes_observed": self.missing_minutes, "reconnects": reconnects,
            "strategy_metrics": None,
            "limitations": ["WebSocket delivery completeness is not guaranteed by row counts alone.",
                            "Gaps are recorded and must not be bridged in later model input.",
                            "No predictions, alerts, labels, or orders are produced by this collector."],
        }
        with self.manifest.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


async def capture(top_n, duration_seconds, output_dir, session=requests):
    if isinstance(duration_seconds, bool) or not 1 <= duration_seconds <= MAX_DURATION_SECONDS:
        raise ValueError(f"duration_seconds must be in [1, {MAX_DURATION_SECONDS}]")
    universe_rows = fetch_top_universe(top_n, session)
    symbols = tuple(row["symbol"] for row in universe_rows)
    streams = "/".join(f"{symbol.lower()}@kline_1m" for symbol in symbols)
    url = f"wss://fstream.binance.com/market/stream?streams={streams}"
    writer = JsonlCapture(output_dir, symbols, universe_rows)
    deadline = time.monotonic() + duration_seconds
    started = time.monotonic()
    reconnects, delay = 0, 1.0
    complete = False
    try:
        import websockets
        while time.monotonic() < deadline:
            writer.connection_event("connecting")
            try:
                async with websockets.connect(url, ping_interval=None, close_timeout=10,
                                              max_queue=2048) as ws:
                    writer.connection_event("connected")
                    delay = 1.0
                    while time.monotonic() < deadline:
                        remaining = deadline - time.monotonic()
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                        except asyncio.TimeoutError:
                            complete = True
                            break
                        try:
                            message = json.loads(raw)
                            row = parse_closed_kline(message, set(symbols))
                        except (json.JSONDecodeError, ValueError, TypeError) as exc:
                            writer.connection_event("invalid_message", type(exc).__name__)
                            continue
                        if row is not None:
                            writer.append_kline(row, int(time.time() * 1000))
                            count = sum(writer.rows_by_symbol.values())
                            if count and count % 500 == 0:
                                print(f"closed_bars={count} reconnects={reconnects}", flush=True)
                    if complete:
                        break
            except Exception as exc:
                reconnects += 1
                writer.connection_event("disconnected", type(exc).__name__)
                await asyncio.sleep(min(delay, max(0.0, deadline - time.monotonic())))
                delay = min(delay * 2, 60.0)
        else:
            complete = True
    finally:
        writer.finalize(complete, reconnects, started)
    return {"run_id": writer.run_id, "complete": complete,
            "rows_by_symbol": writer.rows_by_symbol, "reconnects": reconnects,
            "manifest_path": str(writer.manifest)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--duration-seconds", type=int, default=3600)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    if not 20 <= args.top_n <= 100:
        parser.error("--top-n must be between 20 and 100 COIN-underlying perpetual symbols")
    result = asyncio.run(capture(args.top_n, args.duration_seconds, args.output_dir))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
