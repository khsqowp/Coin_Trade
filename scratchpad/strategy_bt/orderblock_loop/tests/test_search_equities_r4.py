import tempfile
import unittest
from datetime import date
from pathlib import Path
import csv
import pandas as pd
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from equities import Trade
from equities import Bar
from search_equities_r4 import (Membership, NEW_CANDIDATES, _configs,
                                _e2_signal, _crossed_weekly, load_membership,
                                _append_trials, simulate_e2, survivorship_safe_trades,
                                _daily_bars, run)


class SearchEquitiesR4Tests(unittest.TestCase):
    @staticmethod
    def quality_frame(count=40, bad_positions=()):
        day = datetime(2010, 1, 4, tzinfo=timezone.utc)
        rows = []
        while len(rows) < count:
            if day.weekday() < 5:
                close = 100 + len(rows) * .1
                rows.append({"open_time": int(day.timestamp() * 1000), "open": close,
                             "high": close + 1, "low": close - 1, "close": close,
                             "volume": 100, "complete": True})
            day += timedelta(days=1)
        for index in bad_positions:
            rows[index]["high"] = rows[index]["low"] - 1
        return pd.DataFrame(rows)

    def test_ohlc_quality_filter_keeps_symbol_and_computes_bars(self):
        frame = self.quality_frame(bad_positions=(5,))
        member = Membership("US", "AAA", date(2000, 1, 1), date(2020, 1, 1),
                            "fixture", date(2020, 1, 1))
        stats = {}
        bars = _daily_bars(frame, member, stats)
        self.assertEqual(len(bars), len(frame) - 1)
        self.assertEqual(stats["invalid_ohlc"], 1)
        self.assertIsInstance(simulate_e2("E2-B", bars, "US")[0], list)

    def test_quality_exclusion_is_per_symbol_and_trial_metrics_are_aggregated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            universe, membership, trial_path = root / "universe.csv", root / "membership.csv", root / "trials.csv"
            universe.write_text("market,symbol,daily_path\nUS,BAD,bad.csv\nUS,GOOD,good.csv\n")
            membership.write_text("market,symbol,alive_from,alive_through,source,source_asof\n"
                                  "US,BAD,2000-01-01,2020-01-01,fixture,2020-01-01\n"
                                  "US,GOOD,2000-01-01,2020-01-01,fixture,2020-01-01\n")
            frames = {"BAD": self.quality_frame(30, (2, 3, 4)),
                      "GOOD": self.quality_frame(40, (5,))}
            def load(_path, symbol, _market, _split):
                return frames[symbol]
            with patch("search_equities_r3._load_train", side_effect=load):
                results = run(universe, membership, root / "split.json", trials_path=trial_path)
            self.assertTrue(any(r.get("symbol") == "GOOD" for r in results))
            self.assertTrue(any(r.get("symbol") == "GOOD" and "trades" in r for r in results))
            self.assertFalse(any(r.get("symbol") == "BAD" for r in results))
            with trial_path.open(newline="", encoding="utf-8") as handle:
                trial = next(csv.DictReader(handle))
            import json
            metric = json.loads(trial["metric"])
            self.assertEqual(metric["invalid_ohlc_rows_filtered"], 1)
            self.assertEqual(metric["halt_bars_filtered"], 0)
            self.assertEqual(metric["symbols_quality_excluded"], 1)

    def test_membership_market_labels_normalize_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "membership.csv"
            header = "market,symbol,alive_from,alive_through,source,source_asof\n"
            rows = [f"{market},KR{i},2000-01-01,2010-01-01,official,2020-01-01"
                    for i, market in enumerate(("KOSPI", "KOSDAQ", "KONEX", "KOSDAQ GLOBAL"))]
            rows.append("US,AAA,2000-01-01,2010-01-01,official,2020-01-01")
            path.write_text(header + "\n".join(rows) + "\n")
            records = load_membership(path)
            for i in range(4):
                self.assertEqual(records[("KR", f"KR{i}")].market, "KR")
            self.assertEqual(records[("US", "AAA")].market, "US")

            path.write_text(header + "UNKNOWN,AAA,2000-01-01,2010-01-01,official,2020-01-01\n")
            with self.assertRaisesRegex(ValueError, "^invalid membership key: 'UNKNOWN'/'AAA'$"):
                load_membership(path)

            path.write_text(header +
                            "KOSPI,AAA,2000-01-01,2010-01-01,official,2020-01-01\n"
                            "KOSDAQ,AAA,2001-01-01,2011-01-01,official,2020-01-01\n")
            with self.assertRaisesRegex(ValueError, "^duplicate membership record: KR/AAA$"):
                load_membership(path)

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
