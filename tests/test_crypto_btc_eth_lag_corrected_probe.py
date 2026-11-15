import numpy as np
import pandas as pd

from scripts.research.crypto_btc_eth_lag_corrected_probe import (
    FIVE_MIN_MS,
    aggregate_complete_5m,
    make_signals,
    resolve,
)


def test_aggregate_requires_five_consecutive_minute_rows():
    frame = pd.DataFrame({
        "t_open_ms": [0, 60_000, 120_000, 180_000, 240_000, 600_000],
        "o": [10, 11, 12, 13, 14, 15],
        "h": [11, 12, 13, 14, 15, 16],
        "l": [9, 10, 11, 12, 13, 14],
        "c": [10.5, 11.5, 12.5, 13.5, 14.5, 15.5],
    })
    bars = aggregate_complete_5m(frame)
    assert bars.t.tolist() == [0]
    assert bars.iloc[0][["o", "h", "l", "c"]].tolist() == [10, 15, 9, 14.5]


def test_bearish_btc_impulse_and_smaller_eth_drop_is_a_short_signal():
    times = np.arange(24, dtype=np.int64) * FIVE_MIN_MS
    btc_close = 100 * np.exp(np.cumsum(np.tile([0.001, -0.0005], 12)))
    eth_close = 50 * np.exp(np.cumsum(np.tile([0.0008, -0.0002], 12)))
    btc_close[22] = btc_close[21] * np.exp(-0.03)
    eth_close[22] = eth_close[21] * np.exp(-0.005)
    def bars(close):
        return pd.DataFrame({"t": times, "o": close, "h": close * 1.001,
                             "l": close * 0.999, "c": close})
    signals = make_signals(bars(btc_close), bars(eth_close))
    assert signals.loc[22, "btc_z"] < -2
    assert signals.loc[22, "lag_side"] == -1


def test_future_rows_do_not_change_past_signal_values():
    times = np.arange(40, dtype=np.int64) * FIVE_MIN_MS
    close_a = 100 * np.exp(np.cumsum(0.001 * np.sin(np.arange(40))))
    close_b = 50 * np.exp(np.cumsum(0.001 * np.cos(np.arange(40))))
    def bars(close, end):
        values = close[:end]
        return pd.DataFrame({"t": times[:end], "o": values, "h": values * 1.001,
                             "l": values * 0.999, "c": values})
    prior = make_signals(bars(close_a, 32), bars(close_b, 32))
    future_mutated_a, future_mutated_b = close_a.copy(), close_b.copy()
    future_mutated_a[32:] *= 20
    future_mutated_b[32:] *= 0.1
    full = make_signals(bars(future_mutated_a, 40), bars(future_mutated_b, 40))
    pd.testing.assert_frame_equal(
        prior[["btc_z", "eth_z", "lag_side"]],
        full.loc[:31, ["btc_z", "eth_z", "lag_side"]],
    )


def test_same_minute_stop_and_target_touch_resolves_stop_first():
    bars = pd.DataFrame({"t": [0, FIVE_MIN_MS], "o": [100, 100],
                         "h": [101, 103], "l": [99, 97], "c": [100, 100]})
    minutes = pd.DataFrame({"t_open_ms": 300_000 + np.arange(50) * 60_000,
                            "o": np.full(50, 100.0), "h": np.full(50, 103.0),
                            "l": np.full(50, 97.0), "c": np.full(50, 100.0)})
    trade = resolve(0, 1, bars, minutes, previous_range=1.0)
    assert trade["reason"] == "stop"
    assert trade["gross_return"] < 0
