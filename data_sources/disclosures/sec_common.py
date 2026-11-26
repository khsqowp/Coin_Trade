"""공통 SEC 요청 설정과 초당 요청 간격 제어."""
from __future__ import annotations

import os
import time

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "Coin_Trade Research kknd03255@naver.com")


class RateLimiter:
    """연속 요청 사이에 최소 간격을 둔다."""

    def __init__(self, interval: float = 1.0, clock=time.monotonic, sleeper=time.sleep):
        if interval <= 0:
            raise ValueError("interval은 양수여야 합니다")
        self.interval = interval
        self.clock = clock
        self.sleeper = sleeper
        self.next_allowed = None

    def wait(self) -> None:
        now = self.clock()
        if self.next_allowed is not None:
            delay = max(0.0, self.next_allowed - now)
            if delay:
                self.sleeper(delay)
                now = self.clock()
        self.next_allowed = max(now, self.next_allowed or now) + self.interval
