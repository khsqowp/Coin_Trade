"""저가주 3차 후보 프로브 — 초기 소액 운용 단계에서 매수 가능성 높이려고 저가 우량/중견주 위주로 확장.
app/probe_runner.py 공통 실행기(30전략 풀스윕) 재사용."""
from __future__ import annotations

from app.probe_runner import run_kr_full_sweep_probe

CANDIDATES = [
    ("001510", "SK증권"), ("003530", "한화투자증권"), ("000540", "흥국화재"), ("000400", "롯데손해보험"),
    ("029780", "삼성카드"), ("000080", "하이트진로"), ("002350", "넥센타이어"), ("047040", "대우건설"),
    ("051600", "한전KPS"), ("001120", "LX인터내셔널"), ("028670", "팬오션"), ("005180", "빙그레"),
]


def run() -> None:
    run_kr_full_sweep_probe(CANDIDATES)


if __name__ == "__main__":
    run()
