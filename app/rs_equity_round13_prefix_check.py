"""Perturb post-cutoff stock data and verify all Round13 signal prefixes."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from app.rs_equity_round12_13_portfolio import _prepare_config
from app.rs_equity_round13_runner import market_context
from app.rs_equity_round13_transfer import round13_configs
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round13_prefix_validation.json"


def verify_market(market: str, configs: list[dict]) -> dict:
    panel = load_equity_panel(market)
    cutoff = pd.Timestamp("2024-02-22" if market == "US" else "2024-02-06")
    cutoff_index = int(panel.dates.searchsorted(cutoff, side="right"))
    rng = np.random.default_rng(20261014 if market == "US" else 20261015)
    future_shape = panel.c[cutoff_index:].shape
    shock = np.exp(rng.normal(0.0, 0.35, size=future_shape))
    future_slice = slice(cutoff_index, None)
    altered = replace(
        panel,
        o=panel.o.copy(),
        h=panel.h.copy(),
        l=panel.l.copy(),
        c=panel.c.copy(),
        v=panel.v.copy(),
        proxy_close=panel.proxy_close.copy(),
    )
    for name in ("o", "h", "l", "c"):
        getattr(altered, name)[future_slice] *= shock
    altered.v[future_slice] *= 7.0
    altered.proxy_close[future_slice] *= 3.0

    dates = panel.dates[int(panel.dates.searchsorted(pd.Timestamp("2019-01-01"))):]
    gate, breadth = market_context(panel)
    changed_gate, changed_breadth = market_context(altered)
    prefix = panel.dates <= cutoff
    np.testing.assert_array_equal(gate.to_numpy()[prefix], changed_gate.to_numpy()[prefix])
    np.testing.assert_array_equal(breadth.to_numpy()[prefix], changed_breadth.to_numpy()[prefix])

    fields = ("SIGNAL", "VOL_RATIO", "ATR14", "STOP_LEVEL")
    checked = 0
    for config in configs:
        original = _prepare_config(panel, config, dates, gate, breadth)
        mutated = _prepare_config(altered, config, dates, changed_gate, changed_breadth)
        for symbol in original:
            for field in fields:
                left = original[symbol][field].loc[:cutoff].to_numpy()
                right = mutated[symbol][field].loc[:cutoff].to_numpy()
                np.testing.assert_allclose(left, right, rtol=0, atol=0, equal_nan=True)
        checked += 1
        if checked % 10 == 0:
            print(f"[{market}] prefix {checked}/{len(configs)}", flush=True)
    return {
        "market": market,
        "config_count": checked,
        "symbols": len(panel.symbols),
        "cutoff": str(cutoff.date()),
        "future_price_multiplier": "deterministic lognormal, sigma 0.35",
        "future_volume_multiplier": 7.0,
        "future_proxy_multiplier": 3.0,
        "fields": list(fields),
        "changed_prefix_values": 0,
        "passed": checked == len(configs),
    }


def main() -> None:
    configs = round13_configs()
    results = [verify_market(market, configs) for market in ("US", "KR")]
    payload = {
        "source_config_count": len(configs),
        "method": "post-cutoff OHLC shock, volume x7 and equal-weight proxy x3; compare every configured signal and indicator through cutoff",
        "markets": results,
        "passed": all(row["passed"] for row in results),
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
