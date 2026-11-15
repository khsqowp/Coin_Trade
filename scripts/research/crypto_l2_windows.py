"""Bounded offline aggregation of compact L2 rows into UTC 10-second windows.

The input must be the output of crypto_l2_compact.py. Exchange event times
define the windows; receive order defines what was observable. Late data is
counted and flagged, not silently repaired. This tool does not score signals.
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

WINDOW_MS = 10_000
REFILL_MS = 2_000
MAX_DEPTH_ENDPOINT_AGE_MS = 750
MAX_OPEN_WINDOWS_PER_SYMBOL = 256
MAX_EMPTY_WINDOWS_PER_ADVANCE = 3600
MAX_OUTPUT_BYTES = 512 * 1024 * 1024


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _new_window() -> dict[str, Any]:
    return {
        "buy_quote": 0.0, "sell_quote": 0.0, "trade_count": 0,
        "buy_count": 0, "sell_count": 0, "trade_high": None, "trade_low": None,
        "trade_high_event_ms": None, "trade_low_event_ms": None,
        "first_trade_id": None, "last_trade_id": None, "trade_gap_count": 0,
        "trade_seconds": {}, "depth_samples": [],
        "feed_event_count": 0, "feed_event_categories": set(),
        "late_event_count": 0, "first_receive_mono": None, "last_receive_mono": None,
    }


def _touch_receive(window: dict[str, Any], mono: float) -> None:
    first = window["first_receive_mono"]
    last = window["last_receive_mono"]
    window["first_receive_mono"] = mono if first is None else min(first, mono)
    window["last_receive_mono"] = mono if last is None else max(last, mono)


def _depth_sample(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_ms": int(row["exchange_event_ms"]),
        "receive_mono": float(row["received_monotonic_s"]),
        "bid": float(row["bid_depth_quote_5bp_top5"]),
        "ask": float(row["ask_depth_quote_5bp_top5"]),
        "best_bid": float(row["bid"]),
        "best_ask": float(row["ask"]),
        "bid_levels": row.get("bid_levels_5bp_top5", []),
        "ask_levels": row.get("ask_levels_5bp_top5", []),
        "last_update_id": row.get("last_update_id"),
        "kind": row["kind"],
    }


def _first_trade_quote(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_ms": int(row["exchange_event_ms"]),
        "receive_mono": float(row["received_monotonic_s"]),
        "trade_id": row.get("trade_id"),
        "price": float(row["price"]),
        "best_bid": float(row["bid"]),
        "best_ask": float(row["ask"]),
        "book_receive_age_ms": float(row.get("book_receive_age_ms", 0.0)),
        "bid_levels": row.get("bid_levels_5bp_top5", []),
        "ask_levels": row.get("ask_levels_5bp_top5", []),
    }


def _window_row(symbol: str, start: int, item: dict[str, Any], future_samples: list[dict[str, Any]],
                previous_depth: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    end = start + WINDOW_MS
    samples = sorted(item["depth_samples"], key=lambda p: (p["event_ms"], p["receive_mono"]))
    dmin_bid = min(samples, key=lambda p: (p["bid"], p["event_ms"])) if samples else None
    dmin_ask = min(samples, key=lambda p: (p["ask"], p["event_ms"])) if samples else None
    refill_candidates = [p for p in future_samples if end <= p["event_ms"] <= end + REFILL_MS]
    d2s = max(refill_candidates, key=lambda p: (p["event_ms"], p["receive_mono"])) if refill_candidates else None
    dpre = previous_depth
    last_in_window = samples[-1] if samples else previous_depth
    availability_times = [item["first_receive_mono"], item["last_receive_mono"]]
    availability_times.extend(p["receive_mono"] for p in samples)
    if dpre is not None:
        availability_times.append(dpre["receive_mono"])
    if d2s is not None:
        availability_times.append(d2s["receive_mono"])
    availability_times = [value for value in availability_times if value is not None]
    feature_available = max(availability_times) if availability_times else None
    reasons = []
    if dpre is None:
        reasons.append("missing_pre_depth")
    if not samples:
        reasons.append("missing_depth_during_window")
    if d2s is None:
        reasons.append("missing_depth_at_plus_2s")
    if dpre is not None and start - dpre["event_ms"] > MAX_DEPTH_ENDPOINT_AGE_MS:
        reasons.append("stale_pre_depth")
    if d2s is not None and end + REFILL_MS - d2s["event_ms"] > MAX_DEPTH_ENDPOINT_AGE_MS:
        reasons.append("stale_depth_at_plus_2s")
    if item["late_event_count"]:
        reasons.append("late_event_within_window")
    if item["feed_event_count"]:
        reasons.append("feed_event_within_window")
    if item["trade_gap_count"]:
        reasons.append("possible_aggregate_trade_id_gap")

    def ratio(pre: dict[str, Any] | None, low: dict[str, Any] | None,
              after: dict[str, Any] | None, side: str) -> float | None:
        if pre is None or low is None or after is None:
            return None
        denominator = pre[side] - low[side]
        if denominator <= 0:
            return None
        return (after[side] - low[side]) / denominator

    values = {
        "symbol": symbol,
        "window_start_ms": start,
        "window_end_ms": end,
        "trade_count": item["trade_count"],
        "buy_aggressor_count": item["buy_count"],
        "sell_aggressor_count": item["sell_count"],
        "buy_aggressor_quote_volume": item["buy_quote"],
        "sell_aggressor_quote_volume": item["sell_quote"],
        "trade_high": item["trade_high"],
        "trade_high_event_ms": item["trade_high_event_ms"],
        "trade_low": item["trade_low"],
        "trade_low_event_ms": item["trade_low_event_ms"],
        "trade_path": [item["trade_seconds"][key] for key in sorted(item["trade_seconds"])],
        "first_trade_id": item["first_trade_id"],
        "last_trade_id": item["last_trade_id"],
        "possible_trade_id_gaps": item["trade_gap_count"],
        "dpre": dpre,
        "dmin_bid": dmin_bid,
        "dmin_ask": dmin_ask,
        "d_plus_2s": d2s,
        "quote_path": samples,
        "bid_replenishment_ratio": ratio(dpre, dmin_bid, d2s, "bid"),
        "ask_replenishment_ratio": ratio(dpre, dmin_ask, d2s, "ask"),
        "feed_event_count": item["feed_event_count"],
        "feed_event_categories": sorted(item["feed_event_categories"]),
        "late_event_count": item["late_event_count"],
        "first_receive_monotonic_s": item["first_receive_mono"],
        "last_receive_monotonic_s": item["last_receive_mono"],
        "feature_available_receive_monotonic_s": feature_available,
        "data_quality_ready": not reasons,
        "unscorable_reasons": reasons,
    }
    return values, last_in_window


def is_available_by_decision(window: dict[str, Any], decision_receive_monotonic_s: float) -> bool:
    """Return false unless all observations arrived strictly before the decision anchor."""
    available = window.get("feature_available_receive_monotonic_s")
    return (isinstance(available, (int, float)) and not isinstance(available, bool)
            and available < decision_receive_monotonic_s)


def aggregate_windows(source: Path, output: Path, *, allowed_lateness_ms: int = 2000,
                      max_output_bytes: int = MAX_OUTPUT_BYTES) -> dict[str, Any]:
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError("input and output paths must differ")
    if allowed_lateness_ms < 0 or max_output_bytes < 1:
        raise ValueError("lateness must be non-negative and output cap positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".partial")
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or partial.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite an existing window output or manifest")
    input_hash = _sha256(source)
    states: dict[str, dict[str, Any]] = {}
    rows_written = 0
    input_rows = 0
    late_rows = 0
    global_feed_events = 0
    global_disconnect_events = 0
    incomplete_windows = 0
    output_bytes = 0
    output_hash = hashlib.sha256()

    def state_for(symbol: str) -> dict[str, Any]:
        return states.setdefault(symbol, {
            "windows": {}, "next_start": None, "max_event_ms": None,
            "previous_depth": None, "finalized_count": 0,
        })

    def emit(dst: Any, symbol: str, state: dict[str, Any], start: int,
             *, final: bool = True) -> None:
        nonlocal rows_written, output_bytes
        item = state["windows"].pop(start, None) or _new_window()
        future_samples = []
        for future_start in (start + WINDOW_MS, start + 2 * WINDOW_MS):
            future = state["windows"].get(future_start)
            if future:
                future_samples.extend(p for p in future["depth_samples"]
                                      if start + WINDOW_MS <= p["event_ms"] <= start + WINDOW_MS + REFILL_MS)
        values, next_previous = _window_row(symbol, start, item, future_samples,
                                             state["previous_depth"])
        values["window_final"] = final
        data = (json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if output_bytes + len(data) > max_output_bytes:
            raise OSError(f"10-second window output cap exceeded ({max_output_bytes} bytes)")
        dst.write(data)
        output_hash.update(data)
        output_bytes += len(data)
        rows_written += 1
        state["previous_depth"] = next_previous
        state["finalized_count"] += 1

    with source.open("rb") as src, partial.open("xb") as dst:
        for line_no, raw in enumerate(src, 1):
            if not raw.endswith(b"\n"):
                raise IOError(f"compact input has unterminated JSONL at line {line_no}")
            row = json.loads(raw)
            input_rows += 1
            symbol = row.get("symbol")
            if row.get("kind") == "feed_event" and not isinstance(symbol, str):
                global_feed_events += 1
                if row.get("state") == "disconnected":
                    global_disconnect_events += 1
                continue
            if not isinstance(symbol, str) or not symbol:
                continue
            kind = row.get("kind")
            stamp = row.get("exchange_event_ms")
            if kind == "feed_event":
                stamp = row.get("received_at_ms")
            if isinstance(stamp, bool) or not isinstance(stamp, int):
                continue
            state = state_for(symbol)
            start = stamp // WINDOW_MS * WINDOW_MS
            if state["next_start"] is None:
                state["next_start"] = start
            previous_max = state["max_event_ms"]
            watermark_before = (previous_max - allowed_lateness_ms) if previous_max is not None else None
            is_late = watermark_before is not None and stamp < watermark_before
            if is_late:
                late_rows += 1
                if start < state["next_start"]:
                    continue
            item = state["windows"].setdefault(start, _new_window())
            mono = float(row.get("received_monotonic_s", 0.0))
            _touch_receive(item, mono)
            if is_late:
                item["late_event_count"] += 1
            if kind in {"book_update", "book_snapshot", "book_sync"}:
                item["depth_samples"].append(_depth_sample(row))
            elif kind == "agg_trade":
                quote = float(row["quote_quantity"])
                price = float(row["price"])
                second_start = stamp // 1000 * 1000
                second = item["trade_seconds"].setdefault(second_start, {
                    "second_start_ms": second_start, "trade_count": 0,
                    "buy_quote": 0.0, "sell_quote": 0.0,
                    "high": None, "high_event_ms": None,
                    "low": None, "low_event_ms": None,
                    "first": None, "last": None,
                })
                trade_quote = _first_trade_quote(row)
                if second["first"] is None or trade_quote["receive_mono"] < second["first"]["receive_mono"]:
                    second["first"] = trade_quote
                if second["last"] is None or trade_quote["receive_mono"] > second["last"]["receive_mono"]:
                    second["last"] = trade_quote
                second["trade_count"] += 1
                if second["high"] is None or price > second["high"]:
                    second["high"] = price
                    second["high_event_ms"] = stamp
                if second["low"] is None or price < second["low"]:
                    second["low"] = price
                    second["low_event_ms"] = stamp
                if row.get("seller_initiated"):
                    second["sell_quote"] += quote
                else:
                    second["buy_quote"] += quote
                item["trade_count"] += 1
                if item["trade_high"] is None or price > item["trade_high"]:
                    item["trade_high"] = price
                    item["trade_high_event_ms"] = stamp
                if item["trade_low"] is None or price < item["trade_low"]:
                    item["trade_low"] = price
                    item["trade_low_event_ms"] = stamp
                trade_id = row.get("trade_id")
                if item["first_trade_id"] is None:
                    item["first_trade_id"] = trade_id
                item["last_trade_id"] = trade_id
                if row.get("trade_id_gap_before"):
                    item["trade_gap_count"] += 1
                if row.get("seller_initiated"):
                    item["sell_quote"] += quote
                    item["sell_count"] += 1
                else:
                    item["buy_quote"] += quote
                    item["buy_count"] += 1
                if float(row.get("book_receive_age_ms", 0.0)) > 1000:
                    item["feed_event_count"] += 1
                    item["feed_event_categories"].add("stale_book_at_trade")
            elif kind == "feed_event":
                item["feed_event_count"] += 1
                item["feed_event_categories"].add(str(row.get("category") or "unknown"))
            if previous_max is None or stamp > previous_max:
                state["max_event_ms"] = stamp
            watermark = state["max_event_ms"] - allowed_lateness_ms
            advances = 0
            while state["next_start"] + WINDOW_MS + REFILL_MS <= watermark:
                emit(dst, symbol, state, state["next_start"])
                state["next_start"] += WINDOW_MS
                advances += 1
                if advances > MAX_EMPTY_WINDOWS_PER_ADVANCE:
                    raise ValueError("event-time jump exceeds bounded empty-window advance")
            if len(state["windows"]) > MAX_OPEN_WINDOWS_PER_SYMBOL:
                raise ValueError(f"open-window bound exceeded for {symbol}")
        dst.flush()
        os.fsync(dst.fileno())

    for symbol, state in states.items():
        incomplete_windows += len(state["windows"])
    if _sha256(source) != input_hash:
        raise IOError("compact input changed during window aggregation")
    os.replace(partial, output)
    manifest = {
        "format": "cointrade-l2-10s-windows-v1",
        "source_path": str(source), "source_sha256": input_hash,
        "input_rows": input_rows,
        "output_path": str(output), "output_sha256": output_hash.hexdigest(),
        "output_bytes": output.stat().st_size, "windows_written": rows_written,
        "late_input_rows": late_rows, "unfinalized_windows_withheld": incomplete_windows,
        "global_feed_events": global_feed_events,
        "global_disconnect_events": global_disconnect_events,
        "allowed_lateness_ms": allowed_lateness_ms,
        "window_ms": WINDOW_MS, "refill_observation_ms": REFILL_MS,
        "max_depth_endpoint_age_ms": MAX_DEPTH_ENDPOINT_AGE_MS,
        "strategy_metrics": None,
        "quality_pass": late_rows == 0 and global_disconnect_events == 0,
        "limitations": [
            "Window boundaries use exchange event timestamps; receive monotonic times are retained as availability evidence.",
            "Late events for already-finalized windows are counted in the manifest and never backfilled.",
            "No predictive labels, fills, confidence scores, or strategy metrics are calculated.",
            "A successful one-hour replay does not prove multi-day or multi-symbol capture reliability.",
        ],
    }
    with manifest_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="compact v1 JSONL")
    parser.add_argument("--output", required=True, type=Path, help="new 10-second windows JSONL")
    parser.add_argument("--allowed-lateness-ms", type=int, default=2000)
    parser.add_argument("--max-output-bytes", type=int, default=MAX_OUTPUT_BYTES)
    args = parser.parse_args()
    print(json.dumps(aggregate_windows(args.input, args.output,
                                      allowed_lateness_ms=args.allowed_lateness_ms,
                                      max_output_bytes=args.max_output_bytes), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
