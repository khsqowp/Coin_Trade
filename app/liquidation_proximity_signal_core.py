"""IMPORTANT DISCLOSED LIMITATION

These are estimated liquidation clusters from assumed leverage tiers, NOT
historical liquidations, open interest, exchange margin accounts or heatmaps.
Fixed maintenance margin 0.5% ignores tiered margin, fees, collateral and funding.
Daily OHLC swing anchors have equal weight; density is not position notional.
Signals use only completed bars; execution belongs to the next-open runner.
"""

import numpy as np
import pandas as pd

MAINTENANCE_MARGIN = 0.005
TIER_SETS = ((5, 10, 20), (25, 50, 100))


def clusters(frame: pd.DataFrame, window: int, tiers: tuple) -> pd.DataFrame:
    """Trailing 3-bar extrema, known at anchor close, expire after N calendar days.

    A trailing high >= prior two highs / low <= prior two lows is a causal swing.
    Log-price bins of 0.5% pool anchors; >=2 anchors form a dense cluster.
    Nearest cluster is measured by its arithmetic mean, on the proper price side.
    Assumed positions disappear after price has touched their liquidation level.
    A position anchored today can only be liquidated on a later bar.
    """
    if window not in (7, 14, 30) or not tiers or any(x <= 1 for x in tiers):
        raise ValueError("invalid window/leverage tiers")
    if not frame.index.is_monotonic_increasing or not frame.index.is_unique:
        raise ValueError("sorted unique calendar required")
    out = frame.copy()
    hi, lo, close = (frame[x].to_numpy(float) for x in ("High", "Low", "Close"))
    highs = frame.High >= frame.High.shift(1).rolling(2).max()
    lows = frame.Low <= frame.Low.shift(1).rolling(2).min()
    down: list[tuple[pd.Timestamp, float]] = []
    up: list[tuple[pd.Timestamp, float]] = []
    values = []
    width = np.log1p(0.005)
    for i, date in enumerate(frame.index):
        lower = date - pd.Timedelta(days=window - 1)
        down = [(d, p) for d, p in down if d >= lower and lo[i] > p]
        up = [(d, p) for d, p in up if d >= lower and hi[i] < p]
        if highs.iloc[i]:
            down.extend(
                (date, hi[i] * (1 - (1 - MAINTENANCE_MARGIN) / l)) for l in tiers
            )
        if lows.iloc[i]:
            up.extend((date, lo[i] * (1 + (1 - MAINTENANCE_MARGIN) / l)) for l in tiers)
        row: list[float | int] = []
        for anchors, direction in ((down, -1), (up, 1)):
            prices = np.array([p for _, p in anchors])
            if len(prices):
                bins = np.floor(np.log(prices) / width).astype(np.int64)
                ids, counts = np.unique(bins, return_counts=True)
                means = np.array([prices[bins == b].mean() for b in ids])
                dist = direction * (means / close[i] - 1) * 100
                valid = (counts >= 2) & (dist > 0)
                if valid.any():
                    candidates = np.flatnonzero(valid)
                    j = candidates[np.argmin(dist[valid])]
                    row.extend((float(dist[j]), int(counts[j])))
                    continue
            row.extend((np.nan, 0))
        values.append(row)
    out[["DOWN_DISTANCE", "DOWN_DENSITY", "UP_DISTANCE", "UP_DENSITY"]] = np.asarray(
        values, dtype=float
    ).reshape(-1, 4)
    return out


def find_signals(
    frame: pd.DataFrame,
    window: int = 14,
    tiers: tuple = TIER_SETS[0],
    threshold: float = 2.0,
) -> pd.DataFrame:
    """Completed-close downside proximity and upside next-open exit instructions."""
    if threshold not in (1.0, 2.0, 3.0, 5.0):
        raise ValueError("threshold outside predeclared grid")
    out = clusters(frame, window, tiers)
    out["SIGNAL"] = out.DOWN_DISTANCE.le(threshold)
    out["EXIT_SIGNAL"] = out.UP_DISTANCE.le(threshold)
    out["VOL_RATIO"] = (out.DOWN_DENSITY / (1 + out.DOWN_DISTANCE)).fillna(0.0)
    out["ATR14"] = 0.0
    out["STOP_LEVEL"] = 0.0
    return out
