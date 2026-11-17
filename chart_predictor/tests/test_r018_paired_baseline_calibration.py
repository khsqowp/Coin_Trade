import importlib.util
from pathlib import Path

import numpy as np
import pytest


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
    larger_batch = R018.paired_lower_bounds(
        n, x, reps=199, mean_block=5, seed=9, batch_size=199)
    np.testing.assert_array_equal(first["lower"], larger_batch["lower"])


def test_vectorized_bootstrap_matches_original_cluster_resample_formula():
    rng = np.random.default_rng(440)
    n = rng.integers(4, 24, size=(47, 48)).astype(float)
    x = np.empty_like(n)
    for day in range(n.shape[0]):
        x[day] = rng.integers(-n[day].astype(int), n[day].astype(int) + 1)
    eligible = np.ones(48, dtype=bool)
    eligible[[3, 17, 46]] = False
    seed, reps, block = 818, 1999, 7

    # Independent, deliberately simple reference using the original day-index
    # gather and per-replicate cluster residual calculation.
    active = np.flatnonzero(eligible)
    nn, xx = n[:, active], x[:, active]
    total = nn.sum(axis=0)
    delta = xx.sum(axis=0) / total
    d = len(nn)
    se = np.sqrt(d / (d - 1) * ((xx - nn * delta) ** 2).sum(axis=0)) / total
    indices = R018.stationary_indices(np.random.default_rng(seed), reps, d, block)
    maxima = np.empty(reps)
    for b, ix in enumerate(indices):
        n_star, x_star = nn[ix], xx[ix]
        total_star = n_star.sum(axis=0)
        delta_star = x_star.sum(axis=0) / total_star
        se_star = np.sqrt(d / (d - 1) *
                          ((x_star - n_star * delta_star) ** 2).sum(axis=0)) / total_star
        maxima[b] = ((delta_star - delta) / se_star).max()
    critical = float(np.quantile(maxima, 0.95, method="higher"))

    result = R018.paired_lower_bounds(
        n, x, reps=reps, mean_block=block, seed=seed,
        eligible_contrasts=eligible)
    np.testing.assert_allclose(result["delta"][active], delta, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(result["se"][active], se, rtol=1e-13, atol=1e-13)
    assert result["critical"] == pytest.approx(critical, rel=1e-12, abs=1e-12)
    np.testing.assert_allclose(result["lower"][active], delta-critical*se,
                               rtol=1e-12, atol=1e-12)


def test_future_mutation_guard_accepts_causal_and_rejects_peeking_functions():
    prefix = np.array([[1.0], [2.0], [3.0]])
    future_a = np.array([[4.0], [5.0]])
    future_b = np.array([[400.0], [-500.0]])
    R018.assert_prefix_invariant(lambda values: np.cumsum(values, axis=0),
                                 prefix, future_a, future_b)

    def peeks_one_row_ahead(values):
        return values + np.roll(values, -1, axis=0)

    try:
        R018.assert_prefix_invariant(peeks_one_row_ahead, prefix, future_a, future_b)
    except AssertionError as exc:
        assert "future-peeking" in str(exc)
    else:
        raise AssertionError("injected future-peeking rule was not rejected")


def test_nonoverlap_selector_is_outcome_blind_and_enforces_registered_horizon():
    issued = np.zeros((24, 2), dtype=bool)
    issued[[0, 9, 10, 20, 21], 0] = True
    selected = R018.select_nonoverlap(issued, horizon=10)
    assert np.flatnonzero(selected[:, 0]).tolist() == [0, 10, 20]
    selected_20 = R018.select_nonoverlap(issued, horizon=20)
    assert np.flatnonzero(selected_20[:, 0]).tolist() == [0, 20]
    assert not selected[:, 1].any()


def test_claim_eligibility_boundary_and_fail_closed_missingness():
    assert not R018.claim_eligibility(199, 20, 0.10)
    assert R018.claim_eligibility(200, 20, 0.10)
    assert not R018.claim_eligibility(200, 19, 0.10)
    assert not R018.claim_eligibility(200, 20, 0.0999)
    assert not R018.claim_eligibility(200, 20, 0.10, unresolved_count=1)


def test_hierarchical_seed_cells_are_distinct_for_panels_and_blocks():
    seeds = [R018.child_seed(20261123, 0, 0, panel, block, 0)
             for panel in range(10) for block in R018.BLOCKS]
    assert len(seeds) == 50
    assert len(set(seeds)) == len(seeds)


def test_ineligible_contrast_is_visible_but_not_used_for_max_t():
    rng = np.random.default_rng(90)
    n = np.full((365, 48), 20.0)
    x = rng.normal(0, 2, size=(365, 48))
    x[:, -1] += 100.0
    eligible = np.ones(48, dtype=bool)
    eligible[-1] = False
    result = R018.paired_lower_bounds(n, x, reps=199, mean_block=2,
                                      seed=91, eligible_contrasts=eligible)
    assert result["eligible_contrasts"] == 47
    assert np.isnan(result["lower"][-1])


def test_m2_keeps_all_emitted_resolved_denominator_and_fails_closed():
    resolved = R018.m2_summary(emitted=100, resolved_wins=80, unresolved=0)
    assert resolved["status"] == "RESOLVED"
    assert resolved["m2_resolved"] == 0.8
    missing = R018.m2_summary(emitted=100, resolved_wins=79, unresolved=1)
    assert missing["status"] == "INCONCLUSIVE"
    assert missing["m2_resolved"] == 79 / 99
    assert missing["m2_unresolved_as_loss"] == 0.79


def test_future_window_is_average_of_strictly_future_values():
    values = np.arange(8, dtype=float)[:, None]
    got = R018._future_mean(values, 3)
    np.testing.assert_array_equal(got[:3, 0], np.array([2.0, 3.0, 4.0]))
    assert R018._ar_mean_variance(3, 0.0) == 1 / 3


def test_ar_future_window_variance_matches_exact_stationary_formula():
    rho, horizon = 0.70, 10
    rng = np.random.default_rng(77)
    series = R018._ar1(rng, horizon + 1, 30_000, rho)
    averages = R018._future_mean(series, horizon)[0]
    expected = R018._ar_mean_variance(horizon, rho)
    assert np.var(averages, ddof=0) == pytest.approx(expected, rel=0.04)


def test_joint_promotion_requires_point_m2_and_both_baselines():
    m2 = np.full(24, 0.81)
    eligible = np.ones(24, dtype=bool)
    lower = np.full(48, 0.01)
    assert R018.joint_promotion(m2, eligible, lower).all()
    lower[17] = -0.01
    promoted = R018.joint_promotion(m2, eligible, lower)
    assert not promoted[8]
    m2[9] = 0.799
    promoted = R018.joint_promotion(m2, eligible, lower)
    assert not promoted[9]
    eligible[10] = False
    assert not R018.joint_promotion(m2, eligible, lower)[10]


def test_profile_and_missingness_generators_preserve_issue_seed_and_fail_closed():
    n_a, _, a = R018.synthetic_panel(901, profile="A")
    n_b, _, b = R018.synthetic_panel(901, profile="B")
    np.testing.assert_array_equal(n_a, n_b)
    np.testing.assert_array_equal(a["coverage"], b["coverage"])

    _, _, miss_ind = R018.synthetic_panel(902, profile="B",
                                         missingness="independent_1pct")
    independent_rate = (miss_ind["unresolved_by_claim"].sum() /
                        miss_ind["raw_emitted"].sum())
    assert 0.007 <= independent_rate <= 0.013
    assert not miss_ind["eligible_claims"].any()

    _, _, miss_shock = R018.synthetic_panel(903, profile="C",
                                           missingness="shock_5pct")
    shock_rate = (miss_shock["unresolved_by_claim"].sum() /
                  miss_shock["raw_emitted"].sum())
    assert 0.02 <= shock_rate <= 0.08
    assert not miss_shock["eligible_claims"].any()


def test_profile_a_cannot_silently_apply_common_factor_shock_missingness():
    with pytest.raises(ValueError, match="requires the shared common factor"):
        R018.synthetic_panel(4, profile="A", missingness="shock_5pct")


def test_checkpoint_digest_detects_accidental_record_tampering():
    record = {"panel": 3, "values": [1, 2, 3]}
    record["record_sha256"] = R018._record_digest(record)
    assert record["record_sha256"] == R018._record_digest(record)
    record["values"][0] = 9
    assert record["record_sha256"] != R018._record_digest(record)


def test_checkpoint_validator_binds_panel_seed_config_and_source():
    record = {
        "panel": 7, "source_sha256": "source", "config_sha256": "config",
        "panel_seed": 456, "m2_by_claim": [0.5] * 24,
        "eligible_by_claim": [True] * 24,
        "baseline_m2_by_contrast": [0.5] * 48,
        "blocks": {str(b): {"status": "OK"} for b in R018.BLOCKS},
        "errors": {},
    }
    record["record_sha256"] = R018._record_digest(record)
    R018._validate_panel_record(record, panel=7, source_hash="source",
                                config_hash="config", panel_seed=456)
    with pytest.raises(ValueError, match="identity"):
        R018._validate_panel_record(record, panel=8, source_hash="source",
                                    config_hash="config", panel_seed=456)


def test_baseline_gate_requires_exact_profile_source_blocks_and_registered_counts():
    gate = {"run_id": "r018-profile-A-null-none", "profile": "A",
            "scenario": "null", "missingness": "none", "simulations": 5000,
            "bootstrap_reps": 1999, "seed": 20261123, "source_sha256": "s",
            "blocks": list(R018.BLOCKS),
            "results": [{"block_length": b, "gate_pass": True}
                        for b in R018.BLOCKS]}
    R018._validate_profile_a_gate(gate, source_hash="s", simulations=5000,
                                  bootstrap_reps=1999, seed=20261123)
    gate["source_sha256"] = "stale"
    with pytest.raises(ValueError, match="exact registered run"):
        R018._validate_profile_a_gate(gate, source_hash="s", simulations=5000,
                                      bootstrap_reps=1999, seed=20261123)


def test_calibration_gate_prevents_vacuous_null_pass_and_separates_alternatives():
    assert R018._calibration_decision("null", 0.949, 0.001, 0) == ("INCONCLUSIVE", False)
    assert R018._calibration_decision("null", 0.95, 0.06, 0) == ("PASS", True)
    assert R018._calibration_decision("null", 1.0, 0.061, 0) == ("REJECT", False)
    assert R018._calibration_decision("null", 1.0, 0.01, 1) == ("REJECT", False)
    assert R018._calibration_decision("alternatives", 0.0, 1.0, 99) == (
        "POWER_DIAGNOSTIC", None)
