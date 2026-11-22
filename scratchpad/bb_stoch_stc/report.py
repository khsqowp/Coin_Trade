"""Generate an evidence-only report from pipeline CSV artifacts."""
from pathlib import Path
import pandas as pd

def generate(out='results'):
 out=Path(out); synthetic=out.name.endswith('_quick'); mode='synthetic candles (quick smoke run)' if synthetic else 'real parquet candles'; lines=['# Backtest report','',f'Results directory: `{out.name}/`. Data mode: {mode}.','']
 b=out/'stage_b.csv'; a=out/'stage_a.csv'; p=out/'stage_b_pooled.csv'; pl=out/'plateau.csv'; wf=out/'wf_summary.csv'
 stage_b_fresh=b.exists() and (not a.exists() or b.stat().st_mtime>=a.stat().st_mtime)
 lines += ['## Headline: strict all-three-on long, short, combined','']
 if stage_b_fresh:
  d=pd.read_csv(b);chosen=d[d.selected_train.astype(bool)] if 'selected_train' in d else pd.DataFrame()
  if not len(chosen) and 'headline_baseline' in d:chosen=d[d.headline_baseline.astype(bool)]
  if len(chosen):
   sel=chosen.iloc[0];d=d[(d.signal_config==sel.signal_config)&(d.params==sel.params)]
   if bool(sel.get('headline_baseline',False)): lines.append('No tuned candidate qualified; values below are the fixed diagnostic baseline (not a selected winner).')
   for side in ('long','short','combined'):
    g=d[d.side==side]
    if len(g): lines.append(f"- {side}: train trades={int(g.train_trades.sum())}, train return sum={g.train_total_return.sum():.3f}%, mean train drawdown={g.train_max_dd.mean():.3f}%; test trades={int(g.test_trades.sum())}, test return sum={g.test_total_return.sum():.3f}%, mean test drawdown={g.test_max_dd.mean():.3f}%.")
   lines += ['', '### Per-symbol winner results (train and test)', '']
   winner_rows=d[d.signal_config==sel.signal_config]
   lines.append(winner_rows.groupby(['symbol','timeframe','side'])[['train_trades','train_total_return','test_trades','test_total_return']].sum().to_string())
  else: lines.append('Stage B CSV has no headline result rows.')
 else: lines.append('Stage B is missing or older than the current Stage A artifacts; no current winner headline is available.')
 lines += ['', '## Stage A full signal grid','']
 if a.exists():
  q=pd.read_csv(a);ep=out/'stage_a_eligibility.csv'
  if len(q) and ep.exists():
   ranked=pd.read_csv(ep);ranked=ranked[ranked.eligible].copy();ranked['score']=ranked.mean_10+ranked.median_10+ranked.mean_20+ranked.median_20+ranked.win_10/100+ranked.win_20/100
   for side in ('long','short'):
    top=ranked[ranked.side==side].sort_values(['score','train_events'],ascending=False).head(10)
    lines += [f'### {side} eligible rank (train only)','',top[['signal_config','train_events','mean_10','median_10','win_10','mean_20','median_20','win_20']].to_string(index=False),'']
   lines.append('The deterministic grid keeps all three conditions required. Forward return direction is positive for long and negative price return for short. Eligibility is applied before ranking. Pooled means and win rates are event weighted; pooled median is approximated by an event weighted median of the per-series medians because event-level return arrays are not stored.')
  else: lines.append('No Stage A candidate was eligible or the eligibility artifact is missing.')
 epath=out/'stage_a_eligibility.csv'
 if epath.exists():
  e=pd.read_csv(epath);bins=pd.cut(e.train_events,[-1,0,29,149,299,10**12],labels=['0','1-29','30-149','150-299','300+']);dist=bins.value_counts(sort=False)
  lines += ['',f"Eligibility floor: at least 150 pooled training events per direction and at least 30 per timeframe; {int(e.eligible.sum())} side/configuration candidates pass out of {len(e)} recorded candidates.", 'Event-count distribution (pooled train events):', dist.to_string()]
 ab=out/'ablation.csv'
 if stage_b_fresh and ab.exists():
  q=pd.read_csv(ab);lines += ['', '## 2^3 condition ablation: events and forward simulation', '', 'Train and test are kept in separate rows; these are post-selection diagnostics for the selected parameters.', '']
  lines.append(q.groupby(['bb','stoch','stc','split'])[['events','trades','total_return']].sum().to_string())
 lines += ['', '## Selected winner: train selection and plateau','']
 if stage_b_fresh and p.exists():
  q=pd.read_csv(p);q=q[q.side=='combined'];eligible=q[q.eligible]
  lines.append(f"Eligible common parameter sets: {len(eligible)} of {len(q)}; eligibility requires at least 30 pooled train trades across symbols/timeframes.")
  if len(eligible):
   w=eligible.sort_values('robust_score',ascending=False).iloc[0];lines.append(f"Selected train-only winner: signal_config={int(w.signal_config)}, params=`{w.params}`, robust_score={w.robust_score:.4f}. It passed the pooled 30-trade Stage B floor; test metrics below use these fixed parameters and were not used for selection.")
  else: lines.append('No winner: no parameter set met the pooled 30-trade minimum.')
 if stage_b_fresh and pl.exists():
  q=pd.read_csv(pl)
  if len(q) and 'verdict' in q:
   for label,g in q.groupby('winner'):lines.append(f"{label}: {g.verdict.iloc[0]} ({g.robust_neighbor_pct.iloc[0]:.1f}% axial neighbors score at least 50% of winner).")
  else:lines.append('No plateau evaluations available.')
 lines += ['', '## Rolling walk-forward','']
 if wf.exists():
  q=pd.read_csv(wf);lines.append(q.to_string(index=False))
 else: lines.append('Walk-forward summary CSV missing.')
 lines += ['', '## Winner comparison','']
 wc=out/'winner_comparison.csv'
 if wc.exists():
  q=pd.read_csv(wc);rows=[]
  for kind,g in q.groupby('kind',sort=False):
   if not bool(g.selected.any()):continue
   r=g.iloc[0];rows.append(dict(winner=kind,signal_config=int(r.signal_config),signal_knobs=r.signal_knobs,management=r.params,train_trades=int(g.train_trades.sum()),train_return=float(g.train_return.sum()),test_trades=int(g.test_trades.sum()),test_return=float(g.test_total_return.sum()),test_vs_train_degradation=float(g.test_total_return.sum()-g.train_return.sum())))
  if rows:
   table=pd.DataFrame(rows);lines.append('| '+' | '.join(table.columns)+' |');lines.append('| '+' | '.join(['---']*len(table.columns))+' |')
   for row in table.itertuples(index=False,name=None):lines.append('| '+' | '.join(str(x).replace('|','\\|') for x in row)+' |')
  else:lines.append('No pooled candidate passed the required train trade floor.')
 else:lines.append('Winner comparison CSV missing.')
 lines += ['', '## Verdict','']
 if wc.exists():
  q=pd.read_csv(wc);base=q[q.kind=='unconstrained'];stop=q[q.kind=='with_stop']
  if len(base) and len(stop):
   tr=float(base.train_return.sum());te=float(base.test_total_return.sum());st=float(stop.test_total_return.sum());
   lines.append(f"Unconstrained selected return changed from {tr:.3f}% train to {te:.3f}% untouched test ({te-tr:+.3f} percentage points); the with-stop test return was {st:.3f}%. Treat all selected candidates as {('FRAGILE' if pl.exists() and 'FRAGILE' in pd.read_csv(pl).get('verdict',pd.Series(dtype=str)).values else 'unverified')} under the available neighbor checks.")
  else:lines.append('No selected train candidate met the comparison floor; this run establishes no positive result.')
 else:lines.append('Winner comparison evidence is missing; no numerical verdict can be computed.')
 lines.append('Walk-forward selection repeats within each train window. Aggregate returns do not model shared capital, funding, borrowing, or portfolio exposure.')
 lines += ['', '## Reproduce','', '```sh','.venv/bin/python run_all.py --stage all','.venv/bin/python run_all.py --stage all --quick','.venv/bin/python -m pytest','```','']
 path=out/'REPORT.md';path.write_text('\n'.join(lines));return path
