"""RB500-COIN: one-time TRAIN-only batch of 500 preregistered non-orderblock coin configs.

Reuses the existing harness: crypto.simulate_trade / trade_daily_pnl (next-bar-open fill,
stop/target/time exit, funding), metrics.core_gate (fixed G core), data_access via
search_crypto_r14._load_barsets (train cutoff 2023-11-06T16:00Z), and the ledger
lock helpers of search_crypto_r33_delayed_sweep_bos. No test-period data is read.
"""
from __future__ import annotations

import bisect
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

HERE = Path(__file__).resolve().parent
ROUND = "RB500-COIN"
PREREG_PATH = HERE / "PREREG_RB500_COIN.md"
MASTER_PATH = HERE / "PREREG.md"
N_CONFIGS = 500
WARMUP_BARS = 500
FEE_BPS = 4.0
SLIP_BPS = 2.0
FUNDING_POLICY = "adverse_only"
TF_MS = {"1h": 3_600_000, "4h": 14_400_000}
DAY_MS = 86_400_000
BARS_PER_DAY_4H = 6
TRAIN_CUTOFF = "2023-11-06T16:00:00Z"

# (family, variable params in product order, fixed params, quota). Priority order.
FAMILY_SPECS = (
    ("F1_DONCHIAN_TREND_BREAKOUT",
     {"timeframe": ["1h", "4h"], "lookback_bars": [20, 40, 55, 100, 150],
      "direction": ["long", "short"], "reward_r": [1.0, 1.5, 2.0, 2.5, 3.0]},
     {"stop_atr": 2.0, "horizon_bars": 48, "trend_sma_bars": 200}, 100),
    ("F2_TSMOM_SKIP_MONTH",
     {"lookback_days": [60, 90, 120, 180, 365], "skip_days": [0, 7, 30],
      "reward_r": [1.5, 2.0], "horizon_bars": [24, 48]},
     {"timeframe": "4h", "stop_atr": 2.0}, 60),
    ("F3_VOL_SQUEEZE_BREAKOUT",
     {"timeframe": ["1h", "4h"], "squeeze_percentile": [10, 20, 30],
      "breakout_lookback_bars": [20, 40], "reward_r": [0.75, 1.0, 1.5, 2.0, 3.0]},
     {"stop_atr": 2.0, "horizon_bars": 24, "bb_period": 20, "width_window_bars": 200}, 60),
    ("F4_BTC_REGIME_ALT_RS_ROTATION",
     {"top_k": [1, 2, 3, 5, 10], "rs_lookback_bars": [42, 84, 180, 360],
      "regime_sma_bars": [50, 100, 200]},
     {"timeframe": "4h", "stop_atr": 2.0, "horizon_bars": 24, "reward_r": 2.0, "direction": "long"}, 60),
    ("F5_VOLUME_SURGE_MOMENTUM",
     {"timeframe": ["1h", "4h"], "volume_mult": [2.0, 2.5, 3.0, 4.0, 5.0],
      "volume_window_bars": [20, 50, 100, 200, 400]},
     {"stop_atr": 2.0, "horizon_bars": 24, "reward_r": 2.0}, 50),
    ("F6_EMA_PULLBACK_TREND",
     {"timeframe": ["1h", "4h"], "ema_period": [20, 50, 100, 150, 200],
      "tolerance_atr": [0.0, 0.25, 0.5, 0.75, 1.0]},
     {"stop_atr": 2.0, "horizon_bars": 24, "reward_r": 2.0}, 50),
    ("F7_RSI2_SHORT_REVERSAL",
     {"timeframe": ["1h", "4h"], "rsi2_threshold": [5, 10, 15, 20, 25],
      "trend_sma_bars": [0, 50, 100, 200, 400]},
     {"stop_atr": 2.0, "horizon_bars": 24, "reward_r": 1.0}, 50),
    ("F8_SHOCK_REBOUND_LIQ_PROXY",
     {"timeframe": ["1h", "4h"], "shock_atr": [2.0, 2.5, 3.0, 4.0, 5.0],
      "volume_mult": [2.0, 3.0, 4.0, 5.0]},
     {"stop_atr": 2.0, "horizon_bars": 24, "reward_r": 1.0, "direction": "long",
      "volume_window_bars": 100}, 40),
    ("F9_CALENDAR_SESSION",
     {"entry_hour_utc": [0, 8, 16], "entry_weekday": [0, 1, 2, 3, 4],
      "direction": ["long", "short"]},
     {"timeframe": "1h", "stop_atr": 2.0, "horizon_bars": 24, "reward_r": 1.0}, 30),
)


def build_grid() -> list[dict]:
    """Deterministic exact grid: family order, itertools.product over sorted-as-listed values."""
    grid: list[dict] = []
    for family, variable, fixed, quota in FAMILY_SPECS:
        keys = list(variable)
        combos = list(itertools.product(*(variable[k] for k in keys)))
        if len(combos) != quota:
            raise ValueError(f"{family}: grid size {len(combos)} != quota {quota}")
        for values in combos:
            config = {"family": family, **fixed, **dict(zip(keys, values))}
            grid.append(config)
    if len(grid) != N_CONFIGS:
        raise ValueError("grid must have exactly 500 configs")
    for n, config in enumerate(grid):
        config["config_id"] = f"RB-{n:03d}"
    return grid


def grid_sha256(grid: list[dict]) -> str:
    raw = json.dumps(grid, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


# ---------- indicators (all use bars <= i only) ----------

def _sma(x, n):
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def _prior_max(x, n):
    return pd.Series(x).rolling(n, min_periods=n).max().shift(1).to_numpy()


def _prior_min(x, n):
    return pd.Series(x).rolling(n, min_periods=n).min().shift(1).to_numpy()


def _prior_mean(x, n):
    return pd.Series(x).rolling(n, min_periods=n).mean().shift(1).to_numpy()


def _ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def _shift(x, k):
    return pd.Series(x).shift(k).to_numpy()


class Panel:
    """One symbol at one timeframe, as numpy arrays plus the original Bar list."""

    def __init__(self, symbol, bars, funding, tf_ms):
        self.symbol = symbol
        self.bars = bars
        self.funding = funding
        self.keys = sorted(funding)
        self.tf_ms = tf_ms
        self.T = np.array([b.timestamp for b in bars], dtype=np.int64)
        self.O = np.array([b.open for b in bars], dtype=float)
        self.H = np.array([b.high for b in bars], dtype=float)
        self.L = np.array([b.low for b in bars], dtype=float)
        self.C = np.array([b.close for b in bars], dtype=float)
        self.V = np.array([b.volume for b in bars], dtype=float)
        prev_c = np.concatenate(([self.O[0]], self.C[:-1])) if len(self.C) else self.C
        tr = np.maximum(self.H - self.L, np.maximum(np.abs(self.H - prev_c), np.abs(self.L - prev_c)))
        self.atr = pd.Series(tr).rolling(14, min_periods=14).mean().to_numpy()


def _direction_array(n):
    return np.zeros(n, dtype=np.int8)


def _donchian(p, c):
    hi, lo = _prior_max(p.H, c["lookback_bars"]), _prior_min(p.L, c["lookback_bars"])
    trend = _sma(p.C, c["trend_sma_bars"])
    out = _direction_array(len(p.C))
    if c["direction"] == "long":
        out[(p.C > hi) & (p.C > trend)] = 1
    else:
        out[(p.C < lo) & (p.C < trend)] = -1
    return out


def _tsmom(p, c):
    lb, sk = c["lookback_days"] * BARS_PER_DAY_4H, c["skip_days"] * BARS_PER_DAY_4H
    ret = _shift(p.C, sk) / _shift(p.C, lb) - 1
    sign = np.sign(np.nan_to_num(ret))
    prev = _shift(sign, 1)
    out = _direction_array(len(p.C))
    flip = (sign != 0) & (sign != np.nan_to_num(prev, nan=0.0))
    out[flip] = sign[flip].astype(np.int8)
    return out


def _vol_squeeze(p, c):
    n = c["bb_period"]
    mid = _sma(p.C, n)
    sd = pd.Series(p.C).rolling(n, min_periods=n).std(ddof=0).to_numpy()
    width = 4 * sd / mid
    thr = pd.Series(width).rolling(c["width_window_bars"], min_periods=c["width_window_bars"]) \
        .quantile(c["squeeze_percentile"] / 100).to_numpy()
    squeeze_prev = _shift(width <= thr, 1)
    squeeze_prev = np.nan_to_num(squeeze_prev.astype(float), nan=0.0) > 0
    b = c["breakout_lookback_bars"]
    out = _direction_array(len(p.C))
    out[squeeze_prev & (p.C > _prior_max(p.H, b))] = 1
    out[squeeze_prev & (p.C < _prior_min(p.L, b))] = -1
    return out


def _volume_surge(p, c):
    vm = _prior_mean(p.V, c["volume_window_bars"])
    cond = p.V > c["volume_mult"] * vm
    out = _direction_array(len(p.C))
    body = np.sign(p.C - p.O).astype(np.int8)
    out[cond] = body[cond]
    return out


def _ema_pullback(p, c):
    ema = _ema(p.C, c["ema_period"])
    slope_up = ema > _shift(ema, 5)
    slope_dn = ema < _shift(ema, 5)
    tol = c["tolerance_atr"] * p.atr
    out = _direction_array(len(p.C))
    out[(p.C > ema) & slope_up & (p.L <= ema + tol)] = 1
    out[(p.C < ema) & slope_dn & (p.H >= ema - tol)] = -1
    return out


def _rsi2(p, c):
    d = np.diff(p.C, prepend=np.nan)
    gain = pd.Series(np.where(d > 0, d, 0.0)).rolling(2, min_periods=2).mean().to_numpy()
    loss = pd.Series(np.where(d < 0, -d, 0.0)).rolling(2, min_periods=2).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = np.where(loss == 0, 100.0, 100 - 100 / (1 + gain / loss))
    thr = c["rsi2_threshold"]
    if c["trend_sma_bars"] > 0:
        trend = _sma(p.C, c["trend_sma_bars"])
        up_ok, dn_ok = p.C > trend, p.C < trend
    else:
        up_ok = dn_ok = np.ones(len(p.C), dtype=bool)
    out = _direction_array(len(p.C))
    out[(rsi < thr) & up_ok] = 1
    out[(rsi > 100 - thr) & dn_ok] = -1
    return out


def _shock_rebound(p, c):
    vm = _prior_mean(p.V, c["volume_window_bars"])
    drop = p.O - p.C
    cond = (drop >= c["shock_atr"] * p.atr) & (p.V >= c["volume_mult"] * vm)
    out = _direction_array(len(p.C))
    out[cond] = 1
    return out


def _calendar(p, c):
    nxt = np.append(p.T[1:], p.T[-1] + p.tf_ms) if len(p.T) else p.T
    hour = (nxt // 3_600_000) % 24
    weekday = ((nxt // DAY_MS) + 3) % 7
    cond = (hour == c["entry_hour_utc"]) & (weekday == c["entry_weekday"])
    out = _direction_array(len(p.C))
    out[cond] = 1 if c["direction"] == "long" else -1
    return out


def _btc_regime_rs(panels4h, c):
    """Cross-sectional: each 4h row, top-K alts by RS vs BTC, only when BTC > its SMA."""
    btc = panels4h["BTCUSDT"]
    grid = np.unique(np.concatenate([p.T for p in panels4h.values()]))
    alts = sorted(s for s in panels4h if s != "BTCUSDT")
    lb = c["rs_lookback_bars"]

    def aligned_close(p):
        series = pd.Series(p.C, index=p.T).reindex(grid)
        return series.to_numpy()

    cb = aligned_close(btc)
    btc_ret = cb / pd.Series(cb).shift(lb).to_numpy() - 1
    regime = cb > _sma(cb, c["regime_sma_bars"])
    rs = np.full((len(grid), len(alts)), np.nan)
    for j, s in enumerate(alts):
        ca = aligned_close(panels4h[s])
        rs[:, j] = ca / pd.Series(ca).shift(lb).to_numpy() - 1 - btc_ret
    masked = np.where(np.isnan(rs), -np.inf, rs)
    order = np.argsort(-masked, axis=1)[:, : c["top_k"]]
    chosen = np.zeros(rs.shape, dtype=bool)
    rows = np.arange(len(grid))[:, None]
    chosen[rows, order] = np.isfinite(masked[rows, order])
    chosen &= regime[:, None]
    result = {}
    for s in panels4h:
        if s == "BTCUSDT":
            result[s] = _direction_array(len(panels4h[s].C))
            continue
        col = alts.index(s)
        p = panels4h[s]
        rows_of_bars = np.searchsorted(grid, p.T)
        out = _direction_array(len(p.C))
        out[:] = chosen[rows_of_bars, col].astype(np.int8)
        result[s] = out
    return result


DISPATCH = {
    "F1_DONCHIAN_TREND_BREAKOUT": _donchian,
    "F2_TSMOM_SKIP_MONTH": _tsmom,
    "F3_VOL_SQUEEZE_BREAKOUT": _vol_squeeze,
    "F5_VOLUME_SURGE_MOMENTUM": _volume_surge,
    "F6_EMA_PULLBACK_TREND": _ema_pullback,
    "F7_RSI2_SHORT_REVERSAL": _rsi2,
    "F8_SHOCK_REBOUND_LIQ_PROXY": _shock_rebound,
    "F9_CALENDAR_SESSION": _calendar,
}


# ---------- trade simulation (reuses crypto.simulate_trade) ----------
def _funding_window(panel, lo_ms, hi_ms):
    a = bisect.bisect_left(panel.keys, lo_ms)
    b = bisect.bisect_right(panel.keys, hi_ms)
    return {k: panel.funding[k] for k in panel.keys[a:b]}


def simulate_symbol(panel, dirs, config):
    """Return (trades, stats) for one symbol; non-overlapping, next-open entry."""
    from crypto import Setup, Zone, simulate_trade, trade_daily_pnl
    n = len(panel.C)
    horizon, reward, stop_atr = config["horizon_bars"], config["reward_r"], config["stop_atr"]
    trades, stats = [], {"censored_no_exit": 0, "unscorable_funding": 0,
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
        sub = _funding_window(panel, panel.T[entry_i] - panel.tf_ms, hi)
        trade = simulate_trade(panel.bars, setup, funding=sub, max_holding_bars=horizon,
                               fee_bps_per_side=FEE_BPS, slippage_bps_per_side=SLIP_BPS,
                               bar_duration_ms=panel.tf_ms, validated=True,
                               funding_order_policy=FUNDING_POLICY)
        if trade is None:
            stats["censored_no_exit"] += 1
            continue
        last_exit = trade.exit_index
        if trade.net_return is None:
            stats["unscorable_funding"] += 1
            continue
        try:
            daily = trade_daily_pnl(panel.bars, trade, funding=sub, bar_duration_ms=panel.tf_ms)
        except ValueError:
            stats["reconcile_error"] += 1
            continue
        if daily is None:
            stats["unscorable_funding"] += 1
            continue
        trades.append((trade.net_return, trade.exit_reason, daily))
    return trades, stats


def _one_sided_p(values):
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    if var <= 0:
        return None
    t = mean / math.sqrt(var / n)
    return 0.5 * math.erfc(t / math.sqrt(2))


def score_config(config, panels, all_days, n_symbols, bonferroni_n):
    """Pool trades across the universe and apply the fixed G core and Bonferroni rule."""
    from metrics import core_gate, curve_metrics, trade_metrics, wilson_lower
    tf = config["timeframe"]
    panels_tf = panels[tf]
    nets, reasons, day_pnl = [], [], {}
    totals = {"censored_no_exit": 0, "unscorable_funding": 0,
              "reconcile_error": 0, "skipped_overlap": 0}
    cross = (_btc_regime_rs(panels["4h"], config)
             if config["family"] == "F4_BTC_REGIME_ALT_RS_ROTATION" else None)
    for symbol, panel in panels_tf.items():
        dirs = cross[symbol] if cross is not None else DISPATCH[config["family"]](panel, config)
        trades, stats = simulate_symbol(panel, dirs, config)
        for key in totals:
            totals[key] += stats[key]
        for net, reason, daily in trades:
            nets.append(net)
            reasons.append(reason)
            for day, value in daily.items():
                day_pnl[day] = day_pnl.get(day, 0.0) + value
    daily_list = [day_pnl.get(day, 0.0) / n_symbols for day in all_days]
    result = {"config_id": config["config_id"], "family": config["family"],
              "trades": len(nets), **totals}
    if not nets:
        result.update({"status": "no_trades", "passes_core": False, "passes_bonferroni": False,
                       "passes_pass_rule": False})
        return result
    tm = trade_metrics(nets)
    core = core_gate(tm, daily_list, market="crypto")
    cm = curve_metrics(daily_list, 365)
    p1 = _one_sided_p(nets)
    targets = sum(1 for r in reasons if r == "target")
    m2_lower = wilson_lower(targets, len(reasons))
    bonf_pass = p1 is not None and p1 < 0.05 / bonferroni_n
    core_pass = all(core.values())
    result.update({
        "status": "scored", "win_rate": tm.win_rate, "wilson_95_lower": tm.wilson_lower_95,
        "breakeven_win_rate": tm.breakeven_win_rate, "profit_factor": tm.profit_factor,
        "expectancy_bps": tm.expectancy_bps, "cumulative_return": cm.cumulative_return,
        "max_drawdown": cm.max_drawdown, "sharpe": cm.annualized_sharpe,
        "m2_target_rate": targets / len(reasons), "m2_wilson_lower": m2_lower,
        "one_sided_p": p1, "bonferroni_threshold": 0.05 / bonferroni_n,
        "core_gate": {k: bool(v) for k, v in core.items()}, "passes_core": core_pass, "passes_bonferroni": bonf_pass,
        "passes_pass_rule": core_pass and bonf_pass,
    })
    return result





# ---------- run harness: parallel workers, locked ledger append ----------

_WORKER: dict = {}
CODE_FILES = ("search_crypto_rb500.py", "crypto.py", "data_access.py", "metrics.py",
              "search_crypto.py", "search_crypto_r14.py",
              "search_crypto_r19_match_attrition_audit.py",
              "search_crypto_r33_delayed_sweep_bos.py", "resource_guard.py",
              PREREG_PATH.name, MASTER_PATH.name, "universe/CRYPTO_35.csv")


def load_panels():
    import data_access
    import search_crypto_r14 as r14
    import search_crypto as common
    panels, fingerprints = {}, []
    for tf in ("1h", "4h"):
        barsets = r14._load_barsets(data_access.iter_train_bars, tf)
        fingerprints.append(common._train_input_fingerprint(tf, barsets))
        panels[tf] = {symbol: Panel(symbol, bars, funding, TF_MS[tf])
                      for symbol, bars, funding, _excluded in barsets}
    first = min(int(p.T[0]) for p in panels["1h"].values() if len(p.T))
    last = max(int(p.T[-1]) for p in panels["1h"].values() if len(p.T))
    all_days = list(range(first // DAY_MS, last // DAY_MS + 1))
    fingerprint = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    return panels, all_days, len(panels["1h"]), fingerprint


def _init_worker():
    panels, all_days, n_symbols, _fp = load_panels()
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


def _sanitize(value):
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


def _code_sha():
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update((HERE / name).read_bytes())
    return digest.hexdigest()


def _ledger_rows(path):
    old = csv.field_size_limit()
    csv.field_size_limit(sys.maxsize)
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            return sum(1 for _ in reader)
    finally:
        csv.field_size_limit(old)


def _ledger_record(result, grid_sha, code_sha, fingerprint, bonferroni_n, prereg_sha, master_sha):
    config = next(c for c in GRID if c["config_id"] == result["config_id"])
    metric = _sanitize({**result, "bonferroni_denominator": bonferroni_n,
                        "train_input_fingerprint": fingerprint,
                        "prereg_sha256": prereg_sha, "master_prereg_sha256": master_sha,
                        "label_note": "TRAIN_ONLY_NOT_G; survivors-only universe"})
    return {
        "trial_id": f"RB500-crypto-{config['config_id']}-{uuid.uuid4().hex[:12]}",
        "round": ROUND, "market_group": "crypto",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "definition": json.dumps(_sanitize(config), sort_keys=True, separators=(",", ":")),
        "parameter_grid_hash": grid_sha, "code_sha256": code_sha,
        "train_period": f"1h/4h bar close <={TRAIN_CUTOFF}",
        "metric": json.dumps(metric, sort_keys=True, separators=(",", ":"), allow_nan=False),
        "rank": "", "notes": f"RB500 TRAIN-only config {config['config_id']}; not OOS or G approval",
    }


GRID: list[dict] = build_grid()


def append_ledger_locked(records, expected_rows, ledger_path):
    """Append all records in one write under flock; refuse if the row count changed."""
    import search_crypto as common
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=common.FIELDS)
    for record in records:
        writer.writerow(record)
    payload = buffer.getvalue().encode()
    fd = os.open(ledger_path, os.O_WRONLY | os.O_APPEND)
    try:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX)
        if _ledger_rows(ledger_path) != expected_rows:
            raise RuntimeError("ledger row count changed before append; nothing written")
        written = os.write(fd, payload)
        if written != len(payload):
            raise RuntimeError("short ledger append; inspect ledger, do not retry")
        os.fsync(fd)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    return len(records)


def run(commit: bool, configs=None, workers: int = 10):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    import search_crypto as common
    import search_crypto_r19_match_attrition_audit as r19
    import search_crypto_r33_delayed_sweep_bos as r33
    data_root = Path(os.environ.get("TRADING_DATA_DIR", Path.home() / "CODE/trading_data")).expanduser()
    configs = GRID if configs is None else configs
    if commit:
        r19._assert_no_ledger_writer()
        locks = r33._acquire_locks(data_root)
    else:
        locks = []
    try:
        rows = _ledger_rows(common.CSV_PATH)
        bonf_n = rows + len(configs)
        grid_sha = grid_sha256(configs)
        code_sha = _code_sha()
        prereg_sha = hashlib.sha256(PREREG_PATH.read_bytes()).hexdigest()
        master_sha = hashlib.sha256(MASTER_PATH.read_bytes()).hexdigest()
        _, _, _, fingerprint = load_panels()
        ctx = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx,
                                 initializer=_init_worker) as pool:
            results = list(pool.map(_run_one, [(c, bonf_n) for c in configs], chunksize=4))
        out_dir = data_root / "cache/orderblock/runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_csv = out_dir / f"RB500_COIN_{stamp}.csv"
        with out_csv.open("w", newline="", encoding="utf-8") as stream:
            fields = sorted({k for r in results for k in r})
            csv_writer = csv.DictWriter(stream, fieldnames=fields)
            csv_writer.writeheader()
            for r in results:
                csv_writer.writerow({k: (json.dumps(_sanitize(v)) if isinstance(v, (dict, list)) else v)
                                     for k, v in r.items()})
        summary = {"rows_before": rows, "bonferroni_n": bonf_n, "grid_sha256": grid_sha,
                   "code_sha256": code_sha, "fingerprint": fingerprint,
                   "results_csv": str(out_csv), "committed": False}
        if commit:
            records = [_ledger_record(r, grid_sha, code_sha, fingerprint, bonf_n,
                                      prereg_sha, master_sha) for r in results]
            summary["ledger_rows_appended"] = append_ledger_locked(records, rows, common.CSV_PATH)
            summary["committed"] = True
        return summary, results
    finally:
        if locks:
            r33._release_locks(locks)


if __name__ == "__main__":
    commit = "--commit-ledger" in sys.argv
    summary, results = run(commit=commit)
    print(json.dumps(_sanitize(summary), sort_keys=True), flush=True)
