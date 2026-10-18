"""Transfer Round12's declared §53-57 and §59-61 policy batches to equities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.crypto_round12_extension import groups as extension_groups
from app.crypto_round12_final_batch import groups as final_groups
from app.rs_equity_round12_13_portfolio import _costs, _run_config
from app.rs_equity_transfer import load_equity_panel


OUT = Path(__file__).resolve().parents[1] / "docs/research/equity_transfer_2026-10/full_runs/round12_extension_policy_transfer.json"
PARTIAL = OUT.with_suffix(".partial.json")
START = pd.Timestamp("2019-01-01")


def _configs() -> list[dict[str, Any]]:
    out = []
    for section, title, rows in extension_groups():
        out.extend({"phase": f"R12-{section}", "policy_group": title, **row} for row in rows)
    for section, title, rows in final_groups():
        out.extend({"phase": f"R12-{section}", "policy_group": title, **row} for row in rows)
    return out


def _market_context(panel):
    proxy = pd.Series(panel.proxy_close, index=panel.dates)
    gate = proxy > proxy.rolling(200, min_periods=200).mean()
    total = np.zeros(len(panel.dates)); above = np.zeros(len(panel.dates))
    for j in range(len(panel.symbols)):
        close = pd.Series(panel.c[:, j], index=panel.dates)
        sma = close.rolling(50).mean()
        valid = sma.notna().to_numpy() & panel.eligible[:, j]
        total += valid
        above += valid & (close.to_numpy() > sma.to_numpy())
    breadth = pd.Series((total > 0) & (above / np.maximum(total, 1) >= .5), index=panel.dates)
    return gate, breadth


def _save(payload):
    temp = PARTIAL.with_suffix(".partial.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temp.replace(PARTIAL)


def _evaluate(market, payload, configs):
    panel = load_equity_panel(market)
    dates = panel.dates[int(panel.dates.searchsorted(START)):]
    gate, breadth = _market_context(panel)
    costs = _costs(panel)
    meta = payload["markets"].get(market, {})
    rows = list(meta.get("rows", []))
    done = {(json.dumps(r["config"], sort_keys=True), r["cost_case"]) for r in rows}
    meta.update({"market": market, "date_range": [str(dates[0].date()), str(dates[-1].date())],
                 "trading_dates": [str(d.date()) for d in dates], "symbols": len(panel.symbols),
                 "source_config_count": len(configs), "cost_cases": [c[0] for c in costs],
                 "rows": rows, "row_count": len(rows), "complete": False,
                 "btc_proxy": "causal equal-weight equity proxy; not BTC"})
    payload["markets"][market] = meta
    _save(payload)
    total = len(configs) * len(costs); count = len(done)
    for config in configs:
        for cost in costs:
            key = (json.dumps(config, sort_keys=True), cost[0])
            if key in done:
                continue
            rows.append(_run_config(panel, config, dates, gate, breadth, cost))
            done.add(key); count += 1; meta["row_count"] = len(rows)
            if count % 10 == 0 or count == total:
                print(f"[{market}] extension {count}/{total}", flush=True)
                _save(payload)
    meta["complete"] = True
    _save(payload)


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    configs = _configs()
    keys = [json.dumps(c, sort_keys=True) for c in configs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate source policy configuration")
    fingerprint = hashlib.sha256("\n".join(keys).encode()).hexdigest()
    if PARTIAL.exists():
        payload = json.loads(PARTIAL.read_text(encoding="utf-8"))
        if payload.get("config_fingerprint") != fingerprint:
            raise ValueError("checkpoint configuration fingerprint differs from source")
    else:
        payload = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                   "source_config_count": len(configs), "config_fingerprint": fingerprint,
                   "round12_extension_config_count": len(configs), "markets": {}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for market in ("US", "KR"):
        if not payload["markets"].get(market, {}).get("complete"):
            _evaluate(market, payload, configs)
    PARTIAL.replace(OUT)
    print(json.dumps({"configs": len(configs), **{m: r["row_count"] for m, r in payload["markets"].items()}}))


if __name__ == "__main__":
    main()
