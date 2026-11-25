"""RB1000-COINA: TRAIN-only pre-registered derivatives/microstructure batch (lane COINA, 300 configs).

Reuses search_crypto_rb500 for the shared pieces: Panel, load_panels (TRAIN cutoff via
data_access.iter_train_bars), FUNDING_POLICY, _funding_window, _one_sided_p, _sanitize,
_ledger_rows, append_ledger_locked. Trade execution reuses crypto.simulate_trade with
next-bar-open entry. Derivative inputs (Binance UM open interest, top-trader and global
long/short ratios, 1m premium index, 1m taker volume) are read from the external cache and
cut at the TRAIN cutoff before any feature is built. No test-period row is read.
"""
from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import search_crypto_rb500 as rb5

HERE = Path(__file__).resolve().parent
LANE = "COINA"
ROUND = "RB1000-COINA"
PREREG_PATH = HERE / f"PREREG_RB1000_{LANE}.md"
MASTER_PATH = HERE / "PREREG.md"
N_CONFIGS = 300
EXPLORE_ADD = 429          # EXPLORE500 screened configs not in TRAIN_TRIALS.csv (conservative add)
LANE_PARALLEL_ADD = 1000   # all four lanes together, conservative (prereg section 2)
FEE_BPS = rb5.FEE_BPS      # 4 bp per side
SLIP_BPS = rb5.SLIP_BPS    # 2 bp per side (6 bp per side total)
WARMUP_BARS = rb5.WARMUP_BARS
Z_WINDOW = 120
TRAIN_CUTOFF = "2023-11-06 16:00:00"
TRAIN_CUTOFF_MS = int(pd.Timestamp(TRAIN_CUTOFF, tz="UTC").timestamp() * 1000)
DAY_MS = rb5.DAY_MS
EXTERNAL = "external/crypto/binance"
EXPECT_MIN_BPS = 15.0
PF_MIN = 1.30
YEAR_MIN_TRADES = 20
BEAR_YEAR = 2022
TOP_EXCLUDE = 3

FAMILY_SPECS = (
    ("D1_FUNDING_CONTRARIAN_EXTREME",
     {"timeframe": ["1h", "4h"], "funding_threshold": [0.0003, 0.0005, 0.0008],
      "trigger": ["event", "state"], "smoothing": ["last", "mean3"],
      "reward_r": [1.0, 2.0], "horizon_bars": [24, 48]},
     {"stop_atr": 2.0}, 96),
    ("D2_CROWD_LS_RATIO_FADE",
     {"timeframe": ["1h", "4h"],
      "ratio_source": ["global_account", "toptrader_account", "toptrader_position"],
      "z_threshold": [1.5, 2.0, 2.5, 3.0], "reward_r": [1.0, 2.0]},
     {"stop_atr": 2.0, "horizon_bars": 24}, 48),
    ("D3_OI_PRICE_BUILDUP",
     {"timeframe": ["1h", "4h"], "oi_window_bars": [6, 12, 24],
      "oi_z_threshold": [1.0, 1.5, 2.0], "mode": ["continuation", "fade"]},
     {"stop_atr": 2.0, "horizon_bars": 24, "reward_r": 2.0}, 36),
    ("D4_PREMIUM_BASIS_Z",
     {"timeframe": ["1h", "4h"], "premium_window_bars": [1, 3, 6],
      "z_threshold": [1.5, 2.0, 2.5], "mode": ["fade", "follow"]},
     {"stop_atr": 2.0, "horizon_bars": 24, "reward_r": 2.0}, 36),
    ("D5_TAKER_FLOW_IMBALANCE",
     {"timeframe": ["1h", "4h"], "imbalance_window_bars": [3, 6, 12],
      "z_threshold": [1.0, 1.5, 2.0], "mode": ["follow", "fade"]},
     {"stop_atr": 2.0, "horizon_bars": 24, "reward_r": 2.0}, 36),
    ("D6_OI_FLUSH_REBOUND_LIQ_PROXY",
     {"timeframe": ["1h", "4h"], "oi_drop_window_bars": [1, 3, 6],
      "oi_drop_threshold": [0.02, 0.04, 0.06], "reward_r": [1.0, 2.0]},
     {"stop_atr": 2.0, "horizon_bars": 24, "shock_atr": 1.5}, 36),
    ("D7_COMPRESSION_OI_BREAKOUT",
     {"timeframe": ["1h", "4h"], "compression_percentile": [10, 20, 30],
      "reward_r": [1.5, 2.0]},
     {"stop_atr": 2.0, "horizon_bars": 24, "breakout_lookback_bars": 20, "oi_window_bars": 12}, 12),
)

RATIO_COLUMNS = {
    "global_account": ("ls_g_z", "count_long_short_ratio"),
    "toptrader_account": ("ls_ta_z", "count_toptrader_long_short_ratio"),
    "toptrader_position": ("ls_tp_z", "sum_toptrader_long_short_ratio"),
}


def build_grid() -> list[dict]:
    """Deterministic exact grid: family order, itertools.product over values as listed."""
    grid: list[dict] = []
    for family, variable, fixed, quota in FAMILY_SPECS:
        keys = list(variable)
        combos = list(itertools.product(*(variable[k] for k in keys)))
        if len(combos) != quota:
            raise ValueError(f"{family}: grid size {len(combos)} != quota {quota}")
        for values in combos:
            grid.append({"family": family, **fixed, **dict(zip(keys, values))})
    if len(grid) != N_CONFIGS:
        raise ValueError("grid must have exactly 300 configs")
    for n, config in enumerate(grid):
        config["config_id"] = f"COINA-{n:03d}"
    return grid


GRID: list[dict] = build_grid()


# ---------- feature helpers (every value at bar i uses only data known at bar i close) ----------

def _prior_z(x, window=Z_WINDOW):
    """z-score of x[i] against the window [i-W, i-1] (current bar excluded)."""
    s = pd.Series(np.asarray(x, dtype=float))
    prior = s.shift(1)
    mu = prior.rolling(window, min_periods=window).mean()
    sd = prior.rolling(window, min_periods=window).std(ddof=0)
    z = (s - mu) / sd
    return z.where(sd > 0).to_numpy()


def _last_known(close_t, obs_t, obs_v):
    """Value of the last observation strictly before each bar close (no look-ahead)."""
    out = np.full(len(close_t), np.nan)
    if len(obs_t) == 0:
        return out
    j = np.searchsorted(obs_t, close_t, side="left") - 1
    ok = j >= 0
    out[ok] = obs_v[j[ok]]
    return out


def _dedupe_keep_last(t, v):
    order = np.argsort(t, kind="stable")
    t, v = t[order], v[order]
    if len(t) == 0:
        return t, v
    keep = np.append(t[1:] != t[:-1], True)
    return t[keep], v[keep]


def _bin_index(bar_open, tf_ms, t):
    """Bar index containing each minute timestamp t (bar i = [T_i, T_i + tf))."""
    n = len(bar_open)
    idx = np.searchsorted(bar_open, t, side="right") - 1
    idx_c = np.clip(idx, 0, n - 1)
    valid = (idx >= 0) & (t < bar_open[idx_c] + tf_ms)
    return idx_c, valid


def _shift_arr(x, k):
    return pd.Series(np.asarray(x, dtype=float)).shift(k).to_numpy()


def build_features(panel, raw: dict) -> dict:
    """Per-bar derivative features for one symbol/timeframe. raw holds numpy arrays
    (times in epoch ms) already cut at the TRAIN cutoff."""
    n = len(panel.C)
    T = panel.T
    close_t = T + panel.tf_ms
    feats: dict[str, np.ndarray] = {}
    if n == 0:
        return feats

    # funding: events strictly before the bar close are known at that close
    keys = np.asarray(panel.keys, dtype=np.int64)
    rates = np.array([panel.funding[k].rate for k in panel.keys], dtype=float)
    count = np.searchsorted(keys, close_t, side="left")
    prev = np.concatenate(([0], count[:-1]))
    feats["f_new"] = count > prev
    f_last = np.full(n, np.nan)
    ok = count > 0
    f_last[ok] = rates[count[ok] - 1]
    feats["f_last"] = f_last
    r3 = pd.Series(rates).rolling(3, min_periods=3).mean().to_numpy() if len(rates) else rates
    f_m3 = np.full(n, np.nan)
    ok3 = count >= 3
    f_m3[ok3] = r3[count[ok3] - 1]
    feats["f_mean3"] = f_m3

    # long/short ratios (5-minute snapshots), last snapshot before the bar close
    for name, (zname, column) in RATIO_COLUMNS.items():
        t, v = _dedupe_keep_last(raw[f"{column}_t"], raw[f"{column}_v"])
        known = _last_known(close_t, t, v)
        with np.errstate(divide="ignore", invalid="ignore"):
            lr = np.where(known > 0, np.log(known), np.nan)
        feats[zname] = _prior_z(lr)

    # open interest
    t, v = _dedupe_keep_last(raw["oi_t"], raw["oi_v"])
    oi = _last_known(close_t, t, v)
    oi = np.where(oi > 0, oi, np.nan)  # non-positive OI is invalid data -> missing
    feats["oi"] = oi
    with np.errstate(divide="ignore", invalid="ignore"):
        log_oi = np.where(oi > 0, np.log(oi), np.nan)
    for w in (6, 12, 24):
        feats[f"oi_z_{w}"] = _prior_z(log_oi - _shift_arr(log_oi, w))

    # premium index: mean of 1m closes inside each bar
    idx, valid = _bin_index(T, panel.tf_ms, raw["prem_t"])
    sums = np.bincount(idx[valid], weights=raw["prem_v"][valid], minlength=n)
    cnts = np.bincount(idx[valid], minlength=n)
    pm = np.where(cnts > 0, sums / np.maximum(cnts, 1), np.nan)
    for w in (1, 3, 6):
        feats[f"prem_z_{w}"] = _prior_z(pd.Series(pm).rolling(w, min_periods=w).mean().to_numpy())

    # taker imbalance from 1m taker-buy volume
    idx, valid = _bin_index(T, panel.tf_ms, raw["kl_t"])
    vol = np.bincount(idx[valid], weights=raw["kl_v"][valid], minlength=n)
    tb = np.bincount(idx[valid], weights=raw["kl_tb"][valid], minlength=n)
    for w in (3, 6, 12):
        vw = pd.Series(vol).rolling(w, min_periods=w).sum().to_numpy()
        tw = pd.Series(tb).rolling(w, min_periods=w).sum().to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            imb = np.where(vw > 0, 2 * tw / vw - 1, np.nan)
        feats[f"imb_z_{w}"] = _prior_z(imb)

    # volatility compression: ATR/close at or below its own trailing 200-bar quantile (prior bar)
    rv = panel.atr / panel.C
    for p in (10, 20, 30):
        q = pd.Series(rv).rolling(200, min_periods=200).quantile(p / 100).to_numpy()
        comp = np.where(np.isfinite(q), rv <= q, False)
        feats[f"comp_{p}"] = np.concatenate(([False], comp[:-1]))
    return feats


def attach_features(panels: dict, raw_loader) -> None:
    """Load each symbol's raw minute data once (one symbol in memory at a time)."""
    symbols = sorted(set(panels["1h"]) | set(panels["4h"]))
    for symbol in symbols:
        raw = raw_loader(symbol)
        for tf in ("1h", "4h"):
            if symbol in panels[tf]:
                panel = panels[tf][symbol]
                panel.feat = build_features(panel, raw)


# ---------- raw external readers (cut at TRAIN cutoff before any array is built) ----------

def _months(directory: Path):
    return [p for p in sorted(directory.glob("????-??.parquet")) if p.stem <= "2023-11"]


def _read_columns(directory: Path, columns, filters):
    import pyarrow.parquet as pq
    frames = [pq.read_table(p, columns=columns, filters=filters).to_pandas()
              for p in _months(directory)]
    if not frames:
        return pd.DataFrame(columns=columns)
    return pd.concat(frames, ignore_index=True)


def _create_time_ms(series: pd.Series) -> np.ndarray:
    dt = pd.to_datetime(series, utc=True)
    return np.asarray((dt - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(1, "ms"),
                      dtype=np.int64)


def load_raw(symbol: str, base: Path) -> dict:
    ext = base / EXTERNAL
    raw: dict[str, np.ndarray] = {}
    metric_cols = ["create_time", "sum_open_interest", "count_long_short_ratio",
                   "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio"]
    m = _read_columns(ext / "um_metrics" / symbol, metric_cols,
                      [("create_time", "<", TRAIN_CUTOFF)])
    mt = _create_time_ms(m["create_time"]) if len(m) else np.zeros(0, dtype=np.int64)
    raw["oi_t"], raw["oi_v"] = mt, m["sum_open_interest"].to_numpy(float) if len(m) else np.zeros(0)
    for column in ("count_long_short_ratio", "count_toptrader_long_short_ratio",
                   "sum_toptrader_long_short_ratio"):
        raw[f"{column}_t"] = mt
        raw[f"{column}_v"] = m[column].to_numpy(float) if len(m) else np.zeros(0)
    p = _read_columns(ext / "um_premiumIndexKlines_1m" / symbol, ["open_time", "close"],
                      [("open_time", "<", TRAIN_CUTOFF_MS)])
    raw["prem_t"] = p["open_time"].to_numpy(np.int64) if len(p) else np.zeros(0, np.int64)
    raw["prem_v"] = p["close"].to_numpy(float) if len(p) else np.zeros(0)
    k = _read_columns(ext / "um_klines_1m" / symbol, ["open_time", "volume", "taker_buy_volume"],
                      [("open_time", "<", TRAIN_CUTOFF_MS)])
    raw["kl_t"] = k["open_time"].to_numpy(np.int64) if len(k) else np.zeros(0, np.int64)
    raw["kl_v"] = k["volume"].to_numpy(float) if len(k) else np.zeros(0)
    raw["kl_tb"] = k["taker_buy_volume"].to_numpy(float) if len(k) else np.zeros(0)
    return raw


def _data_root() -> Path:
    return Path(os.environ.get("TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()


# ---------- signals: return int8 array, +1 long, -1 short, 0 none; index i = decision at bar i close ----------

def _empty(n):
    return np.zeros(n, dtype=np.int8)


def sig_d1(p, c):
    f = p.feat
    rate = f["f_last"] if c["smoothing"] == "last" else f["f_mean3"]
    short = rate >= c["funding_threshold"]     # crowded longs pay funding -> fade (short)
    long_ = rate <= -c["funding_threshold"]    # crowded shorts pay funding -> fade (long)
    if c["trigger"] == "event":
        short &= f["f_new"]
        long_ &= f["f_new"]
    out = _empty(len(p.C))
    out[short] = -1
    out[long_] = 1
    return out


def sig_d2(p, c):
    zname, _ = RATIO_COLUMNS[c["ratio_source"]]
    z = p.feat[zname]
    out = _empty(len(p.C))
    out[z >= c["z_threshold"]] = -1
    out[z <= -c["z_threshold"]] = 1
    return out


def sig_d3(p, c):
    w = c["oi_window_bars"]
    z = p.feat[f"oi_z_{w}"]
    ret = p.C / _shift_arr(p.C, w) - 1
    build = z >= c["oi_z_threshold"]
    up, dn = build & (ret > 0), build & (ret < 0)
    out = _empty(len(p.C))
    if c["mode"] == "continuation":
        out[up] = 1
        out[dn] = -1
    else:
        out[up] = -1
        out[dn] = 1
    return out


def sig_d4(p, c):
    z = p.feat[f"prem_z_{c['premium_window_bars']}"]
    out = _empty(len(p.C))
    hi, lo = z >= c["z_threshold"], z <= -c["z_threshold"]
    if c["mode"] == "fade":
        out[hi] = -1
        out[lo] = 1
    else:
        out[hi] = 1
        out[lo] = -1
    return out


def sig_d5(p, c):
    z = p.feat[f"imb_z_{c['imbalance_window_bars']}"]
    out = _empty(len(p.C))
    hi, lo = z >= c["z_threshold"], z <= -c["z_threshold"]
    if c["mode"] == "follow":
        out[hi] = 1
        out[lo] = -1
    else:
        out[hi] = -1
        out[lo] = 1
    return out


def sig_d6(p, c):
    w = c["oi_drop_window_bars"]
    oi = p.feat["oi"]
    oi_ret = oi / _shift_arr(oi, w) - 1
    drop = _shift_arr(p.C, w) - p.C
    cond = (oi_ret <= -c["oi_drop_threshold"]) & (drop >= c["shock_atr"] * p.atr)
    out = _empty(len(p.C))
    out[cond] = 1   # liquidation-flush proxy: long rebound only
    return out


def sig_d7(p, c):
    comp = p.feat[f"comp_{c['compression_percentile']}"]
    oi = p.feat["oi"]
    oi_up = (oi / _shift_arr(oi, c["oi_window_bars"]) - 1) > 0
    hi = rb5._prior_max(p.H, c["breakout_lookback_bars"])
    lo = rb5._prior_min(p.L, c["breakout_lookback_bars"])
    out = _empty(len(p.C))
    out[comp & oi_up & (p.C > hi)] = 1
    out[comp & oi_up & (p.C < lo)] = -1
    return out


SIGNALS = {
    "D1_FUNDING_CONTRARIAN_EXTREME": sig_d1,
    "D2_CROWD_LS_RATIO_FADE": sig_d2,
    "D3_OI_PRICE_BUILDUP": sig_d3,
    "D4_PREMIUM_BASIS_Z": sig_d4,
    "D5_TAKER_FLOW_IMBALANCE": sig_d5,
    "D6_OI_FLUSH_REBOUND_LIQ_PROXY": sig_d6,
    "D7_COMPRESSION_OI_BREAKOUT": sig_d7,
}


# ---------- execution: next-bar-open entry, non-overlapping per symbol ----------

def simulate_variant(panel, dirs, config, fee_bps, slip_bps, delay_bars, want_daily):
    """Trades for one symbol. delay_bars shifts every signal later by that many bars."""
    from crypto import Setup, Zone, simulate_trade, trade_daily_pnl
    n = len(panel.C)
    horizon, reward, stop_atr = config["horizon_bars"], config["reward_r"], config["stop_atr"]
    if delay_bars:
        dirs = np.concatenate((np.zeros(delay_bars, dtype=np.int8), dirs[:-delay_bars]))
    trades: list[dict] = []
    stats = {"censored_no_exit": 0, "unscorable_funding": 0,
             "reconcile_error": 0, "skipped_overlap": 0}
    last_exit = -1
    for i in np.flatnonzero(dirs):
        if i < WARMUP_BARS or i + 1 >= n:
            continue
        if i < last_exit:
            stats["skipped_overlap"] += 1
            continue
        a = panel.atr[i]
        if not math.isfinite(a) or a <= 0:
            continue
        direction = "long" if dirs[i] > 0 else "short"
        entry_i = int(i) + 1
        entry = panel.O[entry_i]
        risk = stop_atr * a
        if direction == "long":
            stop, target = entry - risk, entry + reward * risk
        else:
            stop, target = entry + risk, entry - reward * risk
        zone = Zone(int(i), int(i), direction, min(entry, stop), max(entry, stop), a)
        setup = Setup(zone, entry_i, entry, stop, target)
        hi = panel.T[min(entry_i + horizon, n - 1)] + 2 * panel.tf_ms
        sub = rb5._funding_window(panel, panel.T[entry_i] - panel.tf_ms, hi)
        trade = simulate_trade(panel.bars, setup, funding=sub, max_holding_bars=horizon,
                               fee_bps_per_side=fee_bps, slippage_bps_per_side=slip_bps,
                               bar_duration_ms=panel.tf_ms, validated=True,
                               funding_order_policy=rb5.FUNDING_POLICY)
        if trade is None:
            stats["censored_no_exit"] += 1
            continue
        last_exit = trade.exit_index
        if trade.net_return is None:
            stats["unscorable_funding"] += 1
            continue
        daily = None
        if want_daily:
            try:
                daily = trade_daily_pnl(panel.bars, trade, funding=sub, bar_duration_ms=panel.tf_ms)
            except ValueError:
                stats["reconcile_error"] += 1
                continue
            if daily is None:
                stats["unscorable_funding"] += 1
                continue
        trades.append({"symbol": panel.symbol, "net": trade.net_return,
                       "reason": trade.exit_reason, "entry_ts": int(panel.T[entry_i]),
                       "daily": daily})
    return trades, stats


def run_variant(config, panels, fee_bps, slip_bps, delay_bars, want_daily):
    panels_tf = panels[config["timeframe"]]
    trades: list[dict] = []
    totals = {"censored_no_exit": 0, "unscorable_funding": 0,
              "reconcile_error": 0, "skipped_overlap": 0}
    for symbol, panel in panels_tf.items():
        if len(panel.C) == 0:  # symbol with no TRAIN bars: nothing to trade
            continue
        dirs = SIGNALS[config["family"]](panel, config)
        rows, stats = simulate_variant(panel, dirs, config, fee_bps, slip_bps,
                                       delay_bars, want_daily)
        trades.extend(rows)
        for key in totals:
            totals[key] += stats[key]
    return trades, totals


# ---------- statistics and gates ----------

def _pass_ec_pf(tm) -> bool:
    return (tm is not None and tm.count > 0 and tm.expectancy_bps is not None
            and tm.expectancy_bps >= EXPECT_MIN_BPS
            and tm.profit_factor is not None and tm.profit_factor >= PF_MIN)


def _cluster_p(trades):
    by_day: dict[int, list[float]] = {}
    for t in trades:
        by_day.setdefault(t["entry_ts"] // DAY_MS, []).append(t["net"])
    values = [sum(v) / len(v) for v in by_day.values()]
    return rb5._one_sided_p(values), len(values)


def _yearly(trades):
    by_year: dict[int, list[float]] = {}
    for t in trades:
        year = datetime.fromtimestamp(t["entry_ts"] / 1000, tz=timezone.utc).year
        by_year.setdefault(year, []).append(t["net"])
    table = {}
    for year, nets in sorted(by_year.items()):
        table[str(year)] = {"trades": len(nets),
                            "expectancy_bps": sum(nets) / len(nets) * 1e4,
                            "qualifies": len(nets) >= YEAR_MIN_TRADES}
    qual = [v for v in table.values() if v["qualifies"]]
    if not qual:
        return table, False, "no year with >=20 trades"
    positive = sum(1 for v in qual if v["expectancy_bps"] > 0)
    frac_ok = positive / len(qual) >= 2 / 3
    bear = table.get(str(BEAR_YEAR))
    bear_ok = bear is None or not bear["qualifies"] or bear["expectancy_bps"] >= 0
    passed = frac_ok and bear_ok
    reason = f"positive years {positive}/{len(qual)}; bear({BEAR_YEAR}) ok={bear_ok}"
    return table, passed, reason


def _top_exclusion(trades):
    totals: dict[str, float] = {}
    for t in trades:
        totals[t["symbol"]] = totals.get(t["symbol"], 0.0) + t["net"]
    top = sorted(totals, key=lambda s: (-totals[s], s))[:TOP_EXCLUDE]
    rest = [t["net"] for t in trades if t["symbol"] not in top]
    return top, rest


def _one_sided(values):
    return rb5._one_sided_p(values)


def _stats_dict(tm):
    return {"trades": tm.count, "expectancy_bps": tm.expectancy_bps,
            "profit_factor": tm.profit_factor, "win_rate": tm.win_rate}


def score_config(config, panels, all_days, n_symbols, bonferroni_n):
    from metrics import core_gate, curve_metrics, trade_metrics, wilson_lower
    base_trades, base_stats = run_variant(config, panels, FEE_BPS, SLIP_BPS, 0, True)
    result = {"config_id": config["config_id"], "family": config["family"],
              "timeframe": config["timeframe"], "trades": len(base_trades), **base_stats}
    if not base_trades:
        result.update({"status": "no_trades", "candidate": False,
                       "fail_reasons": ["no_trades"]})
        return result
    nets = [t["net"] for t in base_trades]
    day_pnl: dict[int, float] = {}
    for t in base_trades:
        for day, value in t["daily"].items():
            day_pnl[day] = day_pnl.get(day, 0.0) + value
    daily_list = [day_pnl.get(day, 0.0) / n_symbols for day in all_days]
    tm = trade_metrics(nets)
    core = core_gate(tm, daily_list, market="crypto")
    cm = curve_metrics(daily_list, 365)
    p1 = _one_sided(nets)
    bonf_threshold = 0.05 / bonferroni_n
    bonf_pass = p1 is not None and p1 < bonf_threshold
    core_pass = all(core.values())

    delay_trades, _ = run_variant(config, panels, FEE_BPS, SLIP_BPS, 1, False)
    cost_trades, _ = run_variant(config, panels, 2 * FEE_BPS, 2 * SLIP_BPS, 0, False)
    tm_delay = trade_metrics([t["net"] for t in delay_trades]) if delay_trades else None
    tm_cost = trade_metrics([t["net"] for t in cost_trades]) if cost_trades else None
    delay_pass = _pass_ec_pf(tm_delay)
    cost_pass = _pass_ec_pf(tm_cost)

    cluster_p, n_clusters = _cluster_p(base_trades)
    cluster_pass = cluster_p is not None and cluster_p < bonf_threshold
    yearly_table, yearly_pass, yearly_reason = _yearly(base_trades)
    top, rest = _top_exclusion(base_trades)
    tm_top = trade_metrics(rest) if rest else None
    top_pass = _pass_ec_pf(tm_top)

    supp = {"delay_1bar": {**_stats_dict(tm_delay), "pass": delay_pass} if tm_delay else {"pass": False},
            "cost_2x": {**_stats_dict(tm_cost), "pass": cost_pass} if tm_cost else {"pass": False},
            "cluster_p": {"p": cluster_p, "clusters": n_clusters, "pass": cluster_pass},
            "yearly": {"years": yearly_table, "pass": yearly_pass, "reason": yearly_reason},
            "top3_excluded": {"symbols": top, **(_stats_dict(tm_top) if tm_top else {}),
                              "pass": top_pass}}
    fail = []
    if not core_pass:
        fail.append("core_gate:" + ",".join(k for k, v in core.items() if not v))
    if not bonf_pass:
        fail.append("bonferroni_trade_p")
    for name, ok in (("delay_1bar", delay_pass), ("cost_2x", cost_pass),
                     ("cluster_p", cluster_pass), ("yearly", yearly_pass), ("top3", top_pass)):
        if not ok:
            fail.append(name)
    candidate = not fail
    result.update({
        "status": "scored", "win_rate": tm.win_rate, "wilson_95_lower": tm.wilson_lower_95,
        "breakeven_win_rate": tm.breakeven_win_rate, "profit_factor": tm.profit_factor,
        "expectancy_bps": tm.expectancy_bps, "cumulative_return": cm.cumulative_return,
        "max_drawdown": cm.max_drawdown, "sharpe": cm.annualized_sharpe,
        "m2_target_rate": sum(1 for t in base_trades if t["reason"] == "target") / len(base_trades),
        "m2_wilson_lower": wilson_lower(sum(1 for t in base_trades if t["reason"] == "target"),
                                        len(base_trades)),
        "one_sided_p": p1, "bonferroni_threshold": bonf_threshold,
        "core_gate": {k: bool(v) for k, v in core.items()}, "passes_core": core_pass,
        "passes_bonferroni": bonf_pass, "supplementary": supp,
        "fail_reasons": fail, "candidate": candidate,
    })
    return result


# ---------- run harness: process pool, locked ledger append ----------

_WORKER: dict = {}
CODE_FILES = ("search_crypto_rb1000_coina.py", "search_crypto_rb500.py", "crypto.py",
              "data_access.py", "metrics.py", "search_crypto.py", "search_crypto_r14.py",
              "search_crypto_r19_match_attrition_audit.py",
              "search_crypto_r33_delayed_sweep_bos.py", "resource_guard.py",
              PREREG_PATH.name, MASTER_PATH.name, "universe/CRYPTO_35.csv")


def _init_worker():
    panels, all_days, n_symbols, _fp = rb5.load_panels()
    base = _data_root()
    attach_features(panels, lambda symbol: load_raw(symbol, base))
    _WORKER.update(panels=panels, all_days=all_days, n_symbols=n_symbols)


def _run_one(args):
    config, bonferroni_n = args
    try:
        return score_config(config, _WORKER["panels"], _WORKER["all_days"],
                            _WORKER["n_symbols"], bonferroni_n)
    except Exception as exc:  # failures are kept as ledger rows, never dropped
        return {"config_id": config["config_id"], "family": config["family"],
                "status": "failed", "failure_type": type(exc).__name__,
                "detail": str(exc)[:300], "candidate": False}


def _code_sha():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _ledger_record(result, grid_sha, code_sha, fingerprint, bonferroni_n, prereg_sha, master_sha):
    config = next(c for c in GRID if c["config_id"] == result["config_id"])
    metric = rb5._sanitize({**result, "bonferroni_denominator": bonferroni_n,
                            "train_input_fingerprint": fingerprint,
                            "prereg_sha256": prereg_sha, "master_prereg_sha256": master_sha,
                            "label_note": "TRAIN_ONLY_NOT_G; survivors-only universe; "
                                          "EXPLORATORY_LEAD_EXPLORE500 funding-contrarian lineage"})
    return {
        "trial_id": f"RB1000-COINA-{config['config_id']}-{uuid.uuid4().hex[:12]}",
        "round": ROUND, "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(rb5._sanitize(config), sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": f"1h/4h bar close <={TRAIN_CUTOFF} UTC",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":"), allow_nan=False),
        "rank": "",
        "notes": f"RB1000 COINA TRAIN-only config {config['config_id']}; not OOS or G approval",
    }


def run(commit: bool, configs=None, workers: int = 10):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    import search_crypto as common
    import search_crypto_r19_match_attrition_audit as r19
    import search_crypto_r33_delayed_sweep_bos as r33
    data_root = _data_root()
    configs = GRID if configs is None else configs
    locks = []
    if commit:
        r19._assert_no_ledger_writer()
        locks = r33._acquire_locks(data_root)
    try:
        rows = rb5._ledger_rows(common.CSV_PATH)
        bonf_n = rows + EXPLORE_ADD + LANE_PARALLEL_ADD
        grid_sha = rb5.grid_sha256(configs)
        code_sha = _code_sha()
        prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
        master_sha = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
        _, all_days, n_symbols, fingerprint = rb5.load_panels()
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx,
                                 initializer=_init_worker) as pool:
            results = list(pool.map(_run_one, [(c, bonf_n) for c in configs], chunksize=2))
        out_dir = data_root / "cache/orderblock/runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_csv = out_dir / f"RB1000_COINA_{stamp}.csv"
        fields = sorted({k for r in results for k in r})
        with out_csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow({k: (json.dumps(rb5._sanitize(v)) if isinstance(v, (dict, list)) else v)
                                 for k, v in r.items()})
        summary = {"rows_before": rows, "bonferroni_n": bonf_n, "grid_sha256": grid_sha,
                   "code_sha256_before": code_sha, "fingerprint": fingerprint,
                   "n_symbols": n_symbols, "n_days": len(all_days),
                   "results_csv": str(out_csv), "committed": False}
        if commit:
            records = [_ledger_record(r, grid_sha, code_sha, fingerprint, bonf_n,
                                      prereg_sha, master_sha) for r in results]
            summary["ledger_rows_appended"] = rb5.append_ledger_locked(records, rows, common.CSV_PATH)
            summary["committed"] = True
        summary["code_sha256_after"] = _code_sha()
        return summary, results
    finally:
        if locks:
            r33._release_locks(locks)


if __name__ == "__main__":
    commit = "--commit-ledger" in sys.argv
    summary, results = run(commit=commit)
    print(json.dumps(rb5._sanitize(summary), sort_keys=True), flush=True)
