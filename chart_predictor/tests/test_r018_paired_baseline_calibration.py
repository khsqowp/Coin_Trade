import importlib.util
from pathlib import Path

import numpy as np


MODULE_PATH = (Path(__file__).parents[2] /
               "scripts/research/crypto_r018_paired_baseline_calibration.py")
SPEC = importlib.util.spec_from_file_location("r018_calibration", MODULE_PATH)
R018 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R018)


def test_hourly_synthetic_fixture_is_deterministic_and_separates_denominators():
    n1, x1, aux1 = R018.synthetic_panel(123)
    n2, x2, aux2 = R018.synthetic_panel(123)
    np.testing.assert_array_equal(n1, n2)
    np.testing.assert_array_equal(x1, x2)
    np.testing.assert_array_equal(aux1["nonoverlap_n"], aux2["nonoverlap_n"])
    assert n1.shape == (365, 48)
    assert x1.shape == (365, 48)
    np.testing.assert_array_equal(n1[:, 0::2], n1[:, 1::2])
    assert aux1["nonoverlap_n"].shape == (365, 24)
    assert aux1["eligible_claims"].shape == (24,)
    assert aux1["eligible_claims"].all()


def test_stationary_indices_are_circular_and_replayable():
    a = R018.stationary_indices(np.random.default_rng(55), 32, 365, 5)
    b = R018.stationary_indices(np.random.default_rng(55), 32, 365, 5)
    np.testing.assert_array_equal(a, b)
    assert a.shape == (32, 365)
    assert ((a >= 0) & (a < 365)).all()


def test_paired_bound_uses_all_48_contrasts_and_is_deterministic():
    rng = np.random.default_rng(6)
    n = np.full((365, 48), 20.0)
    x = rng.normal(0, 2, size=(365, 48))
    first = R018.paired_lower_bounds(n, x, reps=199, mean_block=5, seed=9)
    second = R018.paired_lower_bounds(n, x, reps=199, mean_block=5, seed=9)
    assert first["lower"].shape == (48,)
    assert first["delta"].shape == (48,)
    assert first["critical"] == second["critical"]
    np.testing.assert_array_equal(first["lower"], second["lower"])
