import pytest
from bundle import build_bundle
from run_tick import FixtureExchange
from http_client import BanError, ExchangeError


def test_intervals_and_interest_fail_soft(ledger, cfg):
    cfg.watchlist = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    cfg.core_symbols = ["BTCUSDT"]

    class Exchange(FixtureExchange):
        def __init__(self):
            super().__init__(
                {
                    "premium_index": [
                        {"symbol": s, "markPrice": "100", "lastFundingRate": "0.001"}
                        for s in cfg.watchlist
                    ],
                    "symbol_info": ledger.symbol_info,
                },
                ledger.now,
            )
            self.calls = []

        def klines(self, symbol, interval, limit=250):
            self.calls.append((symbol, interval))
            return []

        def open_interest(self, symbol):
            raise ExchangeError(500, "mock failure")

    exchange = Exchange()
    bundle = build_bundle(exchange, ledger, cfg, ledger.now)
    assert [i for s, i in exchange.calls if s == "BTCUSDT"] == ["15m", "1h", "4h", "1d"]
    assert [i for s, i in exchange.calls if s == "SOLUSDT"] == ["1h", "4h"]
    assert bundle["symbols"]["BTCUSDT"]["open_interest"] is None
    assert bundle["account"]["virtual_equity"] == 1000

    class Banned(Exchange):
        def open_interest(self, symbol):
            raise BanError(ledger.now + 100)

    with pytest.raises(BanError):
        build_bundle(Banned(), ledger, cfg, ledger.now)
