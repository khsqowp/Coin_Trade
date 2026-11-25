import sys, json, math, numpy as np, pandas as pd
from datetime import datetime, timezone
sys.path.insert(0, "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop")
import verify_rb246_independent as V
from scipy.stats import norm
syms = V.load_universe(); P = V.load_panel(syms); funds = [V.load_funding(s) for s in syms]
D = V.day_count(P); T = P["T"]; btc = P["btc"]
OUT = {}
def yr(ms): return datetime.fromtimestamp(ms/1000, tz=timezone.utc).year
W = {"top_k":3,"rs":84,"reg":100}     # report's RB-246 parameters
S = {"top_k":3,"rs":42,"reg":200}     # best-passing cell in my grid (for comparison)

def stats(tr): return V.metrics(tr, P["t0"], D)
def line(name, m): return f'{name:34s} n={m["n"]:5d} PF={m["PF"]:.3f} exp={m["exp_bp"]:6.1f} cum={m["cum"]:.3f} MDD={m["mdd"]:.3f} Sh={m["sharpe"]:.2f} M2={m["M2"]:.3f} p={m["p_one"]:.2e} bonf={m["bonf_pass"]} core={m["core_pass"]}'

# ---- (1) base + funding decomposition for both
res = {}
for tag, cfg in [("W", W), ("S", S)]:
    tr, info = V.run(P, cfg, funds)
    m = stats(tr); res[tag] = {"base": m, "info": info}
    print(line(f"[{tag}] base", m), info, flush=True)
    tr0, _ = V.run(P, cfg, [None]*len(syms)); m0 = stats(tr0)
    print(line(f"[{tag}] no funding", m0), flush=True)
    res[tag]["nofund"] = m0

# ---- (2) overlap / effective N for W
tr, _ = V.run(P, W, funds)
ents = np.array([x["e"] for x in tr]); nets = np.array([x["net"] for x in tr])
hold = np.array([x["k"]-x["e"] for x in tr])
conc = hold.sum() / (T)  # mean number of simultaneous open positions
uniq_bars = len(np.unique(ents))
dd = np.array([ (x["tin"]-P["t0"])//V.DAY for x in tr])
uniq_days = len(np.unique(dd))
def cluster_p(keys):
    s = pd.Series(nets).groupby(keys).mean().to_numpy()
    t = s.mean()/(s.std(ddof=1)/math.sqrt(len(s)))
    return len(s), float(norm.sf(t)), float(t)
nb, pb, tb = cluster_p(ents); nd, pdy, tdy = cluster_p(dd)
res["overlap"] = {"n_trades": len(tr), "distinct_entry_bars": uniq_bars, "distinct_entry_days": uniq_days,
                  "mean_concurrent_positions": float(conc), "avg_trades_per_entry_bar": len(tr)/uniq_bars,
                  "p_cluster_bar": pb, "t_cluster_bar": tb, "p_cluster_day": pdy, "t_cluster_day": tdy,
                  "eff_n_naive_over_cluster": len(tr)/(len(tr)/uniq_bars)}
print("overlap", json.dumps(res["overlap"], indent=1), flush=True)

# ---- (3) lookahead: truncation test on indicators
def indic(Pp):
    score = V.rs_score(Pp["C"], Pp["btc"], W["rs"]); reg = V.regime_on(Pp["C"], Pp["btc"], W["reg"])
    return score, reg, V.atr14(Pp["H"], Pp["L"], Pp["C"])
full_score, full_reg, full_atr = indic(P)
rng = np.random.default_rng(7)
cuts = sorted(rng.choice(np.arange(1200, T-1), size=25, replace=False).tolist())
mismatch = 0
for c in cuts:
    Pt = {k: (v[:c+1] if isinstance(v, np.ndarray) and v.ndim==2 else v) for k,v in P.items()}
    Pt["T"] = c+1
    s_, r_, a_ = indic(Pt)
    ok = np.array_equal(s_, full_score[:c+1], equal_nan=True) and np.array_equal(r_, full_reg[:c+1]) and np.array_equal(a_, full_atr[:c+1], equal_nan=True)
    mismatch += (not ok)
res["lookahead_truncation"] = {"cut_points": len(cuts), "mismatches": mismatch}
print("lookahead truncation", res["lookahead_truncation"], flush=True)

# ---- (4) nulls for W and S
def null_random(cfg, iters=200):
    out = []
    for i in range(iters):
        r = np.random.default_rng(1000+i)
        trr, _ = V.run(P, cfg, funds, rng=r)
        out.append(stats(trr)["exp_bp"] if trr else np.nan)
    return np.array(out)
def null_shift(cfg, iters=200):
    base_score = V.rs_score(P["C"], btc, cfg["rs"])
    out = []
    for i in range(iters):
        r = np.random.default_rng(5000+i)
        sc = np.empty_like(base_score)
        for j in range(base_score.shape[1]):
            sc[:, j] = np.roll(base_score[:, j], int(r.integers(T)))
        trr, _ = V.run(P, cfg, funds, score=sc)
        out.append(stats(trr)["exp_bp"] if trr else np.nan)
    return np.array(out)
for tag, cfg in [("W", W), ("S", S)]:
    obs = res[tag]["base"]["exp_bp"]
    nr = null_random(cfg); ns = null_shift(cfg)
    res[tag]["null_random"] = {"obs": obs, "median": float(np.nanmedian(nr)), "p95": float(np.nanpercentile(nr,95)), "p_ge_obs": float(np.nanmean(nr>=obs))}
    res[tag]["null_shift"] = {"obs": obs, "median": float(np.nanmedian(ns)), "p95": float(np.nanpercentile(ns,95)), "p_ge_obs": float(np.nanmean(ns>=obs))}
    print(tag, "random-K null", res[tag]["null_random"], flush=True)
    print(tag, "circular-shift null", res[tag]["null_shift"], flush=True)

# ---- (5) cost x2, 1-bar delay
for tag, cfg in [("W", W), ("S", S)]:
    trc, _ = V.run(P, cfg, funds, cost_rt=0.0024); mc = stats(trc)
    trd, _ = V.run(P, cfg, funds, delay=2); md = stats(trd)
    res[tag]["cost2x"] = mc; res[tag]["delay2"] = md
    print(line(f"[{tag}] cost x2", mc), flush=True)
    print(line(f"[{tag}] 1-bar delay", md), flush=True)

# ---- (6) yearly
tr, _ = V.run(P, W, funds)
ey = V.yearly(tr, "tout"); en = V.yearly(tr, "tin")
print("W yearly (exit-year sums %p):", {k:(v["n"], round(v["sum_pct"],1), round(v["wins"]/v["n"],3)) for k,v in sorted(ey.items())})
print("W yearly (entry-year):", {k:(v["n"], round(v["sum_pct"],1)) for k,v in sorted(en.items())})
res["yearly_exit"] = {int(k): v for k,v in ey.items()}; res["yearly_entry"] = {int(k): v for k,v in en.items()}
# 2022 loss anatomy
t22 = [x for x in tr if yr(x["tin"])==2022]
loss22 = [x for x in t22 if x["net"]<=0]
btc_ret = lambda x: P["C"][x["k"],btc]/P["C"][x["e"],btc]-1
anat = {"n": len(t22), "sum_pct": sum(x["net"] for x in t22)*100,
        "losers": len(loss22), "loss_sum_pct": sum(x["net"] for x in loss22)*100,
        "reasons_all": {r: sum(1 for x in t22 if x["reason"]==r) for r in ["stop","target","time"]},
        "reasons_loss": {r: sum(1 for x in loss22 if x["reason"]==r) for r in ["stop","target","time"]},
        "mean_btc_ret_in_trade_pct_2022": float(np.mean([btc_ret(x) for x in t22])*100),
        "mean_btc_ret_in_trade_pct_other": float(np.mean([btc_ret(x) for x in tr if yr(x["tin"])!=2022])*100),
        "mean_net_bp_2022": float(np.mean([x["net"] for x in t22])*1e4),
        "fund_bp_2022": float(np.mean([x["fund"] for x in t22])*1e4),
        "fund_bp_other": float(np.mean([x["fund"] for x in tr if yr(x["tin"])!=2022])*1e4),
        "months_losses": pd.Series([datetime.fromtimestamp(x["tin"]/1000,tz=timezone.utc).strftime("%Y-%m") for x in t22 if x["net"]<=0]).value_counts().head(6).to_dict(),
        "months_loss_sum_pct": (pd.Series({datetime.fromtimestamp(x["tin"]/1000,tz=timezone.utc).strftime("%Y-%m"): x["net"]*100 for x in t22}).groupby(level=0).sum().sort_values().head(6)).round(1).to_dict()}
res["loss_2022"] = anat
print("2022 anatomy", json.dumps(anat, indent=1, default=str), flush=True)

# ---- (9) concentration: per-symbol contribution and exclusion of top-3
contrib = pd.Series([x["net"] for x in tr]).groupby([x["j"] for x in tr]).agg(["sum","count","mean"])
contrib.index = [syms[i] for i in contrib.index]
contrib = contrib.sort_values("sum", ascending=False)
top3 = contrib.index[:3].tolist()
res["concentration"] = {"top3": top3, "share_of_sum_top3": float(contrib["sum"].iloc[:3].sum()/contrib["sum"].sum()), "per_symbol": contrib.round(4).to_dict("index")}
univ = np.array([s not in top3 for s in syms])
trx, _ = V.run(P, W, funds, univ=univ); mx = stats(trx)
print("top3 by net sum", top3, "share", round(res["concentration"]["share_of_sum_top3"],3))
print(line("[W] ex top-3 symbols", mx), flush=True)
res["ex_top3"] = mx
OUTP="/private/tmp/claude-501/-Users-user-CODE-Ochestration/ee6baff2-9664-4b9e-9a9e-5f263219aa7c/scratchpad/rb246_out/validate.json"
json.dump(res, open(OUTP,"w"), indent=1, default=lambda o: float(o) if isinstance(o,(np.floating,)) else (int(o) if isinstance(o,np.integer) else str(o)))
print("saved")
fund_missing=[syms[j] for j in range(len(syms)) if funds[j] is None]
n_fm=sum(1 for x in tr if syms[x["j"]] in fund_missing)
print("trades in symbols lacking funding file:", n_fm, "of", len(tr), fund_missing)
