import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).parents[2] / "scripts/research/crypto_r014_self_normalized_calibration.py"
SPEC = importlib.util.spec_from_file_location("crypto_r014_self_normalized_calibration", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_pivot_reference_is_deterministic_and_finite():
    first = MODULE.brownian_pivot_reference(paths=500, steps=64, seed=15)
    second = MODULE.brownian_pivot_reference(paths=500, steps=64, seed=15)
    np.testing.assert_array_equal(first, second)
    assert first.shape == (500,)
    assert np.isfinite(first).all()
    assert (first > 0).all()


def test_self_normalized_pvalues_preserve_direction_and_shape():
    ref = MODULE.brownian_pivot_reference(paths=3000, steps=128, seed=31)
    scores = np.column_stack((np.linspace(-2, 0, 200),
                              1.0 + 0.1 * np.sin(np.arange(200) / 7)))
    p = MODULE.self_normalized_pvalues(scores, ref)
    assert p.shape == (2,)
    assert p[0] > 0.5
    assert p[1] < 0.5
    assert np.isfinite(p).all() and ((0 <= p) & (p <= 1)).all()


def test_simultaneous_rate_bounds_are_conservative_and_validated():
    values = np.array([[False, True], [True, True], [False, True], [True, True]])
    bounds = MODULE.wilson_upper_by_column(values, z=2.0)
    assert bounds.shape == (2,)
    assert bounds[0] < bounds[1]
    assert (bounds >= values.mean(axis=0)).all()
    with pytest.raises(ValueError):
        MODULE.wilson_upper_by_column(np.array([[0, 2], [1, 0]]), z=2.0)
