#!/usr/bin/env python3
"""Synthetic-only wild-cluster max-t calibration for target-first scores."""

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

TARGET = 0.80
ALPHA = 0.05
SYMBOLS = 20
FRAMES = 12
HORIZONS = (10, 20)
R016_PATH = Path(__file__).with_name("crypto_r016_synthetic_event_calibration.py")
SPEC = importlib.util.spec_from_file_location("r016_generator", R016_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load R016 synthetic-only generator")
R016 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R016)


def _eligibility(issued: np.ndarray, counts: np.ndarray, *, days: int
                 ) -> tuple[np.ndarray, dict]:
    total_n = counts.sum(axis=0)
    all_n, nonoverlap_n = total_n[::2].astype(int), total_n[1::2].astype(int)
    frame_coverage = issued.reshape(FRAMES, len(HORIZONS), days,
                                    SYMBOLS)[:, 0].mean(axis=(1, 2))
    all_symbols, nonoverlap_symbols = R016._unique_symbol_counts(issued)
    eligible_frame = np.repeat(frame_coverage >= 0.10, len(HORIZONS))
    eligible = np.column_stack((
        eligible_frame & (all_n >= 200) & (all_symbols >= SYMBOLS),
        eligible_frame & (nonoverlap_n >= 200)
        & (nonoverlap_symbols >= SYMBOLS))).ravel()
    summary = {"mean_raw_coverage": float(frame_coverage.mean()),
               "all_timeframes_coverage_ge_10pct": bool((frame_coverage >= 0.10).all()),
               "all_emitted_all_claims_N_ge_200": bool((all_n >= 200).all()),
               "nonoverlap_all_claims_N_ge_200": bool((nonoverlap_n >= 200).all()),
               "all_emitted_all_claims_20_symbols": bool((all_symbols >= SYMBOLS).all()),
               "nonoverlap_all_claims_20_symbols": bool((nonoverlap_symbols >= SYMBOLS).all()),
               "median_all_emitted_N": float(np.median(all_n)),
               "median_nonoverlap_N": float(np.median(nonoverlap_n)),
               "eligible_claim_slots": int(eligible.sum())}
    return eligible, summary


def _block_scores(counts: np.ndarray, wins: np.ndarray, block_length: int
                  ) -> np.ndarray:
    if counts.shape != wins.shape or counts.ndim != 2:
        raise ValueError("counts and wins must be same-shaped day-by-claim matrices")
    if block_length < 1:
        raise ValueError("block_length must be positive")
    daily = wins - TARGET * counts
    blocks = [daily[start:start + block_length].sum(axis=0)
              for start in range(0, len(daily), block_length)]
    result = np.stack(blocks, axis=0)
    if result.shape[0] < 2 or not np.isfinite(result).all():
        raise ValueError("at least two finite temporal clusters are required")
    return result


def _mammen_weights(rng: np.random.Generator, reps: int, clusters: int
                    ) -> np.ndarray:
    root5 = math.sqrt(5.0)
    negative = (1.0 - root5) / 2.0
    positive = (1.0 + root5) / 2.0
    p_positive = (root5 - 1.0) / (2.0 * root5)
    draws = rng.random((reps, clusters)) < p_positive
    return np.where(draws, positive, negative)


def wild_cluster_test(block_scores: np.ndarray, eligible: np.ndarray, *,
                      bootstrap_reps: int, seed: int) -> dict:
    """Null-centered, synchronized Mammen wild-cluster bootstrap max-t test."""
    scores = np.asarray(block_scores, dtype=float)
    active = np.flatnonzero(np.asarray(eligible, dtype=bool))
    if scores.ndim != 2 or scores.shape[0] < 10 or scores.shape[1] != len(eligible):
        raise ValueError("scores must be clusters-by-family with >=10 clusters")
    if not np.isfinite(scores).all() or bootstrap_reps < 199:
        raise ValueError("scores must be finite and bootstrap_reps >=199")
    if len(active) == 0:
        return {"eligible_claim_count": 0, "reject_any": False,
                "critical": None, "observed_max_t": None}
    data = scores[:, active]
    clusters = len(data)
    centered = data - data.mean(axis=0, keepdims=True)
    observed_se = np.sqrt(clusters / (clusters - 1.0)
                          * np.sum(centered * centered, axis=0))
    if (observed_se <= 0).any() or not np.isfinite(observed_se).all():
        raise ValueError("observed cluster standard error is zero or invalid")
    observed = data.sum(axis=0) / observed_se
    rng = np.random.default_rng(seed)
    weights = _mammen_weights(rng, bootstrap_reps, clusters)
    weighted = weights[:, :, None] * centered[None, :, :]
    means = weighted.mean(axis=1, keepdims=True)
    bootstrap_se = np.sqrt(clusters / (clusters - 1.0)
                           * np.sum((weighted - means) ** 2, axis=1))
    if (bootstrap_se <= 0).any() or not np.isfinite(bootstrap_se).all():
        raise ValueError("wild-bootstrap standard error is zero or invalid")
    bootstrap_t = weighted.sum(axis=1) / bootstrap_se
    maximum = np.max(bootstrap_t, axis=1)
    critical = float(np.quantile(maximum, 1.0 - ALPHA, method="higher"))
    observed_max = float(np.max(observed))
    return {"eligible_claim_count": int(len(active)),
            "reject_any": bool(observed_max > critical),
            "critical": critical, "observed_max_t": observed_max}


def run(*, simulations: int, bootstrap_reps: int, days: int, seed: int,
        block_lengths: tuple[int, ...], profile: str) -> dict:
    if simulations < 1 or days < 40:
        raise ValueError("simulations must be positive and days >=40")
    settings = {
        "iid_bernoulli": {"rho_common": 0.0, "rho_symbol": 0.0,
                          "rho_frame": 0.0, "overlap_windows": False,
                          "clustered_issuance": False,
                          "independent_claim_outcomes": True},
        "overlap_common": {"rho_common": 0.0, "rho_symbol": 0.0,
                           "rho_frame": 0.0, "overlap_windows": True,
                           "clustered_issuance": True,
                           "independent_claim_outcomes": False},
        "persistent_clustered": {"rho_common": 0.70, "rho_symbol": 0.35,
                                 "rho_frame": 0.25, "overlap_windows": True,
                                 "clustered_issuance": True,
                                 "independent_claim_outcomes": False}}
    if profile not in settings:
        raise ValueError(f"unknown profile: {profile}")
    params = settings[profile]
    root_rng = np.random.default_rng(seed)
    results = []
    started = time.monotonic()
    for block_length in block_lengths:
        false_passes = errors = 0
        coverage_rates = []
        eligible_slots = []
        all_n200, nonoverlap_n200 = [], []
        for _ in range(simulations):
            replication_seed = int(root_rng.integers(0, np.iinfo(np.int32).max))
            labels, issued = R016.generate_replication(
                days=days, seed=replication_seed, **params)
            counts, wins = R016._daily_counts(labels, issued, days)
            eligible, summary = _eligibility(issued, counts, days=days)
            coverage_rates.append(summary["mean_raw_coverage"])
            eligible_slots.append(summary["eligible_claim_slots"])
            all_n200.append(summary["all_emitted_all_claims_N_ge_200"])
            nonoverlap_n200.append(summary["nonoverlap_all_claims_N_ge_200"])
            try:
                scores = _block_scores(counts, wins, block_length)
                result = wild_cluster_test(scores, eligible,
                                           bootstrap_reps=bootstrap_reps,
                                           seed=replication_seed ^ block_length)
                false_passes += int(result["reject_any"])
            except (ValueError, FloatingPointError):
                errors += 1
        possible_false = min(simulations, false_passes + errors)
        rate = possible_false / simulations
        z = 1.959963984540054
        denom = 1.0 + z * z / simulations
        center = (rate + z * z / (2.0 * simulations)) / denom
        half = z * math.sqrt(rate * (1.0 - rate) / simulations
                             + z * z / (4.0 * simulations * simulations)) / denom
        upper = min(1.0, center + half)
        results.append({"block_length": block_length,
                        "simulations": simulations,
                        "family_false_passes": false_passes,
                        "family_false_pass_rate_conservative": rate,
                        "family_false_pass_wilson95": [max(0.0, center - half), upper],
                        "failed_replications": errors,
                        "mean_eligible_claim_slots": float(np.mean(eligible_slots)),
                        "mean_raw_coverage": float(np.mean(coverage_rates)),
                        "all_emitted_N_ge_200_rate": float(np.mean(all_n200)),
                        "nonoverlap_N_ge_200_rate": float(np.mean(nonoverlap_n200)),
                        "screen_pass": bool(errors == 0 and upper <= 0.06)})
    return {"schema_version": 1, "run_id": "r017-wild-cluster-target-first",
            "method": "synchronized_mammen_wild_cluster_bootstrap_max_t",
            "profile": profile, "seed": seed, "days": days,
            "target_rate_null": TARGET, "alpha": ALPHA,
            "symbols": SYMBOLS, "timeframes": FRAMES, "horizons": list(HORIZONS),
            "claims_per_replication": FRAMES * len(HORIZONS),
            "family_branches": ["all_emitted", "outcome_blind_nonoverlap"],
            "bootstrap_reps": bootstrap_reps,
            "block_lengths": list(block_lengths), "settings": params,
            "results": results,
            "r016_generator_sha256": hashlib.sha256(R016_PATH.read_bytes()).hexdigest(),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "python": platform.python_version(), "numpy": np.__version__,
            "interpretation": "synthetic inference-method calibration only; no market outcomes"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=500)
    parser.add_argument("--bootstrap-reps", type=int, default=999)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--seed", type=int, default=20261122)
    parser.add_argument("--profile", choices=("iid_bernoulli", "overlap_common",
                                               "persistent_clustered"),
                        default="iid_bernoulli")
    parser.add_argument("--block-lengths", type=int, nargs="+", default=[1, 2, 5])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(simulations=args.simulations,
                 bootstrap_reps=args.bootstrap_reps,
                 days=args.days, seed=args.seed,
                 block_lengths=tuple(args.block_lengths), profile=args.profile)
    payload = json.dumps(result, indent=2, sort_keys=True).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload + b"\n")
    print(json.dumps({"output": str(args.output), "sha256": hashlib.sha256(payload).hexdigest(),
                      "elapsed_seconds": result["elapsed_seconds"],
                      "results": result["results"]}, sort_keys=True))


if __name__ == "__main__":
    main()
