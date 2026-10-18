"""Transfer Round3's full declared breaker/volatility/loose policy set."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.crypto_round3_research import NAMES, prep as source_prep
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_transfer import EquityPanel, load_equity_panel
from app.round13_costs import simulate_cost_portfolio
from app.technical_portfolio_engine import prepare

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round3_policy_transfer.json"
START = pd.Timestamp("2019-01-01")


def stock_frames(panel: EquityPanel):
    frames = {}
    for j, symbol in enumerate(panel.symbols):
        frame = pd.DataFrame({"Open": panel.o[:, j], "High": panel.h[:, j],
                              "Low": panel.l[:, j], "Close": panel.c[:, j],
                              "Volume": panel.v[:, j]}, index=panel.dates)
        valid = np.isfinite(frame[["Open", "High", "Low", "Close", "Volume"]]).all(axis=1)
        valid &= (frame[["Open", "High", "Low", "Close"]] > 0).all(axis=1)
        valid &= frame.Volume > 0
        frame.loc[~panel.tradable[:, j], "Open"] = np.nan
        frames[symbol] = frame.loc[valid & (frame.index >= START)]
    return frames


def market_trend(panel: EquityPanel):
    proxy = pd.Series(panel.proxy_close, index=panel.dates)
    return (proxy > proxy.rolling(50, min_periods=50).mean()).fillna(False).to_dict()


def source_rows():
    rows = []
    base_names = ["volume_spike_cap5", "heikin_ashi", "frvp"]
    for name in base_names:
        rows.append({"kind": "baseline", "name": name, "config": {}})
        for threshold in (.15, .20, .25, .30):
            for mode, days in (("cooldown", 20), ("cooldown", 40),
                               ("cooldown", 60), ("btc_sma50", 20)):
                rows.append({"kind": "breaker", "name": name,
                             "config": {"dd_trigger": threshold,
                                        "resume_mode": mode, "cooldown_days": days}})
        rows.append({"kind": "volatility", "name": name,
                     "config": {"sizing": "inverse_vol", "target_vol": .40,
                                "weight_cap": .25}})
    for name in ("heikin_ashi_volume_spike_loose", "frvp_volume_spike_loose"):
        rows.append({"kind": "loose_hybrid", "name": name, "config": {}})
    if len(rows) != 56 or sum(x["kind"] != "baseline" for x in rows) != 53:
        raise AssertionError("Round3 expected 53 declared experiments plus 3 baselines")
    return rows


def prepare_signals(panel: EquityPanel, frames=None):
    frames = frames if frames is not None else stock_frames(panel)
    prepared = {name: source_prep(name, frames) for name in NAMES + [
        "heikin_ashi_volume_spike_loose", "frvp_volume_spike_loose"]}
    arrays = {name: prepare(book) for name, book in prepared.items()}
    return prepared, arrays


def run_one(panel, prepared, arrays, trend, row, cost):
    book = prepared[row["name"]]
    cost_name, fee, slip, tax = cost
    keys = arrays[row["name"]][1]
    slip = np.asarray(slip, dtype=float)
    if slip.ndim:
        slip = slip[[panel.symbols.index(symbol) for symbol in keys]]
    kwargs = {"top_k": 8, "hold_days": 20, **row["config"]}
    if kwargs.get("resume_mode") == "btc_sma50":
        kwargs["btc_resume"] = trend
    result = simulate_cost_portfolio(book, prepared=arrays[row["name"]],
                                     fee_pct_one_way=fee, slippage=slip,
                                     sell_tax=tax, return_trace=True, **kwargs)
    trace = result.pop("trace")
    dates = [str(pd.Timestamp(item["date"]).date()) for item in trace]
    curve = [float(item["closing"]) for item in trace]
    metrics = {key: (int(result[key]) if key in ("trades", "stopped", "breaker_events", "breaker_resumes", "blocked_days")
                     else float(result[key]) if isinstance(result[key], (int, float, np.number))
                     else result[key])
               for key in ("cagr", "mdd", "sharpe", "trades", "stopped", "final", "years",
                           "breaker_events", "breaker_resumes", "blocked_days", "breaker_paused_final")}
    return {"kind": row["kind"], "name": row["name"], "config": row["config"],
            "cost_case": cost_name, "metrics": metrics,
            "signal_count": int(sum(frame.SIGNAL.sum() for frame in book.values())),
            "daily_dates": dates, "daily_equity": curve,
            "daily_date_count": len(dates)}


def run_market(market):
    panel = load_equity_panel(market)
    frames = stock_frames(panel)
    prepared, arrays = prepare_signals(panel, frames)
    trend = market_trend(panel)
    specs = source_rows()
    rows = []
    for i, spec in enumerate(specs, 1):
        for cost in _costs(panel):
            rows.append(run_one(panel, prepared, arrays, trend, spec, cost))
        if i % 10 == 0:
            print(f"{market}: {i}/56 Round3 cases", flush=True)
    return {"market": market, "symbols": panel.symbols,
            "dates": [str(x.date()) for x in arrays["volume_spike_cap5"][0]],
            "source_experiment_count": 53, "baseline_count": 3,
            "row_count": len(rows), "rows": rows,
            "definition": "Round3 exact declared portfolio cases on daily equities; BTC resume signal mapped to equal-weight equity proxy SMA50."}


def run():
    payload = {"markets": {market: run_market(market) for market in ("US", "KR")}}
    payload["row_count"] = sum(x["row_count"] for x in payload["markets"].values())
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({m: x["row_count"] for m, x in payload["markets"].items()}))
    return payload


if __name__ == "__main__":
    run()
