"""Small, deterministic metric functions for preregistered candidate gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import isfinite, sqrt
from statistics import mean, stdev
from typing import Mapping, Sequence

WILSON_Z_95 = 1.959963984540054
CORE_REQUIRED_KEYS = frozenset({
    "sample", "net_return", "profit_factor", "expectancy",
    "wilson_vs_breakeven", "drawdown", "sharpe", "solvency",
})
_EVIDENCE_SEAL = object()
ROBUSTNESS_REQUIRED_KEYS = frozenset({
    "bonferroni", "reality_check", "spa", "deflated_sharpe",
    "walk_forward", "monte_carlo",
    "random_entry", "circular_shift", "plateau", "regime_2018",
    "regime_2022", "cost_stress_2x", "delay_1_bar", "untouched_symbols",
    "profit_concentration", "independent_reimplementation", "data_integrity",
})


@dataclass(frozen=True)
class TradeMetrics:
    count: int
    win_rate: float | None
    wilson_lower_95: float | None
    average_win: float | None
    average_loss: float | None
    breakeven_win_rate: float | None
    profit_factor: float | None
    expectancy_bps: float | None


@dataclass(frozen=True)
class CurveMetrics:
    cumulative_return: float
    max_drawdown: float
    annualized_sharpe: float | None
    solvent: bool


@dataclass(frozen=True)
class GateEvidence:
    """Measured, attributable evidence required for a robustness gate."""

    passed: bool
    method: str
    sample_count: int
    diagnostics: Mapping[str, float | int | bool | str | None]
    _seal: object | None = field(default=None, repr=False, compare=False)


def _issue_gate_evidence(passed: bool, method: str, sample_count: int,
                         diagnostics: Mapping[str, float | int | bool | str | None]) -> GateEvidence:
    """Internal constructor; only measured evaluators should issue gate evidence."""
    return GateEvidence(passed, method, sample_count, diagnostics, _EVIDENCE_SEAL)


def _valid_gate_evidence(value: object) -> bool:
    if not isinstance(value, GateEvidence) or value._seal is not _EVIDENCE_SEAL:
        return False
    if (type(value.passed) is not bool or not isinstance(value.method, str)
            or not value.method.strip()
            or not isinstance(value.sample_count, int) or isinstance(value.sample_count, bool)
            or value.sample_count < 1 or not isinstance(value.diagnostics, Mapping)
            or not value.diagnostics):
        return False
    return all(not isinstance(item, float) or isfinite(item)
               for item in value.diagnostics.values())


def wilson_lower(successes: int, trials: int, z: float = WILSON_Z_95) -> float | None:
    """Wilson score interval lower bound, or None when there is no sample."""
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("require 0 <= successes <= trials")
    if trials == 0:
        return None
    p = successes / trials
    z2 = z * z
    denominator = 1 + z2 / trials
    center = p + z2 / (2 * trials)
    margin = z * sqrt((p * (1 - p) / trials) + z2 / (4 * trials * trials))
    return (center - margin) / denominator


def trade_metrics(net_returns: Sequence[float]) -> TradeMetrics:
    """Metrics from completed, post-cost per-trade decimal returns."""
    if any(not isfinite(value) for value in net_returns):
        raise ValueError("trade returns must be finite")
    wins = [value for value in net_returns if value > 0]
    losses = [-value for value in net_returns if value < 0]
    count = len(net_returns)
    avg_win = mean(wins) if wins else None
    avg_loss = mean(losses) if losses else None
    win_rate = len(wins) / count if count else None
    lower = wilson_lower(len(wins), count) if count else None
    breakeven = avg_loss / (avg_win + avg_loss) if avg_win and avg_loss else None
    gross_loss = sum(losses)
    pf = sum(wins) / gross_loss if gross_loss else (float("inf") if wins else None)
    return TradeMetrics(
        count=count,
        win_rate=win_rate,
        wilson_lower_95=lower,
        average_win=avg_win,
        average_loss=avg_loss,
        breakeven_win_rate=breakeven,
        profit_factor=pf,
        expectancy_bps=mean(net_returns) * 10_000 if count else None,
    )


def curve_metrics(daily_returns: Sequence[float], annualization_days: int) -> CurveMetrics:
    """Accumulate daily PnL against fixed initial capital; no profit reinvestment."""
    if annualization_days <= 0:
        raise ValueError("annualization_days must be positive")
    if any(not isfinite(value) for value in daily_returns):
        raise ValueError("daily returns must be finite")
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    solvent = True
    for value in daily_returns:
        equity += value
        if equity <= 0:
            equity = 0.0
            solvent = False
            max_dd = 1.0
            break
        peak = max(peak, equity)
        if peak:
            max_dd = max(max_dd, (peak - equity) / peak)
    sharpe = None
    if solvent and len(daily_returns) >= 2:
        deviation = stdev(daily_returns)
        if deviation > 0:
            sharpe = mean(daily_returns) / deviation * sqrt(annualization_days)
    return CurveMetrics(equity - 1, max_dd, sharpe, solvent)


def core_gate(metrics: TradeMetrics, daily_returns: Sequence[float], *,
              market: str) -> dict[str, bool]:
    """Evaluate the fixed, market-specific numeric core of G."""
    thresholds = {
        "crypto": (100, 15.0, 365),
        "US": (60, 30.0, 252),
        "KR": (60, 30.0, 252),
    }
    if market not in thresholds:
        raise ValueError("market must be crypto, US, or KR")
    minimum_trades, minimum_expectancy_bps, annualization_days = thresholds[market]
    curve = curve_metrics(daily_returns, annualization_days)
    win_gate = (
        metrics.wilson_lower_95 is not None
        and metrics.breakeven_win_rate is not None
        and metrics.wilson_lower_95 > metrics.breakeven_win_rate
    )
    return {
        "sample": metrics.count >= minimum_trades,
        "net_return": curve.cumulative_return > 0,
        "profit_factor": metrics.profit_factor is not None
        and metrics.profit_factor >= 1.30,
        "expectancy": metrics.expectancy_bps is not None
        and metrics.expectancy_bps >= minimum_expectancy_bps,
        "wilson_vs_breakeven": win_gate,
        "drawdown": curve.cumulative_return > 0
        and curve.max_drawdown < curve.cumulative_return / 2,
        "sharpe": curve.annualized_sharpe is not None
        and curve.annualized_sharpe >= 1.0,
        "solvency": curve.solvent,
    }


def full_gate(core_results: dict[str, bool],
              robustness_results: Mapping[str, GateEvidence]) -> bool:
    """Fail closed unless core gates pass and each robustness gate has evidence."""
    if set(core_results) != CORE_REQUIRED_KEYS:
        return False
    if set(robustness_results) != ROBUSTNESS_REQUIRED_KEYS:
        return False
    if any(type(value) is not bool for value in core_results.values()):
        return False
    if any(not _valid_gate_evidence(value) for value in robustness_results.values()):
        return False
    return all(core_results.values()) and all(value.passed for value in robustness_results.values())


def release_gate(candidate_passes: Sequence[bool], pair_correlations: dict[tuple[int, int], float],
                 frozen_returns: Mapping[int, float]) -> bool:
    """Require at least two passing candidates, valid pair correlations and frozen returns."""
    count = len(candidate_passes)
    if any(type(value) is not bool for value in candidate_passes):
        return False
    selected = [index for index, passed in enumerate(candidate_passes) if passed]
    if len(selected) < 2:
        return False
    expected_pairs = set(combinations(selected, 2))
    if set(pair_correlations) != expected_pairs:
        return False
    if any(not isfinite(value) or not -1 <= value <= 1 or value >= 0.5
           for value in pair_correlations.values()):
        return False
    if set(frozen_returns) != set(selected):
        return False
    if any(not isfinite(value) or value < 0 for value in frozen_returns.values()):
        return False
    return True
