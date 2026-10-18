"""Historical OHLCV candles from Binance spot via ccxt's public endpoint (no API key needed)."""
from __future__ import annotations

import time

import ccxt
import pandas as pd

# Safety cap on pagination loops: 800 pages * up to 1000 candles covers several years of
# 15m candles with room to spare, without risking an unbounded loop on unexpected API responses.
MAX_PAGES = 800


def _parse_ts(exchange: "ccxt.Exchange", value: str | None) -> int | None:
    """ISO8601 문자열을 ms 타임스탬프로. 'YYYY-MM-DD' 처럼 시간이 빠진 값도 허용
    (ccxt.parse8601 은 시간 없는 날짜에 None 을 돌려줘서 무한/잘못된 페이지네이션을 유발한다)."""
    if not value:
        return None
    ts = exchange.parse8601(value)
    if ts is None:
        ts = exchange.parse8601(f"{value}T00:00:00Z")
    if ts is None:
        raise ValueError(f"파싱 불가한 날짜: {value!r}")
    return ts


def fetch_ohlcv(symbol: str, timeframe: str, since_iso: str, until_iso: str | None = None) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})
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
