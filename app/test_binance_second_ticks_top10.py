"""Read-only Binance Spot test: discover top-10 USDT pairs, then print 1s trade data.

No API key, account access, orders, or local data files are used. Discovery uses
one public REST ticker snapshot; prices are streamed from the public per-symbol
@trade WebSocket for the selected pairs. REST is never polled.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import websockets

SPOT_WS = "wss://stream.binance.com:9443/stream"
SPOT_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
EXCLUDED_BASES = {
    "USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "EUR", "USD1", "USDP",
    "PYUSD", "USDE", "WBTC", "WETH",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Binance 현물 거래량 상위 종목 초단위 체결 수신 확인")
    parser.add_argument("--top", type=int, default=10, help="거래대금 상위 종목 수 (기본값: 10)")
    parser.add_argument("--test-seconds", type=int, default=60, help="체결 스트림 테스트 시간 (기본값: 60초)")
    parser.add_argument("--continuous", action="store_true", help="중단할 때까지 연결을 유지하고 자동 재접속")
    parser.add_argument("--reconnect-hours", type=float, default=1.0, help="정상 연결 교체 주기 (기본값: 1시간)")
    parser.add_argument("--ranking-refresh-hours", type=float, default=24.0, help="상위 종목 재선정 주기 (기본값: 24시간)")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs/binance_tick_verification.jsonl"),
        help="연속 검증 JSONL 로그 경로",
    )
    return parser.parse_args()


def discover_top_symbols(limit: int) -> list[tuple[str, float]]:
    """Rank USDT spot pairs by 24h quote volume from one public REST snapshot."""
    response = requests.get(SPOT_TICKER_URL, timeout=10)
    response.raise_for_status()
    payload: Any = response.json()
    ranked: list[tuple[str, float]] = []
    for ticker in payload:
        symbol = ticker.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        base = symbol[:-4]
        if base in EXCLUDED_BASES:
            continue
        try:
            quote_volume = float(ticker["quoteVolume"])
            last_price = float(ticker["lastPrice"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0.98 <= last_price <= 1.02:
            continue
        ranked.append((symbol, quote_volume))
    ranked.sort(key=lambda item: item[1], reverse=True)
    if len(ranked) < limit:
        raise RuntimeError(f"상위 {limit}개를 고를 ticker 데이터가 부족함: {len(ranked)}개")
    return ranked[:limit]


async def stream_second_buckets(symbols: list[str], duration: int) -> None:
    streams = "/".join(f"{symbol.lower()}@trade" for symbol in symbols)
    url = f"{SPOT_WS}?streams={streams}"
    buckets: dict[tuple[int, str], dict[str, float | int]] = defaultdict(
        lambda: {"last": 0.0, "trades": 0, "base_volume": 0.0, "quote_volume": 0.0}
    )
    end_at = time.monotonic() + duration
    print("\n[초단위 체결 출력] 시각은 Binance trade time(UTC) 기준")
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        while time.monotonic() < end_at:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, end_at - time.monotonic()))
            except asyncio.TimeoutError:
                break
            message = json.loads(raw)
            trade = message.get("data", {})
            symbol = trade.get("s", "")
            try:
                second = int(trade["T"]) // 1000
                price = float(trade["p"])
                quantity = float(trade["q"])
            except (KeyError, TypeError, ValueError):
                continue
            bucket = buckets[(second, symbol)]
            bucket["last"] = price
            bucket["trades"] += 1
            bucket["base_volume"] += quantity
            bucket["quote_volume"] += price * quantity

    for (second, symbol), data in sorted(buckets.items()):
        ts = datetime.fromtimestamp(second, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{ts}Z  {symbol:12} last={data['last']:.10g}  "
            f"trades={int(data['trades']):5d}  "
            f"volume={data['base_volume']:.8g}  "
            f"quote={data['quote_volume']:.2f} USDT"
        )


def emit_log(log_file: Path, event: dict[str, Any]) -> None:
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    print(line, flush=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as output:
        output.write(line + "\n")


async def run_stream_session(
    ws: Any,
    symbols: list[str],
    log_file: Path,
    max_seconds: float,
) -> str:
    """Log compact per-second aggregates until the socket closes or rotation is due."""
    start = time.monotonic()
    rotation_at = start + max_seconds
    pending: dict[int, dict[str, dict[str, float | int]]] = defaultdict(dict)
    next_second = int(time.time())

    def emit_through(last_second: int) -> None:
        nonlocal next_second
        while next_second <= last_second:
            second = next_second
            tick_data = pending.pop(second, {})
            emit_log(
                log_file,
                {
                    "type": "ticks",
                    "utc": datetime.fromtimestamp(second, tz=timezone.utc).isoformat(),
                    "ticks": tick_data,
                },
            )
            next_second += 1

    while time.monotonic() < rotation_at:
        timeout = min(1.0, max(0.05, rotation_at - time.monotonic()))
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            emit_through(int(time.time()) - 1)
            if time.monotonic() >= rotation_at:
                return "scheduled_rotation"
            continue

        message = json.loads(raw)
        trade = message.get("data", {})
        symbol = trade.get("s", "")
        if symbol not in symbols:
            continue
        try:
            second = int(trade["T"]) // 1000
            price = float(trade["p"])
            quantity = float(trade["q"])
        except (KeyError, TypeError, ValueError):
            continue
        if second < next_second:
            continue
        bucket = pending[second].setdefault(
            symbol, {"last": price, "trades": 0, "base_volume": 0.0, "quote_volume": 0.0}
        )
        bucket["last"] = price
        bucket["trades"] += 1
        bucket["base_volume"] += quantity
        bucket["quote_volume"] += price * quantity
        emit_through(second - 1)

    emit_through(int(time.time()) - 1)
    return "scheduled_rotation"


async def run_continuously(args: argparse.Namespace) -> None:
    if args.reconnect_hours <= 0 or args.ranking_refresh_hours <= 0:
        raise SystemExit("--reconnect-hours와 --ranking-refresh-hours는 0보다 커야 합니다.")

    cached_ranked: list[tuple[str, float]] | None = None
    refresh_ranking_at = 0.0
    retry_seconds = 1
    session_limit = args.reconnect_hours * 60 * 60
    while True:
        try:
            if cached_ranked is None or time.monotonic() >= refresh_ranking_at:
                cached_ranked = discover_top_symbols(args.top)
                refresh_ranking_at = time.monotonic() + args.ranking_refresh_hours * 60 * 60
                emit_log(
                    args.log_file,
                    {
                        "type": "ranking",
                        "utc": datetime.now(timezone.utc).isoformat(),
                        "basis": "Binance Spot USDT 24h quote volume",
                        "symbols": [
                            {"symbol": symbol, "quote_volume_24h": volume}
                            for symbol, volume in cached_ranked
                        ],
                    },
                )

            symbols = [symbol for symbol, _ in cached_ranked]
            streams = "/".join(f"{symbol.lower()}@trade" for symbol in symbols)
            url = f"{SPOT_WS}?streams={streams}"
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                retry_seconds = 1
                emit_log(
                    args.log_file,
                    {
                        "type": "connected",
                        "utc": datetime.now(timezone.utc).isoformat(),
                        "symbols": symbols,
                        "planned_rotation_hours": args.reconnect_hours,
                    },
                )
                reason = await run_stream_session(ws, symbols, args.log_file, session_limit)
                if reason == "scheduled_rotation":
                    emit_log(
                        args.log_file,
                        {
                            "type": "planned_reconnect",
                            "utc": datetime.now(timezone.utc).isoformat(),
                            "ranking_refresh_hours": args.ranking_refresh_hours,
                        },
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — verifier recovers from socket/API failures.
            emit_log(
                args.log_file,
                {
                    "type": "connection_error",
                    "utc": datetime.now(timezone.utc).isoformat(),
                    "error": f"{type(exc).__name__}: {exc}",
                    "retry_in_seconds": retry_seconds,
                },
            )
            await asyncio.sleep(retry_seconds)
            retry_seconds = min(retry_seconds * 2, 60)


async def main() -> None:
    args = parse_args()
    if args.top < 1 or (not args.continuous and args.test_seconds < 1):
        raise SystemExit("--top과 --test-seconds는 모두 1 이상이어야 합니다.")

    if args.continuous:
        await run_continuously(args)
        return

    print(
        f"Binance 현물 USDT 거래대금 상위 {args.top}개 선정 중 "
        "(공개 REST 조회 1회, 가격은 WebSocket)...",
        flush=True,
    )
    ranked = discover_top_symbols(args.top)
    for rank, (symbol, quote_volume) in enumerate(ranked, start=1):
        print(f"{rank:2d}. {symbol:12} 24h_quote_volume={quote_volume:,.0f} USDT")

    print(f"\n선택 종목 체결 스트림을 {args.test_seconds}초 수신합니다...", flush=True)
    await stream_second_buckets([symbol for symbol, _ in ranked], args.test_seconds)


if __name__ == "__main__":
    asyncio.run(main())
