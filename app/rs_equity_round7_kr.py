"""KR adaptation of crypto Round 7 controls on the local KIS daily panel.

The signal is an explicitly labeled volume-spike proxy; accounting is KR next-open.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from app import rs_kr_data as D, rs_kr_engine as E

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/research/equity_transfer_2026-10/full_runs/round7_kr.json'

def signal(P, multiple=3.0):
    # Crypto volume-spike proxy: volume >= multiple * trailing 20-session mean;
    # close-to-close move capped at 5%; rank by 20-session relative volume.
    val = pd.DataFrame(P.v, index=P.dates, columns=P.syms)
    c = pd.DataFrame(P.c, index=P.dates, columns=P.syms)
    ratio = val / val.shift(1).rolling(20, min_periods=20).mean()
    move = c.pct_change(fill_method=None).abs()
    return ratio.to_numpy(), ((ratio >= multiple) & (move < .05) & pd.DataFrame(P.elig,index=P.dates,columns=P.syms)).fillna(False).to_numpy()

def run():
    P=D.load(); ratio, sig=signal(P); T,N=P.c.shape
    start=int(P.dates.searchsorted(pd.Timestamp('2018-11-01')))
    # Independent repeated random controls, matched on signal incidence, using KR event accounting.
    p=float(sig[start:].sum()/max(P.elig[start:].sum(),1)); rng=np.random.default_rng(700000)
    def trial(mask, scores=ratio):
        entry=mask.copy(); exit_sig=np.zeros_like(entry); score=np.nan_to_num(scores,nan=-1e18)
        # Preserve the source champion's 20-session maximum hold. Entry is known
        # at close t; the scheduled close signal is acted on at the next open.
        for lag in range(1, 21):
            exit_sig[lag:] |= entry[:-lag]
        return E.run_events(P,entry,exit_sig,score,slots=8)
    def summary(r):
        m=E.metrics(r,P,start,len(P.dates)-1)
        return {k:(int(m[k]) if k=='trades' else float(m[k])) for k in ('cagr','mdd','calmar','trades','final')}
    base=summary(trial(sig)); controls=[]
    for i in range(500):
        mask=(rng.random((T,N))<p)&P.elig
        controls.append(dict(seed=700000+i,**summary(trial(mask))))
    years=sorted(set(P.dates[start:].year)); symbols=np.argsort(-np.nan_to_num(np.nansum(np.where(sig,ratio,0),axis=0)))[:5]
    loo=[]
    for j in symbols:
        m=sig.copy(); m[:,j]=False; loo.append(dict(kind='symbol',excluded=P.syms[j],**summary(trial(m))))
    for y in years:
        m=sig.copy(); m[P.dates.year==y]=False; loo.append(dict(kind='year',excluded=int(y),**summary(trial(m))))
    # 20-trade moving block bootstrap (trade returns unavailable in shared event engine;
    # derive KR-compatible proxy returns from completed trade PnL is not exposed).
    # Therefore do not fabricate a trade bootstrap; preserve an explicit omission.
    causal=[]
    for cut in [int(T*.55),int(T*.75)]:
        # Future-price mutation invariant for signal decisions.
        altered=P.c.copy(); altered[cut:]*=3
        P2=type(P)(P.dates,P.syms,P.o,P.h,P.l,altered,P.v,P.elig,P.tradable,P.slip)
        _,s2=signal(P2)
        prefix_signal_equal=bool(np.array_equal(sig[:cut],s2[:cut]))
        # Independent prefix replay with the same random stream and same
        # precomputed KR cost vector; future observations are physically removed.
        small=type(P)(P.dates[:cut+1],P.syms,P.o[:cut+1],P.h[:cut+1],P.l[:cut+1],P.c[:cut+1],P.v[:cut+1],P.elig[:cut+1],P.tradable[:cut+1],P.slip)
        small_ratio,small_sig=signal(small)
        full_rng=np.random.default_rng(700000); full_masks=(full_rng.random((T,N))<p)&P.elig
        short_rng=np.random.default_rng(700000); short_masks=(short_rng.random((cut+1,N))<p)&small.elig
        full_curve=trial(full_masks)["eq"].iloc[:cut+1].to_numpy()
        short_ratio=np.nan_to_num(small_ratio,nan=-1e18)
        # Rebuild the 20-session scheduled exits in a strictly truncated run.
        short_exit=np.zeros_like(short_masks)
        for lag in range(1,21): short_exit[lag:] |= short_masks[:-lag]
        short_curve=E.run_events(small,short_masks,short_exit,short_ratio,slots=8)["eq"].to_numpy()
        prefix_nav_equal=bool(np.allclose(full_curve,short_curve,rtol=0,atol=1e-12))
        causal.append(dict(cutoff=str(P.dates[cut]),prefix_signal_equal=prefix_signal_equal,prefix_nav_equal=prefix_nav_equal))
    out=dict(market='KR equity',panel=dict(dates=[str(P.dates[start].date()),str(P.dates[-1].date())],symbols=N,eligible_days=int(P.elig[start:].sum())),
      proxy='Crypto Round7 champion approximated as >=3x 20-session mean volume and absolute daily return <5%; not an equivalent signal.',
      accounting='KR run_events: next-open entry, local commission/slippage/tax, eligibility and tradability filters.',baseline=base,
      random_controls=dict(requested=500,completed=len(controls),seed_start=700000,incidence=p,rows=controls),leave_out=loo,
      bootstrap=dict(requested=1000,block_size=20,completed=0,omission='KR event engine returns aggregate win rate, not a per-trade return ledger; valid block bootstrap unavailable.'),
      causal_checks=causal,omissions=['trade-level bootstrap unavailable: shared event engine does not expose closed-trade return series'])
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)); print('round7',len(controls),len(loo),base)
if __name__=='__main__': run()
