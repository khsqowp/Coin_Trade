"""미국 2차 후보 프로브 — '꾸준한 성장주' 8개 + '자투리(저가주)' 6개를 한 번에 스윕.
app/probe_runner.py 공통 실행기(30전략 풀스윕) 재사용."""
from __future__ import annotations

from app.probe_runner import run_us_full_sweep_probe

GROWTH_CANDIDATES = [
    ("WST", "NYS", "West Pharmaceutical"), ("POOL", "NAS", "Pool Corp"), ("CASY", "NAS", "Casey's General"),
    ("WSO", "NYS", "Watsco"), ("SAIA", "NAS", "Saia"), ("FIX", "NYS", "Comfort Systems"),
    ("MKTX", "NAS", "MarketAxess"), ("IDXX", "NAS", "IDEXX Labs"),
]
SPARE_CHANGE_CANDIDATES = [
    ("BAC", "NYS", "Bank of America"), ("PFE", "NYS", "Pfizer"), ("T", "NYS", "AT&T"),
    ("VZ", "NYS", "Verizon"), ("KMI", "NYS", "Kinder Morgan"), ("F", "NYS", "Ford"),
]
CANDIDATES = GROWTH_CANDIDATES + SPARE_CHANGE_CANDIDATES


def run() -> None:
    run_us_full_sweep_probe(CANDIDATES)


if __name__ == "__main__":
    run()
