"""P7-D native-bar SuperTrend replay.

Data are direct Binance 1h/4h bars, not the main 1m-resampled pipeline, so
results are strategy-level comparable to P5 only. Native 1h bars cannot scan
within-bar chronology: if stop and target are both touched in one bar, stop
wins conservatively. Entry is next 1h open; timeout is at most 12 entry bars.
"""
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import indicators
from .indicators import atr
from .setups import generate_signals
from .setup_backtest import FEE, TIMEFRAME_WIDTH, _metrics, htf_direction_at, load_universe

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "candles_1h_extended.sqlite"
OUT = ROOT / "data" / "p7d"
WIDTH = TIMEFRAME_WIDTH["60m"]
HTF_WIDTH = TIMEFRAME_WIDTH["240m"]


def split_boundary(earliest_ms, latest_ms):
    """Return exclusive 70% calendar cutoff and inclusive observed end."""
    return int(earliest_ms + (latest_ms - earliest_ms) * 0.70)


def fold_for(stamp_ms, start_ms, cutoff_ms):
    return min(4, max(0, int((stamp_ms - start_ms) / (cutoff_ms - start_ms) * 5)))


def htf_aligned(htf_open_ms, directions, side, signal_close_ms):
    """Use setup_backtest's exact latest-fully-closed HTF lookup convention."""
    direction = htf_direction_at(htf_open_ms, directions, HTF_WIDTH, signal_close_ms)
    return direction == (1 if side == "long" else -1)


def resolve_native_trade(signal, frame, multiple, fee=FEE):
    """Replay native 1h OHLC; next-bar entry, 12-bar max, stop-first same-bar ties.

    No 1m/4h intrabar scan is available in this native-resolution dataset.
    """
    entry_i = signal.index + 1
    if entry_i >= len(frame):
        return None
    entry = float(frame.o.iloc[entry_i])
    sign = 1 if signal.side == "long" else -1
    risk = sign * (entry - signal.stop)
    if risk <= 0:
        return None
    liquidation = entry * (1 - sign * (1 - .005))
    if (sign == 1 and signal.stop <= liquidation) or (sign == -1 and signal.stop >= liquidation):
        return None
    target = entry + sign * risk * multiple
    end = min(len(frame), entry_i + 12)
    reason, exitp = "timeout", float(frame.c.iloc[end - 1])
    exit_ms = int(frame.t_open_ms.iloc[end - 1]) + WIDTH
    for j in range(entry_i, end):
        hit_s = frame.l.iloc[j] <= signal.stop if sign == 1 else frame.h.iloc[j] >= signal.stop
        hit_t = frame.h.iloc[j] >= target if sign == 1 else frame.l.iloc[j] <= target
        if hit_s or hit_t:
            reason = "stop" if hit_s else "target"
            exitp = float(signal.stop if hit_s else target)
            exit_ms = int(frame.t_open_ms.iloc[j]) + WIDTH
            break
    gross = sign * (exitp / entry - 1)
    net = gross - 2 * fee
    return {"reason": reason, "net": net, "gross": gross, "r": net / (risk / entry),
            "entry": entry, "day": exit_ms // 86_400_000, "exit_ms": exit_ms}


def _frame(db, table, symbol, before_ms=None):
    sql = f"SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM {table} WHERE symbol=?"
    params = [symbol]
    if before_ms is not None:
        sql += " AND t_open_ms<?"
        params.append(before_ms)
    sql += " ORDER BY t_open_ms"
    return pd.read_sql_query(sql, db, params=params)


def _cell_report(key, trades, years, start_ms, cutoff_ms):
    row = _metrics(key, trades, years)
    folds = []
    for f in range(5):
        sub = [t for t in trades if t["fold"] == f]
        n = len(sub)
        folds.append({"fold": f + 1, "n": n,
                      "hit_rate": sum(t["reason"] == "target" for t in sub) / n if n else None,
                      "mean_net_notional_pct": 100 * float(np.mean([t["net"] for t in sub])) if n else None,
                      "total_net_return_pct": 100 * sum(t["net"] for t in sub)})
    row["folds"] = folds
    positive = [max(0.0, x["total_net_return_pct"]) for x in folds]
    row["fold_positive_count"] = sum((x["mean_net_notional_pct"] or 0) > 0 for x in folds)
    row["top_fold_positive_return_share"] = max(positive) / sum(positive) if sum(positive) else 0.0
    row["red_flags_detected"] = []
    if row["positive_trade_concentration_top_2"] >= .5:
        row["red_flags_detected"].append("positive_return_concentrated_in_top_two_trades")
    if row["top_fold_positive_return_share"] >= .8:
        row["red_flags_detected"].append("positive_return_concentrated_in_one_dev_fold")
    return row


def _write(report):
    OUT.mkdir(parents=True, exist_ok=True)
    jp, mp = OUT / "report.json", OUT / "report.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)), encoding="utf-8")
    lines = ["# P7-D native 1h SuperTrend", "", f"Dev range: {report['start_utc']} to {report['cutoff_utc']} (cutoff exclusive); observed latest open: {report['latest_utc']}.",
             f"Fresh global calendar split; heldout computed: {report['heldout_computed']}.", "",
             "|Side|R|Filter|Dev N|Hit|Wilson 95%|Net %|Expert score/verdict|Bootstrap p|Holm p|Flags|Fold N / hit-rate / net %|Heldout N / hit / net %|",
             "|---|---:|---|---:|---:|---|---:|---|---:|---:|---|---|---|"]
    heldout = {(tuple(x["dev_cell"])): x["metrics"] for x in report.get("heldout_results", [])}
    for r in report["results"]:
        lo, hi = r["wilson_95"]
        ci = f"{lo:.3f}–{hi:.3f}" if lo is not None else "NA"
        hm = heldout.get((r["side"], r["R"], r["vol_filter"]))
        hold = f"{hm['n_signals']} / {hm['hit_rate'] if hm['hit_rate'] is not None else 0:.3f} / {hm['total_net_return_pct']:.2f}" if hm else "not opened"
        folds = "; ".join(f"{x['n']}/{x['hit_rate'] if x['hit_rate'] is not None else 0:.3f}/{x['total_net_return_pct']:.1f}" for x in r["folds"])
        flags = ",".join([x["id"] for x in r["backtest_expert"]["red_flags"]] + r["red_flags_detected"]) or "none"
        lines.append(f"|{r['side']}|{r['R']}R|{r['vol_filter']}|{r['n_signals']}|{r['hit_rate'] if r['hit_rate'] is not None else 0:.3f}|{ci}|{r['total_net_return_pct']:.2f}|{r['backtest_expert']['score']} {r['backtest_expert']['decision']}/{r['backtest_expert']['verdict']}|{r['day_bootstrap_p_one_sided']:.4f}|{r['holm_adjusted_p']:.4f}|{flags}|{folds}|{hold}|")
    lines.extend(["", "## Per-symbol coverage", "", "|Symbol|Resolution|First open ms|Last open ms|Rows|Days|", "|---|---|---:|---:|---:|---:|"])
    for table, rows in report["coverage"]["coverage"].items():
        resolution = "1h" if table == "candles_60m" else "4h"
        for x in rows:
            lines.append(f"|{x['symbol']}|{resolution}|{x['first_t_open_ms']}|{x['last_t_open_ms']}|{x['row_count']}|{x['actual_days_covered']:.2f}|")
    lines.extend(["", "Native 1h/4h bars are not bar-for-bar comparable to P5's 1m-resampled 60m data. Within-bar 1m chronology is unavailable; same-bar stop/target ties assume stop first.", ""])
    mp.write_text("\n".join(lines), encoding="utf-8")
    return jp, mp


def run():
    symbols = load_universe(ROOT / "data" / "universe_collect.json")
    db = sqlite3.connect(f"file:{DB_PATH.resolve()}?mode=ro", uri=True)
    try:
        earliest, latest = db.execute("SELECT MIN(t_open_ms),MAX(t_open_ms) FROM candles_60m").fetchone()
        cutoff = split_boundary(int(earliest), int(latest))
        start = int(earliest)
        grouped = {(side, r, filt): [] for side in ("long", "short") for r in (2, 3)
                   for filt in ("base", "vol_top_third", "htf_trend_align")}
        for symbol in symbols:
            frame = _frame(db, "candles_60m", symbol, cutoff)
            frame = frame[frame.t_open_ms + WIDTH <= cutoff].reset_index(drop=True)
            if len(frame) < 20:
                continue
            htf = _frame(db, "candles_240m", symbol, cutoff)
            htf = htf[htf.t_open_ms + HTF_WIDTH <= cutoff].reset_index(drop=True)
            aa = atr(frame.h, frame.l, frame.c, 14)
            direction = indicators.supertrend_direction(frame.h, frame.l, frame.c, aa)
            prepared = {"atr": aa}
            signals = generate_signals(frame, "supertrend", prepared)
            vol = aa / frame.c.to_numpy(float)
            roll = pd.Series(vol).rolling(168, min_periods=84).quantile(2 / 3).shift(1).to_numpy()
            h_atr = atr(htf.h, htf.l, htf.c, 14) if len(htf) else np.asarray([], float)
            hdir = indicators.supertrend_direction(htf.h, htf.l, htf.c, h_atr) if len(htf) else np.asarray([], int)
            h_opens = htf.t_open_ms.to_numpy(np.int64)
            for sig in signals:
                entry_i = sig.index + 1
                stamp = int(frame.t_open_ms.iloc[entry_i])
                fold = fold_for(stamp, start, cutoff)
                is_vol = np.isfinite(roll[sig.index]) and vol[sig.index] >= roll[sig.index]
                aligned = htf_aligned(h_opens, hdir, sig.side,
                                      int(frame.t_open_ms.iloc[sig.index]) + WIDTH)
                for multiple in (2, 3):
                    result = resolve_native_trade(sig, frame, multiple)
                    if result is None:
                        continue
                    result.update(symbol=symbol, fold=fold, signal_ms=int(frame.t_open_ms.iloc[sig.index]))
                    grouped[(sig.side, multiple, "base")].append(result)
                    if is_vol:
                        grouped[(sig.side, multiple, "vol_top_third")].append(result)
                    if aligned:
                        grouped[(sig.side, multiple, "htf_trend_align")].append(result)
        years = max(0, int((cutoff - start) / (365.2425 * 86_400_000)))
        rows = [_cell_report(("supertrend", side, "60m", multiple, filt), trades, years, start, cutoff)
                for (side, multiple, filt), trades in grouped.items()]
        ordered = sorted(enumerate(rows), key=lambda x: x[1]["day_bootstrap_p_one_sided"])
        prior = 0.0
        for rank, (idx, row) in enumerate(ordered):
            adjusted = min(1.0, max(prior, (len(ordered) - rank) * row["day_bootstrap_p_one_sided"]))
            row["holm_adjusted_p"] = adjusted
            row["holm_adjusted_flag"] = adjusted < .05
            row["pass_after_holm"] = bool(row["hit_gate_75"] and row["minimum_trade_gate_met"] and row["holm_adjusted_flag"])
            prior = adjusted
        eligible = [r for r in rows if r["pass_after_holm"]]
        heldout_rows = []
        # Heldout remains unopened unless a dev cell clears every predeclared gate.
        if eligible:
            for candidate in eligible:
                key = (candidate["side"], candidate["R"], candidate["vol_filter"])
                heldout_trades = []
                for symbol in symbols:
                    full = _frame(db, "candles_60m", symbol)
                    full = full[full.t_open_ms + WIDTH <= int(latest) + WIDTH].reset_index(drop=True)
                    if len(full) < 20:
                        continue
                    htf = _frame(db, "candles_240m", symbol)
                    htf = htf[htf.t_open_ms + HTF_WIDTH <= int(latest) + WIDTH].reset_index(drop=True)
                    aa = atr(full.h, full.l, full.c, 14)
                    signals = generate_signals(full, "supertrend", {"atr": aa})
                    vol = aa / full.c.to_numpy(float)
                    roll = pd.Series(vol).rolling(168, min_periods=84).quantile(2 / 3).shift(1).to_numpy()
                    ha = atr(htf.h, htf.l, htf.c, 14) if len(htf) else np.asarray([], float)
                    hd = indicators.supertrend_direction(htf.h, htf.l, htf.c, ha) if len(htf) else np.asarray([], int)
                    for sig in signals:
                        if sig.side != candidate["side"] or int(full.t_open_ms.iloc[sig.index]) < cutoff:
                            continue
                        nxt = sig.index + 1
                        is_vol = np.isfinite(roll[sig.index]) and vol[sig.index] >= roll[sig.index]
                        aligned = htf_aligned(htf.t_open_ms.to_numpy(np.int64), hd, sig.side,
                                              int(full.t_open_ms.iloc[sig.index]) + WIDTH)
                        if key[2] == "vol_top_third" and not is_vol:
                            continue
                        if key[2] == "htf_trend_align" and not aligned:
                            continue
                        outcome = resolve_native_trade(sig, full, key[1])
                        if outcome is not None and int(full.t_open_ms.iloc[nxt]) >= cutoff:
                            outcome.update(symbol=symbol, signal_ms=int(full.t_open_ms.iloc[sig.index]))
                            heldout_trades.append(outcome)
                heldout_metric = _metrics(("supertrend", key[0], "60m", key[1], key[2]), heldout_trades, years)
                heldout_rows.append({"dev_cell": key, "metrics": heldout_metric})
        coverage = json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))
        report = {"status": "complete", "dataset": str(DB_PATH), "symbols": symbols,
                  "split": "fresh_global_calendar_70_30", "start_ms": start, "cutoff_exclusive_ms": cutoff,
                  "cutoff_utc": datetime.fromtimestamp(cutoff / 1000, timezone.utc).isoformat(),
                  "start_utc": datetime.fromtimestamp(start / 1000, timezone.utc).isoformat(),
                  "latest_open_ms": int(latest), "latest_utc": datetime.fromtimestamp(int(latest) / 1000, timezone.utc).isoformat(),
                  "coverage": coverage, "fee_per_side": FEE, "cells_tested": len(rows),
                  "heldout_computed": bool(eligible), "heldout_results": heldout_rows,
                  "native_resolution_limitation": "Native 1h data cannot scan 1m chronology; a same-bar stop/target tie resolves to stop.",
                  "method": "Native 1h entries; native 4h HTF; ATR14 SuperTrend; 168-bar trailing 2/3 quantile shifted one bar; next-bar open entry; 2R/3R; max 12 entry bars; 0.05% fee per side; five chronological dev folds; centered day-block bootstrap and Holm family of 12.",
                  "runtime_seconds": time.monotonic() - _T0, "results": rows}
        _write(report)
        return report
    finally:
        db.close()


_T0 = time.monotonic()
if __name__ == "__main__":
    report = run()
    print(json.dumps({"cutoff_utc": report["cutoff_utc"], "heldout_computed": report["heldout_computed"],
                      "results": [{k: r[k] for k in ("side", "R", "vol_filter", "n_signals", "hit_rate", "total_net_return_pct", "holm_adjusted_p", "pass_after_holm")} for r in report["results"]]}, indent=2))
