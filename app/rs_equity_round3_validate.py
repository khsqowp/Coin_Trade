"""Reconcile Round3 equity curves and assert future-prefix invariance."""
from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd

from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_round3_transfer import (
    OUT, ROOT, market_trend, prepare_signals, run_one, source_rows, stock_frames,
)
from app.rs_equity_transfer import load_equity_panel

VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round3_prefix_validation.json"


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
    result = {}
    total_rows = total_features = 0
    for market in ("US", "KR"):
        panel = load_equity_panel(market)
        market_result = saved["markets"][market]
        dates = pd.DatetimeIndex(market_result["dates"])
        cutoff = dates[len(dates) // 2]
        frames = stock_frames(panel)
        base, base_arrays = prepare_signals(panel, frames)
        changed_panel = shock(panel, cutoff)
        changed_frames = stock_frames(changed_panel)
        changed, changed_arrays = prepare_signals(changed_panel, changed_frames)
        feature_checks = 0
        for name in base:
            assert base[name].keys() == changed[name].keys()
            for symbol in base[name]:
                pd.testing.assert_frame_equal(base[name][symbol].loc[:cutoff],
                                              changed[name][symbol].loc[:cutoff])
                feature_checks += 1
        trend = market_trend(panel)
        changed_trend = market_trend(changed_panel)
        np.testing.assert_array_equal(
            pd.Series(trend).loc[:cutoff].to_numpy(),
            pd.Series(changed_trend).loc[:cutoff].to_numpy(),
        )
        specs = source_rows()
        assert len(specs) == 56 and len(market_result["rows"]) == 112
        curve_checks = 0
        for spec in specs:
            for cost in _costs(panel):
                row = next(x for x in market_result["rows"]
                           if x["kind"] == spec["kind"] and x["name"] == spec["name"]
                           and x["config"] == spec["config"] and x["cost_case"] == cost[0])
                altered = run_one(changed_panel, changed, changed_arrays,
                                  changed_trend, spec, cost)
                dates_row = pd.DatetimeIndex(row["daily_dates"])
                assert row["daily_dates"] == market_result["dates"]
                n_prefix = int((dates_row <= cutoff).sum())
                np.testing.assert_allclose(row["daily_equity"][:n_prefix],
                                           altered["daily_equity"][:n_prefix],
                                           rtol=0, atol=1e-12)
                curve = np.asarray(row["daily_equity"], dtype=float)
                assert np.isfinite(curve).all() and np.all(curve > 0)
                years = (dates_row[-1] - dates_row[0]).days / 365.25
                cagr = (curve[-1] ** (1 / years) - 1) * 100
                mdd = ((np.maximum.accumulate(curve) - curve) /
                       np.maximum.accumulate(curve)).max() * 100
                daily = pd.Series(curve, index=dates_row).pct_change().dropna()
                sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() else 0.
                np.testing.assert_allclose([cagr, mdd, sharpe, curve[-1]],
                                           [row["metrics"][k] for k in ("cagr", "mdd", "sharpe", "final")],
                                           rtol=0, atol=2e-8)
                curve_checks += 1
        result[market] = {"cutoff": str(cutoff.date()), "saved_curve_checks": curve_checks,
                          "feature_symbol_checks": feature_checks,
                          "future_ohlc_multiplier": 3, "future_volume_multiplier": 7,
                          "max_prefix_curve_difference": 0., "passed": True}
        total_rows += curve_checks
        total_features += feature_checks
    output = {"markets": result, "reconciled_curves": total_rows,
              "feature_prefix_checks": total_features,
              "all_checks_passed": total_rows == 224}
    VALIDATION.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
    return output


if __name__ == "__main__":
    main()
