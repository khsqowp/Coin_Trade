"""Single preregistered R17 follow-through entry diagnostic."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import search_crypto as common
import search_crypto_r14 as r14
from crypto import Bar, Setup, Trade, Zone, simulate_trade
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "PREREG_R17_RECLAIM_FOLLOWTHROUGH.md"
MASTER_PREREG_PATH = HERE / "PREREG.md"
UNIVERSE_PATH = HERE / "universe" / "CRYPTO_35.csv"
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_PREREG_SHA = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()
ROUND = "R17-coin"
MINIMUM_SYMBOLS = 32
CONFIG = {
    "experiment": "R17-OB-MIDPOINT-RECLAIM-NEXT-BAR-FOLLOWTHROUGH",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "bos_origin", "directions": ["long", "short"],
    "confirmation": "first_touch_midpoint_then_next_close_break_touch_extreme",
    "entry": "bar_after_followthrough_open", "deadline_bars": 24,
    "distal_stop_buffer_atr": 0.10, "reward_r": 0.50,
    "max_holding_bars": 24, "round_trip_cost_bps": 12,
    "funding_order_policy": "adverse_only",
}


def _setup(zone: Zone, touch: Bar, follow: Bar, entry: Bar,
           entry_index: int) -> tuple[Setup | None, str]:
    midpoint = (zone.low + zone.high) / 2
    if zone.direction == "long":
        if touch.close <= midpoint or touch.low <= zone.low:
            return None, "touch_failed"
        if follow.close <= touch.high:
            return None, "followthrough_failed"
        if follow.low <= zone.low:
            return None, "followthrough_invalidated"
        stop = zone.low - 0.10 * zone.atr_at_signal
        if entry.open <= zone.low:
            return None, "entry_gapped_past_zone"
        risk = entry.open - stop
        target = entry.open + 0.50 * risk
    else:
        if touch.close >= midpoint or touch.high >= zone.high:
            return None, "touch_failed"
        if follow.close >= touch.low:
            return None, "followthrough_failed"
        if follow.high >= zone.high:
            return None, "followthrough_invalidated"
        stop = zone.high + 0.10 * zone.atr_at_signal
        if entry.open >= zone.high:
            return None, "entry_gapped_past_zone"
        risk = stop - entry.open
        target = entry.open - 0.50 * risk
    if risk <= 0:
        return None, "nonpositive_risk"
    return Setup(zone, entry_index, entry.open, stop, target), "setup"


def _apply_symbol_gate(result: dict) -> dict:
    if result["symbols"] < MINIMUM_SYMBOLS:
        result["status"] = "unscorable"
    return result


def _simulate_segment(bars: list[Bar], funding: dict[int, FundingEvent],
                      zones_by_index: dict[int, Zone]):
    trades: list[Trade] = []
    audit = {key: 0 for key in (
        "zones", "first_touches", "midpoint_failures", "invalidated_zones",
        "expired_zones", "invalid_setups", "right_censored_setups",
        "superseding_zones_dropped", "funding_unscorable_trades",
        "followthrough_failures", "followthrough_invalidated",
        "followthrough_confirmed",
    )}
    audit["zones"] = len(zones_by_index)
    active: Zone | None = None
    i = 0
    while i < len(bars):
        new_zone = zones_by_index.get(i)
        if active is None:
            active = new_zone
            i += 1
            continue
        if new_zone is not None and new_zone.signal_index != active.signal_index:
            audit["superseding_zones_dropped"] += 1
        age = i - active.signal_index
        if age > 24:
            audit["expired_zones"] += 1
            active = None
            continue
        if age == 0:
            i += 1
            continue
        touch = bars[i]
        invalid = (touch.low <= active.low if active.direction == "long"
                   else touch.high >= active.high)
        overlaps = touch.low <= active.high and touch.high >= active.low
        if invalid:
            audit["invalidated_zones"] += 1
            active = None
            i += 1
            continue
        if not overlaps:
            i += 1
            continue
        audit["first_touches"] += 1
        midpoint = (active.low + active.high) / 2
        reclaimed = (touch.close > midpoint if active.direction == "long"
                     else touch.close < midpoint)
        if not reclaimed:
            audit["midpoint_failures"] += 1
            active = None
            i += 1
            continue
        if i + 1 >= len(bars):
            audit["right_censored_setups"] += 1
            break
        follow = bars[i + 1]
        follow_close_ok = (follow.close > touch.high if active.direction == "long"
                           else follow.close < touch.low)
        follow_invalid = (follow.low <= active.low if active.direction == "long"
                          else follow.high >= active.high)
        if not follow_close_ok or follow_invalid:
            audit["followthrough_invalidated" if follow_invalid
                  else "followthrough_failures"] += 1
            active = None
            i += 1
            continue
        if i + 2 >= len(bars):
            audit["right_censored_setups"] += 1
            break
        entry = bars[i + 2]
        setup, reason = _setup(active, touch, follow, entry, i + 2)
        if setup is None:
            if reason == "followthrough_failed":
                audit["followthrough_failures"] += 1
            elif reason == "followthrough_invalidated":
                audit["followthrough_invalidated"] += 1
            elif reason == "touch_failed":
                audit["invalidated_zones"] += 1
            else:
                audit["invalid_setups"] += 1
            active = None
            i += 1
            continue
        audit["followthrough_confirmed"] += 1
        trade = simulate_trade(
            bars, setup, funding=funding, max_holding_bars=24,
            fee_bps_per_side=4.0, slippage_bps_per_side=2.0,
            bar_duration_ms=3_600_000, funding_order_policy="adverse_only",
        )
        if trade is None:
            audit["right_censored_setups"] += 1
            break
        if trade.net_return is None:
            audit["funding_unscorable_trades"] += 1
        trades.append(trade)
        active = None
        i = max(i + 1, trade.exit_index)
    return trades, audit


def _code_hash() -> str:
    names = (
        "crypto.py", "search_crypto.py", "search_crypto_r14.py",
        "search_crypto_r17_reclaim_followthrough.py", "data_access.py",
        "metrics.py", "resource_guard.py", "PREREG.md",
        "PREREG_R17_RECLAIM_FOLLOWTHROUGH.md",
        "tests/test_search_crypto_r17_reclaim_followthrough.py",
        "universe/CRYPTO_35.csv",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _ledger_rows() -> int:
    old_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            return sum(1 for _ in csv.DictReader(stream))
    finally:
        csv.field_size_limit(old_limit)


def _already_recorded(grid_sha: str, code_sha: str, fingerprint: str,
                      prereg_sha: str) -> bool:
    if not common.CSV_PATH.exists():
        return False
    old_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if (row["round"] != ROUND or row["parameter_grid_hash"] != grid_sha
                        or row["code_sha256"] != code_sha):
                    continue
                metric = json.loads(row["metric"])
                if (metric.get("train_input_fingerprint") == fingerprint
                        and metric.get("prereg_sha256") == prereg_sha):
                    return True
    finally:
        csv.field_size_limit(old_limit)
    return False


def _append(result: dict, denominator: int, grid_sha: str, code_sha: str,
            prereg_sha: str, fingerprint: str) -> None:
    exists = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if exists:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    record = {
        "trial_id": f"R17-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(CONFIG, sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps({**result, "train_input_fingerprint": fingerprint,
                              "bonferroni_denominator": denominator,
                              "prereg_sha256": prereg_sha,
                              "master_prereg_sha256": _MASTER_PREREG_SHA},
                             sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "R17 single preregistered TRAIN diagnostic; not a G decision",
    }
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(record)


def run() -> int:
    import data_access

    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    master_sha = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()
    if prereg_sha != _PREREG_SHA or master_sha != _MASTER_PREREG_SHA:
        raise RuntimeError("R17 prereg changed after module import")
    grid_sha = hashlib.sha256(json.dumps(
        [CONFIG], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    code_sha = _code_hash()
    denominator = _ledger_rows() + 1
    with heavy_task("R17"):
        bars_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
        bars_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
        fingerprint = common._train_input_fingerprint(
            "R17-4h-zones-1h-midpoint-followthrough",
            [(f"{symbol}:1h", bars, funding, excluded)
             for symbol, bars, funding, excluded in bars_1h]
            + [(f"{symbol}:4h", bars, {}, excluded)
               for symbol, bars, _funding, excluded in bars_4h],
        )
        if _already_recorded(grid_sha, code_sha, fingerprint, prereg_sha):
            raise RuntimeError("identical R17 input/config already recorded")
        original = r14._simulate_segment
        r14._simulate_segment = _simulate_segment
        try:
            result = r14._trial(bars_1h, bars_4h)
        finally:
            r14._simulate_segment = original
        result["detail"] = (
            "R17 requires next-1h close follow-through after first midpoint reclaim; "
            "entry at following open; TRAIN only; not a G decision"
        )
        _apply_symbol_gate(result)
        if (_code_hash() != code_sha
                or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != prereg_sha
                or hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest() != master_sha):
            raise RuntimeError("R17 source or prereg changed during run")
        _append(result, denominator, grid_sha, code_sha, prereg_sha, fingerprint)
    print(f"R17 completed status={result['status']} trades={result['trades']} "
          f"M2={result['m2_target_first_rate']} N={denominator}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
