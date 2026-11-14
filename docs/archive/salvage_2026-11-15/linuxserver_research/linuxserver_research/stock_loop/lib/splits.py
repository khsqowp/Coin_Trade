"""Dev vs FINAL HOLDOUT (last 24 months, 2024-11-12..2026-11-12).

Holdout bars must never be read during Stage 1-2. Any access path that could return
holdout bars calls guard_dev()/holdout_view(); both raise HoldoutLockedError until an
explicit unlock_holdout(reason) call, which appends a timestamped line to results/holdout_unlock.log.
"""
from __future__ import annotations
import datetime as _dt
from pathlib import Path
import numpy as np
import pandas as pd

DATA_END = pd.Timestamp("2026-11-12")
HOLDOUT_START = pd.Timestamp("2024-11-12")      # aligned with US session spec (2024-11-12..); conservative
UNLOCK_LOG = Path(__file__).resolve().parent.parent / "results" / "holdout_unlock.log"
SEC = "seconds"
_state = {"unlocked": False}


class HoldoutLockedError(RuntimeError):
    pass


def is_unlocked() -> bool:
    return _state["unlocked"]


def unlock_holdout(reason: str, log_path: Path | None = None) -> str:
    """Explicitly unlock the holdout (Stage 3 only). Logs a timestamp; returns the log line."""
    if not reason or not reason.strip():
        raise ValueError("unlock_holdout needs a reason")
    line = f"{_dt.datetime.now().isoformat(timespec=SEC)} UNLOCK holdout (>= {HOLDOUT_START.date()}) reason={reason.strip()}"
    p = Path(log_path) if log_path else UNLOCK_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(line + "\n")
    _state["unlocked"] = True
    return line


def relock_holdout() -> None:  # for tests
    _state["unlocked"] = False


def guard_dev(dates, what: str = "data") -> None:
    """Raise if any date falls in the holdout while locked."""
    d = pd.DatetimeIndex(np.asarray(dates).ravel()) if len(np.asarray(dates)) else pd.DatetimeIndex([])
    if len(d) and not _state["unlocked"] and d.max() >= HOLDOUT_START:
        raise HoldoutLockedError(f"{what}: holdout bars (>= {HOLDOUT_START.date()}) read while locked; call unlock_holdout(reason) in Stage 3 only")


def dev_view(df):
    """Return only development rows (index < HOLDOUT_START)."""
    return df[df.index < HOLDOUT_START]


def holdout_view(df):
    """Return holdout rows; raises unless unlocked."""
    if not _state["unlocked"]:
        raise HoldoutLockedError("holdout is locked; call unlock_holdout(reason)")
    return df[df.index >= HOLDOUT_START]


def dev_halves(dates_dev) -> pd.Timestamp:
    """Midpoint date of the dev span, to split into two halves for sign-consistency checks."""
    d = pd.DatetimeIndex(dates_dev)
    return d[len(d) // 2]
