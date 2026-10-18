"""Validate Round16 equity proxy curves and causal signal prefixes."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from app.rs_equity_round13_runner import market_context
from app.rs_equity_round16_transfer import prepare_round16, round16_configs
from app.rs_equity_transfer import load_equity_panel


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/research/equity_transfer_2026-10"
RUN = BASE / "full_runs/round16_liquidation_proxy_transfer.json"
PREFIX = BASE / "full_runs/round16_prefix_validation.json"
SUMMARY = BASE / "full_runs/round16_summary.json"


def metric_check(row: dict, trading_dates: list[str]) -> dict:
    curve = np.asarray(row["daily_equity"], dtype=float)
    metrics = row["metrics"]
    dates = pd.DatetimeIndex(trading_dates)
    if len(curve) != len(dates) or len(curve) != row["daily_date_count"]:
        raise AssertionError("curve/date length mismatch")
    if not np.isfinite(curve).all() or (curve <= 0).any():
        raise AssertionError("curve contains non-finite/non-positive equity")
    years = (dates[-1] - dates[0]).days / 365.25
    cagr = (curve[-1] / curve[0]) ** (1 / years) - 1
    dd = curve / np.maximum.accumulate(curve) - 1
    mdd = -float(dd.min())
    returns = curve[1:] / curve[:-1] - 1
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(365.0)) if returns.std(ddof=1) else 0.0
    actual = np.array([metrics["cagr"] / 100, metrics["mdd"] / 100, metrics["sharpe"]])
    expected = np.array([cagr, mdd, sharpe])
    np.testing.assert_allclose(actual, expected, rtol=0, atol=2e-8)
    return {"rows": 1, "max_abs_metric_error": float(np.max(np.abs(actual - expected)))}


def prefix_check(market: str, configs: list[dict]) -> dict:
    panel = load_equity_panel(market)
    cutoff = pd.Timestamp("2024-02-22" if market == "US" else "2024-02-06")
    cut = int(panel.dates.searchsorted(cutoff, side="right"))
    rng = np.random.default_rng(20261026 if market == "US" else 20261027)
    shock = np.exp(rng.normal(0, 0.35, size=panel.c[cut:].shape))
    altered = replace(
        panel, o=panel.o.copy(), h=panel.h.copy(), l=panel.l.copy(),
        c=panel.c.copy(), v=panel.v.copy(), proxy_close=panel.proxy_close.copy(),
    )
    for key in ("o", "h", "l", "c"):
        getattr(altered, key)[cut:] *= shock
    altered.v[cut:] *= 7
    altered.proxy_close[cut:] *= 3
    dates = panel.dates[int(panel.dates.searchsorted(pd.Timestamp("2019-01-01"))):]
    fields = ("SIGNAL", "VOL_RATIO", "EXIT_SIGNAL")
    original_cache, altered_cache = {}, {}
    checked = 0
    for config in configs:
        left = prepare_round16(panel, config, dates, cache=original_cache)
        right = prepare_round16(altered, config, dates, cache=altered_cache)
        for symbol in left:
            for field in fields:
                if field not in left[symbol] and field not in right[symbol]:
                    continue
                a = left[symbol].get(field, pd.Series(False, index=left[symbol].index)).loc[:cutoff].to_numpy()
                b = right[symbol].get(field, pd.Series(False, index=right[symbol].index)).loc[:cutoff].to_numpy()
                np.testing.assert_array_equal(a, b)
        checked += 1
        if checked % 50 == 0:
            print(f"[{market}] prefix {checked}/{len(configs)}", flush=True)
    return {
        "market": market, "config_count": checked, "symbols": len(panel.symbols),
        "cutoff": str(cutoff.date()), "future_price_log_sigma": 0.35,
        "future_volume_multiplier": 7, "future_proxy_multiplier": 3,
        "fields": list(fields), "changed_prefix_values": 0, "passed": checked == len(configs),
    }


def main() -> None:
    run = json.loads(RUN.read_text(encoding="utf-8"))
    configs = round16_configs()
    if run["source_config_count"] != len(configs) or len(configs) != 397:
        raise AssertionError("source config count mismatch")
    summaries = {}
    total_checked = 0
    for market, data in run["markets"].items():
        if not data.get("complete") or data["row_count"] != 794 or len(data["rows"]) != 794:
            raise AssertionError(f"incomplete market run: {market}")
        rows = data["rows"]
        for row in rows:
            metric_check(row, data["trading_dates"])
        total_checked += len(rows)
        groups = {}
        for row in rows:
            groups.setdefault((row["cost_case"], row["config"]["variant"]), []).append(row)
        market_summary = {}
        for (cost, variant), group in groups.items():
            cagr = np.array([r["metrics"]["cagr"] for r in group])
            mdd = np.array([r["metrics"]["mdd"] for r in group])
            sharpe = np.array([r["metrics"]["sharpe"] for r in group])
            market_summary[f"{cost}|{variant}"] = {
                "n": len(group), "median_cagr_pct": float(np.median(cagr)),
                "median_mdd_pct": float(np.median(mdd)),
                "positive_cagr_pct": float(np.mean(cagr > 0) * 100),
                "median_sharpe": float(np.median(sharpe)),
                "best_ex_post": max(group, key=lambda r: r["metrics"]["cagr"])["config"]["phase"],
                "best_cagr_pct": float(cagr.max()),
                "best_mdd_pct": float(mdd[np.argmax(cagr)]),
            }
        summaries[market] = market_summary
    prefix = [prefix_check(market, configs) for market in ("US", "KR")]
    prefix_payload = {
        "source_config_count": len(configs),
        "method": "post-cutoff lognormal OHLC shock sigma 0.35, volume x7 and equal-weight proxy x3; compare causal entry/exit signals and rank field through cutoff",
        "markets": prefix, "passed": all(x["passed"] for x in prefix),
    }
    summary_payload = {
        "source_config_count": len(configs), "rows_validated": total_checked,
        "metric_curve_reconciliation": "passed; calendar CAGR, peak-to-trough MDD, daily Sharpe annualized by sqrt(365)",
        "prefix_validation": prefix_payload["passed"], "markets": summaries,
        "interpretation": "Ex-post grid summaries only; configuration maxima are selection-biased, and liquidation proximity is a synthetic OHLC proxy rather than observed equity liquidations.",
    }
    PREFIX.write_text(json.dumps(prefix_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows_validated": total_checked, "prefix_passed": prefix_payload["passed"], "markets": summaries}, ensure_ascii=False))


if __name__ == "__main__":
    main()
