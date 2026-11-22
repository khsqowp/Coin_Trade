import unittest
from unittest.mock import patch

from crypto import (Bar, FundingEvent, Setup, Zone, enforce_single_active_zone,
                    first_retest, simulate_orderblock, simulate_trade, zones)


class CryptoOrderBlockTests(unittest.TestCase):
    def test_retest_entry_uses_next_open_and_fixed_registration_atr(self):
        data = [Bar(i, 100, 102, 98, 100, 10) for i in range(24)]
        data[20] = Bar(20, 100, 101, 99, 100, 10)
        data[21] = Bar(21, 100, 103, 100, 102, 10)
        data[22] = Bar(22, 101, 103, 100, 102, 10)
        zone = Zone(20, 19, "long", 99, 101, 2)
        setup = first_retest(data, zone, deadline=24, reward_r=1.5)
        self.assertIsNotNone(setup)
        self.assertEqual(setup.entry_index, 22)
        self.assertEqual(setup.entry_price, 101)
        self.assertAlmostEqual(setup.stop, 98.8)
        self.assertAlmostEqual(setup.target, 104.3)

    def test_invalidation_on_retest_bar_prevents_entry(self):
        data = [Bar(i, 100, 102, 98, 100, 10) for i in range(23)]
        data[21] = Bar(21, 100, 101, 98.7, 100, 10)
        zone = Zone(20, 19, "long", 99, 101, 2)
        self.assertIsNone(first_retest(data, zone, deadline=24, reward_r=2.0))

    def test_next_open_beyond_ob_edge_is_rejected_even_above_padded_stop(self):
        data = [Bar(i, 102, 103, 101.5, 102, 10) for i in range(23)]
        data[21] = Bar(21, 100, 101, 99.5, 100, 10)
        data[22] = Bar(22, 98.9, 100, 98.5, 99, 10)
        zone = Zone(20, 19, "long", 99, 101, 2)  # padded stop = 98.8
        self.assertIsNone(first_retest(data, zone, deadline=24, reward_r=1.5))

    def test_retest_deadline_is_inclusive_and_expiry_excludes_next_bar(self):
        data = [Bar(i, 102, 103, 101.5, 102, 10) for i in range(47)]
        zone = Zone(20, 19, "long", 99, 101, 2)
        data[44] = Bar(44, 100, 101, 99.5, 100, 10)  # 24th eligible bar after registration
        setup = first_retest(data, zone, deadline=24, reward_r=1.5)
        self.assertIsNotNone(setup)
        self.assertEqual(setup.entry_index, 45)
        data[44] = Bar(44, 102, 103, 101.5, 102, 10)
        data[45] = Bar(45, 102, 103, 100.5, 102, 10)  # 25th bar: expired for H=24
        self.assertIsNone(first_retest(data, zone, deadline=24, reward_r=1.5))
        self.assertIsNotNone(first_retest(data, zone, deadline=48, reward_r=1.5))

    def test_future_mutation_does_not_rewrite_past_zone(self):
        data = [Bar(i, 100, 101, 99, 100, 10) for i in range(30)]
        data[15] = Bar(15, 100, 105, 99, 101, 10)
        data[19] = Bar(19, 101, 102, 99, 100, 10)
        data[20] = Bar(20, 100, 111, 99, 110, 10)
        # A known BOS event exists at the prefix boundary; future bars cannot rewrite it.
        prefix_zones = zones(data[:25], "bos_origin")
        self.assertTrue(any(z.signal_index == 20 for z in prefix_zones))
        extended = data[:25] + [Bar(i, 100, 110, 90, 100, 1000) for i in range(25, 30)]
        full_zones = zones(extended, "bos_origin")
        self.assertEqual([z for z in full_zones if z.signal_index < 25], prefix_zones)

    def test_invalid_parameters_and_ohlc_are_rejected(self):
        data = [Bar(i, 100, 102, 98, 100, 10) for i in range(25)]
        zone = Zone(20, 19, "long", 99, 101, 2)
        with self.assertRaises(ValueError):
            first_retest(data, zone, deadline=12, reward_r=2)
        with self.assertRaises(ValueError):
            zones([Bar(1, 100, 99, 98, 100, 1)], "bos_origin")

    def test_incomplete_bar_is_allowed_only_at_series_tail(self):
        closed = Bar(0, 100, 102, 98, 100, 10)
        partial = Bar(1, 100, 102, 98, 100, 10, complete=False)
        self.assertEqual(zones([closed, partial], "bos_origin"), [])
        with self.assertRaises(ValueError):
            zones([Bar(0, 100, 102, 98, 100, 10, complete=False),
                   Bar(1, 100, 102, 98, 100, 10)], "bos_origin")

    def test_trade_simulation_prefers_stop_and_applies_signed_funding(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(50)]
        data[1] = Bar(1, 100, 103, 98, 100, 10)  # both barriers touch; stop wins
        zone = Zone(0, 0, "long", 99, 100, 1)
        setup = Setup(zone, 1, 100, 99, 102)
        trade = simulate_trade(data, setup, funding={}, max_holding_bars=48)
        self.assertEqual(trade.exit_reason, "stop")
        self.assertEqual(trade.exit_price, 99)

        quiet = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(50)]
        funded = simulate_trade(
            quiet, setup,
            funding={1: FundingEvent(1, 0.001, 100), 5: FundingEvent(5, 0.001, 100)},
        )
        self.assertEqual(funded.exit_reason, "time")
        self.assertEqual(funded.exit_index, 49)
        self.assertAlmostEqual(funded.funding_return, -0.001)
        self.assertAlmostEqual(funded.net_return, -0.0022)

    def test_net_return_subtracts_two_one_way_costs_arithmetically(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(50)]
        data[1] = Bar(1, 100, 102, 99.5, 101, 10)
        setup = Setup(Zone(0, 0, "long", 99, 100, 1), 1, 100, 98, 101)
        trade = simulate_trade(data, setup, funding={}, fee_bps_per_side=5,
                               slippage_bps_per_side=5)
        self.assertIsNotNone(trade)
        self.assertAlmostEqual(trade.gross_return, 0.01)
        self.assertAlmostEqual(trade.cost_bps, 20.0)
        self.assertAlmostEqual(trade.net_return, 0.008)

    def test_default_crypto_cost_is_12bps_and_funding_is_separate_cash_flow(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(50)]
        data[49] = Bar(49, 100.2, 100.5, 100, 100.2, 10)
        setup = Setup(Zone(0, 0, "long", 99, 100, 1), 1, 100, 98, 110)
        trade = simulate_trade(
            data, setup, funding={5: FundingEvent(5, 0.0002, 100)},
        )
        self.assertIsNotNone(trade)
        self.assertAlmostEqual(trade.gross_return, 0.002)
        self.assertAlmostEqual(trade.funding_return, -0.0002)
        self.assertAlmostEqual(trade.cost_bps, 12.0)
        self.assertAlmostEqual(trade.net_return, 0.0006)

    def test_missing_funding_mark_makes_only_held_trade_unscorable(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(50)]
        setup = Setup(Zone(0, 0, "long", 99, 100, 1), 1, 100, 98, 110)
        trade = simulate_trade(
            data, setup, funding={5: FundingEvent(5, 0.001, None)},
        )
        self.assertIsNotNone(trade)
        self.assertIsNone(trade.funding_return)
        self.assertIsNone(trade.net_return)

    def test_unavailable_next_open_time_exit_is_unscorable(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(48)]
        zone = Zone(0, 0, "long", 99, 100, 1)
        setup = Setup(zone, 0, 100, 98, 104)
        self.assertIsNone(simulate_trade(data, setup, funding={}))

    def test_active_zone_blocks_new_same_direction_signal_until_consumed(self):
        data = [Bar(i, 102, 103, 101.5, 102, 10) for i in range(10)]
        zone1 = Zone(1, 0, "long", 99, 100, 1)
        zone2 = Zone(5, 4, "long", 100, 101, 1)
        self.assertEqual(enforce_single_active_zone(data, [zone1, zone2], deadline=24), [zone1])

        data[3] = Bar(3, 102, 103, 99.5, 102, 10)  # first retest consumes zone1
        self.assertEqual(enforce_single_active_zone(data, [zone1, zone2], deadline=24),
                         [zone1, zone2])

    def test_unfinished_trade_is_not_misclassified_as_time_exit(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(20)]
        zone = Zone(0, 0, "long", 99, 100, 1)
        setup = Setup(zone, 0, 100, 98, 104)
        self.assertIsNone(simulate_trade(data, setup, funding={}))

    def test_setup_price_and_funding_timestamp_must_match_input_bars(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(50)]
        zone = Zone(0, 0, "long", 99, 100, 1)
        wrong_entry = Setup(zone, 1, 101, 98, 104)
        with self.assertRaises(ValueError):
            simulate_trade(data, wrong_entry, funding={})
        setup = Setup(zone, 1, 100, 98, 104)
        with self.assertRaises(ValueError):
            simulate_trade(data, setup, funding={5: FundingEvent(999, 0.001, 100)})

    def test_non_finite_funding_mark_is_rejected(self):
        data = [Bar(i, 100, 100.5, 99.5, 100, 10) for i in range(50)]
        setup = Setup(Zone(0, 0, "long", 99, 100, 1), 1, 100, 98, 104)
        with self.assertRaises(ValueError):
            simulate_trade(data, setup,
                           funding={5: FundingEvent(5, 0.001, float("inf"))})

    def test_non_finite_candles_are_rejected(self):
        with self.assertRaises(ValueError):
            zones([Bar(0, float("nan"), 101, 99, 100, 10)], "bos_origin")

    def test_orderblock_strategy_drops_signals_during_position_and_resumes_after_exit(self):
        data = [Bar(i, 101, 103, 100.5, 102, 10) for i in range(60)]
        data[2] = Bar(2, 100, 101, 99.5, 100.5, 10)  # first retest
        data[3] = Bar(3, 101, 103, 100.5, 102, 10)  # enter, then 48 bars held
        data[53] = Bar(53, 101, 102, 100.8, 101.8, 10)  # post-exit retest
        data[54] = Bar(54, 102, 105, 101, 104, 10)  # second target
        candidates = [
            Zone(1, 0, "long", 99, 100, 1),
            Zone(4, 3, "long", 100, 101, 1),  # signal while first trade is open
            Zone(52, 51, "long", 100.5, 101.5, 1),
        ]
        audit = {}
        with patch("crypto.zones", return_value=candidates):
            trades = simulate_orderblock(data, "bos_origin", "long", deadline=24,
                                         reward_r=1.5, funding={}, audit=audit)
        self.assertEqual(len(trades), 2)
        self.assertEqual([trade.setup.zone.signal_index for trade in trades], [1, 52])
        self.assertEqual(trades[0].exit_reason, "time")
        self.assertEqual(trades[0].exit_index, 51)
        self.assertEqual(trades[1].exit_reason, "target")
        self.assertEqual(audit["ignored_while_busy"], 1)


if __name__ == "__main__":
    unittest.main()
