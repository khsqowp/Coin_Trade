"""국내주식 워치리스트 전체(kr_watchlist.STOCK_UNIVERSE — 기존 EMA9/21 스윙봇이 쓰는
감시종목 그대로)에 200/20일 스퀴즈 전략을 과거 일봉으로 백테스트한다.
"""
from __future__ import annotations

from app.kis_auth import issue_token
from app.kis_data import fetch_ohlcv_kis
from app.kr_watchlist import STOCK_UNIVERSE
from app.squeeze_backtest_core import print_report, simulate

SINCE = "2015-01-01"
INITIAL_CAPITAL_KRW = 10_000_000.0


def run() -> None:
    token = issue_token()
    results = []
    for symbol, name in STOCK_UNIVERSE:
        try:
            frame = fetch_ohlcv_kis(symbol, token, SINCE)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}({symbol}): 시세조회 실패 — {exc}")
            continue
        stats = simulate(frame, INITIAL_CAPITAL_KRW)
        if stats is None:
            print(f"  {name}({symbol}): 데이터 부족(SMA200 못 채움) — 건너뜀")
            continue
        stats["symbol"] = symbol
        stats["display"] = f"{name}({symbol})"
        results.append(stats)

    print_report("국장", results)


if __name__ == "__main__":
    run()
