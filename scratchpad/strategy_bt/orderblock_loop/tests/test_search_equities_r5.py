import csv
import json
import math
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from equities import Bar, Trade
from search_equities_r5 import (Membership, NEW_CANDIDATES, _append_trials, _indicators,
                               _cost_bps, _e3j_portfolio_metrics, _signal, simulate_e3,
                               load_membership, survivorship_safe_trades, _daily_bars, run)


class SearchEquitiesR5Tests(unittest.TestCase):
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
        self.assertIsInstance(simulate_e3("E3-A", bars, "US")[0], list)

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
            self.assertEqual(metric["symbols_data_error"], 0)

    def test_unexpected_symbol_error_is_recorded_and_run_continues(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            universe, membership, trial_path = root / "universe.csv", root / "membership.csv", root / "trials.csv"
            universe.write_text("market,symbol,daily_path\nUS,BROKEN,bad.csv\nUS,GOOD,good.csv\n")
            membership.write_text("market,symbol,alive_from,alive_through,source,source_asof\n"
                                  "US,BROKEN,2000-01-01,2020-01-01,fixture,2020-01-01\n"
                                  "US,GOOD,2000-01-01,2020-01-01,fixture,2020-01-01\n")
            frames = {"BROKEN": self.quality_frame(), "GOOD": self.quality_frame()}
            def load(_path, symbol, _market, _split):
                return frames[symbol]
            original = _daily_bars
            def fail_one(frame, member, stats=None):
                if member.symbol == "BROKEN":
                    raise ValueError("synthetic unexpected failure")
                return original(frame, member, stats)
            with patch("search_equities_r3._load_train", side_effect=load), \
                 patch("search_equities_r5._daily_bars", side_effect=fail_one):
                results = run(universe, membership, root / "split.json", trials_path=trial_path)
            self.assertTrue(any(r.get("symbol") == "GOOD" for r in results))
            self.assertFalse(any(r.get("symbol") == "BROKEN" for r in results))
            with trial_path.open(newline="", encoding="utf-8") as handle:
                metrics = [json.loads(row["metric"]) for row in csv.DictReader(handle)]
            self.assertTrue(metrics)
            self.assertTrue(all(metric["symbols_data_error"] == 1 for metric in metrics))

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

    @staticmethod
    def bars(count=260, start=datetime(2010, 1, 4, tzinfo=timezone.utc)):
        result, day = [], start
        while len(result) < count:
            if day.weekday() < 5:
                n = len(result)
                close = 100 + n * 0.01
                result.append(Bar(int(day.timestamp() * 1000), close, close + 1,
                                  close - 1, close))
            day += timedelta(days=1)
        return result

    @staticmethod
    def indicator_fixture(bars):
        n = len(bars)
        return {"close": [b.close for b in bars],
                "high": [b.high for b in bars], "low": [b.low for b in bars],
                "supertrend": [None] * n, "cloud_a": [None] * n, "cloud_b": [None] * n,
                "atr10": [2.0] * n, "atr14": [2.0] * n, "ema20": [100.0] * n,
                "ema100": [90.0] * n, "rsi4": [50.0] * n, "rsi14": [40.0] * n,
                "cci": [0.0] * n, "mfi": [50.0] * n, "williams": [-50.0] * n,
                "adx": [40.0] * n}

    def test_all_ten_rules_emit_the_registered_signal(self):
        for candidate in NEW_CANDIDATES:
            with self.subTest(candidate=candidate):
                bars = self.bars(260)
                i = 220
                ind = self.indicator_fixture(bars)
                if candidate == "E3-A":
                    ind["supertrend"][i-1], ind["supertrend"][i] = 101, 101
                    ind["close"][i-1], ind["close"][i] = 100, 102
                elif candidate == "E3-B":
                    ind["cloud_a"][i], ind["cloud_b"][i] = 100, 101
                    ind["high"][i-25:i+1] = [102] * 26
                    ind["low"][i-25:i+1] = [99] * 26
                    ind["low"][i-8:i+1] = [100] * 9
                    ind["close"][i] = 103
                elif candidate == "E3-C":
                    ind["close"][i-20:i] = [100] * 20
                    ind["atr10"][i-1] = 2
                    ind["ema20"][i] = 100
                    ind["close"][i] = 105
                    b = bars[i]
                    bars[i] = Bar(b.timestamp, 104, 106, 103, 105)
                elif candidate == "E3-D":
                    ind["rsi4"][i-1], ind["rsi4"][i] = 14, 16
                    ind["close"][i] = 101
                elif candidate == "E3-E":
                    ind["cci"][i-1], ind["mfi"][i-1] = -120, 10
                    ind["cci"][i], ind["mfi"][i] = -90, 25
                elif candidate == "E3-F":
                    ind["williams"][i-1], ind["williams"][i] = -85, -55
                    ind["close"][i] = 110
                elif candidate == "E3-G":
                    ind["low"][i-20:i-10] = [100] * 10
                    ind["low"][i-10:i] = [95] * 10
                    ind["rsi14"][i-20:i-10] = [30] * 10
                    ind["rsi14"][i-10:i] = [35] * 10
                    ind["high"][i-20:i] = [100] * 20
                    ind["close"][i] = 101
                elif candidate == "E3-H":
                    b = bars[i]
                    bars[i] = Bar(b.timestamp, 101, 103, 99, 102)
                    ind["low"][i], ind["close"][i], ind["ema20"][i] = 99, 102, 100
                elif candidate == "E3-I":
                    monday = datetime(2010, 2, 1, tzinfo=timezone.utc)
                    bars = self.bars(260, monday - timedelta(days=5))
                    i = 3
                    ind = self.indicator_fixture(bars)
                    ind["close"][i-3:i+1] = [103, 102, 101, 100]
                elif candidate == "E3-J":
                    start = datetime(2010, 10, 28, tzinfo=timezone.utc)
                    bars = self.bars(260, start)
                    i = next(j for j, bar in enumerate(bars) if datetime.fromtimestamp(bar.timestamp / 1000, timezone.utc).month == 11)
                    ind = self.indicator_fixture(bars)
                self.assertIsNotNone(_signal(candidate, bars, ind, i))

    def test_costs_are_deducted_from_synthetic_trade(self):
        bars = [Bar(1, 100, 101, 99, 100), Bar(2, 100, 110, 99, 110),
                Bar(3, 110, 111, 109, 110)]
        with patch("search_equities_r5._indicators", return_value=self.indicator_fixture(bars)), \
             patch("search_equities_r5._signal", side_effect=[("signal", 1, None, None), None]):
            trades, _ = simulate_e3("E3-A", bars, "US")
        self.assertEqual(len(trades), 1)
        self.assertAlmostEqual(trades[0].gross_return, 0.10)
        self.assertAlmostEqual(trades[0].cost_bps, 20.0)
        self.assertAlmostEqual(trades[0].net_return, 0.098)
        self.assertEqual(_cost_bps("KR"), 31.0)

    def test_delisting_gap_fails_closed(self):
        membership = Membership("US", "AAA", date(2000, 1, 1), date(2000, 1, 2),
                                "official", date(2020, 1, 1))
        bars = [Bar(int(datetime(2000, 1, d, tzinfo=timezone.utc).timestamp() * 1000), 100, 101, 99, 100)
                for d in (1, 2, 3)]
        trade = Trade("E3-A", 0, 1, 2, 100, 101, "time", .01, 20, .008)
        kept, gaps = survivorship_safe_trades([trade], bars, membership)
        self.assertEqual(kept, [])
        self.assertEqual(gaps, 1)

    def test_e3j_portfolio_curve_mdd_sharpe_and_pit_cohort(self):
        days = [date(2020, 11, 2), date(2020, 11, 3), date(2020, 11, 4),
                date(2021, 5, 3), date(2021, 5, 4)]

        def bars(closes, through=4):
            result = []
            for i, day in enumerate(days[:through + 1]):
                open_price = 100.0
                close_price = closes[i]
                stamp = int(datetime(day.year, day.month, day.day,
                                     tzinfo=timezone.utc).timestamp() * 1000)
                result.append(Bar(stamp, open_price, max(open_price, close_price) + 1,
                                   min(open_price, close_price) - 1, close_price))
            return result

        symbols = {"AAA": bars([100, 110, 100, 90, 90]),
                   "BBB": bars([100, 100, 110, 100, 100]),
                   "GAP": bars([100, 100, 100, 100], through=3),
                   "LATE": bars([100, 100, 100, 100, 100])}
        members = {
            "AAA": Membership("US", "AAA", date(2020, 1, 1), date(2022, 1, 1), "official", date(2022, 1, 1)),
            "BBB": Membership("US", "BBB", date(2020, 1, 1), date(2022, 1, 1), "official", date(2022, 1, 1)),
            "GAP": Membership("US", "GAP", date(2020, 1, 1), date(2021, 5, 3), "official", date(2022, 1, 1)),
            "LATE": Membership("US", "LATE", date(2020, 11, 3), date(2022, 1, 1), "official", date(2022, 1, 1)),
        }

        result = _e3j_portfolio_metrics(symbols, members)

        # Daily portfolio marks are 1.05, 1.05, 0.95; returns are 1/20, 0, -2/21.
        expected_returns = [1 / 20, 0.0, -2 / 21]
        average = sum(expected_returns) / 3
        sample_variance = sum((value - average) ** 2 for value in expected_returns) / 2
        expected_sharpe = math.sqrt(252) * average / math.sqrt(sample_variance)
        self.assertEqual(result["symbols"], 2)
        self.assertEqual(result["trades"], 2)
        self.assertEqual(result["delisting_gap"], 1)
        self.assertAlmostEqual(result["max_drawdown"], 0.95 / 1.05 - 1)
        self.assertAlmostEqual(result["sharpe"], expected_sharpe)

    def test_membership_interval_is_inclusive(self):
        membership = Membership("US", "AAA", date(2000, 1, 1), date(2000, 1, 2),
                                "official", date(2020, 1, 1))
        bars = [Bar(int(datetime(2000, 1, d, tzinfo=timezone.utc).timestamp() * 1000), 100, 101, 99, 100)
                for d in (1, 2)]
        trade = Trade("E3-A", 0, 0, 1, 100, 101, "time", .01, 20, .008)
        kept, gaps = survivorship_safe_trades([trade], bars, membership)
        self.assertEqual(kept, [trade])
        self.assertEqual(gaps, 0)

    def test_e3_e_requires_real_volume_for_mfi(self):
        with self.assertRaisesRegex(ValueError, "actual daily volume"):
            simulate_e3("E3-E", self.bars(), "US")

    def test_williams_indicator_does_not_depend_on_volume(self):
        indicators = _indicators(self.bars(30))
        self.assertIsNotNone(indicators["williams"][29])
        self.assertIsNone(indicators["mfi"][29])

    def test_trial_writer_keeps_shared_schema_and_code_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trials.csv"
            _append_trials([{"market": "US", "strategy": "E3-A",
                             "parameters": {"candidate": "E3-A"}}], path)
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]), 11)
            self.assertEqual(rows[0]["round"], "R5")
            self.assertEqual(len(rows[0]["code_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
