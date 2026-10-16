"""Run the source-declared Round13 §69-76 equity policy transfer grid."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.rs_equity_round12_13_portfolio import _costs, _run_config
from app.rs_equity_round13_transfer import round13_configs
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round13_policy_transfer.json"
CHECKPOINT = OUTPUT.with_suffix(".partial.json")
START = pd.Timestamp("2019-01-01")


def market_context(panel):
    proxy = pd.Series(panel.proxy_close, index=panel.dates)
    gate = proxy > proxy.rolling(200, min_periods=200).mean()
    eligible_count = np.zeros(len(panel.dates))
    above_count = np.zeros(len(panel.dates))
    for index in range(len(panel.symbols)):
        close = pd.Series(panel.c[:, index], index=panel.dates)
        average = close.rolling(50).mean()
        valid = average.notna().to_numpy() & panel.eligible[:, index]
        eligible_count += valid
        above_count += valid & (close.to_numpy() > average.to_numpy())
    breadth = pd.Series(
        (eligible_count > 0)
        & (above_count / np.maximum(eligible_count, 1) >= 0.5),
        index=panel.dates,
    )
    return gate, breadth


def save_checkpoint(payload: dict[str, Any]) -> None:
    temporary = CHECKPOINT.with_suffix(".partial.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    temporary.replace(CHECKPOINT)


def evaluate_market(market: str, payload: dict[str, Any], configs: list[dict[str, Any]]) -> None:
    panel = load_equity_panel(market)
    dates = panel.dates[int(panel.dates.searchsorted(START)):]
    gate, breadth = market_context(panel)
    market_data = payload["markets"].get(market, {})
    rows = market_data.get("rows", [])
    completed = {
        (json.dumps(row["config"], sort_keys=True), row["cost_case"])
        for row in rows
    }
    market_data.update(
        {
            "market": market,
            "date_range": [str(dates[0].date()), str(dates[-1].date())],
            "trading_dates": [str(date.date()) for date in dates],
            "symbols": len(panel.symbols),
            "source_config_count": len(configs),
            "cost_cases": [case[0] for case in _costs(panel)],
            "rows": rows,
            "row_count": len(rows),
            "complete": False,
            "proxy": "causal equal-weight stock index; not BTC",
        }
    )
    payload["markets"][market] = market_data
    save_checkpoint(payload)

    total = len(configs) * len(_costs(panel))
    for config in configs:
        for cost in _costs(panel):
            key = (json.dumps(config, sort_keys=True), cost[0])
            if key in completed:
                continue
            rows.append(_run_config(panel, config, dates, gate, breadth, cost))
            completed.add(key)
            market_data["row_count"] = len(rows)
            if len(completed) % 10 == 0 or len(completed) == total:
                print(f"[{market}] Round13 {len(completed)}/{total}", flush=True)
                save_checkpoint(payload)
    market_data["complete"] = True
    save_checkpoint(payload)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    configs = round13_configs()
    serialized = [json.dumps(config, sort_keys=True) for config in configs]
    if len(serialized) != len(set(serialized)):
        raise ValueError("duplicate Round13 source configurations")
    fingerprint = hashlib.sha256("\n".join(serialized).encode()).hexdigest()
    if CHECKPOINT.exists():
        payload = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if payload.get("config_fingerprint") != fingerprint:
            raise ValueError("checkpoint config fingerprint does not match source")
    else:
        payload = {
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "source_config_count": len(configs),
            "config_fingerprint": fingerprint,
            "source_sections": "crypto_round13_extension §69-72; crypto_round13_final_batch §73-76",
            "markets": {},
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for market in ("US", "KR"):
        if not payload["markets"].get(market, {}).get("complete"):
            evaluate_market(market, payload, configs)
    CHECKPOINT.replace(OUTPUT)
    print(json.dumps({"configs": len(configs), **{m: v["row_count"] for m, v in payload["markets"].items()}}))


if __name__ == "__main__":
    main()
