import importlib.util
from pathlib import Path

import numpy as np
import pytest


MODULE_PATH = Path(__file__).parents[2] / "scripts/research/crypto_r016_synthetic_event_calibration.py"
SPEC = importlib.util.spec_from_file_location("crypto_r016_synthetic_event_calibration", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_generator_is_deterministic_and_has_expected_dimensions():
    labels_a, issued_a = MODULE.generate_replication(days=80, seed=123)
    labels_b, issued_b = MODULE.generate_replication(days=80, seed=123)
    assert labels_a.shape == (24, 80, 20)
    assert issued_a.shape == labels_a.shape
    np.testing.assert_array_equal(labels_a, labels_b)
    np.testing.assert_array_equal(issued_a, issued_b)


def test_independent_null_profile_has_eighty_percent_marginal():
    labels, _ = MODULE.generate_replication(
        days=250, seed=321, rho_common=0, rho_symbol=0, rho_frame=0,
        overlap_windows=False, clustered_issuance=False,
        independent_claim_outcomes=True)
    assert labels.mean() == pytest.approx(0.80, abs=0.01)


def test_nonoverlap_selection_is_outcome_blind_and_respects_horizon():
    issued = np.zeros((1, 50, 1), dtype=bool)
    issued[0, [1, 5, 12, 22, 23, 45], 0] = True
    selected = MODULE._nonoverlap_mask(issued, 10)
    assert np.flatnonzero(selected[0, :, 0]).tolist() == [1, 12, 22, 45]


def test_outcome_window_starts_after_anchor_and_is_future_immutable():
    common = np.zeros(30)
    idiosyncratic = np.zeros((30, 2))
    frame_noise = np.zeros(30)
    initial = MODULE._future_window_latent(
        common, idiosyncratic, frame_noise, days=10, horizon=5,
        rho_common=0, rho_symbol=0, rho_frame=0, overlap_windows=True)
    common[0] = 1000
    idiosyncratic[0] = 1000
    frame_noise[0] = 1000
    anchor_mutated = MODULE._future_window_latent(
        common, idiosyncratic, frame_noise, days=10, horizon=5,
        rho_common=0, rho_symbol=0, rho_frame=0, overlap_windows=True)
    np.testing.assert_array_equal(initial, anchor_mutated)
    common[1] = 1
    future_mutated = MODULE._future_window_latent(
        common, idiosyncratic, frame_noise, days=10, horizon=5,
        rho_common=0, rho_symbol=0, rho_frame=0, overlap_windows=True)
    assert not np.array_equal(anchor_mutated, future_mutated)


def test_daily_aggregation_contains_both_denominators():
    labels, issued = MODULE.generate_replication(days=80, seed=45)
    counts, wins = MODULE._daily_counts(labels, issued, days=80)
    assert counts.shape == wins.shape == (80, 48)
    assert np.all(wins <= counts)
    assert np.all(counts[:, 1::2].sum(axis=0) <= counts[:, ::2].sum(axis=0))


def test_simultaneous_lower_bound_fails_closed_on_missing_claim():
    counts = np.ones((50, 2))
    wins = np.ones((50, 2))
    counts[:, 0] = 0
    wins[:, 0] = 0
    with pytest.raises(ValueError, match="no emitted events"):
        MODULE.simultaneous_lower_bounds(counts, wins, bootstrap_reps=50,
                                         block_length=10, seed=5)


def test_ineligible_claims_cannot_trigger_a_false_pass():
    counts = np.full((60, 4), 10.0)
    wins = counts.copy()
    result = MODULE.simultaneous_lower_bounds(
        counts, wins, bootstrap_reps=50, block_length=10, seed=6,
        eligible_claims=np.zeros(4, dtype=bool))
    assert result["eligible_claim_count"] == 0
    assert result["reject_any_at_80"] is False
