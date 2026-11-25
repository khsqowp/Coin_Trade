import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, Setup, Zone, r4_zones, simulate_trade
import search_crypto_r14 as r14


def hourly_rows(count, start=0):
    return [Bar((start + i) * r14.DURATION_MS, 100, 102, 98, 101, 1.0)
            for i in range(count)]


class SearchCryptoR14Tests(unittest.TestCase):
    def test_ledger_counter_accepts_large_metric_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            row = {field: "" for field in r14.common.FIELDS}
            row["metric"] = '{"payload":"' + ("x" * 140_000) + '"}'
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=r14.common.FIELDS)
                writer.writeheader()
                writer.writerow(row)
            self.assertEqual(r14._ledger_row_count(path), 1)

    def test_preflight_failure_sentinel_is_append_only_and_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            with patch.object(r14.common, "CSV_PATH", path):
                r14._record_preflight_failure()
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code_sha256"], "UNAVAILABLE_PRE_DATA_ACCESS")
        self.assertIn("no market rows loaded", rows[0]["notes"])

    def test_zone_activates_only_at_four_hour_close(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 102, 98, 101, 1.0)
                     for i in range(3)]
        one_hour = hourly_rows(8, start=8)
        candidate = Zone(1, 0, "long", 99, 101, 2.0)
        with patch.object(r14, "r4_zones", return_value=[candidate]):
            mapped, unaligned = r14._zones_on_confirmation_segments(
                [one_hour], [four_hour]
            )
        self.assertEqual(unaligned, 0)
        self.assertEqual(list(mapped[0]), [0])
        self.assertEqual(mapped[0][0].signal_index, 0)

    def test_unaligned_four_hour_close_is_counted_and_dropped(self):
        four_hour = [Bar(i * r14.ZONE_DURATION_MS, 100, 102, 98, 101, 1.0)
                     for i in range(3)]
        one_hour = hourly_rows(7, start=9)
        candidate = Zone(1, 0, "long", 99, 101, 2.0)
        with patch.object(r14, "r4_zones", return_value=[candidate]):
            mapped, unaligned = r14._zones_on_confirmation_segments(
                [one_hour], [four_hour]
            )
        self.assertEqual(unaligned, 1)
        self.assertEqual(mapped, [{}])

    def test_long_and_short_confirmations_use_next_open_and_fixed_risk(self):
        long_zone = Zone(0, 0, "long", 99, 101, 2.0)
        confirm = Bar(0, 100, 103, 99.5, 101, 1.0)
        next_bar = Bar(r14.DURATION_MS, 101, 102, 100, 101, 1.0)
        long_setup, reason = r14._make_setup(long_zone, confirm, next_bar, 0)
        self.assertEqual(reason, "setup")
        self.assertEqual(long_setup.entry_index, 1)
        self.assertEqual(long_setup.entry_price, 101)
        self.assertEqual(long_setup.stop, 98.8)
        self.assertAlmostEqual(long_setup.target, 102.1)

        short_zone = Zone(0, 0, "short", 99, 101, 2.0)
        short_confirm = Bar(0, 100, 100.5, 97, 99, 1.0)
        short_next = Bar(r14.DURATION_MS, 99, 100, 98, 99, 1.0)
        short_setup, reason = r14._make_setup(short_zone, short_confirm, short_next, 0)
        self.assertEqual(reason, "setup")
        self.assertEqual(short_setup.entry_price, 99)
        self.assertEqual(short_setup.stop, 101.2)
        self.assertAlmostEqual(short_setup.target, 97.9)

    def test_midpoint_failure_and_distal_wick_invalidation_are_distinct(self):
        zone = Zone(0, 0, "long", 99, 101, 2.0)
        next_bar = Bar(r14.DURATION_MS, 100, 101, 99.5, 100, 1.0)
        midpoint_fail = Bar(0, 99.5, 100.5, 99.2, 99.9, 1.0)
        invalidation = Bar(0, 100, 101, 98.9, 100.5, 1.0)
        self.assertEqual(r14._make_setup(zone, midpoint_fail, next_bar, 0)[1],
                         "midpoint_failed")
        self.assertEqual(r14._make_setup(zone, invalidation, next_bar, 0)[1],
                         "invalidated")

    def test_first_touch_is_consumed_without_second_chance(self):
        bars = hourly_rows(6)
        bars[0] = Bar(0, 102, 103, 102, 102.5, 1.0)
        bars[1] = Bar(r14.DURATION_MS, 101, 102, 99.5, 99.8, 1.0)
        bars[2] = Bar(2 * r14.DURATION_MS, 99.8, 101, 99.5, 100.5, 1.0)
        bars[3] = Bar(3 * r14.DURATION_MS, 100.5, 103, 100, 102, 1.0)
        zone = Zone(0, 0, "long", 99, 101, 2.0)
        trades, audit = r14._simulate_segment(bars, {}, {0: zone})
        self.assertEqual(trades, [])
        self.assertEqual(audit["first_touches"], 1)
        self.assertEqual(audit["midpoint_failures"], 1)

    def test_gap_segmentation_uses_each_timeframe_width(self):
        hourly = hourly_rows(2) + [Bar(4 * r14.DURATION_MS, 100, 101, 99, 100, 1.0)]
        four_hour = [Bar(0, 100, 101, 99, 100, 1.0),
                     Bar(8 * r14.DURATION_MS, 100, 101, 99, 100, 1.0)]
        self.assertEqual(r14._segments(hourly, r14.DURATION_MS)[1], 2)
        self.assertEqual(r14._segments(four_hour, r14.ZONE_DURATION_MS)[1], 1)

    def test_future_mutation_cannot_change_confirmed_four_hour_zones(self):
        bars = [Bar(i * r14.ZONE_DURATION_MS, 100, 101, 99, 100, 1.0)
                for i in range(40)]
        bars[10] = Bar(10 * r14.ZONE_DURATION_MS, 100, 110, 99, 100, 1.0)
        bars[19] = Bar(19 * r14.ZONE_DURATION_MS, 101, 102, 99, 100, 1.0)
        bars[20] = Bar(20 * r14.ZONE_DURATION_MS, 100, 112, 99, 111, 1.0)
        prefix_end = 25
        prefix_zones = [zone for zone in r4_zones(bars[:prefix_end], "bos_origin")
                        if zone.signal_index < prefix_end]
        self.assertTrue(prefix_zones, "synthetic prefix must contain a confirmed BOS zone")
        mutated = list(bars)
        for i in range(prefix_end, len(mutated)):
            mutated[i] = Bar(mutated[i].timestamp, 100, 150 + i, 50, 140 + i, 1.0)
        future_mutated_zones = [zone for zone in r4_zones(mutated, "bos_origin")
                                if zone.signal_index < prefix_end]
        self.assertEqual(prefix_zones, future_mutated_zones)

    def test_same_bar_stop_and_target_touch_resolves_to_stop(self):
        zone = Zone(0, 0, "long", 99, 101, 2.0)
        setup = Setup(zone, 1, 101, 98.8, 102.1)
        bars = [Bar(i * r14.DURATION_MS, 100, 101, 99, 100, 1.0)
                for i in range(4)]
        bars[1] = Bar(r14.DURATION_MS, 101, 103, 98, 100, 1.0)
        trade = simulate_trade(
            bars, setup, funding={}, max_holding_bars=r14.MAX_HOLDING_BARS,
            bar_duration_ms=r14.DURATION_MS,
            funding_order_policy=r14.FUNDING_ORDER_POLICY,
        )
        self.assertIsNotNone(trade)
        self.assertEqual(trade.exit_reason, "stop")


if __name__ == "__main__":
    unittest.main()
