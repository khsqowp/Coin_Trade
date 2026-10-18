"""Runs every strategy in app/registry.py against multiple symbols (BTC/ETH plus
sufficiently-liquid altcoins picked by real trading volume) and prints a comparison
table. This is a research/exploration tool — none of these results should be treated
as validated until a strategy clears the gate in docs/trading-agent-plan.md on the
full history AND survives a genuine out-of-sample walk-forward split.
"""
from __future__ import annotations

import argparse

from backtesting import Backtest

from app.data import fetch_ohlcv
from app.markets import top_liquid_altcoins
from app.registry import STRATEGIES

MIN_PROFIT_FACTOR = 1.25
MAX_DRAWDOWN_PCT = 10.0
MIN_TRADES = 300
MIN_USABLE_BARS = 250


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="여러 전략 x 여러 심볼 비교 백테스트")
    parser.add_argument("--symbols", default=None, help="쉼표로 구분한 심볼 목록 (예: BTC/USDT,ETH/USDT). 생략하면 BTC/ETH + 거래량 상위 알트코인을 자동 선택")
    parser.add_argument("--altcoin-count", type=int, default=5)
    parser.add_argument("--min-quote-volume", type=float, default=5_000_000, help="알트코인 자동 선택시 최소 24시간 거래대금(USDT)")
    parser.add_argument("--since", default="2022-01-01T00:00:00Z")
    parser.add_argument("--until", default=None)
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--commission", type=float, default=0.001)
    return parser.parse_args()


def resolve_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        return [s.strip() for s in args.symbols.split(",")]
    core = ["BTC/USDT", "ETH/USDT"]
    print(f"거래량 상위 알트코인 {args.altcoin_count}개 조회 중 (최소 24h 거래대금 {args.min_quote_volume:,.0f} USDT)...")
    altcoins = top_liquid_altcoins(limit=args.altcoin_count, exclude={"BTC", "ETH"}, min_quote_volume=args.min_quote_volume)
    print(f"  선택됨: {altcoins}")
    return core + altcoins


def run(args: argparse.Namespace) -> None:
    symbols = resolve_symbols(args)
    data_cache: dict[tuple[str, str], object] = {}
    results: list[dict] = []

    for name, strategy_cls, timeframe, indicator_fn in STRATEGIES:
        for symbol in symbols:
            cache_key = (symbol, timeframe)
            if cache_key not in data_cache:
                print(f"[데이터] {symbol} {timeframe} 캔들 수집 중...")
                data_cache[cache_key] = fetch_ohlcv(symbol, timeframe, args.since, args.until)
            frame = data_cache[cache_key]
            if frame.empty or len(frame) < MIN_USABLE_BARS:
                print(f"  {name} / {symbol} ({timeframe}): 데이터 부족, 건너뜀")
                continue

            enriched = indicator_fn(frame).dropna()
            if len(enriched) < MIN_USABLE_BARS:
                print(f"  {name} / {symbol} ({timeframe}): 워밍업 이후 데이터 부족, 건너뜀")
                continue

            try:
                stats = Backtest(enriched, strategy_cls, cash=args.cash, commission=args.commission, exclusive_orders=True).run()
            except Exception as exc:  # noqa: BLE001 — 한 조합이 실패해도 나머지 비교는 계속 진행
                print(f"  [오류] {name} / {symbol}: {exc}")
                continue

            results.append(_summarize(name, symbol, timeframe, stats))
            row = results[-1]
            print(f"  [{name} / {symbol}] 수익률 {row['return_pct']:.2f}% (매수보유 {row['buy_hold_pct']:.2f}%) · "
                  f"PF {row['profit_factor']:.2f} · MDD {row['max_drawdown_pct']:.2f}% · 거래 {row['trades']}건 · "
                  f"게이트 {'PASS' if row['gate_pass'] else 'FAIL'}")

    _print_summary(results)


def _summarize(name: str, symbol: str, timeframe: str, stats) -> dict:
    profit_factor = stats.get("Profit Factor", float("nan"))
    max_drawdown = abs(stats.get("Max. Drawdown [%]", float("inf")))
    trades = stats.get("# Trades", 0)
    passed = profit_factor >= MIN_PROFIT_FACTOR and max_drawdown <= MAX_DRAWDOWN_PCT and trades >= MIN_TRADES
    return {
        "strategy": name, "symbol": symbol, "timeframe": timeframe,
        "return_pct": stats.get("Return [%]", float("nan")),
        "buy_hold_pct": stats.get("Buy & Hold Return [%]", float("nan")),
        "profit_factor": profit_factor, "max_drawdown_pct": max_drawdown,
        "trades": trades, "gate_pass": passed,
    }


def _sort_key(row: dict) -> float:
    pf = row["profit_factor"]
    return -pf if pf == pf else 0  # NaN-safe (NaN != NaN)


def _print_summary(results: list[dict]) -> None:
    if not results:
        print("\n비교할 결과가 없습니다 (데이터 부족으로 전부 건너뜀).")
        return
    print("\n=== 전략 비교 요약 (Profit Factor 내림차순) ===")
    print(f"{'전략':<16}{'심볼':<12}{'주기':<6}{'수익률':>9}{'매수보유':>10}{'PF':>7}{'MDD':>8}{'거래수':>8}  게이트")
    for row in sorted(results, key=_sort_key):
        print(f"{row['strategy']:<16}{row['symbol']:<12}{row['timeframe']:<6}{row['return_pct']:>8.2f}%"
              f"{row['buy_hold_pct']:>9.2f}%{row['profit_factor']:>7.2f}{row['max_drawdown_pct']:>7.2f}%"
              f"{row['trades']:>8}  {'PASS' if row['gate_pass'] else 'FAIL'}")

    passed = [row for row in results if row["gate_pass"]]
    if passed:
        print(f"\n게이트 통과: {len(passed)}건 — " + ", ".join(f"{row['strategy']}/{row['symbol']}" for row in passed))
    else:
        print("\n게이트를 통과한 조합이 없습니다 — 파라미터 재검토 필요, 실거래 코드로 넘어가지 말 것.")


if __name__ == "__main__":
    run(parse_args())
