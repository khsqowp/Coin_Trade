"""Offline depth-walk fills and target-first labels for R005 candidates."""
from __future__ import annotations

import math
from typing import Any

MAX_EXECUTION_QUOTE_GAP_MS = 750


def _num(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def walk_book(levels: list[list[Any]], *, order_side: str,
              quote_notional: float) -> dict[str, float] | None:
    """Walk the captured top-five levels for a fixed quote-notional market fill."""
    if order_side not in {"buy", "sell"}:
        raise ValueError("order_side must be buy or sell")
    if not _num(quote_notional) or quote_notional <= 0:
        raise ValueError("quote_notional must be finite and positive")
    if not isinstance(levels, list):
        return None
    parsed = []
    for level in levels:
        if not isinstance(level, (list, tuple)) or len(level) != 2:
            return None
        price, quantity = level
        if not _num(price) or not _num(quantity) or price <= 0 or quantity <= 0:
            return None
        parsed.append((float(price), float(quantity)))
    parsed.sort(key=lambda pair: pair[0], reverse=(order_side == "sell"))
    if not parsed:
        return None

    remaining_quote = float(quote_notional)
    filled_base = 0.0
    for price, available_base in parsed:
        level_quote = price * available_base
        take_quote = min(remaining_quote, level_quote)
        take_base = take_quote / price
        filled_base += take_base
        remaining_quote -= take_quote
        if remaining_quote <= max(1e-8, quote_notional * 1e-12):
            break
    if remaining_quote > max(1e-8, quote_notional * 1e-12) or filled_base <= 0:
        return None
    return {"filled_base": filled_base, "vwap": quote_notional / filled_base,
            "quote_notional": float(quote_notional)}


def walk_book_for_base(levels: list[list[Any]], *, order_side: str,
                       base_quantity: float) -> dict[str, float] | None:
    """Walk levels for the exact base quantity held by the simulated position."""
    if order_side not in {"buy", "sell"}:
        raise ValueError("order_side must be buy or sell")
    if not _num(base_quantity) or base_quantity <= 0:
        raise ValueError("base_quantity must be finite and positive")
    if not isinstance(levels, list):
        return None
    parsed = []
    for level in levels:
        if not isinstance(level, (list, tuple)) or len(level) != 2:
            return None
        price, quantity = level
        if not _num(price) or not _num(quantity) or price <= 0 or quantity <= 0:
            return None
        parsed.append((float(price), float(quantity)))
    parsed.sort(key=lambda pair: pair[0], reverse=(order_side == "sell"))
    remaining = float(base_quantity)
    quote_value = 0.0
    for price, available_base in parsed:
        take = min(remaining, available_base)
        quote_value += take * price
        remaining -= take
        if remaining <= max(1e-12, base_quantity * 1e-12):
            break
    if remaining > max(1e-12, base_quantity * 1e-12):
        return None
    return {"filled_base": float(base_quantity), "vwap": quote_value / base_quantity,
            "quote_notional": quote_value}


def _fill(row: dict[str, Any], *, order_side: str,
          quote_notional: float) -> dict[str, float] | None:
    levels_key = "ask_levels" if order_side == "buy" else "bid_levels"
    return walk_book(row.get(levels_key), order_side=order_side,
                     quote_notional=quote_notional)


def _fill_base(row: dict[str, Any], *, order_side: str,
               base_quantity: float) -> dict[str, float] | None:
    levels_key = "ask_levels" if order_side == "buy" else "bid_levels"
    return walk_book_for_base(row.get(levels_key), order_side=order_side,
                              base_quantity=base_quantity)


def _valid_quote_row(row: dict[str, Any]) -> bool:
    bid, ask = row.get("best_bid"), row.get("best_ask")
    return _num(bid) and _num(ask) and bid > 0 and ask >= bid


def _executable_crossed(row: dict[str, Any], *, side: str,
                        stop: float, target: float) -> tuple[bool, bool]:
    bid, ask = row.get("best_bid"), row.get("best_ask")
    if not _num(bid) or not _num(ask) or bid <= 0 or ask < bid:
        return False, False
    if side == "long":
        return bid <= stop, bid >= target
    return ask >= stop, ask <= target


def _stop_crossed(row: dict[str, Any], *, side: str, stop: float) -> bool:
    bid, ask = row.get("best_bid"), row.get("best_ask")
    if not _num(bid) or not _num(ask) or bid <= 0 or ask < bid:
        return False
    return bid <= stop if side == "long" else ask >= stop


def replay_candidate(
    candidate: dict[str, Any], quote_rows: list[dict[str, Any]], *,
    horizon_ms: int, atr14: float, tick_size: float,
    quote_notional: float = 1000.0, fee_per_side: float = 0.0005,
    funding_events: list[dict[str, Any]] | None = None,
    funding_coverage_complete: bool = False,
) -> dict[str, Any]:
    """Replay one candidate using strictly later observed quotes and depth fills.

    Missing depth, missing horizon coverage, or incomplete funding coverage
    never becomes a zero-cost success. The function scores one horizon only;
    10T and 20T views should reuse the same candidate and not count as separate
    independent signals.
    """
    side = candidate.get("side")
    if not isinstance(side, str) or side not in {"long", "short"}:
        raise ValueError("candidate side must be long or short")
    symbol = candidate.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("candidate must identify its symbol")
    signal_ms = candidate.get("signal_event_ms")
    signal_mono = candidate.get("signal_receive_monotonic_s")
    stop = candidate.get("stop_price_pre_entry")
    if isinstance(signal_ms, bool) or not isinstance(signal_ms, int):
        raise ValueError("candidate signal time must be integer event milliseconds")
    if not _num(signal_mono) or not _num(stop) or stop <= 0:
        raise ValueError("candidate receive time and stop must be finite")
    if isinstance(horizon_ms, bool) or not isinstance(horizon_ms, int) or horizon_ms <= 0:
        raise ValueError("horizon_ms must be a positive integer")
    deadline_ms = signal_ms + horizon_ms
    if not _num(atr14) or atr14 <= 0 or not _num(tick_size) or tick_size <= 0:
        raise ValueError("ATR14 and tick size must be finite and positive")
    if not _num(fee_per_side) or fee_per_side < 0:
        raise ValueError("fee_per_side must be finite and non-negative")
    if not _num(quote_notional) or quote_notional <= 0:
        raise ValueError("quote_notional must be finite and positive")
    if not isinstance(funding_coverage_complete, bool):
        raise ValueError("funding_coverage_complete must be a boolean evidence flag")
    stop_ticks = stop / tick_size
    if abs(stop_ticks - round(stop_ticks)) > 1e-7:
        return {"status": "UNSCORABLE", "reason": "stop_off_exchange_tick",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    if not isinstance(quote_rows, list):
        raise ValueError("quote_rows must be a list")
    if any(not isinstance(row, dict) for row in quote_rows):
        raise ValueError("quote_rows must contain objects")
    if any(row.get("symbol") != symbol for row in quote_rows):
        return {"status": "UNSCORABLE", "reason": "quote_path_symbol_mismatch",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    if any(isinstance(row.get("event_ms"), bool)
           or not isinstance(row.get("event_ms"), int)
           or not _num(row.get("receive_mono")) for row in quote_rows):
        return {"status": "UNSCORABLE", "reason": "invalid_quote_path_timestamp",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    if funding_events is None:
        funding_events = []
    if not isinstance(funding_events, list):
        raise ValueError("funding_events must be a list")

    rows = sorted(quote_rows, key=lambda row: (row.get("event_ms", -1),
                                                row.get("receive_mono", -1)))
    later_rows = [row for row in rows
                  if isinstance(row.get("event_ms"), int)
                  and not isinstance(row.get("event_ms"), bool)
                  and _num(row.get("receive_mono"))
                  and row["event_ms"] > signal_ms
                  and row["receive_mono"] > signal_mono
                  and row["event_ms"] <= deadline_ms + MAX_EXECUTION_QUOTE_GAP_MS]
    if any(right["receive_mono"] <= left["receive_mono"]
           for left, right in zip(later_rows, later_rows[1:])):
        return {"status": "UNSCORABLE", "reason": "receive_order_conflicts_with_event_order",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    # A post-event move through the structural stop cancels the candidate
    # before any hypothetical entry. No retroactive fill is permitted.
    entry_row = None
    entry_candidates = [row for row in later_rows if row["event_ms"] <= deadline_ms]
    if (entry_candidates
            and entry_candidates[0]["event_ms"] - signal_ms > MAX_EXECUTION_QUOTE_GAP_MS):
        return {"status": "UNSCORABLE", "reason": "entry_quote_gap_exceeds_750ms",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    for row in entry_candidates:
        if _stop_crossed(row, side=side, stop=stop):
            return {"status": "INVALIDATED_BEFORE_ENTRY", "target_first": False,
                    "entry": None, "exit": None, "net_return": None}
        entry_row = row
        break
    if entry_row is None:
        return {"status": "UNSCORABLE", "reason": "missing_post_signal_entry_quote",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    if not _valid_quote_row(entry_row):
        return {"status": "UNSCORABLE", "reason": "invalid_quote_path_row",
                "target_first": None, "entry": None, "exit": None, "net_return": None}

    entry_order = "buy" if side == "long" else "sell"
    exit_order = "sell" if side == "long" else "buy"
    entry_fill = _fill(entry_row, order_side=entry_order, quote_notional=quote_notional)
    if entry_fill is None:
        return {"status": "UNSCORABLE", "reason": "insufficient_entry_depth",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    reverse_fill = _fill_base(entry_row, order_side=exit_order,
                              base_quantity=entry_fill["filled_base"])
    if reverse_fill is None:
        return {"status": "UNSCORABLE", "reason": "insufficient_entry_depth",
                "target_first": None, "entry": None, "exit": None, "net_return": None}
    entry = entry_fill["vwap"]
    risk = abs(entry - stop)
    if risk <= 0:
        return {"status": "UNSCORABLE", "reason": "zero_risk_distance",
                "target_first": None, "entry": entry, "exit": None, "net_return": None}
    if (side == "long" and stop >= entry) or (side == "short" and stop <= entry):
        return {"status": "INVALIDATED_BEFORE_ENTRY", "reason": "entry_wrong_side_of_structural_stop",
                "target_first": False, "entry": entry, "exit": None, "net_return": None}
    if risk > 2 * atr14:
        return {"status": "REJECTED_RISK", "reason": "risk_exceeds_2_atr",
                "target_first": None, "entry": entry, "exit": None, "net_return": None}

    target = entry + risk if side == "long" else entry - risk
    if target <= 0:
        return {"status": "UNSCORABLE", "reason": "non_positive_target",
                "target_first": None, "entry": entry, "exit": None, "net_return": None}
    mid = (float(entry_row["best_bid"]) + float(entry_row["best_ask"])) / 2
    if mid <= 0:
        return {"status": "UNSCORABLE", "reason": "invalid_entry_quote",
                "target_first": None, "entry": entry, "exit": None, "net_return": None}
    entry_touch = float(entry_row["best_ask" if side == "long" else "best_bid"])
    exit_touch = float(entry_row["best_bid" if side == "long" else "best_ask"])
    entry_slippage_fraction = max(0.0, (entry - entry_touch) * (1 if side == "long" else -1)) / mid
    entry_exit_slippage_fraction = max(0.0, (exit_touch - reverse_fill["vwap"])
                                       * (1 if side == "long" else -1)) / mid
    estimated_round_trip_cost_fraction = (abs(entry - mid) / mid
                                          + abs(reverse_fill["vwap"] - mid) / mid
                                          + 2 * fee_per_side)
    if risk < 2 * entry * estimated_round_trip_cost_fraction:
        return {"status": "REJECTED_RISK", "reason": "risk_below_2x_round_trip_cost",
                "target_first": None, "entry": entry, "exit": None, "net_return": None,
                "estimated_round_trip_cost_fraction": estimated_round_trip_cost_fraction}

    candidates = [row for row in later_rows
                  if row["event_ms"] > entry_row["event_ms"]
                  and row["receive_mono"] > entry_row["receive_mono"]]
    exit_row = None
    exit_reason = None
    previous_event_ms = entry_row["event_ms"]
    previous_receive_mono = entry_row["receive_mono"]
    for row in candidates:
        if row["receive_mono"] <= previous_receive_mono:
            return {"status": "UNSCORABLE", "reason": "receive_order_conflicts_with_event_order",
                    "target_first": None, "entry": entry, "exit": None, "net_return": None}
        if not _valid_quote_row(row):
            return {"status": "UNSCORABLE", "reason": "invalid_quote_path_row",
                    "target_first": None, "entry": entry, "exit": None, "net_return": None}
        if row["event_ms"] - previous_event_ms > MAX_EXECUTION_QUOTE_GAP_MS:
            return {"status": "UNSCORABLE", "reason": "execution_quote_gap_exceeds_750ms",
                    "target_first": None, "entry": entry, "exit": None, "net_return": None}
        previous_event_ms = row["event_ms"]
        previous_receive_mono = row["receive_mono"]
        if row["event_ms"] > deadline_ms:
            exit_row = row
            exit_reason = "timeout"
            break
        stop_hit, target_hit = _executable_crossed(row, side=side, stop=stop, target=target)
        if stop_hit or target_hit:
            exit_row = row
            exit_reason = "stop" if stop_hit else "target"  # stop-first tie rule
            break
        if row["event_ms"] >= deadline_ms:
            exit_row = row
            exit_reason = "timeout"
            break
    if exit_row is None:
        return {"status": "UNSCORABLE", "reason": "path_does_not_cover_horizon",
                "target_first": None, "entry": entry, "exit": None, "net_return": None}

    exit_fill = _fill_base(exit_row, order_side=exit_order,
                           base_quantity=entry_fill["filled_base"])
    if exit_fill is None:
        return {"status": "UNSCORABLE", "reason": "insufficient_exit_depth",
                "target_first": None, "entry": entry, "exit": None, "net_return": None}

    actual_exit_touch = float(exit_row["best_bid" if side == "long" else "best_ask"])
    actual_exit_slippage_fraction = max(
        0.0, (exit_fill["vwap"] - actual_exit_touch) * (1 if side == "short" else -1),
    ) / mid

    direction = 1.0 if side == "long" else -1.0
    gross_pnl = direction * (exit_fill["vwap"] - entry) * entry_fill["filled_base"]
    fees = fee_per_side * (entry_fill["quote_notional"] + exit_fill["quote_notional"])
    funding_pnl = 0.0
    funding_unscorable = not funding_coverage_complete
    for event in funding_events:
        if not isinstance(event, dict):
            return {"status": "UNSCORABLE", "reason": "invalid_funding_record",
                    "target_first": None, "entry": entry, "exit": exit_fill["vwap"],
                    "net_return": None}
        stamp, rate, mark = event.get("time_ms"), event.get("rate"), event.get("mark")
        if (isinstance(stamp, bool) or not isinstance(stamp, int)
                or not _num(rate) or not _num(mark) or mark <= 0):
            return {"status": "UNSCORABLE", "reason": "invalid_funding_record",
                    "target_first": None, "entry": entry, "exit": exit_fill["vwap"],
                    "net_return": None}
        if entry_row["event_ms"] < stamp <= exit_row["event_ms"]:
            funding_pnl -= direction * float(rate) * float(mark) * entry_fill["filled_base"]
    net_pnl = gross_pnl - fees + funding_pnl
    net_return = None if funding_unscorable else net_pnl / quote_notional
    stress_net_return = (None if funding_unscorable else
                         (gross_pnl - 2 * fees - (entry_slippage_fraction + actual_exit_slippage_fraction)
                          * mid * entry_fill["filled_base"] + funding_pnl) / quote_notional)
    return {
        "status": "SCORED" if not funding_unscorable else "SCORED_GROSS_FUNDING_UNVERIFIED",
        "reason": None if not funding_unscorable else "funding_coverage_incomplete",
        "target_first": exit_reason == "target",
        "exit_reason": exit_reason,
        "entry_event_ms": entry_row["event_ms"],
        "exit_event_ms": exit_row["event_ms"],
        "entry": entry,
        "stop": stop,
        "target": target,
        "exit": exit_fill["vwap"],
        "risk_distance": risk,
        "gross_pnl": gross_pnl,
        "fees": fees,
        "funding_pnl": funding_pnl,
        "net_return": net_return,
        "stress_net_return": stress_net_return,
        "estimated_round_trip_cost_fraction": estimated_round_trip_cost_fraction,
        "entry_slippage_fraction": entry_slippage_fraction,
        "entry_snapshot_exit_slippage_fraction": entry_exit_slippage_fraction,
        "actual_exit_slippage_fraction": actual_exit_slippage_fraction,
    }
