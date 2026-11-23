"""R3 4h-long crypto order-block filter grid; TRAIN-only and data-loader gated."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import uuid
from datetime import datetime, timezone

from pathlib import Path
from trial_ledger_compaction import compact_id_list

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search_crypto as r2  # noqa: E402

TREND_FILTERS = ("none", "close_gt_sma20", "close_gt_sma50", "sma20_gt_sma50")
SESSION_FILTERS = ("none", "asia", "europe", "us")
CONFIGS = tuple({
    "definition": definition, "timeframe": "4h", "direction": "long",
    "deadline": 48, "reward_r": 2.0, "trend_filter": trend,
    "session_filter": session, "minimum_symbols": 25,
    "maximum_censored_fraction": 0.35, "minimum_remaining_trades": 20,
} for definition in r2.DEFINITIONS for trend in TREND_FILTERS
  for session in SESSION_FILTERS)
FIELDS = r2.FIELDS


def exclude_unscorable_symbols(barsets):
    """Exclude only symbols without TRAIN bars; score funding gaps by overlap."""
    kept, empty_excluded = [], []
    for symbol, bars, funding, incomplete_count in barsets:
        if not bars:
            empty_excluded.append(symbol)
            continue
        kept.append((symbol, bars, funding, incomplete_count))
    return kept, [], sorted(empty_excluded)


def _funding_unresolved(event):
    if event.coverage_gap or event.mark_price is None:
        return True
    try:
        return not math.isfinite(event.mark_price) or event.mark_price <= 0
    except (TypeError, ValueError):
        return True


def _apply_symbol_floor(result, minimum_symbols, kept_count):
    result["kept_symbols"] = kept_count
    failures = []
    if result.get("censored_fraction", 0.0) > 0.35:
        failures.append(f"censored_fraction {result['censored_fraction']:.6f} exceeds maximum 0.350000")
    if result.get("trades", 0) < 20:
        failures.append(f"remaining trades {result.get('trades', 0)} below minimum 20")
    if kept_count < minimum_symbols:
        failures.append(f"only {kept_count} kept symbols; need {minimum_symbols}")
    if failures:
        result["status"] = "unscorable"
        result["detail"] = "; ".join(filter(None, (result.get("detail", ""), *failures)))
    return result


def _append_r3(config, result, fingerprint):
    config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
    config_hash = hashlib.sha256(config_json.encode()).hexdigest()
    grid = json.dumps(CONFIGS, sort_keys=True, separators=(",", ":"))
    grid_hash = hashlib.sha256(grid.encode()).hexdigest()
    code_hash = hashlib.sha256()
    for name in ("crypto.py", "search_crypto.py", "search_crypto_r3.py",
                 "data_access.py", "metrics.py", "resource_guard.py",
                 "trial_ledger_compaction.py"):
        code_hash.update((HERE / name).read_bytes())
    metric = {key: result.get(key) for key in r2.METRIC_FIELDS}
    metric["train_input_fingerprint"] = fingerprint
    record = {
        "trial_id": f"R3-coin-reregistered-{config_hash[:12]}-{uuid.uuid4().hex}",
        "round": "R3-coin",
        "market_group": "crypto", "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": config_json, "parameter_grid_hash": grid_hash,
        "code_sha256": code_hash.hexdigest(),
        "train_period": "4h close <=2023-11-06T16:00:00Z",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":")),
        "rank": "", "notes": f"attempted_config_sha256={config_hash}; status={result['status']}; train_input_fingerprint={fingerprint}",
    }
    path = r2.CSV_PATH
    if path.exists() and path.stat().st_size:
        with path.open(newline="", encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch; R3 row not appended")
    with path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if not path.stat().st_size:
            writer.writeheader()
        writer.writerow(record)


def _run(shard="0/1"):
    try:
        shard_index, shard_count = (int(part) for part in shard.split("/", 1))
    except (ValueError, TypeError):
        raise ValueError("--shard must be INDEX/COUNT")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("shard must satisfy 0 <= INDEX < COUNT")
    import data_access

    loader = getattr(data_access, "iter_train_bars", None)
    if loader is None:
        raise RuntimeError("data_access.iter_train_bars contract missing")
    barsets = []
    for symbol, bars, funding in loader(timeframe="4h", shard_index=shard_index,
                                        shard_count=shard_count):
        closed = [bar for bar in bars if bar.complete]
        barsets.append((symbol, closed, funding, len(bars) - len(closed)))
        r2._check_memory()
    fingerprint = r2._train_input_fingerprint("4h", barsets)
    kept, funding_excluded, empty_excluded = exclude_unscorable_symbols(barsets)
    zone_cache = {}
    unresolved_symbols = sorted({
        symbol for symbol, bars, funding, _ in kept
        if any(_funding_unresolved(event) for event in funding.values())
    })
    for config in CONFIGS:
        try:
            result = r2._run_trial(config, kept, zone_cache)
            result["kept_symbols"] = len(kept)
            sensitivity = r2._run_trial(
                config, kept, zone_cache, exclude_symbols=set(unresolved_symbols))
            result.update(
                sensitivity_excluded_symbols=compact_id_list(unresolved_symbols),
                sensitivity_trades=sensitivity["trades"],
                sensitivity_expectancy_bps=sensitivity["expectancy_bps"],
                sensitivity_profit_factor=sensitivity["profit_factor"],
                sensitivity_win_rate=sensitivity["win_rate"],
                sensitivity_max_drawdown=sensitivity["max_drawdown"],
                sensitivity_kept_symbols=sensitivity["kept_symbols"],
            )
            # This is overlap-derived by the scorer; do not restore the old
            # symbol-wide prefilter list.
            result["excluded_no_train_bar_symbols"] = empty_excluded
            _apply_symbol_floor(result, config["minimum_symbols"], len(kept))
        except Exception as exc:
            result = dict.fromkeys(r2.METRIC_FIELDS)
            result.update(status="failed", detail=f"{type(exc).__name__}: {exc}",
                          kept_symbols=len(kept),
                          excluded_funding_symbols=funding_excluded,
                          excluded_no_train_bar_symbols=empty_excluded)
        _append_r3(config, result, fingerprint)
    return 0


def main():
    from resource_guard import heavy_task
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", default="0/1")
    args = parser.parse_args()
    with heavy_task("B-R3-coin"):
        return _run(args.shard)


if __name__ == "__main__":
    raise SystemExit(main())
