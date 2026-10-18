"""Transfer all predeclared Round10 crypto regime policies to US/KR equities.

This is a daily stock adaptation, not literal crypto replication: BTC regime
inputs use the adapter's non-tradable equal-weight equity proxy and stock costs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.crypto_round10_research import configs as source_configs
from app.crypto_round10_research import execution as source_execution
from app.crypto_round10_research import regimes as source_regimes
from app.crypto_round8_research import core as source_core
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import EquityPanel, load_equity_panel
from app.round13_costs import simulate_cost_portfolio
from app.technical_portfolio_engine import prepare

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round10_policy_transfer.json"
VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round10_prefix_validation.json"
START = pd.Timestamp("2019-01-01")


def _stock_frames(panel: EquityPanel) -> dict[str, pd.DataFrame]:
    frames = {}
    for j, symbol in enumerate(panel.symbols):
        frame = pd.DataFrame({
            "Open": panel.o[:, j], "High": panel.h[:, j], "Low": panel.l[:, j],
            "Close": panel.c[:, j], "Volume": panel.v[:, j],
        }, index=panel.dates)
        valid = np.isfinite(frame[["Open", "High", "Low", "Close", "Volume"]]).all(axis=1)
        valid &= (frame[["Open", "High", "Low", "Close"]] > 0).all(axis=1)
        valid &= frame["Volume"] > 0
        frames[symbol] = frame.loc[valid & (frame.index >= START)]
    return frames


def _prepare(panel: EquityPanel, frames: dict[str, pd.DataFrame]):
    families = ("volume", "heikin_ashi", "frvp", "fvg", "vwap")
    prepped = {family: source_core(family, frames) for family in families}
    prepared = {family: prepare(signals) for family, signals in prepped.items()}
    proxy = pd.DataFrame({
        "Open": panel.D["d"]["o"][:, -1], "High": panel.D["d"]["h"][:, -1],
        "Low": panel.D["d"]["l"][:, -1], "Close": panel.D["d"]["c"][:, -1],
        "Volume": panel.D["d"]["v"][:, -1],
    }, index=panel.dates)
    regime = source_regimes(proxy)
    return prepped, prepared, regime


def _run_one(panel: EquityPanel, config: dict[str, Any], prepped: dict,
             prepared: dict, regime: pd.DataFrame, cost: tuple) -> dict[str, Any]:
    kwargs = source_execution(config, prepared, regime)
    cost_name, fee, slip, tax = cost
    keys = prepared[config["family"]][1]
    slip_by_symbol = np.asarray(slip, dtype=float)[
        [panel.symbols.index(symbol) for symbol in keys]
    ] if np.asarray(slip).ndim else float(slip)
    result = simulate_cost_portfolio(
        prepped[config["family"]], fee_pct_one_way=fee,
        slippage=slip_by_symbol, sell_tax=tax, return_trace=True, **kwargs,
    )
    trace = result.pop("trace")
    curve = [float(point["closing"]) for point in trace]
    metric_names = ("cagr", "mdd", "sharpe", "trades", "final", "start", "end")
    metrics = {
        key: (int(result[key]) if key == "trades" else
              str(result[key]) if key in ("start", "end") else float(result[key]))
        for key in metric_names
    }
    return {
        "section": next(section for section, _, group in source_configs() if config in group),
        "config": config, "cost_case": cost_name, "metrics": metrics,
        "signal_count": int(sum(frame.SIGNAL.sum() for frame in prepped[config["family"]].values())),
        "daily_equity": curve, "daily_date_count": len(trace),
    }


def run_market(market: str) -> dict[str, Any]:
    panel = load_equity_panel(market)
    d0 = int(panel.dates.searchsorted(START))
    if d0 >= len(panel.dates) - 100:
        raise RuntimeError(f"insufficient daily data for {market}")
    frames = _stock_frames(panel)
    prepped, prepared, regime = _prepare(panel, frames)
    configs = [config for _, _, group in source_configs() for config in group]
    if len(configs) != 136 or len({json.dumps(x, sort_keys=True) for x in configs}) != 136:
        raise AssertionError("Round10 source grid changed or contains duplicate configurations")
    rows = []
    for index, config in enumerate(configs, 1):
        for cost in _costs(panel):
            rows.append(_run_one(panel, config, prepped, prepared, regime, cost))
        if index % 20 == 0:
            print(f"{market}: {index}/{len(configs)} configurations", flush=True)
    dates = [str(day.date()) for day in pd.DatetimeIndex(prepared["volume"][0])]
    return {
        "market": market, "symbols": panel.symbols, "dates": dates,
        "source_configuration_count": len(configs), "row_count": len(rows), "rows": rows,
        "definition": "Round10 causal daily equity adaptation; BTC regime maps to a synthetic equal-weight equity proxy.",
    }


def run() -> dict[str, Any]:
    payload = {"markets": {market: run_market(market) for market in ("US", "KR")}}
    payload["row_count"] = sum(data["row_count"] for data in payload["markets"].values())
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"markets": {k: v["row_count"] for k, v in payload["markets"].items()},
                      "total": payload["row_count"]}))
    return payload


if __name__ == "__main__":
    run()
