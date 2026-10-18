"""코인 워치리스트 전체(momentum_rotation_loop.UNIVERSE — 기존 모멘텀로테이션 봇이 쓰는
감시종목 그대로)에 공돌투자자 눌림목 반등매매 전략을 과거 스팟 일봉으로 백테스트한다.

국내 주식 중심 전략이지만, 코인도 동일 로직으로 동작 확인을 위해 추가.
"""
from __future__ import annotations

from app.data import fetch_ohlcv
from app.momentum_rotation_loop import UNIVERSE
from app.pullback_rebound_backtest_core import print_report, simulate

SINCE = "2018-01-01T00:00:00Z"
INITIAL_CAPITAL_USDT = 10_000.0

# 테스트할 설정 조합
CONFIGS = [
    (5, False, "SMA5 필터없음"),
    (5, True, "SMA5 거래대금필터"),
    (10, False, "SMA10 필터없음"),
    (10, True, "SMA10 거래대금필터"),
]


def run() -> None:
    for ma_length, volume_filter_enabled, config_name in CONFIGS:
        results = []
        for base in UNIVERSE:
            symbol = f"{base}/USDT"
            try:
                frame = fetch_ohlcv(symbol, "1d", SINCE, None)
            except Exception as exc:  # noqa: BLE001
                continue

            stats = simulate(
                frame,
                INITIAL_CAPITAL_USDT,
                ma_length=ma_length,
                volume_filter_enabled=volume_filter_enabled,
            )
            if stats is None:
                continue

            stats["symbol"] = base
            stats["display"] = base
            results.append(stats)

        print_report("코인", config_name, results)


if __name__ == "__main__":
    run()
