"""Historical OHLCV candles from Binance USDT-margined (USDⓈ-M) perpetual futures via ccxt's
public endpoint (no API key needed). Symbol format is ccxt's unified notation, e.g.
"BTC/USDT:USDT" — not the spot "BTC/USDT".

IMPORTANT DISCLOSED LIMITATION: this only replays OHLCV price action. It does NOT model
funding rate payments (paid/received every 8h based on position direction and market
skew), which can materially erode or help returns for a strategy that holds directional
positions across funding intervals. Any positive backtest result here should be treated
as an upper bound until funding cost is added — do not present futures backtest returns
as realistic without this caveat.
"""
from __future__ import annotations

import time

import ccxt
import pandas as pd

from app.data import _parse_ts

MAX_PAGES = 800


def fetch_perp_ohlcv(
    symbol: str, timeframe: str, since_iso: str, until_iso: str | None = None,
    exchange: ccxt.binance | None = None,
) -> pd.DataFrame:
    # exchange를 안 넘기면(기존 호출부 전부 해당) 예전처럼 매번 새로 만든다 — 하위호환. 여러
    # 종목을 한 사이클에서 연속 조회하는 호출부(coin_swing6_trade.py)는 미리 만든 인스턴스를
    # 넘겨서 load_markets()/exchangeInfo 재호출을 종목 수만큼 반복하지 않게 한다(ccxt는 인스턴스
    # 안에 마켓 캐시를 들고 있어서, 인스턴스를 재사용하면 최초 1회만 적중한다).
    if exchange is None:
        exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})
    since = _parse_ts(exchange, since_iso)
    until = _parse_ts(exchange, until_iso) if until_iso else exchange.milliseconds()
    rows: list[list[float]] = []
    for _ in range(MAX_PAGES):
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        last_ts = batch[-1][0]
        if last_ts >= until or len(batch) < 2:
            break
        since = last_ts + 1
        time.sleep(exchange.rateLimit / 1000)

    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    frame = pd.DataFrame(rows, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    frame = frame.drop_duplicates(subset="timestamp").sort_values("timestamp")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame = frame.set_index("timestamp")
    return frame[frame.index <= pd.Timestamp(until, unit="ms", tz="UTC")]
