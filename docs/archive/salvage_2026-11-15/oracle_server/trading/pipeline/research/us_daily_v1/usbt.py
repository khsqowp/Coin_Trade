"""US daily v1 study (research/us_daily_v1/PREREG_us_daily_v1.md). Rules are fixed in the pre-registration; nothing here is fitted.
Backtest only: no order code. Run:  TP_ROOT=$PWD PYTHONPATH=src .venv_us/bin/python research/us_daily_v1/usbt.py is|oos|sens|lookahead
"""
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from tp import metrics, usdata
from tp.config import RUNS

HERE = Path(__file__).resolve().parent
OUT = RUNS / "research" / "us_daily_v1"
PPY = 252
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
ASSETS = ["SPY", "QQQ"] + SECTORS
SIM_START = "1999-12-31"
IS = ("2000-01-03", "2016-12-30")
OOS = ("2017-01-03", "2026-11-02")
BASE_COST = 0.0005
REGIMES = {
    "dotcom_bust": ("2000-03-24", "2002-10-09"), "bull_03_07": ("2002-10-10", "2007-10-09"), "gfc": ("2007-10-10", "2009-03-09"),
    "bull_09_15": ("2009-03-10", "2015-07-20"), "chop_15_16": ("2015-07-21", "2016-12-30"),
    "q4_2018": ("2018-09-21", "2018-12-24"), "covid_crash": ("2020-02-20", "2020-03-23"), "covid_recovery": ("2020-03-24", "2020-08-10"),
    "bull_2021": ("2021-01-04", "2022-01-03"), "bear_2022": ("2022-01-04", "2022-10-12"),
    "recovery_bull_2023plus": ("2022-10-13", "2026-11-02"), "tariff_2025": ("2025-02-20", "2025-04-08"),
}
TRIALS = ["spy_sma200_m", "spy_absmom12_m", "spy_voltgt_w", "spy_sma200_voltgt_w", "sector_dm3_m", "sector_dm3_trend_m", "spy_rsi2_mr"]
BENCH = ["B1_spy_bh", "B2_qqq_bh", "B3_sector_ew_m", "B4_tbill"]


# ------------------------------------------------------------------ data
def load_panel(end=None):
    O, C = {}, {}
    for s in ASSETS:
        a = usdata.adjusted(usdata.load(s))
        O[s], C[s] = a["open"], a["close"]
    O, C = pd.DataFrame(O), pd.DataFrame(C)
    cal = C["SPY"].dropna().index
    O, C = O.reindex(cal), C.reindex(cal)
    irx = usdata.load("^IRX")["close"].reindex(cal).ffill()
    rf = (irx.shift(1) / 100.0 / PPY).fillna(0.0)          # accrual for day t uses the yield known at t-1
    if end is not None:
        O, C, rf = O.loc[:end], C.loc[:end], rf.loc[:end]
    return O, C, rf


def month_end_flags(idx, shift=0):
    s = pd.Series(idx.to_period("M"), index=idx)
    last = s != s.shift(-1)
    last.iloc[-1] = False                                    # the final bar in the data is not a confirmed month-end
    pos = np.flatnonzero(last.values) - shift
    f = pd.Series(False, index=idx)
    f.iloc[pos[pos >= 0]] = True
    return f


def week_end_flags(idx, weekday=None):
    if weekday is not None:
        return pd.Series(idx.weekday == weekday, index=idx)
    iso = idx.isocalendar()
    key = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    f = pd.Series(key.values != np.roll(key.values, -1), index=idx)
    f.iloc[-1] = False
    return f


# ------------------------------------------------------------------ signals (target weight frames; NaN row = no decision that day)
def wilder_rsi(c, n=2):
    d = c.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    au, ad = up.ewm(alpha=1 / n, adjust=False).mean(), dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad.replace(0, np.nan)).fillna(100)


def _empty(C):
    return pd.DataFrame(np.nan, index=C.index, columns=C.columns)


def signals(name, C, rf, phase=0, wk_day=None):
    spy = C["SPY"]
    sma200 = spy.rolling(200).mean()
    me = month_end_flags(C.index, phase)
    we = week_end_flags(C.index, wk_day)
    tgt = _empty(C)
    band = None
    trend_on = (spy > sma200)
    trend_state = trend_on.astype(float).where(me).ffill().fillna(0.0).astype(bool)     # T1 state as of the latest month-end decision
    rfi = (1 + rf).cumprod()
    if name == "spy_sma200_m":
        tgt.loc[me, :] = 0.0
        tgt.loc[me, "SPY"] = trend_on[me].astype(float)
    elif name == "spy_absmom12_m":
        cash252 = rfi / rfi.shift(252) - 1
        on = (spy / spy.shift(252) - 1) > cash252
        tgt.loc[me, :] = 0.0
        tgt.loc[me, "SPY"] = on[me].astype(float)
    elif name in ("spy_voltgt_w", "spy_sma200_voltgt_w"):
        sig = spy.pct_change().rolling(20).std() * math.sqrt(PPY)
        w = np.minimum(1.0, 0.15 / sig)
        if name == "spy_sma200_voltgt_w":
            w = w * trend_state.astype(float)
        tgt.loc[we, :] = 0.0
        tgt.loc[we, "SPY"] = w[we]
        band = 0.05
    elif name in ("sector_dm3_m", "sector_dm3_trend_m"):
        score = C[SECTORS].shift(21) / C[SECTORS].shift(252) - 1
        cashw = rfi.shift(21) / rfi.shift(252) - 1
        tgt.loc[me, :] = 0.0
        for d in C.index[me.values]:
            sc = score.loc[d].dropna()
            if len(sc) < len(SECTORS):
                continue
            if name == "sector_dm3_trend_m" and not trend_on.loc[d]:
                continue
            top = sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
            for s, v in top:
                if v > cashw.loc[d]:
                    tgt.loc[d, s] = 1.0 / 3
    elif name == "spy_rsi2_mr":
        rsi = wilder_rsi(spy, 2)
        sma5 = spy.rolling(5).mean()
        pos = 0.0
        col = np.full(len(spy), np.nan)
        for i in range(len(spy)):
            if np.isnan(sma200.iloc[i]):
                continue
            if pos == 0 and spy.iloc[i] > sma200.iloc[i] and rsi.iloc[i] < 10:
                pos = 1.0
            elif pos == 1 and spy.iloc[i] > sma5.iloc[i]:
                pos = 0.0
            col[i] = pos
        tgt[:] = 0.0
        tgt["SPY"] = col
        tgt.loc[np.isnan(col), :] = np.nan
    elif name == "B1_spy_bh":
        tgt.loc[SIM_START, :] = 0.0
        tgt.loc[SIM_START, "SPY"] = 1.0
    elif name == "B2_qqq_bh":
        tgt.loc[SIM_START, :] = 0.0
        tgt.loc[SIM_START, "QQQ"] = 1.0
    elif name == "B3_sector_ew_m":
        tgt.loc[me, :] = 0.0
        tgt.loc[me, SECTORS] = 1.0 / len(SECTORS)
    elif name == "B4_tbill":
        tgt.loc[SIM_START, :] = 0.0
    else:
        raise KeyError(name)
    return tgt, band


# ------------------------------------------------------------------ simulator
def simulate(tgt, O, C, rf, cost=BASE_COST, band=None, fill="open", start=SIM_START):
    """Unit-based daily simulation. Decision at close t -> fill at open (or close) of t+1. Returns dict of daily series + fills list."""
    idx = C.index
    i0 = idx.get_loc(pd.Timestamp(start))
    Ov, Cv, T, rfv = O.values, C.values, tgt.values, rf.values
    n, k = len(idx), C.shape[1]
    u = np.zeros(k)
    cash = 1.0
    eq = np.full(n, np.nan)
    gross = np.full(n, np.nan)
    costs = np.zeros(n)
    turn = np.zeros(n)
    fills = []
    eq[i0] = 1.0
    gross[i0] = 0.0
    pending = T[i0] if not np.all(np.isnan(T[i0])) else None
    for i in range(i0 + 1, n):
        cash *= 1 + rfv[i]
        if pending is not None:
            px = Ov[i] if fill == "open" else Cv[i]
            pxs = np.where(np.isnan(px), 0.0, px)
            E = cash + float(np.nansum(u * pxs))
            w = np.nan_to_num(pending)
            safe = np.where(pxs > 0, pxs, 1.0)
            Enet = E                                    # weights apply to post-cost equity: Enet = E - cost * traded(Enet)
            for _ in range(8):
                newu = np.where(pxs > 0, w * Enet / safe, 0.0)
                traded = float(np.sum(np.abs(newu - u) * pxs))
                Enet = E - cost * traded
            newu = np.where(pxs > 0, w * Enet / safe, 0.0)
            du = newu - u
            traded = float(np.sum(np.abs(du) * pxs))
            c = traded * cost
            cash = E - float(np.sum(newu * pxs)) - c
            for j in np.flatnonzero(np.abs(du) * pxs > 1e-12):
                fills.append((idx[i], C.columns[j], float(du[j] * pxs[j] / E), float(newu[j])))
            u = newu
            costs[i] = c / E
            turn[i] = traded / E
            pending = None
        val = np.where(np.isnan(Cv[i]), 0.0, Cv[i])
        E = cash + float(np.sum(u * val))
        eq[i] = E
        gross[i] = float(np.sum(u * val)) / E if E > 0 else 0.0
        row = T[i]
        if not np.all(np.isnan(row)):
            w = np.nan_to_num(row)
            cur = u * val / E
            if band is None or np.max(np.abs(w - cur)) >= band or (w.sum() == 0 and cur.sum() > 0):
                if np.max(np.abs(w - cur)) > 1e-6:
                    pending = row
    s = pd.Series(eq, index=idx)
    return {"eq": s, "ret": s.pct_change(), "gross": pd.Series(gross, index=idx), "cost": pd.Series(costs, index=idx),
            "turn": pd.Series(turn, index=idx), "fills": fills, "units_end": u}


def episodes(fills, O, cost=BASE_COST):
    """Per-asset holding episodes (first buy from flat -> sale back to flat): gross price return at fill opens, minus 2 x cost."""
    out, open_ = [], {}
    held = {}
    for d, a, dw, units_after in fills:
        before = held.get(a, 0.0)
        after = units_after
        held[a] = after
        if before <= 1e-12 and after > 1e-12:
            open_[a] = d
        elif before > 1e-12 and after <= 1e-12 and a in open_:
            e = open_.pop(a)
            out.append(O.loc[d, a] / O.loc[e, a] - 1 - 2 * cost)
    return out


# ------------------------------------------------------------------ metrics
def window_stats(res, rf, a, b, fills=None, O=None, cost=BASE_COST):
    r = res["ret"].loc[a:b].dropna()
    f = rf.loc[r.index]
    ex = r - f
    eq = (1 + r).cumprod()
    yrs = len(r) / PPY
    tot = float(eq.iloc[-1] - 1) if len(r) else 0.0
    d = {"start": str(r.index[0].date()), "end": str(r.index[-1].date()), "days": len(r), "total_return": round(tot, 4),
         "cagr": round((1 + tot) ** (1 / yrs) - 1, 4) if yrs > 0 else None,
         "vol": round(float(r.std() * math.sqrt(PPY)), 4), "sharpe_ex": round(metrics.sharpe_annual(ex.values, PPY), 3) if ex.std() > 1e-10 else 0.0,
         "sharpe_raw": round(metrics.sharpe_annual(r.values, PPY), 3), "mdd": round(metrics.max_drawdown(r.values), 4),
         "exposure": round(float(res["gross"].loc[a:b].mean()), 3),
         "turnover_py": round(float(res["turn"].loc[a:b].sum() / yrs), 2) if yrs > 0 else None,
         "cost_drag_py": round(float(res["cost"].loc[a:b].sum() / yrs), 5) if yrs > 0 else None,
         "psr0_ex": round(metrics.psr(ex.values), 3)}
    if fills is not None:
        fl = [x for x in fills if pd.Timestamp(a) <= x[0] <= pd.Timestamp(b)]
        d["fills"] = len(fl)
        ep = episodes(fl, O, cost) if O is not None else []
        d["round_trips"] = len(ep)
        d["win_rate"] = round(float(np.mean([e > 0 for e in ep])), 3) if ep else None
        d["avg_trip"] = round(float(np.mean(ep)), 4) if ep else None
    return d


def robust_var(x):
    x = np.asarray(x, float)
    if len(x) < 3:
        return 0.0
    mad = float(np.median(np.abs(x - np.median(x))))
    return max((1.4826 * mad) ** 2, 0.0)


def dsr_ann(r, ppy, trial_sr_ann):
    """Verbatim logic of tp.research.dsr_ann (not imported: tp.research pulls crypto-only deps)."""
    x = np.asarray(trial_sr_ann, float)
    n = len(x)
    years = max(len(r) / ppy, 1e-6)
    if n < 3:
        return metrics.psr(r), 0.0, metrics.psr(r), 0.0
    sr0 = metrics.expected_max_sr(1.0 / years, n)
    rv = robust_var(x)
    med, sg = float(np.median(x)), max(rv ** 0.5, 1e-9)
    xc = x[np.abs(x - med) <= 3 * sg] if rv > 0 else x
    var = max(rv, float(np.var(xc, ddof=1)) if len(xc) > 2 else 0.0)
    sr0e = metrics.expected_max_sr(var, n)
    return metrics.psr(r, sr0 / math.sqrt(ppy)), sr0, metrics.psr(r, sr0e / math.sqrt(ppy)), sr0e


def block_bootstrap_ci(diff, block=21, n=2000, seed=0, q=(2.5, 97.5)):
    d = np.asarray(diff, float)
    T = len(d)
    rng = np.random.RandomState(seed)
    nb = int(math.ceil(T / block))
    means = np.empty(n)
    for i in range(n):
        st = rng.randint(0, T - block, size=nb)
        means[i] = np.concatenate([d[s:s + block] for s in st])[:T].mean()
    return float(np.percentile(means, q[0])), float(np.percentile(means, q[1])), float(np.mean(means <= 0))


def tcon():
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(OUT / "trials.sqlite", timeout=30)
    con.execute("CREATE TABLE IF NOT EXISTS trials(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, study TEXT, strat TEXT, side TEXT, sym TEXT, "
                "tf TEXT, variant TEXT, cost TEXT, sr_ann REAL, ppy REAL, n_bars INTEGER, selection INTEGER)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_trial ON trials(study, strat, side, sym, tf, variant, cost)")
    return con


def log_trial(con, strat, variant, cost, ex, selection):
    sr = metrics.sharpe_annual(ex, PPY)
    con.execute("INSERT OR REPLACE INTO trials(ts,study,strat,side,sym,tf,variant,cost,sr_ann,ppy,n_bars,selection) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "US1", strat, "long", "US-ETF", "1d", variant, cost, sr, PPY, len(ex), selection))
    con.commit()
    return sr


def run(name, O, C, rf, cost=BASE_COST, phase=0, wk_day=None, fill="open"):
    tgt, band = signals(name, C, rf, phase=phase, wk_day=wk_day)
    return simulate(tgt, O, C, rf, cost=cost, band=band, fill=fill)


# ------------------------------------------------------------------ stages
def stage_is():
    O, C, rf = load_panel()
    con = tcon()
    rows, srs = {}, {}
    for t in TRIALS + BENCH:
        res = run(t, O, C, rf)
        st = window_stats(res, rf, *IS, fills=res["fills"], O=O)
        rows[t] = st
        if t in TRIALS:
            r = res["ret"].loc[IS[0]:IS[1]].dropna()
            srs[t] = log_trial(con, t, "base", "5bp", (r - rf.loc[r.index]).values, 1)
    sel = max(TRIALS, key=lambda t: srs[t])
    for t in TRIALS:
        res = run(t, O, C, rf)
        r = res["ret"].loc[IS[0]:IS[1]].dropna()
        ex = (r - rf.loc[r.index]).values
        d1, s0, d2, s0e = dsr_ann(ex, PPY, list(srs.values()))
        rows[t].update({"dsr_null": round(d1, 3), "sr0_null": round(s0, 3), "dsr_emp": round(d2, 3), "sr0_emp": round(s0e, 3)})
    out = {"stage": "IS", "period": IS, "selected": sel, "is_sharpe_ex": {k: round(v, 3) for k, v in srs.items()}, "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "is_selection.json").write_text(json.dumps(out, indent=1))
    (HERE / "is_selection.json").write_text(json.dumps(out, indent=1))
    return out


def stage_oos():
    sel = json.loads((OUT / "is_selection.json").read_text())["selected"]
    O, C, rf = load_panel()
    res_all, out = {}, {"selected": sel, "OOS": {}, "IS": {}, "FULL": {}, "regimes": {}}
    for t in TRIALS + BENCH:
        res = run(t, O, C, rf)
        res_all[t] = res
        out["OOS"][t] = window_stats(res, rf, *OOS, fills=res["fills"], O=O)
        out["IS"][t] = window_stats(res, rf, *IS, fills=res["fills"], O=O)
        out["FULL"][t] = window_stats(res, rf, IS[0], OOS[1], fills=res["fills"], O=O)
        out["regimes"][t] = {k: window_stats(res, rf, a, b) for k, (a, b) in REGIMES.items()}
    spy = res_all["B1_spy_bh"]["ret"].loc[OOS[0]:OOS[1]]
    for t in TRIALS + ["B3_sector_ew_m", "B2_qqq_bh"]:
        rr = res_all[t]["ret"].loc[OOS[0]:OOS[1]]
        lo, hi, p = block_bootstrap_ci((rr - spy).values)
        out["OOS"][t]["vs_spy_mean_diff_ann_ci95"] = [round(lo * PPY, 4), round(hi * PPY, 4)]
        out["OOS"][t]["vs_spy_boot_p_le0"] = round(p, 3)
    for k in ("OOS", "FULL"):
        for t in TRIALS:
            r = res_all[t]["ret"].loc[(OOS if k == "OOS" else (IS[0], OOS[1]))[0]:(OOS if k == "OOS" else (IS[0], OOS[1]))[1]].dropna()
            ex = (r - rf.loc[r.index]).values
            con = tcon()
            all_sr = [x[0] for x in con.execute("SELECT sr_ann FROM trials WHERE selection=1 AND study='US1'").fetchall()]
            d1, s0, d2, s0e = dsr_ann(ex, PPY, all_sr)
            out[k][t].update({"dsr_null_n7": round(d1, 3), "dsr_emp_n7": round(d2, 3)})
    json.dump(out, open(OUT / "oos_results.json", "w"), indent=1)
    (HERE / "oos_results.json").write_text(json.dumps(out, indent=1))
    eqs = pd.DataFrame({t: res_all[t]["eq"] for t in TRIALS + BENCH}).loc[SIM_START:]
    eqs.to_csv(HERE / "equity_curves.csv", float_format="%.6f")
    return out


def stage_sens():
    """Selection = 0 diagnostics: costs, fill timing, phase. Logged with selection=0."""
    O, C, rf = load_panel()
    con = tcon()
    out = {}
    for t in TRIALS + ["B3_sector_ew_m"]:
        d = {}
        for c in (0.0, 0.0002, 0.0010, 0.0025):
            res = run(t, O, C, rf, cost=c)
            d["cost_%gbp" % (c * 1e4)] = {p: window_stats(res, rf, *w)["sharpe_ex"] for p, w in (("IS", IS), ("OOS", OOS))}
            r = res["ret"].loc[OOS[0]:OOS[1]].dropna()
            log_trial(con, t, "cost", "%gbp" % (c * 1e4), (r - rf.loc[r.index]).values, 0)
        res = run(t, O, C, rf, fill="close")
        d["fill_next_close"] = {p: window_stats(res, rf, *w)["sharpe_ex"] for p, w in (("IS", IS), ("OOS", OOS))}
        if t.endswith("_m") or t.startswith("B3"):
            for ph in (5, 10):
                res = run(t, O, C, rf, phase=ph)
                st = {p: window_stats(res, rf, *w) for p, w in (("IS", IS), ("OOS", OOS))}
                d["phase_minus%d" % ph] = {p: {"sharpe_ex": s["sharpe_ex"], "mdd": s["mdd"], "total_return": s["total_return"]} for p, s in st.items()}
                r = res["ret"].loc[OOS[0]:OOS[1]].dropna()
                log_trial(con, t, "phase%d" % ph, "5bp", (r - rf.loc[r.index]).values, 0)
        if t.endswith("_w"):
            res = run(t, O, C, rf, wk_day=2)
            st = {p: window_stats(res, rf, *w) for p, w in (("IS", IS), ("OOS", OOS))}
            d["phase_wednesday"] = {p: {"sharpe_ex": s["sharpe_ex"], "mdd": s["mdd"], "total_return": s["total_return"]} for p, s in st.items()}
        out[t] = d
    (HERE / "sensitivity.json").write_text(json.dumps(out, indent=1))
    return out


def stage_lookahead():
    O, C, rf = load_panel()
    O2, C2, rf2 = load_panel(end=IS[1])
    out = {}
    for t in TRIALS + BENCH:
        a = run(t, O, C, rf)["ret"].loc[IS[0]:IS[1]]
        b = run(t, O2, C2, rf2)["ret"].loc[IS[0]:IS[1]]
        out[t] = bool(np.allclose(a.values, b.values, equal_nan=True, rtol=0, atol=1e-12))
    (HERE / "lookahead_check.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    st = sys.argv[1]
    res = {"is": stage_is, "oos": stage_oos, "sens": stage_sens, "lookahead": stage_lookahead}[st]()
    print(json.dumps(res, indent=1)[:20000])
