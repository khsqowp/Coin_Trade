"""사이클 함수가 네트워크 hang 등으로 영영 안 끝나는 경우를 대비한 워치독.

실측 확인된 사고: paper_exchange.py의 lru_cache된 ccxt 클라이언트가 프로세스 내내
재사용되는데, 그 안의 requests 커넥션풀에 죽은(stale) 커넥션이 재사용되면 ccxt의
timeout 설정과 무관하게 요청이 응답 없이 무한 대기하는 경우가 있다 — 펀딩비차익 봇이
이걸로 18시간 넘게 완전히 멈춰있었다(컨테이너는 죽지 않아서 자동 재시작도 안 됨).

파이썬은 스레드를 강제로 죽일 수 없으므로, 사이클을 데몬 스레드에서 돌리고 제한시간
안에 안 끝나면 그 스레드는 방치한 채(어차피 데몬이라 프로세스 종료를 막지 않는다)
다음 사이클로 넘어간다. 방치된 스레드가 나중에 응답을 받아 끝나더라도 이미 다음
사이클이 새 클라이언트/상태로 진행중이라 상태 오염은 없다(각 run_cycle 호출은
load_state()로 최신 상태를 다시 읽어서 시작하는 구조이기 때문).
"""
from __future__ import annotations

import threading
from typing import Callable


def run_with_timeout(func: Callable[[], None], timeout_seconds: float, on_timeout: Callable[[], None]) -> None:
    error: list[BaseException] = []

    def _target() -> None:
        try:
            func()
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        on_timeout()
        return
    if error:
        raise error[0]
