import unittest
import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from crypto import Bar, FundingEvent, Setup, Trade, Zone
from search_crypto import _filter_r3_zones, _sentinel_reason
import search_crypto
from trial_ledger_compaction import compact_id_list
from search_crypto_r3 import (CONFIGS, _append_r3, _apply_symbol_floor,
                              FUNDING_ORDER_POLICY, exclude_unscorable_symbols)


class SearchCryptoR3Tests(unittest.TestCase):
    def test_fallback_price_is_not_a_missing_mark_sentinel(self):
        event = FundingEvent(1, 0.001, 100.25,
                             used_candle_close_fallback=True)
        self.assertIsNone(_sentinel_reason(event))

    def test_grid_has_exactly_48_unique_registered_configs(self):
        keys = {tuple(sorted(config.items())) for config in CONFIGS}
        self.assertEqual(len(CONFIGS), 48)
        self.assertEqual({config["funding_order_policy"] for config in CONFIGS},
                         {"adverse_only"})
        self.assertEqual(len(keys), 48)
        self.assertEqual({config["definition"] for config in CONFIGS},
                         {"displacement", "bos_origin", "volume_displacement"})

    def test_exclusion_drops_unresolved_marks_gaps_and_empty_train(self):
        bars = [Bar(0, 10, 11, 9, 10, 1)]
        barsets = [
            ("GOOD", bars, {1: FundingEvent(1, 0.0, 10)}, 0),
            ("NO_MARK", bars, {1: FundingEvent(1, 0.0, None)}, 0),
            ("GAP", bars, {1: FundingEvent(1, 0.0, 10, coverage_gap=True)}, 0),
            ("NAN_MARK", bars, {1: FundingEvent(1, 0.0, float("nan"))}, 0),
            ("INFINITE_MARK", bars, {1: FundingEvent(1, 0.0, float("inf"))}, 0),
            ("ZERO_MARK", bars, {1: FundingEvent(1, 0.0, 0)}, 0),
            ("EMPTY", [], {}, 0),
        ]
        kept, funding_excluded, empty_excluded = exclude_unscorable_symbols(barsets)
        self.assertEqual([item[0] for item in kept],
                         ["GOOD", "NO_MARK", "GAP", "NAN_MARK", "INFINITE_MARK", "ZERO_MARK"])
        self.assertEqual(funding_excluded, [])
        self.assertEqual(empty_excluded, ["EMPTY"])

    def test_funding_symbol_is_flagged_only_for_a_real_overlapping_trade(self):
        bars = [Bar(0, 10, 11, 9, 10, 1), Bar(14_400_000, 10, 11, 9, 10, 1)]
        zone = Zone(0, 0, "long", 9, 10, 1)
        setup = Setup(zone, 0, 10, 9, 12)
        sentinel = FundingEvent(1_000_000, 0.0, None)
        fake_trade = Trade(setup, 1, 11, "time", 0.1, None, 12, None)
        config = {"definition": "displacement", "timeframe": "4h",
                  "direction": "long", "deadline": 48, "reward_r": 2.0,
                  "minimum_symbols": 1, "trend_filter": "none", "session_filter": "none"}
        with patch.object(search_crypto, "active_zones", return_value=[zone]), \
                patch.object(search_crypto, "_filter_r3_zones", return_value=[zone]), \
                patch.object(search_crypto, "first_retest", return_value=setup), \
                patch.object(search_crypto, "simulate_trade", return_value=fake_trade):
            overlapping = search_crypto._run_trial(
                config, [("BTCUSDT", bars, {sentinel.timestamp: sentinel}, 0)], {})
            outside = search_crypto._run_trial(
                config, [("BTCUSDT", bars,
                          {15_000_000: FundingEvent(15_000_000, 0, None)}, 0)], {})
        self.assertEqual(overlapping["excluded_funding_symbols"], ["BTCUSDT"])
        self.assertEqual(outside["excluded_funding_symbols"], [])
        self.assertEqual(outside["unscorable_funding_trades"], 1)
        self.assertEqual(outside["unscorable_funding_trade_id_summary"],
                         outside["trade_id_summary"])
        self.assertEqual(overlapping["total_trades"], 1)
        self.assertEqual(overlapping["trades"], 0)
        self.assertEqual(overlapping["unscorable_funding_trades"], 0)
        self.assertEqual(overlapping["censored_funding_trades"], 1)
        self.assertEqual(overlapping["unscorable_funding_trade_id_summary"],
                         compact_id_list([]))
        self.assertEqual(overlapping["censored_funding_trade_id_summary"]["count"], 1)
        self.assertEqual(overlapping["trade_id_summary"]["count"], 1)

    def test_r3_passes_adverse_policy_and_scores_unknown_order_settlement(self):
        bars = [Bar(0, 10, 11, 9, 10, 1), Bar(14_400_000, 10, 11, 9, 10, 1)]
        zone = Zone(0, 0, "long", 9, 10, 1)
        setup = Setup(zone, 0, 10, 9, 12)
        # Valid mark, with settlement ordering ambiguity handled by R3 policy.
        event = FundingEvent(14_400_000, 0.001, 100)
        trade = Trade(setup, 1, 11, "time", 0.1, None, 12, 0.09,
                      funding_order_policy="adverse_only", ambiguous_funding_events=1)
        config = {"definition": "displacement", "timeframe": "4h",
                  "direction": "long", "deadline": 48, "reward_r": 2.0,
                  "minimum_symbols": 1, "funding_order_policy": FUNDING_ORDER_POLICY}
        with patch.object(search_crypto, "active_zones", return_value=[zone]), \
                patch.object(search_crypto, "_filter_r3_zones", return_value=[zone]), \
                patch.object(search_crypto, "first_retest", return_value=setup), \
                patch.object(search_crypto, "simulate_trade", return_value=trade) as simulate, \
                patch.object(search_crypto, "trade_daily_pnl", return_value={0: trade.net_return}):
            result = search_crypto._run_trial(
                config, [("BTCUSDT", bars, {event.timestamp: event}, 0)], {})

        self.assertEqual(FUNDING_ORDER_POLICY, "adverse_only")
        self.assertEqual(simulate.call_args.kwargs["funding_order_policy"], "adverse_only")
        self.assertEqual(result["total_trades"], 1)
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["unscorable_funding_trades"], 0)
        self.assertEqual(result["unscorable_funding_trade_id_summary"]["count"], 0)
        self.assertEqual(result["censored_funding_trades"], 0)
        self.assertEqual(result["censored_fraction"], 0.0)
        self.assertEqual(result["funding_sentinels"], [])

    def test_symbol_floor_requires_25_kept_symbols(self):
        result = {"status": "complete", "detail": "", "trades": 20,
                  "censored_fraction": 0.35}
        self.assertIs(_apply_symbol_floor(result, 25, 25), result)
        self.assertEqual(result["status"], "complete")
        _apply_symbol_floor(result, 25, 24)
        self.assertEqual(result["status"], "unscorable")
        self.assertEqual(result["detail"], "only 24 kept symbols; need 25")

    def test_censoring_is_independent_of_trade_pnl(self):
        bars = [Bar(0, 10, 11, 9, 10, 1), Bar(14_400_000, 10, 11, 9, 10, 1)]
        zone = Zone(0, 0, "long", 9, 10, 1)
        setup = Setup(zone, 0, 10, 9, 12)
        sentinel = FundingEvent(1_000_000, 0.0, None)
        config = {"definition": "displacement", "timeframe": "4h", "direction": "long",
                  "deadline": 48, "reward_r": 2.0, "minimum_symbols": 1}
        outcomes = []
        for pnl in (0.1, -0.1):
            fake_trade = Trade(setup, 1, 11, "time", pnl, None, 12, pnl)
            with patch.object(search_crypto, "active_zones", return_value=[zone]), \
                    patch.object(search_crypto, "_filter_r3_zones", return_value=[zone]), \
                    patch.object(search_crypto, "first_retest", return_value=setup), \
                    patch.object(search_crypto, "simulate_trade", return_value=fake_trade):
                outcomes.append(search_crypto._run_trial(
                    config, [("BTCUSDT", bars, {sentinel.timestamp: sentinel}, 0)], {}))
        self.assertEqual(outcomes[0]["censored_funding_trades"], 1)
        self.assertEqual(outcomes[1]["censored_funding_trades"], 1)
        self.assertEqual(outcomes[0]["censored_funding_trade_id_summary"],
                         outcomes[1]["censored_funding_trade_id_summary"])

    def test_censor_and_remaining_trade_threshold_boundaries(self):
        result = {"status": "completed", "detail": "", "trades": 20,
                  "censored_fraction": 0.35}
        _apply_symbol_floor(result, 25, 25)
        self.assertEqual(result["status"], "completed")
        result.update(trades=19)
        _apply_symbol_floor(result, 25, 25)
        self.assertEqual(result["status"], "unscorable")
        self.assertIn("remaining trades 19 below minimum 20", result["detail"])
        result.update(status="completed", detail="", trades=20, censored_fraction=0.350001)
        _apply_symbol_floor(result, 25, 25)
        self.assertEqual(result["status"], "unscorable")
        self.assertIn("censored_fraction", result["detail"])

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
                _append_r3(config, result, "f" * 64)
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertNotEqual(rows[0]["trial_id"], rows[1]["trial_id"])
        self.assertTrue(row["trial_id"].startswith("R3-coin-reregistered-"))
        self.assertEqual(row["round"], "R3-coin")
        self.assertEqual(row["market_group"], "crypto")
        self.assertEqual(json.loads(row["definition"]), config)
        metric = json.loads(row["metric"])
        self.assertEqual(metric["kept_symbols"], 0)
        self.assertEqual(metric["excluded_funding_symbols"], ["BAD"])
        self.assertEqual(metric["train_input_fingerprint"], "f" * 64)


if __name__ == "__main__":
    unittest.main()
