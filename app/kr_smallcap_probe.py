"""소형주 후보 프로브 — app/probe_runner.py 공통 실행기(30전략 풀스윕) 재사용.
통과하면 STOCK_UNIVERSE(ema_cross_watchlist.py 등)에 편입."""
from __future__ import annotations

from app.probe_runner import run_kr_full_sweep_probe

CANDIDATES = [
    ("058470", "리노공업"),
    ("026960", "동서"),
    ("091700", "파트론"),
    ("214150", "클래시스"),
    ("030190", "NICE평가정보"),
    ("041830", "인바디"),
]


def run() -> None:
    run_kr_full_sweep_probe(CANDIDATES)


if __name__ == "__main__":
    run()
