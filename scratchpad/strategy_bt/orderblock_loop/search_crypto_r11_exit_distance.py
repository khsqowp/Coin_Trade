"""Preregistered R11 crypto order-block target-distance TRAIN study."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import search_crypto as common
from search_crypto_r4 import _load_timeframe, _trial

ROUND = "R11-exit-coin"
TIMEFRAME = "4h"
DEFINITIONS = ("displacement", "bos_origin", "volume_displacement")
DIRECTIONS = ("long", "short")
DEADLINES = (24, 48)
TARGET_R = (0.25, 0.50, 0.75, 1.00)
MINIMUM_SYMBOLS = 30
FUNDING_ORDER_POLICY = "adverse_only"
PREREG_PATH = HERE / "PREREG_R11_TARGET_DISTANCE.md"
PREREG_SHA256 = "3c82340065a13613dae94134a42526fb311fe03570185eaea8c50aed116d35c7"

CONFIGS = tuple({
    "definition": definition,
    "timeframe": TIMEFRAME,
    "direction": direction,
    "deadline": deadline,
    "reward_r": target_r,
    "minimum_symbols": MINIMUM_SYMBOLS,
    "funding_order_policy": FUNDING_ORDER_POLICY,
} for definition in DEFINITIONS for direction in DIRECTIONS
  for deadline in DEADLINES for target_r in TARGET_R)


def _grid_hash() -> str:
    encoded = json.dumps(CONFIGS, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _code_hash() -> str:
    names = (
        "crypto.py", "search_crypto.py", "search_crypto_r4.py",
        "search_crypto_r11_exit_distance.py", "data_access.py", "metrics.py",
        "resource_guard.py",
    )
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _registered(grid_hash: str, code_sha: str, fingerprint: str) -> set[str]:
    if not common.CSV_PATH.exists() or common.CSV_PATH.stat().st_size == 0:
        return set()
    csv.field_size_limit(sys.maxsize)
    found = set()
    with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (row["round"] != ROUND or row["parameter_grid_hash"] != grid_hash
                    or row["code_sha256"] != code_sha):
                continue
            try:
                config = json.loads(row["definition"])
                metric = json.loads(row["metric"])
            except (json.JSONDecodeError, TypeError):
                continue
            if (isinstance(config, dict) and isinstance(metric, dict)
                    and metric.get("train_input_fingerprint") == fingerprint
                    and metric.get("preregistration_sha256") == PREREG_SHA256):
                found.add(row["definition"])
    return found


def _append(config: dict, result: dict, fingerprint: str,
            grid_hash: str, code_sha: str) -> None:
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    config_sha = hashlib.sha256(config_json.encode()).hexdigest()
    metric = {
        **result,
        "train_input_fingerprint": fingerprint,
        "preregistration_sha256": PREREG_SHA256,
    }
    record = {
        "trial_id": f"{ROUND}-{config_sha[:12]}-{uuid.uuid4().hex}",
        "round": ROUND,
        "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json,
        "parameter_grid_hash": grid_hash,
        "code_sha256": code_sha,
        "train_period": "bar close <=2023-11-06T16:00:00Z",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": "",
        "notes": f"status={result['status']}; prereg={PREREG_SHA256}",
    }
    has_rows = common.CSV_PATH.exists() and common.CSV_PATH.stat().st_size > 0
    if has_rows:
        with common.CSV_PATH.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != common.FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch; R11 row not appended")
    with common.CSV_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=common.FIELDS)
        if not has_rows:
            writer.writeheader()
        writer.writerow(record)
        stream.flush()


def run() -> int:
    if hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest() != PREREG_SHA256:
        raise RuntimeError("R11 preregistration hash changed; no trials were run")
    if shutil.disk_usage("/").free < 40 * 1024**3:
        raise RuntimeError("less than 40 GiB free; no trials were run")

    import data_access

    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        raise RuntimeError("TRAIN-only data loader is unavailable")
    grid_hash, code_sha = _grid_hash(), _code_hash()
    barsets = _load_timeframe(loader, TIMEFRAME)
    fingerprint = common._train_input_fingerprint(TIMEFRAME, barsets)
    registered = _registered(grid_hash, code_sha, fingerprint)
    zone_cache = {}
    completed = 0
    for config in CONFIGS:
        config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
        if config_json in registered:
            completed += 1
            continue
        try:
            result = _trial(config, barsets, zone_cache)
        except MemoryError as exc:
            result = {"status": "failed", "detail": f"MemoryError: {exc}"}
            _append(config, result, fingerprint, grid_hash, code_sha)
            raise
        except Exception as exc:
            result = {"status": "failed", "detail": f"{type(exc).__name__}: {exc}"}
        _append(config, result, fingerprint, grid_hash, code_sha)
        registered.add(config_json)
        completed += 1
        print(
            f"[{completed}/{len(CONFIGS)}] {config['definition']} "
            f"{config['direction']} D{config['deadline']} "
            f"R{config['reward_r']}: {result['status']} "
            f"M2={result.get('m2_target_first_rate')} "
            f"EV={result.get('expectancy_bps')}bp "
            f"PF={result.get('profit_factor')}",
            flush=True,
        )
    return completed


def main() -> None:
    from resource_guard import heavy_task

    with heavy_task(ROUND):
        completed = run()
    if completed != len(CONFIGS):
        raise RuntimeError(f"expected {len(CONFIGS)} R11 trials, completed {completed}")


if __name__ == "__main__":
    main()
