"""R14-KR-BATCH: one-time, preregistered 500-configuration KR daily TRAIN screen.

Data access stops at the common KR train split (2018-10-26 23:59 UTC). Every
configuration is scored on the same survivors-only proxy universe, with
next-bar-open fills, the preregistered KR round-trip cost (31 bp), and the
point-in-time membership gate. All results are TRAIN_ONLY_NOT_G.
"""
from __future__ import annotations

import csv
import fcntl
import hashlib
import io
import itertools
import json
import math
import multiprocessing as mp
import os
import sys
import traceback
from collections import namedtuple
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import search_crypto as ledger_common
from data_access import EQUITY_COMMON_SPLIT_MS, load_bars
from data_quality import SymbolQualityError, filter_equity_bars
from equities import preregistered_costs
from metrics import core_gate, curve_metrics, trade_metrics
from search_equities_r5 import load_membership

HERE = Path(__file__).resolve().parent
ROUND = "RB500-KR"
PREREG_PATH = HERE / "PREREG_RB500_KR.md"
REPORT_PATH = HERE / "REPORT_RB500_KR.md"
UNIVERSE_PATH = HERE / "universe" / "KR.csv"
TRADING_DATA = Path(os.environ.get(
    "TRADING_DATA_DIR", "/Users/user/CODE/Coin_Trade/trading_data")).expanduser()
CACHE_DIR = TRADING_DATA / "cache" / "orderblock"
RUNS_DIR = CACHE_DIR / "runs"
MEMBERSHIP_PATH = CACHE_DIR / "equity_membership_kr.csv"
SPLIT_PATH = CACHE_DIR / "equity_splits_r14_kr_batch.json"
KR_DIR = TRADING_DATA / "external" / "equities" / "kr"
INDEX_PATH = KR_DIR / "daily_indices.parquet"
INDEX_CODE = "KS11"
TRAIN_PERIOD = "<=2018-10-26T23:59:00Z (KR common split)"
N_NEW = 500
EXPECTED_LEDGER_ROWS = 2689  # measured 2026-11-25 before this run: 1689 + RB500-COIN 500 + US batch 500
BONFERRONI_N = EXPECTED_LEDGER_ROWS + N_NEW
ALPHA = 0.05
CORPORATE_ACTION_MOVE = 0.35  # KRX daily limit is +-30%; larger moves = unadjusted split/bad print
ANNUAL_DAYS = 252
DAY_MS = 86_400_000
EPOCH = date(1970, 1, 1)
COSTS = preregistered_costs("KR")
BUY_COST = (COSTS.commission_bps_per_side + COSTS.slippage_bps_per_side) / 10_000
SELL_COST = (COSTS.commission_bps_per_side + COSTS.slippage_bps_per_side
             + COSTS.sell_tax_bps) / 10_000
ROUND_TRIP_COST = BUY_COST + SELL_COST
CODE_FILES = ("search_kr_r14_batch.py", "data_access.py", "data_quality.py", "equities.py",
              "metrics.py", "search_equities_r5.py", "search_equities_r3.py", "resource_guard.py",
              "search_crypto.py")
XS_FAMILIES = frozenset({"XMOM", "XLOWVOL", "X52WH"})

# Priority order = literature/novelty order (see PREREG_R14_BATCH_KR.md). Axes are
# full cartesian products; the total must be exactly N_NEW.
FAMILIES = (
    ("XMOM", {"lookback": (63, 126, 252), "skip": (0, 21), "top_k": (5, 10, 20, 40),
              "rebalance": (21, 63)}),
    ("XLOWVOL", {"vol_window": (20, 40, 60, 120), "top_k": (5, 10, 20, 40),
                 "rebalance": (21, 63)}),
    ("X52WH", {"window": (126, 252, 504), "top_k": (5, 10, 20, 40), "rebalance": (21, 63)}),
    ("TOM", {"days_remaining": (1, 2, 3, 4), "exit_day": (1, 2, 3),
             "regime_sma": (None, 120, 200)}),
    ("REV", {"lookback": (3, 5, 10), "drop_pct": (5, 10, 15, 20), "trend_sma": (None, 200),
             "hold": (3, 5, 10), "stop_atr": (None, 2)}),
    ("VOLSURGE", {"mult": (2, 3, 4), "up_day": (True, False), "hold": (1, 2, 3, 5, 10),
                  "stop_atr": (None, 2)}),
    ("MATREND", {"sma_n": (20, 60, 120), "regime_sma": (None, 60, 120, 200),
                 "exit_sma": (10, 20), "stop_atr": (None, 3)}),
    ("VBRK", {"k": (0.2, 0.3, 0.5, 0.7, 1.0), "trend_sma": (None, 20), "hold": (1, 3, 5),
              "stop_atr": (None, 2)}),
    ("DONCH", {"breakout": (20, 55, 120), "trail_atr": (1.5, 2, 3, 4),
               "regime_sma": (None, 200), "max_hold": (None, 60)}),
)

Trade = namedtuple("Trade", "e x entry_px exit_px reason net")


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
    """Fail closed unless the frozen prereg records these exact grid and code hashes."""
    text = PREREG_PATH.read_text(encoding="utf-8")
    for label, value in (("grid_sha256", grid_sha), ("code_sha256", code_sha)):
        marker = f"- {label}: `{value}`"
        if marker not in text:
            raise RuntimeError(f"PREREG does not record {label}={value}; refusing to run")


# ------------------------------------------------------------------ ledger I/O
def ledger_rows(path=None):
    path = Path(path or ledger_common.CSV_PATH)
    old_limit = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.reader(stream)
            header = next(reader)
            if tuple(header) != tuple(ledger_common.FIELDS):
                raise ValueError("TRAIN_TRIALS.csv schema mismatch")
            return sum(1 for _ in reader)
    finally:
        csv.field_size_limit(old_limit)


def append_ledger(records, expected_rows, path=None):
    """Append rows under an exclusive flock; refuse if the ledger changed since preregistration."""
    path = Path(path or ledger_common.CSV_PATH)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(ledger_common.FIELDS))
    for record in records:
        writer.writerow(record)
    payload = buffer.getvalue().encode("utf-8")
    csv.field_size_limit(max(csv.field_size_limit(), sys.maxsize))
    with path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            raw = handle.read()
            text = raw.decode("utf-8")
            rows = sum(1 for _ in csv.reader(io.StringIO(text))) - 1
            if rows != expected_rows:
                raise RuntimeError(f"ledger has {rows} rows, expected {expected_rows}; nothing appended")
            if raw and not raw.endswith(b"\n"):
                payload = b"\n" + payload
            handle.seek(0, os.SEEK_END)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# ---------------------------------------------------------------- data loading
@dataclass
class SymbolBars:
    symbol: str
    source: str
    t: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    gidx: np.ndarray
    alive: np.ndarray
    bar_at_global: np.ndarray

    @property
    def n(self):
        return len(self.c)


@dataclass
class BatchState:
    symbols: list
    universe_n: int
    gt: np.ndarray
    index_close: np.ndarray
    index_sma: dict
    close_panel: pd.DataFrame
    high_panel: pd.DataFrame
    alive_panel: pd.DataFrame
    gyear: np.ndarray
    accounting: dict
    input_sha256: str


STATE = None


def _load_symbol(daily_path, symbol):
    # universe CSV carries a stale /Users/user/CODE/trading_data prefix; remap by file name
    primary = KR_DIR / Path(daily_path).name
    alternate_name = ("daily_stocks_current.parquet"
                      if primary.name == "daily_stocks_delisted.parquet"
                      else "daily_stocks_delisted.parquet")
    for path in (primary, KR_DIR / alternate_name):
        frame = load_bars(path, window="train", split_file=SPLIT_PATH, symbol=symbol,
                          end_ms=EQUITY_COMMON_SPLIT_MS, fixed_split_ms=EQUITY_COMMON_SPLIT_MS)
        if len(frame):
            return frame, path
    return None, None


def _load_index():
    return load_bars(INDEX_PATH, window="train", split_file=SPLIT_PATH, symbol=INDEX_CODE,
                     end_ms=EQUITY_COMMON_SPLIT_MS, fixed_split_ms=EQUITY_COMMON_SPLIT_MS)


def prepare_state(universe_rows, membership):
    accounting, loaded = {}, []
    for row in universe_rows:
        symbol = row["symbol"].strip()
        member = membership.get(("KR", symbol))
        if member is None:
            raise ValueError(f"universe symbol without PIT membership: {symbol}")
        frame, source = _load_symbol(row["daily_path"], symbol)
        if frame is None:
            accounting[symbol] = {"status": "no_train_rows"}
            continue
        try:
            clean, quality = filter_equity_bars(frame, symbol)
        except SymbolQualityError as exc:
            accounting[symbol] = {"status": "quality_excluded", "detail": str(exc)}
            continue
        if len(clean) < 30:
            accounting[symbol] = {"status": "too_short", "rows": len(clean)}
            continue
        largest_move = float(np.max(np.abs(np.diff(clean["close"].astype(float))
                                           / clean["close"].astype(float).values[:-1])))
        if largest_move > CORPORATE_ACTION_MOVE:
            accounting[symbol] = {"status": "excluded_unadjusted_jump",
                                  "largest_abs_daily_move": largest_move}
            continue
        accounting[symbol] = {"status": "valid", "source": str(source), **quality}
        loaded.append((symbol, source, clean, member))

    index_frame = _load_index()
    if not len(index_frame):
        raise RuntimeError("KOSPI index TRAIN rows missing; refusing to run without regime data")
    times = [np.asarray(clean["open_time"], dtype=np.int64) for _, _, clean, _ in loaded]
    gt = np.unique(np.concatenate(times + [np.asarray(index_frame["open_time"], dtype=np.int64)]))
    if int(gt.max()) > EQUITY_COMMON_SPLIT_MS:
        raise RuntimeError("post-split data reached the loader; aborting")

    n_global, n_symbols = len(gt), len(loaded)
    close_panel = np.full((n_global, n_symbols), np.nan)
    high_panel = np.full((n_global, n_symbols), np.nan)
    alive_panel = np.zeros((n_global, n_symbols), dtype=bool)
    gday = gt // DAY_MS
    symbols, digest = [], hashlib.sha256()
    for j, (symbol, source, clean, member) in enumerate(loaded):
        t = np.asarray(clean["open_time"], dtype=np.int64)
        gidx = np.searchsorted(gt, t)
        bar_at_global = np.full(n_global, -1, dtype=np.int64)
        bar_at_global[gidx] = np.arange(len(t))
        day = t // DAY_MS
        from_day = (member.alive_from - EPOCH).days
        through_day = (member.alive_through - EPOCH).days
        alive = (day >= from_day) & (day <= through_day)
        arrays = {k: np.asarray(clean[k], dtype=float) for k in ("open", "high", "low", "close")}
        volume = np.asarray(clean["volume"], dtype=float)
        close_panel[gidx, j] = arrays["close"]
        high_panel[gidx, j] = arrays["high"]
        alive_panel[:, j] = (gday >= from_day) & (gday <= through_day)
        digest.update(f"{symbol}|{len(t)}|".encode() + t.tobytes() + arrays["close"].tobytes())
        symbols.append(SymbolBars(symbol, str(source), t, arrays["open"], arrays["high"],
                                  arrays["low"], arrays["close"], volume, gidx, alive,
                                  bar_at_global))

    index_t = np.asarray(index_frame["open_time"], dtype=np.int64)
    index_close = np.full(n_global, np.nan)
    index_close[np.searchsorted(gt, index_t)] = np.asarray(index_frame["close"], dtype=float)
    digest.update(index_close.tobytes())
    index_sma = {w: pd.Series(index_close).rolling(w, min_periods=w).mean().to_numpy()
                 for w in (60, 120, 200)}
    columns = [s.symbol for s in symbols]
    years = pd.DatetimeIndex(pd.to_datetime(gt, unit="ms")).year.to_numpy()
    return BatchState(
        symbols=symbols, universe_n=len(universe_rows), gt=gt, index_close=index_close,
        index_sma=index_sma,
        close_panel=pd.DataFrame(close_panel, columns=columns),
        high_panel=pd.DataFrame(high_panel, columns=columns),
        alive_panel=pd.DataFrame(alive_panel, columns=columns),
        gyear=years, accounting=accounting, input_sha256=digest.hexdigest())


# ------------------------------------------------------------- causal features
def _shift(x, k):
    out = np.full(len(x), np.nan)
    out[k:] = x[:len(x) - k]
    return out


def _rolling(x, n, how):
    return getattr(pd.Series(x).rolling(n, min_periods=n), how)().to_numpy(dtype=float)


def _atr14(s):
    prev_c = _shift(s.c, 1)
    true_range = np.maximum(np.maximum(s.h - s.l, np.abs(s.h - prev_c)), np.abs(s.l - prev_c))
    return _rolling(true_range, 14, "mean")


def _regime(s, st, window):
    if window is None:
        return np.ones(s.n, dtype=bool)
    return st.index_close[s.gidx] > st.index_sma[window][s.gidx]


def _spec(entry, hold=None, exit_sig=None):
    return {"entry": np.asarray(entry, dtype=bool), "hold": hold, "exit_sig": exit_sig,
            "atr": None, "stop_atr": None, "trail_atr": None}


def _with_stops(spec, s, stop_atr=None, trail_atr=None):
    if stop_atr is not None or trail_atr is not None:
        spec["atr"] = _atr14(s)
    spec["stop_atr"], spec["trail_atr"] = stop_atr, trail_atr
    return spec


def _b_rev(p, s, st):
    ret = s.c / _shift(s.c, p["lookback"]) - 1.0
    cond = ret <= -p["drop_pct"] / 100.0
    if p["trend_sma"] is not None:
        cond &= s.c > _rolling(s.c, p["trend_sma"], "mean")
    return _with_stops(_spec(cond, hold=p["hold"]), s, p["stop_atr"])


def _b_volsurge(p, s, st):
    median_volume = _rolling(_shift(s.v, 1), 60, "median")
    cond = s.v >= p["mult"] * median_volume
    if p["up_day"]:
        cond &= s.c > _shift(s.c, 1)
    return _with_stops(_spec(cond, hold=p["hold"]), s, p["stop_atr"])


def _b_vbrk(p, s, st):
    trigger = s.h >= s.o + p["k"] * (_shift(s.h, 1) - _shift(s.l, 1))
    if p["trend_sma"] is not None:
        trigger &= s.c > _rolling(s.c, p["trend_sma"], "mean")
    return _with_stops(_spec(trigger, hold=p["hold"]), s, p["stop_atr"])


def _b_matrend(p, s, st):
    sma = _rolling(s.c, p["sma_n"], "mean")
    cross_up = (s.c > sma) & (_shift(s.c, 1) <= _shift(sma, 1))
    cond = cross_up & _regime(s, st, p["regime_sma"])
    exit_sig = s.c < _rolling(s.c, p["exit_sma"], "mean")
    return _with_stops(_spec(cond, exit_sig=exit_sig), s, p["stop_atr"])


def _b_donch(p, s, st):
    prior_high = _rolling(_shift(s.h, 1), p["breakout"], "max")
    cond = (s.c > prior_high) & _regime(s, st, p["regime_sma"])
    return _with_stops(_spec(cond, hold=p["max_hold"]), s, None, p["trail_atr"])


def _b_tom(p, s, st):
    dt = pd.to_datetime(s.t, unit="ms")
    ym = np.asarray(dt.year * 100 + dt.month)
    series = pd.Series(ym)
    rank = series.groupby(ym).cumcount().to_numpy() + 1
    size = series.groupby(ym).transform("size").to_numpy()
    entry = ((size - rank) == p["days_remaining"]) & _regime(s, st, p["regime_sma"])
    month_change_next = np.zeros(s.n, dtype=bool)
    month_change_next[:-1] = ym[1:] != ym[:-1]
    rank_next = np.zeros(s.n, dtype=np.int64)
    rank_next[:-1] = rank[1:]
    exit_sig = month_change_next & (rank_next == p["exit_day"])
    return _spec(entry, exit_sig=exit_sig)


TIME_SERIES_BUILDERS = {"REV": _b_rev, "VOLSURGE": _b_volsurge, "VBRK": _b_vbrk,
                        "MATREND": _b_matrend, "DONCH": _b_donch, "TOM": _b_tom}


def cross_sectional_specs(cfg, st):
    """Monthly-style rebalance: rank alive symbols on the rebalance day, enter next open."""
    p, family = cfg["params"], cfg["family"]
    rebalance, top_k = p["rebalance"], p["top_k"]
    if family == "XMOM":
        score = st.close_panel.shift(p["skip"]) / st.close_panel.shift(p["lookback"]) - 1.0
        warm = p["lookback"] + 1
    elif family == "XLOWVOL":
        ret = st.close_panel / st.close_panel.shift(1) - 1.0
        score = -ret.rolling(p["vol_window"], min_periods=p["vol_window"]).std()
        warm = p["vol_window"] + 1
    else:
        score = st.close_panel / st.high_panel.rolling(p["window"], min_periods=p["window"]).max()
        warm = p["window"]
    values = score.where(st.alive_panel).to_numpy()
    picks = {}
    for g in range(warm, values.shape[0], rebalance):
        row = values[g]
        ok = np.flatnonzero(np.isfinite(row))
        if ok.size == 0:
            continue
        chosen = ok[np.argsort(-row[ok], kind="stable")][:top_k]
        for j in chosen:
            picks.setdefault(int(j), []).append(g)
    specs = {}
    for j, days in picks.items():
        s = st.symbols[j]
        positions = s.bar_at_global[np.asarray(days)]
        entry = np.zeros(s.n, dtype=bool)
        entry[positions[positions >= 0]] = True
        specs[j] = _spec(entry, hold=rebalance)
    return specs


# ------------------------------------------------------------------ simulation
def _exit_candidates(s, spec, sidx, e, entry_px, a, end):
    last_bar = []
    o, h, l = s.o, s.h, s.l
    stop_atr, trail_atr = spec["stop_atr"], spec["trail_atr"]
    if stop_atr is not None:
        level = entry_px - stop_atr * a
        hits = np.flatnonzero(l[e:end + 1] <= level)
        if hits.size:
            j = e + int(hits[0])
            last_bar.append((j, 0, min(o[j], level), "stop"))
    if trail_atr is not None and end > e:
        running_high = np.maximum.accumulate(h[e:end])
        trail = running_high - trail_atr * spec["atr"][e:end]
        hits = np.flatnonzero(l[e + 1:end + 1] <= trail)
        if hits.size:
            k = int(hits[0])
            j = e + 1 + k
            last_bar.append((j, 0, min(o[j], trail[k]), "trail"))
    if spec["exit_sig"] is not None:
        hits = np.flatnonzero(spec["exit_sig"][e:end])
        if hits.size:
            k = e + int(hits[0])
            last_bar.append((k + 1, 1, o[k + 1], "signal"))
    if spec["hold"] is not None and e + spec["hold"] <= s.n - 1:
        tx = e + spec["hold"]
        last_bar.append((tx, 2, o[tx], "time"))
    return last_bar


def simulate(s, spec):
    """Next-open entries, stop-first intrabar ordering, one position per symbol."""
    n, last = s.n, s.n - 1
    trades, censored, gaps, busy = [], 0, 0, -1
    needs_atr = spec["stop_atr"] is not None or spec["trail_atr"] is not None
    for sidx in np.flatnonzero(spec["entry"]):
        sidx = int(sidx)
        if sidx <= busy or sidx >= last or not s.alive[sidx]:
            continue
        e = sidx + 1
        entry_px = s.o[e]
        if not (np.isfinite(entry_px) and entry_px > 0):
            continue
        a = spec["atr"][sidx] if needs_atr else np.nan
        if needs_atr and not np.isfinite(a):
            continue
        end = min(last, e + spec["hold"]) if spec["hold"] is not None else last
        candidates = _exit_candidates(s, spec, sidx, e, entry_px, a, end)
        if not candidates:
            censored += 1
            break
        x, _, exit_px, reason = min(candidates, key=lambda item: (item[0], item[1]))
        busy = x - 1
        if not s.alive[x]:
            gaps += 1
            continue
        trades.append(Trade(e, x, entry_px, exit_px, reason,
                            exit_px / entry_px - 1.0 - ROUND_TRIP_COST))
    return trades, censored, gaps


def trade_daily_pnl(s, tr):
    """Per-sleeve daily P&L, scaled by entry notional, with buy and sell costs placed on the fill days."""
    c, e, x = s.c, tr.e, tr.x
    if x == e:
        vec = np.array([(tr.exit_px - tr.entry_px) / tr.entry_px])
    else:
        vec = np.empty(x - e + 1)
        vec[0] = (c[e] - tr.entry_px) / tr.entry_px
        vec[1:-1] = (c[e + 1:x] - c[e:x - 1]) / tr.entry_px
        vec[-1] = (tr.exit_px - c[x - 1]) / tr.entry_px
    vec[0] -= BUY_COST
    vec[-1] -= SELL_COST
    return vec


def build_spec(cfg, s, st):
    builder = TIME_SERIES_BUILDERS[cfg["family"]]
    return builder(cfg["params"], s, st)


def evaluate(cfg, st):
    specs = cross_sectional_specs(cfg, st) if cfg["family"] in XS_FAMILIES else None
    nets, port = [], np.zeros(len(st.gt))
    censored = gaps = traded_symbols = 0
    for j, s in enumerate(st.symbols):
        if specs is not None:
            spec = specs.get(j)
        else:
            spec = build_spec(cfg, s, st)
        if spec is None or not spec["entry"].any():
            continue
        trades, cens, gap = simulate(s, spec)
        censored += cens
        gaps += gap
        if trades:
            traded_symbols += 1
        for tr in trades:
            nets.append(tr.net)
            port[s.gidx[tr.e:tr.x + 1]] += trade_daily_pnl(s, tr) / st.universe_n
    return summarize_config(nets, port, censored, gaps, traded_symbols, st)


def summarize_config(nets, port, censored, gaps, traded_symbols, st):
    tm = trade_metrics(nets)
    curve = curve_metrics(port.tolist(), ANNUAL_DAYS)
    core = core_gate(tm, port.tolist(), market="KR")
    if np.any(port != 0):
        p_value = float(stats.ttest_1samp(port, 0.0, alternative="greater").pvalue)
        p_value = 1.0 if not math.isfinite(p_value) else p_value
    else:
        p_value = 1.0
    by_year = pd.Series(port).groupby(st.gyear).sum()
    positive_total = float(by_year.sum())
    top_share = float(by_year.max() / positive_total) if positive_total > 0 else None
    bonferroni_pass = p_value <= ALPHA / BONFERRONI_N
    return {
        "status": "ok", "trades": tm.count, "censored": censored, "delisting_gap": gaps,
        "symbols_traded": traded_symbols, "win_rate_pct": _pct(tm.win_rate),
        "profit_factor": tm.profit_factor, "expectancy_bps": tm.expectancy_bps,
        "wilson_lower_95": tm.wilson_lower_95, "breakeven_win_rate": tm.breakeven_win_rate,
        "average_win": tm.average_win, "average_loss": tm.average_loss,
        "cum_return": curve.cumulative_return, "max_drawdown": curve.max_drawdown,
        "sharpe": curve.annualized_sharpe, "p_one_sided": p_value,
        "core": core, "core_pass": all(core.values()), "bonferroni_pass": bonferroni_pass,
        "screen_pass": bool(all(core.values()) and bonferroni_pass),
        "top_year_share": top_share, "m2": "해당 없음 (KR)",
    }


def _pct(value):
    return None if value is None else 100.0 * value


def _worker(task):
    index, cfg = task
    try:
        with np.errstate(invalid="ignore", divide="ignore"):
            result = evaluate(cfg, STATE)
    except Exception as exc:  # recorded as a failed trial row, never dropped
        result = {"status": "failed", "detail": f"{type(exc).__name__}: {exc}",
                  "trace": traceback.format_exc(limit=3)[-800:]}
    return index, result


# ------------------------------------------------------------------- reporting
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
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.floating,)):
        return _clean(float(value))
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def ledger_records(configs, results, grid_sha, code_sha, prereg_sha, input_sha):
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for index, (cfg, res) in enumerate(zip(configs, results)):
        cfg_sha = sha256_text(json.dumps(cfg, sort_keys=True, separators=(",", ":")))
        metric = _clean({**res, "bonferroni_denominator": BONFERRONI_N,
                         "expected_prior_rows": EXPECTED_LEDGER_ROWS,
                         "prereg_sha256": prereg_sha, "code_sha256": code_sha,
                         "grid_sha256": grid_sha, "train_input_sha256": input_sha,
                         "universe": "KR.csv survivors-only proxy; PIT_UNKNOWN",
                         "config_index": index})
        records.append({
            "trial_id": f"{ROUND}-KR-{cfg_sha[:24]}", "round": ROUND, "market_group": "KR",
            "utc_timestamp": now,
            "definition": json.dumps(cfg, sort_keys=True, separators=(",", ":")),
            "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
            "train_period": TRAIN_PERIOD,
            "metric": json.dumps(metric, sort_keys=True, separators=(",", ":"), allow_nan=False,
                                 default=_json_default),
            "rank": "",
            "notes": "RB500-KR TRAIN only; TRAIN_ONLY_NOT_G; survivors-only proxy universe; "
                     "no TEST/OOS access; failed rows kept",
        })
    return records


def results_frame(configs, results):
    rows = []
    for index, (cfg, res) in enumerate(zip(configs, results)):
        row = {"config_index": index, "family": cfg["family"],
               "params": json.dumps(cfg["params"], sort_keys=True, separators=(",", ":"))}
        row.update({k: v for k, v in res.items() if k not in ("core", "trace")})
        row["core_json"] = json.dumps(res.get("core", {}), sort_keys=True, default=_json_default)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    global STATE
    configs = build_configs()
    grid_sha = grid_sha256(configs)
    code_sha = code_sha256()
    prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
    verify_prereg(grid_sha, code_sha)
    rows_before = ledger_rows()
    if rows_before != EXPECTED_LEDGER_ROWS:
        raise RuntimeError(f"ledger has {rows_before} rows; PREREG expects {EXPECTED_LEDGER_ROWS}")
    universe_rows = list(csv.DictReader(UNIVERSE_PATH.open(newline="", encoding="utf-8-sig")))
    membership = load_membership(MEMBERSHIP_PATH)
    STATE = prepare_state(universe_rows, membership)
    ctx = mp.get_context("fork")
    tasks = list(enumerate(configs))
    with ctx.Pool(processes=os.cpu_count()) as pool:
        collected = dict(pool.map(_worker, tasks, chunksize=2))
    results = [collected[i] for i in range(len(configs))]
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    frame = results_frame(configs, results)
    out_csv = RUNS_DIR / f"rb500_kr_train_{stamp}.csv"
    frame.to_csv(out_csv, index=False)
    records = ledger_records(configs, results, grid_sha, code_sha, prereg_sha,
                             STATE.input_sha256)
    append_ledger(records, EXPECTED_LEDGER_ROWS)
    print(json.dumps({"results_csv": str(out_csv), "ledger_rows_after": ledger_rows(),
                      "failed": sum(r["status"] != "ok" for r in results),
                      "screen_pass": sum(bool(r.get("screen_pass")) for r in results)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
