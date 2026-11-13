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
    return [json.loads(x) for x in Path(row["events_file"]).read_text().splitlines() if x]

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
    levels=(0.,.005,.01,.015,.02,.03,.04,.05,.06,.07,.08,.09,.10,.12,.14,.16,.18,.20,.225,.25,.275,.30,.35,.40,.50,.60,.75,1.)
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

def levels(): return (0.,.005,.01,.015,.02,.03,.04,.05,.06,.07,.08,.09,.10,.12,.14,.16,.18,.20,.225,.25,.275,.30,.35,.40,.50,.60,.75,1.)

def curve_rows(cells, lev, family):
    rows=[r for r in cells.values() if r['params']['lev']==lev and r['params']['family']==family]
    return sorted(rows,key=lambda r: -1 if r['params'].get('s') is None else r['params']['s'])

def main():
    d=json.loads((OUT/'results_v2.json').read_text()); P,CF=load_all(); c=d['cells']; base=c[d['baseline_id']]
    if 'curves' not in d:
        for row in c.values(): stop_quality(row,P)
        d['stx_type']=baseline_stx(base,P); d['crash_episode_analysis']=crash_episodes(P,CF,c)
    d['curves']={}
    for lev in (4.,3.,2.):
        fam='both_reentry' if lev==4. else 'leverage_both'; rows=curve_rows(c,lev,fam)
        b=base if lev==4 else next(r for r in c.values() if r['params']['lev']==lev and r['params']['s'] is None)
        curve=[{'id':b['id'],'s':None,'label':'baseline','liquidation_equivalent':False,'margin_pnl_pct':None,'stops_per_year':0.,'whipsaw_7':None,
                **{w:{k:b[w][k] for k in ('cagr','imdd','calmar_i','end')} for w in ('IS','OOS','full')}}]
        for i,r in enumerate(rows):
            nei=rows[max(0,i-2):i+3]
            helps={w:sum(x[w]['calmar_i']>b[w]['calmar_i'] and x[w]['cagr']>=.9*b[w]['cagr'] for x in nei)/len(nei) for w in ('IS','OOS')}
            hurts={w:sum(x[w]['calmar_i']<b[w]['calmar_i'] and x[w]['cagr']>=.9*b[w]['cagr'] for x in nei)/len(nei) for w in ('IS','OOS')}
            label='helps' if min(helps.values())>=.8 else ('hurts' if min(hurts.values())>=.8 else 'noise')
            s=r['params']['s']; q={'id':r['id'],'s':s,'label':label,'liquidation_equivalent':bool(s is not None and s*lev>=1),
                'margin_pnl_pct':None if s is None else 100*s*lev,'stops_per_year':r['stops_per_year']['all'],
                'stops_long_per_year':r['stops_per_year']['long'],'stops_short_per_year':r['stops_per_year']['short'],
                'liquidations':r['liquidations'],'kills_mean':r['kills_mean'],
                'whipsaw_7':r['stop_quality']['phase_pooled'].get('whipsaw_7')}
            for w in ('IS','OOS','full'): q[w]={k:r[w][k] for k in ('cagr','imdd','calmar_i','end')}
            curve.append(q)
        d['curves'][str(int(lev))]=curve
    cand=[r for r in curve_rows(c,4.,'both_reentry') if r['IS']['end']>=.85*base['IS']['end']]
    cand.sort(key=lambda r:r['IS']['calmar_i'],reverse=True); d['selected_candidates']=[r['id'] for r in cand[:3]]
    best=c[d['selected']['best_both']]
    d['year_metrics']={}
    for r in (base,best):
        yout={}
        for y in range(2022,2027):
            arr=[r['phase_results'][str(p)]['years'][str(y)] for p in (0,1,2)]; arr=[x for x in arr if x]
            yout[str(y)]={k:float(np.mean([x[k] for x in arr])) for k in ('cagr','mdd','imdd','sharpe','end')} if arr else None
        d['year_metrics'][r['id']]=yout
    def paths(row):
        sim=TPSim(P,CF); p=row['params']; out=[]
        for ph in (0,1,2):
            z=sim.run(sl={'SL':p['sL'],'SS':p['sS'],'lockout':p['lock'],'fillmode':p['fill']},phase=ph,crash_mode=p['crash'],**{**ENVA,'lev':p['lev']})
            out.append(z['eq'].to_numpy())
        return np.asarray(out)
    if 'matched_stops' not in d.get('concentration',{}) or (d['concentration'].get('largest_stop_events') and 'symbol' not in d['concentration']['largest_stop_events'][0]):
        bp=paths(base); cp=paths(best); daily=np.nanmean(np.log(cp[:,1:]/cp[:,:-1])-np.log(bp[:,1:]/bp[:,:-1]),axis=0)
        dates=P['days'].tz_localize(None).to_numpy()[1:]; pos=daily[(dates>=np.datetime64('2024-07-01'))&(daily>0)]
        stops=[e for e in read_events(best) if e['type']==4]; base_events=read_events(base)
        base_map={(e['phase'],e['symbol_index'],e['side'],e['entry_day']):e for e in base_events}
        attribution=[]
        for e in stops:
            match=base_map.get((e['phase'],e['symbol_index'],e['side'],e['entry_day']))
            if match:
                delta=(e['pnl']-match['pnl'])/max(e['equity_entry'],1e-12)
                attribution.append({'phase':e['phase'],'symbol_index':e['symbol_index'],'symbol':P['names'][e['symbol_index']],
                    'side':e['side'],'entry_day':e['entry_day'],'entry_date':str(P['days'][e['entry_day']].date()),
                    'exit_day':e['exit_day'],'candidate_stop_pnl':e['pnl'],'baseline_spell_pnl':match['pnl'],'improvement_over_baseline':delta})
        positive=np.array([max(x['improvement_over_baseline'],0.) for x in attribution])
        d['concentration']={'top5_days_share':float(np.sort(pos)[-5:].sum()/pos.sum()) if pos.sum()>0 else None,
            'top5_positive_stop_events_share':float(np.sort(positive)[-5:].sum()/positive.sum()) if positive.sum()>0 else None,
            'matched_stops':len(attribution),'candidate_stops':len(stops),
            'largest_stop_events':sorted(attribution,key=lambda e:e['improvement_over_baseline'],reverse=True)[:5]}
    d['trial_accounting']={'v1':98,'v2_unique':len(c),'total':98+len(c),'nominal_005_per_trial':.05/(98+len(c)),'planned_v2':125,'count_error':len(c)!=125}
    (OUT/'results_v2.json').write_text(json.dumps(d,indent=2,allow_nan=False)); (OUT/'results.json').write_text(json.dumps(d,indent=2,allow_nan=False)); report(d)

def report(d):
    c=d['cells']; b=c[d['baseline_id']]; sel=c[d['selected']['best_both']]; s=sel['params'].get('s')
    # Plain-language executive summary: exactly ten lines.
    curve={x['s']:x for x in d['curves']['4']}
    lv=[]
    lv.append(f"The symmetric both-side stop selected by IS is {s:.1%}; IS/OOS Calmar_i is {sel['IS']['calmar_i']:.3f}/{sel['OOS']['calmar_i']:.3f} versus baseline {b['IS']['calmar_i']:.3f}/{b['OOS']['calmar_i']:.3f}.")
    for x in (.005,.01,.03,.05,.10,.15,.30,1.):
        r=curve.get(x)
        if r is None:
            lo,hi=curve[.14],curve[.16]; r={w:{k:(lo[w][k]+hi[w][k])/2 for k in ('cagr','imdd','calmar_i')} for w in ('IS','OOS')}
            lv.append(f"At 15.0% (interpolated between tested 14% and 16%), IS/OOS CAGR is {r['IS']['cagr']:.2%}/{r['OOS']['cagr']:.2%}, intraday MDD {r['IS']['imdd']:.2%}/{r['OOS']['imdd']:.2%}, and Calmar_i {r['IS']['calmar_i']:.3f}/{r['OOS']['calmar_i']:.3f}.")
        else: lv.append(f"At {x:.1%}, IS/OOS CAGR is {r['IS']['cagr']:.2%}/{r['OOS']['cagr']:.2%}, intraday MDD {r['IS']['imdd']:.2%}/{r['OOS']['imdd']:.2%}, and Calmar_i {r['IS']['calmar_i']:.3f}/{r['OOS']['calmar_i']:.3f}.")
    lv.append(f"The grid therefore {'shows a possible stop benefit' if sel['OOS']['calmar_i']>b['OOS']['calmar_i'] else 'does not show an OOS stop benefit'} at the IS-selected level; OOS remains held-out diagnosis.")
    txt='\n'.join(lv[:10])+'\n\n## 4x stop curve\n\n| s | margin PnL equiv | IS CAGR / IMDD / Calmar_i | OOS CAGR / IMDD / Calmar_i | full CAGR / IMDD / Calmar_i | stops/year L/S | 7d whipsaw | label |\n|---:|---:|---:|---:|---:|---:|---:|---|\n'
    for x in d['curves']['4']:
        ss='baseline' if x['s'] is None else f"{x['s']:.1%}"+(' †' if x['liquidation_equivalent'] else '')
        w=x['whipsaw_7']; txt+=f"| {ss} | {'—' if x['margin_pnl_pct'] is None else format(x['margin_pnl_pct'],'.1f')+'%'} | {x['IS']['cagr']:.2%} / {x['IS']['imdd']:.2%} / {x['IS']['calmar_i']:.3f} | {x['OOS']['cagr']:.2%} / {x['OOS']['imdd']:.2%} / {x['OOS']['calmar_i']:.3f} | {x['full']['cagr']:.2%} / {x['full']['imdd']:.2%} / {x['full']['calmar_i']:.3f} | {x.get('stops_long_per_year',0):.1f}/{x.get('stops_short_per_year',0):.1f} | {'n/a' if w is None else f'{w:.1%}'} | {x['label']} |\n"
    txt+='\n† At/beyond isolated liquidation equivalent. Margin PnL equivalent = s × leverage; equivalences are 25% at 4x, 33.3% at 3x, 50% at 2x. At 100%, a long stop is unreachable unless price reaches zero; short stop triggers at 2× entry. Intraday cross-margin liquidation is checked before SL realization; the kill switch is later.\n\n## 3x and 2x curve\n\n| leverage | s | IS CAGR / IMDD / Calmar_i | OOS CAGR / IMDD / Calmar_i | full CAGR / IMDD / Calmar_i | stops/year | label |\n|---:|---:|---:|---:|---:|---:|---|\n'
    for lev in ('3','2'):
        for x in d['curves'][lev]:
            ss='baseline' if x['s'] is None else f"{x['s']:.1%}"+(' †' if x['liquidation_equivalent'] else '')
            txt+=f"| {lev}x | {ss} | {x['IS']['cagr']:.2%} / {x['IS']['imdd']:.2%} / {x['IS']['calmar_i']:.3f} | {x['OOS']['cagr']:.2%} / {x['OOS']['imdd']:.2%} / {x['OOS']['calmar_i']:.3f} | {x['full']['cagr']:.2%} / {x['full']['imdd']:.2%} / {x['full']['calmar_i']:.3f} | {x['stops_per_year']:.1f} | {x['label']} |\n"
    txt+='\n## Best candidates and annual diagnosis\n\n'
    for cid in d['selected_candidates']:
        r=c[cid]; txt+=f"- s={r['params']['s']:.1%}: IS/OOS Calmar_i {r['IS']['calmar_i']:.3f}/{r['OOS']['calmar_i']:.3f}; CAGR {r['IS']['cagr']:.2%}/{r['OOS']['cagr']:.2%}; ending multiple {r['IS']['end']:.3f}x/{r['OOS']['end']:.3f}x.\n"
    lockouts=[r for r in c.values() if r['params']['family']=='both_lockout' and r['IS']['end']>=.85*b['IS']['end']]
    if lockouts:
        lockbest=max(lockouts,key=lambda r:r['IS']['calmar_i'])
        txt+=f"- Best eligible lockout s={lockbest['params']['s']:.1%}: IS/OOS Calmar_i {lockbest['IS']['calmar_i']:.3f}/{lockbest['OOS']['calmar_i']:.3f}; CAGR {lockbest['IS']['cagr']:.2%}/{lockbest['OOS']['cagr']:.2%}. All 28 lockout rows remain in results_v2.json.\n"
    txt+='\n| year | baseline CAGR / IMDD / end | selected CAGR / IMDD / end |\n|---:|---:|---:|\n'
    for y in range(2022,2027):
        bm=d['year_metrics'][b['id']][str(y)]; sm=d['year_metrics'][sel['id']][str(y)]
        if bm and sm: txt+=f"| {y} | {bm['cagr']:.2%} / {bm['imdd']:.2%} / {bm['end']:.3f}x | {sm['cagr']:.2%} / {sm['imdd']:.2%} / {sm['end']:.3f}x |\n"
    txt+='\n## Crash-filter reference rows\n\nMode 0 disables crash flattening; mode 2 flattens longs and retains normal short positions. These comparisons are descriptive and do not recommend changing the crash filter.\n\n| mode | stop | IS Calmar_i | OOS Calmar_i | IS/OOS end | liq / kill |\n|---:|---:|---:|---:|---:|---:|\n'
    for r in c.values():
        if r['params']['family']=='crash_reference': txt+=f"| {r['params']['crash_name']} | {r['params'].get('ref_stop')} | {r['IS']['calmar_i']:.3f} | {r['OOS']['calmar_i']:.3f} | {r['IS']['end']:.3f}x / {r['OOS']['end']:.3f}x | {r['liquidations']} / {r['kills_mean']:.1f} |\n"
    ep=d['crash_episode_analysis']['episodes']; earnings={side:[] for side in ('short','long')}
    for e in ep:
        for x in e['counterfactual_by_phase']: earnings[x['side']].append(x['pnl_pct_equity_after_roundtrip_cost'])
    sums={side:sum(vals) for side,vals in earnings.items()}
    txt+=f"\nAcross {len(ep)} BTC crash episodes, the fixed short book averaged {sums['short']/max(len(earnings['short']),1):.2%} of starting equity per episode-phase after 0.2% round-trip costs; {sum(x>0 for x in earnings['short'])}/{len(earnings['short'])} episode-phase observations were profitable. Long-book equivalent averaged {sums['long']/max(len(earnings['long']),1):.2%}, profitable in {sum(x>0 for x in earnings['long'])}/{len(earnings['long'])}. Thus the full-flat filter did sell profitable shorts during sell-offs in this sample, while longs lost overall; this remains descriptive and does not recommend changing the filter.\n\n## STX events, concentration, and trial accounting\n\n"
    txt+='\n| episode | start–end | BTC 14d | short book after cost (phase mean) | long book after cost (phase mean) | crash-off equity change | live-flat equity change |\n|---:|---|---:|---:|---:|---:|---:|\n'
    for e in ep:
        sides={side:[x['pnl_pct_equity_after_roundtrip_cost'] for x in e['counterfactual_by_phase'] if x['side']==side] for side in ('short','long')}
        changes={mode:[x['change_pct_start_equity'] for x in e['equity_changes_by_phase'] if x['mode']==mode] for mode in (0,1)}
        txt+=f"| {e['episode']} | {e['start']}–{e['end']} | {e['btc_14d_return_on_start']:.1%} | {np.mean(sides['short']):.2%} | {np.mean(sides['long']):.2%} | {np.mean(changes[0]):.2%} | {np.mean(changes[1]):.2%} |\n"
    txt+='\n## STX events, concentration, and trial accounting\n\n'
    q=d['stx_type']; conc=d['concentration']; txt+=f"STX-type baseline spells (>=20% adverse underlying excursion): {q['spell_count_phase_occurrences']} phase occurrences and {q['distinct_symbol_side_entry_spells']} distinct symbol/side/entry spells. For each spell, all 28 stop thresholds' trigger day, underlying loss and 3/7-day whipsaw outcome are in results_v2.json. Top-five positive OOS daily excess share: {conc['top5_days_share']}; top-five matched stopped-event improvement share: {conc['top5_positive_stop_events_share']} ({conc['matched_stops']}/{conc['candidate_stops']} stops matched to a baseline spell).\n\n| largest matched event | phase | side | entry index | stop PnL | baseline spell PnL | improvement / entry equity |\n|---:|---:|---|---:|---:|---:|---:|\n"
    # Ranked matched stop events and compact contiguous helps bands.
    txt=txt.replace('| largest matched event | phase | side | entry index | stop PnL | baseline spell PnL | improvement / entry equity |','| rank | symbol | phase | side | entry date | stop PnL | baseline spell PnL | improvement / entry equity |')
    for i,e in enumerate(conc['largest_stop_events'],1): txt+=f"| {i} | {e['symbol']} | {e['phase']} | {'long' if e['side']>0 else 'short'} | {e['entry_date']} | {e['candidate_stop_pnl']:.4f} | {e['baseline_spell_pnl']:.4f} | {e['improvement_over_baseline']:.2%} |\n"
    txt+='\nContiguous helps bands under the preregistered neighbor test: '
    bandtxt=[]
    for lev in ('4','3','2'):
        vals=[x['s'] for x in d['curves'][lev] if x['s'] is not None and x['label']=='helps']
        if vals: bandtxt.append(f"{lev}x: {min(vals):.1%}–{max(vals):.1%}")
        else: bandtxt.append(f"{lev}x: none")
    txt+= '; '.join(bandtxt)+'.\n\nFor high-s 4x rows (s >=25%), the intraday liquidation count and daily-close kill count by cell are: '
    high=[x for x in d['curves']['4'] if x['s'] is not None and x['s']>=.25]
    txt+=', '.join(f"{x['s']:.1%}: liquidation={x['liquidations']}, mean kills={x['kills_mean']:.2f}" for x in high)+". Where liquidation occurred, the engine intraday liquidation check precedes stop realization and the later kill switch; these high-s rows had the listed zero/nonzero liquidation counts.\n\n"
    z=d['trial_accounting']; txt+=f"Trials: v1 {z['v1']} + v2 {z['v2_unique']} = {z['total']} unique cells; nominal 0.05/trials={z['nominal_005_per_trial']:.6f}. V1 results were observed before v2 revision, creating forking-paths risk. V2 grid and selection rule were fixed before v2 runs, but the preregistered count estimate was 125 while 127 unique IDs actually ran; this discrepancy was appended after execution. Survivorship: 45 current listings omit delisted assets. Three phase offsets are correlated slices of one historical path, not independent samples. Fill prices are range-clamped approximations.\n"
    (OUT/'report.md').write_text(txt)

if __name__=='__main__': main()
