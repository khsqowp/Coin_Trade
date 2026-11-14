"""KR-daily-v1 backtest. Rules: research/kr_daily_v1/PREREG_kr_daily_v1.md (hashed before this ran). Nothing here is fitted.
Signal at close t -> fill at open t+1 with per-side slippage + commission (+ sell tax for stocks). Offline, deterministic.
Usage: python bt.py [main|sens|ext]"""
import json, math, sqlite3, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

from tp import metrics, research

KR = Path("/app/kr")
DATA = KR / "data"
IDX, BOND = "069500", "114260"
SECT = ["139220", "139230", "139240", "139250", "139260", "139270", "139280", "139290"]
STK = ["005930", "005490", "005380", "009540", "012330", "051910", "055550", "105560", "032830", "000270"]
START, IS_END, OOS_START = "2012-06-01", "2019-12-31", "2020-01-01"
PPY = 252
COMM = 0.00015


def load():
    o, c = {}, {}
    for p in sorted(DATA.glob("*.parquet")):
        d = pd.read_parquet(p)
        d.index = d.index.tz_convert(None).normalize()
        o[p.stem], c[p.stem] = d["open"], d["close"]
    cal = c[IDX].index
    O, C = pd.DataFrame(o).reindex(cal), pd.DataFrame(c).reindex(cal)
    listed = C.notna()
    C = C.ffill()
    O = O.where(O > 0)                     # some ETF rows carry open=0 on no-trade days
    O = O.fillna(C.shift(1)).where(listed | listed.cummax())   # halted/no-trade day: open = previous close
    return O, C, listed


def cost_model(slip_mult=1.0, stock_tax=0.0020):
    m = {}
    for a in [IDX]: m[a] = (0.0003 * slip_mult + COMM, 0.0003 * slip_mult + COMM)
    m[BOND] = (0.0005 * slip_mult + COMM, 0.0005 * slip_mult + COMM)
    for a in SECT: m[a] = (0.0020 * slip_mult + COMM, 0.0020 * slip_mult + COMM)
    for a in STK: m[a] = (0.0010 * slip_mult + COMM, 0.0010 * slip_mult + COMM + stock_tax)
    return m          # asset -> (buy cost frac, sell cost frac)


# ------------------------------------------------------------------ signals (each returns target weights on DECISION days only)
def month_ends(cal):
    s = pd.Series(cal, index=cal)
    return set(s.groupby([cal.year, cal.month]).max())


def week_ends(cal):
    s = pd.Series(cal, index=cal)
    iso = cal.isocalendar()
    return set(s.groupby([iso.year.values, iso.week.values]).max())


def mkt_filter(C):
    cal = C.index
    me = sorted(month_ends(cal))
    mc = C[IDX].loc[me]
    on = (mc > mc.rolling(10).mean())
    return on                                  # indexed by month-end dates


def sig_t1(C):
    on = mkt_filter(C)
    return pd.DataFrame({IDX: on.astype(float)}).loc[on.index[9:]]


def sig_t2(C):
    me = sorted(month_ends(C.index))
    r12 = (C[IDX] / C[IDX].shift(252) - 1).loc[me].dropna()
    return pd.DataFrame({IDX: (r12 > 0).astype(float)})


def sig_t3(C):
    vol = C[IDX].pct_change().rolling(20).std() * math.sqrt(PPY)
    w = (0.15 / vol).clip(upper=1.0)
    we = sorted(week_ends(C.index))
    return pd.DataFrame({IDX: w.loc[we].dropna()})        # 0.10 hysteresis applied in the simulator (band=0.10)


def rsi_wilder(x, n=2):
    d = x.diff()
    up, dn = d.clip(lower=0), (-d).clip(lower=0)
    au, ad = up.ewm(alpha=1 / n, adjust=False).mean(), dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad.replace(0, np.nan))


def sig_t4(C):
    x = C[IDX]
    sma200, sma5, r = x.rolling(200).mean(), x.rolling(5).mean(), rsi_wilder(x, 2)
    pos, out = 0.0, {}
    for t in x.index[200:]:
        if pos == 0 and x[t] > sma200[t] and r[t] < 10:
            pos = 1.0
        elif pos == 1 and x[t] > sma5[t]:
            pos = 0.0
        out[t] = pos
    return pd.DataFrame({IDX: pd.Series(out)})


def sig_xsmom(C, assets, use_filter):
    me = sorted(month_ends(C.index))
    mom = (C[assets].shift(21) / C[assets].shift(252) - 1).loc[me]
    on = mkt_filter(C)
    rows = {}
    for t in me:
        m = mom.loc[t].dropna()
        if len(m) < 3 or pd.isna(on.get(t)) or (t not in on.index):
            continue
        w = pd.Series(0.0, index=assets)
        if not (use_filter and not bool(on[t])) and not pd.isna(C[IDX].loc[:t].tail(1).iloc[0]):
            top = m.sort_values(ascending=False).head(3)
            for a, v in top.items():
                if v > 0:
                    w[a] = 1 / 3
        rows[t] = w
    return pd.DataFrame(rows).T


def sig_eqw(C, assets, listed):
    me = sorted(month_ends(C.index))
    rows = {}
    for t in me:
        av = [a for a in assets if listed[a].loc[:t].any()]
        rows[t] = pd.Series({a: (1 / len(av) if a in av else 0.0) for a in assets})
    return pd.DataFrame(rows).T


def sig_bh(C):
    return pd.DataFrame({IDX: pd.Series(1.0, index=[C.index[0]])})


# ------------------------------------------------------------------ simulator
def simulate(targets, O, C, cm, start=START, end=None, full_rebal=False, band=0.0, cash_asset=None, capital=None):
    """targets: DataFrame decision_date x asset -> weight (missing asset = 0). Executed at the next open.
    Unchanged target weights are not re-traded (drift kept) unless full_rebal. band: trade only if |new-old target| >= band (T3).
    cash_asset: residual weight goes to this asset (sensitivity). capital: integer shares at this KRW capital."""
    cal = C.index
    assets = sorted(set(targets.columns) | ({cash_asset} if cash_asset else set()))
    targets = targets.reindex(columns=assets).fillna(0.0)
    d0 = cal[cal < pd.Timestamp(start)][-1]
    days = cal[cal >= d0] if end is None else cal[(cal >= d0) & (cal <= pd.Timestamp(end))]
    tdec = targets.loc[targets.index <= d0]
    cur_t = tdec.iloc[-1].copy() if len(tdec) else pd.Series(0.0, index=assets)   # target in force at the start (executed day 1)
    pending = cur_t.copy() if len(tdec) else None
    cur_t = pd.Series(0.0, index=assets) if pending is not None else cur_t
    if cash_asset and pending is not None:
        pending[cash_asset] = max(0.0, 1 - pending.drop(cash_asset).sum())
    nav0 = float(capital or 1.0)
    cash, val = nav0, pd.Series(0.0, index=assets)
    navs, costs_paid, trades, open_ep = [], 0.0, [], {}
    Ov, Cv = O[assets], C[assets]
    prev = d0
    for t in days[1:]:
        o, c, cp = Ov.loc[t], Cv.loc[t], Cv.loc[prev]
        val = val * (o / cp).fillna(1.0)
        if pending is not None:
            nav_o = cash + val.sum()
            changed = [a for a in assets if full_rebal or abs(pending[a] - cur_t[a]) > 1e-12]
            sells, buys = {}, {}
            for a in changed:
                tgt = pending[a] * nav_o
                if capital:
                    tgt = math.floor(tgt / o[a]) * o[a] if o[a] > 0 else 0.0
                d = tgt - val[a]
                if d < -1e-12: sells[a] = -d
                elif d > 1e-12: buys[a] = d
            for a, x in sells.items():
                fee = x * cm[a][1]
                cash += x - fee; val[a] -= x; costs_paid += fee
                ep = open_ep.setdefault(a, [0.0, 0.0]); ep[1] += x - fee
                if val[a] <= 1e-9 * nav0:
                    val[a] = 0.0; trades.append(ep[1] / ep[0] - 1 if ep[0] > 0 else 0.0); open_ep.pop(a)
            tot_b = sum(x * (1 + cm[a][0]) for a, x in buys.items())
            scale = min(1.0, cash / tot_b) if tot_b > 0 else 1.0
            for a, x in buys.items():
                x *= scale
                if capital and o[a] > 0:
                    x = math.floor(x / o[a]) * o[a]
                fee = x * cm[a][0]
                cash -= x + fee; val[a] += x; costs_paid += fee
                ep = open_ep.setdefault(a, [0.0, 0.0]); ep[0] += x + fee
            cur_t = pending.copy()
            pending = None
        val = val * (c / o).fillna(1.0)
        navs.append((t, cash + val.sum(), float(val.sum() / (cash + val.sum()))))
        if t in targets.index:
            nt = targets.loc[t].copy()
            if cash_asset:
                nt[cash_asset] = max(0.0, 1 - nt.drop(cash_asset).sum())
            if band > 0 and (nt - cur_t).abs().max() < band:
                pass
            elif (nt - cur_t).abs().max() > 1e-12 or full_rebal:
                pending = nt
        prev = t
    nav = pd.DataFrame(navs, columns=["t", "nav", "expo"]).set_index("t")
    nav["ret"] = nav["nav"].pct_change().fillna(nav["nav"].iloc[0] / nav0 - 1)
    for a, ep in open_ep.items():                                   # mark open episodes at the last close, net of exit costs
        trades.append((val[a] * (1 - cm[a][1]) + ep[1]) / ep[0] - 1 if ep[0] > 0 else 0.0)
    return nav, {"costs": costs_paid / nav0, "trades": trades}


# ------------------------------------------------------------------ metrics
def stats(r, expo=None):
    r = np.asarray(r, float)
    if len(r) < 5:
        return {}
    yrs = len(r) / PPY
    tot = float(np.prod(1 + r) - 1)
    out = {"days": len(r), "total_return": round(tot, 4), "cagr": round((1 + tot) ** (1 / yrs) - 1, 4),
           "sharpe": round(metrics.sharpe_annual(r, PPY), 3), "vol": round(float(r.std(ddof=1) * math.sqrt(PPY)), 4),
           "mdd": round(metrics.max_drawdown(r), 4), "psr0": round(metrics.psr(r), 3)}
    if expo is not None:
        out["time_in_market"] = round(float((np.asarray(expo) > 0.01).mean()), 3)
    return out


def trade_stats(tr):
    tr = np.asarray(tr, float)
    return {"round_trips": int(len(tr)), "win_rate": round(float((tr > 0).mean()), 3) if len(tr) else None,
            "avg_trade": round(float(tr.mean()), 4) if len(tr) else None}


def regimes():
    p = KR / "REGIMES.json"
    return json.loads(p.read_text())["windows"] if p.exists() else []


def by_regime(nav, bench_nav):
    out = []
    for w in regimes():
        m = (nav.index >= w["start"]) & (nav.index <= w["end"])
        s, b = nav["ret"][m], bench_nav["ret"].reindex(nav.index)[m]
        out.append({"label": w["label"], "type": w["type"], "start": w["start"], "end": w["end"],
                    "strat": stats(s.values, nav["expo"][m].values), "B1": stats(b.values)})
    types = {}
    for typ in ("bull", "bear", "chop"):
        m = np.zeros(len(nav), bool)
        for w in regimes():
            if w["type"] == typ:
                m |= (nav.index >= w["start"]) & (nav.index <= w["end"])
        types[typ] = {"strat": stats(nav["ret"][m].values), "B1": stats(bench_nav["ret"].reindex(nav.index)[m].values)}
    return out, types


def tcon():
    con = sqlite3.connect(KR / "trials.sqlite")
    con.execute("CREATE TABLE IF NOT EXISTS trials(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, study TEXT, strat TEXT, side TEXT, sym TEXT, "
                "tf TEXT, variant TEXT, cost TEXT, sr_ann REAL, ppy REAL, n_bars INTEGER, selection INTEGER)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_trial ON trials(study, strat, side, sym, tf, variant, cost)")
    return con


def build(C, listed):
    return {
        "T1_IDX_SMA10M": (sig_t1(C), {}),
        "T2_IDX_TSMOM12": (sig_t2(C), {}),
        "T3_IDX_VOLTGT15": (sig_t3(C), {"band": 0.10}),
        "T4_IDX_RSI2": (sig_t4(C), {}),
        "T5_SEC_MOM3": (sig_xsmom(C, SECT, False), {}),
        "T6_SEC_MOM3_MF": (sig_xsmom(C, SECT, True), {}),
        "T7_STK_MOM3": (sig_xsmom(C, STK, False), {}),
        "T8_STK_MOM3_MF": (sig_xsmom(C, STK, True), {}),
    }


def bench(C, listed):
    return {"B1_BH_069500": (sig_bh(C), {}),
            "B2_EQW_SECTORS": (sig_eqw(C, SECT, listed), {"full_rebal": True}),
            "B3_EQW_STOCKS10": (sig_eqw(C, STK, listed), {"full_rebal": True})}


def split_stats(nav):
    ins, oos = nav.loc[:IS_END], nav.loc[OOS_START:]
    return {"IS": stats(ins["ret"].values, ins["expo"].values), "OOS": stats(oos["ret"].values, oos["expo"].values),
            "FULL": stats(nav["ret"].values, nav["expo"].values)}


def main():
    O, C, listed = load()
    cm = cost_model()
    con = tcon()
    res, navs = {}, {}
    for name, (tg, kw) in {**build(C, listed), **bench(C, listed)}.items():
        nav, ex = simulate(tg, O, C, cm, **kw)
        navs[name] = nav
        sel = 1 if name.startswith("T") else 0
        ins = nav.loc[:IS_END]["ret"].values
        con.execute("INSERT OR REPLACE INTO trials(ts,study,strat,side,sym,tf,variant,cost,sr_ann,ppy,n_bars,selection) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "KR1", name, "long", "-", "1d", "IS", "primary",
                     metrics.sharpe_annual(ins, PPY), PPY, len(ins), sel))
        yrs = len(nav) / PPY
        res[name] = {**split_stats(nav), **trade_stats(ex["trades"]), "cost_drag_per_yr": round(ex["costs"] / yrs, 4),
                     "n_decisions": int(len(tg))}
    con.commit()
    trial_is = np.array([r[0] for r in con.execute("SELECT sr_ann FROM trials WHERE study='KR1' AND selection=1 AND variant='IS' AND cost='primary'")])
    full_sr = np.array([res[k]["FULL"]["sharpe"] for k in res if k.startswith("T")])
    oos_sr = np.array([res[k]["OOS"]["sharpe"] for k in res if k.startswith("T")])
    b1 = navs["B1_BH_069500"]
    for k in res:
        nav = navs[k]
        for seg, rr, pool_ in (("IS", nav.loc[:IS_END]["ret"].values, trial_is), ("OOS", nav.loc[OOS_START:]["ret"].values, oos_sr),
                               ("FULL", nav["ret"].values, full_sr)):
            d, sr0, de, sr0e = research.dsr_ann(rr, PPY, pool_)
            res[k][seg].update({"dsr_null": round(d, 3), "dsr_null_sr0": round(sr0, 3), "dsr_emp": round(de, 3), "dsr_emp_sr0": round(sr0e, 3)})
        res[k]["regimes"], res[k]["regime_types"] = by_regime(nav, b1)
        diff = (nav["ret"] - b1["ret"].reindex(nav.index)).loc[OOS_START:].values
        lo, hi = research.block_bootstrap_ci(diff, block=20, n=2000)
        res[k]["oos_daily_excess_vs_B1_ci90_ann"] = [round(lo * PPY, 4), round(hi * PPY, 4)]
    pick = max((k for k in res if k.startswith("T")), key=lambda k: res[k]["IS"]["sharpe"])
    out = {"n_selection_trials": int(len(trial_is)), "is_pick": pick, "window": [str(b1.index[0].date()), str(b1.index[-1].date())], "results": res}
    (KR / "results_main.json").write_text(json.dumps(out, indent=1, default=str))
    pd.DataFrame({k: v["nav"] for k, v in navs.items()}).to_csv(KR / "nav_main.csv")
    print(json.dumps({"pick": pick, "n": len(trial_is)}))


def sens():
    O, C, listed = load()
    out = {}
    specs = {"slip_x2": dict(cm=cost_model(2.0)), "slip_x3": dict(cm=cost_model(3.0)), "stock_tax_0.30": dict(cm=cost_model(1.0, 0.0030)),
             "cash_in_114260": dict(cm=cost_model(), cash_asset=BOND), "int_shares_10M_KRW": dict(cm=cost_model(), capital=10_000_000)}
    allsig = {**build(C, listed), **bench(C, listed)}
    for sname, sp in specs.items():
        out[sname] = {}
        for name, (tg, kw) in allsig.items():
            if sp.get("cash_asset") and not name.startswith("T"):
                continue
            kw2 = {**kw, **{k: v for k, v in sp.items() if k != "cm"}}
            nav, ex = simulate(tg, O, C, sp["cm"], **kw2)
            out[sname][name] = {**split_stats(nav), "cost_drag_per_yr": round(ex["costs"] / (len(nav) / PPY), 4)}
    # rebalance-phase sensitivity: execute monthly decisions 5 trading days later (informational, selection=0)
    out["phase_plus5d"] = {}
    for name, (tg, kw) in allsig.items():
        if name in ("T3_IDX_VOLTGT15", "T4_IDX_RSI2", "B1_BH_069500"):
            continue
        cal = C.index
        pos = [cal.get_loc(t) for t in tg.index]
        tg2 = tg.copy(); tg2.index = [cal[min(p + 5, len(cal) - 1)] for p in pos]
        tg2 = tg2[~tg2.index.duplicated(keep="last")]
        nav, ex = simulate(tg2, O, C, cost_model(), **kw)
        out["phase_plus5d"][name] = split_stats(nav)
    (KR / "results_sens.json").write_text(json.dumps(out, indent=1, default=str))
    print("sens done")


def ext():
    """Index-only trials over the longer 069500 history (2008-06 .. 2012-05, pre-window: GFC + 2011 crash). selection=0, informational."""
    O, C, listed = load()
    cm = cost_model()
    out = {}
    for name, tg, kw in [("T1_IDX_SMA10M", sig_t1(C), {}), ("T2_IDX_TSMOM12", sig_t2(C), {}), ("T3_IDX_VOLTGT15", sig_t3(C), {"band": 0.10}),
                         ("T4_IDX_RSI2", sig_t4(C), {}), ("B1_BH_069500", sig_bh(C), {})]:
        nav, ex = simulate(tg, O, C, cm, start="2008-06-02", end="2012-05-31", **kw)
        out[name] = {"PRE_2008_06_2012_05": stats(nav["ret"].values, nav["expo"].values), **trade_stats(ex["trades"])}
    (KR / "results_ext.json").write_text(json.dumps(out, indent=1, default=str))
    print("ext done")


if __name__ == "__main__":
    {"main": main, "sens": sens, "ext": ext}[sys.argv[1] if len(sys.argv) > 1 else "main"]()
