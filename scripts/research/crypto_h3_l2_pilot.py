"""Replay the preregistered H3 top-five L2 imbalance pilot (no orders)."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from chart_predictor.l2_book import LocalBook, SequenceGap

FROZEN_INPUT_SHA256 = "aff87b771f2494fdc70ccc424e0a383f32670183d9753a83e68a92b9ebb1a991"
DEFAULT_TICK_SIZES = {"BTCUSDT": 0.10, "ETHUSDT": 0.01}
ROUND_TRIP_FEE = 0.001
HORIZONS_S = (1, 3, 5)
CONFIRM_SECONDS = 1.0
COOLDOWN_SECONDS = 5.0
RANDOM_SEED = 20261116


@dataclass(frozen=True)
class QuotePoint:
    symbol: str
    received_mono: float
    received_ms: int
    bid: float
    ask: float
    mid: float
    imbalance: float | None
    epoch: int
    source: str


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _point(book: LocalBook, symbol: str, record: dict[str, Any], epoch: int,
           source: str) -> QuotePoint | None:
    if not book.valid or len(book.bids) < 5 or len(book.asks) < 5:
        return None
    bids = sorted(book.bids.items(), reverse=True)[:5]
    asks = sorted(book.asks.items())[:5]
    bid, ask = bids[0][0], asks[0][0]
    if bid <= 0 or ask <= 0 or bid >= ask:
        return None
    bid_qty = sum(q for _, q in bids)
    ask_qty = sum(q for _, q in asks)
    total = bid_qty + ask_qty
    imbalance = (bid_qty - ask_qty) / total if total > 0 else None
    return QuotePoint(
        symbol=symbol,
        received_mono=float(record["received_monotonic_s"]),
        received_ms=int(record["received_at_ms"]),
        bid=bid,
        ask=ask,
        mid=(bid + ask) / 2.0,
        imbalance=imbalance,
        epoch=epoch,
        source=source,
    )


def reconstruct(path: Path, expected_sha256: str | None = None) -> tuple[dict[str, list[QuotePoint]], dict[str, Any]]:
    """Rebuild snapshot-bridged books from the recorded write order, fail closed."""
    digest = _sha256(path)
    if expected_sha256 and digest != expected_sha256:
        raise ValueError(f"input SHA-256 mismatch: {digest}")
    books = {symbol: LocalBook() for symbol in DEFAULT_TICK_SIZES}
    buffers: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in books}
    snapshots: dict[str, dict[str, Any] | None] = {symbol: None for symbol in books}
    epochs = {symbol: 0 for symbol in books}
    points: dict[str, list[QuotePoint]] = {symbol: [] for symbol in books}
    counts: dict[str, int] = {"json_rows": 0, "depth_deltas": 0, "depth_snapshots": 0,
                              "book_invalid": 0, "book_valid": 0,
                              "sequence_errors": 0, "unbridged_snapshots": 0}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            record = json.loads(line)
            counts["json_rows"] += 1
            kind, symbol = record.get("kind"), record.get("symbol")
            if symbol not in books:
                if kind == "connection" and record.get("stream") == "depth" and record.get("state") == "disconnected":
                    for name in books:
                        books[name].invalidate("depth_disconnect")
                        buffers[name].clear()
                        snapshots[name] = None
                        epochs[name] += 1
                continue

            book = books[symbol]
            if kind == "depth_snapshot":
                counts["depth_snapshots"] += 1
                snapshots[symbol] = record.get("event")
                continue

            if kind == "depth_delta":
                counts["depth_deltas"] += 1
                event = record.get("event")
                if not isinstance(event, dict):
                    raise ValueError(f"line {line_number}: depth delta missing event")
                if book.valid:
                    try:
                        book.apply_diff(event)
                    except (SequenceGap, ValueError):
                        counts["sequence_errors"] += 1
                        buffers[symbol] = [event]
                        snapshots[symbol] = None
                        epochs[symbol] += 1
                        continue
                    point = _point(book, symbol, record, epochs[symbol], "depth_delta")
                    if point is not None:
                        points[symbol].append(point)
                else:
                    buffers[symbol].append(event)
                continue

            if kind == "book_state" and record.get("state") == "invalid":
                counts["book_invalid"] += 1
                book.invalidate(str(record.get("reason") or "invalid_state"))
                epochs[symbol] += 1
                continue

            if kind == "book_state" and record.get("state") == "valid":
                if not book.valid:
                    snapshot = snapshots[symbol]
                    if not isinstance(snapshot, dict):
                        counts["unbridged_snapshots"] += 1
                        buffers[symbol].clear()
                        continue
                    try:
                        if not book.install_snapshot(snapshot, buffers[symbol]):
                            counts["unbridged_snapshots"] += 1
                            buffers[symbol].clear()
                            snapshots[symbol] = None
                            continue
                    except (SequenceGap, ValueError):
                        counts["sequence_errors"] += 1
                        buffers[symbol].clear()
                        snapshots[symbol] = None
                        book.invalidate("replay_snapshot_bridge_error")
                        epochs[symbol] += 1
                        continue
                    buffers[symbol].clear()
                counts["book_valid"] += 1
                point = _point(book, symbol, record, epochs[symbol], "snapshot_bridge")
                if point is not None:
                    points[symbol].append(point)

    for symbol, rows in points.items():
        if any(a.received_mono > b.received_mono for a, b in zip(rows, rows[1:])):
            raise ValueError(f"{symbol}: reconstructed quote times are not monotonic")
    return points, {"input_sha256": digest, **counts,
                    "quotes_by_symbol": {s: len(v) for s, v in points.items()}}


def detect_events(points: dict[str, list[QuotePoint]], tick_sizes: dict[str, float]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    events: list[dict[str, Any]] = []
    eligible_updates: dict[str, int] = {}
    for symbol, rows in points.items():
        tick = float(tick_sizes[symbol])
        streak_side = 0
        streak_count = 0
        streak_epoch: int | None = None
        pending: dict[str, Any] | None = None
        cooldown_until = float("-inf")
        update_count = 0
        for point in rows:
            if point.source != "depth_delta":
                streak_side, streak_count, streak_epoch, pending = 0, 0, None, None
                continue
            update_count += 1
            if streak_epoch != point.epoch:
                streak_side, streak_count, streak_epoch, pending = 0, 0, point.epoch, None
            if pending is not None:
                if point.received_mono - pending["trigger_mono"] > CONFIRM_SECONDS:
                    pending = None
                elif point.received_mono > pending["trigger_mono"]:
                    move = point.mid - pending["reference_mid"]
                    if move >= tick - 1e-9 and pending["side"] == 1:
                        signal = True
                    elif move <= -tick + 1e-9 and pending["side"] == -1:
                        signal = True
                    else:
                        signal = False
                    if signal:
                        if point.received_mono >= cooldown_until:
                            events.append({
                                "symbol": symbol,
                                "side": pending["side"],
                                "trigger_mono": pending["trigger_mono"],
                                "trigger_ms": pending["trigger_ms"],
                                "entry_mono": point.received_mono,
                                "entry_ms": point.received_ms,
                                "entry_mid": point.mid,
                                "entry_bid": point.bid,
                                "entry_ask": point.ask,
                                "tick_size": tick,
                                "epoch": point.epoch,
                                "confirmation_move": move,
                            })
                            cooldown_until = point.received_mono + COOLDOWN_SECONDS
                        pending = None
                        streak_side, streak_count = 0, 0
                        continue
                if pending is not None:
                    continue
            if point.received_mono < cooldown_until or point.imbalance is None:
                streak_side, streak_count = 0, 0
                continue
            side = 1 if point.imbalance > 0.60 else (-1 if point.imbalance < -0.60 else 0)
            if side == 0:
                streak_side, streak_count = 0, 0
                continue
            if side == streak_side:
                streak_count += 1
            else:
                streak_side, streak_count = side, 1
            if streak_count == 3:
                pending = {"side": side, "trigger_mono": point.received_mono,
                           "trigger_ms": point.received_ms, "reference_mid": point.mid}
                streak_side, streak_count = 0, 0
        eligible_updates[symbol] = update_count
    return events, eligible_updates


def _wilson(successes: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if n == 0:
        return None
    p = successes / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return [center - half, center + half]


def _outcome(points: list[QuotePoint], event: dict[str, Any], horizon: int) -> dict[str, Any] | None:
    due = event["entry_mono"] + horizon
    selected = next((p for p in points if p.epoch == event["epoch"] and p.received_mono >= due), None)
    if selected is None or selected.received_mono > due + 1.0:
        return None
    side = event["side"]
    mid_return = side * (selected.mid / event["entry_mid"] - 1.0)
    if side == 1:
        gross_quote_return = selected.bid / event["entry_ask"] - 1.0
    else:
        gross_quote_return = event["entry_bid"] / selected.ask - 1.0
    net_quote_return = gross_quote_return - ROUND_TRIP_FEE
    return {"observed_mono": selected.received_mono,
            "observed_delay_after_due_s": selected.received_mono - due,
            "side_correct": mid_return > 0,
            "raw_mid_return_bps": (selected.mid / event["entry_mid"] - 1.0) * 10000,
            "signed_mid_return_bps": mid_return * 10000,
            "cross_spread_net_return_bps": net_quote_return * 10000}


def _prior_momentum(points: list[QuotePoint], event: dict[str, Any]) -> int:
    previous = next((p for p in reversed(points)
                     if p.epoch == event["epoch"] and p.received_mono <= event["entry_mono"] - 1.0), None)
    if previous is None:
        return 0
    delta = event["entry_mid"] - previous.mid
    return 1 if delta > 0 else (-1 if delta < 0 else 0)


def score(points: dict[str, list[QuotePoint]], events: list[dict[str, Any]],
          eligible_updates: dict[str, int], metadata: dict[str, Any],
          tick_sizes: dict[str, float]) -> dict[str, Any]:
    rng = random.Random(RANDOM_SEED)
    for event in events:
        event["price_only_momentum_side"] = _prior_momentum(points[event["symbol"]], event)
        event["random_side"] = rng.choice((-1, 1))
    results: dict[str, Any] = {}
    for horizon in HORIZONS_S:
        rows: list[dict[str, Any]] = []
        for event in events:
            outcome = _outcome(points[event["symbol"]], event, horizon)
            if outcome is not None:
                rows.append({**event, **outcome})
        by_symbol: dict[str, Any] = {}
        for symbol in points:
            cell = [r for r in rows if r["symbol"] == symbol]
            side_hits = sum(bool(r["side_correct"]) for r in cell)
            by_symbol[symbol] = {
                "n_scored": len(cell),
                "signal_count": sum(e["symbol"] == symbol for e in events),
                "side_correct": side_hits,
                "directional_hit_rate": side_hits / len(cell) if cell else None,
                "wilson_95_descriptive_only": _wilson(side_hits, len(cell)),
                "mean_signed_mid_markout_bps": sum(r["signed_mid_return_bps"] for r in cell) / len(cell) if cell else None,
                "mean_cross_spread_fee_net_bps": sum(r["cross_spread_net_return_bps"] for r in cell) / len(cell) if cell else None,
            }
        candidate_hits = sum(bool(r["side_correct"]) for r in rows)
        comparator: dict[str, Any] = {}
        for name, field in (("prior_1s_mid_momentum", "price_only_momentum_side"),
                            ("fixed_seed_random", "random_side")):
            matched = [r for r in rows if r[field] != 0]
            hits = sum(r[field] * r["raw_mid_return_bps"] > 0 for r in matched)
            comparator[name] = {"n": len(matched), "hits": hits,
                                "directional_hit_rate": hits / len(matched) if matched else None}
        results[str(horizon)] = {
            "n_signals": len(events), "n_scored": len(rows),
            "unscorable": len(events) - len(rows),
            "candidate_hits": candidate_hits,
            "candidate_directional_hit_rate": candidate_hits / len(rows) if rows else None,
            "wilson_95_descriptive_only": _wilson(candidate_hits, len(rows)),
            "mean_signed_mid_markout_bps": sum(r["signed_mid_return_bps"] for r in rows) / len(rows) if rows else None,
            "mean_cross_spread_fee_net_bps": sum(r["cross_spread_net_return_bps"] for r in rows) / len(rows) if rows else None,
            "comparators": comparator,
            "by_symbol": by_symbol,
        }
    return {
        "experiment": "crypto_h3_l2_pilot",
        "classification": "descriptive_development_pilot_not_validation",
        "input": metadata,
        "code_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=BASE, check=True,
                                       capture_output=True, text=True).stdout.strip(),
        "tick_sizes": tick_sizes,
        "rule": {"top_levels": 5, "imbalance_threshold_abs_strictly_greater_than": 0.60,
                 "consecutive_valid_depth_updates": 3, "confirmation_ticks": 1,
                 "confirmation_window_s": CONFIRM_SECONDS, "cooldown_s": COOLDOWN_SECONDS,
                 "round_trip_fee": ROUND_TRIP_FEE, "horizons_s": list(HORIZONS_S),
                 "random_seed": RANDOM_SEED},
        "events": events,
        "eligible_depth_updates": eligible_updates,
        "signal_coverage_per_valid_depth_update": {
            s: len([e for e in events if e["symbol"] == s]) / eligible_updates[s]
            if eligible_updates[s] else None for s in eligible_updates
        },
        "scores": results,
        "limits": [
            "Two symbols and one capture hour cannot meet the registered 20-symbol sealed M4 gate.",
            "Wilson intervals are descriptive and do not account for serial/event dependence.",
            "Best-quote crossing with a fixed fee omits queue position, impact, and post-receive execution delay; it is not a fill simulation.",
            "One client-side disconnect was injected; router, ISP, and exchange-side failures were not tested.",
        ],
        "decision": "PENDING_REVIEW",
    }


def run(input_path: Path, output_path: Path, expected_sha256: str | None = FROZEN_INPUT_SHA256,
        tick_sizes: dict[str, float] | None = None) -> dict[str, Any]:
    ticks = tick_sizes or DEFAULT_TICK_SIZES
    points, metadata = reconstruct(input_path, expected_sha256)
    events, eligible = detect_events(points, ticks)
    result = score(points, events, eligible, metadata, ticks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=FROZEN_INPUT_SHA256)
    args = parser.parse_args(argv)
    result = run(args.input, args.output, args.expected_sha256)
    print(json.dumps({"output": str(args.output), "signals": len(result["events"]),
                      "classification": result["classification"],
                      "scores": {h: {"n": r["n_scored"], "hit_rate": r["candidate_directional_hit_rate"]}
                                 for h, r in result["scores"].items()}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
