import unittest
from unittest.mock import patch

from crypto import Bar, Zone
import search_crypto_r7 as r7


class SearchCryptoR7Tests(unittest.TestCase):
    def test_exactly_one_fixed_trial_and_adverse_funding(self):
        self.assertEqual(len(r7.CONFIGS), 1)
        self.assertEqual(r7.CONFIGS[0]["funding_order_policy"], "adverse_only")
        self.assertEqual(r7.CONFIGS[0]["btc_regime"],
                         "close_above_sma150_and_sma150_rising_24_bars")
        with self.assertRaises(ValueError):
            r7.configs_for("R7-other")

    def test_btc_regime_requires_only_trailing_closed_values(self):
        bars = [Bar(index * r7.DURATION_MS, 100, 101, 99, 100 + index, 1)
                for index in range(180)]
        flags = r7._btc_regime(bars)
        self.assertFalse(flags[bars[172].timestamp + r7.DURATION_MS])
        self.assertTrue(flags[bars[173].timestamp + r7.DURATION_MS])
        bars[174] = Bar(bars[174].timestamp, 1, 2, 0.5, 1, 1)
        revised = r7._btc_regime(bars)
        self.assertEqual(
            flags[bars[173].timestamp + r7.DURATION_MS],
            revised[bars[173].timestamp + r7.DURATION_MS],
        )

    def test_regime_lookup_uses_latest_available_btc_bar(self):
        times = [100, 200, 300]
        flags = {100: False, 200: True, 300: False}
        self.assertFalse(r7._regime_at(199, times, flags))
        self.assertTrue(r7._regime_at(250, times, flags))
        self.assertFalse(r7._regime_at(300, times, flags))

    def test_btc_regime_is_available_at_candle_close_not_open(self):
        bars = [Bar(index * r7.DURATION_MS, 100, 101, 99, 100 + index, 1)
                for index in range(175)]
        last = bars[-1]
        bars[-1] = Bar(last.timestamp, last.open, 2, 0.5, 1, last.volume)
        flags = r7._btc_regime(bars)
        regime_times = sorted(flags)
        available_at = bars[-2].timestamp + r7.DURATION_MS

        self.assertFalse(r7._regime_at(available_at - 1, regime_times, flags))
        self.assertTrue(r7._regime_at(available_at, regime_times, flags))
        self.assertFalse(r7._regime_at(
            available_at + r7.DURATION_MS, regime_times, flags
        ))

    def test_alt_signal_uses_regime_available_at_signal_close(self):
        bars = [Bar(index * r7.DURATION_MS, 100, 101, 99, 100, 1)
                for index in range(4)]
        zone = Zone(0, 0, "long", 98, 102, 1)
        close_time = bars[0].timestamp + r7.DURATION_MS

        with patch.object(r7, "_setup_for_zone", return_value=None) as setup:
            r7._trades_for_symbol(
                bars, {}, r7.CONFIGS[0], [zone], [close_time], {close_time: True}
            )
        setup.assert_called_once()

        with patch.object(r7, "_setup_for_zone", return_value=None) as setup:
            r7._trades_for_symbol(
                bars, {}, r7.CONFIGS[0], [zone], [close_time + r7.DURATION_MS],
                {close_time + r7.DURATION_MS: True},
            )
        setup.assert_not_called()

    def test_btc_regime_filters_signal_before_retest_search(self):
        bars = [Bar(i * r7.DURATION_MS, 100, 101, 99, 100, 1) for i in range(5)]
        zone = Zone(1, 0, "long", 98, 102, 1)
        config = r7.CONFIGS[0]
        trades, _audit = r7._trades_for_symbol(
            bars, {}, config, [zone], [0], {0: False}
        )
        self.assertEqual(trades, [])


if __name__ == "__main__":
    unittest.main()
