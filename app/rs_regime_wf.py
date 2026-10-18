"""Phase-averaged walk-forward of the two surviving regime families (research only).
Phase = rebalance start offset (0..R-1 days); every number is the mean over phases, so a lucky rebalance phase can't carry it."""
from __future__ import annotations
import itertools, json
import numpy as np, pandas as pd
from app.rs_regime_lib import Engine, load_cache

c, f, _ = load_cache()
BTC = c["BTC"]
M14 = BTC.pct_change(14).to_numpy()
def sma_up(n): return (BTC / BTC.rolling(n, min_periods=n).mean() - 1).to_numpy() > 0
START = pd.Timestamp("2022-01-04")  # common window start for every phase
ENG = {}
def eng(off):
    if off not in ENG:
        ENG[off] = Engine(c, f, start=(pd.Timestamp("2022-01-01") + pd.Timedelta(days=off)).strftime("%Y-%m-%d"))
    return ENG[off]

def design_w(e, d, K, R):
    base = e.book(14, K, R)[0]
    kind = d[0]
    if kind == "base": return base
    if kind == "rev":    # ("rev", thr, Lrev)
        fl = np.isfinite(M14) & (M14 < d[1]); return np.where(fl[:, None], -e.book(d[2], K, R)[0], base)
    if kind == "flat":
        fl = np.isfinite(M14) & (M14 < d[1]); return np.where(fl[:, None], 0.0, base)
    if kind == "trend":  # ("trend", n, Lalt)
        up = sma_up(d[1]); return np.where(up[:, None], e.book(d[2], K, R)[0], base)
    if kind == "combo":  # ("combo", n, Lalt, thr, Lrev)
        up = sma_up(d[1]); b = np.where(up[:, None], e.book(d[2], K, R)[0], base)
        fl = np.isfinite(M14) & (M14 < d[3]); return np.where(fl[:, None], -e.book(d[4], K, R)[0], b)
    raise ValueError(kind)

def net_series(e, w, with_funding=True):
    delta = np.abs(np.diff(w, axis=0, prepend=np.zeros((1, w.shape[1])))).sum(axis=1)
    earned = np.vstack([np.zeros((1, w.shape[1])), w[:-1]]); to = np.r_[0, delta[:-1]]
    net = (earned * e.ret).sum(1) - to * 0.001
    if with_funding: net = net - (earned * e.funding.to_numpy()).sum(1)
    return pd.Series(net, index=c.index).loc[START:], pd.Series(to, index=c.index).loc[START:], pd.Series(np.abs(earned).sum(1), index=c.index).loc[START:]

def stats(r):
    if len(r) < 30: return dict(CAGR=np.nan, MDD=np.nan, Calmar=np.nan, Sharpe=np.nan, worst=np.nan)
    eq = (1 + r).cumprod(); y = len(r) / 365
    cagr = eq.iloc[-1] ** (1 / y) - 1; mdd = (1 - eq / eq.cummax().clip(lower=1)).max()
    return dict(CAGR=cagr, MDD=mdd, Calmar=cagr / mdd if mdd > 0 else np.nan,
                Sharpe=r.mean() / r.std() * np.sqrt(365), worst=r.min())

WINDOWS = {"TRAIN": ("2022-01-04", "2024-06-30"), "OOS": ("2024-07-01", "2030-01-01"), "FULL": ("2022-01-04", "2030-01-01"),
           "F2023": ("2023-01-01", "2023-12-31"), "F2024": ("2024-01-01", "2024-12-31"), "F2025+": ("2025-01-01", "2030-01-01")}
_cache = {}
def evaluate(d, K=12, R=2):
    key = (d, K, R)
    if key in _cache: return _cache[key]
    out = {}
    phases = []
    for off in range(R):
        e = eng(off); r, to, gr = net_series(e, design_w(e, d, K, R))
        phases.append((r, to, gr))
    for name, (a, b) in WINDOWS.items():
        ss = [stats(r.loc[a:b]) for r, _, _ in phases]
        out[name] = {k: float(np.nanmean([s[k] for s in ss])) for k in ss[0]}
        out[name]["MDD_worstphase"] = float(np.nanmax([s["MDD"] for s in ss]))
        out[name]["CAGR_minphase"] = float(np.nanmin([s["CAGR"] for s in ss]))
    yr = {}
    for y in range(2022, 2027):
        v = [((1 + r.loc[str(y)]).prod() - 1) for r, _, _ in phases]; yr[y] = float(np.mean(v))
    out["years"] = yr
    yrs = len(phases[0][0]) / 365
    out["turnover_x_yr"] = float(np.mean([t.sum() / yrs for _, t, _ in phases]))
    out["time_in_mkt"] = float(np.mean([(g > 0.05).mean() for _, _, g in phases]))
    ex = [r[r.index.year != 2024] for r, _, _ in phases]
    out["ex2024"] = {k: float(np.mean([stats(x)[k] for x in ex])) for k in ("CAGR", "MDD", "Calmar", "Sharpe")}
    _cache[key] = out
    return out

def fmt(name, o):
    return (f"{name:34s} TR {o['TRAIN']['CAGR']*100:5.1f}/{o['TRAIN']['MDD']*100:4.1f}/{o['TRAIN']['Calmar']:4.2f} "
            f"OOS {o['OOS']['CAGR']*100:5.1f}/{o['OOS']['MDD']*100:4.1f}/{o['OOS']['Calmar']:4.2f} "
            f"FULL {o['FULL']['CAGR']*100:5.1f}/{o['FULL']['MDD']*100:4.1f}/{o['FULL']['Calmar']:4.2f} Sh {o['FULL']['Sharpe']:.2f} "
            f"worst {o['FULL']['worst']*100:.1f} MDDmaxph {o['FULL']['MDD_worstphase']*100:.1f} "
            f"| yrs " + " ".join(f"{y%100}:{v*100:+.0f}" for y, v in o['years'].items()) +
            f" | exCal2024 {o['ex2024']['CAGR']*100:.1f}/{o['ex2024']['MDD']*100:.1f} | to {o['turnover_x_yr']:.0f}x tim {o['time_in_mkt']*100:.0f}%")

FAMILY = ([("base",)] + [("rev", t, L) for t in (-0.05, -0.075, -0.1, -0.125, -0.15) for L in (3, 5, 7)]
          + [("flat", t) for t in (-0.05, -0.1)]
          + [("trend", n, L) for n in (100, 150, 200, 250) for L in (21, 28, 35)]
          + [("combo", n, 28, t, 5) for n in (150, 200) for t in (-0.075, -0.1)])

def walk_forward(K, R):
    print(f"\n=== walk-forward K={K} R={R}; family size {len(FAMILY)} (phase-averaged) ===")
    res = []
    for fold, (tr_end, te_a, te_b) in {"OOS 2024-07+": ("2024-06-30", "2024-07-01", "2030-01-01"),
                                      "2023": ("2022-12-31", "2023-01-01", "2023-12-31"),
                                      "2024": ("2023-12-31", "2024-01-01", "2024-12-31"),
                                      "2025+": ("2024-12-31", "2025-01-01", "2030-01-01")}.items():
        scored = []
        for d in FAMILY:
            e = [net_series(eng(o), design_w(eng(o), d, K, R))[0] for o in range(R)]
            trs = [stats(r.loc["2022-01-04":tr_end]) for r in e]
            tes = [stats(r.loc[te_a:te_b]) for r in e]
            tr = {k: np.mean([s[k] for s in trs]) for k in ("CAGR", "MDD", "Calmar")}
            te = {k: np.mean([s[k] for s in tes]) for k in ("CAGR", "MDD", "Calmar")}
            scored.append((d, tr, te))
        ok = [s for s in scored if s[1]["MDD"] <= 0.25]
        best = max(ok, key=lambda s: s[1]["Calmar"])
        b = [s for s in scored if s[0] == ("base",)][0]
        rank = sorted(ok, key=lambda s: -s[1]["Calmar"]).index(best)
        beat = np.mean([s[2]["Calmar"] > b[2]["Calmar"] for s in scored if s[0] != ("base",)])
        print(f"{fold:13s} pick {str(best[0]):34s} train Calmar {best[1]['Calmar']:.2f} | TEST cagr/mdd/calmar "
              f"{best[2]['CAGR']*100:5.1f}/{best[2]['MDD']*100:4.1f}/{best[2]['Calmar']:.2f}  vs base "
              f"{b[2]['CAGR']*100:5.1f}/{b[2]['MDD']*100:4.1f}/{b[2]['Calmar']:.2f} | share of family beating base on test Calmar {beat:.0%}")
        res.append((fold, best[0]))
    return res

if __name__ == "__main__":
    for K, R in ((12, 2), (12, 3), (8, 3)):
        print(f"\n##### K={K} R={R}")
        for d in [("base",), ("rev", -0.1, 5), ("rev", -0.075, 5), ("rev", -0.1, 3), ("rev", -0.1, 7), ("flat", -0.1),
                  ("trend", 200, 28), ("trend", 150, 28), ("trend", 100, 28), ("trend", 200, 35),
                  ("combo", 200, 28, -0.1, 5)]:
            print(fmt(str(d), evaluate(d, K, R)))
        walk_forward(K, R)
