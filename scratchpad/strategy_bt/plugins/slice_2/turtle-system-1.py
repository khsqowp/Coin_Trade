"""Archived spec turtle-system-1 (daily): 20-day breakout, 10-day exit, 2N stop, last-breakout-winner filter, 55-day fallback."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_lib as L
from common.indicators import atr

SPEC_ID = "turtle-system-1"
PARAMS = {"entry_n": 20, "exit_n": 10, "fallback_n": 55, "stop_mult": 2.0, "atr_n": 20}
PARAM_GRID = {"entry_n": [15, 20, 25], "exit_n": [7, 10, 14]}
TIMEFRAMES = ["1d"]
SIDES = "both"
IMPLEMENTED_FIELDS = ["entry_long", "entry_short", "exit", "stop_loss", "filters", "timeframes"]
DEVIATIONS = [
    "Breakouts are CLOSE-based (close > prior N-day high excl. current bar) with next-open fill; the original buys intrabar 'above' the level (harness has no stop-entry orders).",
    "Position sizing NOT implemented: no volatility-normalised units and no pyramiding (add 1 unit per 0.5N, max 4); fixed notional single unit. position_sizing field unimplemented. Material.",
    "N = Wilder-smoothed (seed SMA) 20-day true range via common.atr; stop = 2N from the fill price, N taken at the signal bar.",
    "Filter: a hypothetical 20-day-system trade stream is tracked independent of real trades (enter next open on 20-day breakout when hypothetical flat, exit at next open after close beyond the 10-day opposite channel or intrabar at 2N stop; winner = profit>0). A new 20-day entry is taken only if the previous completed hypothetical trade (either direction) was NOT a winner (or none exists). 55-day breakout (close-based) is always taken when flat (fallback).",
    "Hypothetical-trade fills ignore fees/slippage. Gap-through-stop in the hypothetical track fills at the open.",
    "20-day entries are event-based (only the bar that starts a hypothetical trade); 55-day entry is level-based while flat.",
    "Exit channels are close-based: long exit when close < prior exit_n-day low (signal exit, fills next open).",
]

def signals(df, entry_n=20, exit_n=10, fallback_n=55, stop_mult=2.0, atr_n=20):
    h = df.high.to_numpy(float); l = df.low.to_numpy(float); c = df.close.to_numpy(float); o = df.open.to_numpy(float)
    n = len(c); N = atr(h, l, c, int(atr_n))
    hh = L.prior_extreme(h, entry_n, "max"); ll = L.prior_extreme(l, entry_n, "min")
    hf = L.prior_extreme(h, fallback_n, "max"); lf = L.prior_extreme(l, fallback_n, "min")
    hx = L.prior_extreme(h, exit_n, "max"); lx_ = L.prior_extreme(l, exit_n, "min")
    le = np.zeros(n, bool); se = np.zeros(n, bool)
    pos = 0; pending = 0; pend_stop = np.nan; entry_px = np.nan; stop = np.nan; exit_pending = False
    last_win = None  # outcome of last completed hypothetical 20-day trade
    for i in range(n):
        # --- hypothetical track: fills happening on bar i
        if exit_pending:
            pnl = (o[i] - entry_px) * pos; last_win = pnl > 0; pos = 0; exit_pending = False
        if pending and pos == 0:
            pos = pending; entry_px = o[i]; stop = entry_px - pos * pend_stop; pending = 0
        if pos and not exit_pending:
            hit = (l[i] <= stop) if pos > 0 else (h[i] >= stop)
            if hit:
                px = o[i] if ((o[i] < stop) if pos > 0 else (o[i] > stop)) else stop
                last_win = (px - entry_px) * pos > 0; pos = 0
        # --- decisions at close of bar i
        if pos == 0 and not pending and np.isfinite(N[i]):
            d = 1 if (np.isfinite(hh[i]) and c[i] > hh[i]) else (-1 if (np.isfinite(ll[i]) and c[i] < ll[i]) else 0)
            if d:
                pending = d; pend_stop = stop_mult * N[i]
                if last_win is None or not last_win:
                    (le if d > 0 else se)[i] = True
        elif pos and not exit_pending:
            if (pos > 0 and np.isfinite(lx_[i]) and c[i] < lx_[i]) or (pos < 0 and np.isfinite(hx[i]) and c[i] > hx[i]):
                exit_pending = True
        if np.isfinite(hf[i]) and c[i] > hf[i]:
            le[i] = True
        if np.isfinite(lf[i]) and c[i] < lf[i]:
            se[i] = True
    lx = np.zeros(n, bool); sx = np.zeros(n, bool)
    ok = np.isfinite(lx_); lx[ok] = c[ok] < lx_[ok]
    ok = np.isfinite(hx); sx[ok] = c[ok] > hx[ok]
    return L.frame(df, le=le, se=se, lx=lx, sx=sx, atr_stop=stop_mult * N)
