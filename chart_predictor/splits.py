"""Deterministic replay anchors and sealed-period access guard."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from .collector import DB_PATH
from .resample import resample_frame
from .store import connect_trials, record_trial

REGISTRY = Path(__file__).parent / "data" / "sealed_registry.json"


def freeze_registry(path=REGISTRY, freeze_timestamp=None):
    """Create a fixed sealed-period boundary once; never silently move it."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = freeze_timestamp or datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps({"freeze_timestamp": stamp}, indent=2))
    return json.loads(path.read_text())


def symbol_split(symbol):
    """Assign symbols reproducibly to 70 percent dev or 30 percent held-out."""
    bucket = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16) % 100
    return "dev" if bucket < 70 else "heldout"


def build_anchors(symbol, timeframe, db_path=DB_PATH, registry_path=REGISTRY, trial_path=None):
    """Return timestamped causal feature frames, rejecting/logging sealed anchors."""
    import sqlite3
    registry = freeze_registry(registry_path)
    freeze_ms = int(pd.Timestamp(registry["freeze_timestamp"]).timestamp() * 1000)
    db = sqlite3.connect(db_path)
    raw = pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles "
                            "WHERE symbol=? AND t_open_ms<? ORDER BY t_open_ms",
                            db, params=(symbol, freeze_ms))
    db.close()
    width = {"1m": 60_000, "5m": 300_000, "30m": 1_800_000, "60m": 3_600_000}[timeframe]
    frame = raw if timeframe == "1m" else resample_frame(raw, timeframe, now_ms=freeze_ms)
    frame = frame[frame.t_open_ms + width <= freeze_ms].reset_index(drop=True)
    frame["anchor_time_ms"] = frame.t_open_ms + width
    horizon_ms = {"1m": 1_200_000, "5m": 6_000_000, "30m": 36_000_000, "60m": 72_000_000}[timeframe]
    anchors = frame.iloc[::max(1, (horizon_ms + width - 1) // width)].reset_index(drop=True)
    return _guard(anchors, symbol, timeframe, registry_path, trial_path)


def _guard(anchors, symbol, timeframe, registry_path, trial_path):
    """Apply freeze boundary and persist evidence of any sealed access."""
    registry = freeze_registry(registry_path)
    freeze_ms = int(pd.Timestamp(registry["freeze_timestamp"]).timestamp() * 1000)
    sealed = anchors[anchors.anchor_time_ms > freeze_ms]
    if len(sealed):
        db = connect_trials(trial_path)
        record_trial(db, datetime.now(timezone.utc).isoformat(), "system", "sealed-guard", "",
                     "sealed_access", f"blocked {symbol} {timeframe} post-freeze anchor", len(sealed))
        db.close()
        raise PermissionError("sealed anchor access is blocked")
    return anchors


def split_anchors(anchors, split):
    """Assign earliest 60 percent to development and remaining 40 to validation."""
    if split not in {"dev", "validation"}:
        raise ValueError("split must be dev or validation")
    ordered = anchors.sort_values("anchor_time_ms").reset_index(drop=True)
    cut = int(len(ordered) * .6)
    return ordered.iloc[:cut] if split == "dev" else ordered.iloc[cut:]
