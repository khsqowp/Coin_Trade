#!/usr/bin/env python3
"""R019-P synthetic-only partial-null, power, and missingness evaluation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R018_PATH = HERE / "crypto_r018_paired_baseline_calibration.py"
R019_PATH = HERE / "crypto_r019_block_multiplier_calibration.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


R018 = _load(R018_PATH, "r018_for_r019p")
R019 = _load(R019_PATH, "r019_for_r019p")
CLAIMS, CONTRASTS = R018.CLAIMS, R018.CONTRASTS
BLOCKS, ALTERNATIVES = R018.BLOCKS, R018.ALTERNATIVES
SIMULATIONS, BOOTSTRAP_REPS, MASTER_SEED = 5000, 1999, 20261125
SCENARIO_INDEX = {"alternatives": 1, "independent_1pct": 2, "shock_5pct": 3}


def truth_by_claim(scenario: str) -> np.ndarray:
    """Return registered paired truth, positive for alternatives, zero for nulls."""
    truth = np.zeros(CLAIMS, dtype=float)
    if scenario == "alternatives":
        for claim in range(CLAIMS):
            pc, pb = ALTERNATIVES[claim % len(ALTERNATIVES)]
            truth[claim] = pc - pb
    elif scenario not in {"independent_1pct", "shock_5pct"}:
        raise ValueError("unknown R19-P scenario")
    return truth


def classify_panel(*, scenario: str, profile: str, eligible: np.ndarray,
                   m2: np.ndarray, lower_by_block: np.ndarray,
                   unresolved: np.ndarray, all_loss_m2: np.ndarray) -> dict:
    """Apply frozen partial-null, promotion, power, and missingness scoring."""
    eligible = np.asarray(eligible, dtype=bool)
    m2 = np.asarray(m2, dtype=float)
    unresolved = np.asarray(unresolved, dtype=int)
    all_loss_m2 = np.asarray(all_loss_m2, dtype=float)
    lower = np.asarray(lower_by_block, dtype=float)
    if (eligible.shape != (CLAIMS,) or m2.shape != (CLAIMS,) or
            unresolved.shape != (CLAIMS,) or all_loss_m2.shape != (CLAIMS,)):
        raise ValueError("claim arrays must contain 24 elements")
    if lower.shape != (len(BLOCKS), CONTRASTS):
        raise ValueError("lower_by_block must have shape (5, 48)")
    pair_claims = R019.paired_claim_rejections(lower, eligible)
    promoted = R019.multiscale_claim_promotions(m2, eligible, lower)
    unresolved_promotions = bool(np.any(promoted & (unresolved > 0)))
    if unresolved_promotions:
        raise AssertionError("a claim with unresolved emitted outcomes was promoted")
    if scenario == "alternatives":
        null_claims = np.array([i % len(ALTERNATIVES) == 2 for i in range(CLAIMS)])
        partial_pair = bool(np.any(pair_claims & null_claims))
        partial_full = bool(np.any(promoted & null_claims))
        power = []
        for alt_i, (pc, pb) in enumerate(ALTERNATIVES):
            group = np.array([i % len(ALTERNATIVES) == alt_i for i in range(CLAIMS)])
            denom = int(np.sum(eligible & group))
            power.append({
                "p_candidate": pc, "p_baseline": pb,
                "eligible_claims": denom,
                "m2_gate_hits": int(np.sum(eligible & group & (m2 >= 0.80))),
                "paired_multiscale_hits": int(np.sum(pair_claims & group)),
                "full_rule_hits": int(np.sum(promoted & group)),
            })
    else:
        partial_pair = partial_full = False
        power = []
    true_claim = truth_by_claim(scenario)
    true_contrast = np.repeat(true_claim, 2)
    active = np.repeat(eligible, 2)
    covered = bool(active.any() and np.all(
        lower[:, active] <= true_contrast[active][None, :]))
    return {
        "all_claims_eligible": bool(eligible.all()),
        "eligible_claims": int(eligible.sum()),
        "unresolved_events": int(unresolved.sum()),
        "unresolved_claims": int(np.sum(unresolved > 0)),
        "m2_resolved_by_claim": m2.tolist(),
        "m2_all_unresolved_as_loss_by_claim": all_loss_m2.tolist(),
        "multiscale_family_covered": covered,
        "paired_rejections_by_claim": pair_claims.tolist(),
        "promotions_by_claim": promoted.tolist(),
        "partial_null_paired_family_error": partial_pair,
        "partial_null_full_rule_error": partial_full,
        "power_by_alternative": power,
        "promotion_with_unresolved_claim": unresolved_promotions,
    }


def _digest(row: dict) -> str:
    clean = {k: v for k, v in row.items() if k != "record_sha256"}
    raw = json.dumps(clean, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                               allow_nan=False) + "\n")
    os.replace(temp, path)


def run_profile(output: Path, profile: str, scenario: str, *, resume=False):
    if profile not in {"A", "B", "C"} or scenario not in SCENARIO_INDEX:
        raise ValueError("invalid profile/scenario")
    missingness = "none" if scenario == "alternatives" else scenario
    if profile == "A" and scenario == "shock_5pct":
        raise ValueError("shock_5pct is inapplicable to profile A")
    runner_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    dep_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (R018_PATH, R019_PATH)}
    config = {
        "run_id": f"r019p-{profile}-{scenario}", "profile": profile,
        "scenario": scenario, "missingness": missingness,
        "simulations": SIMULATIONS, "bootstrap_reps": BOOTSTRAP_REPS,
        "master_seed": MASTER_SEED, "block_lengths": list(BLOCKS),
        "claims": CLAIMS, "contrasts": CONTRASTS, "days": R018.DAYS,
        "runner_sha256": runner_hash, "dependencies_sha256": dep_hashes,
        "numpy": np.__version__, "python": platform.python_version(),
        "market_data_read": False,
    }
    config_hash = hashlib.sha256(json.dumps(
        config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = output / "manifest.json"
    if output.exists():
        if not resume or not manifest.is_file():
            raise FileExistsError(f"output exists; pass --resume: {output}")
        if json.loads(manifest.read_text()) != config:
            raise ValueError("resume manifest does not match frozen configuration")
    else:
        output.mkdir(parents=True)
        _atomic_json(manifest, config)

    profile_i = ord(profile) - ord("A")
    scen_i = SCENARIO_INDEX[scenario]
    rows = []
    start = time.monotonic()
    for panel in range(SIMULATIONS):
        path = output / f"panel_{panel:05d}.json"
        panel_seed = int(np.random.SeedSequence(
            [MASTER_SEED, 20, scen_i, profile_i, panel, 0]).generate_state(1)[0])
        if path.is_file():
            row = json.loads(path.read_text())
            if (row.get("panel") != panel or row.get("config_sha256") != config_hash
                    or row.get("panel_seed") != panel_seed
                    or row.get("record_sha256") != _digest(row)):
                raise ValueError(f"invalid resume checkpoint {path}")
            rows.append(row)
            continue

        n, x, aux = R018.synthetic_panel(
            panel_seed, profile=profile,
            alternative=(scenario == "alternatives"), missingness=missingness)
        eligible_claims = np.asarray(aux["eligible_claims"], dtype=bool)
        eligible_contrasts = np.repeat(eligible_claims, 2)
        lower = np.full((len(BLOCKS), CONTRASTS), np.nan)
        criticals, errors = {}, {}
        for ell in BLOCKS:
            seed = int(np.random.SeedSequence(
                [MASTER_SEED, 20, scen_i, profile_i, panel, ell]).generate_state(1)[0])
            try:
                result = R019.block_multiplier_lower_bounds(
                    n, x, reps=BOOTSTRAP_REPS, block_length=ell, seed=seed,
                    eligible_contrasts=eligible_contrasts)
                lower[BLOCKS.index(ell)] = result["lower"]
                criticals[str(ell)] = result["critical"]
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                errors[str(ell)] = type(exc).__name__ + ": " + str(exc)
                criticals[str(ell)] = None

        scoring = classify_panel(
            scenario=scenario, profile=profile, eligible=eligible_claims,
            m2=np.asarray(aux["m2_resolved"], dtype=float),
            lower_by_block=lower,
            unresolved=np.asarray(aux["unresolved_by_claim"], dtype=int),
            all_loss_m2=np.asarray(aux["all_loss_m2"], dtype=float))
        row = {
            "panel": panel, "profile": profile, "scenario": scenario,
            "panel_seed": panel_seed, "config_sha256": config_hash,
            "all_claims_eligible": scoring["all_claims_eligible"],
            "eligible_claims": scoring["eligible_claims"],
            "unresolved_events": scoring["unresolved_events"],
            "unresolved_claims": scoring["unresolved_claims"],
            "m2_resolved_by_claim": scoring["m2_resolved_by_claim"],
            "m2_all_unresolved_as_loss_by_claim": scoring[
                "m2_all_unresolved_as_loss_by_claim"],
            "multiscale_family_covered": scoring["multiscale_family_covered"],
            "paired_rejections_by_claim": scoring["paired_rejections_by_claim"],
            "promotions_by_claim": scoring["promotions_by_claim"],
            "partial_null_paired_family_error": scoring["partial_null_paired_family_error"],
            "partial_null_full_rule_error": scoring["partial_null_full_rule_error"],
            "power_by_alternative": scoring["power_by_alternative"],
            "promotion_with_unresolved_claim": scoring["promotion_with_unresolved_claim"],
            "critical_by_block": criticals, "errors": errors,
        }
        row["record_sha256"] = _digest(row)
        _atomic_json(path, row)
        rows.append(row)
        if (panel + 1) % 25 == 0:
            print(json.dumps({"run_id": config["run_id"],
                              "progress_panels": panel + 1,
                              "elapsed_seconds": round(time.monotonic()-start, 1)},
                             sort_keys=True), flush=True)

    errors = sum(bool(row["errors"]) for row in rows)
    all_eligible = sum(bool(row["all_claims_eligible"]) for row in rows)
    summary = {
        **config, "elapsed_seconds": round(time.monotonic()-start, 3),
        "all_claims_eligible_panels": all_eligible,
        "all_claims_eligible_rate": all_eligible / SIMULATIONS,
        "failed_panels": errors,
        "promotion_with_unresolved_panels": sum(
            bool(row["promotion_with_unresolved_claim"]) for row in rows),
        "multiscale_family_coverage": sum(
            bool(row["multiscale_family_covered"]) for row in rows) / SIMULATIONS,
        "interpretation": "synthetic R019-P diagnostic only",
    }
    if scenario == "alternatives":
        pn = sum(bool(row["partial_null_paired_family_error"]) for row in rows)
        fn = sum(bool(row["partial_null_full_rule_error"]) for row in rows)
        summary.update({
            "partial_null_paired_false_events": pn,
            "partial_null_paired_rate": pn / SIMULATIONS,
            "partial_null_paired_wilson95": list(R018._wilson95(pn, SIMULATIONS)),
            "partial_null_full_false_events": fn,
            "partial_null_full_rate": fn / SIMULATIONS,
            "partial_null_full_wilson95": list(R018._wilson95(fn, SIMULATIONS)),
            "power_by_alternative": [
                {"p_candidate": pc, "p_baseline": pb,
                 "eligible_claims": sum(r["power_by_alternative"][i]["eligible_claims"] for r in rows),
                 "m2_gate_hits": sum(r["power_by_alternative"][i]["m2_gate_hits"] for r in rows),
                 "paired_multiscale_hits": sum(r["power_by_alternative"][i]["paired_multiscale_hits"] for r in rows),
                 "full_rule_hits": sum(r["power_by_alternative"][i]["full_rule_hits"] for r in rows)}
                for i, (pc, pb) in enumerate(ALTERNATIVES)],
        })
        summary["decision"] = "PASS" if (
            summary["partial_null_paired_wilson95"][1] <= 0.06 and
            summary["partial_null_full_wilson95"][1] <= 0.06 and
            summary["all_claims_eligible_rate"] >= 0.95 and errors == 0
        ) else "REJECT"
    else:
        eligible_counts = np.asarray([row["eligible_claims"] for row in rows])
        unresolved_counts = np.asarray([row["unresolved_events"] for row in rows])
        summary.update({
            "eligible_claims_min": int(eligible_counts.min()),
            "eligible_claims_median": float(np.median(eligible_counts)),
            "eligible_claims_max": int(eligible_counts.max()),
            "panels_with_any_unresolved": int(np.sum(unresolved_counts > 0)),
            "panels_with_any_promotion": int(sum(
                any(row["promotions_by_claim"]) for row in rows)),
            "decision": "DIAGNOSTIC_ONLY",
        })
    _atomic_json(output / "results.json", summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", choices=("A", "B", "C"), required=True)
    p.add_argument("--scenario", choices=tuple(SCENARIO_INDEX), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    result = run_profile(args.output, args.profile, args.scenario, resume=args.resume)
    print(json.dumps({k: result[k] for k in ("run_id", "decision",
                     "all_claims_eligible_rate", "failed_panels")}, sort_keys=True))


if __name__ == "__main__":
    main()
