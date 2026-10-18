"""Run all 397 Round16 source configurations with synthetic OHLC tier proxies."""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import pandas as pd

from app.rs_equity_round12_13_portfolio import _costs, _run_config
from app.rs_equity_round13_runner import market_context
from app.rs_equity_round16_transfer import prepare_round16, round16_configs
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round16_liquidation_proxy_transfer.json"
CHECKPOINT = OUTPUT.with_suffix(".partial.json")
START = pd.Timestamp("2019-01-01")


def save(payload: dict) -> None:
    temporary = CHECKPOINT.with_suffix(".partial.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(CHECKPOINT)


def run_market(market: str, payload: dict, configs: list[dict]) -> None:
    panel = load_equity_panel(market)
    dates = panel.dates[int(panel.dates.searchsorted(START)):]
    gate, breadth = market_context(panel)
    market_data = payload["markets"].setdefault(market, {})
    rows = market_data.get("rows", [])
    done = {(json.dumps(row["config"], sort_keys=True), row["cost_case"]) for row in rows}
    market_data.update(
        market=market,
        date_range=[str(dates[0].date()), str(dates[-1].date())],
        trading_dates=[str(date.date()) for date in dates],
        symbols=len(panel.symbols),
        source_config_count=len(configs),
        cost_cases=[case[0] for case in _costs(panel)],
        rows=rows,
        row_count=len(rows),
        complete=False,
        liquidation_proxy="synthetic OHLC swing anchors; assumed leverage tiers; not actual liquidations/OI",
    )
    payload["markets"][market] = market_data
    save(payload)
    total_rows = len(configs) * len(_costs(panel))
    finished_configs = 0
    signal_cache = {}
    for config in configs:
        config_key = json.dumps(config, sort_keys=True)
        missing_costs = [
            cost for cost in _costs(panel)
            if (config_key, cost[0]) not in done
        ]
        if not missing_costs:
            finished_configs += 1
            continue
        prepared = prepare_round16(panel, config, dates, cache=signal_cache)
        runtime_config = {**config, **config["execution"]}
        for cost in missing_costs:
            result = _run_config(
                panel, runtime_config, dates, gate, breadth, cost,
                prepared_override=prepared,
            )
            result["config"] = config
            rows.append(result)
            done.add((config_key, cost[0]))
        finished_configs += 1
        market_data["row_count"] = len(rows)
        if finished_configs % 25 == 0 or finished_configs == len(configs):
            print(
                f"[{market}] Round16 {finished_configs}/{len(configs)} configs; "
                f"{len(rows)}/{total_rows} rows",
                flush=True,
            )
            save(payload)
    if len(rows) != total_rows:
        raise ValueError(f"{market} expected {total_rows} rows, got {len(rows)}")
    market_data["complete"] = True
    save(payload)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    configs = round16_configs()
    serialized = [json.dumps(config, sort_keys=True) for config in configs]
    fingerprint = hashlib.sha256("\n".join(serialized).encode()).hexdigest()
    if CHECKPOINT.exists():
        payload = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if payload.get("config_fingerprint") != fingerprint:
            raise ValueError("Round16 checkpoint fingerprint mismatch")
    else:
        payload = {
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "source_config_count": len(configs),
            "config_fingerprint": fingerprint,
            "source": "crypto_round16_liquidation_research.plans()",
            "note": "Equity liquidation tiers are synthetic OHLC proxies; no historical equity liquidation feed is represented.",
            "markets": {},
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for market in ("US", "KR"):
        if not payload["markets"].get(market, {}).get("complete"):
            run_market(market, payload, configs)
    CHECKPOINT.replace(OUTPUT)
    print(json.dumps({"configs": len(configs), **{m: v["row_count"] for m, v in payload["markets"].items()}}))


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=FutureWarning)
    main()
