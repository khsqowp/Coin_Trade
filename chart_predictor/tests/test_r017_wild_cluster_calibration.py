import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).parents[2] / "scripts/research/crypto_r017_wild_cluster_calibration.py"
SPEC = importlib.util.spec_from_file_location("crypto_r017_wild_cluster_calibration", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_mammen_weights_have_registered_two_point_values_and_moments():
    weights = MODULE._mammen_weights(np.random.default_rng(7), 100_000, 1).ravel()
    np.testing.assert_allclose(np.unique(weights),
                               np.array([(1 - np.sqrt(5)) / 2,
                                         (1 + np.sqrt(5)) / 2]))
    assert weights.mean() == pytest.approx(0.0, abs=0.01)
    assert np.mean(weights**2) == pytest.approx(1.0, abs=0.02)
    assert np.mean(weights**3) == pytest.approx(1.0, abs=0.04)


def test_block_scores_aggregate_consecutive_null_score_rows():
    counts = np.array([[1, 2], [2, 0], [0, 1], [1, 1], [2, 3]], dtype=float)
    wins = np.array([[1, 2], [1, 0], [0, 1], [1, 0], [2, 2]], dtype=float)
    scores = MODULE._block_scores(counts, wins, block_length=2)
    np.testing.assert_allclose(scores, np.array([[-0.4, 0.4], [0.2, -0.6], [0.4, -0.4]]))


def test_zero_eligible_claims_do_not_promote_a_family():
    scores = np.ones((20, 4))
    result = MODULE.wild_cluster_test(scores, np.zeros(4, dtype=bool),
                                      bootstrap_reps=199, seed=5)
    assert result["eligible_claim_count"] == 0
    assert result["reject_any"] is False


def test_wild_cluster_test_rejects_nonfinite_scores():
    scores = np.ones((20, 2))
    scores[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        MODULE.wild_cluster_test(scores, np.ones(2, dtype=bool),
                                 bootstrap_reps=199, seed=5)
