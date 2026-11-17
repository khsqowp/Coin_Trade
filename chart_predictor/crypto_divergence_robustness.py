"""Causal divergence rules and preregistered robustness-test primitives.

Research-only: this module never submits orders or calls exchange APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from . import indicators


@dataclass(frozen=True)
class DivergenceSignal:
    index: int                 # confirmation candle, never the historical pivot anchor
    anchor: int
    side: str
    pivot_price: float
    oscillator_at_anchor: float


def divergence_signals(high, low, close, oscillator, lag=3, macro_direction=None):
    """Return regular divergence events at pivot confirmation, using anchor values.

    macro_direction is an optional {-1, 0, +1} series aligned to close; a signal
    is emitted only when the most recently closed higher-timeframe regime agrees.
    """
    h, l, c, osc = (np.asarray(x, dtype=float) for x in (high, low, close, oscillator))
    if not (len(h) == len(l) == len(c) == len(osc)):
        raise ValueError("OHLC and oscillator arrays must have equal lengths")
    if lag < 1:
        raise ValueError("lag must be positive")
    macro = np.ones(len(c), dtype=int) if macro_direction is None else np.asarray(macro_direction, dtype=int)
    if len(macro) != len(c):
        raise ValueError("macro_direction must align with candles")
    sh, sl = indicators.confirmed_swings(h, l, lag)
    out, lows, highs = [], [], []
    for i in range(len(c)):
        anchor = i - lag
        if np.isfinite(sl[i]) and np.isfinite(osc[anchor]):
            price, value = float(sl[i]), float(osc[anchor])
            if lows and price < lows[-1][1] and value > lows[-1][2] and macro[i] == 1:
                out.append(DivergenceSignal(i, anchor, "long", price, value))
            lows.append((anchor, price, value))
        if np.isfinite(sh[i]) and np.isfinite(osc[anchor]):
            price, value = float(sh[i]), float(osc[anchor])
            if highs and price > highs[-1][1] and value < highs[-1][2] and macro[i] == -1:
                out.append(DivergenceSignal(i, anchor, "short", price, value))
            highs.append((anchor, price, value))
    return out


def drawdown_pct(returns):
    """Compound per-trade fractional returns and return peak-to-trough MDD."""
    r = np.asarray(returns, dtype=float)
    if r.ndim != 1 or not np.all(np.isfinite(r)) or np.any(r <= -1):
        raise ValueError("returns must be finite 1-D fractional returns greater than -100%")
    equity = np.r_[1.0, np.cumprod(1.0 + r)]
    peak = np.maximum.accumulate(equity)
    return float(np.max(1.0 - equity / peak, initial=0.0) * 100.0)


def monte_carlo_reorder_mdd(net_r, *, risk_fraction=0.01, simulations=1000, seed=20261117):
    """Permute fixed net-R trades; report chronological and permutation MDDs.

    This preserves the observed outcome multiset and tests order risk only. It is
    not a model of changing distributions, serial dependence, or concurrency.
    """
    values = np.asarray(net_r, dtype=float)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("net_r must be a finite one-dimensional sequence")
    if not 0 < risk_fraction < 1 or simulations != 1000:
        raise ValueError("risk_fraction must be in (0,1); this preregistration requires 1000 permutations")
    chronological = drawdown_pct(values * risk_fraction)
    rng = np.random.default_rng(seed)
    samples = np.empty(simulations, dtype=float)
    for i in range(simulations):
        samples[i] = drawdown_pct(rng.permutation(values) * risk_fraction)
    return {
        "simulations": simulations,
        "seed": seed,
        "risk_fraction_per_trade": risk_fraction,
        "chronological_mdd_pct": chronological,
        "permuted_mdd_median_pct": float(np.quantile(samples, 0.50)),
        "permuted_mdd_p95_pct": float(np.quantile(samples, 0.95)),
        "permuted_mdd_max_pct": float(np.max(samples)),
    }


def walk_forward_windows(start_day, *, train_days=504, test_days=252, count=5):
    """Create five chronological day-based windows; boundaries are half-open."""
    if train_days != 504 or test_days != 252 or count != 5:
        raise ValueError("walk-forward geometry is frozen at 504/252 calendar days × 5 windows")
    windows = []
    for fold in range(count):
        train_start = start_day + fold * test_days
        train_end = train_start + train_days
        test_end = train_end + test_days
        windows.append({"fold": fold + 1, "train_start": train_start,
                        "train_end": train_end, "test_start": train_end,
                        "test_end": test_end})
    return windows


def plateau_summary(rows, *, min_neighbor_pass_fraction=0.80, max_neighbor_m2_gap=0.10):
    """Score a frozen rectangular parameter grid using one-step neighbors.

    Each row needs `params` (mapping), `m2`, `n`, `net_expectancy`, `resolved`.
    A cell passes only at M2>=0.80, n>=30, resolved=true and positive expectancy.
    """
    by_key = {tuple(sorted(row["params"].items())): row for row in rows}
    dimensions = sorted({k for row in rows for k in row["params"]})
    levels = {d: sorted({row["params"][d] for row in rows}) for d in dimensions}
    results = []
    for key, row in by_key.items():
        params = dict(key)
        neighbors = []
        for dim in dimensions:
            idx = levels[dim].index(params[dim])
            for adjacent in (idx - 1, idx + 1):
                if 0 <= adjacent < len(levels[dim]):
                    changed = dict(params)
                    changed[dim] = levels[dim][adjacent]
                    neighbor = by_key.get(tuple(sorted(changed.items())))
                    if neighbor is not None:
                        neighbors.append(neighbor)
        passing = [n for n in neighbors if n.get("resolved", False) and n.get("m2") is not None
                   and n["m2"] >= 0.80 and n["n"] >= 30
                   and n["net_expectancy"] > 0 and n.get("resolved", False)]
        fraction = len(passing) / len(neighbors) if neighbors else None
        valid_m2 = [n["m2"] for n in neighbors if n.get("resolved", False) and n.get("m2") is not None]
        median_m2 = float(np.median(valid_m2)) if valid_m2 else None
        robust = (row.get("resolved", False) and row.get("m2") is not None and row["m2"] >= 0.80 and row["n"] >= 30
                  and row["net_expectancy"] > 0 and len(neighbors) >= 4
                  and fraction is not None and fraction >= min_neighbor_pass_fraction
                  and median_m2 is not None
                  and median_m2 >= row["m2"] - max_neighbor_m2_gap)
        results.append({"params": params, "neighbor_count": len(neighbors),
                        "neighbor_pass_fraction": fraction, "neighbor_median_m2": median_m2,
                        "plateau_robust": bool(robust)})
    return results
