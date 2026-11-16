#!/usr/bin/env python3
"""Synthetic null calibration of self-normalized tests for dependent score means."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import time
from pathlib import Path

import numpy as np

ALPHA = 0.05
NULL_PRECISION = 0.80
FRAME_COUNT = 12
SCENARIOS = [
    {"days": d, "mean_count": m, "rho": rho, "common_fraction": common}
    for d in (365, 900)
    for m in (8, 40)
    for rho in (0.0, 0.5, 0.9)
    for common in (0.0, 0.75)
]


def _load_r013_generator():
    source = Path(__file__).with_name("crypto_r013_inference_calibration.py")
    spec = importlib.util.spec_from_file_location("crypto_r013_dgp", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load frozen R013 synthetic DGP")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def brownian_pivot_reference(*, paths: int, steps: int, seed: int,
                             batch_size: int = 2048) -> np.ndarray:
    """Simulate discrete Riemann approximations to the SN Brownian pivot."""
    if paths < 1 or steps < 2 or batch_size < 1:
        raise ValueError("paths and batch_size must be positive; steps must be >= 2")
    rng = np.random.default_rng(seed)
    ref = np.empty(paths, dtype=float)
    time_grid = np.arange(1, steps + 1, dtype=float) / steps
    offset = 0
    while offset < paths:
        size = min(batch_size, paths - offset)
        increments = rng.normal(0.0, 1.0 / math.sqrt(steps), size=(size, steps))
        brownian = np.cumsum(increments, axis=1)
        endpoint = brownian[:, -1]
        bridge = brownian - endpoint[:, None] * time_grid[None, :]
        denominator = np.mean(bridge * bridge, axis=1)
        ref[offset:offset + size] = endpoint * endpoint / denominator
        offset += size
    if not np.isfinite(ref).all() or (ref <= 0).any():
        raise FloatingPointError("Brownian pivot simulation produced invalid values")
    return np.sort(ref)


def self_normalized_statistic(scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = _validate_scores(scores)
    n = values.shape[0]
    cumulative_means = np.cumsum(values, axis=0) / np.arange(1, n + 1)[:, None]
    full_mean = values.mean(axis=0)
    k = np.arange(1, n + 1, dtype=float)[:, None]
    normalizer = np.sum((k * (cumulative_means - full_mean)) ** 2, axis=0) / (n * n)
    if not np.isfinite(normalizer).all() or (normalizer <= 0).any():
        raise ValueError("self-normalizer is zero or invalid; inference is not evaluable")
    statistic = n * full_mean * full_mean / normalizer
    if not np.isfinite(statistic).all():
        raise ValueError("self-normalized statistic is invalid")
    return full_mean, statistic


def self_normalized_pvalues(scores: np.ndarray, sorted_reference: np.ndarray) -> np.ndarray:
    values = _validate_scores(scores)
    reference = np.asarray(sorted_reference, dtype=float)
    if reference.ndim != 1 or len(reference) < 100 or not np.isfinite(reference).all():
        raise ValueError("reference must be a finite sorted pivot vector with >=100 draws")
    if np.any(reference[1:] < reference[:-1]):
        raise ValueError("reference pivot values must be sorted ascending")
    mean, statistic = self_normalized_statistic(values)
    below = np.searchsorted(reference, statistic, side="left")
    tail = (len(reference) - below + 1.0) / (len(reference) + 1.0)
    pvalues = np.where(mean > 0, tail / 2.0, 1.0 - tail / 2.0)
    return np.clip(pvalues, 0.0, 1.0)


def wilson_upper(successes: int, trials: int, z: float) -> float:
    if trials <= 0 or not 0 <= successes <= trials or z <= 0:
        raise ValueError("invalid Wilson interval inputs")
    phat = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    center = (phat + z2 / (2.0 * trials)) / denom
    half = z * math.sqrt(phat * (1.0 - phat) / trials + z2 / (4.0 * trials * trials)) / denom
    return min(1.0, center + half)


def wilson_upper_by_column(rejections: np.ndarray, z: float) -> np.ndarray:
    values = np.asarray(rejections)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] < 1:
        raise ValueError("rejections must be a non-empty repetitions-by-tests matrix")
    if not np.isin(values, (0, 1, False, True)).all():
        raise ValueError("rejections must contain only Boolean or binary values")
    trials = values.shape[0]
    return np.array([wilson_upper(int(values[:, j].sum()), trials, z)
                     for j in range(values.shape[1])])


def _validate_scores(scores: np.ndarray) -> np.ndarray:
    arr = np.asarray(scores, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 2 or arr.shape[1] < 1 or not np.isfinite(arr).all():
        raise ValueError("scores must be a finite days-by-timeframes matrix")
    return arr


def run_calibration(*, simulations: int = 1000, reference_paths: int = 250_000,
                    reference_steps: int = 2048, seed: int = 20261117,
                    reference_seed: int = 20261118) -> dict:
    if simulations < 1:
        raise ValueError("simulations must be positive")
    started = time.monotonic()
    dgp = _load_r013_generator()
    reference = brownian_pivot_reference(paths=reference_paths, steps=reference_steps,
                                         seed=reference_seed)
    # One-sided upper bounds with a Bonferroni simultaneous 95% confidence
    # guarantee over 288 per-timeframe rates plus 24 scenario FWER rates.
    confidence_cells = len(SCENARIOS) * (FRAME_COUNT + 1)
    z = __import__("statistics").NormalDist().inv_cdf(1.0 - 0.05 / confidence_cells)
    results = []
    total_failures = 0
    for scenario_index, scenario in enumerate(SCENARIOS):
        stream = np.random.default_rng(seed + scenario_index * 1_000_003)
        rejection_matrix = np.zeros((simulations, FRAME_COUNT), dtype=bool)
        errors = 0
        for replication in range(simulations):
            sim_seed = int(stream.integers(0, np.iinfo(np.int32).max))
            scores = dgp.simulate_scores(frames=FRAME_COUNT, seed=sim_seed, **scenario)
            try:
                pvalues = self_normalized_pvalues(scores, reference)
                rejection_matrix[replication] = dgp.holm_reject(pvalues, alpha=ALPHA)
            except (ValueError, FloatingPointError):
                errors += 1
        total_failures += errors
        per_timeframe = []
        rate_upper = wilson_upper_by_column(rejection_matrix, z=z)
        for frame in range(FRAME_COUNT):
            count = int(rejection_matrix[:, frame].sum())
            per_timeframe.append({"frame_index": frame,
                                  "type1_rate": count / simulations,
                                  "simultaneous_upper_bound": float(rate_upper[frame])})
        fwer_count = int(np.any(rejection_matrix, axis=1).sum())
        fwer_rate = fwer_count / simulations
        fwer_upper = wilson_upper(fwer_count, simulations, z=z)
        qualified = (errors == 0 and max(rate_upper) <= 0.075 and fwer_upper <= 0.085)
        results.append({**scenario, "simulations": simulations, "failed_replications": errors,
                        "per_timeframe_type1": per_timeframe,
                        "mean_per_test_type1": float(rejection_matrix.mean()),
                        "holm_fwer": fwer_rate,
                        "holm_fwer_simultaneous_upper_bound": fwer_upper,
                        "screen_qualified": bool(qualified)})
    return {"schema_version": 1, "method": "self_normalized_recursive_mean_brownian_pivot",
            "alpha": ALPHA, "null_precision": NULL_PRECISION, "timeframes": FRAME_COUNT,
            "seed": seed, "reference_seed": reference_seed,
            "reference_paths": reference_paths, "reference_steps": reference_steps,
            "reference_resolution": 0.5 / (reference_paths + 1),
            "scenario_count": len(SCENARIOS), "scenarios": results,
            "simultaneous_confidence_level": 0.95,
            "bonferroni_interval_count": confidence_cells,
            "per_test_upper_threshold": 0.075, "holm_fwer_upper_threshold": 0.085,
            "failed_replications": total_failures,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "python": platform.python_version(), "numpy": np.__version__,
            "note": "synthetic inference calibration only; not a strategy or market result"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--reference-paths", type=int, default=250_000)
    parser.add_argument("--reference-steps", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=20261117)
    parser.add_argument("--reference-seed", type=int, default=20261118)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_calibration(simulations=args.simulations,
                             reference_paths=args.reference_paths,
                             reference_steps=args.reference_steps,
                             seed=args.seed, reference_seed=args.reference_seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True).encode()
    args.output.write_bytes(payload + b"\n")
    print(json.dumps({"output": str(args.output),
                      "sha256": hashlib.sha256(payload).hexdigest(),
                      "scenario_count": result["scenario_count"],
                      "failed_replications": result["failed_replications"],
                      "elapsed_seconds": result["elapsed_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
