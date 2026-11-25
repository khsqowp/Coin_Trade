"""RB1000-COINB: TRAIN-only lane of 300 preregistered cross-asset / calendar / factor coin configs.

Reuses the RB500 harness (search_crypto_rb500): Panel, indicator helpers, _funding_window,
_one_sided_p, load_panels (TRAIN cutoff 2023-11-06T16:00Z), locked ledger append, and
crypto.simulate_trade / trade_daily_pnl (next-bar-open fill, stop/target/time exit, funding).
Order-block families are not in this lane. No test-period data is read.
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

import search_crypto_rb500 as rb

HERE = Path(__file__).resolve().parent
ROUND = "RB1000-COINB"
PREREG_PATH = HERE / "PREREG_RB1000_COINB.md"
MASTER_PATH = HERE / "PREREG.md"
N_CONFIGS = 300
PRIOR_EXPLORE_ROWS = 429          # EXPLORE500 screen additions (not in ledger)
LANE_TOTAL_CONFIGS = 1000         # conservative all-lane denominator term
WARMUP_BARS = rb.WARMUP_BARS
FEE_BPS, SLIP_BPS = 4.0, 2.0       # base: 6bp per side, 12bp round trip
COST2_FEE_BPS, COST2_SLIP_BPS = 8.0, 4.0   # cost x2: 12bp per side, 24bp round trip
FUNDING_POLICY = "adverse_only"
TF_MS = {"1h": 3_600_000, "4h": 14_400_000}
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
BARS_PER_DAY_4H = 6
REWARD_NONE = 50.0                 # effectively no target; exit by stop or time only
MIN_TRADES_PER_YEAR = 20
MIN_TRADES_CORE = 100              # rb.core_gate("crypto") sample rule (code value; stricter than 60)
TRAIN_CUTOFF = rb.TRAIN_CUTOFF

# (family, variable params in product order, fixed params, quota). Priority order.
FAMILY_SPECS = (
    ("C1_CS_SHORT_REVERSAL_LS",
     {"lookback_days": [1, 2, 3, 5, 7], "top_k": [2, 3, 5], "horizon_bars": [24, 48],
      "stop_atr": [2.0, 3.0]},
     {"timeframe": "4h", "reward_r": REWARD_NONE, "side": "reversal"}, 60),
    ("C2_CS_MOMENTUM_LS",
     {"lookback_days": [7, 14, 30, 60, 90], "top_k": [2, 3, 5], "horizon_bars": [24, 48],
      "stop_atr": [2.0, 3.0]},
     {"timeframe": "4h", "reward_r": REWARD_NONE, "side": "momentum"}, 60),
    ("C3_CS_LOWVOL_LS",
     {"vol_days": [7, 14, 30, 60, 90], "top_k": [2, 4], "horizon_bars": [24, 48],
      "stop_atr": [2.0, 3.0]},
     {"timeframe": "4h", "reward_r": REWARD_NONE, "side": "lowvol"}, 40),
    ("C4_BTC_ETH_SPREAD_REVERSION",
     {"window_bars": [30, 60, 120, 240], "entry_z": [2.0, 2.5, 3.0, 3.5],
      "horizon_bars": [24, 48]},
     {"timeframe": "4h", "stop_atr": 3.0, "reward_r": REWARD_NONE}, 32),
    ("C5_BTC_SHOCK_ALT_LAG_FOLLOW",
     {"lag_bars": [1, 3, 6, 12, 24], "shock_z": [2.0, 2.5, 3.0], "horizon_bars": [24, 48]},
     {"timeframe": "1h", "stop_atr": 2.0, "reward_r": 1.5}, 30),
    ("C6_VOLUME_REGIME_TREND_CROSS",
     {"fast_bars": [6, 12, 24, 48, 96], "slow_bars": [120, 240], "ratio_thr": [1.3, 1.6, 2.0]},
     {"timeframe": "4h", "stop_atr": 2.0, "reward_r": 2.0, "horizon_bars": 24, "trend_bars": 24}, 30),
    ("C7_VOL_REGIME_TREND_OR_FADE",
     {"fast_bars": [6, 12], "slow_bars": [84, 168], "rv_ratio_thr": [1.3, 1.6, 2.0],
      "mode": ["trend", "fade"]},
     {"timeframe": "4h", "stop_atr": 2.0, "reward_r": 2.0, "horizon_bars": 24}, 24),
    ("C8_SETTLEMENT_PRE_WINDOW",
     {"offset_hours": [1, 2, 3, 4], "direction": ["long", "short"],
      "settle_hour_utc": [0, 8, 16]},
     {"timeframe": "1h", "stop_atr": 2.0, "reward_r": REWARD_NONE, "horizon_bars": 24}, 24),
)


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
        config["config_id"] = f"CB-{n:03d}"
    return grid


def grid_sha256(grid: list[dict]) -> str:
    raw = json.dumps(grid, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


# ---------- cross-sectional / pair / lead-lag signal construction ----------

def _grid_matrix(panels_tf):
    """Aligned log-close matrix (time x symbol) on the union of bar timestamps; NaN = no bar."""
    syms = sorted(panels_tf)
    grid = np.unique(np.concatenate([panels_tf[s].T for s in syms]))
    logc = np.full((len(grid), len(syms)), np.nan)
    for j, s in enumerate(syms):
        p = panels_tf[s]
        logc[np.searchsorted(grid, p.T), j] = np.log(p.C)
    return grid, syms, logc


def _to_symbol_dirs(panels_tf, grid, syms, mat):
    out = {}
    for j, s in enumerate(syms):
        rows = np.searchsorted(grid, panels_tf[s].T)
        out[s] = mat[rows, j].astype(np.int8)
    return out


def _cs_dirs(panels_tf, c):
    """Dollar-neutral cross-sectional long/short. Rebalance every horizon+1 bars so that
    each position's time exit lands exactly on the next rebalance open (no overlap skip)."""
    grid, syms, logc = _grid_matrix(panels_tf)
    df = pd.DataFrame(logc)
    if c["side"] in ("reversal", "momentum"):
        lb = c["lookback_days"] * BARS_PER_DAY_4H
        score = (df - df.shift(lb)).to_numpy()
    else:  # lowvol: realized vol of 1-bar log returns over vol_days
        w = c["vol_days"] * BARS_PER_DAY_4H
        score = df.diff().rolling(w, min_periods=w).std(ddof=0).to_numpy()
    k = c["top_k"]
    reb = c["horizon_bars"] + 1
    long_is_top = c["side"] == "momentum"
    mat = np.zeros(logc.shape, dtype=np.int8)
    for t in range(1, len(grid)):
        if t % reb:
            continue
        row = score[t]
        ok = np.flatnonzero(np.isfinite(row))
        if len(ok) < 2 * k:
            continue
        order = ok[np.argsort(row[ok], kind="stable")]
        low, high = order[:k], order[-k:]
        if long_is_top:
            mat[t, high] = 1
            mat[t, low] = -1
        else:
            mat[t, low] = 1
            mat[t, high] = -1
    return _to_symbol_dirs(panels_tf, grid, syms, mat)


def _pair_dirs(panels_tf, c):
    """ETH/BTC log-spread z-score (prior window). z >= e: short ETH, long BTC; z <= -e: reverse."""
    grid, syms, logc = _grid_matrix(panels_tf)
    e_i, b_i = syms.index("ETHUSDT"), syms.index("BTCUSDT")
    spread = pd.Series(logc[:, e_i] - logc[:, b_i])
    w = c["window_bars"]
    prior = spread.shift(1)
    mu = prior.rolling(w, min_periods=w).mean()
    sd = prior.rolling(w, min_periods=w).std(ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.nan_to_num(((spread - mu) / sd).to_numpy(), nan=0.0, posinf=0.0, neginf=0.0)
    thr = c["entry_z"]
    mat = np.zeros(logc.shape, dtype=np.int8)
    hi, lo = z >= thr, z <= -thr
    mat[hi, e_i], mat[hi, b_i] = -1, 1
    mat[lo, e_i], mat[lo, b_i] = 1, -1
    return _to_symbol_dirs(panels_tf, grid, syms, mat)


def _leadlag_dirs(panels_1h, c):
    """BTC shock (lag-L log return z-score >= threshold) -> follow shock direction in alts that
    have moved less than BTC over the same L bars in that direction."""
    grid, syms, logc = _grid_matrix(panels_1h)
    b_i = syms.index("BTCUSDT")
    L = c["lag_bars"]
    df = pd.DataFrame(logc)
    lr = (df - df.shift(L)).to_numpy()
    sd = df.iloc[:, b_i].diff().rolling(336, min_periods=168).std(ddof=0).shift(1).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.nan_to_num(lr[:, b_i] / (sd * math.sqrt(L)), nan=0.0, posinf=0.0, neginf=0.0)
    d = np.sign(np.nan_to_num(lr[:, b_i], nan=0.0))
    shock = (np.abs(z) >= c["shock_z"]) & (d != 0)
    mat = np.zeros(logc.shape, dtype=np.int8)
    for j in range(len(syms)):
        if j == b_i:
            continue
        alt = lr[:, j]
        lag = d * np.nan_to_num(alt, nan=0.0) < d * np.nan_to_num(lr[:, b_i], nan=0.0)
        m = shock & lag & np.isfinite(alt)
        mat[m, j] = d[m].astype(np.int8)
    return _to_symbol_dirs(panels_1h, grid, syms, mat)


# ---------- per-symbol signals (use bars <= i only) ----------

def _volreg_signal(p, c):
    """Volume regime cross-up (fast mean / slow mean crosses ratio_thr), trend direction."""
    fast, slow = rb._sma(p.V, c["fast_bars"]), rb._sma(p.V, c["slow_bars"])
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = fast / slow
    thr = c["ratio_thr"]
    cross = (ratio >= thr) & (rb._shift(ratio, 1) < thr)
    trend = np.sign(np.nan_to_num(p.C - rb._shift(p.C, c["trend_bars"]), nan=0.0))
    return np.where(cross, trend, 0).astype(np.int8)


def _volrv_signal(p, c):
    """Realized-vol regime cross-up (fast RV / slow RV crosses threshold), trend or fade."""
    lr = np.diff(np.log(p.C), prepend=np.nan)
    rf = pd.Series(lr).rolling(c["fast_bars"], min_periods=c["fast_bars"]).std(ddof=0).to_numpy()
    rs = pd.Series(lr).rolling(c["slow_bars"], min_periods=c["slow_bars"]).std(ddof=0).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = rf / rs
    thr = c["rv_ratio_thr"]
    cross = (ratio >= thr) & (rb._shift(ratio, 1) < thr)
    d = np.sign(np.nan_to_num(p.C - rb._shift(p.C, c["fast_bars"]), nan=0.0))
    if c["mode"] == "fade":
        d = -d
    return np.where(cross, d, 0).astype(np.int8)


def _settle_signal(p, c):
    """Signal on bar i when the entry bar (i+1) opens at (settlement hour - offset) UTC."""
    if len(p.T) == 0:  # symbol with no TRAIN bars at this timeframe
        return np.zeros(0, dtype=np.int8)
    nxt = np.append(p.T[1:], p.T[-1] + p.tf_ms)
    hour = (nxt // HOUR_MS) % 24
    target = (c["settle_hour_utc"] - c["offset_hours"]) % 24
    sign = 1 if c["direction"] == "long" else -1
    return np.where(hour == target, sign, 0).astype(np.int8)


PER_SYMBOL = {"C6": _volreg_signal, "C7": _volrv_signal, "C8": _settle_signal}


def dirs_for_config(config, panels):
    fam = config["family"][:2]
    panels_tf = panels[config["timeframe"]]
    if fam in ("C1", "C2", "C3"):
        return _cs_dirs(panels_tf, config)
    if fam == "C4":
        return _pair_dirs(panels_tf, config)
    if fam == "C5":
        return _leadlag_dirs(panels_tf, config)
    return {s: PER_SYMBOL[fam](panels_tf[s], config) for s in panels_tf}


# ---------- trade simulation (crypto.simulate_trade; entry delay and cost are parameters) ----------

def simulate_symbol(panel, dirs, config, *, delay: int = 1, fee_bps: float = FEE_BPS,
                    slip_bps: float = SLIP_BPS, want_daily: bool = False):
    """Non-overlapping trades for one symbol. Entry = open of bar i+delay (delay=1 is base)."""
    from crypto import Setup, Zone, simulate_trade, trade_daily_pnl
    n = len(panel.C)
    horizon, reward, stop_atr = config["horizon_bars"], config["reward_r"], config["stop_atr"]
    trades, stats = [], {"censored_no_exit": 0, "unscorable_funding": 0,
                         "reconcile_error": 0, "skipped_overlap": 0}
    last_exit = -1
    for i in np.flatnonzero(dirs):
        if i < WARMUP_BARS or i + delay >= n:
            continue
        if i < last_exit:
            stats["skipped_overlap"] += 1
            continue
        a = panel.atr[i]
        if not math.isfinite(a) or a <= 0:
            continue
        direction = "long" if dirs[i] > 0 else "short"
        entry_i = int(i) + delay
        entry = panel.O[entry_i]
        risk = stop_atr * a
        if direction == "long":
            stop, target = entry - risk, entry + reward * risk
        else:
            stop, target = entry + risk, entry - reward * risk
        zone = Zone(int(i), int(i), direction, min(entry, stop), max(entry, stop), a)
        setup = Setup(zone, entry_i, entry, stop, target)
        hi = panel.T[min(entry_i + horizon, n - 1)] + 2 * panel.tf_ms
        sub = rb._funding_window(panel, panel.T[entry_i] - panel.tf_ms, hi)
        trade = simulate_trade(panel.bars, setup, funding=sub, max_holding_bars=horizon,
                               fee_bps_per_side=fee_bps, slippage_bps_per_side=slip_bps,
                               bar_duration_ms=panel.tf_ms, validated=True,
                               funding_order_policy=FUNDING_POLICY)
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
        trades.append({"symbol": panel.symbol, "entry_ts": int(panel.T[entry_i]),
                       "entry_year": int(_utc_year(int(panel.T[entry_i]))),
                       "exit_reason": trade.exit_reason, "net": trade.net_return,
                       "daily": daily})
    return trades, stats


def _utc_year(ts_ms: int) -> int:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).year


def _run_trades(panels_tf, dirs_map, config, **kwargs):
    trades, totals = [], {"censored_no_exit": 0, "unscorable_funding": 0,
                          "reconcile_error": 0, "skipped_overlap": 0}
    for symbol, panel in panels_tf.items():
        t, stats = simulate_symbol(panel, dirs_map[symbol], config, **kwargs)
        trades.extend(t)
        for key in totals:
            totals[key] += stats[key]
    return trades, totals


def _group_stats(values):
    from metrics import trade_metrics
    if not values:
        return {"n": 0, "expectancy_bps": None, "sum_return": 0.0}
    tm = trade_metrics(values)
    return {"n": tm.count, "expectancy_bps": tm.expectancy_bps, "sum_return": float(sum(values))}


def supplementary(trades_base, trades_delay, trades_cost2, n_bonf):
    """Preregistered supplementary checks (all required; failure => not a candidate)."""
    from metrics import trade_metrics
    out = {}
    nets_d = [t["net"] for t in trades_delay]
    tm_d = trade_metrics(nets_d) if nets_d else None
    delay_pass = bool(tm_d and tm_d.count >= MIN_TRADES_CORE
                      and tm_d.expectancy_bps is not None and tm_d.expectancy_bps >= 15.0
                      and tm_d.profit_factor is not None and tm_d.profit_factor >= 1.30)
    out["delay1"] = {"trades": tm_d.count if tm_d else 0,
                     "expectancy_bps": tm_d.expectancy_bps if tm_d else None,
                     "profit_factor": tm_d.profit_factor if tm_d else None, "pass": delay_pass}

    nets_c2 = [t["net"] for t in trades_cost2]
    tm_c2 = trade_metrics(nets_c2) if nets_c2 else None
    cost2_pass = bool(tm_c2 and tm_c2.expectancy_bps is not None and tm_c2.expectancy_bps > 0)
    out["cost2"] = {"trades": tm_c2.count if tm_c2 else 0,
                    "expectancy_bps": tm_c2.expectancy_bps if tm_c2 else None, "pass": cost2_pass}

    by_day = {}
    for t in trades_base:
        by_day.setdefault(t["entry_ts"] // DAY_MS, []).append(t["net"])
    day_means = [sum(v) / len(v) for v in by_day.values()]
    p_cluster = rb._one_sided_p(day_means) if len(day_means) >= 2 else None
    cluster_pass = bool(p_cluster is not None and p_cluster < 0.05 / n_bonf)
    out["cluster"] = {"entry_days": len(day_means), "p_one_sided": p_cluster,
                      "threshold": 0.05 / n_bonf, "pass": cluster_pass}

    years = {}
    for t in trades_base:
        years.setdefault(t["entry_year"], []).append(t["net"])
    year_rows = {str(y): _group_stats(v) for y, v in sorted(years.items())}
    qualifying = [r for r in year_rows.values() if r["n"] >= MIN_TRADES_PER_YEAR]
    years_pass = bool(qualifying) and all(r["expectancy_bps"] > 0 for r in qualifying)
    out["years"] = {"by_year": year_rows, "qualifying_years": len(qualifying),
                    "pass": years_pass}

    pnl_by_symbol = {}
    for t in trades_base:
        pnl_by_symbol[t["symbol"]] = pnl_by_symbol.get(t["symbol"], 0.0) + t["net"]
    top3 = sorted(pnl_by_symbol, key=lambda s: pnl_by_symbol[s], reverse=True)[:3]
    rest = [t["net"] for t in trades_base if t["symbol"] not in top3]
    tm_x = trade_metrics(rest) if rest else None
    excl_pass = bool(tm_x and tm_x.count >= MIN_TRADES_CORE
                     and tm_x.expectancy_bps is not None and tm_x.expectancy_bps >= 15.0
                     and tm_x.profit_factor is not None and tm_x.profit_factor >= 1.30)
    out["exclude_top3"] = {"symbols": top3, "trades": tm_x.count if tm_x else 0,
                           "expectancy_bps": tm_x.expectancy_bps if tm_x else None,
                           "profit_factor": tm_x.profit_factor if tm_x else None,
                           "pass": excl_pass}
    out["all_pass"] = bool(delay_pass and cost2_pass and cluster_pass and years_pass and excl_pass)
    return out


def score_config(config, panels, all_days, n_symbols, bonferroni_n):
    from metrics import core_gate, curve_metrics, trade_metrics, wilson_lower
    tf = config["timeframe"]
    panels_tf = panels[tf]
    dirs_map = dirs_for_config(config, panels)
    base, totals = _run_trades(panels_tf, dirs_map, config, want_daily=True)
    delayed, _ = _run_trades(panels_tf, dirs_map, config, delay=2)
    cost2, _ = _run_trades(panels_tf, dirs_map, config, fee_bps=COST2_FEE_BPS,
                           slip_bps=COST2_SLIP_BPS)
    result = {"config_id": config["config_id"], "family": config["family"], "trades": len(base),
              **totals, "signal_bars": int(sum(int(np.count_nonzero(d)) for d in dirs_map.values()))}
    if not base:
        result.update({"status": "no_trades", "passes_core": False, "passes_bonferroni": False,
                       "candidate": False})
        return result
    nets = [t["net"] for t in base]
    day_pnl = {}
    for t in base:
        for day, value in t["daily"].items():
            day_pnl[day] = day_pnl.get(day, 0.0) + value
    daily_list = [day_pnl.get(day, 0.0) / n_symbols for day in all_days]
    tm = trade_metrics(nets)
    core = core_gate(tm, daily_list, market="crypto")
    cm = curve_metrics(daily_list, 365)
    p1 = rb._one_sided_p(nets)
    targets = sum(1 for t in base if t["exit_reason"] == "target")
    core_pass = all(core.values())
    bonf_pass = p1 is not None and p1 < 0.05 / bonferroni_n
    supp = supplementary(base, delayed, cost2, bonferroni_n)
    result.update({
        "status": "scored", "win_rate": tm.win_rate, "wilson_95_lower": tm.wilson_lower_95,
        "breakeven_win_rate": tm.breakeven_win_rate, "profit_factor": tm.profit_factor,
        "expectancy_bps": tm.expectancy_bps, "cumulative_return": cm.cumulative_return,
        "max_drawdown": cm.max_drawdown, "sharpe": cm.annualized_sharpe,
        "m2_target_rate": targets / len(base), "m2_wilson_lower": wilson_lower(targets, len(base)),
        "one_sided_p": p1, "bonferroni_threshold": 0.05 / bonferroni_n,
        "core_gate": {k: bool(v) for k, v in core.items()}, "passes_core": core_pass,
        "passes_bonferroni": bonf_pass, "supplementary": supp,
        "candidate": bool(core_pass and bonf_pass and supp["all_pass"]),
    })
    return result


# ---------- run harness ----------

_WORKER: dict = {}
CODE_FILES = ("search_coinb_rb1000.py", "search_crypto_rb500.py", "crypto.py", "data_access.py",
              "metrics.py", "search_crypto.py", "search_crypto_r14.py", "resource_guard.py",
              PREREG_PATH.name, MASTER_PATH.name, "universe/CRYPTO_35.csv")


def _init_worker():
    panels, all_days, n_symbols, _fp = rb.load_panels()
    _WORKER.update(panels=panels, all_days=all_days, n_symbols=n_symbols)


def _run_one(args):
    config, bonferroni_n = args
    try:
        return score_config(config, _WORKER["panels"], _WORKER["all_days"],
                            _WORKER["n_symbols"], bonferroni_n)
    except Exception as exc:  # failures are kept as ledger rows, never dropped
        return {"config_id": config["config_id"], "family": config["family"],
                "status": "failed", "failure_type": type(exc).__name__,
                "detail": str(exc)[:300]}


def _code_sha():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _ledger_record(result, grid_sha, code_sha, fingerprint, bonferroni_n, prereg_sha,
                   master_sha, rows_before):
    config = next(c for c in GRID if c["config_id"] == result["config_id"])
    metric = rb._sanitize({**result, "bonferroni_denominator": bonferroni_n,
                           "rows_before": rows_before,
                           "denominator_formula": "rows_before + 429 + 1000",
                           "train_input_fingerprint": fingerprint,
                           "prereg_sha256": prereg_sha, "master_prereg_sha256": master_sha,
                           "label_note": "TRAIN_ONLY_NOT_G; survivors-only universe"})
    return {
        "trial_id": f"RB1000-COINB-{config['config_id']}-{uuid.uuid4().hex[:12]}",
        "round": ROUND, "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(rb._sanitize(config), sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": f"1h/4h bar close <={TRAIN_CUTOFF}",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":"), allow_nan=False),
        "rank": "",
        "notes": f"RB1000-COINB TRAIN-only config {config['config_id']}; not OOS or G approval",
    }


GRID: list[dict] = build_grid()


def run(commit: bool, configs=None, workers: int = 10):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    import search_crypto as common
    import search_crypto_r19_match_attrition_audit as r19
    import search_crypto_r33_delayed_sweep_bos as r33
    data_root = Path(os.environ.get("TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    configs = GRID if configs is None else configs
    locks = []
    if commit:
        r19._assert_no_ledger_writer()
        locks = r33._acquire_locks(data_root)
    try:
        rows = rb._ledger_rows(common.CSV_PATH)
        bonf_n = rows + PRIOR_EXPLORE_ROWS + LANE_TOTAL_CONFIGS
        grid_sha = grid_sha256(configs)
        code_sha = _code_sha()
        prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
        master_sha = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
        _, _, _, fingerprint = rb.load_panels()
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx,
                                 initializer=_init_worker) as pool:
            results = list(pool.map(_run_one, [(c, bonf_n) for c in configs], chunksize=2))
        out_dir = data_root / "cache/orderblock/runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_csv = out_dir / f"RB1000_COINB_{stamp}.csv"
        with out_csv.open("w", newline="", encoding="utf-8") as stream:
            fields = sorted({k for r in results for k in r})
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow({k: (json.dumps(rb._sanitize(v)) if isinstance(v, (dict, list)) else v)
                                 for k, v in r.items()})
        summary = {"rows_before": rows, "bonferroni_n": bonf_n, "grid_sha256": grid_sha,
                   "code_sha256": code_sha, "fingerprint": fingerprint,
                   "results_csv": str(out_csv), "committed": False}
        if commit:
            records = [_ledger_record(r, grid_sha, code_sha, fingerprint, bonf_n,
                                      prereg_sha, master_sha, rows) for r in results]
            summary["ledger_rows_appended"] = rb.append_ledger_locked(records, rows, common.CSV_PATH)
            summary["committed"] = True
        return summary, results
    finally:
        if locks:
            r33._release_locks(locks)


if __name__ == "__main__":
    commit = "--commit-ledger" in sys.argv
    summary, results = run(commit=commit)
    print(json.dumps(rb._sanitize(summary), sort_keys=True), flush=True)
