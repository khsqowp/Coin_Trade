"""Validate showdown daily curves and future-prefix invariance."""
from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd

from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_showdown_transfer import OUT, ROOT, configurations, portfolio_inputs, simulate
from app.rs_equity_transfer import load_equity_panel

VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/showdown_prefix_validation.json"


def shock(panel, cutoff):
    changed = copy.copy(panel)
    after = panel.dates > cutoff
    for key in ("o", "h", "l", "c"):
        setattr(changed, key, getattr(panel, key).copy())
        getattr(changed, key)[after] *= 3.
    changed.v = panel.v.copy()
    changed.v[after] *= 7.
    changed.proxy_close = panel.proxy_close.copy()
    changed.proxy_close[after] *= 3.
    return changed


def main():
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    results = {}
    total = 0
    for market in ("US", "KR"):
        panel = load_equity_panel(market)
        dates = pd.DatetimeIndex(saved["markets"][market]["dates"])
        cutoff = dates[len(dates) // 2]
        prefix_n = int((dates <= cutoff).sum())
        changed = shock(panel, cutoff)
        base_dates, base_inputs, base_bull = portfolio_inputs(panel)
        alt_dates, alt_inputs, alt_bull = portfolio_inputs(changed)
        assert base_dates.equals(alt_dates)
        np.testing.assert_array_equal(base_bull[:prefix_n], alt_bull[:prefix_n])
        configs = configurations()
        assert len(configs) == 112 and len(saved["markets"][market]["rows"]) == 224
        checked = 0
        for config in configs:
            for cost in _costs(panel):
                row = next(x for x in saved["markets"][market]["rows"]
                           if x["config"] == config and x["cost_case"] == cost[0])
                altered = simulate(alt_inputs, alt_dates, alt_bull, config, cost, market)
                expected_dates = row["daily_dates"]
                assert expected_dates == [str(x.date()) for x in dates[:len(expected_dates)]]
                prefix = int((pd.DatetimeIndex(expected_dates) <= cutoff).sum())
                np.testing.assert_allclose(row["daily_equity"][:prefix],
                                           altered["daily_equity"][:prefix], rtol=0, atol=1e-12)
                curve = np.asarray(row["daily_equity"], dtype=float)
                curve_dates = pd.DatetimeIndex(row["daily_dates"])
                assert len(curve) == len(curve_dates) and np.isfinite(curve).all() and (curve >= 0).all()
                insolvent = bool(curve[-1] <= 0)
                years = max((curve_dates[-1] - curve_dates[0]).days / 365.25, 1 / 365.25)
                cagr = -100. if insolvent else (curve[-1] ** (1 / years) - 1) * 100
                peaks = np.maximum.accumulate(curve)
                mdd = 100. if insolvent else ((peaks - curve) / peaks).max() * 100
                daily = pd.Series(row["daily_returns"], dtype=float)
                assert len(daily) == len(curve)
                sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() else 0.
                np.testing.assert_allclose([cagr, mdd, sharpe, curve[-1]],
                                           [row["metrics"][k] for k in ("cagr", "mdd", "sharpe", "final")],
                                           rtol=0, atol=1e-9)
                checked += 1
        total += checked
        results[market] = {"curves": checked, "cutoff": str(cutoff.date()),
                           "price_multiplier": 3, "volume_multiplier": 7,
                           "max_prefix_difference": 0., "passed": True}
    output = {"markets": results, "reconciled_curves": total,
              "all_checks_passed": total == 448}
    VALIDATION.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
    return output


if __name__ == "__main__":
    main()
