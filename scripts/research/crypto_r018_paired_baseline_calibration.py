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
import time
from pathlib import Path

import numpy as np

CLAIMS = 24
CONTRASTS = 48
DAYS = 365
SYMBOLS = 20
HORIZONS = (10, 20)
BLOCKS = (1, 2, 5, 10, 20)


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


def paired_lower_bounds(n: np.ndarray, x: np.ndarray, *, reps: int,
                        mean_block: int, seed: int) -> dict:
    """One-sided max-T simultaneous lower bounds for paired mean differences."""
    n = np.asarray(n, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    if n.ndim != 2 or x.shape != n.shape or n.shape[1] != CONTRASTS:
        raise ValueError("n and x must be day-by-48-contrast matrices")
    if not np.isfinite(n).all() or not np.isfinite(x).all() or (n < 0).any():
        raise ValueError("non-finite or negative daily counts")
    total_n = n.sum(axis=0)
    if (total_n <= 0).any():
        raise ValueError("each contrast needs emitted events")
    delta = x.sum(axis=0) / total_n
    resid = x - n * delta
    d = n.shape[0]
    se = np.sqrt(d / (d - 1) * (resid * resid).sum(axis=0)) / total_n
    if not np.isfinite(se).all() or (se <= 0).any():
        raise ValueError("invalid observed cluster standard error")
    ix = stationary_indices(np.random.default_rng(seed), reps, d, mean_block)
    bn = n[ix].sum(axis=1)
    bx = x[ix].sum(axis=1)
    if (bn <= 0).any():
        raise ValueError("bootstrap sample has an empty contrast")
    delta_star = bx / bn
    residual_star = x[ix] - n[ix] * delta_star[:, None, :]
    se_star = np.sqrt(d / (d - 1) * (residual_star ** 2).sum(axis=1)) / bn
    if not np.isfinite(se_star).all() or (se_star <= 0).any():
        raise ValueError("invalid bootstrap cluster standard error")
    t_star = (delta_star - delta[None, :]) / se_star
    max_t = t_star.max(axis=1)
    critical = float(np.quantile(max_t, 0.95, method="higher"))
    return {"delta": delta, "se": se,
            "lower": delta - critical * se, "critical": critical,
            "false_superiority": bool(np.any(delta - critical * se > 0.0))}


def synthetic_panel(seed: int, days: int = DAYS) -> tuple[np.ndarray, np.ndarray, dict]:
    """Generate an hourly-anchor IID boundary panel under the frozen contract."""
    rng = np.random.default_rng(seed)
    hours = days * 24
    # Signal issuance follows the preregistered hot/cold Markov process for
    # each timeframe-symbol stream and is independent of synthetic outcomes.
    hot = rng.random((12, SYMBOLS)) < 0.12
    issued = np.zeros((12, hours, SYMBOLS), dtype=bool)
    for t in range(hours):
        if t:
            prior = hot
            hot = np.where(prior, rng.random(prior.shape) >= 0.22,
                           rng.random(prior.shape) < 0.035)
        chance = np.where(hot, 0.48, 0.045)
        issued[:, t, :] = rng.random((12, SYMBOLS)) < chance
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
            for symbol in range(SYMBOLS):
                anchors = np.flatnonzero(issued[frame, :, symbol])
                next_allowed = 0
                for anchor in anchors:
                    if anchor >= next_allowed:
                        selected[frame, anchor, symbol] = True
                        next_allowed = int(anchor + horizon)
            for day in range(days):
                lo, hi = day * 24, (day + 1) * 24
                daily_n[day, c] = issued[frame, lo:hi, :].sum()
                daily_nonoverlap[day, c] = selected[frame, lo:hi, :].sum()
            symbols_nonoverlap[c] = selected[frame].any(axis=0).sum()
    eligible = ((daily_nonoverlap.sum(axis=0) >= 200) &
                (symbols_nonoverlap >= SYMBOLS) &
                np.repeat(coverage >= 0.10, len(HORIZONS)))
    # Construct all-emitted paired contrasts. Candidate and each comparator
    # share exactly the emitted anchors; their marginal rates are equal.
    x = np.empty((days, CONTRASTS), dtype=np.float64)
    pvals = (0.25, 0.50, 0.80, 0.95)
    corr = (0.25, 0.50, 0.80)
    for c in range(CLAIMS):
        frame = c // len(HORIZONS)
        mask = issued[frame]
        event_times, event_symbols = np.nonzero(mask)
        day_ids = event_times // 24
        p = pvals[c % len(pvals)]
        r = corr[c % len(corr)]
        # Profile A: independent event factors; no overlap-window dependence.
        event_count = len(event_times)
        common = rng.normal(size=event_count)
        eps_c = rng.normal(size=event_count)
        cutoff = _norm_ppf(p)
        yc = (math.sqrt(r) * common + math.sqrt(1 - r) * eps_c) <= cutoff
        for comparator in range(2):
            eps_b = rng.normal(size=event_count)
            yb = (math.sqrt(r) * common + math.sqrt(1 - r) * eps_b) <= cutoff
            pos = 2 * c + comparator
            x[:, pos] = np.bincount(day_ids, weights=yc.astype(np.int8) -
                                    yb.astype(np.int8), minlength=days)
    paired_n = np.repeat(daily_n, 2, axis=1)
    return paired_n, x, {"eligible_claims": eligible,
                         "nonoverlap_n": daily_nonoverlap,
                         "coverage": coverage}


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
    for s in range(simulations):
        panel_seed = np.random.SeedSequence([seed, s]).generate_state(1)[0].item()
        n, x, aux = synthetic_panel(int(panel_seed))
        if n.shape != (DAYS, CONTRASTS) or x.shape != (DAYS, CONTRASTS):
            raise AssertionError("smoke panel schema mismatch")
        if not (aux["eligible_claims"].all() and
                (aux["nonoverlap_n"].sum(axis=0) >= 200).all() and
                (aux["coverage"] >= 0.10).all()):
            raise AssertionError("synthetic eligibility fixture failed")
        for block in BLOCKS:
            a = paired_lower_bounds(n, x, reps=bootstrap_reps,
                                    mean_block=block, seed=seed + s + block)
            b = paired_lower_bounds(n, x, reps=bootstrap_reps,
                                    mean_block=block, seed=seed + s + block)
            if a["critical"] != b["critical"] or not np.array_equal(a["lower"], b["lower"]):
                raise AssertionError("deterministic replay mismatch")
        outcomes.append({"panel": s, "all_emitted_N": int(n.sum()),
                         "nonoverlap_min_N": int(aux["nonoverlap_n"].sum(axis=0).min()),
                         "eligible_claims": CLAIMS})
    return {"run_id": "r018-smoke", "seed": seed, "simulations": simulations,
            "bootstrap_reps": bootstrap_reps, "claims": CLAIMS,
            "paired_contrasts": CONTRASTS, "block_lengths": list(BLOCKS),
            "method_only": True, "market_data_read": False,
            "outcomes": outcomes,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "elapsed_seconds": round(time.monotonic() - t0, 3)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = run_smoke()
    raw = json.dumps(result, sort_keys=True, indent=2).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw + b"\n")
    print(json.dumps({"output": str(args.output), "sha256": hashlib.sha256(raw).hexdigest(),
                      "elapsed_seconds": result["elapsed_seconds"],
                      "panels": len(result["outcomes"]),
                      "method_only": True}, sort_keys=True))


if __name__ == "__main__":
    main()
