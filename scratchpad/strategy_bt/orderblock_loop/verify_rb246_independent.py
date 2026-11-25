#!/usr/bin/env python3
"""RB-246 (F4: BTC regime alt relative-strength long rotation) - independent re-implementation.

Written from PREREG_RB500_COIN.md only (section 3 F4, section 4-6 execution/cost/gate rules).
TRAIN ONLY: every bar used has open_time + 4h <= 2023-11-06 16:00Z (enforced by a pyarrow
filter on read). Read-only with respect to the ledger. Results are written to the session
scratchpad, never to the ledger.
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.stats import norm

BASE = "/Users/user/CODE/Coin_Trade/trading_data"
BARS_DIR = f"{BASE}/cache/orderblock/bars/4h"
FUND_DIR = f"{BASE}/external/crypto/binance/um_fundingRate"
UNIV_CSV = "/Users/user/CODE/Coin_Trade/scratchpad/strategy_bt/orderblock_loop/universe/CRYPTO_35.csv"
OUT = "/private/tmp/claude-501/-Users-user-CODE-Ochestration/ee6baff2-9664-4b9e-9a9e-5f263219aa7c/scratchpad/rb246_out"

TF = 4 * 3600 * 1000
DAY = 24 * 3600 * 1000
CUTOFF = int(datetime(2023, 11, 6, 16, tzinfo=timezone.utc).timestamp() * 1000)
WARM = 500          # bars (grid index) per symbol before any signal
NU = 35             # daily normalisation denominator (PREREG section 5)
COST_RT = 0.0012    # round trip 12 bp (6 bp per side)
BTC = "BTCUSDT"
N_TRIALS = 2189     # PREREG: R(1689) + 500; confirmed against ledger row count in verify step
HORIZON = 24
STOP_ATR = 2.0
REWARD = 2.0

# F4 grid in PREREG order: top_k x rs_lookback x regime_sma (product, listed order)
F4_TOPK = [1, 2, 3, 5, 10]
F4_RS = [42, 84, 180, 360]
F4_REG = [50, 100, 200]


def f4_grid():
    cfgs = []
    for i, (k, rs, reg) in enumerate(
        (k, rs, reg) for k in F4_TOPK for rs in F4_RS for reg in F4_REG
    ):
        cfgs.append({"idx": i, "label": f"RB-{221 + i}", "top_k": k, "rs": rs, "reg": reg})
    assert len(cfgs) == 60
    return cfgs


# ---------------------------------------------------------------- data
def load_universe():
    return pd.read_csv(UNIV_CSV)["symbol"].tolist()


def load_panel(syms, cutoff=CUTOFF):
    """Aligned 4h panel on a common grid. Only complete bars with open+4h <= cutoff."""
    frames = {}
    for s in syms:
        t = pq.read_table(
            f"{BARS_DIR}/{s}.parquet",
            columns=["open_time", "open", "high", "low", "close", "complete"],
            filters=[("open_time", "<=", cutoff - TF)],
        ).to_pandas()
        t = t[t["complete"].astype(bool)].drop_duplicates("open_time").sort_values("open_time")
        frames[s] = t
    t0 = min(int(f.open_time.iloc[0]) for f in frames.values() if len(f))
    grid = np.arange(t0, cutoff - TF + 1, TF, dtype=np.int64)
    T, S = len(grid), len(syms)
    O = np.full((T, S), np.nan)
    H = np.full((T, S), np.nan)
    L = np.full((T, S), np.nan)
    C = np.full((T, S), np.nan)
    misaligned = 0
    for j, s in enumerate(syms):
        f = frames[s]
        ot = f.open_time.to_numpy(np.int64)
        ok = (ot - t0) % TF == 0
        misaligned += int((~ok).sum())
        idx = (ot[ok] - t0) // TF
        O[idx, j] = f.open.to_numpy()[ok]
        H[idx, j] = f.high.to_numpy()[ok]
        L[idx, j] = f.low.to_numpy()[ok]
        C[idx, j] = f.close.to_numpy()[ok]
    first = np.array([int(np.argmax(np.isfinite(C[:, j]))) if np.isfinite(C[:, j]).any() else T
                      for j in range(S)])
    atr = atr14(H, L, C)
    return {
        "grid": grid, "syms": syms, "O": O, "H": H, "L": L, "C": C,
        "ATR": atr, "first": first, "btc": syms.index(BTC), "t0": t0,
        "misaligned": misaligned, "T": T,
    }


def load_funding(sym, cutoff=CUTOFF):
    d = f"{FUND_DIR}/{sym}"
    if not os.path.isdir(d):
        return None
    parts = []
    for f in sorted(os.listdir(d)):
        if not f.endswith(".parquet") or f[:7] > "2023-11":
            continue
        parts.append(
            pq.read_table(f"{d}/{f}", columns=["calc_time", "last_funding_rate"],
                          filters=[("calc_time", "<", cutoff)]).to_pandas()
        )
    if not parts:
        return None
    df = pd.concat(parts).drop_duplicates("calc_time").sort_values("calc_time")
    return df["calc_time"].to_numpy(np.int64), df["last_funding_rate"].to_numpy(float)


# ---------------------------------------------------------------- indicators (causal)
def atr14(H, L, C):
    prev = np.full_like(C, np.nan)
    prev[1:] = C[:-1]
    tr = np.maximum(H - L, np.maximum(np.abs(H - prev), np.abs(L - prev)))  # NaN propagates
    return pd.DataFrame(tr).rolling(14, min_periods=14).mean().to_numpy()


def rs_score(C, btc, L):
    R = np.full_like(C, np.nan)
    R[L:] = C[L:] / C[:-L] - 1
    Cb = C[:, btc]
    Rb = np.full(len(Cb), np.nan)
    Rb[L:] = Cb[L:] / Cb[:-L] - 1
    return R - Rb[:, None]


def regime_on(C, btc, n):
    Cb = C[:, btc]
    sma = pd.Series(Cb).rolling(n, min_periods=n).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        return Cb > sma  # NaN -> False


def base_mask(P):
    T, S = P["C"].shape
    warm = np.arange(T)[:, None] >= (P["first"][None, :] + WARM)
    m = np.isfinite(P["C"]) & np.isfinite(P["ATR"]) & warm
    m[:, P["btc"]] = False  # BTC is the regime asset, never traded in F4
    return m


# ---------------------------------------------------------------- execution
def funding_pay(fund, t_in, t_out):
    """Adverse-only policy: boundary events (== entry or exit time) charged max(rate,0) for a long;
    interior events signed. Returns (payment as fraction of notional, n_events)."""
    if fund is None:
        return 0.0, 0
    ts, rates = fund
    lo = np.searchsorted(ts, t_in, side="left")
    hi = np.searchsorted(ts, t_out, side="right")
    pay = 0.0
    for x, r in zip(ts[lo:hi], rates[lo:hi]):
        pay += max(r, 0.0) if (x == t_in or x == t_out) else r
    return float(pay), int(hi - lo)


def sim_trade(P, j, t, e, cost_rt, fund_j, horizon=HORIZON, stop_atr=STOP_ATR, reward=REWARD):
    O, H, Lo = P["O"][:, j], P["H"][:, j], P["L"][:, j]
    T = P["T"]
    entry = O[e]
    d = stop_atr * P["ATR"][t, j]
    stop, tgt = entry - d, entry + reward * d
    k, reason, px = None, None, None
    for jj in range(e, e + horizon):
        if jj >= T or not (np.isfinite(O[jj]) and np.isfinite(H[jj]) and np.isfinite(Lo[jj])):
            return None  # censored: missing / out-of-range bar on the path
        if O[jj] <= stop:
            k, reason, px = jj, "stop", O[jj]
        elif Lo[jj] <= stop:
            k, reason, px = jj, "stop", stop
        elif O[jj] >= tgt:
            k, reason, px = jj, "target", O[jj]
        elif H[jj] >= tgt:
            k, reason, px = jj, "target", tgt
        if k is not None:
            break
    if k is None:
        k = e + horizon
        if k >= T or not np.isfinite(O[k]):
            return None
        px, reason = O[k], "time"
    gross = px / entry - 1.0
    tin, tout = int(P["grid"][e]), int(P["grid"][k])
    fp, nev = funding_pay(fund_j, tin, tout)
    return {"j": j, "t": t, "e": e, "k": k, "tin": tin, "tout": tout, "reason": reason,
            "gross": gross, "fund": fp, "nfund": nev, "net": gross - cost_rt - fp,
            "atr": float(P["ATR"][t, j])}


def run(P, cfg, funds, score=None, delay=1, cost_rt=COST_RT, mode="literal", univ=None,
        rng=None, base=None, horizon=HORIZON):
    """mode 'literal': top-K by score among all candidates, then drop picks held (PREREG 5 'no overlap').
    mode 'replace': top-K among candidates not currently held (alternative reading, sensitivity only)."""
    T = P["T"]
    if score is None:
        score = rs_score(P["C"], P["btc"], cfg["rs"])
    reg = regime_on(P["C"], P["btc"], cfg["reg"])
    if base is None:
        base = base_mask(P)
    cand = base & np.isfinite(score)
    if univ is not None:
        cand = cand & univ[None, :]
    entry_ok = np.zeros_like(cand)
    entry_ok[: T - delay] = np.isfinite(P["O"][delay:])
    cand = cand & entry_ok
    last_exit = np.full(P["C"].shape[1], -1, dtype=np.int64)
    trades, censored, held_skip = [], 0, 0
    K = cfg["top_k"]
    for t in range(T - delay):
        if not reg[t]:
            continue
        js = np.nonzero(cand[t])[0]
        if js.size == 0:
            continue
        if rng is not None:
            order = rng.permutation(js)
        else:
            order = js[np.argsort(-score[t, js], kind="stable")]
        if mode == "replace":
            order = [j for j in order if t >= last_exit[j]]
        for j in order[:K]:
            if t < last_exit[j]:
                held_skip += 1
                continue
            tr = sim_trade(P, j, t, t + delay, cost_rt, funds[j], horizon=horizon)
            if tr is None:
                censored += 1
                continue
            last_exit[j] = tr["k"]
            trades.append(tr)
    return trades, {"censored": censored, "held_skips": held_skip}


# ---------------------------------------------------------------- metrics
def wilson_lower(k, n, z=1.959964):
    if n == 0:
        return float("nan")
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    rad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - rad) / den


def metrics(trades, t0, D, n_trials=N_TRIALS):
    n = len(trades)
    if n == 0:
        return {"n": 0}
    net = np.array([x["net"] for x in trades])
    reason = np.array([x["reason"] for x in trades])
    days = np.array([(x["tout"] - t0) // DAY for x in trades], dtype=np.int64)
    daily = np.zeros(D)
    np.add.at(daily, days, net)
    daily = daily / NU
    cum = float(daily.sum())
    curve = np.cumsum(daily)
    pk = np.maximum.accumulate(np.maximum(curve, 0.0))
    mdd = float(np.max(pk - curve))
    mu, sd = daily.mean(), daily.std(ddof=1)
    sharpe = float(mu / sd * math.sqrt(365)) if sd > 0 else float("nan")
    w, l = net[net > 0], -net[net <= 0]
    pf = float(w.sum() / l.sum()) if l.sum() > 0 else float("inf")
    avg_w = float(w.mean()) if len(w) else 0.0
    avg_l = float(l.mean()) if len(l) else 0.0
    be = avg_l / (avg_w + avg_l) if (avg_w + avg_l) > 0 else float("nan")
    wins = int(len(w))
    wl = wilson_lower(wins, n)
    exp_bp = float(net.mean() * 1e4)
    t_stat = float(net.mean() / (net.std(ddof=1) / math.sqrt(n)))
    p1 = float(norm.sf(t_stat))
    m2k = int((reason == "target").sum())
    gates = {
        "n>=100": n >= 100,
        "cum>0": cum > 0,
        "PF>=1.30": pf >= 1.30,
        "exp>=15bp": exp_bp >= 15,
        "wilson_lo>breakeven": wl > be,
        "MDD<cum/2": mdd < cum / 2,
        "Sharpe>=1.0": sharpe >= 1.0,
        "solvency(1x unlevered, assumed)": True,
    }
    return {
        "n": n, "wins": wins, "win_rate": wins / n, "wilson_lo": wl, "breakeven_p": be,
        "PF": pf, "exp_bp": exp_bp, "cum": cum, "mdd": mdd, "sharpe": sharpe,
        "ann_ret": float(mu * 365), "t": t_stat, "p_one": p1,
        "bonf_pass": bool(p1 < 0.05 / n_trials),
        "M2": m2k / n, "M2_lo": wilson_lower(m2k, n),
        "reasons": {r: int((reason == r).sum()) for r in ["stop", "target", "time"]},
        "core_pass": all(gates.values()), "gates": {k: bool(v) for k, v in gates.items()},
        "censored_note": None,
    }


def yearly(trades, key="tout", t0=None):
    out = {}
    for x in trades:
        y = datetime.fromtimestamp(x[key] / 1000, tz=timezone.utc).year
        out.setdefault(y, {"n": 0, "sum_pct": 0.0, "wins": 0})
        out[y]["n"] += 1
        out[y]["sum_pct"] += x["net"] * 100
        out[y]["wins"] += int(x["net"] > 0)
    return out


def day_count(P):
    D = (CUTOFF - P["t0"]) // DAY + 1
    return int(D)
