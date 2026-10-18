"""Validate saved causal equity peer-pair outputs and future-prefix invariance."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.rs_equity_peer_pairs import (
    ENTRY_Z, EXIT_Z, OUT, STOP_Z, _point_in_time_peer_and_z, make_pair_targets,
)
from app.rs_equity_transfer import load_equity_panel

VALIDATION = OUT.with_name("equity_peer_pairs_validation.json")


def validate() -> dict:
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    market_results = {}
    for market in ("US", "KR"):
        panel = load_equity_panel(market)
        data = saved["markets"][market]
        assert len(data["rows"]) == 144
        assert len({(r["entry_z"], r["exit_z"], r["stop_z"], r["cadence"], r["cost_case"])
                    for r in data["rows"]}) == 144
        dates = pd.DatetimeIndex(data["dates"])
        cutoff = dates[len(dates) // 2]
        cut = int(panel.dates.searchsorted(cutoff, side="right"))
        altered = panel.c.copy()
        rng = np.random.default_rng(20261014 + (market == "KR"))
        altered[cut:] *= np.exp(rng.normal(0, .45, altered[cut:].shape))
        base_peers, base_z = _point_in_time_peer_and_z(panel.c)
        changed_peers, changed_z = _point_in_time_peer_and_z(altered)
        signal_configs = 0
        max_curve_metric_error = 0.0
        for entry in ENTRY_Z:
            for exit_ in EXIT_Z:
                for stop in STOP_Z:
                    original_targets, _ = make_pair_targets(
                        panel, entry, exit_, stop, peer_data=(base_peers, base_z))
                    # Compare pre-cutoff peer/z inputs directly and portfolio targets.
                    np.testing.assert_array_equal(base_peers[:cut], changed_peers[:cut])
                    np.testing.assert_allclose(base_z[:cut], changed_z[:cut], rtol=0, atol=0, equal_nan=True)
                    altered_panel = type("Panel", (), {
                        "c": altered, "eligible": panel.eligible, "tradable": panel.tradable,
                    })()
                    changed_targets, _ = make_pair_targets(
                        altered_panel, entry, exit_, stop,
                        peer_data=(changed_peers, changed_z))
                    np.testing.assert_allclose(original_targets[:cut], changed_targets[:cut], rtol=0, atol=0)
                    assert np.max(np.abs(original_targets.sum(axis=1))) <= 1e-12
                    assert np.max(np.abs(original_targets).sum(axis=1)) <= 1.0 + 1e-12
                    signal_configs += 1
        # Recompute every reported metric from the stored account-equity curve.
        for row in data["rows"]:
            curve = np.asarray(row["daily_equity"], float)
            row_dates = pd.DatetimeIndex(row["daily_dates"])
            assert len(curve) == len(row_dates) == len(dates)
            assert np.isfinite(curve).all() and np.all(curve > 0)
            rets = np.r_[0.0, curve[1:] / curve[:-1] - 1]
            years = (row_dates[-1] - row_dates[0]).days / 365.25
            cagr = (curve[-1] / curve[0]) ** (1 / years) - 1
            mdd = float(np.max(1 - curve / np.maximum.accumulate(curve)))
            sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else 0.0
            reported = row["metrics"]
            errors = [abs(cagr - reported["cagr"]), abs(mdd - reported["mdd"]),
                      abs(sharpe - reported["sharpe"])]
            max_curve_metric_error = max(max_curve_metric_error, *errors)
            np.testing.assert_allclose([cagr, mdd, sharpe],
                                       [reported["cagr"], reported["mdd"], reported["sharpe"]],
                                       rtol=0, atol=2e-8)
        market_results[market] = {
            "rows": len(data["rows"]), "signal_configs_future_prefix_checked": signal_configs,
            "cutoff": str(cutoff.date()), "future_log_price_sigma": .45,
            "max_saved_curve_metric_error": max_curve_metric_error,
            "passed": True,
        }
    result = {
        "markets": market_results,
        "result_rows": sum(x["rows"] for x in market_results.values()),
        "signal_future_prefix_checks": sum(x["signal_configs_future_prefix_checked"] for x in market_results.values()),
        "saved_curves_reconciled": all(x["max_saved_curve_metric_error"] <= 2e-8 for x in market_results.values()),
        "all_checks_passed": all(x["passed"] for x in market_results.values()),
    }
    VALIDATION.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False))
