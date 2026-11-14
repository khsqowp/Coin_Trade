#!/usr/bin/env python3
"""Append long/short/cash comparators to an already completed run."""
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> int:
    root = Path(sys.argv[1])
    stamp = sys.argv[2]
    script = root / "run_backtest.py"
    spec = importlib.util.spec_from_file_location("backtest_module", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    result_path = root / "results" / ("strategy_results_" + stamp + ".csv")
    manifest_path = root / "results" / ("manifest_" + stamp + ".json")
    results = pd.read_csv(result_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    windows = module.WINDOWS_DAYS
    rows = []
    for symbol in manifest["symbols"]:
        funding = pd.read_csv(root / "data" / "funding" / (symbol + ".csv"))
        for interval in manifest["intervals"]:
            df = pd.read_csv(root / "data" / "klines" / (symbol + "_" + interval + ".csv"))
            max_days = manifest["data_days_by_interval"][interval]
            for name, value, params in [("buy_hold_long", 1.0, "always long"),
                                        ("buy_hold_short", -1.0, "always short"),
                                        ("cash", 0.0, "flat exposure")]:
                signal = pd.Series(value, index=df.index)
                for days in windows:
                    if days > max_days:
                        continue
                    metrics = module.eval_strategy(df, signal, funding, days, interval)
                    rows.append({"symbol": symbol, "interval": interval, "window_days": days,
                                 "strategy": name, "family": "baseline", "params": params,
                                 "fee_per_side_pct": module.FEE_PER_SIDE * 100,
                                 "slippage_per_side_pct": module.SLIPPAGE_PER_SIDE * 100,
                                 "initial_equity_usdt": module.INITIAL_EQUITY, **metrics})
    baseline = pd.DataFrame(rows)
    if len(results[results.family == "baseline"]):
        results = results[results.family != "baseline"]
    results["initial_equity_usdt"] = module.INITIAL_EQUITY
    results = pd.concat([results, baseline], ignore_index=True)
    results.to_csv(result_path, index=False, float_format="%.8g")
    usable = results.dropna(subset=["sharpe"])
    summary = (usable.groupby(["interval", "window_days", "family"], dropna=False)
               .agg(variants=("strategy", "count"), median_sharpe=("sharpe", "median"),
                    median_return_pct=("return_pct", "median"), median_cagr_pct=("cagr_pct", "median"),
                    median_max_dd_pct=("max_dd_pct", "median"), median_trades=("trades", "median"))
               .reset_index().sort_values(["interval", "window_days", "family"]))
    summary_path = root / "results" / ("family_summary_" + stamp + ".csv")
    summary.to_csv(summary_path, index=False, float_format="%.8g")
    manifest["baseline_variants"] = ["buy_hold_long", "buy_hold_short", "cash"]
    manifest["initial_equity_usdt"] = module.INITIAL_EQUITY
    manifest["strategy_variants_per_symbol_interval"] = {
        key: int(results[(results.symbol + ":" + results.interval) == key]["strategy"].nunique())
        for key in manifest["strategy_variants_per_symbol_interval"]
    }
    manifest["baseline_rows"] = len(baseline)
    manifest["results_rows"] = len(results)
    manifest["baseline_added_utc"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("baseline rows={} total rows={} variants per dataset={}".format(
        len(baseline), len(results), min(manifest["strategy_variants_per_symbol_interval"].values())))
    print("results={} summary={} manifest={}".format(result_path, summary_path, manifest_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
