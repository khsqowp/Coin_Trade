"""Pre-specified US weekly SMA40 long/flat backtest; offline and point-in-time universe."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from tp import metrics, usdata
from tp.config import RUNS, DATA

import usbt2

HERE = Path(__file__).resolve().parent
OUT = RUNS / "research" / "us_daily_v2"
PPY = 252


def weekly_signal(close, week_idx):
    wc = np.asarray(close, float)[np.asarray(week_idx, int)]
    ma = pd.DataFrame(wc).rolling(40, min_periods=40).mean().to_numpy()
    return wc, ma, np.isfinite(ma) & (wc > ma)


def _period_stats(r, expo=None):
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return {}
    nav = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.r_[1.0, nav])[1:]
    years = len(r) / PPY
    # Guard against numerically explosive CAGR on short windows (small 'years' exponent) dominating cross-sectional means.
    cagr = float(nav[-1] ** (1 / years) - 1) if (nav[-1] > 0 and years >= 0.25) else None
    return {"days": int(len(r)), "total_return": float(nav[-1] - 1),
            "cagr": cagr,
            "sharpe": float(metrics.sharpe_annual(r, PPY)), "mdd": float(-np.min(nav / peak - 1)),
            "win_rate_in_market": float(np.mean(r[np.asarray(expo, bool)] > 0)) if expo is not None and np.asarray(expo, bool).any() else None,
            "time_in_market": float(np.mean(expo)) if expo is not None else None}


def _vector_sim(P, signal, cost):
    """Independent all-in curves, with next-session open execution; matrices are days x symbols."""
    C, O, E = P.C.values.astype(float), P.O.values.astype(float), P.E.values
    n, k = C.shape
    close = pd.DataFrame(C).ffill().values
    target = np.vstack([np.zeros((1, k), bool), signal[:-1]])
    held = np.zeros(k, bool)
    ret = np.zeros((n, k), float)
    expo = np.zeros((n, k), bool)
    entries = np.zeros((n, k), bool)
    prev = close[0].copy()
    for t in range(1, n):
        op = np.where(np.isfinite(O[t]) & (O[t] > 0), O[t], prev)
        valid = E[t] & np.isfinite(C[t]) & (C[t] > 0) & np.isfinite(op) & (op > 0)
        desired = target[t] & valid
        buy, sell = desired & ~held, held & ~desired
        was_held = held.copy()
        fee = np.where(buy | sell, cost, 0.0)
        entries[t] = buy
        gap = np.divide(op, prev, out=np.ones(k), where=prev > 0) - 1
        intraday = np.divide(np.nan_to_num(C[t], nan=op), op, out=np.ones(k), where=op > 0) - 1
        gross = np.where(was_held, 1 + gap, 1.0) * np.where(desired, 1 + intraday, 1.0) - 1
        ret[t] = (1 + gross) * (1 - fee) - 1
        expo[t] = desired
        held = desired
        prev = np.where(np.isfinite(close[t]), close[t], prev)
    return ret, expo, entries


def _summarize(P, ret, expo, entries):
    idx, syms = P.C.index, list(P.C.columns)
    ISP, OOSP = usbt2.periods(P)
    masks = {"IS": (idx >= ISP[0]) & (idx <= ISP[1]), "OOS": (idx >= OOSP[0]) & (idx <= OOSP[1]),
             "FULL": (idx >= ISP[0]) & (idx <= OOSP[1])}
    c = P.C.ffill().values
    bh = np.zeros_like(ret)
    bh[1:] = np.nan_to_num(c[1:] / np.where(c[:-1] > 0, c[:-1], np.nan) - 1)
    rows = []
    for j, sym in enumerate(syms):
        eligible = P.E.iloc[:, j].values
        if not eligible.any():
            continue
        row = {"symbol": sym}
        for key, mask in masks.items():
            m = mask & eligible
            s = _period_stats(ret[m, j], expo[m, j])
            bht = float(np.prod(1 + bh[m, j]) - 1) if m.any() else 0.0
            s.update({"entries": int(entries[m, j].sum()), "buy_hold_total_return": bht,
                      "excess_vs_buy_hold": s.get("total_return", 0.0) - bht})
            row[key] = s
        rows.append(row)
    aggregate = {}
    fields = ("total_return", "cagr", "sharpe", "mdd", "win_rate_in_market", "entries", "time_in_market", "excess_vs_buy_hold")
    for key in masks:
        aggregate[key] = {}
        for field in fields:
            v = [r[key][field] for r in rows if r[key].get(field) is not None and np.isfinite(r[key][field])]
            aggregate[key][field] = {"mean": float(np.mean(v)) if v else None, "median": float(np.median(v)) if v else None}
        excess = [r[key]["excess_vs_buy_hold"] for r in rows]
        aggregate[key]["beat_buy_hold"] = {"count": int(sum(x > 0 for x in excess)), "eligible_count": len(excess)}
    return rows, aggregate, masks


def _stats_frame(res, P, a, b):
    r = res["ret"].loc[a:b].dropna().values
    exp = res["gross"].loc[a:b].values
    s = _period_stats(r, exp > 0.01)
    if s and "cost" in res:
        c = res["cost"].loc[a:b]
        yrs = max(len(c) / PPY, 1e-6)
        s["cost_drag_per_yr"] = float(c.sum() / yrs)
        s["annualised_turnover"] = float(res["turn"].loc[a:b].mean() * PPY)
    return s


def _portfolio_metrics(res, P, ISP, OOSP):
    full = (str(ISP[0]), str(OOSP[1]))
    return {"IS": _stats_frame(res, P, *ISP), "OOS": _stats_frame(res, P, *OOSP), "FULL": _stats_frame(res, P, *full)}


def smoke_test():
    """Fast synthetic causality and one-symbol cost parity check against usbt2.sim_targets."""
    x = np.arange(1.0, 46.0)[:, None]
    _, ma, sig = weekly_signal(x, np.arange(len(x)))
    changed = x.copy(); changed[40:] *= 100
    _, ma2, sig2 = weekly_signal(changed, np.arange(len(changed)))
    assert np.allclose(ma[:40], ma2[:40], equal_nan=True) and np.array_equal(sig[:40], sig2[:40])
    class Fake:
        pass
    P = Fake(); P.C = pd.DataFrame({"X": [100., 102., 103., 101.]}, index=pd.bdate_range("2020-01-01", periods=4))
    P.O = pd.DataFrame({"X": [100., 100., 102., 103.]}, index=P.C.index)
    P.E = pd.DataFrame(True, index=P.C.index, columns=P.C.columns)
    P.rf = pd.Series(0., index=P.C.index)
    daily = np.ones((4, 1), bool)
    own, _, _ = _vector_sim(P, daily, usbt2.BASE_COST)
    engine = usbt2.sim_targets(P, {0: np.array([1.0])}, cost=usbt2.BASE_COST, start=str(P.C.index[0].date()))
    assert np.allclose(np.prod(1 + own[1:, 0]), engine["eq"].iloc[-1], atol=1e-7)
    return True


def main():
    # cache=False: the on-disk panel.pkl was pickled while usbt2.py ran as __main__, so unpickling its Panel class
    # fails under this script's own __main__ (classic pickle module-qualification gotcha). Recompute instead of
    # mutating/overwriting the shared cache file.
    P = usbt2.load_panel(cache=False)
    # Group by ISO year and week; week numbers repeat at year boundaries.
    iso = P.C.index.isocalendar()
    widx = pd.Series(np.arange(len(P.C)), index=P.C.index).groupby([iso.year.to_numpy(), iso.week.to_numpy()]).max().to_numpy(int)
    wc, ma, wsig = weekly_signal(P.C.ffill().values, widx)
    signal = np.zeros(P.E.shape, bool)
    tg, ew = {}, {}
    for q, t in enumerate(widx):
        end = widx[q + 1] + 1 if q + 1 < len(widx) else len(P.C)
        eligible_long = wsig[q] & P.E.iloc[t].values
        signal[t:end] = wsig[q]
        ix = np.flatnonzero(eligible_long)
        w = np.zeros(P.C.shape[1]); w[ix] = 1 / len(ix) if len(ix) else 0
        tg[int(t)] = w
        elig = P.E.iloc[t].values
        ixew = np.flatnonzero(elig)
        wew = np.zeros(P.C.shape[1]); wew[ixew] = 1 / len(ixew) if len(ixew) else 0
        ew[int(t)] = wew
    signal &= P.E.values
    rmat, exmat, entries = _vector_sim(P, signal, usbt2.BASE_COST)
    rows, aggregate, masks = _summarize(P, rmat, exmat, entries)
    ISP, OOSP = usbt2.periods(P)
    start = usbt2.sim_start(P, ISP)
    strat = usbt2.sim_targets(P, tg, cost=usbt2.BASE_COST, start=start)
    ewres = usbt2.sim_targets(P, ew, cost=usbt2.BASE_COST, start=start)
    spy = P.spyC.loc[start:]
    spyres = pd.DataFrame({"eq": spy / spy.iloc[0], "gross": 1.0}, index=spy.index)
    spyres["ret"] = spyres["eq"].pct_change()
    base = _portfolio_metrics(strat, P, ISP, OOSP)
    sens = {}
    base_sh = base["OOS"].get("sharpe")
    for c in (0.0020, 0.0040):
        rr = usbt2.sim_targets(P, tg, cost=c, start=start)
        sh = _portfolio_metrics(rr, P, ISP, OOSP)["OOS"].get("sharpe")
        sens[str(int(c * 10000)) + "bp"] = {"oos_sharpe": sh, "delta_vs_10bp": sh - base_sh if sh is not None and base_sh is not None else None}
    result = {"strategy": "weekly adjusted close > inclusive SMA40; long/flat; next-session open fills",
              "universe": {"definition": "P.E: PIT S&P 500 membership spell, adjusted close available, >=260 observed sessions; vendor coverage limitation applies", "symbols": len(P.C.columns), "ever_eligible": int(P.E.any(axis=0).sum()), "is_start": ISP[0], "last_bar": str(P.C.index[-1].date()), "week_ends": int(len(widx))},
              "known_bias": "Removed/delisted members included only while PIT members when Yahoo still serves data; missing vendor history remains a known coverage bias.",
              "per_symbol_summary": aggregate, "per_symbol": rows,
              "portfolio": {"strategy": base, "SPY_buy_hold": _portfolio_metrics(spyres, P, ISP, OOSP),
                            "EW_eligible_weekly_rebalanced_static_universe": _portfolio_metrics(ewres, P, ISP, OOSP)},
              "sensitivity": sens}
    OUT.mkdir(parents=True, exist_ok=True); HERE.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=1, default=str)
    (OUT / "results_ma40.json").write_text(payload)
    (HERE / "results_ma40.json").write_text(payload)
    strat["eq"].rename("nav").to_csv(HERE / "nav_ma40.csv", index_label="date")
    print(json.dumps({"portfolio": result["portfolio"], "sensitivity": sens}, indent=1, default=str))


if __name__ == "__main__":
    main()
