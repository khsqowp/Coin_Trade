"""Causal daily-equity transfer of the 72 Mach7 portfolio configurations.

The original crypto runner enters at the same close used to confirm its signal.
This transfer uses prior-close signals and next-open entries/exits. Stops and
targets use OHLC with stop-first ordering when both are touched on one bar.
"""
from __future__ import annotations

from itertools import product
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.rs_equity_transfer import EquityPanel, load_equity_panel


OUT = Path(__file__).resolve().parents[1] / "docs/research/equity_transfer_2026-10/full_runs/mach7_portfolio_transfer.json"
START = pd.Timestamp("2019-01-01")
TOP_NS = (3, 5, 8)
REGIMES = ("none", "self_sma200", "btc_sma200_proxy")
RS_RANKS = ("off", "on")
EXIT_MODES = ("trail_ema", "rr2")
STOP_MODES = ("swing", "pct")


def _features(panel: EquityPanel, start_i: int) -> dict[str, np.ndarray]:
    n, m = panel.c.shape
    entry = np.zeros((n, m), bool)
    exit_ema = np.full((n, m), np.nan)
    stop_swing = np.full((n, m), np.nan)
    ema_fast = np.full((n, m), np.nan)
    sma200 = np.full((n, m), np.nan)
    ret90 = np.full((n, m), np.nan)
    for j in range(m):
        ok = np.isfinite(panel.c[:, j])
        if ok.sum() < 260:
            continue
        f = pd.DataFrame({"Open": panel.o[:, j], "High": panel.h[:, j], "Low": panel.l[:, j],
                          "Close": panel.c[:, j], "Volume": panel.v[:, j]}, index=panel.dates).dropna(subset=["Close"])
        c, h, low = f.Close, f.High, f.Low
        fast, mid, slow = (c.ewm(span=k, adjust=False).mean() for k in (10, 50, 200))
        dip = (low <= fast).rolling(10, min_periods=1).max().astype(bool)
        entry_s = (fast > mid) & (mid > slow) & dip & (c > fast) & (c > h.shift())
        loc = panel.dates.get_indexer(f.index)
        entry[loc, j] = entry_s.to_numpy(bool)
        ema_fast[loc, j] = fast.to_numpy(float)
        exit_ema[loc, j] = mid.to_numpy(float)
        sma200[loc, j] = c.rolling(200, min_periods=200).mean().to_numpy(float)
        ret90[loc, j] = c.pct_change(90, fill_method=None).to_numpy(float)
        stop_swing[loc, j] = low.rolling(10, min_periods=1).min().to_numpy(float)
    proxy = pd.Series(panel.proxy_close, index=panel.dates)
    proxy_gate = proxy > proxy.rolling(200, min_periods=200).mean()
    entry[:start_i] = False
    return {"entry": entry, "ema_fast": ema_fast, "ema_exit": exit_ema,
            "sma200": sma200, "ret90": ret90, "stop_swing": stop_swing,
            "proxy_gate": proxy_gate.to_numpy(bool)}


def _metrics(eq: np.ndarray, dates: pd.DatetimeIndex) -> dict[str, float]:
    daily = eq / np.r_[1.0, eq[:-1]] - 1.0
    years = max((dates[-1] - dates[0]).days / 365.25, 1 / 365.25)
    cagr = float(eq[-1] ** (1 / years) - 1) if eq[-1] > 0 else -1.0
    peak = np.maximum.accumulate(np.r_[1.0, eq])[1:]
    mdd = float(np.max(1 - eq / peak))
    vol = float(daily.std()) if len(daily) else 0.0
    sharpe = float(daily.mean() / vol * np.sqrt(252)) if vol > 0 else 0.0
    return {"cagr": cagr, "mdd": mdd, "sharpe": sharpe, "final_equity": float(eq[-1])}


def _window_metrics(eq: np.ndarray, dates: pd.DatetimeIndex, a: int, b: int, prefix: str) -> dict[str, float]:
    if b - a < 30:
        return {f"{prefix}_{k}": float("nan") for k in ("cagr", "mdd", "sharpe")}
    base = eq[a - 1] if a > 0 else 1.0
    stats = _metrics(eq[a:b] / base, dates[a:b])
    return {f"{prefix}_{k}": stats[k] for k in ("cagr", "mdd", "sharpe")}


def _run(panel: EquityPanel, f: dict[str, np.ndarray], start_i: int, cfg: dict[str, Any],
         buy_cost: np.ndarray, sell_cost: np.ndarray) -> dict[str, float]:
    n, m = panel.c.shape
    cash = 1.0
    qty = np.zeros(m)
    stops = np.full(m, np.nan)
    targets = np.full(m, np.nan)
    last_close = panel.c[start_i - 1].copy()
    eq = np.ones(n - start_i)
    trades = exposure_days = 0
    for t in range(start_i, n):
        # Prior-close exit condition is executable at today's open.
        if t > start_i:
            for j in np.flatnonzero(qty > 0):
                if f["exit_flag"][t - 1, j] and np.isfinite(panel.o[t, j]):
                    cash += qty[j] * panel.o[t, j] * (1 - sell_cost[j])
                    qty[j] = 0.0
                    trades += 1

        # Causal regime/RS filtering, with signals observed at yesterday's close.
        if t > start_i:
            free = max(0, cfg["top_n"] - int(np.count_nonzero(qty)))
            if free:
                s = t - 1
                candidates = []
                for j in range(m):
                    if qty[j] or not f["entry"][s, j] or not panel.eligible[t, j] or not panel.tradable[t, j]:
                        continue
                    if cfg["regime"] == "self_sma200" and not (
                        np.isfinite(f["sma200"][s, j]) and panel.c[s, j] > f["sma200"][s, j]
                    ):
                        continue
                    if cfg["regime"] == "btc_sma200_proxy" and not f["proxy_gate"][s]:
                        continue
                    rs = f["ret90"][s, j]
                    if cfg["rs_rank"] == "on":
                        cross = f["ret90"][s]
                        finite = cross[np.isfinite(cross)]
                        median = float(np.median(finite)) if len(finite) else np.inf
                        if not np.isfinite(rs) or rs <= median:
                            continue
                    candidates.append((j, rs if np.isfinite(rs) else -np.inf))
                candidates.sort(key=lambda x: x[1], reverse=True)
                marked = cash + sum(qty[j] * (panel.o[t, j] if np.isfinite(panel.o[t, j]) else last_close[j])
                                    for j in range(m) if qty[j] > 0)
                for j, _ in candidates[:free]:
                    price = panel.o[t, j]
                    if not np.isfinite(price) or price <= 0:
                        continue
                    stop = (f["stop_swing"][s, j] if cfg["stop_mode"] == "swing" else price * .92)
                    if not np.isfinite(stop) or stop <= 0 or stop >= price:
                        continue
                    alloc = min(marked / cfg["top_n"], cash)
                    if alloc <= 0:
                        break
                    qty[j] = alloc * (1 - buy_cost[j]) / price
                    cash -= alloc
                    last_close[j] = price
                    stops[j] = stop
                    targets[j] = price + 2 * (price - stop) if cfg["exit_mode"] == "rr2" else np.nan

        # Intraday stop/target after any opening fill; stop wins ambiguous bars.
        for j in np.flatnonzero(qty > 0):
            op, lo, hi = panel.o[t, j], panel.l[t, j], panel.h[t, j]
            stop, target = stops[j], targets[j]
            fill = np.nan
            if np.isfinite(op) and op <= stop:
                fill = op
            elif np.isfinite(lo) and lo <= stop:
                fill = stop
            elif np.isfinite(target) and np.isfinite(op) and op >= target:
                fill = op
            elif np.isfinite(target) and np.isfinite(hi) and hi >= target:
                fill = target
            if np.isfinite(fill):
                cash += qty[j] * fill * (1 - sell_cost[j])
                qty[j] = 0.0
                stops[j] = targets[j] = np.nan
                trades += 1

        # End-of-day exit signal is acted on next session; equity marks today's close.
        f["exit_flag"][t] = panel.c[t] < (
            f["ema_fast"][t] if cfg["exit_mode"] == "trail_ema" else f["ema_exit"][t]
        )
        val = cash
        for j in np.flatnonzero(qty > 0):
            mark = panel.c[t, j] if np.isfinite(panel.c[t, j]) else last_close[j]
            if np.isfinite(mark):
                val += qty[j] * mark
        last_close[np.isfinite(panel.c[t])] = panel.c[t, np.isfinite(panel.c[t])]
        eq[t - start_i] = val
        if np.any(qty > 0):
            exposure_days += 1

    # Liquidate open inventory at the final close and include sell-side costs.
    for j in np.flatnonzero(qty > 0):
        px = panel.c[-1, j] if np.isfinite(panel.c[-1, j]) else last_close[j]
        if np.isfinite(px):
            eq[-1] -= qty[j] * px * sell_cost[j]
            trades += 1
    out = _metrics(eq, panel.dates[start_i:])
    out.update({"trades": float(trades), "exposure_fraction": exposure_days / max(1, len(eq))})
    split = int(len(eq) * .60)
    out.update(_window_metrics(eq, panel.dates[start_i:], 0, split, "is"))
    out.update(_window_metrics(eq, panel.dates[start_i:], split, len(eq), "oos"))
    w22 = int(panel.dates[start_i:].searchsorted(pd.Timestamp("2022-01-03")))
    out.update(_window_metrics(eq, panel.dates[start_i:], w22, len(eq), "w22"))
    out["daily_equity"] = eq.tolist()
    return out


def _costs(panel: EquityPanel) -> list[tuple[str, np.ndarray, np.ndarray]]:
    m = len(panel.symbols)
    if panel.market == "US":
        return [("KIS_0.36pct", np.full(m, .0036), np.full(m, .0036)),
                ("low_0.08pct", np.full(m, .0008), np.full(m, .0008))]
    return [("KR_base", .00015 + panel.slip, .00015 + .0018 + panel.slip),
            ("KR_2x_slippage", .00015 + 2 * panel.slip, .00015 + .0018 + 2 * panel.slip)]


def evaluate(market: str) -> dict[str, Any]:
    panel = load_equity_panel(market)
    start_i = max(int(panel.dates.searchsorted(START)), 220)
    f = _features(panel, start_i)
    rows = []
    combos = list(product(TOP_NS, REGIMES, RS_RANKS, EXIT_MODES, STOP_MODES))
    for top_n, regime, rs_rank, exit_mode, stop_mode in combos:
        cfg = {"top_n": top_n, "regime": regime, "rs_rank": rs_rank,
               "exit_mode": exit_mode, "stop_mode": stop_mode}
        # Each configuration gets a private exit-flag array; exits depend on mode.
        for cost_name, buy, sell in _costs(panel):
            features = dict(f)
            features["exit_flag"] = np.zeros_like(f["entry"], dtype=bool)
            full = _run(panel, features, start_i, cfg, buy, sell)
            rows.append({"market": market, **cfg, "cost_case": cost_name, **full})
    return {"market": market, "date_range": [str(panel.dates[start_i].date()), str(panel.dates[-1].date())],
            "symbols": len(panel.symbols), "combination_count": len(combos), "cost_cases": [c[0] for c in _costs(panel)],
            "rows": rows, "row_count": len(rows),
            "execution": "signal prior close, entry/indicator exit next open; intraday stop/target uses OHLC, stop-first ambiguous bars; final close liquidation",
            "btc_regime": "synthetic equal-weight equity proxy SMA200, not BTC; approximate transfer"}


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    payload = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(), "source_combinations": 72,
               "markets": {m: evaluate(m) for m in ("US", "KR")}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({m: v["row_count"] for m, v in payload["markets"].items()}))


if __name__ == "__main__":
    main()
