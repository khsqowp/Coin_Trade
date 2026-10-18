"""Statistical-significance based validation gate — an alternative to the flat
"trades >= 300" rule in docs/trading-agent-plan.md.

Bootstrap-resamples per-trade returns to check whether an apparent edge survives
sampling uncertainty, rather than requiring an arbitrarily large trade count outright.
This matters for slower swing strategies (e.g. 4h/1d holding periods) that will never
rack up hundreds of trades in a few years of history even if the edge is real — the
fixed trade-count rule structurally penalizes low-frequency strategies regardless of
quality. This is NOT a replacement for the 300-trade rule everywhere; it's a second,
complementary lens (see app/full_search.py's "2" and combination views).
"""
from __future__ import annotations

import numpy as np


def bootstrap_expectancy_gate(trade_returns: np.ndarray, iterations: int = 2000,
                               confidence: float = 0.95, min_trades: int = 20,
                               random_state: int = 42) -> dict:
    n = len(trade_returns)
    if n < min_trades:
        return {"passed": False, "reason": f"거래 {n}건 < 최소 {min_trades}건 (부트스트랩 신뢰 불가)",
                "lower_bound": float("nan"), "trades": n}

    rng = np.random.default_rng(random_state)
    means = np.empty(iterations)
    for idx in range(iterations):
        sample = rng.choice(trade_returns, size=n, replace=True)
        means[idx] = sample.mean()

    lower_bound = float(np.percentile(means, (1 - confidence) * 100))
    passed = lower_bound > 0
    return {
        "passed": passed,
        "reason": f"{confidence:.0%} 신뢰구간 하한 기대수익 {lower_bound:.4f} ({'>' if passed else '<='} 0)",
        "lower_bound": lower_bound,
        "trades": n,
    }
