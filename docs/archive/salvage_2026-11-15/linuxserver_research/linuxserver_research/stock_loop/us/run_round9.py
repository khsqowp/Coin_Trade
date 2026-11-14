"""Round 9: ETF / VIX / cross-asset hypotheses US-42..US-52. DEV ONLY. python -m us.run_round9"""
import time, resource, sys, json
from .common import *  # noqa
from .hyp import lag
from .run_round import prev_ps

ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
        "EFA", "EEM", "EWJ", "EWZ", "FXI", "TLT", "IEF", "HYG", "LQD", "GLD", "SLV", "USO", "DBC", "VNQ", "XBI", "SMH"]
EQ3 = ["SPY", "QQQ", "IWM"]


def load_etf():
    cal = data.load_index("SPY").index
    fr = {"SPY": adj_idx("SPY"), "QQQ": adj_idx("QQQ")}
    for s in ETFS:
        if s not in fr:
            fr[s] = data.load_ohlcv("us", s, download=False)
    E = data.build_panel(fr, cal, market="us")
    assert E.dates.max() < splits.HOLDOUT_START
    v = pd.read_parquet(ROOT / "results" / "us42_raw" / "VIX.parquet")
    ix = pd.DatetimeIndex(pd.to_datetime(v.index))
    v.index = (ix.tz_localize(None) if ix.tz is not None else ix).normalize()
    v = v[~v.index.duplicated()].sort_index()
    v = v[v.index < splits.HOLDOUT_START]
    vix = v["Close"].reindex(cal).to_numpy(dtype=float)
    return E, vix


class Ctx:
    def __init__(self, E, vix):
        self.E, self.vix, self._c = E, vix, {}

    def f(self, k, fn):
        if k not in self._c:
            self._c[k] = fn()
        return self._c[k]

    def sma(self, n):
        return self.f(("sma", n), lambda: F.sma(self.E.close, n))


def cols(E, syms):
    return [E.codes.index(s) for s in syms]


def vix_mask(E, sig, syms=EQ3):
    m = np.zeros(E.close.shape, bool)
    m[:, cols(E, syms)] = np.nan_to_num(sig, nan=0).astype(bool)[:, None]
    return m


def vstat(vix):
    s = pd.Series(vix)
    return dict(m20p=s.shift(1).rolling(20, min_periods=15).mean().to_numpy(), sma10=s.rolling(10, min_periods=8).mean().to_numpy(),
                sma20=s.rolling(20, min_periods=15).mean().to_numpy(), sd20=s.rolling(20, min_periods=15).std().to_numpy())


def build(C, hid):
    E, vix = C.E, C.vix
    c = E.close
    up = c > C.sma(200)
    ok = np.isfinite(c)
    vs = vstat(vix)
    if hid == "US-42":
        rsi = C.f("rsi2", lambda: F.rsi(c, 2)); s5 = C.sma(5)
        return var_exit_events(E, (rsi < 5) & up, 5, lambda ti, ci, k: c[ti + k, ci] > s5[ti + k, ci])
    if hid == "US-43":
        return fixed_events(E, ((c / lag(c, 3) - 1) <= -0.03) & up, ("close", 0), ("close", 5))
    if hid == "US-44":
        return fixed_events(E, (F.down_streak(c) >= 4) & up, ("close", 0), ("close", 3))
    if hid == "US-45":
        ibs = C.f("ibs", lambda: F.ibs(E.high, E.low, c))
        return var_exit_events(E, (ibs < 0.10) & up, 5, lambda ti, ci, k: ibs[ti + k, ci] > 0.70)
    if hid == "US-46":
        return fixed_events(E, (c > C.sma(50)) & (C.sma(50) > C.sma(200)) & (c <= 0.98 * C.sma(10)), ("close", 0), ("close", 5))
    if hid == "US-47":
        sig = vix / vs["m20p"] >= 1.25
        return var_exit_events(E, vix_mask(E, sig), 10, lambda ti, ci, k: vix[ti + k] < vs["sma10"][ti + k])
    if hid == "US-48":
        return fixed_events(E, vix_mask(E, vix > vs["sma20"] + 2 * vs["sd20"]), ("close", 0), ("close", 5))
    if hid == "US-49":
        j = np.full(len(vix), np.nan); j[1:] = vix[1:] / vix[:-1] - 1
        return fixed_events(E, vix_mask(E, j >= 0.15), ("close", 0), ("close", 3))
    if hid == "US-50":
        k = E.codes.index("SPY")
        r = np.full(len(vix), np.nan); r[1:] = c[1:, k] / c[:-1, k] - 1
        rv = pd.Series(r).rolling(10, min_periods=10).std().to_numpy() * np.sqrt(252) * 100
        return fixed_events(E, vix_mask(E, vix / rv >= 1.8), ("close", 0), ("close", 5))
    if hid == "US-51":
        s, t = E.codes.index("SPY"), E.codes.index("TLT")
        r5s = c[:, s] / lag(c[:, [s]], 5)[:, 0] - 1
        r5t = c[:, t] / lag(c[:, [t]], 5)[:, 0] - 1
        sig = ((r5s - r5t) <= -0.04) & up[:, s]
        return fixed_events(E, vix_mask(E, sig, ["SPY"]), ("close", 0), ("close", 5))
    if hid == "US-52":
        prev = np.full(len(vix), np.nan); prev[1:] = vix[:-1]
        return fixed_events(E, vix_mask(E, (vix >= 30) & (vix < prev)), ("close", 0), ("close", 10))
    raise KeyError(hid)


IDEAS = {"US-42": "ETF RSI2<5 & >SMA200, exit >SMA5/5d", "US-43": "ETF 3d drop<=-3% & >SMA200, hold 5", "US-44": "ETF 4 down closes & >SMA200, hold 3",
         "US-45": "ETF IBS<0.10 & >SMA200, exit IBS>0.7/5d", "US-46": "ETF pullback >=2% below SMA10 in trend (SMA50>SMA200), hold 5",
         "US-47": "VIX/20d mean>=1.25 -> buy SPY,QQQ,IWM, exit VIX<SMA10 or 10d", "US-48": "VIX > upper Bollinger(20,2) -> SPY,QQQ,IWM hold 5",
         "US-49": "VIX 1d jump>=15% -> SPY,QQQ,IWM hold 3", "US-50": "VIX/realised vol>=1.8 -> SPY,QQQ,IWM hold 5",
         "US-51": "SPY-TLT 5d <=-4% & SPY>SMA200 -> SPY hold 5", "US-52": "VIX>=30 and falling -> SPY,QQQ,IWM hold 10"}


def analyse(ev, E, N):
    wk = (ev.dates.isocalendar().year.to_numpy().astype(int) * 100 + ev.dates.isocalendar().week.to_numpy().astype(int))
    sp = ev.dates.min() + (ev.dates.max() - ev.dates.min()) / 2
    s = es.summarize(ev, sp)
    _, s["t_week"] = es.cluster_t(ev.net, wk)
    s["p_week"] = es.t_to_p(s["t_week"])
    s["n_weeks"] = int(len(np.unique(wk)))
    s["n_eff"] = s["n_weeks"]
    s["mean_2x"] = float((ev.net - ev.cost).mean())
    s["mean_3x"] = float((ev.net - 2 * ev.cost).mean())
    _, s["t_2x_week"] = es.cluster_t(ev.net - ev.cost, wk)
    pr = pf.simulate(ev, E.dates, N=N, capital=1.3e6, cost_model=COST)
    s.update(sharpe=pr["sharpe"], maxdd=pr["maxdd"], worst=pr["worst"], port_n=pr["n"])
    y = pd.Series(ev.net).groupby(ev.dates.year).agg(["mean", "count"])
    s["year_means"] = {int(k): dict(mean=float(r["mean"]), n=int(r["count"])) for k, r in y.iterrows()}
    s["by_inst"] = {}
    syms = np.array(E.codes, dtype=object)[ev.ci]
    for sym in sorted(set(syms)):
        m = syms == sym
        if m.sum() >= 10:
            s["by_inst"][sym] = dict(n=int(m.sum()), mean=float(ev.net[m].mean()), gross=float(ev.gross[m].mean()))
    s["verdict"] = "advance" if (s["n"] >= 30 and s["mean"] > 0 and s["t_week"] >= 3 and s.get("h1", -1) > 0 and s.get("h2", -1) > 0) else (
        "hurts" if s["n"] >= 30 and s["mean"] < 0 and s["t_week"] <= -3 else "noise")
    return s


def main():
    out = ROOT / "results" / "US_round9.json"
    if out.exists() and "--force" not in sys.argv:
        sys.exit("exists")
    resources_ok()
    t0 = time.time()
    E, vix = load_etf()
    print("ETF panel", E.close.shape, "VIX valid", int(np.isfinite(vix).sum()), flush=True)
    C = Ctx(E, vix)
    res = {}
    for hid, idea in IDEAS.items():
        ev = build(C, hid)
        N = 3 if hid in ("US-47", "US-48", "US-49", "US-50", "US-52") else (1 if hid == "US-51" else 5)
        if len(ev) < 5:
            res[hid] = dict(n=len(ev), verdict="noise", mean=float("nan"), t_week=float("nan"), p_week=1.0, idea=idea); print(hid, "too few", len(ev)); continue
        s = analyse(ev, E, N)
        s["idea"] = idea
        res[hid] = s
        print(hid, "n", s["n"], "weeks", s["n_weeks"], "net %.3f%% tw %.2f t %.2f gross %.3f%% h %.3f/%.3f 2x %.3f%% 3x %.3f%% Sh %.2f yrs+ %.2f %s" % (
            100 * s["mean"], s["t_week"], s["t"], 100 * s["gross"], 100 * s["h1"], 100 * s["h2"], 100 * s["mean_2x"], 100 * s["mean_3x"], s["sharpe"], s["years_pos"], s["verdict"]), flush=True)
        save_trades(ev, E, ROOT / "results" / hid / f"trades_{hid}.parquet")
    prev = prev_ps()
    ids = list(prev) + list(res)
    qs = dict(zip(ids, es.bh_qvalues([prev[i] if i in prev else res[i]["p_week"] for i in ids])))
    for i in res:
        res[i]["q_cum"] = qs[i]; res[i]["p"] = res[i]["p_week"]
        report.dump_json({i: res[i]}, ROOT / "results" / i / "summary.json")
    report.dump_json(dict(n_trials_round=len(res), n_trials_cum=len(ids), res=res), out)
    for i, s in res.items():
        if s["n"] < 5:
            continue
        txt = (f"{s['idea']} [n={s['n']}, weeks={s['n_weeks']}, gross {100*s['gross']:.3f}%, BE cost {100*s['break_even']:.3f}%, 2x {100*s['mean_2x']:.3f}%, 3x {100*s['mean_3x']:.3f}%, "
               f"halves {100*s['h1']:.3f}/{100*s['h2']:.3f}%, yrs+ {s['years_pos']:.2f}, date-t {s['t']:.2f}, BH q(cum {len(ids)}) {s['q_cum']:.3f}]")
        report.append_ledger(report.ledger_row(i, "US", txt, "S1", s["mean"], s["t_week"], s["sharpe"], "locked", s["verdict"], "stage2" if s["verdict"] == "advance" else "drop"))
    print("survivors", [i for i in res if res[i]["verdict"] == "advance"], "cum trials", len(ids))
    print("done %.0fs peakMB %d" % (time.time() - t0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024))


if __name__ == "__main__":
    main()
