"""Exploratory, development-only order-block hypothesis probe on local 1m DB.

This uses already-exposed data and MUST NOT be described as OOS validation.
The database is opened read-only. Outputs are written only to an explicit new
run directory outside the candle database.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "chart_predictor/data/candles.sqlite"
DEV_START = "2026-07-17T00:00:00Z"
DEV_END = "2026-10-09T00:00:00Z"  # existing P5 development cutoff; exposed data
FEE_RT = 0.001
STRESS_RT = 0.003
SLIP_BASE = 0.0004  # assumed 2 bp/side, sensitivity only
SLIP_STRESS = 0.001  # assumed 5 bp/side, sensitivity only
HORIZONS = (10, 20)


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def true_range_atr(frame: pd.DataFrame, period: int = 14) -> np.ndarray:
    h, l, c = (frame[x].to_numpy(float) for x in ("h", "l", "c"))
    prev = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    return pd.Series(tr).rolling(period, min_periods=period).mean().shift(1).to_numpy()


def form_zones(frame: pd.DataFrame, max_age: int = 60) -> list[dict]:
    """Return causally formed OBs with timestamps/indices; no outcomes are read."""
    o, h, l, c = (frame[x].to_numpy(float) for x in ("o", "h", "l", "c"))
    atr = true_range_atr(frame)
    zones = []
    for i in range(14, len(frame)):
        if not np.isfinite(atr[i]):
            continue
        bullish = c[i] - o[i] > 1.5 * atr[i] and c[i] > h[i - 1]
        bearish = o[i] - c[i] > 1.5 * atr[i] and c[i] < l[i - 1]
        if bullish or bearish:
            side = "long" if bullish else "short"
            for j in range(i - 1, max(-1, i - 6), -1):
                opposite = c[j] < o[j] if side == "long" else c[j] > o[j]
                if opposite:
                    zones.append({"low": float(l[j]), "high": float(h[j]),
                                  "born": i, "side": side, "max_age": max_age})
                    break
    return zones


def breaker_signals(frame: pd.DataFrame) -> list[dict]:
    """Trade only the first retest after a close invalidates a formed OB."""
    o, h, l, c = (frame[x].to_numpy(float) for x in ("o", "h", "l", "c"))
    atr_values = true_range_atr(frame)
    zones = []
    signals = []
    for i in range(len(frame)):
        keep = []
        for z in zones:
            if i - z["born"] > z["max_age"]:
                continue
            if z["state"] == "ob":
                invalid = c[i] < z["low"] if z["side"] == "long" else c[i] > z["high"]
                if invalid:
                    z = {**z, "state":"breaker", "break_index":i,
                         "trade_side":"short" if z["side"]=="long" else "long"}
                else:
                    keep.append(z)
                    continue
            if i <= z["break_index"]:
                keep.append(z)
                continue
            side = z["trade_side"]
            touched = l[i] <= z["high"] and h[i] >= z["low"]
            recovered = (c[i] < z["low"] and c[i] < o[i]) if side == "short" else (c[i] > z["high"] and c[i] > o[i])
            if touched:
                if recovered:
                    signals.append({"hypothesis":"breaker_retest", "signal_index":i,
                                    "signal_side":side,
                                    "stop":z["high"] if side=="short" else z["low"]})
                # First retest consumes the zone, whether or not it confirms.
                continue
            failed = c[i] > z["high"] if side=="short" else c[i] < z["low"]
            if not failed:
                keep.append(z)
        zones=keep
        # New zones become active only after processing the completed candle.
        if i >= 14:
            atr = atr_values[i]
            if not np.isfinite(atr):
                continue
            bullish = c[i]-o[i] > 1.5*atr and c[i] > h[i-1]
            bearish = o[i]-c[i] > 1.5*atr and c[i] < l[i-1]
            if bullish or bearish:
                side="long" if bullish else "short"
                for j in range(i-1,max(-1,i-6),-1):
                    if (c[j] < o[j]) if side=="long" else (c[j] > o[j]):
                        zones.append({"low":float(l[j]),"high":float(h[j]),"born":i,
                                      "side":side,"state":"ob","max_age":60})
                        break
    return signals


def htf_mitigation_signals(frame: pd.DataFrame, width: int = 5) -> list[dict]:
    """HTF OBs projected causally to LTF; signal only on first LTF mitigation."""
    htf = frame.set_index(pd.to_datetime(frame.t_open_ms, unit="ms", utc=True)).resample(
        f"{width}min", origin="epoch", label="left", closed="left").agg(
        o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"),
        v=("v", "sum"), count=("t_open_ms", "count"))
    htf = htf[htf["count"] == width].drop(columns="count").reset_index(names="t_open")
    htf["t_open_ms"] = htf.t_open.astype("int64") // 1_000_000
    # A higher timeframe bar becomes usable only at its close. Form zones from
    # completed HTF bars; evaluate the first LTF mitigation after availability.
    zones = form_zones(htf)
    one = frame.reset_index(drop=True)
    times = one.t_open_ms.to_numpy(np.int64)
    htf_end = htf.t_open_ms.to_numpy(np.int64) + width * 60_000
    signals = []
    for z in zones:
        created_at = int(htf_end[z["born"]])
        signal_side = z["side"]
        start = int(np.searchsorted(times, created_at, side="left"))
        end = min(len(one), start + 60 * width)
        for i in range(start, end):
            row = one.iloc[i]
            if i and int(times[i]) != int(times[i-1]) + 60_000:
                break
            if row.l <= z["high"] and row.h >= z["low"]:
                invalid = row.c < z["low"] if signal_side=="long" else row.c > z["high"]
                recovered = row.c > z["high"] and row.c > row.o if signal_side == "long" else row.c < z["low"] and row.c < row.o
                if recovered:
                    signals.append({"hypothesis":"htf_first_mitigation", "signal_index":i,
                                    "signal_side":signal_side,
                                    "stop":float(z["low"] if signal_side=="long" else z["high"]),
                                    "zone_low":z["low"],"zone_high":z["high"]})
                break
    return signals


def score(frame: pd.DataFrame, signals: list[dict], symbol: str, horizon: int) -> list[dict]:
    rows=[]
    end_ms=int(pd.Timestamp(DEV_END).timestamp()*1000)
    start_ms=int(pd.Timestamp(DEV_START).timestamp()*1000)
    for s in signals:
        i=int(s["signal_index"])
        if i+1+horizon>len(frame) or not(start_ms<=int(frame.t_open_ms.iloc[i])<end_ms):
            continue
        fut=frame.iloc[i+1:i+1+horizon]
        if len(fut)!=horizon or int(fut.t_open_ms.iloc[-1])>=end_ms: continue
        side=s["signal_side"]; entry=float(fut.o.iloc[0]); stop=float(s["stop"])
        if (side=="long" and stop>=entry) or (side=="short" and stop<=entry):
            rows.append({"hypothesis":s["hypothesis"],"symbol":symbol,"signal_time_ms":int(frame.t_open_ms.iloc[i]),"horizon":horizon,"m2":0,"exit":"INVALID_ENTRY","net_base":-FEE_RT-SLIP_BASE,"net_stress":-STRESS_RT-SLIP_STRESS})
            continue
        risk=abs(entry-stop)
        # Side comparison is explicit so long/short symmetry is auditable.
        target=entry+(2*risk if side=="long" else -2*risk)
        reason="TIMEOUT"; exit_px=float(fut.c.iloc[-1]); hit=0
        for r in fut.itertuples(index=False):
            stop_hit=(r.o<=stop or r.l<=stop) if side=="long" else (r.o>=stop or r.h>=stop)
            target_hit=(r.o>=target or r.h>=target) if side=="long" else (r.o<=target or r.l<=target)
            if stop_hit:
                reason="STOP"; exit_px=float(r.o if ((r.o<=stop) if side=="long" else (r.o>=stop)) else stop); break
            if target_hit:
                reason="TARGET"; exit_px=float(target); hit=1; break
        gross=(exit_px/entry-1)*(1 if side=="long" else -1)
        rows.append({"hypothesis":s["hypothesis"],"symbol":symbol,"signal_time_ms":int(frame.t_open_ms.iloc[i]),"horizon":horizon,"m2":hit,"exit":reason,"net_base":gross-FEE_RT-SLIP_BASE,"net_stress":gross-STRESS_RT-SLIP_STRESS})
    return rows


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--db",type=Path,default=DEFAULT_DB)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit-symbols",type=int,default=0,help="0 = all symbols; diagnostic only")
    args=p.parse_args()
    if args.out.exists(): raise SystemExit(f"refusing to overwrite {args.out}")
    args.out.mkdir(parents=True)
    db=sqlite3.connect(f"file:{args.db.resolve()}?mode=ro",uri=True)
    symbols=[r[0] for r in db.execute("SELECT DISTINCT symbol FROM candles ORDER BY symbol")]
    if args.limit_symbols: symbols=symbols[:args.limit_symbols]
    all_rows=[]
    for n,symbol in enumerate(symbols,1):
        frame=pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles WHERE symbol=? ORDER BY t_open_ms",db,params=(symbol,))
        for name,fn in (("breaker_retest",breaker_signals),("htf_first_mitigation",htf_mitigation_signals)):
            sigs=fn(frame)
            for horizon in HORIZONS: all_rows.extend(score(frame,sigs,symbol,horizon))
        print(f"processed {n}/{len(symbols)} symbols; events={len(all_rows)}",flush=True)
    db.close()
    ledger=args.out/"events.csv"
    with ledger.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(all_rows[0]) if all_rows else ["hypothesis","symbol","signal_time_ms","horizon","m2","exit","net_base","net_stress"]);w.writeheader();w.writerows(all_rows)
    report={"status":"EXPLORATORY_DEVELOPMENT_ONLY","db":str(args.db),"db_sha256":digest_file(args.db),"symbols":symbols,"period_utc":[DEV_START,DEV_END],"fee_round_trip":[FEE_RT,STRESS_RT],"slippage_assumption_round_trip":[SLIP_BASE,SLIP_STRESS],"trial_cells":4,"event_rows":len(all_rows),"metrics":{}}
    for name in ("breaker_retest","htf_first_mitigation"):
        report["metrics"][name]={}
        for horizon in HORIZONS:
            rr=[x for x in all_rows if x["hypothesis"]==name and x["horizon"]==horizon]
            report["metrics"][name][str(horizon)]={"n":len(rr),"m2":sum(x["m2"] for x in rr)/len(rr) if rr else None,"net_base":float(np.mean([x["net_base"] for x in rr])) if rr else None,"net_stress":float(np.mean([x["net_stress"] for x in rr])) if rr else None,"exit_counts":{k:sum(x["exit"]==k for x in rr) for k in sorted({x["exit"] for x in rr})}}
    (args.out/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    return 0

if __name__=="__main__": raise SystemExit(main())
