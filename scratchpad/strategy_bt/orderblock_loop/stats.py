"""Fail-closed statistical helpers for the preregistered orderblock gates."""

from __future__ import annotations

import json
from math import ceil, erf, exp, isfinite, sqrt
from random import Random
from statistics import NormalDist, mean, stdev
from typing import Callable, Mapping, Sequence

from metrics import GateEvidence, _issue_gate_evidence

SEED = 20261122
ALPHA = 0.05
PASS, FAIL, UNKNOWN = "pass", "fail", "undetermined"
CORE = ("sample", "net_return", "profit_factor", "expectancy",
        "wilson_vs_breakeven", "drawdown", "sharpe", "solvency")
ROBUST = ("walk_forward", "monte_carlo",
          "random_entry", "circular_shift", "plateau", "regime_2018",
          "regime_2022", "cost_stress_2x", "delay_1_bar",
          "untouched_symbols", "profit_concentration",
          "independent_reimplementation", "data_integrity")


def walk_forward_evidence(folds: Sequence[Sequence[float]]) -> GateEvidence:
    """Measure the preregistered five chronological validation folds."""
    if any(not isfinite(value) for fold in folds for value in fold):
        raise ValueError("walk-forward fold returns must be finite")
    fold_pnl = [sum(fold) for fold in folds]
    positive_folds = sum(value > 0 for value in fold_pnl)
    pooled = sum(fold_pnl)
    passed = len(folds) == 5 and all(folds) and positive_folds >= 4 and pooled > 0
    return _issue_gate_evidence(bool(passed), "five-fold chronological walk-forward",
                                sum(map(len, folds)),
                                {"fold_count": len(folds), "positive_folds": positive_folds,
                                 "pooled_net_return": pooled})


def _fixed_capital_mdd(trade_pnl: Sequence[float]) -> float:
    equity = peak = 1.0
    maximum = 0.0
    for pnl in trade_pnl:
        equity += pnl
        if equity <= 0:
            return 1.0
        peak = max(peak, equity)
        maximum = max(maximum, (peak - equity) / peak)
    return maximum


def monte_carlo_reorder_evidence(trade_pnl: Sequence[float], *,
                                 repetitions: int = 1000,
                                 seed: int = SEED) -> GateEvidence:
    """Reorder fixed-initial-capital completed trade PnL exactly 1,000 times."""
    values = list(map(float, trade_pnl))
    if not values or any(not isfinite(value) for value in values):
        raise ValueError("Monte Carlo requires finite completed trade PnL")
    if repetitions != 1000:
        raise ValueError("preregistered Monte Carlo count is exactly 1,000")
    rng = Random(seed)
    drawdowns = []
    for _ in range(repetitions):
        path = values.copy()
        rng.shuffle(path)
        drawdowns.append(_fixed_capital_mdd(path))
    drawdowns.sort()
    p95 = drawdowns[ceil(0.95 * repetitions) - 1]
    total_return = sum(values)
    passed = total_return > 0 and p95 < total_return / 2
    return _issue_gate_evidence(passed, "1,000 seeded trade-order permutations", len(values),
                                {"permutations": repetitions, "p95_mdd": p95,
                                 "observed_mdd": _fixed_capital_mdd(values),
                                 "test_net_return": total_return})


def plateau_evidence(winner_config: Mapping[str, object],
                     preregistered_configs: Sequence[Mapping[str, object]],
                     returns: Sequence[float | None]) -> GateEvidence:
    """Derive the one-grid-step neighbor shell from the full preregistered grid."""
    configs = [dict(config) for config in preregistered_configs]
    values = [None if value is None else float(value) for value in returns]
    if (not configs or len(configs) != len(values)
            or any(value is not None and not isfinite(value) for value in values)):
        raise ValueError("plateau requires one finite return for each registered config")
    keys = [json.dumps(config, sort_keys=True, separators=(",", ":")) for config in configs]
    if len(set(keys)) != len(keys):
        raise ValueError("registered parameter configurations must be unique")
    winner_key = json.dumps(dict(winner_config), sort_keys=True, separators=(",", ":"))
    if winner_key not in keys:
        raise ValueError("winner must be present in the full preregistered grid")
    winner_index = keys.index(winner_key)
    winner_return = values[winner_index]
    if winner_return is None:
        raise ValueError("winner parameter cell must have a measured return")
    numeric_axes: dict[str, list[float]] = {}
    for key in winner_config:
        axis = sorted({float(config[key]) for config in configs
                       if key in config and isinstance(config[key], (int, float))
                       and not isinstance(config[key], bool)})
        if len(axis) > 1:
            numeric_axes[key] = axis
    neighbors: list[float | None] = []
    winner = configs[winner_index]
    for index, config in enumerate(configs):
        if index == winner_index:
            continue
        changed = [key for key in winner
                   if config.get(key) != winner.get(key)]
        if len(changed) != 1:
            continue
        key = changed[0]
        axis = numeric_axes.get(key)
        if axis is None or config.get(key) not in axis or winner.get(key) not in axis:
            continue
        if abs(axis.index(config[key]) - axis.index(winner[key])) == 1:
            neighbors.append(values[index])
    complete = bool(neighbors) and all(value is not None for value in neighbors)
    valid = sum(value is not None and value >= winner_return * 0.5
                for value in neighbors) if winner_return > 0 else 0
    ratio = valid / len(neighbors) if complete else 0.0
    passed = complete and winner_return > 0 and ratio >= 0.70
    return _issue_gate_evidence(passed, "derived adjacent preregistered parameter cells",
                                len(neighbors), {"expected_neighbors": len(neighbors),
                                                 "valid_neighbors": valid,
                                                 "missing_neighbors": sum(value is None for value in neighbors),
                                                 "valid_fraction": ratio,
                                                 "complete_shell": complete,
                                                 "winner_return": winner_return})


def data_integrity_evidence(bars: Sequence[object], *, cutoff_ms: int,
                            source_fingerprint: str, funding_complete: bool,
                            source_unchanged: bool) -> GateEvidence:
    """Audit chronology, cutoff, OHLC, fingerprint and source/funding controls."""
    timestamps = [getattr(bar, "timestamp", None) for bar in bars]
    ordered = all(isinstance(ts, int) and not isinstance(ts, bool)
                  and ts <= cutoff_ms for ts in timestamps)
    ordered = ordered and all(a < b for a, b in zip(timestamps, timestamps[1:]))
    ohlc_valid = all(
        all(isfinite(float(getattr(bar, key))) for key in ("open", "high", "low", "close"))
        and getattr(bar, "low") <= min(getattr(bar, "open"), getattr(bar, "close"))
        <= max(getattr(bar, "open"), getattr(bar, "close")) <= getattr(bar, "high")
        for bar in bars
    )
    fingerprint_valid = (len(source_fingerprint) == 64
                         and all(ch in "0123456789abcdef" for ch in source_fingerprint.lower()))
    passed = bool(bars) and ordered and ohlc_valid and fingerprint_valid \
        and funding_complete and source_unchanged
    return _issue_gate_evidence(passed, "cutoff/OHLC/fingerprint/funding/source audit", len(bars),
                                {"chronological_and_pre_cutoff": ordered,
                                 "ohlc_valid": ohlc_valid,
                                 "fingerprint_valid": fingerprint_valid,
                                 "funding_complete": funding_complete,
                                 "source_unchanged": source_unchanged})


def wilson_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float] | None:
    if trials < 0 or successes < 0 or successes > trials or not 0 < confidence < 1:
        raise ValueError("invalid Wilson interval inputs")
    if trials == 0:
        return None
    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    p, z2 = successes / trials, z * z
    den = 1 + z2 / trials
    center = p + z2 / (2 * trials)
    half = z * sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials))
    return max(0.0, (center - half) / den), min(1.0, (center + half) / den)


def bonferroni(p_value: float, comparisons: int, alpha: float = ALPHA) -> dict[str, float | bool]:
    if not isfinite(p_value) or not 0 <= p_value <= 1 or comparisons < 1:
        raise ValueError("p_value must be in [0,1] and comparisons positive")
    threshold = alpha / comparisons
    return {"adjusted_p": min(1.0, p_value * comparisons),
            "threshold": threshold, "pass": p_value <= threshold}


def _stationary_indices(length: int, block_length: float, rng: Random) -> list[int]:
    if length < 1 or block_length <= 0:
        raise ValueError("series and block length must be positive")
    restart = min(1.0, 1.0 / block_length)
    indexes, current = [], rng.randrange(length)
    for _ in range(length):
        if rng.random() < restart:
            current = rng.randrange(length)
        else:
            current = (current + 1) % length
        indexes.append(current)
    return indexes


def _validate_returns(candidate_returns: Sequence[Sequence[float]]) -> list[list[float]]:
    values = [list(map(float, row)) for row in candidate_returns]
    if not values or not values[0] or any(len(row) != len(values[0]) for row in values):
        raise ValueError("returns must be a nonempty rectangular candidate-by-time matrix")
    if any(not isfinite(value) for row in values for value in row):
        raise ValueError("returns must be finite")
    return values


def _arch_comparison(returns: list[list[float]], block_length: float, reps: int,
                     seed: int, method: str) -> float | None:
    try:
        from arch.bootstrap import SPA, RealityCheck
    except ImportError:
        return None
    # arch expects observations x models; negative returns are losses against zero.
    import numpy as np
    losses = -np.asarray(returns, dtype=float).T
    benchmark = np.zeros(losses.shape[0])
    kwargs = {"bootstrap": "stationary", "reps": reps,
              "block_size": block_length, "seed": seed}
    if method == "rc":
        test = RealityCheck(benchmark, losses, **kwargs)
        test.compute()
        return float(test.pvalues["upper"])
    test = SPA(benchmark, losses, **kwargs)
    test.compute()
    return float(test.pvalues["consistent"])


def stdlib_bootstrap_family_p(returns: Sequence[Sequence[float]], *, block_length: float,
                              reps: int = 100_000, seed: int = SEED,
                              method: str = "rc") -> float:
    """Approximate family p-value retained only as an independent cross-check."""
    returns = _validate_returns(returns)
    if method not in ("rc", "spa") or reps < 1:
        raise ValueError("method must be rc or spa and reps positive")
    return _bootstrap_family_p(returns, block_length, reps, seed, method)


def _bootstrap_family_p(returns: list[list[float]], block_length: float, reps: int,
                        seed: int, method: str) -> float:
    t = len(returns[0])
    observed = max(mean(row) for row in returns)
    centered = [([x - mean(row) for x in row] if method == "rc" else
                 [x - max(0.0, mean(row) - stdev(row) / sqrt(t)) for x in row])
                for row in returns]
    rng, exceed = Random(seed), 0
    for _ in range(reps):
        indexes = _stationary_indices(t, block_length, rng)
        statistic = max(mean([row[i] for i in indexes]) for row in centered)
        if statistic >= observed:
            exceed += 1
    return (exceed + 1) / (reps + 1)


def reality_check(candidate_returns: Sequence[Sequence[float]], *, block_length: float,
                  reps: int = 100_000, seed: int = SEED) -> dict[str, float | str]:
    values = _validate_returns(candidate_returns)
    arch_p = _arch_comparison(values, block_length, reps, seed, "rc")
    if arch_p is None:
        raise RuntimeError("arch.bootstrap.RealityCheck is required by PREREG")
    return {"p_value": arch_p, "method": "arch.bootstrap.RealityCheck upper"}


def hansen_spa(candidate_returns: Sequence[Sequence[float]], *, block_length: float,
               reps: int = 100_000, seed: int = SEED) -> dict[str, float | str]:
    values = _validate_returns(candidate_returns)
    arch_p = _arch_comparison(values, block_length, reps, seed, "spa")
    if arch_p is None:
        raise RuntimeError("arch.bootstrap.SPA is required by PREREG")
    return {"p_value": arch_p, "method": "arch.bootstrap.SPA consistent"}


def deflated_sharpe(daily_returns: Sequence[float], trials: int) -> float | None:
    """Probability observed Sharpe exceeds the expected maximum over trials."""
    x = list(map(float, daily_returns))
    if trials < 1 or len(x) < 3 or any(not isfinite(v) for v in x):
        return None
    sd = stdev(x)
    if sd == 0:
        return None
    n = len(x)
    sr = mean(x) / sd
    centered = [v - mean(x) for v in x]
    skew = sum(v ** 3 for v in centered) / n / (sum(v ** 2 for v in centered) / n) ** 1.5
    kurtosis = sum(v ** 4 for v in centered) / n / (sum(v ** 2 for v in centered) / n) ** 2
    if trials == 1:
        expected_max = 0.0
    else:
        norm = NormalDist()
        a = norm.inv_cdf(1 - 1 / trials)
        b = norm.inv_cdf(1 - 1 / (trials * exp(1)))
        euler = 0.5772156649015329
        expected_max = (1 - euler) * a + euler * b
    variance = max(0.0, (1 - skew * sr + ((kurtosis - 1) / 4) * sr * sr) / (n - 1))
    if variance == 0:
        return None
    z = (sr - expected_max / sqrt(n)) / sqrt(variance)
    return 0.5 * (1 + erf(z / sqrt(2)))


def random_entry_null(values: Sequence[float], *, repetitions: int = 200,
                      trades_per_draw: int | None = None,
                      seed: int = SEED) -> list[float]:
    """Low-level draw helper; not a gate (use matched_random_entry_evidence)."""
    x = list(map(float, values))
    if trades_per_draw is None:
        raise ValueError("trades_per_draw must be explicit; full-pool draws have no null variation")
    count = trades_per_draw
    if (repetitions < 1 or count < 1 or count >= len(x)
            or any(not isfinite(v) for v in x)):
        raise ValueError("invalid random-entry null inputs")
    rng, result = Random(seed), []
    for _ in range(repetitions):
        result.append(sum(rng.sample(x, count)))
    return result


def matched_random_entry_evidence(
        observed_return: float,
        eligible_by_symbol: Mapping[str, Sequence[int]],
        observed_by_symbol: Mapping[str, Sequence[int]],
        evaluate_entries: Callable[[Mapping[str, Sequence[int]]], float], *,
        repetitions: int = 200, seed: int = SEED) -> GateEvidence:
    """Compare against matched random entries, evaluated by the same simulator.

    The callback must run identical entry/exit, overlap, sizing and cost rules for
    the submitted entry map. Counts are preserved per symbol; sampling is without
    replacement. Invalid or unmatched inputs fail closed instead of yielding evidence.
    """
    if not isfinite(observed_return) or repetitions != 200:
        raise ValueError("random-entry test requires finite return and exactly 200 repetitions")
    if not eligible_by_symbol or set(eligible_by_symbol) != set(observed_by_symbol):
        raise ValueError("eligible and observed symbol sets must match")
    eligible: dict[str, list[int]] = {}
    observed: dict[str, list[int]] = {}
    for symbol in sorted(eligible_by_symbol):
        pool, selected = list(eligible_by_symbol[symbol]), list(observed_by_symbol[symbol])
        if (not pool or len(set(pool)) != len(pool) or len(set(selected)) != len(selected)
                or not set(selected).issubset(pool) or len(selected) > len(pool)):
            raise ValueError(f"invalid matched entry indexes for {symbol}")
        eligible[symbol], observed[symbol] = pool, selected
    if sum(map(len, observed.values())) < 1:
        raise ValueError("candidate must contain at least one observed entry")
    rng, null_returns = Random(seed), []
    for _ in range(repetitions):
        draw = {symbol: rng.sample(eligible[symbol], len(observed[symbol]))
                for symbol in eligible}
        value = float(evaluate_entries(draw))
        if not isfinite(value):
            raise ValueError("matched simulator returned a non-finite value")
        null_returns.append(value)
    ordered = sorted(null_returns)
    p95 = ordered[ceil(0.95 * repetitions) - 1]
    passed = observed_return > p95
    return _issue_gate_evidence(passed, "200 per-symbol matched random-entry replays", repetitions,
                                {"repetitions": repetitions, "observed_return": observed_return,
                                 "null_p95": p95, "null_mean": mean(null_returns),
                                 "candidate_entries": sum(map(len, observed.values()))})


def circular_shift_null(signal_by_symbol: Mapping[str, Sequence[float]], *,
                         repetitions: int = 1000, seed: int = SEED) -> list[dict[str, list[float]]]:
    if repetitions < 1 or not signal_by_symbol:
        raise ValueError("invalid circular-shift null inputs")
    if any(not values or any(not isfinite(float(v)) for v in values)
           for values in signal_by_symbol.values()):
        raise ValueError("signals must be finite nonempty series")
    if len({len(values) for values in signal_by_symbol.values()}) != 1:
        raise ValueError("per-symbol signals must cover the same aligned observation dates")
    rng, shifted = Random(seed), []
    for _ in range(repetitions):
        sample = {}
        for symbol, values in signal_by_symbol.items():
            offset = rng.randrange(len(values))
            sample[symbol] = list(values[offset:]) + list(values[:offset])
        shifted.append(sample)
    return shifted


def circular_shift_evidence(
        observed_statistic: float, signal_by_symbol: Mapping[str, Sequence[float]],
        evaluate_signals: Callable[[Mapping[str, Sequence[float]]], float], *,
        repetitions: int = 1000, seed: int = SEED) -> GateEvidence:
    """Run circular-shift surrogates through the candidate's same evaluator."""
    if not isfinite(observed_statistic) or repetitions != 1000:
        raise ValueError("circular-shift test requires finite statistic and exactly 1,000 repetitions")
    shifted = circular_shift_null(signal_by_symbol, repetitions=repetitions, seed=seed)
    null_values = [float(evaluate_signals(sample)) for sample in shifted]
    if any(not isfinite(value) for value in null_values):
        raise ValueError("circular-shift evaluator returned a non-finite statistic")
    ordered = sorted(null_values)
    p95 = ordered[ceil(0.95 * repetitions) - 1]
    return _issue_gate_evidence(observed_statistic > p95,
                                "1,000 per-symbol circular-shift full-pipeline replays",
                                repetitions,
                                {"repetitions": repetitions, "observed_statistic": observed_statistic,
                                 "null_p95": p95, "null_mean": mean(null_values)})


def concentration_by_year(daily_pnl: Mapping[object, float]) -> dict[str, object]:
    if not daily_pnl or any(not isfinite(float(v)) for v in daily_pnl.values()):
        return {"max_year_share": None, "shares": {}}
    total = sum(daily_pnl.values())
    if total <= 0:
        return {"max_year_share": None, "shares": {}}
    annual: dict[int, float] = {}
    for date_or_year, pnl in daily_pnl.items():
        year = getattr(date_or_year, "year", date_or_year)
        if not isinstance(year, int):
            raise ValueError("daily PnL keys must be years or date-like values")
        annual[year] = annual.get(year, 0.0) + pnl
    shares = {year: pnl / total for year, pnl in annual.items()}
    return {"max_year_share": max(shares.values()), "shares": shares}


def gate_decision(candidate_metrics: Mapping[str, object],
                  cumulative_counts: Mapping[str, int]) -> dict[str, str]:
    """Return G criterion statuses. Missing, malformed, or absent evidence is unknown."""
    stat_keys = ("bonferroni", "reality_check", "spa", "deflated_sharpe")
    result = {key: _status(candidate_metrics.get(key)) for key in (*CORE, *ROBUST, *stat_keys)}
    frozen = cumulative_counts.get("frozen_test_candidates")
    train = cumulative_counts.get("train_trials")
    pchecks = (("bonferroni", "bonferroni_p", frozen, True),
               ("reality_check", "reality_check_p", frozen, True),
               ("spa", "spa_p", frozen, True),
               ("deflated_sharpe", "deflated_sharpe_probability", train, False))
    for criterion, metric, count, lower in pchecks:
        value = candidate_metrics.get(metric)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            result[criterion] = UNKNOWN
        elif not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
            result[criterion] = UNKNOWN
        elif lower:
            result[criterion] = PASS if 0 <= value <= ALPHA / count else FAIL
        else:
            result[criterion] = PASS if 1 - ALPHA / count <= value <= 1 else FAIL
    return result


def null_percentile_pass(observed: float, null_results: Sequence[float],
                         percentile: float = 0.95) -> bool | None:
    values = list(map(float, null_results))
    if (not isfinite(observed) or not 0 < percentile < 1 or not values
            or any(not isfinite(value) for value in values)):
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(percentile * len(ordered))))
    return observed > ordered[index]


def _status(value: object) -> str:
    if type(value) is bool:
        return PASS if value else FAIL
    return UNKNOWN
