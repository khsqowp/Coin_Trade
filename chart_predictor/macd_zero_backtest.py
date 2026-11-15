"""Preregistered MACD zero-line + RSI(14) > 50 long-only research runner.

The input candle SQLite file is opened read-only. Funding responses and reports
are written only below the caller-supplied isolated run directory.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor import indicators


SYMBOLS = ("BNBUSDT", "BTCUSDT", "DOGEUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
TIMEFRAMES_MIN = (1, 3, 5, 10, 15, 30, 60, 120, 240, 360, 720, 1440)
EXIT_POLICIES = ("tp_2r", "tp_3r", "tp_4r", "macd_zero_down")
TF_R_MULTIPLE = {"tp_2r": 2.0, "tp_3r": 3.0, "tp_4r": 4.0}
START_MS = 1601510400000  # 2020-10-01T00:00:00Z
TRAIN_END_MS = 1704067200000  # 2024-01-01T00:00:00Z
VALIDATION_END_MS = 1735689600000  # 2025-01-01T00:00:00Z
FINAL_END_MS = 1782864000000  # 2026-07-01T00:00:00Z
HORIZON_BARS = 20
STOP_ATR = 1.5
FEE_BASE = 0.0005
SLIPPAGE_BASE = 0.0002
BOOTSTRAP_SEED = 20261116
BOOTSTRAP_REPLICATES = 10000
BLOCK_DAYS = 7
SCREEN_FUNDING_ID = "screen-through-2025-01-01"
FINAL_FUNDING_ID = "final-through-2026-07-01"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ema(values: np.ndarray, period: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    out = np.full(values.size, np.nan, dtype=np.float64)
    if not values.size:
        return out
    alpha = 2.0 / (period + 1.0)
    out[0] = values[0]
    for i in range(1, values.size):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def rsi_wilder(close: np.ndarray, period: int = 14) -> np.ndarray:
    return indicators.rsi(np.asarray(close, dtype=np.float64), period)


def atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    return indicators.atr(np.asarray(high, dtype=np.float64), np.asarray(low, dtype=np.float64), np.asarray(close, dtype=np.float64), period)


def resample_minutes(frame: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """UTC epoch-aligned bars; discard buckets without every expected minute."""
    if minutes == 1:
        return frame[["open_ms", "open", "high", "low", "close"]].copy().reset_index(drop=True)
    width = minutes * 60_000
    tmp = frame.copy()
    tmp["bucket"] = (tmp["open_ms"] // width) * width
    g = tmp.groupby("bucket", sort=True)
    out = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), n=("open_ms", "size"))
    out = out[out["n"] == minutes].drop(columns="n").reset_index(names="open_ms")
    return out[["open_ms", "open", "high", "low", "close"]]


def read_symbol(db_path: str | Path, symbol: str, through_ms: int) -> pd.DataFrame:
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        return pd.read_sql_query(
            "SELECT open_ms,open,high,low,close FROM candles WHERE symbol=? AND open_ms<? ORDER BY open_ms",
            con,
            params=(symbol, through_ms),
        )
    finally:
        con.close()


def load_funding(run_dir: str | Path, snapshot_id: str, symbol: str, start_ms: int, end_ms: int, minute: pd.DataFrame) -> list[dict]:
    records: list[dict] = []
    for path in sorted((Path(run_dir) / "funding" / snapshot_id / symbol).glob("page_*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))
        records.extend(page)
    records = [r for r in records if start_ms <= int(r["fundingTime"]) < end_ms and r.get("rateType", "Regular") == "Regular"]
    records.sort(key=lambda r: int(r["fundingTime"]))
    seen: set[int] = set()
    out = []
    for r in records:
        t = int(r["fundingTime"])
        if t not in seen:
            seen.add(t)
            mark_text = r.get("markPrice")
            if mark_text not in (None, ""):
                mark = float(mark_text)
            else:
                # Historical endpoint rows often omit markPrice. Use the 1m
                # open at or immediately before settlement (timestamps can
                # carry millisecond jitter) as a causal proxy.
                times = minute["open_ms"].to_numpy(dtype=np.int64)
                i = int(np.searchsorted(times, t, side="right")) - 1
                if i < 0 or t - int(times[i]) >= 60_000:
                    raise ValueError(f"No prior minute open within one minute of funding timestamp {t}")
                mark = float(minute["open"].iloc[i])
            out.append({"time": t, "rate": float(r["fundingRate"]), "mark": mark})
    return out


def fetch_funding(run_dir: str | Path, end_ms: int, snapshot_id: str) -> dict:
    """Fetch unauthenticated USDⓈ-M funding pages; never calls account/order APIs."""
    start_ms = START_MS
    base = Path(run_dir) / "funding" / snapshot_id
    base.mkdir(parents=True, exist_ok=True)
    if any(base.rglob("page_*.json")) or (base / "manifest.json").exists():
        raise FileExistsError(f"Funding snapshot already exists and is immutable: {base}")
    manifest = {"endpoint": "https://fapi.binance.com/fapi/v1/fundingRate", "retrieved_at": datetime.now(timezone.utc).isoformat(), "range_start_ms": start_ms, "range_end_exclusive_ms": end_ms, "symbols": {}}
    for symbol in SYMBOLS:
        target = base / symbol
        target.mkdir(parents=True, exist_ok=True)
        for old in target.glob("page_*.json"):
            old.unlink()
        cursor = start_ms
        pages = []
        page_num = 0
        while cursor < end_ms:
            query = urllib.parse.urlencode({"symbol": symbol, "startTime": cursor, "endTime": end_ms - 1, "limit": 1000})
            req = urllib.request.Request(f"{manifest['endpoint']}?{query}", headers={"User-Agent": "cointrade-r004-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
            rows = json.loads(payload)
            if not isinstance(rows, list):
                raise RuntimeError(f"Unexpected funding response type for {symbol}: {type(rows).__name__}")
            fname = target / f"page_{page_num:04d}.json"
            fname.write_bytes(payload)
            times = [int(r["fundingTime"]) for r in rows]
            pages.append({"path": str(fname.relative_to(Path(run_dir))), "sha256": hashlib.sha256(payload).hexdigest(), "rows": len(rows), "first_ms": min(times) if times else None, "last_ms": max(times) if times else None})
            page_num += 1
            if not rows or len(rows) < 1000:
                break
            next_cursor = max(times) + 1
            if next_cursor <= cursor:
                raise RuntimeError(f"Funding pagination did not advance for {symbol}")
            cursor = next_cursor
            time.sleep(0.15)
        unique = sorted({int(r["fundingTime"]) for p in target.glob("page_*.json") for r in json.loads(p.read_text(encoding="utf-8"))})
        gaps = np.diff(np.asarray(unique, dtype=np.int64)) if len(unique) > 1 else np.asarray([], dtype=np.int64)
        max_gap = int(gaps.max()) if gaps.size else None
        manifest["symbols"][symbol] = {
            "pages": pages,
            "rows": len(unique),
            "first_ms": unique[0] if unique else None,
            "last_ms": unique[-1] if unique else None,
            "duplicate_timestamps": sum(len(json.loads(p.read_text(encoding="utf-8"))) for p in target.glob("page_*.json")) - len(unique),
            "max_gap_ms": max_gap,
            "coverage_check_24h": bool(unique and unique[0] <= start_ms + 86_400_000 and unique[-1] >= end_ms - 86_400_000 and (max_gap is None or max_gap <= 86_400_000)),
        }
    out = base / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def signal_arrays(bars: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    close = bars["close"].to_numpy(dtype=np.float64)
    macd = indicators.macd(close, 12, 26, 9)[0]
    rsi = rsi_wilder(close, 14)
    atr = atr_wilder(bars["high"].to_numpy(), bars["low"].to_numpy(), close, 14)
    long_signal = np.zeros(close.size, dtype=bool)
    long_signal[1:] = (macd[:-1] <= 0.0) & (macd[1:] > 0.0) & (rsi[1:] > 50.0)
    down_cross = np.zeros(close.size, dtype=bool)
    down_cross[1:] = (macd[:-1] >= 0.0) & (macd[1:] < 0.0)
    return macd, atr, long_signal, down_cross


def _price_at_time(minute: pd.DataFrame, t: int, field: str) -> float:
    times = minute["open_ms"].to_numpy(dtype=np.int64)
    i = int(np.searchsorted(times, t, side="left"))
    if i >= len(times) or int(times[i]) != t:
        raise ValueError(f"Missing minute price at {t}")
    return float(minute[field].iloc[i])


def _funding_between(events: list[dict], start: int, end: int, exit_reason: str) -> float:
    """Funding as fraction of entry notional; conservative positive settlement tie."""
    times = [e["time"] for e in events]
    lo = bisect.bisect_right(times, start)
    hi = bisect.bisect_left(times, end)
    total = sum(e["rate"] * e["mark"] for e in events[lo:hi])
    if hi < len(events) and events[hi]["time"] == end and events[hi]["rate"] > 0 and exit_reason in {"macd_zero_down", "timeout"}:
        total += events[hi]["rate"] * events[hi]["mark"]
    return total


def funding_prefix(events: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    times = np.asarray([e["time"] for e in events], dtype=np.int64)
    values = np.asarray([e["rate"] * e["mark"] for e in events], dtype=np.float64)
    return times, np.r_[0.0, np.cumsum(values)]


def funding_sum(prefix: tuple[np.ndarray, np.ndarray], start_exclusive: int, end_inclusive: int) -> float:
    times, cumulative = prefix
    lo = int(np.searchsorted(times, start_exclusive, side="right"))
    hi = int(np.searchsorted(times, end_inclusive, side="right"))
    return float(cumulative[hi] - cumulative[lo])


def resolve_long_bar(open_price: float, high: float, low: float, stop: float, target: float | None) -> tuple[str | None, float | None]:
    """Conservative OHLC barrier resolution: adverse stop wins ambiguous ties."""
    if open_price <= stop:
        return "stop", open_price
    stop_hit = low <= stop
    target_hit = target is not None and high >= target
    if stop_hit:
        return "stop", stop
    if target_hit:
        return "target", target
    return None, None


def simulate_symbol(
    bars: pd.DataFrame,
    minute: pd.DataFrame,
    funding: list[dict],
    minutes: int,
    split_start: int,
    split_end: int,
    policy: str,
    indicator_pack: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None,
) -> list[dict]:
    width = minutes * 60_000
    macd, atr, signals, down = indicator_pack if indicator_pack is not None else signal_arrays(bars)
    bt = bars["open_ms"].to_numpy(dtype=np.int64)
    mo = minute["open_ms"].to_numpy(dtype=np.int64)
    mh = minute["high"].to_numpy(dtype=np.float64)
    ml = minute["low"].to_numpy(dtype=np.float64)
    mopen = minute["open"].to_numpy(dtype=np.float64)
    mclose = minute["close"].to_numpy(dtype=np.float64)
    trades: list[dict] = []
    busy_until = split_start
    for i in np.flatnonzero(signals):
        signal_close = int(bt[i] + width)
        entry_i = int(i + 1)
        if signal_close <= split_start or signal_close > split_end or entry_i >= len(bt):
            continue
        entry_time = int(bt[entry_i])
        max_end = entry_time + HORIZON_BARS * width
        if entry_time < split_start or max_end > split_end or entry_time < busy_until:
            continue
        atr_i = float(atr[i])
        if not math.isfinite(atr_i) or atr_i <= 0:
            continue
        raw_entry = float(bars["open"].iloc[entry_i])
        stop = raw_entry - STOP_ATR * atr_i
        if stop <= 0 or stop >= raw_entry:
            continue
        risk = raw_entry - stop
        target = raw_entry + TF_R_MULTIPLE[policy] * risk if policy in TF_R_MULTIPLE else None
        down_time = None
        if policy == "macd_zero_down":
            for j in range(entry_i, min(len(bt), entry_i + HORIZON_BARS)):
                if down[j]:
                    down_time = int(bt[j] + width)
                    break
        start_idx = int(np.searchsorted(mo, entry_time, side="left"))
        end_idx = int(np.searchsorted(mo, max_end, side="left"))
        if start_idx >= len(mo) or int(mo[start_idx]) != entry_time or end_idx - start_idx < HORIZON_BARS * minutes:
            continue
        reason = "timeout"
        raw_exit = float(mclose[end_idx - 1])
        exit_time = int(mo[end_idx - 1] + 60_000)
        target_first = False
        stop_first = False
        for k in range(start_idx, end_idx):
            minute_open_time = int(mo[k])
            if down_time is not None and minute_open_time >= down_time:
                raw_exit = float(mopen[k])
                exit_time = minute_open_time
                reason = "macd_zero_down"
                break
            barrier, barrier_price = resolve_long_bar(float(mopen[k]), float(mh[k]), float(ml[k]), stop, target)
            if barrier is not None:
                raw_exit = float(barrier_price)
                exit_time = minute_open_time + 60_000
                reason = barrier
                stop_first = barrier == "stop"
                target_first = barrier == "target"
                break
        fund_fraction = _funding_between(funding, entry_time, exit_time, reason)
        trades.append({
            "signal_time": signal_close,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry": raw_entry,
            "exit": raw_exit,
            "stop": stop,
            "target": target,
            "risk_fraction": risk / raw_entry,
            "bars_held": max(1, int(math.ceil((exit_time - entry_time) / width))),
            "exit_reason": reason,
            "target_first": target_first,
            "stop_first": stop_first,
            "funding_raw_price_units": fund_fraction,
        })
        busy_until = exit_time
    return trades


def trade_net_fraction(trade: dict, fee: float, slippage: float) -> float:
    entry_fill = trade["entry"] * (1.0 + slippage)
    exit_fill = trade["exit"] * (1.0 - slippage)
    pnl = (exit_fill - entry_fill) / trade["entry"]
    fees = fee * (entry_fill + exit_fill) / trade["entry"]
    funding = trade["funding_raw_price_units"] / trade["entry"]
    return pnl - fees - funding


def daily_closes(minute: pd.DataFrame, start_ms: int, end_ms: int) -> tuple[np.ndarray, np.ndarray]:
    x = minute[(minute.open_ms >= start_ms) & (minute.open_ms < end_ms)].copy()
    x["day"] = (x["open_ms"] // 86_400_000) * 86_400_000
    d = x.groupby("day", sort=True).agg(close=("close", "last"), n=("open_ms", "size"))
    expected_days = (end_ms - start_ms) // 86_400_000
    if len(d) != expected_days or (d["n"] != 1440).any():
        raise ValueError(f"Incomplete UTC daily marks in split {start_ms}:{end_ms}")
    return d.index.to_numpy(dtype=np.int64) + 86_400_000 - 1, d["close"].to_numpy(dtype=np.float64)


def equity_curve_for_symbol(
    minute: pd.DataFrame,
    trades: list[dict],
    funding: list[dict],
    start_ms: int,
    end_ms: int,
    fee: float,
    slippage: float,
    daily_mark: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    daily_end, closes = daily_mark if daily_mark is not None else daily_closes(minute, start_ms, end_ms)
    funding_cum = funding_prefix(funding)
    trade_states = []
    equity = 1.0
    for t in trades:
        t = dict(t)
        t["equity_before"] = equity
        t["net_fraction"] = trade_net_fraction(t, fee, slippage)
        t["entry_fill"] = t["entry"] * (1.0 + slippage)
        t["entry_fee"] = t["equity_before"] * (t["entry_fill"] / t["entry"]) * fee
        t["qty"] = t["equity_before"] / t["entry"]
        equity *= max(0.0, 1.0 + t["net_fraction"])
        trade_states.append(t)
    curve = np.ones(len(daily_end), dtype=np.float64)
    j = 0
    realized = 1.0
    for d, (day_end, mark) in enumerate(zip(daily_end, closes)):
        while j < len(trade_states) and trade_states[j]["exit_time"] <= day_end + 1:
            realized = trade_states[j]["equity_before"] * max(0.0, 1.0 + trade_states[j]["net_fraction"])
            j += 1
        if j < len(trade_states) and trade_states[j]["entry_time"] <= day_end and trade_states[j]["exit_time"] > day_end + 1:
            t = trade_states[j]
            paid = funding_sum(funding_cum, t["entry_time"], int(day_end + 1)) * t["qty"]
            marked = t["equity_before"] + t["qty"] * (mark - t["entry_fill"]) - t["entry_fee"] - paid
            curve[d] = max(0.0, marked)
        else:
            curve[d] = max(0.0, realized)
    return curve


def buy_hold_curve(minute: pd.DataFrame, funding: list[dict], start_ms: int, end_ms: int, fee: float, slippage: float, daily_mark: tuple[np.ndarray, np.ndarray] | None = None) -> np.ndarray:
    d_end, closes = daily_mark if daily_mark is not None else daily_closes(minute, start_ms, end_ms)
    raw_entry = _price_at_time(minute, start_ms, "open")
    entry_fill = raw_entry * (1 + slippage)
    qty = 1.0 / raw_entry
    entry_fee = qty * entry_fill * fee
    funding_cum = funding_prefix(funding)
    curve = []
    for day_end, mark in zip(d_end, closes):
        paid = funding_sum(funding_cum, start_ms, int(day_end + 1)) * qty
        value = 1.0 + qty * (mark - entry_fill) - entry_fee - paid
        if day_end + 1 >= end_ms:
            exit_fill = mark * (1 - slippage)
            value -= qty * mark * fee
            value += qty * (exit_fill - mark)
        curve.append(max(0.0, value))
    return np.asarray(curve, dtype=np.float64)


def curve_stats(curve: np.ndarray, start_ms: int, end_ms: int) -> dict:
    curve = np.asarray(curve, dtype=np.float64)
    if not curve.size or curve[0] <= 0 or curve[-1] <= 0:
        return {"final_equity": float(curve[-1]) if curve.size else None, "cagr": None, "mdd_pct": None, "sharpe": None}
    rets = np.diff(np.r_[1.0, curve])
    years = (end_ms - start_ms) / (365.25 * 86_400_000)
    peaks = np.maximum.accumulate(curve)
    mdd = float(np.max(1.0 - curve / peaks))
    sd = float(np.std(rets, ddof=1)) if rets.size > 1 else 0.0
    sharpe = float(np.mean(rets) / sd * math.sqrt(365.25)) if sd > 0 else 0.0
    return {"final_equity": float(curve[-1]), "cagr": float(curve[-1] ** (1.0 / years) - 1.0), "mdd_pct": mdd * 100.0, "sharpe": sharpe}


def quarterly_returns(curve: np.ndarray, start_ms: int, end_ms: int) -> list[dict]:
    curve = np.asarray(curve, dtype=np.float64)
    day_count = (end_ms - start_ms) // 86_400_000
    if curve.size != day_count:
        raise ValueError("Daily equity length differs from split duration")
    keys = []
    for i in range(day_count):
        dt = datetime.fromtimestamp((start_ms + (i + 1) * 86_400_000) / 1000, timezone.utc)
        keys.append((dt.year, (dt.month - 1) // 3 + 1))
    out = []
    for q in sorted(set(keys)):
        indices = [i for i, key in enumerate(keys) if key == q]
        before = 1.0 if indices[0] == 0 else float(curve[indices[0] - 1])
        after = float(curve[indices[-1]])
        out.append({"quarter": f"{q[0]}-Q{q[1]}", "return": after / before - 1.0})
    return out


def wilson(successes: int, n: int) -> list[float | None]:
    if n == 0:
        return [None, None]
    z = 1.959963984540054
    p = successes / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [mid - half, mid + half]


def block_bootstrap(excess_daily: np.ndarray, seed: int = BOOTSTRAP_SEED) -> dict:
    x = np.asarray(excess_daily, dtype=np.float64)
    if x.size < 30:
        return {"mean_daily_excess": float(np.mean(x)) if x.size else None, "ci95": [None, None], "p_one_sided": None}
    rng = np.random.default_rng(seed)
    n = x.size
    blocks = math.ceil(n / BLOCK_DAYS)
    offsets = np.arange(BLOCK_DAYS)
    samples = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    centered = x - np.mean(x)
    null_samples = np.empty(BOOTSTRAP_REPLICATES, dtype=np.float64)
    for b in range(BOOTSTRAP_REPLICATES):
        starts = rng.integers(0, n, size=blocks)
        idx = np.concatenate([(s + offsets) % n for s in starts])[:n]
        samples[b] = np.mean(x[idx])
        null_samples[b] = np.mean(centered[idx])
    lo, hi = np.quantile(samples, [0.025, 0.975])
    p = (1 + int(np.sum(null_samples >= np.mean(x)))) / (BOOTSTRAP_REPLICATES + 1)
    return {"mean_daily_excess": float(np.mean(x)), "ci95": [float(lo), float(hi)], "p_one_sided": float(p)}


def holm(p_values: list[float | None]) -> list[float | None]:
    indexed = [(i, p) for i, p in enumerate(p_values) if p is not None]
    indexed.sort(key=lambda pair: pair[1])
    n = len(indexed)
    out: list[float | None] = [None] * len(p_values)
    running = 0.0
    for rank, (i, p) in enumerate(indexed):
        running = max(running, min(1.0, (n - rank) * p))
        out[i] = running
    return out


def _split_bounds() -> dict[str, tuple[int, int]]:
    return {
        "train": (START_MS, TRAIN_END_MS),
        "validation": (TRAIN_END_MS, VALIDATION_END_MS),
        "final": (VALIDATION_END_MS, FINAL_END_MS),
    }


def _select_policy(results: list[dict]) -> list[dict]:
    selected = []
    for minutes in TIMEFRAMES_MIN:
        candidates = [r for r in results if r["split"] == "validation" and r["timeframe_min"] == minutes]
        eligible = [r for r in candidates if r["base"]["strategy"]["cagr"] is not None
                    and r["base"]["strategy"]["cagr"] > r["base"]["buy_hold"]["cagr"]
                    and r["base"]["mean_net_trade_pct"] > 0
                    and r["base"]["trade_count"] >= 30
                    and r["base"]["strategy"]["mdd_pct"] <= r["base"]["buy_hold"]["mdd_pct"]]
        if eligible:
            order = {name: i for i, name in enumerate(EXIT_POLICIES)}
            best = sorted(eligible, key=lambda r: (-r["base"]["strategy"]["cagr"], r["base"]["turnover"], order[r["exit_policy"]]))[0]
            selected.append({"timeframe_min": minutes, "exit_policy": best["exit_policy"], "validation_cagr": best["base"]["strategy"]["cagr"], "validation_buy_hold_cagr": best["base"]["buy_hold"]["cagr"], "validation_mdd_pct": best["base"]["strategy"]["mdd_pct"], "validation_buy_hold_mdd_pct": best["base"]["buy_hold"]["mdd_pct"]})
    return selected


def run_screen(db_path: str | Path, run_dir: str | Path) -> dict:
    run_dir = Path(run_dir)
    results = []
    splits = _split_bounds()
    screen_end = VALIDATION_END_MS
    for symbol in SYMBOLS:
        minute = read_symbol(db_path, symbol, screen_end)
        if minute.empty or int(minute.open_ms.iloc[0]) > START_MS or int(minute.open_ms.iloc[-1]) < TRAIN_END_MS - 60_000:
            raise ValueError(f"Insufficient common-window price data for {symbol}")
        funding_cache = {name: load_funding(run_dir, SCREEN_FUNDING_ID, symbol, *bounds, minute) for name, bounds in splits.items() if name != "final"}
        daily_cache = {name: daily_closes(minute, *bounds) for name, bounds in splits.items() if name != "final"}
        bh_cache = {}
        for name, (start_ms, end_ms) in splits.items():
            if name == "final":
                continue
            events = funding_cache[name]
            daily_mark = daily_cache[name]
            bh_cache[(name, "base")] = buy_hold_curve(minute, events, start_ms, end_ms, FEE_BASE, SLIPPAGE_BASE, daily_mark)
            bh_cache[(name, "stress")] = buy_hold_curve(minute, events, start_ms, end_ms, 2 * FEE_BASE, 2 * SLIPPAGE_BASE, daily_mark)
        for tf in TIMEFRAMES_MIN:
            bars = resample_minutes(minute, tf)
            indicator_pack = signal_arrays(bars)
            signals = indicator_pack[2]
            for split_name in ("train", "validation"):
                start_ms, end_ms = splits[split_name]
                events = funding_cache[split_name]
                for policy in EXIT_POLICIES:
                    trades = simulate_symbol(bars, minute, events, tf, start_ms, end_ms, policy, indicator_pack)
                    base_curve = equity_curve_for_symbol(minute, trades, events, start_ms, end_ms, FEE_BASE, SLIPPAGE_BASE, daily_cache[split_name])
                    stress_curve = equity_curve_for_symbol(minute, trades, events, start_ms, end_ms, 2 * FEE_BASE, 2 * SLIPPAGE_BASE, daily_cache[split_name])
                    bh_base = bh_cache[(split_name, "base")]
                    bh_stress = bh_cache[(split_name, "stress")]
                    nets = [trade_net_fraction(t, FEE_BASE, SLIPPAGE_BASE) for t in trades]
                    gross_wins = sum(t["target_first"] for t in trades)
                    net_wins = sum(x > 0 for x in nets)
                    result = {
                        "split": split_name,
                        "symbol": symbol,
                        "timeframe_min": tf,
                        "exit_policy": policy,
                        "signal_count": int(np.sum(signals[(bars.open_ms.to_numpy() >= start_ms) & (bars.open_ms.to_numpy() + tf * 60_000 < end_ms)])),
                        "trade_count": len(trades),
                        "target_first_count": int(gross_wins),
                        "stop_first_count": int(sum(t["stop_first"] for t in trades)),
                        "timeout_or_rule_exit_count": int(len(trades) - gross_wins - sum(t["stop_first"] for t in trades)),
                        "target_first_rate": gross_wins / len(trades) if trades and policy in TF_R_MULTIPLE else None,
                        "target_first_wilson95": wilson(gross_wins, len(trades)) if policy in TF_R_MULTIPLE else [None, None],
                        "net_win_count": int(net_wins),
                        "net_win_rate": net_wins / len(trades) if trades else None,
                        "net_win_wilson95": wilson(net_wins, len(trades)),
                        "base": {"strategy": curve_stats(base_curve, start_ms, end_ms), "buy_hold": curve_stats(bh_base, start_ms, end_ms), "mean_net_trade_pct": float(np.mean(nets) * 100) if nets else 0.0, "median_net_trade_pct": float(np.median(nets) * 100) if nets else 0.0},
                        "stress": {"strategy": curve_stats(stress_curve, start_ms, end_ms), "buy_hold": curve_stats(bh_stress, start_ms, end_ms), "mean_net_trade_pct": float(np.mean([trade_net_fraction(t, 2 * FEE_BASE, 2 * SLIPPAGE_BASE) for t in trades]) * 100) if trades else 0.0},
                        "turnover": float(len(trades) / ((end_ms - start_ms) / 86_400_000)),
                        "trades": trades,
                        "equity_base": base_curve.tolist(),
                        "bh_equity_base": bh_base.tolist(),
                        "equity_stress": stress_curve.tolist(),
                        "bh_equity_stress": bh_stress.tolist(),
                    }
                    results.append(result)
    # Aggregate six equal symbol sleeves per split/timeframe/exit and cost case.
    aggregate = []
    for split_name in ("train", "validation"):
        start_ms, end_ms = splits[split_name]
        for tf in TIMEFRAMES_MIN:
            for policy in EXIT_POLICIES:
                rows = [r for r in results if r["split"] == split_name and r["timeframe_min"] == tf and r["exit_policy"] == policy]
                p = len(rows[0]["equity_base"]) if rows else 0
                record = {"split": split_name, "timeframe_min": tf, "exit_policy": policy}
                for cost_name in ("base", "stress"):
                    strat = np.mean([np.asarray(r[f"equity_{cost_name}"]) for r in rows], axis=0)
                    bh = np.mean([np.asarray(r[f"bh_equity_{cost_name}"]) for r in rows], axis=0)
                    trade_returns = [trade_net_fraction(t, FEE_BASE if cost_name == "base" else 2 * FEE_BASE, SLIPPAGE_BASE if cost_name == "base" else 2 * SLIPPAGE_BASE) for r in rows for t in r["trades"]]
                    days = (end_ms - start_ms) / 86_400_000
                    target_n = sum(r["trade_count"] for r in rows if r["target_first_rate"] is not None)
                    target_wins = sum(r["target_first_count"] for r in rows if r["target_first_rate"] is not None)
                    win_count = sum(sum(trade_net_fraction(t, FEE_BASE if cost_name == "base" else 2 * FEE_BASE, SLIPPAGE_BASE if cost_name == "base" else 2 * SLIPPAGE_BASE) > 0 for t in r["trades"]) for r in rows)
                    record[cost_name] = {"strategy": curve_stats(strat, start_ms, end_ms), "buy_hold": curve_stats(bh, start_ms, end_ms), "mean_net_trade_pct": float(np.mean(trade_returns) * 100) if trade_returns else 0.0, "median_net_trade_pct": float(np.median(trade_returns) * 100) if trade_returns else 0.0, "net_win_count": int(win_count), "net_win_rate": win_count / len(trade_returns) if trade_returns else None, "net_win_wilson95": wilson(win_count, len(trade_returns)), "trade_count": len(trade_returns), "signal_count": int(sum(r["signal_count"] for r in rows)), "turnover": float(len(trade_returns) / days), "target_first_count": int(target_wins) if target_n else None, "target_trade_count": int(target_n) if target_n else None, "target_first_rate": target_wins / target_n if target_n else None, "target_first_wilson95": wilson(target_wins, target_n) if target_n else [None, None], "strategy_daily_returns": np.diff(np.r_[1.0, strat]).tolist(), "buy_hold_daily_returns": np.diff(np.r_[1.0, bh]).tolist()}
                aggregate.append(record)
    result_obj = {
        "run_id": "2026-11-16-r004-macd-zero-rsi50",
        "phase": "screen",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_sha256": sha256_file(__file__),
        "indicator_code_sha256": sha256_file(indicators.__file__),
        "price_db_sha256": sha256_file(db_path),
        "funding_snapshot_id": SCREEN_FUNDING_ID,
        "funding_manifest_sha256": sha256_file(Path(run_dir) / "funding" / SCREEN_FUNDING_ID / "manifest.json"),
        "funding_coverage_checks": json.loads((Path(run_dir) / "funding" / SCREEN_FUNDING_ID / "manifest.json").read_text(encoding="utf-8"))["symbols"],
        "splits": {k: [v[0], v[1]] for k, v in splits.items() if k != "final"},
        "symbols": list(SYMBOLS),
        "timeframes_min": list(TIMEFRAMES_MIN),
        "exit_policies": list(EXIT_POLICIES),
        "aggregate_results": aggregate,
        "symbol_results": [{k: v for k, v in r.items() if not k.endswith("equity_base") and not k.endswith("equity_stress") and not k.endswith("trades")} for r in results],
        "trial_cells": len(aggregate),
        "selected_validation": _select_policy(aggregate),
    }
    return result_obj


def run_final(db_path: str | Path, run_dir: str | Path, selection_path: str | Path, expected_selection_sha: str) -> dict:
    if sha256_file(selection_path) != expected_selection_sha:
        raise ValueError("Selection file SHA-256 differs from the frozen expected value")
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    if selection.get("run_id") != "2026-11-16-r004-macd-zero-rsi50" or selection.get("selected_validation") is None:
        raise ValueError("Invalid validation selection artifact")
    if selection.get("code_sha256") != sha256_file(__file__) or selection.get("indicator_code_sha256") != sha256_file(indicators.__file__):
        raise ValueError("Experiment code differs from the frozen validation implementation")
    selected = selection["selected_validation"]
    final_manifest = Path(run_dir) / "funding" / FINAL_FUNDING_ID / "manifest.json"
    if not final_manifest.exists() or sha256_file(final_manifest) == selection.get("funding_manifest_sha256"):
        raise ValueError("Final phase must use the extended funding manifest frozen after validation")
    # Final implementation is intentionally a separate phase. The current runner
    # reports the selected set, but does not silently tune it or reopen validation.
    bounds = _split_bounds()["final"]
    results = []
    for symbol in SYMBOLS:
        minute = read_symbol(db_path, symbol, bounds[1])
        events = load_funding(run_dir, FINAL_FUNDING_ID, symbol, bounds[0], bounds[1], minute)
        for choice in selected:
            tf, policy = int(choice["timeframe_min"]), choice["exit_policy"]
            bars = resample_minutes(minute, tf)
            trades = simulate_symbol(bars, minute, events, tf, *bounds, policy)
            base_curve = equity_curve_for_symbol(minute, trades, events, *bounds, FEE_BASE, SLIPPAGE_BASE)
            stress_curve = equity_curve_for_symbol(minute, trades, events, *bounds, 2 * FEE_BASE, 2 * SLIPPAGE_BASE)
            bh = buy_hold_curve(minute, events, *bounds, FEE_BASE, SLIPPAGE_BASE)
            bh_stress = buy_hold_curve(minute, events, *bounds, 2 * FEE_BASE, 2 * SLIPPAGE_BASE)
            results.append({"symbol": symbol, "timeframe_min": tf, "exit_policy": policy, "trades": trades, "equity_base": base_curve.tolist(), "equity_stress": stress_curve.tolist(), "bh_base": bh.tolist(), "bh_stress": bh_stress.tolist(), "trade_count": len(trades), "signal_count": int(sum(t["signal_time"] >= bounds[0] for t in trades))})
    aggregate = []
    pvals = []
    for choice in selected:
        tf, policy = int(choice["timeframe_min"]), choice["exit_policy"]
        rows = [r for r in results if r["timeframe_min"] == tf and r["exit_policy"] == policy]
        strat = np.mean([r["equity_base"] for r in rows], axis=0)
        bh = np.mean([r["bh_base"] for r in rows], axis=0)
        q_strategy = quarterly_returns(strat, *bounds)
        q_bh = quarterly_returns(bh, *bounds)
        q_excess = [{"quarter": s["quarter"], "strategy": s["return"], "buy_hold": b["return"], "excess": s["return"] - b["return"]} for s, b in zip(q_strategy, q_bh)]
        diff = np.diff(np.r_[1.0, strat]) - np.diff(np.r_[1.0, bh])
        boot = block_bootstrap(diff, BOOTSTRAP_SEED + tf)
        pvals.append(boot["p_one_sided"])
        stress_strat = np.mean([r["equity_stress"] for r in rows], axis=0)
        stress_bh = np.mean([r["bh_stress"] for r in rows], axis=0)
        net_returns = [trade_net_fraction(t, FEE_BASE, SLIPPAGE_BASE) for r in rows for t in r["trades"]]
        net_stress = [trade_net_fraction(t, 2 * FEE_BASE, 2 * SLIPPAGE_BASE) for r in rows for t in r["trades"]]
        aggregate.append({"timeframe_min": tf, "exit_policy": policy, "base_strategy": curve_stats(strat, *bounds), "base_buy_hold": curve_stats(bh, *bounds), "base_excess_bootstrap": boot, "stress_strategy": curve_stats(stress_strat, *bounds), "stress_buy_hold": curve_stats(stress_bh, *bounds), "mean_net_trade_pct": float(np.mean(net_returns) * 100) if net_returns else 0.0, "stress_mean_net_trade_pct": float(np.mean(net_stress) * 100) if net_stress else 0.0, "trade_count": sum(r["trade_count"] for r in rows), "signal_count": sum(r["signal_count"] for r in rows), "quarterly_excess": q_excess, "positive_excess_quarters": sum(q["excess"] > 0 for q in q_excess), "symbol_results": [{"symbol": r["symbol"], "trade_count": r["trade_count"], "base_strategy": curve_stats(r["equity_base"], *bounds), "base_buy_hold": curve_stats(r["bh_base"], *bounds)} for r in rows]})
    adjusted = holm(pvals)
    for row, adj in zip(aggregate, adjusted):
        row["holm_adjusted_p"] = adj
    return {"run_id": "2026-11-16-r004-macd-zero-rsi50", "phase": "final_holdout", "code_sha256": sha256_file(__file__), "indicator_code_sha256": sha256_file(indicators.__file__), "selection_sha256": expected_selection_sha, "price_db_sha256": sha256_file(db_path), "funding_snapshot_id": FINAL_FUNDING_ID, "funding_manifest_sha256": sha256_file(final_manifest), "funding_coverage_checks": json.loads(final_manifest.read_text(encoding="utf-8"))["symbols"], "results": aggregate, "selected_timeframe_tests": len(selected)}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--fetch-funding-end-ms", type=int)
    p.add_argument("--funding-snapshot-id")
    p.add_argument("--screen", action="store_true")
    p.add_argument("--final", action="store_true")
    p.add_argument("--selection")
    p.add_argument("--expected-selection-sha")
    p.add_argument("--output")
    a = p.parse_args()
    if a.fetch_funding_end_ms:
        if not a.funding_snapshot_id:
            p.error("--funding-snapshot-id is required when fetching funding data")
        print(json.dumps(fetch_funding(a.run_dir, a.fetch_funding_end_ms, a.funding_snapshot_id), indent=2))
        return 0
    if a.screen:
        result = run_screen(a.db, a.run_dir)
    elif a.final and a.selection and a.expected_selection_sha:
        result = run_final(a.db, a.run_dir, a.selection, a.expected_selection_sha)
    else:
        p.error("choose --fetch-funding-end-ms, --screen, or --final with selection and expected SHA")
    serialized = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
    if a.output:
        Path(a.output).parent.mkdir(parents=True, exist_ok=True)
        Path(a.output).write_text(serialized + "\n", encoding="utf-8")
    print(json.dumps({"run_id": result["run_id"], "phase": result.get("phase"), "cells": len(result.get("aggregate_results", result.get("results", []))), "selected": len(result.get("selected_validation", [])), "price_db_sha256": result["price_db_sha256"], "funding_manifest_sha256": result["funding_manifest_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
