"""미국주식(KIS 해외) 일봉으로 마하세븐 3기법을 백테스트한다.
us_watchlist.STOCK_UNIVERSE 전체에 대해 세 기법별로 결과를 비교한다.
"""
from __future__ import annotations

from app.kis_auth import issue_token
from app.kis_overseas_data import fetch_ohlcv_kis_overseas
from app.mach7_backtest_core import print_report, simulate
from app.mach7_indicators import add_mach7_ma_pullback, add_mach7_rsi_pullback, add_mach7_bb_pullback
from app.us_watchlist import STOCK_UNIVERSE

SINCE = "2015-01-01"
INITIAL_CAPITAL_USD = 10_000.0


def run() -> None:
    print("미장 3기법 마하세븐 백테스트 시작...")
    token = issue_token()

    results_ma = []
    results_rsi = []
    results_bb = []

    for symbol, excd, name in STOCK_UNIVERSE:
        print(f"  {name}({symbol})...", end=" ", flush=True)
        try:
            frame = fetch_ohlcv_kis_overseas(symbol, excd, token, SINCE)
        except Exception as exc:  # noqa: BLE001
            print(f"시세조회 실패({exc})")
            continue

        if len(frame) < 210:
            print("데이터 부족")
            continue

        # 이평선 눌림목
        try:
            frame_ma = add_mach7_ma_pullback(frame)
            stats_ma = simulate(frame_ma, INITIAL_CAPITAL_USD, "ENTRY_SIGNAL", "EXIT_SIGNAL", "STOP_PRICE")
            if stats_ma:
                stats_ma["symbol"] = symbol
                stats_ma["display"] = f"{name}({symbol})"
                results_ma.append(stats_ma)
                print(f"MA {stats_ma['total_return_pct']:+.1f}%", end=" ")
        except Exception as exc:  # noqa: BLE001
            print(f"MA실패({exc})", end=" ")

        # RSI 눌림목
        try:
            frame_rsi = add_mach7_rsi_pullback(frame)
            stats_rsi = simulate(frame_rsi, INITIAL_CAPITAL_USD, "ENTRY_SIGNAL", "EXIT_SIGNAL", "STOP_PRICE")
            if stats_rsi:
                stats_rsi["symbol"] = symbol
                stats_rsi["display"] = f"{name}({symbol})"
                results_rsi.append(stats_rsi)
                print(f"RSI {stats_rsi['total_return_pct']:+.1f}%", end=" ")
        except Exception as exc:  # noqa: BLE001
            print(f"RSI실패({exc})", end=" ")

        # 볼린저밴드 눌림목
        try:
            frame_bb = add_mach7_bb_pullback(frame)
            stats_bb = simulate(frame_bb, INITIAL_CAPITAL_USD, "ENTRY_SIGNAL", "EXIT_SIGNAL", "STOP_PRICE")
            if stats_bb:
                stats_bb["symbol"] = symbol
                stats_bb["display"] = f"{name}({symbol})"
                results_bb.append(stats_bb)
                print(f"BB {stats_bb['total_return_pct']:+.1f}%", end=" ")
        except Exception as exc:  # noqa: BLE001
            print(f"BB실패({exc})", end=" ")

        print()

    print_report("미장-이평선눌림목", results_ma)
    print_report("미장-RSI눌림목", results_rsi)
    print_report("미장-볼린저밴드눌림목", results_bb)


if __name__ == "__main__":
    run()
