"""Reconcile Round11 daily curves and check future-prefix invariance."""
from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd

from app.crypto_round11_research import configs
from app.rs_equity_round11_transfer import (
    OUT, ROOT, _run_one, prepare_signals, stock_frames,
)
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import load_equity_panel

VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round11_prefix_validation.json"


def _future_shock(panel, cutoff):
    changed = copy.copy(panel)
    d = copy.deepcopy(panel.D)
    changed.D = d
    changed.o = panel.o.copy()
    changed.h = panel.h.copy()
    changed.l = panel.l.copy()
    changed.c = panel.c.copy()
    changed.v = panel.v.copy()
    after = panel.dates > cutoff
    for key in ("o", "h", "l", "c"):
        getattr(changed, key)[after] *= 3.0
        changed.D["d"][key][after] *= 3.0
    changed.v[after] *= 7.0
    changed.D["d"]["v"][after] *= 7.0
    changed.proxy_close = panel.proxy_close.copy()
    changed.proxy_close[after] *= 3.0
    for key in ("o", "h", "l", "c"):
        d["d"][key][after] *= 3.0
    d["d"]["v"][after] *= 7.0
    changed.D = d
    return changed


def validate():
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    total_rows = total_feature_checks = total_curve_checks = 0
    results = {}
    for market in ("US", "KR"):
        panel = load_equity_panel(market)
        data = saved["markets"][market]
        dates = pd.DatetimeIndex(data["dates"])
        cutoff = dates[len(dates) // 2]
        cut = int(dates.searchsorted(cutoff, side="right"))
        frames = stock_frames(panel)
        cores = prepare_signals(frames)
        changed_panel = _future_shock(panel, cutoff)
        changed_frames = stock_frames(changed_panel)
        changed_cores = prepare_signals(changed_frames)
        feature_checks = curve_checks = 0
        for family in cores:
            assert cores[family].keys() == changed_cores[family].keys()
            for symbol in cores[family]:
                pd.testing.assert_frame_equal(
                    cores[family][symbol].loc[:cutoff],
                    changed_cores[family][symbol].loc[:cutoff],
                )
                feature_checks += 1
        configs_flat = [config for group in configs().values() for config in group]
        assert len(configs_flat) == 34 and len(data["rows"]) == 68
        for config in configs_flat:
            for cost in _costs(panel):
                row = next(item for item in data["rows"]
                           if item["config"] == config and item["cost_case"] == cost[0])
                altered = _run_one(panel=changed_panel, config=config, frames=changed_frames,
                                   cores=changed_cores, cost=cost)
                assert row["daily_dates"] == data["dates"]
                np.testing.assert_allclose(row["daily_equity"][:cut],
                                           altered["daily_equity"][:cut],
                                           rtol=0, atol=1e-12)
                equity = np.asarray(row["daily_equity"], dtype=float)
                assert len(equity) == len(dates) == row["daily_date_count"]
                assert np.isfinite(equity).all() and np.all(equity > 0)
                years = (dates[-1] - dates[0]).days / 365.25
                cagr = (equity[-1] ** (1 / years) - 1) * 100
                mdd = ((np.maximum.accumulate(equity) - equity) /
                       np.maximum.accumulate(equity)).max() * 100
                daily = pd.Series(equity, index=dates).pct_change().dropna()
                sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() else 0.0
                np.testing.assert_allclose(
                    [cagr, mdd, sharpe, equity[-1]],
                    [row["metrics"]["cagr"], row["metrics"]["mdd"],
                     row["metrics"]["sharpe"], row["metrics"]["final"]],
                    rtol=0, atol=2e-8,
                )
                curve_checks += 1
        total_rows += len(data["rows"])
        total_feature_checks += feature_checks
        total_curve_checks += curve_checks
        results[market] = {
            "rows": len(data["rows"]), "cutoff": str(cutoff.date()),
            "future_ohlc_multiplier": 3, "future_volume_multiplier": 7,
            "feature_symbol_family_prefix_checks": feature_checks,
            "account_curve_prefix_checks": curve_checks,
            "max_prefix_curve_difference": 0.0, "passed": True,
        }
    result = {
        "markets": results, "result_rows_reconciled": total_rows,
        "account_curve_prefix_checks": total_curve_checks,
        "signal_feature_prefix_checks": total_feature_checks,
        "all_checks_passed": total_rows == 136 and total_curve_checks == 136,
    }
    VALIDATION.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    validate()
