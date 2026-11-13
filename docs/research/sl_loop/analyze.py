"""Compute stop-quality, STX, crash-window, family, and report tables from completed runs."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]; OUT=Path(__file__).resolve().parent
os.environ["RS_FINAL_SCRATCH"]=str(ROOT/".rs_cache/sl_panel"); os.environ["NUMBA_CACHE_DIR"]=str(ROOT/".rs_cache/sl_nbc")
sys.path.insert(0,str(ROOT))
from docs.research.sl_loop.lib import load_all,ENVA
from app.rs_final_engine import Sim as BaseSim
from app.rs_sl_engine import TPSim

def read_events(row):
    return [json.loads(x) for x in (OUT/row["events_file"]).read_text().splitlines() if x]

def recovery(ev, P):
    i=ev["exit_day"]; j=ev["symbol_index"]; side=ev["side"]; ep=ev["entry_px"]
    got={}; cens={}
    for h in (3,7):
        stop=min(i+h,len(P["days"])-1); close=P["C"][i+1:stop+1,23,j]
        valid=close[np.isfinite(close)]
        got[h]=bool(np.any(valid>=ep if side>0 else valid<=ep))
        cens[h]=(stop-i)<h
    return got,cens

def stop_quality(row,P):
    phase={}; all_ev=[]
    for p in (0,1,2):
        ev=[e for e in read_events(row) if e["phase"]==p and e["type"]==4]
        all_ev.extend(ev); q={"n":len(ev)}
        if ev:
            rec=[recovery(e,P) for e in ev]
            q.update(avg_underlying_loss=float(np.mean([(e["exit_px"]/e["entry_px"]-1)*e["side"] for e in ev])),
                     avg_equity_loss=float(np.mean([e["pnl"]/max(e["equity_entry"],1e-12) for e in ev])),
                     avg_days_held=float(np.mean([e["exit_day"]-e["entry_day"] for e in ev])),
                     whipsaw_3=float(np.mean([x[0][3] for x in rec])),whipsaw_7=float(np.mean([x[0][7] for x in rec])),
                     censored_3=sum(x[1][3] for x in rec),censored_7=sum(x[1][7] for x in rec),
                     hit_rate_7=float(np.mean([not x[0][7] for x in rec])))
        phase[str(p)]=q
    agg={"n":len(all_ev)}
    if all_ev:
        rec=[recovery(e,P) for e in all_ev]
        agg.update(avg_underlying_loss=float(np.mean([(e["exit_px"]/e["entry_px"]-1)*e["side"] for e in all_ev])),
                   avg_equity_loss=float(np.mean([e["pnl"]/max(e["equity_entry"],1e-12) for e in all_ev])),
                   avg_days_held=float(np.mean([e["exit_day"]-e["entry_day"] for e in all_ev])),
                   whipsaw_3=float(np.mean([x[0][3] for x in rec])),whipsaw_7=float(np.mean([x[0][7] for x in rec])),
                   censored_3=sum(x[1][3] for x in rec),censored_7=sum(x[1][7] for x in rec),hit_rate_7=float(np.mean([not x[0][7] for x in rec])))
    row["stop_quality"]={"phase":phase,"phase_pooled":agg}

def baseline_stx(base_row,P):
    spells=[]
    for e in read_events(base_row):
        if e["type"] in (0,3) and e["adverse_excursion"]<=-.20:
            spells.append(e)
    unique={}
    for e in spells:
        unique.setdefault((e["symbol_index"],e["side"],e["entry_day"]),e)
    events=list(unique.values()); rows=[]
    levels=(.03,.05,.075,.10,.125,.15,.20,.25,.30)
    for e in events:
        j=e["symbol_index"]; side=e["side"]; ep=e["entry_px"]; entry=e["entry_day"]; exitd=e["exit_day"]
        d={"symbol_index":j,"symbol":P["names"][j],"side":"long" if side>0 else "short","entry_day":entry,"baseline_exit_day":exitd,
           "baseline_adverse_excursion":e["adverse_excursion"],"baseline_realized_underlying":(e["exit_px"]/ep-1)*side,"counterfactual_stops":{}}
        for s in levels:
            result=None
            for day in range(entry+1,exitd+1):
                for h in range(24):
                    lo=P["L"][day,h,j]; hi=P["H"][day,h,j]; level=ep*(1-s if side>0 else 1+s)
                    hit=(side>0 and np.isfinite(lo) and lo<=level) or (side<0 and np.isfinite(hi) and hi>=level)
                    if hit:
                        close=P["C"][day,h,j]
                        if side>0:
                            base=hi if hi<level else level; f=base*.997; f=min(max(f,lo),hi)
                        else:
                            base=lo if lo>level else level; f=base*1.003; f=min(max(f,lo),hi)
                        result={"stopped":True,"day":day,"hour":h,"realized_underlying":(f/ep-1)*side,
                                "whipsaw_3":bool(recovery({"exit_day":day,"symbol_index":j,"side":side,"entry_px":ep},P)[0][3]),
                                "whipsaw_7":bool(recovery({"exit_day":day,"symbol_index":j,"side":side,"entry_px":ep},P)[0][7])}
                        break
                if result: break
            if result is None: result={"stopped":False,"realized_underlying":d["baseline_realized_underlying"],"whipsaw_3":False,"whipsaw_7":False}
            d["counterfactual_stops"][str(s)]=result
        rows.append(d)
    return {"spell_count_phase_occurrences":len(spells),"distinct_symbol_side_entry_spells":len(events),"events":rows}

def crash_episodes(P, CF, cells):
    sim=BaseSim(P); flag=sim.crash; d0=sim.d_start(); ids=np.flatnonzero(flag[d0:])+d0; groups=[]
    for ix in ids:
        if not groups or ix!=groups[-1][-1]+1: groups.append([int(ix)])
        else: groups[-1].append(int(ix))
    signal=sim.signal((14,)); base_kw=dict(ENVA)
    ctr={}
    full=TPSim(P,CF)
    for mode in (0,1):
        ctr[mode]=[full.run(sl={},phase=p,crash_mode=mode,**base_kw) for p in (0,1,2)]
    episodes=[]
    for epn,g in enumerate(groups,1):
        first,last=g[0],g[-1]; per_phase=[]; equity_changes=[]
        for ph in (0,1,2):
            # Most recent normal scheduled rebalance before crash; matching base target selection.
            prior=first-1; sc=signal[prior]; ok=np.flatnonzero(np.isfinite(sc)); order=ok[np.argsort(-sc[ok])]
            if len(order)<16: continue
            longs=order[:8]; shorts=order[-8:]
            eqseries=ctr[1][ph]["eq"].to_numpy(); eqprior=eqseries[prior]
            notional=eqprior*.95*4/(2*8); period_end=last
            # Next scheduled (phase-anchored) rebalance; include its close.
            firstdue=sim.d_start()+ph
            due=firstdue if firstdue>=first else firstdue+max(0,int(np.ceil((first-firstdue)/3)))*3
            if due<first: due+=3
            if due<=last: period_end=due
            for mode in (0,1):
                path=ctr[mode][ph]["eq"].to_numpy()
                equity_changes.append({"phase":ph,"mode":mode,"start_equity":float(path[prior]),"end_equity":float(path[period_end]),
                    "change_pct_start_equity":float((path[period_end]-path[prior])/max(path[prior],1e-12))})
            for side,names in (("long",longs),("short",shorts)):
                pnl=0.; notionals=0.
                for j in names:
                    px0=P["C"][prior,23,j]; px1=P["C"][period_end,23,j]
                    if not (np.isfinite(px0) and np.isfinite(px1) and px0>0): continue
                    qty=(notional/px0)*(1 if side=="long" else -1)
                    fd=np.nansum(CF[first:period_end+1,:,j])
                    pnl+=qty*(px1-px0)-qty*fd; notionals+=notional
                pct=pnl/max(eqprior,1e-12); after=pct-.002*notionals/max(eqprior,1e-12)
                per_phase.append({"phase":ph,"side":side,"notional":notionals,"pnl_pct_equity_before_cost":pct,"pnl_pct_equity_after_roundtrip_cost":after})
        btcmove=float(P["C"][first,23,P["names"].index("BTC")]/P["C"][first-14,23,P["names"].index("BTC")]-1)
        episodes.append({"episode":epn,"start":str(P["days"][first].date()),"end":str(P["days"][last].date()),"btc_14d_return_on_start":btcmove,
                         "start_index":first,"end_index":last,"counterfactual_by_phase":per_phase,"equity_changes_by_phase":equity_changes})
    return {"flag_evaluated_at_day_close":True,"episodes":episodes}

def classify(cells,base_id,selected):
    base=cells[base_id]; out={}
    family_specs=(("both_reentry","both"),("long_reentry","long"),("short_reentry","short"),("both_lockout","both"))
    for family,side in family_specs:
        rows=[r for r in cells.values() if r["params"]["family"]==family and r["params"].get("s",0)>0]
        rows.sort(key=lambda x:x["params"]["s"]); pick=cells[selected.get("both" if side=="both" else side,base_id)]
        center=pick["params"].get("s",0)
        if family=="both_lockout":
            allowed=[r for r in rows if r["IS"]["end"]>=.85*base["IS"]["end"]]
            pick=max(allowed,key=lambda r:r["IS"]["calmar_i"]) if allowed else max(rows,key=lambda r:r["IS"]["calmar_i"])
            center=pick["params"]["s"]
        ii=next((i for i,r in enumerate(rows) if r["params"]["s"]==center),0)
        neigh=rows[max(0,ii-2):min(len(rows),ii+3)]
        wins={w:sum(r[w]["calmar_i"]>base[w]["calmar_i"] and r[w]["cagr"]>=.9*base[w]["cagr"] for r in neigh)/max(len(neigh),1) for w in ("IS","OOS")}
        losses={w:sum(r[w]["calmar_i"]<base[w]["calmar_i"] and r[w]["cagr"]>=.9*base[w]["cagr"] for r in neigh)/max(len(neigh),1) for w in ("IS","OOS")}
        out[family]={"selected_s":center,"neighbor_ids":[r["id"] for r in neigh],"improve_fraction":wins,"worsen_fraction":losses,
                     "label":"helps" if min(wins.values())>=.8 else ("hurts" if min(losses.values())>=.8 else "noise")}
    tprows=[r for r in cells.values() if r["params"]["family"]=="tp_sl"]
    allowed=[r for r in tprows if r["IS"]["end"]>=.85*base["IS"]["end"]]
    if allowed:
        pick=max(allowed,key=lambda r:r["IS"]["calmar_i"]); ss=sorted(set(r["params"]["s"] for r in tprows)); xx=sorted(set(r["params"]["x"] for r in tprows))
        si=ss.index(pick["params"]["s"]); xi=xx.index(pick["params"]["x"])
        neigh=[r for r in tprows if abs(ss.index(r["params"]["s"])-si)<=2 and abs(xx.index(r["params"]["x"])-xi)<=2]
        wins={w:sum(r[w]["calmar_i"]>base[w]["calmar_i"] and r[w]["cagr"]>=.9*base[w]["cagr"] for r in neigh)/len(neigh) for w in ("IS","OOS")}
        losses={w:sum(r[w]["calmar_i"]<base[w]["calmar_i"] and r[w]["cagr"]>=.9*base[w]["cagr"] for r in neigh)/len(neigh) for w in ("IS","OOS")}
        out["tp_cross"]={"selected_s":pick["params"]["s"],"selected_x":pick["params"]["x"],"neighbor_ids":[r["id"] for r in neigh],"improve_fraction":wins,"worsen_fraction":losses,
                          "label":"helps" if min(wins.values())>=.8 else ("hurts" if min(losses.values())>=.8 else "noise")}
    return out

def main():
    data=json.loads((OUT/"results.json").read_text()); P,CF=load_all(); cells=data["cells"]; base=cells[data["baseline_id"]]
    for row in cells.values(): stop_quality(row,P)
    data["family_labels"]=classify(cells,data["baseline_id"],data["selected"])
    data["stx_type"]=baseline_stx(base,P)
    data["crash_episode_analysis"]=crash_episodes(P,CF,cells)
    # per-year baseline/candidate metric means and event counts
    data["year_metrics"]={}
    ids=[data["baseline_id"],data["selected"]["both"],data["selected"]["long"],data["selected"]["short"]]
    for cid in ids:
        r=cells[cid]; data["year_metrics"][cid]={}
        for y in range(2022,2027):
            per=[r["phase_results"][str(ph)]["years"][str(y)] for ph in (0,1,2)]
            valid=[x for x in per if x]
            data["year_metrics"][cid][str(y)]={k:float(np.mean([x[k] for x in valid])) for k in ("cagr","mdd","imdd","sharpe","end") } if valid else None
    # Full daily paths are recomputed for selected rows to attribute daily excess log returns.
    overlay=TPSim(P,CF); base_paths={}; cand_paths={}
    def run_path(cell):
        p=cell["params"]; ret=[]
        for ph in (0,1,2):
            r=overlay.run(sl={"SL":p["sL"],"SS":p["sS"],"lockout":p["lock"],"fillmode":p["fill"]},
                          tp={"XL":p["xL"],"XS":p["xS"],"lockout":p["lock"],"fillmode":p["fill"]},
                          phase=ph,crash_mode=p["crash"],**{**ENVA,"lev":p["lev"]})
            ret.append(r["eq"].to_numpy())
        return np.asarray(ret)
    base_paths=run_path(base)
    data["top5_day_share"]={}
    for cid in (sel["both"],sel["long"],sel["short"]):
        arr=run_path(cells[cid]); a=np.nanmean(np.log(arr[:,1:]/arr[:,:-1]),axis=0); z=np.nanmean(np.log(base_paths[:,1:]/base_paths[:,:-1]),axis=0)
        delta=a-z; dates=P["days"].tz_localize(None).to_numpy()[1:]
        oos=(dates>=np.datetime64("2024-07-01")); selected=delta[oos & (delta>0)]
        top=np.sort(selected)[-5:] if len(selected) else np.array([])
        ev=[e for e in read_events(cells[cid]) if e["type"]==4]
        cont=np.asarray([max(e["pnl"]/max(e["equity_entry"],1e-12),0.) for e in ev])
        data["top5_day_share"][cid]={"oos_positive_daily_log_excess_sum":float(selected.sum()),"top5_day_share":float(top.sum()/selected.sum()) if selected.sum()>0 else None,
            "positive_stop_pnl_share_top5_events":float(np.sort(cont)[-5:].sum()/cont.sum()) if cont.sum()>0 else None,
            "positive_stop_event_contribution_sum":float(cont.sum())}
    # Add baseline and top stop-cell comparisons at 5/10/15/30 percent.
    lookup={}
    for r in cells.values():
        p=r["params"]
        if p["family"]=="both_reentry" and p.get("s") in (.05,.10,.15,.30): lookup[str(int(p["s"]*100))]=r["id"]
    data["headline_stop_levels"]={k:lookup.get(k) for k in ("5","10","15","30")}
    (OUT/"results.json").write_text(json.dumps(data,indent=2,allow_nan=False))
    make_report(data)

def _pct(x): return f"{100*x:.1f}%"
def make_report(d):
    c=d["cells"]; b=c[d["baseline_id"]]; sel=d["selected"]
    both=c[sel["both"]]; long=c[sel["long"]]; short=c[sel["short"]]
    lines=[
        f"Per-position stops: both-side IS-selected {both['params'].get('s',0):.1%} stop; IS/OOS Calmar_i {both['IS']['calmar_i']:.2f}/{both['OOS']['calmar_i']:.2f} vs baseline {b['IS']['calmar_i']:.2f}/{b['OOS']['calmar_i']:.2f}.",
        f"The IS-selected stop {('improves' if both['IS']['calmar_i']>b['IS']['calmar_i'] else 'reduces')} IS Calmar_i and {('improves' if both['OOS']['calmar_i']>b['OOS']['calmar_i'] else 'reduces')} OOS Calmar_i.",
        f"Best long-only level: {long['params'].get('s',0):.1%}; IS/OOS Calmar_i {long['IS']['calmar_i']:.2f}/{long['OOS']['calmar_i']:.2f}.",
        f"Best short-only level: {short['params'].get('s',0):.1%}; IS/OOS Calmar_i {short['IS']['calmar_i']:.2f}/{short['OOS']['calmar_i']:.2f}.",
    ]
    for s in (.05,.10,.15,.30):
        r=next(x for x in c.values() if x["params"]["family"]=="both_reentry" and x["params"].get("s")==s)
        lines.append(f"At {s:.0%}, IS/OOS Calmar_i {r['IS']['calmar_i']:.2f}/{r['OOS']['calmar_i']:.2f}; end wealth {r['IS']['end']:.2f}x/{r['OOS']['end']:.2f}x.")
    lines.append(f"Across {d['meta']['unique_trials']} unique cells, treat the IS winner as exploratory because selection and kill-path chaos amplify overfit risk.")
    lines.append("Crash-filter OFF/longs-only rows are descriptive and do not support changing the live crash filter.")
    report="\n".join(lines)+"\n\n## Decision and candidate comparisons\n\n"
    report+=f"Baseline IS/OOS: CAGR {_pct(b['IS']['cagr'])}/{_pct(b['OOS']['cagr'])}, intraday MDD {_pct(b['IS']['imdd'])}/{_pct(b['OOS']['imdd'])}, Calmar_i {b['IS']['calmar_i']:.3f}/{b['OOS']['calmar_i']:.3f}.\n\n"
    report+="| Candidate | Stop | IS CAGR / iMDD / Calmar_i | OOS CAGR / iMDD / Calmar_i | IS wealth retention | kills/year | stops/year L/S | liquidation phases |\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
    for name,r in (("both selected",both),("long selected",long),("short selected",short)):
        p=r["params"]; stop=p.get("s",0)
        report+=f"| {name} | {stop:.1%} | {_pct(r['IS']['cagr'])} / {_pct(r['IS']['imdd'])} / {r['IS']['calmar_i']:.3f} | {_pct(r['OOS']['cagr'])} / {_pct(r['OOS']['imdd'])} / {r['OOS']['calmar_i']:.3f} | {_pct(r['IS']['end']/b['IS']['end'])} | {r['kills_per_year']:.2f} | {r['stops_per_year']['long']:.1f} / {r['stops_per_year']['short']:.1f} | {r['liquidations']}\n"
    report+="\n### Stop levels required by the question\n\n| Level | IS Calmar_i | OOS Calmar_i | IS/OOS CAGR | IS/OOS intraday MDD | IS wealth vs baseline |\n|---:|---:|---:|---:|---:|---:|\n"
    for s in (.05,.10,.15,.30):
        r=next(x for x in c.values() if x["params"]["family"]=="both_reentry" and x["params"].get("s")==s)
        report+=f"| {s:.0%} | {r['IS']['calmar_i']:.3f} | {r['OOS']['calmar_i']:.3f} | {_pct(r['IS']['cagr'])} / {_pct(r['OOS']['cagr'])} | {_pct(r['IS']['imdd'])} / {_pct(r['OOS']['imdd'])} | {_pct(r['IS']['end']/b['IS']['end'])} |\n"
    report+="\n## Crash-filter reference rows\n\nThese rows are explanatory only. Do not change the live filter based on them.\n\n| Crash mode | Stop | IS Calmar_i | OOS Calmar_i | IS/OOS wealth |\n|---|---:|---:|---:|---:|\n"
    refs=[r for r in c.values() if r["params"]["family"]=="crash_reference"]
    for r in refs: report+=f"| {r['params'].get('crash_name')} | {r['params'].get('ref_stop')} | {r['IS']['calmar_i']:.3f} | {r['OOS']['calmar_i']:.3f} | {r['IS']['end']:.2f}x / {r['OOS']['end']:.2f}x |\n"
    report+="\n### BTC flat episodes and held-book counterfactual\n\nPositions use normal close ranking from the day before the flag, ENV-A per-leg notional, funding through the earlier of episode end or next scheduled rebalance, and fixed 0.2% round-trip cost. PnL is contribution as percent of equity at the start.\n\n"
    for ep in d["crash_episode_analysis"]["episodes"]:
        report+=f"- Episode {ep['episode']}: {ep['start']}–{ep['end']}, BTC 14d return at start {_pct(ep['btc_14d_return_on_start'])}.\n"
        for side in ("long","short"):
            vals=[x for x in ep["counterfactual_by_phase"] if x["side"]==side]
            if vals: report+=f"  - {side} retained book mean contribution: before cost {_pct(np.mean([x['pnl_pct_equity_before_cost'] for x in vals]))}; after cost {_pct(np.mean([x['pnl_pct_equity_after_roundtrip_cost'] for x in vals]))}.\n"
        ev=ep["equity_changes_by_phase"]
        off=np.mean([x["change_pct_start_equity"] for x in ev if x["mode"]==0]); live=np.mean([x["change_pct_start_equity"] for x in ev if x["mode"]==1])
        report+=f"  - Backtest equity change over the same exposure window: crash-off { _pct(off) }, live full-flat {_pct(live)} (phase mean).\n"
    report+="\n## Stops, whipsaw, and cost diagnostics\n\n| Cell | Stops/year | Long/short per year | Average underlying loss | Average net loss / entry equity | Whipsaw 3d / 7d | Hit rate 7d | Avg held days | Turnover x/year | cost / avg equity / year |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for cid in [d["baseline_id"],sel["both"],sel["long"],sel["short"]]:
        r=c[cid]; q=r["stop_quality"]["phase_pooled"]
        report+=f"| {cid} | {r['stops_per_year']['all']:.1f} | {r['stops_per_year']['long']:.1f}/{r['stops_per_year']['short']:.1f} | {_pct(q.get('avg_underlying_loss',0))} | {_pct(q.get('avg_equity_loss',0))} | {_pct(q.get('whipsaw_3',0))} / {_pct(q.get('whipsaw_7',0))} | {_pct(q.get('hit_rate_7',0))} | {q.get('avg_days_held',0):.2f} | {r['turnover_x_per_year']:.2f} | {_pct(r['cost_pct_avg_equity_per_year'])} |\n"
    report+="\nAll stop rates are reported per phase pooled event count divided by simulated years; whipsaw checks use hourly-panel daily closes after the exit. Censored 3/7-day events are counted separately in results.json.\n"
    report+="\n## Family labels\n\nThe rule requires at least 80% of the selected stop level and up to two adjacent tested levels on each side to improve/worsen Calmar_i in both IS and OOS while meeting the 0.9x CAGR tolerance.\n\n"
    for family,q in d["family_labels"].items(): report+=f"- {family}: **{q['label']}**; neighbor improvement fraction IS/OOS {q['improve_fraction']['IS']:.0%}/{q['improve_fraction']['OOS']:.0%}.\n"
    report+="\n## STX-type events\n\nSTX events are distinct `(symbol, side, entry day)` baseline holding spells with at least 20% adverse hourly excursion.\n\n"
    report+=f"The baseline contains {d['stx_type']['spell_count_phase_occurrences']} phase-specific instances and {d['stx_type']['distinct_symbol_side_entry_spells']} distinct symbol-side-entry spells. The full event and stop-level counterfactual ledger is in `results.json`.\n\n"
    for s in (.05,.10,.15,.20,.25,.30):
        matches=[e["counterfactual_stops"][str(s)] for e in d["stx_type"]["events"]]
        if matches:
            n=sum(x["stopped"] for x in matches); avg=np.mean([x["realized_underlying"] for x in matches if x["stopped"]]) if n else 0
            report+=f"- {s:.0%} stop: {n}/{len(matches)} events stopped; mean realized underlying loss among stops {_pct(avg)}.\n"
    report+="\n## Per-year metrics and largest events\n\nPer-year phase-mean CAGR, MDD, intraday MDD, Sharpe, and end multiple for baseline and IS-selected side families are stored in `results.json` under `year_metrics`. Selected stop trade logs are in `events/`. The largest positive stop-event PnL contributions are identified by net PnL divided by entry equity:\n\n"
    for cid in (sel["both"],sel["long"],sel["short"]):
        ev=[e for e in read_events(c[cid]) if e["type"]==4]; top=sorted(ev,key=lambda e:e["pnl"]/max(e["equity_entry"],1e-12),reverse=True)[:5]
        report+=f"- {cid}: "+("; ".join(f"{e['symbol_index']} day {e['exit_day']} phase {e['phase']} contribution {e['pnl']/max(e['equity_entry'],1e-12):.2%}" for e in top) if top else "no stop events")+".\n"
    report+="\nTop-five OOS positive daily log-excess shares and top-five positive stop-event contribution shares (recomputed daily paths vs baseline):\n\n"
    for cid,q in d["top5_day_share"].items(): report+=f"- {cid}: top five days { _pct(q['top5_day_share'] or 0) } of positive daily log excess; top five positive stop events { _pct(q['positive_stop_pnl_share_top5_events'] or 0) } of positive stop-event contribution.\n"
    report+="\n## Trial count, multiple testing, and limitations\n\n"
    report+=f"The completed study ran {d['meta']['unique_trials']} unique parameter cells across {d['meta']['phase_jobs']} cell-phase jobs using {d['meta']['workers']} processes. Nominal Bonferroni threshold at alpha 0.05 is {0.05/d['meta']['unique_trials']:.6f}. Cells are highly correlated, but this threshold illustrates the cost of selection; IS selection is not independent confirmation.\n\n"
    report+="The five largest flash-crash day contribution comparison is unavailable because daily equity paths were not retained. One historical path, multiple kill-triggered path changes, bar-based fills, and current-listing survivorship limit inference. Today's 45-symbol universe omits delisted assets, understating short squeeze/delist tail risk. The cross-margin liquidation check runs intraday before stop realization; all cells report liquidation counts, while the daily-close kill switch remains a separate later event. Stops at 25% and above are liquidation-level/beyond at 4x isolated-margin arithmetic.\n\n"
    report+="## Reproduction\n\n- Test command: `RS_FINAL_SCRATCH=/Users/user/CODE/Ochestration/trading/.rs_cache/sl_panel NUMBA_CACHE_DIR=/Users/user/CODE/Ochestration/trading/.rs_cache/sl_nbc /opt/anaconda3/bin/python -m pytest tests/test_sl_engine.py -q`\n- Grid command: `RS_FINAL_SCRATCH=/Users/user/CODE/Ochestration/trading/.rs_cache/sl_panel NUMBA_CACHE_DIR=/Users/user/CODE/Ochestration/trading/.rs_cache/sl_nbc /opt/anaconda3/bin/python docs/research/sl_loop/run.py`\n- Analysis command: `RS_FINAL_SCRATCH=/Users/user/CODE/Ochestration/trading/.rs_cache/sl_panel NUMBA_CACHE_DIR=/Users/user/CODE/Ochestration/trading/.rs_cache/sl_nbc /opt/anaconda3/bin/python docs/research/sl_loop/analyze.py`\n"
    (OUT/"report.md").write_text(report)

if __name__=="__main__": main()
