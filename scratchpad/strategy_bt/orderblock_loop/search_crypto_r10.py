"""R10 TRAIN-only hierarchical 4h-parent/1h-child BOS-origin candidate.

Pure state-machine helpers accept in-memory bars; the explicit CLI adapter reads
only the registered TRAIN window and writes its event cache outside this repo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import resource
from pathlib import Path
import sys
import uuid
from typing import Mapping, Sequence

from crypto import (Bar, FundingEvent, Setup, Trade, Zone, _validate, r4_zones,
                    simulate_trade, trade_daily_pnl)
from metrics import curve_metrics, trade_metrics, wilson_lower

HOUR_MS = 3_600_000
FOUR_HOUR_MS = 4 * HOUR_MS
PARENT_LIFE = 48
CHILD_LIFE = 24
HOLD_BARS = 48
CUTOFF_MS = 1_699_286_400_000  # 2023-11-06T16:00:00Z
HERE = Path(__file__).resolve().parent
UNIVERSE_PATH = HERE / "universe" / "CRYPTO_35.csv"
PREREG_PATH = HERE / "PREREG.md"
TRIAL_CSV_PATH = HERE / "TRAIN_TRIALS.csv"
TRIAL_FIELDS = ("trial_id", "round", "market_group", "utc_timestamp", "definition",
                "parameter_grid_hash", "code_sha256", "train_period", "metric",
                "rank", "notes")
CONFIG = {"round": "R10-coin", "definition": "bos_origin",
          "parent_timeframe": "4h", "child_timeframe": "1h",
          "parent_life_bars": 48, "child_retest_bars": 24,
          "reward_r": 2.0, "hold_bars": 48, "cost_bps_round_trip": 12,
          "funding_order_policy": "adverse_only", "cutoff_ms": CUTOFF_MS}


def segments(bars: Sequence[Bar], duration_ms: int) -> list[tuple[int, int]]:
    """Validate completed aligned bars; return half-open continuous segments."""
    if duration_ms <= 0:
        raise ValueError("duration_ms must be positive")
    if any(not b.complete for b in bars):
        raise ValueError("completed bars only")
    if any(b.timestamp % duration_ms for b in bars):
        raise ValueError("open timestamps must align to UTC boundaries")
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError("timestamps must be strictly increasing")
    if not bars:
        return []
    out, start = [], 0
    for i in range(1, len(bars)):
        if bars[i].timestamp - bars[i - 1].timestamp != duration_ms:
            out.append((start, i))
            start = i
    out.append((start, len(bars)))
    return out


def stable_id(symbol: str, segment_start: int, signal_ts: int,
              direction: str, role: str) -> str:
    """Stable role-specific ID with all preregistered identity components."""
    if role not in {"parent", "child", "trade"}:
        raise ValueError("invalid identity role")
    raw = f"{symbol}|{segment_start}|{signal_ts}|{direction}|{role}"
    return hashlib.sha256(raw.encode()).hexdigest()


def contact(bar: Bar, zone: Zone) -> bool:
    return bar.low <= zone.high and bar.high >= zone.low


def invalid(bar: Bar, zone: Zone) -> bool:
    return bar.low <= zone.low if zone.direction == "long" else bar.high >= zone.high


@dataclass
class SequenceState:
    symbol: str
    parent: Zone
    parent_id: str
    segment_start: int
    parent_signal_close: int
    parent_retest_close: int | None = None
    parent_retest_index: int | None = None
    child: Zone | None = None
    child_id: str | None = None
    child_retest_close: int | None = None
    child_retest_index: int | None = None
    terminal: bool = False
    events: list[dict] = field(default_factory=list)

    def emit(self, status: str, **fields) -> dict:
        row = {"symbol": self.symbol, "parent_zone_id": self.parent_id,
               "child_zone_id": self.child_id, "status": status, **fields}
        self.events.append(row)
        return row


def choose_parent_candidates(zones: Sequence[Zone]) -> dict[int, Zone]:
    """Drop all directions on a 4h timestamp when opposing origins coincide."""
    grouped: dict[int, list[Zone]] = {}
    for z in zones:
        grouped.setdefault(z.signal_index, []).append(z)
    return {i: zs[0] for i, zs in grouped.items()
            if len(zs) == 1 and len({z.direction for z in zs}) == 1}


def _eligible_child(parent: Zone, parent_retest_close: int,
                    child: Zone, child_close: int) -> bool:
    return (child_close > parent_retest_close
            and child.direction == parent.direction
            and child.low >= parent.low and child.high <= parent.high)


def first_child_retest(bars: Sequence[Bar], zone: Zone) -> tuple[str, int | None]:
    """First overlap/invalidation in child bars signal+1 through signal+24."""
    end = min(len(bars) - 1, zone.signal_index + CHILD_LIFE)
    for i in range(zone.signal_index + 1, end + 1):
        bar = bars[i]
        if contact(bar, zone):
            return ("invalidated", None) if invalid(bar, zone) else ("retested", i)
        if invalid(bar, zone):
            return "invalidated", None
    if len(bars) - 1 < zone.signal_index + CHILD_LIFE:
        return "right_censored", None
    return "expired", None


def _zone_id(symbol: str, segment_start: int, bars: Sequence[Bar], zone: Zone,
             role: str) -> str:
    return stable_id(symbol, segment_start, bars[zone.signal_index].timestamp,
                     zone.direction, role)


def _replay_parent_closes(state: SequenceState, parent_bars: Sequence[Bar],
                          signal_i: int, through_ts: int,
                          next_parent_i: int) -> tuple[int, str | None]:
    """Apply every eligible completed parent close up to timestamp, in order."""
    i = next_parent_i
    while i < min(len(parent_bars), signal_i + PARENT_LIFE + 1):
        close_ts = parent_bars[i].timestamp + FOUR_HOUR_MS
        if close_ts > through_ts:
            break
        age = i - signal_i
        if invalid(parent_bars[i], state.parent):
            state.emit("parent_invalidated", parent_close=close_ts,
                       expiry_coincident=(age == PARENT_LIFE))
            return i + 1, "parent_invalidated"
        if age == PARENT_LIFE:
            state.emit("parent_expired", parent_close=close_ts)
            return i + 1, "parent_expired"
        i += 1
    return i, None


def _event(state: SequenceState, status: str, **fields) -> dict:
    """Add stable linkage and event timing to every funnel record."""
    return state.emit(status, **fields)


def _segment_after_gap(segments_: Sequence[tuple[int, int]], stop: int) -> bool:
    return any(start >= stop for start, _ in segments_)


def _next_parent_after_close(parent_bars: Sequence[Bar], timestamp: int) -> int:
    """First parent signal whose close is strictly after sequence termination."""
    return next((i for i,b in enumerate(parent_bars)
                 if b.timestamp+FOUR_HOUR_MS > timestamp),len(parent_bars))


def simulate_symbol(symbol: str, bars4h: Sequence[Bar], bars1h: Sequence[Bar],
                    funding: Mapping[int, FundingEvent] | None = None,
                    *, parent_zones: Sequence[Zone] | None = None,
                    child_zones: Sequence[Zone] | None = None,
                    cutoff_ms: int = CUTOFF_MS) -> tuple[list[Trade], list[dict], dict[str, int]]:
    """Replay one parent sequence against one overlapping 1h continuous segment."""
    _validate(bars4h)
    _validate(bars1h)
    pseg, cseg = segments(bars4h, FOUR_HOUR_MS), segments(bars1h, HOUR_MS)
    keys = ("parents", "parent_retests", "children", "child_retests", "trades",
            "sequence_gap_terminated", "parent_invalidated", "parent_expired",
            "child_failed", "cutoff_child_censored", "cutoff_entry_censored", "cutoff_exit_censored",
            "entry_skipped", "ignored_parent_signals", "ambiguous_parent",
            "ambiguous_child", "child_candidates_considered",
            "child_rejected_direction", "child_rejected_outside_parent",
            "funding_unscorable_trades", "funding_ambiguous_trades")
    counts = dict.fromkeys(keys, 0)
    trades: list[Trade] = []
    events: list[dict] = []
    raw_parents = list(parent_zones) if parent_zones is not None else None
    raw_children = list(child_zones) if child_zones is not None else None
    funding = funding or {}
    busy_until_global = -1

    for ps, pe in pseg:
        ppart = list(bars4h[ps:pe])
        pstart = ppart[0].timestamp
        if raw_parents is None:
            pzs = r4_zones(ppart, "bos_origin")
        else:
            pzs = [Zone(z.signal_index-ps, z.origin_index-ps, z.direction,
                        z.low, z.high, z.atr_at_signal)
                   for z in raw_parents if ps <= z.signal_index < pe]
        grouped_p = _group_zones(pzs)
        counts["ambiguous_parent"] += sum(len(v) > 1 for v in grouped_p.values())
        pmap = choose_parent_candidates(pzs)
        processed_parent_signals=set()
        pi = 0
        while pi < len(ppart):
            if pi not in pmap:
                pi += 1
                continue
            parent = pmap[pi]
            processed_parent_signals.add(pi)
            signal_open = ppart[pi].timestamp
            if signal_open + FOUR_HOUR_MS <= busy_until_global:
                counts["ignored_parent_signals"] += 1
                events.append({"symbol":symbol,"status":"parent_ignored_active_sequence",
                    "parent_zone_id":_zone_id(symbol,pstart,ppart,parent,"parent"),
                    "parent_signal_open":signal_open,
                    "parent_signal_close":signal_open+FOUR_HOUR_MS,
                    "direction":parent.direction,"segment_start_utc":pstart})
                pi += 1
                continue
            counts["parents"] += 1
            pid = _zone_id(symbol, pstart, ppart, parent, "parent")
            state = SequenceState(symbol, parent, pid, pstart,
                signal_open + FOUR_HOUR_MS)
            _event(state, "parent_created", parent_signal_open=signal_open,
                   parent_signal_close=state.parent_signal_close,
                   parent_signal_index=pi, segment_start_utc=pstart)

            # Scan only bars after this parent's actual signal index.
            retest_i = None
            terminal_reason = None
            last_age = min(PARENT_LIFE, len(ppart)-1-pi)
            for age in range(1, last_age+1):
                j = pi + age
                pb = ppart[j]
                if invalid(pb, parent):
                    terminal_reason = "parent_invalidated"
                    _event(state, terminal_reason,
                           parent_close=pb.timestamp+FOUR_HOUR_MS,
                           expiry_coincident=(age == PARENT_LIFE))
                    counts[terminal_reason] += 1
                    break
                if contact(pb, parent):
                    retest_i = j
                    state.parent_retest_index = j
                    state.parent_retest_close = pb.timestamp+FOUR_HOUR_MS
                    counts["parent_retests"] += 1
                    _event(state, "parent_retested", parent_retest_open=pb.timestamp,
                           parent_retest_close=state.parent_retest_close,
                           parent_retest_index=j, parent_age_bars=age)
                    break
            if terminal_reason:
                busy_until_global=max(busy_until_global,pb.timestamp+FOUR_HOUR_MS)
                pi = min(pe-ps, pi + (j-pi) + 1)
                events.extend(state.events)
                continue
            if retest_i is None:
                if last_age == PARENT_LIFE:
                    expiry_ts=ppart[pi+PARENT_LIFE].timestamp+FOUR_HOUR_MS
                    _event(state, "parent_expired", parent_close=expiry_ts)
                    counts["parent_expired"] += 1
                    busy_until_global=max(busy_until_global,expiry_ts)
                    pi += PARENT_LIFE + 1
                elif _segment_after_gap(pseg, pe):
                    busy_until_global=max(busy_until_global,ppart[-1].timestamp+FOUR_HOUR_MS)
                    _event(state, "sequence_gap_terminated", reason="parent_4h_gap",
                           gap_after_utc=ppart[-1].timestamp+FOUR_HOUR_MS)
                    counts["sequence_gap_terminated"] += 1
                    pi = pe-ps
                else:
                    busy_until_global=max(busy_until_global,ppart[-1].timestamp+FOUR_HOUR_MS)
                    _event(state, "parent_right_censored", reason="train_segment_end")
                    pi = pe-ps
                events.extend(state.events)
                continue
            age_retest = retest_i-pi
            if age_retest == PARENT_LIFE:
                _event(state, "parent_expired_on_retest", parent_close=state.parent_retest_close)
                counts["parent_expired"] += 1
                busy_until_global=max(busy_until_global,state.parent_retest_close)
                events.extend(state.events)
                pi = retest_i+1
                continue

            # Select the 1h segment containing the parent signal itself. Never
            # jump to a later segment after a missing hour.
            c_bounds = next(((a,b) for a,b in cseg
                if bars1h[a].timestamp <= signal_open < bars1h[b-1].timestamp+HOUR_MS), None)
            if c_bounds is None:
                _event(state, "sequence_gap_terminated", reason="no_1h_segment_at_parent_signal")
                counts["sequence_gap_terminated"] += 1
                busy_until_global=max(busy_until_global,state.parent_retest_close)
                events.extend(state.events)
                pi = retest_i+1
                continue
            cs, ce = c_bounds
            parent_segment_end = ppart[-1].timestamp + FOUR_HOUR_MS
            cpart = [b for b in bars1h[cs:ce] if b.timestamp < parent_segment_end]
            if not cpart or cpart[0].timestamp > signal_open:
                _event(state, "sequence_gap_terminated", reason="1h_gap_at_parent_signal")
                counts["sequence_gap_terminated"] += 1
                busy_until_global=max(busy_until_global,state.parent_retest_close)
                events.extend(state.events)
                pi = retest_i+1
                continue
            cstart = cpart[0].timestamp
            if raw_children is None:
                czs = r4_zones(cpart, "bos_origin")
            else:
                czs = [Zone(z.signal_index-cs, z.origin_index-cs, z.direction,
                            z.low, z.high, z.atr_at_signal)
                       for z in raw_children if cs <= z.signal_index < ce]
            groups_c = _group_zones(czs)
            cclose_map = {i: group[0] for i,group in groups_c.items() if len(group)==1}
            next_parent_i = pi+1
            # Replay every 1h close, updating all intervening parent closes first.
            selected = None
            failed = False
            for ci in range(max(0, (state.parent_retest_close-cstart)//HOUR_MS), len(cpart)):
                close_ts = cpart[ci].timestamp+HOUR_MS
                if close_ts > parent_segment_end:
                    break
                next_parent_i, parent_terminal = _replay_parent_closes(
                    state, ppart, pi, close_ts, next_parent_i)
                if parent_terminal:
                    counts[parent_terminal] += 1
                    terminal_reason = parent_terminal
                    break
                if close_ts <= state.parent_retest_close:
                    continue
                if ci not in groups_c:
                    continue
                group = groups_c[ci]
                if len(group) != 1:
                    counts["ambiguous_child"] += 1
                    _event(state,"ambiguous_child_timestamp_discarded",
                           child_signal_close=close_ts,candidate_count=len(group))
                    continue  # all candidates at this close are discarded
                child = group[0]
                counts["child_candidates_considered"] += 1
                candidate_id=_zone_id(symbol,cstart,cpart,child,"child")
                if child.direction != parent.direction:
                    counts["child_rejected_direction"] += 1
                    _event(state,"child_rejected_direction",candidate_zone_id=candidate_id,
                           child_signal_close=close_ts,direction=child.direction)
                    continue
                if child.low < parent.low or child.high > parent.high:
                    counts["child_rejected_outside_parent"] += 1
                    _event(state,"child_rejected_outside_parent",candidate_zone_id=candidate_id,
                           child_signal_close=close_ts,child_low=child.low,child_high=child.high)
                    continue
                if close_ts <= state.parent_retest_close:
                    continue
                selected = (ci, child)
                break
            if terminal_reason:
                busy_until_global=max(busy_until_global,
                    state.events[-1].get("parent_close",state.parent_retest_close))
                events.extend(state.events)
                pi = min(pe-ps, pi + max(1, next_parent_i-pi))
                continue
            if selected is None:
                gap = _segment_after_gap(cseg, ce) or _segment_after_gap(pseg, pe)
                status = "sequence_gap_terminated" if gap else "cutoff_child_censored"
                _event(state, status, reason="1h_gap_before_child" if gap else "train_end_before_child")
                if gap:
                    counts["sequence_gap_terminated"] += 1
                else:
                    counts["cutoff_child_censored"] += 1
                busy_until_global=max(busy_until_global,
                    cpart[-1].timestamp+HOUR_MS if cpart else state.parent_retest_close)
                events.extend(state.events)
                pi = (pe-ps if gap else min(pe-ps, pi+PARENT_LIFE+1))
                continue

            ci, child = selected
            state.child = child
            state.child_id = _zone_id(symbol, cstart, cpart, child, "child")
            child_close = cpart[ci].timestamp+HOUR_MS
            counts["children"] += 1
            _event(state, "child_selected", child_zone_id=state.child_id,
                   child_signal_open=cpart[ci].timestamp,
                   child_signal_close=child_close, child_signal_index=ci,
                   child_low=child.low, child_high=child.high)

            retest_i = None
            for ri in range(ci+1, min(len(cpart), ci+CHILD_LIFE+1)):
                rclose = cpart[ri].timestamp+HOUR_MS
                if rclose > parent_segment_end:
                    break
                next_parent_i, parent_terminal = _replay_parent_closes(
                    state, ppart, pi, rclose, next_parent_i)
                if parent_terminal:
                    terminal_reason = parent_terminal
                    counts[parent_terminal] += 1
                    break
                cb = cpart[ri]
                if invalid(cb, child):
                    failed = True
                    _event(state, "child_first_retest_failed", child_close=rclose,
                           child_index=ri, reason="distal_wick_invalidation")
                    counts["child_failed"] += 1
                    break
                if contact(cb, child):
                    retest_i = ri
                    state.child_retest_index = ri
                    state.child_retest_close = rclose
                    counts["child_retests"] += 1
                    _event(state, "child_retested", child_retest_open=cb.timestamp,
                           child_retest_close=rclose, child_retest_index=ri)
                    break
            if terminal_reason:
                busy_until_global=max(busy_until_global,
                    state.events[-1].get("parent_close",state.parent_retest_close))
                events.extend(state.events)
                pi = min(pe-ps, pi+max(1,next_parent_i-pi))
                continue
            if failed:
                busy_until_global=max(busy_until_global,cpart[ri].timestamp+HOUR_MS)
                events.extend(state.events)
                pi = max(pi+1,_next_parent_after_close(ppart,cpart[ri].timestamp+HOUR_MS))
                continue
            if retest_i is None:
                gap = _segment_after_gap(cseg, ce) or _segment_after_gap(pseg, pe)
                reason = "1h_gap_during_child_retest" if gap else "child_retest_window_unobserved"
                _event(state, "sequence_gap_terminated" if gap else "child_retest_right_censored",
                       reason=reason)
                if gap:
                    counts["sequence_gap_terminated"] += 1
                counts["child_failed"] += 1
                busy_until_global=max(busy_until_global,cpart[-1].timestamp+HOUR_MS)
                events.extend(state.events)
                pi = (pe-ps if gap else min(pe-ps,pi+PARENT_LIFE+1))
                continue

            entry_i = retest_i+1
            if entry_i >= len(cpart) or cpart[entry_i].timestamp >= parent_segment_end:
                gap = _segment_after_gap(cseg, ce) or _segment_after_gap(pseg, pe)
                status = "sequence_gap_terminated" if gap else "cutoff_entry_censored"
                _event(state, status, reason="segment_boundary_before_entry",
                       cutoff_timestamp=cutoff_ms)
                counts["sequence_gap_terminated" if gap else "cutoff_entry_censored"] += 1
                busy_until_global=max(busy_until_global,cpart[-1].timestamp+HOUR_MS)
                events.extend(state.events)
                pi = pe-ps if gap else min(pe-ps,pi+PARENT_LIFE+1)
                continue
            entry_ts = cpart[entry_i].timestamp
            # Parent 4h close ordering precedes this entry open, including ties.
            next_parent_i, parent_terminal = _replay_parent_closes(
                state, ppart, pi, entry_ts, next_parent_i)
            if parent_terminal:
                counts[parent_terminal] += 1
                busy_until_global=max(busy_until_global,
                    state.events[-1].get("parent_close",entry_ts))
                events.extend(state.events)
                pi = min(pe-ps,pi+max(1,next_parent_i-pi))
                continue
            if entry_ts >= cutoff_ms:
                _event(state, "cutoff_entry_censored", entry_timestamp=entry_ts,
                       cutoff_timestamp=cutoff_ms)
                counts["cutoff_entry_censored"] += 1
                busy_until_global=max(busy_until_global,entry_ts)
                events.extend(state.events)
                pi = min(pe-ps,pi+PARENT_LIFE+1)
                continue
            atr = child.atr_at_signal
            stop = child.low-.10*atr if child.direction == "long" else child.high+.10*atr
            entry = cpart[entry_i].open
            if (entry <= stop if child.direction=="long" else entry >= stop):
                _event(state,"entry_skipped_gap_through_stop",entry_timestamp=entry_ts,
                       entry_price=entry,stop=stop)
                counts["entry_skipped"] += 1
                busy_until_global=max(busy_until_global,entry_ts)
                events.extend(state.events)
                pi = max(pi+1,_next_parent_after_close(ppart,entry_ts))
                continue
            risk = abs(entry-stop)
            target = entry+(2*risk if child.direction=="long" else -2*risk)
            setup = Setup(Zone(ci,child.origin_index,child.direction,child.low,
                               child.high,atr),entry_i,entry,stop,target)
            fseg = {ts:ev for ts,ev in funding.items()
                    if entry_ts <= ts <= cpart[-1].timestamp+HOUR_MS+1_000}
            trade = simulate_trade(cpart,setup,funding=fseg,max_holding_bars=HOLD_BARS,
                fee_bps_per_side=4.0,slippage_bps_per_side=2.0,
                bar_duration_ms=HOUR_MS,funding_order_policy="adverse_only")
            if trade is None:
                gap = _segment_after_gap(cseg,ce) or _segment_after_gap(pseg,pe)
                status = "sequence_gap_terminated" if gap else "cutoff_exit_censored"
                _event(state,status,reason="incomplete_48_bar_exit_path",
                    trade_id=stable_id(symbol,cstart,cpart[ci].timestamp,
                                       child.direction,"trade"),
                    direction=child.direction,entry_timestamp=entry_ts,
                    entry_price=entry,stop=stop,target=target,
                    entry_occurred=True,exit_path_complete=False,
                    m2_included=False)
                counts["sequence_gap_terminated" if gap else "cutoff_exit_censored"] += 1
                busy_until_global=max(busy_until_global,cpart[-1].timestamp+HOUR_MS)
            else:
                trades.append(trade)
                counts["trades"] += 1
                counts["funding_unscorable_trades"] += int(trade.net_return is None)
                counts["funding_ambiguous_trades"] += int(trade.ambiguous_funding_events > 0)
                exit_ts = cpart[trade.exit_index].timestamp
                trade_funding = [ev for ts,ev in sorted(fseg.items())
                                  if entry_ts < ts <= exit_ts+HOUR_MS+1_000]
                daily = trade_daily_pnl(cpart,trade,funding=fseg,
                                        bar_duration_ms=HOUR_MS)
                _event(state,"entered",trade_id=stable_id(symbol,cstart,
                    cpart[ci].timestamp,child.direction,"trade"),
                    direction=child.direction,
                    entry_timestamp=entry_ts,entry_price=entry,stop=stop,target=target,
                    exit_timestamp=exit_ts,exit_price=trade.exit_price,
                    exit_reason=trade.exit_reason,gross_return=trade.gross_return,
                    funding_return=trade.funding_return,funding_unscorable=trade.net_return is None,
                    funding_ambiguous_events=trade.ambiguous_funding_events,
                    funding_event_count=len(trade_funding),
                    funding_events=[{"timestamp":ev.timestamp,"rate":ev.rate,
                        "mark_price":ev.mark_price,"coverage_gap":ev.coverage_gap,
                        "used_candle_close_fallback":ev.used_candle_close_fallback}
                        for ev in trade_funding],
                    daily_pnl=daily,
                    risk_per_unit=risk,
                    gross_r=trade.gross_return*entry/risk,
                    net_r=(trade.net_return*entry/risk
                           if trade.net_return is not None else None),
                    net_return=trade.net_return,cost_bps=trade.cost_bps,m2_included=True,
                    m2_target_hit=(trade.exit_reason=="target"))
            events.extend(state.events)
            if trade is not None:
                busy_until_global=max(busy_until_global,cpart[trade.exit_index].timestamp+HOUR_MS)
                pi=max(pi+1,_next_parent_after_close(ppart,busy_until_global))
            else:
                pi=max(pi+1,_next_parent_after_close(ppart,busy_until_global))
        for signal_i, group in grouped_p.items():
            if len(group)>1:
                for candidate in group:
                    events.append({"symbol":symbol,"status":"ambiguous_parent_timestamp_discarded",
                        "parent_zone_id":_zone_id(symbol,pstart,ppart,candidate,"parent"),
                        "parent_signal_open":ppart[signal_i].timestamp,
                        "parent_signal_close":ppart[signal_i].timestamp+FOUR_HOUR_MS,
                        "direction":candidate.direction,"candidate_count":len(group),
                        "segment_start_utc":pstart})
            elif signal_i not in processed_parent_signals:
                candidate=group[0]
                counts["ignored_parent_signals"]+=1
                events.append({"symbol":symbol,"status":"parent_ignored_active_sequence",
                    "parent_zone_id":_zone_id(symbol,pstart,ppart,candidate,"parent"),
                    "parent_signal_open":ppart[signal_i].timestamp,
                    "parent_signal_close":ppart[signal_i].timestamp+FOUR_HOUR_MS,
                    "direction":candidate.direction,"segment_start_utc":pstart})
    return trades, events, counts


def _group_zones(zones: Sequence[Zone]) -> dict[int, list[Zone]]:
    grouped: dict[int, list[Zone]] = {}
    for zone in zones:
        grouped.setdefault(zone.signal_index, []).append(zone)
    return grouped


def run_symbols(barsets):
    """Aggregate in-memory `(symbol, 4h, 1h, funding)` tuples only."""
    barsets = list(barsets)
    if len({row[0] for row in barsets}) != len(barsets):
        raise ValueError("duplicate symbols")
    eligible=[]
    ineligible={}
    for s,p,c,f in barsets:
        try:
            valid=_common_tf_eligible(p,c)
        except (ValueError,TypeError) as exc:
            valid=False
            ineligible[s]=f"{type(exc).__name__}: {exc}"
        if valid:
            eligible.append((s,p,c,f))
        elif s not in ineligible:
            ineligible[s]="missing_or_incomplete_common_timeframe_bars"
    if len(eligible) < 30:
        return {"status": "unscorable", "eligible_symbols": len(eligible),
                "ineligible_symbols": len(barsets)-len(eligible),
                "ineligible_reasons": ineligible,
                "trades": 0, "events": 0, "funnel": {},
                "m2_signal_count": 0, "m2_target_hits": 0,
                "m2_target_first_rate": None, "m2_nonoverlap_count": 0,
                "funding_unscorable_trades": 0}
    trades, events, audit = [], [], {}
    for symbol, p, c, f in eligible:
        t, e, counts = simulate_symbol(symbol, p, c, f)
        trades.extend(t)
        events.extend(e)
        for key, value in counts.items():
            audit[key] = audit.get(key, 0) + value
    hits = sum(t.exit_reason == "target" for t in trades)
    nonoverlap = _nonoverlap_events(events)
    nonoverlap_hits = sum(e["m2_target_hit"] for e in nonoverlap)
    scored = [t.net_return for t in trades if t.net_return is not None]
    tm = trade_metrics(scored)
    trade_events=[e for e in events if e.get("status")=="entered"]
    strict_events=[e for e in trade_events if e.get("net_return") is not None
                   and e.get("funding_ambiguous_events",0)==0]
    strict_tm=trade_metrics([e["net_return"] for e in strict_events])
    all_curve=_portfolio_curve(trade_events,eligible)
    strict_curve=_portfolio_curve(strict_events,eligible)
    by_direction={}
    for direction in ("long","short"):
        rows=[e for e in trade_events if e["direction"]==direction]
        returns=[e["net_return"] for e in rows if e.get("net_return") is not None]
        dmetrics=trade_metrics(returns)
        dnonoverlap=_nonoverlap_events([e for e in events
            if e.get("status")=="entered" and e.get("direction")==direction])
        dhits=sum(e["m2_target_hit"] for e in rows)
        by_direction[direction]={"trades":len(rows),"scoreable_trades":dmetrics.count,
            "m2_target_hits":dhits,"m2_target_first_rate":dhits/len(rows) if rows else None,
            "m2_wilson_lower_95":wilson_lower(dhits,len(rows)),
            "m2_nonoverlap_count":len(dnonoverlap),
            "m2_nonoverlap_target_hits":sum(e["m2_target_hit"] for e in dnonoverlap),
            "expectancy_bps":dmetrics.expectancy_bps,"profit_factor":dmetrics.profit_factor,
            "win_rate":dmetrics.win_rate,"curve":_portfolio_curve(rows,eligible)}
    funding_rows=[ev for e in trade_events for ev in e.get("funding_events",[])]
    return {"status": "unscorable" if any(t.net_return is None for t in trades) else "completed",
            "eligible_symbols": len(eligible), "ineligible_symbols": len(barsets)-len(eligible),
            "ineligible_reasons": ineligible,
            "trades": len(trades), "events": len(events), "funnel": audit,
            "event_rows": events,
            "m2_signal_count": len(trades), "m2_target_hits": hits,
            "m2_target_first_rate": hits/len(trades) if trades else None,
            "m2_wilson_lower_95": wilson_lower(hits, len(trades)),
            "m2_nonoverlap_count": len(nonoverlap),
            "m2_nonoverlap_target_hits": nonoverlap_hits,
            "m2_nonoverlap_target_first_rate": (nonoverlap_hits/len(nonoverlap)
                                                  if nonoverlap else None),
            "m2_nonoverlap_wilson_lower_95": wilson_lower(nonoverlap_hits,len(nonoverlap)),
            "funding_unscorable_trades": sum(t.net_return is None for t in trades),
            "funding_ambiguous_events": sum(t.ambiguous_funding_events for t in trades),
            "funding_ambiguous_trades": sum(t.ambiguous_funding_events>0 for t in trades),
            "funding_events_observed":len(funding_rows),
            "funding_coverage_gaps":sum(bool(e["coverage_gap"]) for e in funding_rows),
            "funding_close_fallbacks":sum(bool(e["used_candle_close_fallback"]) for e in funding_rows),
            "average_funding_return": (sum(t.funding_return for t in trades
                if t.funding_return is not None)/sum(t.funding_return is not None for t in trades)
                if any(t.funding_return is not None for t in trades) else None),
            "gross_expectancy_bps": (sum(e["gross_return"] for e in trade_events)/len(trade_events)*10000
                if trade_events else None),
            "round_trip_cost_bps":12.0,
            "scoreable_trades": tm.count, "win_rate": tm.win_rate,
            "expectancy_bps": tm.expectancy_bps, "profit_factor": tm.profit_factor,
            "wilson_95_lower": tm.wilson_lower_95,
            "strict_scoreable_trades":strict_tm.count,
            "strict_expectancy_bps":strict_tm.expectancy_bps,
            "strict_profit_factor":strict_tm.profit_factor,
            "strict_win_rate":strict_tm.win_rate,
            "curve":all_curve,"strict_curve":strict_curve,
            "by_direction":by_direction}


def _portfolio_curve(events, eligible):
    symbols=[row[0] for row in eligible]
    by_symbol={symbol:{} for symbol in symbols}
    for event in events:
        daily=event.get("daily_pnl")
        if daily is None:
            continue
        target=by_symbol.setdefault(event["symbol"],{})
        for day,value in daily.items():
            day=int(day)
            target[day]=target.get(day,0.0)+value
    first=min((p[0].timestamp//86_400_000 for _,p,_,_ in eligible if p),default=None)
    last=max((c[-1].timestamp//86_400_000 for _,_,c,_ in eligible if c),default=None)
    series=[] if first is None or last is None else [
        sum(by_symbol[s].get(day,0.0) for s in symbols)/len(symbols)
        for day in range(first,last+1)]
    result=curve_metrics(series,365)
    return {"cumulative_return":result.cumulative_return,
            "max_drawdown":result.max_drawdown,
            "annualized_sharpe":result.annualized_sharpe,
            "solvent":result.solvent}


def _common_tf_eligible(parent_bars, child_bars):
    """Require at least one complete 4h interval represented by its four 1h bars."""
    if not parent_bars or not child_bars or any(not b.complete for b in parent_bars+child_bars):
        return False
    _validate(parent_bars)
    _validate(child_bars)
    segments(parent_bars,FOUR_HOUR_MS)
    segments(child_bars,HOUR_MS)
    child_opens={b.timestamp for b in child_bars}
    return any(all(bar.timestamp+k*HOUR_MS in child_opens for k in range(4))
               for bar in parent_bars)


def _nonoverlap_events(events):
    chosen=[]
    by_symbol={}
    for event in events:
        if event.get("status")=="entered" and event.get("m2_included"):
            by_symbol.setdefault(event["symbol"],[]).append(event)
    for symbol,rows in by_symbol.items():
        end=-1
        for row in sorted(rows,key=lambda e:(e["exit_timestamp"],e["entry_timestamp"],e["trade_id"])):
            if row["entry_timestamp"] >= end:
                chosen.append(row)
                end=row["exit_timestamp"]+HOUR_MS
    return chosen


def _expected_symbols(path: Path = UNIVERSE_PATH) -> frozenset[str]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["symbol"]:
            raise ValueError("frozen universe must have only a symbol column")
        symbols = [r["symbol"].strip() for r in reader]
    if not symbols or any(not s for s in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("frozen universe has empty or duplicate symbols")
    return frozenset(symbols)


def _check_symbols(rows, expected: frozenset[str], timeframe: str) -> None:
    names = [r[0] for r in rows]
    if len(names) != len(set(names)) or set(names) != set(expected):
        raise ValueError(f"{timeframe} TRAIN symbols differ from frozen universe")


def _load_train_barsets(*, loader=None, universe_path: Path = UNIVERSE_PATH,
                       data_dir=None):
    """TRAIN-only two-timeframe adapter. Calling it reads market files."""
    if loader is None:
        import data_access as loader
    expected = _expected_symbols(universe_path)
    loaded = {}
    for timeframe in ("4h", "1h"):
        kwargs = {"timeframe": timeframe}
        if data_dir is not None:
            kwargs["data_dir"] = data_dir
        rows = []
        for row in loader.iter_train_bars(**kwargs):
            rows.append(row)
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak_bytes=peak if sys.platform=="darwin" else peak*1024
            if peak_bytes>3*1024**3:
                raise MemoryError(f"peak RSS exceeded 3 GiB: {peak_bytes} bytes")
        _check_symbols(rows, expected, timeframe)
        loaded[timeframe] = {s: (bars, funding) for s, bars, funding in rows}
    result = []
    for symbol in sorted(expected):
        p_all, pf = loaded["4h"][symbol]
        c_all, cf = loaded["1h"][symbol]
        # Keep all TRAIN rows in the fingerprint. Eligibility validation below
        # excludes malformed/incomplete symbols without laundering their input.
        p = list(p_all)
        c = list(c_all)
        merged = dict(pf)
        for ts, event in cf.items():
            if ts in merged and merged[ts] != event:
                raise ValueError(f"{symbol} funding inputs differ between timeframes")
            merged[ts] = event
        result.append((symbol, p, c, merged))
    return result


def _fingerprint(barsets, prereg_sha: str, universe_sha: str) -> str:
    digest = hashlib.sha256()
    def add(record):
        digest.update(json.dumps(record, sort_keys=True, separators=(",",":"),
                                 allow_nan=False).encode()+b"\n")
    add(["R10-train-input-v1", prereg_sha, universe_sha])
    for symbol,p,c,funding in sorted(barsets,key=lambda row:row[0]):
        add(["symbol",symbol])
        for timeframe,bars in (("4h",p),("1h",c)):
            add(["timeframe",timeframe])
            for b in bars:
                add([b.timestamp,b.open,b.high,b.low,b.close,b.volume,b.complete])
        for ts,event in sorted(funding.items()):
            if ts != event.timestamp:
                raise ValueError("funding key differs from event timestamp")
            add(["funding",ts,event.rate,event.mark_price,event.coverage_gap,
                 event.used_candle_close_fallback])
    return digest.hexdigest()


def _code_sha() -> str:
    digest=hashlib.sha256()
    for path in (HERE/"search_crypto_r10.py",HERE/"crypto.py",
                 HERE/"search_crypto.py",HERE/"data_access.py",
                 HERE/"metrics.py",UNIVERSE_PATH,PREREG_PATH):
        digest.update(path.name.encode()+b"\0"+path.read_bytes())
    return digest.hexdigest()


def _append_trial(result, fingerprint, event_path, code_sha, prereg_sha):
    config_json=json.dumps(CONFIG,sort_keys=True,separators=(",",":"))
    grid=hashlib.sha256(config_json.encode()).hexdigest()
    row={"trial_id":f"R10-crypto-{uuid.uuid4().hex}","round":"R10-coin",
         "market_group":"crypto","utc_timestamp":datetime.now(timezone.utc).isoformat(),
         "definition":config_json,"parameter_grid_hash":grid,"code_sha256":code_sha,
         "train_period":"4h bar close <=2023-11-06T16:00:00Z",
         "metric":json.dumps(_json_clean({**result,"train_input_fingerprint":fingerprint,
             "prereg_sha256":prereg_sha,"event_file":str(event_path)}),
             sort_keys=True,separators=(",",":")),"rank":"",
         "notes":f"status={result['status']}; train_input_fingerprint={fingerprint}"}
    exists=TRIAL_CSV_PATH.exists() and TRIAL_CSV_PATH.stat().st_size>0
    if exists:
        with TRIAL_CSV_PATH.open(newline="",encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != TRIAL_FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    with TRIAL_CSV_PATH.open("a",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=TRIAL_FIELDS)
        if not exists: writer.writeheader()
        writer.writerow(row)


def _run_train_once(*, data_dir=None, cache_dir=None, loader=None):
    """Execute explicit TRAIN only; never loads TEST/OOS or writes cache in repo."""
    prereg_sha=hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    universe_sha=hashlib.sha256(UNIVERSE_PATH.read_bytes()).hexdigest()
    code_sha=_code_sha()
    try:
        barsets=_load_train_barsets(loader=loader,data_dir=data_dir)
    except Exception as exc:
        _append_trial({"status":"failed","detail":f"TRAIN load failed: {type(exc).__name__}: {exc}"},
                      "unavailable","",code_sha,prereg_sha)
        raise
    if (_code_sha()!=code_sha or
            hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()!=prereg_sha):
        raise RuntimeError("R10 source or PREREG changed while TRAIN data was loading")
    try:
        fingerprint=_fingerprint(barsets,prereg_sha,universe_sha)
    except Exception as exc:
        _append_trial({"status":"failed","detail":f"fingerprint failed: {type(exc).__name__}: {exc}"},
                      "unavailable","",code_sha,prereg_sha)
        raise
    config_hash=hashlib.sha256(json.dumps(CONFIG,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    # R10's own previous identical completed run must not be silently reused.
    if TRIAL_CSV_PATH.exists():
        with TRIAL_CSV_PATH.open(newline="",encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if row.get("round")!="R10-coin" or row.get("code_sha256")!=code_sha or row.get("parameter_grid_hash")!=config_hash:
                    continue
                try: metric=json.loads(row["metric"])
                except (ValueError,KeyError,TypeError): continue
                if metric.get("train_input_fingerprint")==fingerprint and metric.get("prereg_sha256")==prereg_sha and metric.get("status") in {"completed","unscorable"}:
                    raise RuntimeError("matching R10 code/config/TRAIN/prereg fingerprint already recorded")
    root=Path(cache_dir or os.environ.get("TRADING_DATA_DIR",Path.home()/"CODE/trading_data"))
    root=root.expanduser().resolve()
    if root==HERE or HERE in root.parents:
        raise ValueError("event cache must be outside the repository")
    output=root/"cache/orderblock"
    output.mkdir(parents=True,exist_ok=True)
    event_path=output/f"r10-events-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}.jsonl"
    try:
        result=run_symbols(barsets)
        with event_path.open("x",encoding="utf-8") as stream:
            for event in result.pop("event_rows",[]):
                stream.write(json.dumps(_json_clean(event),sort_keys=True,allow_nan=False)+"\n")
            stream.flush(); os.fsync(stream.fileno())
        _append_trial(result,fingerprint,event_path,code_sha,prereg_sha)
    except Exception as exc:
        _append_trial({"status":"failed","detail":f"{type(exc).__name__}: {exc}"},
                      fingerprint,event_path,code_sha,prereg_sha)
        raise
    return {**result,"event_file":str(event_path),
            "train_input_fingerprint":fingerprint}


def _json_clean(value):
    if isinstance(value,float) and not math.isfinite(value):
        return None
    if isinstance(value,dict):
        return {key:_json_clean(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):
        return [_json_clean(item) for item in value]
    return value


def run_train(*, data_dir=None, cache_dir=None, loader=None):
    """Use the shared heavy-run lock; a running R4 job is never interrupted."""
    from resource_guard import heavy_task
    with heavy_task("B-R10-coin"):
        return _run_train_once(data_dir=data_dir,cache_dir=cache_dir,loader=loader)


def main(argv=None):
    parser=argparse.ArgumentParser(description="R10 TRAIN-only hierarchical OB candidate")
    parser.add_argument("--data-dir",default=None)
    parser.add_argument("--cache-dir",default=None)
    args=parser.parse_args(argv)
    result=run_train(data_dir=args.data_dir,cache_dir=args.cache_dir)
    print(json.dumps(_json_clean(result),sort_keys=True,allow_nan=False),flush=True)


if __name__=="__main__":
    main()
