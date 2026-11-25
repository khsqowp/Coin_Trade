"""RB1000-KR: preregistered 200-configuration KR daily TRAIN screen (lane KR).

Families are chosen to avoid the RB500-KR families (XMOM/XLOWVOL/X52WH/TOM/REV/VOLSURGE/
MATREND/VBRK/DONCH): gap follow-through, limit-move follow-through, holiday/expiry/weekday
calendar effects, gap reversal, KOSPI/KOSDAQ/breadth regime switching, index-trend proxy.
Data access stops at the common KR train split (2018-10-26 23:59 UTC). All results are
TRAIN_ONLY_NOT_G. Price-limit-exceeding jumps are handled by the preregistered rule in
`adjust_corporate_actions` before any strategy is evaluated.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import multiprocessing as mp
import os
import sys
import traceback
from collections import Counter, namedtuple
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import search_crypto as ledger_common
import search_kr_r14_batch as base
from data_access import EQUITY_COMMON_SPLIT_MS, load_bars
from data_quality import SymbolQualityError, filter_equity_bars, tick_size
from metrics import core_gate, curve_metrics, trade_metrics
from search_equities_r5 import load_membership

HERE = Path(__file__).resolve().parent
ROUND = "RB1000-KR"
PREREG_PATH = HERE / "PREREG_RB1000_KR.md"
REPORT_PATH = HERE / "REPORT_RB1000_KR.md"
RUNS_DIR = base.RUNS_DIR
KR_DIR = base.KR_DIR
INDEX_PATH = base.INDEX_PATH
SPLIT_PATH = base.SPLIT_PATH
N_NEW = 200
LEDGER_ROWS_PRIOR = 3489          # measured 2026-11-25 at PREREG time (other lanes appended); reset at run start
EXPLORE500_ROWS = 429             # EXPLORE500 additions (common rule)
OTHER_LANES_CAP = 1000            # conservative cap for concurrent lanes (common rule)
BONFERRONI_N = LEDGER_ROWS_PRIOR + EXPLORE500_ROWS + OTHER_LANES_CAP  # 4918 at PREREG time; reset at run start
ALPHA = 0.05
ANNUAL_DAYS = 252
DAY_MS = base.DAY_MS
EPOCH = base.EPOCH
LIMIT_MOVE = 0.30                 # KRX daily price limit (base price)
LOCK_MOVE = 0.29                  # open-based limit proximity used for fill blocking
SPLIT_TOL = 0.02
SPLIT_MAX_N = 20
VOL_SPIKE = 1.5
MIN_BASKET = 30
MIN_SAMPLE_ROWS = 30
BUY_COST = base.BUY_COST
SELL_COST = base.SELL_COST
ROUND_TRIP_COST = base.ROUND_TRIP_COST
CODE_FILES = ("search_rb1000_kr.py", "search_kr_r14_batch.py", "data_access.py", "data_quality.py",
              "equities.py", "metrics.py", "search_equities_r5.py", "search_crypto.py")
TRAIN_PERIOD = "<=2018-10-26T23:59:00Z (KR common split)"

# Priority order (see PREREG_RB1000_KR.md). Every axis is a full cartesian product.
FAMILIES = (
    ("GAPUP", {"gap": (0.02, 0.04, 0.07), "confirm": ("green", "none"),
               "volume_filter": (None, VOL_SPIKE), "hold": (1, 3, 5, 10)}),
    ("LIMIT", {"direction": ("up", "down"), "threshold": (0.15, 0.29), "hold": (1, 3, 5, 10)}),
    ("PREHOL", {"k": (1, 2), "hold": (1, 2, 3, 5)}),
    ("OPEXP", {"offset": (-3, -2, -1, 1), "hold": (1, 2, 3, 5)}),
    ("WKDAY", {"weekday": (0, 4), "hold": (1, 2)}),
    ("GAPDN", {"gap": (0.02, 0.04, 0.07), "volume_filter": (None, VOL_SPIKE),
               "hold": (1, 3, 5, 10)}),
    ("RGM", {"indicator": ("KS11_SMA60", "KS11_SMA120", "KS11_SMA200", "KS11_MOM252",
                           "KQ11_SMA120", "BREADTH200"),
             "confirm": (1, 5), "direction": ("above", "below"),
             "universe": ("all", "liquid_half")}),
    ("ETFTR", {"index": ("KS200", "KS11", "KQ11"), "sma": (20, 40, 60, 100, 150, 200),
               "band": (0.0, 0.01)}),
)

Unit = namedtuple("Unit", "e x vec net group")
STATE = None


# ---------------------------------------------------------------- grid & hashes
def build_configs():
    configs = []
    for family, axes in FAMILIES:
        names = list(axes)
        for values in itertools.product(*(axes[name] for name in names)):
            configs.append({"family": family, "params": dict(zip(names, values))})
    if len(configs) != N_NEW:
        raise ValueError(f"grid must contain exactly {N_NEW} configs, got {len(configs)}")
    if len({json.dumps(c, sort_keys=True) for c in configs}) != N_NEW:
        raise ValueError("grid contains duplicate configs")
    return configs


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def grid_sha256(configs):
    return sha256_text(json.dumps(configs, sort_keys=True, separators=(",", ":")))


def code_sha256():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode() + b"\0")
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def verify_prereg(grid_sha, code_sha):
    text = PREREG_PATH.read_text(encoding="utf-8")
    for label, value in (("grid_sha256", grid_sha), ("code_sha256", code_sha)):
        if f"- {label}: `{value}`" not in text:
            raise RuntimeError(f"PREREG does not record {label}={value}; refusing to run")


# -------------------------------------------------------- price-limit jump rule
def split_ratio(factor):
    """Return n when prev/cur ratio matches a 1/n or n split within SPLIT_TOL, else 0."""
    for n in range(2, SPLIT_MAX_N + 1):
        if abs(factor * n - 1.0) <= SPLIT_TOL:
            return n
        if abs(factor / n - 1.0) <= SPLIT_TOL:
            return n
    return 0


def limit_threshold(prev_close):
    return LIMIT_MOVE + tick_size(prev_close) / prev_close + 1e-12


def _pair_thresholds(close):
    """Limit threshold per adjacent pair (k-1, k), computed on the ORIGINAL price scale."""
    return np.array([limit_threshold(p) for p in close[:-1]])


def _jump_indices(close, thr=None):
    prev, cur = close[:-1], close[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = cur / prev - 1.0
    thr = _pair_thresholds(close) if thr is None else thr
    return np.flatnonzero(np.abs(ret) > thr) + 1


def adjust_corporate_actions(t, o, h, l, c, v):
    """Preregistered rule (PREREG_RB1000_KR section 1.1).

    A close-to-close move beyond the KRX limit (30% plus one tick) is a corporate action or a
    bad print. Process moves from latest to earliest:
      * ratio matches 1/n or n (n=2..20, within 2%): back-adjust all earlier prices by the
        ratio and divide earlier volume by it (split/reverse-split continuity);
      * any other move: drop every bar before it (segment exclusion) and stop.
    Returns kept arrays and a report. Residual moves beyond the limit are counted after
    adjustment and must be zero.
    """
    t = np.asarray(t, dtype=np.int64)
    o, h, l, c, v = (np.array(x, dtype=float) for x in (o, h, l, c, v))
    v_orig = v.copy()
    report = {"rows_in": int(len(c)), "jumps": 0, "split_adjusted": 0, "split_ratios": {},
              "truncated": False, "truncation_index": None, "rows_dropped": 0,
              "residual_jumps": 0, "volume_ratio_split_median": None}
    if len(c) < 2:
        return t, o, h, l, c, v, report
    thr_pairs = _pair_thresholds(c)
    jumps = _jump_indices(c, thr_pairs)
    report["jumps"] = int(len(jumps))
    if len(jumps) == 0:
        return t, o, h, l, c, v, report
    factors = {int(k): float(c[k] / c[k - 1]) for k in jumps}
    vol_ratios = []
    cut = 0
    for k in jumps[::-1]:
        k = int(k)
        f = factors[k]
        n = split_ratio(f)
        if n == 0:
            cut = k
            report["truncated"] = True
            report["truncation_index"] = k
            break
        o[:k] *= f
        h[:k] *= f
        l[:k] *= f
        c[:k] *= f
        v[:k] /= f
        report["split_adjusted"] += 1
        report["split_ratios"][str(n)] = report["split_ratios"].get(str(n), 0) + 1
        if v_orig[k - 1] > 0:
            vol_ratios.append(float(v_orig[k] / v_orig[k - 1]))
    report["rows_dropped"] = int(cut)
    if vol_ratios:
        report["volume_ratio_split_median"] = float(np.median(vol_ratios))
    t, o, h, l, c, v = t[cut:], o[cut:], h[cut:], l[cut:], c[cut:], v[cut:]
    if len(c) >= 2:
        with np.errstate(divide="ignore", invalid="ignore"):
            ret_after = c[1:] / c[:-1] - 1.0
        report["residual_jumps"] = int(np.sum(np.abs(ret_after) > thr_pairs[cut:]))
    return t, o, h, l, c, v, report


# ----------------------------------------------------------------- data loading
def _load_stock(row, membership):
    symbol = row["symbol"].strip()
    member = membership.get(("KR", symbol))
    if member is None:
        raise ValueError(f"universe symbol without PIT membership: {symbol}")
    frame, source = base._load_symbol(row["daily_path"], symbol)
    if frame is None:
        return None, {"status": "no_train_rows"}
    try:
        clean, quality = filter_equity_bars(frame, symbol)
    except SymbolQualityError as exc:
        return None, {"status": "quality_excluded", "detail": str(exc)}
    if len(clean) < MIN_SAMPLE_ROWS:
        return None, {"status": "too_short", "rows": int(len(clean))}
    t, o, h, l, c, v, rep = adjust_corporate_actions(
        np.asarray(clean["open_time"], dtype=np.int64), clean["open"], clean["high"],
        clean["low"], clean["close"], clean["volume"])
    if len(c) < MIN_SAMPLE_ROWS:
        return None, {"status": "too_short_after_adjust", "rows": int(len(c)), "adjust": rep}
    record = {"symbol": symbol, "t": t, "o": o, "h": h, "l": l, "c": c, "v": v,
              "from_day": (member.alive_from - EPOCH).days,
              "through_day": (member.alive_through - EPOCH).days}
    return record, {"status": "valid", "source": str(source), "adjust": rep, **quality}


def _load_index_code(code):
    frame = load_bars(INDEX_PATH, window="train", split_file=SPLIT_PATH, symbol=code,
                      end_ms=EQUITY_COMMON_SPLIT_MS, fixed_split_ms=EQUITY_COMMON_SPLIT_MS)
    if not len(frame):
        raise RuntimeError(f"index {code} TRAIN rows missing; refusing to run")
    return {"t": np.asarray(frame["open_time"], dtype=np.int64),
            "o": np.asarray(frame["open"], dtype=float),
            "c": np.asarray(frame["close"], dtype=float)}


# ------------------------------------------------------------------- panel
class Panel:
    """Wide (symbols x bars) arrays on the union trading grid, plus index arrays."""

    def __init__(self, records, index_series):
        grid = set()
        for rec in records:
            grid.update(rec["t"].tolist())
        for series in index_series.values():
            grid.update(series["t"].tolist())
        self.gt = np.array(sorted(grid), dtype=np.int64)
        self.T = len(self.gt)
        self.days = self.gt // DAY_MS
        self.symbols = [rec["symbol"] for rec in records]
        S = len(records)
        self.S = S
        shape = (S, self.T)
        self.O, self.H, self.L, self.C, self.V = (np.full(shape, np.nan) for _ in range(5))
        self.ALIVE = np.zeros(shape, dtype=bool)
        for s, rec in enumerate(records):
            idx = np.searchsorted(self.gt, rec["t"])
            self.O[s, idx] = rec["o"]
            self.H[s, idx] = rec["h"]
            self.L[s, idx] = rec["l"]
            self.C[s, idx] = rec["c"]
            self.V[s, idx] = rec["v"]
        with np.errstate(invalid="ignore"):
            self.OK = np.isfinite(self.O) & np.isfinite(self.C) & (self.O > 0) & (self.C > 0)
        in_member = (self.days[None, :] >= np.array([r["from_day"] for r in records])[:, None]) & \
                    (self.days[None, :] <= np.array([r["through_day"] for r in records])[:, None])
        self.ALIVE = in_member & self.OK
        self.OKCUM = np.concatenate([np.zeros((S, 1), dtype=np.int64),
                                     np.cumsum(self.OK, axis=1, dtype=np.int64)], axis=1)
        self.PREV = np.full(shape, np.nan)
        self.PREV[:, 1:] = self.C[:, :-1]
        with np.errstate(invalid="ignore", divide="ignore"):
            self.RET = self.C / self.PREV - 1.0
            self.GAP = self.O / self.PREV - 1.0
        self.UPOPEN = self.GAP >= LOCK_MOVE
        self.DNOPEN = self.GAP <= -LOCK_MOVE
        self.VMED = _rolling_median_rows(self.V, 20, shift=1)
        self.VALMED = _rolling_median_rows(self.C * self.V, 20, shift=0)
        self.index = {}
        for code, series in index_series.items():
            arr_o = np.full(self.T, np.nan)
            arr_c = np.full(self.T, np.nan)
            idx = np.searchsorted(self.gt, series["t"])
            arr_o[idx] = series["o"]
            arr_c[idx] = series["c"]
            self.index[code] = {"O": arr_o, "C": arr_c}
        self.years = pd.to_datetime(self.gt, unit="ms").year.to_numpy()
        self._indicator_cache = {}


def _rolling_median_rows(values, window, shift):
    frame = pd.DataFrame(values.T)
    out = frame.rolling(window, min_periods=window).median().to_numpy().T
    if shift:
        out = np.concatenate([np.full((out.shape[0], shift), np.nan), out[:, :-shift]], axis=1)
    return out


def _compact(arr):
    pos = np.flatnonzero(np.isfinite(arr))
    return pos, arr[pos]


def _scatter(pos, vals, T):
    out = np.full(T, np.nan)
    out[pos] = vals
    return out


def index_sma(arr, n, T):
    pos, vals = _compact(arr)
    return _scatter(pos, pd.Series(vals).rolling(n, min_periods=n).mean().to_numpy(), T)


def index_mom(arr, n, T):
    pos, vals = _compact(arr)
    prev = np.full(len(vals), np.nan)
    prev[n:] = vals[:-n] if n > 0 else vals
    return _scatter(pos, vals / prev - 1.0, T)


def indicator(name, P):
    """Causal regime flags on the grid. NaN means unknown and is treated as not-on."""
    if name in P._indicator_cache:
        return P._indicator_cache[name]
    T = P.T
    if name.startswith("KS11_") or name.startswith("KQ11_"):
        code = name.split("_")[0]
        close = P.index[code]["C"]
        if name.endswith("MOM252"):
            known = np.isfinite(index_mom(close, 252, T))
            value = index_mom(close, 252, T) > 0
        else:
            n = int(name.split("SMA")[1])
            sma = index_sma(close, n, T)
            known = np.isfinite(sma)
            value = close > sma
    elif name == "BREADTH200":
        with np.errstate(invalid="ignore"):
            sma = _rolling_mean_rows(P.C, 200)
            eligible = P.ALIVE & np.isfinite(sma)
            above = eligible & (P.C > sma)
            denom = eligible.sum(axis=0)
            breadth = np.divide(above.sum(axis=0), denom, out=np.zeros(T), where=denom > 0)
        known = denom >= 20
        value = known & (breadth >= 0.5)
    else:
        raise ValueError(f"unknown indicator {name}")
    value = np.asarray(value, dtype=bool) & np.asarray(known, dtype=bool)
    known = np.asarray(known, dtype=bool)
    P._indicator_cache[name] = (value, known)
    return value, known


def _rolling_mean_rows(values, window):
    frame = pd.DataFrame(values.T)
    return frame.rolling(window, min_periods=window).mean().to_numpy().T


# ------------------------------------------------------------- unit builders
def position_vec(O, C, e, x, buy, sell):
    """Daily fractional returns for a long held from open of e to open of x (days e..x)."""
    if e < 0 or x <= e or x >= len(O):
        return None
    oe, ox = O[e], O[x]
    if not (np.isfinite(oe) and oe > 0 and np.isfinite(ox) and ox > 0):
        return None
    seg = C[e:x]
    if not np.all(np.isfinite(seg)) or np.any(seg <= 0):
        return None
    vec = np.empty(x - e + 1)
    vec[0] = seg[0] / oe - 1.0 - buy
    if x - e > 1:
        vec[1:x - e] = seg[1:] / seg[:-1] - 1.0
    vec[-1] = ox / seg[-1] - 1.0 - sell
    net = ox / oe - 1.0 - buy - sell
    return vec, net


def event_units(P, s, signal_idx, hold, delay, mult, counts):
    """Single-stock event trades: signal at close t, fill at open t+1+delay, time exit."""
    O, C = P.O[s], P.C[s]
    alive, up_open, dn_open = P.ALIVE[s], P.UPOPEN[s], P.DNOPEN[s]
    T = P.T
    buy, sell = BUY_COST * mult, SELL_COST * mult
    units, busy = [], -1
    for t in signal_idx:
        t = int(t)
        if t <= busy:
            continue
        e = t + 1 + delay
        if e >= T:
            counts["censored"] += 1
            continue
        if not alive[e]:
            counts["entry_not_alive"] += 1
            continue
        if up_open[e]:
            counts["blocked_limit_up_open"] += 1
            continue
        x = e + hold
        if x >= T:
            counts["censored"] += 1
            break
        xx = x
        while xx < T and dn_open[xx] and xx - x < 5:
            xx += 1
        if xx >= T or dn_open[xx]:
            counts["censored"] += 1
            continue
        if xx > x:
            counts["deferred_exit_limit_down"] += 1
        if not alive[xx]:
            counts["delisting_gap"] += 1
            busy = xx - 1
            continue
        res = position_vec(O, C, e, xx, buy, sell)
        if res is None:
            counts["invalid_path"] += 1
            continue
        vec, net = res
        units.append(Unit(e, xx, vec, net, P.symbols[s]))
        busy = xx - 1
    return units


def basket_unit(P, e, x, universe, mult, counts):
    """Equal-weight basket bought at open e and sold at open x; members fixed at entry."""
    T = P.T
    if e < 1 or x >= T or x <= e:
        counts["basket_out_of_range"] += 1
        return None
    buy, sell = BUY_COST * mult, SELL_COST * mult
    valid = (P.OKCUM[:, x + 1] - P.OKCUM[:, e] == x - e + 1) & P.ALIVE[:, e] & P.ALIVE[:, x]
    members = np.flatnonzero(valid)
    if universe == "liquid_half" and members.size:
        value = P.VALMED[members, e - 1]
        keep = np.isfinite(value)
        members, value = members[keep], value[keep]
        if members.size:
            order = np.argsort(-value, kind="stable")
            members = members[order][: math.ceil(members.size / 2)]
    if members.size < MIN_BASKET:
        counts["thin_basket"] += 1
        return None
    vecs, nets = [], []
    for s in members:
        res = position_vec(P.O[s], P.C[s], e, x, buy, sell)
        if res is not None:
            vecs.append(res[0])
            nets.append(res[1])
    if len(vecs) < MIN_BASKET:
        counts["thin_basket"] += 1
        return None
    vec = np.mean(np.stack(vecs), axis=0)
    return Unit(e, x, vec, float(np.mean(nets)), f"BASKET-{e}")


def state_pairs(enter, exit_, delay, T):
    """Flat->long on enter[t], long->flat on exit[t]; fills at t+1+delay."""
    pairs, in_pos, entry_t = [], False, None
    for t in range(T - 1):
        if not in_pos:
            if enter[t]:
                in_pos, entry_t = True, t
        elif exit_[t]:
            pairs.append((entry_t + 1 + delay, t + 1 + delay))
            in_pos = False
    return pairs, in_pos


def calendar(P):
    cal_t = P.index["KS11"]["C"]
    cal_pos = np.flatnonzero(np.isfinite(cal_t))
    dates = (P.gt[cal_pos] // DAY_MS).astype("datetime64[D]")
    return cal_pos, dates


def holiday_eve_flags(dates):
    flags = np.zeros(len(dates), dtype=bool)
    if len(dates) > 1:
        flags[:-1] = np.busday_count(dates[:-1] + np.timedelta64(1, "D"), dates[1:]) > 0
    return flags


def option_expiry_indices(dates):
    """KRX index option expiry = 2nd Thursday, or the prior trading day if it is not a trading day."""
    day_numbers = dates.astype("datetime64[D]").astype(np.int64)
    index_of = {int(d): j for j, d in enumerate(day_numbers)}
    out = []
    months = sorted({int(x) for x in dates.astype("datetime64[M]").astype(np.int64)})
    for month in months:
        first = np.datetime64(month, "M").astype("datetime64[D]").astype(np.int64)
        weekday = int((first + 3) % 7)              # Monday=0; 1970-01-01 was a Thursday
        first_thu = int(first + (3 - weekday) % 7)
        second_thu = first_thu + 7
        if second_thu in index_of:
            out.append(index_of[second_thu])
        else:
            prior = np.flatnonzero(day_numbers < second_thu)
            if prior.size:
                prior_month = np.datetime64(int(day_numbers[prior[-1]]), "D").astype("datetime64[M]")
                if int(prior_month.astype(np.int64)) == month:
                    out.append(int(prior[-1]))
    return out


def calendar_pairs(family, params, dates, cal_pos, delay, T):
    pairs = []
    n = len(dates)
    if family == "PREHOL":
        for jh in np.flatnonzero(holiday_eve_flags(dates)):
            je = jh - (params["k"] - 1)
            jx = jh + params["hold"]
            pairs.append((je, jx))
    elif family == "OPEXP":
        for jE in option_expiry_indices(dates):
            je = jE + params["offset"]
            pairs.append((je, je + params["hold"]))
    elif family == "WKDAY":
        weekday = pd.to_datetime(dates).day_of_week.to_numpy()
        for je in np.flatnonzero(weekday == params["weekday"]):
            pairs.append((je, je + params["hold"]))
    out = []
    for je, jx in pairs:
        je, jx = int(je) + delay, int(jx) + delay
        if je < 0 or jx >= n or jx <= je:
            continue
        e, x = int(cal_pos[je]), int(cal_pos[jx])
        if x < T:
            out.append((e, x))
    return out


def build_units(cfg, delay, mult, P):
    family, p = cfg["family"], cfg["params"]
    counts = Counter()
    units = []
    if family in ("GAPUP", "GAPDN"):
        sig = P.GAP >= p["gap"] if family == "GAPUP" else P.GAP <= -p["gap"]
        sig = sig & P.ALIVE
        if family == "GAPUP" and p["confirm"] == "green":
            sig = sig & (P.C > P.O)
        if p["volume_filter"] is not None:
            sig = sig & (P.V >= p["volume_filter"] * P.VMED)
        for s in range(P.S):
            units += event_units(P, s, np.flatnonzero(sig[s]), p["hold"], delay, mult, counts)
    elif family == "LIMIT":
        if p["direction"] == "up":
            sig = (P.RET >= p["threshold"]) & P.ALIVE
        else:
            sig = (P.RET <= -p["threshold"]) & P.ALIVE
        for s in range(P.S):
            units += event_units(P, s, np.flatnonzero(sig[s]), p["hold"], delay, mult, counts)
    elif family in ("PREHOL", "OPEXP", "WKDAY"):
        cal_pos, dates = calendar(P)
        for e, x in calendar_pairs(family, p, dates, cal_pos, delay, P.T):
            u = basket_unit(P, e, x, "all", mult, counts)
            if u is not None:
                units.append(u)
    elif family == "RGM":
        value, known = indicator(p["indicator"], P)
        hold = value if p["direction"] == "above" else (known & ~value)
        if p["confirm"] > 1:
            hold = pd.Series(hold.astype(int)).rolling(p["confirm"], min_periods=p["confirm"]).min().fillna(0).to_numpy() == 1
        pairs, open_end = state_pairs(hold, ~hold, delay, P.T)
        counts["open_at_end"] = int(open_end)
        for e, x in pairs:
            u = basket_unit(P, e, x, p["universe"], mult, counts)
            if u is not None:
                units.append(u)
    elif family == "ETFTR":
        arr = P.index[p["index"]]
        sma = index_sma(arr["C"], p["sma"], P.T)
        with np.errstate(invalid="ignore"):
            enter = arr["C"] > sma * (1.0 + p["band"])
            exit_ = arr["C"] < sma * (1.0 - p["band"])
        enter = np.where(np.isnan(enter.astype(float)), False, enter).astype(bool)
        exit_ = np.where(np.isnan(exit_.astype(float)), False, exit_).astype(bool)
        pairs, open_end = state_pairs(enter, exit_, delay, P.T)
        counts["open_at_end"] = int(open_end)
        for e, x in pairs:
            res = position_vec(arr["O"], arr["C"], e, x, BUY_COST * mult, SELL_COST * mult)
            if res is None:
                counts["invalid_path"] += 1
                continue
            units.append(Unit(e, x, res[0], res[1], f"INDEX-{p['index']}"))
    else:
        raise ValueError(f"unknown family {family}")
    return units, dict(counts)


# ------------------------------------------------------------ summaries
def portfolio(units, T):
    sums, cnt = np.zeros(T), np.zeros(T)
    for u in units:
        sums[u.e:u.x + 1] += u.vec
        cnt[u.e:u.x + 1] += 1
    return np.divide(sums, cnt, out=np.zeros(T), where=cnt > 0)


def _gate(units, T, n_bonf):
    nets = [u.net for u in units]
    tm = trade_metrics(nets)
    port = portfolio(units, T)
    core = core_gate(tm, port.tolist(), market="KR")
    if np.any(port != 0):
        p_value = float(stats.ttest_1samp(port, 0.0, alternative="greater").pvalue)
        p_value = 1.0 if not math.isfinite(p_value) else p_value
    else:
        p_value = 1.0
    curve = curve_metrics(port.tolist(), ANNUAL_DAYS)
    return {"tm": tm, "port": port, "core": core, "core_pass": all(core.values()),
            "p_one_sided": p_value, "bonferroni_pass": p_value <= ALPHA / n_bonf,
            "curve": curve}


def _metric_row(g):
    tm, curve = g["tm"], g["curve"]
    return {"trades": tm.count, "win_rate_pct": None if tm.win_rate is None else 100 * tm.win_rate,
            "profit_factor": tm.profit_factor, "expectancy_bps": tm.expectancy_bps,
            "wilson_lower_95": tm.wilson_lower_95, "breakeven_win_rate": tm.breakeven_win_rate,
            "cum_return": curve.cumulative_return, "max_drawdown": curve.max_drawdown,
            "sharpe": curve.annualized_sharpe, "p_one_sided": g["p_one_sided"],
            "core": g["core"], "core_pass": g["core_pass"],
            "bonferroni_pass": g["bonferroni_pass"],
            "screen_pass": bool(g["core_pass"] and g["bonferroni_pass"])}


def cluster_p_value(units):
    by_entry = {}
    for u in units:
        by_entry.setdefault(u.e, []).append(u.net)
    means = np.array([np.mean(v) for v in by_entry.values()])
    if means.size < 2:
        return 1.0, int(means.size)
    p = float(stats.ttest_1samp(means, 0.0, alternative="greater").pvalue)
    return (1.0 if not math.isfinite(p) else p), int(means.size)


def yearly_sums(port, years):
    return pd.Series(port).groupby(years).sum()


def bear_years(index_close, years):
    """KOSPI (KS11) TRAIN-window calendar-year return below zero."""
    frame = pd.DataFrame({"y": years, "c": index_close}).dropna()
    if frame.empty:
        return set()
    last = frame.groupby("y")["c"].last()
    prev = last.shift(1)
    ret = last / prev - 1.0
    ret.iloc[0] = last.iloc[0] / frame.groupby("y")["c"].first().iloc[0] - 1.0
    return set(int(y) for y in ret[ret < 0].index)


def evaluate_config(cfg_index, cfg):
    P = STATE
    n_bonf = BONFERRONI_N
    base_units, base_counts = build_units(cfg, 0, 1.0, P)
    base_g = _gate(base_units, P.T, n_bonf)
    row = _metric_row(base_g)
    row["counts"] = base_counts
    row["units"] = len(base_units)
    d1_units, _ = build_units(cfg, 1, 1.0, P)
    d1 = _metric_row(_gate(d1_units, P.T, n_bonf))
    c2_units, _ = build_units(cfg, 0, 2.0, P)
    c2 = _metric_row(_gate(c2_units, P.T, n_bonf))
    cl_p, cl_n = cluster_p_value(base_units)
    ys = yearly_sums(base_g["port"], P.years)
    total = float(ys.sum())
    max_share = float(ys.max() / total) if total > 0 else None
    bears = bear_years(P.index["KS11"]["C"], P.years)
    bear_sum = float(ys[ys.index.isin(list(bears))].sum()) if bears else None
    group_sum = {}
    for u in base_units:
        group_sum[u.group] = group_sum.get(u.group, 0.0) + u.net
    top3 = set(sorted(group_sum, key=lambda g: -group_sum[g])[:3])
    ex_units = [u for u in base_units if u.group not in top3]
    ex_g = _gate(ex_units, P.T, n_bonf)
    checks = {
        "S1_delay1_screen": d1["screen_pass"],
        "S2_cost2x_core": c2["core_pass"],
        "S3_cluster_p": bool(cl_p <= ALPHA / n_bonf and cl_n >= 2),
        "S4a_year_concentration": bool(total > 0 and max_share is not None and max_share <= 0.5),
        "S4b_bear_years_nonnegative": bool(bear_sum is not None and bear_sum >= 0),
        "S5_top3_excluded_core": bool(ex_g["core_pass"]),
    }
    candidate = bool(row["screen_pass"] and all(checks.values()))
    return {"status": "ok", "base": row, "delay1": d1, "cost2x": c2,
            "cluster_p": cl_p, "cluster_n": cl_n, "year_max_share": max_share,
            "bear_years": sorted(bears), "bear_sum": bear_sum,
            "yearly": {str(int(k)): float(v) for k, v in ys.items()},
            "top3_groups": sorted(top3), "top3_excluded": _metric_row(ex_g),
            "checks": checks, "candidate": candidate, "screen_pass": row["screen_pass"]}


def _worker(task):
    index, cfg = task
    try:
        with np.errstate(invalid="ignore", divide="ignore"):
            result = evaluate_config(index, cfg)
    except Exception as exc:
        result = {"status": "failed", "detail": f"{type(exc).__name__}: {exc}",
                  "trace": traceback.format_exc(limit=4)[-900:]}
    return index, result


# ------------------------------------------------------------------ reporting
def _json_default(value):
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.floating):
        return _clean(float(value))
    return value


def ledger_records(configs, results, grid_sha, code_sha, prereg_sha, input_sha):
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for index, (cfg, res) in enumerate(zip(configs, results)):
        cfg_json = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
        cfg_sha = sha256_text(cfg_json)
        metric = _clean({**res, "bonferroni_denominator": BONFERRONI_N,
                         "expected_prior_rows": LEDGER_ROWS_PRIOR,
                         "prereg_sha256": prereg_sha, "code_sha256": code_sha,
                         "grid_sha256": grid_sha, "train_input_sha256": input_sha,
                         "universe": "KR.csv survivors-only proxy; PIT_UNKNOWN",
                         "config_index": index})
        records.append({
            "trial_id": f"{ROUND}-KR-{cfg_sha[:24]}", "round": ROUND, "market_group": "KR",
            "utc_timestamp": now,
            "definition": cfg_json,
            "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
            "train_period": TRAIN_PERIOD,
            "metric": json.dumps(metric, sort_keys=True, separators=(",", ":"), allow_nan=False,
                                 default=_json_default),
            "rank": "",
            "notes": "RB1000-KR TRAIN only; TRAIN_ONLY_NOT_G; survivors-only proxy universe; "
                     "price-limit jump rule applied; no TEST/OOS access; failed rows kept",
        })
    return records


def results_frame(configs, results):
    rows = []
    for index, (cfg, res) in enumerate(zip(configs, results)):
        row = {"config_index": index, "family": cfg["family"],
               "params": json.dumps(cfg["params"], sort_keys=True, separators=(",", ":")),
               "status": res.get("status")}
        if res.get("status") == "ok":
            base_row = res["base"]
            row.update({k: v for k, v in base_row.items() if k not in ("core",)})
            row["delay1_screen_pass"] = res["delay1"]["screen_pass"]
            row["cost2x_core_pass"] = res["cost2x"]["core_pass"]
            row["cluster_p"] = res["cluster_p"]
            row["year_max_share"] = res["year_max_share"]
            row["bear_sum"] = res["bear_sum"]
            row["top3_excluded_core_pass"] = res["top3_excluded"]["core_pass"]
            row["candidate"] = res["candidate"]
            row["counts"] = json.dumps(base_row.get("counts", {}), sort_keys=True)
        else:
            row["detail"] = res.get("detail")
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------- main path
def main():
    global STATE, BONFERRONI_N, LEDGER_ROWS_PRIOR
    configs = build_configs()
    grid_sha = grid_sha256(configs)
    code_sha = code_sha256()
    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    verify_prereg(grid_sha, code_sha)
    # Common-rule denominator: ledger rows measured immediately before this run, plus 429, plus 1000.
    rows_before = base.ledger_rows()
    LEDGER_ROWS_PRIOR = rows_before
    BONFERRONI_N = rows_before + EXPLORE500_ROWS + OTHER_LANES_CAP
    universe_rows = list(csv.DictReader(base.UNIVERSE_PATH.open(newline="", encoding="utf-8-sig")))
    membership = load_membership(base.MEMBERSHIP_PATH)
    records, accounting = [], {}
    for row in universe_rows:
        rec, info = _load_stock(row, membership)
        accounting[row["symbol"].strip()] = info
        if rec is not None:
            records.append(rec)
    index_series = {code: _load_index_code(code) for code in ("KS11", "KQ11", "KS200")}
    P = Panel(records, index_series)
    if int(P.gt.max()) > EQUITY_COMMON_SPLIT_MS:
        raise RuntimeError("post-split data reached the loader; aborting")
    STATE = P
    quality = summarize_quality(accounting, records)
    digest = hashlib.sha256()
    for rec in records:
        digest.update(rec["symbol"].encode() + rec["t"].tobytes() + rec["c"].tobytes())
    input_sha = digest.hexdigest()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (RUNS_DIR / f"rb1000_kr_jump_quality_{stamp}.json").write_text(
        json.dumps({"quality": quality, "train_input_sha256": input_sha}, indent=2,
                   default=_json_default, ensure_ascii=False), encoding="utf-8")
    ctx = mp.get_context("fork")
    tasks = list(enumerate(configs))
    with ctx.Pool(processes=os.cpu_count()) as pool:
        collected = dict(pool.map(_worker, tasks, chunksize=2))
    results = [collected[i] for i in range(len(configs))]
    frame = results_frame(configs, results)
    out_csv = RUNS_DIR / f"rb1000_kr_train_{stamp}.csv"
    frame.to_csv(out_csv, index=False)
    records_out = ledger_records(configs, results, grid_sha, code_sha, prereg_sha, input_sha)
    base.append_ledger(records_out, rows_before)
    print(json.dumps({"results_csv": str(out_csv), "ledger_rows_after": base.ledger_rows(),
                      "failed": sum(r["status"] != "ok" for r in results),
                      "screen_pass": sum(bool(r.get("screen_pass")) for r in results),
                      "candidates": sum(bool(r.get("candidate")) for r in results)},
                     default=_json_default))
    return 0


def summarize_quality(accounting, records):
    statuses = Counter(v["status"] for v in accounting.values())
    adj = [v["adjust"] for v in accounting.values() if "adjust" in v]
    split_ratio_counts = Counter()
    for a in adj:
        split_ratio_counts.update(a.get("split_ratios", {}))
    vol_meds = [a["volume_ratio_split_median"] for a in adj if a.get("volume_ratio_split_median")]
    return {
        "universe_rows": len(accounting), "statuses": dict(statuses),
        "stocks_loaded": len(records),
        "stocks_with_any_limit_jump": sum(1 for a in adj if a["jumps"] > 0),
        "jumps_total": sum(a["jumps"] for a in adj),
        "split_adjusted_total": sum(a["split_adjusted"] for a in adj),
        "split_ratio_counts": dict(split_ratio_counts),
        "stocks_truncated": sum(1 for a in adj if a["truncated"]),
        "rows_dropped_by_truncation": sum(a["rows_dropped"] for a in adj),
        "residual_jumps_after_rule": sum(a["residual_jumps"] for a in adj),
        "volume_ratio_split_median_of_medians": float(np.median(vol_meds)) if vol_meds else None,
    }


if __name__ == "__main__":
    sys.exit(main())
