"""Pre-specified KR weekly SMA40 long/flat backtest. Offline; uses bt2's panel and portfolio engine."""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import bt2

KR = Path(os.environ.get("KR_DIR", "/app/kr"))
V1 = Path(os.environ.get("V1_DIR", "/app/v1"))


def weekly_signal(close, week_idx):
    """Return weekly close, SMA40, and causal long/flat signal arrays."""
    wc = np.asarray(close, float)[np.asarray(week_idx, int)]
    ma = pd.DataFrame(wc).rolling(40, min_periods=40).mean().to_numpy()
    return wc, ma, np.isfinite(ma) & (wc > ma)


def _stats(r, expo=None):
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return {}
    nav = np.cumprod(1 + r)
    years = len(r) / bt2.PPY
    peak = np.maximum.accumulate(np.r_[1.0, nav])[1:]
    # CAGR is only meaningful with >=~1 quarter of history; annualising shorter windows produces
    # numerically explosive values (small 'years' exponent) that would otherwise dominate the cross-sectional mean.
    cagr = float(nav[-1] ** (1 / years) - 1) if (nav[-1] > 0 and years >= 0.25) else None
    return {"days": int(len(r)), "total_return": float(nav[-1] - 1),
            "cagr": cagr,
            "sharpe": float(bt2.metrics.sharpe_annual(r, bt2.PPY)),
            "mdd": float(-np.min(nav / peak - 1)),
            "win_rate_in_market": float(np.mean(r[np.asarray(expo, bool)] > 0)) if expo is not None and np.asarray(expo, bool).any() else None,
            "time_in_market": float(np.mean(expo)) if expo is not None else None}


def _per_symbol(P, sig_daily, active):
    """Vectorized independent all-in equity curves; daily mark uses adjusted close and open fills."""
    T, N = P.cf.shape
    close = P.cf.astype(float)
    open_ = P.o.astype(float)
    wanted = sig_daily & active
    # Decision at close t is filled at open t+1.
    target = np.vstack([np.zeros((1, N), bool), wanted[:-1]])
    held = np.zeros(N, bool)
    nav = np.ones(N)
    prev_close = close[0].copy()
    rets = np.zeros((T, N), float)
    exposure = np.zeros((T, N), bool)
    entries = np.zeros((T, N), bool)
    for t in range(1, T):
        op = open_[t]
        op = np.where(np.isfinite(op) & (op > 0), op, prev_close)
        valid = np.isfinite(op) & (op > 0) & np.isfinite(close[t]) & (close[t] > 0)
        # Force out when no longer eligible; otherwise use the delayed weekly target.
        desired = target[t] & active[t] & valid
        buy = desired & ~held
        sell = ~desired & held
        was_held = held.copy()
        fee_buy = np.zeros(N); fee_sell = np.zeros(N)
        fee_buy[buy] = bt2.COMM + np.array([bt2.slip_of(P.med60[t-1, j]) for j in np.flatnonzero(buy)])
        fee_sell[sell] = bt2.COMM + bt2.TAX + np.array([bt2.slip_of(P.med60[t-1, j]) for j in np.flatnonzero(sell)])
        nav *= np.where(buy, 1 / (1 + fee_buy), 1) * np.where(sell, 1 - fee_sell, 1)
        entries[t] = buy
        # Close-to-open then open-to-close return while held after fills.
        gap = np.divide(op, prev_close, out=np.ones(N), where=np.isfinite(prev_close) & (prev_close > 0)) - 1
        intraday = np.divide(close[t], op, out=np.ones(N), where=op > 0) - 1
        dayret = np.where(was_held, 1 + gap, 1.0) * np.where(desired, 1 + intraday, 1.0) - 1
        nav *= 1 + dayret
        # Include transaction costs in the daily return.
        rets[t] = (1 + dayret) * np.where(buy, 1 / (1 + fee_buy), 1) * np.where(sell, 1 - fee_sell, 1) - 1
        exposure[t] = desired
        held = desired
        prev_close = np.where(np.isfinite(close[t]), close[t], prev_close)
    return rets, exposure, entries


def _symbol_summary(P, rets, expo, entries, bh_ret):
    idx = pd.DatetimeIndex(P.cal)
    windows = {"IS": (idx >= bt2.START) & (idx <= bt2.IS_END),
               "OOS": (idx >= bt2.OOS_START) & (idx <= bt2.END),
               "FULL": (idx >= bt2.START) & (idx <= bt2.END)}
    rows = []
    for j, sym in enumerate(P.syms):
        if not P.elig[:, j].any():
            continue
        row = {"symbol": sym}
        for label, m in windows.items():
            ix = m & P.elig[:, j]
            rr, ee = rets[ix, j], expo[ix, j]
            sm = _stats(rr, ee)
            br = bh_ret[ix, j]
            bht = float(np.prod(1 + br) - 1) if len(br) else 0.0
            sm["entries"] = int(entries[ix, j].sum())
            sm["buy_hold_total_return"] = bht
            sm["excess_vs_buy_hold"] = sm.get("total_return", 0.0) - bht
            row[label] = sm
        rows.append(row)
    summary = {}
    for label in windows:
        summary[label] = {}
        for metric in ("total_return", "cagr", "sharpe", "mdd", "win_rate_in_market", "entries", "time_in_market", "excess_vs_buy_hold"):
            vals = [r[label].get(metric) for r in rows if r[label].get(metric) is not None and np.isfinite(r[label][metric])]
            summary[label][metric] = {"mean": float(np.mean(vals)) if vals else None, "median": float(np.median(vals)) if vals else None}
        ex = [r[label]["excess_vs_buy_hold"] for r in rows]
        summary[label]["beat_buy_hold"] = {"count": int(sum(x > 0 for x in ex)), "eligible_count": len(ex)}
    return rows, summary


def smoke_test():
    """Fast synthetic causality and single-name cost parity check against bt2.simulate."""
    x = np.arange(1.0, 46.0)[:, None]
    _, ma, s = weekly_signal(x, np.arange(40))
    changed = x.copy(); changed[40:] *= 100
    _, ma2, s2 = weekly_signal(changed, np.arange(40))
    assert np.allclose(ma[:39], ma2[:39], equal_nan=True) and np.array_equal(s[:39], s2[:39])
    P = bt2.Panel(); P.cal = pd.bdate_range("2020-01-01", periods=5); P.t0 = 1
    P.cf = np.array([[100.], [100.], [102.], [104.], [105.]])
    P.c = P.cf.copy(); P.o = P.cf.copy(); P.row = np.ones((5, 1), bool)
    P.trad = P.row.copy(); P.med60 = np.full((5, 1), 6e10); P.last = np.array([4])
    P.has = P.row.copy()
    own, _, _ = _per_symbol(P, np.ones((5, 1), bool), P.row)
    nav, _ = bt2.simulate(P, {0: {0: 1.0}}, mode="full", full_rebal=False)
    assert np.isclose(np.prod(1 + own[1:, 0]), np.prod(1 + nav["ret"].values), atol=1e-9)
    return True


def main():
    P = bt2.load_panel()
    widx = np.array(sorted(bt2.week_end_idx(P.cal)), int)
    wc, ma, weekly = weekly_signal(P.cf, widx)
    daily = np.zeros_like(P.elig, bool)
    for q, t in enumerate(widx):
        if q + 1 < len(widx):
            daily[t:widx[q + 1] + 1] = weekly[q]
        else:
            daily[t:] = weekly[q]
    daily &= P.elig
    sig = {}
    for q, t in enumerate(widx):
        if t < P.t0 - 1:
            continue
        ix = np.flatnonzero(weekly[q] & P.elig[t])
        sig[int(t)] = {int(j): 1.0 / len(ix) for j in ix} if len(ix) else {}
    # Independent curves; adjusted-close B&H comparator is frictionless by definition.
    active = P.elig
    rmat, exmat, entries = _per_symbol(P, daily, active)
    bh = np.zeros_like(rmat)
    prev = np.vstack([P.cf[0], P.cf[:-1]]).astype(float)
    bh[1:] = np.where(active[1:] & active[:-1], P.cf[1:] / np.where(prev[1:] > 0, prev[1:], np.nan) - 1, 0)
    per_rows, per_summary = _symbol_summary(P, rmat, exmat, entries, bh)
    nav, ex = bt2.simulate(P, sig, mode="full", full_rebal=False, capital=1e8)
    b1 = bt2.b1_nav(P)
    ew_sig = bt2.sig_ew(P, all_elig=True)
    ew_nav, ex_ew = bt2.simulate(P, ew_sig, mode="full", full_rebal=False)
    # Delta/"sticky-weight" variant: only trade on entry (weight = 1/n_active AT ENTRY, held fixed, no re-equalisation
    # when other names enter/exit) and on exit (close to 0). Isolates turnover-from-breadth (every week's full
    # re-equalisation across a large, changing active set) from turnover-from-the-signal-itself.
    held_prev, dsig = set(), {}
    for q, t in enumerate(widx):
        if t < P.t0 - 1:
            continue
        active_now = set(np.flatnonzero(weekly[q] & P.elig[t]).tolist())
        n_act = len(active_now)
        ch = {}
        for a in held_prev - active_now:
            ch[a] = 0.0
        for a in active_now - held_prev:
            ch[a] = 1.0 / n_act if n_act else 0.0
        if ch:
            dsig[int(t)] = ch
        held_prev = active_now
    nav_sticky, ex_sticky = bt2.simulate(P, dsig, mode="delta", full_rebal=False, capital=1e8)
    sens = {}
    for label, kwargs in {"slip_2x": {"slip_mult": 2.0}, "tax_30bp": {"tax": 0.0030}}.items():
        sn, _ = bt2.simulate(P, sig, mode="full", full_rebal=False, **kwargs)
        base = bt2.split(nav)["OOS"].get("sharpe")
        stressed = bt2.split(sn)["OOS"].get("sharpe")
        sens[label] = {"oos_sharpe": stressed, "delta_vs_base": stressed - base if stressed is not None and base is not None else None}

    def with_cost(navdf, exdict):
        s = bt2.split(navdf)
        yrs = len(navdf) / bt2.PPY
        s["cost_drag_per_yr"] = round(exdict["costs"] / yrs, 4)
        return s

    result = {"strategy": "weekly close > inclusive SMA40; long/flat; next-session open fills",
              "universe": {"definition": "P.elig: >=252 observed bars, traded, >=55 traded sessions and 60-session median traded value >=1bn KRW", "symbols": len(P.syms), "ever_eligible": int(active.any(axis=0).sum()), "week_ends": int(len(widx))},
              "per_symbol_summary": per_summary, "per_symbol": per_rows,
              "portfolio": {"strategy_full_reequalize": with_cost(nav, ex), "B1_069500_buy_hold": bt2.split(b1),
                            "EW_eligible_buy_hold_style": with_cost(ew_nav, ex_ew),
                            "strategy_sticky_weight_at_entry": with_cost(nav_sticky, ex_sticky)},
              "sensitivity": sens}
    KR.mkdir(parents=True, exist_ok=True)
    (KR / "results_ma40.json").write_text(json.dumps(result, indent=1, default=str))
    nav.to_csv(KR / "nav_ma40.csv", index_label="date")
    print(json.dumps({"portfolio": result["portfolio"], "sensitivity": sens}, indent=1, default=str))


if __name__ == "__main__":
    main()
