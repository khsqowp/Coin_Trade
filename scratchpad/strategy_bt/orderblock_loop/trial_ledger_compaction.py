"""Pure helpers for compacting trial ledger identifier lists."""

from hashlib import sha256
from typing import Iterable


def compact_id_list(ids: Iterable[str]) -> dict[str, int | str]:
    """Return the input count and SHA-256 of its sorted newline-joined IDs."""
    ordered_ids = sorted(ids)
    payload = "\n".join(ordered_ids).encode("utf-8")
    return {"count": len(ordered_ids), "sha256": sha256(payload).hexdigest()}
