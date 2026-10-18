"""Fixed-grid evaluation + selection protocol (IS 2022-01..2024-06 selects, OOS 2024-07+ untouched)."""
from __future__ import annotations
import itertools, json, math
import numpy as np, pandas as pd
from statistics import NormalDist
from app.rs_final_data import load_panel
from app.rs_final_engine import Sim, window_metrics, yearly_returns

IS = ("2022-01-01", "2024-06-30"); OOS = ("2024-07-01", None)
FOLDS = [("2022-01-01", "2023-04-30"), ("2023-05-01", "2024-08-31"), ("2024-09-01", None)]
SIG = {
    "S0": dict(lbs=(14,), rebal=3, K=8, band=0),
    "S1": dict(lbs=(14,), rebal=2, K=12, band=0),
    "S2": dict(lbs=(14, 28), rebal=3, K=14, band=2),
    "S3": dict(lbs=(14,), rebal=4, K=8, band=0),
    "S4": dict(lbs=(14,), rebal=3, K=12, band=2),
}
ACCT = {"ideal": dict(minn=0.0, eq0=1.0), "m5": dict(minn=5.0, eq0=142.0), "m20": dict(minn=20.0, eq0=142.0)}
KILL = dict(kill=0.35, cool=14)


def overlays():
    o = {"O0": {}, "O2": dict(regime_b=True), "O3": dict(crash_flat=True)}
    for T, cap in itertools.product((0.12, 0.15, 0.18), (1.0, 1.5, 2.0)):
        o[f"O1_T{int(T*100)}_c{cap}"] = dict(vt=T, cap=cap, lev=cap)
        o[f"O4_T{int(T*100)}_c{cap}"] = dict(vt=T, cap=cap, lev=cap, regime_b=True)
    return o


def run_cfg(S, sig: dict, ov: dict, acct: str, extra: dict | None = None):
    """phase-averaged runs; returns list of results (one per phase 0..N-1)"""
    kw = {**sig, **ov, **ACCT[acct], **KILL, **(extra or {})}
    N = kw["rebal"]
    return [S.run(phase=p, **kw) for p in range(N)]


def summarise(rs, a=None, b=None):
    ms = [window_metrics(r, a, b) for r in rs]
    if any(m is None for m in ms):
        return None
    d = {k: float(np.mean([m[k] for m in ms])) for k in ("cagr", "mdd", "imdd", "calmar", "sharpe", "worst_day")}
    d["imdd_worst_phase"] = float(max(m["imdd"] for m in ms))
    d["worst_day_min"] = float(min(m["worst_day"] for m in ms))
    d["cagr_min_phase"] = float(min(m["cagr"] for m in ms))
    return d


def avg_ret(rs):
    return np.mean([r["eq"].dropna().pct_change().fillna(0).to_numpy() for r in rs], axis=0), rs[0]["eq"].dropna().index


def full_row(S, sig, ov, acct, extra=None):
    rs = run_cfg(S, sig, ov, acct, extra)
    row = dict(IS=summarise(rs, *IS), OOS=summarise(rs, *OOS), full=summarise(rs),
               folds=[summarise(rs, *f) for f in FOLDS])
    ys = [yearly_returns(r) for r in rs]
    row["years"] = {y: float(np.mean([d[y] for d in ys])) for y in ys[0]}
    row["skip_rate"] = float(np.mean([r["skip"] / max(r["att"], 1) for r in rs]))
    row["skips"] = float(np.mean([r["skip"] for r in rs])); row["attempts"] = float(np.mean([r["att"] for r in rs]))
    row["kills"] = float(np.mean([r["kills"] for r in rs])); row["liq"] = any(r["liq"] for r in rs)
    row["npos"] = float(np.mean([r["npos"] for r in rs]))
    row["flat_frac"] = float(np.mean([(r["expo"].loc[r["eq"].dropna().index] == 0).mean() for r in rs]))
    row["gross"] = float(np.mean([r["expo"].loc[r["eq"].dropna().index].mean() for r in rs]))
    return row, rs


def deflated_sharpe(sr_hat, T, sr_trials, skew, kurt):
    """Bailey & Lopez de Prado DSR. sr_* are per-period (daily) Sharpe ratios."""
    nd = NormalDist(); N = len(sr_trials); g = 0.5772156649
    sd = float(np.std(sr_trials, ddof=1))
    sr0 = sd * ((1 - g) * nd.inv_cdf(1 - 1 / N) + g * nd.inv_cdf(1 - 1 / (N * math.e)))
    den = math.sqrt(max(1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2, 1e-9))
    return nd.cdf((sr_hat - sr0) * math.sqrt(T - 1) / den), sr0


def main():
    S = Sim(load_panel())
    ov = overlays()
    table = {}; rets = {}
    n = 0
    for sname, sg in SIG.items():
        for oname, o in ov.items():
            key = f"{sname}|{oname}"
            row, rs = full_row(S, sg, o, "ideal")
            for ac in ("m5", "m20"):
                r2, _ = full_row(S, sg, o, ac)
                row[ac] = dict(full=r2["full"], IS=r2["IS"], OOS=r2["OOS"], skip_rate=r2["skip_rate"], skips=r2["skips"],
                               attempts=r2["attempts"], kills=r2["kills"], flat_frac=r2["flat_frac"], npos=r2["npos"], years=r2["years"])
            table[key] = row; n += 1
            ret, idx = avg_ret(rs)
            rets[key] = pd.Series(ret, index=idx)
    # ---- selection on IS
    base = table["S0|O0"]
    def okIS(r):
        return r["IS"]["imdd"] <= 0.25 and r["IS"]["worst_day_min"] > -0.07
    cand = sorted([k for k, r in table.items() if okIS(r)], key=lambda k: -table[k]["IS"]["calmar"])
    # multiple testing
    isr = {k: rets[k][(rets[k].index >= pd.Timestamp(IS[0], tz="UTC")) & (rets[k].index <= pd.Timestamp(IS[1], tz="UTC"))] for k in rets}
    sr_trials = [float(v.mean() / v.std()) for v in isr.values() if v.std() > 0]
    dsr = {}
    for k in cand[:10]:
        v = isr[k]; sr = float(v.mean() / v.std())
        sk = float(((v - v.mean()) ** 3).mean() / v.std() ** 3); ku = float(((v - v.mean()) ** 4).mean() / v.std() ** 4)
        p, sr0 = deflated_sharpe(sr, len(v), sr_trials, sk, ku)
        dsr[k] = dict(sr_ann=sr * math.sqrt(365), dsr=p, sr0_ann=sr0 * math.sqrt(365))
    bi, bo = base["IS"], base["OOS"]
    beat = {k: (r["IS"]["calmar"] > bi["calmar"] and r["OOS"]["calmar"] > bo["calmar"]) for k, r in table.items()}
    beat_cagr = {k: (r["IS"]["cagr"] > bi["cagr"] and r["OOS"]["cagr"] > bo["cagr"]) for k, r in table.items()}
    beat_both = {k: beat[k] and beat_cagr[k] for k in table}
    out = dict(n_configs=n, n_sims_ideal=sum(len(range(SIG[k.split('|')[0]]['rebal'])) for k in table) * 3,
               candidates_IS_filter=cand, dsr=dsr, frac_beat_calmar=float(np.mean(list(beat.values()))),
               frac_beat_calmar_and_cagr=float(np.mean(list(beat_both.values()))),
               n_pass_filter=len(cand), sr_trial_sd_ann=float(np.std(sr_trials) * math.sqrt(365)),
               beat_calmar=[k for k, v in beat.items() if v], table=table)
    json.dump(out, open("docs/research/final_grid.json", "w"), default=float, separators=(",", ":"))
    pd.to_pickle(rets, "/private/tmp/claude-501/-Users-user-Desktop-CODE-Ochestration/20fd8e9e-6d26-4ff1-a6b5-39a3bd8d3e48/scratchpad/rets.pkl")
    print("configs", n, "pass IS filter", len(cand), "beat base Calmar IS&OOS", out["frac_beat_calmar"], "and CAGR", out["frac_beat_calmar_and_cagr"])
    def p(r):
        f = lambda w: f"{w['cagr']*100:5.1f}/{w['imdd']*100:4.1f}/{w['calmar']:.2f}"
        return f"IS {f(r['IS'])} OOS {f(r['OOS'])} full {f(r['full'])} wpMDD {r['full']['imdd_worst_phase']*100:4.1f}"
    print("BASE", p(base))
    for k in cand[:15]:
        r = table[k]
        print(f"{k:16s} {p(r)} | m5 skip {r['m5']['skip_rate']*100:4.1f}% m5full {r['m5']['full']['cagr']*100:5.1f} | dsr {dsr[k]['dsr']:.2f}" if k in dsr else f"{k:16s} {p(r)}")
    print("top by OOS Calmar among all:")
    for k in sorted(table, key=lambda k: -table[k]["OOS"]["calmar"])[:8]:
        print(f"{k:16s} {p(table[k])}")


if __name__ == "__main__":
    main()
