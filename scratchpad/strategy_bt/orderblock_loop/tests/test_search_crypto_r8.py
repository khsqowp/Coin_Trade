import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crypto import (Bar, FundingEvent, Setup, Zone, simulate_trade,
                    trade_daily_pnl)
import search_crypto_r8 as r8


def bars(rows, start=0):
    return [Bar((i + start) * r8.DURATION_MS, *row, 1)
            for i, row in enumerate(rows)]


class SearchCryptoR8Tests(unittest.TestCase):
    def setUp(self):
        self.zone = Zone(0, 0, "long", 9.5, 10.5, 1.0)

    def test_no_trade_before_close_confirmed_invalidation(self):
        data = bars([
            (10, 11, 9, 10),
            (10, 10.0, 9.2, 9.4),
        ])
        with patch.object(r8, "_atr", return_value=1.0):
            setup, consumed, reason = r8._flip_setup(data, self.zone)
        self.assertIsNone(setup)
        self.assertEqual((consumed, reason), (1, "expired"))

    def test_first_rejection_after_invalidation_enters_next_open(self):
        data = bars([
            (10, 11, 9, 10),
            (10, 10.4, 9.7, 9.8),
            (9.8, 10.0, 9.2, 9.4),
            (9.4, 10.2, 9.3, 9.4),
            (9.4, 9.8, 9.1, 9.5),
            (9.5, 10.3, 9.4, 9.6),
        ])
        with patch.object(r8, "_atr", return_value=1.0):
            setup, consumed, reason = r8._flip_setup(data, self.zone)
        self.assertEqual(reason, "setup")
        self.assertEqual(consumed, 3)
        self.assertEqual(setup.zone.direction, "short")
        self.assertEqual(setup.entry_index, 4)
        self.assertEqual(setup.entry_price, data[4].open)
        self.assertAlmostEqual(setup.stop, 10.3)
        self.assertAlmostEqual(setup.target, 7.6)

    def test_recovery_above_ob_cancels_before_retest(self):
        data = bars([
            (10, 11, 9, 10),
            (10, 10.4, 9.7, 9.8),
            (9.8, 10.0, 9.2, 9.4),
            (9.4, 10.8, 9.3, 10.6),
            (10.6, 10.8, 9.2, 9.4),
        ])
        setup, consumed, reason = r8._flip_setup(data, self.zone)
        self.assertIsNone(setup)
        self.assertEqual((consumed, reason), (3, "recovered"))

    def test_first_zone_touch_that_does_not_reject_consumes_setup(self):
        data = bars([
            (10, 11, 9, 10),
            (10, 10.4, 9.7, 9.4),
            (9.4, 10.2, 9.3, 10.0),
            (10.0, 10.1, 9.2, 9.4),
        ])
        setup, consumed, reason = r8._flip_setup(data, self.zone)
        self.assertIsNone(setup)
        self.assertEqual((consumed, reason), (2, "first_retest_failed"))

    def test_gap_above_stop_skips_entry_without_later_retest(self):
        data = bars([
            (10, 11, 9, 10),
            (10, 10.4, 9.7, 9.8),
            (9.8, 10.0, 9.2, 9.4),
            (9.4, 10.2, 9.3, 9.4),
            (10.4, 10.8, 10.1, 10.5),
            (10.0, 10.3, 9.1, 9.4),
        ])
        with patch.object(r8, "_atr", return_value=1.0):
            setup, consumed, reason = r8._flip_setup(data, self.zone)
        self.assertIsNone(setup)
        self.assertEqual((consumed, reason), (3, "gap_skipped"))

    def test_future_bars_do_not_change_first_setup(self):
        prefix = bars([
            (10, 11, 9, 10),
            (10, 10.4, 9.7, 9.8),
            (9.8, 10.0, 9.2, 9.4),
            (9.4, 10.2, 9.3, 9.4),
            (9.4, 9.8, 9.1, 9.5),
        ])
        future_changed = prefix + bars([(8, 12, 7, 11), (11, 13, 6, 7)], start=5)
        with patch.object(r8, "_atr", return_value=1.0):
            first = r8._flip_setup(prefix, self.zone)
            second = r8._flip_setup(future_changed, self.zone)
        self.assertEqual(first, second)

    def test_fixed_config_and_m2_denominators(self):
        self.assertEqual(len(r8.CONFIGS), 1)
        self.assertEqual(r8.CONFIG["trade_direction"], "short")
        metrics = r8._m2_metrics([
            ("A", 0, 20, True), ("A", 10, 30, False), ("A", 25, 40, True),
        ])
        self.assertEqual(metrics["m2_signal_count"], 3)
        self.assertEqual(metrics["m2_target_hits"], 2)
        self.assertEqual(metrics["m2_nonoverlap_signal_count"], 2)
        self.assertEqual(metrics["m2_nonoverlap_target_hits"], 2)

    def test_bar_gap_splits_r8_sequences_and_counts_missing_bars(self):
        data = bars([
            (10, 11, 9, 10), (10, 11, 9, 10),
        ]) + bars([
            (10, 11, 9, 10), (10, 11, 9, 10),
        ], start=3)

        segments, missing = r8._continuous_segments(data)

        self.assertEqual([len(segment) for segment in segments], [2, 2])
        self.assertEqual(missing, 1)
        self.assertEqual(segments[0][-1].timestamp + r8.DURATION_MS,
                         segments[1][0].timestamp - r8.DURATION_MS)

    def test_bar_timestamp_must_be_aligned_to_four_hour_open(self):
        data = [Bar(r8.DURATION_MS // 2, 10, 11, 9, 10, 1)]

        with self.assertRaisesRegex(ValueError, "UTC 4h boundary"):
            r8._continuous_segments(data)

    def test_bar_timestamps_must_increase_strictly(self):
        data = bars([(10, 11, 9, 10), (10, 11, 9, 10)])
        data[1] = Bar(data[0].timestamp, 10, 11, 9, 10, 1)

        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            r8._continuous_segments(data)

    def test_resume_requires_matching_train_input_fingerprint(self):
        fields = ("round", "parameter_grid_hash", "code_sha256", "metric")
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "round": "R8-coin", "parameter_grid_hash": "grid",
                    "code_sha256": "code",
                    "metric": json.dumps({
                        "train_input_fingerprint": "fingerprint-a",
                        "prereg_sha256": "prereg-a", "status": "completed",
                    }),
                })
            with patch.object(r8.common, "CSV_PATH", ledger):
                self.assertTrue(r8._already_recorded(
                    "grid", "code", "fingerprint-a", "prereg-a"
                ))
                self.assertFalse(r8._already_recorded(
                    "grid", "code", "fingerprint-a", "prereg-b"
                ))
                self.assertFalse(r8._already_recorded(
                    "grid", "code", "fingerprint-b", "prereg-a"
                ))

    def test_resume_ignores_malformed_or_missing_fingerprint_metrics(self):
        fields = ("round", "parameter_grid_hash", "code_sha256", "metric")
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for metric in ("{}", "[]", "not-json"):
                    writer.writerow({
                        "round": "R8-coin", "parameter_grid_hash": "grid",
                        "code_sha256": "code", "metric": metric,
                    })
            with patch.object(r8.common, "CSV_PATH", ledger):
                self.assertFalse(r8._already_recorded(
                    "grid", "code", "fingerprint-a", "prereg-a"
                ))

    def test_short_same_bar_stop_and_ambiguous_adverse_funding_reconcile(self):
        candles = [Bar(i * r8.DURATION_MS, 100, 100.5, 99.5, 100, 1)
                   for i in range(50)]
        candles[2] = Bar(2 * r8.DURATION_MS, 100, 101.5, 97.5, 99, 1)
        setup = Setup(Zone(0, 0, "short", 99, 101, 1), 1, 100, 101, 98)
        event_ts = candles[2].timestamp + r8.DURATION_MS // 2
        funding = {event_ts: FundingEvent(event_ts, -0.001, 100)}

        trade = simulate_trade(
            candles, setup, funding=funding, bar_duration_ms=r8.DURATION_MS,
            funding_order_policy=r8.FUNDING_ORDER_POLICY,
        )

        self.assertEqual(trade.exit_reason, "stop")
        self.assertEqual(trade.exit_price, 101)
        self.assertEqual(trade.ambiguous_funding_events, 1)
        self.assertAlmostEqual(trade.funding_return, -0.001)
        daily = trade_daily_pnl(
            candles, trade, funding=funding, bar_duration_ms=r8.DURATION_MS,
        )
        self.assertAlmostEqual(sum(daily.values()), trade.net_return)


if __name__ == "__main__":
    unittest.main()
