#!/usr/bin/env python3
"""Synthetic-only calibration for dependent target-first rate claims.

This is an inference-method diagnostic. It does not read candles, market labels,
or candidate strategy outputs and cannot qualify a trading strategy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from pathlib import Path

import numpy as np

TARGET_RATE = 0.80
ALPHA = 0.05
SYMBOLS = 20
FRAMES = 12
HORIZONS = (10, 20)


def _ar1(rng: np.random.Generator, length: int, rho: float) -> np.ndarray:
    if not -0.999 < rho < 1.0:
        raise ValueError("rho must be in (-0.999, 1)")
    values = np.empty(length, dtype=float)
    values[0] = rng.normal()
    scale = math.sqrt(1.0 - rho * rho)
    for i in range(1, length):
        values[i] = rho * values[i - 1] + scale * rng.normal()
    return values


def _normal_cdf(values: np.ndarray) -> np.ndarray:
    return np.fromiter((0.5 * (1.0 + math.erf(float(x) / math.sqrt(2.0)))
                        for x in values.ravel()), dtype=float).reshape(values.shape)


def _ar_average_variance(horizon: int, rho: float) -> float:
    """Variance of sqrt(H) times an H-point stationary AR(1) average."""
    return (horizon + 2.0 * sum((horizon - lag) * rho ** lag
                                for lag in range(1, horizon))) / horizon


def _issue_mask(rng: np.random.Generator, days: int, symbols: int,
                frames: int, *, clustered: bool = True) -> np.ndarray:
    """Markov-clustered forecast issuance, approximately 10% coverage."""
    if not clustered:
        return rng.random((frames, days, symbols)) < 0.105
    hot = np.zeros((frames, days, symbols), dtype=bool)
    issued = np.zeros_like(hot)
    hot[:, 0, :] = rng.random((frames, symbols)) < 0.12
    for day in range(days):
        if day:
            prior = hot[:, day - 1, :]
            turn_on = rng.random((frames, symbols)) < 0.035
            turn_off = rng.random((frames, symbols)) < 0.22
            hot[:, day, :] = np.where(prior, ~turn_off, turn_on)
        chance = np.where(hot[:, day, :], 0.48, 0.045)
        issued[:, day, :] = rng.random((frames, symbols)) < chance
    return issued


def _nonoverlap_mask(issued: np.ndarray, horizon: int) -> np.ndarray:
    """Greedy earliest-event sample; selection uses issuance times only."""
    frames, days, symbols = issued.shape
    selected = np.zeros_like(issued)
    for frame in range(frames):
        for symbol in range(symbols):
            next_allowed = 0
            for day in range(days):
                if day >= next_allowed and issued[frame, day, symbol]:
                    selected[frame, day, symbol] = True
                    next_allowed = day + horizon
    return selected


def generate_replication(*, days: int, seed: int,
                         rho_common: float = 0.70,
                         rho_symbol: float = 0.35,
                         rho_frame: float = 0.25,
                         overlap_windows: bool = True,
                         clustered_issuance: bool = True,
                         independent_claim_outcomes: bool = False
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Return target-first labels and issue masks for 12×2 synthetic claims.

    Labels are generated from an exactly-80%-marginal probit mixture. Each
    outcome depends on overlapping future-window latent shocks, with common
    serial dependence and symbol-level serial dependence. This outcome model
    is intentionally synthetic and is not a simulated market-price strategy.
    """
    if days < 40:
        raise ValueError("days must be at least 40 for the 20-step horizon")
    rng = np.random.default_rng(seed)
    common = _ar1(rng, days + max(HORIZONS), rho_common)
    idiosyncratic = np.column_stack([_ar1(rng, days + max(HORIZONS), rho_symbol)
                                     for _ in range(SYMBOLS)])
    issued = _issue_mask(rng, days, SYMBOLS, FRAMES, clustered=clustered_issuance)
    from statistics import NormalDist
    cutoff = NormalDist().inv_cdf(TARGET_RATE)
    claim_labels = []
    for frame in range(FRAMES):
        frame_noise = _ar1(rng, days + max(HORIZONS), rho_frame)
        for horizon in HORIZONS:
            # Future-window average makes adjacent target-first outcomes
            # dependent; synchronized factors couple symbols and claims.
            latent = (rng.normal(size=(days, SYMBOLS))
                      if independent_claim_outcomes else _future_window_latent(
                          common, idiosyncratic, frame_noise, days=days,
                          horizon=horizon, rho_common=rho_common,
                          rho_symbol=rho_symbol, rho_frame=rho_frame,
                          overlap_windows=overlap_windows))
            heterogeneity = 0.70
            conditional_p = _normal_cdf((cutoff - math.sqrt(heterogeneity) * latent)
                                        / math.sqrt(1.0 - heterogeneity))
            claim_labels.append(rng.random((days, SYMBOLS)) < conditional_p)
    labels = np.stack(claim_labels, axis=0)
    repeated_issues = np.repeat(issued[:, None, :, :], len(HORIZONS), axis=1)
    return labels, repeated_issues.reshape(FRAMES * len(HORIZONS), days, SYMBOLS)


def _daily_counts(labels: np.ndarray, issued: np.ndarray,
                  days: int) -> tuple[np.ndarray, np.ndarray]:
    """Aggregate full-issue and outcome-blind non-overlap ledgers by day."""
    claims = labels.shape[0]
    count_columns = []
    win_columns = []
    for claim in range(claims):
        frame = claim // len(HORIZONS)
        horizon = HORIZONS[claim % len(HORIZONS)]
        all_mask = issued[claim]
        selected_mask = _nonoverlap_mask(issued[claim:claim + 1], horizon)[0]
        for mask in (all_mask, selected_mask):
            count_columns.append(mask.sum(axis=1))
            win_columns.append((mask & labels[claim]).sum(axis=1))
    counts = np.column_stack(count_columns).astype(float)
    wins = np.column_stack(win_columns).astype(float)
    if counts.shape != (days, claims * 2) or wins.shape != counts.shape:
        raise AssertionError("daily aggregation shape mismatch")
    return counts, wins


def _stationary_indices(rng: np.random.Generator, *, reps: int, days: int,
                        mean_block: int) -> np.ndarray:
    if reps < 20 or not 1 <= mean_block <= days:
        raise ValueError("reps must be >=20 and mean_block within [1, days]")
    indices = np.empty((reps, days), dtype=np.int32)
    restart = 1.0 / mean_block
    for rep in range(reps):
        indices[rep, 0] = rng.integers(days)
        for day in range(1, days):
            if rng.random() < restart:
                indices[rep, day] = rng.integers(days)
            else:
                indices[rep, day] = (indices[rep, day - 1] + 1) % days
    return indices


def simultaneous_lower_bounds(counts: np.ndarray, wins: np.ndarray, *,
                              bootstrap_reps: int, block_length: int,
                              seed: int,
                              eligible_claims: np.ndarray | None = None) -> dict:
    """Synchronized stationary-block maximum-standardized-error bounds.

    Both denominator branches (all emitted; outcome-blind non-overlap) are in
    one 48-claim family, preventing selection of the more favorable branch.
    This is a candidate method only; calibration results determine whether it
    is rejected, not accepted for market inference.
    """
    count = np.asarray(counts, dtype=float)
    win = np.asarray(wins, dtype=float)
    if count.ndim != 2 or win.shape != count.shape or count.shape[0] < 40:
        raise ValueError("counts/wins must be same-shaped day-by-claim matrices")
    if not np.isfinite(count).all() or not np.isfinite(win).all():
        raise ValueError("counts/wins must be finite")
    if (count < 0).any() or (win < 0).any() or (win > count).any():
        raise ValueError("invalid success/count totals")
    total_n, total_w = count.sum(axis=0), win.sum(axis=0)
    eligible = (np.ones(count.shape[1], dtype=bool) if eligible_claims is None
                else np.asarray(eligible_claims, dtype=bool))
    if eligible.shape != total_n.shape:
        raise ValueError("eligible_claims must have one flag per family claim")
    if ((total_n == 0) & eligible).any():
        raise ValueError("eligible claim has no emitted events")
    estimate = np.full_like(total_n, np.nan, dtype=float)
    estimate[total_n > 0] = total_w[total_n > 0] / total_n[total_n > 0]
    active = np.flatnonzero(eligible)
    lower = np.full_like(estimate, np.nan)
    if len(active) == 0:
        return {"estimate": estimate, "lower": lower,
                "critical": None, "reject_any_at_80": False,
                "eligible_claim_count": 0,
                "claim_count": int(count.shape[1])}
    active_count = count[:, active]
    active_wins = win[:, active]
    rng = np.random.default_rng(seed)
    indices = _stationary_indices(rng, reps=bootstrap_reps,
                                  days=count.shape[0], mean_block=block_length)
    boot_n = active_count[indices].sum(axis=1)
    boot_w = active_wins[indices].sum(axis=1)
    if (boot_n == 0).any():
        raise ValueError("bootstrap replicate omitted an entire claim")
    boot_p = boot_w / boot_n
    se = boot_p.std(axis=0, ddof=1)
    if (se <= 0).any() or not np.isfinite(se).all():
        raise ValueError("bootstrap standard error is zero or invalid")
    active_estimate = estimate[active]
    max_t = np.max((active_estimate[None, :] - boot_p) / se[None, :], axis=1)
    critical = float(np.quantile(max_t, 1.0 - ALPHA, method="higher"))
    lower[active] = active_estimate - critical * se
    return {"estimate": estimate, "lower": lower, "se": se,
            "critical": critical,
            "reject_any_at_80": bool(np.any((lower > TARGET_RATE) & eligible)),
            "eligible_claim_count": int(eligible.sum()),
            "claim_count": int(len(estimate)),
            "tested_claim_count": int(len(active))}


def _unique_symbol_counts(issued: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Count emitted and outcome-blind non-overlap symbols per claim."""
    all_symbols = issued.any(axis=1).sum(axis=1)
    selected_symbols = []
    for claim in range(issued.shape[0]):
        horizon = HORIZONS[claim % len(HORIZONS)]
        selected = _nonoverlap_mask(issued[claim:claim + 1], horizon)[0]
        selected_symbols.append(int(selected.any(axis=0).sum()))
    return all_symbols.astype(int), np.asarray(selected_symbols, dtype=int)


def _future_window_latent(common: np.ndarray, idiosyncratic: np.ndarray,
                          frame_noise: np.ndarray, *, days: int, horizon: int,
                          rho_common: float, rho_symbol: float, rho_frame: float,
                          overlap_windows: bool) -> np.ndarray:
    """Build standardized latent outcomes strictly from anchor+1 onward."""
    if overlap_windows:
        future = [(math.sqrt(0.35) * common[offset:offset + days, None]
                   + math.sqrt(0.45) * idiosyncratic[offset:offset + days]
                   + math.sqrt(0.20) * frame_noise[offset:offset + days, None])
                  for offset in range(1, horizon + 1)]
        latent = np.mean(future, axis=0) * math.sqrt(horizon)
        variance = sum(weight * _ar_average_variance(horizon, rho)
                       for weight, rho in ((0.35, rho_common),
                                           (0.45, rho_symbol),
                                           (0.20, rho_frame)))
        return latent / math.sqrt(variance)
    return (math.sqrt(0.35) * common[1:days + 1, None]
            + math.sqrt(0.45) * idiosyncratic[1:days + 1]
            + math.sqrt(0.20) * frame_noise[1:days + 1, None])


def run_calibration(*, simulations: int = 500, bootstrap_reps: int = 399,
                    days: int = 365, seed: int = 20261117,
                    block_lengths: tuple[int, ...] = (10, 20, 40, 60, 90, 180),
                    rho_common: float = 0.70, rho_symbol: float = 0.35,
                    rho_frame: float = 0.25, overlap_windows: bool = True,
                    clustered_issuance: bool = True,
                    independent_claim_outcomes: bool = False) -> dict:
    if simulations < 1:
        raise ValueError("simulations must be positive")
    started = time.monotonic()
    rng = np.random.default_rng(seed)
    results = []
    for block_length in block_lengths:
        false_pass = 0
        errors = 0
        coverage = []
        all_claims_n200 = []
        nonoverlap_claims_n200 = []
        all_claims_20_symbols = []
        nonoverlap_claims_20_symbols = []
        all_event_counts = []
        nonoverlap_counts = []
        for _ in range(simulations):
            replication_seed = int(rng.integers(0, np.iinfo(np.int32).max))
            labels, issued = generate_replication(
                days=days, seed=replication_seed, rho_common=rho_common,
                rho_symbol=rho_symbol, rho_frame=rho_frame,
                overlap_windows=overlap_windows,
                clustered_issuance=clustered_issuance,
                independent_claim_outcomes=independent_claim_outcomes)
            counts, wins = _daily_counts(labels, issued, days)
            claim_counts = counts.sum(axis=0)
            all_n = claim_counts[::2].astype(int)
            nonoverlap_n = claim_counts[1::2].astype(int)
            all_event_counts.extend(all_n.tolist())
            nonoverlap_counts.extend(nonoverlap_n.tolist())
            all_claims_n200.append(bool(np.all(all_n >= 200)))
            nonoverlap_claims_n200.append(bool(np.all(nonoverlap_n >= 200)))
            all_symbol_n, nonoverlap_symbol_n = _unique_symbol_counts(issued)
            all_claims_20_symbols.append(bool(np.all(all_symbol_n >= SYMBOLS)))
            nonoverlap_claims_20_symbols.append(
                bool(np.all(nonoverlap_symbol_n >= SYMBOLS)))
            frame_coverage = issued.reshape(FRAMES, len(HORIZONS), days,
                                            SYMBOLS)[:, 0].mean(axis=(1, 2))
            coverage.append(frame_coverage)
            claim_eligibility = np.repeat(frame_coverage >= 0.10, len(HORIZONS))
            joint_eligibility = np.column_stack((
                claim_eligibility & (all_n >= 200) & (all_symbol_n >= SYMBOLS),
                claim_eligibility & (nonoverlap_n >= 200)
                & (nonoverlap_symbol_n >= SYMBOLS))).ravel()
            try:
                result = simultaneous_lower_bounds(
                    counts, wins, bootstrap_reps=bootstrap_reps,
                    block_length=block_length, seed=replication_seed ^ block_length,
                    eligible_claims=joint_eligibility)
                false_pass += int(result["reject_any_at_80"])
            except (ValueError, FloatingPointError):
                errors += 1
        rate = false_pass / simulations
        conservative_count = min(simulations, false_pass + errors)
        conservative_rate = conservative_count / simulations
        # Wilson upper bound, 95%; failures count as possible false passes.
        z = 1.959963984540054
        denom = 1.0 + z * z / simulations
        center = (conservative_rate + z * z / (2 * simulations)) / denom
        half = z * math.sqrt(conservative_rate * (1 - conservative_rate) / simulations
                             + z * z / (4 * simulations * simulations)) / denom
        upper = min(1.0, center + half)
        results.append({"mean_block_length": block_length,
                        "simulations": simulations,
                        "family_false_passes": false_pass,
                        "family_false_pass_rate": rate,
                        "family_false_pass_rate_conservative_errors_as_pass": conservative_rate,
                        "family_false_pass_wilson95": [max(0.0, center - half),
                                                         upper],
                        "failed_replications": errors,
                        "mean_raw_coverage": float(np.mean(coverage)),
                        "all_timeframe_coverage_ge_10pct_rate": float(
                            np.mean([np.min(frame_coverage) >= 0.10
                                     for frame_coverage in coverage])),
                        "all_emitted_N_median": float(np.median(all_event_counts)),
                        "nonoverlap_N_median": float(np.median(nonoverlap_counts)),
                        "all_emitted_all_claims_N_ge_200_rate": float(np.mean(all_claims_n200)),
                        "nonoverlap_all_claims_N_ge_200_rate": float(
                            np.mean(nonoverlap_claims_n200)),
                        "all_emitted_all_claims_20_symbols_rate": float(
                            np.mean(all_claims_20_symbols)),
                        "nonoverlap_all_claims_20_symbols_rate": float(
                            np.mean(nonoverlap_claims_20_symbols)),
                        "screen_pass": bool(errors == 0 and upper <= 0.06)})
    return {"schema_version": 1,
            "run_id": "r016-synthetic-event-target-first-calibration",
            "method": "synchronized_stationary_block_bootstrap_max_standardized_error",
            "seed": seed, "target_rate_null": TARGET_RATE, "alpha": ALPHA,
            "symbols": SYMBOLS, "timeframes": FRAMES, "horizons": list(HORIZONS),
            "claims_per_replication": FRAMES * len(HORIZONS),
            "denominator_branches_in_joint_family": ["all_emitted", "outcome_blind_nonoverlap"],
            "days": days, "bootstrap_reps": bootstrap_reps,
            "block_lengths": list(block_lengths), "scenarios": results,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "dgp": {"marginal_target_first_probability": TARGET_RATE,
                    "common_ar1_rho": rho_common, "symbol_ar1_rho": rho_symbol,
                    "frame_ar1_rho": rho_frame,
                    "overlapping_future_window_labels": overlap_windows,
                    "clustered_signal_issuance": clustered_issuance,
                    "independent_claim_outcomes": independent_claim_outcomes,
                    "target_first_outcomes_are_synthetic_binary_labels": True},
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "python": platform.python_version(), "numpy": np.__version__,
            "interpretation": "synthetic method calibration only; not strategy or market evidence"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=500)
    parser.add_argument("--bootstrap-reps", type=int, default=399)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--seed", type=int, default=20261117)
    parser.add_argument("--block-lengths", type=int, nargs="+",
                        default=[10, 20, 40, 60, 90, 180])
    parser.add_argument("--rho-common", type=float, default=0.70)
    parser.add_argument("--rho-symbol", type=float, default=0.35)
    parser.add_argument("--rho-frame", type=float, default=0.25)
    parser.add_argument("--no-overlap-windows", action="store_true")
    parser.add_argument("--iid-issuance", action="store_true")
    parser.add_argument("--independent-claim-outcomes", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_calibration(simulations=args.simulations,
                             bootstrap_reps=args.bootstrap_reps,
                             days=args.days, seed=args.seed,
                             block_lengths=tuple(args.block_lengths),
                             rho_common=args.rho_common,
                             rho_symbol=args.rho_symbol,
                             rho_frame=args.rho_frame,
                             overlap_windows=not args.no_overlap_windows,
                             clustered_issuance=not args.iid_issuance,
                             independent_claim_outcomes=args.independent_claim_outcomes)
    payload = json.dumps(result, indent=2, sort_keys=True).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload + b"\n")
    print(json.dumps({"output": str(args.output),
                      "sha256": hashlib.sha256(payload).hexdigest(),
                      "elapsed_seconds": result["elapsed_seconds"],
                      "scenarios": result["scenarios"]}, sort_keys=True))


if __name__ == "__main__":
    main()
