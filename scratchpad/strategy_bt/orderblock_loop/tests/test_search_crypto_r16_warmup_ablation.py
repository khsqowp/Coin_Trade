import unittest
from unittest.mock import patch

from crypto import Bar, Zone
import search_crypto_r14 as r14
import search_crypto_r15 as r15
import search_crypto_r16_warmup_ablation as r16


def bars(count, *, rising=True, start=0):
    closes = [100.0 + i if rising else 500.0 - i for i in range(count)]
    return [Bar((start + i) * r14.ZONE_DURATION_MS,
                close, close + 1, close - 1, close, 1.0)
            for i, close in enumerate(closes)]


class SearchCryptoR16Tests(unittest.TestCase):
    def test_warmup_only_keeps_both_directions_after_ema_is_computable(self):
        segment = bars(r16.r15.EMA_SLOW + 1)
        candidates = [
            Zone(198, 10, "long", 100, 101, 2.0),
            Zone(199, 10, "long", 100, 101, 2.0),
            Zone(200, 10, "short", 100, 101, 2.0),
        ]
        stats = {"raw": 0, "kept": 0, "warmup_excluded": 0}
        with patch.object(r14, "r4_zones", return_value=candidates):
            _original, build = r16._warmup_only_zone_builder(stats)
            kept = build(segment, "bos_origin")
        self.assertEqual([zone.signal_index for zone in kept], [199, 200])
        self.assertEqual([zone.direction for zone in kept], ["long", "short"])
        self.assertEqual(stats, {"raw": 3, "kept": 2, "warmup_excluded": 1})

    def test_gap_restarts_ema_availability(self):
        first = bars(r16.r15.EMA_SLOW, rising=True)
        second = bars(r16.r15.EMA_SLOW, rising=False, start=500)
        segments, _missing = r14._segments(first + second, r14.ZONE_DURATION_MS)
        self.assertEqual(len(segments), 2)
        self.assertIsNone(r15._ema_regimes(segments[1])[r16.r15.EMA_SLOW - 2])
        self.assertEqual(r15._ema_regimes(segments[1])[r16.r15.EMA_SLOW - 1], "short")

    def test_filter_is_prefix_invariant_at_zone_signal(self):
        segment = bars(r16.r15.EMA_SLOW + 10)
        signal = r16.r15.EMA_SLOW + 2
        candidate = Zone(signal, 10, "long", 100, 101, 2.0)
        stats = {"raw": 0, "kept": 0, "warmup_excluded": 0}
        with patch.object(r14, "r4_zones", return_value=[candidate]):
            _original, build = r16._warmup_only_zone_builder(stats)
            before = build(segment, "bos_origin")
            altered = list(segment)
            for i in range(signal + 1, len(altered)):
                altered[i] = Bar(altered[i].timestamp, 1, 10_000, 0.1, 9_000, 1.0)
            after = build(altered, "bos_origin")
        self.assertEqual([zone.signal_index for zone in before], [signal])
        self.assertEqual([zone.signal_index for zone in after], [signal])


if __name__ == "__main__":
    unittest.main()
