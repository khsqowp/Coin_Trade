"""미국 소형주(배당킹/스테디 컴파운더) 후보 프로브 — app/probe_runner.py 공통 실행기(30전략 풀스윕) 재사용."""
from __future__ import annotations

from app.probe_runner import run_us_full_sweep_probe

CANDIDATES = [
    ("AWR", "NYS", "American States Water"),
    ("GRC", "NYS", "Gorman-Rupp"),
    ("MSA", "NYS", "MSA Safety"),
    ("ROL", "NYS", "Rollins"),
    ("NWN", "NYS", "Northwest Natural"),
    ("AAON", "NAS", "AAON"),
]


def run() -> None:
    run_us_full_sweep_probe(CANDIDATES)


if __name__ == "__main__":
    run()
