from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import search_crypto_r12_btc_daily_alignment as r12
from crypto import Bar, Zone


DAY = 86_400_000
FOUR_HOURS = 14_400_000


def daily_bars(count: int, *, upward: bool = True) -> list[Bar]:
    bars = []
    for day in range(count):
        close = 100.0 + day if upward else 300.0 - day
        for slot in range(6):
            timestamp = day * DAY + slot * FOUR_HOURS
            bars.append(Bar(timestamp, close, close + 1, close - 1, close, 10.0))
    return bars


class BtcDailyAlignmentTests(unittest.TestCase):
    def test_upward_and_downward_daily_regimes_require_full_warmup(self):
        rising = r12.build_daily_regimes(daily_bars(140))
        falling = r12.build_daily_regimes(daily_bars(140, upward=False))
        self.assertEqual(rising[140 * DAY], "long")
        self.assertEqual(falling[140 * DAY], "short")
        self.assertNotIn(119 * DAY, rising)

    def test_flat_daily_series_has_no_direction_bias(self):
        bars = [Bar(b.timestamp, 100, 101, 99, 100, b.volume) for b in daily_bars(140)]
        regimes = r12.build_daily_regimes(bars)
        self.assertIsNone(regimes[140 * DAY])

    def test_missing_bar_resets_ema_and_requires_a_new_full_segment(self):
        bars = daily_bars(245)
        missing_day = 122
        bars = [b for b in bars if b.timestamp // DAY != missing_day]
        regimes = r12.build_daily_regimes(bars)
        self.assertIn(122 * DAY, regimes)
        self.assertNotIn(123 * DAY, regimes)
        self.assertNotIn(242 * DAY, regimes)
        self.assertIn(243 * DAY, regimes)

    def test_entry_uses_only_a_daily_close_strictly_before_entry(self):
        regimes = {100: "long", 200: "short"}
        self.assertIsNone(r12.regime_before(100, regimes))
        self.assertEqual(r12.regime_before(101, regimes), "long")
        self.assertEqual(r12.regime_before(200, regimes), "long")
        self.assertEqual(r12.regime_before(201, regimes), "short")

    def test_future_bar_mutation_does_not_change_past_regime(self):
        bars = daily_bars(150)
        cutoff = 140 * DAY
        before = r12.build_daily_regimes(bars)
        changed = [
            Bar(b.timestamp, b.open, b.high, b.low, b.close, b.volume)
            if b.timestamp < cutoff else
            Bar(b.timestamp, 1, 3, 0.5, 1, b.volume)
            for b in bars
        ]
        after = r12.build_daily_regimes(changed)
        self.assertEqual(
            {ts: bias for ts, bias in before.items() if ts < cutoff},
            {ts: bias for ts, bias in after.items() if ts < cutoff},
        )

    def test_zone_is_kept_only_when_first_entry_bias_matches_direction(self):
        bars = [
            Bar(0, 100, 101, 99, 100, 1),
            Bar(FOUR_HOURS, 100, 102, 100, 101, 1),
            Bar(2 * FOUR_HOURS, 100, 103, 100, 102, 1),
        ]
        zone = Zone(0, 0, "long", 99, 101, 1)
        zone_builder = lambda _bars, _definition: [zone]
        with patch.object(r12.r4, "r4_zones", side_effect=zone_builder):
            kept = r12._filtered_zones(
                bars, "displacement", {2 * FOUR_HOURS - 1: "long"}, zone_builder,
            )
            rejected = r12._filtered_zones(
                bars, "displacement", {2 * FOUR_HOURS - 1: "short"}, zone_builder,
            )
            unknown = r12._filtered_zones(bars, "displacement", {}, zone_builder)
        self.assertEqual(kept, [zone])
        self.assertEqual(rejected, [])
        self.assertEqual(unknown, [])

    def test_installed_filter_calls_original_zone_builder_without_recursion(self):
        bars = [
            Bar(0, 100, 101, 99, 100, 1),
            Bar(FOUR_HOURS, 100, 102, 100, 101, 1),
            Bar(2 * FOUR_HOURS, 100, 103, 100, 102, 1),
        ]
        zone = Zone(0, 0, "long", 99, 101, 1)
        calls = []

        def original_builder(_bars, definition):
            calls.append(definition)
            return [zone]

        with patch.object(r12.r4, "r4_zones", side_effect=original_builder):
            original = r12._install_regime_filter({2 * FOUR_HOURS - 1: "long"})
            try:
                result = r12.r4.r4_zones(bars, "displacement")
            finally:
                r12.r4.r4_zones = original
        self.assertEqual(result, [zone])
        self.assertEqual(calls, ["displacement"])

    def test_fixed_final_round_grid_has_six_unique_configs(self):
        self.assertEqual(len(r12.CONFIGS), 6)
        self.assertEqual(len({str(sorted(c.items())) for c in r12.CONFIGS}), 6)
        self.assertTrue(all(c["timeframe"] == "4h" for c in r12.CONFIGS))
        self.assertTrue(all(c["deadline"] == 24 and c["reward_r"] == 1.5 for c in r12.CONFIGS))


if __name__ == "__main__":
    unittest.main()
