"""코인(바이낸스) 일봉으로 마하세븐 3기법을 백테스트한다.
momentum_rotation_loop.UNIVERSE(46종목) 전체에 대해 세 기법별로 결과를 비교한다.
"""
from __future__ import annotations

from app.data import fetch_ohlcv
from app.mach7_backtest_core import print_report, simulate
from app.mach7_indicators import add_mach7_ma_pullback, add_mach7_rsi_pullback, add_mach7_bb_pullback
from app.momentum_rotation_loop import UNIVERSE

SINCE = "2020-01-01"
INITIAL_CAPITAL_USDT = 10_000.0


def run() -> None:
    print("코인 3기법 마하세븐 백테스트 시작...")
    results_ma = []
    results_rsi = []
    results_bb = []

    for base in UNIVERSE:
        symbol = f"{base}/USDT"
        print(f"  {symbol}...", end=" ", flush=True)
        try:
            frame = fetch_ohlcv(symbol, "1d", SINCE)
        except Exception as exc:  # noqa: BLE001
            print(f"시세조회 실패({exc})")
            continue

        if len(frame) < 210:
            print("데이터 부족")
            continue

        # 이평선 눌림목
        try:
            frame_ma = add_mach7_ma_pullback(frame)
            stats_ma = simulate(frame_ma, INITIAL_CAPITAL_USDT, "ENTRY_SIGNAL", "EXIT_SIGNAL", "STOP_PRICE")
            if stats_ma:
                stats_ma["symbol"] = base
                stats_ma["display"] = base
                results_ma.append(stats_ma)
                print(f"MA {stats_ma['total_return_pct']:+.1f}%", end=" ")
        except Exception as exc:  # noqa: BLE001
            print(f"MA실패({exc})", end=" ")

        # RSI 눌림목
        try:
            frame_rsi = add_mach7_rsi_pullback(frame)
            stats_rsi = simulate(frame_rsi, INITIAL_CAPITAL_USDT, "ENTRY_SIGNAL", "EXIT_SIGNAL", "STOP_PRICE")
            if stats_rsi:
                stats_rsi["symbol"] = base
                stats_rsi["display"] = base
                results_rsi.append(stats_rsi)
                print(f"RSI {stats_rsi['total_return_pct']:+.1f}%", end=" ")
        except Exception as exc:  # noqa: BLE001
            print(f"RSI실패({exc})", end=" ")

        # 볼린저밴드 눌림목
        try:
            frame_bb = add_mach7_bb_pullback(frame)
            stats_bb = simulate(frame_bb, INITIAL_CAPITAL_USDT, "ENTRY_SIGNAL", "EXIT_SIGNAL", "STOP_PRICE")
            if stats_bb:
                stats_bb["symbol"] = base
                stats_bb["display"] = base
                results_bb.append(stats_bb)
                print(f"BB {stats_bb['total_return_pct']:+.1f}%", end=" ")
        except Exception as exc:  # noqa: BLE001
            print(f"BB실패({exc})", end=" ")

        print()

    print_report("코인-이평선눌림목", results_ma)
    print_report("코인-RSI눌림목", results_rsi)
    print_report("코인-볼린저밴드눌림목", results_bb)


if __name__ == "__main__":
    run()
