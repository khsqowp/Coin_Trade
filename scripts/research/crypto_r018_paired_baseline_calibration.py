#!/usr/bin/env python3
"""Synthetic-only paired-baseline inference smoke harness for R018.

This module deliberately consumes no candle database or market-result files.
Its Bernoulli outcomes are method-test fixtures, not strategy evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import time
from pathlib import Path

import numpy as np

CLAIMS = 24
CONTRASTS = 48
DAYS = 365
SYMBOLS = 20
HORIZONS = (10, 20)
BLOCKS = (1, 2, 5, 10, 20)
ALTERNATIVES = ((0.79, 0.50), (0.80, 0.50), (0.80, 0.80),
                (0.85, 0.50), (0.85, 0.80))
NORMAL_975 = 1.959963984540054


def child_seed(root: int, *coordinates: int) -> int:
    """Stable NumPy SeedSequence child keyed by the full experiment cell."""
    return int(np.random.SeedSequence([root, *coordinates]).generate_state(1)[0])


def select_nonoverlap(issued: np.ndarray, horizon: int) -> np.ndarray:
    """Greedy earliest-event selector, using timestamps only."""
    issued = np.asarray(issued, dtype=bool)
    if issued.ndim != 2 or horizon < 1:
        raise ValueError("issued must be time-by-symbol and horizon positive")
    selected = np.zeros_like(issued)
    for symbol in range(issued.shape[1]):
        next_allowed = 0
        for anchor in np.flatnonzero(issued[:, symbol]):
            if anchor >= next_allowed:
                selected[anchor, symbol] = True
                next_allowed = int(anchor + horizon)
    return selected


def claim_eligibility(nonoverlap_n: int, nonoverlap_symbols: int,
                      coverage: float, *, unresolved_count: int = 0) -> bool:
    return (nonoverlap_n >= 200 and nonoverlap_symbols >= SYMBOLS and
            coverage >= 0.10 and unresolved_count == 0)


def m2_summary(emitted: int, resolved_wins: int, unresolved: int) -> dict:
    if emitted < 0 or resolved_wins < 0 or unresolved < 0:
        raise ValueError("counts must be nonnegative")
    resolved = emitted - unresolved
    if resolved < 0 or resolved_wins > resolved:
        raise ValueError("inconsistent emitted/resolved counts")
    return {"status": "INCONCLUSIVE" if unresolved else "RESOLVED",
            "m2_resolved": (resolved_wins / resolved if resolved else None),
            "m2_unresolved_as_loss": (resolved_wins / emitted if emitted else None),
            "emitted": emitted, "resolved": resolved, "unresolved": unresolved}


def joint_promotion(m2: np.ndarray, eligible_claims: np.ndarray,
                    lower_bounds: np.ndarray) -> np.ndarray:
    """Apply the fixed point-M2 and both-baseline superiority gates by claim."""
    m2 = np.asarray(m2, dtype=np.float64)
    eligible = np.asarray(eligible_claims, dtype=bool)
    lower = np.asarray(lower_bounds, dtype=np.float64)
    if m2.shape != (CLAIMS,) or eligible.shape != (CLAIMS,):
        raise ValueError("M2 and eligibility need one value per claim")
    if lower.shape != (CONTRASTS,):
        raise ValueError("lower_bounds must contain 48 paired contrasts")
    both_baselines = np.column_stack((lower[0::2], lower[1::2])).min(axis=1)
    return eligible & (m2 >= 0.80) & (both_baselines > 0.0)


def stationary_indices(rng: np.random.Generator, reps: int, days: int,
                       mean_block: int) -> np.ndarray:
    """Circular stationary-bootstrap indices, shape (reps, days)."""
    if reps < 1 or days < 2 or not 1 <= mean_block <= days:
        raise ValueError("invalid stationary-bootstrap dimensions")
    ix = np.empty((reps, days), dtype=np.int32)
    restart = 1.0 / mean_block
    ix[:, 0] = rng.integers(days, size=reps)
    for d in range(1, days):
        reset = rng.random(reps) < restart
        ix[:, d] = np.where(reset, rng.integers(days, size=reps),
                            (ix[:, d - 1] + 1) % days)
    return ix


def assert_prefix_invariant(forecast_fn, prefix: np.ndarray,
                            future_a: np.ndarray, future_b: np.ndarray) -> None:
    """Reject a forecast function whose output changes when only future data changes."""
    prefix = np.asarray(prefix)
    a, b = np.asarray(future_a), np.asarray(future_b)
    if prefix.ndim < 1 or a.shape != b.shape or a.ndim != prefix.ndim:
        raise ValueError("prefix and future alternatives must have matching ranks")
    if prefix.shape[1:] != a.shape[1:]:
        raise ValueError("future alternatives must match the prefix feature shape")
    left = np.asarray(forecast_fn(np.concatenate((prefix, a), axis=0)))
    right = np.asarray(forecast_fn(np.concatenate((prefix, b), axis=0)))
    if left.shape[0] < len(prefix) or right.shape[0] < len(prefix):
        raise AssertionError("forecast function returned too few prefix outputs")
    if not np.array_equal(left[:len(prefix)], right[:len(prefix)]):
        raise AssertionError("future-peeking detected: prefix forecast changed")


def paired_lower_bounds(n: np.ndarray, x: np.ndarray, *, reps: int,
                        mean_block: int, seed: int,
                        eligible_contrasts: np.ndarray | None = None,
                        batch_size: int = 32) -> dict:
    """One-sided max-T simultaneous lower bounds for paired mean differences."""
    n = np.asarray(n, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    if n.ndim != 2 or x.shape != n.shape or n.shape[1] != CONTRASTS:
        raise ValueError("n and x must be day-by-48-contrast matrices")
    if not np.isfinite(n).all() or not np.isfinite(x).all() or (n < 0).any():
        raise ValueError("non-finite or negative daily counts")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    eligible = (np.ones(CONTRASTS, dtype=bool) if eligible_contrasts is None
                else np.asarray(eligible_contrasts, dtype=bool))
    if eligible.shape != (CONTRASTS,):
        raise ValueError("eligible_contrasts must have 48 flags")
    active = np.flatnonzero(eligible)
    if active.size == 0:
        return {"delta": np.full(CONTRASTS, np.nan),
                "se": np.full(CONTRASTS, np.nan),
                "lower": np.full(CONTRASTS, np.nan), "critical": None,
                "false_superiority": False, "eligible_contrasts": 0}
    n, x = n[:, active], x[:, active]
    total_n = n.sum(axis=0)
    if (total_n <= 0).any():
        raise ValueError("each contrast needs emitted events")
    delta = x.sum(axis=0) / total_n
    resid = x - n * delta
    d = n.shape[0]
    se = np.sqrt(d / (d - 1) * (resid * resid).sum(axis=0)) / total_n
    if not np.isfinite(se).all() or (se <= 0).any():
        raise ValueError("invalid observed cluster standard error")
    indices = stationary_indices(np.random.default_rng(seed), reps, d, mean_block)
    # Exact sufficient-statistic form of the same cluster bootstrap. A sampled
    # day may occur repeatedly; its multiplicity is its weight. This avoids
    # materializing reps×days×contrasts copies of n/x in Python batches.
    weights = np.zeros((reps, d), dtype=np.float64)
    rows = np.repeat(np.arange(reps, dtype=np.int32), d)
    np.add.at(weights, (rows, indices.reshape(-1)), 1.0)
    bn = weights @ n
    bx = weights @ x
    if (bn <= 0).any():
        raise ValueError("bootstrap sample has an empty contrast")
    delta_star = bx / bn
    sum_x2 = weights @ (x * x)
    sum_xn = weights @ (x * n)
    sum_n2 = weights @ (n * n)
    residual_ss = sum_x2 - 2.0 * delta_star * sum_xn + delta_star * delta_star * sum_n2
    if (residual_ss < -1e-9).any():
        raise ValueError("negative bootstrap residual sum of squares")
    residual_ss = np.maximum(residual_ss, 0.0)
    se_star = np.sqrt(d / (d - 1) * residual_ss) / bn
    if not np.isfinite(se_star).all() or (se_star <= 0).any():
        raise ValueError("invalid bootstrap cluster standard error")
    t_star = (delta_star - delta[None, :]) / se_star
    max_t = t_star.max(axis=1)
    critical = float(np.quantile(max_t, 0.95, method="higher"))
    lower = np.full(CONTRASTS, np.nan)
    delta_full, se_full = np.full(CONTRASTS, np.nan), np.full(CONTRASTS, np.nan)
    delta_full[active], se_full[active] = delta, se
    lower[active] = delta - critical * se
    return {"delta": delta_full, "se": se_full, "lower": lower,
            "critical": critical,
            "false_superiority": bool(np.any(lower[active] > 0.0)),
            "eligible_contrasts": int(active.size)}


def _ar1(rng: np.random.Generator, steps: int, columns: int, rho: float) -> np.ndarray:
    out = np.empty((steps, columns), dtype=np.float64)
    out[0] = rng.normal(size=columns)
    innovation = math.sqrt(1.0 - rho * rho)
    for t in range(1, steps):
        out[t] = rho * out[t - 1] + innovation * rng.normal(size=columns)
    return out


def _future_mean(x: np.ndarray, horizon: int) -> np.ndarray:
    """At anchor t return mean(x[t+1:t+H+1]); uses no anchor/current sample."""
    prefix = np.concatenate((np.zeros((1,) + x.shape[1:]),
                             np.cumsum(x, axis=0)), axis=0)
    return ((prefix[horizon + 1:horizon + 1 + (len(x) - horizon)] -
             prefix[1:1 + (len(x) - horizon)]) / horizon)


def _ar_mean_variance(horizon: int, rho: float) -> float:
    return (horizon + 2 * sum((horizon - lag) * rho ** lag
                              for lag in range(1, horizon))) / (horizon ** 2)


def synthetic_panel(seed: int, days: int = DAYS, *, profile: str = "A",
                    alternative: bool = False, missingness: str = "none"
                    ) -> tuple[np.ndarray, np.ndarray, dict]:
    """Generate paired synthetic labels under one preregistered R018 profile."""
    if profile not in {"A", "B", "C"}:
        raise ValueError("profile must be A, B, or C")
    if missingness not in {"none", "independent_1pct", "shock_5pct"}:
        raise ValueError("unknown missingness scenario")
    if profile == "A" and missingness == "shock_5pct":
        raise ValueError("shock_5pct requires the shared common factor in profile B or C")
    seed_seq = np.random.SeedSequence(seed)
    issue_seed, outcome_seed = seed_seq.spawn(2)
    rng_issue = np.random.default_rng(issue_seed)
    rng = np.random.default_rng(outcome_seed)
    hours = days * 24
    # Signal issuance follows the preregistered hot/cold Markov process for
    # each timeframe-symbol stream and is independent of synthetic outcomes.
    hot = rng_issue.random((12, SYMBOLS)) < 0.12
    issued = np.zeros((12, hours, SYMBOLS), dtype=bool)
    for t in range(hours):
        if t:
            prior = hot
            hot = np.where(prior, rng_issue.random(prior.shape) >= 0.22,
                           rng_issue.random(prior.shape) < 0.035)
        chance = np.where(hot, 0.48, 0.045)
        issued[:, t, :] = rng_issue.random((12, SYMBOLS)) < chance
    coverage = issued.mean(axis=(1, 2))
    daily_n = np.zeros((days, CLAIMS), dtype=np.float64)
    daily_nonoverlap = np.zeros_like(daily_n)
    symbols_nonoverlap = np.zeros((CLAIMS,), dtype=np.int64)
    # Outcome-blind earliest-event selector: suppress later anchors until H
    # hourly synthetic bins after the selected event.
    selected = np.zeros_like(issued)
    for frame in range(12):
        for horizon_i, horizon in enumerate(HORIZONS):
            c = frame * len(HORIZONS) + horizon_i
            selected[frame] = select_nonoverlap(issued[frame], horizon)
            for day in range(days):
                lo, hi = day * 24, (day + 1) * 24
                daily_n[day, c] = issued[frame, lo:hi, :].sum()
                daily_nonoverlap[day, c] = selected[frame, lo:hi, :].sum()
            symbols_nonoverlap[c] = selected[frame].any(axis=0).sum()
    # R018's fixed profiles use clustered issuance; profile A isolates IID
    # outcomes, while B/C add overlapping future-window dependence.
    if profile == "A":
        common = symbol_factor = frame_factor = None
        rho_common = rho_symbol = rho_frame = 0.0
    else:
        rho_common, rho_symbol, rho_frame = ((0.0, 0.0, 0.0) if profile == "B"
                                             else (0.70, 0.35, 0.25))
        steps = hours + max(HORIZONS)
        common = _ar1(rng, steps, 1, rho_common)[:, 0]
        symbol_factor = _ar1(rng, steps, SYMBOLS, rho_symbol)
        frame_factor = _ar1(rng, steps, 12, rho_frame)
    # Construct all-emitted paired contrasts. Candidate and each comparator
    # share exactly the emitted anchors; their marginal rates are equal.
    x = np.empty((days, CONTRASTS), dtype=np.float64)
    daily_candidate_wins = np.zeros((days, CLAIMS), dtype=np.float64)
    daily_baseline_wins = np.zeros((days, CONTRASTS), dtype=np.float64)
    pvals = (0.25, 0.50, 0.80, 0.95)
    corr = (0.25, 0.50, 0.80)
    unresolved_by_claim = np.zeros(CLAIMS, dtype=np.int64)
    resolved_wins = np.zeros(CLAIMS, dtype=np.int64)
    daily_resolved_n = np.zeros((days, CLAIMS), dtype=np.float64)
    raw_emitted = daily_n.sum(axis=0).astype(np.int64)
    for c in range(CLAIMS):
        frame = c // len(HORIZONS)
        horizon = HORIZONS[c % len(HORIZONS)]
        mask = issued[frame]
        event_times, event_symbols = np.nonzero(mask)
        day_ids = event_times // 24
        p_baseline = pvals[c % len(pvals)]
        if alternative:
            p_candidate, p_baseline = ALTERNATIVES[c % len(ALTERNATIVES)]
        else:
            p_candidate = p_baseline
        r = corr[c % len(corr)]
        event_count = len(event_times)
        if profile == "A":
            latent = rng.normal(size=event_count)
            shock = np.zeros(event_count, dtype=bool)
        else:
            avar = _ar_mean_variance(horizon, rho_common)
            bvar = _ar_mean_variance(horizon, rho_symbol)
            cvar = _ar_mean_variance(horizon, rho_frame)
            af = _future_mean(common[:, None], horizon)[:hours, 0] / math.sqrt(avar)
            bf = _future_mean(symbol_factor, horizon)[:hours] / math.sqrt(bvar)
            cf = _future_mean(frame_factor[:, frame:frame + 1], horizon)[:hours, 0] / math.sqrt(cvar)
            latent_grid = (math.sqrt(0.35) * af[:, None] +
                           math.sqrt(0.45) * bf + math.sqrt(0.20) * cf[:, None])
            latent = latent_grid[event_times, event_symbols]
            # The 5% stress is keyed to the standardized shared UTC-time
            # factor at the anchor, not to policy outcomes or symbol factors.
            shock = np.abs(common[event_times]) > NORMAL_975
        unresolved = (rng.random(event_count) < 0.01 if missingness == "independent_1pct"
                      else shock if missingness == "shock_5pct"
                      else np.zeros(event_count, dtype=bool))
        unresolved_by_claim[c] = int(unresolved.sum())
        resolved = ~unresolved
        daily_resolved_n[:, c] = np.bincount(day_ids[resolved], minlength=days)
        eps_c = rng.normal(size=event_count)
        candidate_score = math.sqrt(r) * latent + math.sqrt(1 - r) * eps_c
        yc = candidate_score <= _norm_ppf(p_candidate)
        resolved_wins[c] = int(yc[resolved].sum())
        daily_candidate_wins[:, c] = np.bincount(
            day_ids[resolved], weights=yc[resolved].astype(np.int8), minlength=days)
        for comparator in range(2):
            eps_b = rng.normal(size=event_count)
            baseline_score = math.sqrt(r) * latent + math.sqrt(1 - r) * eps_b
            yb = baseline_score <= _norm_ppf(p_baseline)
            pos = 2 * c + comparator
            daily_baseline_wins[:, pos] = np.bincount(
                day_ids[resolved], weights=yb[resolved].astype(np.int8), minlength=days)
            x[:, pos] = np.bincount(day_ids[resolved], weights=yc[resolved].astype(np.int8) -
                                    yb[resolved].astype(np.int8), minlength=days)
    paired_n = np.repeat(daily_resolved_n, 2, axis=1)
    eligible = np.array([claim_eligibility(
        int(daily_nonoverlap[:, c].sum()), int(symbols_nonoverlap[c]),
        float(coverage[c // len(HORIZONS)]),
        unresolved_count=int(unresolved_by_claim[c])) for c in range(CLAIMS)])
    resolved_n = daily_resolved_n.sum(axis=0)
    m2 = np.divide(resolved_wins, resolved_n, out=np.full(CLAIMS, np.nan),
                   where=resolved_n > 0)
    return paired_n, x, {"eligible_claims": eligible,
                         "nonoverlap_n": daily_nonoverlap,
                         "nonoverlap_symbols": symbols_nonoverlap,
                         "coverage": coverage,
                         "candidate_wins": daily_candidate_wins,
                         "baseline_wins": daily_baseline_wins,
                         "resolved_wins": resolved_wins,
                         "m2_resolved": m2,
                         "m2_status": np.where(unresolved_by_claim > 0,
                                               "INCONCLUSIVE", "RESOLVED"),
                         "unresolved_by_claim": unresolved_by_claim,
                         "raw_emitted": raw_emitted,
                         "all_loss_m2": np.divide(resolved_wins, raw_emitted,
                                                  out=np.full(CLAIMS, np.nan),
                                                  where=raw_emitted > 0)}


def _norm_ppf(p: float) -> float:
    a = (-39.69683028665376, 220.9460984245205, -275.9285104469687,
         138.3577518672690, -30.66479806614716, 2.506628277459239)
    b = (-54.47609879822406, 161.5858368580409, -155.6989798598866,
         66.80131188771972, -13.28068155288572)
    c = (-0.007784894002430293, -0.3223964580411365, -2.400758277161838,
         -2.549732539343734, 4.374664141464968, 2.938163982698783)
    d = (0.007784695709041462, 0.3224671290700398, 2.445134137142996,
         3.754408661907416)
    if not 0 < p < 1:
        raise ValueError("p must be strictly between zero and one")
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > 1 - 0.02425:
        q = math.sqrt(-2 * math.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def run_smoke(simulations: int = 10, bootstrap_reps: int = 199,
              seed: int = 20261120) -> dict:
    if simulations != 10 or bootstrap_reps != 199:
        raise ValueError("R018 smoke is frozen at 10 panels and 199 draws")
    t0 = time.monotonic()
    outcomes = []
    seed_cells = [child_seed(seed, 0, 0, panel, block, 0)
                  for panel in range(simulations) for block in BLOCKS]
    if len(set(seed_cells)) != len(seed_cells):
        raise AssertionError("duplicate hierarchical seed cell")
    prefix = np.array([[1.0], [2.0], [3.0]])
    future_a, future_b = np.array([[4.0], [5.0]]), np.array([[40.0], [-50.0]])
    assert_prefix_invariant(lambda v: np.cumsum(v, axis=0), prefix, future_a, future_b)
    try:
        assert_prefix_invariant(lambda v: v + np.roll(v, -1, axis=0),
                                prefix, future_a, future_b)
    except AssertionError as exc:
        if "future-peeking" not in str(exc):
            raise
    else:
        raise AssertionError("injected future-peeking rule passed the causal guard")
    for s in range(simulations):
        panel_seed = child_seed(seed, 0, 0, s)
        n, x, aux = synthetic_panel(int(panel_seed))
        if n.shape != (DAYS, CONTRASTS) or x.shape != (DAYS, CONTRASTS):
            raise AssertionError("smoke panel schema mismatch")
        if not (aux["eligible_claims"].all() and
                (aux["nonoverlap_n"].sum(axis=0) >= 200).all() and
                (aux["nonoverlap_symbols"] >= SYMBOLS).all() and
                (aux["coverage"] >= 0.10).all()):
            raise AssertionError("synthetic eligibility fixture failed")
        for block in BLOCKS:
            a = paired_lower_bounds(n, x, reps=bootstrap_reps,
                                    mean_block=block,
                                    seed=child_seed(seed, 0, 0, s, block, 0))
            b = paired_lower_bounds(n, x, reps=bootstrap_reps,
                                    mean_block=block,
                                    seed=child_seed(seed, 0, 0, s, block, 0))
            if a["critical"] != b["critical"] or not np.array_equal(a["lower"], b["lower"]):
                raise AssertionError("deterministic replay mismatch")
            if a["eligible_contrasts"] != CONTRASTS:
                raise AssertionError("max-T family did not include all 48 contrasts")
        all_n = n[:, 0::2].sum(axis=0)
        all_w = aux["candidate_wins"].sum(axis=0)
        m2 = all_w / all_n
        if not np.array_equal(m2, aux["m2_resolved"]):
            raise AssertionError("M2 denominator is not the all-emitted resolved ledger")
        baseline_m2 = aux["baseline_wins"].sum(axis=0) / n.sum(axis=0)
        outcomes.append({"panel": s, "all_emitted_N": int(all_n.sum()),
                         "nonoverlap_min_N": int(aux["nonoverlap_n"].sum(axis=0).min()),
                         "nonoverlap_min_symbols": int(aux["nonoverlap_symbols"].min()),
                         "m2_min": float(m2.min()), "m2_max": float(m2.max()),
                         "baseline_m2_min": float(baseline_m2.min()),
                         "baseline_m2_max": float(baseline_m2.max()),
                         "eligible_claims": CLAIMS})
    return {"run_id": "r018-smoke", "seed": seed, "simulations": simulations,
            "bootstrap_reps": bootstrap_reps, "claims": CLAIMS,
            "paired_contrasts": CONTRASTS, "block_lengths": list(BLOCKS),
            "method_only": True, "market_data_read": False,
            "outcomes": outcomes,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "elapsed_seconds": round(time.monotonic() - t0, 3)}


def _wilson95(successes: int, trials: int) -> list[float]:
    if trials < 1 or not 0 <= successes <= trials:
        raise ValueError("invalid binomial counts")
    z = 1.959963984540054
    rate = successes / trials
    denom = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / denom
    half = z * math.sqrt(rate * (1-rate) / trials +
                         z*z / (4*trials*trials)) / denom
    return [max(0.0, center-half), min(1.0, center+half)]


def _atomic_json(path: Path, value: dict) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    os.replace(temp, path)


def _record_digest(record: dict) -> str:
    unsigned = dict(record)
    unsigned.pop("record_sha256", None)
    raw = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _validate_panel_record(record: dict, *, panel: int, source_hash: str,
                           config_hash: str, panel_seed: int) -> None:
    required = {"panel", "source_sha256", "config_sha256", "panel_seed",
                "m2_by_claim", "baseline_m2_by_contrast", "blocks", "errors",
                "record_sha256", "eligible_by_claim"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise ValueError("checkpoint panel schema is incomplete")
    if (record["panel"] != panel or record["source_sha256"] != source_hash or
            record["config_sha256"] != config_hash or record["panel_seed"] != panel_seed):
        raise ValueError("checkpoint panel identity does not match run configuration")
    if (len(record["m2_by_claim"]) != CLAIMS or
            len(record["eligible_by_claim"]) != CLAIMS or
            len(record["baseline_m2_by_contrast"]) != CONTRASTS or
            set(record["blocks"]) != {str(block) for block in BLOCKS}):
        raise ValueError("checkpoint panel dimensions do not match registered family")
    if record["record_sha256"] != _record_digest(record):
        raise ValueError("checkpoint panel checksum mismatch")


def _validate_profile_a_gate(gate: dict, *, source_hash: str,
                             simulations: int, bootstrap_reps: int,
                             seed: int) -> None:
    if (gate.get("run_id") != "r018-profile-A-null-none" or
            gate.get("profile") != "A" or gate.get("scenario") != "null" or
            gate.get("missingness") != "none" or
            gate.get("simulations") != simulations or
            gate.get("bootstrap_reps") != bootstrap_reps or
            gate.get("seed") != seed or gate.get("source_sha256") != source_hash or
            gate.get("blocks") != list(BLOCKS) or
            [row.get("block_length") for row in gate.get("results", [])] != list(BLOCKS) or
            len(gate.get("results", [])) != len(BLOCKS) or
            not all(row.get("gate_pass") is True for row in gate["results"])):
        raise ValueError("profile-A calibration gates did not all pass exact registered run")


def _calibration_decision(scenario: str, eligible_rate: float,
                          wilson_upper: float, errors: int) -> tuple[str, bool | None]:
    if scenario == "alternatives":
        return "POWER_DIAGNOSTIC", None
    if eligible_rate < 0.95:
        return "INCONCLUSIVE", False
    passed = wilson_upper <= 0.06 and errors == 0
    return ("PASS" if passed else "REJECT"), passed


def run_iid_boundary(*, output_dir: Path, simulations: int = 5000,
                     bootstrap_reps: int = 1999, seed: int = 20261123,
                     resume: bool = False, scenario: str = "null",
                     profile: str = "A", missingness: str = "none",
                     baseline_results: Path | None = None) -> dict:
    """Execute one preregistered scenario, with resumable panel checkpoints."""
    if simulations != 5000 or bootstrap_reps != 1999 or seed != 20261123:
        raise ValueError("R018 primary calibration counts/seed are preregistered")
    if scenario not in {"null", "alternatives"}:
        raise ValueError("scenario must be null or alternatives")
    if profile not in {"A", "B", "C"}:
        raise ValueError("profile must be A, B, or C")
    if missingness not in {"none", "independent_1pct", "shock_5pct"}:
        raise ValueError("unknown missingness scenario")
    if profile == "A" and missingness == "shock_5pct":
        raise ValueError("shock_5pct requires profile B or C")
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    baseline_gate_sha256 = None
    if profile != "A":
        if baseline_results is None or not baseline_results.is_file():
            raise ValueError("profile B/C requires the completed profile-A gate result")
        gate_result = json.loads(baseline_results.read_text())
        _validate_profile_a_gate(gate_result, source_hash=source_hash,
                                 simulations=simulations,
                                 bootstrap_reps=bootstrap_reps, seed=seed)
        baseline_gate_sha256 = hashlib.sha256(baseline_results.read_bytes()).hexdigest()
    scenario_index = 0 if scenario == "null" else 1
    profile_index = ord(profile) - ord("A")
    missing_index = {"none": 0, "independent_1pct": 1, "shock_5pct": 2}[missingness]
    config = {"run_id": f"r018-profile-{profile}-{scenario}-{missingness}",
              "scenario": scenario, "profile": profile, "missingness": missingness,
              "simulations": simulations, "bootstrap_reps": bootstrap_reps,
              "seed": seed, "blocks": list(BLOCKS), "claims": CLAIMS,
              "contrasts": CONTRASTS, "days": DAYS,
              "baseline_gate_sha256": baseline_gate_sha256,
              "source_sha256": source_hash, "numpy": np.__version__,
              "python": platform.python_version(), "market_data_read": False}
    config_hash = hashlib.sha256(json.dumps(
        config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest_path = output_dir / "manifest.json"
    if output_dir.exists():
        if not resume or not manifest_path.is_file():
            raise FileExistsError(f"output exists; pass --resume to continue: {output_dir}")
        old = json.loads(manifest_path.read_text())
        if old != config:
            raise ValueError("resume manifest does not match this exact run configuration")
    else:
        output_dir.mkdir(parents=True)
        _atomic_json(manifest_path, config)
    t0 = time.monotonic()
    block_rows = {block: [] for block in BLOCKS}
    eligibility_counts = []
    panel_records = []
    completed = 0
    for panel in range(simulations):
        panel_path = output_dir / f"panel_{panel:05d}.json"
        if panel_path.exists():
            prior = json.loads(panel_path.read_text())
            expected_seed = child_seed(seed, profile_index, scenario_index,
                                       missing_index, panel, 0)
            try:
                _validate_panel_record(prior, panel=panel, source_hash=source_hash,
                                       config_hash=config_hash, panel_seed=expected_seed)
            except ValueError as exc:
                raise ValueError(f"invalid checkpoint panel file: {panel_path}: {exc}") from exc
            panel_result = prior
        else:
            panel_seed = child_seed(seed, profile_index, scenario_index,
                                    missing_index, panel, 0)
            n, x, aux = synthetic_panel(
                panel_seed, profile=profile,
                alternative=(scenario == "alternatives"), missingness=missingness)
            claim_ok = aux["eligible_claims"]
            contrast_ok = np.repeat(claim_ok, 2)
            m2 = aux["m2_resolved"]
            true_delta = np.zeros(CONTRASTS, dtype=np.float64)
            if scenario == "alternatives":
                for claim in range(CLAIMS):
                    pc, pb = ALTERNATIVES[claim % len(ALTERNATIVES)]
                    true_delta[2 * claim:2 * claim + 2] = pc - pb
            panel_blocks = {}
            errors = {}
            for block in BLOCKS:
                try:
                    inference = paired_lower_bounds(
                        n, x, reps=bootstrap_reps, mean_block=block,
                        seed=child_seed(seed, profile_index, scenario_index,
                                        missing_index, panel, block, 0),
                        eligible_contrasts=contrast_ok)
                    promoted = joint_promotion(m2, claim_ok, inference["lower"])
                    family_reject = bool(np.any(inference["lower"][contrast_ok] > 0.0))
                    family_covered = bool(claim_ok.all() and np.all(
                        inference["lower"][contrast_ok] <= true_delta[contrast_ok]))
                    panel_blocks[str(block)] = {
                        "status": ("INELIGIBLE" if inference["critical"] is None else "OK"),
                        "unconditional_family_rejection": bool(claim_ok.all() and family_reject),
                        "conditional_family_rejection": bool(claim_ok.all() and family_reject),
                        "joint_user_rule_any": bool(claim_ok.all() and promoted.any()),
                        "joint_user_rule_claims": int(promoted.sum()),
                        "joint_user_rule_claims_by_claim": promoted.tolist(),
                        "family_covered": family_covered,
                        "eligible_contrasts": inference["eligible_contrasts"],
                        "critical": inference["critical"]}
                except (ValueError, FloatingPointError) as exc:
                    errors[str(block)] = type(exc).__name__ + ": " + str(exc)
                    panel_blocks[str(block)] = {"status": "ERROR",
                                                "unconditional_family_rejection": False,
                                                "conditional_family_rejection": False,
                                                "joint_user_rule_any": False,
                                                "joint_user_rule_claims": 0,
                                                "joint_user_rule_claims_by_claim": [False] * CLAIMS,
                                                "family_covered": False,
                                                "eligible_contrasts": int(contrast_ok.sum()),
                                                "critical": None}
            panel_result = {
                "panel": panel, "source_sha256": source_hash,
                "config_sha256": config_hash, "panel_seed": panel_seed,
                "all_emitted_n": int(n[:, 0::2].sum()),
                "min_nonoverlap_n": int(aux["nonoverlap_n"].sum(axis=0).min()),
                "min_nonoverlap_symbols": int(aux["nonoverlap_symbols"].min()),
                "min_timeframe_coverage": float(aux["coverage"].min()),
                "eligible_claims": int(claim_ok.sum()),
                "eligible_by_claim": claim_ok.tolist(),
                "all_claims_eligible": bool(claim_ok.all()),
                "m2_min": float(np.min(m2)), "m2_max": float(np.max(m2)),
                "m2_by_claim": m2.tolist(),
                "all_loss_m2_by_claim": aux["all_loss_m2"].tolist(),
                "unresolved_by_claim": aux["unresolved_by_claim"].tolist(),
                "resolved_n_by_claim": (n[:, 0::2].sum(axis=0)).tolist(),
                "baseline_m2_by_contrast": (aux["baseline_wins"].sum(axis=0) /
                                             n.sum(axis=0)).tolist(),
                "errors": errors, "blocks": panel_blocks}
            panel_result["record_sha256"] = _record_digest(panel_result)
            _atomic_json(panel_path, panel_result)
        completed += 1
        panel_records.append(panel_result)
        eligibility_counts.append(int(panel_result["eligible_claims"]))
        for block in BLOCKS:
            block_rows[block].append(panel_result["blocks"][str(block)])
        if completed % 25 == 0:
            print(json.dumps({"progress_panels": completed,
                              "elapsed_seconds": round(time.monotonic()-t0, 1)},
                             sort_keys=True), flush=True)
    summaries = []
    for block, rows in block_rows.items():
        raw_rejections = sum(bool(row["unconditional_family_rejection"]) for row in rows)
        conditional_rows = [row for row in rows
                            if row.get("eligible_contrasts") == CONTRASTS and
                            row.get("status") == "OK"]
        conditional_rejections = sum(bool(row["conditional_family_rejection"])
                                     for row in rows)
        errors = sum(row.get("status") == "ERROR" for row in rows)
        possible_false = min(simulations, raw_rejections + errors)
        rejection_rate = raw_rejections / simulations
        wilson = _wilson95(possible_false, simulations)
        conditional_covered = sum(bool(row["family_covered"])
                                  for row in conditional_rows)
        alternative_rates = None
        if scenario == "alternatives":
            alternative_rates = []
            for alt_i, pair in enumerate(ALTERNATIVES):
                claims = [c for c in range(CLAIMS) if c % len(ALTERNATIVES) == alt_i]
                point_hits = sum(
                    bool(record["eligible_by_claim"][c]) and
                    float(record["m2_by_claim"][c]) >= 0.80
                    for record in panel_records for c in claims)
                joint_hits = sum(
                    bool(record["blocks"][str(block)][
                        "joint_user_rule_claims_by_claim"][c])
                    for record in panel_records for c in claims)
                eligible_instances = sum(bool(record["eligible_by_claim"][c])
                                         for record in panel_records for c in claims)
                alternative_rates.append({
                    "p_candidate": pair[0], "p_baseline": pair[1],
                    "claim_instances": simulations * len(claims),
                    "eligible_claim_instances": int(eligible_instances),
                    "candidate_point_gate_hits": int(point_hits),
                    "candidate_point_gate_rate": (point_hits / eligible_instances
                                                   if eligible_instances else None),
                    "joint_rule_hits": int(joint_hits),
                    "joint_rule_rate": (joint_hits / eligible_instances
                                         if eligible_instances else None)})
        eligible_rate = len(conditional_rows) / simulations
        decision, gate_pass = _calibration_decision(
            scenario, eligible_rate, wilson[1], errors)
        summaries.append({
            "block_length": block, "simulations": simulations,
            "unconditional_family_rejections": raw_rejections,
            "unconditional_family_rejection_rate": rejection_rate,
            "paired_fwer": rejection_rate if scenario == "null" else None,
            "paired_fwer_wilson95_conservative_errors": wilson if scenario == "null" else None,
            "conditional_all_claims_family_rejections": conditional_rejections,
            "conditional_all_claims_family_rejection_rate": (
                conditional_rejections / len(conditional_rows)
                if conditional_rows else None),
            "all_claims_eligible_rate": eligible_rate,
            "failed_panel_block_cells": errors,
            "joint_user_rule_false_promotions": sum(
                bool(row["joint_user_rule_any"]) for row in rows),
            "joint_user_rule_rate": sum(bool(row["joint_user_rule_any"])
                                         for row in rows) / simulations,
            "simultaneous_family_coverage": sum(bool(row["family_covered"])
                                                 for row in rows) / simulations,
            "conditional_all_claims_simultaneous_coverage": (
                conditional_covered / len(conditional_rows)
                if conditional_rows else None),
            "eligible_claims_mean": float(np.mean(eligibility_counts)),
            "alternative_point_and_joint_rates": alternative_rates,
            "decision": decision,
            "gate_pass": gate_pass})
    result = {**config, "results": summaries,
              "elapsed_seconds": round(time.monotonic() - t0, 3),
              "interpretation": "synthetic paired-inference calibration only"}
    _atomic_json(output_dir / "results.json", result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--full-iid-calibration", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--scenario", choices=("null", "alternatives"), default="null")
    ap.add_argument("--profile", choices=("A", "B", "C"), default="A")
    ap.add_argument("--missingness", choices=("none", "independent_1pct", "shock_5pct"),
                    default="none")
    ap.add_argument("--baseline-results", type=Path)
    args = ap.parse_args()
    if args.full_iid_calibration:
        result = run_iid_boundary(output_dir=args.output, resume=args.resume,
                                  scenario=args.scenario, profile=args.profile,
                                  missingness=args.missingness,
                                  baseline_results=args.baseline_results)
        print(json.dumps({"output": str(args.output / "results.json"),
                          "elapsed_seconds": result["elapsed_seconds"],
                          "results": result["results"], "method_only": True},
                         sort_keys=True))
    else:
        result = run_smoke()
        raw = json.dumps(result, sort_keys=True, indent=2).encode()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw + b"\n")
        print(json.dumps({"output": str(args.output),
                          "sha256": hashlib.sha256(raw).hexdigest(),
                          "elapsed_seconds": result["elapsed_seconds"],
                          "panels": len(result["outcomes"]),
                          "method_only": True}, sort_keys=True))


if __name__ == "__main__":
    main()
