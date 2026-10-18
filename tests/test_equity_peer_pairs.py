from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.rs_equity_peer_pairs import _point_in_time_peer_and_z, make_pair_targets


def _panel(close):
    close = np.asarray(close, float)
    nday, nsym = close.shape
    return SimpleNamespace(
        c=close,
        eligible=np.isfinite(close),
        tradable=np.isfinite(close),
        symbols=[f"S{i}" for i in range(nsym)],
    )


def test_peer_and_zscore_do_not_use_future_prices():
    rng = np.random.default_rng(41)
    n = 360
    common = rng.normal(0, .01, n)
    returns = np.column_stack([
        common + rng.normal(0, .002, n),
        common + rng.normal(0, .003, n),
        rng.normal(0, .012, n),
    ])
    close = 50 * np.cumprod(1 + returns, axis=0)
    original_peer, original_z = _point_in_time_peer_and_z(close, min_obs=40, z_window=25)
    changed = close.copy()
    changed[240:] *= np.exp(rng.normal(0, .7, changed[240:].shape))
    changed_peer, changed_z = _point_in_time_peer_and_z(changed, min_obs=40, z_window=25)
    np.testing.assert_array_equal(original_peer[:240], changed_peer[:240])
    np.testing.assert_allclose(original_z[:240], changed_z[:240], rtol=0, atol=0, equal_nan=True)


def test_pair_targets_are_gross_bounded_and_dollar_neutral():
    rng = np.random.default_rng(7)
    n = 420
    market = rng.normal(0, .008, n)
    returns = np.column_stack([
        market + rng.normal(0, .002, n),
        market + rng.normal(0, .003, n),
        -market + rng.normal(0, .003, n),
        rng.normal(0, .01, n),
    ])
    panel = _panel(100 * np.cumprod(1 + returns, axis=0))
    target, active = make_pair_targets(panel, entry_z=1.5, exit_z=.25, stop_z=3.0)
    np.testing.assert_allclose(target.sum(axis=1), 0.0, rtol=0, atol=1e-12)
    assert np.all(np.abs(target).sum(axis=1) <= 1.0 + 1e-12)
    assert np.all(active >= 0)
    assert np.count_nonzero(active) > 0


def test_pair_thresholds_reject_invalid_ordering():
    panel = _panel(np.tile(np.linspace(90, 110, 240)[:, None], (1, 2)))
    try:
        make_pair_targets(panel, entry_z=1.0, exit_z=1.5, stop_z=3.0)
    except ValueError:
        return
    raise AssertionError("invalid threshold ordering must be rejected")
