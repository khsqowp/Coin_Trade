#!/usr/bin/env python3
"""Synthetic-only null calibration for R012 overlapping forecast precision."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from pathlib import Path

import numpy as np

NULL_PRECISION = 0.80
ALPHA = 0.05
OUTCOME_HETEROGENEITY = 0.75


def simulate_scores(*, days: int, frames: int, mean_count: int, rho: float,
                    common_fraction: float, seed: int) -> np.ndarray:
    """Return daily W - .8N scores under a stationary, exactly-80% null.

    Daily counts are negative-binomial and independent of outcomes. Outcomes
    are conditionally binomial with a Gaussian-copula AR(1) success probability;
    common latent innovations synchronize timeframe shocks. Marginal success
    probability is exactly .8 by the probit convolution identity.
    """
    if days <= 0 or frames <= 0 or mean_count <= 0:
        raise ValueError("days, frames, and mean_count must be positive")
    if not 0 <= rho < 1 or not 0 <= common_fraction <= 1:
        raise ValueError("rho must be in [0,1) and common_fraction in [0,1]")

    rng = np.random.default_rng(seed)
    # NB(size=2): Var(N) = mean + mean^2 / size.
    size = 2.0
    prob = size / (size + mean_count)
    counts = rng.negative_binomial(size, prob, size=(days, frames))
    common = _ar1(rng.normal(size=days), rho)
    idiosyncratic = np.column_stack([_ar1(rng.normal(size=days), rho) for _ in range(frames)])
    latent = (math.sqrt(common_fraction) * common[:, None]
              + math.sqrt(1.0 - common_fraction) * idiosyncratic)
    # Conditional P(Y=1 | latent) calibrated to marginal P(Y=1)=.8.
    from statistics import NormalDist
    threshold = NormalDist().inv_cdf(NULL_PRECISION)
    conditional_p = _normal_cdf((threshold - math.sqrt(OUTCOME_HETEROGENEITY) * latent)
                                / math.sqrt(1.0 - OUTCOME_HETEROGENEITY))
    wins = rng.binomial(counts, conditional_p)
    return wins.astype(float) - NULL_PRECISION * counts


def _ar1(innovations: np.ndarray, rho: float) -> np.ndarray:
    if rho == 0:
        return innovations
    values = np.empty_like(innovations)
    values[0] = innovations[0]
    scale = math.sqrt(1 - rho * rho)
    for i in range(1, len(values)):
        values[i] = rho * values[i - 1] + scale * innovations[i]
    return values


def _normal_cdf(values: np.ndarray) -> np.ndarray:
    # Vectorized approximation-free CDF from the platform libm.
    return np.fromiter((0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))
                        for x in np.ravel(values)), dtype=float).reshape(values.shape)


def _hac_se(values: np.ndarray, lag: int) -> np.ndarray:
    n, frames = values.shape
    if lag < 0 or lag >= n:
        raise ValueError("lag must be in [0, days)")
    centered = values - values.mean(axis=0, keepdims=True)
    long_run = np.sum(centered * centered, axis=0) / n
    for k in range(1, lag + 1):
        weight = 1.0 - k / (lag + 1.0)
        gamma = np.sum(centered[k:] * centered[:-k], axis=0) / n
        long_run += 2.0 * weight * gamma
    return np.sqrt(np.maximum(long_run, np.finfo(float).tiny) / n)


def hac_pvalues(scores: np.ndarray, lag: int) -> np.ndarray:
    scores = _validate_scores(scores)
    z = scores.mean(axis=0) / _hac_se(scores, lag)
    return np.clip(0.5 * np.fromiter((math.erfc(float(x) / math.sqrt(2.0))
                                      for x in z), dtype=float), 0.0, 1.0)


def block_bootstrap_pvalues(scores: np.ndarray, block_length: int, reps: int,
                            seed: int, studentizer_lag: int | None = None) -> np.ndarray:
    """Synchronized circular MBB p-values for one-sided null score tests."""
    scores = _validate_scores(scores)
    n, frames = scores.shape
    if not 1 <= block_length <= n or reps <= 0:
        raise ValueError("block_length must be in [1, days] and reps positive")
    lag = min(block_length - 1, n - 1) if studentizer_lag is None else studentizer_lag
    observed = scores.mean(axis=0) / _hac_se(scores, lag)
    centered = scores - scores.mean(axis=0, keepdims=True)
    rng = np.random.default_rng(seed)
    blocks_needed = n // block_length
    if blocks_needed < 2:
        raise ValueError("at least two complete bootstrap blocks are required")
    starts = rng.integers(0, n, size=(reps, blocks_needed))
    extended = np.concatenate((centered, centered[:block_length - 1]), axis=0)
    prefix = np.vstack((np.zeros((1, frames)), np.cumsum(extended, axis=0)))
    all_block_sums = prefix[block_length:] - prefix[:-block_length]
    selected = all_block_sums[starts]
    # Studentize synchronized block totals; incomplete calendar tails are
    # omitted rather than assigned a different effective block weight.
    statistics = selected.mean(axis=1) / (
        selected.std(axis=1, ddof=1) / math.sqrt(blocks_needed)
    )
    exceed = np.sum(statistics >= observed[None, :], axis=0)
    return (exceed + 1.0) / (reps + 1.0)


def holm_reject(pvalues: np.ndarray, alpha: float = ALPHA) -> np.ndarray:
    p = np.asarray(pvalues, dtype=float)
    if p.ndim != 1 or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("pvalues must be a finite one-dimensional vector in [0,1]")
    order = np.argsort(p, kind="stable")
    sorted_reject = np.zeros(len(p), dtype=bool)
    for rank, index in enumerate(order):
        if p[index] <= alpha / (len(p) - rank):
            sorted_reject[rank] = True
        else:
            break
    result = np.zeros(len(p), dtype=bool)
    result[order] = sorted_reject
    return result


def _validate_scores(scores: np.ndarray) -> np.ndarray:
    arr = np.asarray(scores, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 2 or arr.shape[1] < 1 or not np.isfinite(arr).all():
        raise ValueError("scores must be a finite days-by-frames matrix")
    return arr


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> list[float]:
    if trials <= 0:
        return [float("nan"), float("nan")]
    phat = successes / trials
    denom = 1 + z * z / trials
    center = (phat + z * z / (2 * trials)) / denom
    half = z * math.sqrt(phat * (1 - phat) / trials + z * z / (4 * trials * trials)) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def run_calibration(*, simulations: int = 1000, bootstrap_reps: int = 499,
                    seed: int = 20261116) -> dict:
    if simulations < 1 or bootstrap_reps < 1:
        raise ValueError("simulation counts must be positive")
    scenarios = [
        {"days": d, "mean_count": m, "rho": r, "common_fraction": c}
        for d in (365, 900)
        for m in (8, 40)
        for r in (0.0, 0.5, 0.9)
        for c in (0.0, 0.75)
    ]
    # The preregistered full grid; each scenario receives a deterministic RNG stream.
    methods = [*(f"hac_lag_{lag}" for lag in (7, 14, 30)),
               *(f"mbb_block_{length}" for length in (7, 14, 30))]
    results = []
    started = time.monotonic()
    for scenario_i, scenario in enumerate(scenarios):
        rejects = {method: 0 for method in methods}
        fwer = {method: 0 for method in methods}
        rng = np.random.default_rng(seed + scenario_i * 1000003)
        for _ in range(simulations):
            sim_seed = int(rng.integers(0, np.iinfo(np.int32).max))
            scores = simulate_scores(frames=12, seed=sim_seed, **scenario)
            for lag in (7, 14, 30):
                p = hac_pvalues(scores, lag)
                key = f"hac_lag_{lag}"
                rejects[key] += int(np.sum(p <= ALPHA))
                fwer[key] += int(np.any(holm_reject(p)))
            for block in (7, 14, 30):
                p = block_bootstrap_pvalues(scores, block, bootstrap_reps,
                                            seed=sim_seed ^ (block * 7919),
                                            studentizer_lag=block)
                key = f"mbb_block_{block}"
                rejects[key] += int(np.sum(p <= ALPHA))
                fwer[key] += int(np.any(holm_reject(p)))
        rows = []
        for method in methods:
            test_count = simulations * 12
            size = rejects[method] / test_count
            family_rate = fwer[method] / simulations
            size_ci = wilson_interval(rejects[method], test_count)
            fwer_ci = wilson_interval(fwer[method], simulations)
            qualified = size_ci[1] <= 0.075 and fwer_ci[1] <= 0.085
            rows.append({"method": method, "per_test_type1": size,
                         "per_test_95pct_wilson": size_ci,
                         "holm_fwer": family_rate,
                         "holm_fwer_95pct_wilson": fwer_ci,
                         "screen_qualified": qualified})
        results.append({**scenario, "simulations": simulations, "methods": rows})
    return {"schema_version": 1, "seed": seed, "alpha": ALPHA,
            "null_precision": NULL_PRECISION, "timeframes": 12,
            "outcome_heterogeneity": OUTCOME_HETEROGENEITY,
            "bootstrap_reps": bootstrap_reps,
            "scenario_count": len(scenarios), "scenario_results": results,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "python": platform.python_version(), "numpy": np.__version__,
            "note": "synthetic method calibration only; not a strategy or market result"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--bootstrap-reps", type=int, default=499)
    parser.add_argument("--seed", type=int, default=20261116)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_calibration(simulations=args.simulations,
                             bootstrap_reps=args.bootstrap_reps, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, sort_keys=True).encode()
    args.output.write_bytes(encoded + b"\n")
    print(json.dumps({"output": str(args.output), "sha256": hashlib.sha256(encoded).hexdigest(),
                      "scenario_count": report["scenario_count"],
                      "elapsed_seconds": report["elapsed_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
