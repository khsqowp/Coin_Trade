#!/usr/bin/env python3
"""Corrected synthetic calibration separating raw size from Holm FWER."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import time
from pathlib import Path

import numpy as np

ALPHA = 0.05
FRAME_COUNT = 12
CONFIDENCE_CELLS = 24 * (FRAME_COUNT + 1)
TIMEFRAME_NAMES = ["1m", "3m", "5m", "10m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"]


def _load_script(name: str, filename: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_rejections(pvalues: np.ndarray, alpha: float = ALPHA) -> tuple[np.ndarray, bool]:
    p = np.asarray(pvalues, dtype=float)
    if p.ndim != 1 or p.size != FRAME_COUNT or not np.isfinite(p).all():
        raise ValueError("pvalues must be a finite vector for all 12 timeframes")
    if ((p < 0) | (p > 1)).any() or not 0 < alpha < 1:
        raise ValueError("pvalues must be in [0,1] and alpha in (0,1)")
    dgp = _load_script("r013_helpers", "crypto_r013_inference_calibration.py")
    raw_rejections = p <= alpha
    holm_family_reject = bool(np.any(dgp.holm_reject(p, alpha=alpha)))
    return raw_rejections, holm_family_reject


def type1_summary(raw_rejections: np.ndarray, z: float) -> list[dict]:
    values = np.asarray(raw_rejections)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] != FRAME_COUNT:
        raise ValueError("raw_rejections must be replications by 12 timeframes")
    if not np.isin(values, (0, 1, False, True)).all():
        raise ValueError("raw_rejections must be Boolean or binary")
    r014 = _load_script("r014_helpers", "crypto_r014_self_normalized_calibration.py")
    upper = r014.wilson_upper_by_column(values, z=z)
    n = values.shape[0]
    return [{"frame_index": j, "timeframe": TIMEFRAME_NAMES[j],
             "rejections": int(values[:, j].sum()),
             "rate": float(values[:, j].mean()),
             "upper_bound": float(upper[j])}
            for j in range(FRAME_COUNT)]


def run_calibration(*, simulations: int = 1000, reference_paths: int = 250_000,
                    reference_steps: int = 2048, seed: int = 20261119,
                    reference_seed: int = 20261120) -> dict:
    if simulations < 1:
        raise ValueError("simulations must be positive")
    started = time.monotonic()
    r013 = _load_script("r013_dgp", "crypto_r013_inference_calibration.py")
    r014 = _load_script("r014_sn_method", "crypto_r014_self_normalized_calibration.py")
    reference = r014.brownian_pivot_reference(paths=reference_paths,
                                              steps=reference_steps,
                                              seed=reference_seed)
    z = __import__("statistics").NormalDist().inv_cdf(1.0 - 0.05 / CONFIDENCE_CELLS)
    scenarios = []
    for scenario_index, scenario in enumerate(r014.SCENARIOS):
        stream = np.random.default_rng(seed + scenario_index * 1_000_003)
        raw_rejections = np.zeros((simulations, FRAME_COUNT), dtype=bool)
        family_rejections = np.zeros(simulations, dtype=bool)
        errors = 0
        for replication in range(simulations):
            sim_seed = int(stream.integers(0, np.iinfo(np.int32).max))
            scores = r013.simulate_scores(frames=FRAME_COUNT, seed=sim_seed, **scenario)
            try:
                p = r014.self_normalized_pvalues(scores, reference)
                raw_rejections[replication], family_rejections[replication] = evaluate_rejections(p)
            except (ValueError, FloatingPointError):
                errors += 1
        type1 = type1_summary(raw_rejections, z=z)
        fwer_count = int(family_rejections.sum())
        fwer = fwer_count / simulations
        fwer_upper = r014.wilson_upper(fwer_count, simulations, z=z)
        qualified = (errors == 0
                     and max(item["upper_bound"] for item in type1) <= 0.075
                     and fwer_upper <= 0.085)
        scenarios.append({**scenario, "simulations": simulations,
                          "failed_replications": errors,
                          "per_timeframe_type1": type1,
                          "mean_per_test_type1": float(raw_rejections.mean()),
                          "holm_fwer": fwer,
                          "holm_fwer_upper_bound": fwer_upper,
                          "screen_qualified": bool(qualified)})
    return {"schema_version": 1,
            "method": "self_normalized_recursive_mean_brownian_pivot_corrected_size_aggregation",
            "alpha": ALPHA, "timeframes": TIMEFRAME_NAMES,
            "seed": seed, "reference_seed": reference_seed,
            "reference_paths": reference_paths, "reference_steps": reference_steps,
            "reference_pvalue_resolution": 0.5 / (reference_paths + 1),
            "scenario_count": len(scenarios), "scenarios": scenarios,
            "one_sided_simultaneous_confidence": 0.95,
            "bonferroni_interval_count": CONFIDENCE_CELLS,
            "per_timeframe_type1_upper_threshold": 0.075,
            "holm_fwer_upper_threshold": 0.085,
            "failed_replications": sum(s["failed_replications"] for s in scenarios),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "python": platform.python_version(), "numpy": np.__version__,
            "note": "synthetic inference calibration only; not a strategy or market result"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--reference-paths", type=int, default=250_000)
    parser.add_argument("--reference-steps", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=20261119)
    parser.add_argument("--reference-seed", type=int, default=20261120)
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
