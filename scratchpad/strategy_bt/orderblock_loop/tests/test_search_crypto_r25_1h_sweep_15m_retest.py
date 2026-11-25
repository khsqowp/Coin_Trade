from __future__ import annotations

import unittest
from unittest.mock import patch

import search_crypto_r14 as r14
import search_crypto_r25_1h_sweep_15m_retest as r25
from crypto import Bar, FundingEvent, Zone


class R25PreBosSweepTests(unittest.TestCase):
    def test_sweep_is_strict_and_directional(self):
        bars = [Bar(i * r25.BAR_1H_MS, 100, 101, 99, 100, 1)
                for i in range(25)]
        bars.append(Bar(25 * r25.BAR_1H_MS, 100, 101, 98.9, 100.1, 1))
        self.assertTrue(r25._external_sweep(bars, 25, "long"))
        self.assertFalse(r25._external_sweep(bars, 25, "short"))
        equal_level = list(bars)
        equal_level[25] = Bar(25 * r25.BAR_1H_MS, 100, 101, 99, 100.1, 1)
        self.assertFalse(r25._external_sweep(equal_level, 25, "long"))

    def test_sweep_must_precede_bos_by_one_to_three_bars(self):
        bars = [Bar(i * r25.BAR_1H_MS, 100, 101, 99, 100, 1)
                for i in range(31)]
        bars[25] = Bar(25 * r25.BAR_1H_MS, 100, 101, 98.9, 100.1, 1)
        self.assertTrue(r25._pre_bos_sweep(bars, 26, "long"))
        self.assertTrue(r25._pre_bos_sweep(bars, 28, "long"))
        self.assertFalse(r25._pre_bos_sweep(bars, 29, "long"))

    def test_future_mutation_cannot_change_pre_bos_sweep_label(self):
        bars = [Bar(i * r25.BAR_1H_MS, 100, 101, 99, 100, 1)
                for i in range(34)]
        bars[25] = Bar(25 * r25.BAR_1H_MS, 100, 101, 98.9, 100.1, 1)
        baseline = r25._pre_bos_sweep(bars, 28, "long")
        changed = list(bars)
        for i in range(28, len(changed)):
            old = changed[i]
            changed[i] = Bar(old.timestamp, old.open, old.high + 100,
                             old.low - 100, old.close, old.volume)
        self.assertEqual(r25._pre_bos_sweep(changed, 28, "long"), baseline)

    def test_bos_candle_itself_cannot_supply_its_own_sweep(self):
        bars = [Bar(i * r25.BAR_1H_MS, 100, 101, 99, 100, 1)
                for i in range(30)]
        bars[28] = Bar(28 * r25.BAR_1H_MS, 100, 101, 98.9, 100.1, 1)
        self.assertFalse(r25._pre_bos_sweep(bars, 28, "long"))

    def test_cutoff_gate_rejects_bar_that_closes_after_freeze(self):
        cutoff = 100 * r25.BAR_1H_MS
        allowed = [("BTCUSDT", [Bar(cutoff - r25.BAR_15M_MS, 100, 101,
                                     99, 100, 1)], {}, 0)]
        rejected = [("BTCUSDT", [Bar(cutoff, 100, 101, 99, 100, 1)], {}, 0)]
        r25._validate_cutoff(allowed, r25.BAR_15M_MS, cutoff)
        with self.assertRaisesRegex(ValueError, "post-cutoff"):
            r25._validate_cutoff(rejected, r25.BAR_15M_MS, cutoff)

    def test_symbol_gate_uses_intersection_and_exact_30_boundary(self):
        rows_15m = [(f"S{i}", [object()], {}, 0) for i in range(30)]
        rows_1h = [(f"S{i}", [object()], {}, 0) for i in range(29)]
        self.assertEqual(len(r25._usable_symbols(rows_15m, rows_1h)), 29)
        rows_1h.append(("S29", [object()], {}, 0))
        self.assertEqual(len(r25._usable_symbols(rows_15m, rows_1h)), 30)
        self.assertEqual(r25._unscorable_result(29)["status"], "unscorable")
        self.assertEqual(r25._unscorable_result(29)["symbols"], 29)

    def test_fixed_universe_loader_fills_missing_symbols_as_empty(self):
        expected = frozenset({"A", "B", "C"})
        rows = [("A", [Bar(0, 100, 101, 99, 100, 1)], {})]
        loaded = r25._load_fixed_universe(
            lambda **_kwargs: iter(rows), "15m", expected)
        self.assertEqual([row[0] for row in loaded], ["A", "B", "C"])
        self.assertEqual(loaded[1][1], [])
        self.assertEqual(loaded[2][1], [])

    def test_one_hour_loader_rejects_fifteen_minute_phase_offset(self):
        rows = [("A", [Bar(r25.BAR_15M_MS, 100, 101, 99, 100, 1)], {})]
        with self.assertRaisesRegex(ValueError, "non-UTC bar boundary"):
            r25._load_fixed_universe(
                lambda **_kwargs: iter(rows), "1h", frozenset({"A"}))

    def test_clock_context_restores_r14_globals_after_exception(self):
        before = (r14.DURATION_MS, r14.ZONE_DURATION_MS, r14.DEADLINE,
                  r14.MAX_HOLDING_BARS, r14.REWARD_R, r14.STOP_BUFFER_ATR)
        with self.assertRaisesRegex(RuntimeError, "synthetic"):
            with r25._r14_15m_1h_clock():
                self.assertEqual(r14.DURATION_MS, r25.BAR_15M_MS)
                self.assertEqual(r14.ZONE_DURATION_MS, r25.BAR_1H_MS)
                raise RuntimeError("synthetic")
        after = (r14.DURATION_MS, r14.ZONE_DURATION_MS, r14.DEADLINE,
                 r14.MAX_HOLDING_BARS, r14.REWARD_R, r14.STOP_BUFFER_ATR)
        self.assertEqual(after, before)

    def test_end_to_end_filtered_zone_maps_confirms_and_hits_real_target(self):
        hour = r25.BAR_1H_MS
        fifteen = r25.BAR_15M_MS
        bars_1h = [Bar(i * hour, 100, 101, 99, 100.5, 1000)
                   for i in range(42)]
        bars_1h[25] = Bar(25 * hour, 100, 101, 98.9, 100.1, 1000)
        bars_15m = [Bar(i * fifteen, 100, 101, 99, 100.5, 1000)
                    for i in range(len(bars_1h) * 4)]
        bars_15m[117] = Bar(117 * fifteen, 99, 99.2, 98.2, 98.8, 1000)
        bars_15m[118] = Bar(118 * fifteen, 98.9, 99.2, 98.5, 99.0, 1000)
        bars_15m[119] = Bar(119 * fifteen, 99.0, 100, 98.5, 99.8, 1000)
        accepted = Zone(28, 24, "long", 98, 99, 1.0)
        rejected = Zone(33, 30, "long", 98, 99, 1.0)
        original_simulate = r14.simulate_trade
        observed = []

        def capture(*args, **kwargs):
            trade = original_simulate(*args, **kwargs)
            observed.append((args[1], trade))
            return trade

        with patch.object(r14, "_expected_symbols", return_value=frozenset({"BTCUSDT"})), \
                patch.object(r14, "r4_zones", return_value=[accepted, rejected]), \
                patch.object(r14, "simulate_trade", side_effect=capture):
            result = r25._trial_with_pre_bos_sweep(
                [("BTCUSDT", bars_15m, {}, 0)],
                [("BTCUSDT", bars_1h, {}, 0)])

        self.assertEqual(result["raw_bos_zones"], 2)
        self.assertEqual(result["pre_bos_sweep_zones"], 1)
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["m2_target_hits"], 1)
        self.assertEqual(len(observed), 1)
        setup, trade = observed[0]
        self.assertEqual(setup.zone.signal_index, 116)
        self.assertEqual(setup.entry_index, 118)
        self.assertAlmostEqual(setup.target, 99.4)
        self.assertEqual(trade.exit_reason, "target")
        self.assertEqual(trade.exit_index, 119)
        self.assertAlmostEqual(trade.cost_bps, 12)

    def test_missing_activation_timestamp_is_counted_as_unaligned(self):
        fifteen_minutes = [0, 1, 2, 3, 5, 6, 7]
        bars_15m = [Bar(i * r25.BAR_15M_MS, 100, 101, 99, 100.5, 1)
                    for i in fifteen_minutes]
        bars_1h = [Bar(i * r25.BAR_1H_MS, 100, 101, 99, 100.5, 1)
                   for i in range(3)]
        zone = Zone(0, 0, "long", 98, 99, 1.0)
        with r25._r14_15m_1h_clock(), \
                patch.object(r14, "r4_zones", return_value=[zone]):
            segments_15m, _ = r14._segments(bars_15m, r25.BAR_15M_MS)
            segments_1h, _ = r14._segments(bars_1h, r25.BAR_1H_MS)
            mapped, unaligned = r14._zones_on_confirmation_segments(
                segments_15m, segments_1h)
        self.assertEqual(unaligned, 1)
        self.assertTrue(all(not mapping for mapping in mapped))

    def test_real_15m_engine_stop_priority_and_adverse_funding(self):
        bars = [Bar(i * r25.BAR_15M_MS, 100, 101, 99, 100.5, 1000)
                for i in range(8)]
        bars[1] = Bar(r25.BAR_15M_MS, 99, 99.2, 98.2, 98.8, 1000)
        bars[2] = Bar(2 * r25.BAR_15M_MS, 98.9, 100, 97, 99, 1000)
        zone = Zone(0, 0, "long", 98, 99, 1.0)
        funding = {bars[2].timestamp: FundingEvent(
            bars[2].timestamp, 0.001, 98.9)}
        with r25._r14_15m_1h_clock():
            trades, audit = r14._simulate_segment(bars, funding, {0: zone})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].exit_reason, "stop")
        self.assertEqual(trades[0].exit_price, 97.9)
        self.assertLess(trades[0].funding_return, 0)
        self.assertAlmostEqual(trades[0].cost_bps, 12)
        self.assertEqual(audit["funding_unscorable_trades"], 0)

    def test_real_15m_engine_counts_expiry_and_invalidation(self):
        zone = Zone(0, 0, "long", 98, 99, 1.0)
        no_touch = [Bar(i * r25.BAR_15M_MS, 100, 101, 100, 100.5, 1)
                    for i in range(27)]
        invalidated = [Bar(i * r25.BAR_15M_MS, 100, 101, 99, 100.5, 1)
                       for i in range(3)]
        invalidated[1] = Bar(r25.BAR_15M_MS, 99, 100, 97.9, 98.5, 1)
        with r25._r14_15m_1h_clock():
            _trades, expiry_audit = r14._simulate_segment(no_touch, {}, {0: zone})
            _trades, invalidation_audit = r14._simulate_segment(
                invalidated, {}, {0: zone})
        self.assertEqual(expiry_audit["expired_zones"], 1)
        self.assertEqual(invalidation_audit["invalidated_zones"], 1)


if __name__ == "__main__":
    unittest.main()
