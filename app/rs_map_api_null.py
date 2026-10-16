"""Random-signal nulls (turnover-matched AR(1) scores / spell-shuffled flags). 4 workers max. Output scratch pickle."""
from __future__ import annotations
import sys, time, pickle
import multiprocessing as mp
import numpy as np, pandas as pd
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim, _sim, params
from app.rs_map_api_feat import rank_z
from app.rs_map_api_run import returns
from app.rs_map_api_stats import D, stats, win, BLK

G = {}


def init():
    sim = Sim(load_panel())
    z = np.load(D + 'features.npz')
    G['sim'] = sim
    G['sig'] = {k[2:]: z[k] for k in z.files if k.startswith('s_')}
    G['flg'] = {k[2:]: z[k] for k in z.files if k.startswith('g_')}
    G['d0'] = sim.d_start()
    G['mom14'] = sim.signal((14,))
    days = sim.days[G['d0']:]
    G['isw'] = np.asarray(win(days.tz_localize(None), *BLK['IS']))
    G['hw'] = np.asarray(win(days.tz_localize(None), *BLK['HOLD']))


def _init(rho):
    init(); G['rho'] = rho


def run_score(score, flag, r, k):
    sim, d0 = G['sim'], G['d0']
    rets = []
    for ph in range(r):
        eq, _, _, _ = _sim(sim.H, sim.L, sim.C, sim.FD, np.ascontiguousarray(score), np.asarray(flag, float),
                           params(rebal=r, K=k, lev=1, deploy=1, cost=.001, fund=1, phase=ph), sim.minj(0), sim.step_j, d0, sim.nd)
        rets.append(returns(eq, d0))
    return np.mean(rets, axis=0)


def rho_of(a, mask_days):
    rk = pd.DataFrame(a).rank(axis=1).to_numpy()
    c = []
    for i in range(1, len(a)):
        if mask_days[i]:
            x, y = rk[i], rk[i - 1]; ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() > 8:
                c.append(np.corrcoef(x[ok], y[ok])[0, 1])
    rs = float(np.nanmean(c))
    return float(np.clip(2 * np.sin(np.pi * rs / 6), 0, 0.999))


def ar1(shape, rho, mask, rng):
    out = np.empty(shape); e = rng.standard_normal(shape)
    out[0] = e[0]
    s = np.sqrt(1 - rho * rho)
    for i in range(1, shape[0]):
        out[i] = rho * out[i - 1] + s * e[i]
    out[~mask] = np.nan
    return out


def task(t):
    kind, name, seed, r, k, w = t
    rng = np.random.default_rng(seed)
    rho = G['rho'][name] if 'rho' in G and name in G['rho'] else None
    if kind == 'flag':
        f = G['flg'][name].astype(float)
        # shuffle spell order
        edges = np.flatnonzero(np.diff(np.r_[0, f, 0]) != 0)
        v = f.copy()
        chg = np.flatnonzero(np.diff(f) != 0) + 1
        spells = np.split(f, chg)
        order = rng.permutation(len(spells))
        nf = np.concatenate([spells[i] for i in order])
        ret = run_score(G['mom14'], np.maximum(nf, G['sim'].crash), r, k)
    else:
        if rho is None:
            rho = rho_of(G['sig'][name], np.ones(len(G['sig'][name]), bool))
        sig = G['sig'][name]
        mask = np.isfinite(sig)
        rnd = ar1(sig.shape, rho, mask, rng)
        if kind == 'm1':
            ret = run_score(rnd, np.zeros(G['sim'].nd), r, k)
        else:
            ret = run_score(G['mom14'] + w * rank_z(rnd), G['sim'].crash.astype(float), r, k)
    isr = ret[G['isw']]
    st = stats(isr)
    return kind, name, st['calmar'], st['sharpe'], stats(ret[G['hw']])['calmar']


def main():
    draws = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    init()
    names = sorted(G['sig'])
    rho = {}
    isd = np.asarray(win(G['sim'].days.tz_localize(None), *BLK['IS']))
    for n in names:
        rho[n] = rho_of(G['sig'][n], isd)
    G['rho'] = rho
    flags = sorted(G['flg'])
    tasks = []
    for n in names:
        for d in range(draws):
            tasks.append(('m1', n, 1000 + d, 3, 8, 0.0))
            tasks.append(('m3', n, 5000 + d, 3, 8, 1.0))
    for n in flags:
        for d in range(min(draws, 200)):
            tasks.append(('flag', n, 9000 + d, 3, 8, 0.0))
    print('tasks', len(tasks), flush=True)
    t0 = time.time(); out = []
    with mp.get_context('spawn').Pool(4, initializer=_init, initargs=(rho,)) as p:
        for i, o in enumerate(p.imap_unordered(task, tasks, chunksize=64), 1):
            out.append(o)
            if i % 5000 == 0:
                print(i, time.time() - t0, flush=True)
    pickle.dump(dict(out=out, rho=rho), open(D + 'null.pkl', 'wb'))
    print('done', time.time() - t0)


if __name__ == '__main__':
    main()
