import numpy as np
import pytest

from scripts.research.cvd_block_bootstrap import (
    bootstrap_contrast,
    bootstrap_m2,
    draw_date_indices,
    event_weighted_m2,
    CONTRAST_ALPHA,
)


def test_moving_blocks_are_deterministic_nonwrapping_and_exact_length():
    class FixedStarts:
        def __init__(self):
            self.starts = iter([7, 0, 4, 2])

        def integers(self, low, high):
            assert (low, high) == (0, 8)
            return next(self.starts)

    first = draw_date_indices(10, FixedStarts(), block_days=3)
    assert first.tolist() == [7, 8, 9, 0, 1, 2, 4, 5, 6, 2]
    assert len(first) == 10


def test_replicate_uses_event_weighted_not_daily_mean_m2():
    labels = [[1, 1, 1, 1], [0]]
    assert event_weighted_m2(labels) == 0.8
    full = [[1, 1, 1, 1]] + [[0] for _ in range(13)]
    result = bootstrap_m2(full, seed=2, replicates=10, block_days=1)
    assert result["status"] == "PASS"
    assert result["defined_replicates"] == 10
    assert len(result["denominator_vector"]) == 10
    assert len(result["denominators_sha256"]) == 64


def test_paired_baseline_keeps_abstentions_as_misses_and_shared_dates():
    candidate = [[1, 0], [1], [0], [1]] + [[] for _ in range(10)]
    baseline = [[1, 0], [0], [0], [0]] + [[] for _ in range(10)]
    result = bootstrap_contrast(candidate, baseline, paired=True, seed=7,
                                replicates=100, block_days=1)
    assert result["status"] == "PASS"
    assert result["observed_difference"] == pytest.approx(0.4)
    assert result["undefined_replicates"] <= 1


def test_paired_bootstrap_reuses_exact_date_indices_and_fixed_quantiles():
    candidate = [[i % 2] for i in range(20)]
    baseline = [[0] for _ in range(20)]
    seed, replicates, block_days = 319, 100, 3
    expected = []
    rng = np.random.Generator(np.random.PCG64(seed))
    for _ in range(replicates):
        indices = draw_date_indices(20, rng, block_days)
        sampled_candidate = [candidate[int(i)][0] for i in indices]
        sampled_baseline = [baseline[int(i)][0] for i in indices]
        expected.append(sum(sampled_candidate) / 20 - sum(sampled_baseline) / 20)
    result = bootstrap_contrast(candidate, baseline, paired=True, seed=seed,
                                replicates=replicates, block_days=block_days)
    assert result["defined_replicates"] == replicates
    assert result["undefined_replicates"] == 0
    assert len(result["indices_sha256"]) == 64
    assert result["denominator_vector"] == [20] * replicates
    assert len(result["denominators_sha256"]) == 64
    assert result["lower95"] == pytest.approx(np.quantile(expected, 0.05, method="linear"))
    assert result["simultaneous_lower"] == pytest.approx(
        np.quantile(expected, CONTRAST_ALPHA, method="linear"))


def test_unequal_paired_daily_counts_fail_closed():
    with pytest.raises(ValueError, match="mismatched event counts"):
        bootstrap_contrast([[1, 0], []], [[1], []], paired=True,
                           replicates=1, block_days=1)


def test_more_than_one_percent_undefined_replicates_is_not_evaluable():
    labels = [[1]] + [[] for _ in range(13)]
    result = bootstrap_m2(labels, seed=1, replicates=100, block_days=1)
    assert result["status"] == "NOT_EVALUABLE"
    assert result["undefined_replicates"] > 1


def test_independent_arms_preserve_zero_event_dates_and_report_fixed_family_bound():
    left = [[1], [0], [1], [0]] + [[1] for _ in range(10)]
    right = [[0], [1], [0], [1]] + [[0] for _ in range(10)]
    result = bootstrap_contrast(left, right, paired=False, seed=22,
                                replicates=100, block_days=2)
    assert result["status"] == "PASS"
    assert result["observed_difference"] == pytest.approx(5 / 7)
    assert "simultaneous_lower" in result
