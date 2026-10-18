"""코인 워치리스트 전체(momentum_rotation_loop.UNIVERSE — 기존 모멘텀로테이션 봇이 쓰는
감시종목 그대로)에 200/20일 스퀴즈 전략을 과거 스팟 일봉으로 백테스트한다.
"""
from __future__ import annotations

from app.data import fetch_ohlcv
from app.momentum_rotation_loop import UNIVERSE
from app.squeeze_backtest_core import print_report, simulate

SINCE = "2018-01-01T00:00:00Z"
INITIAL_CAPITAL_USDT = 10_000.0


def run() -> None:
    results = []
    for base in UNIVERSE:
        symbol = f"{base}/USDT"
        try:
            frame = fetch_ohlcv(symbol, "1d", SINCE, None)
        except Exception as exc:  # noqa: BLE001
            print(f"  {base}: 시세조회 실패 — {exc}")
            continue
        stats = simulate(frame, INITIAL_CAPITAL_USDT)
        if stats is None:
            print(f"  {base}: 데이터 부족(SMA200 못 채움) — 건너뜀")
            continue
        stats["symbol"] = base
        stats["display"] = base
        results.append(stats)

    print_report("코인", results)


if __name__ == "__main__":
    run()
