"""Unit tests for the credentials-free crypto futures data collector."""
from __future__ import annotations

import unittest
import json
from unittest.mock import patch

from app import crypto_tick_stream


class CryptoTickStreamTests(unittest.TestCase):
    def test_stream_name_preserves_protocol_suffix_case(self) -> None:
        self.assertEqual(crypto_tick_stream._stream_name("BTC", "@markPrice@1s"), "btcusdt@markPrice@1s")
        self.assertEqual(crypto_tick_stream.FUTURES_WS_URL, "wss://fstream.binance.com/market/stream")

    def test_symbol_filter_limits_all_crypto_feeds(self) -> None:
        with patch.dict("os.environ", {"CRYPTO_TICK_BASES": "btc, ETH"}):
            self.assertEqual(crypto_tick_stream._configured_bases({"XRP", "DOGE"}), ["BTC", "ETH"])

    def test_symbol_filter_defaults_when_unset(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(crypto_tick_stream._configured_bases({"ETH", "BTC"}), ["BTC", "ETH"])

    def test_symbol_filter_rejects_invalid_symbols(self) -> None:
        with patch.dict("os.environ", {"CRYPTO_TICK_BASES": "BTC,../etc"}):
            with self.assertRaises(ValueError):
                crypto_tick_stream._configured_bases({"ETH"})

    def test_trade_record_preserves_exchange_flow_fields(self) -> None:
        event = {
            "E": 1_797_000_000_010,
            "T": 1_797_000_000_000,
            "t": 987654,
            "p": "67000.10",
            "q": "0.125",
            "m": True,
        }
        with patch.object(crypto_tick_stream, "now_iso", return_value="2026-10-18T03:00:00+00:00"):
            result = crypto_tick_stream._trade_record(event)

        self.assertEqual(result["price"], 67000.10)
        self.assertEqual(result["quantity"], 0.125)
        self.assertTrue(result["buyer_is_maker"])
        self.assertEqual(result["exchange_event_ts"], event["E"])
        self.assertEqual(result["trade_ts"], event["T"])
        self.assertEqual(result["trade_id"], event["t"])
        self.assertEqual(result["ts"], "2026-10-18T03:00:00+00:00")

    def test_aggregate_trade_event_is_parsed_for_futures_strategy_feed(self) -> None:
        perp_buffer: dict[str, list[dict]] = {}
        funding_buffer: dict[str, list[dict]] = {}
        event = {
            "e": "aggTrade", "s": "BTCUSDT", "E": 1_797_000_000_010,
            "T": 1_797_000_000_000, "a": 987654, "p": "67000.10", "q": "0.125", "m": False,
        }
        with patch.object(crypto_tick_stream, "now_iso", return_value="2026-10-18T03:00:00+00:00"):
            crypto_tick_stream._handle_futures_message(json.dumps({"data": event}), perp_buffer, funding_buffer)

        self.assertEqual(perp_buffer["BTC"][0]["trade_id"], 987654)
        self.assertEqual(perp_buffer["BTC"][0]["price"], 67000.10)
        self.assertEqual(perp_buffer["BTC"][0]["quantity"], 0.125)

    def test_mark_price_handler_preserves_funding_and_exchange_times(self) -> None:
        perp_buffer: dict[str, list[dict]] = {}
        funding_buffer: dict[str, list[dict]] = {}
        event = {
            "e": "markPriceUpdate",
            "s": "BTCUSDT",
            "E": 1_797_000_000_010,
            "T": 1_797_000_800_000,
            "p": "67001.25",
            "r": "0.00010000",
        }
        with patch.object(crypto_tick_stream, "now_iso", return_value="2026-10-18T03:00:00+00:00"):
            crypto_tick_stream._handle_futures_message(json.dumps({"data": event}), perp_buffer, funding_buffer)

        record = funding_buffer["BTC"][0]
        self.assertEqual(record["mark_price"], 67001.25)
        self.assertEqual(record["funding_rate"], 0.0001)
        self.assertEqual(record["exchange_event_ts"], event["E"])
        self.assertEqual(record["next_funding_ts"], event["T"])
        self.assertEqual(record["mark_price_raw"], event["p"])
        self.assertEqual(record["funding_rate_raw"], event["r"])


if __name__ == "__main__":
    unittest.main()
