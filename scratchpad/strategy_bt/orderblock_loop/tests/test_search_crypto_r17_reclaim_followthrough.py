import unittest
from types import SimpleNamespace
from unittest.mock import patch

from crypto import Bar, FundingEvent, Zone
import search_crypto_r17_reclaim_followthrough as r17


def bar(i, *, open_, high, low, close):
    return Bar(i * 3_600_000, open_, high, low, close, 1.0)


def long_setup_bars():
    return [
        bar(0, open_=98, high=99, low=97, close=98),
        bar(1, open_=98, high=100, low=98, close=99),
        bar(2, open_=99, high=102, low=98, close=101),
        bar(3, open_=101, high=103, low=100, close=102),
        bar(4, open_=102, high=103, low=101, close=102),
    ]


def mocked_trade(bars, setup, **_kwargs):
    return SimpleNamespace(setup=setup, exit_index=setup.entry_index,
                           exit_reason="target", net_return=0.01)


class SearchCryptoR17Tests(unittest.TestCase):
    def test_long_requires_break_and_enters_following_open(self):
        bars = long_setup_bars()
        zone = Zone(0, 0, "long", 95, 100, 5)
        with patch.object(r17, "simulate_trade", side_effect=mocked_trade) as sim:
            trades, audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(len(trades), 1)
        setup = sim.call_args.args[1]
        self.assertEqual((setup.entry_index, setup.entry_price), (3, 101))
        self.assertEqual(audit["followthrough_confirmed"], 1)

    def test_midpoint_reclaim_without_next_bar_break_consumes_zone(self):
        bars = long_setup_bars()
        bars[2] = bar(2, open_=99, high=101, low=98, close=100)
        zone = Zone(0, 0, "long", 95, 100, 5)
        with patch.object(r17, "simulate_trade", side_effect=mocked_trade) as sim:
            trades, audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(trades, [])
        sim.assert_not_called()
        self.assertEqual(audit["followthrough_failures"], 1)

    def test_short_confirmation_is_symmetric(self):
        bars = [
            bar(0, open_=102, high=103, low=101, close=102),
            bar(1, open_=102, high=103, low=100, close=101),
            bar(2, open_=101, high=102, low=98, close=99),
            bar(3, open_=99, high=100, low=97, close=98),
            bar(4, open_=98, high=99, low=97, close=98),
        ]
        zone = Zone(0, 0, "short", 100, 105, 5)
        with patch.object(r17, "simulate_trade", side_effect=mocked_trade) as sim:
            trades, _audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(len(trades), 1)
        setup = sim.call_args.args[1]
        self.assertEqual((setup.entry_index, setup.entry_price), (3, 99))
        self.assertEqual(setup.target, 95.75)

    def test_followthrough_distal_wick_invalidates(self):
        bars = long_setup_bars()
        bars[2] = bar(2, open_=99, high=103, low=94, close=102)
        zone = Zone(0, 0, "long", 95, 100, 5)
        with patch.object(r17, "simulate_trade", side_effect=mocked_trade) as sim:
            trades, audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(trades, [])
        sim.assert_not_called()
        self.assertEqual(audit["followthrough_invalidated"], 1)

    def test_valid_followthrough_without_entry_is_censored(self):
        bars = long_setup_bars()[:3]
        zone = Zone(0, 0, "long", 95, 100, 5)
        trades, audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(trades, [])
        self.assertEqual(audit["right_censored_setups"], 1)

    def test_failed_followthrough_is_counted_even_without_later_entry_bar(self):
        bars = long_setup_bars()[:3]
        bars[2] = bar(2, open_=99, high=101, low=98, close=100)
        zone = Zone(0, 0, "long", 95, 100, 5)
        trades, audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(trades, [])
        self.assertEqual(audit["followthrough_failures"], 1)
        self.assertEqual(audit["right_censored_setups"], 0)

    def test_gap_between_touch_and_followthrough_is_not_bridged(self):
        bars = [
            bar(0, open_=98, high=99, low=97, close=98),
            bar(1, open_=98, high=100, low=98, close=99),
            bar(3, open_=99, high=102, low=98, close=101),
            bar(4, open_=101, high=103, low=100, close=102),
        ]
        segments, _gaps = r17.r14._segments(bars, 3_600_000)
        zone = Zone(0, 0, "long", 95, 100, 5)
        outcomes = []
        with patch.object(r17, "simulate_trade", side_effect=mocked_trade) as sim:
            for index, segment in enumerate(segments):
                outcomes.append(r17._simulate_segment(
                    segment, {}, {0: zone} if index == 0 else {}
                ))
        self.assertEqual(outcomes[0][0], [])
        self.assertEqual(outcomes[0][1]["right_censored_setups"], 1)
        sim.assert_not_called()

    def test_future_bars_do_not_change_entry_setup(self):
        bars_a = long_setup_bars()
        bars_b = list(bars_a)
        bars_b[4] = bar(4, open_=1, high=10_000, low=0.1, close=9_000)
        zone = Zone(0, 0, "long", 95, 100, 5)
        observed = []

        def capture(_bars, setup, **_kwargs):
            observed.append((setup.entry_index, setup.entry_price, setup.stop, setup.target))
            return mocked_trade(_bars, setup)

        with patch.object(r17, "simulate_trade", side_effect=capture):
            r17._simulate_segment(bars_a, {}, {0: zone})
            r17._simulate_segment(bars_b, {}, {0: zone})
        self.assertEqual(observed[0], observed[1])

    def test_entry_gap_past_zone_is_rejected(self):
        bars = long_setup_bars()
        bars[3] = bar(3, open_=94, high=96, low=93, close=95)
        zone = Zone(0, 0, "long", 95, 100, 5)
        with patch.object(r17, "simulate_trade", side_effect=mocked_trade) as sim:
            trades, audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(trades, [])
        sim.assert_not_called()
        self.assertEqual(audit["invalid_setups"], 1)

    def test_same_bar_stop_and_target_touch_is_stop_first(self):
        bars = long_setup_bars()
        bars[4] = bar(4, open_=102, high=105, low=94, close=101)
        zone = Zone(0, 0, "long", 95, 100, 5)
        trades, _audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].exit_reason, "stop")

    def test_actual_trade_path_applies_registered_costs_and_funding(self):
        bars = long_setup_bars()
        bars[4] = bar(4, open_=102, high=105, low=100, close=104)
        zone = Zone(0, 0, "long", 95, 100, 5)
        trades, audit = r17._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(len(trades), 1)
        self.assertAlmostEqual(trades[0].cost_bps, 12.0)
        self.assertLess(trades[0].net_return, trades[0].gross_return)
        funding = {4 * 3_600_000: FundingEvent(4 * 3_600_000, 0.001, 100)}
        trades_with_funding, audit_with_funding = r17._simulate_segment(
            bars, funding, {0: zone}
        )
        self.assertEqual(len(trades_with_funding), 1)
        self.assertEqual(audit_with_funding["funding_unscorable_trades"], 0)
        self.assertEqual(trades_with_funding[0].ambiguous_funding_events, 1)
        self.assertLess(trades_with_funding[0].net_return, trades[0].net_return)

    def test_preregistered_symbol_gate_is_32_not_r14_default(self):
        self.assertEqual(r17._apply_symbol_gate({"symbols": 31, "status": "completed"})["status"],
                         "unscorable")
        self.assertEqual(r17._apply_symbol_gate({"symbols": 32, "status": "completed"})["status"],
                         "completed")


if __name__ == "__main__":
    unittest.main()
