"""Transfer Round4 winner robustness, trade-ledger, period and sensitivity tests."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from app.crypto_round3_research import PATH as ROUND3_SOURCE, prep as source_prep
from app.rs_equity_round12_13_portfolio import _costs
from app.rs_equity_round3_transfer import market_trend, stock_frames
from app.rs_equity_transfer import load_equity_panel
from app.round13_costs import simulate_cost_portfolio
from app.technical_portfolio_engine import prepare

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round4_robustness_transfer.json"
VALIDATION = ROOT / "docs/research/equity_transfer_2026-10/full_runs/round4_prefix_validation.json"
PERIODS = [("2019-09-08", "2022-12-31"), ("2023-01-01", "2026-10-05")]
PERIODS += [(f"{year}-09-08", f"{year + 2}-09-07") for year in range(2019, 2024)]
PERIODS += [("2024-10-06", "2026-10-05")]


def winners():
    source = json.loads(ROUND3_SOURCE.read_text(encoding="utf-8"))
    rows = source["winners"]
    expected = [("heikin_ashi", t) for t in (.15, .20, .25, .30)] + [("frvp", .20)]
    actual = [(r["name"], r["config"]["dd_trigger"]) for r in rows]
    if actual != expected:
        raise AssertionError(f"Round4 source winner definition changed: {actual}")
    return rows


def _prepare(name, frames):
    book = source_prep(name, frames)
    return book, prepare(book)


def _execute(panel, frames, name, config, trend, cost, *, keep_ledger=False):
    book, arrays = _prepare(name, frames)
    cost_name, fee, slip, tax = cost
    keys = arrays[1]
    slip = np.asarray(slip, dtype=float)
    if slip.ndim:
        slip = slip[[panel.symbols.index(symbol) for symbol in keys]]
    kwargs = dict(config)
    if kwargs.get("resume_mode") == "btc_sma50":
        kwargs["btc_resume"] = trend
    result = simulate_cost_portfolio(book, prepared=arrays, fee_pct_one_way=fee,
                                     slippage=slip, sell_tax=tax,
                                     return_trace=keep_ledger, **kwargs)
    records = result.pop("records", [])
    trace = result.pop("trace", [])
    breaker_log = result.pop("breaker_log", [])
    metric_keys = ("cagr", "mdd", "sharpe", "trades", "stopped", "tp_hit", "final", "start", "end", "years",
                   "breaker_events", "breaker_resumes", "blocked_days", "breaker_paused_final", "paused_age_final")
    row = {"metrics": {key: (bool(result[key]) if isinstance(result[key], (bool, np.bool_)) else
                             int(result[key]) if key in ("trades", "stopped", "tp_hit", "breaker_events", "breaker_resumes", "blocked_days", "paused_age_final") else
                             float(result[key]) if isinstance(result[key], (int, float, np.number)) else result[key])
                       for key in metric_keys if key in result},
           "cost_case": cost_name, "daily_date_count": len(arrays[0])}
    if keep_ledger:
        dates = pd.DatetimeIndex(pd.to_datetime([x["date"] for x in trace]))
        curve = np.asarray([x["closing"] for x in trace], dtype=float)
        trade_records = []
        contributions = np.zeros((len(records), len(curve)), dtype=float)
        for j, trade in enumerate(records):
            entry, exit_ = int(trade["entry"]), int(trade["exit"])
            close = book[trade["symbol"]].Close.reindex(dates).ffill().to_numpy(float)
            contributions[j, entry:exit_] = trade["qty"] * close[entry:exit_] - trade["cost"]
            contributions[j, exit_:] = trade["pnl"]
            trade_records.append({k: (float(v) if isinstance(v, (int, float, np.number)) else v)
                                  for k, v in trade.items()})
        if records:
            np.testing.assert_allclose(1 + contributions.sum(axis=0), curve, rtol=1e-9, atol=1e-8)
            assert abs(sum(t["pnl"] for t in records) - (row["metrics"]["final"] - 1)) < 1e-7
        row.update(daily_dates=[str(x.date()) for x in dates],
                   daily_equity=curve.tolist(), trades=trade_records,
                   trade_contributions=contributions.tolist(),
                   breaker_log=breaker_log,
                   trace=[{"date": str(x["date"]), "closing": float(x["closing"]),
                           "paused": bool(x["paused"]), "positions": int(x["positions"])}
                          for x in trace])
    return row


def _concentration(records):
    ranked = sorted(records, key=lambda t: (-t["pnl"], t["id"]))
    positive = sum(max(0., t["pnl"]) for t in records)
    net = sum(t["pnl"] for t in records)
    return {str(n): {"pnl": sum(t["pnl"] for t in ranked[:n]),
                     "positive_pct": sum(t["pnl"] for t in ranked[:n]) / positive * 100 if positive else 0.,
                     "net_pct": sum(t["pnl"] for t in ranked[:n]) / net * 100 if abs(net) > 1e-12 else None}
            for n in (10, 20)}


def _flapping(row):
    events = row["breaker_log"]
    resumes = [i for i, event in enumerate(events) if event["kind"] == "resume"]
    gaps = []
    censored = 0
    for idx in resumes:
        nxt = next((e for e in events[idx + 1:] if e["kind"] == "pause"), None)
        gap = None if nxt is None else int(nxt["index"] - events[idx]["index"])
        gaps.append(gap)
        censored += int(gap is None and len(row["trace"]) - 1 - events[idx]["index"] < 5)
    return {"pauses": row["metrics"]["breaker_events"],
            "resumes": row["metrics"]["breaker_resumes"], "censored_5d": censored,
            "within": {str(n): {"count": sum(g is not None and g <= n for g in gaps),
                                "pct": sum(g is not None and g <= n for g in gaps) / len(gaps) * 100 if gaps else 0.}
                       for n in (1, 3, 5)}}


def _metrics(curve, dates, trades):
    equity = pd.Series(curve, index=dates, dtype=float)
    years = (dates[-1] - dates[0]).days / 365.25
    daily = equity.pct_change().dropna()
    insolvent = bool((equity <= 0).any())
    return {"cagr": None if insolvent else float((equity.iloc[-1] ** (1 / years) - 1) * 100),
            "mdd": None if insolvent else float(((equity.cummax() - equity) / equity.cummax()).max() * 100),
            "diagnostic_raw_drawdown": float(((equity.cummax() - equity) / equity.cummax()).max() * 100),
            "sharpe": None if insolvent else (float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() else 0.),
            "minimum_equity": float(equity.min()), "final": float(equity.iloc[-1]),
            "trades": int(trades), "years": years, "insolvent": insolvent}


def _leave_out(row, n_values=(5, 10, 20, 50)):
    curve = np.asarray(row["daily_equity"], dtype=float)
    dates = pd.DatetimeIndex(row["daily_dates"])
    contributions = np.asarray(row["trade_contributions"], dtype=float)
    ranking = sorted(row["trades"], key=lambda t: (-t["pnl"], t["id"]))
    output = []
    for n in n_values:
        removed = [t["id"] for t in ranking[:n]]
        idx = [i for i, t in enumerate(row["trades"]) if t["id"] in removed]
        reduced = curve - contributions[idx].sum(axis=0) if idx else curve.copy()
        previous = np.r_[1., curve[:-1]]
        retained_daily = np.diff(reduced, prepend=1.) / previous
        normalized = np.cumprod(1 + retained_daily)
        output.append({"n": n, "actual_removed": len(idx), "removed_trade_ids": removed,
                       "fixed_dollar_metrics": _metrics(reduced, dates, len(row["trades"]) - len(idx)),
                       "normalized_metrics": _metrics(normalized, dates, len(row["trades"]) - len(idx)),
                       "fixed_dollar_equity": reduced.tolist(),
                       "normalized_equity": normalized.tolist()})
    return output


def _symbol_audit(row, frames, panel, config, trend, cost):
    grouped = defaultdict(lambda: {"trades": 0, "pnl": 0.})
    for trade in row["trades"]:
        grouped[trade["symbol"]]["trades"] += 1
        grouped[trade["symbol"]]["pnl"] += trade["pnl"]
    symbols = [{"symbol": s, **grouped[s]} for s in frames]
    symbols.sort(key=lambda x: (-x["pnl"], x["symbol"]))
    gross_net = row["metrics"]["final"] - 1
    top = symbols[:5]
    share = sum(x["pnl"] for x in top) / gross_net * 100 if abs(gross_net) > 1e-12 else None
    top_count = sorted(symbols, key=lambda x: (-x["trades"], x["symbol"]))[:5]
    out = {"symbols": symbols, "top5_profit": [x["symbol"] for x in top],
           "top5_net_pct": share,
           "top5_trade_pct": sum(x["trades"] for x in top) / max(len(row["trades"]), 1) * 100,
           "top5_by_trade_count": [x["symbol"] for x in top_count],
           "top5_count_pct": sum(x["trades"] for x in top_count) / max(len(row["trades"]), 1) * 100}
    if share is not None and share >= 50:
        excluded = set(x["symbol"] for x in top)
        restricted = {s: f for s, f in frames.items() if s not in excluded}
        out["exclude_top5_metrics"] = _execute(panel, restricted, "heikin_ashi", config,
                                                 trend, cost)["metrics"]
    return out


def run_market(market):
    panel = load_equity_panel(market)
    frames = stock_frames(panel)
    trend = market_trend(panel)
    cost_rows = _costs(panel)
    source_winners = winners()
    full_rows, period_rows, sensitivity_rows = [], [], []
    for winner_index, winner in enumerate(source_winners, 1):
        name, config = winner["name"], winner["config"].copy()
        for cost in cost_rows:
            full = _execute(panel, frames, name, config, trend, cost, keep_ledger=True)
            full["winner_index"] = winner_index
            full["name"] = name
            full["config"] = winner["config"]
            full["concentration"] = _concentration(full["trades"])
            if winner_index == 3 and name == "heikin_ashi":
                full["leave_top_trade_out"] = _leave_out(full)
                full["symbol_audit"] = _symbol_audit(full, frames, panel, config, trend, cost)
                full["breaker_flapping"] = _flapping(full)
            # The daily per-trade matrix is only needed to derive the saved
            # leave-out curves; retaining it for every winner bloats JSON by
            # hundreds of megabytes without adding information.
            full.pop("trade_contributions", None)
            full.pop("trace", None)
            full.pop("breaker_log", None)
            full_rows.append(full)
            for start, end in PERIODS:
                sliced_frames = {s: f.loc[start:end] for s, f in frames.items() if len(f.loc[start:end])}
                period_trend = pd.Series(panel.proxy_close, index=panel.dates).loc[start:end]
                period_trend = (period_trend > period_trend.rolling(50, min_periods=50).mean()).fillna(False).to_dict()
                period = _execute(panel, sliced_frames, name, config, period_trend, cost)
                period_rows.append({"winner_index": winner_index, "name": name,
                                    "config": winner["config"], "cost_case": cost[0],
                                    "period_start": start, "period_end": end,
                                    "period_observations": period["daily_date_count"],
                                    "metrics": period["metrics"]})
            if winner_index == 3 and name == "heikin_ashi":
                for threshold in (.15, .20, .22, .25, .27, .30):
                    sens_config = {"dd_trigger": threshold, "resume_mode": "btc_sma50", "cooldown_days": 20}
                    sensitivity = _execute(panel, frames, name, sens_config, trend, cost)
                    sensitivity_rows.append({"name": name, "threshold": threshold,
                                             "cost_case": cost[0], "metrics": sensitivity["metrics"]})
        print(f"{market}: winner {winner_index}/{len(source_winners)} completed", flush=True)
    return {"market": market, "symbols": panel.symbols,
            "date_start": str(panel.dates[0].date()), "date_end": str(panel.dates[-1].date()),
            "full_winners": full_rows, "independent_periods": period_rows,
            "sensitivity": sensitivity_rows,
            "source_period_definitions": PERIODS,
            "source_winner_count": len(source_winners),
            "full_winner_curve_count": len(full_rows)}


def run():
    payload = {"source": str(ROUND3_SOURCE), "markets": {m: run_market(m) for m in ("US", "KR")},
              "source_winners": [{"name": x["name"], "config": x["config"]} for x in winners()]}
    payload["full_curve_count"] = sum(x["full_winner_curve_count"] for x in payload["markets"].values())
    payload["period_result_count"] = sum(len(x["independent_periods"]) for x in payload["markets"].values())
    payload["sensitivity_result_count"] = sum(len(x["sensitivity"]) for x in payload["markets"].values())
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"full_curves": payload["full_curve_count"],
                      "period_results": payload["period_result_count"],
                      "sensitivity_results": payload["sensitivity_result_count"]}))
    return payload


if __name__ == "__main__":
    run()
