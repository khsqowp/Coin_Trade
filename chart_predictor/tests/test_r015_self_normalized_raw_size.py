import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).parents[2] / "scripts/research/crypto_r015_self_normalized_raw_size.py"
SPEC = importlib.util.spec_from_file_location("crypto_r015_self_normalized_raw_size", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_raw_and_holm_rejections_are_kept_separate():
    p = np.array([0.001, 0.03, 0.10] + [0.9] * 9)
    raw, family = MODULE.evaluate_rejections(p, alpha=0.05)
    np.testing.assert_array_equal(raw, np.array([True, True] + [False] * 10))
    assert family is True


def test_invalid_p_values_fail_closed():
    with pytest.raises(ValueError):
        MODULE.evaluate_rejections(np.array([0.001, np.nan] + [0.9] * 10), alpha=0.05)


def test_result_bounds_are_based_on_unadjusted_rejections():
    raw = np.column_stack((np.array([True, True, False, True]),
                           np.array([False, True, False, False]),
                           np.zeros((4, 10), dtype=bool)))
    bounds = MODULE.type1_summary(raw, z=2.0)
    assert bounds[0]["rate"] == pytest.approx(0.75)
    assert bounds[1]["rate"] == pytest.approx(0.25)
    assert bounds[0]["upper_bound"] > bounds[0]["rate"]
