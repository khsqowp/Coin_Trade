"""US daily v2 study (research/us_daily_v2/PREREG_us_daily_v2.md): cross-sectional rules on the point-in-time S&P 500.
Rules are fixed in the pre-registration; nothing here is fitted. Backtest only, no order code.
Run: TP_ROOT=$PWD PYTHONPATH=src:research/us_daily_v1 .venv_us/bin/python research/us_daily_v2/usbt2.py coverage|is|oos|null|sens|lookahead
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from tp import metrics, usdata
from tp.config import RUNS
import usbt as v1   # round-1 helpers: window_stats, dsr_ann, block_bootstrap_ci, wilder_rsi, month/week flags, tcon/log_trial schema

HERE = Path(__file__).resolve().parent
OUT = RUNS / "research" / "us_daily_v2"
PPY = 252
CAL_START = "1998-01-02"
OOS = ("2017-01-03", None)
IS_END = "2016-12-30"
BASE_COST = 0.0010
N = 50
TRIALS = ["mom12_1", "mom12_1_mkt", "riskadj_mom", "high52w", "low_vol", "st_reversal_w", "rsi2_pullback", "volume_drift", "trend_breadth"]
SLOT_RULES = ("rsi2_pullback", "volume_drift")
REGIMES = dict(v1.REGIMES)
REGIMES["covid_full"] = ("2020-02-20", "2020-08-10")
# Data-cleaning exclusions (PREREG addendum A1, decided before any v2 strategy run): re-used tickers whose vendor series is a DIFFERENT
# company overlapping the old S&P 500 membership spell (vendor longName audit, coverage.json).
REUSED_TICKER_EXCLUDE = {"CCU", "CPWR", "CSR", "EP", "KG", "SII", "SNT", "SUN",
                         "PARA", "BBT"}            # addendum A2: recent-spell re-use found by the dollar-volume screen
ADJ_JUMP, ADJ_RET, CLOSE_RET = 0.15, 0.15, 0.10     # addendum A2: double-counted corporate-action adjustment repair


def repair_adjustment(d):
    """Neutralise a vendor adjustment-factor jump when it is a double count: factor (adjclose/close) moves > 15% in one day, the
    adjclose return is > 15% in size, but the split-adjusted close return is < 10% (the close series already absorbed the event).
    Returns (repaired frame, list of repaired dates). Legitimate spin-off-as-dividend cases (close drops, adjclose smooth) are untouched."""
    d = d.copy()
    f = d["adjclose"] / d["close"]
    jump = f / f.shift(1) - 1
    ra = d["adjclose"].pct_change()
    rc = d["close"].pct_change()
    bad = (jump.abs() > ADJ_JUMP) & (ra.abs() > ADJ_RET) & (rc.abs() < CLOSE_RET)
    fixed = []
    for t in d.index[bad.fillna(False).values]:
        k = 1 + float(jump.loc[t])
        d.loc[d.index < t, "adjclose"] *= k
        fixed.append(str(t.date()))
    return d, fixed
ETF_SKIP = {"SPY", "QQQ", "DIA", "IWM", "MDY", "RSP", "IJH", "IWB", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}


# ------------------------------------------------------------------ panel
class Panel:
    pass


def load_panel(end=None, cache=True):
    pk = OUT / "panel.pkl"
    if cache and end is None and pk.exists():
        return pd.read_pickle(pk)
    se = pd.read_csv(usdata.US_DIR / "pit" / "sp500_ticker_start_end.csv")
    se["sym"] = se["ticker"].str.replace(".", "-", regex=False)
    se["end_date"] = se["end_date"].fillna("2099-12-31")
    spy = usdata.load("SPY")
    cal = spy.loc[CAL_START:].index
    O, C, V, M = {}, {}, {}, {}
    info = {}
    for sym in sorted(set(se["sym"])):
        p, pm, _ = usdata._paths(sym)
        if not p.exists() or sym in REUSED_TICKER_EXCLUDE:
            continue
        meta = json.loads(pm.read_text())
        it = (meta.get("vendor") or {}).get("instrumentType")
        info[sym] = meta.get("vendor") or {}
        if it not in (None, "EQUITY"):
            continue
        d, fx = repair_adjustment(usdata.load(sym))
        if fx:
            info.setdefault("_adj_repairs", {})[sym] = fx
        a = usdata.adjusted(d).reindex(cal)
        O[sym], C[sym], V[sym] = a["open"], a["close"], d["volume"].reindex(cal)
        m = pd.Series(False, index=cal)
        for _, r in se[se["sym"] == sym].iterrows():
            m.loc[r["start_date"]:r["end_date"]] = True
        M[sym] = m
    P = Panel()
    P.O, P.C, P.V, P.M = pd.DataFrame(O), pd.DataFrame(C), pd.DataFrame(V), pd.DataFrame(M)
    P.C = P.C.where(P.C > 0)
    P.O = P.O.where(P.O > 0)
    P.info = info
    a = usdata.adjusted(spy).reindex(cal)
    P.spyO, P.spyC = a["open"], a["close"]
    irx = usdata.load("^IRX")["close"].reindex(cal).ffill()
    P.rf = (irx.shift(1) / 100.0 / PPY).fillna(0.0)
    hist = P.C.notna().cumsum()
    P.E = P.M & P.C.notna() & (hist >= 260)
    # membership-wide coverage: spells of tickers with no usable data
    allm = {}
    for _, r in se.iterrows():
        allm.setdefault(r["sym"], []).append((r["start_date"], r["end_date"]))
    P.spells = allm
    if end is not None:
        for k in ("O", "C", "V", "M", "E"):
            setattr(P, k, getattr(P, k).loc[:end])
        P.spyO, P.spyC, P.rf = P.spyO.loc[:end], P.spyC.loc[:end], P.rf.loc[:end]
    if cache and end is None:
        OUT.mkdir(parents=True, exist_ok=True)
        pd.to_pickle(P, pk)
    return P


def coverage(P):
    """Per-year PIT coverage: member-days with usable data / all member-days (members without any vendor data count as missing)."""
    cal = P.C.index
    tot = pd.Series(0.0, index=cal)
    for sym, sp in P.spells.items():
        m = pd.Series(0.0, index=cal)
        for a, b in sp:
            m.loc[a:b] = 1.0
        tot += m
    have = (P.M & P.C.notna()).sum(axis=1)
    elig = P.E.sum(axis=1)
    df = pd.DataFrame({"members": tot, "with_data": have, "eligible": elig})
    yr = df.groupby(df.index.year).sum()
    yr["coverage"] = yr["with_data"] / yr["members"]
    yr["eligible_share"] = yr["eligible"] / yr["members"]
    daily_n = df.groupby(df.index.year)[["members", "with_data", "eligible"]].mean().round(1)
    return yr, daily_n


def is_start(yr, thr=0.85):
    years = [y for y in yr.index if 2000 <= y <= 2016]
    for y in years:
        if all(yr.loc[z, "coverage"] >= thr for z in years if z >= y):
            return "%d-01-03" % y if y != 2008 else "2008-01-02"
    return "2008-01-02"


# ------------------------------------------------------------------ signals
def dec_flags(P, kind, phase=0, wk_day=None):
    idx = P.C.index
    if kind == "M":
        return v1.month_end_flags(idx, phase).values
    if kind == "W":
        return v1.week_end_flags(idx, wk_day).values
    return np.ones(len(idx), bool)


def scores(P, name):
    C = P.C
    if name in ("mom12_1", "mom12_1_mkt"):
        return C.shift(21) / C.shift(252) - 1
    r = C.pct_change(fill_method=None)
    if name == "riskadj_mom":
        return (C.shift(21) / C.shift(252) - 1) / r.rolling(252, min_periods=200).std()
    if name == "high52w":
        return C / C.rolling(252, min_periods=200).max()
    if name == "low_vol":
        return -r.rolling(252, min_periods=200).std()
    if name == "st_reversal_w":
        return -(C / C.shift(5) - 1)
    raise KeyError(name)


def monthly_targets(P, name, phase=0, wk_day=None, rng=None, count_from=None):
    """{row: weight vector} for monthly/weekly rules. rng -> random-portfolio null with the same eligibility, dates and counts."""
    kind = "W" if name.endswith("_w") else "M"
    flags = dec_flags(P, kind, phase, wk_day)
    Ev = P.E.values
    k = P.C.shape[1]
    spy_on = (P.spyC > P.spyC.rolling(200).mean()).values
    tg, counts = {}, {}
    if name == "trend_breadth":
        C = P.C
        q = ((C > C.rolling(200, min_periods=200).mean()) & (C.rolling(50).mean() > C.rolling(200, min_periods=200).mean())).values
        for i in np.flatnonzero(flags):
            sel = np.flatnonzero(Ev[i] & q[i])
            n = len(sel) if count_from is None else count_from.get(i, 0)
            if rng is not None:
                pool = np.flatnonzero(Ev[i])
                sel = rng.choice(pool, size=min(n, len(pool)), replace=False) if n else np.array([], int)
            w = np.zeros(k)
            if len(sel):
                w[sel] = min(1.0 / len(sel), 0.02)
            tg[i], counts[i] = w, len(sel)
        return tg, counts
    if name == "ew_univ":
        for i in np.flatnonzero(flags):
            sel = np.flatnonzero(Ev[i])
            w = np.zeros(k)
            w[sel] = 1.0 / len(sel) if len(sel) else 0
            tg[i] = w
        return tg, counts
    S = scores(P, name).values
    for i in np.flatnonzero(flags):
        w = np.zeros(k)
        if name == "mom12_1_mkt" and not spy_on[i]:
            tg[i] = w
            continue
        ok = Ev[i] & ~np.isnan(S[i])
        pool = np.flatnonzero(ok)
        if len(pool) < N:
            tg[i] = w
            continue
        if rng is None:
            sel = pool[np.lexsort((pool, -S[i][pool]))][:N]     # score desc, ties by column (tickers are sorted)
        else:
            sel = rng.choice(pool, size=N, replace=False)
        w[sel] = 1.0 / N
        tg[i] = w
    return tg, counts


def sim_targets(P, tg, cost=BASE_COST, start=None, contrib_from=None):
    """Unit-based simulation; decision at close i -> fill at open i+1. Held names without data are valued/sold at their last close."""
    idx = P.C.index
    Cff = P.C.ffill().values
    Ov = P.O.values
    Cv = P.C.values
    rfv = P.rf.values
    n, k = Cff.shape
    i0 = idx.get_loc(pd.Timestamp(start)) if start else 0
    u = np.zeros(k)
    cash = 1.0
    eq = np.full(n, np.nan)
    gross = np.full(n, np.nan)
    costs = np.zeros(n)
    turn = np.zeros(n)
    fills = []
    contrib = np.zeros(k) if contrib_from is not None else None
    ci0 = idx.get_loc(pd.Timestamp(contrib_from)) if contrib_from is not None else None
    eq[i0], gross[i0] = 1.0, 0.0
    pending = tg.get(i0)
    lastE = 1.0
    for i in range(i0 + 1, n):
        cash *= 1 + rfv[i]
        if contrib is not None and i >= ci0:
            dpx = np.nan_to_num(Cff[i] - Cff[i - 1])
            contrib += u * dpx / lastE
        if pending is not None:
            fillpx = np.where(np.isnan(Ov[i]), Cff[i - 1], Ov[i])
            fillpx = np.where(np.isnan(fillpx), 0.0, fillpx)
            buyable = ~np.isnan(Ov[i]) & ~np.isnan(Cv[i])
            w = np.where(buyable, pending, 0.0)
            # names already held whose open is missing but have target>0: keep current units (cannot trade)
            E = cash + float(np.sum(u * fillpx))
            safe = np.where(fillpx > 0, fillpx, 1.0)
            Enet = E
            for _ in range(6):
                newu = np.where(fillpx > 0, w * Enet / safe, 0.0)
                hold_nt = (~buyable) & (pending > 0) & (u > 0)
                newu[hold_nt] = u[hold_nt]
                traded = float(np.sum(np.abs(newu - u) * fillpx))
                Enet = E - cost * traded
            du = newu - u
            c = traded * cost
            cash = E - float(np.sum(newu * fillpx)) - c
            nz = np.flatnonzero(np.abs(du) * fillpx > 1e-12)
            for j in nz:
                fills.append((idx[i], P.C.columns[j], float(du[j] * fillpx[j] / E), float(newu[j])))
            u = newu
            costs[i], turn[i] = c / E, traded / E
            pending = None
        val = np.nan_to_num(Cff[i])
        pos = float(np.sum(u * val))
        E = cash + pos
        eq[i], gross[i] = E, pos / E if E > 0 else 0.0
        lastE = E
        if i in tg:
            pending = tg[i]
    s = pd.Series(eq, index=idx)
    return {"eq": s, "ret": s.pct_change(), "gross": pd.Series(gross, index=idx), "cost": pd.Series(costs, index=idx),
            "turn": pd.Series(turn, index=idx), "fills": fills, "contrib": contrib}


def slot_candidates(P, name):
    C, V = P.C, P.V
    if name == "rsi2_pullback":
        rsi = C.apply(lambda s: v1.wilder_rsi(s.dropna(), 2).reindex(s.index))
        cand = P.E & (C > C.rolling(200, min_periods=200).mean()) & (rsi < 5)
        prio = rsi                                        # ascending
        sma5 = C.rolling(5).mean()
        return cand.values, prio.values, True, (C > sma5).values, 10
    if name == "volume_drift":
        vr = V / V.shift(1).rolling(50, min_periods=50).mean()
        cand = P.E & (vr > 3) & (C.pct_change(fill_method=None) > 0.04)
        return cand.values, (-vr).values, True, None, 20
    raise KeyError(name)


def sim_slots(P, name, cost=BASE_COST, start=None, rng=None, slots=20, slot_w=0.05, contrib_from=None, pre=None):
    """Event rule with fixed slots: entries get slot_w of equity at the fill open; held names are not re-weighted.
    Exit at the next open when exit_flag (close-based) or max hold reached, or when the name has no data."""
    cand, prio, asc, exitf, maxhold = pre if pre is not None else slot_candidates(P, name)
    idx = P.C.index
    Cv, Ov, Cff = P.C.values, P.O.values, P.C.ffill().values
    Ev = P.E.values
    rfv = P.rf.values
    n, k = Cv.shape
    i0 = idx.get_loc(pd.Timestamp(start)) if start else 0
    u = np.zeros(k)
    held_since = {}
    cash = 1.0
    eq = np.full(n, np.nan)
    gross = np.full(n, np.nan)
    costs, turn = np.zeros(n), np.zeros(n)
    fills = []
    contrib = np.zeros(k) if contrib_from is not None else None
    ci0 = idx.get_loc(pd.Timestamp(contrib_from)) if contrib_from is not None else None
    eq[i0], gross[i0] = 1.0, 0.0
    to_buy, to_sell = [], []
    lastE = 1.0
    for i in range(i0 + 1, n):
        cash *= 1 + rfv[i]
        if contrib is not None and i >= ci0:
            contrib += u * np.nan_to_num(Cff[i] - Cff[i - 1]) / lastE
        if to_sell or to_buy:
            Eo = cash + float(np.sum(u * np.nan_to_num(np.where(np.isnan(Ov[i]), Cff[i - 1], Ov[i]))))
            tr = 0.0
            for j in to_sell:
                px = Ov[i, j] if not np.isnan(Ov[i, j]) else Cff[i - 1, j]
                v = u[j] * px
                cash += v * (1 - cost)
                tr += v
                fills.append((idx[i], P.C.columns[j], -v / Eo, 0.0))
                u[j] = 0.0
                held_since.pop(j, None)
            for j in to_buy:
                px = Ov[i, j]
                if np.isnan(px) or np.isnan(Cv[i, j]) or u[j] > 0:
                    continue
                amt = min(slot_w * Eo, cash / (1 + cost))
                if amt <= 1e-9:
                    break
                u[j] = amt / px
                cash -= amt * (1 + cost)
                tr += amt
                held_since[j] = i
                fills.append((idx[i], P.C.columns[j], amt / Eo, float(u[j])))
            costs[i], turn[i] = tr * cost / Eo, tr / Eo
            to_buy, to_sell = [], []
        pos = float(np.sum(u * np.nan_to_num(Cff[i])))
        E = cash + pos
        eq[i], gross[i] = E, pos / E if E > 0 else 0.0
        lastE = E
        # decisions at close i
        for j in list(held_since):
            if np.isnan(Cv[i, j]) or (i - held_since[j] + 1) >= maxhold or (exitf is not None and exitf[i, j]):
                to_sell.append(j)
        free = slots - (len(held_since) - len(to_sell))
        if free > 0:
            c = np.flatnonzero(cand[i] & (u == 0))
            if rng is not None:
                pool = np.flatnonzero(Ev[i] & (u == 0))
                c = rng.choice(pool, size=min(len(c), len(pool)), replace=False) if len(c) else c
                to_buy = list(c[:free])
            elif len(c):
                pr = prio[i, c]
                order = np.lexsort((c, pr))
                to_buy = list(c[order][:free])
    s = pd.Series(eq, index=idx)
    return {"eq": s, "ret": s.pct_change(), "gross": pd.Series(gross, index=idx), "cost": pd.Series(costs, index=idx),
            "turn": pd.Series(turn, index=idx), "fills": fills, "contrib": contrib}


def run(P, name, cost=BASE_COST, phase=0, wk_day=None, start=None, rng=None, contrib_from=None, pre=None, counts=None):
    if name in SLOT_RULES:
        return sim_slots(P, name, cost=cost, start=start, rng=rng, contrib_from=contrib_from, pre=pre), None
    tg, cnt = monthly_targets(P, name, phase=phase, wk_day=wk_day, rng=rng, count_from=counts)
    return sim_targets(P, tg, cost=cost, start=start, contrib_from=contrib_from), cnt


def bench(P, name, start):
    idx = P.C.index
    if name == "ew_univ":
        tg, _ = monthly_targets(P, "ew_univ")
        return sim_targets(P, tg, start=start)
    # single-ETF buy-and-hold via a one-column panel
    sym = {"spy_bh": "SPY", "rsp_bh": "RSP"}[name]
    a = usdata.adjusted(usdata.load(sym)).reindex(idx)
    Q = Panel()
    Q.O, Q.C = a[["open"]].rename(columns={"open": sym}), a[["close"]].rename(columns={"close": sym})
    Q.rf = P.rf
    first = a["close"].first_valid_index()
    st = max(pd.Timestamp(start), first)
    st = idx[idx.get_indexer([st], method="bfill")[0]]
    return sim_targets(Q, {idx.get_loc(st): np.array([1.0])}, start=st)


# ------------------------------------------------------------------ stats helpers
def wstats(res, P, a, b, fills=True):
    O = P.O if fills else None
    return v1.window_stats(res, P.rf, a, b, fills=res["fills"] if fills else None, O=O, cost=BASE_COST)


def periods(P):
    cov = json.loads((HERE / "coverage.json").read_text())
    ISP = (cov["is_start"], IS_END)
    OOSP = (OOS[0], str(P.C.index[-1].date()))
    return ISP, OOSP


def sim_start(P, ISP):
    idx = P.C.index
    j = idx.get_loc(pd.Timestamp(ISP[0]))
    return str(idx[j - 1].date())            # decision on the bar before IS start, fill on IS start


# ------------------------------------------------------------------ stages
def stage_coverage():
    P = load_panel(cache=False)
    yr, dn = coverage(P)
    st = is_start(yr)
    # ticker re-use audit: spells ended before 2015 whose ticker has vendor data
    audit = []
    for sym, sp in P.spells.items():
        if sym in P.info and not sym.startswith("_") and all(b < "2015-01-01" for a, b in sp):
            audit.append((sym, sp, P.info[sym].get("longName"), P.info[sym].get("instrumentType")))
    nonequity = sorted(s for s, v in P.info.items() if not s.startswith("_") and v.get("instrumentType") not in (None, "EQUITY"))
    out = {"is_start": st, "yearly": yr.round(4).reset_index().to_dict(orient="records"), "daily_avg_counts": dn.reset_index().to_dict(orient="records"),
           "n_symbols_with_data": int(P.C.shape[1]), "adj_repairs": P.info.get("_adj_repairs", {}), "n_pit_symbols": len(P.spells), "nonequity_excluded": nonequity,
           "reuse_audit_old_spells_with_data": audit}
    (HERE / "coverage.json").write_text(json.dumps(out, indent=1, default=str))
    return {k: v for k, v in out.items() if k != "reuse_audit_old_spells_with_data"} | {"n_audit": len(audit)}


def stage_is():
    P = load_panel()
    ISP, _ = periods(P)
    st0 = sim_start(P, ISP)
    con = tcon()
    rows, srs = {}, {}
    for t in TRIALS:
        res, _ = run(P, t, start=st0)
        rows[t] = wstats(res, P, *ISP)
        r = res["ret"].loc[ISP[0]:ISP[1]].dropna()
        srs[t] = log_trial(con, t, "base", "10bp", (r - P.rf.loc[r.index]).values, 1)
    for b in ("spy_bh", "rsp_bh", "ew_univ"):
        res = bench(P, b, st0)
        rows[b] = wstats(res, P, *ISP, fills=False)
    sel = max(TRIALS, key=lambda t: srs[t])
    v1_srs = [x[0] for x in v1.tcon().execute("SELECT sr_ann FROM trials WHERE selection=1 AND study='US1'").fetchall()]
    allsr = list(srs.values()) + v1_srs
    for t in TRIALS:
        res, _ = run(P, t, start=st0)
        r = res["ret"].loc[ISP[0]:ISP[1]].dropna()
        ex = (r - P.rf.loc[r.index]).values
        a16 = v1.dsr_ann(ex, PPY, allsr)
        a9 = v1.dsr_ann(ex, PPY, list(srs.values()))
        rows[t].update({"dsr_null_n16": round(a16[0], 3), "sr0_null_n16": round(a16[1], 3), "dsr_emp_n16": round(a16[2], 3),
                        "dsr_null_n9": round(a9[0], 3), "dsr_emp_n9": round(a9[2], 3)})
    out = {"stage": "IS", "period": ISP, "selected": sel, "is_sharpe_ex": {k: round(v, 3) for k, v in srs.items()}, "rows": rows,
           "n_trials_cumulative": len(allsr)}
    (OUT / "is_selection.json").write_text(json.dumps(out, indent=1))
    (HERE / "is_selection.json").write_text(json.dumps(out, indent=1))
    return out


def tcon():
    import sqlite3
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(OUT / "trials.sqlite", timeout=30)
    con.execute("CREATE TABLE IF NOT EXISTS trials(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, study TEXT, strat TEXT, side TEXT, sym TEXT, "
                "tf TEXT, variant TEXT, cost TEXT, sr_ann REAL, ppy REAL, n_bars INTEGER, selection INTEGER)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_trial ON trials(study, strat, side, sym, tf, variant, cost)")
    return con


def log_trial(con, strat, variant, cost, ex, selection):
    sr = metrics.sharpe_annual(ex, PPY)
    con.execute("INSERT OR REPLACE INTO trials(ts,study,strat,side,sym,tf,variant,cost,sr_ann,ppy,n_bars,selection) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "US2", strat, "long", "SP500-PIT", "1d", variant, cost, sr, PPY, len(ex), selection))
    con.commit()
    return sr


def stage_oos():
    P = load_panel()
    ISP, OOSP = periods(P)
    st0 = sim_start(P, ISP)
    sel = json.loads((OUT / "is_selection.json").read_text())["selected"]
    out = {"selected": sel, "IS": {}, "OOS": {}, "FULL": {}, "regimes": {}, "yearly": {}, "concentration": {}}
    R = {}
    for t in TRIALS + ["spy_bh", "rsp_bh", "ew_univ"]:
        if t in TRIALS:
            res, _ = run(P, t, start=st0, contrib_from=OOSP[0])
        else:
            res = bench(P, t, st0)
        R[t] = res
        f = t in TRIALS
        out["IS"][t] = wstats(res, P, *ISP, fills=f)
        out["OOS"][t] = wstats(res, P, *OOSP, fills=f)
        out["FULL"][t] = wstats(res, P, ISP[0], OOSP[1], fills=f)
        out["regimes"][t] = {k: v1.window_stats(res, P.rf, a, min(b, OOSP[1])) for k, (a, b) in REGIMES.items() if a >= ISP[0]}
        out["yearly"][t] = {str(y.year): round(float(v), 4) for y, v in ((1 + res["ret"].loc[ISP[0]:]).resample("YE").prod() - 1).items()}
    for ref in ("spy_bh", "ew_univ"):
        rb = R[ref]["ret"].loc[OOSP[0]:OOSP[1]]
        for t in TRIALS:
            rr = R[t]["ret"].loc[OOSP[0]:OOSP[1]]
            lo, hi, p = v1.block_bootstrap_ci((rr - rb).values)
            out["OOS"][t]["vs_%s_ci95_ann" % ref] = [round(lo * PPY, 4), round(hi * PPY, 4)]
            out["OOS"][t]["vs_%s_p_le0" % ref] = round(p, 3)
    v1_srs = [x[0] for x in v1.tcon().execute("SELECT sr_ann FROM trials WHERE selection=1 AND study='US1'").fetchall()]
    allsr = [x[0] for x in tcon().execute("SELECT sr_ann FROM trials WHERE selection=1 AND study='US2'").fetchall()] + v1_srs
    for t in TRIALS:
        r = R[t]["ret"].loc[OOSP[0]:OOSP[1]].dropna()
        d = v1.dsr_ann((r - P.rf.loc[r.index]).values, PPY, allsr)
        out["OOS"][t].update({"dsr_null_n16": round(d[0], 3), "dsr_emp_n16": round(d[2], 3)})
        # concentration: drop the 10 largest OOS P&L contributors (their contribution set to 0, i.e. as if that capital sat idle)
        c = R[t]["contrib"]
        top = np.argsort(-c)[:10]
        out["concentration"][t] = {"top10": [(P.C.columns[j], round(float(c[j]), 4)) for j in top],
                                   "sum_top10": round(float(c[top].sum()), 4), "sum_all": round(float(c.sum()), 4)}
    (HERE / "oos_results.json").write_text(json.dumps(out, indent=1))
    eqs = pd.DataFrame({t: R[t]["eq"] for t in R}).loc[st0:]
    eqs.to_csv(HERE / "equity_curves.csv", float_format="%.6f")
    return {"selected": sel}


def stage_null(draws_m=200, draws_s=100):
    P = load_panel()
    ISP, OOSP = periods(P)
    st0 = sim_start(P, ISP)
    out = {}
    pre = {t: slot_candidates(P, t) for t in SLOT_RULES}
    for t in TRIALS:
        res, cnt = run(P, t, start=st0, pre=pre.get(t))
        real = {p: wstats(res, P, *w, fills=False)["sharpe_ex"] for p, w in (("IS", ISP), ("OOS", OOSP))}
        nd = draws_s if t in SLOT_RULES else draws_m
        rng = np.random.default_rng(20261104 + TRIALS.index(t))
        sims = {"IS": [], "OOS": []}
        for _ in range(nd):
            rr, _ = run(P, t, start=st0, rng=rng, pre=pre.get(t), counts=cnt)
            for p, w in (("IS", ISP), ("OOS", OOSP)):
                sims[p].append(wstats(rr, P, *w, fills=False)["sharpe_ex"])
        out[t] = {"draws": nd, "real": real,
                  "p": {p: round((1 + sum(x >= real[p] for x in sims[p])) / (1 + nd), 4) for p in sims},
                  "null_median": {p: round(float(np.median(sims[p])), 3) for p in sims},
                  "null_p95": {p: round(float(np.percentile(sims[p], 95)), 3) for p in sims}}
        print(t, out[t], flush=True)
    ps = [out[t]["p"]["OOS"] for t in TRIALS]
    m = len(ps)
    order = np.argsort(ps)
    q = np.empty(m)
    prev = 1.0
    for rank in range(m, 0, -1):
        j = order[rank - 1]
        prev = min(prev, ps[j] * m / rank)
        q[j] = prev
    for t, qq in zip(TRIALS, q):
        out[t]["bonferroni_OOS"] = round(min(1.0, out[t]["p"]["OOS"] * m), 4)
        out[t]["bh_q_OOS"] = round(float(qq), 4)
    (HERE / "null_results.json").write_text(json.dumps(out, indent=1))
    return out


def stage_sens():
    P = load_panel()
    ISP, OOSP = periods(P)
    st0 = sim_start(P, ISP)
    con = tcon()
    out = {}
    pre = {t: slot_candidates(P, t) for t in SLOT_RULES}
    for t in TRIALS + ["ew_univ"]:
        d = {}
        for c in (0.0005, 0.0020, 0.0040):
            if t == "ew_univ":
                tg, _ = monthly_targets(P, "ew_univ")
                res = sim_targets(P, tg, cost=c, start=st0)
            else:
                res, _ = run(P, t, cost=c, start=st0, pre=pre.get(t))
            d["cost_%gbp" % (c * 1e4)] = {p: wstats(res, P, *w, fills=False)["sharpe_ex"] for p, w in (("IS", ISP), ("OOS", OOSP))}
            r = res["ret"].loc[OOSP[0]:].dropna()
            log_trial(con, t, "cost", "%gbp" % (c * 1e4), (r - P.rf.loc[r.index]).values, 0)
        if t not in SLOT_RULES and t != "ew_univ":
            variants = [("phase_wednesday", dict(wk_day=2))] if t.endswith("_w") else [("phase_minus5", dict(phase=5)), ("phase_minus10", dict(phase=10))]
            for nm, kw in variants:
                res, _ = run(P, t, start=st0, **kw)
                d[nm] = {p: {k: wstats(res, P, *w, fills=False)[k] for k in ("sharpe_ex", "mdd", "total_return")} for p, w in (("IS", ISP), ("OOS", OOSP))}
                r = res["ret"].loc[OOSP[0]:].dropna()
                log_trial(con, t, nm, "10bp", (r - P.rf.loc[r.index]).values, 0)
        out[t] = d
        print(t, json.dumps(d), flush=True)
    (HERE / "sensitivity.json").write_text(json.dumps(out, indent=1))
    return out


def stage_lookahead():
    P = load_panel()
    ISP, _ = periods(P)
    st0 = sim_start(P, ISP)
    Q = load_panel(end=ISP[1], cache=False)
    out = {}
    for t in TRIALS:
        a, _ = run(P, t, start=st0)
        b, _ = run(Q, t, start=st0)
        x, y = a["ret"].loc[ISP[0]:ISP[1]].values, b["ret"].loc[ISP[0]:ISP[1]].values
        out[t] = bool(np.allclose(x, y, equal_nan=True, rtol=0, atol=1e-12))
    (HERE / "lookahead_check.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    st = sys.argv[1]
    t0 = time.time()
    res = {"coverage": stage_coverage, "is": stage_is, "oos": stage_oos, "null": stage_null, "sens": stage_sens, "lookahead": stage_lookahead}[st]()
    print(json.dumps(res, indent=1, default=str)[:15000])
    print("elapsed %.0fs" % (time.time() - t0))
