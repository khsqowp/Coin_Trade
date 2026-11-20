"""Pre-registered synchronized date-block bootstrap primitives for CVD research."""
from __future__ import annotations

import hashlib
import json

import numpy as np


SEED = 20261120
BLOCK_DAYS = 7
REPLICATES = 10_000
CONTRAST_ALPHA = 0.05 / 10


def draw_date_indices(n_dates: int, rng: np.random.Generator,
                      block_days: int = BLOCK_DAYS) -> np.ndarray:
    """Draw K date indices from non-circular moving blocks; no wraparound."""
    if n_dates <= 0 or block_days <= 0 or block_days > n_dates:
        raise ValueError("invalid date/block dimensions")
    chunks = []
    remaining = n_dates
    while remaining:
        start = int(rng.integers(0, n_dates - block_days + 1))
        take = min(block_days, remaining)
        chunks.append(np.arange(start, start + take, dtype=np.int64))
        remaining -= take
    return np.concatenate(chunks)


def _count_sum(daily_labels: list[list[int]], indices: np.ndarray) -> tuple[int, int]:
    count = total = 0
    for day_index in indices:
        labels = daily_labels[int(day_index)]
        count += len(labels)
        total += sum(labels)
    return count, total


def _paired_difference(candidate: list[list[int]], baseline: list[list[int]],
                       indices: np.ndarray) -> float | None:
    candidate_count = baseline_count = candidate_sum = baseline_sum = 0
    for day_index in indices:
        i = int(day_index)
        left, right = candidate[i], baseline[i]
        if len(left) != len(right):
            raise ValueError("paired baseline day has mismatched event counts")
        candidate_count += len(left)
        baseline_count += len(right)
        candidate_sum += sum(left)
        baseline_sum += sum(right)
    if candidate_count == 0 or baseline_count == 0:
        return None
    return candidate_sum / candidate_count - baseline_sum / baseline_count


def _independent_difference(left: list[list[int]], right: list[list[int]],
                            indices: np.ndarray) -> float | None:
    left_count, left_sum = _count_sum(left, indices)
    right_count, right_sum = _count_sum(right, indices)
    if left_count == 0 or right_count == 0:
        return None
    return left_sum / left_count - right_sum / right_count


def _denominators_sha256(values: list) -> str:
    payload = json.dumps(values, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def bootstrap_m2(daily_labels: list[list[int]], *, seed: int = SEED,
                 replicates: int = REPLICATES, block_days: int = BLOCK_DAYS) -> dict:
    if not daily_labels:
        raise ValueError("daily grid must not be empty")
    if any(label not in (0, 1) for day in daily_labels for label in day):
        raise ValueError("labels must be binary 0/1")
    rng = np.random.Generator(np.random.PCG64(seed))
    estimates = []
    undefined = 0
    indices_digest = hashlib.sha256()
    denominator_vector = []
    for _ in range(replicates):
        indices = draw_date_indices(len(daily_labels), rng, block_days)
        indices_digest.update(indices.astype("<i8", copy=False).tobytes())
        count, total = _count_sum(daily_labels, indices)
        denominator_vector.append(count)
        estimate = total / count if count else None
        if estimate is None:
            undefined += 1
        else:
            estimates.append(estimate)
    if undefined / replicates > 0.01:
        return {"status": "NOT_EVALUABLE", "undefined_replicates": undefined,
                "defined_replicates": len(estimates),
                "indices_sha256": indices_digest.hexdigest(),
                "denominator_vector": denominator_vector,
                "denominators_sha256": _denominators_sha256(denominator_vector)}
    values = np.asarray(estimates, dtype=float)
    return {"status": "PASS", "undefined_replicates": undefined,
            "defined_replicates": len(estimates),
            "indices_sha256": indices_digest.hexdigest(),
            "denominator_vector": denominator_vector,
            "denominators_sha256": _denominators_sha256(denominator_vector),
            "lower95": float(np.quantile(values, 0.05, method="linear")),
            "estimate_median": float(np.quantile(values, 0.5, method="linear"))}


def bootstrap_contrast(left: list[list[int]], right: list[list[int]], *,
                       paired: bool, seed: int = SEED, replicates: int = REPLICATES,
                       block_days: int = BLOCK_DAYS) -> dict:
    if not left or len(left) != len(right):
        raise ValueError("arms must share the same nonempty date grid")
    if any(label not in (0, 1) for arm in (left, right) for day in arm for label in day):
        raise ValueError("labels must be binary 0/1")
    if paired and any(len(a) != len(b) for a, b in zip(left, right)):
        raise ValueError("paired baseline day has mismatched event counts")
    rng = np.random.Generator(np.random.PCG64(seed))
    estimates = []
    undefined = 0
    statistic = _paired_difference if paired else _independent_difference
    indices_digest = hashlib.sha256()
    denominator_vector = []
    for _ in range(replicates):
        indices = draw_date_indices(len(left), rng, block_days)
        indices_digest.update(indices.astype("<i8", copy=False).tobytes())
        left_n, _ = _count_sum(left, indices)
        if paired:
            denominator = left_n
            denominator_vector.append(denominator)
            undefined_here = denominator == 0
        else:
            right_n, _ = _count_sum(right, indices)
            denominator_vector.append({"left": left_n, "right": right_n})
            undefined_here = left_n == 0 or right_n == 0
        estimate = statistic(left, right, indices)
        if undefined_here or estimate is None:
            undefined += 1
        else:
            estimates.append(estimate)
    if undefined / replicates > 0.01:
        return {"status": "NOT_EVALUABLE", "undefined_replicates": undefined,
                "defined_replicates": len(estimates),
                "indices_sha256": indices_digest.hexdigest(),
                "denominator_vector": denominator_vector,
                "denominators_sha256": _denominators_sha256(denominator_vector)}
    observed = statistic(left, right, np.arange(len(left), dtype=np.int64))
    if observed is None:
        return {"status": "NOT_EVALUABLE", "undefined_replicates": undefined,
                "defined_replicates": len(estimates), "reason": "observed_arm_empty",
                "indices_sha256": indices_digest.hexdigest(),
                "denominator_vector": denominator_vector,
                "denominators_sha256": _denominators_sha256(denominator_vector)}
    values = np.asarray(estimates, dtype=float)
    return {"status": "PASS", "observed_difference": float(observed),
            "undefined_replicates": undefined, "defined_replicates": len(estimates),
            "indices_sha256": indices_digest.hexdigest(),
            "denominator_vector": denominator_vector,
            "denominators_sha256": _denominators_sha256(denominator_vector),
            "lower95": float(np.quantile(values, 0.05, method="linear")),
            "simultaneous_lower": float(np.quantile(values, CONTRAST_ALPHA, method="linear"))}


def event_weighted_m2(labels: list[list[int]]) -> float | None:
    count = sum(len(day) for day in labels)
    return sum(sum(day) for day in labels) / count if count else None
