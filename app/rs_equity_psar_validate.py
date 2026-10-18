"""Reconcile native PSAR transfer curves and test post-cutoff prefix stability."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from app.rs_equity_psar_transfer import OUT, START, prepare_psar
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/psar_native_validation.json"


def market_check(market: str, result: dict) -> dict:
    panel = load_equity_panel(market)
    dates = panel.dates[int(panel.dates.searchsorted(START)):]
    data = result["markets"][market]
    curve_checks = 0
    for row in data["rows"]:
        curve = np.asarray(row["daily_equity"], dtype=float)
        if len(curve) != len(dates) or not np.isfinite(curve).all() or (curve <= 0).any():
            raise AssertionError("invalid PSAR daily curve")
        metrics = row["metrics"]
        years = (dates[-1] - dates[0]).days / 365.25
        cagr = (curve[-1] / curve[0]) ** (1 / years) - 1
        mdd = float((1 - curve / np.maximum.accumulate(curve)).max())
        rets = curve[1:] / curve[:-1] - 1
        sharpe = float(rets.mean() / rets.std(ddof=1) * np.sqrt(365)) if rets.std(ddof=1) else 0.0
        np.testing.assert_allclose(
            [metrics["cagr"] / 100, metrics["mdd"] / 100, metrics["sharpe"]],
            [cagr, mdd, sharpe], rtol=0, atol=2e-8,
        )
        curve_checks += 1

    cutoff = pd.Timestamp("2024-02-22" if market == "US" else "2024-02-06")
    cut = int(panel.dates.searchsorted(cutoff, side="right"))
    rng = np.random.default_rng(20261028 if market == "US" else 20261029)
    shock = np.exp(rng.normal(0, 0.35, size=panel.c[cut:].shape))
    altered = replace(
        panel, o=panel.o.copy(), h=panel.h.copy(), l=panel.l.copy(),
        c=panel.c.copy(), v=panel.v.copy(), proxy_close=panel.proxy_close.copy(),
    )
    for key in ("o", "h", "l", "c"):
        getattr(altered, key)[cut:] *= shock
    altered.v[cut:] *= 7
    altered.proxy_close[cut:] *= 3
    prefix_dates = panel.dates[int(panel.dates.searchsorted(START)):]
    original = prepare_psar(panel, prefix_dates)
    perturbed = prepare_psar(altered, prefix_dates)
    checked_values = 0
    for symbol in original:
        for field in ("SIGNAL", "EXIT_SIGNAL"):
            a = original[symbol][field].loc[:cutoff].to_numpy()
            b = perturbed[symbol][field].loc[:cutoff].to_numpy()
            np.testing.assert_array_equal(a, b)
            checked_values += len(a)
    return {
        "market": market,
        "symbols": len(panel.symbols),
        "cutoff": str(cutoff.date()),
        "curve_rows_reconciled": curve_checks,
        "prefix_fields_checked": ["SIGNAL", "EXIT_SIGNAL"],
        "prefix_values_compared": checked_values,
        "future_price_log_sigma": 0.35,
        "future_volume_multiplier": 7,
        "future_proxy_multiplier": 3,
        "changed_prefix_values": 0,
        "passed": True,
    }


def main() -> None:
    result = json.loads(OUT.read_text(encoding="utf-8"))
    checks = [market_check(market, result) for market in ("US", "KR")]
    payload = {
        "source_library": "pandas-ta 0.4.71b0",
        "markets": checks,
        "all_curve_metrics_reconciled": True,
        "all_prefix_checks_passed": all(row["passed"] for row in checks),
    }
    VALIDATION.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
