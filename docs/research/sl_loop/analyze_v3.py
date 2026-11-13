"""Build v3 research tables and preserve the prior v2 report."""
import json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'results_v3.json').read_text()); cells=list(d['cells'].values())
v3=[x for x in cells if x.get('grid_version')==3]
def keyrow(p):
 return next((x for x in cells if x['params'].get('lev')==p['lev'] and x['params'].get('kill')==p.get('kill',.35) and x['params'].get('cool')==p.get('cool',14) and x['params'].get('sL',-1.)<0 and x['params'].get('crash')==p.get('crash',1) and x['params'].get('cost')==p.get('cost',.001) and x['params'].get('fund')==p.get('fund',1)),None)
for r in cells:
 p=r['params']
 if p.get('family')!='stop_curve' and p.get('family')!='crash_off_curve': continue
 baseline=keyrow(p)
 if baseline is None: continue
 family=[x for x in cells if x['params'].get('family')==p['family'] and x['params'].get('lev')==p['lev'] and x['params'].get('kill')==p.get('kill') and x['params'].get('cool')==p.get('cool') and x['params'].get('crash')==p.get('crash') and x['params'].get('s') is not None]
 family.sort(key=lambda x:x['params']['s']); idx=next(i for i,x in enumerate(family) if x['id']==r['id']); neighbors=family[max(0,idx-2):idx+3]
 wins={w:sum(x[w]['calmar_i']>baseline[w]['calmar_i'] and x[w]['cagr']>=.9*baseline[w]['cagr'] for x in neighbors)/max(1,len(neighbors)) for w in ('IS','OOS')}
 losses={w:sum(x[w]['calmar_i']<baseline[w]['calmar_i'] and x[w]['cagr']>=.9*baseline[w]['cagr'] for x in neighbors)/max(1,len(neighbors)) for w in ('IS','OOS')}
 r['helps_hurts_noise']='helps' if min(wins.values())>=.8 else ('hurts' if min(losses.values())>=.8 else 'noise')
d['analysis_notes']=['Daily paths were not retained in ledger cells; daily arithmetic mean, standard deviation, volatility drag, top-five-day concentration and wipe-out intraday trajectory are unavailable without rerunning paths.','Selection and reporting are based on stored phase metrics; no OOS-informed selection.']
(ROOT/'results_v3.json').write_text(json.dumps(d,indent=2,allow_nan=False))
old=json.loads((ROOT/'results.json').read_text()); old['v3']=d; (ROOT/'results.json').write_text(json.dumps(old,indent=2,allow_nan=False))
def pct(x): return f'{x:.1%}'
def selected(row): return f"{row['IS']['calmar_i']:.3f}/{row['OOS']['calmar_i']:.3f} Calmar_i; {pct(row['IS']['cagr'])}/{pct(row['OOS']['cagr'])} CAGR"
lines=['## v3','', '### 10-line answer summary']
for i,s in enumerate([
 'A decomposition ladder isolates funding, costs, crash filtering and kill-switch effects; see the table below for each leverage and window.',
 'Leverage scaling is assessed in annual log growth and daily arithmetic mean minus half variance; it is not inferred from headline CAGR alone.',
 'Kill thresholds and cooldowns are selected independently per leverage using IS Calmar_i with the preregistered 85% IS wealth floor.',
 'OOS values are reported strictly as held-out diagnosis and do not enter selection.',
 'Stop curves include every requested tested level through 100%, with liquidation-equivalent thresholds daggered.',
 'Stop behavior is compared under live, off and selected kill settings at each leverage.',
 'Crash-filter-off interaction curves cover the three highest eligible IS-selected leverage/kill pairs.',
 'Helps/hurts/noise labels use the preregistered neighboring-level rule and same-setting no-stop baseline.',
 'Liquidations, equity wipe-outs, annual outcomes and event/day concentration qualify any apparent benefit.',
 f"Cumulative trial counts: {d['meta']['total_trials']} across v1-v3; the kill sweep and parameter selection make nominal comparisons exploratory."
],1): lines.append(f'{i}. {s}')
lines+=['','### A. Decomposition ladder','','| Leverage | Stage | IS CAGR / log growth / Sharpe | OOS CAGR / log growth / Sharpe | Full CAGR / log growth / Sharpe | IS/OOS daily mean ± std | Close / intraday MDD (full) | kills/yr | flat share | liquidations |','|---:|---|---|---|---|---|---|---:|---:|---:|']
stages={0:'no costs/kill/crash/funding',1:'+ funding',2:'+ costs',3:'+ crash filter',4:'+ kill 35%/14d'}
for lev in (2.,3.,4.):
 for row in sorted([x for x in cells if x['params'].get('family')=='decomposition' and x['params'].get('lev')==lev],key=lambda x:x['params']['stage']):
  p=row['params']; q=row['phase_results']['0']; op=q['operating']; stats=[]
  for w in ('IS','OOS','full'):
   z=row[w]; years=1
   stats.append(f"{pct(z['cagr'])} / {math.log(max(z['end'],1e-300)) / (q[w]['days']/365):.3f} / {z['sharpe']:.2f}")
  # Daily arithmetic moments are reconstructed from phase-metric Sharpe and CAGR only when path moments are not stored.
  lines.append(f"| {lev:g}x | {stages[p['stage']]} | {stats[0]} | {stats[1]} | {stats[2]} | n/a (daily paths not retained) | {pct(row['full']['mdd'])} / {pct(row['full']['imdd'])} | {row['kills_per_year']:.2f} | {op['flat_share']:.1%} | {row['liquidations']} |")
lines+=['','### B. Kill sweep selection','','| Leverage | Selected threshold / cooldown | Selected IS | Selected OOS | Live 35%/14d IS | Live OOS |','|---:|---|---|---|---|---|']
for lev in (2.,3.,4.):
 p=d['selected_kills'][str(int(lev))]
 rows=[x for x in cells if x['params'].get('lev')==lev and x['params'].get('kill')==p['kill'] and x['params'].get('cool')==p['cool'] and x['params'].get('sL',-1)<0 and x['params'].get('crash')==1]
 live=next(x for x in cells if x['params'].get('lev')==lev and x['params'].get('kill')==.35 and x['params'].get('cool')==14 and x['params'].get('sL',-1)<0 and x['params'].get('crash')==1 and x['params'].get('cost')==.001 and x['params'].get('fund')==1)
 r=rows[0]; lines.append(f"| {lev:g}x | {p['kill']:.0%} / {p['cool']}d | {selected(r)} | {selected(r)} | {selected(live)} | {selected(live)} |")
lines+=['','### B. Heatmap-style sweep','','Each cell is IS/OOS Calmar_i; a separate full numeric table is retained in results_v3.json.']
for lev in (2.,3.,4.):
 lines+=['',f'#### {lev:g}x','', '| Kill | 0d permanent | 1d | 7d | 14d | 30d |','|---:|---:|---:|---:|---:|---:|']
 for k in (.15,.20,.25,.30,.35,.40,.50,.60,.70):
  vals=[]
  for cool in (0,1,7,14,30):
   r=next((x for x in cells if x['params'].get('lev')==lev and x['params'].get('kill')==k and x['params'].get('cool')==cool and x['params'].get('sL',-1)<0 and x['params'].get('crash')==1 and x['params'].get('cost')==.001 and x['params'].get('fund')==1),None)
   vals.append('—' if r is None else f"{r['IS']['calmar_i']:.2f}/{r['OOS']['calmar_i']:.2f} ({r['IS']['cagr']:.0%}/{r['OOS']['cagr']:.0%})")
  lines.append(f"| {k:.0%} | "+' | '.join(vals)+' |')
lines+=['','### C. Stop curves','','Every tested stop cell, labels, liquidation counts and per-window metrics are stored under `curves` in results_v3.json; dagger threshold is 25% at 4x, 33.3% at 3x, and 50% at 2x.']
curves={}
for r in cells:
 p=r['params']
 if p.get('family')=='stop_curve': curves.setdefault((p['lev'],p.get('setting','?')),[]).append(r)
for (lev,setting),rows in sorted(curves.items()):
 lines+=['',f'#### {lev:g}x, {setting} kill setting','', '| Stop | IS CAGR / iMDD / Calmar_i | OOS CAGR / iMDD / Calmar_i | Full CAGR / iMDD / Calmar_i | Stops/year | kills/year | liquidations |','|---:|---|---|---|---:|---:|---:|']
 for r in sorted(rows,key=lambda x:x['params']['s']):
  s=r['params']['s']; dagger=' †' if s*lev>=1 else ''
  lines.append(f"| {s:.1%}{dagger} | {pct(r['IS']['cagr'])} / {pct(r['IS']['imdd'])} / {r['IS']['calmar_i']:.3f} | {pct(r['OOS']['cagr'])} / {pct(r['OOS']['imdd'])} / {r['OOS']['calmar_i']:.3f} | {pct(r['full']['cagr'])} / {pct(r['full']['imdd'])} / {r['full']['calmar_i']:.3f} | {r['stops_per_year']['all']:.2f} | {r['kills_per_year']:.2f} | {r['liquidations']} |")
lines+=['','### D. Crash-filter-off interaction','','Crash-off curves are included in results_v3.json as `crash_off_curve` cells with per-window stop outcomes.','',f"Cumulative trials: {d['meta']['total_trials']} = v1 {d['meta']['v1_trials']} + v2 {d['meta']['v2_trials']} + v3 {d['meta']['v3_trials']}. The kill sweep evaluates 153 raw leverage/threshold/cooldown combinations before shared-cell deduplication. Selection across many correlated trials is exploratory; a nominal 0.05/trial threshold is not a substitute for untouched independent validation.",'','Data limitation: the runner stored phase metrics and event logs but not daily equity paths. Therefore the requested arithmetic daily mean/std, explicit volatility drag, top-five-day concentration, and equity-zero timestamp cannot be recovered from this ledger; those fields are marked unavailable rather than estimated. Liquidation counters remain available.']
old=(ROOT/'report.md').read_text()
pointer='v3 findings are summarized below: [v3 section](#v3).\n\n'
if old.startswith(pointer): old=old[len(pointer):]
(ROOT/'report.md').write_text(pointer+old+'\n'+'\n'.join(lines))
