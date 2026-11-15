"""Offline deterministic reducer for a captured Binance USD-M L2 JSONL segment.

This utility never connects to an exchange and never emits signals or orders. It
reconstructs sequence-valid local books, then writes compact quote/trade rows
with their receive ordering and provenance. Invalid book intervals fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from chart_predictor.l2_book import LocalBook, SequenceGap

MAX_OUTPUT_BYTES = 512 * 1024 * 1024


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _depth_metrics(book: LocalBook, mid: float, band_bps: float = 5.0) -> dict[str, float]:
    lower = mid * (1 - band_bps / 10_000)
    upper = mid * (1 + band_bps / 10_000)

    bid_levels = _depth_levels(book.bids, lower, mid, reverse=True)
    ask_levels = _depth_levels(book.asks, mid, upper, reverse=False)

    return {
        "bid_depth_quote_5bp_top5": sum(p * q for p, q in bid_levels),
        "ask_depth_quote_5bp_top5": sum(p * q for p, q in ask_levels),
        "bid_levels_5bp_top5": [[p, q] for p, q in bid_levels],
        "ask_levels_5bp_top5": [[p, q] for p, q in ask_levels],
    }


def _depth_levels(levels: dict[float, float], low: float, high: float,
                  *, reverse: bool) -> list[tuple[float, float]]:
    return sorted(((p, q) for p, q in levels.items() if low <= p <= high),
                  reverse=reverse)[:5]


def reduce_capture(source: Path, output: Path, *, max_output_bytes: int = MAX_OUTPUT_BYTES) -> dict[str, Any]:
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("input and output paths must differ")
    if max_output_bytes < 1:
        raise ValueError("output cap must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or partial.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite an existing compact output or manifest")
    source_sha256 = _digest(source)
    books: dict[str, LocalBook] = {}
    pending: dict[str, list[dict[str, Any]]] = {}
    waiting_snapshots: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    latest_book_rows: dict[str, dict[str, Any]] = {}
    last_book_receive_mono: dict[str, float] = {}
    rows = 0
    raw_records = 0
    synchronized = 0
    invalidations = 0
    feed_events = 0
    possible_trade_gaps = 0
    duplicate_trade_ids = 0
    out_of_order_trade_ids = 0
    last_trade_id: dict[str, int] = {}
    out_bytes = 0
    digest = hashlib.sha256()

    with source.open("rb") as src, partial.open("xb") as dst:
        for line_no, raw in enumerate(src, 1):
            if not raw.endswith(b"\n"):
                raise IOError(f"source has unterminated JSONL at line {line_no}")
            record = json.loads(raw)
            if not isinstance(record.get("receive_clock_domain"), str) or not record["receive_clock_domain"]:
                record["receive_clock_domain"] = source.parent.name
            raw_records += 1
            kind = record.get("kind")
            symbol = record.get("symbol")
            event = record.get("event")
            if kind == "connection":
                row = {
                    "kind": "feed_event",
                    "symbol": symbol,
                    "category": "connection",
                    "stream": record.get("stream"),
                    "state": record.get("state"),
                    "received_at_ms": record.get("received_at_ms"),
                    "received_monotonic_s": record.get("received_monotonic_s"),
                    "receive_clock_domain": record.get("receive_clock_domain"),
                    "error_type": record.get("error"),
                }
                out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                rows += 1
                feed_events += 1
                continue
            if not isinstance(symbol, str) or not symbol:
                continue
            book = books.setdefault(symbol, LocalBook())
            pending.setdefault(symbol, [])

            if kind == "book_state" and record.get("state") == "invalid":
                book.invalidate(str(record.get("reason") or "recorded_invalid"))
                pending[symbol].clear()
                waiting_snapshots.pop(symbol, None)
                last_book_receive_mono.pop(symbol, None)
                latest_book_rows.pop(symbol, None)
                invalidations += 1
                row = {
                    "kind": "feed_event", "symbol": symbol,
                    "category": "book_invalid", "reason": record.get("reason"),
                    "received_at_ms": record.get("received_at_ms"),
                    "received_monotonic_s": record.get("received_monotonic_s"),
                    "receive_clock_domain": record.get("receive_clock_domain"),
                }
                out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                rows += 1
                feed_events += 1
                continue
            if kind == "depth_delta" and isinstance(event, dict):
                if not book.valid:
                    pending[symbol].append(event)
                    if len(pending[symbol]) > 50_000:
                        raise ValueError(f"pending depth buffer overflow for {symbol}")
                    waiting = waiting_snapshots.get(symbol)
                    if waiting is not None:
                        snapshot, snapshot_record = waiting
                        try:
                            ok = book.install_snapshot(snapshot, pending[symbol])
                        except (SequenceGap, ValueError):
                            ok = False
                        if ok:
                            pending[symbol].clear()
                            waiting_snapshots.pop(symbol, None)
                            synchronized += 1
                            last = float(record["received_monotonic_s"])
                            last_book_receive_mono[symbol] = last
                            row = _book_row(symbol, event, record, book)
                            row["kind"] = "book_sync"
                            latest_book_rows[symbol] = row
                            out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                            rows += 1
                else:
                    try:
                        book.apply_diff(event)
                    except (SequenceGap, ValueError):
                        book.invalidate("replay_sequence_gap")
                        pending[symbol] = [event]
                        latest_book_rows.pop(symbol, None)
                        last_book_receive_mono.pop(symbol, None)
                        invalidations += 1
                        row = {
                            "kind": "feed_event", "symbol": symbol,
                            "category": "depth_sequence_gap",
                            "received_at_ms": record.get("received_at_ms"),
                            "received_monotonic_s": record.get("received_monotonic_s"),
                            "receive_clock_domain": record.get("receive_clock_domain"),
                        }
                        out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                        rows += 1
                        feed_events += 1
                        continue
                    last_book_receive_mono[symbol] = float(record["received_monotonic_s"])
                    row = _book_row(symbol, event, record, book)
                    latest_book_rows[symbol] = row
                    out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                    rows += 1
            elif kind == "depth_snapshot" and isinstance(event, dict):
                waiting_snapshots[symbol] = (event, record)
                try:
                    ok = book.install_snapshot(event, pending[symbol])
                except (SequenceGap, ValueError):
                    ok = False
                if ok:
                    pending[symbol].clear()
                    waiting_snapshots.pop(symbol, None)
                    synchronized += 1
                    last_book_receive_mono[symbol] = float(record["received_monotonic_s"])
                    row = _book_row(symbol, event, record, book, snapshot=True)
                    latest_book_rows[symbol] = row
                    out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                    rows += 1
            elif (kind == "aggTrade" and isinstance(event, dict) and book.valid
                  and symbol in latest_book_rows):
                received_mono = float(record["received_monotonic_s"])
                age_ms = max(0.0, (received_mono - last_book_receive_mono.get(symbol, received_mono)) * 1000)
                trade_id = event.get("a")
                previous_trade_id = last_trade_id.get(symbol)
                if (isinstance(trade_id, bool) or not isinstance(trade_id, int)
                        or trade_id <= 0):
                    row = {
                        "kind": "feed_event", "symbol": symbol,
                        "category": "invalid_agg_trade_id",
                        "exchange_event_ms": event.get("T", event.get("E")),
                        "received_at_ms": record.get("received_at_ms"),
                        "received_monotonic_s": record.get("received_monotonic_s"),
                        "receive_clock_domain": record.get("receive_clock_domain"),
                    }
                    out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                    rows += 1
                    feed_events += 1
                    continue
                if isinstance(previous_trade_id, int) and trade_id <= previous_trade_id:
                    duplicate = trade_id == previous_trade_id
                    if duplicate:
                        duplicate_trade_ids += 1
                    else:
                        out_of_order_trade_ids += 1
                    row = {
                        "kind": "feed_event", "symbol": symbol,
                        "category": "duplicate_agg_trade_id" if duplicate else "out_of_order_agg_trade_id",
                        "exchange_event_ms": event.get("T", event.get("E")),
                        "received_at_ms": record.get("received_at_ms"),
                        "received_monotonic_s": record.get("received_monotonic_s"),
                        "receive_clock_domain": record.get("receive_clock_domain"),
                        "trade_id": trade_id,
                    }
                    out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                    rows += 1
                    feed_events += 1
                    continue
                possible_gap = (isinstance(trade_id, int) and isinstance(previous_trade_id, int)
                                and trade_id > previous_trade_id + 1)
                if possible_gap:
                    possible_trade_gaps += 1
                row = _trade_row(symbol, event, record, latest_book_rows[symbol], age_ms,
                                 trade_id_gap_before=bool(possible_gap))
                if isinstance(trade_id, int):
                    last_trade_id[symbol] = trade_id
                out_bytes += _write_row(dst, digest, row, max_output_bytes - out_bytes)
                rows += 1

            if out_bytes > max_output_bytes:
                raise OSError(f"compact output cap exceeded ({max_output_bytes} bytes)")

        dst.flush()
        os.fsync(dst.fileno())

    if _digest(source) != source_sha256:
        raise IOError("source changed during deterministic replay")
    output_digest = digest.hexdigest()
    os.replace(partial, output)
    manifest = {
        "format": "cointrade-l2-compact-v1",
        "source_path": str(source),
        "source_sha256": source_sha256,
        "source_bytes": source.stat().st_size,
        "source_records": raw_records,
        "output_path": str(output),
        "output_sha256": output_digest,
        "output_bytes": output.stat().st_size,
        "output_rows": rows,
        "synchronized_snapshots": synchronized,
        "invalidations": invalidations,
        "feed_events_preserved": feed_events,
        "possible_trade_id_gaps": possible_trade_gaps,
        "duplicate_trade_ids_dropped": duplicate_trade_ids,
        "out_of_order_trade_ids_dropped": out_of_order_trade_ids,
        "strategy_metrics": None,
        "limitations": [
            "Rows preserve receive order; exchange event time is retained separately.",
            "Trade rows use the latest locally reconstructed book received before the trade row.",
            "This reducer does not infer event-time ordering, fills, or predictive performance.",
            "A zero-invalidations result on one pilot does not establish production feed reliability.",
        ],
    }
    with manifest_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return manifest


def _book_row(symbol: str, event: dict[str, Any], record: dict[str, Any], book: LocalBook,
              *, snapshot: bool = False) -> dict[str, Any]:
    bid = max(book.bids)
    ask = min(book.asks)
    mid = (bid + ask) / 2
    return {
        "kind": "book_snapshot" if snapshot else "book_update",
        "symbol": symbol,
        "exchange_event_ms": event.get("T", event.get("E")),
        "received_at_ms": record.get("received_at_ms"),
        "received_monotonic_s": record.get("received_monotonic_s"),
        "receive_clock_domain": record.get("receive_clock_domain"),
        "last_update_id": book.last_update_id,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        **_depth_metrics(book, mid),
    }


def _trade_row(symbol: str, event: dict[str, Any], record: dict[str, Any], book_row: dict[str, Any],
               book_age_ms: float, *, trade_id_gap_before: bool) -> dict[str, Any]:
    return {
        "kind": "agg_trade",
        "symbol": symbol,
        "trade_id": event.get("a"),
        "trade_id_gap_before": trade_id_gap_before,
        "first_trade_id": event.get("f"),
        "last_trade_id": event.get("l"),
        "exchange_event_ms": event.get("T", event.get("E")),
        "received_at_ms": record.get("received_at_ms"),
        "received_monotonic_s": record.get("received_monotonic_s"),
        "receive_clock_domain": record.get("receive_clock_domain"),
        "price": float(event["p"]),
        "base_quantity": float(event["q"]),
        "quote_quantity": float(event["p"]) * float(event["q"]),
        "seller_initiated": bool(event["m"]),
        "book_last_update_id": book_row["last_update_id"],
        "book_receive_age_ms": book_age_ms,
        "bid": book_row["bid"],
        "ask": book_row["ask"],
        "mid": book_row["mid"],
        "bid_depth_quote_5bp_top5": book_row["bid_depth_quote_5bp_top5"],
        "ask_depth_quote_5bp_top5": book_row["ask_depth_quote_5bp_top5"],
        "bid_levels_5bp_top5": book_row["bid_levels_5bp_top5"],
        "ask_levels_5bp_top5": book_row["ask_levels_5bp_top5"],
    }


def _write_row(dst: Any, digest: Any, row: dict[str, Any], remaining_bytes: int) -> int:
    data = (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    if len(data) > remaining_bytes:
        raise OSError("compact output cap exceeded before row write")
    dst.write(data)
    digest.update(data)
    return len(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="captured JSONL segment")
    parser.add_argument("--output", required=True, type=Path, help="new compact JSONL path")
    parser.add_argument("--max-output-bytes", type=int, default=MAX_OUTPUT_BYTES)
    args = parser.parse_args()
    print(json.dumps(reduce_capture(args.input, args.output,
                                    max_output_bytes=args.max_output_bytes), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
