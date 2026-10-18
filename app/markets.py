"""Binance spot market discovery — picks sufficiently liquid altcoins by real trading
volume instead of a hardcoded symbol list, per the requirement to only test coins
with enough volume to actually trade."""
from __future__ import annotations

import ccxt

# 방향성 매매 대상이 아닌 스테이블코인/랩드 자산 등은 제외한다.
_EXCLUDE_BASES = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "EUR", "WBTC", "WETH", "WBETH"}


def top_liquid_altcoins(quote: str = "USDT", limit: int = 5, exclude: set[str] | None = None,
                         min_quote_volume: float = 5_000_000) -> list[str]:
    """24시간 거래대금(quoteVolume) 기준 상위 N개 알트코인 심볼을 반환한다."""
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
    markets = exchange.load_markets()
    tickers = exchange.fetch_tickers()
    exclude_bases = _EXCLUDE_BASES | (exclude or set())

    candidates: list[tuple[str, float]] = []
    for symbol, market in markets.items():
        if not market.get("spot") or market.get("quote") != quote:
            continue
        base = market.get("base")
        if base in exclude_bases:
            continue
        ticker = tickers.get(symbol)
        if not ticker:
            continue
        quote_volume = ticker.get("quoteVolume") or 0
        if quote_volume < min_quote_volume:
            continue
        candidates.append((symbol, quote_volume))

    candidates.sort(key=lambda item: item[1], reverse=True)
    return [symbol for symbol, _ in candidates[:limit]]
