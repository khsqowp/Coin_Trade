"""Preregistered MACD-zero/RSI-50 long backtest on local 1m futures candles."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from chart_predictor.indicators import atr, macd, rsi
from chart_predictor.resample import resample_frame

START_MS = 1_784_246_400_000
END_MS = 1_791_504_000_000
SPLIT_MS = START_MS + int((END_MS - START_MS) * 0.70)
MINUTE = 60_000
BAR = 5 * MINUTE
MAX_HOLD = 20
FEE_BASE = 0.0005
EXITS = ("macd_zero_down", "rsi_below_50", "fixed_2R", "chandelier_3ATR", "time")


def entry_signal_mask(macd_line, rsi_values):
    m, r = np.asarray(macd_line, float), np.asarray(rsi_values, float)
    out = np.zeros(len(m), dtype=bool)
    out[1:] = (m[:-1] <= 0) & (m[1:] > 0) & (r[1:] > 50)
    return out


def exit_signal_mask(macd_line, rsi_values):
    m, r = np.asarray(macd_line, float), np.asarray(rsi_values, float)
    macd_down, rsi_down = np.zeros(len(m), bool), np.zeros(len(m), bool)
    macd_down[1:] = (m[:-1] >= 0) & (m[1:] < 0)
    rsi_down[1:] = (r[:-1] >= 50) & (r[1:] < 50)
    return {"macd_zero_down": macd_down, "rsi_below_50": rsi_down}


def resolve_barrier(open_price, high, low, stop, target=None):
    if open_price <= stop:
        return "stop_gap", float(open_price)
    if target is not None and open_price >= target:
        return "target", float(target)
    if low <= stop:
        return "stop", float(stop)
    if target is not None and high >= target:
        return "target", float(target)
    return None


def trade_net_return(entry, exit_price, fee_per_side):
    gross = exit_price / entry - 1
    return gross, gross - fee_per_side * (1 + exit_price / entry)


def _load_symbol(db_path, symbol):
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        raw = pd.read_sql_query(
            "SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles "
            "WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",
            db, params=(symbol, START_MS, END_MS))
    expected = np.arange(START_MS, END_MS, MINUTE, dtype=np.int64)
    if len(raw) != len(expected) or not np.array_equal(raw.t_open_ms.to_numpy(), expected):
        raise ValueError(f"{symbol}: expected {len(expected)} continuous 1m rows, got {len(raw)}")
    bars = resample_frame(raw, "5m", now_ms=END_MS)
    if len(bars) * 5 != len(raw):
        raise ValueError(f"{symbol}: incomplete 5m aggregation")
    close = bars.c.to_numpy(float)
    mline, _, _ = macd(close)
    rv = rsi(close, 14)
    av = atr(bars.h, bars.l, close, 14)
    signals = entry_signal_mask(mline, rv)
    exits = exit_signal_mask(mline, rv)
    bars["macd"], bars["rsi"], bars["atr"] = mline, rv, av
    bars["entry_signal"] = signals
    bars["macd_exit"] = exits["macd_zero_down"]
    bars["rsi_exit"] = exits["rsi_below_50"]
    input_hash = hashlib.sha256(raw.to_csv(index=False, float_format="%.12g").encode()).hexdigest()
    return raw, bars, input_hash


def _simulate(raw, bars, symbol, split_ms, fee, exit_type):
    """One position at a time; fixed 20-bar signal cooldown for paired exits."""
    minute_by_open = {int(row.t_open_ms): row for row in raw.itertuples(index=False)}
    trades, next_allowed = [], 0
    for i in range(1, len(bars) - MAX_HOLD - 1):
        if i < next_allowed or not bool(bars.entry_signal.iloc[i]):
            continue
        entry_i = i + 1
        entry_ms = int(bars.t_open_ms.iloc[entry_i])
        expiry_i = entry_i + MAX_HOLD
        expiry_ms = int(bars.t_open_ms.iloc[expiry_i])
        if expiry_ms >= END_MS or (split_ms and expiry_ms >= split_ms):
            continue
        entry = float(bars.o.iloc[entry_i])
        risk = 2 * float(bars.atr.iloc[i])
        if not np.isfinite(risk) or risk <= 0:
            continue
        stop, target = entry - risk, (entry + 2 * risk if exit_type == "fixed_2R" else None)
        highwater, reason, out, exit_ms = entry, "time", None, None
        # Inspect 20 completed bars only; the timeout fills at the following open.
        for j in range(entry_i, expiry_i):
            bar_open = int(bars.t_open_ms.iloc[j])
            for minute in range(bar_open, bar_open + BAR, MINUTE):
                candle = minute_by_open.get(minute)
                if candle is None:
                    raise ValueError(f"{symbol}: missing minute candle at {minute}")
                result = resolve_barrier(float(candle.o), float(candle.h), float(candle.l), stop, target)
                if result:
                    reason, out = result
                    exit_ms = minute
                    break
            if out is not None:
                break
            highwater = max(highwater, float(bars.h.iloc[j]))
            if exit_type == "chandelier_3ATR":
                trail = highwater - 3 * float(bars.atr.iloc[j])
                stop = max(stop, trail)
            if exit_type in ("macd_zero_down", "rsi_below_50") and bool(bars[f"{exit_type.split('_')[0]}_exit"].iloc[j]):
                # Signal is known at bar close; execute next bar open, respecting stop gap.
                next_open = float(bars.o.iloc[j + 1])
                if next_open <= stop:
                    reason, out = "stop_gap", next_open
                else:
                    reason, out = "signal", next_open
                exit_ms = int(bars.t_open_ms.iloc[j + 1])
                break
        if out is None:
            out = float(bars.o.iloc[expiry_i])
            j = expiry_i - 1
            exit_ms = int(bars.t_open_ms.iloc[expiry_i])
        _, net = trade_net_return(entry, out, fee)
        trades.append({"symbol": symbol, "entry_ms": entry_ms, "exit_ms": exit_ms,
                       "entry": entry, "exit": out, "reason": reason, "net_return": net,
                       "net_R": net * entry / risk,
                       "bars_held": (j + 1 - entry_i if reason in ("signal", "time") else j - entry_i + 1)})
        next_allowed = entry_i + MAX_HOLD
    return trades


def _metrics(trades):
    if not trades:
        return {"trades": 0, "win_rate": None, "wilson95": None, "mean_net_R": None,
                "median_net_R": None, "profit_factor": None, "avg_minutes": None, "exit_reasons": {}}
    vals = np.array([t["net_R"] for t in trades])
    wins = int(np.sum(vals > 0)); n = len(vals); z = 1.959963984540054
    den = 1 + z*z/n
    center = (wins/n + z*z/(2*n))/den
    half = z*np.sqrt((wins/n*(1-wins/n)+z*z/(4*n))/n)/den
    gains, losses = vals[vals > 0].sum(), -vals[vals < 0].sum()
    return {"trades": n, "win_rate": wins/n, "wilson95": [max(0, center-half), min(1, center+half)],
            "mean_net_R": float(vals.mean()), "median_net_R": float(np.median(vals)),
            "profit_factor": float(gains/losses) if losses else (None if gains == 0 else "inf"),
            "avg_minutes": float(np.mean([t["bars_held"]*5 for t in trades])),
            "exit_reasons": pd.Series([t["reason"] for t in trades]).value_counts().to_dict()}


def _block_ci(trades, baseline, seed=20261115, reps=5000):
    a = pd.DataFrame(trades).set_index(["symbol", "entry_ms"])["net_R"]
    b = pd.DataFrame(baseline).set_index(["symbol", "entry_ms"])["net_R"]
    pair = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna().reset_index()
    pair["day"] = pair.entry_ms // 86_400_000
    daily = pair.groupby("day").apply(lambda x: (x.a-x.b).mean(), include_groups=False).to_numpy()
    if len(daily) < 2:
        return {"days": int(len(daily)), "mean_difference": None, "ci95": None}
    rng = np.random.default_rng(seed)
    draws = np.mean(rng.choice(daily, (reps, len(daily)), replace=True), axis=1)
    return {"days": int(len(daily)), "mean_difference": float(daily.mean()),
            "ci95": [float(x) for x in np.quantile(draws, [0.025, 0.975])]}


def run(db_path, output_dir):
    loaded, hashes = {}, {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        raw, bars, hashes[symbol] = _load_symbol(db_path, symbol)
        loaded[symbol] = (raw, bars)
    train = {}
    for exit_type in EXITS:
        train[exit_type] = []
        for symbol, (raw, bars) in loaded.items():
            train[exit_type] += _simulate(raw, bars, symbol, SPLIT_MS, FEE_BASE, exit_type)
    eligible = [e for e in EXITS[:-1] if len(train[e]) >= 30 and
                _metrics(train[e])["mean_net_R"] > 0 and _metrics(train[e])["profit_factor"] not in (None, "inf") and
                _metrics(train[e])["profit_factor"] > 1]
    # Always treat the later segment as conditional; serialize it only if training selects a rule.
    selected = max(eligible, key=lambda e: (_metrics(train[e])["mean_net_R"], -EXITS.index(e))) if eligible else None
    report = {"status": "exploratory", "preregistration": "docs/research/macd_zero_rsi_backtest_prereg_20261115.md",
              "window_utc": ["2026-07-17T00:00:00Z", "2026-10-09T00:00:00Z"],
              "split_utc": pd.to_datetime(SPLIT_MS, unit="ms", utc=True).isoformat(),
              "symbols": {s: {"one_minute_rows": 120960, "five_minute_bars": 24192, "selected_window_sha256": hashes[s]} for s in hashes},
              "fees_per_side": {"base": FEE_BASE, "stress": 0.001},
              "entry": "5m MACD(12,26) line crosses <=0 to >0; same close RSI(14)>50; next 5m open",
              "train": {
                  e: {"pooled": _metrics(train[e]), "by_symbol": {
                      symbol: _metrics([t for t in train[e] if t["symbol"] == symbol])
                      for symbol in loaded}}
                  for e in EXITS},
              "eligible_exits": eligible, "selected_exit": selected,
              "holdout": None, "holdout_trade_files_written": False,
              "strategy_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "caveats": ["Only two major coins and 84 days; not generalizable or the 80% accuracy gate.",
                          "Existing research window is not an untouched sealed evaluation.",
                          "No spread, slippage, impact, funding or liquidation model; returns may be overstated."]}
    if selected:
        report["holdout"] = {}
        holdout = {selected: [], "time": []}
        for kind in holdout:
            for symbol, (raw, bars) in loaded.items():
                holdout[kind] += _simulate(raw, bars, symbol, None, FEE_BASE, kind)
            holdout[kind] = [t for t in holdout[kind] if t["entry_ms"] >= SPLIT_MS]
        for fee_name, fee in (("base", FEE_BASE), ("stress", 0.001)):
            report["holdout"][fee_name] = {}
            for kind in (selected, "time"):
                if fee == FEE_BASE:
                    trades = holdout[kind]
                else:
                    trades = []
                    for symbol, (raw, bars) in loaded.items():
                        trades += _simulate(raw, bars, symbol, None, fee, kind)
                    trades = [t for t in trades if t["entry_ms"] >= SPLIT_MS]
                report["holdout"][fee_name][kind] = _metrics(trades)
                if fee_name == "base":
                    report.setdefault("holdout_trade_rows", {})[kind] = trades
            a = report["holdout_trade_rows"][selected]
            b = report["holdout_trade_rows"]["time"]
            report["holdout"][fee_name]["paired_utc_day_block_bootstrap"] = _block_ci(a, b)
        report["holdout_trade_files_written"] = True
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    trade_rows = report.pop("holdout_trade_rows", {})
    (outdir / "macd_zero_rsi_report.json").write_text(json.dumps(report, indent=2, allow_nan=False, default=str)+"\n")
    for name, rows in train.items():
        pd.DataFrame(rows).to_csv(outdir / f"train_{name}_trades.csv", index=False)
    for name, rows in trade_rows.items():
        pd.DataFrame(rows).to_csv(outdir / f"holdout_{name}_trades.csv", index=False)
    (outdir / "macd_zero_rsi_report.md").write_text(_markdown(report)+"\n")
    return report


def _markdown(report):
    lines = ["# MACD zero-cross + RSI(14)>50 backtest", "", "Status: exploratory; no claim of a validated edge.",
             "", f"Selected exit on training segment: `{report['selected_exit']}`.", "", "## Training results", "",
             "| Exit | Trades | Win rate (Wilson 95%) | Mean net R | Median net R | PF | Avg hold (min) |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for name, result in report["train"].items():
        m = result["pooled"]
        ci = m["wilson95"]
        wr = "n/a" if ci is None else f"{m['win_rate']:.1%} ({ci[0]:.1%}–{ci[1]:.1%})"
        lines.append(f"| {name} | {m['trades']} | {wr} | {m['mean_net_R']} | {m['median_net_R']} | {m['profit_factor']} | {m['avg_minutes']} |")
    lines += ["", "## Conditional holdout", "", json.dumps(report["holdout"], indent=2, ensure_ascii=False), "",
              "## Limitations", ""] + [f"- {x}" for x in report["caveats"]]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-db", required=True, help="Existing candles.sqlite, opened read-only")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.data_db, args.output_dir), indent=2, default=str))


if __name__ == "__main__":
    main()
