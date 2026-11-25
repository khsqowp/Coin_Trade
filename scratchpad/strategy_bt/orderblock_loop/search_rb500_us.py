"""RB500-US TRAIN-only runner: 500 preregistered US daily configurations.

Implements PREREG_RB500_US.md. Only rows dated <= 2018-10-26 are read from the
Yahoo panel (predicate pushdown). Trades: next-bar-open entry, stop/rule/time
exits, 20bp round-trip cost. Results are sufficient statistics per config.
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
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

import rb500_us_grid as grid
from data_quality import SymbolQualityError, filter_equity_bars
from equities import preregistered_costs
from metrics import wilson_lower

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("TRADING_DATA_DIR", "/Users/user/CODE/Coin_Trade/trading_data"))
PARQUET = DATA_DIR / "external/equities/us/yahoo_daily_us_stocks.parquet"
UNIVERSE = ROOT / "universe/US.csv"
LEDGER = ROOT / "TRAIN_TRIALS.csv"
RUNS = DATA_DIR / "cache/orderblock/runs"
ROUND = "RB500-US"
CUTOFF = pd.Timestamp("2018-10-26 23:59:00")
TRIAL_FIELDS = ["trial_id", "round", "market_group", "utc_timestamp", "definition",
                "parameter_grid_hash", "code_sha256", "train_period", "metric", "rank", "notes"]
_COSTS = preregistered_costs("US")
COST_ONE_WAY = (_COSTS.commission_bps_per_side + _COSTS.slippage_bps_per_side) / 10_000
COST_RT = 2 * COST_ONE_WAY
TIME_CAP_F12 = 250
MIN_BREADTH_SYMBOLS = 50
# accumulator slots
N, NW, NL, SW, SL, SUM, SQ, M2N, M2S, GAP, NANSK, BELOW, CENS, ERR = range(14)
NACC = 14

CONFIGS = grid.build_grid()
CTX: dict = {}


# ---------------------------------------------------------------- data
def load_frames(symbols: list[str]) -> tuple[dict, dict]:
    """Return ({symbol: frame}, {symbol: reason}) using only TRAIN-dated rows."""
    df = pd.read_parquet(
        PARQUET, columns=["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"],
        filters=[("date", "<=", CUTOFF), ("ticker", "in", sorted(symbols))])
    if not df.empty and df["date"].max() > CUTOFF:
        raise RuntimeError("post-cutoff row returned by loader")
    frames, failures = {}, {}
    for sym, g in df.groupby("ticker", sort=True):
        try:
            frames[sym] = _clean_symbol(sym, g)
        except (SymbolQualityError, ValueError) as exc:
            failures[sym] = f"{type(exc).__name__}: {exc}"
    return frames, failures


def _clean_symbol(sym: str, g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date")
    factor = g["adj_close"].to_numpy(float) / g["close"].to_numpy(float)
    frame = pd.DataFrame({
        "open_time": g["date"].values.astype("datetime64[ms]").astype(np.int64),
        "open": g["open"].to_numpy(float) * factor,
        "high": g["high"].to_numpy(float) * factor,
        "low": g["low"].to_numpy(float) * factor,
        "close": g["adj_close"].to_numpy(float),
        "volume": g["volume"].to_numpy(float),
    })
    vals = frame[["open", "high", "low", "close"]].to_numpy()
    ok = np.isfinite(vals).all(axis=1) & (vals > 0).all(axis=1) & np.isfinite(factor)
    ok &= frame["high"].to_numpy() >= frame["low"].to_numpy()
    tol = 1e-9
    for col in ("open", "close"):
        ok &= frame[col].to_numpy() <= frame["high"].to_numpy() * (1 + tol)
        ok &= frame[col].to_numpy() >= frame["low"].to_numpy() * (1 - tol)
    frame = frame.loc[ok].reset_index(drop=True)
    if frame["open_time"].duplicated().any() or not frame["open_time"].is_monotonic_increasing:
        raise ValueError("non-unique or unsorted dates")
    kept, _ = filter_equity_bars(frame, sym)
    if kept.empty:
        raise ValueError("no usable rows after quality filter")
    return kept


def build_matrices(frames: dict[str, pd.DataFrame]) -> dict:
    syms = sorted(frames)
    cal = np.unique(np.concatenate([f["open_time"].to_numpy() for f in frames.values()]))
    S, T = len(syms), len(cal)
    mats = {k: np.full((S, T), np.nan) for k in ("O", "H", "L", "C", "V")}
    for si, sym in enumerate(syms):
        f = frames[sym]
        pos = np.searchsorted(cal, f["open_time"].to_numpy())
        mats["O"][si, pos] = f["open"].to_numpy()
        mats["H"][si, pos] = f["high"].to_numpy()
        mats["L"][si, pos] = f["low"].to_numpy()
        mats["C"][si, pos] = f["close"].to_numpy()
        mats["V"][si, pos] = f["volume"].to_numpy()
    dates = pd.to_datetime(cal, unit="ms")
    month = dates.year * 12 + dates.month
    me = np.zeros(T, bool)
    me[:-1] = month[1:] != month[:-1]
    me[-1] = True
    last_k = {}
    for k in (1, 2, 3):
        flags = np.zeros(T, bool)
        for d in range(k):
            flags[:T - d] |= me[d:]
        last_k[k] = flags
    return {"syms": syms, "cal": cal, "me": me, "last_k": last_k, **mats}


def _shift(M: np.ndarray, k: int) -> np.ndarray:
    out = np.full_like(M, np.nan)
    if k == 0:
        return M.copy()
    out[:, k:] = M[:, :-k]
    return out


def cross_sectional_context(m: dict) -> dict:
    """Breadth gate, feature matrices, and rebalance picks for the 152 XS configs."""
    C = m["C"]
    sma200 = pd.DataFrame(C.T).rolling(200, min_periods=200).mean().to_numpy().T
    valid = np.isfinite(C) & np.isfinite(sma200)
    n_valid = valid.sum(axis=0)
    n_above = (valid & (C > sma200)).sum(axis=0)
    breadth = np.where(n_valid >= MIN_BREADTH_SYMBOLS, n_above / np.maximum(n_valid, 1), np.nan)
    ctx = {"breadth_ok": (~np.isnan(breadth)) & (np.nan_to_num(breadth, nan=0.0) >= 0.5),
           "last_k": m["last_k"]}
    lr = np.full_like(C, np.nan)
    lr[:, 1:] = np.log(C[:, 1:] / C[:, :-1])
    ctx["feats_base"] = {
        "vol63": pd.DataFrame(lr.T).rolling(63, min_periods=63).std(ddof=1).to_numpy().T,
        "vol252": pd.DataFrame(lr.T).rolling(252, min_periods=252).std(ddof=1).to_numpy().T,
        "pos12": (C / _shift(C, 252)) > 1.0,
    }
    ctx["picks"] = {}
    for cfg in CONFIGS:
        if cfg["family"] in ("F01_MOM_12_1_XS", "F02_LOWVOL_QUALITY_XS", "F11_SHORT_REVERSAL_XS"):
            ctx["picks"][cfg["config_id"]] = _picks(cfg, m, ctx)
    return ctx


def _ret(C: np.ndarray, lb_days: int, skip_days: int) -> np.ndarray:
    return _shift(C, skip_days) / _shift(C, lb_days) - 1.0


def _gate_ok(cfg: dict, ctx: dict, i: int) -> bool:
    return True if cfg.get("gate", cfg.get("regime", "none")) == "none" else bool(ctx["breadth_ok"][i])


def _picks(cfg: dict, m: dict, ctx: dict) -> tuple[np.ndarray, np.ndarray]:
    C, me = m["C"], m["me"]
    fam = cfg["family"]
    if fam == "F01_MOM_12_1_XS":
        score = _ret(C, 21 * cfg["lookback_m"], 21 * cfg["skip_m"])
        rows, n, descending, qmask = np.flatnonzero(me), cfg["top_n"], True, None
        min_row = 21 * cfg["lookback_m"]
    elif fam == "F02_LOWVOL_QUALITY_XS":
        score = ctx["feats_base"][f"vol{cfg['vol_window']}"]
        rows, n, descending = np.flatnonzero(me), cfg["bottom_n"], False
        qmask = ctx["feats_base"]["pos12"] if cfg["quality"] == "pos_12m" else None
        min_row = cfg["vol_window"] + 1
    else:
        lb = cfg["lookback_d"]
        score = _ret(C, lb, 0)
        rows = np.arange(lb, C.shape[1], lb)
        n, descending, qmask = cfg["bottom_n"], False, None
        min_row = lb
    I, S = [], []
    for i in rows:
        if i < min_row or not _gate_ok(cfg, ctx, i):
            continue
        s_all = score[:, i]
        ok = np.isfinite(s_all) & np.isfinite(C[:, i])
        if qmask is not None:
            ok &= qmask[:, i]
        cand = np.flatnonzero(ok)
        if cand.size == 0:
            continue
        order = cand[np.argsort(-s_all[cand] if descending else s_all[cand], kind="stable")]
        chosen = order[:n]
        I.extend([i] * len(chosen))
        S.extend(chosen.tolist())
    return np.asarray(I, dtype=np.int64), np.asarray(S, dtype=np.int64)


# ---------------------------------------------------------- indicators
def symbol_indicators(o, h, l, c, v) -> dict:
    valid = np.isfinite(o) & np.isfinite(h) & np.isfinite(l) & np.isfinite(c)
    cs = pd.Series(c)
    ind = {"valid": valid, "c": c, "o": o}
    for n in (5, 10, 20, 50, 100, 200):
        ind[f"sma{n}"] = cs.rolling(n, min_periods=n).mean().to_numpy()
    prev = cs.shift(1).to_numpy()
    tr = np.fmax(h - l, np.fmax(np.abs(h - prev), np.abs(l - prev)))
    ind["atr"] = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()
    d = cs.diff()
    up = d.clip(lower=0).rolling(2, min_periods=2).mean().to_numpy()
    dn = (-d).clip(lower=0).rolling(2, min_periods=2).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100 - 100 / (1 + up / dn)
    ind["rsi2"] = np.where(dn == 0, 100.0, rsi)
    ind["streak"] = _down_streak(c, valid)
    hi252 = pd.Series(h).rolling(252, min_periods=252).max().to_numpy()
    ind["ratio52"] = c / hi252
    ind["gap"] = o / prev - 1.0
    ind["range_prev"] = np.r_[np.nan, (h - l)[:-1]]
    ind["vavg20"] = pd.Series(v).shift(1).rolling(20, min_periods=20).mean().to_numpy()
    for nn in (20, 55, 120):
        ind[f"dmax{nn}"] = pd.Series(c).shift(1).rolling(nn, min_periods=nn).max().to_numpy()
    for mm in (10, 20):
        ind[f"dmin{mm}"] = pd.Series(c).shift(1).rolling(mm, min_periods=mm).min().to_numpy()
    return ind


def _down_streak(c: np.ndarray, valid: np.ndarray) -> np.ndarray:
    out = np.zeros(len(c))
    for i in range(1, len(c)):
        if valid[i] and valid[i - 1] and c[i] < c[i - 1]:
            out[i] = out[i - 1] + 1
    return out


def _trend(name: str, ind: dict) -> np.ndarray:
    if name == "none":
        return np.ones(len(ind["c"]), bool)
    n = int(name.replace("sma", ""))
    with np.errstate(invalid="ignore"):
        return ind["c"] > ind[f"sma{n}"]


def _prev(x: np.ndarray) -> np.ndarray:
    return np.r_[np.nan, x[:-1]]


def build_signal(cfg: dict, ind: dict, si: int, ctx: dict):
    """Return (signal, rule_exit_mask or None, stop_atr, hold_bars) for one symbol."""
    fam, c, o, valid = cfg["family"], ind["c"], ind["o"], ind["valid"]
    if fam in ("F01_MOM_12_1_XS", "F02_LOWVOL_QUALITY_XS", "F11_SHORT_REVERSAL_XS"):
        I, S = ctx["picks"][cfg["config_id"]]
        sig = np.zeros(len(c), bool)
        sig[I[S == si]] = True
        return sig & valid, None, 0, cfg["hold_d"]
    if fam == "F03_RSI2_PULLBACK":
        with np.errstate(invalid="ignore"):
            sig = (ind["rsi2"] < cfg["rsi_thr"]) & _trend(f"sma{cfg['trend_sma']}", ind)
        rule = c > ind["sma5"]
        return sig & valid, rule, cfg["stop_atr"], cfg["max_hold"]
    if fam == "F04_DOWN_STREAK_REBOUND":
        sig = (ind["streak"] >= cfg["streak_n"]) & _trend(f"sma{cfg['trend_sma']}", ind)
        return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
    if fam == "F05_GAP_DOWN_REVERSAL":
        with np.errstate(invalid="ignore"):
            sig = (ind["gap"] <= -cfg["gap_pct"] / 100) & (c > o) & _trend(cfg["trend"], ind)
        return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
    if fam == "F06_NEAR_52W_HIGH":
        with np.errstate(invalid="ignore"):
            sig = (ind["ratio52"] >= cfg["prox"]) & _trend(cfg["trend"], ind)
        return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
    if fam == "F07_VOLUME_SURGE_UP":
        with np.errstate(invalid="ignore"):
            sig = (ctx_vol(ind) >= cfg["vol_mult"] * ind["vavg20"]) & (c > o) & _trend(cfg["trend"], ind)
        return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
    if fam == "F08_MA_CROSS_REGIME":
        fa, sl = (int(x) for x in cfg["pair"].split("_"))
        fast, slow = ind[f"sma{fa}"], ind[f"sma{sl}"]
        with np.errstate(invalid="ignore"):
            cross = (fast > slow) & (_prev(fast) <= _prev(slow))
            rule = fast < slow
        sig = cross & _regime(cfg["regime"], ctx)
        return sig & valid, rule, cfg["stop_atr"], cfg["max_hold"]
    if fam == "F09_TURN_OF_MONTH":
        sig = ctx["last_k"][cfg["days_before_end"]] & _trend(cfg["trend"], ind)
        return sig & valid, None, 0, cfg["hold_d"]
    if fam == "F10_VOL_BREAKOUT_CLOSE":
        with np.errstate(invalid="ignore"):
            sig = (c > o + cfg["k"] * ind["range_prev"]) & _trend(cfg["trend"], ind)
        return sig & valid, None, cfg["stop_atr"], cfg["hold_d"]
    if fam == "F12_DONCHIAN_TREND":
        with np.errstate(invalid="ignore"):
            sig = (c > ind[f"dmax{cfg['entry_n']}"]) & _regime(cfg["regime"], ctx)
            rule = c < ind[f"dmin{cfg['exit_m']}"]
        return sig & valid, rule, cfg["stop_atr"], TIME_CAP_F12
    raise ValueError(f"unknown family {fam}")


def ctx_vol(ind: dict) -> np.ndarray:
    return ind["vol_raw"]


def _regime(name: str, ctx: dict) -> np.ndarray:
    return np.ones(len(ctx["breadth_ok"]), bool) if name == "none" else ctx["breadth_ok"]


# --------------------------------------------------------- simulation
def simulate(sig, rule, stop_k, hold, o, h, l, c, atr) -> np.ndarray:
    acc = np.zeros(NACC)
    T = len(o)
    busy = -1
    for i in np.flatnonzero(sig):
        if i < busy:
            continue
        e = i + 1
        if e >= T:
            break
        entry = o[e]
        if not np.isfinite(entry):
            acc[NANSK] += 1
            continue
        stop = None
        if stop_k > 0:
            if not np.isfinite(atr[i]):
                acc[NANSK] += 1
                continue
            stop = entry - stop_k * atr[i]
            if entry <= stop:
                acc[BELOW] += 1
                continue
        tlast = e + hold - 1
        end = min(tlast, T - 1)
        if np.isnan(np.concatenate([o[e:end + 1], h[e:end + 1], l[e:end + 1], c[e:end + 1]])).any():
            acc[GAP] += 1
            continue
        x, price, outcome = _exit(e, end, tlast, T, stop, rule, o, l, c)
        if x is None:
            acc[CENS] += 1
            break
        net = price / entry - 1.0 - COST_RT
        _add(acc, net)
        if stop is not None:
            acc[M2N] += 1
            acc[M2S] += _m2(entry, stop, h, l, e, x)
        busy = x
    return acc


def _exit(e, end, tlast, T, stop, rule, o, l, c):
    js = np.inf
    if stop is not None:
        hit = np.flatnonzero(l[e:end + 1] <= stop)
        if hit.size:
            js = hit[0]
    jr = np.inf
    if rule is not None:
        rr = np.flatnonzero(rule[e:end + 1])
        if rr.size:
            jr = rr[0]
    jt = (tlast - e) if tlast <= T - 1 else np.inf
    if np.isfinite(js) and js <= jr and js <= jt:
        x = e + int(js)
        return x, (o[x] if o[x] <= stop else stop), "stop"
    if np.isfinite(jr) and jr < jt:
        x = e + int(jr) + 1
        if x > T - 1:
            return None, None, "censored"
        return x, o[x], "rule"
    if np.isfinite(jt):
        x = tlast
        return x, c[x], "time"
    return None, None, "censored"


def _m2(entry, stop, h, l, e, x) -> int:
    target = entry + 2 * (entry - stop)
    ht = np.flatnonzero(h[e:x + 1] >= target)
    hs = np.flatnonzero(l[e:x + 1] <= stop)
    return int(ht.size > 0 and (hs.size == 0 or ht[0] < hs[0]))


def _add(acc, net):
    acc[N] += 1
    acc[SUM] += net
    acc[SQ] += net * net
    if net > 0:
        acc[NW] += 1
        acc[SW] += net
    else:
        acc[NL] += 1
        acc[SL] += -net


# ------------------------------------------------------------ workers
def _work(si: int):
    m = CTX["m"]
    o, h, l, c, v = (m[k][si] for k in ("O", "H", "L", "C", "V"))
    ind = symbol_indicators(o, h, l, c, v)
    ind["vol_raw"] = v
    out = np.zeros((len(CONFIGS), NACC))
    errors = {}
    for k, cfg in enumerate(CONFIGS):
        try:
            sig, rule, stop_k, hold = build_signal(cfg, ind, si, CTX)
            out[k] = simulate(sig, rule, stop_k, hold, o, h, l, c, ind["atr"])
        except Exception as exc:  # recorded, never silently dropped
            out[k, ERR] = 1
            errors[cfg["config_id"]] = f"{type(exc).__name__}: {exc}"
    return si, out, errors


def run_all(m: dict, ctx: dict, processes: int) -> tuple[np.ndarray, dict]:
    CTX.update({"m": m, **ctx})
    S = len(m["syms"])
    total = np.zeros((len(CONFIGS), NACC))
    errors: dict = {}
    per_sym = np.zeros((S, len(CONFIGS), NACC))
    with mp.get_context("fork").Pool(processes) as pool:
        for si, out, errs in pool.imap_unordered(_work, range(S)):
            per_sym[si] = out
            errors.update({f"{m['syms'][si]}|{k}": v for k, v in errs.items()})
    total = per_sym.sum(axis=0)
    symbols_traded = (per_sym[:, :, N] > 0).sum(axis=0)
    total = np.column_stack([total, symbols_traded])
    return total, errors


# -------------------------------------------------------------- stats
def metrics_row(acc: np.ndarray, symbols_traded: int, n_total: int) -> dict:
    n = int(acc[N])
    row = {"trades": n, "symbols_traded": symbols_traded, "gap_skipped": int(acc[GAP]),
           "nan_entry_skipped": int(acc[NANSK]), "below_stop_skipped": int(acc[BELOW]),
           "right_censored": int(acc[CENS]), "errors": int(acc[ERR])}
    if n == 0:
        row.update(win_rate=None, wilson_lower=None, pf=None, expectancy_bp=None, p_one_sided=None,
                   breakeven_win_rate=None, m2_n=int(acc[M2N]), m2_rate=None,
                   bonferroni_pass=False, screen_pass=False)
        return row
    mean = acc[SUM] / n
    var = (acc[SQ] - n * mean * mean) / (n - 1) if n > 1 else float("nan")
    sd = math.sqrt(max(var, 0.0)) if n > 1 else float("nan")
    if n > 1 and sd > 0:
        t = mean / (sd / math.sqrt(n))
        p = float(sps.t.sf(t, n - 1))
    else:
        p = 1.0 if mean <= 0 else 0.0
    avg_w = acc[SW] / acc[NW] if acc[NW] else None
    avg_l = acc[SL] / acc[NL] if acc[NL] else None
    be = avg_l / (avg_w + avg_l) if avg_w is not None and avg_l is not None else None
    pf = (acc[SW] / acc[SL]) if acc[SL] > 0 else (float("inf") if acc[SW] > 0 else None)
    wl = wilson_lower(int(acc[NW]), n)
    thr = 0.05 / n_total
    row.update(win_rate=acc[NW] / n, wilson_lower=wl, pf=pf, expectancy_bp=mean * 1e4,
               p_one_sided=p, breakeven_win_rate=be, m2_n=int(acc[M2N]),
               m2_rate=(acc[M2S] / acc[M2N]) if acc[M2N] else None,
               bonferroni_pass=bool(p <= thr))
    row["screen_pass"] = bool(n >= 60 and pf is not None and pf >= 1.30 and mean * 1e4 >= 30
                              and wl is not None and be is not None and wl > be
                              and row["bonferroni_pass"])
    return row


def numeric_neighbors(configs: list[dict]) -> dict[int, list[int]]:
    index = {}
    for cfg in configs:
        key = (cfg["family"], tuple((k, v) for k, v in cfg.items() if k not in ("config_id", "family")))
        index[key] = cfg["config_id"]
    axes = {fam: axes for fam, axes in grid.FAMILIES}
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
                    key = (cfg["family"], tuple((k, vv) for k, vv in other.items()
                                                if k not in ("config_id", "family")))
                    if key in index:
                        nb.append(index[key])
        out[cfg["config_id"]] = nb
    return out


def ledger_rows_count(path: Path) -> int:
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.reader(stream)
            header = next(reader)
            if header != TRIAL_FIELDS:
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            return sum(1 for _ in reader)
    finally:
        csv.field_size_limit(old)


def append_ledger(rows: list[dict], expected_before: int) -> None:
    """Append-only write under an exclusive flock; refuses if the denominator moved."""
    RUNS.mkdir(parents=True, exist_ok=True)
    lock_path = RUNS / ".cointrade_train_trials.lock"
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if ledger_rows_count(LEDGER) != expected_before:
            raise RuntimeError("ledger row count changed since run start; not appended")
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


def code_sha256() -> str:
    h = hashlib.sha256()
    for name in ("search_rb500_us.py", "rb500_us_grid.py", "PREREG_RB500_US.md",
                 "data_quality.py", "equities.py", "metrics.py"):
        h.update(name.encode() + b"\0")
        h.update((ROOT / name).read_bytes())
    return h.hexdigest()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processes", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    if grid.grid_sha256(CONFIGS) != "41b901a96c2cda2121ec2d21595bf16f294fbc9b490a00f475109c3d8bc14b2c":
        raise RuntimeError("grid hash mismatch with preregistered value")
    n_pre = ledger_rows_count(LEDGER)
    n_total = n_pre + len(CONFIGS)
    symbols = [line.split(",")[1].strip() for line in UNIVERSE.read_text(encoding="utf-8-sig").splitlines()[1:] if line.strip()]
    frames, failures = load_frames(symbols)
    m = build_matrices(frames)
    ctx = cross_sectional_context(m)
    total, errors = run_all(m, ctx, args.processes)
    rows = []
    for k, cfg in enumerate(CONFIGS):
        row = metrics_row(total[k, :NACC], int(total[k, NACC]), n_total)
        row.update({"config_id": cfg["config_id"], "family": cfg["family"],
                    "params": json.dumps({a: b for a, b in cfg.items() if a not in ("config_id", "family")},
                                         sort_keys=True)})
        rows.append(row)
    by_id = {r["config_id"]: r for r in rows}
    nbs = numeric_neighbors(CONFIGS)
    for cid, row in by_id.items():
        neigh = [by_id[j] for j in nbs[cid]]
        base = row["expectancy_bp"]
        pos = [x for x in neigh if x["expectancy_bp"] is not None and x["expectancy_bp"] > 0]
        half = ([x for x in neigh if x["expectancy_bp"] is not None and base is not None
                 and base > 0 and x["expectancy_bp"] >= 0.5 * base])
        row["neighbors"] = len(neigh)
        row["neighbor_pos_share"] = len(pos) / len(neigh) if neigh else None
        row["neighbor_half_share"] = len(half) / len(neigh) if neigh else None
    RUNS.mkdir(parents=True, exist_ok=True)
    out_csv = RUNS / "RB500_US_configs.csv"
    fields = list(rows[0].keys())
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    summary = {"n_pre": n_pre, "n_total": n_total, "symbols_loaded": len(frames),
               "symbols_failed": failures, "errors": len(errors),
               "code_sha256": code_sha256(), "grid_sha256": grid.grid_sha256(CONFIGS)}
    (RUNS / "RB500_US_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    if not args.no_ledger:
        now = datetime.now(timezone.utc).isoformat()
        ledger_rows_out = []
        for r in rows:
            metric = {k: ("inf" if v == float("inf") else v) for k, v in r.items()
                      if k not in ("config_id", "family", "params")}
            ledger_rows_out.append({
                "trial_id": f"RB500-US-{r['config_id']:03d}", "round": ROUND, "market_group": "US",
                "utc_timestamp": now, "definition": json.dumps(
                    {"config_id": r["config_id"], "family": r["family"], **json.loads(r["params"])},
                    sort_keys=True, separators=(",", ":")),
                "parameter_grid_hash": summary["grid_sha256"], "code_sha256": summary["code_sha256"],
                "train_period": "<=2018-10-26T23:59:00Z (common cutoff inclusive)",
                "metric": json.dumps(metric, sort_keys=True, separators=(",", ":"), default=str),
                "rank": "", "notes": "TRAIN only; not G; TRAIN_ONLY_NOT_G; survivors-only US.csv"})
        append_ledger(ledger_rows_out, n_pre)
    print(json.dumps({"n_pre": n_pre, "n_total": n_total, "symbols": len(frames),
                      "failures": len(failures), "errors": len(errors)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
