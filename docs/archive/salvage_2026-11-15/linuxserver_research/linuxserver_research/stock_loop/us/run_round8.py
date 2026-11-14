"""Round 8: longer-hold family US-36..US-41. DEV ONLY. python -m us.run_round8"""
import time, resource, sys, json
from .common import *  # noqa
from .hyp import lag
from .hyp4 import frozen_mask, top_frac, FREEZE
from .hyp6 import regime
from .hyp7 import mem_elig
from .run_round import World, prev_ps

HOLDS = (10, 20, 40)
SECT = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]


def universe(W, u):
    return mem_elig(W) if u == "MEM" else frozen_mask(W.P, FREEZE[u], 100)


def stag_days(valid_any, step=20):
    first = int(np.argmax(valid_any))
    d = np.zeros(len(valid_any), bool)
    d[first::step] = True
    return d


def score(W, kind):
    P = W.P
    if kind == "S126":
        return W.f("mom126", lambda: P.close / lag(P.close, 126) - 1)
    if kind == "S121":
        return W.f("mom121", lambda: lag(P.close, 21) / lag(P.close, 252) - 1)
    if kind == "SV":
        def f():
            r = np.full(P.close.shape, np.nan); r[1:] = P.close[1:] / P.close[:-1] - 1
            sd = pd.DataFrame(r).rolling(126, min_periods=100).std().to_numpy()
            return (P.close / lag(P.close, 126) - 1) / sd
        return W.f("sv", f)
    raise KeyError(kind)


def stock_ev(W, u, kind, h, spy_filter=False, dip=False):
    P = W.P
    el = universe(W, u)
    days = stag_days(el.any(axis=1))
    if spy_filter:
        days &= np.nan_to_num(regime(W, "a"), nan=0).astype(bool)
    mask = top_frac(score(W, kind), el, 0.25) & days[:, None]
    if dip:
        mask &= (W.f("rsi2", lambda: F.rsi(P.close, 2)) < 5)
    return fixed_events(P, mask, ("close", 0), ("close", h), el), P, el


def etf_mom(W, h):
    E = W.E
    cols = [E.codes.index(s) for s in SECT]
    sc = np.full(E.close.shape, np.nan)
    r = E.close / lag(E.close, 126) - 1
    sc[:, cols] = r[:, cols]
    ok = np.isfinite(sc)
    days = stag_days(ok.any(axis=1))
    rank = np.argsort(np.argsort(np.where(ok, -sc, np.inf), axis=1, kind="stable"), axis=1)
    mask = (rank < 3) & ok & days[:, None]
    return fixed_events(E, mask, ("close", 0), ("close", h), None), E, ok


def etf_trend(W, sym, sma, h=20):
    E = W.E
    j = E.codes.index(sym)
    s = F.sma(E.close[:, [j]], sma)[:, 0]
    sig = np.isfinite(s) & (E.close[:, j] > s)
    days = stag_days(np.isfinite(s))
    m = np.zeros(E.close.shape, bool)
    m[:, j] = sig & days
    return fixed_events(E, m, ("close", 0), ("close", h), None), E, None


def registry():
    R = []   # (rid, family, group-key, universe tag, N, builder)
    for fam, kind, sf in (("US-36", "S126", False), ("US-37", "S121", False), ("US-38", "S126", True), ("US-39", "SV", False)):
        for h in HOLDS:
            for u in ("MEM", "F14", "F18"):
                R.append((f"{fam}-h{h}-{u}", fam, f"{fam}-h{h}", u, 10, lambda W, u=u, k=kind, h=h, sf=sf: stock_ev(W, u, k, h, sf)))
    for h, N in ((20, 3), (40, 6)):
        R.append((f"US-40-secmom-h{h}", "US-40", f"US-40-secmom-h{h}", "ETF", N, lambda W, h=h: etf_mom(W, h)))
    for sym in ("SPY", "QQQ", "IWM"):
        for sm in (100, 200):
            R.append((f"US-40-trend-{sym}-sma{sm}", "US-40", f"US-40-trend-{sym}-sma{sm}", "ETF", 1, lambda W, s=sym, m=sm: etf_trend(W, s, m)))
    for u in ("MEM", "F14", "F18"):
        R.append((f"US-41-h40-{u}", "US-41", "US-41-h40", u, 10, lambda W, u=u: stock_ev(W, u, "S126", 40, False, True)))
    return R


def nw_alpha(y, x, lags=10):
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b
    Xu = X * u[:, None]
    S = Xu.T @ Xu
    for l in range(1, lags + 1):
        G = Xu[l:].T @ Xu[:-l]
        S += (1 - l / (lags + 1)) * (G + G.T)
    XtXi = np.linalg.inv(X.T @ X)
    cov = XtXi @ S @ XtXi
    return float(b[0] * 252), float(b[0] / np.sqrt(cov[0, 0])), float(b[1])


def mtm(ev, P, N):
    T = P.close.shape[0]
    acc = pf.select_trades(ev, N, seed=0)
    sel = ev.subset(acc)
    daily = np.zeros(T)
    for ti, ci, xs, c in zip(sel.ti, sel.ci, sel.x_slot, sel.cost):
        b = (xs - 1) // 2
        r = P.close[ti + 1:b + 1, ci] / P.close[ti:b, ci] - 1
        daily[ti + 1:b + 1] += np.nan_to_num(r) / N
        daily[b] -= c / N
    lo, hi = int(sel.ti.min()) + 1, int(((sel.x_slot - 1) // 2).max())
    return daily, lo, hi, len(sel)


def perf(d):
    d = np.asarray(d, float)
    sd = d.std()
    eq = np.cumprod(1 + d)
    return dict(sharpe=float(d.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan"), ann=float(d.mean() * 252),
                maxdd=float((eq / np.maximum.accumulate(eq) - 1).min()))


def run_one(rid, N, ev, Pq, elig, W, split):
    s = es.summarize(ev, split)
    month = (ev.dates.year * 12 + ev.dates.month).to_numpy()
    _, s["t_month"] = es.cluster_t(ev.net, month)
    s["p_month"] = es.t_to_p(s["t_month"])
    _, s["t_block"] = block_t(ev)
    m2, t2 = es.cluster_t(ev.net - ev.cost, month)
    s["mean_2x"], s["t_2x_month"] = m2, t2
    s["mean_3x"] = float((ev.net - 2 * ev.cost).mean())
    s["mean_after_tax_upper"] = float(0.78 * ev.net.mean()) if ev.net.mean() > 0 else float(ev.net.mean())
    s.update(extras(ev, Pq))
    s["max_conc_all"] = pf.max_concurrent(ev)
    d, lo, hi, nacc = mtm(ev, Pq, N)
    sl = slice(lo, hi + 1)
    s["port"] = perf(d[sl]); s["port"]["n_accepted"] = nacc
    s["port"]["year_ret"] = {int(y): float(np.prod(1 + d[sl][Pq.dates[sl].year == y]) - 1) for y in sorted(set(Pq.dates[sl].year))}
    spy = W.E.close[:, W.E.codes.index("SPY")]
    spyr = np.full(len(spy), np.nan); spyr[1:] = spy[1:] / spy[:-1] - 1
    s["spy"] = perf(np.nan_to_num(spyr[sl]))
    if elig is None:           # ETF family: benchmark = equal weight of the traded ETFs (or the single ETF)
        cols = sorted(set(ev.ci.tolist()))
        r = np.full(Pq.close.shape, np.nan); r[1:] = Pq.close[1:] / Pq.close[:-1] - 1
        bh = np.nanmean(r[:, cols], axis=1)
    else:
        r = np.full(Pq.close.shape, np.nan); r[1:] = Pq.close[1:] / Pq.close[:-1] - 1
        e1 = np.zeros_like(elig); e1[1:] = elig[:-1]
        bh = np.nanmean(np.where(e1, r, np.nan), axis=1)
    s["bh"] = perf(np.nan_to_num(bh[sl]))
    a, at, b = nw_alpha(d[sl], spyr[sl])
    s["alpha_ann"], s["alpha_t"], s["beta"] = a, at, b
    s["exposure"] = float(np.mean(np.abs(d[sl]) > 0))
    s["verdict"] = "advance" if (s["mean"] > 0 and s["t_month"] >= 3 and s.get("h1", -1) > 0 and s.get("h2", -1) > 0) else (
        "hurts" if s["mean"] < 0 and s["t_month"] <= -3 else "noise")
    return s


def gate(res):
    out = {}
    groups = {}
    for rid, s in res.items():
        groups.setdefault(s["gkey"], {})[s["univ"]] = s
    for g, d in groups.items():
        if "ETF" in d:
            s = d["ETF"]
            ok = s["verdict"] == "advance" and s["mean_2x"] > 0 and s["port"]["sharpe"] > s["bh"]["sharpe"]
            out[g] = dict(PASS=bool(ok))
            continue
        if not all(u in d for u in ("MEM", "F14", "F18")):
            continue
        c1 = all(d[u]["mean"] > 0 and d[u]["t_month"] >= 2 and d[u]["mean_2x"] > 0 for u in d)
        c2 = all(d[u]["port"]["sharpe"] > d[u]["bh"]["sharpe"] and d[u]["alpha_ann"] > 0 for u in d) and d["MEM"]["alpha_t"] >= 2
        c3 = d["MEM"].get("top5_share", 9) <= 0.40
        c4 = d["MEM"]["verdict"] == "advance"
        out[g] = dict(c1_pos_t2_2x=bool(c1), c2_beats_bh_alpha=bool(c2), c3_top5=bool(c3), c4_stage1_mem=bool(c4), PASS=bool(c1 and c2 and c3 and c4))
    return out


def main():
    out = ROOT / "results" / "US_round8.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit("exists")
    resources_ok()
    t0 = time.time()
    P, E = load_world()
    W = World(P, E)
    res = {}
    for rid, fam, gkey, u, N, fn in registry():
        resources_ok()
        ev, Pq, elig = fn(W)
        sp = ev.dates.min() + (ev.dates.max() - ev.dates.min()) / 2
        s = run_one(rid, N, ev, Pq, elig, W, sp)
        s.update(family=fam, gkey=gkey, univ=u, N=N)
        res[rid] = s
        print(rid, "n", s["n"], "net %.3f%% tm %.2f tb %.2f 2x %.3f%% 3x %.3f%% top5 %.2f | Sh %.2f BH %.2f SPY %.2f DD %.0f%%/%.0f%% alpha %.1f%% t %.2f beta %.2f %s %.0fs" % (
            100 * s["mean"], s["t_month"], s["t_block"], 100 * s["mean_2x"], 100 * s["mean_3x"], s.get("top5_share", np.nan),
            s["port"]["sharpe"], s["bh"]["sharpe"], s["spy"]["sharpe"], 100 * s["port"]["maxdd"], 100 * s["bh"]["maxdd"],
            100 * s["alpha_ann"], s["alpha_t"], s["beta"], s["verdict"], time.time() - t0), flush=True)
    prev = prev_ps()
    ids = list(prev) + list(res)
    qs = dict(zip(ids, es.bh_qvalues([prev[i] if i in prev else res[i]["p_month"] for i in ids])))
    for i in res:
        res[i]["q_cum"] = qs[i]
        res[i]["p"] = res[i]["p_month"]
    g = gate(res)
    report.dump_json(dict(n_trials_round=len(res), n_trials_cum=len(ids), res=res, gate=g), out)
    for i, s in res.items():
        idea = (f"{s['family']} {i}: n={s['n']}, gross {100*s['gross']:.3f}%, 2x {100*s['mean_2x']:.3f}%, 3x {100*s['mean_3x']:.3f}%, top5 {s.get('top5_share', float('nan')):.2f}, "
                f"Sh(MTM) {s['port']['sharpe']:.2f} vs BH {s['bh']['sharpe']:.2f}/SPY {s['spy']['sharpe']:.2f}, DD {100*s['port']['maxdd']:.0f}%, alpha {100*s['alpha_ann']:.1f}% t={s['alpha_t']:.2f} beta {s['beta']:.2f}, BH q(cum {len(ids)}) {s['q_cum']:.3f}")
        report.append_ledger(report.ledger_row(i, "US", idea, "S1", s["mean"], s["t_month"], s["port"]["sharpe"], "locked", s["verdict"], "stage2" if g.get(s["gkey"], {}).get("PASS") else "drop"))
    print("GATE", json.dumps(g))
    print("gate PASS:", [k for k, v in g.items() if v["PASS"]], "cum trials", len(ids))
    print("done %.0fs peakMB %d" % (time.time() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024))


if __name__ == "__main__":
    main()
