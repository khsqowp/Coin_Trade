"""Transfer all 34 Round11 portfolio policies to the current US/KR stock panels."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.crypto_round11_research import build as source_build
from app.crypto_round11_research import configs as source_configs
from app.crypto_round8_research import core as source_core
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import EquityPanel, load_equity_panel
from app.round11_portfolio import simulate
from app.technical_portfolio_engine import prepare

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round11_policy_transfer.json"
VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round11_prefix_validation.json"
START = pd.Timestamp("2019-01-01")
FAMILIES = ("volume", "heikin_ashi", "frvp")


class StockFrames(dict):
    """Expose the synthetic market proxy as BTC without making it tradable."""

    def __init__(self, stocks: dict[str, pd.DataFrame], proxy: pd.DataFrame):
        super().__init__(stocks)
        self.proxy = proxy

    def __getitem__(self, key):
        return self.proxy if key == "BTC" else super().__getitem__(key)


def stock_frames(panel: EquityPanel) -> StockFrames:
    stocks = {}
    for j, symbol in enumerate(panel.symbols):
        frame = pd.DataFrame({
            "Open": panel.o[:, j], "High": panel.h[:, j], "Low": panel.l[:, j],
            "Close": panel.c[:, j], "Volume": panel.v[:, j],
        }, index=panel.dates)
        valid = np.isfinite(frame[["Open", "High", "Low", "Close", "Volume"]]).all(axis=1)
        valid &= (frame[["Open", "High", "Low", "Close"]] > 0).all(axis=1)
        valid &= frame.Volume > 0
        stocks[symbol] = frame.loc[valid & (frame.index >= START)]
    proxy = pd.DataFrame({
        "Open": panel.D["d"]["o"][:, -1], "High": panel.D["d"]["h"][:, -1],
        "Low": panel.D["d"]["l"][:, -1], "Close": panel.D["d"]["c"][:, -1],
        "Volume": panel.D["d"]["v"][:, -1],
    }, index=panel.dates)
    return StockFrames(stocks, proxy)


def prepare_signals(frames: StockFrames):
    cores = {family: source_core(family, frames) for family in FAMILIES}
    return cores


def _adapt_build(config: dict[str, Any], frames: StockFrames, cores: dict[str, dict]):
    prepped, data, kwargs, state = source_build(config, frames, cores)
    adaptation = None
    if config.get("universe") == "large10":
        # Coin capitalization names have no stock-market meaning. Use a causal
        # monthly top-10 dollar-turnover proxy, not a fabricated market-cap rank.
        dates = pd.DatetimeIndex(sorted(set().union(*(f.index for f in cores["volume"].values()))))
        dollar_turnover = pd.DataFrame({
            symbol: (frame.Close * frame.Volume).rolling(30, min_periods=20).mean()
            for symbol, frame in frames.items()
        }).reindex(dates)
        membership: dict[pd.Timestamp, set[str]] = {}
        current: set[str] = set()
        for day in dates:
            if (day + pd.Timedelta(days=1)).month != day.month:
                current = set(dollar_turnover.loc[day].dropna().sort_values(
                    ascending=False, kind="stable").head(10).index)
            membership[day] = current.copy()
        for symbol, signal_frame in prepped.items():
            signal_frame["SIGNAL"] = cores["volume"][symbol]["SIGNAL"].reindex(
                signal_frame.index, fill_value=False
            ) & pd.Series({day: symbol in membership[day] for day in signal_frame.index})
        data = prepare(prepped)
        adaptation = "large10 mapped to causal monthly top-10 trailing dollar-turnover; historical stock market-cap membership unavailable"
    return prepped, data, kwargs, state, adaptation


def _run_one(panel: EquityPanel, config: dict[str, Any], frames: StockFrames,
             cores: dict[str, dict], cost: tuple) -> dict[str, Any]:
    prepped, data, kwargs, state, adaptation = _adapt_build(config, frames, cores)
    cost_case, fee_pct, slip, tax = cost
    keys = data[1]
    slip_array = np.asarray(slip, dtype=float)
    if slip_array.ndim:
        slip_array = slip_array[[panel.symbols.index(symbol) for symbol in keys]]
    result = simulate(
        prepped, prepared=data, return_trace=True,
        fee=fee_pct / 100, slippage=slip_array, sell_tax=tax,
        borrow_annual=.01 if panel.market == "US" else .03, **kwargs,
    )
    trace = result["trace"]
    metrics = {key: result[key] for key in
               ("cagr", "mdd", "sharpe", "trades", "final", "insolvent", "stopped")}
    row = {
        "config": config, "cost_case": cost_case, "metrics": metrics,
        "signal_count": int(sum(frame.SIGNAL.sum() for frame in prepped.values())),
        "daily_equity": result["equity"], "daily_dates": [str(x) for x in data[0]],
        "daily_date_count": len(data[0]), "active_positions_max": max(
            (point["positions"] for point in trace), default=0),
    }
    if adaptation:
        row["adaptation"] = adaptation
    return row


def run_market(market: str) -> dict[str, Any]:
    panel = load_equity_panel(market)
    frames = stock_frames(panel)
    cores = prepare_signals(frames)
    configs = [config for group in source_configs().values() for config in group]
    if len(configs) != 34 or len({json.dumps(x, sort_keys=True) for x in configs}) != 34:
        raise AssertionError("Round11 source config grid changed or is not unique")
    rows = []
    for i, config in enumerate(configs, 1):
        for cost in _costs(panel):
            rows.append(_run_one(panel, config, frames, cores, cost))
        if i % 10 == 0:
            print(f"{market}: {i}/{len(configs)} Round11 configs", flush=True)
    dates = rows[0]["daily_dates"]
    return {
        "market": market, "symbols": panel.symbols, "dates": dates,
        "source_config_count": len(configs), "row_count": len(rows), "rows": rows,
        "definition": "Round11 daily equity adaptation; proxy regime is synthetic equal-weight equity, large10 uses turnover proxy.",
    }


def run():
    payload = {"markets": {market: run_market(market) for market in ("US", "KR")}}
    payload["row_count"] = sum(item["row_count"] for item in payload["markets"].values())
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({market: item["row_count"] for market, item in payload["markets"].items()}))
    return payload


if __name__ == "__main__":
    run()
