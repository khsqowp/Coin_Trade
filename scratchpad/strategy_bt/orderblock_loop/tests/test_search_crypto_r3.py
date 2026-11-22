import unittest
import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, FundingEvent, Zone
from search_crypto import _filter_r3_zones
from search_crypto_r3 import CONFIGS, _append_r3, exclude_unscorable_symbols


class SearchCryptoR3Tests(unittest.TestCase):
    def test_grid_has_exactly_48_unique_registered_configs(self):
        keys = {tuple(sorted(config.items())) for config in CONFIGS}
        self.assertEqual(len(CONFIGS), 48)
        self.assertEqual(len(keys), 48)
        self.assertEqual({config["definition"] for config in CONFIGS},
                         {"displacement", "bos_origin", "volume_displacement"})

    def test_exclusion_drops_unresolved_marks_gaps_and_empty_train(self):
        bars = [Bar(0, 10, 11, 9, 10, 1)]
        barsets = [
            ("GOOD", bars, {1: FundingEvent(1, 0.0, 10)}, 0),
            ("NO_MARK", bars, {1: FundingEvent(1, 0.0, None)}, 0),
            ("GAP", bars, {1: FundingEvent(1, 0.0, 10, coverage_gap=True)}, 0),
            ("EMPTY", [], {}, 0),
        ]
        kept, funding_excluded, empty_excluded = exclude_unscorable_symbols(barsets)
        self.assertEqual([item[0] for item in kept], ["GOOD"])
        self.assertEqual(funding_excluded, ["GAP", "NO_MARK"])
        self.assertEqual(empty_excluded, ["EMPTY"])

    def test_daily_trend_uses_only_prior_completed_utc_days(self):
        day_ms = 86_400_000
        bars = [Bar(day * day_ms, 100, 101, 99, 100, 1) for day in range(20)]
        bars.append(Bar(20 * day_ms, 100, 121, 99, 120, 1))
        bars.append(Bar(21 * day_ms, 100, 1001, 99, 1000, 1))
        candidate = Zone(21, 19, "long", 99, 101, 1)
        config = {"trend_filter": "close_gt_sma20", "session_filter": "none"}
        filtered = _filter_r3_zones(bars, [candidate], config)
        self.assertEqual(filtered, [candidate])
        bars[21] = Bar(21 * day_ms, 100, 101, 99, 100, 1)
        self.assertEqual(_filter_r3_zones(bars, [candidate], config), [candidate])

    def test_session_filter_classifies_signal_bar_open_utc(self):
        day_ms = 86_400_000
        bars = [Bar(day_ms + 8 * 3_600_000, 100, 101, 99, 100, 1)]
        candidate = Zone(0, 0, "long", 99, 101, 1)
        self.assertEqual(_filter_r3_zones(
            bars, [candidate], {"trend_filter": "none", "session_filter": "europe"}),
            [candidate])
        self.assertEqual(_filter_r3_zones(
            bars, [candidate], {"trend_filter": "none", "session_filter": "asia"}), [])

    def test_trial_writer_records_r3_round_and_filter_config(self):
        config = CONFIGS[0]
        result = {"status": "unscorable", "kept_symbols": 0,
                  "excluded_funding_symbols": ["BAD"],
                  "excluded_no_train_bar_symbols": ["EMPTY"]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trials.csv"
            with patch("search_crypto_r3.r2.CSV_PATH", path):
                _append_r3(config, result, "f" * 64)
            with path.open(newline="", encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
        self.assertEqual(row["round"], "R3-coin")
        self.assertEqual(row["market_group"], "crypto")
        self.assertEqual(json.loads(row["definition"]), config)
        metric = json.loads(row["metric"])
        self.assertEqual(metric["kept_symbols"], 0)
        self.assertEqual(metric["excluded_funding_symbols"], ["BAD"])
        self.assertEqual(metric["train_input_fingerprint"], "f" * 64)


if __name__ == "__main__":
    unittest.main()
