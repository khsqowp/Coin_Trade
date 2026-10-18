"""US-only Round 7 robustness transfer; no network access or shared-file edits."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from app.rs_equity_transfer import load_equity_panel
from app.rs_equity_round5_transfer import _frames, _prepare, _bucket, _metrics, PERIODS
from app.rs_equity_round12_13_portfolio import _costs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/research/equity_transfer_2026-10/full_runs/round7_us.json'
SEED = 700000

def compact(m):
    return {k:m[k] for k in ('cagr','mdd','sharpe','trades','final','years') if k in m}

def run():
    panel=load_equity_panel('US'); frames=_frames(panel)
    book=_prepare(frames,'volume_spike_cap5',3.0,5.0)
    rows=[]; cost_outputs=[]
    for cost in _costs(panel):
        base=_bucket(panel,book,cost); rec=base['records']; dates=base['dates']; curve=base['curve']
        # Preserve the source frequency definition; stock signal rate is evaluated per symbol-day.
        arrays=[]
        for s,f in book.items():
            x=f.copy(); arrays.append((s,x))
        eligible=sum(int((np.isfinite(panel.c[:,j][:-1]) & np.isfinite(panel.c[:,j][1:])).sum()) for j in range(len(panel.symbols)))
        p=len(rec)/max(eligible,1); trials=[]
        for seed in range(SEED,SEED+500):
            rng=np.random.default_rng(seed); random_book={}
            for s,f in arrays:
                z=f.copy(); z['SIGNAL']=pd.Series((rng.random(len(z))<p)&z.Close.notna().to_numpy(),index=z.index); random_book[s]=z
            r=_bucket(panel,random_book,cost); trials.append(dict(seed=seed,metrics=compact(r['metrics'])))
        # US adaptation: symbol leave-outs use exact top-five crypto champion identifiers only as a proxy rule;
        # report corresponding top five US realized-PnL contributors instead of implying name equivalence.
        agg={s:sum(t['pnl'] for t in rec if t['symbol']==s) for s in panel.symbols}
        top=sorted(agg,key=lambda s:(-agg[s],s))[:5]
        loo=[]
        for s in top:
            r=_bucket(panel,{k:v for k,v in book.items() if k!=s},cost); loo.append(dict(kind='symbol',excluded=s,metrics=compact(r['metrics'])))
        years=sorted({pd.Timestamp(t['exit_date']).year for t in rec})
        for year in years:
            selected={s:f.loc[f.index.year!=year] for s,f in book.items()}
            r=_bucket(panel,selected,cost); loo.append(dict(kind='year',excluded=year,metrics=compact(r['metrics'])))
        # Trade-block bootstrap: trade outcomes are net realized returns. This is a proxy CI,
        # not the original portfolio engine's independently resampled daily equity path.
        returns=np.array([t['pnl']/max(t['cost'],1e-12) for t in rec],float)
        rng=np.random.default_rng(710000); samples=[]
        if len(returns)>=20:
            for _ in range(1000):
                starts=rng.integers(0,len(returns)-20+1,size=int(np.ceil(len(returns)/20)))
                ix=(starts[:,None]+np.arange(20)).ravel()[:len(returns)]
                q=returns[ix]; samples.append(float(q.mean()/q.std(ddof=1)*np.sqrt(len(q))) if q.std(ddof=1)>0 else 0.)
        ci=np.percentile(samples,[2.5,97.5]).tolist() if samples else None
        base_m=base['metrics']; controls={k:[x['metrics'][k] for x in trials] for k in ('cagr','sharpe')}
        mc={k:dict(p=float((1+sum(v>=base_m[k] for v in vals))/501),q95=float(np.percentile(vals,95)),max=float(max(vals))) for k,vals in controls.items()}
        cost_outputs.append(dict(cost_case=cost[0],baseline=compact(base_m),eligible_symbol_days=eligible,signal_probability=p,
          monte_carlo=dict(n=500,seed_range=[SEED,SEED+499],tests=mc,trial_metrics=trials),
          leave_out=dict(top5_us_realized_contributors=top,years=years,rows=loo),
          bootstrap=dict(n=1000,block_size=20,seed=710000,ci95=ci,trade_count=len(returns),samples=samples),
          causal_checks=dict(prefix='existing engine signal-next-open contract; not independently mutation-tested in this runner',passed=None)))
    out=dict(market='US',symbols=panel.symbols,source='app/crypto_round7_research.py',source_baseline=json.loads((ROOT/'docs/round7-results-2026-10-07.json').read_text())['baseline'],
      methodology='KIS local daily panel (54 names); existing cost cases and next-open simulate_cost_portfolio. Crypto champion is volume_spike_cap5; crypto-only symbol names mapped to realized US top-five contributors. Bootstrap uses realized trade returns, a labeled non-equivalent proxy.',cost_cases=cost_outputs,
      omissions=['Original crypto ledger exact-match is not applicable to distinct US assets.','Original causal prefix/future-mutation assertions were not ported into this execution artifact.'])
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False,default=str))
    print('ROUND7_US',len(panel.symbols),len(cost_outputs),[len(x['monte_carlo']['trial_metrics']) for x in cost_outputs],[x['leave_out']['rows'].__len__() for x in cost_outputs])
    return out
if __name__=='__main__': run()
