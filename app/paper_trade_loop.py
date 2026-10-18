"""펀딩비 차익거래 모의투자 상시 실행 루프.

바이낸스 펀딩비는 8시간마다 정산되지만, 진입 기회를 놓치지 않도록 더 짧은 주기로 확인한다.
한 사이클에서 예외가 나도 루프 전체가 죽지 않도록 사이클 단위로 예외를 흡수한다.
"""
from __future__ import annotations

import os
import time
import traceback

from app.paper_funding_arb import run_cycle
from app.watchdog import run_with_timeout

CHECK_INTERVAL_SECONDS = int(os.environ.get("PAPER_TRADE_CHECK_INTERVAL_SECONDS", "60"))
CYCLE_TIMEOUT_SECONDS = int(os.environ.get("PAPER_TRADE_CYCLE_TIMEOUT_SECONDS", "45"))


def main() -> None:
    print(f"펀딩비 차익거래 모의투자 루프 시작 (사이클 주기 {CHECK_INTERVAL_SECONDS}초)", flush=True)
    while True:
        try:
            run_with_timeout(
                run_cycle, CYCLE_TIMEOUT_SECONDS,
                on_timeout=lambda: print(
                    f"사이클이 {CYCLE_TIMEOUT_SECONDS}초 넘게 안 끝나 hang으로 보고 포기, 다음 사이클로 넘어감", flush=True,
                ),
            )
        except Exception:
            print("사이클 실행 중 오류 발생:", flush=True)
            traceback.print_exc()
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
