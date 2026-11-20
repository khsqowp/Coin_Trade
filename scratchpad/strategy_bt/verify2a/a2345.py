"""A2-A5 for the six candidates. Real plugin signals -> common.engine.simulate (via lib.run_row)."""
import json, sys
import numpy as np, pandas as pd
from lib import *

TFD = {"15m": pd.Timedelta("15min"), "1h": pd.Timedelta("1h"), "4h": pd.Timedelta("4h"), "1d": pd.Timedelta("1D")}
UNIT = NOTIONAL / CAPITAL * 100.0          # pct of capital per 1.0 return on one 1000 notional
TXN = (0.0004 + 0.0002) * UNIT             # pct cost per position transition (fee+slippage, default harness)
FUND_FALLBACK = 0.0001                     # only used if a symbol's funding csv is absent (assumption, flagged)

def pos_series(trades, n):
    pos = np.zeros(n)
    for t in trades:
        e, x = t["entry"], t["exit"]
        end = x + 1 if t["reason"] in ("time", "end_mark") else x   # time/end exits fill at that bar's close
        pos[e:min(end, n)] = 1.0 if t["side"] == "long" else -1.0
    return pos

# ---------------- A2 ----------------
def a2(sid, tf, params, res, side, rng, draws=1000):
    null = np.zeros(draws); model = 0.0; long_leg = short_leg = 0.0; bh_l = bh_s = 0.0
    for s, (trades, df, ts) in res.items():
        n = len(df); o = df.open.to_numpy(float); c = df.close.to_numpy(float)
        nxt = np.r_[o[1:], c[-1]]; r = nxt / o - 1.0
        pos = pos_series(trades, n)
        trans = np.abs(np.diff(np.r_[pos, pos[0]])).sum()       # cyclic transitions, shift-invariant
        model += UNIT * (pos * r).sum() - TXN * trans
        # all circular shifts of pos against r via FFT: corr[k] = sum_i pos[(i-k)%n] r[i]
        corr = np.fft.irfft(np.conj(np.fft.rfft(r)) * np.fft.rfft(pos), n)  # corr[k]=sum_i r[i]pos[(i+k)%n]
        ks = rng.integers(0, n, draws)
        null += UNIT * corr[ks] - TXN * trans
        bh = UNIT * (c[-1] / o[0] - 1.0)
        fl = float((pos > 0).mean()); fs = float((pos < 0).mean())
        bh_l += bh * fl; bh_s += -bh * fs
        long_leg += sum(t["pct"] for t in trades if t["side"] == "long")
        short_leg += sum(t["pct"] for t in trades if t["side"] == "short")
    p95 = float(np.percentile(null, 95)); pct = float(100 * np.mean(null <= model))
    f_null = model < p95
    f_leg = long_leg < bh_l
    return dict(harness_return=total_pct(res), model_return=model, null_p50=float(np.median(null)), null_p95=p95, null_percentile=pct,
                long_leg=long_leg, long_bh_scaled=bh_l, short_leg=short_leg, short_bh_scaled=bh_s,
                fail_null=bool(f_null), fail_longleg=bool(f_leg), A2="FAIL" if (f_null or f_leg) else "PASS")

# ---------------- A3 ----------------
def a3(sid, tf, params, frames, plugin_path):
    sc = {"base": dict(), "delay1": dict(delay=1), "slip0.05": dict(slippage=0.0005), "slip0.10": dict(slippage=0.0010),
          "fee0.06": dict(fee=0.0006)}
    out = {}
    for k, kw in sc.items():
        r, _ = run_row(sid, tf, params, frames=frames, plugin_path=plugin_path, **kw)
        out[k] = total_pct(r)
    fail = out["delay1"] <= 0 or out["slip0.05"] <= 0
    return dict(**{f"ret_{k}": v for k, v in out.items()}, A3="FAIL" if fail else "PASS")

# ---------------- A4 ----------------
def load_funding():
    f = {}
    for s in SYMS:
        p = HERE / "funding" / f"{s}.csv"
        if p.exists():
            d = pd.read_csv(p, parse_dates=["time"]); f[s] = (d.time.to_numpy("datetime64[ns]"), d.fundingRate.to_numpy(float))
    return f

def trade_funding_pct(t, ts, tf, fund):
    """pct-of-capital funding paid (positive = cost) for one trade; funding stamps within [entry open, exit time)."""
    a = np.datetime64(ts[t["entry"]].tz_convert("UTC").tz_localize(None), "ns")
    x = t["exit"]; xt = ts[x] + (TFD[tf] if t["reason"] in ("time", "end_mark") else pd.Timedelta(0))
    b = np.datetime64(xt.tz_convert("UTC").tz_localize(None), "ns")
    times, rates = fund
    i, j = np.searchsorted(times, a, "left"), np.searchsorted(times, b, "left")
    sgn = 1.0 if t["side"] == "long" else -1.0
    return sgn * rates[i:j].sum() * UNIT, int(j - i)

def a4(sid, tf, params, res, fund):
    cost = 0.0; nstamps = 0; assumed = []; longc = shortc = 0.0
    for s, (trades, df, ts) in res.items():
        for t in trades:
            if s in fund:
                c, k = trade_funding_pct(t, ts, tf, fund[s])
            else:
                hold = (ts[t["exit"]] - ts[t["entry"]]) / pd.Timedelta("8h")
                c = (1.0 if t["side"] == "long" else -1.0) * FUND_FALLBACK * hold * UNIT; k = 0
                assumed.append(s)
            cost += c; nstamps += k
            if t["side"] == "long": longc += c
            else: shortc += c
    gross = total_pct(res); net = gross - cost
    return dict(gross_return=gross, funding_cost_pct=cost, funding_long=longc, funding_short=shortc, net_return=net,
                funding_stamps=nstamps, assumed_constant_syms=",".join(sorted(set(assumed))), A4="FAIL" if net <= 0 else "PASS")

# ---------------- A5 ----------------
def a5(sid, tf, params, res):
    ev = []
    for s, (trades, df, ts) in res.items():
        o = df.open.to_numpy(float)
        for t in trades:
            sgn = 1 if t["side"] == "long" else -1
            ev.append(dict(sym=s, t=t, et=ts[t["entry"]], xt=ts[t["exit"]], fill=o[t["entry"]] * (1 + sgn * 0.0002)))
    ev.sort(key=lambda e: e["et"])
    cash = CAPITAL; active = []; kept = []; skipped = 0
    for e in ev:
        for a in [a for a in active if a["xt"] <= e["et"]]:
            cash += a["t"]["net"] * a["scale"]; active.remove(a)
        free = cash - sum(a["notional"] for a in active)
        notional = min(NOTIONAL, free)
        if notional <= 1e-9: skipped += 1; continue
        e["notional"] = notional; e["scale"] = notional / NOTIONAL; active.append(e); kept.append(e)
    grid = pd.DatetimeIndex(sorted(set().union(*[set(ts) for _, _, ts in res.values()])))
    delta = {s: np.zeros(len(res[s][1])) for s in res}
    for e in kept:
        s = e["sym"]; df = res[s][1]; t = e["t"]; c = df.close.to_numpy(float); sgn = 1 if t["side"] == "long" else -1
        a, x = t["entry"], t["exit"]; sc = e["scale"]; qty = e["notional"] / e["fill"]
        if x > a:
            delta[s][a:x] += sgn * qty * (c[a:x] - e["fill"]) - e["fill"] * qty * 0.0004
        delta[s][x:] += t["net"] * sc
        if x == a: delta[s][a:] += 0   # same-bar round trip: realized only
    eq = np.full(len(grid), CAPITAL)
    for s in res:
        ser = pd.Series(delta[s], index=res[s][2]); eq = eq + ser.reindex(grid, method="ffill").fillna(0.0).to_numpy()
    eqs = pd.Series(eq, index=grid)
    peak = eqs.cummax(); dd = float(((eqs - peak) / peak).min() * 100)
    ret = (eqs.iloc[-1] / CAPITAL - 1) * 100
    days = max((grid[-1] - grid[0]).days, 1); cagr = ((eqs.iloc[-1] / CAPITAL) ** (365.0 / days) - 1) * 100
    d = eqs.resample("1D").last().dropna().pct_change().dropna()
    sharpe = float(d.mean() / d.std(ddof=1) * np.sqrt(365)) if d.std() > 0 else float("nan")
    inpos = np.zeros(len(grid)); gross = np.zeros(len(grid))
    for e in kept:
        m = (grid >= e["et"]) & (grid < e["xt"] + (TFD[tf] if e["t"]["reason"] in ("time", "end_mark") else pd.Timedelta(0)))
        inpos += m; gross += m * e["notional"]
    exposure = float((inpos > 0).mean() * 100); avg_gross = float(gross.mean() / CAPITAL * 100)
    ratio = abs(dd) / ret if ret > 0 else float("inf")
    return dict(port_return=float(ret), port_cagr=float(cagr), port_maxdd=dd, port_sharpe=sharpe, exposure_pct=exposure,
                avg_gross_pct_capital=avg_gross, trades_kept=len(kept), trades_skipped_capital=skipped,
                maxdd_over_return=float(ratio), A5="FAIL" if (ret <= 0 or ratio > 1.0) else "PASS")

def main():
    rows = load_summary(); fund = load_funding(); rng = np.random.default_rng(20261120)
    out = {k: [] for k in ("A2", "A3", "A4", "A5")}
    for sid in CANDS:
        tf, params, r = candidate_row(sid, rows); pp = find_plugin(sid); frames = test_frames(tf)
        res, side = run_row(sid, tf, params, frames=frames, plugin_path=pp)
        assert abs(total_pct(res) - float(r["test_return"])) < 1e-6
        base = dict(strategy_id=sid, timeframe=tf, params=json.dumps(params), side=side)
        out["A2"].append({**base, **a2(sid, tf, params, res, side, rng)})
        out["A3"].append({**base, **a3(sid, tf, params, frames, pp)})
        out["A4"].append({**base, **a4(sid, tf, params, res, fund)})
        out["A5"].append({**base, **a5(sid, tf, params, res)})
    for k, v in out.items():
        pd.DataFrame(v).to_csv(HERE / f"{k.lower()}_results.csv", index=False); print(k); print(pd.DataFrame(v).drop(columns=["params"]).T.to_string())

if __name__ == "__main__":
    main()
