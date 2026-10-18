"""Reconcile Round4 trade ledgers/curves and future-prefix invariance."""
from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd

from app.crypto_round3_research import prep as source_prep
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_round3_transfer import market_trend, stock_frames
from app.rs_equity_round4_transfer import OUT, ROOT, _execute, winners
from app.rs_equity_transfer import load_equity_panel

VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round4_prefix_validation.json"


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


def validate():
    saved = json.loads(OUT.read_text(encoding="utf-8"))
    configs = winners()
    all_curves = all_features = 0
    markets = {}
    for market in ("US", "KR"):
        panel = load_equity_panel(market)
        data = saved["markets"][market]
        dates = pd.DatetimeIndex(data["full_winners"][0]["daily_dates"])
        cutoff = dates[len(dates) // 2]
        base_frames = stock_frames(panel)
        changed_panel = shock(panel, cutoff)
        changed_frames = stock_frames(changed_panel)
        feature_count = 0
        families = {name for item in configs for name in (item["name"],)}
        for name in families:
            base = source_prep(name, base_frames)
            changed = source_prep(name, changed_frames)
            assert base.keys() == changed.keys()
            for symbol in base:
                pd.testing.assert_frame_equal(base[symbol].loc[:cutoff], changed[symbol].loc[:cutoff])
                feature_count += 1
        base_trend = market_trend(panel)
        altered_trend = market_trend(changed_panel)
        np.testing.assert_array_equal(pd.Series(base_trend).loc[:cutoff].to_numpy(),
                                      pd.Series(altered_trend).loc[:cutoff].to_numpy())
        curve_count = 0
        for winner in configs:
            name, config = winner["name"], winner["config"]
            for cost in _costs(panel):
                row = next(r for r in data["full_winners"]
                           if r["name"] == name and r["config"] == config and r["cost_case"] == cost[0])
                altered = _execute(changed_panel, changed_frames, name, config,
                                   altered_trend, cost, keep_ledger=True)
                actual_dates = pd.DatetimeIndex(row["daily_dates"])
                prefix_n = int((actual_dates <= cutoff).sum())
                np.testing.assert_allclose(row["daily_equity"][:prefix_n],
                                           altered["daily_equity"][:prefix_n], rtol=0, atol=1e-12)
                curve = np.asarray(row["daily_equity"], dtype=float)
                assert np.isfinite(curve).all() and np.all(curve > 0)
                contributions = np.zeros((len(row["trades"]), len(curve)), dtype=float)
                for i, trade in enumerate(row["trades"]):
                    close = base_frames[trade["symbol"]].Close.reindex(actual_dates).ffill().to_numpy(float)
                    entry, exit_ = int(trade["entry"]), int(trade["exit"])
                    contributions[i, entry:exit_] = trade["qty"] * close[entry:exit_] - trade["cost"]
                    contributions[i, exit_:] = trade["pnl"]
                np.testing.assert_allclose(1 + contributions.sum(axis=0), curve,
                                           rtol=1e-9, atol=1e-8)
                years = (actual_dates[-1] - actual_dates[0]).days / 365.25
                cagr = (curve[-1] ** (1 / years) - 1) * 100
                mdd = ((np.maximum.accumulate(curve) - curve) /
                       np.maximum.accumulate(curve)).max() * 100
                daily = pd.Series(curve, index=actual_dates).pct_change().dropna()
                sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() else 0.
                np.testing.assert_allclose([cagr, mdd, sharpe, curve[-1], len(row["trades"])],
                                           [row["metrics"][k] for k in ("cagr", "mdd", "sharpe", "final", "trades")],
                                           rtol=0, atol=2e-8)
                curve_count += 1
        markets[market] = {"cutoff": str(cutoff.date()), "full_curve_prefix_checks": curve_count,
                           "signal_symbol_prefix_checks": feature_count,
                           "future_ohlc_multiplier": 3, "future_volume_multiplier": 7,
                           "max_prefix_difference": 0., "passed": True}
        all_curves += curve_count
        all_features += feature_count
    output = {"markets": markets, "full_curve_prefix_checks": all_curves,
              "signal_symbol_prefix_checks": all_features,
              "all_checks_passed": all_curves == 20}
    VALIDATION.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))
    return output


if __name__ == "__main__":
    validate()
