import unittest
from unittest.mock import patch

from equities import (Bar, Costs, c1_signals, preregistered_costs, simulate_c1,
                      simulate_c2, simulate_c3, simulate_c4)


def bars(rows):
    return [Bar(i, *row) for i, row in enumerate(rows)]


class EquitiesTests(unittest.TestCase):
    def test_c3_uses_prior_high_and_next_open_entry(self):
        data = [Bar(i, 100, 101, 99, 100) for i in range(150)]
        data[126] = Bar(126, 100, 102, 99, 102)
        data[127] = Bar(127, 103, 104, 102, 103)
        data[128] = Bar(128, 103, 104, 102, 103)
        trades = simulate_c3(data, lookback=126, stop_atr=2,
                             reward_r=2, holding_bars=20)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].entry_index, 127)
        self.assertEqual(trades[0].entry_price, 103)
        with self.assertRaises(ValueError):
            simulate_c3(data, lookback=100)

    def test_c4_requires_uptrend_pullback_and_next_open(self):
        data = [Bar(i, 100 + i * 0.1, 101 + i * 0.1,
                    99 + i * 0.1, 100 + i * 0.1) for i in range(210)]
        data[205] = Bar(205, 120.4, 121, 120, 120.8)
        data[206] = Bar(206, 120.9, 121.5, 120.5, 121)
        data[207] = Bar(207, 121, 121.5, 120.5, 121)
        trades = simulate_c4(data, distance_atr=1.0, stop_buffer=0,
                             reward_r=2, holding_bars=10)
        self.assertTrue(all(t.entry_index == t.signal_index + 1 for t in trades))
        self.assertTrue(all(t.strategy == "C4" for t in trades))

    def test_c1_signal_is_causal_and_enters_next_open(self):
        data = bars([(10, 11, 9, 10)] * 14 + [(10, 10, 8, 9), (9, 10, 8, 9),
                                               (10, 12, 10, 12), (10, 11, 9.5, 10.5),
                                               (11, 17, 10, 16), (12, 13, 11, 12)])
        signals = c1_signals(data, "daily")
        self.assertTrue(any(index == 16 for index, _, _ in signals))
        # Altering future bars cannot change the already-established signal.
        prefix = c1_signals(data[:17], "daily")
        self.assertEqual([s for s in signals if s[0] < 17], prefix)
        trades = simulate_c1(data, lookback=10, retest_bars=10, reward_r=2, holding_bars=20)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].signal_index, 16)
        self.assertEqual(trades[0].entry_index, 18)
        self.assertEqual(trades[0].entry_price, data[18].open)
        self.assertEqual(trades[0].exit_reason, "target")

    def test_c2_skips_entry_that_gaps_through_target_or_stop(self):
        data = [Bar(i, 100, 101, 99, 100) for i in range(20)]
        data[14] = Bar(14, 100, 101, 99, 100)
        data[15] = Bar(15, 80, 82, 70, 81)  # gap and bullish close; target is 100
        data[16] = Bar(16, 101, 103, 99, 102)  # entry beyond target: skip
        self.assertEqual(simulate_c2(data), [])

        data[16] = Bar(16, 69, 72, 68, 71)  # entry at/below signal low stop: skip
        self.assertEqual(simulate_c2(data), [])

    def test_same_bar_stop_and_target_resolves_stop_first(self):
        # Directly exercise a C1 trade whose entry bar reaches both levels.
        data = bars([(10, 11, 9, 10)] * 14 + [(10, 10, 8, 9),
            (10, 12, 10, 12), (10, 12, 9, 11), (11, 17, 7, 12)])
        trades = simulate_c1(data, lookback=10, retest_bars=10, reward_r=2, holding_bars=20)
        self.assertTrue(trades)
        self.assertEqual(trades[0].exit_reason, "stop")
        kr_trades = simulate_c1(data, lookback=10, retest_bars=10, reward_r=2,
                                holding_bars=20, market="KR")
        self.assertTrue(kr_trades)
        self.assertNotEqual(trades[0].cost_bps, kr_trades[0].cost_bps)

    def test_weekly_incomplete_bar_is_excluded(self):
        data = [Bar(i, 10, 11, 9, 10, complete=True) for i in range(14)]
        data += [Bar(14, 10, 12, 10, 12, complete=False)]
        self.assertNotIn(14, [i for i, _, _ in c1_signals(data, "weekly")])

    def test_incomplete_bar_must_be_trailing(self):
        data = [Bar(0, 10, 11, 9, 10, complete=False),
                Bar(1, 10, 11, 9, 10, complete=True)]
        with self.assertRaises(ValueError):
            c1_signals(data, "daily")

    def test_non_finite_ohlc_is_rejected(self):
        with self.assertRaises(ValueError):
            c1_signals([Bar(0, float("nan"), 11, 9, 10)], "daily")

    def test_market_costs_are_selected_by_market_when_not_overridden(self):
        # Explicit market selection prevents KR from silently inheriting US costs.
        self.assertEqual(preregistered_costs("US").commission_bps_per_side, 5.0)
        self.assertEqual(preregistered_costs("KR").commission_bps_per_side, 1.5)
        self.assertEqual(preregistered_costs("KR").sell_tax_bps, 18.0)

    def test_simulated_kr_trade_charges_kr_costs_not_us_costs(self):
        data = [Bar(i, 100, 101, 99, 100) for i in range(20)]
        with patch("equities.c2_signals", return_value=[(1, 101, 90)]):
            us = simulate_c2(data, holding_bars=5, market="US")
            kr = simulate_c2(data, holding_bars=5, market="KR")
        self.assertEqual(len(us), 1)
        self.assertEqual(len(kr), 1)
        self.assertEqual(us[0].cost_bps, 20.0)
        self.assertEqual(kr[0].cost_bps, 31.0)
        self.assertAlmostEqual(us[0].net_return, us[0].gross_return - 0.002)
        self.assertAlmostEqual(kr[0].net_return, kr[0].gross_return - 0.0031)

    def test_trade_net_return_uses_subtractive_preregistered_round_trip_cost(self):
        from equities import _trade

        us = _trade("C1", 0, 1, 2, 100, 110, "time", preregistered_costs("US"))
        kr = _trade("C1", 0, 1, 2, 100, 110, "time", preregistered_costs("KR"))
        self.assertAlmostEqual(us.gross_return, 0.10)
        self.assertEqual(us.cost_bps, 20.0)
        self.assertAlmostEqual(us.net_return, 0.098)
        self.assertEqual(kr.cost_bps, 31.0)
        self.assertAlmostEqual(kr.net_return, 0.0969)

    def test_overlapping_c1_signal_is_ignored_while_first_zone_is_active(self):
        data = [Bar(i, 102, 103, 101.5, 102) for i in range(40)]
        data[6] = Bar(6, 101, 103, 100.5, 102.8)  # retest zone2 only
        with patch("equities.c1_signals", return_value=[(1, 99, 100), (5, 101, 102)]):
            trades = simulate_c1(data, lookback=10, retest_bars=10,
                                 reward_r=2, holding_bars=20)
        self.assertEqual(trades, [])

    def test_c1_signal_confirmed_on_exit_bar_is_not_dropped(self):
        data = [Bar(i, 102, 103, 101.5, 102) for i in range(30)]
        data[2] = Bar(2, 100, 101, 99.5, 100.5)
        data[3] = Bar(3, 100, 102, 99.5, 101.5)  # target for first trade; new signal at close
        data[4] = Bar(4, 101, 103, 100.5, 101.5)
        data[5] = Bar(5, 102, 104, 101.5, 103)  # target for second trade
        with patch("equities.c1_signals", return_value=[(1, 99, 100), (3, 100, 101)]):
            trades = simulate_c1(data, lookback=10, retest_bars=10,
                                 reward_r=2, holding_bars=20)
        self.assertEqual([trade.signal_index for trade in trades], [1, 3])
        self.assertEqual(trades[0].exit_index, 3)
        self.assertEqual(trades[1].entry_index, 5)

    def test_weekly_signal_on_exit_week_close_is_eligible_after_exit(self):
        weekly = [Bar(4 + 5 * i, 102, 103, 101.5, 102) for i in range(25)]
        weekly[2] = Bar(14, 100, 101, 99.5, 100.5)
        weekly[18] = Bar(94, 101, 103, 100.5, 102)
        daily = [Bar(i, 100, 101, 99.5, 100) for i in range(130)]
        daily[89] = Bar(89, 100, 102, 99.5, 101.5)  # first target, same weekly close
        for i in range(95, len(daily)):
            daily[i] = Bar(i, 102, 103, 101, 102)
        daily[96] = Bar(96, 102, 106, 101, 105)  # second target
        with patch("equities.c1_signals", return_value=[(1, 99, 100), (17, 100, 101)]):
            trades = simulate_c1(weekly, timeframe="weekly", lookback=10,
                                 retest_bars=10, reward_r=2, holding_bars=20,
                                 execution_bars=daily)
        self.assertEqual([trade.signal_index for trade in trades], [1, 17])
        self.assertEqual(trades[0].exit_index, 89)
        self.assertEqual(trades[1].entry_index, 95)

    def test_c1_audit_separates_expired_from_right_censored_retest_windows(self):
        short_data = [Bar(i, 102, 103, 101.5, 102) for i in range(4)]
        full_data = [Bar(i, 102, 103, 101.5, 102) for i in range(15)]
        with patch("equities.c1_signals", return_value=[(1, 99, 100)]):
            short_audit = {}
            full_audit = {}
            simulate_c1(short_data, retest_bars=10, audit=short_audit)
            simulate_c1(full_data, retest_bars=10, audit=full_audit)
        self.assertEqual(short_audit["right_censored"], 1)
        self.assertEqual(short_audit["expired"], 0)
        self.assertEqual(full_audit["right_censored"], 0)
        self.assertEqual(full_audit["expired"], 1)

    def test_weekly_last_bar_signal_is_right_censored_without_followup(self):
        weekly = [Bar(i, 102, 103, 101.5, 102) for i in range(12)]
        daily = [Bar(i, 102, 103, 101, 102) for i in range(60)]
        with patch("equities.c1_signals", return_value=[(11, 99, 100)]):
            audit = {}
            trades = simulate_c1(weekly, timeframe="weekly", lookback=10,
                                 retest_bars=10, reward_r=2, holding_bars=20,
                                 execution_bars=daily, audit=audit)
        self.assertEqual(trades, [])
        self.assertEqual(audit["right_censored"], 1)
        self.assertEqual(audit["expired"], 0)

    def test_cost_fields_match_preregistration(self):
        self.assertEqual(preregistered_costs("US"), Costs(5, 5, 0))
        self.assertEqual(preregistered_costs("KR"), Costs(1.5, 5, 18))


if __name__ == "__main__":
    unittest.main()
