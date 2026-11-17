#!/usr/bin/env python3
"""R019 synthetic-only multi-scale block-multiplier calibration.

This method study reads no market candles or outcome labels. Its synthetic
Bernoulli outcomes are fixtures for inference-method calibration only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import time
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
R018_PATH = HERE / "crypto_r018_paired_baseline_calibration.py"
_SPEC = importlib.util.spec_from_file_location("r018_for_r019", R018_PATH)
R018 = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(R018)

CLAIMS = R018.CLAIMS
CONTRASTS = R018.CONTRASTS
DAYS = R018.DAYS
BLOCKS = R018.BLOCKS
SIMULATIONS = 5000
BOOTSTRAP_REPS = 1999
MASTER_SEED = 20261124
METHOD_ID = "r019-overlapping-block-multiplier-multiscale-v1"


def multiscale_claim_promotions(m2: np.ndarray, eligible: np.ndarray,
                               lower_by_block: np.ndarray) -> np.ndarray:
    """Pass only when both baselines clear every frozen dependence scale."""
    m2 = np.asarray(m2, dtype=np.float64)
    eligible = np.asarray(eligible, dtype=bool)
    lower = np.asarray(lower_by_block, dtype=np.float64)
    if m2.shape != (CLAIMS,) or eligible.shape != (CLAIMS,):
        raise ValueError("M2 and eligibility must contain 24 claims")
    if lower.shape != (len(BLOCKS), CONTRASTS):
        raise ValueError("lower_by_block must have shape (5, 48)")
    both = lower.reshape(len(BLOCKS), CLAIMS, 2) > 0.0
    both_baselines_all_scales = both.all(axis=0).all(axis=1)
    return eligible & (m2 >= 0.80) & both_baselines_all_scales


def block_multiplier_lower_bounds(n: np.ndarray, x: np.ndarray, *,
                                  reps: int, block_length: int, seed: int,
                                  eligible_contrasts: np.ndarray | None = None
                                  ) -> dict:
    """One-sided max-T lower bounds via overlapping block-sum multipliers.

    The day-level influence vectors preserve paired contrasts. One normal
    multiplier is shared across all 48 coordinates at each overlapping-block
    start, preserving cross-contrast dependence. The method is accepted only
    after its complete preregistered Monte Carlo calibration passes.
    """
    n = np.asarray(n, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    if n.ndim != 2 or n.shape != x.shape or n.shape[1] != CONTRASTS:
        raise ValueError("n and x must be matching day-by-48 matrices")
    if not np.isfinite(n).all() or not np.isfinite(x).all() or (n < 0).any():
        raise ValueError("n/x must be finite and counts nonnegative")
    days = n.shape[0]
    ell = int(block_length)
    if days < 2 or not 1 <= ell <= days or reps < 1:
        raise ValueError("invalid day, block-length, or replicate count")
    eligible = (np.ones(CONTRASTS, dtype=bool) if eligible_contrasts is None
                else np.asarray(eligible_contrasts, dtype=bool))
    if eligible.shape != (CONTRASTS,):
        raise ValueError("eligible_contrasts must contain 48 flags")
    active = np.flatnonzero(eligible)
    full_delta = np.full(CONTRASTS, np.nan)
    full_se = np.full(CONTRASTS, np.nan)
    full_lower = np.full(CONTRASTS, np.nan)
    if not active.size:
        return {"delta": full_delta, "se": full_se, "lower": full_lower,
                "critical": None, "eligible_contrasts": 0,
                "block_starts": days - ell + 1}

    nn, xx = n[:, active], x[:, active]
    total_n = nn.sum(axis=0)
    if (total_n <= 0).any():
        raise ValueError("each eligible contrast must have emitted events")
    delta = xx.sum(axis=0) / total_n
    influence = xx - nn * delta[None, :]

    # Prefix differences produce every overlapping length-ell vector block.
    prefix = np.vstack((np.zeros((1, active.size)), np.cumsum(influence, axis=0)))
    block_sums = prefix[ell:] - prefix[:-ell]
    starts = block_sums.shape[0]
    block_ss = np.einsum("ij,ij->j", block_sums, block_sums)
    if (not np.isfinite(block_ss).all()) or (block_ss <= 0.0).any():
        raise ValueError("invalid overlapping-block long-run variance")

    rng = np.random.default_rng(seed)
    multipliers = rng.standard_normal((reps, starts))
    bootstrap_sums = multipliers @ block_sums
    studentized = bootstrap_sums / np.sqrt(block_ss)[None, :]
    if not np.isfinite(studentized).all():
        raise ValueError("non-finite block-multiplier statistic")
    critical = float(np.quantile(studentized.max(axis=1), 0.95, method="higher"))

    # Bartlett long-run variance from overlapping block sums. Each ratio
    # influence mean has variance approximately D*Omega/N^2.
    omega_diag = block_ss / (starts * ell)
    se = np.sqrt(days * omega_diag) / total_n
    if not np.isfinite(se).all() or (se <= 0.0).any():
        raise ValueError("invalid ratio standard error")
    lower = delta - critical * se
    full_delta[active], full_se[active], full_lower[active] = delta, se, lower
    return {"delta": full_delta, "se": full_se, "lower": full_lower,
            "critical": critical, "eligible_contrasts": int(active.size),
            "block_starts": int(starts)}


def _record_digest(record: dict) -> str:
    clean = {key: value for key, value in record.items() if key != "record_sha256"}
    raw = json.dumps(clean, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                               allow_nan=False) + "\n")
    os.replace(temp, path)


def _wilson95(successes: int, trials: int) -> tuple[float, float]:
    return R018._wilson95(successes, trials)


def _panel_result(panel: int, profile: str, *, source_hash: str,
                  config_hash: str) -> dict:
    profile_i = ord(profile) - ord("A")
    panel_seed = R018.child_seed(MASTER_SEED, 19, profile_i, panel, 0)
    n, x, aux = R018.synthetic_panel(panel_seed, profile=profile,
                                    alternative=False, missingness="none")
    claim_ok = np.asarray(aux["eligible_claims"], dtype=bool)
    contrast_ok = np.repeat(claim_ok, 2)
    lowers = np.full((len(BLOCKS), CONTRASTS), np.nan)
    criticals, errors = {}, {}
    for ell in BLOCKS:
        seed = R018.child_seed(MASTER_SEED, 19, profile_i, panel, ell)
        try:
            result = block_multiplier_lower_bounds(
                n, x, reps=BOOTSTRAP_REPS, block_length=ell,
                seed=seed, eligible_contrasts=contrast_ok)
            if result["eligible_contrasts"] != int(contrast_ok.sum()):
                raise ValueError("eligible contrast count mismatch")
            lowers[BLOCKS.index(ell)] = result["lower"]
            criticals[str(ell)] = result["critical"]
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            errors[str(ell)] = type(exc).__name__ + ": " + str(exc)
            criticals[str(ell)] = None

    if not errors:
        m2 = np.asarray(aux["m2_resolved"], dtype=np.float64)
        robust_pair_fwer = bool(np.any(np.all(lowers[:, contrast_ok] > 0.0, axis=0)))
        full_promotions = multiscale_claim_promotions(m2, claim_ok, lowers)
        single_scale_fwer = {
            str(ell): bool(np.any(lowers[i, contrast_ok] > 0.0))
            for i, ell in enumerate(BLOCKS)}
        single_scale_covered = {
            str(ell): bool(np.all(lowers[i, contrast_ok] <= 0.0))
            for i, ell in enumerate(BLOCKS)}
        robust_covered = bool(np.all(lowers[:, contrast_ok] <= 0.0))
    else:
        m2 = np.asarray(aux["m2_resolved"], dtype=np.float64)
        robust_pair_fwer = False
        full_promotions = np.zeros(CLAIMS, dtype=bool)
        single_scale_fwer = {str(ell): False for ell in BLOCKS}
        single_scale_covered = {str(ell): False for ell in BLOCKS}
        robust_covered = False

    record = {
        "panel": panel, "profile": profile,
        "source_sha256": source_hash, "config_sha256": config_hash,
        "panel_seed": panel_seed,
        "all_emitted_n": int(n[:, 0::2].sum()),
        "eligible_by_claim": claim_ok.tolist(),
        "eligible_claims": int(claim_ok.sum()),
        "all_claims_eligible": bool(claim_ok.all()),
        "min_nonoverlap_n": int(aux["nonoverlap_n"].sum(axis=0).min()),
        "min_nonoverlap_symbols": int(aux["nonoverlap_symbols"].min()),
        "min_timeframe_coverage": float(aux["coverage"].min()),
        "m2_by_claim": m2.tolist(),
        "unresolved_by_claim": np.asarray(aux["unresolved_by_claim"]).tolist(),
        "single_scale_fwer": single_scale_fwer,
        "single_scale_covered": single_scale_covered,
        "multiscale_pair_family_false_superiority": robust_pair_fwer,
        "multiscale_full_rule_false_promotions": int(full_promotions.sum()),
        "multiscale_full_rule_any": bool(full_promotions.any()),
        "multiscale_family_covered": robust_covered,
        "critical_by_block": criticals,
        "errors": errors,
    }
    record["record_sha256"] = _record_digest(record)
    return record


def run_null_profile(output_dir: Path, profile: str, *, resume: bool = False,
                     simulations: int = SIMULATIONS,
                     bootstrap_reps: int = BOOTSTRAP_REPS,
                     master_seed: int = MASTER_SEED) -> dict:
    """Run one fixed R19-N profile, with exact resumable panel records."""
    if simulations != SIMULATIONS or bootstrap_reps != BOOTSTRAP_REPS:
        raise ValueError("R19-N simulations/draws are preregistered at 5000/1999")
    if master_seed != MASTER_SEED or profile not in {"A", "B", "C"}:
        raise ValueError("R19-N master seed/profile is preregistered")
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    dependency_hash = hashlib.sha256(R018_PATH.read_bytes()).hexdigest()
    config = {
        "method_id": METHOD_ID, "profile": profile, "scenario": "null",
        "missingness": "none", "simulations": simulations,
        "bootstrap_reps": bootstrap_reps, "master_seed": master_seed,
        "block_lengths": list(BLOCKS), "claims": CLAIMS,
        "contrasts": CONTRASTS, "days": DAYS,
        "source_sha256": source_hash,
        "r018_generator_sha256": dependency_hash,
        "numpy": np.__version__, "python": platform.python_version(),
        "market_data_read": False,
    }
    config_hash = hashlib.sha256(json.dumps(
        config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = output_dir / "manifest.json"
    if output_dir.exists():
        if not resume or not manifest.is_file():
            raise FileExistsError(f"output exists; pass --resume for exact run: {output_dir}")
        prior_config = json.loads(manifest.read_text())
        if prior_config != config:
            raise ValueError("resume manifest differs from frozen configuration")
    else:
        output_dir.mkdir(parents=True)
        _atomic_json(manifest, config)

    start = time.monotonic()
    records = []
    for panel in range(simulations):
        panel_file = output_dir / f"panel_{panel:05d}.json"
        if panel_file.is_file():
            record = json.loads(panel_file.read_text())
            digest = record.get("record_sha256")
            if (record.get("panel") != panel or
                    record.get("source_sha256") != source_hash or
                    record.get("config_sha256") != config_hash or
                    digest != _record_digest(record)):
                raise ValueError(f"checkpoint mismatch or checksum error: {panel_file}")
        else:
            record = _panel_result(panel, profile, source_hash=source_hash,
                                   config_hash=config_hash)
            _atomic_json(panel_file, record)
        records.append(record)
        if (panel + 1) % 25 == 0:
            print(json.dumps({"profile": profile, "progress_panels": panel + 1,
                              "elapsed_seconds": round(time.monotonic()-start, 1)},
                             sort_keys=True), flush=True)

    scale_rows = []
    for ell in BLOCKS:
        false_count = sum(bool(row["single_scale_fwer"][str(ell)]) for row in records)
        coverage = sum(bool(row["single_scale_covered"][str(ell)]) for row in records)
        scale_rows.append({"block_length": ell, "false_family_rejections": false_count,
                           "false_family_rate": false_count / simulations,
                           "wilson95": _wilson95(false_count, simulations),
                           "simultaneous_coverage": coverage / simulations})
    pair_false = sum(bool(r["multiscale_pair_family_false_superiority"]) for r in records)
    full_false = sum(bool(r["multiscale_full_rule_any"]) for r in records)
    errors = sum(bool(r["errors"]) for r in records)
    all_eligible = sum(bool(r["all_claims_eligible"]) for r in records)
    pair_wilson = _wilson95(pair_false, simulations)
    full_wilson = _wilson95(full_false, simulations)
    eligible_rate = all_eligible / simulations
    gate_pass = (pair_wilson[1] <= 0.06 and full_wilson[1] <= 0.06 and
                 eligible_rate >= 0.95 and errors == 0)
    result = {
        **config, "elapsed_seconds": round(time.monotonic() - start, 3),
        "interpretation": "synthetic multi-scale block-multiplier calibration only",
        "multiscale_pair_false_family_rejections": pair_false,
        "multiscale_pair_false_family_rate": pair_false / simulations,
        "multiscale_pair_false_family_wilson95": pair_wilson,
        "multiscale_full_rule_false_promotions": full_false,
        "multiscale_full_rule_false_promotion_rate": full_false / simulations,
        "multiscale_full_rule_wilson95": full_wilson,
        "all_claims_eligible_panels": all_eligible,
        "all_claims_eligible_rate": eligible_rate,
        "failed_panels": int(errors), "single_scale_diagnostics": scale_rows,
        "multiscale_family_coverage": sum(
            bool(r["multiscale_family_covered"]) for r in records) / simulations,
        "decision": "PASS" if gate_pass else "REJECT",
        "gate_pass": bool(gate_pass),
    }
    _atomic_json(output_dir / "results.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("A", "B", "C"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = run_null_profile(args.output, args.profile, resume=args.resume)
    print(json.dumps({"output": str(args.output / "results.json"),
                      "decision": result["decision"],
                      "pair_rate": result["multiscale_pair_false_family_rate"],
                      "full_rule_rate": result["multiscale_full_rule_false_promotion_rate"],
                      "elapsed_seconds": result["elapsed_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
