"""읽기 전용 ccxt 호출용 재시도(+백오프) 헬퍼.

주문 생성/취소 호출에는 절대 쓰지 말 것 — 타임아웃이 나도 서버에서는 체결됐을 수 있어
재시도하면 중복 주문이 된다. 시세/잔고/포지션 조회 같은 멱등 호출 전용.
"""
from __future__ import annotations

import socket
import time
from typing import Callable, TypeVar

import ccxt

T = TypeVar("T")

# RateLimitExceeded/DDoSProtection 은 NetworkError 하위지만 재시도하면 IP 밴(-1003)을 악화시키므로 제외.
_NON_RETRYABLE = (ccxt.RateLimitExceeded, ccxt.DDoSProtection)
_RETRYABLE = (ccxt.NetworkError, socket.gaierror, TimeoutError)


def retry_read(fn: Callable[..., T], *args, tries: int = 3, base_delay: float = 1.0,
               sleep: Callable[[float], None] = time.sleep, **kwargs) -> T:
    for attempt in range(1, tries + 1):
        try:
            return fn(*args, **kwargs)
        except _NON_RETRYABLE:
            raise
        except _RETRYABLE as exc:
            if attempt >= tries:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            print(f"  읽기 재시도 {attempt}/{tries - 1} ({type(exc).__name__}) — {delay:g}초 후", flush=True)
            sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover
