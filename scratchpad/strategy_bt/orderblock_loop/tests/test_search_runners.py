import unittest
import csv
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, FundingEvent
from search_crypto import (METRIC_FIELDS, _append, _funding_by_timestamp,
                           _run_trial, _train_input_fingerprint)
from equities import Bar as EquityBar, Trade
from search_equities import _configs, _daily_trade_pnl, _max_drawdown, _weekly_bars


class SearchRunnerTests(unittest.TestCase):
    def test_train_input_fingerprint_is_canonical_and_content_sensitive(self):
        bars = [Bar(1000, 100, 102, 99, 101, 12)]
        funding = {1500: FundingEvent(1500, 0.001, 100.5,
                                      used_candle_close_fallback=True)}
        barsets = [("ETHUSDT", bars, funding, 0), ("EMPTY", [], {}, 0)]
        fingerprint = _train_input_fingerprint("15m", barsets)
        self.assertEqual(fingerprint, _train_input_fingerprint("15m", barsets[::-1]))
        self.assertNotEqual(fingerprint, _train_input_fingerprint(
            "1h", barsets))
        changed_bar = [Bar(1000, 100, 102, 99, 101.25, 12)]
        self.assertNotEqual(fingerprint, _train_input_fingerprint(
            "15m", [("ETHUSDT", changed_bar, funding, 0), ("EMPTY", [], {}, 0)]))
        changed_funding = {1500: FundingEvent(1500, 0.001, 101,
                                               used_candle_close_fallback=True)}
        self.assertNotEqual(fingerprint, _train_input_fingerprint(
            "15m", [("ETHUSDT", bars, changed_funding, 0), ("EMPTY", [], {}, 0)]))
        sentinel = {1500: FundingEvent(1500, 0.0, None, coverage_gap=True)}
        self.assertNotEqual(fingerprint, _train_input_fingerprint(
            "15m", [("ETHUSDT", bars, sentinel, 0), ("EMPTY", [], {}, 0)]))

    def test_trial_ledger_keeps_current_funding_field_names_and_fingerprint(self):
        fingerprint = "a" * 64
        row = {
            "timestamp_utc": "2026-11-22T00:00:00+00:00",
            "definition": "bos_origin", "timeframe": "15m", "direction": "long",
            "deadline": 24, "reward_r": 1.5,
            "train_input_fingerprint": fingerprint,
            "symbols": 31, "trades": 4,
            "symbols_with_unresolved_funding_prices": 2,
            "symbols_unresolved_funding_prices": ["APTUSDT", "ARBUSDT"],
            "symbols_with_funding_coverage_gaps": 1, "symbols_funding_gap": ["APTUSDT"],
            "funding_sentinels": [{"symbol": "APTUSDT", "timestamp_ms": 1500,
                                   "reason": "missing_mark", "overlap_trade_ids": ["t1"],
                                   "overlap_trade_count": 1}],
            "unscorable_funding_trades": 1, "unscorable_funding_trade_ids": ["t1"],
            "time_exit_censored_setups": 2, "time_exit_censored_setup_ids": ["c1", "c2"],
            "symbols_without_bars": 3, "status": "unscorable", "detail": "fixture",
        }
        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "trials.csv"
            with patch("search_crypto.CSV_PATH", ledger):
                _append(row)
            with ledger.open(newline="", encoding="utf-8") as stream:
                record = next(csv.DictReader(stream))
        metric = json.loads(record["metric"])
        self.assertEqual(metric["symbols_with_unresolved_funding_prices"], 2)
        self.assertEqual(metric["symbols_unresolved_funding_prices"],
                         ["APTUSDT", "ARBUSDT"])
        self.assertEqual(metric["train_input_fingerprint"], fingerprint)
        self.assertEqual(metric["funding_sentinels"][0]["timestamp_ms"], 1500)
        self.assertEqual(metric["funding_sentinels"][0]["overlap_trade_ids"], ["t1"])
        self.assertEqual(metric["unscorable_funding_trades"], 1)
        self.assertEqual(metric["time_exit_censored_setups"], 2)
        self.assertNotIn("symbols_missing_funding_marks", metric)
        self.assertNotIn("symbols_excluded_missing_funding_marks", metric)
        self.assertNotIn("symbols_excluded_funding_gap", metric)
        self.assertEqual(set(metric), set(METRIC_FIELDS))
        self.assertIn(f"train_input_fingerprint={fingerprint}", record["notes"])

    def test_equity_round_one_search_grid_matches_preregistered_count(self):
        configs = _configs()
        self.assertEqual(len(configs), 68)
        self.assertEqual(sum(config["family"] == "C1" for config in configs), 32)
        self.assertEqual(sum(config["family"] == "C2" for config in configs), 4)
        self.assertEqual(sum(config["family"] == "C3" for config in configs), 16)
        self.assertEqual(sum(config["family"] == "C4" for config in configs), 16)
        self.assertEqual({config["family"] for config in configs}, {"C1", "C2", "C3", "C4"})

    def test_equity_mdd_aggregates_simultaneous_portfolio_exits(self):
        result = _max_drawdown([(1, 0.10), (1, -0.10), (2, -0.10)])
        self.assertAlmostEqual(result, 10.0)

    def test_equity_daily_curve_includes_unrealized_interim_drawdown(self):
        bars = [EquityBar(1 * 86_400_000, 100, 101, 99, 100),
                EquityBar(2 * 86_400_000, 100, 101, 79, 80),
                EquityBar(3 * 86_400_000, 80, 111, 79, 110)]
        trade = Trade("C1", 0, 0, 2, 100, 110, "target", .1, 20, .098)
        marks = _daily_trade_pnl(bars, trade, "US")
        self.assertAlmostEqual(sum(marks.values()), trade.net_return)
        self.assertLess(marks[2], -.19)

    def test_equity_weekly_bars_require_full_weekdays_and_mark_close_time(self):
        monday = int(datetime(2025, 10, 6, tzinfo=timezone.utc).timestamp() * 1000)
        complete = [Bar(monday + day * 86_400_000, 10, 11, 9, 10 + day, 1)
                    for day in range(5)]
        short_holiday_week = [Bar(monday + 7 * 86_400_000 + day * 86_400_000,
                                  10, 11, 9, 10, 1)
                              for day in (0, 1, 3, 4)]
        weekly = _weekly_bars(complete + short_holiday_week)
        self.assertEqual(len(weekly), 1)
        self.assertEqual(datetime.fromtimestamp(weekly[0].timestamp / 1000, timezone.utc),
                         datetime(2025, 10, 10, 23, 59, tzinfo=timezone.utc))

    def test_crypto_runner_preserves_exact_funding_timestamp(self):
        bars = [Bar(1000, 100, 101, 99, 100, 10),
                Bar(2000, 100, 101, 99, 100, 10)]
        event = FundingEvent(2000, 0.001, 100)
        self.assertEqual(_funding_by_timestamp(bars, {2000: event}), {2000: event})

    def test_crypto_runner_preserves_funding_inside_bar_interval(self):
        bars = [Bar(1000, 100, 101, 99, 100, 10),
                Bar(2000, 100, 101, 99, 100, 10)]
        event = FundingEvent(1500, 0.001, 100)
        self.assertEqual(_funding_by_timestamp(bars, {1500: event}), {1500: event})

    def test_crypto_runner_keeps_funding_at_last_candle_close_with_jitter(self):
        bars = [Bar(1000, 100, 101, 99, 100, 10),
                Bar(2000, 100, 101, 99, 100, 10)]
        event = FundingEvent(3009, 0.001, 100)
        self.assertEqual(_funding_by_timestamp(bars, {3009: event}, 1000), {3009: event})

    def test_crypto_runner_keeps_missing_mark_symbols_and_enforces_30_symbols(self):
        bars = [Bar(0, 100, 101, 99, 100, 10), Bar(900_000, 100, 101, 99, 100, 10)]
        missing = FundingEvent(0, 0.001, None)
        valid = [(f"S{i}", bars, {}, 0) for i in range(30)]
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            [*valid, ("MISSING", bars, {0: missing}, 0)], {},
        )
        self.assertEqual(result["symbols"], 31)
        self.assertEqual(result["symbols_with_unresolved_funding_prices"], 1)
        self.assertEqual(result["status"], "completed")
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            valid[:29], {},
        )
        self.assertEqual(result["status"], "unscorable")

    def test_crypto_runner_keeps_nonempty_symbol_with_funding_gap_sentinel(self):
        bars = [Bar(0, 100, 101, 99, 100, 10), Bar(900_000, 100, 101, 99, 100, 10)]
        gap = FundingEvent(0, 0.0, None, coverage_gap=True)
        valid = [(f"S{i}", bars, {}, 0) for i in range(30)]
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            [*valid, ("GAP", bars, {0: gap}, 0)], {},
        )
        self.assertEqual(result["symbols"], 31)
        self.assertEqual(result["symbols_with_funding_coverage_gaps"], 1)
        self.assertEqual(result["symbols_funding_gap"], ["GAP"])
        self.assertEqual(result["funding_sentinels"][0]["symbol"], "GAP")
        self.assertEqual(result["funding_sentinels"][0]["reason"], "missing_settlement")
        self.assertEqual(result["funding_sentinels"][0]["overlap_trade_count"], 0)
        self.assertEqual(result["status"], "completed")

    def test_any_trade_overlapping_missing_settlement_makes_trial_unscorable(self):
        bars = [Bar(i * 900_000, 100, 101, 99, 100, 10) for i in range(40)]
        # Confirm a pivot high, break it at bar 30 from a red origin candle,
        # retest the origin zone at bar 31, then enter and hit target at bar 32.
        bars[24] = Bar(24 * 900_000, 101, 103, 100, 102, 10)
        bars[29] = Bar(29 * 900_000, 101, 102, 100, 100.5, 10)
        bars[30] = Bar(30 * 900_000, 102, 105, 101, 104, 20)
        bars[31] = Bar(31 * 900_000, 103, 103.5, 100.5, 101, 10)
        bars[32] = Bar(32 * 900_000, 101, 104, 100.5, 103, 10)
        # Settlement is inside the target-exit candle, so ordering is unknown.
        gap_ts = bars[32].timestamp + 500
        gap = FundingEvent(gap_ts, 0.0, None, coverage_gap=True)
        barsets = [(f"S{i}", bars, {}, 0) for i in range(30)]
        barsets.append(("GAP", bars, {gap_ts: gap}, 0))
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            barsets, {},
        )
        self.assertGreater(result["trades"], 0)
        self.assertEqual(result["unscorable_funding_trades"], 1)
        self.assertEqual(result["status"], "unscorable")
        sentinel = next(item for item in result["funding_sentinels"]
                        if item["symbol"] == "GAP")
        self.assertEqual(sentinel["timestamp_ms"], gap_ts)
        self.assertEqual(sentinel["overlap_trade_count"], 1)
        self.assertEqual(len(sentinel["overlap_trade_ids"]), 1)

    def test_censored_setup_overlapping_missing_settlement_makes_trial_unscorable(self):
        bars = [Bar(i * 900_000, 100, 101, 99, 100, 10) for i in range(40)]
        bars[24] = Bar(24 * 900_000, 101, 103, 100, 102, 10)
        bars[29] = Bar(29 * 900_000, 101, 102, 100, 100.5, 10)
        bars[30] = Bar(30 * 900_000, 102, 105, 101, 104, 20)
        bars[31] = Bar(31 * 900_000, 103, 103.5, 100.5, 101, 10)
        for index in range(32, len(bars)):
            bars[index] = Bar(index * 900_000, 101, 101.2, 100.5, 101.1, 10)
        gap_ts = bars[35].timestamp + 500
        gap = FundingEvent(gap_ts, 0.0, None, coverage_gap=True)
        barsets = [(f"S{i}", bars, {}, 0) for i in range(30)]
        barsets.append(("GAP", bars, {gap_ts: gap}, 0))
        result = _run_trial(
            {"definition": "bos_origin", "deadline": 24, "direction": "long",
             "reward_r": 1.5, "timeframe": "15m"},
            barsets, {},
        )
        self.assertEqual(result["time_exit_censored_setups"], 31)
        self.assertEqual(result["unscorable_censored_setup_count"], 1)
        self.assertEqual(result["status"], "unscorable")
        sentinel = next(item for item in result["funding_sentinels"]
                        if item["symbol"] == "GAP")
        self.assertEqual(sentinel["censored_setup_count"], 1)


if __name__ == "__main__":
    unittest.main()
