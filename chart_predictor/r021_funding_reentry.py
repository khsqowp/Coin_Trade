"""Causal signal primitives for the exploratory R021 funding-reentry trial."""
from __future__ import annotations

import numpy as np


def funding_extreme_side(prior_rates: np.ndarray, current_rate: float, min_history: int = 60) -> int | None:
    """Return contrarian side for a trailing-history funding extreme.

    The current settlement is compared with quantiles computed exclusively
    from earlier settlements. Negative lower-tail funding maps to long (+1),
    positive upper-tail funding to short (-1); otherwise there is no signal.
    """
    prior = np.asarray(prior_rates, dtype=np.float64)
    prior = prior[np.isfinite(prior)]
    if not np.isfinite(current_rate) or min_history < 1:
        raise ValueError("funding rate and minimum history must be valid")
    if prior.size < min_history:
        return None
    lower, upper = np.quantile(prior, [0.1, 0.9], method="linear")
    if current_rate <= lower:
        return 1
    if current_rate >= upper:
        return -1
    return None


def macro_side(close: float, ema: float) -> int:
    """Direction of the last fully completed macro bar; 0 means neutral."""
    if not np.isfinite(close) or not np.isfinite(ema):
        return 0
    return 1 if close > ema else -1 if close < ema else 0


def first_reentry_breakout(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    event_index: int,
    side: int,
    max_wait: int = 20,
    pullback_atr: float = 0.5,
    breakout_bars: int = 3,
) -> int | None:
    """Find first close-break after a distinct ATR-sized post-event pullback.

    Candidate bars are fully closed. The pullback must occur on a bar before
    the breakout bar; the breakout close must exceed/fall below the prior
    ``breakout_bars`` candle extremes. The event bar is the price reference.
    """
    arrays = [np.asarray(x, dtype=np.float64) for x in (high, low, close, atr)]
    if len({x.size for x in arrays}) != 1 or side not in (-1, 1):
        raise ValueError("OHLC/ATR lengths must match and side must be -1 or +1")
    if max_wait < 1 or breakout_bars < 1 or pullback_atr <= 0:
        raise ValueError("window and pullback parameters must be positive")
    high, low, close, atr = arrays
    if event_index < 0 or event_index >= close.size:
        raise ValueError("event_index is outside the bar arrays")
    reference_atr = atr[event_index]
    reference_price = close[event_index]
    if not np.isfinite(reference_atr) or reference_atr <= 0 or not np.isfinite(reference_price):
        return None

    pulled_back = False
    stop = min(close.size, event_index + max_wait + 1)
    for i in range(event_index + 1, stop):
        if not pulled_back:
            pulled_back = (low[i] <= reference_price - pullback_atr * reference_atr
                           if side == 1 else high[i] >= reference_price + pullback_atr * reference_atr)
            continue
        left = i - breakout_bars
        if left <= event_index:
            continue
        if side == 1 and close[i] > np.max(high[left:i]):
            return i
        if side == -1 and close[i] < np.min(low[left:i]):
            return i
    return None
