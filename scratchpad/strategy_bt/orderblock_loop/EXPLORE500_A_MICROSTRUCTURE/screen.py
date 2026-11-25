"""
EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered G-gate track,
not added to TRAIN_TRIALS.csv, no promotion without separate formal
preregistration + synthetic tests + resource-gated TRAIN run.

Cheap, approximate backtest harness for the ~167 non-orderblock crypto
microstructure ideas in ideas_catalog.py (lane A of the one-time 500-idea
exploratory screen). This is a rough ranking pass, not a rigorous backtest.

SCOPE / SIMPLIFICATIONS (documented plainly, per task instructions):
  - Symbols: a fixed 12-symbol subset of the 35-symbol universe (large/liquid
    perps): BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT,
    AVAXUSDT, DOTUSDT, LINKUSDT, LTCUSDT, ATOMUSDT.
  - Timeframe: 1h only (TRAIN-only / cutoff-safe via data_access.iter_train_bars).
  - Bars per symbol capped at the most recent MAX_BARS (12000) 1h bars for speed.
  - Shared exit convention for every idea (so results are comparable):
      stop  = entry_price -/+ 1.5 * ATR(14) at the signal bar's close
      target = 2R (2x the stop distance) in the trade's favor
      max hold = 48 bars; if neither stop nor target is hit, exit at the
        close of the last bar in the 48-bar window (or at the last
        available bar if data runs out first)
      if a single bar's high/low would hit BOTH stop and target, the stop
        is conservatively assumed to trigger first (worst case, no intrabar
        path information available from OHLC bars)
      entries are simulated at the OPEN of the bar immediately after the
        signal bar's close (no same-bar lookahead)
      a flat 12bp round-trip transaction cost is subtracted from every trade
  - No funding P&L is modeled except for ideas whose mechanism is specifically
    about funding rate (those use the FundingEvent rate directly for signal
    generation only; funding CARRY is not added to trade P&L in this pass --
    only directional price P&L net of the 12bp cost is scored, for all ideas
    uniformly, to keep metrics comparable across the whole screen).
  - Overlapping trades from the same idea/symbol are allowed to be in flight
    simultaneously (no position-sizing or capital-constraint model) -- this
    is a per-signal edge screen, not a portfolio simulation.
  - Several indicators use rolling/causal windows (no lookahead), but a few
    (e.g. funding "steepness" percentile) use a simplified full-series or
    long-rolling-window percentile rather than a point-in-time expanding
    percentile; where that occurs it is noted in the relevant function's
    docstring below. No formal look-ahead-bias audit has been performed.
  - Divergence detection (RSI/Stochastic) uses a simplified trailing
    "rolling N-bar extreme" proxy for swing pivots, not a confirmed
    swing-pivot detector with forward confirmation bars. This is a
    deliberate cheap-screen simplification.
  - Cross-asset ideas (relative-strength/lead-lag/decorrelation vs BTC) are
    evaluated only for the 11 non-BTC symbols in the subset, using BTCUSDT's
    own bars from this same subset as the reference series.
  - "4h momentum" in the single multi-timeframe idea is approximated as a
    40-bar (10 x 4h-equivalent) return on the 1h series rather than loading
    a separate 4h timeframe, to keep the pipeline single-timeframe for speed.

Of the 167 ideas in IDEAS.csv, 124 are actually backtested here (grouped
under 68 distinct signal-generating functions); the remaining 43 are
proposed with full mechanism/rationale/prior-rank text but not backtested
this pass (see ideas_catalog.py's _PROPOSED list for the reason per idea --
either the required data isn't in the local bar/funding parquet files at
all, e.g. open interest, spot price, liquidations, order-book depth, unlock
calendars; or it was deprioritized purely to stay inside the ~15-minute
runtime budget for this cheap pass).

Composite score (for RESULTS.csv), explicit and reproducible:
  composite_score = expectancy_bps * ln(1 + n_trades)
                     * reliability_penalty * pf_penalty
  where:
    reliability_penalty = min(1.0, n_trades / 30)   # ramps 0->1 under 30 trades
    pf_penalty = 0.0 if profit_factor <= 0 else min(1.0, profit_factor)
                 (so any idea with profit_factor < 1.0 has its score scaled
                 down proportionally to how far below 1.0 it is, and a
                 degenerate idea with no losing trades at all, profit_factor
                 = inf, is capped at pf_penalty = 1.0 so it isn't rewarded
                 beyond parity)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ORDERBLOCK_DIR = HERE.parent
sys.path.insert(0, str(ORDERBLOCK_DIR))
sys.path.insert(0, str(HERE))

from data_access import iter_train_bars  # noqa: E402
from ideas_catalog import build_catalog  # noqa: E402

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
           "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "LTCUSDT", "ATOMUSDT"]
TIMEFRAME = "1h"
MAX_BARS = 12000
ATR_PERIOD = 14
STOP_ATR_MULT = 1.5
TARGET_R_MULT = 2.0
MAX_HOLD_BARS = 48
ROUNDTRIP_COST_BPS = 12.0
LABEL = ("EXPLORATORY SCREEN ONLY -- not part of the 13-round preregistered "
         "G-gate track, not added to TRAIN_TRIALS.csv, no promotion without "
         "separate formal preregistration + synthetic tests + "
         "resource-gated TRAIN run.")


# ===========================================================================
# Indicator helpers (all causal / rolling, no lookahead unless documented)
# ===========================================================================

def ema(s, span):
    return s.ewm(span=span, adjust=False).mean()


def sma(s, window):
    return s.rolling(window).mean()


def true_range(df):
    prev_close = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(df, period=14):
    return true_range(df).ewm(alpha=1.0 / period, adjust=False).mean()


def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def stochastic_k(df, period=14):
    low_min = df["low"].rolling(period).min()
    high_max = df["high"].rolling(period).max()
    return 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)


def bollinger(close, window=20, nstd=2):
    mid = sma(close, window)
    std = close.rolling(window).std()
    upper = mid + nstd * std
    lower = mid - nstd * std
    bandwidth = (upper - lower) / mid.replace(0, np.nan)
    return mid, upper, lower, bandwidth


def keltner(df, ema_window=20, atr_window=10, mult=1.5):
    mid = ema(df["close"], ema_window)
    rng = atr(df, atr_window)
    return mid, mid + mult * rng, mid - mult * rng


def donchian(df, window):
    return df["high"].rolling(window).max(), df["low"].rolling(window).min()


def rolling_vwap(df, window):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    pv = tp * df["volume"]
    return pv.rolling(window).sum() / df["volume"].rolling(window).sum().replace(0, np.nan)


def zscore(s, window):
    m = s.rolling(window).mean()
    sd = s.rolling(window).std()
    return (s - m) / sd.replace(0, np.nan)


def rolling_pct_rank(s, window):
    # O(n*window) python-level rolling rank; acceptable for a handful of calls.
    def _last_rank(x):
        arr = np.asarray(x)
        return (arr <= arr[-1]).sum() / len(arr) * 100.0
    return s.rolling(window).apply(_last_rank, raw=True)


def obv(df):
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def clv_series(df):
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return ((df["close"] - df["low"]) - (df["high"] - df["close"])) / rng


def cmf(df, window=20):
    mfv = clv_series(df).fillna(0) * df["volume"]
    return mfv.rolling(window).sum() / df["volume"].rolling(window).sum().replace(0, np.nan)


def ad_line(df):
    mfv = clv_series(df).fillna(0) * df["volume"]
    return mfv.cumsum()


def parabolic_sar(df, step=0.02, max_step=0.2):
    high = df["high"].values
    low = df["low"].values
    n = len(df)
    sar = np.zeros(n)
    trend = np.zeros(n, dtype=int)
    if n < 2:
        return pd.Series(sar, index=df.index), pd.Series(trend, index=df.index)
    trend[0] = 1
    sar[0] = low[0]
    af = step
    ep = high[0]
    for i in range(1, n):
        prev_sar = sar[i - 1]
        if trend[i - 1] == 1:
            cand = prev_sar + af * (ep - prev_sar)
            cand = min(cand, low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < cand:
                trend[i] = -1
                sar[i] = ep
                af = step
                ep = low[i]
            else:
                trend[i] = 1
                sar[i] = cand
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + step, max_step)
        else:
            cand = prev_sar + af * (ep - prev_sar)
            cand = max(cand, high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > cand:
                trend[i] = 1
                sar[i] = ep
                af = step
                ep = high[i]
            else:
                trend[i] = -1
                sar[i] = cand
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + step, max_step)
    return pd.Series(sar, index=df.index), pd.Series(trend, index=df.index)


def trend_age(trend):
    """Bars since the trend series last flipped sign (causal)."""
    flip = trend.ne(trend.shift(1))
    grp = flip.cumsum()
    return grp.groupby(grp).cumcount()


def pairwise_divergence(price, indicator, window, kind, mode):
    """Simplified trailing-extreme divergence proxy (see module docstring).

    kind: 'high' or 'low' -- which price extreme to track.
    mode: 'regular' or 'hidden'.
    Returns a boolean Series, causal (no lookahead): a rolling N-bar extreme
    is, by construction of a trailing rolling max/min, confirmed exactly at
    the bar where it occurs (no future bars needed).
    """
    roll = price.rolling(window).max() if kind == "high" else price.rolling(window).min()
    flags = (price >= roll) if kind == "high" else (price <= roll)
    vals_p = price.values
    vals_i = indicator.values
    flag_vals = flags.values
    sig = np.zeros(len(price), dtype=bool)
    last_val = None
    last_ind = None
    for idx in range(len(price)):
        if flag_vals[idx]:
            if last_val is not None and not (np.isnan(vals_i[idx]) or np.isnan(last_ind)):
                if kind == "low":
                    if mode == "regular" and vals_p[idx] < last_val and vals_i[idx] > last_ind:
                        sig[idx] = True
                    if mode == "hidden" and vals_p[idx] > last_val and vals_i[idx] < last_ind:
                        sig[idx] = True
                else:
                    if mode == "regular" and vals_p[idx] > last_val and vals_i[idx] < last_ind:
                        sig[idx] = True
                    if mode == "hidden" and vals_p[idx] < last_val and vals_i[idx] > last_ind:
                        sig[idx] = True
            last_val = vals_p[idx]
            last_ind = vals_i[idx]
    return pd.Series(sig, index=price.index)


def utc_parts(timestamps_ms):
    dt = pd.to_datetime(timestamps_ms, unit="ms", utc=True)
    return dt.dt.hour, dt.dt.weekday, dt.dt.floor("D")


def daily_prior_levels(df, date):
    """Prior UTC day's high/low/close -> P/S1/R1, Camarilla H3/L3, Woodie mid, mapped onto each bar."""
    daily = df.groupby(date).agg(day_high=("high", "max"), day_low=("low", "min"),
                                  day_close=("close", "last"))
    prior = daily.shift(1)
    P = (prior["day_high"] + prior["day_low"] + prior["day_close"]) / 3
    S1 = 2 * P - prior["day_high"]
    R1 = 2 * P - prior["day_low"]
    rng = prior["day_high"] - prior["day_low"]
    H3 = prior["day_close"] + rng * 1.1 / 4
    L3 = prior["day_close"] - rng * 1.1 / 4
    Pw = (prior["day_high"] + prior["day_low"] + 2 * prior["day_close"]) / 4
    S1w = 2 * Pw - prior["day_high"]
    midw = (Pw + S1w) / 2
    out = {}
    for name, series in [("prior_high", prior["day_high"]), ("prior_low", prior["day_low"]),
                          ("P", P), ("S1", S1), ("R1", R1), ("H3", H3), ("L3", L3),
                          ("Pw", Pw), ("midw", midw)]:
        out[name] = date.map(series)
    return out


def opening_range_levels(df, date, hour, target_hour=0):
    is_open_bar = (hour == target_hour) & (
        (date != date.shift(1)) if target_hour == 0 else True)
    if target_hour != 0:
        # first bar of that hour each day
        is_open_bar = (hour == target_hour) & (hour.shift(1) != target_hour)
    or_high = df["high"].where(is_open_bar).ffill()
    or_low = df["low"].where(is_open_bar).ffill()
    return or_high, or_low


# ===========================================================================
# Per-symbol feature bundle
# ===========================================================================

def compute_features(df, funding_rate_series, btc_close_aligned=None):
    f = {}
    f["atr14"] = atr(df, ATR_PERIOD)
    f["ema9"] = ema(df["close"], 9)
    f["ema21"] = ema(df["close"], 21)
    f["ema55"] = ema(df["close"], 55)
    f["ema200"] = ema(df["close"], 200)
    f["rsi14"] = rsi(df["close"], 14)
    f["stoch14"] = stochastic_k(df, 14)
    bb_mid, bb_up, bb_lo, bb_bw = bollinger(df["close"], 20, 2)
    f["bb_mid"], f["bb_up"], f["bb_lo"], f["bb_bw"] = bb_mid, bb_up, bb_lo, bb_bw
    kc_mid, kc_up, kc_lo = keltner(df, 20, 10, 1.5)
    f["kc_mid"], f["kc_up"], f["kc_lo"] = kc_mid, kc_up, kc_lo
    f["don20_up"], f["don20_lo"] = donchian(df, 20)
    f["don55_up"], f["don55_lo"] = donchian(df, 55)
    f["vwma20"] = (df["close"] * df["volume"]).rolling(20).sum() / df["volume"].rolling(20).sum().replace(0, np.nan)
    f["obv"] = obv(df)
    f["cmf20"] = cmf(df, 20)
    f["ad_line"] = ad_line(df)
    f["clv"] = clv_series(df)
    f["vwap24"] = rolling_vwap(df, 24)
    f["ema200_z"] = zscore(df["close"] - f["ema200"], 200)
    f["z10"] = zscore(df["close"], 10)
    f["rank50"] = rolling_pct_rank(df["close"], 50)
    f["atr_pctrank100"] = rolling_pct_rank(f["atr14"], 100)
    logret = np.log(df["close"] / df["close"].shift(1))
    f["rv24"] = logret.rolling(24).std()
    f["rv168"] = logret.rolling(168).std()
    f["vol_of_vol"] = f["atr14"].rolling(14).std().rolling(50).std()
    sar, trend = parabolic_sar(df)
    f["sar"], f["sar_trend"] = sar, trend
    f["trend_age"] = trend_age(trend)
    hour, weekday, date = utc_parts(df["timestamp"])
    f["hour"], f["weekday"], f["date"] = hour, weekday, date
    f.update({f"piv_{k}": v for k, v in daily_prior_levels(df, date).items()})
    f["or_utc_high"], f["or_utc_low"] = opening_range_levels(df, date, hour, target_hour=0)
    f["or_us_high"], f["or_us_low"] = opening_range_levels(df, date, hour, target_hour=13)
    f["funding"] = funding_rate_series.reindex(df.index)
    f["funding_z"] = zscore(f["funding"], 720)
    if btc_close_aligned is not None:
        f["btc_close"] = btc_close_aligned.reindex(df.index)
        f["btc_ret1"] = f["btc_close"].pct_change()
        f["alt_btc_ratio"] = df["close"] / f["btc_close"]
        f["alt_btc_ratio_ret24"] = f["alt_btc_ratio"].pct_change(24)
        f["alt_btc_ratio_z"] = zscore(f["alt_btc_ratio"], 200)
        f["btc_corr50"] = df["close"].pct_change().rolling(50).corr(f["btc_close"].pct_change())
    return f


def funding_change_points(funding_rate_series):
    s = funding_rate_series
    change = s.ne(s.shift(1)) & s.notna()
    return np.where(change.values)[0]


# ===========================================================================
# Signal registry: signal_key -> fn(df, f) -> dict(side -> bool Series)
# ===========================================================================

SIGNAL_REGISTRY = {}


def register(key):
    def deco(fn):
        SIGNAL_REGISTRY[key] = fn
        return fn
    return deco


@register("bb_squeeze_breakout")
def _sig(df, f):
    squeeze = f["bb_bw"].rolling(100).apply(lambda x: (x <= x[-1]).sum() / len(x) * 100.0, raw=True) <= 20
    sq_prev = squeeze.shift(1).fillna(False)
    return {"long": sq_prev & (df["close"] > f["bb_up"]),
            "short": sq_prev & (df["close"] < f["bb_lo"])}


@register("atr_contraction_breakout")
def _sig(df, f):
    contr = (f["atr_pctrank100"] < 20).shift(1).fillna(False)
    prior_high = df["high"].shift(1).rolling(20).max()
    prior_low = df["low"].shift(1).rolling(20).min()
    return {"long": contr & (df["close"] > prior_high),
            "short": contr & (df["close"] < prior_low)}


@register("keltner_squeeze_breakout")
def _sig(df, f):
    inside = (df["close"] < f["kc_up"]) & (df["close"] > f["kc_lo"])
    inside_10 = inside.rolling(10).sum() >= 9
    inside_prev = inside_10.shift(1).fillna(False)
    return {"long": inside_prev & (df["close"] > f["kc_up"]),
            "short": inside_prev & (df["close"] < f["kc_lo"])}


@register("ttm_squeeze_breakout")
def _sig(df, f):
    squeeze_on = (f["bb_up"] < f["kc_up"]) & (f["bb_lo"] > f["kc_lo"])
    sq_prev = squeeze_on.shift(1).fillna(False)
    return {"long": sq_prev & (df["close"] > f["bb_up"]),
            "short": sq_prev & (df["close"] < f["bb_lo"])}


@register("vol_cone_low_extreme")
def _sig(df, f):
    thresh = f["rv24"].rolling(500).quantile(0.05)
    extreme_prev = (f["rv24"] <= thresh).shift(1).fillna(False)
    return {"long": extreme_prev & (df["close"] > df["high"].shift(1))}


@register("bb_pctb_exhaustion")
def _sig(df, f):
    vol5 = sma(df["volume"], 5)
    declining = vol5 < vol5.shift(5)
    return {"long": (df["close"] < f["bb_lo"]) & declining,
            "short": (df["close"] > f["bb_up"]) & declining}


@register("volume_spike_continuation")
def _sig(df, f):
    spike = df["volume"] > 3 * sma(df["volume"], 20)
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    loc = (df["close"] - df["low"]) / rng
    return {"long": spike & (loc > 0.667), "short": spike & (loc < 0.333)}


@register("volume_spike_fade")
def _sig(df, f):
    spike = df["volume"] > 3 * sma(df["volume"], 20)
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    body = (df["close"] - df["open"]).abs() / rng
    small_body = body < 0.25
    is_low = df["close"] <= df["close"].rolling(20).min()
    is_high = df["close"] >= df["close"].rolling(20).max()
    return {"long": spike & small_body & is_low, "short": spike & small_body & is_high}


@register("climax_volume_fade")
def _sig(df, f):
    is_climax = df["volume"] >= df["volume"].rolling(50).max()
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    up_wick = (df["high"] - df[["open", "close"]].max(axis=1)) / rng
    lo_wick = (df[["open", "close"]].min(axis=1) - df["low"]) / rng
    return {"short": is_climax & (up_wick >= 0.5), "long": is_climax & (lo_wick >= 0.5)}


@register("updown_volume_pressure")
def _sig(df, f):
    up_vol = df["volume"].where(df["close"] > df["open"], 0.0)
    dn_vol = df["volume"].where(df["close"] < df["open"], 0.0)
    ratio = up_vol.rolling(20).sum() / dn_vol.rolling(20).sum().replace(0, np.nan)
    hi = ratio.rolling(200).quantile(0.9)
    lo = ratio.rolling(200).quantile(0.1)
    return {"long": ratio > hi, "short": ratio < lo}


@register("vwap_reversion")
def _sig(df, f):
    dev = (df["close"] - f["vwap24"]) / f["vwap24"]
    return {"short": dev > 0.02, "long": dev < -0.02}


@register("ema200_zscore_reversion")
def _sig(df, f):
    return {"short": f["ema200_z"] > 2, "long": f["ema200_z"] < -2}


@register("vwap_trend_continuation")
def _sig(df, f):
    slope = f["vwap24"].diff()
    flip_up = (slope > 0) & (slope.shift(1) <= 0)
    flip_dn = (slope < 0) & (slope.shift(1) >= 0)
    return {"long": flip_up & (df["close"] > f["vwap24"]),
            "short": flip_dn & (df["close"] < f["vwap24"])}


@register("rsi_regular_divergence")
def _sig(df, f):
    return {"long": pairwise_divergence(df["close"], f["rsi14"], 20, "low", "regular"),
            "short": pairwise_divergence(df["close"], f["rsi14"], 20, "high", "regular")}


@register("rsi_hidden_divergence")
def _sig(df, f):
    return {"long": pairwise_divergence(df["close"], f["rsi14"], 20, "low", "hidden"),
            "short": pairwise_divergence(df["close"], f["rsi14"], 20, "high", "hidden")}


@register("stoch_regular_divergence")
def _sig(df, f):
    return {"long": pairwise_divergence(df["close"], f["stoch14"], 20, "low", "regular"),
            "short": pairwise_divergence(df["close"], f["stoch14"], 20, "high", "regular")}


@register("rsi_extreme_threshold")
def _sig(df, f):
    was_low = f["rsi14"].shift(1) < 20
    was_high = f["rsi14"].shift(1) > 80
    return {"long": was_low & (f["rsi14"] >= 20), "short": was_high & (f["rsi14"] <= 80)}


@register("donchian20_breakout")
def _sig(df, f):
    up = df["high"].shift(1).rolling(20).max()
    lo = df["low"].shift(1).rolling(20).min()
    return {"long": df["close"] > up, "short": df["close"] < lo}


@register("donchian55_breakout")
def _sig(df, f):
    up = df["high"].shift(1).rolling(55).max()
    lo = df["low"].shift(1).rolling(55).min()
    return {"long": df["close"] > up, "short": df["close"] < lo}


@register("donchian_volume_confirmed")
def _sig(df, f):
    up = df["high"].shift(1).rolling(20).max()
    lo = df["low"].shift(1).rolling(20).min()
    vol_ok = df["volume"] > sma(df["volume"], 20)
    return {"long": (df["close"] > up) & vol_ok, "short": (df["close"] < lo) & vol_ok}


@register("utc_daily_or_breakout")
def _sig(df, f):
    return {"long": df["close"] > f["or_utc_high"], "short": df["close"] < f["or_utc_low"]}


@register("session_or_breakout_us")
def _sig(df, f):
    return {"long": df["close"] > f["or_us_high"], "short": df["close"] < f["or_us_low"]}


@register("funding_extreme_fade")
def _sig(df, f):
    return {"short": f["funding"] > 0.0005, "long": f["funding"] < -0.0005}


@register("funding_zscore_extreme_fade")
def _sig(df, f):
    return {"short": f["funding_z"] > 2, "long": f["funding_z"] < -2}


@register("funding_trend_momentum")
def _sig(df, f):
    idxs = funding_change_points(f["funding"])
    vals = f["funding"].values
    n = len(df)
    up = np.zeros(n, dtype=bool)
    dn = np.zeros(n, dtype=bool)
    for k in range(2, len(idxs)):
        i0, i1, i2 = idxs[k - 2], idxs[k - 1], idxs[k]
        v0, v1, v2 = vals[i0], vals[i1], vals[i2]
        if abs(v2) < 0.0005:
            if v0 < v1 < v2:
                up[i2] = True
            if v0 > v1 > v2:
                dn[i2] = True
    return {"long": pd.Series(up, index=df.index), "short": pd.Series(dn, index=df.index)}


@register("funding_settlement_gapfade")
def _sig(df, f):
    idxs = funding_change_points(f["funding"])
    n = len(df)
    up = np.zeros(n, dtype=bool)
    dn = np.zeros(n, dtype=bool)
    close = df["close"].values
    for i in idxs:
        if i == 0:
            continue
        chg = (close[i] - close[i - 1]) / close[i - 1]
        if chg > 0.003:
            dn[i] = True
        elif chg < -0.003:
            up[i] = True
    return {"long": pd.Series(up, index=df.index), "short": pd.Series(dn, index=df.index)}


@register("funding_not_overheated_momentum")
def _sig(df, f):
    is_high = df["close"] >= df["close"].rolling(20).max()
    return {"long": (f["funding"] > 0) & (f["funding"] < 0.00025) & is_high}


@register("funding_curve_steepness")
def _sig(df, f):
    diff = f["funding"].diff()
    thresh = diff.rolling(500).quantile(0.9)
    is_high = df["close"] > df["high"].shift(1)
    return {"long": (diff > thresh) & (diff > 0) & is_high}


@register("vwma_momentum")
def _sig(df, f):
    slope = f["vwma20"].diff()
    return {"long": (slope > 0) & (df["close"] > f["vwma20"]),
            "short": (slope < 0) & (df["close"] < f["vwma20"])}


@register("obv_breakout")
def _sig(df, f):
    obv_hi = f["obv"] >= f["obv"].rolling(20).max()
    obv_lo = f["obv"] <= f["obv"].rolling(20).min()
    price_hi = df["close"] >= df["close"].rolling(20).max()
    price_lo = df["close"] <= df["close"].rolling(20).min()
    return {"long": obv_hi.shift(1).fillna(False) & price_hi,
            "short": obv_lo.shift(1).fillna(False) & price_lo}


@register("vol_term_structure_fade")
def _sig(df, f):
    ratio = f["rv24"] / f["rv168"].replace(0, np.nan)
    inv = ratio > 1.5
    return {"short": inv, "long": inv}


@register("vol_of_vol_breakout")
def _sig(df, f):
    thresh = f["vol_of_vol"].rolling(200).quantile(0.9)
    spike_prev = (f["vol_of_vol"] > thresh).shift(1).fillna(False)
    return {"long": spike_prev & (df["close"] > df["high"].shift(1)),
            "short": spike_prev & (df["close"] < df["low"].shift(1))}


@register("streak_fade")
def _sig(df, f):
    up = df["close"] > df["close"].shift(1)
    grp_up = (~up).cumsum()
    streak_up = up.groupby(grp_up).cumcount() + 1
    streak_up = streak_up.where(up, 0)
    dn = df["close"] < df["close"].shift(1)
    grp_dn = (~dn).cumsum()
    streak_dn = dn.groupby(grp_dn).cumcount() + 1
    streak_dn = streak_dn.where(dn, 0)
    return {"short": streak_up >= 4, "long": streak_dn >= 4}


@register("streak_momentum")
def _sig(df, f):
    avg_rng = (df["high"] - df["low"]).rolling(20).mean()
    prior_up = (df["close"].shift(1) > df["close"].shift(2))
    prior_dn = (df["close"].shift(1) < df["close"].shift(2))
    prior_big = (df["high"].shift(1) - df["low"].shift(1)) > avg_rng.shift(1)
    return {"long": prior_up & prior_big, "short": prior_dn & prior_big}


@register("run_length_continuation")
def _sig(df, f):
    up = df["close"] > df["close"].shift(1)
    grp_up = (~up).cumsum()
    streak_up = (up.groupby(grp_up).cumcount() + 1).where(up, 0)
    dn = df["close"] < df["close"].shift(1)
    grp_dn = (~dn).cumsum()
    streak_dn = (dn.groupby(grp_dn).cumcount() + 1).where(dn, 0)
    rec_up = streak_up.rolling(50).max().shift(1)
    rec_dn = streak_dn.rolling(50).max().shift(1)
    return {"long": (streak_up >= rec_up) & up, "short": (streak_dn >= rec_dn) & dn}


@register("inside_bar_breakout")
def _sig(df, f):
    inside = (df["high"] < df["high"].shift(1)) & (df["low"] > df["low"].shift(1))
    inside_prev = inside.shift(1).fillna(False)
    ib_high = df["high"].shift(1).where(inside.shift(1), np.nan).ffill()
    ib_low = df["low"].shift(1).where(inside.shift(1), np.nan).ffill()
    return {"long": inside_prev & (df["close"] > ib_high),
            "short": inside_prev & (df["close"] < ib_low)}


@register("engulfing_continuation")
def _sig(df, f):
    bull_engulf = ((df["close"] > df["open"]) & (df["close"].shift(1) < df["open"].shift(1)) &
                   (df["close"] >= df["open"].shift(1)) & (df["open"] <= df["close"].shift(1)))
    bear_engulf = ((df["close"] < df["open"]) & (df["close"].shift(1) > df["open"].shift(1)) &
                   (df["close"] <= df["open"].shift(1)) & (df["open"] >= df["close"].shift(1)))
    uptrend = df["close"] > f["ema55"]
    downtrend = df["close"] < f["ema55"]
    return {"long": bull_engulf & uptrend, "short": bear_engulf & downtrend}


@register("three_bar_thrust")
def _sig(df, f):
    up = df["close"] > df["close"].shift(1)
    rng = df["high"] - df["low"]
    up3 = up & up.shift(1) & up.shift(2)
    inc_rng = (rng > rng.shift(1)) & (rng.shift(1) > rng.shift(2))
    dn = df["close"] < df["close"].shift(1)
    dn3 = dn & dn.shift(1) & dn.shift(2)
    return {"long": up3 & inc_rng, "short": dn3 & inc_rng}


@register("marubozu_breakout")
def _sig(df, f):
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    body = (df["close"] - df["open"]).abs() / rng
    maru = body >= 0.9
    bull = maru & (df["close"] > df["open"])
    bear = maru & (df["close"] < df["open"])
    return {"long": bull.shift(1).fillna(False), "short": bear.shift(1).fillna(False)}


@register("pivot_s1_bounce")
def _sig(df, f):
    return {"long": (df["low"] <= f["piv_S1"]) & (df["close"] > f["piv_S1"])}


@register("pivot_r1_reject")
def _sig(df, f):
    return {"short": (df["high"] >= f["piv_R1"]) & (df["close"] < f["piv_R1"])}


@register("camarilla_breakout")
def _sig(df, f):
    return {"long": df["close"] > f["piv_H3"], "short": df["close"] < f["piv_L3"]}


@register("woodie_midpoint_reversion")
def _sig(df, f):
    return {"long": (df["low"] <= f["piv_midw"]) & (df["close"] > f["piv_P"])}


@register("ema_slope_filtered_cross")
def _sig(df, f):
    cross_up = (f["ema9"] > f["ema21"]) & (f["ema9"].shift(1) <= f["ema21"].shift(1))
    cross_dn = (f["ema9"] < f["ema21"]) & (f["ema9"].shift(1) >= f["ema21"].shift(1))
    slope9 = f["ema9"].diff()
    slope21 = f["ema21"].diff()
    return {"long": cross_up & (slope9 > 0) & (slope21 > 0),
            "short": cross_dn & (slope9 < 0) & (slope21 < 0)}


@register("ma_ribbon_pullback")
def _sig(df, f):
    bull = (f["ema9"] > f["ema21"]) & (f["ema21"] > f["ema55"])
    bear = (f["ema9"] < f["ema21"]) & (f["ema21"] < f["ema55"])
    touch_up = (df["low"] <= f["ema21"]) & (df["close"] > f["ema21"])
    touch_dn = (df["high"] >= f["ema21"]) & (df["close"] < f["ema21"])
    return {"long": bull & touch_up, "short": bear & touch_dn}


@register("ma_compression_expansion")
def _sig(df, f):
    spread = ((f["ema9"] - f["ema55"]).abs() / df["close"])
    compressed = spread.rolling(100).apply(lambda x: x[-1] <= x.min() * 1.05, raw=True).astype(bool)
    comp_prev = compressed.shift(1).fillna(False)
    widening = spread > spread.shift(1)
    bull = (f["ema9"] > f["ema21"]) & (df["close"] > f["ema55"])
    bear = (f["ema9"] < f["ema21"]) & (df["close"] < f["ema55"])
    return {"long": comp_prev & widening & bull, "short": comp_prev & widening & bear}


@register("price_volume_divergence")
def _sig(df, f):
    new_hi = df["close"] >= df["close"].rolling(20).max()
    new_lo = df["close"] <= df["close"].rolling(20).min()
    vol10 = sma(df["volume"], 10)
    declining = vol10 < vol10.shift(10)
    return {"short": new_hi & declining, "long": new_lo & declining}


@register("cmf_divergence")
def _sig(df, f):
    price_slope20 = df["close"].diff(20)
    cmf_neg = (f["cmf20"] < 0) & (f["cmf20"].shift(1) >= 0)
    cmf_pos = (f["cmf20"] > 0) & (f["cmf20"].shift(1) <= 0)
    return {"short": cmf_neg & (price_slope20 >= 0), "long": cmf_pos & (price_slope20 <= 0)}


@register("ad_line_divergence")
def _sig(df, f):
    ad_slope = f["ad_line"].diff(20)
    price_slope = df["close"].diff(20)
    ad_neg_flip = (ad_slope < 0) & (ad_slope.shift(1) >= 0)
    ad_pos_flip = (ad_slope > 0) & (ad_slope.shift(1) <= 0)
    return {"short": ad_neg_flip & (price_slope > 0), "long": ad_pos_flip & (price_slope < 0)}


@register("btc_relative_strength_momentum")
def _sig(df, f):
    if "alt_btc_ratio_ret24" not in f:
        return {}
    r = f["alt_btc_ratio_ret24"]
    hi = r.rolling(200).quantile(0.8)
    lo = r.rolling(200).quantile(0.2)
    return {"long": r > hi, "short": r < lo}


@register("btc_relative_strength_reversion")
def _sig(df, f):
    if "alt_btc_ratio_z" not in f:
        return {}
    z = f["alt_btc_ratio_z"]
    return {"short": z > 2.5, "long": z < -2.5}


@register("btc_lead_lag_momentum")
def _sig(df, f):
    if "btc_ret1" not in f:
        return {}
    r = f["btc_ret1"]
    return {"long": r > 0.01, "short": r < -0.01}


@register("session_hour_seasonality_fade")
def _sig(df, f):
    thin_hour = f["hour"].isin([2, 3, 4])
    rng = df["high"] - df["low"]
    avg_rng20 = rng.rolling(20).mean()
    outsized = rng > 1.5 * avg_rng20
    up_move = df["close"] > df["open"]
    return {"long": thin_hour & outsized & ~up_move, "short": thin_hour & outsized & up_move}


@register("session_hour_seasonality_momentum")
def _sig(df, f):
    busy_hour = f["hour"].isin([13, 14, 15, 16])
    prior4_high = df["high"].shift(1).rolling(4).max()
    return {"long": busy_hour & (df["close"] > prior4_high)}


@register("weekend_low_liquidity_reversion")
def _sig(df, f):
    is_weekend = f["weekday"].isin([5, 6])
    dev = (df["close"] - sma(df["close"], 20)) / f["atr14"].replace(0, np.nan)
    return {"long": is_weekend & (dev < -1.5), "short": is_weekend & (dev > 1.5)}


@register("mtf_momentum_alignment")
def _sig(df, f):
    roc_1h = df["close"].pct_change(10)
    roc_4h_equiv = df["close"].pct_change(40)
    return {"long": (roc_1h > 0) & (roc_4h_equiv > 0)}


@register("wick_sweep_high_fade")
def _sig(df, f):
    prior_max = df["high"].shift(1).rolling(20).max()
    return {"short": (df["high"] > prior_max) & (df["close"] < prior_max)}


@register("wick_sweep_low_fade")
def _sig(df, f):
    prior_min = df["low"].shift(1).rolling(20).min()
    return {"long": (df["low"] < prior_min) & (df["close"] > prior_min)}


@register("prior_day_high_sweep_reject")
def _sig(df, f):
    return {"short": (df["high"] > f["piv_prior_high"]) & (df["close"] < f["piv_prior_high"])}


@register("prior_day_low_sweep_reject")
def _sig(df, f):
    return {"long": (df["low"] < f["piv_prior_low"]) & (df["close"] > f["piv_prior_low"])}


@register("zscore_short_window_reversion")
def _sig(df, f):
    return {"short": f["z10"] > 2.2, "long": f["z10"] < -2.2}


@register("rolling_rank_extreme_reversion")
def _sig(df, f):
    return {"short": f["rank50"] > 97, "long": f["rank50"] < 3}


@register("atr_norm_momentum")
def _sig(df, f):
    # 10-bar price change expressed in units of ATR(14) ("how many ATRs did
    # price move in the last 10 bars"), NOT the same as a plain pct return.
    norm = (df["close"] - df["close"].shift(10)) / f["atr14"].replace(0, np.nan)
    return {"long": norm > 3, "short": norm < -3}


@register("atr_norm_contrarian_fade")
def _sig(df, f):
    norm = (df["close"] - df["close"].shift(10)) / f["atr14"].replace(0, np.nan)
    return {"short": norm > 3, "long": norm < -3}


@register("parabolic_exhaustion_reversal")
def _sig(df, f):
    flip_dn = (f["sar_trend"] == -1) & (f["sar_trend"].shift(1) == 1)
    flip_up = (f["sar_trend"] == 1) & (f["sar_trend"].shift(1) == -1)
    long_trend = f["trend_age"].shift(1) >= 30
    return {"short": flip_dn & long_trend, "long": flip_up & long_trend}


@register("rsi_extreme_rare_exhaustion")
def _sig(df, f):
    return {"short": f["rsi14"] > 90, "long": f["rsi14"] < 10}


@register("decorrelation_spike_fade")
def _sig(df, f):
    if "btc_corr50" not in f:
        return {}
    decorr = f["btc_corr50"] < f["btc_corr50"].rolling(200).quantile(0.2)
    alt_ret24 = df["close"].pct_change(24)
    btc_ret24 = f["btc_close"].pct_change(24)
    outperf = alt_ret24 > btc_ret24
    underperf = alt_ret24 < btc_ret24
    return {"short": decorr & outperf, "long": decorr & underperf}


@register("clv_streak_continuation")
def _sig(df, f):
    pos = f["clv"] > 0.5
    neg = f["clv"] < -0.5
    pos3 = pos & pos.shift(1) & pos.shift(2)
    neg3 = neg & neg.shift(1) & neg.shift(2)
    return {"long": pos3, "short": neg3}


# ===========================================================================
# Backtest engine
# ===========================================================================

def simulate_idea(df, atr_arr, signal_bool, side):
    """Vectorized-ish forward scan; returns array of net bps per trade."""
    n = len(df)
    high = df["high"].values
    low = df["low"].values
    close = df["open"].values  # entries use OPEN; reuse var name for brevity below
    open_ = df["open"].values
    sig_idx = np.where(signal_bool.fillna(False).values)[0]
    trades = []
    for i in sig_idx:
        entry_idx = i + 1
        if entry_idx >= n:
            continue
        stop_dist = STOP_ATR_MULT * atr_arr[i]
        if not np.isfinite(stop_dist) or stop_dist <= 0:
            continue
        entry_price = open_[entry_idx]
        window_end = min(entry_idx + MAX_HOLD_BARS, n - 1)
        h = high[entry_idx:window_end + 1]
        l = low[entry_idx:window_end + 1]
        if side == "long":
            target_price = entry_price + TARGET_R_MULT * stop_dist
            stop_price = entry_price - stop_dist
            hit_target = np.where(h >= target_price)[0]
            hit_stop = np.where(l <= stop_price)[0]
        else:
            target_price = entry_price - TARGET_R_MULT * stop_dist
            stop_price = entry_price + stop_dist
            hit_target = np.where(h <= target_price)[0] if False else np.where(l <= target_price)[0]
            hit_stop = np.where(h >= stop_price)[0]
        t_first = hit_target[0] if len(hit_target) else None
        s_first = hit_stop[0] if len(hit_stop) else None
        if s_first is not None and (t_first is None or s_first <= t_first):
            R = -1.0
        elif t_first is not None:
            R = TARGET_R_MULT
        else:
            exit_price = close[window_end] if window_end < n else entry_price
            exit_price = df["close"].values[window_end]
            raw = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
            R = raw / stop_dist
        risk_pct = stop_dist / entry_price
        raw_bps = R * risk_pct * 10000.0
        net_bps = raw_bps - ROUNDTRIP_COST_BPS
        trades.append(net_bps)
    return np.array(trades)


def metrics_for(trade_bps):
    n_trades = len(trade_bps)
    if n_trades == 0:
        return dict(n_trades=0, win_rate=np.nan, profit_factor=np.nan,
                    expectancy_bps=np.nan, rough_sharpe=np.nan, composite_score=0.0)
    wins = trade_bps[trade_bps > 0]
    losses = trade_bps[trade_bps <= 0]
    win_rate = len(wins) / n_trades
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (np.inf if gross_win > 0 else np.nan)
    expectancy_bps = trade_bps.mean()
    sd = trade_bps.std(ddof=1) if n_trades > 1 else np.nan
    rough_sharpe = (expectancy_bps / sd) if sd and sd > 0 else np.nan
    reliability_penalty = min(1.0, n_trades / 30.0)
    if not np.isfinite(profit_factor):
        pf_penalty = 1.0
    elif profit_factor <= 0:
        pf_penalty = 0.0
    else:
        pf_penalty = min(1.0, profit_factor)
    composite = expectancy_bps * math.log(1 + n_trades) * reliability_penalty * pf_penalty
    return dict(n_trades=n_trades, win_rate=win_rate, profit_factor=profit_factor,
                expectancy_bps=expectancy_bps, rough_sharpe=rough_sharpe,
                composite_score=composite)


# ===========================================================================
# Main
# ===========================================================================

def build_funding_series(funding_dict, timestamps):
    if not funding_dict:
        return pd.Series(np.nan, index=range(len(timestamps)))
    items = sorted(funding_dict.items())
    f_ts = np.array([t for t, _ in items])
    f_rate = np.array([ev.rate for _, ev in items])
    idx = np.searchsorted(f_ts, timestamps, side="right") - 1
    rate = np.where(idx >= 0, f_rate[np.clip(idx, 0, len(f_rate) - 1)], np.nan)
    return pd.Series(rate, index=range(len(timestamps)))


def load_all():
    raw = {}
    for symbol, bars, funding in iter_train_bars(TIMEFRAME):
        if symbol not in SYMBOLS or not bars:
            continue
        df = pd.DataFrame({
            "timestamp": [b.timestamp for b in bars],
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }).sort_values("timestamp").reset_index(drop=True)
        if len(df) > MAX_BARS:
            df = df.iloc[-MAX_BARS:].reset_index(drop=True)
        fseries = build_funding_series(funding, df["timestamp"].values)
        raw[symbol] = (df, fseries)
    return raw


def main():
    print("Loading bars for symbols:", SYMBOLS)
    raw = load_all()
    missing = [s for s in SYMBOLS if s not in raw]
    if missing:
        print("WARNING: missing symbols (no data):", missing)

    btc_df = raw.get("BTCUSDT", (None, None))[0]

    feats = {}
    for symbol, (df, fseries) in raw.items():
        btc_aligned = None
        if symbol != "BTCUSDT" and btc_df is not None:
            merged = pd.merge(df[["timestamp"]], btc_df[["timestamp", "close"]],
                               on="timestamp", how="left", suffixes=("", "_btc"))
            btc_aligned = merged["close"].reset_index(drop=True)
            btc_aligned.index = df.index
        feats[symbol] = compute_features(df, fseries, btc_aligned)
        print(f"  features ready: {symbol} ({len(df)} bars)")

    catalog = build_catalog()
    implemented = [r for r in catalog if r["implemented"]]
    print(f"\nTotal ideas: {len(catalog)}; implemented/backtested this pass: {len(implemented)}")

    results = []
    for row in implemented:
        key = row["signal_key"]
        side = row["side"]
        fn = SIGNAL_REGISTRY.get(key)
        if fn is None:
            print(f"  !! no signal fn for {key}, skipping {row['idea_id']}")
            continue
        all_bps = []
        for symbol, (df, fseries) in raw.items():
            f = feats[symbol]
            try:
                sigs = fn(df, f)
            except Exception as e:  # pragma: no cover
                print(f"  !! error in {key} for {symbol}: {e}")
                continue
            sig = sigs.get(side)
            if sig is None:
                continue
            atr_arr = f["atr14"].values
            bps = simulate_idea(df, atr_arr, sig, side)
            if len(bps):
                all_bps.append(bps)
        trade_bps = np.concatenate(all_bps) if all_bps else np.array([])
        m = metrics_for(trade_bps)
        m["idea_id"] = row["idea_id"]
        results.append(m)

    results.sort(key=lambda r: r["idea_id"])
    write_outputs(catalog, results)
    print("\nDone.")


def write_outputs(catalog, results):
    out_dir = HERE

    # IDEAS.csv
    ideas_path = out_dir / "IDEAS.csv"
    with open(ideas_path, "w") as fh:
        fh.write(f"# {LABEL}\n")
        fh.write("# ~167 proposed lane-A (non-orderblock) crypto microstructure ideas, "
                 "ordered by prior_rank ascending (1=highest qualitative pre-run likelihood).\n")
        fh.write("idea_id,name,mechanism_one_liner,rationale_one_liner,prior_rank_note\n")
        for row in catalog:
            vals = [row["idea_id"], row["name"], row["mechanism_one_liner"],
                    row["rationale_one_liner"], row["prior_rank_note"]]
            fh.write(",".join('"' + str(v).replace('"', "'") + '"' for v in vals) + "\n")
    print(f"wrote {ideas_path}")

    # RESULTS.csv
    res_by_id = {r["idea_id"]: r for r in results}
    results_path = out_dir / "RESULTS.csv"
    with open(results_path, "w") as fh:
        fh.write(f"# {LABEL}\n")
        fh.write(f"# Backtested {len(results)} of 167 proposed ideas this pass "
                 f"(see screen.py / ideas_catalog.py docstrings for which were skipped and why).\n")
        fh.write("# composite_score = expectancy_bps * ln(1+n_trades) * reliability_penalty * pf_penalty\n")
        fh.write("#   reliability_penalty = min(1.0, n_trades/30); "
                 "pf_penalty = 0.0 if profit_factor<=0 else min(1.0, profit_factor)\n")
        fh.write("idea_id,n_trades,win_rate,profit_factor,expectancy_bps,rough_sharpe,composite_score\n")
        for row in catalog:
            r = res_by_id.get(row["idea_id"])
            if r is None:
                continue
            fh.write(",".join(str(x) for x in [
                r["idea_id"], r["n_trades"],
                _fmt(r["win_rate"]), _fmt(r["profit_factor"]),
                _fmt(r["expectancy_bps"]), _fmt(r["rough_sharpe"]), _fmt(r["composite_score"]),
            ]) + "\n")
    print(f"wrote {results_path}")

    # RANKED_TOP20.md
    name_by_id = {row["idea_id"]: row for row in catalog}
    ranked = sorted(results, key=lambda r: (r["composite_score"] if np.isfinite(r["composite_score"]) else -1e18),
                     reverse=True)
    top20 = ranked[:20]
    md_path = out_dir / "RANKED_TOP20.md"
    with open(md_path, "w") as fh:
        fh.write(f"# {LABEL}\n\n")
        fh.write("This is an exploratory screen only: no look-ahead-bias audit, no "
                 "multiple-testing correction, no walk-forward validation. Not "
                 "G-eligible, not added to any real ledger, no promotion without "
                 "separate formal preregistration + synthetic tests + "
                 "resource-gated TRAIN run.\n\n")
        fh.write(f"Backtested on {len(SYMBOLS)} symbols ({', '.join(SYMBOLS)}), "
                 f"timeframe={TIMEFRAME}, up to {MAX_BARS} most-recent bars/symbol. "
                 f"Exit convention: {STOP_ATR_MULT}x ATR14 stop, {TARGET_R_MULT}R target, "
                 f"{MAX_HOLD_BARS}-bar max hold, {ROUNDTRIP_COST_BPS}bp round-trip cost.\n\n")
        fh.write("## Top 20 by composite_score\n\n")
        for rank, r in enumerate(top20, start=1):
            row = name_by_id[r["idea_id"]]
            fh.write(f"### {rank}. {row['idea_id']} -- {row['name']}\n\n")
            fh.write(f"- composite_score: {_fmt(r['composite_score'])}\n")
            fh.write(f"- n_trades: {r['n_trades']}, win_rate: {_fmt(r['win_rate'])}, "
                     f"profit_factor: {_fmt(r['profit_factor'])}, "
                     f"expectancy_bps: {_fmt(r['expectancy_bps'])}, "
                     f"rough_sharpe: {_fmt(r['rough_sharpe'])}\n")
            fh.write(f"- mechanism: {row['mechanism_one_liner']}\n")
            fh.write(f"- rationale: {row['rationale_one_liner']}\n")
            fh.write(f"- prior rank note: {row['prior_rank_note']}\n")
            note = "Scored well" if (np.isfinite(r["composite_score"]) and r["composite_score"] > 0) else "Scored poorly/near-zero"
            fh.write(f"- post-hoc note: {note} on this cheap screen "
                     f"({r['n_trades']} trades across the {len(SYMBOLS)}-symbol subset); "
                     "see caveats above before drawing any conclusion.\n\n")
    print(f"wrote {md_path}")


def _fmt(x):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return ""
    if isinstance(x, float):
        return f"{x:.6g}"
    return str(x)


if __name__ == "__main__":
    main()
