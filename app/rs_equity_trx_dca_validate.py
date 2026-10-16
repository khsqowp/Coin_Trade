"""Re-run the DCA equity transfer, reconcile saved curves, and perturb the future."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import load_equity_panel
from app.rs_equity_trx_dca_transfer import OUT, simulate_dca


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/trx_dca_swing_validation.json"


def check_market(market: str, saved: dict) -> dict:
    panel = load_equity_panel(market)
    data = saved["markets"][market]
    cutoff = pd.Timestamp("2024-02-22" if market == "US" else "2024-02-06")
    cut = int(panel.dates.searchsorted(cutoff, side="right"))
    rng = np.random.default_rng(20261030 if market == "US" else 20261031)
    shock = np.exp(rng.normal(0, 0.35, size=panel.c[cut:].shape))
    altered = replace(
        panel, o=panel.o.copy(), h=panel.h.copy(), l=panel.l.copy(),
        c=panel.c.copy(), v=panel.v.copy(), proxy_close=panel.proxy_close.copy(),
    )
    for key in ("o", "h", "l", "c"):
        getattr(altered, key)[cut:] *= shock
    altered.v[cut:] *= 7
    altered.proxy_close[cut:] *= 3

    curve_checks = 0
    prefix_checks = 0
    max_prefix_difference = 0.0
    for case, fee, slip, tax in _costs(panel):
        original_run = simulate_dca(panel, fee, np.asarray(slip, float), tax)
        mutated_run = simulate_dca(altered, fee, np.asarray(slip, float), tax)
        stored = next(row for row in data["rows"] if row["cost_case"] == case)
        curve = np.asarray(original_run["daily_equity"], dtype=float)
        stored_curve = np.asarray(stored["daily_equity"], dtype=float)
        dates = pd.DatetimeIndex(original_run["daily_dates"])
        if len(curve) != len(stored_curve) or len(dates) != len(curve):
            raise AssertionError("saved curve/calendar lengths differ")
        np.testing.assert_allclose(curve, stored_curve, rtol=0, atol=1e-12)
        years = (dates[-1] - dates[0]).days / 365.25
        cagr = (curve[-1] / curve[0]) ** (1 / years) - 1
        mdd = float((1 - curve / np.maximum.accumulate(curve)).max())
        returns = curve[1:] / curve[:-1] - 1
        sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(365)) if returns.std(ddof=1) else 0.0
        np.testing.assert_allclose(
            [stored["metrics"]["cagr"] / 100, stored["metrics"]["mdd"] / 100, stored["metrics"]["sharpe"]],
            [cagr, mdd, sharpe], rtol=0, atol=2e-8,
        )
        curve_checks += 1
        prefix = dates <= cutoff
        left = curve[prefix]
        right = np.asarray(mutated_run["daily_equity"], float)[prefix]
        np.testing.assert_allclose(left, right, rtol=0, atol=0)
        max_prefix_difference = max(max_prefix_difference, float(np.max(np.abs(left - right))))
        prefix_checks += len(left)

    return {
        "market": market, "cutoff": str(cutoff.date()),
        "cost_curves_reconciled": curve_checks,
        "account_equity_prefix_values_compared": prefix_checks,
        "future_price_log_sigma": 0.35,
        "future_volume_multiplier": 7,
        "future_proxy_multiplier": 3,
        "max_prefix_difference": max_prefix_difference,
        "passed": True,
    }


def main() -> None:
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    markets = [check_market(market, saved) for market in ("US", "KR")]
    payload = {
        "markets": markets,
        "all_saved_curves_reconciled": all(x["cost_curves_reconciled"] == 2 for x in markets),
        "all_future_prefix_checks_passed": all(x["passed"] for x in markets),
    }
    VALIDATION.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
