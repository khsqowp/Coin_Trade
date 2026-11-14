"""Coin short-term CHART PATTERNS - deterministic detectors, no images, no LLM (long only).

Pivot confirmation delay: a pivot high/low at bar i needs K=5 bars on each side, so it only becomes known at bar i+K.
All detectors use confirmed pivots only => no look-ahead (verified by the truncation test and unit tests).
Detectors (entry = OR of the enabled patterns; disabling a rule removes that pattern):
  sr_breakout_retest : close breaks above the last confirmed pivot-high (resistance) by 0.2%, then within 15 bars a bar
                       dips to the level (low <= R*1.003) and closes green above R  -> entry on the retest hold.
  double_bottom      : two confirmed pivot lows within 1% (8..80 bars apart); entry when close crosses above the neckline
                       (highest high between them) within 40 bars of the second low.
  ascending_triangle : last 3 confirmed pivot highs flat (within 0.6%) and last 3 pivot lows strictly rising; entry on close
                       above the flat top within 40 bars of the last pivot.
  bull_flag          : pole (>= max(3%, 6*ATR%)) followed by a 6-bar shallow tight consolidation (retrace <= 50% of the pole);
                       entry on close above the flag high.
Exits: double top (two flat pivot highs, close below the valley), close below the last confirmed pivot low (structure break),
ATRx3 trailing stop (protective), 60-bar time stop. Chart reading by images is deliberately NOT used."""
import numpy as np
import pandas as pd
from tp import ind, poolkit as pk

K = 5
META = {"id": "coin_chart_patterns", "family": "chart_pattern", "market": "crypto", "profile": "crypto_fast",
        "timeframes": ["15m", "1h"], "symbols": ["BTC/USDT", "ETH/USDT"]}
RULES = {"sr_breakout_retest": "resistance breakout followed by a successful retest",
         "double_bottom": "double bottom neckline breakout", "ascending_triangle": "flat top + rising lows breakout",
         "bull_flag": "pole then tight shallow flag, breakout above flag high",
         "bearish_pattern_exit": "double top confirmed by a close below its valley",
         "structure_break_exit": "close below the last confirmed pivot low",
         "atr_trail_stop": "exit when close < highest close - 3*ATR(14)"}
PROTECTIVE = {"atr_trail_stop"}
RULE_KINDS = {"sr_breakout_retest": "entry", "double_bottom": "entry", "ascending_triangle": "entry", "bull_flag": "entry",
              "bearish_pattern_exit": "exit", "structure_break_exit": "exit", "atr_trail_stop": "protective"}


def pivots(h, l):
    """Boolean arrays: pivot_hi[i] / pivot_lo[i], known only from bar i+K onward (NaN-padded => False near the end)."""
    hs, ls = pd.Series(h), pd.Series(l)
    prior_hi = hs.shift(1).rolling(K, min_periods=K).max()
    next_hi = hs[::-1].shift(1).rolling(K, min_periods=K).max()[::-1]
    prior_lo = ls.shift(1).rolling(K, min_periods=K).min()
    next_lo = ls[::-1].shift(1).rolling(K, min_periods=K).min()[::-1]
    return ((hs > prior_hi) & (hs >= next_hi)).values, ((ls < prior_lo) & (ls <= next_lo)).values


def generate_signals(df, disabled=frozenset()):
    disabled = frozenset(disabled)
    n = len(df)
    o, h, l, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    atr = ind.atr(df, 14).values
    ph, pl = pivots(h, l)
    hs, ls = pd.Series(h), pd.Series(l)
    # bull-flag helpers (vectorised, causal)
    fl_hi = hs.shift(1).rolling(6, min_periods=6).max().values
    fl_lo = ls.shift(1).rolling(6, min_periods=6).min().values
    pole_top = hs.shift(7).rolling(14, min_periods=14).max().values
    pole_bot = ls.shift(15).rolling(14, min_periods=14).min().values
    entry = np.zeros(n, bool)
    bear = np.zeros(n, bool)
    struct = np.zeros(n, bool)
    hi_list, lo_list = [], []                      # confirmed (index, price)
    pending = None                                 # (R, break_bar)
    used = set()
    cool = -10
    for j in range(n):
        i = j - K
        if i >= 0:
            if ph[i]:
                hi_list.append((i, h[i]))
            if pl[i]:
                lo_list.append((i, l[i]))
        fire = False
        if "sr_breakout_retest" not in disabled and hi_list:
            if pending is not None:
                R, jb = pending
                if j - jb > 15 or c[j] < R * 0.99:
                    pending = None
                elif j > jb and l[j] <= R * 1.003 and c[j] > R and c[j] > o[j]:
                    fire, pending = True, None
            if pending is None and j > 0:
                R = hi_list[-1][1]
                if j - hi_list[-1][0] <= 150 and c[j] > R * 1.002 and c[j - 1] <= R * 1.002:
                    pending = (R, j)
        if "double_bottom" not in disabled and len(lo_list) >= 2:
            (a, la), (b, lb) = lo_list[-2], lo_list[-1]
            if 8 <= b - a <= 80 and abs(lb / la - 1) < 0.01 and j - b <= 40 and (a, b, "db") not in used:
                neck = h[a:b + 1].max()
                if c[j] > neck and c[j - 1] <= neck and neck / lb - 1 >= 0.015:
                    fire = True
                    used.add((a, b, "db"))
        if "ascending_triangle" not in disabled and len(hi_list) >= 3 and len(lo_list) >= 3:
            t3 = [p for _, p in hi_list[-3:]]
            l3 = [p for _, p in lo_list[-3:]]
            top = max(t3)
            key = (hi_list[-1][0], lo_list[-1][0], "tri")
            if (max(t3) / min(t3) - 1 < 0.006 and l3[0] < l3[1] < l3[2] and j - max(hi_list[-1][0], lo_list[-1][0]) <= 40
                    and c[j] > top * 1.001 and c[j - 1] <= top * 1.001 and key not in used):
                fire = True
                used.add(key)
        if "bull_flag" not in disabled and j >= 40 and fl_hi[j] == fl_hi[j] and pole_top[j] == pole_top[j] and pole_bot[j] == pole_bot[j]:
            pole = pole_top[j] - pole_bot[j]
            if pole > 0 and pole / pole_bot[j] >= max(0.03, 6 * atr[j] / c[j] if atr[j] == atr[j] else 0.03):
                if (pole_top[j] - fl_lo[j]) <= 0.5 * pole and (fl_hi[j] - fl_lo[j]) <= 0.6 * pole \
                        and c[j] > fl_hi[j] and c[j - 1] <= fl_hi[j]:
                    fire = True
        if fire and j - cool >= 10:
            entry[j] = True
            cool = j
        if "bearish_pattern_exit" not in disabled and len(hi_list) >= 2:
            (a, pa), (b, pb) = hi_list[-2], hi_list[-1]
            if 8 <= b - a <= 80 and abs(pb / pa - 1) < 0.01 and j - b <= 40:
                valley = l[a:b + 1].min()
                if c[j] < valley and c[j - 1] >= valley:
                    bear[j] = True
        if "structure_break_exit" not in disabled and lo_list and c[j] < lo_list[-1][1]:
            struct[j] = True
    sig = pk.position_loop(entry, c, atr, bear | struct, trail_mult=None if "atr_trail_stop" in disabled else 3.0, max_bars=60)
    return pk.to_series(sig, df)
