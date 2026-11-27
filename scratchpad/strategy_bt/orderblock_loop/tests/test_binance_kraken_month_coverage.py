import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import binance_kraken_month_coverage as coverage


class TimestampCoverageTests(unittest.TestCase):
    def test_canonical_data_root_is_required(self):
        with self.assertRaises(ValueError):
            coverage.require_data_root("/not/the/repository")

    def test_only_first_csv_field_is_interpreted(self):
        months, error = coverage.months_from_timestamp_lines(
            [b"1514764800,not-a-price,not-volume\n"]
        )
        self.assertIsNone(error)
        self.assertEqual(months, {"2018-01"})

    def test_monthly_boundary_maps_to_utc_month(self):
        months, error = coverage.months_from_timestamp_lines(
            [b"1517443200,ignored\n"]
        )
        self.assertIsNone(error)
        self.assertEqual(months, {"2018-02"})

    def test_stops_at_first_timestamp_after_frozen_window(self):
        months, error = coverage.months_from_timestamp_lines(
            [b"1672444799,x\n", b"1672531200,x\n", b"bad-row\n"]
        )
        self.assertIsNone(error)
        self.assertEqual(months, {"2022-12"})

    def test_unsorted_timestamps_fail_closed(self):
        months, error = coverage.months_from_timestamp_lines(
            [b"1517443200,x\n", b"1514764800,x\n"]
        )
        self.assertEqual(error, "timestamp-unsorted")
        self.assertEqual(months, {"2018-02"})

    def test_fixed_cohort_and_threshold_do_not_drift(self):
        self.assertEqual(len(coverage.ASSETS), 29)
        self.assertEqual(len(coverage.BINANCE_COMPLETE), 20)
        self.assertNotIn("BCC", coverage.BINANCE_COMPLETE)


if __name__ == "__main__":
    unittest.main()
