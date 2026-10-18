"""CLI entrypoint: fetch Binance history, run RegimeSwitchStrategy, and check the
validation gate defined in docs/trading-agent-plan.md before any live code gets written."""
from __future__ import annotations

import argparse
import sys

from backtesting import Backtest

from app.data import fetch_ohlcv
from app.indicators import add_indicators
from app.strategy import RegimeSwitchStrategy

MIN_PROFIT_FACTOR = 1.25
MAX_DRAWDOWN_PCT = 10.0
MIN_TRADES = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Binance regime-switch strategy backtest")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--since", default="2022-01-01T00:00:00Z")
    parser.add_argument("--until", default=None)
    parser.add_argument("--cash", type=float, default=1_000_000)
    parser.add_argument("--commission", type=float, default=0.001)
    return parser.parse_args()


def run(symbol: str, timeframe: str, since: str, until: str | None, cash: float, commission: float) -> None:
    print(f"[1/3] {symbol} {timeframe} 캔들 수집 중 ({since} ~ {until or '현재'})...")
    frame = fetch_ohlcv(symbol, timeframe, since, until)
    if frame.empty:
        print("데이터를 받아오지 못했습니다 — 네트워크 연결 또는 심볼을 확인하세요.", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(frame)}개 캔들 수집 완료")

    print("[2/3] 지표 계산 중...")
    enriched = add_indicators(frame).dropna()
    print(f"  워밍업 이후 {len(enriched)}개 캔들 사용")

    print("[3/3] 백테스트 실행 중 (경제팀 오버레이 필터 있음/없음 비교)...")
    baseline_bt = Backtest(enriched, RegimeSwitchStrategy, cash=cash, commission=commission, exclusive_orders=True)
    baseline_stats = baseline_bt.run(USE_REGIME_FILTER=False)
    print("\n--- 오버레이 필터 없음 (순수 기술적 지표만) ---")
    print(baseline_stats)

    filtered_bt = Backtest(enriched, RegimeSwitchStrategy, cash=cash, commission=commission, exclusive_orders=True)
    filtered_stats = filtered_bt.run(USE_REGIME_FILTER=True)
    print("\n--- 오버레이 필터 적용 (리서치 기반 리스크오프 구간 진입 보류) ---")
    print(filtered_stats)

    print("\n비용 2배 적용 재검증 중 (필터 적용 버전 기준)...")
    stressed_stats = Backtest(enriched, RegimeSwitchStrategy, cash=cash, commission=commission * 2, exclusive_orders=True).run(USE_REGIME_FILTER=True)

    _print_gate(filtered_stats, stressed_stats)


def _print_gate(stats, stressed_stats) -> None:
    profit_factor = stats.get("Profit Factor", float("nan"))
    max_drawdown = abs(stats.get("Max. Drawdown [%]", float("inf")))
    trade_count = stats.get("# Trades", 0)
    stressed_return = stressed_stats.get("Return [%]", float("-inf"))

    checks = [
        (f"Profit Factor >= {MIN_PROFIT_FACTOR}", profit_factor >= MIN_PROFIT_FACTOR, profit_factor),
        (f"최대낙폭 <= {MAX_DRAWDOWN_PCT}%", max_drawdown <= MAX_DRAWDOWN_PCT, max_drawdown),
        (f"거래 횟수 >= {MIN_TRADES}", trade_count >= MIN_TRADES, trade_count),
        ("비용 2배 적용시 기대값 양수", stressed_return > 0, stressed_return),
    ]
    print("\n=== 검증 기준 (docs/trading-agent-plan.md) ===")
    all_passed = True
    for label, passed, value in checks:
        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] {label} (실측값: {value:.4g})")
        all_passed = all_passed and passed

    if all_passed:
        print("\n결론: 게이트 통과 — 다음 단계(모의투자 연동) 진행 가능")
    else:
        print("\n결론: 게이트 미통과 — 파라미터 재검토 필요, 실거래 코드로 넘어가지 말 것")


if __name__ == "__main__":
    args = parse_args()
    run(args.symbol, args.timeframe, args.since, args.until, args.cash, args.commission)
