import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (Path(__file__).resolve().parents[2] / "scripts" / "research" /
          "crypto_r019_block_multiplier_calibration.py")
SPEC = importlib.util.spec_from_file_location("r019_test_module", SCRIPT)
R19 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R19)


def _slow_reference(n, x, *, reps, ell, seed):
    delta = x.sum(axis=0) / n.sum(axis=0)
    influence = x - n * delta
    blocks = np.stack([influence[i:i + ell].sum(axis=0)
                       for i in range(len(n) - ell + 1)])
    ss = (blocks * blocks).sum(axis=0)
    rng = np.random.default_rng(seed)
    mult = np.array([[rng.standard_normal() for _ in range(len(blocks))]
                     for _ in range(reps)])
    t = (mult @ blocks / np.sqrt(ss)).max(axis=1)
    critical = np.quantile(t, 0.95, method="higher")
    omega = ss / (len(blocks) * ell)
    se = np.sqrt(len(n) * omega) / n.sum(axis=0)
    return delta, se, delta - critical * se, critical


def test_block_multiplier_matches_independent_slow_reference_and_replays():
    rng = np.random.default_rng(71)
    n = rng.integers(1, 5, size=(31, R19.CONTRASTS)).astype(float)
    x = np.array([[rng.binomial(int(count), 0.57) for count in row]
                  for row in n], dtype=float)
    expected = _slow_reference(n, x, reps=79, ell=5, seed=9021)
    got = R19.block_multiplier_lower_bounds(
        n, x, reps=79, block_length=5, seed=9021)
    got_again = R19.block_multiplier_lower_bounds(
        n, x, reps=79, block_length=5, seed=9021)
    for key, value in zip(("delta", "se", "lower", "critical"), expected):
        np.testing.assert_allclose(got[key], value, rtol=1e-12, atol=1e-12)
        np.testing.assert_array_equal(got[key], got_again[key])


def test_multiscale_promotion_requires_every_scale_and_both_baselines():
    m2 = np.full(R19.CLAIMS, 0.81)
    eligible = np.ones(R19.CLAIMS, dtype=bool)
    lower = np.ones((len(R19.BLOCKS), R19.CONTRASTS))
    assert R19.multiscale_claim_promotions(m2, eligible, lower).all()

    lower[2, 7] = 0.0
    promoted = R19.multiscale_claim_promotions(m2, eligible, lower)
    assert not promoted[3]
    assert promoted.sum() == R19.CLAIMS - 1
    lower[2, 7] = 1.0
    m2[4] = 0.79
    assert not R19.multiscale_claim_promotions(m2, eligible, lower)[4]
    m2[4] = 0.81
    eligible[4] = False
    assert not R19.multiscale_claim_promotions(m2, eligible, lower)[4]


def test_block_multiplier_rejects_bad_or_degenerate_inputs():
    n = np.ones((12, R19.CONTRASTS))
    x = np.tile(np.arange(12)[:, None] % 2, (1, R19.CONTRASTS)).astype(float)
    with pytest.raises(ValueError, match="matching day"):
        R19.block_multiplier_lower_bounds(n, x[:, :-1], reps=10,
                                          block_length=2, seed=1)
    with pytest.raises(ValueError, match="invalid overlapping-block"):
        R19.block_multiplier_lower_bounds(n, n, reps=10,
                                          block_length=2, seed=1)
    with pytest.raises(ValueError, match="each eligible contrast"):
        R19.block_multiplier_lower_bounds(
            np.zeros_like(n), np.zeros_like(n), reps=10,
            block_length=2, seed=1)
