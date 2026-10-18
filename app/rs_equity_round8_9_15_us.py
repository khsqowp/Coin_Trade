"""US Round 8/9/15 scope inventory and explicit replayability audit.

This module never presents crypto-only families as executed US evidence. It
enumerates source-declared configs and records unavailable/incompatible inputs.
"""
from __future__ import annotations
import hashlib, importlib, json
from pathlib import Path
from app.crypto_round8_research import variants
from app.rs_equity_transfer import load_equity_panel
from app.rs_equity_round12_13_portfolio import _costs

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/research/equity_transfer_2026-10/full_runs'

def run():
    panel=load_equity_panel('US'); r8=json.loads((ROOT/'docs/round8-results-2026-10-07.json').read_text())
    reps=[]
    for i,rep in enumerate(r8['top10'],1):
        configs=[{'filter':f,'config':c} for f,c in variants(rep)]
        reps.append(dict(rank=i,family=rep['family'],representative_name=rep['name'],source_config=rep['config'],
                         source_metrics=rep['metrics'],declared_variants=len(configs),configs=configs,
                         evaluated=0,status='NOT_RUN: source configs depend on crypto signal cores/engine semantics; no equivalent US adapter validated'))
    (OUT/'round8_9_15_us.json').write_text(json.dumps(dict(market='US',symbols=panel.symbols,
      panel_dates=[str(panel.dates.min().date()),str(panel.dates.max().date())],
      source_top10_sha256=hashlib.sha256((ROOT/'docs/round8-results-2026-10-07.json').read_bytes()).hexdigest(),
      source_variants_function='app.crypto_round8_research.variants',round8=dict(representatives=reps,declared_configs=sum(x['declared_variants'] for x in reps),evaluated_configs=0,
      blockers=['No validated equity equivalents for the crypto portfolio engine filter/timing/stop semantics across these ten source families.','Ensemble source mixes independent crypto capital buckets and requires a separate equity-equivalent combined-ledger engine.']),
      round9=dict(source_config=json.loads((ROOT/'docs/round9-results-2026-10-07.json').read_text())['config'],
        source_period_cells=8,source_variants_declared=0,us_replays=0,
        blockers=['Round9 source-selected TOP_K12 candidate must be resolved from the full source Round8 experiment table; checked-in Round8 result contains only 3 experiments and none establishes that selection.','No source-defined breaker mapping to US was validated for the fixed candidate.']),
      round15=dict(source_counts=json.loads((ROOT/'docs/round15-results-2026-10-07.json').read_text())['counts'],
        source_total_unique=json.loads((ROOT/'docs/round15-results-2026-10-07.json').read_text())['total_unique'],
        source_checks=json.loads((ROOT/'docs/round15-results-2026-10-07.json').read_text())['checks'],
        us_hypothesis_test_count=0,us_recomputed_p=None,
        raw_us_trials_available=False,
        omissions=['Original 300-control input/trial vector and full per-hypothesis p-value table are absent from Round15 artifact.','No crypto p-value copied or interpreted as US evidence.']),
      environment=dict(cost_cases=[c[0] for c in _costs(panel)],daily_symbols=len(panel.symbols)),
      status='inventory_only_for_round8_9_15'),ensure_ascii=False,indent=2,allow_nan=False))
    print('ROUND8_DECLARED',sum(x['declared_variants'] for x in reps),'EVALUATED',0,'ROUND9_REPLAYS',0,'ROUND15_US_TESTS',0)
if __name__=='__main__':run()
