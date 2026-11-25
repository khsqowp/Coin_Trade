from __future__ import annotations

import unittest

import search_crypto_r23_r21_attribution as r23


class R23AttributionTests(unittest.TestCase):
    def test_fixed_direction_and_year_groups_keep_all_signals(self):
        records = [
            {"direction": "long", "year": 2020, "target_hit": True,
             "net_return": 0.01},
            {"direction": "long", "year": 2020, "target_hit": False,
             "net_return": -0.005},
            {"direction": "short", "year": 2021, "target_hit": True,
             "net_return": 0.02},
            {"direction": "short", "year": 2021, "target_hit": False,
             "net_return": None},
        ]
        result = r23._summarize(records)
        self.assertEqual(result["by_direction"]["long"]["signals"], 2)
        self.assertEqual(result["by_direction"]["long"]["target_hits"], 1)
        self.assertEqual(result["by_direction"]["short"]["scoreable_trades"], 1)
        self.assertEqual(result["by_utc_entry_year"]["2021"]["signals"], 2)
        self.assertEqual(result["by_utc_entry_year"]["2021"]["target_hits"], 1)

    def test_no_observed_groups_returns_empty_axes(self):
        self.assertEqual(r23._summarize([]), {
            "by_direction": {}, "by_utc_entry_year": {}})


if __name__ == "__main__":
    unittest.main()
