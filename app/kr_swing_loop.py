"""국내주식 스윙 자동매매 메인 루프 — 단일 프로세스 안에서 이중 주기로 동작한다.
  - 장중(09:00~15:20 KST, 평일) 매분: kr_intraday_risk.check_once() — 보유종목 손절 +
    전일 스캔이 채운 매매대기열 소비
  - 장마감후(15:35 KST 이후, 하루 1회): kr_daily_scan.run_once() — 워치리스트 재스캔,
    다음날 소비할 대기열 갱신

공휴일은 별도로 다루지 않는다(휴장일엔 KIS가 주문/시세 오류를 뱉을 뿐 루프가 죽지는 않음).
"""
from __future__ import annotations

import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

from app.kis_auth import issue_token
from app.kr_daily_scan import run_once as run_daily_scan
from app.kr_intraday_risk import check_once as run_intraday_risk
from app.kr_state import load_state, log_event, save_state
from app.watchdog import run_with_timeout

KST = ZoneInfo("Asia/Seoul")
MARKET_OPEN = dt.time(9, 0)
MARKET_CLOSE_FOR_RISK = dt.time(15, 20)
SCAN_AFTER = dt.time(15, 35)
# 장중 실시간 손절 체크 주기 — tick_stream.py 웹소켓 틱을 우선 쓰게 되면서(kr_intraday_risk.py)
# REST 호출이 크게 줄어, 예전 60초보다 훨씬 짧게 돌려도 KIS 호출한도에 안 걸린다.
LOOP_SLEEP_SECONDS = int(os.environ.get("KR_SWING_LOOP_SLEEP_SECONDS", "10"))
TOKEN_TTL_SECONDS = 12 * 3600
INTRADAY_TIMEOUT_SECONDS = 30
SCAN_TIMEOUT_SECONDS = 120


def main() -> None:
    state = load_state()
    log_event(state, "국내주식 스윙 자동매매 루프 시작")
    save_state(state)

    token = issue_token()
    token_issued_at = time.monotonic()

    while True:
        try:
            if time.monotonic() - token_issued_at > TOKEN_TTL_SECONDS:
                token = issue_token()
                token_issued_at = time.monotonic()

            now = dt.datetime.now(KST)
            is_weekday = now.weekday() < 5

            if is_weekday and MARKET_OPEN <= now.time() <= MARKET_CLOSE_FOR_RISK:
                state = load_state()
                run_with_timeout(
                    lambda: run_intraday_risk(token, state), INTRADAY_TIMEOUT_SECONDS,
                    on_timeout=lambda: print(f"[경고] 장중 리스크체크가 {INTRADAY_TIMEOUT_SECONDS}초 넘게 안 끝나 hang으로 보고 포기", flush=True),
                )
            elif is_weekday and now.time() >= SCAN_AFTER:
                run_with_timeout(
                    lambda: run_daily_scan(token), SCAN_TIMEOUT_SECONDS,
                    on_timeout=lambda: print(f"[경고] 일일스캔이 {SCAN_TIMEOUT_SECONDS}초 넘게 안 끝나 hang으로 보고 포기", flush=True),
                )
        except Exception as exc:  # noqa: BLE001 — 한 사이클 실패로 루프 전체가 죽지 않게
            state = load_state()
            log_event(state, f"[오류] 루프 사이클 실패: {exc}")
            save_state(state)

        time.sleep(LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
