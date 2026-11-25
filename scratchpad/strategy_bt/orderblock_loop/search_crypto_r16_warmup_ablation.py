"""Single preregistered R16 EMA-warmup ablation for causal attribution."""

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
import search_crypto_r15 as r15
from resource_guard import heavy_task

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "PREREG_R16_EMA_WARMUP_ABLATION.md"
MASTER_PREREG_PATH = HERE / "PREREG.md"
_PREREG_SHA = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
_MASTER_PREREG_SHA = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()
ROUND = "R16-coin"
CONFIG = {
    "experiment": "R16-OB-EMA-WARMUP-ONLY-ABLATION",
    "zone_timeframe": "4h", "confirmation_timeframe": "1h",
    "definition": "bos_origin", "filter": "ema50_200_computable_only_no_direction_match",
    "minimum_symbols": r14.MINIMUM_SYMBOLS,
    "deadline_bars": r14.DEADLINE,
    "confirmation": "first_touch_close_beyond_zone_midpoint",
    "distal_sweep_required": False, "reward_r": r14.REWARD_R,
    "stop_buffer_atr": r14.STOP_BUFFER_ATR,
    "max_holding_bars": r14.MAX_HOLDING_BARS,
    "funding_order_policy": r14.FUNDING_ORDER_POLICY,
}


def _warmup_only_zone_builder(stats):
    original = r14.r4_zones

    def build(bars, definition):
        zones = original(bars, definition)
        states = r15._ema_regimes(bars)
        stats["raw"] += len(zones)
        kept = []
        for zone in zones:
            if states[zone.signal_index] is None:
                stats["warmup_excluded"] += 1
            else:
                kept.append(zone)
        stats["kept"] += len(kept)
        return kept

    return original, build


def _code_hash():
    names = (
        "crypto.py", "search_crypto.py", "search_crypto_r14.py",
        "search_crypto_r15.py", "search_crypto_r16_warmup_ablation.py",
        "data_access.py", "metrics.py", "resource_guard.py", "PREREG.md",
        "PREREG_R15_LOCAL_4H_TREND_ALIGNMENT.md",
        "PREREG_R16_EMA_WARMUP_ABLATION.md", "universe/CRYPTO_35.csv",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _grid_hash():
    encoded = json.dumps([CONFIG], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _already_recorded(grid_hash, code_sha, fingerprint, prereg_sha):
    csv.field_size_limit(sys.maxsize)
    if not common.CSV_PATH.exists():
        return False
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (row["round"] != ROUND or row["parameter_grid_hash"] != grid_hash
                    or row["code_sha256"] != code_sha):
                continue
            try:
                metric = json.loads(row["metric"])
            except (json.JSONDecodeError, TypeError):
                continue
            if (metric.get("train_input_fingerprint") == fingerprint
                    and metric.get("prereg_sha256") == prereg_sha):
                return True
    return False


def _append(result, fingerprint, denominator, grid_hash, code_sha, prereg_sha):
    config_json = json.dumps(CONFIG, sort_keys=True, separators=(",", ":"))
    metric = {
        **result, "train_input_fingerprint": fingerprint,
        "bonferroni_denominator": denominator,
        "prereg_sha256": prereg_sha,
        "master_prereg_sha256": _MASTER_PREREG_SHA,
    }
    record = {
        "trial_id": f"R16-crypto-{uuid.uuid4().hex}", "round": ROUND,
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json, "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha,
        "train_period": "4h/1h bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": "R16 single preregistered TRAIN ablation; not a G decision",
    }
    exists = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if exists:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(record)


def run():
    import data_access

    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    master_prereg_sha = hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest()
    if prereg_sha != _PREREG_SHA or master_prereg_sha != _MASTER_PREREG_SHA:
        raise RuntimeError("R16 prereg changed after import")
    grid_hash = _grid_hash()
    code_sha = _code_hash()
    denominator = r14._ledger_row_count(common.CSV_PATH) + 1
    with heavy_task("R16"):
        bars_1h = r14._load_barsets(data_access.iter_train_bars, "1h")
        bars_4h = r14._load_barsets(data_access.iter_train_bars, "4h")
        fingerprint = common._train_input_fingerprint(
            "R16-4h-ema-availability-only+1h-confirmation",
            [(f"{symbol}:1h", bars, funding, excluded)
             for symbol, bars, funding, excluded in bars_1h]
            + [(f"{symbol}:4h", bars, {}, excluded)
               for symbol, bars, _funding, excluded in bars_4h],
        )
        if _already_recorded(grid_hash, code_sha, fingerprint, prereg_sha):
            raise RuntimeError("identical R16 ablation already recorded; refusing duplicate run")
        stats = {"raw": 0, "kept": 0, "warmup_excluded": 0}
        original, filtered = _warmup_only_zone_builder(stats)
        r14.r4_zones = filtered
        try:
            result = r14._trial(bars_1h, bars_4h)
        finally:
            r14.r4_zones = original
        result["detail"] = "EMA computability-only ablation; no direction filter; TRAIN only; not a G decision"
        result.update({
            "warmup_filter_raw_zones": stats["raw"],
            "warmup_filter_kept_zones": stats["kept"],
            "warmup_filter_excluded_zones": stats["warmup_excluded"],
        })
        if (_code_hash() != code_sha
                or hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != prereg_sha
                or hashlib.sha256(MASTER_PREREG_PATH.read_bytes()).hexdigest() != master_prereg_sha):
            raise RuntimeError("R16 code/prereg changed during the run")
        _append(result, fingerprint, denominator, grid_hash, code_sha, prereg_sha)
    print(f"R16 completed status={result['status']} trades={result['trades']} "
          f"M2={result['m2_target_first_rate']} kept_zones={stats['kept']} N={denominator}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
