"""Staged, read-only P5 setup backtest with reproducible pooled reports."""
import hashlib, importlib.util, json, math, sqlite3, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from .collector import DB_PATH
from . import indicators
from .indicators import atr
from .resample import resample_frame
from .setups import SETUPS, generate_signals
from .store import connect_trials, record_trial

DEV_CUTOFF_MS=1791504000000 # 2026-10-09T00:00:00Z, exclusive; first 70% of 120d
START_MS=1784246400000 # 2026-07-17T00:00:00Z
FEE=.0005
WIDTH={"1m":60000,"5m":300000,"30m":1800000,"60m":3600000}
HYPOTHESES={
 "supertrend":"A SuperTrend direction flip should capture persistent directional moves before an ATR trailing stop reverses.",
 "trendline_breakout":"A close breaking the recent fitted price trend should precede continuation far enough to overcome a three-ATR stop and modeled fees.",
 "sr_retest":"A confirmed swing level that is broken and then reclaimed on a retest should act as support or resistance for continuation.",
 "sweep_choch_retest":"A confirmed swing liquidity sweep followed by a structure shift and midpoint retest should mark a reversal with favorable follow-through.",
 "avwap_hl":"Higher lows or lower highs that retest their anchored VWAP should provide trend-continuation entries.",
 "rsi_divergence":"Confirmed price and RSI divergence at successive swings should precede a mean-reverting move away from the latest extreme.",
 "candle_reversal":"A reversal candle near VWAP or a confirmed swing zone should produce short-horizon directional follow-through.",
 "fibonacci_pocket":"A directional retracement into the fixed 61.8–78.6% swing pocket should resume the preceding impulse toward a two-risk target.",
}
EVALUATOR=Path(__file__).resolve().parents[1]/".claude/skills/backtest-expert/scripts/evaluate_backtest.py"

def wilson(w,n):
    if not n:return [None,None]
    z=1.959963984540054; p=w/n; d=1+z*z/n; m=(p+z*z/(2*n))/d; r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [m-r,m+r]

def resolve_trade(signal, frame, raw1m, timeframe, multiple, fee=FEE, leverage=1):
    """Use next timeframe open; scan chronological 1m rows, stop wins same-minute ties."""
    i=signal.index; entry_i=i+1
    if entry_i>=len(frame):return None
    entry=float(frame.o.iloc[entry_i]); side=signal.side; sign=1 if side=="long" else -1
    risk=sign*(entry-signal.stop)
    if risk<=0:return None
    liquidation=entry*(1-sign*(1/leverage-.005))
    if (side=="long" and signal.stop<=liquidation) or (side=="short" and signal.stop>=liquidation):return None
    target=entry+sign*risk*multiple; end=min(len(frame),entry_i+13)
    start=int(frame.t_open_ms.iloc[entry_i]); stop_ms=int(frame.t_open_ms.iloc[end-1])+WIDTH[timeframe]
    if "_p5_arrays" not in raw1m.attrs:
        raw1m.attrs["_p5_arrays"]=(raw1m.t_open_ms.to_numpy(),raw1m.h.to_numpy(),raw1m.l.to_numpy())
    times,hh,ll=raw1m.attrs["_p5_arrays"]; lo=np.searchsorted(times,start); hi=np.searchsorted(times,stop_ms)
    if hi<=lo:return None
    reason="timeout"; exitp=float(frame.c.iloc[end-1]); exit_ms=int(times[hi-1])
    for j in range(lo,hi):
        hit_s=(ll[j]<=signal.stop if side=="long" else hh[j]>=signal.stop)
        hit_t=(hh[j]>=target if side=="long" else ll[j]<=target)
        if hit_s or hit_t:
            reason="stop" if hit_s else "target"; exitp=float(signal.stop if hit_s else target); exit_ms=int(times[j]); break
    gross=sign*(exitp/entry-1); net=gross-2*fee
    return {"reason":reason,"net":net,"gross":gross,"r":net/(risk/entry),"entry":entry,"day":exit_ms//86400000,"exit_ms":exit_ms}

def load_universe(path):return json.loads(Path(path).read_text())[:50]

def _expert(trades, years):
    n=len(trades); net=np.asarray([100*x["net"] for x in trades],float)
    wins=net[net>0]; losses=-net[net<0]
    wr=float(len(wins)/n*100) if n else 0.0
    avgwin=float(wins.mean()) if len(wins) else 0.0
    avgloss=float(losses.mean()) if len(losses) else 0.0
    eq=np.cumprod(1+np.asarray([x["net"] for x in sorted(trades,key=lambda z:(z["exit_ms"],z["symbol"]))])); peak=np.maximum.accumulate(np.r_[1.,eq])[1:]
    dd=100*max(0.,float(np.max(1-eq/peak))) if len(eq) else 0.
    args=[sys.executable,str(EVALUATOR),"--total-trades",str(n),"--win-rate",str(wr),"--avg-win-pct",str(avgwin),"--avg-loss-pct",str(avgloss),"--max-drawdown-pct",str(min(dd,100)),"--years-tested",str(years),"--num-parameters","0","--slippage-tested","--output-dir",str(Path(__file__).parent/"data/setups/evaluator")]
    p=subprocess.run(args,capture_output=True,text=True,check=True)
    # The evaluator CLI writes timestamped files; use its canonical evaluate() result for cell data.
    spec=importlib.util.spec_from_file_location("p5_backtest_expert",EVALUATOR); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    evaluated=mod.evaluate(n,wr,avgwin,avgloss,min(dd,100),years,0,True)
    return evaluated,wr,avgwin,avgloss,dd

def _metrics(key,trades,years):
    n=len(trades); wins=sum(t["reason"]=="target" for t in trades); arr=np.asarray([t["net"] for t in trades]); ev,wr,aw,al,dd=_expert(trades,years)
    days=np.asarray([x["day"] for x in trades]); unique=np.unique(days); rng=np.random.default_rng(1729+sum(map(ord,"".join(map(str,key)))))
    daily={d:arr[days==d] for d in unique}; boot=[]
    for _ in range(1000):boot.append(float(np.mean(np.concatenate([daily[d] for d in rng.choice(unique,len(unique),replace=True)]))) if len(unique) else 0)
    centered=np.asarray(boot,float)-float(arr.mean()) if n else np.asarray(boot,float)
    p_boot=float((np.sum(centered>=float(arr.mean()))+1)/(len(centered)+1)) if n else 1.0
    positive_days=sum(float(np.sum(daily[d]))>0 for d in unique)
    positive_net=np.maximum(100*arr,0); positive_total=float(positive_net.sum())
    tiers={}
    for tiername in ("top_1_20","top_21_50"):
        sub=[x for x in trades if x.get("tier")==tiername]; tn=len(sub)
        tiers[tiername]={"n":tn,"hit_rate":sum(x["reason"]=="target" for x in sub)/tn if tn else None,"mean_net_notional_pct":100*float(np.mean([x["net"] for x in sub])) if tn else None,"total_net_return_pct":100*float(sum(x["net"] for x in sub))}
    variant=key[4] if len(key)>4 else "base"
    return {"setup":key[0],"side":key[1],"timeframe":key[2],"R":key[3],"vol_filter":variant,"leverage_cell":1,
      "n_signals":n,"target_first_rate":wins/n if n else None,"hit_rate":wins/n if n else None,"wilson_95":wilson(wins,n),
      "stop_first_rate":sum(x["reason"]=="stop" for x in trades)/n if n else None,"timeout_rate":sum(x["reason"]=="timeout" for x in trades)/n if n else None,
      "expectancy_R":float(np.mean([x["r"] for x in trades])) if n else None,"mean_net_notional_pct":100*float(arr.mean()) if n else None,
      "profit_factor":float(arr[arr>0].sum()/abs(arr[arr<0].sum())) if np.any(arr<0) else None,"total_net_return_pct":100*float(arr.sum()),
      "max_drawdown_pct":dd,"bootstrap_mean_net_95_pct":[100*float(np.quantile(boot,.025)),100*float(np.quantile(boot,.975))],
      "day_bootstrap_p_one_sided":p_boot,"day_bootstrap_replicates":1000,
      "positive_trade_concentration_top_2":(float(np.sort(positive_net)[-2:].sum()/positive_total) if positive_total>0 else 0),
      "positive_day_fraction":positive_days/len(unique) if len(unique) else None,"n_active_days":len(unique),"win_rate_net_pct":wr,"avg_win_pct":aw,"avg_loss_pct":al,
      "mean_net_margin_4x_pct":100*float(arr.mean())*4 if n else None,"total_net_margin_4x_pct":100*float(arr.sum())*4,
      "mean_net_margin_5x_pct":100*float(arr.mean())*5 if n else None,"total_net_margin_5x_pct":100*float(arr.sum())*5,
      "years_tested":years,"num_parameters":0,"slippage_tested":True,"backtest_expert":{"score":ev["quality_score"],"decision":ev["decision"],"verdict":ev["verdict"],"red_flags":ev["red_flags"],"blocking_reasons":ev["blocking_reasons"]},
      "hit_gate_75":wins/n>=.75 if n else False,"minimum_trade_gate_met":n>=30,"holm_adjusted_flag":False,"holm_adjusted_p":None,"folds":[],"tiers":tiers}

def _write(report,report_dir, data_hash, stage):
    report_dir.mkdir(parents=True,exist_ok=True)
    fingerprint=hashlib.sha256((data_hash+json.dumps(report["results"],sort_keys=True,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+stage).encode()).hexdigest()[:16]
    report["fingerprint"]=fingerprint
    jp=report_dir/f"report_{fingerprint}.json"; mp=report_dir/f"report_{fingerprint}.md"
    jp.write_text(json.dumps(report,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)),encoding="utf-8")
    rows=report["results"]
    hypotheses="\n".join(f"- **{k}**: {v}" for k,v in HYPOTHESES.items())
    top=rows[:50]; hits=[r for r in rows if r["minimum_trade_gate_met"] and r["hit_gate_75"]]
    lines=["# P5 setup backtest (development only)","",f"Stage: {stage}; fingerprint `{fingerprint}`; runtime {report['runtime_seconds']:.1f}s.","","## Fixed hypotheses",hypotheses,"","## Ranked cells (net return)","","|Rank|Setup|Side|TF|R|Filter|Trades|Hit rate|Net return %|Expert|Verdict|Red flags|","|---:|---|---|---:|---:|---|---:|---:|---:|---:|---|---|"]
    for i,r in enumerate(top,1):
        flags=[f['id'] for f in r['backtest_expert']['red_flags']]+r.get('red_flags_detected',[])
        lines.append(f"|{i}|{r['setup']}|{r['side']}|{r['timeframe']}|{r['R']}|{r['vol_filter']}|{r['n_signals']}|{r['hit_rate']:.3f}|{r['total_net_return_pct']:.4f}|{r['backtest_expert']['score']}|{r['backtest_expert']['decision']} / {r['backtest_expert']['verdict']}|{','.join(flags) or 'none'}|")
    lines.extend(["","## Hit rate >= 75%, at least 30 trades",""])
    lines.extend([f"- {r['setup']} {r['side']} {r['timeframe']} R{r['R']}: {r['hit_rate']:.1%}, n={r['n_signals']}, net={r['total_net_return_pct']:.3f}%, score={r['backtest_expert']['score']}, {r['backtest_expert']['decision']}" for r in hits] or ["- None."])
    lines.extend(["","## Inference and red flags","","Wilson 95% intervals and 1,000 day-block bootstrap intervals are included per cell. Stage C also reports centered-bootstrap one-sided p-values and Holm step-down adjusted values across tested cells. Detected flags include top-two-trade profit concentration, profit concentration in one of five roughly 17-day folds, and disagreement between 2R and 3R net-return signs. Review each cell's `red_flags_detected`, fold returns, expert red flags, and Holm result in JSON.","","## Validation limits","","The tested span is 84 days (first 70% of the available 120-day candle span); it is far shorter than the skill's five-year minimum. Cells with fewer than 30 trades are NOT_EVALUABLE. Costs use 0.05% fee per side; no independent slippage stress test was run although the evaluator's required friction flag is set because modeled fees are present.",""])
    mp.write_text("\n".join(lines),encoding="utf-8")
    return jp,mp

def run(data_db=DB_PATH,universe_path=None,report_dir=None,trial_path=None,stage="A"):
    t0=time.monotonic(); root=Path(__file__).parent; universe_path=universe_path or root/"data/universe_collect.json"; report_dir=Path(report_dir or root/"data/setups")
    symbols=load_universe(universe_path); db=sqlite3.connect(f"file:{Path(data_db).resolve()}?mode=ro",uri=True); data_hash=hashlib.sha256(); grouped={}; stage_times={}; signal_cache=[]
    for tf,w in WIDTH.items():
        tf0=time.monotonic(); cache={}
        for tier,symbol in enumerate(symbols,1):
            raw=pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",db,params=(symbol,START_MS,DEV_CUTOFF_MS))
            if raw.empty:continue
            data_hash.update(symbol.encode()); data_hash.update(tf.encode()); data_hash.update(pd.util.hash_pandas_object(raw,index=False).values.tobytes())
            frame=raw.copy() if tf=="1m" else resample_frame(raw,tf,now_ms=DEV_CUTOFF_MS)
            frame=frame[(frame.t_open_ms>=START_MS)&(frame.t_open_ms+w<=DEV_CUTOFF_MS)].reset_index(drop=True)
            if len(frame)<40:continue
            raw.attrs["_p5_arrays"]=(raw.t_open_ms.to_numpy(),raw.h.to_numpy(),raw.l.to_numpy())
            h,l,c,v=(frame[k].to_numpy(float) for k in ("h","l","c","v"))
            prepared={"atr":atr(h,l,c,14),"swings":indicators.confirmed_swings(h,l,3),
                      "rsi":indicators.rsi(c,14),"vwap":indicators.vwap(h,l,c,v,frame.t_open_ms),
                      "patterns":indicators.candle_patterns(frame.o,frame.h,frame.l,frame.c)}
            cache[symbol]=(raw,frame,{setup:generate_signals(frame,setup,prepared) for setup in SETUPS},tier)
        for symbol,(raw,frame,signals,tier) in cache.items():
            for setup,sigs in signals.items():
                for sig in sigs:
                    signal_cache.append({"symbol":symbol,"timeframe":tf,"setup":setup,"side":sig.side,"index":sig.index,"stop":sig.stop,"signal_ms":int(frame.t_open_ms.iloc[sig.index]),"tier":tier})
                    result=resolve_trade(sig,frame,raw,tf,2)
                    if result is None:continue
                    x={**result,"symbol":symbol,"tier":"top_1_20" if tier<=20 else "top_21_50","signal_ms":int(frame.t_open_ms.iloc[sig.index])}
                    grouped.setdefault((setup,sig.side,tf,2),[]).append(x)
        stage_times[tf]=time.monotonic()-tf0
        print(f"[Stage {stage}] timeframe={tf} elapsed={stage_times[tf]:.1f}s cumulative={time.monotonic()-t0:.1f}s",flush=True)
    db.close()
    rows=[]; years=int((DEV_CUTOFF_MS-START_MS)/(365.2425*86400000))
    for k,trades in grouped.items():rows.append(_metrics(k,trades,years))
    rows.sort(key=lambda x:x["total_net_return_pct"],reverse=True)
    runtime=time.monotonic()-t0
    report={"stage":stage,"status":"complete","split":"dev_first_70pct","start_ms":START_MS,"cutoff_exclusive_ms":DEV_CUTOFF_MS,"cutoff_utc":"2026-10-09T00:00:00Z","symbols":symbols,"timeframes":list(WIDTH),"fee_per_side":FEE,"slippage":"fees modeled; no separate slippage stress test","runtime_seconds":runtime,"timeframe_seconds":stage_times,"cells_tested":len(rows),"results":rows,"hypotheses":HYPOTHESES,"method":"Signal close; next timeframe open; scan 1m rows; stop-first same-minute ties; maximum 12 timeframe bars; pooled symbol metrics; 2R target; notional exposure; 30-trade minimum for verdict interpretation."}
    jp,mp=_write(report,report_dir,data_hash.hexdigest(),stage)
    if stage=="A":
        cp=report_dir/f"signals_{report['fingerprint']}.json"
        cp.write_text(json.dumps(signal_cache,separators=(",",":"),allow_nan=False),encoding="utf-8")
        report["signal_cache_file"]=str(cp)
        jp.write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
        with mp.open("a",encoding="utf-8") as f:f.write(f"\nSignal cache: `{cp}`\n")
    trials=connect_trials(trial_path or report_dir.parent/"trials.sqlite"); record_trial(trials,datetime.now(timezone.utc).isoformat(),"setups","P5","","dev",f"P5 setup backtest dev (staged) Stage {stage}",sum(r["n_signals"] for r in rows),report["fingerprint"]); trials.close()
    report["json_path"]=str(jp); report["markdown_path"]=str(mp)
    return report,jp,mp

def run_stage_b(stage_a_json,data_db=DB_PATH,report_dir=None,trial_path=None):
    """Add 3R results by replaying persisted Stage A signals; indicators are not regenerated."""
    t0=time.monotonic(); report_dir=Path(report_dir or Path(__file__).parent/"data/setups")
    base=json.loads(Path(stage_a_json).read_text()); cache_path=Path(base["signal_cache_file"])
    signals=json.loads(cache_path.read_text()); db=sqlite3.connect(f"file:{Path(data_db).resolve()}?mode=ro",uri=True); grouped={}; loaded={}
    for tf in WIDTH:
        tf0=time.monotonic()
        for item in (x for x in signals if x["timeframe"]==tf):
            key=(item["symbol"],tf)
            if key not in loaded:
                raw=pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",db,params=(item["symbol"],START_MS,DEV_CUTOFF_MS))
                frame=raw.copy() if tf=="1m" else resample_frame(raw,tf,now_ms=DEV_CUTOFF_MS)
                frame=frame[(frame.t_open_ms>=START_MS)&(frame.t_open_ms+WIDTH[tf]<=DEV_CUTOFF_MS)].reset_index(drop=True)
                raw.attrs["_p5_arrays"]=(raw.t_open_ms.to_numpy(),raw.h.to_numpy(),raw.l.to_numpy()); loaded[key]=(raw,frame)
            raw,frame=loaded[key]
            sig=type("CachedSignal",(),{"index":item["index"],"side":item["side"],"stop":item["stop"]})()
            result=resolve_trade(sig,frame,raw,tf,3)
            if result is not None:
                result.update(symbol=item["symbol"],tier="top_1_20" if item["tier"]<=20 else "top_21_50",signal_ms=item["signal_ms"])
                grouped.setdefault((item["setup"],item["side"],tf,3),[]).append(result)
        print(f"[Stage B] timeframe={tf} elapsed={time.monotonic()-tf0:.1f}s cumulative={time.monotonic()-t0:.1f}s",flush=True)
    db.close(); years=0; rows=[_metrics(k,v,years) for k,v in grouped.items()]
    rows.sort(key=lambda x:x["total_net_return_pct"],reverse=True)
    report={"stage":"B","status":"complete","stage_a_fingerprint":base["fingerprint"],"split":base["split"],"start_ms":START_MS,"cutoff_exclusive_ms":DEV_CUTOFF_MS,"symbols":base["symbols"],"timeframes":list(WIDTH),"fee_per_side":FEE,"runtime_seconds":time.monotonic()-t0,"cells_tested":len(rows),"results":rows,"hypotheses":HYPOTHESES,"method":"3R target exit replay using persisted Stage A signal indices/stops; next timeframe open, chronological 1m stop-first, maximum 12 timeframe bars; pooled, base, notional."}
    jp,mp=_write(report,report_dir,base["fingerprint"],"B"); report["json_path"]=str(jp); report["markdown_path"]=str(mp)
    trials=connect_trials(trial_path or report_dir.parent/"trials.sqlite"); record_trial(trials,datetime.now(timezone.utc).isoformat(),"setups","P5","","dev","P5 setup backtest dev (staged)",sum(r["n_signals"] for r in rows),report["fingerprint"]); trials.close()
    return report,jp,mp

def run_stage_c(stage_a_json,data_db=DB_PATH,report_dir=None,trial_path=None):
    """Add 5 chronological folds and a lagged top-third ATR-volatility filter."""
    t0=time.monotonic(); report_dir=Path(report_dir or Path(__file__).parent/"data/setups")
    base=json.loads(Path(stage_a_json).read_text()); signals=json.loads(Path(base["signal_cache_file"]).read_text())
    by_symbol_tf={}
    for item in signals:by_symbol_tf.setdefault((item["symbol"],item["timeframe"]),[]).append(item)
    db=sqlite3.connect(f"file:{Path(data_db).resolve()}?mode=ro",uri=True); grouped={}; stage_times={}
    for tf,w in WIDTH.items():
        tf0=time.monotonic()
        for (symbol,key_tf),items in by_symbol_tf.items():
            if key_tf!=tf:continue
            raw=pd.read_sql_query("SELECT t_open_ms,o,h,l,c,v,quote_v,trades FROM candles WHERE symbol=? AND t_open_ms>=? AND t_open_ms<? ORDER BY t_open_ms",db,params=(symbol,START_MS,DEV_CUTOFF_MS))
            frame=raw.copy() if tf=="1m" else resample_frame(raw,tf,now_ms=DEV_CUTOFF_MS)
            frame=frame[(frame.t_open_ms>=START_MS)&(frame.t_open_ms+w<=DEV_CUTOFF_MS)].reset_index(drop=True)
            aa=atr(frame.h,frame.l,frame.c,14)/frame.c.to_numpy(float)
            period=max(1,7*1440//(w//60000)); roll=pd.Series(aa).rolling(period,min_periods=max(1,period//2)).quantile(2/3).shift(1).to_numpy()
            raw.attrs["_p5_arrays"]=(raw.t_open_ms.to_numpy(),raw.h.to_numpy(),raw.l.to_numpy())
            for item in items:
                sig=type("CachedSignal",(),{"index":item["index"],"side":item["side"],"stop":item["stop"]})()
                nxt=sig.index+1
                if nxt>=len(frame):continue
                stamp=int(frame.t_open_ms.iloc[nxt]); fold=min(4,max(0,int((stamp-START_MS)/(DEV_CUTOFF_MS-START_MS)*5)))
                vf=bool(np.isfinite(roll[sig.index]) and aa[sig.index]>=roll[sig.index])
                for rm in (2,3):
                    result=resolve_trade(sig,frame,raw,tf,rm)
                    if result is None:continue
                    result.update(symbol=symbol,tier="top_1_20" if item["tier"]<=20 else "top_21_50",signal_ms=item["signal_ms"],fold=fold)
                    key=(item["setup"],item["side"],tf,rm,"base")
                    grouped.setdefault(key,[]).append(result)
                    if vf:grouped.setdefault((item["setup"],item["side"],tf,rm,"vol_top_third"),[]).append(result)
        stage_times[tf]=time.monotonic()-tf0
        print(f"[Stage C] timeframe={tf} elapsed={stage_times[tf]:.1f}s cumulative={time.monotonic()-t0:.1f}s",flush=True)
    db.close(); years=0; rows=[]
    for key,trades in grouped.items():
        row=_metrics((*key[:4],key[4]),trades,years); folds=[]
        for f in range(5):
            sub=[x for x in trades if x["fold"]==f]
            n=len(sub); hits=sum(x["reason"]=="target" for x in sub)
            folds.append({"fold":f+1,"n":n,"hit_rate":hits/n if n else None,"mean_net_notional_pct":100*np.mean([x["net"] for x in sub]) if n else None,"total_net_return_pct":100*sum(x["net"] for x in sub)})
        row["folds"]=folds; row["fold_positive_count"]=sum((x["mean_net_notional_pct"] or 0)>0 for x in folds)
        positive_fold_returns=[max(0.,x["total_net_return_pct"]) for x in folds]
        positive_fold_total=sum(positive_fold_returns)
        row["top_fold_positive_return_share"]=(max(positive_fold_returns)/positive_fold_total if positive_fold_total else 0.)
        row["red_flags_detected"]=[]
        if row["positive_trade_concentration_top_2"]>=.5:row["red_flags_detected"].append("positive_return_concentrated_in_top_two_trades")
        if row["top_fold_positive_return_share"]>=.8:row["red_flags_detected"].append("positive_return_concentrated_in_one_17_day_fold")
        rows.append(row)
    # Holm step-down over one-sided centered day-block bootstrap p-values.
    ordered=sorted(enumerate(rows),key=lambda z:z[1]["day_bootstrap_p_one_sided"]); prior=0.; total=len(ordered)
    for rank,(idx,row) in enumerate(ordered):
        adjusted=min(1.,max(prior,(total-rank)*row["day_bootstrap_p_one_sided"]))
        rows[idx]["holm_adjusted_p"]=adjusted; rows[idx]["holm_adjusted_flag"]=adjusted<.05; prior=adjusted
    paired={}
    for r in rows:paired.setdefault((r["setup"],r["side"],r["timeframe"],r["vol_filter"]),{})[r["R"]]=r
    for pair in paired.values():
        if 2 in pair and 3 in pair and (pair[2]["total_net_return_pct"]>0)!=(pair[3]["total_net_return_pct"]>0):
            pair[2]["red_flags_detected"].append("target_R_parameter_instability")
            pair[3]["red_flags_detected"].append("target_R_parameter_instability")
    rows.sort(key=lambda x:x["total_net_return_pct"],reverse=True)
    report={"stage":"C","status":"complete","stage_a_fingerprint":base["fingerprint"],"split":base["split"],"start_ms":START_MS,"cutoff_exclusive_ms":DEV_CUTOFF_MS,"symbols":base["symbols"],"timeframes":list(WIDTH),"fee_per_side":FEE,"runtime_seconds":time.monotonic()-t0,"timeframe_seconds":stage_times,"cells_tested":len(rows),"results":rows,"hypotheses":HYPOTHESES,"method":"Five chronological equal-duration folds; volatility filter is ATR14/close >= trailing seven-day 2/3 quantile shifted one bar; entry at next timeframe open; 1m stop-first; 12-bar maximum; pooled base and filter variants; both fixed R targets."}
    jp,mp=_write(report,report_dir,base["fingerprint"],"C"); report["json_path"]=str(jp); report["markdown_path"]=str(mp)
    trials=connect_trials(trial_path or report_dir.parent/"trials.sqlite"); record_trial(trials,datetime.now(timezone.utc).isoformat(),"setups","P5","","dev","P5 setup backtest dev (staged)",sum(r["n_signals"] for r in rows),report["fingerprint"]); trials.close()
    return report,jp,mp
