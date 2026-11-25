from __future__ import annotations

import unittest
from unittest.mock import patch

from crypto import Bar, Zone
import search_crypto_r21_pre_bos_sweep as r21


class R21ZoneMappingIntegrationTests(unittest.TestCase):
    def test_filtered_builder_reaches_r14_real_zone_mapping_callsite(self):
        four_hour = [Bar(i * r21.BAR_MS, 100, 101, 99, 100.5, 1000)
                     for i in range(48)]
        row = four_hour[25]
        four_hour[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
        hourly = [Bar(i * r21.r14.DURATION_MS, 100, 101, 99, 100.5, 1000)
                  for i in range(48 * 4)]
        zones = [Zone(28, 24, "long", 99, 100, 1),
                 Zone(40, 36, "long", 99, 100, 1)]

        def invoke_actual_mapping(_barsets_1h, _barsets_4h):
            return r21.r14._zones_on_confirmation_segments(
                [hourly], [four_hour])

        with patch.object(r21.r14, "r4_zones", return_value=zones), \
                patch.object(r21.r14, "_trial", side_effect=invoke_actual_mapping):
            stats = {"raw_bos_zones": 0, "pre_bos_sweep_zones": 0}
            mapped, unaligned = r21._trial_with_filtered_zones([], [], stats)

        self.assertEqual(unaligned, 0)
        self.assertEqual(list(mapped[0]), [28 * 4 + 4])
        self.assertEqual(stats, {"raw_bos_zones": 2, "pre_bos_sweep_zones": 1})
        self.assertEqual(r21.r14.r4_zones, r21.r4_zones)


if __name__ == "__main__":
    unittest.main()
