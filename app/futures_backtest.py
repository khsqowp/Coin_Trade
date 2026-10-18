"""롱/숏 선물 전략 백테스트 CLI — app/futures_strategies.py의 LongShortTrendStrategy를
바이낸스 무기한 스왑 데이터로 테스트하고 매수·보유와 비교한다.

정직하게 명시: 펀딩비 미반영(app/futures_data.py 참고). 여기 수익률은 낙관적 상한선이다.
"""
from __future__ import annotations

import argparse

from backtesting import Backtest

from app.extra_indicators import add_supertrend_indicators
from app.futures_data import fetch_perp_ohlcv
from app.futures_strategies import LongShortTrendStrategy

MIN_USABLE_BARS = 250


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="롱/숏 선물 추세추종 전략 테스트")
    parser.add_argument("--symbols", default="BTC/USDT:USDT,ETH/USDT:USDT")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--since", default="2022-01-01T00:00:00Z")
    parser.add_argument("--until", default=None)
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--commission", type=float, default=0.0005)  # Binance USDⓈ-M perp taker fee (VIP 0)
    parser.add_argument("--min-adx", type=float, default=0, help="진입 시점 최소 ADX (0이면 필터 비활성)")
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    print("*** 주의: 펀딩비 미반영 — 아래 수익률은 낙관적 상한선입니다 ***\n")
    for symbol in [s.strip() for s in args.symbols.split(",")]:
        print(f"[데이터] {symbol} {args.timeframe} 캔들 수집 중...")
        frame = fetch_perp_ohlcv(symbol, args.timeframe, args.since, args.until)
        if frame.empty or len(frame) < MIN_USABLE_BARS:
            print(f"  {symbol}: 데이터 부족, 건너뜀")
            continue
        enriched = add_supertrend_indicators(frame).dropna()
        if len(enriched) < MIN_USABLE_BARS:
            print(f"  {symbol}: 워밍업 이후 데이터 부족, 건너뜀")
            continue

        stats = Backtest(enriched, LongShortTrendStrategy, cash=args.cash,
                          commission=args.commission, exclusive_orders=True).run(MIN_ADX_ENTRY=args.min_adx)
        ret = stats.get("Return [%]", float("nan"))
        bh = stats.get("Buy & Hold Return [%]", float("nan"))
        pf = stats.get("Profit Factor", float("nan"))
        mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
        trades = stats.get("# Trades", 0)
        sharpe = stats.get("Sharpe Ratio", float("nan"))
        sortino = stats.get("Sortino Ratio", float("nan"))
        calmar = stats.get("Calmar Ratio", float("nan"))
        print(f"  [{symbol}] 수익률 {ret:.2f}% (매수보유 {bh:.2f}%, 초과 {ret - bh:+.2f}%p) "
              f"PF {pf:.2f} MDD {mdd:.2f}% 거래 {trades}건 "
              f"Sharpe {sharpe:.2f} Sortino {sortino:.2f} Calmar {calmar:.2f}")


if __name__ == "__main__":
    run(parse_args())
