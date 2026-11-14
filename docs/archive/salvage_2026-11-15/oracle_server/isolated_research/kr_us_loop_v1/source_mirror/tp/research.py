"""Research round 2: futures-cost baselines, adaptive (regime -> strategy/timeframe/side/risk) walk-forward, AI-role overlays.
See research/PREREG_round2.md (written before these results). LLM/news judgements are NEVER used here (history contamination);
everything is deterministic, causal and uses frozen pool strategies. No order functionality exists anywhere in this module."""
import hashlib
import itertools
import json
import math
import os
import sqlite3
import time

import numpy as np
import pandas as pd

from . import costs, futbt, metrics, pool, regime_det, store
from .config import RUNS

RES = RUNS / "research"
SRC = "binanceusdm"
STRATS = ["coin_trend_mtf", "coin_mean_reversion", "coin_breakout_squeeze", "coin_momentum_accel", "coin_chart_patterns"]
ALT = "coin_btc_regime_alt"
SIDES = ("long", "short", "ls")
TFS = ("5m", "15m", "1h", "4h")
SYMS = ("BTC/USDT", "ETH/USDT")
PPY = store.PERIODS_PER_YEAR
TF_MS = store.TF_MS
BASE_COST = costs.BASE_FUT


# ------------------------------------------------------------------ helpers
def ms(index):
    return ((index - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).values.astype("int64")


def load_df(sym, tf):
    return store.get_ohlcv(sym, tf, source=SRC)


def fund_arr(sym, df, tf):
    ts, rate = futbt.load_funding(sym.replace("/", ""))
    return futbt.funding_per_bar(df.index, TF_MS[tf], ts, rate)


def with_btc(df, tf):
    b = load_df("BTC/USDT", tf)
    out = df.copy()
    for k in ("close", "high", "low"):
        out["btc_" + k] = b[k].reindex(df.index)
    return out.dropna(subset=["btc_close"])


_SIG_CACHE = {}


def get_signal(strat, side, sym, tf, df=None):
    """Signal Series in {-1,0,1} on `df` index. long = pool signal; short = same code on the inverse-price mirror; ls = long - short."""
    key = (strat, side, sym, tf)
    if key in _SIG_CACHE:
        return _SIG_CACHE[key]
    df = load_df(sym, tf) if df is None else df
    mod = pool.load(strat)
    need_btc = getattr(mod, "NEEDS_BTC", False)

    def run(d):
        dd = with_btc(d, tf) if need_btc else d
        return mod.generate_signals(dd).reindex(d.index).fillna(0.0)
    if side == "long":
        s = run(df)
    elif side == "short":
        s = -run(futbt.mirror(df))
    else:
        s = run(df) - run(futbt.mirror(df))
    _SIG_CACHE[key] = s
    return s


def sim(df, sig, cost=BASE_COST, lev=1.0, nf=None, sym="BTC/USDT", tf="1h", fr=None):
    fr = fund_arr(sym, df, tf) if fr is None else fr
    return futbt.simulate(df, sig, cost, lev=lev, nf=nf, fr=fr)


def quick_ret(df, s, side_cost, fr):
    """Fast vectorised per-bar return of a signal series (continuous-rebalance semantics) used for selection / shadow tracking."""
    o, c = df["open"].values, df["close"].values
    s = np.asarray(s, float)
    h = np.r_[0.0, s[:-1]]
    hp = np.r_[0.0, h[:-1]]
    gap = np.r_[0.0, o[1:] / c[:-1] - 1.0]
    intra = c / o - 1.0
    return hp * gap + h * intra - np.abs(h - hp) * side_cost - h * fr


def align(sig_tf, tf, clock_index, clock_tf):
    """Signal known at the CLOSE of each clock bar from a series on another timeframe: latest tf bar whose end <= clock bar close."""
    ends = ms(sig_tf.index) + TF_MS[tf]
    q = ms(clock_index) + TF_MS[clock_tf]
    pos = np.searchsorted(ends, q, side="right") - 1
    vals = sig_tf.values
    return np.where(pos >= 0, vals[np.clip(pos, 0, len(vals) - 1)], 0.0)


# ------------------------------------------------------------------ trials registry
def tcon():
    RES.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(RES / "trials.sqlite", timeout=30)
    con.execute("CREATE TABLE IF NOT EXISTS trials(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, study TEXT, strat TEXT, side TEXT, sym TEXT, "
                "tf TEXT, variant TEXT, cost TEXT, sr_ann REAL, ppy REAL, n_bars INTEGER, selection INTEGER)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_trial ON trials(study, strat, side, sym, tf, variant, cost)")     # re-runs replace, never duplicate
    return con


def log_trial(con, study, strat, side, sym, tf, variant, cost, r, ppy, selection=1):
    sr = metrics.sharpe_annual(r, ppy)
    con.execute("INSERT OR REPLACE INTO trials(ts,study,strat,side,sym,tf,variant,cost,sr_ann,ppy,n_bars,selection) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), study, strat, side, sym, tf, variant, cost, sr, ppy, len(r), selection))
    return sr


def trial_summary(con, tfs=None):
    """Annualised Sharpe of all logged SELECTION trials (optionally only those on the given timeframes: costs make SRs on very different
    timeframes non-exchangeable, so the deflation is computed within the relevant timeframe group)."""
    rows = con.execute("SELECT sr_ann, tf FROM trials WHERE selection=1").fetchall()
    return np.array([r[0] for r in rows if (tfs is None or r[1] in tfs)], float)


def robust_var(x):
    x = np.asarray(x, float)
    if len(x) < 3:
        return 0.0
    mad = float(np.median(np.abs(x - np.median(x))))
    return max((1.4826 * mad) ** 2, 0.0)


def dsr_ann(r, ppy, trial_sr_ann):
    """Deflated Sharpe ratio of series r against the expected maximum annualised SR over the logged selection trials.
    PRIMARY (standard, null-hypothesis variance): trials are assumed to have zero true skill, so the cross-trial variance of the SR estimate is
    ~1/years of data. STRICTER reference ('emp'): the empirical cross-trial variance (robust, outlier-trimmed), which also contains the genuine
    cost-driven dispersion between timeframes and is therefore very conservative. Returns (dsr_primary, sr0_primary, dsr_emp, sr0_emp)."""
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


def block_bootstrap_ci(diff, block=96, n=1000, seed=0, q=(5, 95)):
    """CI of the mean of a paired per-bar difference series (moving-block bootstrap)."""
    d = np.asarray(diff, float)
    T = len(d)
    if T < 2 * block:
        return (float("nan"), float("nan"))
    rng = np.random.RandomState(seed)
    nb = int(math.ceil(T / block))
    means = np.empty(n)
    for i in range(n):
        st = rng.randint(0, T - block, size=nb)
        means[i] = np.concatenate([d[s:s + block] for s in st])[:T].mean()
    return float(np.percentile(means, q[0])), float(np.percentile(means, q[1]))


# ------------------------------------------------------------------ S1 baselines
def combos():
    for st in STRATS:
        for sym in SYMS:
            for tf in TFS:
                for side in SIDES:
                    yield st, side, sym, tf
    for tf in TFS:
        yield ALT, "long", "ETH/USDT", tf


def stats_row(res, ppy, df):
    r = res["ret"].values
    yrs = len(r) / ppy
    return {"total_return": round(float(res["equity"].iloc[-1] - 1), 4), "sharpe": round(metrics.sharpe_annual(r, ppy), 3),
            "mdd": round(metrics.max_drawdown(r), 4), "trades": int(res["n_open"]), "trades_per_year": round(res["n_open"] / yrs, 1),
            "exposure": round(float(res["h"].mean()), 3), "fees_pct_per_year": round(100 * res["fees"] / yrs, 2),
            "funding_pct_per_year": round(100 * res["funding"] / yrs, 2), "liquidations": res["n_liq"], "bars": len(r)}


def study_baseline(cost=BASE_COST, log=print):
    con = tcon()
    rows, rets = [], []
    for st, side, sym, tf in combos():
        df = load_df(sym, tf)
        sig = get_signal(st, side, sym, tf, df)
        res = sim(df, sig, cost, 1.0, 1.0, sym, tf)
        row = {"strategy": st, "side": side, "symbol": sym, "tf": tf, **stats_row(res, PPY[tf], df)}
        row["sr_ann_trial"] = log_trial(con, "S1", st, side, sym, tf, "unit", cost.name, res["ret"].values, PPY[tf])
        rows.append(row)
        rets.append(res["ret"].values)
    for row, r in zip(rows, rets):
        d, sr0, de, sr0e = dsr_ann(r, PPY[row["tf"]], trial_summary(con))        # N = ALL selection trials (124), not only this timeframe
        row["psr0"], row["dsr"], row["dsr_threshold_sr_ann"] = round(metrics.psr(r), 3), round(d, 3), round(sr0, 3)
        row["dsr_emp"], row["dsr_emp_threshold"] = round(de, 3), round(sr0e, 3)
    for sym in SYMS:                                  # buy & hold on futures (funding applied), not a selection trial
        for tf in TFS:
            df = load_df(sym, tf)
            res = sim(df, pd.Series(1.0, index=df.index), cost, 1.0, 1.0, sym, tf)
            rows.append({"strategy": "buy_hold", "side": "long", "symbol": sym, "tf": tf, **stats_row(res, PPY[tf], df)})
            log_trial(con, "S1", "buy_hold", "long", sym, tf, "unit", cost.name, res["ret"].values, PPY[tf], selection=0)
    con.commit()
    trial_sr = trial_summary(con)
    con.close()
    out = {"cost": cost.name, "n_selection_trials": int(len(trial_sr)), "rows": rows}
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "s1_baseline.json").write_text(json.dumps(out, indent=1))
    return out


# ------------------------------------------------------------------ S2 sensitivity
SENS_COMBOS = [("coin_trend_mtf", "long", "BTC/USDT", "1h"), ("coin_trend_mtf", "ls", "BTC/USDT", "15m"),
               ("coin_mean_reversion", "long", "ETH/USDT", "15m"), ("coin_breakout_squeeze", "ls", "ETH/USDT", "1h"),
               ("coin_momentum_accel", "long", "BTC/USDT", "5m"), ("coin_chart_patterns", "ls", "BTC/USDT", "1h")]


def study_sensitivity(log=print):
    out = {"cost_grid": [], "leverage": [], "mmr": [], "spot_vs_futures": []}
    con = tcon()
    for st, side, sym, tf in SENS_COMBOS:
        df = load_df(sym, tf)
        sig = get_signal(st, side, sym, tf, df)
        fr = fund_arr(sym, df, tf)
        for name, cm in costs.scenarios("futures").items():
            res = sim(df, sig, cm, 1.0, 1.0, sym, tf, fr)
            out["cost_grid"].append({"strategy": st, "side": side, "symbol": sym, "tf": tf, "scenario": name, "side_cost_pct": round(100 * cm.side_cost, 4),
                                     **stats_row(res, PPY[tf], df)})
            log_trial(con, "S2", st, side, sym, tf, "cost_grid", name, res["ret"].values, PPY[tf], selection=0)
        for lev in (1, 2, 3, 5, 10):                                   # full-equity margin
            res = sim(df, sig, BASE_COST, float(lev), float(lev), sym, tf, fr)
            out["leverage"].append({"strategy": st, "side": side, "symbol": sym, "tf": tf, "mode": "full_equity_margin", "lev": lev, **stats_row(res, PPY[tf], df)})
        for lev in (1, 3, 10):                                         # Risk-Engine 25% notional cap
            res = sim(df, sig, BASE_COST, float(lev), 0.25, sym, tf, fr)
            out["leverage"].append({"strategy": st, "side": side, "symbol": sym, "tf": tf, "mode": "notional_cap_25pct", "lev": lev, **stats_row(res, PPY[tf], df)})
        for mmr in (0.004, 0.005, 0.01):
            cm = costs.make("futures", mmr=mmr, name="mmr%.3f" % mmr)
            res = sim(df, sig, cm, 5.0, 5.0, sym, tf, fr)
            out["mmr"].append({"strategy": st, "side": side, "symbol": sym, "tf": tf, "mmr": mmr, "lev": 5, **stats_row(res, PPY[tf], df)})
        if side == "long":                                              # spot (no funding, spot fee) vs futures on the same signal
            sdf = store.get_ohlcv(sym, tf, source="binance")
            ssig = pool.load(st).generate_signals(sdf)
            from . import bt
            for nm, cm in (("spot_taker", costs.make("spot", slip=0.0002)), ("spot_bnb", costs.make("spot", bnb=True, slip=0.0002))):
                ret, h = bt.simulate(sdf, ssig, cm.fee_side, cm.slip)
                entries = int(((h > 0) & (h.shift(1).fillna(0) == 0)).sum())
                out["spot_vs_futures"].append({"strategy": st, "symbol": sym, "tf": tf, "model": nm, "side_cost_pct": round(100 * cm.side_cost, 4),
                                               "total_return": round(float((1 + ret).prod() - 1), 4), "sharpe": round(metrics.sharpe_annual(ret.values, PPY[tf]), 3),
                                               "trades": entries})
            res = sim(df, sig, BASE_COST, 1.0, 1.0, sym, tf, fr)
            out["spot_vs_futures"].append({"strategy": st, "symbol": sym, "tf": tf, "model": "futures_taker+funding",
                                           "side_cost_pct": round(100 * BASE_COST.side_cost, 4), "total_return": round(float(res["equity"].iloc[-1] - 1), 4),
                                           "sharpe": round(metrics.sharpe_annual(res["ret"].values, PPY[tf]), 3), "trades": int(res["n_open"])})
    con.commit()
    con.close()
    (RES / "s2_sensitivity.json").write_text(json.dumps(out, indent=1))
    return out


# ------------------------------------------------------------------ S3 adaptive walk-forward
A1_TABLE = {"trend_up": ("coin_trend_mtf", "long", "1h", 1.0), "trend_down": ("coin_trend_mtf", "short", "1h", 1.0),
            "range": ("coin_mean_reversion", "ls", "15m", 0.7), "high_vol": ("coin_breakout_squeeze", "ls", "15m", 0.5)}
CLOCKS = {"W15": {"clock": "15m", "days": 365, "train": 120, "test": 30, "tfs": ("15m", "1h", "4h")},
          "W5": {"clock": "5m", "days": 180, "train": 60, "test": 20, "tfs": ("5m", "15m", "1h", "4h")}}


def regime_codes(sym_for_regime, clock_df, clock):
    """Regime label (BTC 4h price classifier) aligned causally to the clock bars. Returns array of labels (object)."""
    d4 = load_df(sym_for_regime, "4h")
    lab = regime_det.classify_series(d4)
    ends = ms(lab.index) + TF_MS["4h"]
    q = ms(clock_df.index) + TF_MS[clock]
    pos = np.searchsorted(ends, q, side="right") - 1
    v = lab.values
    return np.where(pos >= 0, v[np.clip(pos, 0, len(v) - 1)], "unknown")


def cfg_signals(sym, clock, tfs, clock_df):
    cfg = {}
    for st in STRATS:
        for side in SIDES:
            for tf in tfs:
                s = get_signal(st, side, sym, tf)
                cfg[(st, side, tf)] = align(s, tf, clock_df.index, clock)
    return cfg


def study_adaptive(name, log=print):
    P = CLOCKS[name]
    clock = P["clock"]
    bar_per_day = 86400_000 // TF_MS[clock]
    con = tcon()
    out = {"study": name, "clock": clock, "folds": [], "results": {}}
    agg = {}
    for sym in SYMS:
        full = load_df(sym, clock)
        df = full.iloc[-P["days"] * bar_per_day:]
        fr = fund_arr(sym, df, clock)
        cfg = cfg_signals(sym, clock, P["tfs"], df)
        # regime from BTC always (market leader) so ETH/BTC share the same state
        labs = regime_codes("BTC/USDT", df, clock)
        side_cost = BASE_COST.side_cost
        quick = {k: quick_ret(df, v, side_cost, fr) for k, v in cfg.items()}
        n, tr, te = len(df), P["train"] * bar_per_day, P["test"] * bar_per_day
        folds = []
        a = 0
        while a + tr + te <= n:
            folds.append((a, a + tr, a + tr + te))
            a += te
        methods = {m: [] for m in ("buy_hold", "fixed_avg", "wf_best_fixed", "oracle_best_fixed", "A1_rule", "A2_learned")}
        for (s0, s1, e1) in folds:
            tsl = slice(s1, e1)
            dtest = df.iloc[tsl]
            frt = fr[tsl]
            test_ret = {}
            for k, v in cfg.items():                                   # precise futures sim of every fixed config in the test fold
                test_ret[k] = futbt.simulate(dtest, pd.Series(v[tsl], index=dtest.index), BASE_COST, 1.0, 1.0, frt)["ret"].values
            train_sr = {k: metrics.sharpe_period(q[s0:s1]) for k, q in quick.items()}
            best = max(train_sr, key=train_sr.get)
            methods["buy_hold"].append(futbt.simulate(dtest, pd.Series(1.0, index=dtest.index), BASE_COST, 1.0, 1.0, frt)["ret"].values)
            methods["fixed_avg"].append(np.mean([r for r in test_ret.values()], axis=0))
            methods["wf_best_fixed"].append(test_ret[best])
            methods["oracle_best_fixed"].append(max(test_ret.values(), key=lambda r: metrics.sharpe_period(r)))
            # A1: pre-registered rule table
            comp = a1_signal(labs, cfg)
            methods["A1_rule"].append(futbt.simulate(dtest, pd.Series(comp[tsl], index=dtest.index), BASE_COST, 1.0, 1.0, frt)["ret"].values)
            # A2: table learned on train only (mean per-bar net return inside each regime; min 200 bars else flat)
            comp2 = np.zeros(n)
            table = {}
            for reg in ("trend_up", "trend_down", "range", "high_vol"):
                m = labs[s0:s1] == reg
                if m.sum() < 200:
                    table[reg] = None
                    continue
                kbest = max(quick, key=lambda k: quick[k][s0:s1][m].mean())
                if quick[kbest][s0:s1][m].mean() <= 0:
                    table[reg] = None
                    continue
                table[reg] = kbest
                comp2 += np.where(labs == reg, cfg[kbest], 0.0)
            methods["A2_learned"].append(futbt.simulate(dtest, pd.Series(np.clip(comp2[tsl], -1, 1), index=dtest.index), BASE_COST, 1.0, 1.0, frt)["ret"].values)
            out["folds"].append({"symbol": sym, "train": [str(df.index[s0]), str(df.index[s1 - 1])], "test": [str(df.index[s1]), str(df.index[e1 - 1])],
                                 "wf_best": list(best), "a2_table": {k: (list(v) if v else None) for k, v in table.items()}})
        for m, lst in methods.items():
            agg.setdefault(m, []).append(np.concatenate(lst))
        out.setdefault("regime_share", {})[sym] = {k: round(float((labs == k).mean()), 3) for k in ("trend_up", "trend_down", "range", "high_vol", "unknown")}
    ppy = PPY[clock]
    tf_group = tuple(P["tfs"])
    trial_sr = trial_summary(con)
    for m, arrs in agg.items():
        r = np.concatenate(arrs)                                       # BTC then ETH concatenated: pooled statistics
        sr = metrics.sharpe_annual(r, ppy)
        if m in ("A1_rule", "A2_learned", "wf_best_fixed"):
            log_trial(con, name, m, "-", "pooled", clock, "walk_forward", BASE_COST.name, r, ppy, selection=1)
            trial_sr = trial_summary(con)
        d, sr0, de, sr0e = dsr_ann(r, ppy, trial_sr)
        out["results"][m] = {"oos_bars": len(r), "total_return_pooled": round(float(np.prod(1 + r) - 1), 4), "sharpe": round(sr, 3), "mdd": round(metrics.max_drawdown(r), 4),
                             "psr0": round(metrics.psr(r), 3), "dsr": round(d, 3), "dsr_sr0_ann": round(sr0, 3),
                             "dsr_emp": round(de, 3), "dsr_emp_sr0_ann": round(sr0e, 3),
                             "per_symbol_sharpe": {s: round(metrics.sharpe_annual(a, ppy), 3) for s, a in zip(SYMS, arrs)}}
    for m in ("A1_rule", "A2_learned"):
        for ref in ("wf_best_fixed", "fixed_avg", "buy_hold"):
            diff = np.concatenate(agg[m]) - np.concatenate(agg[ref])
            lo, hi = block_bootstrap_ci(diff, block=bar_per_day)
            out["results"][m].setdefault("delta_vs", {})[ref] = {"mean_bar_return_diff": float(diff.mean()), "ci90_lo": lo, "ci90_hi": hi,
                                                                 "annualised_return_diff_pct": round(100 * float(diff.mean()) * ppy, 2),
                                                                 "significant": bool(lo > 0)}
    con.commit()
    out["n_selection_trials_total"] = int(len(trial_summary(con)))
    con.close()
    (RES / ("s3_adaptive_%s.json" % name)).write_text(json.dumps(out, indent=1, default=str))
    return out



# ------------------------------------------------------------------ reusable overlays (also used by the forward tracker)
def vol_scale(df, tf):
    """(d) volatility targeting: clip(expanding-median(rv)/rv, .25, 2) in quarter steps; rv = 7-day rolling std of returns (causal)."""
    rv = pd.Series(df["close"].pct_change().values).rolling(int(7 * 86400_000 // TF_MS[tf]), min_periods=50).std().values
    med = pd.Series(rv).expanding(min_periods=100).median().shift(1).values
    scale = np.clip(np.where(np.isfinite(rv) & np.isfinite(med) & (rv > 0), med / rv, 1.0), 0.25, 2.0)
    return np.round(scale * 4) / 4


def fomc_mask(df, tf, times, hours=6):
    """(a) True within +-hours of an FOMC statement (decision-bar close time)."""
    close_t = ms(df.index) + TF_MS[tf]
    mask = np.zeros(len(df), bool)
    for t in times:
        mask |= np.abs(close_t - int(t.timestamp() * 1000)) <= hours * 3600_000
    return mask


def retire_active(df, tf, sig, fr, cost=BASE_COST):
    """(e) 1.0 while the 30-day rolling SHADOW Sharpe of the strategy (computed continuously with costs) of the previous bar is > 0."""
    win = int(30 * 86400_000 // TF_MS[tf])
    sh = pd.Series(quick_ret(df, sig, cost.side_cost, fr))
    rs = (sh.rolling(win, min_periods=win).mean() / sh.rolling(win, min_periods=win).std()).shift(1).fillna(1.0).values
    return np.where(rs > 0, 1.0, 0.0)


def a1_signal(labs, cfg):
    """Pre-registered A1 rule table -> composite signal on the clock."""
    comp = np.zeros(len(labs))
    for reg, (st, side, tf, w) in A1_TABLE.items():
        comp += np.where(labs == reg, w * cfg[(st, side, tf)], 0.0)
    return np.clip(comp, -1, 1)


# ------------------------------------------------------------------ S4 overlays (AI-role deterministic substitutes)
BASES = [("coin_trend_mtf", "ls", "BTC/USDT", "1h"), ("coin_trend_mtf", "ls", "ETH/USDT", "1h"),
         ("coin_mean_reversion", "ls", "BTC/USDT", "15m"), ("coin_mean_reversion", "ls", "ETH/USDT", "15m")]


def trade_segments(sig):
    """[(start_idx, end_idx_exclusive, sign)] contiguous same-sign position segments (position is held from the bar AFTER the signal)."""
    s = np.sign(np.asarray(sig))
    segs, i, n = [], 0, len(s)
    while i < n:
        if s[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < n and s[j + 1] == s[i]:
            j += 1
        segs.append((i, j + 1, int(s[i])))
        i = j + 1
    return segs


def logistic_fit(X, y, lam=1.0, iters=30):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.c_[np.ones(len(X)), (X - mu) / sd]
    w = np.zeros(Z.shape[1])
    R = lam * np.eye(Z.shape[1])
    R[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - y) + R @ w
        H = Z.T @ (Z * (p * (1 - p))[:, None]) + R + 1e-6 * np.eye(len(w))
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-6:
            break
    return w, mu, sd


def logistic_predict(model, X):
    w, mu, sd = model
    Z = np.c_[np.ones(len(X)), (X - mu) / sd]
    return 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))


def meta_features(df, labs):
    c, atr = df["close"], None
    from . import ind
    atr = ind.atr(df, 14)
    atrp = (atr / c)
    volrank = atrp.rolling(250, min_periods=50).apply(lambda x: (x[:-1] < x[-1]).mean(), raw=True).fillna(0.5).values
    er = ((c - c.shift(30)).abs() / c.diff().abs().rolling(30, min_periods=30).sum()).fillna(0.3).values
    dist = ((c - ind.ema(c, 50)).abs() / atr).fillna(0).values
    hour = df.index.hour.values + df.index.minute.values / 60.0
    F = np.c_[volrank, er, dist, np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24),
              (labs == "trend_up").astype(float), (labs == "trend_down").astype(float), (labs == "range").astype(float),
              (labs == "high_vol").astype(float)]
    return F


def study_overlays(log=print):
    from . import fomc
    con = tcon()
    out = {"bases": [], "summary": {}}
    try:
        fomc_times = fomc.statement_times()
    except Exception:       # noqa: BLE001
        fomc_times = []
    for st, side, sym, tf in BASES:
        df = load_df(sym, tf)
        n = len(df)
        fr = fund_arr(sym, df, tf)
        sig = get_signal(st, side, sym, tf, df).values
        labs = regime_codes("BTC/USDT", df, tf)
        ppy = PPY[tf]
        seg_n = n // 6
        oos0 = 2 * seg_n                                   # first two sixths = train-only for the learned overlay; ALL variants scored on the rest
        def score(s, lev_nf=1.0):
            res = futbt.simulate(df, pd.Series(s, index=df.index), BASE_COST, 1.0, lev_nf, fr)
            r = res["ret"].values[oos0:]
            return {"sharpe": round(metrics.sharpe_annual(r, ppy), 3), "total_return": round(float(np.prod(1 + r) - 1), 4), "mdd": round(metrics.max_drawdown(r), 4),
                    "trades": int(res["n_open"])}, r
        base_m, base_r = score(sig)
        row = {"base": [st, side, sym, tf], "oos_start": str(df.index[oos0]), "baseline": base_m, "overlays": {}}
        log_trial(con, "S4", st, side, sym, tf, "base", BASE_COST.name, base_r, ppy, selection=1)
        # (a) FOMC +-6h flat
        if fomc_times:
            mask = fomc_mask(df, tf, fomc_times)
            m_a, r_a = score(np.where(mask, 0.0, sig))
            log_trial(con, "S4", st, side, sym, tf, "fomc_filter", BASE_COST.name, r_a, ppy, selection=1)
            # placebo: same number of 12h windows at random times (quick sim)
            qb = quick_ret(df, sig, BASE_COST.side_cost, fr)[oos0:]
            sr_act = metrics.sharpe_period(quick_ret(df, np.where(mask, 0.0, sig), BASE_COST.side_cost, fr)[oos0:])
            rng = np.random.RandomState(7)
            k = len([t for t in fomc_times if df.index[0] <= pd.Timestamp(t) <= df.index[-1]])
            w = int(12 * 3600_000 // TF_MS[tf])
            better = 0
            for _ in range(500):
                mk = np.zeros(n, bool)
                for st0 in rng.randint(0, n - w, size=k):
                    mk[st0:st0 + w] = True
                if metrics.sharpe_period(quick_ret(df, np.where(mk, 0.0, sig), BASE_COST.side_cost, fr)[oos0:]) >= sr_act:
                    better += 1
            m_a.update({"events_in_data": k, "placebo_p": round((better + 1) / 501, 3), "delta_sharpe": round(m_a["sharpe"] - base_m["sharpe"], 3)})
            row["overlays"]["a_fomc_filter"] = m_a
        # (c) meta-labelling (logistic on deterministic features, purged walk-forward)
        segs = trade_segments(sig)
        F = meta_features(df, labs)
        q = quick_ret(df, sig, BASE_COST.side_cost, fr)
        T = []
        for (i, j, sgn) in segs:
            T.append({"i": i, "j": j, "x": F[max(i - 1, 0)], "y": 1.0 if np.prod(1 + q[i + 1:j + 1]) - 1 > 0 else 0.0})
        keep = np.ones(len(T), bool)
        step = seg_n
        for f0 in range(oos0, n, step):
            f1 = min(f0 + step, n)
            tr = [t for t in T if t["j"] + int(86400_000 // TF_MS[tf]) < f0]
            te_idx = [k for k, t in enumerate(T) if f0 <= t["i"] < f1]
            if len(tr) < 30 or not te_idx:
                continue
            mdl = logistic_fit(np.array([t["x"] for t in tr]), np.array([t["y"] for t in tr]))
            p = logistic_predict(mdl, np.array([T[k]["x"] for k in te_idx]))
            for k, pk_ in zip(te_idx, p):
                keep[k] = pk_ >= 0.5
        s_c = sig.copy()
        for k, t in enumerate(T):
            if not keep[k]:
                s_c[t["i"]:t["j"]] = 0.0
        m_c, r_c = score(s_c)
        m_c["trades_kept_frac_oos"] = round(float(np.mean([keep[k] for k, t in enumerate(T) if t["i"] >= oos0])) if any(t["i"] >= oos0 for t in T) else 1.0, 3)
        m_c["delta_sharpe"] = round(m_c["sharpe"] - base_m["sharpe"], 3)
        log_trial(con, "S4", st, side, sym, tf, "meta_label", BASE_COST.name, r_c, ppy, selection=1)
        row["overlays"]["c_meta_label"] = m_c
        # (d) volatility targeting
        scale = vol_scale(df, tf)
        m_d, r_d = score(sig * scale)
        m_d["delta_sharpe"] = round(m_d["sharpe"] - base_m["sharpe"], 3)
        log_trial(con, "S4", st, side, sym, tf, "vol_target", BASE_COST.name, r_d, ppy, selection=1)
        row["overlays"]["d_vol_target"] = m_d
        # (e) retirement on rolling shadow Sharpe
        active = retire_active(df, tf, sig, fr)
        m_e, r_e = score(sig * active)
        m_e["delta_sharpe"] = round(m_e["sharpe"] - base_m["sharpe"], 3)
        m_e["active_frac"] = round(float(active[oos0:].mean()), 3)
        log_trial(con, "S4", st, side, sym, tf, "retirement", BASE_COST.name, r_e, ppy, selection=1)
        row["overlays"]["e_retirement"] = m_e
        # (b) regime-switch replacement = A1/A2 in S3 (reported there)
        out["bases"].append(row)
    con.commit()
    trial_sr = trial_summary(con)
    for k in ("a_fomc_filter", "c_meta_label", "d_vol_target", "e_retirement"):
        ds = [b["overlays"][k]["delta_sharpe"] for b in out["bases"] if k in b["overlays"]]
        out["summary"][k] = {"improved_on": sum(d > 0 for d in ds), "of": len(ds), "mean_delta_sharpe": round(float(np.mean(ds)), 3) if ds else None}
    out["n_selection_trials_total"] = int(len(trial_sr))
    con.close()
    (RES / "s4_overlays.json").write_text(json.dumps(out, indent=1, default=str))
    return out
