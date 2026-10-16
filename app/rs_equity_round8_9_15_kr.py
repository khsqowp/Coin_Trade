"""KR evidence inventory for crypto Rounds 8/9/15.

This module deliberately does not convert crypto p-values or pretend that
crypto signal definitions are native KR strategies. It snapshots declared
search denominators and the exact source-selected representatives.
"""
import ast, hashlib, json
from pathlib import Path
from app import rs_kr_data as D

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/research/equity_transfer_2026-10/full_runs/round8_9_15_kr.json'
SOURCES=['docs/round8-results-2026-10-07.json','docs/round9-results-2026-10-07.json','docs/round15-results-2026-10-07.json']

def declared_variants():
    # Extract the unmodified variants() function from the source AST without importing
    # its pandas_ta/numba-dependent crypto modules.
    tree=ast.parse((ROOT/'app/crypto_round8_research.py').read_text())
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='variants')
    ns={'json':json}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'crypto_round8_research.py','exec'),ns)
    top=json.loads((ROOT/'docs/round8-results-2026-10-07.json').read_text())['top10']
    return [{'rank':i,'family':r['family'],'representative_name':r['name'],'config':r['config'],
             'source':r['source'],'source_status':r['status'],
             'variants':[{'filter':f,'config':c} for f,c in ns['variants'](r)]}
            for i,r in enumerate(top,1)]

def run():
    p=D.load(); reps=declared_variants()
    r9=json.loads((ROOT/'docs/round9-results-2026-10-07.json').read_text())
    r15=json.loads((ROOT/'docs/round15-results-2026-10-07.json').read_text())
    sources={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in SOURCES}
    r12=json.loads((ROOT/'docs/round12-results-2026-10-07.json').read_text())
    r13=json.loads((ROOT/'docs/round13-results-2026-10-07.json').read_text())
    r14=json.loads((ROOT/'docs/round14-results-2026-10-07.json').read_text())
    # Full declared search denominators: preserve source-level unique counts and
    # candidate scopes, not just the subset with saved KR-compatible controls.
    out={'market':'KR equity','panel':{'symbols':len(p.syms),'dates':[str(p.dates[0].date()),str(p.dates[-1].date())],'sessions':len(p.dates)},
      'crypto_sources_sha256':sources,'round8':{'top10_source_selected_representatives':reps,
        'declared_variant_count':sum(len(x['variants']) for x in reps),'evaluated_in_kr':0,
        'omission':'All declared configs inventoried, but no KR strategy evaluation claimed: source families include crypto-specific signals/accounting and no one-to-one mapping is defined.'},
      'round9':{'source_fixed_config':r9['config'],'source_periods':r9['periods'],
        'source_checks':{'flapping_threshold':r9['thresholds'],'period_alpha_min':r9['thresholds']['alpha_positive_min']},
        'kr_reproductions':0,'omission':'TOP_K12 source diagnosis inventoried; KR score/ranking, breaker and crypto benchmark are not equivalent to KR broad-market state. No KR diagnosis result asserted.'},
      'round15':{'source_counts':r15['counts'],'unique_hypotheses':r15['total_unique'],'declared_tests':r15['checks'],
        'trial_control_source_counts':{'round12':len(r12.get('experiments',[])),'round13':len(r13.get('experiments',[])),'round14':len(r14.get('experiments',[]))},
        'source_hypothesis_inputs_available':True,'kr_hypotheses_recomputed':0,'kr_inference':None,
        'omission':'Round15 contains only aggregate crypto p and multiplicity counts; no raw 300-control trial series or per-hypothesis matched null inputs. Equity p-values cannot be recomputed. Crypto p-values intentionally not reused.'},
      'limitations':['No KR result is inferred from crypto-only benchmarks or universe-specific ranking.','No market adaptation is claimed for Round8, Round9, or Round15; this is the requested auditable source inventory and explicit gap record.']}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)); print('round8 variants',out['round8']['declared_variant_count'],'round9 periods',len(r9['periods']),'round15 hypotheses',r15['total_unique'])
if __name__=='__main__':run()
