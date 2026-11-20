"""A1 step 2: White Reality Check, Hansen SPA (stationary bootstrap, 2000 draws, zero benchmark), Deflated Sharpe."""
import json
import numpy as np, pandas as pd
from scipy_free_stats import norm_cdf, norm_ppf
from lib import *

B, MEAN_BLOCK, SEED = 2000, 10, 20261120
EULER = 0.5772156649015329

def stationary_idx(T, B, mean_block, rng):
    p = 1.0 / mean_block
    new = rng.random((B, T)) < p; new[:, 0] = True
    start = rng.integers(0, T, (B, T))
    idx = np.where(new, start, 0)
    # propagate: idx[t] = idx[t-1]+1 unless new
    out = np.empty((B, T), dtype=np.int64); out[:, 0] = idx[:, 0]
    for t in range(1, T):
        out[:, t] = np.where(new[:, t], idx[:, t], (out[:, t - 1] + 1) % T)
    return out

def main():
    M = pd.read_csv(HERE / "a1_daily_pnl_matrix.csv", index_col=0, parse_dates=True)
    rows = load_summary()
    summ = {(r["strategy_id"], r["timeframe"]): r for r in rows}
    X = M.to_numpy(float); T, K = X.shape
    keep = X.std(0) > 0
    rng = np.random.default_rng(SEED)
    idx = stationary_idx(T, B, MEAN_BLOCK, rng)
    dbar = X.mean(0)
    boot = np.empty((B, K))
    for c in range(0, B, 200):
        boot[c:c + 200] = X[idx[c:c + 200]].mean(1)
    rt = np.sqrt(T)
    omega = rt * boot.std(0, ddof=1); omega[omega == 0] = np.nan
    # RC
    rc_stat_k = rt * dbar
    rc_null = (rt * (boot - dbar))[:, keep].max(1)
    rc_stat = max(rc_stat_k[keep].max(), 0.0)
    rc_p = float(np.mean(rc_null >= rc_stat))
    # SPA (Hansen 2005, consistent mu_c)
    t_k = rc_stat_k / omega
    thresh = -np.sqrt(omega ** 2 / T * 2 * np.log(np.log(T)))
    # Hansen (2005) consistent estimator: mu_c = dbar for models clearly inferior (dbar <= -A_k), else 0.
    mu_c = np.where(dbar <= thresh, dbar, 0.0)
    z = rt * (boot - dbar + mu_c) / omega
    z = np.where(keep, z, -np.inf)
    spa_null = np.maximum(z.max(1), 0.0)
    spa_stat = max(np.nanmax(np.where(keep, t_k, -np.inf)), 0.0)
    spa_p = float(np.mean(spa_null >= spa_stat))
    best = int(np.nanargmax(np.where(keep, dbar, -np.inf)))
    # DSR
    ledger_n = int(sum(int(float(r["n_candidates_tested"] or 0)) for r in rows if r["status"] in ("DONE", "INELIGIBLE")))
    n_rows = sum(r["status"] == "DONE" for r in rows)
    N = ledger_n
    # per-row own TEST window (days between first and last test timestamp across symbols)
    wins = {}
    def window(tf):
        if tf not in wins:
            fr = test_frames(tf)
            wins[tf] = (min(ts[0] for _, ts in fr.values()).floor("D"), max(ts[-1] for _, ts in fr.values()).floor("D"))
        return wins[tf]
    srs, own = [], {}
    for j, col in enumerate(M.columns):
        sid, tf = col.split("|"); a, b = window(tf)
        x = M[col].loc[a:b].to_numpy(float)
        own[col] = x
        srs.append(x.mean() / x.std(ddof=1) if x.std() > 0 else np.nan)
    srs = np.array(srs); var_sr = float(np.nanvar(srs, ddof=1))
    sr0 = np.sqrt(var_sr) * ((1 - EULER) * norm_ppf(1 - 1 / N) + EULER * norm_ppf(1 - 1 / (N * np.e)))
    def dsr(x, N=N):
        sr0 = np.sqrt(var_sr) * ((1 - EULER) * norm_ppf(1 - 1 / N) + EULER * norm_ppf(1 - 1 / (N * np.e)))
        sd = x.std(ddof=1); sr = x.mean() / sd; n = len(x)
        z_ = (x - x.mean()) / sd; sk = float((z_ ** 3).mean()); ku = float((z_ ** 4).mean())
        den = np.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr ** 2, 1e-12))
        return sr, sk, ku, norm_cdf((sr - sr0) * np.sqrt(n - 1) / den), n
    res = []
    cols = list(M.columns)
    for sid in CANDS:
        tf, params, r = candidate_row(sid, rows)
        j = cols.index(f"{sid}|{tf}")
        p_rc = float(np.mean(rc_null >= rc_stat_k[j]))               # single-step adjusted RC p for this row
        p_spa = float(np.mean(spa_null >= max(t_k[j], 0.0)))         # same, studentized + recentred (SPA)
        sr, sk, ku, d, n = dsr(own[cols[j]])
        d_own = dsr(own[cols[j]], N=max(int(float(r['n_candidates_tested'])), 2))[3]
        fail = (p_rc > .10) or (p_spa > .10) or (d < .95)
        res.append(dict(strategy_id=sid, timeframe=tf, test_return=float(r["test_return"]), mean_daily_pct=dbar[j],
                        rc_adj_p=p_rc, spa_adj_p=p_spa, daily_sr=sr, skew=sk, kurt=ku, n_days=n, sr0=sr0, dsr=d, dsr_info_only_own_grid_N=d_own,
                        rank_by_mean=int((dbar > dbar[j]).sum() + 1), A1="FAIL" if fail else "PASS"))
    pd.DataFrame(res).to_csv(HERE / "a1_results.csv", index=False)
    fam = dict(T_days=T, K_rows=K, K_nonconstant=int(keep.sum()), B=B, mean_block=MEAN_BLOCK, seed=SEED,
               family_rc_p=rc_p, family_spa_p=spa_p, best_row=cols[best], best_row_mean_daily_pct=float(dbar[best]),
               N_trials=N, N_note=f"sum of n_candidates_tested (grid points) over {n_rows} DONE rows + INELIGIBLE rows (rows with implemented plugin); NO_PLUGIN excluded; TIMEOUT row has no count",
               var_sr_across_rows=var_sr, sr0=float(sr0))
    json.dump(fam, open(HERE / "a1_family.json", "w"), indent=1)
    print(json.dumps(fam, indent=1)); print(pd.DataFrame(res).to_string())

if __name__ == "__main__":
    main()
