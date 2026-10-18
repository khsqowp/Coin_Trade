"""Run Round14's 44 predeclared account configurations on US and KR stocks."""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import pandas as pd

from app.rs_equity_round12_13_portfolio import _costs, _run_config
from app.rs_equity_round13_runner import market_context
from app.rs_equity_round14_transfer import round14_configs
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round14_policy_transfer.json"
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
        btc_proxy="causal equal-weight stock proxy; not BTC",
    )
    save(payload)
    total = len(configs) * len(_costs(panel))
    for config in configs:
        for cost in _costs(panel):
            key = (json.dumps(config, sort_keys=True), cost[0])
            if key in done:
                continue
            rows.append(_run_config(panel, config, dates, gate, breadth, cost))
            done.add(key)
            market_data["row_count"] = len(rows)
            if len(done) % 10 == 0 or len(done) == total:
                print(f"[{market}] Round14 {len(done)}/{total}", flush=True)
                save(payload)
    market_data["complete"] = True
    save(payload)


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    configs = round14_configs()
    serialized = [json.dumps(config, sort_keys=True) for config in configs]
    fingerprint = hashlib.sha256("\n".join(serialized).encode()).hexdigest()
    if CHECKPOINT.exists():
        payload = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if payload.get("config_fingerprint") != fingerprint:
            raise ValueError("Round14 checkpoint fingerprint mismatch")
    else:
        payload = {
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "source_config_count": len(configs),
            "config_fingerprint": fingerprint,
            "source": "crypto_round14_research.plans()",
            "markets": {},
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    for market in ("US", "KR"):
        if not payload["markets"].get(market, {}).get("complete"):
            run_market(market, payload, configs)
    CHECKPOINT.replace(OUTPUT)
    print(json.dumps({"configs": len(configs), **{market: value["row_count"] for market, value in payload["markets"].items()}}))


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=FutureWarning)
    main()
