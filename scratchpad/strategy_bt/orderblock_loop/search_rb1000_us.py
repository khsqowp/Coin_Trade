"""RB1000-US TRAIN-only runner: 200 preregistered US configurations (lane US).

Implements PREREG_RB1000_US.md. Only rows dated <= 2018-10-26 are read. Reuses the
RB500-US loaders, OHLC adjustment, quality filter, indicator set, and exit engine
from search_rb500_us, and adds trade-level records for the supplementary checks
(1-bar delay, 2x cost, entry-date clustering, calendar-year, top-3 exclusion).
"""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import json
import math
import multiprocessing as mp
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

import rb1000_us_grid as grid
import search_rb500_us as base
from metrics import wilson_lower

ROOT = Path(__file__).resolve().parent
DATA_DIR = base.DATA_DIR
ETF_PARQUET = DATA_DIR / "external/equities/us/yahoo_daily_us_etf.parquet"
FRED_PARQUET = DATA_DIR / "external/equities/macro/fred_series.parquet"
RUNS = base.RUNS
LEDGER = base.LEDGER
CUTOFF = base.CUTOFF
COST_RT = base.COST_RT
ROUND = "RB1000-US"
TRIAL_FIELDS = base.TRIAL_FIELDS
ALPHA = 0.05
MIN_N = 60
MIN_PF = 1.30
MIN_EXP_BP = 30.0
YEAR_MIN_TRADES = 5
YEAR_MIN_COUNT = 3
YEAR_POS_SHARE = 0.60
CLUSTER_ALPHA = 0.05
BIG_HOLD = 10**6
LEDGER_ADD = 429 + 1000
SPY = "SPY"
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
FACTOR_SETS = {"mom_52w": ("mom", "ratio52"), "mom_lowvol": ("mom", "lowvol"),
               "mom_52w_lowvol": ("mom", "ratio52", "lowvol")}
CONFIGS = grid.build_grid()
CTX: dict = {}

L01, L02, L03, L04, L05 = (f for f, _ in grid.FAMILIES[:5])
L06, L07, L08, L09, L10, L11, L12 = (f for f, _ in grid.FAMILIES[5:])
XS_FAMILIES = {L03, L04, L05}
STOCK_FAMILIES = XS_FAMILIES | {L09, L10, L11}
ETF_FAMILIES = {L01, L02, L06, L07, L08, L12}
assert STOCK_FAMILIES | ETF_FAMILIES == {f for f, _ in grid.FAMILIES}


# ---------------------------------------------------------------- helpers
def _roll(M: np.ndarray, w: int, how: str = "mean") -> np.ndarray:
    """Rolling statistic along time (axis 1) with full-window requirement."""
    r = pd.DataFrame(M.T).rolling(w, min_periods=w)
    return getattr(r, how)().to_numpy().T


def _shift1(a: np.ndarray) -> np.ndarray:
    return np.r_[False, a[:-1]]


def _delay(sig: np.ndarray, rule):
    return _shift1(sig), (None if rule is None else _shift1(rule))


# ---------------------------------------------------------------- data
def load_etf_frames(symbols: list[str]) -> tuple[dict, dict]:
    df = pd.read_parquet(
        ETF_PARQUET, columns=["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"],
        filters=[("date", "<=", CUTOFF), ("ticker", "in", sorted(symbols))])
    if not df.empty and df["date"].max() > CUTOFF:
        raise RuntimeError("post-cutoff row returned by ETF loader")
    frames, failures = {}, {}
    for sym, g in df.groupby("ticker", sort=True):
        try:
            frames[sym] = base._clean_symbol(sym, g)
        except (base.SymbolQualityError, ValueError) as exc:
            failures[sym] = f"{type(exc).__name__}: {exc}"
    return frames, failures


def load_fred() -> dict[str, pd.Series]:
    df = pd.read_parquet(FRED_PARQUET, columns=["series", "date", "value"],
                         filters=[("series", "in", ["T10Y2Y", "VIXCLS"]), ("date", "<=", CUTOFF)])
    if not df.empty and df["date"].max() > CUTOFF:
        raise RuntimeError("post-cutoff row returned by FRED loader")
    out = {}
    for name, g in df.groupby("series"):
        ser = pd.Series(g["value"].to_numpy(float), index=pd.DatetimeIndex(g["date"])).sort_index()
        out[name] = ser[~ser.index.duplicated(keep="last")].dropna()
    return out


def build_etf_world(frames: dict, fred: dict) -> dict:
    m = base.build_matrices(frames)
    dates = pd.DatetimeIndex(pd.to_datetime(m["cal"], unit="ms"))
    m["dates"] = dates
    m["t10"] = fred["T10Y2Y"].reindex(dates, method="ffill").to_numpy(float)
    m["vix"] = fred["VIXCLS"].reindex(dates).to_numpy(float)  # exact date only; missing stays NaN
    m["spy"] = m["syms"].index(SPY)
    m["sector_idx"] = [m["syms"].index(s) for s in SECTORS if s in m["syms"]]
    m["opex"] = third_fridays(dates)
    m["bear"] = bear_year_map(m)
    return m


def third_fridays(dates: pd.DatetimeIndex) -> np.ndarray:
    """Index of the option-expiry trading day for each month (3rd Friday, or prior trading day)."""
    out = []
    for p in pd.period_range(dates[0], dates[-1], freq="M"):
        first = p.start_time
        third = first + pd.Timedelta(days=(4 - first.weekday()) % 7 + 14)
        j = dates.searchsorted(third, side="right") - 1
        if j < 0 or (third - dates[j]).days > 4:
            continue
        out.append(j)
    return np.asarray(out, dtype=int)


def bear_year_map(W: dict) -> dict[int, bool]:
    """Calendar year is 'bear' when the SPY adjusted return in that year (partial years allowed) is < 0."""
    C = W["C"][W["spy"]]
    years = W["dates"].year.to_numpy()
    first, last = {}, {}
    for idx, y in enumerate(years):
        if np.isfinite(C[idx]):
            first.setdefault(int(y), C[idx])
            last[int(y)] = C[idx]
    out, prev = {}, None
    for y in sorted(last):
        base_c = prev if prev is not None else first[y]
        out[y] = bool(last[y] / base_c - 1.0 < 0)
        prev = last[y]
    return out


def build_stock_context(m: dict, W: dict) -> dict:
    """Stock-world feature matrices and cross-sectional picks (computed before forking)."""
    dates_s = pd.DatetimeIndex(pd.to_datetime(m["cal"], unit="ms"))
    C, H, V = m["C"], m["H"], m["V"]
    spy_c = W["C"][W["spy"]]
    spy_r_etf = np.full(len(spy_c), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        spy_r_etf[1:] = spy_c[1:] / spy_c[:-1] - 1.0
    spy_r = pd.Series(spy_r_etf, index=W["dates"]).reindex(dates_s).to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.full_like(C, np.nan)
        r[:, 1:] = C[:, 1:] / C[:, :-1] - 1.0
        lr = np.full_like(C, np.nan)
        lr[:, 1:] = np.log(C[:, 1:] / C[:, :-1])
        dv = C * V
        ill = np.where(dv > 0, np.abs(r) / dv, np.nan)
        feats = {
            ("beta", 126): _beta(r, np.broadcast_to(spy_r, C.shape), 126),
            ("beta", 252): _beta(r, np.broadcast_to(spy_r, C.shape), 252),
            ("amihud", 63): _roll(ill, 63),
            ("amihud", 252): _roll(ill, 252),
            ("mom",): base._shift(C, 21) / base._shift(C, 252) - 1.0,
            ("ratio52",): C / _roll(H, 252, "max"),
            ("lowvol",): -_roll(lr, 63, "std"),
        }
    ctx = {"m": m, "feats": feats, "dates": dates_s, "picks": {}}
    for cfg in CONFIGS:
        if cfg["family"] in XS_FAMILIES:
            ctx["picks"][cfg["config_id"]] = xs_picks(cfg, m, feats)
    return ctx


def _beta(r: np.ndarray, mk: np.ndarray, w: int) -> np.ndarray:
    mr, mm = _roll(r, w), _roll(mk, w)
    cov = _roll(r * mk, w) - mr * mm
    var = _roll(mk * mk, w) - mm * mm
    with np.errstate(invalid="ignore", divide="ignore"):
        return cov / var


def xs_picks(cfg: dict, m: dict, feats: dict) -> tuple[np.ndarray, np.ndarray]:
    """Rebalance-day picks (row, symbol) for the stock cross-sectional families."""
    C = m["C"]
    T = C.shape[1]
    fam, rb = cfg["family"], cfg["rebal_d"]
    if fam == L03:
        min_row, desc, n = cfg["beta_window"], False, cfg["bottom_n"]
        score = feats[("beta", cfg["beta_window"])]
    elif fam == L04:
        min_row, desc, n = cfg["window"], True, cfg["top_n"]
        score = feats[("amihud", cfg["window"])]
    else:
        min_row, desc, n, score = 252, True, cfg["top_n"], None
    I, S = [], []
    for i in np.arange(min_row, T, rb):
        ok = np.isfinite(C[:, i])
        if score is None:
            for k in FACTOR_SETS[cfg["factor_set"]]:
                ok &= np.isfinite(feats[(k,)][:, i])
            cand = np.flatnonzero(ok)
            if cand.size == 0:
                continue
            ranks = np.zeros(cand.size)
            for k in FACTOR_SETS[cfg["factor_set"]]:
                order = np.argsort(feats[(k,)][cand, i], kind="stable")
                rk = np.empty(cand.size)
                rk[order] = np.arange(cand.size)
                ranks += rk / max(cand.size - 1, 1)
            chosen = cand[np.argsort(-ranks, kind="stable")][:n]
        else:
            ok &= np.isfinite(score[:, i])
            cand = np.flatnonzero(ok)
            if cand.size == 0:
                continue
            vals = score[cand, i]
            order = cand[np.argsort(-vals if desc else vals, kind="stable")]
            chosen = order[:n]
        I.extend([i] * len(chosen))
        S.extend(chosen.tolist())
    return np.asarray(I, dtype=np.int64), np.asarray(S, dtype=np.int64)


# ------------------------------------------------------- stock-world legs
def stock_leg(cfg: dict, ind: dict, si: int):
    fam = cfg["family"]
    c, o, valid = ind["c"], ind["o"], ind["valid"]
    if fam in XS_FAMILIES:
        I, S = CTX["picks"][cfg["config_id"]]
        sig = np.zeros(len(c), bool)
        sig[I[S == si]] = True
        return sig & valid, None, 0, cfg["rebal_d"]
    with np.errstate(invalid="ignore"):
        if fam == L09:
            sig = ((ind["gap"] >= cfg["gap_pct"] / 100.0) & (ind["clv"] >= cfg["clv_min"]) & (c > o))
            return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
        if fam == L10:
            sig = (ind["clv"] <= cfg["clv_max"]) & (ind["ret"] <= cfg["ret_max_pct"] / 100.0)
            return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
        if fam == L11:
            sig = (ind["ratio52"] >= cfg["prox"]) & (ind["vol_raw"] >= cfg["vol_mult"] * ind["vavg20"])
            return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
    raise ValueError(f"not a stock family: {fam}")


# --------------------------------------------------------- ETF-world legs
def _gate(name: str, t10: np.ndarray, i: int) -> bool:
    if name == "none":
        return True
    if name == "t10y2y_pos":
        return bool(np.isfinite(t10[i]) and t10[i] > 0)
    if name == "t10y2y_rise3m":
        return bool(i >= 63 and np.isfinite(t10[i]) and np.isfinite(t10[i - 63]) and t10[i] > t10[i - 63])
    raise ValueError(name)


def legs_l01(cfg: dict, W: dict) -> dict:
    C, t10, T = W["C"], W["t10"], W["C"].shape[1]
    L = 21 * cfg["lookback_m"]
    secs = W["sector_idx"]
    sig = {si: np.zeros(T, bool) for si in secs}
    for i in np.flatnonzero(W["me"]):
        if i < max(L, 63) + 1 or not _gate(cfg["curve_gate"], t10, i):
            continue
        cands = []
        for si in secs:
            ret = C[si, i] / C[si, i - L] - 1.0
            if np.isfinite(ret) and ret > 0:
                cands.append((-ret, si))
        cands.sort()
        for _, si in cands[: cfg["top_k"]]:
            sig[si][i] = True
    return {si: (sig[si], None, 0, 21) for si in secs}


def legs_l02(cfg: dict, W: dict) -> dict:
    C, si = W["C"], W["spy"]
    T = C.shape[1]
    sig = np.zeros(T, bool)
    sma200 = pd.Series(C[si]).rolling(200, min_periods=200).mean().to_numpy()
    for o_idx in W["opex"]:
        s = o_idx - cfg["pre_days"] - 1
        if s < 0:
            continue
        if cfg["trend"] == "sma200" and not (C[si, s] > sma200[s]):
            continue
        sig[s] = True
    return {si: (sig, None, 0, cfg["hold_d"])}


def legs_l06(cfg: dict, W: dict) -> dict:
    si = W["spy"]
    vix = pd.Series(W["vix"])
    mode = cfg["mode"]
    if mode.startswith("level"):
        cond = vix < float(mode[5:])
    else:
        q = int(mode[3:]) / 100.0
        cond = vix < vix.shift(1).rolling(252, min_periods=252).quantile(q)
    cond = cond.fillna(False).to_numpy(bool)
    k = cfg["confirm_d"]
    state = pd.Series(cond.astype(float)).rolling(k, min_periods=k).min().fillna(0.0).to_numpy() == 1.0
    sig = state & ~_shift1(state)
    return {si: (sig, ~cond, 0, BIG_HOLD)}


def legs_l07(cfg: dict, W: dict) -> dict:
    si, vix = W["spy"], W["vix"]
    prev = np.r_[np.nan, vix[:-1]]
    with np.errstate(invalid="ignore"):
        sig = (vix >= cfg["vix_thr"]) & (vix < prev)
    return {si: (sig, None, 0, cfg["hold_d"])}


def legs_l08(cfg: dict, W: dict) -> dict:
    C, spy, secs = W["C"], W["spy"], W["sector_idx"]
    T = C.shape[1]
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = C / C[spy]
    ma = _roll(ratio, cfg["ma_n"])
    spy_sma = pd.Series(C[spy]).rolling(200, min_periods=200).mean().to_numpy()
    sig = {si: np.zeros(T, bool) for si in secs}
    for i in range(max(cfg["ma_n"], 200) + 1, T, cfg["rebal_d"]):
        if cfg["spy_trend"] == "spy_sma200" and not (C[spy, i] > spy_sma[i]):
            continue
        for si in secs:
            if np.isfinite(ratio[si, i]) and np.isfinite(ma[si, i]) and ratio[si, i] > ma[si, i]:
                sig[si][i] = True
    return {si: (sig[si], None, 0, cfg["rebal_d"]) for si in secs}


def legs_l12(cfg: dict, W: dict) -> dict:
    C, spy, dates = W["C"], W["spy"], W["dates"]
    T = len(dates)
    sma200 = pd.Series(C[spy]).rolling(200, min_periods=200).mean().to_numpy()
    last_by_year: dict[int, int] = {}
    for idx, y in enumerate(dates.year):
        last_by_year[int(y)] = idx
    max_year = int(dates.year.max())
    sig = np.zeros(T, bool)
    for y, D in last_by_year.items():
        if y >= max_year:  # 2018 is cut at the TRAIN boundary: year-end not inside TRAIN
            continue
        s = D - cfg["entry_before_ye"]
        if s < 0:
            continue
        if cfg["trend"] == "sma200" and not (C[spy, s] > sma200[s]):
            continue
        sig[s] = True
    return {spy: (sig, None, 0, cfg["hold_d"])}


ETF_BUILDERS = {L01: legs_l01, L02: legs_l02, L06: legs_l06, L07: legs_l07, L08: legs_l08, L12: legs_l12}


# ---------------------------------------------------------- simulation
def simulate_trades(sig, rule, stop_k, hold, o, h, l, c, atr):
    """Same execution rules as search_rb500_us.simulate, returning per-trade records."""
    T = len(o)
    busy = -1
    E, X, NET = [], [], []
    counts = np.zeros(4, dtype=np.int64)  # gap-skipped, nan-skipped, below-stop, right-censored
    for i in np.flatnonzero(sig):
        if i < busy:
            continue
        e = i + 1
        if e >= T:
            break
        entry = o[e]
        if not np.isfinite(entry):
            counts[1] += 1
            continue
        stop = None
        if stop_k > 0:
            if not np.isfinite(atr[i]):
                counts[1] += 1
                continue
            stop = entry - stop_k * atr[i]
            if entry <= stop:
                counts[2] += 1
                continue
        tlast = e + hold - 1
        end = min(tlast, T - 1)
        seg = np.concatenate([o[e:end + 1], h[e:end + 1], l[e:end + 1], c[e:end + 1]])
        if np.isnan(seg).any():
            counts[0] += 1
            continue
        x, price, _ = base._exit(e, end, tlast, T, stop, rule, o, l, c)
        if x is None:
            counts[3] += 1
            break
        E.append(e)
        X.append(x)
        NET.append(price / entry - 1.0 - COST_RT)
        busy = x
    return np.asarray(E, dtype=np.int64), np.asarray(X, dtype=np.int64), np.asarray(NET, dtype=float), counts


def _work_stock(si: int):
    m = CTX["m"]
    o, h, l, c, v = (m[k][si] for k in ("O", "H", "L", "C", "V"))
    ind = base.symbol_indicators(o, h, l, c, v)
    ind["vol_raw"] = v
    with np.errstate(invalid="ignore", divide="ignore"):
        rng = h - l
        ind["clv"] = np.where(rng > 0, (c - l) / rng, np.nan)
        ind["ret"] = np.r_[np.nan, c[1:] / c[:-1] - 1.0]
    out = {}
    for cfg in CTX["stock_cfgs"]:
        cid = cfg["config_id"]
        try:
            sig, rule, stop_k, hold = stock_leg(cfg, ind, si)
            for d in (0, 1):
                s, r = (sig, rule) if d == 0 else _delay(sig, rule)
                out[(cid, d)] = simulate_trades(s, r, stop_k, hold, o, h, l, c, ind["atr"])
        except Exception as exc:  # recorded as a failed config, never dropped silently
            out[(cid, "error")] = f"{type(exc).__name__}: {exc}"
    return si, out


def run_stock_world(m: dict, processes: int):
    S = len(m["syms"])
    results: dict = {}
    errors: dict = {}
    with mp.get_context("fork").Pool(processes) as pool:
        for si, out in pool.imap_unordered(_work_stock, range(S)):
            for key, val in out.items():
                if key[1] == "error":
                    errors.setdefault(key[0], val)
                    continue
                results.setdefault(key, []).append((si, val))
    return results, errors


def run_etf_world(W: dict):
    results: dict = {}
    errors: dict = {}
    atr = {si: base.symbol_indicators(W["O"][si], W["H"][si], W["L"][si], W["C"][si], W["V"][si])["atr"]
           for si in range(len(W["syms"]))}
    for cfg in CONFIGS:
        if cfg["family"] not in ETF_FAMILIES:
            continue
        cid = cfg["config_id"]
        try:
            legs = ETF_BUILDERS[cfg["family"]](cfg, W)
            for d in (0, 1):
                parts = []
                for si, (sig, rule, stop_k, hold) in legs.items():
                    s, r = (sig, rule) if d == 0 else _delay(sig, rule)
                    parts.append((si, simulate_trades(s, r, stop_k, hold, W["O"][si], W["H"][si],
                                                      W["L"][si], W["C"][si], atr[si])))
                results[(cid, d)] = parts
        except Exception as exc:
            errors[cid] = f"{type(exc).__name__}: {exc}"
    return results, errors


# -------------------------------------------------------------- stats
def core_stats(net: np.ndarray) -> dict:
    n = int(net.size)
    if n == 0:
        return {"n": 0, "win_rate": None, "wilson_lower": None, "pf": None, "expectancy_bp": None,
                "p_raw": None, "breakeven": None}
    wins = net > 0
    nw = int(wins.sum())
    nl = n - nw
    sw = float(net[wins].sum())
    sl = float(-net[~wins].sum())
    mean = float(net.mean())
    sd = float(net.std(ddof=1)) if n > 1 else float("nan")
    if n > 1 and sd > 0:
        p = float(sps.t.sf(mean / (sd / math.sqrt(n)), n - 1))
    else:
        p = 1.0 if mean <= 0 else 0.0
    avg_w = sw / nw if nw else None
    avg_l = sl / nl if nl else None
    be = avg_l / (avg_w + avg_l) if (avg_w is not None and avg_l is not None) else None
    pf = (sw / sl) if sl > 0 else (float("inf") if sw > 0 else None)
    return {"n": n, "win_rate": nw / n, "wilson_lower": wilson_lower(nw, n), "pf": pf,
            "expectancy_bp": mean * 1e4, "p_raw": p, "breakeven": be}


def cluster_p(E: np.ndarray, net: np.ndarray):
    if net.size == 0:
        return None
    per_date = pd.Series(net).groupby(E).mean().to_numpy()
    k = per_date.size
    if k < 2:
        return None
    mean = per_date.mean()
    sd = per_date.std(ddof=1)
    if sd > 0:
        return float(sps.t.sf(mean / (sd / math.sqrt(k)), k - 1))
    return 1.0 if mean <= 0 else 0.0


def year_check(E: np.ndarray, net: np.ndarray, dates: pd.DatetimeIndex, bear: dict) -> dict:
    out = {"years_eligible": 0, "years_pos": 0, "pos_share": None, "bear_eligible": 0,
           "bear_pool_exp_bp": None, "year_pass": False, "year_exp_bp": {}}
    if net.size == 0:
        return out
    years = np.asarray(dates.year)[E]
    eligible = []
    for y in np.unique(years):
        mask = years == y
        if mask.sum() >= YEAR_MIN_TRADES:
            e_bp = float(net[mask].mean() * 1e4)
            out["year_exp_bp"][int(y)] = round(e_bp, 2)
            eligible.append(int(y))
            if e_bp > 0:
                out["years_pos"] += 1
    out["years_eligible"] = len(eligible)
    if eligible:
        out["pos_share"] = out["years_pos"] / len(eligible)
    bear_years = {y for y, b in bear.items() if b}
    bear_mask = np.isin(years, list(bear_years))
    out["bear_eligible"] = sum(1 for y in eligible if y in bear_years)
    if bear_mask.any():
        out["bear_pool_exp_bp"] = float(net[bear_mask].mean() * 1e4)
    out["year_pass"] = bool(
        out["years_eligible"] >= YEAR_MIN_COUNT and out["pos_share"] is not None
        and out["pos_share"] >= YEAR_POS_SHARE and out["bear_eligible"] >= 1
        and out["bear_pool_exp_bp"] is not None and out["bear_pool_exp_bp"] > 0)
    return out


def top3_check(sym: np.ndarray, net: np.ndarray, syms: list[str]):
    traded = np.unique(sym)
    if traded.size < 4:
        return None, []
    sums = pd.Series(net).groupby(sym).sum().sort_values(ascending=False)
    top = [int(k) for k in sums.index[:3]]
    keep = ~np.isin(sym, top)
    return core_stats(net[keep]), [syms[k] for k in top]


def passes_core(s, thr: float) -> bool:
    if s is None or s["n"] < MIN_N or s["pf"] is None or s["pf"] < MIN_PF:
        return False
    if s["expectancy_bp"] is None or s["expectancy_bp"] < MIN_EXP_BP:
        return False
    if s["wilson_lower"] is None or s["breakeven"] is None:
        return False
    return s["wilson_lower"] > s["breakeven"] and s["p_raw"] <= thr


def evaluate(rec: dict, N: int) -> dict:
    thr = ALPHA / N
    flags = {
        "screen_pass": passes_core(rec["base"], thr),
        "delay1_pass": passes_core(rec["delay"], thr),
        "cost2x_pass": passes_core(rec["cost2x"], thr),
        "cluster_pass": rec["p_cluster"] is not None and rec["p_cluster"] <= CLUSTER_ALPHA,
        "year_pass": bool(rec["year"]["year_pass"]),
        "top3_pass": rec["top3"] is not None and passes_core(rec["top3"], thr),
    }
    flags["candidate"] = bool(flags["screen_pass"] and all(
        flags[k] for k in ("delay1_pass", "cost2x_pass", "cluster_pass", "year_pass", "top3_pass")))
    flags["bonferroni_thr"] = thr
    flags["N_denominator"] = N
    return flags


def assemble(results: dict, cfg: dict, world: str, syms: list[str], dates: pd.DatetimeIndex, bear: dict):
    cid = cfg["config_id"]
    if (cid, 0) not in results:
        return None
    parts0 = results[(cid, 0)]
    parts1 = results[(cid, 1)]

    def cat(parts):
        items = parts
        sym = np.concatenate([np.full(v[0].size, si, dtype=np.int64) for si, v in items]) if items else np.zeros(0, np.int64)
        E = np.concatenate([v[0] for _, v in items]) if items else np.zeros(0, np.int64)
        NET = np.concatenate([v[2] for _, v in items]) if items else np.zeros(0)
        counts = np.sum([v[3] for _, v in items], axis=0) if items else np.zeros(4, np.int64)
        return sym, E, NET, counts

    sym0, E0, net0, counts0 = cat(parts0)
    _, E1, net1, _ = cat(parts1)
    top3, top_names = top3_check(sym0, net0, syms)
    rec = {
        "base": core_stats(net0), "delay": core_stats(net1),
        "cost2x": core_stats(net0 - COST_RT), "p_cluster": cluster_p(E0, net0),
        "year": year_check(E0, net0, dates, bear), "top3": top3, "top3_names": top_names,
        "symbols_traded": int(np.unique(sym0).size), "gap_skipped": int(counts0[0]),
        "nan_skipped": int(counts0[1]), "below_stop_skipped": int(counts0[2]),
        "right_censored": int(counts0[3]),
        "single_instrument": len(syms) == 1 or int(np.unique(sym0).size) < 2,
    }
    return rec


def neighbor_index(configs: list[dict]) -> dict[int, list[int]]:
    index = {}
    for cfg in configs:
        key = (cfg["family"], tuple(sorted((k, v) for k, v in cfg.items() if k not in ("config_id", "family"))))
        index[key] = cfg["config_id"]
    axes = dict(grid.FAMILIES)
    out = {}
    for cfg in configs:
        nb = []
        for name, values in axes[cfg["family"]].items():
            v = cfg[name]
            if isinstance(v, str):
                continue
            pos = values.index(v)
            for step in (-1, 1):
                if 0 <= pos + step < len(values):
                    other = dict(cfg)
                    other[name] = values[pos + step]
                    key = (cfg["family"], tuple(sorted((k, vv) for k, vv in other.items()
                                                       if k not in ("config_id", "family"))))
                    if key in index:
                        nb.append(index[key])
        out[cfg["config_id"]] = nb
    return out


# ------------------------------------------------------------- ledger
def ledger_rows_count(path: Path) -> int:
    return base.ledger_rows_count(path)


def append_ledger(make_rows) -> int:
    """Append-only under flock. make_rows(count) returns rows using the count seen under the lock."""
    RUNS.mkdir(parents=True, exist_ok=True)
    lock_path = RUNS / ".cointrade_train_trials.lock"
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        count = ledger_rows_count(LEDGER)
        rows = make_rows(count)
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=TRIAL_FIELDS)
        for row in rows:
            writer.writerow(row)
        payload = buf.getvalue().encode("utf-8")
        fd = os.open(LEDGER, os.O_WRONLY | os.O_APPEND)
        try:
            before = os.fstat(fd).st_size
            written = os.write(fd, payload)
            if written != len(payload):
                os.ftruncate(fd, before)
                raise OSError("short append; partial rows rolled back")
        finally:
            os.close(fd)
    return count


def code_sha256() -> str:
    h = hashlib.sha256()
    for name in ("search_rb1000_us.py", "rb1000_us_grid.py", "PREREG_RB1000_US.md",
                 "search_rb500_us.py", "data_quality.py", "equities.py", "metrics.py"):
        h.update(name.encode() + b"\0")
        h.update((ROOT / name).read_bytes())
    return h.hexdigest()


def _jsonable(v):
    if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
        return "inf" if v == float("inf") else (None if math.isnan(v) else "-inf")
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return _jsonable(float(v))
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def _flat_metric(rec: dict, flags: dict) -> dict:
    out = {"status": "ok"}
    for k in ("n", "win_rate", "wilson_lower", "pf", "expectancy_bp", "p_raw", "breakeven"):
        out[k] = rec["base"][k]
    out.update({f"delay1_{k}": rec["delay"][k] for k in ("n", "pf", "expectancy_bp", "p_raw")})
    out.update({f"cost2x_{k}": rec["cost2x"][k] for k in ("n", "pf", "expectancy_bp", "p_raw")})
    out["p_cluster"] = rec["p_cluster"]
    y = rec["year"]
    out.update({"year_eligible": y["years_eligible"], "year_pos_share": y["pos_share"],
                "bear_eligible": y["bear_eligible"], "bear_pool_exp_bp": y["bear_pool_exp_bp"],
                "year_exp_bp": y["year_exp_bp"]})
    if rec["top3"] is None:
        out.update({"top3_n": None, "top3_exp_bp": None, "top3_pf": None, "top3_p_raw": None,
                    "top3_excluded": [], "top3_note": "N/A (fewer than 4 traded symbols)"})
    else:
        out.update({"top3_n": rec["top3"]["n"], "top3_exp_bp": rec["top3"]["expectancy_bp"],
                    "top3_pf": rec["top3"]["pf"], "top3_p_raw": rec["top3"]["p_raw"],
                    "top3_excluded": rec["top3_names"], "top3_note": ""})
    out.update({"symbols_traded": rec["symbols_traded"], "gap_skipped": rec["gap_skipped"],
                "nan_skipped": rec["nan_skipped"], "below_stop_skipped": rec["below_stop_skipped"],
                "right_censored": rec["right_censored"]})
    out.update(flags)
    return {k: _jsonable(v) for k, v in out.items()}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processes", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    if grid.grid_sha256(CONFIGS) != PREREG_GRID_SHA256:
        raise RuntimeError("grid hash mismatch with preregistered value")

    n_pre = ledger_rows_count(LEDGER)
    N_used = n_pre + LEDGER_ADD
    symbols = [line.split(",")[1].strip() for line in base.UNIVERSE.read_text(encoding="utf-8-sig").splitlines()[1:]
               if line.strip()]
    stock_frames, stock_fail = base.load_frames(symbols)
    etf_frames, etf_fail = load_etf_frames(list(SECTORS) + [SPY])
    fred = load_fred()
    W = build_etf_world(etf_frames, fred)
    m = base.build_matrices(stock_frames)
    CTX.update(build_stock_context(m, W))
    CTX["stock_cfgs"] = [c for c in CONFIGS if c["family"] in STOCK_FAMILIES]
    stock_res, stock_err = run_stock_world(m, args.processes)
    etf_res, etf_err = run_etf_world(W)

    stock_dates = CTX["dates"]
    records: dict[int, dict] = {}
    for cfg in CONFIGS:
        cid = cfg["config_id"]
        if cfg["family"] in STOCK_FAMILIES:
            if cid in stock_err:
                records[cid] = {"error": stock_err[cid]}
                continue
            parts_by_key = {(cid, d): stock_res.get((cid, d), []) for d in (0, 1)}
            rec = assemble(parts_by_key, cfg, "stock", m["syms"], stock_dates, W["bear"])
        else:
            if cid in etf_err:
                records[cid] = {"error": etf_err[cid]}
                continue
            rec = assemble(etf_res, cfg, "etf", W["syms"], W["dates"], W["bear"])
        if rec is None:
            records[cid] = {"error": "no result"}
            continue
        if rec["single_instrument"] and cfg["family"] in ETF_FAMILIES:
            rec["top3"], rec["top3_names"] = None, []
        records[cid] = rec

    nbs = neighbor_index(CONFIGS)
    exp_of = {cid: r["base"]["expectancy_bp"] for cid, r in records.items() if "error" not in r}
    summary_rows = []
    for cfg in CONFIGS:
        cid = cfg["config_id"]
        params = {k: v for k, v in cfg.items() if k not in ("config_id", "family")}
        r = records[cid]
        if "error" in r:
            summary_rows.append({"config_id": cid, "family": cfg["family"], "params": json.dumps(params, sort_keys=True),
                                 "status": "failed", "error": r["error"]})
            continue
        neigh = [exp_of[j] for j in nbs[cid] if exp_of.get(j) is not None]
        base_e = exp_of[cid]
        pos = [x for x in neigh if x > 0]
        half = [x for x in neigh if base_e is not None and base_e > 0 and x >= 0.5 * base_e]
        r["neighbors"] = len(neigh)
        r["neighbor_pos_share"] = (len(pos) / len(neigh)) if neigh else None
        r["neighbor_half_share"] = (len(half) / len(neigh)) if neigh else None
        summary_rows.append({"config_id": cid, "family": cfg["family"], "params": json.dumps(params, sort_keys=True),
                             "status": "ok", "error": "", "neighbors": r["neighbors"],
                             "neighbor_pos_share": r["neighbor_pos_share"],
                             "neighbor_half_share": r["neighbor_half_share"], "_rec": r})

    code_sha = code_sha256()

    def make_rows_factory(N: int, now: str):
        rows = []
        for cfg in CONFIGS:
            cid = cfg["config_id"]
            params = {k: v for k, v in cfg.items() if k not in ("config_id", "family")}
            r = records[cid]
            if "error" in r:
                metric = {"status": "failed", "error": r["error"]}
                flags = {"candidate": False, "N_denominator": N}
            else:
                flags = evaluate(r, N)
                metric = _flat_metric(r, flags)
            rows.append({
                "trial_id": f"RB1000-US-{cid:03d}", "round": ROUND, "market_group": "US",
                "utc_timestamp": now,
                "definition": json.dumps({"config_id": cid, "family": cfg["family"], **params},
                                         sort_keys=True, separators=(",", ":")),
                "parameter_grid_hash": PREREG_GRID_SHA256, "code_sha256": code_sha,
                "train_period": "<=2018-10-26T23:59:00Z (common cutoff inclusive)",
                "metric": json.dumps(metric, sort_keys=True, separators=(",", ":"), default=str),
                "rank": "",
                "notes": "TRAIN only; not G; TRAIN_ONLY_NOT_G; survivors-only(stocks); lane US; "
                         f"N_denominator={N}; candidate={bool(flags.get('candidate'))}"})
        return rows

    now = datetime.now(timezone.utc).isoformat()
    final_flags = {}
    ledger_count_at_write = None
    if not args.no_ledger:
        ledger_count_at_write = append_ledger(lambda count: make_rows_factory(count + LEDGER_ADD, now))
        N_final = ledger_count_at_write + LEDGER_ADD
    else:
        N_final = N_used

    # per-config CSV (flags with the denominator actually used)
    RUNS.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for row in summary_rows:
        if row["status"] != "ok":
            out_rows.append(row)
            continue
        r = row.pop("_rec")
        flags = evaluate(r, N_final)
        flat = _flat_metric(r, flags)
        out_rows.append({**{k: row[k] for k in ("config_id", "family", "params", "status", "error",
                                                 "neighbors", "neighbor_pos_share", "neighbor_half_share")},
                         **{k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in flat.items()}})
        final_flags[row["config_id"]] = flags["candidate"]
    fields = []
    for r_ in out_rows:
        for k in r_:
            if k not in fields:
                fields.append(k)
    out_csv = RUNS / "RB1000_US_configs.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r_ in out_rows:
            w.writerow({k: ("" if v is None else v) for k, v in r_.items()})

    fam_counts: dict = {}
    for row in out_rows:
        f = row["family"]
        d = fam_counts.setdefault(f, {"configs": 0, "failed": 0, "screen": 0, "candidates": 0, "exp_pos": 0})
        d["configs"] += 1
        if row["status"] != "ok":
            d["failed"] += 1
            continue
        d["screen"] += int(bool(row["screen_pass"]))
        d["candidates"] += int(bool(row["candidate"]))
        d["exp_pos"] += int(row["expectancy_bp"] is not None and float(row["expectancy_bp"]) > 0)
    summary = {
        "round": ROUND, "n_pre_run_start": n_pre, "ledger_count_at_write": ledger_count_at_write,
        "N_denominator_used": N_final, "bonferroni_thr": ALPHA / N_final,
        "symbols_loaded_stock": len(stock_frames), "symbols_failed_stock": stock_fail,
        "symbols_loaded_etf": len(etf_frames), "symbols_failed_etf": etf_fail,
        "bear_years": {int(k): v for k, v in W["bear"].items()},
        "opex_days": int(len(W["opex"])),
        "family_counts": fam_counts,
        "candidates": [cid for cid, ok in final_flags.items() if ok],
        "code_sha256": code_sha, "grid_sha256": PREREG_GRID_SHA256,
    }
    (RUNS / "RB1000_US_summary.json").write_text(
        json.dumps(summary, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_pre_run_start", "ledger_count_at_write",
                                               "N_denominator_used", "candidates")}, ensure_ascii=False))
    print(json.dumps(fam_counts, ensure_ascii=False))
    return 0


PREREG_GRID_SHA256 = "0754dc1d2b1154624228a1cdef52a1a9aca428f220addc348433008e6751af94"

if __name__ == "__main__":
    raise SystemExit(main())
