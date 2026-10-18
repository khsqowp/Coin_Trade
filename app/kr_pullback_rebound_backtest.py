"""국내주식 워치리스트 전체(kr_watchlist.STOCK_UNIVERSE — 기존 EMA9/21 스윙봇이 쓰는
감시종목 그대로)에 공돌투자자 눌림목 반등매매 전략을 과거 일봉으로 백테스트한다.

SMA5 vs SMA10, 거래대금 필터 유무를 모두 테스트해서 어느 조합이 효과적인지 비교한다.
"""
from __future__ import annotations

from app.kis_auth import issue_token
from app.kis_data import fetch_ohlcv_kis
from app.kr_watchlist import STOCK_UNIVERSE
from app.pullback_rebound_backtest_core import print_report, simulate

SINCE = "2015-01-01"
INITIAL_CAPITAL_KRW = 10_000_000.0

# 테스트할 설정 조합: (ma_length, volume_filter_enabled, 설명)
CONFIGS = [
    (5, False, "SMA5 필터없음"),
    (5, True, "SMA5 거래대금필터"),
    (10, False, "SMA10 필터없음"),
    (10, True, "SMA10 거래대금필터"),
]


def run() -> None:
    token = issue_token()

    for ma_length, volume_filter_enabled, config_name in CONFIGS:
        results = []
        for symbol, name in STOCK_UNIVERSE:
            try:
                frame = fetch_ohlcv_kis(symbol, token, SINCE)
            except Exception as exc:  # noqa: BLE001
                continue

            stats = simulate(
                frame,
                INITIAL_CAPITAL_KRW,
                ma_length=ma_length,
                volume_filter_enabled=volume_filter_enabled,
            )
            if stats is None:
                continue

            stats["symbol"] = symbol
            stats["display"] = f"{name}({symbol})"
            results.append(stats)

        print_report("국장", config_name, results)


if __name__ == "__main__":
    run()
