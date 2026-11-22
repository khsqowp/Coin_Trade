import tempfile
import unittest
from datetime import date
from pathlib import Path
import csv

from equities import Trade
from equities import Bar
from search_equities_r4 import (Membership, NEW_CANDIDATES, _configs,
                                _e2_signal, _crossed_weekly, load_membership,
                                _append_trials, simulate_e2, survivorship_safe_trades)


class SearchEquitiesR4Tests(unittest.TestCase):
    def test_c1_robustness_grid_is_16_per_market(self):
        self.assertEqual(len(_configs()), 16)
        self.assertEqual(len(NEW_CANDIDATES), 6)

    def test_requires_complete_membership_schema_and_unique_symbols(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "membership.csv"
            path.write_text("market,symbol,alive_from,alive_through,source,source_asof\n"
                            "US,AAA,2000-01-01,2010-01-01,official,2020-01-01\n")
            records = load_membership(path)
            self.assertTrue(records[("US", "AAA")].alive(date(2005, 1, 1)))
            self.assertFalse(records[("US", "AAA")].alive(date(2011, 1, 1)))
            path.write_text("market,symbol\nUS,AAA\n")
            with self.assertRaisesRegex(ValueError, "requires"):
                load_membership(path)

    def test_delisting_gap_excludes_trade_without_in_life_exit(self):
        membership = Membership("US", "AAA", date(2000, 1, 1), date(2000, 1, 2),
                                "official", date(2020, 1, 1))
        bars = [
            type("BarFixture", (), {"timestamp": 946684800000})(),
            type("BarFixture", (), {"timestamp": 946771200000})(),
            type("BarFixture", (), {"timestamp": 946857600000})(),
        ]
        trade = Trade("C1", 0, 1, 2, 100, 101, "time", .01, 20, .008)
        accepted, gaps = survivorship_safe_trades([trade], bars, membership)
        self.assertEqual(accepted, [])
        self.assertEqual(gaps, 1)

    @staticmethod
    def synthetic_bars(count=300):
        # Weekday-only UTC fixtures; no market files or external data are read.
        from datetime import datetime, timedelta, timezone
        stamp = datetime(2010, 1, 4, tzinfo=timezone.utc)
        bars = []
        day = stamp
        while len(bars) < count:
            if day.weekday() < 5:
                n = len(bars)
                close = 100 + n * .01
                bars.append(Bar(int(day.timestamp() * 1000), close, close + .5,
                                close - .5, close))
            day += timedelta(days=1)
        return bars

    def test_e2_a_252_day_momentum_signal(self):
        bars = self.synthetic_bars()
        self.assertIsNotNone(_e2_signal("E2-A", bars, 252, [], []))

    def test_e2_b_55_day_donchian_candidate_runs(self):
        trades, _ = simulate_e2("E2-B", self.synthetic_bars(), "US")
        self.assertIsInstance(trades, list)

    def test_e2_c_bollinger_candidate_runs(self):
        trades, _ = simulate_e2("E2-C", self.synthetic_bars(), "KR")
        self.assertIsInstance(trades, list)

    def test_e2_d_weekly_donchian_signal(self):
        bars = self.synthetic_bars()
        weekly, last = _crossed_weekly(bars)
        self.assertGreaterEqual(len(weekly), 20)
        self.assertIsInstance(_e2_signal("E2-D", bars, last[-1], weekly, last), (tuple, type(None)))

    def test_e2_e_weekly_sma_candidate_runs(self):
        trades, _ = simulate_e2("E2-E", self.synthetic_bars(), "US")
        self.assertIsInstance(trades, list)

    def test_e2_f_volatility_contraction_candidate_runs(self):
        trades, _ = simulate_e2("E2-F", self.synthetic_bars(), "KR")
        self.assertIsInstance(trades, list)

    def test_r4_trial_writer_uses_shared_schema_and_code_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trials.csv"
            row = {"market": "US", "strategy": "E2-A", "parameters": {"candidate": "E2-A"},
                   "trades": 0, "survivorship_biased": False}
            _append_trials([row], path)
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]), 11)
            self.assertEqual(rows[0]["round"], "R4")
            self.assertEqual(len(rows[0]["code_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
