"""US research helpers (US session). DEV DATA ONLY in Stage 1-2. Never edits lib/."""
import os, sys
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lib import data, splits, costs, eventstudy as es, portfolio as pf, baseline as bl, report, features as F  # noqa: E402

SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
COST = costs.USCost()
COST2 = COST.with_(mult=2)


def resources_ok():
    la = os.getloadavg()[0]
    avail = [int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0] / 1048576
    if la > 4 or avail < 2:
        sys.exit(f"ABORT load={la:.2f} availGiB={avail:.1f}")


def adj_idx(name):
    d = data.load_index(name)
    f = d["adj close"] / d["close"]
    return pd.DataFrame({"open": d.open * f, "high": d.high * f, "low": d.low * f, "close": d.close * f,
                         "rawclose": d.close, "volume": d.volume})


def load_world():
    """P = 503 S&P names panel, E = ETF panel (SPY,QQQ,IWM + 11 sectors) on the same dev calendar."""
    P = data.load_panel("us")
    frames = {"SPY": adj_idx("SPY"), "QQQ": adj_idx("QQQ")}
    for s in ["IWM"] + SECTORS:
        frames[s] = data.load_ohlcv("us", s, download=False)
    E = data.build_panel(frames, P.dates, market="us")
    assert P.dates.max() < splits.HOLDOUT_START and E.dates.max() < splits.HOLDOUT_START
    return P, E


def topk_mask(v20, k):
    """Point-in-time top-k by value20 each row (bar)."""
    v = np.nan_to_num(np.asarray(v20, dtype=float), nan=-1.0)
    thr = np.partition(v, -k, axis=1)[:, -k]
    return (v >= thr[:, None]) & (v > 0)


def rolling_min(a, n):
    return -F.rolling_max(-a, n)


def fixed_events(P, mask, entry, exit, elig=None, cost=COST):
    return es.make_events(P, mask, entry, exit, cost_model=cost, eligible=elig)


def var_exit_events(P, mask, H, cond_fn, elig=None, cost=COST):
    """Entry at close of signal bar t. Exit at close of first k in 1..H with cond_fn(ti, ci, k) True, else t+H.
    Events with missing prices or running past the end are dropped."""
    T = P.close.shape[0]
    ok = np.asarray(mask, dtype=bool) & np.isfinite(P.close)
    if elig is not None:
        ok &= elig
    ok[max(T - H, 0):] = False
    ti, ci = np.nonzero(ok)
    off = np.full(len(ti), H, dtype=np.int64)
    for k in range(H - 1, 0, -1):
        off = np.where(cond_fn(ti, ci, k), k, off)
    xi = ti + off
    with np.errstate(invalid="ignore", divide="ignore"):
        gross = P.close[xi, ci] / P.close[ti, ci] - 1.0
    g = np.isfinite(gross)
    ti, ci, xi, gross = ti[g], ci[g], xi[g], gross[g]
    splits.guard_dev(P.dates[xi], "var_exit_events") if len(ti) else None
    c = np.full(len(ti), float(cost.roundtrip()))
    return es.Events(ti, ci, 2 * ti + 1, 2 * xi + 1, gross, c, P.dates[ti], P.dates[xi])


def month_turn_days(dates, back=2):
    """Calendar index of the `back`-th-from-last trading day of each full month (>=15 bars in calendar)."""
    s = pd.Series(np.arange(len(dates)), index=dates)
    out = []
    for _, g in s.groupby([dates.year, dates.month]):
        if len(g) >= 15 and len(g) >= back:
            out.append(int(g.iloc[-back]))
    return np.array(out, dtype=np.int64)


def block_t(ev, block=5):
    """t clustered on 5-bar blocks of the entry bar (conservative for overlapping holds)."""
    return es.cluster_t(ev.net, (ev.e_slot // 2) // block)


def verdict(s):
    if s["n"] < 30:
        return "noise"
    if s["mean"] > 0 and s["t"] >= 3 and s["h1"] > 0 and s["h2"] > 0:
        return "advance"
    if s["mean"] < 0 and s["t"] <= -3:
        return "hurts"
    return "noise"


def full_stats(ev, P, split, N=5):
    s = es.summarize(ev, split)
    if len(ev) == 0:
        s.update(verdict="noise")
        return s
    _, s["t_block"] = block_t(ev)
    e2 = ev.with_cost(ev.cost * 2)
    s2 = es.summarize(e2, split)
    s["mean_2x"], s["t_2x"] = s2["mean"], s2["t"]
    pr = pf.simulate(ev, P.dates, N=N, capital=1.3e6, cost_model=COST)
    s.update(sharpe=pr["sharpe"], ann=pr["ann"], maxdd=pr["maxdd"], port_n=pr["n"], worst=pr["worst"],
             max_conc=pr["max_conc"], trades_month=pr["trades_month"], N=N)
    s["avg_hold"] = float(((ev.x_slot - ev.e_slot) / 2).mean())
    s["max_conc_all"] = pf.max_concurrent(ev)
    s["worst_all"] = float(ev.net.min())
    s["verdict"] = verdict(s)
    s["fragile"] = bool(s["verdict"] == "advance" and not (s["t_block"] >= 2))
    return s


def save_trades(ev, P, path, seed=0, cap=50000):
    n = len(ev)
    idx = np.arange(n)
    if n > cap:
        idx = np.sort(np.random.default_rng(seed).choice(n, cap, replace=False))
    df = pd.DataFrame({"entry": ev.dates[idx], "exit": ev.xdates[idx], "sym": np.array(P.codes, dtype=object)[ev.ci[idx]],
                       "gross": ev.gross[idx], "cost": ev.cost[idx], "net": ev.net[idx]})
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return n, len(idx)


def extras(ev, P):
    """3x cost, top-5 symbol share of P&L, next-open entry (close-entry events only)."""
    o = {}
    if len(ev) == 0:
        return o
    o["mean_3x"] = float((ev.net - 2 * ev.cost).mean())
    syms = np.array(P.codes, dtype=object)[ev.ci]
    g = pd.Series(ev.net, index=syms).groupby(level=0).sum().sort_values(ascending=False)
    tot = float(g.sum())
    o["top5_share"] = float(g.head(5).sum() / tot) if tot > 0 else float("nan")
    o["n_symbols"] = int(len(g))
    xi = (ev.x_slot - 1) // 2
    ok = (ev.e_slot % 2 == 1) & (xi >= ev.ti + 1) & (ev.ti + 1 < P.open.shape[0])
    if ok.any():
        ti, ci = ev.ti[ok], ev.ci[ok]
        gno = P.close[xi[ok], ci] / P.open[ti + 1, ci] - 1
        o["mean_nextopen"] = float(np.nanmean(gno - ev.cost[ok]))
    return o
