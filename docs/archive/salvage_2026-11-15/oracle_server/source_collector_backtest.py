#!/usr/bin/env python3
"""Public-data, no-order Binance USD-M strategy screening harness.

Signals are formed from completed candles and applied from the next candle open.
This is a research screen, not an execution simulator or a profitability claim.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import requests

BASE = "https://fapi.binance.com"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
INTERVALS = ["1m", "5m", "15m", "1h", "4h"]
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
               "1h": 3_600_000, "4h": 14_400_000}
WINDOWS_DAYS = [7, 30, 90, 180, 365, 730, 1095, 1825]
FEE_PER_SIDE = 0.0005       # generic taker assumption; account VIP not known
SLIPPAGE_PER_SIDE = 0.0002  # explicit sensitivity assumption, not measured
INITIAL_EQUITY = 128.88323162  # user-provided research capital; sizing precision/minimums remain unmodeled
MAX_RETRIES = 6


def utc_ms_days(days: int) -> int:
    return int((time.time() - days * 86400) * 1000)


def get_json(path: str, params: dict) -> list:
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(BASE + path, params=params, timeout=30)
            if response.status_code in (418, 429):
                time.sleep(min(60, 3 ** attempt))
                continue
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "code" in data:
                raise RuntimeError("Binance API error: {}".format(data.get("msg", data["code"])))
            return data
        except Exception as exc:
            last = exc
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError("GET {} failed: {}".format(path, last))


def fetch_klines(symbol: str, interval: str, start_ms: int, out: Path) -> pd.DataFrame:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        try:
            cached = pd.read_csv(out)
            covers_start = len(cached) and int(cached.open_time_ms.iloc[0]) <= start_ms + INTERVAL_MS[interval]
            is_fresh = len(cached) and int(cached.open_time_ms.iloc[-1]) >= int(time.time() * 1000) - INTERVAL_MS[interval] * 2
            if covers_start and is_fresh:
                return cached.drop_duplicates("open_time_ms").sort_values("open_time_ms").reset_index(drop=True)
        except Exception:
            pass
    rows: List[list] = []
    cursor = start_ms
    now = int(time.time() * 1000)
    while cursor < now:
        page = get_json("/fapi/v1/klines", {
            "symbol": symbol, "interval": interval, "startTime": cursor, "limit": 1000
        })
        if not page:
            break
        rows.extend(page)
        next_cursor = int(page[-1][0]) + INTERVAL_MS[interval]
        if next_cursor <= cursor:
            raise RuntimeError("Kline pagination stalled for {} {}".format(symbol, interval))
        cursor = next_cursor
        if len(page) < 1000:
            break
        time.sleep(0.12)
    cols = ["open_time_ms", "open", "high", "low", "close", "volume", "close_time_ms",
            "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
    df = pd.DataFrame(rows, columns=cols)
    if df.empty:
        raise RuntimeError("No klines returned for {} {}".format(symbol, interval))
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["open_time_ms"] = pd.to_numeric(df.open_time_ms, errors="coerce").astype("int64")
    df = df.dropna(subset=["open", "high", "low", "close"]).drop_duplicates("open_time_ms")
    df = df.sort_values("open_time_ms").reset_index(drop=True)
    df.to_csv(out, index=False)
    return df


def fetch_funding(symbol: str, start_ms: int, out: Path) -> pd.DataFrame:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        cached = pd.read_csv(out)
        covers_start = len(cached) and int(cached.funding_time_ms.iloc[0]) <= start_ms + 9 * 3600_000
        is_fresh = len(cached) and int(cached.funding_time_ms.iloc[-1]) >= int(time.time() * 1000) - 9 * 3600_000
        if covers_start and is_fresh:
            return cached.drop_duplicates("funding_time_ms").sort_values("funding_time_ms").reset_index(drop=True)
    rows: List[dict] = []
    cursor = start_ms
    now = int(time.time() * 1000)
    while cursor < now:
        page = get_json("/fapi/v1/fundingRate", {
            "symbol": symbol, "startTime": cursor, "limit": 1000
        })
        if not page:
            break
        rows.extend(page)
        next_cursor = int(page[-1]["fundingTime"]) + 1
        if next_cursor <= cursor:
            raise RuntimeError("Funding pagination stalled for {}".format(symbol))
        cursor = next_cursor
        if len(page) < 1000:
            break
        time.sleep(0.12)
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["funding_time_ms", "funding_rate"])
    else:
        df = df.rename(columns={"fundingTime": "funding_time_ms", "fundingRate": "funding_rate"})
        df = df[["funding_time_ms", "funding_rate"]]
        df["funding_time_ms"] = pd.to_numeric(df.funding_time_ms).astype("int64")
        df["funding_rate"] = pd.to_numeric(df.funding_rate)
        df = df.drop_duplicates("funding_time_ms").sort_values("funding_time_ms").reset_index(drop=True)
    df.to_csv(out, index=False)
    return df


@dataclass(frozen=True)
class Strategy:
    name: str
    family: str
    params: str


def make_strategies(df: pd.DataFrame) -> List[Tuple[Strategy, pd.Series]]:
    c = df.close
    h, l = df.high, df.low
    sigs: List[Tuple[Strategy, pd.Series]] = []

    def add(name: str, family: str, params: str, signal: pd.Series):
        sigs.append((Strategy(name, family, params), signal.replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1, 1)))

    sma_cache: Dict[int, pd.Series] = {}
    ema_cache: Dict[int, pd.Series] = {}
    for n in [5, 10, 15, 20, 30, 50, 75, 100, 150, 200]:
        sma_cache[n] = c.rolling(n, min_periods=n).mean()
        ema_cache[n] = c.ewm(span=n, adjust=False, min_periods=n).mean()
    fasts = [5, 10, 15, 20, 30, 50]
    slows = [20, 30, 50, 75, 100, 150, 200]
    pairs = [(f, s) for f in fasts for s in slows if f < s]
    for f, s in pairs:
        add("sma_{}_{}".format(f, s), "sma_cross", "fast={},slow={}".format(f, s),
            (sma_cache[f] > sma_cache[s]).astype(float))
        add("ema_{}_{}".format(f, s), "ema_cross", "fast={},slow={}".format(f, s),
            (ema_cache[f] > ema_cache[s]).astype(float))

    # Donchian breakouts: the channel is lagged so today's high/low is excluded.
    for n in [10, 20, 40, 55, 100, 200]:
        upper = h.rolling(n, min_periods=n).max().shift(1)
        lower = l.rolling(n, min_periods=n).min().shift(1)
        add("donchian_long_{}".format(n), "donchian", "n={}".format(n), (c > upper).astype(float))
        add("donchian_ls_{}".format(n), "donchian", "n={}".format(n),
            pd.Series(np.where(c > upper, 1.0, np.where(c < lower, -1.0, 0.0)), index=df.index))

    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((gain == 0) & (loss > 0), 0.0)
    rsi = rsi.mask((gain == 0) & (loss == 0), 50.0)
    for lo, hi in [(20, 50), (25, 55), (30, 60), (35, 65), (40, 70), (30, 70)]:
        # Mean-reversion: enter at oversold, exit at neutral; position is long-only.
        state = np.zeros(len(df), dtype=float)
        rv = rsi.to_numpy()
        for i in range(1, len(rv)):
            state[i] = 1.0 if (np.isfinite(rv[i]) and rv[i] < lo) else (0.0 if (np.isfinite(rv[i]) and rv[i] > hi) else state[i - 1])
        add("rsi_mr_{}_{}".format(lo, hi), "rsi_mean_reversion", "entry={},exit={}".format(lo, hi), pd.Series(state, index=df.index))
        add("rsi_ls_{}_{}".format(lo, hi), "rsi_extremes", "low={},high={}".format(lo, hi),
            pd.Series(np.where(rsi < lo, 1.0, np.where(rsi > hi, -1.0, 0.0)), index=df.index))

    for n in [20, 50]:
        mid = c.rolling(n, min_periods=n).mean()
        sd = c.rolling(n, min_periods=n).std(ddof=0)
        for mult in [1.5, 2.0, 2.5]:
            upper, lower = mid + mult * sd, mid - mult * sd
            add("bb_mr_{}_{}".format(n, mult), "bollinger_mean_reversion", "n={},k={}".format(n, mult),
                pd.Series(np.where(c < lower, 1.0, np.where(c > mid, 0.0, np.nan)), index=df.index).ffill().fillna(0))
            add("bb_breakout_{}_{}".format(n, mult), "bollinger_breakout", "n={},k={}".format(n, mult),
                pd.Series(np.where(c > upper, 1.0, np.where(c < lower, -1.0, 0.0)), index=df.index))

    for f, s, sig in [(8, 21, 5), (12, 26, 9), (5, 35, 5), (19, 39, 9), (6, 19, 4), (10, 30, 7)]:
        line = c.ewm(span=f, adjust=False).mean() - c.ewm(span=s, adjust=False).mean()
        signal_line = line.ewm(span=sig, adjust=False).mean()
        add("macd_{}_{}_{}".format(f, s, sig), "macd", "fast={},slow={},signal={}".format(f, s, sig),
            (line > signal_line).astype(float))

    for n in [10, 20, 50, 100, 200]:
        mom = c / c.shift(n) - 1
        add("roc_long_{}".format(n), "rate_of_change", "n={}".format(n), (mom > 0).astype(float))
        add("roc_ls_{}".format(n), "rate_of_change_long_short", "n={}".format(n),
            pd.Series(np.where(mom > 0, 1.0, np.where(mom < 0, -1.0, 0.0)), index=df.index))

    # Volatility-filtered trend variants; threshold is lagged and uses no future bar.
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    for n in [20, 50, 100, 200]:
        trend = c > sma_cache[n]
        low_vol = atr / c < (atr / c).rolling(100, min_periods=30).quantile(0.5)
        for invert in [False, True]:
            filt = low_vol if invert else ~low_vol
            add("trend_vol_{}_{}".format(n, "low" if invert else "high"), "volatility_regime_trend",
                "trend_sma={},vol_regime={}".format(n, "low" if invert else "high"),
                (trend & filt).astype(float))
    add("buy_hold_long", "baseline", "always long", pd.Series(1.0, index=df.index))
    add("buy_hold_short", "baseline", "always short", pd.Series(-1.0, index=df.index))
    add("cash", "baseline", "flat exposure", pd.Series(0.0, index=df.index))
    return sigs


def eval_strategy(df: pd.DataFrame, signal: pd.Series, funding: pd.DataFrame,
                  days: int, interval: str) -> dict:
    # Signal at completed bar t, exposure starts at next bar open. Return runs open-to-next-open.
    opens = df.open.to_numpy(dtype=float)
    close_times = df.open_time_ms.to_numpy(dtype=np.int64)
    sig = signal.to_numpy(dtype=float)
    pos = np.zeros(len(df), dtype=float)
    if len(pos) > 1:
        pos[1:] = sig[:-1]
    next_open = np.roll(opens, -1)
    next_open[-1] = np.nan
    gross = next_open / opens - 1
    turnover = np.abs(pos - np.roll(pos, 1))
    turnover[0] = abs(pos[0])
    costs = turnover * (FEE_PER_SIDE + SLIPPAGE_PER_SIDE)
    funding_cost = np.zeros(len(df), dtype=float)
    if len(funding):
        ftime = funding.funding_time_ms.to_numpy(dtype=np.int64)
        frate = funding.funding_rate.to_numpy(dtype=float)
        idx = np.searchsorted(close_times, ftime, side="right") - 1
        valid = (idx >= 0) & (idx < len(df))
        # Positive funding is paid by longs; negative funding by shorts.
        np.add.at(funding_cost, idx[valid], pos[idx[valid]] * frate[valid])
    net = pos * gross - costs - funding_cost
    start_ms = int(time.time() * 1000 - days * 86400_000)
    mask = (close_times >= start_ms) & np.isfinite(net)
    idxs = np.flatnonzero(mask)
    if len(idxs) < 30:
        return {"bars": len(idxs), "actual_window_days": np.nan, "return_pct": np.nan, "cagr_pct": np.nan, "sharpe": np.nan,
                "sortino": np.nan, "max_dd_pct": np.nan, "trades": 0, "win_rate_pct": np.nan,
                "fees_pct_start": np.nan, "funding_pct_start": np.nan, "exposure_pct": np.nan}
    r = net[idxs].copy()
    unit_cost = FEE_PER_SIDE + SLIPPAGE_PER_SIDE
    # Treat every evaluation window as starting flat; re-enter at its first open.
    opening_cost = abs(pos[idxs[0]]) * unit_cost
    r[0] = pos[idxs[0]] * gross[idxs[0]] - funding_cost[idxs[0]] - opening_cost
    # Charge the final liquidation of any open exposure so a window does not end for free.
    closing_cost = abs(pos[idxs[-1]]) * unit_cost
    r[-1] -= closing_cost
    equity = np.cumprod(1 + r)
    total = float(equity[-1] - 1)
    elapsed_days = max(1 / 1440, (close_times[idxs[-1]] - close_times[idxs[0]] + INTERVAL_MS[interval]) / 86400_000)
    annual_factor = 365.25 * 86400_000 / INTERVAL_MS[interval]
    cagr = float(equity[-1] ** (365.25 / elapsed_days) - 1) if equity[-1] > 0 else -1.0
    std = float(np.std(r, ddof=1))
    sharpe = float(np.mean(r) / std * math.sqrt(annual_factor)) if std > 0 else np.nan
    downside_deviation = float(np.sqrt(np.mean(np.minimum(r, 0) ** 2)))
    sortino = float(np.mean(r) / downside_deviation * math.sqrt(annual_factor)) if downside_deviation > 0 else np.nan
    peak = np.maximum.accumulate(np.concatenate([[1.0], equity]))[1:]
    mdd = float(np.min(equity / peak - 1))
    trade_rets = []
    window_pos = pos[idxs]
    signs = np.sign(window_pos).astype(np.int8)
    bar_returns = window_pos * gross[idxs] - funding_cost[idxs]
    # Find contiguous non-flat position runs in vectorized form; compound each run in NumPy.
    boundaries = np.flatnonzero(np.r_[True, signs[1:] != signs[:-1], True])
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        if signs[start] == 0:
            continue
        segment_growth = float(np.prod(np.maximum(1e-12, 1 + bar_returns[start:end])))
        trade_rets.append(segment_growth * (1 - unit_cost) ** 2 - 1)
    total_fee = float(np.sum(costs[idxs[1:]]) + opening_cost + closing_cost)
    total_funding = float(np.sum(funding_cost[idxs]))
    exposure = float(np.mean(np.abs(pos[idxs]) > 0))
    return {"bars": len(idxs), "actual_window_days": elapsed_days, "return_pct": total * 100, "cagr_pct": cagr * 100,
            "sharpe": sharpe, "sortino": sortino, "max_dd_pct": mdd * 100,
            "trades": len(trade_rets), "win_rate_pct": float(np.mean(np.array(trade_rets) > 0) * 100) if trade_rets else np.nan,
            "fees_pct_start": total_fee * 100, "funding_pct_start": total_funding * 100,
            "exposure_pct": exposure * 100}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default="data")
    p.add_argument("--output-dir", default="results")
    p.add_argument("--symbols", default=",".join(SYMBOLS))
    p.add_argument("--intervals", default=",".join(INTERVALS))
    p.add_argument("--max-years", type=int, default=5)
    p.add_argument("--download-only", action="store_true")
    args = p.parse_args()
    data_dir, output_dir = Path(args.data_dir), Path(args.output_dir)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    intervals = [s.strip() for s in args.intervals.split(",") if s.strip()]
    max_days = args.max_years * 365
    # One-minute candles have shorter requests to limit transfer size; other bars up to max-years.
    days_by_interval = {"1m": min(max_days, 90), "5m": min(max_days, 365),
                        "15m": min(max_days, 1095), "1h": max_days, "4h": max_days}
    datasets: Dict[Tuple[str, str], pd.DataFrame] = {}
    funding_data: Dict[str, pd.DataFrame] = {}
    print("Downloading Binance public USD-M candles; no API key or order endpoint is used.", flush=True)
    for sym in symbols:
        for interval in intervals:
            if interval not in INTERVAL_MS:
                raise ValueError("Unsupported interval: {}".format(interval))
            days = days_by_interval.get(interval, max_days)
            start = utc_ms_days(days)
            fpath = data_dir / "klines" / (sym + "_" + interval + ".csv")
            df = fetch_klines(sym, interval, start, fpath)
            datasets[(sym, interval)] = df
            print("DATA {} {} rows={} first={} last={}".format(sym, interval, len(df),
                  datetime.fromtimestamp(df.open_time_ms.iloc[0] / 1000, timezone.utc).isoformat(),
                  datetime.fromtimestamp(df.open_time_ms.iloc[-1] / 1000, timezone.utc).isoformat()), flush=True)
        fpath = data_dir / "funding" / (sym + ".csv")
        funding_data[sym] = fetch_funding(sym, utc_ms_days(max_days), fpath)
        print("FUNDING {} rows={}".format(sym, len(funding_data[sym])), flush=True)
    if args.download_only:
        return 0

    rows = []
    strategy_count: Dict[Tuple[str, str], int] = {}
    for (sym, interval), df in datasets.items():
        strategies = make_strategies(df)
        strategy_count[(sym, interval)] = len(strategies)
        for strategy, signal in strategies:
            for days in WINDOWS_DAYS:
                if days > days_by_interval[interval]:
                    continue
                metric = eval_strategy(df, signal, funding_data[sym], days, interval)
                rows.append({"symbol": sym, "interval": interval, "window_days": days,
                             "strategy": strategy.name, "family": strategy.family, "params": strategy.params,
                             "fee_per_side_pct": FEE_PER_SIDE * 100,
                             "slippage_per_side_pct": SLIPPAGE_PER_SIDE * 100,
                             "initial_equity_usdt": INITIAL_EQUITY, **metric})
        print("BACKTEST {} {} strategies={} windows={} complete".format(
            sym, interval, len(strategies), sum(d <= days_by_interval[interval] for d in WINDOWS_DAYS)), flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = output_dir / ("strategy_results_" + stamp + ".csv")
    results = pd.DataFrame(rows)
    results.to_csv(csv_path, index=False, float_format="%.8g")
    usable = results.dropna(subset=["sharpe"])
    summary = (usable.groupby(["interval", "window_days", "family"], dropna=False)
               .agg(variants=("strategy", "count"), median_sharpe=("sharpe", "median"),
                    median_return_pct=("return_pct", "median"), median_cagr_pct=("cagr_pct", "median"),
                    median_max_dd_pct=("max_dd_pct", "median"), median_trades=("trades", "median"))
               .reset_index().sort_values(["interval", "window_days", "family"]))
    summary_path = output_dir / ("family_summary_" + stamp + ".csv")
    summary.to_csv(summary_path, index=False, float_format="%.8g")
    manifest = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Binance USD-M Futures public REST API",
        "symbols": symbols, "intervals": intervals, "data_days_by_interval": days_by_interval,
        "evaluation_windows_days": WINDOWS_DAYS,
        "initial_equity_usdt": INITIAL_EQUITY,
        "strategy_variants_per_symbol_interval": {"{}:{}".format(k[0], k[1]): v for k, v in strategy_count.items()},
        "fee_per_side": FEE_PER_SIDE, "slippage_per_side": SLIPPAGE_PER_SIDE,
        "fee_assumption_note": "Generic taker assumption; actual VIP/BNB discount unknown.",
        "slippage_assumption_note": "Fixed assumption, not measured from order book.",
        "execution": "Signal uses completed candle; exposure starts at next candle open; open-to-open PnL.",
        "funding": "Public historical funding rate charged/credited using exposure active at funding timestamp.",
        "constraints": ["No authenticated account endpoints", "No order endpoints", "1x exposure only",
                        "Current symbols only; delisted-asset survivorship bias remains",
                        "Close-price signals do not model intrabar stop execution or market impact",
                        "Thousands of comparisons create selection bias; top results are exploratory only"],
        "results_csv": str(csv_path), "family_summary_csv": str(summary_path),
    }
    manifest_path = output_dir / ("manifest_" + stamp + ".json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("RESULTS {}".format(csv_path), flush=True)
    print("SUMMARY {}".format(summary_path), flush=True)
    print("MANIFEST {}".format(manifest_path), flush=True)
    print("ROWS {} STRATEGIES_PER_DATASET {}".format(len(results), min(strategy_count.values())), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted by operator", file=sys.stderr)
        raise SystemExit(130)
