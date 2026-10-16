"""Finalist table: matched-baseline wins, neighbourhood, nulls, lag tests, correlation/blend, holdout (once)."""
from __future__ import annotations
import json, pickle
import numpy as np, pandas as pd
from app.rs_map_api_stats import D, BLK, load, stats, win, matched_baseline, base_id

LIVE = 'M5_mom14_r3_k8_w0_c1_l0'


def inv_vol_blend(a, b, n=60):
    sa = pd.Series(a).rolling(n, min_periods=10).std().shift(1).to_numpy()
    sb = pd.Series(b).rolling(n, min_periods=10).std().shift(1).to_numpy()
    w = np.where(np.isfinite(sa) & np.isfinite(sb), (1 / sa) / (1 / sa + 1 / sb), 0.5)
    return w * a + (1 - w) * b


def neighbours(r, row):
    """one-step neighbours in (rebal, K, w) and sibling windows of same signal stem."""
    pool = r[(r['mode'] == row['mode']) & (r.signal == row.signal)]
    R = sorted(pool.rebal.unique()); Ks = sorted(pool.K.unique()); W = sorted(pool.w.unique())
    def step(v, vals, d):
        i = vals.index(v) + d
        return vals[i] if 0 <= i < len(vals) else None
    out = []
    for dr, dk, dw in [(-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1)]:
        rr, kk, ww = step(row.rebal, R, dr), step(row.K, Ks, dk), step(row.w, W, dw)
        if None in (rr, kk, ww):
            continue
        if (rr, kk, ww) == (row.rebal, row.K, row.w):
            continue
        m = pool[(pool.rebal == rr) & (pool.K == kk) & (pool.w == ww)]
        out.append(float(m.IS_calmar.iloc[0]))
    # sibling signals: same family prefix up to last numeric window token
    stem = '_'.join(row.signal.split('_')[:-2]) if row.signal[-2] == '_' else row.signal
    sib = r[(r['mode'] == row['mode']) & (r.rebal == row.rebal) & (r.K == row.K) & (r.w == row.w) &
            (r.signal.str.startswith(stem)) & (r.signal != row.signal) & (r.signal.str[-1] == row.signal[-1])]
    return out, [float(x) for x in sib.IS_calmar]


def main():
    r, ret, days = load('full'); r1, _, _ = load('lag_1'); rm, _, _ = load('lag_-1')
    r1 = r1.set_index('case_id'); rm = rm.set_index('case_id')
    nul = pickle.load(open(D + 'null.pkl', 'rb'))['out']
    nd = pd.DataFrame(nul, columns=['kind', 'name', 'calmar', 'sharpe', 'hold_calmar'])
    bm = matched_baseline(r); ri = r.set_index('case_id')
    live = ret[LIVE]
    isw, hw = win(days, *BLK['IS']), win(days, *BLK['HOLD'])
    blocks = ['IS', 'T2023', 'T2024', 'T2025', 'T2026']
    out = {}
    # ---------- null summaries: best-of-N
    best = {}
    for kind, mode in [('m1', 'M1'), ('m3', 'M3')]:
        x = nd[nd.kind == kind]
        piv = x.groupby('name').calmar.apply(list)
        M = np.array([piv[n] for n in sorted(piv.index)]).T  # draws x signals
        mx = M.max(axis=1)
        cell = r[(r['mode'] == mode) & (r.rebal == 3) & (r.K == 8) & ((r.w == 1.0) if mode == 'M3' else True)]
        real_best = float(cell.IS_calmar.max())
        best[mode] = dict(null_best_of_signals_median=float(np.median(mx)), null_best_p95=float(np.quantile(mx, .95)),
                          null_best_max=float(mx.max()), real_best=real_best, p_value=float((mx >= real_best).mean()),
                          n_signals=int(M.shape[1]), draws=int(M.shape[0]),
                          null_single_median=float(np.median(M)), null_single_p95=float(np.quantile(M, .95)))
    xf = nd[nd.kind == 'flag']
    pf = xf.groupby('name').calmar.apply(list)
    best['flags'] = {n: dict(p95=float(np.quantile(v, .95)), med=float(np.median(v))) for n, v in pf.items()}
    out['null_best'] = {k: v for k, v in best.items() if k != 'flags'}
    # ---------- candidates
    rows = []
    for cid, x in ri.iterrows():
        if x['mode'] not in ('M1', 'M3', 'M4'):
            continue
        bid = bm[(bool(x.crash) or x['mode'] == 'M4', int(x.rebal), int(x.K))] if x['mode'] != 'M1' else bm[(False, int(x.rebal), int(x.K))]
        b = ri.loc[bid]
        wins = [x[f'{k}_calmar'] > b[f'{k}_calmar'] for k in blocks]
        rows.append((cid, bid, sum(wins)))
    cand = pd.DataFrame(rows, columns=['case_id', 'base', 'wins']).set_index('case_id')
    c = ri.join(cand, how='inner')
    c5 = c[c.wins == 5].copy()
    out['n_candidates_win5'] = {m: int((c5['mode'] == m).sum()) for m in ['M1', 'M3', 'M4']}
    # take best cell per (mode, signal), then top 10 by IS calmar
    top = c5.sort_values('IS_calmar', ascending=False).groupby(['mode', 'signal']).head(1).head(14)
    fin = []
    for cid, x in top.iterrows():
        nb, sib = neighbours(r, x)
        a = ret[cid]
        yr = np.array([x[f'return_{y}'] for y in range(2022, 2027)])
        lg = np.log1p(np.clip(yr, -0.99, None))
        carry = float(lg.max() / lg[lg > 0].sum()) if (lg > 0).any() else 1.0
        ix = isw
        corr_is = float(np.corrcoef(a[ix], live[ix])[0, 1]); corr_h = float(np.corrcoef(a[hw], live[hw])[0, 1])
        bl50 = 0.5 * a + 0.5 * live; blv = inv_vol_blend(a, live)
        nl = nd[(nd.kind == {'M1': 'm1', 'M3': 'm3'}.get(x['mode'], 'flag')) & (nd.name == x.signal)].calmar
        base_cell_is = float(ri.loc[x.base, 'IS_calmar'])
        fin.append(dict(
            case=cid, mode=x['mode'], signal=x.signal, rebal=int(x.rebal), K=int(x.K), w=float(x.w),
            IS_cagr=float(x.IS_cagr), IS_mdd=float(x.IS_mdd), IS_imdd=float(x.IS_imdd), IS_calmar=float(x.IS_calmar),
            IS_phase_worst_mdd=float(x.IS_phase_worst_mdd), base_IS_calmar=base_cell_is,
            calmar_blocks={k: float(x[f'{k}_calmar']) for k in blocks}, base_blocks={k: float(ri.loc[x.base, f'{k}_calmar']) for k in blocks},
            yearly={y: float(x[f'return_{y}']) for y in range(2022, 2027)}, year_carry=carry,
            nb_ratio_min=float(min([v / x.IS_calmar for v in nb])) if nb else None,
            nb_frac_ok=float(np.mean([v >= .8 * x.IS_calmar for v in nb])) if nb else None,
            sib_frac_ok=float(np.mean([v >= .8 * x.IS_calmar for v in sib])) if sib else None, n_sib=len(sib),
            null_pct_same_signal=float((nl <= x.IS_calmar).mean()) if len(nl) else None,
            lag1_IS_calmar=float(r1.loc[cid.replace('_l0', '_l1') if False else cid, 'IS_calmar']) if cid in r1.index else None,
            corr_live_IS=corr_is, corr_live_hold=corr_h,
            IS_stats=stats(a[ix]), HOLD_stats=stats(a[hw]),
            live_IS=stats(live[ix]), live_HOLD=stats(live[hw]),
            blend50_IS=stats(bl50[ix]), blend50_HOLD=stats(bl50[hw]), blendiv_IS=stats(blv[ix]), blendiv_HOLD=stats(blv[hw])))
    # lag tables: case ids differ by suffix l1/l-1
    for f in fin:
        base_id_ = f['case'][:-1] if f['case'].endswith('l0') else f['case']
        f['lag_plus1_IS_calmar'] = float(r1.loc[base_id_ + '1', 'IS_calmar']) if f['mode'] != 'M4' else None
        f['lead_minus1_IS_calmar'] = float(rm.loc[base_id_ + '-1', 'IS_calmar']) if f['mode'] != 'M4' else None
        f['lag_plus1_HOLD_calmar'] = float(r1.loc[base_id_ + '1', 'HOLDOUT_calmar']) if f['mode'] != 'M4' else None
    out['finalists'] = fin
    out['live'] = dict(IS=stats(live[isw]), HOLD=stats(live[hw]), case=LIVE)
    json.dump(out, open(D + 'final.json', 'w'), indent=1, default=float)
    print(json.dumps(out['null_best'], indent=1))
    print(out['n_candidates_win5'])
    for f in fin:
        print(f"{f['mode']} {f['signal'][:28]:28s} r{f['rebal']}K{f['K']}w{f['w']:g} IS {f['IS_cagr']:.2f}/{f['IS_mdd']:.2f}/{f['IS_calmar']:.2f} base {f['base_IS_calmar']:.2f} "
              f"nb {f['nb_frac_ok']} sib {f['sib_frac_ok']}({f['n_sib']}) nullpct {f['null_pct_same_signal']} carry {f['year_carry']:.2f} "
              f"corr {f['corr_live_IS']:.2f} | lag1 {f['lag_plus1_IS_calmar']} lead {f['lead_minus1_IS_calmar']} | HOLD {f['HOLD_stats']['cagr']:.2f}/{f['HOLD_stats']['mdd']:.2f} live {f['live_HOLD']['cagr']:.2f}/{f['live_HOLD']['mdd']:.2f}")
    # flags: compare actual vs null p95
    fl = r[r['mode'] == 'M4']; fl = fl[(fl.rebal == 3) & (fl.K == 8)]
    t = []
    for _, x in fl.iterrows():
        nb_ = best['flags'][x.signal]
        t.append((x.signal, float(x.IS_calmar), nb_['med'], nb_['p95'], float(x.HOLDOUT_calmar)))
    t.sort(key=lambda z: -z[1])
    out['flags_3_8'] = t
    json.dump(out, open(D + 'final.json', 'w'), indent=1, default=float)
    print('base 3/8 crash IS calmar', ri.loc[LIVE, 'IS_calmar'])
    for z in t[:12]:
        print('flag', z[0], 'IS %.2f null_med %.2f null_p95 %.2f hold %.2f' % z[1:])
    print('flags beating own null p95:', sum(z[1] > z[3] for z in t), 'of', len(t))


if __name__ == '__main__':
    main()
