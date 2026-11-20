"""Build the auditable report and compact B3/B4 surface artifact from the run ledger."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
with (ROOT / 'results/group_b.csv').open() as f:
    rows = list(csv.DictReader(f))
candidates = list(dict.fromkeys(r['candidate'] for r in rows if r['scenario'] == 'FINAL'))

def b3_edge_monotone(cid):
    surf=[r for r in rows if r['candidate']==cid and r['scenario']=='B3' and r['status']=='DONE']
    axes=sorted({k for r in surf for k in json.loads(r.get('params') or '{}')})
    for axis in axes:
        scores={}
        for r in surf:
            p=json.loads(r.get('params') or '{}')
            if axis in p:
                x=float(p[axis]); scores[x]=scores.get(x,0.0)+float(r.get('train_return_pct') or 0)
        xs=sorted(scores); vals=[scores[x] for x in xs]
        if len(xs)<2: continue
        best=max(xs,key=lambda x:scores[x])
        if best==xs[0] and all(vals[i]>=vals[i+1] for i in range(len(vals)-1)): return True
        if best==xs[-1] and all(vals[i]<=vals[i+1] for i in range(len(vals)-1)): return True
    return False

# Re-adjudicate B3 using its registered edge-plus-monotonicity rule, then keep the
# machine-readable FINAL rows aligned with the surface-derived verdict.
for cid in candidates:
    final=next(r for r in rows if r['candidate']==cid and r['scenario']=='FINAL')
    fails=final.get('tag','').removeprefix('DOWNGRADED(').removesuffix(')').split(',') if final.get('tag','').startswith('DOWNGRADED(') else []
    selected=next((r for r in rows if r['candidate']==cid and r['scenario']=='B3' and r['status']=='DONE' and r.get('selected_train','').lower()=='true'),{})
    b3fail=b3_edge_monotone(cid) or (selected and float(selected.get('test_return_pct') or 0)<=0)
    fails=[x for x in fails if x!='B3']
    if b3fail: fails.append('B3')
    yearly=[r for r in rows if r['candidate']==cid and r['scenario']=='B5' and r.get('basket_sharpe')]
    b5fail=bool(yearly) and sum(float(r['basket_sharpe'])<=float(r['btc_sharpe']) for r in yearly)>len(yearly)/2
    fails=[x for x in fails if x!='B5']
    if b5fail: fails.append('B5')
    final['tag']='PASS_ALL' if not fails else 'DOWNGRADED('+','.join(x for x in ['B1','B2','B3','B4','B5','B6'] if x in fails)+')'
with (ROOT / 'results/group_b.csv').open('w', newline='') as f:
    cols=sorted({k for r in rows for k in r})
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(rows)
with (ROOT / 'results/b3_surfaces.csv').open('w', newline='') as f:
    surface = [r for r in rows if r['scenario'] == 'B3' and r['status'] == 'DONE']
    cols = sorted({k for r in surface for k in r})
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(surface)

def get(cid, sc, **filters):
    return next((r for r in rows if r['candidate'] == cid and r['scenario'] == sc and all(r.get(k) == v for k, v in filters.items())), {})

years = sorted({int(r['window']) for r in rows if r['scenario'] == 'B1' and r.get('window', '').isdigit()})
out = ['# Group B third-pass re-evaluation', '', 'Final tags follow `verify2/SCENARIOS.md`. Frozen settings are used for B1, B2, B5, and B6. B3/B4 use the extended grid for diagnostic selection only.', '', '| Candidate | B1 | B2 | B3 | B4 | B5 | B6 | Final tag |', '|---|---|---|---|---|---|---|---|']
for cid in candidates:
    final = get(cid, 'FINAL').get('tag', 'UNKNOWN')
    fail = final[11:-1].split(',') if final.startswith('DOWNGRADED(') else []
    vals=[]
    for sc in ['B1','B2','B3','B4','B5','B6']:
        applicable = sc != 'B6' or cid == 'jesse_simple_bollinger'
        vals.append(('FAIL' if sc in fail else 'PASS') if applicable else 'N/A')
    out.append(f"| `{cid}` | {' | '.join(vals)} | **{final}** |")

out += ['', '## Scenario verdict evidence', '', '| Candidate | B1 negative years / years; stress 2018, 2022 | B2 positive / available (strict / 5) | B3 selected TEST; edge-monotone | B4 WF / frozen | B5 years Sharpe <= BTC | B6 agreement; test-return signs |', '|---|---|---|---|---:|---:|---|']
for cid in candidates:
    b1=[r for r in rows if r['candidate']==cid and r['scenario']=='B1' and r.get('symbol')=='POOLED' and r.get('window','').isdigit()]
    neg=sum(float(r.get('return_pct') or 0)<0 for r in b1)
    stress=[]
    for y in ['stress2018','stress2022']:
        r=get(cid,'B1',symbol='POOLED',window=y); stress.append(f"{float(r.get('return_pct') or 0):.2f}")
    b2=next((r for r in rows if r['candidate']==cid and r['scenario']=='B2' and r['status']=='RULE'),{})
    chosen=next((r for r in rows if r['candidate']==cid and r['scenario']=='B3' and r['status']=='DONE' and r.get('selected_train','').lower()=='true'),{})
    b4=get(cid,'B4',status='DONE')
    b5=[r for r in rows if r['candidate']==cid and r['scenario']=='B5' and r.get('basket_sharpe')]
    b5n=sum(float(r['basket_sharpe'])<=float(r['btc_sharpe']) for r in b5)
    b6=get(cid,'B6',status='PASS') or get(cid,'B6',status='FAIL')
    b6proof=f"{b6.get('agreement_pct','N/A')}%; {b6.get('forward_result_pct','N/A')} vs {b6.get('backward_result_pct','N/A')}" if b6 else 'N/A'
    out.append(f"| `{cid}` | {neg}/{len(b1)}; {stress[0]}, {stress[1]} | {b2.get('available_positive','N/A')} ({b2.get('strict_five_positive','N/A')}) | {chosen.get('test_return_pct','N/A')}; {'yes' if b3_edge_monotone(cid) else 'no'} | {b4.get('ratio','N/A')} | {b5n}/{len(b5)} | {b6proof} |")

out += ['', '## B1: calendar-year and stress-window returns', '', 'Harness trade returns are attributed by exit year and summed in percentage points. A year absent from the ledger had no closed trades.', '', '| Candidate | ' + ' | '.join(map(str, years)) + ' | 2018 stress | 2022 stress |', '|---|' + '|'.join(['---:'] * (len(years)+2)) + '|']
for cid in candidates:
    vals=[]
    for y in years + ['stress2018','stress2022']:
        r=get(cid,'B1',symbol='POOLED',window=str(y)); vals.append(f"{float(r.get('return_pct') or 0):.2f}")
    out.append(f"| `{cid}` | {' | '.join(vals)} |")

out += ['', '## B2: untouched symbols', '', 'Untouched symbols present in the cache directory are ADA, DOGE, LINK, LTC, and AVAX. The daily candidates use cached 1h bars resampled to daily. The result uses the available-symbols threshold (at least 60% positive); strict denominator is always five and missing symbols are explicitly flagged.', '', '| Candidate | ADA | DOGE | LINK | LTC | AVAX | Available positive | Strict five positive |', '|---|---:|---:|---:|---:|---:|---|---|']
for cid in candidates:
    vals=[]
    for s in ['ADAUSDT','DOGEUSDT','LINKUSDT','LTCUSDT','AVAXUSDT']:
        r=get(cid,'B2',symbol=s,status='DONE'); vals.append(f"{float(r.get('return_pct')):.2f}" if r else 'MISSING')
    rule=next((r for r in rows if r['candidate']==cid and r['scenario']=='B2' and r['status']=='RULE'),{})
    out.append(f"| `{cid}` | {' | '.join(vals)} | {rule.get('available_positive','0/0')} | {rule.get('strict_five_positive','0/5')} |")

out += ['', '## B3/B4: parameter-surface summary', '', 'Full per-symbol, per-parameter TRAIN/TEST values are in [`results/b3_surfaces.csv`](results/b3_surfaces.csv); raw observations are in [`results/group_b.csv`](results/group_b.csv). Numeric axes extend two original-grid steps in both directions. B3 selects the pooled TRAIN maximum; inspect the full surface for edge and monotonicity by axis.', '', '| Candidate | TRAIN maximum | TEST at selection | Selected parameters | Walk-forward / frozen TEST |', '|---|---:|---:|---|---:|']
for cid in candidates:
    surf=[r for r in rows if r['candidate']==cid and r['scenario']=='B3' and r['status']=='DONE']
    chosen=next((r for r in surf if r.get('selected_train','').lower()=='true'),{})
    wf=get(cid,'B4',status='DONE')
    out.append(f"| `{cid}` | {chosen.get('train_return_pct','NA')} | {chosen.get('test_return_pct','NA')} | `{chosen.get('params','NA')}` | {wf.get('ratio','NA')} |")

out += ['', 'Per-axis boundary analysis uses the pooled TRAIN return at each grid value, summed across symbols and all other parameter combinations. `Edge` means the selected maximum is at either newly added boundary. `Monotone` means pooled TRAIN return improves at every adjacent step toward that boundary.', '', '| Candidate | Axis | New grid min–max | Optimum | Edge | Monotone toward edge |', '|---|---|---:|---:|---|---|']
for cid in candidates:
    surf=[r for r in rows if r['candidate']==cid and r['scenario']=='B3' and r['status']=='DONE']
    if not surf:
        out.append(f'| `{cid}` | unavailable | N/A | N/A | N/A | N/A |'); continue
    axes=sorted({k for r in surf for k in json.loads(r.get('params') or '{}')})
    for axis in axes:
        scores={}
        for r in surf:
            p=json.loads(r.get('params') or '{}')
            if axis in p: scores.setdefault(float(p[axis]),0.0); scores[float(p[axis])]+=float(r.get('train_return_pct') or 0)
        xs=sorted(scores)
        if not xs: continue
        best=max(xs,key=lambda x:scores[x]); edge=best in (xs[0],xs[-1])
        vals=[scores[x] for x in xs]
        mono=all(vals[i]<=vals[i+1] for i in range(len(vals)-1)) if best==xs[-1] else (all(vals[i]>=vals[i+1] for i in range(len(vals)-1)) if best==xs[0] else False)
        out.append(f'| `{cid}` | `{axis}` | {xs[0]:g}–{xs[-1]:g} | {best:g} | {"yes" if edge else "no"} | {"yes" if edge and mono else "no"} |')

out += ['', '## B5: daily basket versus buy-and-hold', '', 'Basket daily return is equal-weighted across the four daily strategies; each strategy is equal-weighted across available symbols. Returns are marked to market using harness trade entry/exit intervals. Sharpe is annualized with √365. Failure is basket Sharpe less than or equal to BTC buy-and-hold Sharpe in more than half the years.', '', '| Candidate | Year | Basket return % | Basket Sharpe | BTC B&H Sharpe | 5-coin B&H Sharpe |', '|---|---:|---:|---:|---:|---:|']
for cid in candidates:
    if cid not in {'btc-macd-15-41-12','turtle-system-2','btc-bollinger-37-16','btc-roc-36-9pct'}:
        continue
    for r in rows:
        if r['candidate']==cid and r['scenario']=='B5':
            out.append(f"| `{cid}` | {r['window']} | {r.get('basket_return_pct')} | {r.get('basket_sharpe')} | {r.get('btc_sharpe')} | {r.get('five_coin_sharpe')} |")

b6=get('jesse_simple_bollinger','B6')
out += ['', '## B6: Jesse source convention', '', 'Source files read: `/private/tmp/claude-501/-Users-user-CODE-Ochestration/ee6baff2-9664-4b9e-9a9e-5f263219aa7c/scratchpad/jesse_old/ichimoku_old.py`, `.../scratchpad/jesse_ex/SimpleBollinger/__init__.py`, and `/private/tmp/claude-501/-Users-user-CODE-Ochestration/ee6baff2-9664-4b9e-9a9e-5f263219aa7c/scratchpad/ichimoku_cloud.py`. Jesse-old uses `candles[:-(displacement-1)]`; default displacement 26 computes cloud from 25 bars earlier, including conversion/base windows ending at that earlier bar. Candle layout is `[ts, open, close, high, low, volume]`. Agreement is calculated over the full long 1h history and the chronological final 40% TEST window. Shift 0 is a reference.', '', '| Window | Shift-26 vs shift-25 agreement | Shift-26 vs shift-0 agreement |', '|---|---:|---:|', f"| Full long 1h | {b6.get('agreement_pct','NA')}% | {b6.get('shift0_agreement_pct','NA')}% |", f"| TEST | {b6.get('test_agreement_pct','NA')}% | {b6.get('shift0_test_agreement_pct','NA')}% |", '', f"TEST return under shift 26: {b6.get('forward_result_pct','NA')}%; under shift 25: {b6.get('backward_result_pct','NA')}%. Direct-port cloud max absolute error against vectorized shift 25: {b6.get('direct_cloud_max_abs_error','NA')}.", '', 'Jesse SimpleBollinger uses Bollinger defaults source=hl2, period=20, devup/devdn=2, SMA, and TA-Lib standard deviation ddof=0. `common.indicators.bollinger` is a separate local implementation; equivalence is not assumed. The current wrapper delegates to closed `jesse_rust`; its internal semantics remain unverifiable. A pytest directly ports Jesse-old and compares rolling 80-candle output with the shift-25 vectorized series.', '', '## Data coverage and limitations', '', '- B1 long data begins 2017-08 for BTC/ETH, 2017-11 for BNB, and 2018-05 for XRP. Long 15m data exists only for BTC and ETH.', '- Cached rows after long-data endpoints are appended in memory only. Long parquet files are not modified.', '- B2 flags the available-symbols rule when fewer than five symbols are evaluated; strict-five result remains shown separately.', '- B3/B4 use expanded grids and are diagnostics, not updates to frozen settings. The full CSV records every per-symbol TRAIN/TEST point and the report states edge and monotonicity by axis.', '- B5’s 5-coin benchmark is equal-weighted across symbols available on each date.', '- No network access was used. `results/group_b.csv` contains observations and final tags.']
(ROOT/'REPORT.md').write_text('\n'.join(out)+'\n')
