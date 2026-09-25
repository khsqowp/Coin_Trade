"""코인 롱숏 스윙 페이퍼봇 상시 실행 루프.

TRX 봇(trx_swing_loop.py)과 같은 구조 — 사이클 단위로 예외를 흡수해 루프 전체가 죽지 않게
한다. 이 봇은 완전 페이퍼(가상자본)라 키 자체가 필요없지만, 2026-09-25 재설계로 매 사이클
전체 유니버스(45종목)의 일봉을 다시 조회하게 돼 사이클 하나가 예전(고정 6종목)보다 무거워짐
— 타임아웃을 그만큼 넉넉히 잡는다.
"""
from __future__ import annotations

import os
import time
import traceback

from app.coin_swing6_trade import run_cycle
from app.watchdog import run_with_timeout

CHECK_INTERVAL_SECONDS = int(os.environ.get("COIN_SWING6_CHECK_INTERVAL_SECONDS", "120"))
CYCLE_TIMEOUT_SECONDS = int(os.environ.get("COIN_SWING6_CYCLE_TIMEOUT_SECONDS", "240"))


def main() -> None:
    print(f"코인 롱숏 스윙 페이퍼봇 루프 시작 (사이클 주기 {CHECK_INTERVAL_SECONDS}초)", flush=True)
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
