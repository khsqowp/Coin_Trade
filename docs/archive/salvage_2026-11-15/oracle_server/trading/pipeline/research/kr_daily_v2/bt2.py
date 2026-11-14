"""KR-daily-v2 backtest. Rules: research/kr_daily_v2/PREREG_kr_daily_v2.md (hashed before any v2 data was read). Nothing is fitted.
Usage: python bt2.py main|sens|robust   (offline; reads /app/kr/data/*.parquet and /app/v1/data/069500.parquet)."""
import json, math, sqlite3, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

from tp import metrics, research

KR = Path("/app/kr"); V1 = Path("/app/v1")
START, IS_END, OOS_START, END = "2012-06-01", "2019-12-31", "2020-01-01", "2026-11-03"
PPY, COMM, TAX = 252, 0.00015, 0.0020
N_PRIMARY, N_WIDE, N_STRESS = 17, 233, 1000


# ------------------------------------------------------------------ panel
class Panel:
    pass


REPAIRS = []


def repair(d, delisted):
    """Addendum A1: beyond-limit moves between traded rows outside the delisting window = unadjusted corporate action -> back-adjust."""
    d = d.copy()
    px = d[["open", "high", "low", "close"]].to_numpy(float).copy(); vol = d["volume"].to_numpy(float).copy()
    lim = np.where(d.index < pd.Timestamp("2015-06-15"), 0.155, 0.305)
    tr = np.where(vol > 0)[0]
    n = len(d); ev = []
    for k in range(1, len(tr)):
        t, p = tr[k], tr[k - 1]
        if delisted and t >= n - 15:
            continue
        f = px[t, 3] / px[p, 3]
        if px[p, 3] > 0 and abs(f - 1) > lim[t]:
            px[:t] *= f; vol[:t] /= f; ev.append((str(d.index[t].date()), round(float(f), 4)))
    d[["open", "high", "low", "close"]] = px; d["volume"] = vol
    return d, ev


def load_panel(exclude=(), raw=False):
    idx = pd.read_parquet(V1 / "data" / "069500.parquet")
    idx.index = idx.index.tz_convert(None).normalize()
    cal = idx.index[(idx.index >= "2011-05-01") & (idx.index <= END)]
    files = sorted(p for p in (KR / "data").glob("*.parquet") if p.stem not in exclude)
    cols = {k: {} for k in ("open", "high", "low", "close", "volume", "value")}
    for p in files:
        d = pd.read_parquet(p)
        d.index = pd.to_datetime(d.index).normalize()
        d = d[~d.index.duplicated()].sort_index()
        d = d[(d.index >= cal[0]) & (d.index <= cal[-1])]
        if len(d) == 0:
            continue
        if not raw:
            d, ev = repair(d, d.index[-1] < cal[-1])
            if ev:
                REPAIRS.append((p.stem, ev))
        d = d.reindex(cal)
        for k in cols:
            cols[k][p.stem] = d[k].astype("float32")
    P = Panel()
    P.cal, P.syms = cal, list(cols["close"].keys())
    for k, v in cols.items():
        setattr(P, k[0] if k != "volume" and k != "value" else k, pd.DataFrame(v, index=cal).to_numpy(np.float32))
    P.row = ~np.isnan(P.c)
    P.has = P.row & (np.nan_to_num(P.volume) > 0)
    P.cf = pd.DataFrame(P.c).ffill().to_numpy(np.float32)
    prev = np.vstack([np.full((1, P.cf.shape[1]), np.nan, np.float32), P.cf[:-1]])
    locked = (P.h == P.l) & (np.abs(P.o / prev - 1) >= 0.25)
    P.trad = P.has & ~np.nan_to_num(locked, nan=0).astype(bool) & (np.nan_to_num(P.o) > 0)
    val = np.where(P.has, np.nan_to_num(P.value), 0.0).astype(np.float32)
    first = np.argmax(P.row, axis=0)
    listed = np.arange(len(cal))[:, None] >= first[None, :]
    val = np.where(listed, val, np.nan)
    P.med60 = pd.DataFrame(val).rolling(60, min_periods=30).median().to_numpy(np.float32)
    P.nbars = np.cumsum(P.row, axis=0)
    P.trd60 = pd.DataFrame(P.has.astype(np.float32)).rolling(60, min_periods=60).sum().to_numpy()
    P.last = np.where(P.row.any(0), len(cal) - 1 - np.argmax(P.row[::-1], axis=0), -1)
    P.delisted = P.last < len(cal) - 1
    P.elig = (P.nbars >= 252) & P.has & (np.nan_to_num(P.trd60) >= 55) & (np.nan_to_num(P.med60) >= 1e9)
    P.elig3 = (P.nbars >= 30) & P.row & (np.nan_to_num(P.med60) >= 1e9)
    P.idx_close = idx["close"].reindex(cal).ffill().to_numpy()
    P.idx_open = idx["open"].reindex(cal).ffill().to_numpy()
    ret = P.cf / prev - 1
    P.ret = np.where(P.has, ret, np.nan).astype(np.float32)
    P.t0 = int(np.searchsorted(cal, pd.Timestamp(START)))
    return P


def u500(P, t):
    m = np.where(P.elig[t], P.med60[t], -1)
    k = int((m > 0).sum())
    order = np.argsort(-m)[:min(500, k)]
    return order


def month_end_idx(cal):
    s = pd.Series(np.arange(len(cal)), index=cal)
    return set(s.groupby([cal.year, cal.month]).max().values)


def week_end_idx(cal):
    s = pd.Series(np.arange(len(cal)), index=cal)
    iso = cal.isocalendar()
    return set(s.groupby([iso.year.values, iso.week.values]).max().values)


# ------------------------------------------------------------------ signals: return dict t -> {asset: weight} (full target on that day)
def topn(scores, cand, n, high=True):
    s = scores[cand]
    ok = ~np.isnan(s)
    c, s = cand[ok], s[ok]
    if len(c) < n:
        return {}
    o = np.argsort(-s if high else s, kind="stable")[:n]
    return {int(a): 1.0 / n for a in c[o]}


def lag(a, k):
    out = np.full_like(a, np.nan)
    out[k:] = a[:-k]
    return out


def feats(P):
    F = {}
    F["mom12_1"] = lag(P.cf, 21) / lag(P.cf, 252) - 1
    F["vol252"] = pd.DataFrame(P.ret).rolling(252, min_periods=200).std().to_numpy(np.float32)
    F["h52"] = P.cf / pd.DataFrame(P.cf).rolling(252, min_periods=200).max().to_numpy(np.float32)
    F["r5"] = P.cf / lag(P.cf, 5) - 1
    F["r60"] = P.cf / lag(P.cf, 60) - 1
    return F


def mkt_filter_on(P):
    cal = P.cal
    me = sorted(month_end_idx(cal))
    mc = pd.Series(P.idx_close[me], index=me)
    on = mc > mc.rolling(10).mean()
    return on.to_dict()


def sig_monthly(P, score_fn, n=20, high=True, mf=None, phase=0):
    me = sorted(month_end_idx(P.cal))
    out = {}
    for t in me:
        t2 = t + phase
        if t2 < P.t0 - 1 or t2 >= len(P.cal):
            continue
        cand = u500(P, t2)
        if mf is not None and not mf.get(t, True):
            out[t2] = {}
            continue
        out[t2] = topn(score_fn(t2), cand, n, high)
    return out


def rank_pct(x):
    s = pd.Series(x)
    return s.rank(pct=True).to_numpy()


def sig_v6(P, F, phase=0):
    def score(t):
        cand = u500(P, t)
        s = np.full(P.cf.shape[1], np.nan)
        m, v = F["mom12_1"][t][cand], F["vol252"][t][cand]
        ok = ~np.isnan(m) & ~np.isnan(v)
        rm, rv = np.full(len(cand), np.nan), np.full(len(cand), np.nan)
        rm[ok], rv[ok] = rank_pct(m[ok]), rank_pct(-v[ok])
        s[cand] = (rm + rv) / 2
        return s
    return sig_monthly(P, score, 20, True, phase=phase)


def crash_state(mkt, thr=-0.10, look=14, rec=0.0):
    r = mkt / pd.Series(mkt).shift(look).to_numpy() - 1
    st = np.zeros(len(r), bool); on = False
    for i, x in enumerate(r):
        if np.isnan(x):
            continue
        if not on and x <= thr:
            on = True
        elif on and x >= rec:
            on = False
        st[i] = on
    return st


def sig_v3(P, F):
    r1 = np.where(P.elig3, P.ret, np.nan)
    ew = np.nan_to_num(np.nanmean(np.where(np.isnan(r1), np.nan, r1), axis=1))
    mkt = np.cumprod(1 + ew)
    bad = crash_state(mkt) | (mkt < pd.Series(mkt).rolling(200, min_periods=200).mean().to_numpy())
    out, last_bad = {}, False
    start = P.t0 - 1
    for t in range(start, len(P.cal)):
        force = last_bad and not bad[t]
        due = ((t - start) % 21 == 0) or force
        if bad[t]:
            out[t] = {}
        elif due:
            cand = np.where(P.elig3[t])[0]
            out[t] = topn(np.where(P.elig3[t], F["r60"][t], np.nan), cand, 5, True)
        last_bad = bad[t]
    return out


def sig_v7(P, F):
    mx = pd.DataFrame(P.cf).shift(1).rolling(70, min_periods=70).max().to_numpy(np.float32)
    mn = pd.DataFrame(P.cf).shift(1).rolling(25, min_periods=25).min().to_numpy(np.float32)
    me = month_end_idx(P.cal)
    members, held, out = set(), set(), {}
    for t in range(P.t0 - 260, len(P.cal)):
        if t in me or not members:
            members = set(u500(P, t).tolist())
        if t < P.t0 - 1:
            continue
        ch = {}
        for a in list(held):
            if (t >= P.last[a]) or (P.has[t, a] and P.cf[t, a] < mn[t, a]):
                held.discard(a); ch[a] = 0.0
        free = 20 - len(held)
        if free > 0:
            cands = [a for a in members if a not in held and P.has[t, a] and P.cf[t, a] > mx[t, a]]
            cands.sort(key=lambda a: -P.med60[t, a])
            for a in cands[:free]:
                held.add(a); ch[a] = 0.05
        if ch:
            out[t] = ch
    return out, "delta"


def sig_v8(P, F):
    vbase = pd.DataFrame(np.where(P.row, P.volume, np.nan)).shift(1).rolling(20, min_periods=15).mean().to_numpy(np.float32)
    ratio = P.volume / vbase
    me = month_end_idx(P.cal)
    members, held, out = set(), {}, {}
    for t in range(P.t0 - 260, len(P.cal)):
        if t in me or not members:
            members = set(u500(P, t).tolist())
        if t < P.t0 - 1:
            continue
        ch = {}
        for a, t_sig in list(held.items()):
            if t - t_sig >= 20 or t >= P.last[a]:
                del held[a]; ch[a] = 0.0
        free = 20 - len(held)
        if free > 0:
            cands = [a for a in members if a not in held and P.has[t, a] and ratio[t, a] >= 3.0 and P.ret[t, a] < 0.03]
            cands.sort(key=lambda a: -ratio[t, a])
            for a in cands[:free]:
                held[a] = t; ch[a] = 0.05
        if ch:
            out[t] = ch
    return out, "delta"


def sig_v9(P, F):
    we = sorted(week_end_idx(P.cal))
    out = {}
    for t in we:
        if t < P.t0 - 1:
            continue
        out[t] = topn(F["r5"][t], u500(P, t), 20, False)
    return out


def sig_ew(P, all_elig=False):
    out = {}
    for t in sorted(month_end_idx(P.cal)):
        if t < P.t0 - 1:
            continue
        c = np.where(P.elig[t])[0] if all_elig else u500(P, t)
        out[t] = {int(a): 1.0 / len(c) for a in c} if len(c) else {}
    return out


# ------------------------------------------------------------------ simulator
def slip_of(m, mult=1.0):
    if not (m == m):
        return 0.005 * mult
    return mult * (0.0005 if m >= 5e10 else 0.0010 if m >= 1e10 else 0.0025 if m >= 1e9 else 0.0050)


def simulate(P, sig, mode="full", full_rebal=False, slip_mult=1.0, tax=TAX, capital=None, exclude=None):
    """sig: dict t -> target dict (mode 'full': complete target; 'delta': only changed names). Fills at the open of t+1."""
    T, N = P.cf.shape
    ex = set(exclude or ())
    val = np.zeros(N); cash = 1.0
    cin, cout = np.zeros(N), np.zeros(N)
    cur = {}; pend = {}
    navs, expo, trades, ep, parts = [], [], [], {}, []
    costs = 0.0
    t_start = P.t0 - 1
    for t in range(t_start, T):
        if t > t_start:
            pc = P.cf[t - 1]
            ro = np.where(P.row[t], P.o[t], pc); ro = np.where(np.isnan(ro) | (ro <= 0), np.where(P.row[t], P.c[t], pc), ro)
            held = np.nonzero(val)[0]
            if len(held):
                val[held] *= np.nan_to_num(ro[held] / pc[held], nan=1.0)
            # delisting: data ended -> close at last close
            for a in held:
                if t > P.last[a] and val[a] > 0:
                    x = val[a]; fee = x * (slip_of(P.med60[P.last[a], a], slip_mult) + COMM + tax)
                    cash += x - fee; cin[a] += x - fee; costs += fee; val[a] = 0.0
                    e = ep.pop(a, None)
                    if e: trades.append((e[1] + x - fee) / e[0] - 1)
                    pend.pop(a, None); cur.pop(a, None)
            if pend:
                nav_o = cash + val.sum()
                sells, buys = {}, {}
                for a, (w, age) in list(pend.items()):
                    if not P.trad[t, a]:
                        if w * nav_o > val[a] and age >= 5:
                            pend.pop(a)
                        else:
                            pend[a] = (w, age + 1)
                        continue
                    d = w * nav_o - val[a]
                    if d < -1e-12: sells[a] = -d
                    elif d > 1e-12: buys[a] = d
                    pend.pop(a)
                for a, x in sells.items():
                    fee = x * (slip_of(P.med60[t - 1, a], slip_mult) + COMM + tax)
                    cash += x - fee; val[a] -= x; costs += fee; cin[a] += x - fee
                    e = ep.setdefault(a, [0.0, 0.0]); e[1] += x - fee
                    if capital: parts.append(x * capital / max(P.med60[t - 1, a], 1.0))
                    if val[a] <= 1e-12:
                        val[a] = 0.0; e = ep.pop(a); trades.append(e[1] / e[0] - 1 if e[0] > 0 else 0.0)
                tot = sum(x * (1 + slip_of(P.med60[t - 1, a], slip_mult) + COMM) for a, x in buys.items())
                sc = min(1.0, cash / tot) if tot > 0 else 1.0
                for a, x in buys.items():
                    x *= sc; fee = x * (slip_of(P.med60[t - 1, a], slip_mult) + COMM)
                    cash -= x + fee; val[a] += x; costs += fee; cout[a] += x + fee
                    e = ep.setdefault(a, [0.0, 0.0]); e[0] += x + fee
                    if capital: parts.append(x * capital / max(P.med60[t - 1, a], 1.0))
            rc = np.where(P.row[t], P.c[t], np.nan)
            held = np.nonzero(val)[0]
            if len(held):
                val[held] *= np.nan_to_num(rc[held] / ro[held], nan=1.0)
        nav = cash + val.sum()
        navs.append(nav); expo.append(val.sum() / nav if nav > 0 else 0)
        if t in sig:
            tgt = {a: w for a, w in sig[t].items() if a not in ex}
            if mode == "delta":
                for a, w in tgt.items():
                    if abs(cur.get(a, 0.0) - w) > 1e-12 or full_rebal:
                        pend[a] = (w, 0)
                    if w == 0: cur.pop(a, None)
                    else: cur[a] = w
            else:
                names = set(tgt) | set(cur) | set(np.nonzero(val)[0].tolist())
                for a in names:
                    w = tgt.get(a, 0.0)
                    if full_rebal or abs(cur.get(a, 0.0) - w) > 1e-12 or (w == 0 and val[a] > 0):
                        pend[a] = (w, 0)
                cur = dict(tgt)
    nav = pd.Series(navs, index=P.cal[t_start:T])
    out = pd.DataFrame({"nav": nav, "expo": expo})
    out["ret"] = out["nav"].pct_change().fillna(0.0)
    out = out.iloc[1:]
    for a, e in ep.items():
        trades.append((e[1] + val[a]) / e[0] - 1 if e[0] > 0 else 0.0)
    pnl = cin - cout + val
    return out, {"costs": costs, "trades": trades, "pnl": pnl, "parts": parts}


# ------------------------------------------------------------------ metrics
def stats(r, expo=None):
    r = np.asarray(r, float)
    if len(r) < 5:
        return {}
    yrs = len(r) / PPY; tot = float(np.prod(1 + r) - 1)
    o = {"days": len(r), "total_return": round(tot, 4), "cagr": round((1 + tot) ** (1 / yrs) - 1, 4) if tot > -1 else -1.0,
         "sharpe": round(metrics.sharpe_annual(r, PPY), 3), "vol": round(float(r.std(ddof=1) * math.sqrt(PPY)), 4),
         "mdd": round(metrics.max_drawdown(r), 4), "psr0": round(metrics.psr(r), 3)}
    if expo is not None:
        o["time_in_market"] = round(float((np.asarray(expo) > 0.01).mean()), 3)
    return o


def split(nav):
    i, o = nav.loc[:IS_END], nav.loc[OOS_START:]
    return {"IS": stats(i["ret"], i["expo"]), "OOS": stats(o["ret"], o["expo"]), "FULL": stats(nav["ret"], nav["expo"]),
            "PRE2018": stats(nav.loc[:"2017-12-31"]["ret"]), "POST2018": stats(nav.loc["2018-01-01":]["ret"])}


def regimes(nav, b1):
    W = json.loads((V1 / "REGIMES.json").read_text())["windows"]
    rows, types = [], {}
    for w in W:
        m = (nav.index >= w["start"]) & (nav.index <= w["end"])
        rows.append({"label": w["label"], "type": w["type"], "start": w["start"], "end": w["end"],
                     "strat": stats(nav["ret"][m], nav["expo"][m]), "B1": stats(b1["ret"].reindex(nav.index)[m])})
    for typ in ("bull", "bear", "chop"):
        m = np.zeros(len(nav), bool)
        for w in W:
            if w["type"] == typ:
                m |= (nav.index >= w["start"]) & (nav.index <= w["end"])
        types[typ] = {"strat": stats(nav["ret"][m]), "B1": stats(b1["ret"].reindex(nav.index)[m])}
    return rows, types


def b1_nav(P):
    t0 = P.t0
    nav = (1 / (1 + 0.0003 + COMM)) * P.idx_close[t0:] / P.idx_open[t0]
    s = pd.DataFrame({"nav": nav}, index=P.cal[t0:])
    s["ret"] = s["nav"].pct_change().fillna(s["nav"].iloc[0] - 1); s["expo"] = 1.0
    return s


def trials_build(P, F, phase=0):
    mf = mkt_filter_on(P)
    return {
        "V1_XS_MOM12_1": (sig_monthly(P, lambda t: F["mom12_1"][t], phase=phase), "full"),
        "V2_XS_MOM12_1_MF": (sig_monthly(P, lambda t: F["mom12_1"][t], mf=mf, phase=phase), "full"),
        "V3_XS_MOM60_REPL": (sig_v3(P, F), "full"),
        "V4_XS_52WH": (sig_monthly(P, lambda t: F["h52"][t], phase=phase), "full"),
        "V5_XS_LOWVOL": (sig_monthly(P, lambda t: F["vol252"][t], high=False, phase=phase), "full"),
        "V6_XS_MOM_LOWVOL": (sig_v6(P, F, phase=phase), "full"),
        "V7_TS_DONCHIAN_70_25": sig_v7(P, F),
        "V8_EV_VOLSPIKE20": sig_v8(P, F),
        "V9_XS_STREV_W": (sig_v9(P, F), "full"),
    }


def main():
    P = load_panel(); F = feats(P)
    b1 = b1_nav(P)
    T = trials_build(P, F)
    T["B4_EW_U500"] = (sig_ew(P), "full")
    T["B5_EW_ALL_ELIG"] = (sig_ew(P, True), "full")
    res, navs, extras = {}, {"B1_BH_069500": b1}, {}
    con = sqlite3.connect(KR / "trials.sqlite")
    con.execute("CREATE TABLE IF NOT EXISTS trials(study TEXT, strat TEXT, sr_is REAL, sr_full REAL, n_bars INTEGER, selection INTEGER, ts TEXT, PRIMARY KEY(study, strat))")
    for name, (sig, mode) in T.items():
        t1 = time.time()
        nav, ex = simulate(P, sig, mode=mode, full_rebal=name.startswith("B"), capital=1e8)
        navs[name] = nav; extras[name] = ex
        yrs = len(nav) / PPY
        pnl = ex["pnl"]; top = np.argsort(-pnl)[:10]
        parts = np.array(ex["parts"]) if ex["parts"] else np.array([0.0])
        res[name] = {**split(nav), "round_trips": len(ex["trades"]),
                     "win_rate": round(float((np.array(ex["trades"]) > 0).mean()), 3) if ex["trades"] else None,
                     "cost_drag_per_yr": round(ex["costs"] / yrs, 4),
                     "top10_pnl_share": round(float(pnl[top].sum() / pnl.sum()), 3) if pnl.sum() > 0 else None,
                     "top10_names": [P.syms[a] for a in top],
                     "participation_100M_p95": round(float(np.percentile(parts, 95)), 5),
                     "participation_100M_max": round(float(parts.max()), 5),
                     "n_decisions": len(sig), "sec": round(time.time() - t1, 1)}
        con.execute("INSERT OR REPLACE INTO trials VALUES (?,?,?,?,?,?,?)", ("KR2", name, metrics.sharpe_annual(nav.loc[:IS_END]["ret"], PPY),
                    metrics.sharpe_annual(nav["ret"], PPY), len(nav), 1 if name.startswith("V") else 0, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        con.commit()
        print(name, res[name]["IS"].get("sharpe"), res[name]["OOS"].get("sharpe"), res[name]["sec"], flush=True)
    res["B1_BH_069500"] = split(b1)
    v1 = json.loads((V1 / "results_main.json").read_text())["results"]
    v1_is = [v1[k]["IS"]["sharpe"] for k in v1 if k.startswith("T")]
    pool_is = np.array(v1_is + [res[k]["IS"]["sharpe"] for k in res if k.startswith("V")])
    for k in list(res):
        nav = navs[k]
        for seg, rr in (("IS", nav.loc[:IS_END]["ret"].values), ("OOS", nav.loc[OOS_START:]["ret"].values), ("FULL", nav["ret"].values)):
            d, sr0, de, sr0e = research.dsr_ann(rr, PPY, pool_is)
            res[k][seg].update({"dsr_N17": round(d, 3), "sr0_N17": round(sr0, 3), "dsr_emp_N17": round(de, 3)})
            for nn in (N_WIDE, N_STRESS):
                d2, s2, _, _ = research.dsr_ann(rr, PPY, np.zeros(nn) + np.linspace(-1, 1, nn))
                res[k][seg]["dsr_N%d" % nn] = round(d2, 3); res[k][seg]["sr0_N%d" % nn] = round(s2, 3)
        res[k]["regimes"], res[k]["regime_types"] = regimes(nav, b1)
        diff = (nav["ret"] - b1["ret"].reindex(nav.index)).loc[OOS_START:].values
        res[k]["oos_excess_vs_B1_ci90_ann"] = [round(x * PPY, 4) for x in research.block_bootstrap_ci(diff, block=20, n=2000)]
        if "B4_EW_U500" in navs:
            d4 = (nav["ret"] - navs["B4_EW_U500"]["ret"].reindex(nav.index)).loc[OOS_START:].values
            res[k]["oos_excess_vs_B4_ci90_ann"] = [round(x * PPY, 4) for x in research.block_bootstrap_ci(d4, block=20, n=2000)]
    pick = max((k for k in res if k.startswith("V")), key=lambda k: res[k]["IS"]["sharpe"])
    fac = [f for _, ev in REPAIRS for _, f in ev]
    cov = {"codes_with_data": len(P.syms), "delisted_in_panel": int(P.delisted.sum()),
           "repairs": {"names": len(REPAIRS), "events": len(fac), "factor_pctiles_5_50_95": [round(float(np.percentile(fac, q)), 3) for q in (5, 50, 95)] if fac else [],
                       "examples": REPAIRS[:15]},
           "eligible_per_year": {str(y): int(np.mean([P.elig[t].sum() for t in range(len(P.cal)) if P.cal[t].year == y])) for y in range(2012, 2027)}}
    (KR / "results_main.json").write_text(json.dumps({"is_pick": pick, "coverage": cov, "results": res}, indent=1, default=str))
    pd.DataFrame({k: v["nav"] for k, v in navs.items()}).to_csv(KR / "nav_main.csv")
    print(json.dumps({"pick": pick, "coverage": cov}))


def sens():
    P = load_panel(); F = feats(P)
    out = {}
    T = trials_build(P, F)
    T["B4_EW_U500"] = (sig_ew(P), "full")
    for sname, kw in {"slip_x2": {"slip_mult": 2.0}, "tax_0.30": {"tax": 0.0030}}.items():
        out[sname] = {}
        for name, (sig, mode) in T.items():
            nav, ex = simulate(P, sig, mode=mode, full_rebal=name.startswith("B"), **kw)
            out[sname][name] = {**split(nav), "cost_drag_per_yr": round(ex["costs"] / (len(nav) / PPY), 4)}
            print(sname, name, out[sname][name]["OOS"].get("sharpe"), flush=True)
    out["phase_plus5"] = {}
    T5 = trials_build(P, F, phase=5)
    for name in ("V1_XS_MOM12_1", "V2_XS_MOM12_1_MF", "V4_XS_52WH", "V5_XS_LOWVOL", "V6_XS_MOM_LOWVOL"):
        sig, mode = T5[name]
        nav, ex = simulate(P, sig, mode=mode)
        out["phase_plus5"][name] = split(nav)
    pick = json.loads((KR / "results_main.json").read_text())["is_pick"]
    Pr = load_panel(raw=True); Fr = feats(Pr)
    sig, mode = trials_build(Pr, Fr)[pick]
    nav, ex = simulate(Pr, sig, mode=mode)
    out["unrepaired_data_pick"] = {pick: split(nav)}
    (KR / "results_sens.json").write_text(json.dumps(out, indent=1, default=str))


def robust():
    """Top-10 P&L contributors removed (per trial, names from results_main) -> rerun."""
    R = json.loads((KR / "results_main.json").read_text())["results"]
    out = {}
    base = load_panel(); F = feats(base)
    T = trials_build(base, F); T["B4_EW_U500"] = (sig_ew(base), "full")
    for name in T:
        if name not in R:
            continue
        drop = set(R[name]["top10_names"])
        P = load_panel(exclude=drop); F2 = feats(P)
        T2 = trials_build(P, F2); T2["B4_EW_U500"] = (sig_ew(P), "full")
        sig, mode = T2[name]
        nav, ex = simulate(P, sig, mode=mode, full_rebal=name.startswith("B"))
        out[name] = {"dropped": sorted(drop), **split(nav)}
        print(name, out[name]["FULL"].get("sharpe"), flush=True)
    (KR / "results_robust.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    {"main": main, "sens": sens, "robust": robust}[sys.argv[1]]()
