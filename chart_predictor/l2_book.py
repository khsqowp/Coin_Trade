"""Sequence-checked local book reconstruction for public USDⓈ-M depth data.

This module has no network, persistence, strategy, or order-routing behavior.
Callers must discard a book after any exception and resynchronize from a new
snapshot plus buffered depth events.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping


class SequenceGap(RuntimeError):
    """Raised when a forward depth update is not contiguous with local state."""


def _update_id(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _levels(rows: object, field: str) -> dict[float, float]:
    if not isinstance(rows, (list, tuple)):
        raise ValueError(f"{field} must be a list of price/quantity pairs")
    result: dict[float, float] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError(f"{field} contains a malformed price/quantity pair")
        try:
            price, quantity = float(row[0]), float(row[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} contains a non-numeric level") from exc
        if not math.isfinite(price) or price <= 0 or not math.isfinite(quantity) or quantity < 0:
            raise ValueError(f"{field} contains an invalid price or quantity")
        result[price] = quantity
    return result


def _event_ids(event: Mapping[str, object]) -> tuple[int, int, int]:
    first = _update_id(event.get("U"), "U")
    final = _update_id(event.get("u"), "u")
    previous = _update_id(event.get("pu"), "pu")
    if first > final:
        raise ValueError("depth event U must not exceed u")
    return first, final, previous


def _apply_levels(book: dict[float, float], rows: object, field: str) -> None:
    for price, quantity in _levels(rows, field).items():
        if quantity == 0:
            book.pop(price, None)
        else:
            book[price] = quantity


class LocalBook:
    """A book that is usable only after snapshot/diff sequence synchronization."""

    def __init__(self) -> None:
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}
        self.last_update_id: int | None = None
        self.valid = False
        self.invalidate_reason: str | None = "not_initialized"

    def invalidate(self, reason: str) -> None:
        """Fail closed: erase levels so invalid data cannot be consumed downstream."""
        self.bids.clear()
        self.asks.clear()
        self.last_update_id = None
        self.valid = False
        self.invalidate_reason = reason

    def install_snapshot(
        self,
        snapshot: Mapping[str, object],
        buffered_events: Iterable[Mapping[str, object]],
    ) -> bool:
        """Install snapshot and replay buffered events beginning at its bridge.

        Returns false if the buffer contains no event spanning the snapshot ID.
        A sequence discontinuity invalidates state and raises ``SequenceGap``.
        """
        self.invalidate("snapshot_not_bridged")
        try:
            snapshot_id = _update_id(snapshot.get("lastUpdateId"), "lastUpdateId")
            bids = _levels(snapshot.get("bids"), "bids")
            asks = _levels(snapshot.get("asks"), "asks")
            buffered = list(buffered_events)
            parsed = [(_event_ids(event), event) for event in buffered]
        except (AttributeError, TypeError, ValueError) as exc:
            self.invalidate("invalid_snapshot_or_buffer")
            raise ValueError("invalid snapshot or buffered depth event") from exc

        bridge_index = next(
            (index for index, ((first, final, _), _) in enumerate(parsed)
             if final >= snapshot_id and first <= snapshot_id),
            None,
        )
        if bridge_index is None:
            self.invalidate("snapshot_bridge_missing")
            return False

        if any(final >= snapshot_id for (_, final, _), _ in parsed[:bridge_index]):
            self.invalidate("buffer_reordered_before_snapshot_bridge")
            raise SequenceGap("non-stale buffered depth event arrived before snapshot bridge")

        candidate_bids, candidate_asks = bids, asks
        candidate_last_id = snapshot_id
        try:
            (first, final, _), bridge = parsed[bridge_index]
            if first > snapshot_id or final < snapshot_id:
                raise SequenceGap("first buffered event does not bridge the snapshot")
            _apply_levels(candidate_bids, bridge.get("b"), "b")
            _apply_levels(candidate_asks, bridge.get("a"), "a")
            candidate_last_id = final
            for (event_first, event_final, previous), event in parsed[bridge_index + 1:]:
                if previous != candidate_last_id:
                    raise SequenceGap(
                        f"buffered sequence discontinuity: pu={previous}, expected={candidate_last_id}"
                    )
                if event_final <= candidate_last_id or event_first > event_final:
                    raise SequenceGap("buffered depth event did not advance the sequence")
                _apply_levels(candidate_bids, event.get("b"), "b")
                _apply_levels(candidate_asks, event.get("a"), "a")
                candidate_last_id = event_final
        except (SequenceGap, ValueError):
            self.invalidate("buffer_sequence_invalid")
            raise
        self.bids, self.asks = candidate_bids, candidate_asks
        self.last_update_id = candidate_last_id
        self.valid = True
        self.invalidate_reason = None
        return self.valid

    def apply_diff(self, event: Mapping[str, object]) -> str:
        """Apply one next delta, invalidating state on duplicates or sequence gaps."""
        if not self.valid or self.last_update_id is None:
            raise RuntimeError("cannot apply depth delta to an invalid book")
        try:
            (first, final, previous) = _event_ids(event)
            bids = _levels(event.get("b"), "b")
            asks = _levels(event.get("a"), "a")
        except (AttributeError, TypeError, ValueError) as exc:
            self.invalidate("invalid_depth_event")
            raise ValueError("invalid depth event") from exc

        if previous != self.last_update_id:
            expected = self.last_update_id
            self.invalidate("sequence_gap")
            raise SequenceGap(f"depth sequence discontinuity: pu={previous}, expected={expected}")
        if final <= self.last_update_id or first > final:
            self.invalidate("invalid_update_range")
            raise SequenceGap("depth event did not advance the sequence")

        _apply_levels(self.bids, event.get("b"), "b")
        _apply_levels(self.asks, event.get("a"), "a")
        self.last_update_id = final
        return "applied"
