"""Evaluate registered KR-daily-v2 hypotheses/gates and write the final markdown report."""
import json, datetime, math
from pathlib import Path
import numpy as np
import bt2

KR = Path('/app/kr')
V1 = Path('/app/v1')
MAIN = json.loads((KR / 'results_main.json').read_text())
SENS = json.loads((KR / 'results_sens.json').read_text())
ROB = json.loads((KR / 'results_robust.json').read_text())
NULL = json.loads((KR / 'results_null.json').read_text())
R = MAIN['results']
PICK = MAIN['is_pick']
B1, B4, B5 = 'B1_BH_069500', 'B4_EW_U500', 'B5_EW_ALL_ELIG'
VTRIALS = [k for k in R if k.startswith('V')]
p = R[PICK]  # alias for the IS-pick result dict; used by the capacity line before its later reassignment (harmless no-op there)


def fnum(x, digits=3):
    if x is None: return 'n/a'
    try:
        if not math.isfinite(float(x)): return 'n/a'
    except (TypeError, ValueError): return 'n/a'
    return f'{float(x):.{digits}f}'


def pct(x, digits=1):
    return 'n/a' if x is None else f'{float(x)*100:.{digits}f}%'


def verdict(ok): return 'PASS' if ok else 'FAIL'


def sharpe_gate(name):
    d = R[name]
    rt = d['regime_types']
    regime_ok = sum(rt[t]['strat'].get('sharpe', -999) > 0 for t in ('bull','bear','chop')) >= 2 and rt['bear']['strat'].get('total_return', -999) > rt['bear']['B1'].get('total_return', 999)
    robust_full = ROB.get(name, {}).get('FULL', {}).get('sharpe', -999)
    slip = SENS.get('slip_x2', {}).get(name, {}).get('OOS', {}).get('sharpe', -999)
    b4full = R[B4]['FULL'].get('sharpe', 999)
    return {
      'a': d['OOS'].get('sharpe', -999) >= .5,
      'b': d['OOS'].get('sharpe', -999) >= R[B1]['OOS'].get('sharpe', 999) and d['OOS'].get('sharpe', -999) >= R[B4]['OOS'].get('sharpe', 999),
      'c': d['FULL'].get('dsr_N17', -999) >= .90 and d['FULL'].get('dsr_N233', -999) >= .80,
      'd': d['FULL'].get('mdd', 999) <= .35,
      'e': regime_ok,
      'f': slip >= .4 and robust_full >= b4full,
      'g': d.get('participation_100M_p95', 999) <= .05,
    }

GATES = sharpe_gate(PICK)
OVERALL = all(GATES.values())
all_trial_gates = {k: sharpe_gate(k) for k in VTRIALS}
any_trial_pass = any(all(g.values()) for g in all_trial_gates.values())
H = {}
# Registered hypothesis statements are applied literally; support means the stated directional prediction occurred.
H['H1'] = (R['V1_XS_MOM12_1']['OOS']['sharpe'] <= R[B4]['OOS']['sharpe'], f"V1 OOS Sharpe {fnum(R['V1_XS_MOM12_1']['OOS']['sharpe'])} vs B4 {fnum(R[B4]['OOS']['sharpe'])}.")
H2v, H2b = R['V5_XS_LOWVOL'], R[B4]
H['H2'] = (all(H2v[s]['mdd'] < H2b[s]['mdd'] and H2v[s]['sharpe'] >= H2b[s]['sharpe'] for s in ('IS','OOS')), f"IS MDD/Sharpe {pct(H2v['IS']['mdd'])}/{fnum(H2v['IS']['sharpe'])} vs B4 {pct(H2b['IS']['mdd'])}/{fnum(H2b['IS']['sharpe'])}; OOS {pct(H2v['OOS']['mdd'])}/{fnum(H2v['OOS']['sharpe'])} vs {pct(H2b['OOS']['mdd'])}/{fnum(H2b['OOS']['sharpe'])}.")
H['H3'] = (R['V8_EV_VOLSPIKE20']['OOS']['sharpe'] <= R[B4]['OOS']['sharpe'], f"V8 OOS Sharpe {fnum(R['V8_EV_VOLSPIKE20']['OOS']['sharpe'])} vs B4 {fnum(R[B4]['OOS']['sharpe'])}.")
H4 = R['V9_XS_STREV_W']
H['H4'] = (H4['IS']['total_return'] < 0 and H4['OOS']['total_return'] < 0, f"V9 IS total return {pct(H4['IS']['total_return'])}; OOS {pct(H4['OOS']['total_return'])}.")
H['H5'] = (R['V7_TS_DONCHIAN_70_25']['regime_types']['chop']['strat']['sharpe'] < R[B4]['regime_types']['chop']['strat']['sharpe'], f"V7 chop Sharpe {fnum(R['V7_TS_DONCHIAN_70_25']['regime_types']['chop']['strat']['sharpe'])} vs B4 {fnum(R[B4]['regime_types']['chop']['strat']['sharpe'])}.")
H6v = R['V3_XS_MOM60_REPL']
H['H6'] = (H6v['PRE2018']['sharpe'] < H6v['POST2018']['sharpe'], f"V3 PRE2018 Sharpe {fnum(H6v['PRE2018']['sharpe'])}; POST2018 {fnum(H6v['POST2018']['sharpe'])}.")
H['H7'] = (not any_trial_pass, 'No trial evaluated against the registered gate criteria (a)-(g) passes.' if not any_trial_pass else 'At least one trial would satisfy all gate items in a diagnostic check; only the IS pick is eligible under the registered selection rule.')

# Coverage / QC evidence assembled from immutable fetch outputs plus the completed engine run.
fetch_rows=[]
for line in (KR/'fetch_log.jsonl').read_text().splitlines():
    try: fetch_rows.append(json.loads(line))
    except Exception: pass
unique={str(x.get('code')) for x in fetch_rows if x.get('code')}
target=3240
listed_keys={str(x.get('code')) for x in fetch_rows if x.get('code') and x.get('status')=='listed'}
delisted_keys={str(x.get('code')) for x in fetch_rows if x.get('code') and x.get('status')=='delisted'}
listed=len(listed_keys); delisted=len(delisted_keys)
fetch_complete=len(unique)>=target
errors=sum(1 for x in fetch_rows if x.get('error'))
data_files=len(list((KR/'data').glob('*.parquet')))
trigger_path=KR/'FETCH_TRIGGER.marker'
trigger_info={}
if trigger_path.exists():
    for line in trigger_path.read_text().splitlines():
        if '=' in line:
            k,v=line.split('=',1); trigger_info[k]=v
fetch_complete=trigger_info.get('trigger')=='fetch_complete'
order_progress=trigger_info.get('order_positions_traversed','unknown/3240')
snapshot_parquet=int(trigger_info.get('parquet_snapshot',data_files))
snapshot_none=int(trigger_info.get('no_row_snapshot',0))
qc_logs=sorted(KR.glob('stage_qc2_*.log'))
qc_path=qc_logs[-1] if qc_logs else None  # Use the resumed QC run, not the earlier failed attempt.
qc_text=qc_path.read_text(errors='replace') if qc_path else 'QC stage log unavailable.'
now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
# Calculate the requested pick capacity checks at 10M and 1bn; the main engine already
# stores all-trial participation at 100M using this identical simulator.
Pcap = bt2.load_panel(); Fcap = bt2.feats(Pcap)
sigcap, modecap = bt2.trials_build(Pcap, Fcap)[PICK]
capacity = {}
for capital in (1e7, 1e9):
    _, excap = bt2.simulate(Pcap, sigcap, mode=modecap, capital=capital)
    parts = np.asarray(excap['parts'], float) if excap['parts'] else np.asarray([0.0])
    capacity[str(int(capital))] = {'p95': float(np.percentile(parts, 95)), 'max': float(parts.max())}

lines=[]
def add(s=''): lines.append(s)
add('# KR-daily-v2: full-universe Korean equities daily-bar research report')
add(); add(f'Generated {now}. Research only: no orders, no forward registration, and no strategy promotion beyond the registered IS-pick rule.')
add(); add('## Bottom line')
add(); add(f"**Overall pre-registered gate: {verdict(OVERALL)}. IS pick: `{PICK}`.** The selection is mechanical (highest IS Sharpe among V1-V9); a failed gate means no strategy advances. OOS Sharpe is {fnum(R[PICK]['OOS']['sharpe'])}, versus B1 {fnum(R[B1]['OOS']['sharpe'])} and B4 {fnum(R[B4]['OOS']['sharpe'])}; FULL DSR is {fnum(R[PICK]['FULL'].get('dsr_N17'))} at N=17 and {fnum(R[PICK]['FULL'].get('dsr_N233'))} at N=233. The post-hoc A3 random-portfolio results are diagnostic only and do not change this gate.")
add(); add('## 1. Registration, disclosure, and contamination')
add(); add('- Main protocol: `PREREG_kr_daily_v2.md`, written before v2 price data opened; A1 fixes the corporate-action/delisting repair rule; A2 merges market-transfer pairs and splits terminal delisting/re-listing spells.')
add('- The owner disclosed prior exposure to KR-daily-v1 index history/results, a prior KR stock-rule study, and a large crypto strategy catalog. V2 OOS is new only for the specified cross-sectional rules; the market path is contaminated by prior observation.')
add('- A3 is explicitly post-hoc, added because the main KR v2 registration omitted a random-portfolio null and per-trial p-value corrections that were used in US v2. It has selection count 0, is reported separately, and cannot override registered hypotheses or gates.')
add('- QC/reporting fixes during execution: qc2.py failed because Addendum A2 market-transfer codes have duplicate listed/delisted rows; its status lookup now gives listed precedence. qc2.py only prints diagnostics, so this has no effect on backtest results. gate_report_v2.py also evaluated coverage against target before assigning it; the assignment was moved before use. The report also selects the newest QC stage log so it cites the successful rerun. These reporting fixes do not change engine calculations, methodology, or registered thresholds.')
add('- No threshold, lookback, cost, universe rule, split, or gate was changed after registration. The only methodology addition is the separately labeled A3 diagnostic.')
add(); add('## 2. Coverage and data QC')
add(); add(f'- Universe target: {target:,} segmented instruments (2,588 listed + 652 terminally delisted). Fetch log has {len(unique):,} unique instrument keys ({listed:,} listed-status records, {delisted:,} delisted-status records, {errors:,} logged errors); data directory has {data_files:,} parquet files. Panel loaded by the engine: {MAIN["coverage"].get("codes_with_data", "n/a")} names, including {MAIN["coverage"].get("delisted_in_panel", "n/a")} delisted histories.')
add(f"- Fetch outcome: {'all target instruments logged before the deadline' if fetch_complete else f'fixed deadline/early-stop coverage {len(unique):,}/{target:,}; analysis uses the fetched-so-far subset'}; no backfill is performed.")
add('- A1 repair statistics from the strategy panel: '+json.dumps(MAIN['coverage'].get('repairs', {}), ensure_ascii=False))
add('- QC stage output:')
add('```text'); add(qc_text.rstrip()); add('```')
add(); add('## 3. Rules, windows, and execution')
add(); add('The nine fixed V-trials, point-in-time U500/eligibility rules, B1 (KODEX 200 buy-and-hold), B4 (monthly equal-weight U500), B5 (monthly equal-weight all eligible), execution deferrals, slippage tiers, 0.015% commission, 0.20% sell tax, and cash handling follow the main registration and A1/A2. IS is 2012-06-01 through 2019-12-31; OOS is 2020-01-01 through 2026-11-03; FULL is the registered evaluation window.')
add(); add('## 4. IS/OOS/FULL results')
add(); add('| Strategy | IS Sharpe | IS return | IS MDD | OOS Sharpe | OOS return | OOS MDD | FULL Sharpe | FULL CAGR | FULL MDD | DSR N17 | DSR N233 | DSR N1000 | round trips | cost/year | top-10 P&L share |')
add('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for k in VTRIALS+[B1,B4,B5]:
    d=R[k]; I,O,F=d['IS'],d['OOS'],d['FULL']
    add(f"| {k} | {fnum(I.get('sharpe'))} | {pct(I.get('total_return'))} | {pct(I.get('mdd'))} | {fnum(O.get('sharpe'))} | {pct(O.get('total_return'))} | {pct(O.get('mdd'))} | {fnum(F.get('sharpe'))} | {pct(F.get('cagr'))} | {pct(F.get('mdd'))} | {fnum(F.get('dsr_N17'))} | {fnum(F.get('dsr_N233'))} | {fnum(F.get('dsr_N1000'))} | {d.get('round_trips','—')} | {pct(d.get('cost_drag_per_yr'))} | {pct(d.get('top10_pnl_share'))} |")
add(); add(f"**IS pick:** `{PICK}` with IS Sharpe {fnum(R[PICK]['IS'].get('sharpe'))}. Its OOS excess-return 90% block-bootstrap intervals are B1 {R[PICK].get('oos_excess_vs_B1_ci90_ann')} annualized and B4 {R[PICK].get('oos_excess_vs_B4_ci90_ann')} annualized.")
add(); add('## 5. Regime-window breakdown')
add(); add('| Strategy | Window | Type | Dates | Strategy return | B1 return | Strategy Sharpe | B1 Sharpe |')
add('|---|---|---|---|---:|---:|---:|---:|')
for k in VTRIALS+[B1,B4,B5]:
    for w in R[k].get('regimes',[]):
        sr=w['strat']; br=w['B1']
        add(f"| {k} | {w['label']} | {w['type']} | {w['start']}..{w['end']} | {pct(sr.get('total_return'))} | {pct(br.get('total_return'))} | {fnum(sr.get('sharpe'))} | {fnum(br.get('sharpe'))} |")
add(); add('**Aggregated regime types (Sharpe / total return):**')
add(); add('| Strategy | Bull | Bear | Chop |')
add('|---|---|---|---|')
for k in VTRIALS+[B1,B4,B5]:
    t=R[k].get('regime_types',{})
    def rt(x):
        q=t.get(x,{}).get('strat',{}); return f"{fnum(q.get('sharpe'))} / {pct(q.get('total_return'))}"
    add(f'| {k} | {rt("bull")} | {rt("bear")} | {rt("chop")} |')
add(); add('## 6. Sensitivity and robustness results')
add(); add('| Scenario | Trial | IS Sharpe | OOS Sharpe | FULL Sharpe |')
add('|---|---|---:|---:|---:|')
for sn, label in [('slip_x2','Slippage x2'),('tax_0.30','Sell tax 0.30%')]:
    for k,d in SENS.get(sn,{}).items():
        add(f"| {label} | {k} | {fnum(d.get('IS',{}).get('sharpe'))} | {fnum(d.get('OOS',{}).get('sharpe'))} | {fnum(d.get('FULL',{}).get('sharpe'))} |")
for k,d in SENS.get('phase_plus5',{}).items():
    add(f"| Rebalance phase +5 | {k} | {fnum(d.get('IS',{}).get('sharpe'))} | {fnum(d.get('OOS',{}).get('sharpe'))} | {fnum(d.get('FULL',{}).get('sharpe'))} |")
for k,d in SENS.get('unrepaired_data_pick',{}).items():
    add(f"| Unrepaired data (IS pick) | {k} | {fnum(d.get('IS',{}).get('sharpe'))} | {fnum(d.get('OOS',{}).get('sharpe'))} | {fnum(d.get('FULL',{}).get('sharpe'))} |")
add(); add('**Capacity/participation at 10M, 100M, and 1bn KRW:**')
add(); add('| Trial | 100M p95 participation / median traded value | 100M max | 10M/1bn values |')
add('|---|---:|---:|---|')
for k in VTRIALS:
    d=R[k]
    add(f"| {k} | {pct(d.get('participation_100M_p95'))} | {pct(d.get('participation_100M_max'))} | See IS-pick capacity row below for 10M and 1bn. |")
add()
add(f"**IS-pick capacity at 10M / 100M / 1bn KRW (95th-percentile participation / max):** {PICK}: {pct(capacity['10000000']['p95'])} / {pct(p.get('participation_100M_p95'))} / {pct(capacity['1000000000']['p95'])}; max {pct(capacity['10000000']['max'])} / {pct(p.get('participation_100M_max'))} / {pct(capacity['1000000000']['max'])}. Gate (g) uses only the registered 100M p95 value.")
add(); add('**Top-10-contributor-removed rerun:**')
add(); add('| Trial | Removed instruments | IS Sharpe | OOS Sharpe | FULL Sharpe |')
add('|---|---|---:|---:|---:|')
for k in VTRIALS:
    d=ROB.get(k,{})
    add(f"| {k} | {', '.join(d.get('dropped',[]))} | {fnum(d.get('IS',{}).get('sharpe'))} | {fnum(d.get('OOS',{}).get('sharpe'))} | {fnum(d.get('FULL',{}).get('sharpe'))} |")
add(); add('## 7. Post-hoc Addendum A3 random-portfolio null')
add(); add('This is a diagnostic added after registration; selection count = 0. Statistic: annualized Sharpe of daily strategy returns minus B1 daily returns. Each null draw matches eligible pool, rebalance/event dates, target constituent counts/weights, cash decisions, slot timing, and `bt2.simulate` costs. P-values use `(1 + #null >= observed)/(1 + draws)`. Bonferroni and BH q-values cover the nine OOS trials.')
add(); add('| Trial | Draws | IS active Sharpe | IS p | OOS active Sharpe | OOS p | Bonferroni p | BH q | Null OOS median | Null OOS p95 |')
add('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for k in VTRIALS:
    d=NULL['trials'][k]
    add(f"| {k} | {d['draws']} | {fnum(d['real_active_sharpe'].get('IS'))} | {fnum(d['p'].get('IS'),4)} | {fnum(d['real_active_sharpe'].get('OOS'))} | {fnum(d['p'].get('OOS'),4)} | {fnum(d.get('bonferroni_OOS'),4)} | {fnum(d.get('bh_q_OOS'),4)} | {fnum(d['null_median'].get('OOS'))} | {fnum(d['null_p95'].get('OOS'))} |")
add(); add('These p-values and corrections do not enter gates (a)-(g), the IS selection, or the final registered PASS/FAIL.')
add(); add('## 8. Hypotheses H1-H7')
add(); add('| Hypothesis | Verdict | Evidence |')
add('|---|---|---|')
for k,(ok,detail) in H.items(): add(f'| {k} | **{"SUPPORTED" if ok else "REJECTED"}** | {detail} |')
add(); add('H7 evaluates whether any V trial would satisfy all seven numerical gate conditions as a diagnostic; only the IS pick is eligible for the actual registered gate and no alternative trial is promoted.')
add(); add('## 9. Pre-registered gate for the IS pick')
add(); add('| Item | Registered criterion | Observed value | Verdict |')
add('|---|---|---|---|')
p=R[PICK]
add(f"| (a) | OOS Sharpe >= 0.5 | {fnum(p['OOS'].get('sharpe'))} | **{verdict(GATES['a'])}** |")
add(f"| (b) | OOS Sharpe >= both B1 and B4 | pick {fnum(p['OOS'].get('sharpe'))}; B1 {fnum(R[B1]['OOS'].get('sharpe'))}; B4 {fnum(R[B4]['OOS'].get('sharpe'))} | **{verdict(GATES['b'])}** |")
add(f"| (c) | FULL DSR N=17 >= 0.90 and N=233 >= 0.80 | {fnum(p['FULL'].get('dsr_N17'))}; {fnum(p['FULL'].get('dsr_N233'))} | **{verdict(GATES['c'])}** |")
add(f"| (d) | FULL MDD <= 35% | {pct(p['FULL'].get('mdd'))} | **{verdict(GATES['d'])}** |")
rt=p['regime_types']; npos=sum(rt[x]['strat'].get('sharpe',-999)>0 for x in ('bull','bear','chop'))
add(f"| (e) | Sharpe > 0 in at least 2/3 regime types and bear return > B1 bear return | positive Sharpe types {npos}/3; bear {pct(rt['bear']['strat'].get('total_return'))} vs B1 {pct(rt['bear']['B1'].get('total_return'))} | **{verdict(GATES['e'])}** |")
add(f"| (f) | Slippage-x2 OOS Sharpe >= 0.4 and top-10-removed FULL Sharpe >= B4 FULL Sharpe | slip-x2 {fnum(SENS.get('slip_x2',{}).get(PICK,{}).get('OOS',{}).get('sharpe'))}; robust {fnum(ROB.get(PICK,{}).get('FULL',{}).get('sharpe'))}; B4 {fnum(R[B4]['FULL'].get('sharpe'))} | **{verdict(GATES['f'])}** |")
add(f"| (g) | 100M KRW 95th percentile participation <= 5% of median traded value | {pct(p.get('participation_100M_p95'))} | **{verdict(GATES['g'])}** |")
add(); add(f'**Overall registered gate: {verdict(OVERALL)}.** No alternative IS trial is promoted if the pick fails.')
add(); add('## 10. Limitations and interpretation')
add(); add('- Prices and traded values come from the KIS paper quotation path. Dividends are excluded; KIS data quality and corporate-action repair uncertainty remain relevant.')
add('- The fetch may stop at its fixed deadline with less than the 3,240 target. The random fetch order makes that subset pre-specified, but smaller coverage reduces breadth and power; the exact realized coverage above governs this report.')
add('- Market-path contamination is explicit: the researcher had already seen index history and prior-round results. DSR at N=233 and N=1000 is a sensitivity, not a complete count of all historical research choices.')
add('- The random-portfolio test is post-hoc and schedule-matched. It is not evidence of prospective performance and does not rescue a failed registered gate.')
add(); add('## 11. What was touched')
add(); add('- Files written under `research/kr_daily_v2/`: A3 addendum and timestamp, `null_test_v2.py`, `gate_report_v2.py`, orchestration script, timestamped stage logs, result JSONs, report, and completion/failure marker as applicable.')
add('- Containers: only hardened disposable `tp-pipeline:local` offline analysis containers are launched by the orchestration script. The dedicated `kr2fetch` container is observed only; no other running service is stopped, restarted, or modified.')
add('- No secrets file was read, printed, or modified. The analysis containers use `--network none`. No git add, commit, or push is performed.')
add(); add('## Reproduction artifacts')
add(); add('`results_main.json`, `results_sens.json`, `results_robust.json`, `results_null.json`, `qc2` stage log, `fetch_log.jsonl`, and `PIPELINE_DONE.marker` (if successful).')
(KR/'REPORT_kr_daily_v2.md').write_text('\n'.join(lines)+'\n')
print('WROTE REPORT_kr_daily_v2.md; pick=%s overall=%s' % (PICK, verdict(OVERALL)), flush=True)
