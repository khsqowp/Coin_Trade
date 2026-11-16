import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).parents[2] / "scripts/research/crypto_r013_inference_calibration.py"
SPEC = importlib.util.spec_from_file_location("crypto_r013_inference_calibration", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_simulated_null_has_expected_marginal_precision_and_reproducible():
    first = MODULE.simulate_scores(days=1200, frames=4, mean_count=8, rho=0.5,
                                   common_fraction=0.75, seed=91)
    second = MODULE.simulate_scores(days=1200, frames=4, mean_count=8, rho=0.5,
                                    common_fraction=0.75, seed=91)
    np.testing.assert_array_equal(first, second)
    # E[W - .8N] is zero; counts have mean 8 by construction.
    assert abs(first.mean()) / 8 < 0.02


def test_test_statistics_and_holm_are_bounded_and_deterministic():
    rng = np.random.default_rng(12)
    scores = rng.normal(0, 1, size=(240, 12))
    p1 = MODULE.hac_pvalues(scores, lag=14)
    p2 = MODULE.block_bootstrap_pvalues(scores, block_length=14, reps=99, seed=88)
    assert p1.shape == p2.shape == (12,)
    assert np.isfinite(p1).all() and np.isfinite(p2).all()
    assert ((0 <= p1) & (p1 <= 1)).all()
    assert ((0 <= p2) & (p2 <= 1)).all()
    np.testing.assert_array_equal(MODULE.holm_reject(p1, alpha=0.05),
                                  MODULE.holm_reject(p1, alpha=0.05))


@pytest.mark.parametrize("kwargs", [
    {"days": 0, "frames": 2, "mean_count": 8, "rho": 0.5, "common_fraction": 0.0, "seed": 1},
    {"days": 10, "frames": 2, "mean_count": 8, "rho": 1.0, "common_fraction": 0.0, "seed": 1},
    {"days": 10, "frames": 2, "mean_count": 8, "rho": 0.5, "common_fraction": 1.1, "seed": 1},
])
def test_simulator_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        MODULE.simulate_scores(**kwargs)
