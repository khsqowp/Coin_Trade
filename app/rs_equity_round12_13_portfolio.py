"""Transfer the explicit Round12/13 account-policy groups to stock panels.

Signal definitions come from the coin research adapters; market/BTC regime
signals are mapped to a causal equal-weight stock proxy. Execution uses the
existing next-open portfolio engine with explicit US/KR trading costs.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.rs_equity_transfer import EquityPanel, load_equity_panel
from app.round12_signals import find_signals as r12_signal
from app.round13_signals import FAMILIES as R13_FAMILIES, find_signals as r13_signal, hysteresis
from app.round13_costs import simulate_cost_portfolio
from app.crypto_round12_research import phase2_groups
from app.crypto_round13_research import groups as r13_groups
from app.crypto_bucket_ensemble_research import volume_prep
from app.rs_equity_round13_transfer import (
    OnlineCompletedTradeScale,
    completed_reference_scales,
)


OUT = Path(__file__).resolve().parents[1] / "docs/research/equity_transfer_2026-10/full_runs/round12_13_policy_transfer.json"
PARTIAL = OUT.with_suffix(".partial.json")
START = pd.Timestamp("2019-01-01")


def _configs() -> list[dict[str, Any]]:
    out = []
    for title, rows in phase2_groups():
        out.extend({"phase": "R12", "policy_group": title, **row} for row in rows)
    for phase, title, rows in r13_groups():
        out.extend({"phase": f"R13-{phase}", "policy_group": title, **row} for row in rows)
    return out


def _residual(close: pd.Series, market: pd.Series) -> pd.Series:
    ret, mret = close.pct_change(fill_method=None), market.pct_change(fill_method=None).reindex(close.index)
    beta = ret.rolling(90, min_periods=60).cov(mret) / mret.rolling(90, min_periods=60).var()
    return ret - beta.shift(1) * mret


def _prepare_config(panel: EquityPanel, config: dict[str, Any], dates: pd.DatetimeIndex,
                    proxy_gate: pd.Series, breadth: pd.Series) -> dict[str, pd.DataFrame]:
    family = config["family"]
    frames: dict[str, pd.DataFrame] = {}
    market_ret = pd.Series(panel.proxy_close, index=panel.dates).pct_change(fill_method=None)
    tomorrow = pd.Series(panel.dates[1:].weekday < 5, index=panel.dates[:-1]).reindex(panel.dates, fill_value=False)
    next_market_day = pd.Series(panel.dates[1:].day, index=panel.dates[:-1]).reindex(panel.dates)
    next_month_edge = (next_market_day <= 5) | (next_market_day >= 25)
    for j, symbol in enumerate(panel.symbols):
        raw = pd.DataFrame({"Open": panel.o[:, j], "High": panel.h[:, j], "Low": panel.l[:, j],
                            "Close": panel.c[:, j], "Volume": panel.v[:, j]}, index=panel.dates)
        signal_family = "rebound" if family == "volume_spike" else family
        if signal_family in R13_FAMILIES:
            f = r13_signal(raw, signal_family)
        else:
            f = r12_signal(raw, signal_family, **config.get("params", {}))
        if family == "volume_spike":
            f["SIGNAL"] = volume_prep({symbol: raw})[symbol]["SIGNAL"].reindex(raw.index)
        close, high = raw.Close, raw.High
        sig = f.SIGNAL.copy()
        if config.get("self_trend"):
            sig &= close > close.rolling(200).mean()
        if config.get("volume_confirm"):
            sig &= f.VOL_RATIO >= 1.5
        if config.get("persistence"):
            turnover = raw.Volume * raw.Close
            ratio = turnover / turnover.shift(1).rolling(60).median()
            sig &= (ratio >= 1.5).rolling(5).sum() >= 3
        if config.get("weekly_trend"):
            weekly = close.resample("W-SUN").last()
            allowed = weekly > weekly.rolling(10).mean()
            sig &= allowed.reindex(close.index, method="ffill").fillna(False)
        if config.get("monthly_trend"):
            monthly = close.resample("ME").last()
            allowed = monthly > monthly.rolling(6).mean()
            sig &= allowed.reindex(close.index, method="ffill").fillna(False)
        if config.get("weekly_indicator"):
            weekly_bars = (
                raw.resample("W-SUN")
                .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
                .dropna()
            )
            weekly_signal = r13_signal(weekly_bars, config["weekly_indicator"])["SIGNAL"]
            confirmed = weekly_signal.rolling(4).max().fillna(False).astype(bool)
            sig &= confirmed.reindex(close.index, method="ffill").fillna(False)
        if config.get("or_family"):
            or_family = config["or_family"]
            if or_family in R13_FAMILIES:
                other = r13_signal(raw, or_family)["SIGNAL"]
            else:
                other = r12_signal(raw, or_family)["SIGNAL"]
            sig |= other.reindex(close.index, fill_value=False)
        if config.get("breadth"):
            sig &= breadth.reindex(close.index, fill_value=False)
        if config.get("weekdays"):
            sig &= tomorrow.reindex(close.index, fill_value=False)
        if config.get("month_edge"):
            sig &= next_month_edge.reindex(close.index, fill_value=False)
        if config.get("and_family"):
            if config["and_family"] in R13_FAMILIES:
                confirm = r13_signal(raw, config["and_family"]).SIGNAL
            else:
                confirm = r12_signal(raw, config["and_family"]).SIGNAL
            sig &= confirm.rolling(5).max().fillna(False).astype(bool)
        if family == "residual_rebound":
            resid = _residual(close, market_ret)
            past = resid.shift(1).rolling(5).sum()
            threshold = resid.shift(1).rolling(60).std() * np.sqrt(5)
            sig &= (past < -threshold) & (resid > 0)
        if not panel.eligible[:, j].all():
            sig &= pd.Series(panel.eligible[:, j], index=panel.dates)
        if config.get("rank") == "relative_strength":
            f["VOL_RATIO"] = close.pct_change(90, fill_method=None).fillna(-1.)
        elif config.get("rank") == "low_vol":
            f["VOL_RATIO"] = -close.pct_change(fill_method=None).rolling(20).std().fillna(-1.)
        elif config.get("rank") == "downside":
            down = close.pct_change(fill_method=None).clip(upper=0).pow(2).rolling(30).mean().pow(.5)
            f["VOL_RATIO"] = -down.fillna(-1.)
        elif config.get("rank") == "residual" or family == "residual_rebound":
            resid = _residual(close, market_ret)
            f["VOL_RATIO"] = resid.rolling(20).sum().fillna(-1.)
        else:
            # Some original round13 families are not volume-ranked; stable rank is neutral.
            f["VOL_RATIO"] = f.VOL_RATIO.replace([np.inf, -np.inf], 0.).fillna(0.)
        f["SIGNAL"] = sig.fillna(False).astype(bool)
        # An untradable open must not become an executable next-open candidate.
        f["Open"] = f["Open"].where(panel.tradable[:, j])
        frames[symbol] = f.loc[dates]
    return frames


def _costs(panel: EquityPanel) -> list[tuple[str, float, np.ndarray, float]]:
    if panel.market == "US":
        return [("KIS_0.36pct", .36, np.zeros(len(panel.symbols)), 0.),
                ("low_0.08pct", .08, np.zeros(len(panel.symbols)), 0.)]
    return [("KR_base", .015, panel.slip, .0018),
            ("KR_2x_slippage", .015, panel.slip * 2, .0018)]


def _run_config(panel: EquityPanel, config: dict[str, Any], dates: pd.DatetimeIndex,
                proxy_gate: pd.Series, breadth: pd.Series, cost: tuple[str, float, np.ndarray, float],
                prepared_override: dict[str, pd.DataFrame] | None = None) -> dict[str, Any]:
    prepped = (
        _prepare_config(panel, config, dates, proxy_gate, breadth)
        if prepared_override is None else prepared_override
    )
    kwargs: dict[str, Any] = {
        k: config[k] for k in (
            "top_k", "hold_days", "sizing", "target_vol", "weight_cap",
            "timing", "stop", "tp", "selection", "dd_trigger",
            "resume_mode", "cooldown_days", "symbol_trade_share_cap",
        ) if k in config
    }
    kwargs.setdefault("top_k", 8)
    kwargs.setdefault("hold_days", 20)
    state = proxy_gate.copy()
    if config.get("btc_trend"):
        kwargs["btc_ok"] = state.to_dict()
    if config.get("btc_confirm"):
        raw = state.fillna(False).astype(int).to_numpy()
        confirmed_state = np.zeros(len(raw), dtype=bool)
        pending, count, accepted = -1, 0, -1
        for i, value in enumerate(raw):
            count = count + 1 if value == pending else 1
            pending = int(value)
            if count >= int(config["btc_confirm"]):
                accepted = int(value)
            confirmed_state[i] = accepted == 1
        kwargs["btc_ok"] = pd.Series(confirmed_state, index=state.index).to_dict()
    if config.get("btc_hysteresis"):
        width = float(config["btc_hysteresis"])
        kwargs["btc_ok"] = hysteresis(pd.Series(panel.proxy_close, index=panel.dates), width).astype(bool).to_dict()
    if config.get("resume_mode") == "btc_sma50":
        proxy = pd.Series(panel.proxy_close, index=panel.dates)
        kwargs["btc_resume"] = (proxy > proxy.rolling(50).mean()).to_dict()
    if config.get("breaker"):
        kwargs.update(dd_trigger=.25, dd_resume=.10, resume_mode="cooldown", cooldown_days=40)
    cost_name, fee, slip, tax = cost
    if np.asarray(slip).ndim > 0:
        slip_by_symbol = np.asarray(slip)[[panel.symbols.index(s) for s in sorted(prepped)]]
    else:
        slip_by_symbol = slip
    if config.get("online_sizing"):
        kwargs["entry_scale"] = OnlineCompletedTradeScale(
            config["online_sizing"], config.get("online_window", 40)
        )
    elif config.get("shrink_sizing"):
        reference = simulate_cost_portfolio(
            prepped, fee_pct_one_way=fee, slippage=slip_by_symbol, sell_tax=tax,
            return_trace=True, **kwargs
        )
        reference_dates = pd.DatetimeIndex(
            pd.to_datetime([point["date"] for point in reference["trace"]])
        )
        kwargs["entry_scale"] = completed_reference_scales(
            reference_dates, reference["records"], config["shrink_sizing"],
            config.get("shrink_window", 40),
        )
    exit_signals = None
    if prepped and all("EXIT_SIGNAL" in frame for frame in prepped.values()):
        ordered_symbols = sorted(prepped)
        exit_signals = np.column_stack([
            prepped[symbol]["EXIT_SIGNAL"].reindex(dates, fill_value=False).to_numpy(bool)
            for symbol in ordered_symbols
        ])
    run = simulate_cost_portfolio(prepped, fee_pct_one_way=fee, slippage=slip_by_symbol, sell_tax=tax,
                                  exit_signals=exit_signals, return_trace=True, **kwargs)
    trace = run.pop("trace")
    dates_run = pd.DatetimeIndex(pd.to_datetime([r["date"] for r in trace]))
    curve = np.asarray([r["closing"] for r in trace], dtype=float)
    run.pop("allocations", None); run.pop("records", None)
    run.pop("breaker_log", None); run.pop("symbol_share_log", None)
    return {"config": config, "policy_group": config["policy_group"], "cost_case": cost_name,
            "signal_count": int(sum(frame.SIGNAL.sum() for frame in prepped.values())),
            "metrics": {k: (str(run[k]) if k in ("start", "end") else
                            int(run[k]) if k == "trades" else float(run[k]))
                        for k in ("cagr", "mdd", "sharpe", "trades", "final", "start", "end")},
            "daily_equity": curve.tolist(), "daily_date_count": len(dates_run)}


def evaluate(market: str, payload: dict[str, Any]) -> dict[str, Any]:
    panel = load_equity_panel(market)
    d0 = int(panel.dates.searchsorted(START))
    dates = panel.dates[d0:]
    proxy_close = pd.Series(panel.proxy_close, index=panel.dates)
    proxy_gate = proxy_close > proxy_close.rolling(200, min_periods=200).mean()
    breadth_n = np.zeros(len(panel.dates)); breadth_ok = np.zeros(len(panel.dates))
    for j in range(len(panel.symbols)):
        close = pd.Series(panel.c[:, j], index=panel.dates)
        sma50 = close.rolling(50).mean()
        valid = sma50.notna().to_numpy() & panel.eligible[:, j]
        breadth_n += valid
        breadth_ok += valid & (close.to_numpy() > sma50.to_numpy())
    breadth = pd.Series((breadth_n > 0) & (breadth_ok / np.maximum(breadth_n, 1) >= .5), index=panel.dates)
    configs = _configs()
    prior = payload["markets"].get(market, {})
    rows = list(prior.get("rows", []))
    done = {(json.dumps(r["config"], sort_keys=True), r["cost_case"]) for r in rows}
    market_meta = {"market": market, "date_range": [str(dates[0].date()), str(dates[-1].date())],
                   "trading_dates": [str(d.date()) for d in dates], "symbols": len(panel.symbols),
                   "source_config_count": len(configs), "unique_config_count": len({json.dumps(c, sort_keys=True) for c in configs}),
                   "cost_cases": [c[0] for c in _costs(panel)], "rows": rows, "row_count": len(rows),
                   "complete": False, "btc_proxy": "causal equal-weight equity proxy; not BTC",
                   "execution": "prior-close signal, next-open fill; fixed holding horizon; point-in-time eligibility and tradable-open filter"}
    payload["markets"][market] = market_meta
    _save_checkpoint(payload)
    total = len(configs) * len(_costs(panel))
    done_n = len(done)
    for config in configs:
        for cost in _costs(panel):
            key = (json.dumps(config, sort_keys=True), cost[0])
            if key in done:
                continue
            rows.append(_run_config(panel, config, dates, proxy_gate, breadth, cost))
            done.add(key)
            done_n += 1
            market_meta["row_count"] = len(rows)
            if done_n % 10 == 0 or done_n == total:
                print(f"[{market}] {done_n}/{total} portfolio-policy cases", flush=True)
                _save_checkpoint(payload)
    market_meta["complete"] = True
    _save_checkpoint(payload)
    return market_meta


def _save_checkpoint(payload: dict[str, Any]) -> None:
    temp = PARTIAL.with_suffix(".partial.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temp.replace(PARTIAL)


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    configs = _configs()
    fingerprint = hashlib.sha256(json.dumps(configs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if PARTIAL.exists():
        payload = json.loads(PARTIAL.read_text(encoding="utf-8"))
        if payload.get("config_fingerprint") != fingerprint:
            raise ValueError("checkpoint configuration fingerprint differs from current source")
    else:
        payload = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                   "round12_policy_configs": sum(1 for c in configs if c["phase"] == "R12"),
                   "round13_policy_configs": sum(1 for c in configs if c["phase"].startswith("R13-")),
                   "source_config_count": len(configs), "config_fingerprint": fingerprint, "markets": {}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for market in ("US", "KR"):
        current = payload["markets"].get(market, {})
        if not current.get("complete"):
            evaluate(market, payload)
    PARTIAL.replace(OUT)
    print(json.dumps({"configs": len(configs), **{m: x["row_count"] for m, x in payload["markets"].items()}}))


if __name__ == "__main__":
    main()
