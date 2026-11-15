import numpy as np
import pandas as pd

from chart_predictor.btc_lead_alt_lag_probe import (
    _features_for_alt, _moving_block_inference, signal_side,
)


def test_signal_rule_is_sign_symmetric_and_requires_all_trend_gates():
    assert signal_side(0.02, 0.01, -0.001, 0.003, 0.01) == "long"
    assert signal_side(-0.02, 0.01, 0.001, -0.003, -0.01) == "short"
    assert signal_side(0.02, 0.01, 0.001, 0.003, 0.01) is None
    assert signal_side(0.02, 0.01, -0.001, 0.003, -0.01) is None
    assert signal_side(float("nan"), 0.01, -0.001, 0.003, 0.01) is None


def test_feature_prefix_is_unchanged_when_future_prices_are_mutated():
    n = 500
    times = np.arange(n, dtype=np.int64) * 60_000
    btc_close = 100 * np.exp(np.cumsum(0.0002 + 0.0001 * np.sin(np.arange(n) / 7)))
    alt_close = 20 * np.exp(np.cumsum(0.00025 + 0.0002 * np.sin(np.arange(n) / 9)))

    def frame(symbol, close):
        return pd.DataFrame({"t_open_ms": times, "o": close * 0.9999,
                             "h": close * 1.001, "l": close * 0.999,
                             "c": close})

    thresholds = {0: 0.0005}
    base = _features_for_alt(frame("ALT", alt_close), frame("BTC", btc_close), thresholds)
    anchor = 200
    assert np.isclose(base.iloc[anchor].alt_r5,
                      np.log(alt_close[anchor] / alt_close[anchor - 5]))
    assert np.isclose(base.iloc[anchor].alt_r15_pre,
                      np.log(alt_close[anchor - 5] / alt_close[anchor - 20]))
    assert np.isclose(base.iloc[anchor].alt_r60_pre,
                      np.log(alt_close[anchor - 5] / alt_close[anchor - 65]))
    changed_btc = btc_close.copy()
    changed_alt = alt_close.copy()
    changed_btc[401:] *= np.linspace(1, 2, n - 401)
    changed_alt[401:] *= np.linspace(1, 0.5, n - 401)
    mutated = _features_for_alt(frame("ALT", changed_alt), frame("BTC", changed_btc), thresholds)
    columns = ["btc_r5", "btc_threshold", "beta_lagged", "alt_r5", "residual",
               "alt_r15_pre", "alt_r60_pre", "atr14", "side"]
    pd.testing.assert_frame_equal(base.loc[:400, columns], mutated.loc[:400, columns])
    # Deliberately leaky next-close feature is sensitive to the same mutation.
    leaky_before = np.log(alt_close[402] / alt_close[401])
    leaky_after = np.log(changed_alt[402] / changed_alt[401])
    assert leaky_before != leaky_after


def test_cluster_bootstrap_emits_paired_utc_day_intervals():
    rows = []
    for day in range(21):
        for minute, outcome in enumerate(("TARGET", "STOP")):
            entry_ms = day * 86_400_000 + minute * 60_000
            common = {"symbol": "ALT", "entry_ms": entry_ms, "horizon_bars": 10,
                      "gross_return": 0.02 if outcome == "TARGET" else -0.01,
                      "risk_fraction": 0.01}
            rows.append({**common, "strategy": "candidate", "outcome": outcome})
            rows.append({**common, "strategy": "fixed_seed_random",
                         "outcome": "STOP"})
    result = _moving_block_inference(rows, replicates=100, block_days=7)
    paired = next(row for row in result if row.get("paired_difference") ==
                  "candidate_minus_fixed_seed_random")
    assert paired["paired_events"] == 42
    assert paired["precision_difference_ci95"][0] > 0
