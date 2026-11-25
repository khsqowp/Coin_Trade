from __future__ import annotations

import unittest
import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, Zone
import search_crypto_r22_bos_acceptance as r22


def bars4h(count=48):
    bars = [Bar(i * r22.r21.BAR_MS, 100, 101, 99, 100.5, 1000)
            for i in range(count)]
    row = bars[25]
    bars[25] = Bar(row.timestamp, 100, 101, 98.9, 100.1, 1000)
    return bars


class R22BosAcceptanceTests(unittest.TestCase):
    def test_ledger_row_preflight_counts_all_rows_after_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "TRAIN_TRIALS.csv"
            with ledger.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=r22.common.FIELDS)
                writer.writeheader()
                writer.writerow({field: "sentinel" for field in r22.common.FIELDS})
            with patch.object(r22.common, "CSV_PATH", ledger):
                self.assertEqual(r22._ledger_rows(), 1)

    def test_long_acceptance_is_strict_and_shifts_activation_index(self):
        bars = bars4h()
        zone = Zone(28, 24, "long", 99, 100, 1)
        bars[29] = Bar(bars[29].timestamp, 100, 101, 99, 100, 1000)
        stats = {key: 0 for key in (
            "raw_bos_zones", "pre_bos_sweep_zones", "acceptance_confirmed_zones",
            "acceptance_rejected_zones", "acceptance_confirmation_unavailable")}
        with patch.object(r22.r14, "r4_zones", return_value=[zone]):
            _, builder = r22._zones_for_acceptance(stats)
            self.assertEqual(builder(bars, "bos_origin"), [])
        self.assertEqual(stats["acceptance_rejected_zones"], 1)

        bars[29] = Bar(bars[29].timestamp, 100, 101, 99, 100.1, 1000)
        stats = {key: 0 for key in stats}
        with patch.object(r22.r14, "r4_zones", return_value=[zone]):
            _, builder = r22._zones_for_acceptance(stats)
            accepted = builder(bars, "bos_origin")
        self.assertEqual([z.signal_index for z in accepted], [29])
        self.assertEqual(stats["acceptance_confirmed_zones"], 1)

    def test_short_acceptance_uses_strict_lower_boundary(self):
        bars = bars4h()
        row = bars[25]
        bars[25] = Bar(row.timestamp, 100, 101.1, 99, 100.9, 1000)
        zone = Zone(28, 24, "short", 100, 101, 1)
        bars[29] = Bar(bars[29].timestamp, 100, 101, 99, 100, 1000)
        stats = {key: 0 for key in (
            "raw_bos_zones", "pre_bos_sweep_zones", "acceptance_confirmed_zones",
            "acceptance_rejected_zones", "acceptance_confirmation_unavailable")}
        with patch.object(r22.r14, "r4_zones", return_value=[zone]):
            _, builder = r22._zones_for_acceptance(stats)
            self.assertEqual(builder(bars, "bos_origin"), [])
        bars[29] = Bar(bars[29].timestamp, 100, 101, 99, 99.9, 1000)
        stats = {key: 0 for key in stats}
        with patch.object(r22.r14, "r4_zones", return_value=[zone]):
            _, builder = r22._zones_for_acceptance(stats)
            accepted = builder(bars, "bos_origin")
        self.assertEqual([z.signal_index for z in accepted], [29])

    def test_missing_confirmation_bar_is_counted_and_excluded(self):
        bars = bars4h(29)
        zone = Zone(28, 24, "long", 99, 100, 1)
        stats = {key: 0 for key in (
            "raw_bos_zones", "pre_bos_sweep_zones", "acceptance_confirmed_zones",
            "acceptance_rejected_zones", "acceptance_confirmation_unavailable")}
        with patch.object(r22.r14, "r4_zones", return_value=[zone]):
            _, builder = r22._zones_for_acceptance(stats)
            self.assertEqual(builder(bars, "bos_origin"), [])
        self.assertEqual(stats["acceptance_confirmation_unavailable"], 1)

    def test_acceptance_bar_close_is_known_before_real_zone_activation(self):
        four_hour = bars4h()
        hourly = [Bar(i * r22.r14.DURATION_MS, 100, 101, 99, 100.5, 1000)
                  for i in range(48 * 4)]
        zones = [Zone(28, 24, "long", 99, 100, 1),
                 Zone(40, 36, "long", 99, 100, 1)]

        def invoke_actual_mapping(_barsets_1h, _barsets_4h):
            return r22.r14._zones_on_confirmation_segments([hourly], [four_hour])

        stats = {key: 0 for key in (
            "raw_bos_zones", "pre_bos_sweep_zones", "acceptance_confirmed_zones",
            "acceptance_rejected_zones", "acceptance_confirmation_unavailable")}
        with patch.object(r22.r14, "r4_zones", return_value=zones), \
                patch.object(r22.r14, "_trial", side_effect=invoke_actual_mapping):
            mapped, unaligned = r22._trial_with_acceptance([], [], stats)
        self.assertEqual(unaligned, 0)
        self.assertEqual(list(mapped[0]), [30 * 4])
        self.assertEqual(stats["acceptance_confirmed_zones"], 1)
        self.assertEqual(r22.r14.r4_zones, r22.r21.r4_zones)

    def test_future_bars_do_not_change_preexisting_acceptance_decision(self):
        bars = bars4h()
        zone = Zone(28, 24, "long", 99, 100, 1)
        bars[29] = Bar(bars[29].timestamp, 100, 102, 99, 101, 1000)

        def selected(series):
            stats = {key: 0 for key in (
                "raw_bos_zones", "pre_bos_sweep_zones", "acceptance_confirmed_zones",
                "acceptance_rejected_zones", "acceptance_confirmation_unavailable")}
            with patch.object(r22.r14, "r4_zones", return_value=[zone]):
                _, builder = r22._zones_for_acceptance(stats)
                return builder(series, "bos_origin")

        baseline = selected(bars)
        future_changed = list(bars)
        for index in range(30, len(future_changed)):
            old = future_changed[index]
            future_changed[index] = Bar(old.timestamp, old.open, old.high + 50,
                                         old.low - 50, old.close / 2, old.volume * 10)
        self.assertEqual(baseline, selected(future_changed))


if __name__ == "__main__":
    unittest.main()
