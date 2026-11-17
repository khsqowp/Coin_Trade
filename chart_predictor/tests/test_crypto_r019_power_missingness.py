import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = (Path(__file__).resolve().parents[2] / "scripts" / "research" /
          "crypto_r019_power_missingness.py")
SPEC = importlib.util.spec_from_file_location("r019p_test_module", SCRIPT)
R19P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R19P)


def test_alternative_truth_and_partial_null_family_are_fixed():
    truth = R19P.truth_by_claim("alternatives")
    assert truth.shape == (R19P.CLAIMS,)
    assert all(truth[i] == 0 for i in range(R19P.CLAIMS) if i % 5 == 2)
    assert all(truth[i] > 0 for i in range(R19P.CLAIMS) if i % 5 != 2)
    assert np.all(R19P.truth_by_claim("independent_1pct") == 0)


def test_partial_null_counts_both_baselines_and_all_scales():
    eligible = np.ones(R19P.CLAIMS, dtype=bool)
    m2 = np.full(R19P.CLAIMS, 0.81)
    unresolved = np.zeros(R19P.CLAIMS, dtype=int)
    lower = np.ones((len(R19P.BLOCKS), R19P.CONTRASTS))
    scored = R19P.classify_panel(
        scenario="alternatives", profile="A", eligible=eligible, m2=m2,
        lower_by_block=lower, unresolved=unresolved, all_loss_m2=m2)
    assert scored["partial_null_paired_family_error"]
    assert scored["partial_null_full_rule_error"]

    # If just one baseline at one scale fails, that null claim is not rejected.
    for claim in range(R19P.CLAIMS):
        if claim % 5 == 2:
            lower[0, 2 * claim + 1] = 0.0
    scored = R19P.classify_panel(
        scenario="alternatives", profile="A", eligible=eligible, m2=m2,
        lower_by_block=lower, unresolved=unresolved, all_loss_m2=m2)
    assert not scored["partial_null_paired_family_error"]
    assert not scored["partial_null_full_rule_error"]


def test_unresolved_claims_are_ineligible_and_never_promoted():
    eligible = np.ones(R19P.CLAIMS, dtype=bool)
    eligible[2] = False
    unresolved = np.zeros(R19P.CLAIMS, dtype=int)
    unresolved[2] = 1
    scored = R19P.classify_panel(
        scenario="independent_1pct", profile="A", eligible=eligible,
        m2=np.full(R19P.CLAIMS, 0.9),
        lower_by_block=np.ones((len(R19P.BLOCKS), R19P.CONTRASTS)),
        unresolved=unresolved, all_loss_m2=np.full(R19P.CLAIMS, 0.9))
    assert not scored["promotions_by_claim"][2]
    assert not scored["promotion_with_unresolved_claim"]

    eligible[2] = True
    with pytest.raises(AssertionError, match="unresolved"):
        R19P.classify_panel(
            scenario="independent_1pct", profile="A", eligible=eligible,
            m2=np.full(R19P.CLAIMS, 0.9),
            lower_by_block=np.ones((len(R19P.BLOCKS), R19P.CONTRASTS)),
            unresolved=unresolved, all_loss_m2=np.full(R19P.CLAIMS, 0.9))
