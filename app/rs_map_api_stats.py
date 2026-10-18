"""Selection statistics for map_api results (reads scratch results; no network).
python -m app.rs_map_api_stats  -> writes docs/research/map_api_stats.json"""
from __future__ import annotations
import json, sys
import numpy as np, pandas as pd

D = '/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/20fd8e9e-6d26-4ff1-a6b5-39a3bd8d3e48/scratchpad/map_api/'
BLK = {'IS': ('2022-01-01', '2026-06-11'), 'T2023': ('2023-01-01', '2023-12-31'), 'T2024': ('2024-01-01', '2024-12-31'),
       'T2025': ('2025-01-01', '2025-12-31'), 'T2026': ('2026-01-01', '2026-06-11'), 'HOLD': ('2026-06-12', '2030-01-01')}


def load(tag='full'):
    r = pd.read_pickle(f'{D}{tag}/results.pkl')
    z = np.load(f'{D}{tag}/daily_returns.npz')
    ret = {k: z[k] for k in z.files}
    days = pd.DatetimeIndex(np.load(f'{D}full/days.npy'))
    return r, ret, days


def stats(x: np.ndarray):
    if len(x) < 20:
        return dict(cagr=np.nan, mdd=np.nan, calmar=np.nan, sharpe=np.nan)
    e = np.cumprod(1 + x); hw = np.maximum.accumulate(np.r_[1., e])[1:]
    mdd = float(np.max(1 - e / hw)); cagr = float(e[-1] ** (365 / len(x)) - 1) if e[-1] > 0 else -1.0
    sd = x.std(ddof=1)
    return dict(cagr=cagr, mdd=mdd, calmar=cagr / mdd if mdd > 0 else 0.0, sharpe=float(x.mean() / sd * np.sqrt(365)) if sd > 0 else 0.0)


def win(days, a, b):
    return (days >= pd.Timestamp(a)) & (days <= pd.Timestamp(b))


def matched_baseline(r):
    b = r[(r['mode'] == 'M5') & (r.signal == 'mom14')]
    m = {}
    for _, x in b.iterrows():
        m[(bool(x.crash), int(x.rebal), int(x.K))] = x.case_id
    return m


def base_id(row, bm):
    crash = bool(row.crash) or row['mode'] == 'M4'
    return bm[(crash, int(row.rebal), int(row.K))]


def deflated_sharpe(sr_daily, n_trials, sr_std_trials, T, skew, kurt):
    """Bailey/Lopez de Prado deflated Sharpe probability (daily units)."""
    from math import sqrt
    from scipy.stats import norm
    emc = 0.5772156649
    z1, z2 = norm.ppf(1 - 1 / n_trials), norm.ppf(1 - 1 / (n_trials * np.e))
    sr0 = sr_std_trials * ((1 - emc) * z1 + emc * z2)
    den = sqrt(max(1e-12, 1 - skew * sr_daily + (kurt - 1) / 4 * sr_daily ** 2))
    return float(norm.cdf((sr_daily - sr0) * sqrt(T - 1) / den)), float(sr0)


# ------------------------------------------------------------------ analysis
def block_stats(ret, days):
    return {k: stats(ret[win(days, a, b)]) for k, (a, b) in BLK.items()}


def walk_forward(r, ret, days, mode, pick_pool=None):
    """expanding window: pick best-train-Calmar case per test block; chain OOS returns."""
    x = r[r['mode'] == mode] if pick_pool is None else pick_pool
    out, chain = {}, []
    for test, (ta, tb) in [('2023', ('2023-01-01', '2023-12-31')), ('2024', ('2024-01-01', '2024-12-31')),
                           ('2025', ('2025-01-01', '2025-12-31')), ('2026H1', ('2026-01-01', '2026-06-11'))]:
        tr = win(days, '2022-01-01', pd.Timestamp(ta) - pd.Timedelta(days=1))
        te = win(days, ta, tb)
        best, bc = None, -9
        for cid in x.case_id:
            c = stats(ret[cid][tr])['calmar']
            if c > bc:
                bc, best = c, cid
        o = stats(ret[best][te])
        out[test] = dict(pick=best, train_calmar=bc, test_cagr=o['cagr'], test_mdd=o['mdd'], test_calmar=o['calmar'])
        chain.append(ret[best][te])
    return out, np.concatenate(chain)


def main():
    r, ret, days = load('full')
    r1, ret1, _ = load('lag_1'); rm, retm, _ = load('lag_-1')
    bm = matched_baseline(r)
    live = 'M5_mom14_r3_k8_w0_c1_l0'
    res = dict(n_cases=int(len(r)), by_mode=r.groupby('mode').size().to_dict())
    # --- matched-baseline wins
    blocks = ['IS', 'T2023', 'T2024', 'T2025', 'T2026']
    rows = []
    for _, x in r[r['mode'].isin(['M1', 'M2', 'M3', 'M4', 'M4b'])].iterrows():
        bid = base_id(x, bm) if x['mode'] != 'M4b' else bm[(False, int(x.rebal), int(x.K))]
        if x['mode'] in ('M1', 'M2'):
            bid = bm[(False, int(x.rebal), int(x.K))]
        br = r.set_index('case_id').loc[bid]
        w = [x[f'{b}_calmar'] > br[f'{b}_calmar'] for b in blocks]
        rows.append(dict(case_id=x.case_id, base=bid, wins=int(sum(w)), win_all=bool(all(w))))
    wd = pd.DataFrame(rows).set_index('case_id')
    r2 = r.set_index('case_id').join(wd)
    summ = r2[r2.wins.notna()].groupby(['mode', 'family']).agg(n=('wins', 'size'), win_all=('win_all', 'mean'),
                                                              win_IS=('wins', lambda s: float((s >= 1).mean())),
                                                              med_IS_calmar=('IS_calmar', 'median')).reset_index()
    res['win_summary'] = summ.round(4).to_dict('records')
    # --- walk-forward per mode and for the pooled "any new signal"
    wf = {}
    live_ret = ret[live]
    ref_chain = np.concatenate([live_ret[win(days, a, b)] for a, b in
                                [('2023-01-01', '2023-12-31'), ('2024-01-01', '2024-12-31'), ('2025-01-01', '2025-12-31'), ('2026-01-01', '2026-06-11')]])
    wf['live_baseline_same_period'] = stats(ref_chain)
    for mode in ['M1', 'M2', 'M3', 'M4', 'M4b']:
        o, ch = walk_forward(r, ret, days, mode)
        wf[mode] = dict(folds=o, chained=stats(ch), corr_with_live=float(np.corrcoef(ch, ref_chain)[0, 1]))
    for fam in ['d', 'h', 'b', 'e']:
        for mode in ['M1', 'M3']:
            pool = r[(r['mode'] == mode) & (r.family == fam)]
            o, ch = walk_forward(r, ret, days, mode, pool)
            wf[f'{mode}_{fam}'] = dict(folds={k: dict(pick=v['pick'], test_calmar=v['test_calmar']) for k, v in o.items()},
                                       chained=stats(ch))
    res['walk_forward'] = wf
    # --- deflated Sharpe for top 15 by IS calmar per mode
    isw = win(days, *BLK['IS'])
    from scipy.stats import skew, kurtosis
    dsr = {}
    for mode in ['M1', 'M3', 'M4']:
        x = r[r['mode'] == mode]
        srs = np.array([ret[c][isw].mean() / ret[c][isw].std(ddof=1) for c in x.case_id])
        top = x.sort_values('IS_calmar', ascending=False).head(10)
        lst = []
        for cid in top.case_id:
            a = ret[cid][isw]; sr = a.mean() / a.std(ddof=1)
            p, sr0 = deflated_sharpe(sr, len(x), srs.std(), len(a), skew(a), kurtosis(a, fisher=False))
            lst.append(dict(case=cid, sharpe_ann=float(sr * np.sqrt(365)), dsr_prob=p, sr0_ann=float(sr0 * np.sqrt(365))))
        dsr[mode] = lst
    res['deflated_sharpe'] = dsr
    json.dump(res, open('/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/20fd8e9e-6d26-4ff1-a6b5-39a3bd8d3e48/scratchpad/map_api/stats1.json', 'w'), default=float, indent=1)
    print(json.dumps(res['win_summary'], default=float)[:6000])
    for k, v in wf.items():
        print(k, json.dumps(v.get('chained', v), default=float)[:300])
    for m, l in dsr.items():
        print(m, [(d['case'][3:40], round(d['dsr_prob'], 3)) for d in l[:5]])


if __name__ == '__main__':
    main()
