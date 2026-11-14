"""trader_skill v1 study (research/us_daily_v2/trader_skill_v1/PREREG_trader_skill_v1.md): SEC XBRL fundamentals
and a fixed rule-based screener as new cross-sectional factors on the same point-in-time S&P 500 panel as v2.
Reuses research/us_daily_v2/usbt2.py (panel, execution, costs, IS/OOS periods, benchmarks) and
research/us_daily_v1/usbt.py (dsr_ann, block_bootstrap_ci, window_stats, tcon/log_trial pattern) verbatim.
Run: TP_ROOT=$PWD PYTHONPATH=src:research/us_daily_v1:research/us_daily_v2 .venv_us/bin/python \
     research/us_daily_v2/trader_skill_v1/ts_bt.py factors|is|oos|null|sens
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import usbt2 as v2                 # research/us_daily_v2
import usbt as v1                  # research/us_daily_v1: dsr_ann, block_bootstrap_ci, window_stats
from tp.config import RUNS

HERE = Path(__file__).resolve().parent
OUT = RUNS / "research" / "us_daily_v2" / "trader_skill_v1"
PPY = 252
N = 50
STUDY = "US_TS1"
TRIALS = ["xbrl_growth", "xbrl_margin", "xbrl_margin_chg", "xbrl_value", "quality_composite",
          "screener_ew", "screener_mom", "screener_lowvol", "mom_quality", "xbrl_growth_mkt",
          "value_momentum", "screener_trend_breadth"]
FILTERED = {"screener_ew", "screener_mom", "screener_lowvol", "screener_trend_breadth"}   # null draws same count from E
PASS_RULE = dict(min_earn_yield=0.0, min_rev_growth=0.0, min_margin_chg=-0.02)


class FactorBundle:
    pass


# ------------------------------------------------------------------ fundamentals panel
def reuse_audit(P, raw):
    """Logical (not performance-based) extra ticker-reuse check beyond v2's own REUSED_TICKER_EXCLUDE: a resolved
    CIK's fundamentals must have at least one 'filed' date overlapping [spell_start, spell_end + 400d] for some PIT
    membership spell of that symbol, else the matched company cannot be the one that was actually in the S&P 500
    under that ticker -> exclude. Found by chance while reviewing CIK resolution output (e.g. COMS resolving to a
    2018-founded shell whose ticker clearly reused a pre-2011 S&P member's old symbol); documented in the report."""
    flagged = []
    for sym, rows in list(raw.items()):
        sp = P.spells.get(sym)
        if not sp or not rows:
            continue
        filed_years = [r["filed"] for r in rows if r.get("filed")]
        if not filed_years:
            continue
        ok = False
        for a, b in sp:
            bb = (pd.Timestamp(b) + pd.Timedelta(days=400)) if b != "2099-12-31" else pd.Timestamp("2100-01-01")
            if any(pd.Timestamp(a) <= pd.Timestamp(f) <= bb for f in filed_years):
                ok = True
                break
        if not ok:
            flagged.append(sym)
            del raw[sym]
    return flagged


def build_fund_panel(P):
    """{sym: list of quarterly dict rows} (build_fundamentals.py output) -> daily-forward-filled matrices
    aligned to P.C's index/columns. A fact is visible starting filed-date + 1 calendar day (hard PIT rule)."""
    raw = json.loads((HERE / "fundamentals_pit.json").read_text())
    flagged = reuse_audit(P, raw)
    if flagged:
        (HERE / "reuse_audit_fundamentals.json").write_text(json.dumps(flagged, indent=1))
        print("fundamentals reuse-audit excluded %d symbols: %s" % (len(flagged), flagged), flush=True)
    idx = P.C.index
    cols = P.C.columns
    mats = {k: pd.DataFrame(np.nan, index=idx, columns=cols) for k in
            ("rev_growth_yoy", "gross_margin", "margin_chg", "trailing_eps")}
    n_syms = 0
    for sym in cols:
        rows = raw.get(sym)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["visible"] = pd.to_datetime(df["filed"]) + pd.Timedelta(days=1)
        df = df.sort_values("visible").drop_duplicates("visible", keep="last")
        if df["visible"].iloc[-1] < idx[0] or df["visible"].iloc[0] > idx[-1]:
            continue
        s = df.set_index("visible")
        # put known values on their visible dates, ffill across the trading calendar
        for k in mats:
            ser = pd.Series(s[k].values, index=s.index)
            ser = ser[~ser.index.duplicated(keep="last")]
            full = ser.astype("float64").reindex(ser.index.union(idx)).sort_index().ffill().reindex(idx)
            mats[k][sym] = full.values
        n_syms += 1
    print("fundamentals matrices built for %d / %d symbols" % (n_syms, len(cols)), flush=True)
    return mats


def build_extras(P):
    mats = build_fund_panel(P)
    earn_yield = (mats["trailing_eps"] / P.C).where(mats["trailing_eps"] > 0)
    PASS = ((earn_yield > PASS_RULE["min_earn_yield"]) &
            (mats["rev_growth_yoy"] > PASS_RULE["min_rev_growth"]) &
            (mats["margin_chg"] > PASS_RULE["min_margin_chg"]))
    PASS = PASS.fillna(False)

    def pct_rank(df):
        return df.where(P.E).rank(axis=1, pct=True)

    rk = {"mom12_1": pct_rank(v2.scores(P, "mom12_1")), "rev_growth_yoy": pct_rank(mats["rev_growth_yoy"]),
          "margin_chg": pct_rank(mats["margin_chg"]), "earn_yield": pct_rank(earn_yield)}
    quality_composite = rk["rev_growth_yoy"].add(rk["margin_chg"], fill_value=np.nan).add(rk["earn_yield"], fill_value=np.nan)
    X = FactorBundle()
    X.rev_growth_yoy, X.gross_margin, X.margin_chg = mats["rev_growth_yoy"], mats["gross_margin"], mats["margin_chg"]
    X.earn_yield, X.PASS, X.quality_composite = earn_yield, PASS, quality_composite
    X.rk_mom, X.rk_growth, X.rk_margin_chg, X.rk_earn_yield = rk["mom12_1"], rk["rev_growth_yoy"], rk["margin_chg"], rk["earn_yield"]
    return X


def load_all(cache=True):
    pk = OUT / "panel_ts.pkl"
    if cache and pk.exists():
        return pd.read_pickle(pk)
    P = v2.load_panel(cache=False)   # cache=False: never read/write v2's own panel.pkl (pickled under __main__
                                      # when usbt2.py was run directly; also avoids touching v2's existing files)
    X = build_extras(P)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.to_pickle((P, X), pk)
    return P, X


# ------------------------------------------------------------------ targets (generic, reuses v2's execution engine)
def monthly_targets_v2(P, score=None, mask=None, N=N, market_filter=None, breadth=False, cap=0.02, rng=None,
                        count_from=None, phase=0, soft=False):
    flags = v1.month_end_flags(P.C.index, phase).values
    Ev = (mask if mask is not None else P.E).values
    Ebase = P.E.values     # null always draws from the full base eligible set, never from a filtered mask
    k = P.C.shape[1]
    tg, counts = {}, {}
    Sv = score.values if score is not None else None
    for i in np.flatnonzero(flags):
        if market_filter is not None and not market_filter[i]:
            tg[i], counts[i] = np.zeros(k), 0
            continue
        if breadth:
            sel = np.flatnonzero(Ev[i])
            n = len(sel) if count_from is None else count_from.get(i, 0)
            if rng is not None:
                pool = np.flatnonzero(Ebase[i])
                sel = rng.choice(pool, size=min(n, len(pool)), replace=False) if n else np.array([], int)
            w = np.zeros(k)
            if len(sel):
                w[sel] = min(1.0 / len(sel), cap)
            tg[i], counts[i] = w, len(sel)
            continue
        ok = Ev[i] & ~np.isnan(Sv[i])
        pool = np.flatnonzero(ok)
        n_target = N if count_from is None else count_from.get(i, N)
        w = np.zeros(k)
        if rng is not None:
            poolf = np.flatnonzero(Ebase[i])
            sel = rng.choice(poolf, size=min(n_target, len(poolf)), replace=False) if n_target else np.array([], int)
            if len(sel):
                w[sel] = 1.0 / len(sel)
            tg[i], counts[i] = w, len(sel)
            continue
        if len(pool) == 0:
            tg[i], counts[i] = w, 0
            continue
        if len(pool) < n_target and not soft:
            tg[i], counts[i] = w, 0
            continue
        m = min(n_target, len(pool))      # soft=True (Y7/Y8, pre-registered "top min(50, passers)"): m < N when the
        sel = pool[np.lexsort((pool, -Sv[i][pool]))][:m]      # PASS-filtered pool is smaller than N; soft=False (v2-
        w[sel] = 1.0 / m                                      # style, Y1-5/9/10/11): m == N always (else cash, above).
        tg[i], counts[i] = w, m
    return tg, counts


SOFT_TOPN = {"screener_mom", "screener_lowvol"}      # pre-registered "top min(50, passers)"; all other topN rules
                                                      # require the full N=50 or go to cash (v2's own convention).


def strategy_spec(P, X, name, phase=0):
    """-> (score_or_None, mask, market_filter_or_None, breadth_bool)"""
    spy_on = (P.spyC > P.spyC.rolling(200).mean()).values
    if name == "xbrl_growth":
        return X.rev_growth_yoy, P.E, None, False
    if name == "xbrl_margin":
        return X.gross_margin, P.E, None, False
    if name == "xbrl_margin_chg":
        return X.margin_chg, P.E, None, False
    if name == "xbrl_value":
        return X.earn_yield, P.E, None, False
    if name == "quality_composite":
        return X.quality_composite, P.E, None, False
    if name == "screener_ew":
        return None, P.E & X.PASS, None, True
    if name == "screener_mom":
        return v2.scores(P, "mom12_1"), P.E & X.PASS, None, False
    if name == "screener_lowvol":
        return v2.scores(P, "low_vol"), P.E & X.PASS, None, False
    if name == "mom_quality":
        return X.rk_mom.add(X.quality_composite, fill_value=np.nan), P.E, None, False
    if name == "xbrl_growth_mkt":
        return X.rev_growth_yoy, P.E, spy_on, False
    if name == "value_momentum":
        return X.rk_earn_yield.add(X.rk_mom, fill_value=np.nan), P.E, None, False
    if name == "screener_trend_breadth":
        C = P.C
        trend = (C > C.rolling(200, min_periods=200).mean()) & (C.rolling(50).mean() > C.rolling(200, min_periods=200).mean())
        return None, P.E & X.PASS & trend, None, True
    raise KeyError(name)


def run(P, X, name, cost=v2.BASE_COST, start=None, rng=None, contrib_from=None, counts=None, phase=0):
    score, mask, mf, breadth = strategy_spec(P, X, name, phase=phase)
    tg, cnt = monthly_targets_v2(P, score=score, mask=mask, market_filter=mf, breadth=breadth, rng=rng,
                                  count_from=counts, phase=phase, soft=name in SOFT_TOPN)
    res = v2.sim_targets(P, tg, cost=cost, start=start, contrib_from=contrib_from)
    return res, cnt


# ------------------------------------------------------------------ stats / trial logging (mirrors usbt2.py)
def wstats(res, P, a, b):
    return v1.window_stats(res, P.rf, a, b, fills=None)


def tcon():
    import sqlite3
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(OUT / "trials.sqlite", timeout=30)
    con.execute("CREATE TABLE IF NOT EXISTS trials(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, study TEXT, strat TEXT, side TEXT, sym TEXT, "
                "tf TEXT, variant TEXT, cost TEXT, sr_ann REAL, ppy REAL, n_bars INTEGER, selection INTEGER)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_trial ON trials(study, strat, side, sym, tf, variant, cost)")
    return con


def log_trial(con, strat, variant, cost, ex, selection):
    from tp import metrics
    sr = metrics.sharpe_annual(ex, PPY)
    con.execute("INSERT OR REPLACE INTO trials(ts,study,strat,side,sym,tf,variant,cost,sr_ann,ppy,n_bars,selection) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), STUDY, strat, "long", "SP500-PIT", "1d", variant, cost, sr, PPY, len(ex), selection))
    con.commit()
    return sr


def prior_srs():
    v1_srs = [x[0] for x in v1.tcon().execute("SELECT sr_ann FROM trials WHERE selection=1 AND study='US1'").fetchall()]
    v2_srs = [x[0] for x in v2.tcon().execute("SELECT sr_ann FROM trials WHERE selection=1 AND study='US2'").fetchall()]
    return v1_srs, v2_srs


def periods(P):
    return v2.periods(P)


def sim_start(P, ISP):
    return v2.sim_start(P, ISP)


# ------------------------------------------------------------------ stages
def stage_factors():
    P, X = load_all(cache=False)
    cov = {}
    for k in ("rev_growth_yoy", "gross_margin", "margin_chg", "earn_yield"):
        m = getattr(X, k)
        cov[k] = {"pct_eligible_days_with_value": round(float((m.where(P.E).notna()).sum().sum() /
                  max(P.E.sum().sum(), 1)), 4)}
    pass_rate = float((X.PASS & P.E).sum().sum() / max(P.E.sum().sum(), 1))
    out = {"coverage": cov, "screener_pass_rate_of_eligible": round(pass_rate, 4),
           "n_symbols_total": int(P.C.shape[1])}
    (HERE / "factor_coverage.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def stage_is():
    P, X = load_all()
    ISP, _ = periods(P)
    st0 = sim_start(P, ISP)
    con = tcon()
    rows, srs = {}, {}
    for t in TRIALS:
        res, _ = run(P, X, t, start=st0)
        rows[t] = wstats(res, P, *ISP)
        r = res["ret"].loc[ISP[0]:ISP[1]].dropna()
        srs[t] = log_trial(con, t, "base", "10bp", (r - P.rf.loc[r.index]).values, 1)
    sel = max(TRIALS, key=lambda t: srs[t])
    v1_srs, v2_srs = prior_srs()
    allsr = list(srs.values()) + v1_srs + v2_srs
    for t in TRIALS:
        res, _ = run(P, X, t, start=st0)
        r = res["ret"].loc[ISP[0]:ISP[1]].dropna()
        ex = (r - P.rf.loc[r.index]).values
        a28 = v1.dsr_ann(ex, PPY, allsr)
        a12 = v1.dsr_ann(ex, PPY, list(srs.values()))
        rows[t].update({"dsr_null_n28": round(a28[0], 3), "dsr_emp_n28": round(a28[2], 3),
                        "dsr_null_n12": round(a12[0], 3), "dsr_emp_n12": round(a12[2], 3)})
    out = {"stage": "IS", "period": ISP, "selected": sel, "is_sharpe_ex": {k: round(v, 3) for k, v in srs.items()},
           "rows": rows, "n_trials_cumulative": len(allsr)}
    (OUT / "is_selection.json").write_text(json.dumps(out, indent=1))
    (HERE / "is_selection.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1, default=str)[:6000])
    return out


def stage_oos():
    P, X = load_all()
    ISP, OOSP = periods(P)
    st0 = sim_start(P, ISP)
    sel = json.loads((OUT / "is_selection.json").read_text())["selected"]
    out = {"selected": sel, "IS": {}, "OOS": {}, "FULL": {}, "concentration": {}}
    R = {}
    for t in TRIALS + ["spy_bh", "ew_univ"]:
        if t in TRIALS:
            res, _ = run(P, X, t, start=st0, contrib_from=OOSP[0])
        else:
            res = v2.bench(P, t, st0)
        R[t] = res
        out["IS"][t] = wstats(res, P, *ISP)
        out["OOS"][t] = wstats(res, P, *OOSP)
        out["FULL"][t] = wstats(res, P, ISP[0], OOSP[1])
    for ref in ("spy_bh", "ew_univ"):
        rb = R[ref]["ret"].loc[OOSP[0]:OOSP[1]]
        for t in TRIALS:
            rr = R[t]["ret"].loc[OOSP[0]:OOSP[1]]
            lo, hi, p = v1.block_bootstrap_ci((rr - rb).values)
            out["OOS"][t]["vs_%s_ci95_ann" % ref] = [round(lo * PPY, 4), round(hi * PPY, 4)]
            out["OOS"][t]["vs_%s_p_le0" % ref] = round(p, 3)
    v1_srs, v2_srs = prior_srs()
    allsr = [x[0] for x in tcon().execute("SELECT sr_ann FROM trials WHERE selection=1 AND study=?", (STUDY,)).fetchall()] + v1_srs + v2_srs
    for t in TRIALS:
        r = R[t]["ret"].loc[OOSP[0]:OOSP[1]].dropna()
        d = v1.dsr_ann((r - P.rf.loc[r.index]).values, PPY, allsr)
        out["OOS"][t].update({"dsr_null_n28": round(d[0], 3), "dsr_emp_n28": round(d[2], 3)})
        c = R[t].get("contrib")
        if c is not None:
            top = np.argsort(-c)[:10]
            out["concentration"][t] = {"top10": [(P.C.columns[j], round(float(c[j]), 4)) for j in top],
                                       "sum_top10": round(float(c[top].sum()), 4), "sum_all": round(float(c.sum()), 4)}
    (HERE / "oos_results.json").write_text(json.dumps(out, indent=1))
    eqs = pd.DataFrame({t: R[t]["eq"] for t in R}).loc[st0:]
    eqs.to_csv(HERE / "equity_curves.csv", float_format="%.6f")
    print(json.dumps({"selected": sel, "OOS_selected": out["OOS"][sel], "OOS_spy_bh": out["OOS"]["spy_bh"],
                      "OOS_ew_univ": out["OOS"]["ew_univ"]}, indent=1, default=str))
    return {"selected": sel}


def stage_null(draws=200):
    P, X = load_all()
    ISP, OOSP = periods(P)
    st0 = sim_start(P, ISP)
    out = {}
    for t in TRIALS:
        res, cnt = run(P, X, t, start=st0)
        real = {p: wstats(res, P, *w)["sharpe_ex"] for p, w in (("IS", ISP), ("OOS", OOSP))}
        rng = np.random.default_rng(20261110 + TRIALS.index(t))
        sims = {"IS": [], "OOS": []}
        for _ in range(draws):
            rr, _ = run(P, X, t, start=st0, rng=rng, counts=cnt)
            for p, w in (("IS", ISP), ("OOS", OOSP)):
                sims[p].append(wstats(rr, P, *w)["sharpe_ex"])
        out[t] = {"draws": draws, "real": real,
                  "p": {p: round((1 + sum(x >= real[p] for x in sims[p])) / (1 + draws), 4) for p in sims},
                  "null_median": {p: round(float(np.median(sims[p])), 3) for p in sims},
                  "null_p95": {p: round(float(np.percentile(sims[p], 95)), 3) for p in sims},
                  "null_draws_from": "full eligible set E, same monthly count as the real strategy" if t in FILTERED
                                     else "full eligible set E, same fixed N=%d" % N}
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
    P, X = load_all()
    ISP, OOSP = periods(P)
    st0 = sim_start(P, ISP)
    con = tcon()
    sel = json.loads((OUT / "is_selection.json").read_text())["selected"]
    out = {}
    for c in (0.0005, 0.0020, 0.0040):
        res, _ = run(P, X, sel, cost=c, start=st0)
        out["cost_%gbp" % (c * 1e4)] = {p: wstats(res, P, *w)["sharpe_ex"] for p, w in (("IS", ISP), ("OOS", OOSP))}
        r = res["ret"].loc[OOSP[0]:].dropna()
        log_trial(con, sel, "cost", "%gbp" % (c * 1e4), (r - P.rf.loc[r.index]).values, 0)
    for nm, ph in (("phase_minus5", 5), ("phase_minus10", 10)):
        res, _ = run(P, X, sel, start=st0, phase=ph)
        out[nm] = {p: wstats(res, P, *w)["sharpe_ex"] for p, w in (("IS", ISP), ("OOS", OOSP))}
        r = res["ret"].loc[OOSP[0]:].dropna()
        log_trial(con, sel, nm, "10bp", (r - P.rf.loc[r.index]).values, 0)
    (HERE / "sensitivity.json").write_text(json.dumps(out, indent=1))
    print(sel, json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    st = sys.argv[1]
    t0 = time.time()
    res = {"factors": stage_factors, "is": stage_is, "oos": stage_oos, "null": stage_null, "sens": stage_sens}[st]()
    print("elapsed %.0fs" % (time.time() - t0))
