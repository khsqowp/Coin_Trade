"""Prefix-invariance test for every Round14 stock-transfer configuration."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from app.rs_equity_round12_13_portfolio import _prepare_config
from app.rs_equity_round13_runner import market_context
from app.rs_equity_round14_transfer import round14_configs
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round14_prefix_validation.json"


def verify(market: str, configs: list[dict]) -> dict:
    panel = load_equity_panel(market)
    cutoff = pd.Timestamp("2024-02-22" if market == "US" else "2024-02-06")
    cutoff_index = int(panel.dates.searchsorted(cutoff, side="right"))
    rng = np.random.default_rng(20261024 if market == "US" else 20261025)
    shock = np.exp(rng.normal(0.0, 0.35, size=panel.c[cutoff_index:].shape))
    changed = replace(
        panel,
        o=panel.o.copy(), h=panel.h.copy(), l=panel.l.copy(),
        c=panel.c.copy(), v=panel.v.copy(), proxy_close=panel.proxy_close.copy(),
    )
    future = slice(cutoff_index, None)
    for key in ("o", "h", "l", "c"):
        getattr(changed, key)[future] *= shock
    changed.v[future] *= 7
    changed.proxy_close[future] *= 3
    dates = panel.dates[int(panel.dates.searchsorted(pd.Timestamp("2019-01-01"))):]
    gate, breadth = market_context(panel)
    new_gate, new_breadth = market_context(changed)
    prefix = panel.dates <= cutoff
    np.testing.assert_array_equal(gate.to_numpy()[prefix], new_gate.to_numpy()[prefix])
    np.testing.assert_array_equal(breadth.to_numpy()[prefix], new_breadth.to_numpy()[prefix])
    for config in configs:
        original = _prepare_config(panel, config, dates, gate, breadth)
        perturbed = _prepare_config(changed, config, dates, new_gate, new_breadth)
        for symbol in original:
            for field in ("SIGNAL", "VOL_RATIO", "ATR14", "STOP_LEVEL"):
                np.testing.assert_allclose(
                    original[symbol][field].loc[:cutoff].to_numpy(),
                    perturbed[symbol][field].loc[:cutoff].to_numpy(),
                    rtol=0, atol=0, equal_nan=True,
                )
    return {
        "market": market, "config_count": len(configs), "symbols": len(panel.symbols),
        "cutoff": str(cutoff.date()), "future_price_sigma": 0.35,
        "future_volume_multiplier": 7, "future_proxy_multiplier": 3,
        "fields": ["SIGNAL", "VOL_RATIO", "ATR14", "STOP_LEVEL", "market_gate", "breadth"],
        "changed_prefix_values": 0, "passed": True,
    }


def main() -> None:
    configs = round14_configs()
    results = [verify(market, configs) for market in ("US", "KR")]
    payload = {"source_config_count": len(configs), "markets": results, "passed": all(row["passed"] for row in results)}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
