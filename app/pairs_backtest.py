"""페어 트레이딩(통계적 차익거래) 백테스트 CLI — app/pairs_strategies.py의
PairsMeanReversionStrategy를 두 자산의 가격 비율에 대해 테스트한다.

여기서 "매수·보유" 비교는 "두 자산을 50/50 롱/숏으로 고정 보유했을 때"에 해당한다 —
동적 평균회귀 매매가 정적 포지션보다 나은지를 보여주는 의미 있는 기준선이다.
"""
from __future__ import annotations

import argparse

from backtesting import Backtest

from app.data import fetch_ohlcv
from app.pairs_data import build_ratio_frame
from app.pairs_strategies import PairsMeanReversionStrategy

MIN_USABLE_BARS = 250


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="페어 트레이딩(통계적 차익거래) 전략 테스트")
    parser.add_argument("--pairs", default="BTC/USDT-ETH/USDT,BTC/USDT-SOL/USDT,ETH/USDT-SOL/USDT",
                         help="쉼표 구분, 각 페어는 'A-B' 형식 (예: BTC/USDT-ETH/USDT)")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--since", default="2022-01-01T00:00:00Z")
    parser.add_argument("--until", default=None)
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--commission", type=float, default=0.001)
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    data_cache: dict[str, object] = {}
    for pair in [p.strip() for p in args.pairs.split(",")]:
        symbol_a, symbol_b = pair.split("-")
        for symbol in (symbol_a, symbol_b):
            if symbol not in data_cache:
                print(f"[데이터] {symbol} {args.timeframe} 캔들 수집 중...")
                data_cache[symbol] = fetch_ohlcv(symbol, args.timeframe, args.since, args.until)

        frame_a, frame_b = data_cache[symbol_a], data_cache[symbol_b]
        if frame_a.empty or frame_b.empty:
            print(f"  {pair}: 데이터 부족, 건너뜀")
            continue

        ratio_frame = build_ratio_frame(frame_a, frame_b).dropna()
        if len(ratio_frame) < MIN_USABLE_BARS:
            print(f"  {pair}: 정렬 후 데이터 부족, 건너뜀")
            continue

        stats = Backtest(ratio_frame, PairsMeanReversionStrategy, cash=args.cash,
                          commission=args.commission, exclusive_orders=True).run()
        ret = stats.get("Return [%]", float("nan"))
        bh = stats.get("Buy & Hold Return [%]", float("nan"))
        pf = stats.get("Profit Factor", float("nan"))
        mdd = abs(stats.get("Max. Drawdown [%]", float("inf")))
        trades = stats.get("# Trades", 0)
        print(f"  [{pair}] 수익률 {ret:.2f}% (정적 50/50 보유 {bh:.2f}%, 초과 {ret - bh:+.2f}%p) "
              f"PF {pf:.2f} MDD {mdd:.2f}% 거래 {trades}건")


if __name__ == "__main__":
    run(parse_args())
