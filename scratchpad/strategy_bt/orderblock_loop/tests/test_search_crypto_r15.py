import unittest
from unittest.mock import patch

from crypto import Bar, Zone
import search_crypto_r15 as r15


def trend_bars(count, *, rising=True, start=0):
    values = [100.0 + i if rising else 500.0 - i for i in range(count)]
    return [Bar((start + i) * r15.r14.ZONE_DURATION_MS,
                close, close + 1, close - 1, close, 1.0)
            for i, close in enumerate(values)]


class SearchCryptoR15Tests(unittest.TestCase):
    def test_ema_warmup_and_aligned_directions(self):
        warmup = r15._ema_regimes(trend_bars(r15.EMA_SLOW - 1))
        self.assertTrue(all(state is None for state in warmup))
        rising = r15._ema_regimes(trend_bars(r15.EMA_SLOW + 10))
        falling = r15._ema_regimes(trend_bars(r15.EMA_SLOW + 10, rising=False))
        self.assertEqual(rising[r15.EMA_SLOW - 1], "long")
        self.assertEqual(falling[r15.EMA_SLOW - 1], "short")

    def test_flat_prices_have_no_directional_ema_state(self):
        bars = [Bar(i * r15.r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1.0)
                for i in range(r15.EMA_SLOW + 5)]
        self.assertTrue(all(state is None for state in r15._ema_regimes(bars)))

    def test_future_mutation_does_not_change_prior_filter_state(self):
        bars = trend_bars(r15.EMA_SLOW + 20)
        prefix_end = r15.EMA_SLOW + 5
        before = r15._ema_regimes(bars[:prefix_end])
        altered = list(bars)
        for i in range(prefix_end, len(altered)):
            altered[i] = Bar(altered[i].timestamp, 1, 10_000, 0.1, 9_000, 1.0)
        after = r15._ema_regimes(altered)
        self.assertTrue(any(state == "long" for state in before))
        self.assertEqual(before, after[:prefix_end])

    def test_zone_filter_keeps_only_signal_timeframe_alignment(self):
        bars = trend_bars(r15.EMA_SLOW + 2)
        candidates = [
            Zone(199, 10, "long", 100, 101, 2.0),
            Zone(200, 10, "short", 100, 101, 2.0),
            Zone(10, 5, "long", 100, 101, 2.0),
        ]
        stats = {"raw": 0, "kept": 0, "no_regime": 0, "misaligned": 0}
        with patch.object(r15.r14, "r4_zones", return_value=candidates):
            _original, build = r15._filtered_zone_builder(stats)
            kept = build(bars, "bos_origin")
        self.assertEqual([zone.signal_index for zone in kept], [199])
        self.assertEqual(stats, {"raw": 3, "kept": 1, "no_regime": 1, "misaligned": 1})

    def test_filter_builds_regime_from_each_contiguous_segment_only(self):
        first = trend_bars(r15.EMA_SLOW, rising=True, start=0)
        second = trend_bars(r15.EMA_SLOW, rising=False, start=500)
        self.assertEqual(r15._ema_regimes(first)[-1], "long")
        self.assertEqual(r15._ema_regimes(second)[-1], "short")

    def test_actual_gap_split_restarts_ema_warmup_at_199_200_boundary(self):
        first = trend_bars(r15.EMA_SLOW, rising=True, start=0)
        second = trend_bars(r15.EMA_SLOW, rising=False, start=500)
        segments, _missing = r15.r14._segments(
            first + second, r15.r14.ZONE_DURATION_MS
        )
        self.assertEqual(len(segments), 2)
        first_states = r15._ema_regimes(segments[0])
        second_states = r15._ema_regimes(segments[1])
        self.assertEqual(first_states[198], None)
        self.assertEqual(first_states[199], "long")
        self.assertEqual(second_states[198], None)
        self.assertEqual(second_states[199], "short")

    def test_zone_filter_result_is_prefix_invariant_after_signal(self):
        bars = trend_bars(r15.EMA_SLOW + 10)
        signal = r15.EMA_SLOW + 2
        candidate = Zone(signal, 10, "long", 100, 101, 2.0)
        stats = {"raw": 0, "kept": 0, "no_regime": 0, "misaligned": 0}
        with patch.object(r15.r14, "r4_zones", return_value=[candidate]):
            _original, build = r15._filtered_zone_builder(stats)
            before = build(bars, "bos_origin")
            altered = list(bars)
            for i in range(signal + 1, len(altered)):
                altered[i] = Bar(altered[i].timestamp, 1, 10_000, 0.1, 9_000, 1.0)
            after = build(altered, "bos_origin")
        self.assertEqual([z.signal_index for z in before], [signal])
        self.assertEqual([z.signal_index for z in after], [signal])

    def test_r15_filter_and_4h_to_1h_alignment_integrate(self):
        four_hour = trend_bars(r15.EMA_SLOW + 1)
        one_hour = [Bar((r15.EMA_SLOW * 4 + i) * r15.r14.DURATION_MS,
                        100, 101, 99, 100, 1.0) for i in range(8)]
        candidate = Zone(r15.EMA_SLOW - 1, 20, "long", 99, 101, 2.0)
        stats = {"raw": 0, "kept": 0, "no_regime": 0, "misaligned": 0}
        with patch.object(r15.r14, "r4_zones", return_value=[candidate]):
            _original, build = r15._filtered_zone_builder(stats)
        with patch.object(r15.r14, "r4_zones", side_effect=build):
            mapped, unaligned = r15.r14._zones_on_confirmation_segments([one_hour], [four_hour])
        self.assertEqual(unaligned, 0)
        self.assertEqual(list(mapped[0]), [0])
        self.assertEqual(stats["kept"], 1)


if __name__ == "__main__":
    unittest.main()
