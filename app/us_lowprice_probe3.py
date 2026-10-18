"""저가주 3차 후보 프로브 (미국) — 초기 소액 운용 단계에서 매수 가능성 높이려고 저가주 위주로 확장.
app/probe_runner.py 공통 실행기(30전략 풀스윕) 재사용."""
from __future__ import annotations

from app.probe_runner import run_us_full_sweep_probe

CANDIDATES = [
    ("NOK", "NYS", "Nokia"), ("HBAN", "NAS", "Huntington Bancshares"), ("KEY", "NYS", "KeyCorp"),
    ("RF", "NYS", "Regions Financial"), ("GM", "NYS", "General Motors"), ("SIRI", "NAS", "Sirius XM"),
    ("DVN", "NYS", "Devon Energy"), ("GOLD", "NYS", "Barrick"), ("CCL", "NYS", "Carnival"), ("AAL", "NAS", "American Airlines"),
]


def run() -> None:
    run_us_full_sweep_probe(CANDIDATES)


if __name__ == "__main__":
    run()
