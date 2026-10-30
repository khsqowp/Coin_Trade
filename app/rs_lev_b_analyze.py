"""BACKTESTER-B lev_loop analysis: distributions, admissibility, paired block-bootstrap, Reality Check, PBO, concentration.
python -I app/rs_lev_b_analyze.py <outdir> -> prints tables, writes <outdir>/../analysis.json"""
from __future__ import annotations
import itertools, json, os, pickle, sys
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

OUT = sys.argv[1]
TRIGS = {1: "T1 worst-hour", 2: "T2 hour-close", 0: "T0 daily-close"}
B_REPS = 2000
BLOCK = 20
SEED = 12345


def load(d, t, w):
    with open(os.path.join(OUT, f"{d}_T{t}_{w}.pkl"), "rb") as f:
        return pickle.load(f)


def ids():
    return sorted({f.split("_")[0] for f in os.listdir(OUT) if f.endswith(".pkl")})


def dist(x):
    x = np.asarray(x, float)
    return np.percentile(x, 10), np.median(x), np.percentile(x, 90)


def summarize(res):
    r = res["sc0"]["rows"]
    d = dict(term=dist(r.term), logg=dist(r.logg), mdd=dist(r.mdd), imdd=dist(r.imdd), kills=dist(r.kills), dlv=dist(r.dlv),
             g=np.median(r.avg_g), maxg=np.median(r.max_g), hloss=r.hloss.max())
    liq = {}
    for sc, v in res.items():
        rr = v["rows"]
        liq[sc] = int(((rr.liq_t > 0) | (rr.liq_f > 0)).sum()) if sc == "sc0" else int((rr.liq_f > 0).sum())
    d["liq"] = liq
    return d


def stationary_idx(n, B, rng, mean_block=BLOCK):
    p = 1.0 / mean_block
    idx = np.empty((B, n), np.int64)
    for b in range(B):
        i = rng.integers(n)
        for t in range(n):
            idx[b, t] = i
            i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return idx


def daily_lr(eq):
    e = np.maximum(eq, 1e-6)
    lr = np.diff(np.log(e), axis=1)
    return lr.mean(axis=0)


def boot_ci(dser, idx):
    m = dser[idx].mean(axis=1) * 365.0
    return np.percentile(m, [5, 50, 95]), m


def main():
    rng = np.random.default_rng(SEED)
    D = ids()
    cand = [d for d in D if d.startswith("D")]
    summ = {}
    for d in D:
        for t in TRIGS:
            for w in ("IS", "OOS", "FULL"):
                summ[(d, t, w)] = summarize(load(d, t, w))
    # ---------- tables of distributions
    lines = []
    for w in ("IS", "OOS"):
        for t in (1, 2, 0):
            lines.append(f"\n### {w} / {TRIGS[t]} (120 paths; p10 | median | p90)")
            lines.append("| id | terminal W | ann.log-growth | MDD close | MDD intraday | kills (med) | delev (med) | avg gross | max 1h loss | liq paths sc0/1/2/3/4 |")
            lines.append("|---|---|---|---|---|---|---|---|---|---|")
            for d in D:
                s = summ[(d, t, w)]
                f3 = lambda x, k=1: f"{x[0]:.{k}f}|{x[1]:.{k}f}|{x[2]:.{k}f}"
                lq = "/".join(str(s['liq'].get(sc, '-')) for sc in ("sc0", "sc1", "sc2", "sc3", "sc4"))
                lines.append(f"| {d} | {f3(s['term'], 2)} | {f3(s['logg'], 2)} | {f3(s['mdd'], 2)} | {f3(s['imdd'], 2)} | {s['kills'][1]:.0f} | {s['dlv'][1]:.0f} | {s['g']:.2f} | {s['hloss']:.2f} | {lq} |")
    # ---------- admissibility / eligibility
    adm = {}
    for d in D:
        ok = True
        for w in ("IS", "OOS"):
            for t in (1, 2):
                if sum(summ[(d, t, w)]["liq"].values()) > 0:
                    ok = False
        adm[d] = ok
    elig = {}
    for d in D:
        des_lev = None
        elig[d] = {}
        for w in ("IS", "OOS"):
            for t in (1, 2):
                elig[d][(w, t)] = summ[(d, t, w)]["g"] >= 0.90 * summ[("D00", t, w)]["g"]
    lines.append("\n### Admissibility (0 liquidations in IS+OOS x T1,T2 x all scenarios) and eligibility (avg gross >= 0.9 x D00)")
    for d in D:
        e = {f"{w}-T{t}": ("Y" if v else "n") for (w, t), v in elig[d].items()}
        lines.append(f"- {d}: admissible={adm[d]}  elig={e}  liq_total={ {w: {t: sum(summ[(d,t,w)]['liq'].values()) for t in (1,2,0)} for w in ('IS','OOS','FULL')} }")
    # ---------- paired bootstrap vs D00
    boot = {}
    series = {}
    for w in ("IS", "OOS"):
        for t in (1, 2):
            S = {d: daily_lr(load(d, t, w)["sc0"]["eq"]) for d in D}
            series[(w, t)] = S
    n_IS = len(series[("IS", 1)]["D00"]); n_OOS = len(series[("OOS", 1)]["D00"])
    idx = {"IS": stationary_idx(n_IS, B_REPS, rng), "OOS": stationary_idx(n_OOS, B_REPS, rng)}
    lines.append(f"\n### Paired block-bootstrap (stationary, mean block {BLOCK}d, {B_REPS} reps) of annualised mean log-growth difference vs D00: [5%, 50%, 95%] and point")
    lines.append("| id | win | trig | point | 5% | 50% | 95% | verdict-cell |")
    lines.append("|---|---|---|---|---|---|---|---|")
    cellv = {}
    for d in cand:
        if d == "D00":
            continue
        for w in ("IS", "OOS"):
            for t in (1, 2):
                dd = series[(w, t)][d] - series[(w, t)]["D00"]
                ci, m = boot_ci(dd, idx[w])
                v = "better" if ci[0] > 0 else ("worse" if ci[2] < 0 else "n.d.")
                cellv[(d, w, t)] = (float(dd.mean() * 365), ci.tolist(), v)
                boot[(d, w, t)] = m
                lines.append(f"| {d} | {w} | T{t} | {dd.mean()*365:+.2f} | {ci[0]:+.2f} | {ci[1]:+.2f} | {ci[2]:+.2f} | {v} |")
    verdict = {}
    for d in cand:
        if d == "D00":
            continue
        out = {}
        for w in ("IS", "OOS"):
            vs = [cellv[(d, w, t)][2] for t in (1, 2)]
            out[w] = "better" if all(v == "better" for v in vs) else ("worse" if all(v == "worse" for v in vs) else "not distinguishable")
        if out["IS"] == out["OOS"] != "not distinguishable":
            strength = "strongly supported"
        elif "not distinguishable" in (out["IS"], out["OOS"]) and (out["IS"] == out["OOS"]):
            strength = "unknown"
        else:
            strength = "weak"
        out["strength"] = strength
        verdict[d] = out
    lines.append("\n### Verdicts vs D00 (IS | OOS; better = 90% CI lower bound > 0 in BOTH T1 and T2)")
    for d, o in verdict.items():
        lines.append(f"- {d}: IS={o['IS']} OOS={o['OOS']} -> {o['strength']}; admissible={adm[d]}")
    # ---------- Reality Check (IS, T1 and T2 average statistic)
    lines.append("\n### White Reality-Check haircut (IS; stat = mean of T1,T2 annualised log-growth diff vs D00; 19 comparisons)")
    ks = [d for d in cand if d != "D00"]
    obs = {d: 0.5 * sum(cellv[(d, "IS", t)][0] for t in (1, 2)) for d in ks}
    bm = {d: 0.5 * (boot[(d, "IS", 1)] + boot[(d, "IS", 2)]) for d in ks}
    cen = {d: bm[d] - np.mean(bm[d]) for d in ks}
    mx = np.max(np.vstack([cen[d] for d in ks]), axis=0)
    thr95 = float(np.percentile(mx, 95))
    rc = {}
    for d in ks:
        p = float((mx >= obs[d]).mean())
        rc[d] = p
        lines.append(f"- {d}: IS stat {obs[d]:+.3f}/yr  RC p={p:.3f}")
    lines.append(f"- 95% max-stat haircut threshold = {thr95:+.3f}/yr (a design must exceed this to be distinguishable from the best of 19 null draws)")
    # ---------- PBO (CSCV)
    def pbo(M, S=10):
        T, N = M.shape
        blocks = np.array_split(np.arange(T), S)
        logits = []
        for comb in itertools.combinations(range(S), S // 2):
            tr = np.concatenate([blocks[i] for i in comb]); te = np.concatenate([blocks[i] for i in range(S) if i not in comb])
            sr_tr = M[tr].mean(0) / (M[tr].std(0) + 1e-12); sr_te = M[te].mean(0) / (M[te].std(0) + 1e-12)
            best = int(np.argmax(sr_tr)); rank = (sr_te < sr_te[best]).sum() + 1
            w = rank / (N + 1)
            logits.append(np.log(w / (1 - w)))
        return float((np.array(logits) <= 0).mean())
    lines.append("\n### PBO (CSCV S=10, 252 splits, 20 designs, IS mean-path daily log-returns)")
    pb = {}
    for t in (1, 2):
        M = np.column_stack([series[("IS", t)][d] for d in cand])
        pb[t] = pbo(M)
        lines.append(f"- T{t}: PBO = {pb[t]:.2f}")
    # ---------- concentration
    lines.append("\n### Concentration (average over 120 paths, sc0, FULL window; share of positive symbol contribution from top-5 symbols; top-5 trades share of summed positive trade contributions)")
    names = None
    for d in ("D00", "D02", "D08", "D12"):
        for t in (2, 0):
            r = load(d, t, "FULL")["sc0"]
            c = r["contrib"]
            pos = np.sort(c[c > 0])[::-1]
            sh = pos[:5].sum() / max(pos.sum(), 1e-12)
            tr = np.sort(r["trp"])[::-1]
            tp = tr[tr > 0]
            sh_tr = tp[:5 * 120].sum() / max(tp.sum(), 1e-12)  # top 5 per path equivalents
            net = c.sum()
            lines.append(f"- {d} T{t}: top-5 symbols = {sh*100:.0f}% of positive symbol contrib; net contrib sum {net:.2f}; top-5 trades per path = {sh_tr*100:.1f}% of positive trade contributions")
    res = dict(adm=adm, verdict=verdict, rc=rc, thr95=thr95, pbo=pb,
               cell={f"{k[0]}|{k[1]}|T{k[2]}": v for k, v in cellv.items()})
    json.dump(res, open(os.path.join(os.path.dirname(OUT), "analysis.json"), "w"), indent=1, default=float)
    print("\n".join(lines))


main()
