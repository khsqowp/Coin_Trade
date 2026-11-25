from __future__ import annotations

import unittest
from unittest.mock import patch

from crypto import Bar, FundingEvent, Setup, Zone, simulate_trade
import search_crypto_r24_bos_impulse_target as r24


def hourly_bars(count=12):
    return [Bar(i * r24.HOUR_MS, 100, 101, 99, 100, 1000)
            for i in range(count)]


class R24BosImpulseTargetTests(unittest.TestCase):
    def test_long_target_is_highest_of_exact_four_completed_pre_activation_bars(self):
        bars = hourly_bars()
        bars[1] = Bar(bars[1].timestamp, 100, 103, 99, 100, 1000)
        bars[2] = Bar(bars[2].timestamp, 100, 102, 99, 100, 1000)
        zone = Zone(4, 1, "long", 98, 99, 1)
        self.assertEqual(r24._structure_target(bars, zone, 100), (103, None))

    def test_short_target_is_lowest_of_exact_four_completed_pre_activation_bars(self):
        bars = hourly_bars()
        bars[3] = Bar(bars[3].timestamp, 100, 101, 97, 100, 1000)
        zone = Zone(4, 1, "short", 101, 102, 1)
        self.assertEqual(r24._structure_target(bars, zone, 98), (97, None))

    def test_missing_or_nonconsecutive_pre_activation_bars_are_rejected(self):
        zone = Zone(3, 1, "long", 98, 99, 1)
        self.assertEqual(r24._structure_target(hourly_bars(), zone, 100),
                         (None, "structure_target_unavailable"))
        bars = hourly_bars()
        bars[2] = Bar(bars[2].timestamp + 1, 100, 101, 99, 100, 1000)
        self.assertEqual(r24._structure_target(
            bars, Zone(4, 1, "long", 98, 99, 1), 100),
            (None, "structure_target_unavailable"))

    def test_target_must_be_strictly_ahead_of_entry(self):
        bars = hourly_bars()
        zone = Zone(4, 1, "long", 98, 99, 1)
        self.assertEqual(r24._structure_target(bars, zone, 101),
                         (None, "structure_target_not_ahead"))
        short_zone = Zone(4, 1, "short", 101, 102, 1)
        self.assertEqual(r24._structure_target(bars, short_zone, 99),
                         (None, "structure_target_not_ahead"))

    def test_future_bars_cannot_change_structural_target(self):
        bars = hourly_bars()
        bars[2] = Bar(bars[2].timestamp, 100, 104, 99, 100, 1000)
        zone = Zone(4, 1, "long", 98, 99, 1)
        baseline = r24._structure_target(bars, zone, 100)
        changed = list(bars)
        for index in range(4, len(changed)):
            old = changed[index]
            changed[index] = Bar(old.timestamp, old.open, old.high + 100,
                                 old.low - 100, old.close * 2, old.volume)
        self.assertEqual(r24._structure_target(changed, zone, 100), baseline)

    def test_setup_replaces_fixed_r_target_and_counts_wrong_side(self):
        bars = hourly_bars()
        bars[1] = Bar(bars[1].timestamp, 100, 103, 99, 100, 1000)
        zone = Zone(4, 1, "long", 98, 99, 1)
        base = lambda *_: (Setup(zone, 6, 100, 98, 101), "setup")
        stats = {"structure_target_unavailable": 0, "structure_target_not_ahead": 0}
        result, reason = r24._make_setup_with_structure_target(
            base, bars, zone, bars[5], bars[6], 5, stats, [])
        self.assertEqual(reason, "setup")
        self.assertEqual(result.target, 103)

        base_bad = lambda *_: (Setup(zone, 6, 104, 98, 106), "setup")
        result, reason = r24._make_setup_with_structure_target(
            base_bad, bars, zone, bars[5], bars[6], 5, stats, [])
        self.assertIsNone(result)
        self.assertEqual(reason, "structure_target_not_ahead")
        self.assertEqual(stats["structure_target_not_ahead"], 1)

    def test_target_capped_entry_cancel_is_not_a_trade(self):
        bars = hourly_bars()
        zone = Zone(4, 1, "long", 98, 99, 1)
        base = lambda *_: (Setup(zone, 6, 104, 98, 105), "setup")
        stats = {"structure_target_unavailable": 0,
                 "structure_target_not_ahead": 0}
        result, reason = r24._make_setup_with_structure_target(
            base, bars, zone, bars[5], bars[6], 5, stats, [])
        self.assertIsNone(result)
        self.assertEqual(reason, "structure_target_not_ahead")
        self.assertEqual(stats["structure_target_not_ahead"], 1)

    def test_structural_target_reaches_real_simulator_stop_first_cost_and_funding(self):
        bars = hourly_bars()
        bars[1] = Bar(bars[1].timestamp, 100, 103, 99, 100, 1000)
        bars[6] = Bar(bars[6].timestamp, 100, 104, 97, 100, 1000)
        zone = Zone(4, 1, "long", 98, 99, 1)
        base = lambda *_: (Setup(zone, 6, bars[6].open, 98, 101), "setup")
        stats = {"structure_target_unavailable": 0,
                 "structure_target_not_ahead": 0}
        setup, reason = r24._make_setup_with_structure_target(
            base, bars, zone, bars[5], bars[6], 5, stats, [])
        self.assertEqual(reason, "setup")
        self.assertEqual(setup.target, 103)
        trade = simulate_trade(
            bars, setup,
            funding={bars[6].timestamp: FundingEvent(
                bars[6].timestamp, 0.001, 100)},
            max_holding_bars=24, fee_bps_per_side=4,
            slippage_bps_per_side=2, bar_duration_ms=r24.HOUR_MS,
            funding_order_policy="adverse_only")
        self.assertEqual(trade.exit_reason, "stop")
        self.assertEqual(trade.exit_price, 98)
        self.assertAlmostEqual(trade.cost_bps, 12)
        self.assertAlmostEqual(trade.funding_return, -0.001)

    def test_r21_filter_reaches_r14_mapper_and_anchor_is_confirmed_bos_candle(self):
        four_hour = [Bar(i * r24.r21.BAR_MS, 100, 101, 99, 100.5, 1000)
                     for i in range(48)]
        sweep = four_hour[25]
        four_hour[25] = Bar(sweep.timestamp, 100, 101, 98.9, 100.1, 1000)
        hourly = hourly_bars(48 * 4)
        # BOS candle 28 maps to activation at 1h index 116; its four bars are 112..115.
        anchor_bar = hourly[114]
        hourly[114] = Bar(anchor_bar.timestamp, 100, 150, 99, 100, 1000)
        zones = [Zone(28, 24, "long", 98, 99, 1),
                 Zone(40, 36, "long", 98, 99, 1)]

        def use_real_mapper(_barsets_1h, _barsets_4h):
            mapped, unaligned = r24.r14._zones_on_confirmation_segments(
                [hourly], [four_hour])
            zone = mapped[0][116]
            return {"mapped": list(mapped[0]), "unaligned": unaligned,
                    "target": r24._structure_target(hourly, zone, 110)}

        stats = {"structure_target_unavailable": 0,
                 "structure_target_not_ahead": 0}
        target_r_values = []
        with patch.object(r24.r14, "r4_zones", return_value=zones), \
                patch.object(r24.r14, "_trial", side_effect=use_real_mapper):
            result = r24._trial_with_structure_target(
                [], [], stats, target_r_values)
        self.assertEqual(result["mapped"], [116])
        self.assertEqual(result["unaligned"], 0)
        self.assertEqual(result["target"], (150, None))
        self.assertEqual(r24.r14.r4_zones, r24.r21.r4_zones)


if __name__ == "__main__":
    unittest.main()
