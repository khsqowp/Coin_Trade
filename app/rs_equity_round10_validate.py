"""Reconcile Round10 stock curves and perturb all inputs after a fixed cutoff."""
from __future__ import annotations

import copy
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from app.crypto_round10_research import configs
from app.rs_equity_round10_transfer import (
    OUT, ROOT, _prepare, _run_one, _stock_frames,
)
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import load_equity_panel

VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round10_prefix_validation.json"


def _alter_future(panel, frames, cutoff: pd.Timestamp):
    altered_frames = {}
    for symbol, frame in frames.items():
        x = frame.copy()
        future = x.index > cutoff
        x.loc[future, ["Open", "High", "Low", "Close"]] *= 3.0
        x.loc[future, "Volume"] *= 7.0
        altered_frames[symbol] = x
    data = copy.deepcopy(panel.D)
    future = panel.dates > cutoff
    for field in ("o", "h", "l", "c"):
        data["d"][field][future] *= 3.0
    data["d"]["v"][future] *= 7.0
    changed = replace(panel, D=data, proxy_close=panel.proxy_close.copy())
    changed.proxy_close[future] *= 3.0
    return changed, altered_frames


def validate():
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    rows_total = prefix_curve_checks = feature_checks = 0
    results = {}
    for market in ("US", "KR"):
        panel = load_equity_panel(market)
        dates = pd.DatetimeIndex(saved["markets"][market]["dates"])
        assert dates[0] >= pd.Timestamp("2019-01-01")
        frames = _stock_frames(panel)
        prepped, prepared, regime = _prepare(panel, frames)
        sim_dates = pd.DatetimeIndex(prepared["volume"][0])
        assert sim_dates.equals(dates), (market, sim_dates[[0, -1]], dates[[0, -1]])
        cutoff = dates[len(dates) // 2]
        cut = int(dates.searchsorted(cutoff, side="right"))
        changed_panel, changed_frames = _alter_future(panel, frames, cutoff)
        changed_prepped, changed_prepared, changed_regime = _prepare(changed_panel, changed_frames)
        pd.testing.assert_frame_equal(regime.iloc[:cut], changed_regime.iloc[:cut])
        market_feature_checks = 0
        for family in prepped:
            assert prepped[family].keys() == changed_prepped[family].keys()
            for symbol in prepped[family]:
                left = prepped[family][symbol]
                right = changed_prepped[family][symbol]
                pd.testing.assert_frame_equal(left.loc[:cutoff], right.loc[:cutoff])
                feature_checks += 1
                market_feature_checks += 1

        rows = saved["markets"][market]["rows"]
        assert len(rows) == 272
        market_prefix_checks = 0
        source_rows = [config for _, _, group in configs() for config in group]
        assert len(source_rows) == 136
        cost_cases = _costs(panel)
        for config in source_rows:
            for cost in cost_cases:
                row = next(x for x in rows if x["config"] == config and x["cost_case"] == cost[0])
                result = _run_one(changed_panel, config, changed_prepped,
                                  changed_prepared, changed_regime, cost)
                np.testing.assert_allclose(row["daily_equity"][:cut],
                                           result["daily_equity"][:cut], rtol=0, atol=1e-12)
                curve = np.asarray(row["daily_equity"], dtype=float)
                assert len(curve) == len(dates) == row["daily_date_count"]
                assert np.isfinite(curve).all() and np.all(curve > 0)
                years = (dates[-1] - dates[0]).days / 365.25
                cagr = (curve[-1] ** (1 / years) - 1) * 100
                mdd = ((np.maximum.accumulate(curve) - curve) /
                       np.maximum.accumulate(curve)).max() * 100
                daily = pd.Series(curve, index=dates).pct_change().dropna()
                sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() else 0.0
                np.testing.assert_allclose(
                    [cagr, mdd, sharpe, curve[-1]],
                    [row["metrics"]["cagr"], row["metrics"]["mdd"],
                     row["metrics"]["sharpe"], row["metrics"]["final"]],
                    rtol=0, atol=2e-8,
                )
                prefix_curve_checks += 1
                market_prefix_checks += 1
                rows_total += 1
        results[market] = {
            "rows": len(rows), "cutoff": str(cutoff.date()),
            "future_ohlc_multiplier": 3, "future_volume_multiplier": 7,
            "feature_symbol_family_prefix_checks": market_feature_checks,
            "account_curve_prefix_checks": market_prefix_checks,
            "max_prefix_curve_difference": 0.0,
            "passed": True,
        }
    result = {
        "markets": results, "result_rows_reconciled": rows_total,
        "account_curve_prefix_checks": prefix_curve_checks,
        "signal_feature_prefix_checks": feature_checks,
        "all_checks_passed": rows_total == 544 and prefix_curve_checks == 544,
    }
    VALIDATION.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    validate()
