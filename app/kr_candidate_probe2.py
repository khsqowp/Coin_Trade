"""소형/중형주 2차 후보 프로브 — '꾸준한 성장주' 8개 + '자투리(저가주)' 6개를 한 번에 스윕.
app/probe_runner.py 공통 실행기(30전략 풀스윕) 재사용."""
from __future__ import annotations

from app.probe_runner import run_kr_full_sweep_probe

GROWTH_CANDIDATES = [
    ("214450", "파마리서치"), ("271560", "오리온"), ("001680", "대상"), ("161890", "한국콜마"),
    ("192820", "코스맥스"), ("145720", "덴티움"), ("003230", "삼양식품"), ("145020", "휴젤"),
]
SPARE_CHANGE_CANDIDATES = [
    ("036460", "한국가스공사"), ("000370", "한화손해보험"), ("082640", "동양생명"),
    ("001270", "부국증권"), ("003540", "대신증권"), ("003690", "코리안리"),
]
CANDIDATES = GROWTH_CANDIDATES + SPARE_CHANGE_CANDIDATES


def run() -> None:
    run_kr_full_sweep_probe(CANDIDATES)


if __name__ == "__main__":
    run()
