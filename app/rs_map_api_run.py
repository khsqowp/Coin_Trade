"""Resumable offline phase-averaged map experiments. Run with PYTHONPATH=."""
import os
# Keep compilation artifacts outside the repository and cap native threads.
os.environ.setdefault('NUMBA_CACHE_DIR','/private/tmp/rs_map_api_numba')
for _key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS']:
    os.environ[_key] = '1'
import argparse
import json
import multiprocessing as mp
from pathlib import Path
import time
import numpy as np
import pandas as pd
from numba import njit
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim, _sim, params, window_metrics, yearly_returns
from app.rs_map_api_feat import build_features, rank_z, shift_signal

OUT = Path('/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/20fd8e9e-6d26-4ff1-a6b5-39a3bd8d3e48/scratchpad/map_api')
WINDOWS = {'IS':('2022-01-01','2026-06-11'), 'F1':('2022-01-01','2022-12-31'), 'T2023':('2023-01-01','2023-12-31'), 'T2024':('2024-01-01','2024-12-31'), 'T2025':('2025-01-01','2025-12-31'), 'T2026':('2026-01-01','2026-06-11'), 'HOLDOUT':('2026-06-12',None)}
G = {}


@njit(cache=True)
def long_only(dc, fd, score, d0, rebal, k, phase, reference=0):
    """Close trades affect the following day; drift includes funding in NAV."""
    nd,n = dc.shape
    eq = np.ones(nd); weights = np.zeros(n); wealth = 1.0
    for i in range(d0,nd):
        gross = np.zeros(n); fund = 0.0
        if i > d0:
            for j in range(n):
                change = 0.0
                if np.isfinite(dc[i,j]) and np.isfinite(dc[i-1,j]) and dc[i-1,j]>0:
                    change = dc[i,j]/dc[i-1,j]-1
                    if np.isfinite(fd[i,j]):
                        fund += weights[j]*fd[i,j]/dc[i-1,j]
                gross[j] = weights[j]*(1+change)
            factor = 1.0 + gross.sum()-weights.sum()-fund
            wealth *= factor
            if factor > 0:
                weights = gross/factor
        eq[i] = wealth
        if i == nd-1:
            continue
        due = i >= d0+phase and (i-d0-phase)%rebal == 0
        if reference == 1: due = i == d0  # BTC buy and hold
        if due:
            target = np.zeros(n)
            valid = np.isfinite(score[i]) & np.isfinite(dc[i]) & (dc[i]>0)
            count = valid.sum()
            if reference == 2:
                if count == 0: continue
                for j in range(n):
                    if valid[j]: target[j] = 1.0/count
            else:
                if count < k: continue
                order = np.argsort(-np.where(valid,score[i],-1e100))
                for j in order[:k]: target[j] = 1.0/k
            charge = .001*np.abs(target-weights).sum()
            wealth *= max(0.0,1-charge)
            weights = target
    return eq


def init_worker(feature_path):
    sim = Sim(load_panel())
    z = np.load(feature_path)
    signals = {k[2:]:np.ascontiguousarray(z[k]) for k in z.files if k.startswith('s_')}
    flags = {k[2:]:z[k] for k in z.files if k.startswith('g_')}
    d0 = sim.d_start()
    G.update(sim=sim, signals=signals, flags=flags, d0=d0, dc=sim.C[:,-1],
             zero=np.zeros(sim.nd), mom={w:sim.signal((w,)) for w in [7,10,14,21,28]},
             zsignals={k:rank_z(v) for k,v in signals.items()})
    G['turnover'] = {}
    for name,a in {**signals,**{f'mom{x}':v for x,v in G['mom'].items()}}.items():
        ranks = pd.DataFrame(a).rank(axis=1,pct=True).to_numpy()
        changes = np.abs(ranks[1:]-ranks[:-1])
        counts = np.isfinite(changes).sum(axis=1)
        values = np.divide(np.nansum(changes,axis=1),counts,out=np.full(len(counts),np.nan),where=counts>0)
        dates = sim.days[1:]
        mask = (dates>=pd.Timestamp('2022-01-01',tz='UTC')) & (dates<=pd.Timestamp('2026-06-11',tz='UTC'))
        G['turnover'][name] = float(np.nanmean(values[mask]))


def returns(eq, d0):
    a = np.asarray(eq[d0:],float).copy()
    # A liquidated engine path ends in NaNs: preserve total loss, then remain zero.
    last = 1.0
    for i in range(len(a)):
        if not np.isfinite(a[i]): a[i] = last
        last = a[i]
    prev = np.r_[1.,a[:-1]]
    return np.divide(a,prev,out=np.ones_like(a),where=prev>0)-1


def evaluate(c):
    sim,d0 = G['sim'],G['d0']
    mode,name,r,k,w,sign,lag,crash = (c[x] for x in ['mode','signal','rebal','K','w','sign','lag','crash'])
    flag = G['zero']
    if mode in ['M1','M2','M3']:
        score = shift_signal(G['signals'][name],lag)
        if mode == 'M3': score = G['mom'][14]+w*rank_z(score)
    elif mode in ['M4','M4b']:
        score = G['mom'][14]
        flag = G['flags'][name]
    elif name == 'BTC_BH':
        score = np.full_like(G['dc'],np.nan)
        score[:,sim.names.index('BTC')] = 1
    elif name == 'EW_UNIVERSE':
        score = np.where(np.isfinite(G['dc']),0.,np.nan)
    else:
        score = G['mom'][int(name[3:])]
    if crash: flag = np.maximum(flag,sim.crash)
    pr_returns, pr_worst = [], []
    phases = range(r) if name != 'BTC_BH' else range(1)
    for ph in phases:
        if mode == 'M2' or mode == 'REF':
            ref = 1 if name=='BTC_BH' else (2 if name=='EW_UNIVERSE' else 0)
            eq = long_only(G['dc'],sim.FD,score,d0,r,k,ph,ref)
            worst = eq
        else:
            eq,worst,_,_ = _sim(sim.H,sim.L,sim.C,sim.FD,np.ascontiguousarray(score),np.asarray(flag,float),
                                params(rebal=r,K=k,lev=1,deploy=1,cost=.001,fund=1,phase=ph),sim.minj(0),sim.step_j,d0,sim.nd)
        rr = returns(eq,d0)
        prev = np.r_[1.,np.asarray(eq[d0:-1])]
        wr = np.divide(worst[d0:],prev,out=np.ones_like(prev),where=np.isfinite(prev)&(prev>0))
        wr = np.where(np.isfinite(wr),wr,1.)
        pr_returns.append(rr); pr_worst.append(wr)
    mean = np.mean(pr_returns,axis=0)
    equity = np.cumprod(1+mean)
    previous = np.r_[1.,equity[:-1]]
    res = {'eq':pd.Series(equity,index=sim.days[d0:]),'worst':pd.Series(previous*np.mean(pr_worst,axis=0),index=sim.days[d0:])}
    row = c.copy()
    turnover_name = 'mom14' if mode in ['M4','M4b'] else name
    row['mean_daily_rank_turnover'] = G['turnover'].get(turnover_name,0. if name in ['BTC_BH','EW_UNIVERSE'] else np.nan)
    # Overlay turnover refers to its traded, combined score, not its ingredient.
    if mode=='M3' or lag:
        ranks = pd.DataFrame(score).rank(axis=1,pct=True).to_numpy()
        mask = (sim.days[1:]>=pd.Timestamp('2022-01-01',tz='UTC')) & (sim.days[1:]<=pd.Timestamp('2026-06-11',tz='UTC'))
        row['mean_daily_rank_turnover'] = float(np.nanmean(np.abs(np.diff(ranks,axis=0))[mask]))
    for label,(a,b) in WINDOWS.items():
        # Include first day's return in each independently rebased window.
        mask = (res['eq'].index>=pd.Timestamp(a,tz='UTC'))
        if b: mask &= res['eq'].index<=pd.Timestamp(b,tz='UTC')
        rr = mean[mask]; ww = np.mean(pr_worst,axis=0)[mask]
        ee = np.cumprod(1+rr); pp = np.r_[1.,ee[:-1]]
        hw = np.maximum.accumulate(np.r_[1.,ee])[1:]
        mdd = float(np.max(1-ee/hw)) if len(ee) else np.nan
        imdd = float(np.max(1-np.minimum(ee,pp*ww)/hw)) if len(ee) else np.nan
        cagr = float(ee[-1]**(365/len(ee))-1) if len(ee) and ee[-1]>0 else -1.
        sd = np.std(rr,ddof=1) if len(rr)>1 else 0.
        metrics = dict(cagr=cagr,mdd=mdd,imdd=imdd,calmar=cagr/mdd if mdd>0 else 0.,
                       sharpe=float(np.mean(rr)/sd*np.sqrt(365)) if sd>0 else 0.,days=len(rr),
                       calmar_intraday=cagr/imdd if imdd>0 else 0.)
        for key,value in metrics.items(): row[f'{label}_{key}'] = value
        phase_dd = []
        phase_idd = []
        for rp,wp in zip(pr_returns,pr_worst):
            ep = np.cumprod(1+rp[mask]); hp = np.maximum.accumulate(np.r_[1.,ep])[1:]
            phase_dd.append(float(np.max(1-ep/hp)))
            phase_idd.append(float(np.max(1-np.minimum(ep,np.r_[1.,ep[:-1]]*wp[mask])/hp)))
        row[f'{label}_phase_worst_mdd'] = max(phase_dd)
        row[f'{label}_phase_worst_imdd'] = max(phase_idd)
    for year in range(2022,2027):
        row[f'return_{year}'] = float(np.prod(1+mean[sim.days[d0:].year==year])-1)
    return row,mean.astype(np.float32)


def cases(names, metadata, flags, lag):
    out = []
    def add(mode,name,r,k,w=0.,crash=False):
        meta = metadata.get(name,{})
        out.append(dict(case_id=f'{mode}_{name}_r{r}_k{k}_w{w:g}_c{int(crash)}_l{lag if mode in ["M1","M2","M3"] else 0}',
                        mode=mode,signal=name,family=meta.get('family','g' if name.startswith('g_') else 'baseline'),
                        rebal=r,K=k,w=w,sign=meta.get('sign',1),lag=lag if mode in ['M1','M2','M3'] else 0,crash=crash))
    for name in names:
        for mode in ['M1','M2']:
            for r in [1,2,3,5,7]:
                for k in [4,6,8,10,12]: add(mode,name,r,k)
        for w in [.25,.5,1.]:
            for r in [2,3,5]:
                for k in [6,8,10]: add('M3',name,r,k,w,True)
    for name in flags:
        for r,k in [(3,8),(2,6),(2,10),(5,6),(5,10)]:
            add('M4',name,r,k,crash=True)
            add('M4b',name,r,k)
    for lb in [7,10,14,21,28]:
        for r in [1,2,3,5,7]:
            for k in [4,6,8,10,12]:
                for crash in [False,True]: add('M5',f'mom{lb}',r,k,crash=crash)
    for r in [1,2,3,5,7]:
        for k in [4,6,8,10,12]: add('REF','mom14',r,k)
    add('REF','BTC_BH',1,1)
    add('REF','EW_UNIVERSE',1,1)
    return out


def atomic_pickle(df,path):
    tmp = path.with_suffix('.tmp'); df.to_pickle(tmp); tmp.replace(path)


def save_npz(path,arrays):
    tmp = path.with_suffix('.tmp.npz'); np.savez_compressed(tmp,**arrays); tmp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--lag',type=int,default=0,help='Additional signal lag; -1 is a leak positive control')
    args = parser.parse_args()
    start = time.monotonic()
    OUT.mkdir(parents=True,exist_ok=True)
    feature_path = OUT/'features.npz'
    if not feature_path.exists():
        P = load_panel()
        signals,meta,flags,audit = build_features(P)
        save_npz(feature_path,{**{'s_'+k:v for k,v in signals.items()},**{'g_'+k:v for k,v in flags.items()}})
        (OUT/'feature_metadata.json').write_text(json.dumps(dict(metadata=meta,audit=audit),indent=2))
    else:
        meta = json.loads((OUT/'feature_metadata.json').read_text())['metadata']
        with np.load(feature_path) as z: flags = [k[2:] for k in z.files if k.startswith('g_')]
    names = list(meta)
    if args.smoke: names = ['d_fund_mean_7_p','h_session_0_7_p','b_taker_imb_7_p']
    all_cases = cases(names,meta,flags,args.lag)
    dest = OUT/('smoke' if args.smoke else ('full' if args.lag==0 else f'lag_{args.lag}'))
    dest.mkdir(exist_ok=True)
    counts = pd.Series([c['mode'] for c in all_cases]).value_counts(sort=False).to_dict()
    print('CASE_COUNTS',json.dumps(counts),'TOTAL',len(all_cases),flush=True)
    all_rows,all_returns = [],{}
    with mp.get_context('spawn').Pool(4,initializer=init_worker,initargs=(str(feature_path),)) as pool:
        for mode in counts:
            table_path,ret_path = dest/f'{mode}.pkl',dest/f'{mode}.npz'
            rows,series = [],{}
            if table_path.exists() and ret_path.exists():
                rows = pd.read_pickle(table_path).to_dict('records')
                with np.load(ret_path) as z: series = {k:z[k] for k in z.files}
            done = {x['case_id'] for x in rows} & set(series)
            rows = [x for x in rows if x['case_id'] in done]
            pending = [c for c in all_cases if c['mode']==mode and c['case_id'] not in done]
            for ix,(row,rr) in enumerate(pool.imap_unordered(evaluate,pending,chunksize=8),1):
                rows.append(row); series[row['case_id']] = rr
                if ix%250==0:
                    save_npz(ret_path,series); atomic_pickle(pd.DataFrame(rows),table_path)
                    print(mode,len(rows),'/',counts[mode],f'elapsed={time.monotonic()-start:.1f}s',flush=True)
            save_npz(ret_path,series); atomic_pickle(pd.DataFrame(rows),table_path)
            all_rows.extend(rows); all_returns.update(series)
            print('MODE_DONE',mode,len(rows),f'elapsed={time.monotonic()-start:.1f}s',flush=True)
    df = pd.DataFrame(all_rows)
    assert len(df)==len(all_cases) and df.case_id.is_unique
    assert set(df.case_id)==set(all_returns)
    assert all(a.dtype==np.float32 and np.isfinite(a).all() for a in all_returns.values())
    atomic_pickle(df,dest/'results.pkl'); save_npz(dest/'daily_returns.npz',all_returns)
    sim = Sim(load_panel()); np.save(dest/'days.npy',sim.days[sim.d_start():].tz_localize(None).values)
    baseline = df[(df['mode']=='M5') & (df.signal=='mom14') & (df.rebal==3) & (df.K==8) & df.crash]
    columns = ['case_id']+[f'{win}_{m}' for win in ['IS','HOLDOUT'] for m in ['cagr','mdd','imdd','calmar','sharpe','phase_worst_mdd','phase_worst_imdd']]
    print('BASELINE',baseline[columns].to_json(orient='records'),flush=True)
    elapsed = time.monotonic()-start
    summary = dict(counts=counts,total=len(df),runtime_seconds=elapsed,baseline=baseline[columns].to_dict('records'),
                   methodology='phase mean simple returns; Calmar uses closing MDD; IMDD separate; windows rebased including first return; F1 train-only; holdout never ranked',
                   approximations='long-only daily close drift and funding; no hourly liquidation; missing regimes inactive; sector membership current; percentile 365 calendar days')
    (dest/'summary.json').write_text(json.dumps(summary,indent=2))
    print('VERIFIED',len(df),'cases',f'runtime={elapsed:.2f}s','ARTIFACTS',dest,flush=True)


if __name__=='__main__': main()
