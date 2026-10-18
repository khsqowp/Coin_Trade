"""장 시작 갭업/급등주 전략 백테스트용 원본 데이터 캡처.

KIS 분봉 조회는 보통 당일치만 주고 과거 날짜를 재현 못 한다(app/kis_data.py 일봉 조회처럼
페이지네이션되는 건 확인했지만 분봉은 아직 실측 안 함) — 그래서 "장 시작 직후 몇 분간
누가 얼마나 뛰었는가"를 사후에 재구성하려면 그 순간 실시간으로 스냅샷을 떠서 쌓아두는
것 말고는 방법이 없다. 이 스크립트가 그 캡처만 한다 — 매매도, 종목선정 로직도 없다.

등락률 순위 API(app/kis_ranking.py)는 이미 시장 전체를 등락률순으로 정렬해서 한 번에
주므로, 종목을 1000개 개별 구독/조회하는 대신 이 스냅샷만 주기적으로 뜨면 "그 순간 뜨던
종목 상위 N개"가 다 잡힌다. 계좌 조회/주문을 전혀 안 하므로 kr-rotation과 같은 계좌를
같이 써도 포지션에 영향 없음(순수 시세 조회).

env:
  SCAN_START_HHMM        스냅샷 시작 시각 KST "HH:MM" (기본 "09:00", 장 시작 5분 전부터 켜둠)
  SCAN_WINDOW_MINUTES     시작 후 몇 분간 스냅샷 뜰지 (기본 120)
  SCAN_MIN_GAP_SECONDS    한 스냅샷(페이지네이션 포함) 종료 후 다음 시작까지 최소 간격 (기본 2)
  SCAN_MAX_PAGES          스냅샷 1회당 최대 페이지 수 — app/kis_ranking.py 참고 (기본 5)
"""
from __future__ import annotations

import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

from app.kis_auth import issue_token
from app.kis_ranking import fetch_fluctuation_ranking
from app.tick_archive import append_batch

KST = ZoneInfo("Asia/Seoul")
_START_HH, _START_MM = (int(x) for x in os.environ.get("SCAN_START_HHMM", "09:00").split(":"))
WINDOW_MINUTES = int(os.environ.get("SCAN_WINDOW_MINUTES", "120"))
MIN_GAP_SECONDS = float(os.environ.get("SCAN_MIN_GAP_SECONDS", "2"))
MAX_PAGES = int(os.environ.get("SCAN_MAX_PAGES", "5"))
TOKEN_TTL_SECONDS = 12 * 3600
CATEGORY = "opening-scan-kr"


def _now() -> dt.datetime:
    return dt.datetime.now(KST)


def _today_window(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    start = now.replace(hour=_START_HH, minute=_START_MM, second=0, microsecond=0)
    return start, start + dt.timedelta(minutes=WINDOW_MINUTES)


def _sleep_until(target: dt.datetime) -> None:
    while True:
        remaining = (target - _now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 60))


def _next_start_after(now: dt.datetime) -> dt.datetime:
    candidate = now.replace(hour=_START_HH, minute=_START_MM, second=0, microsecond=0)
    if candidate <= now:
        candidate += dt.timedelta(days=1)
    while candidate.weekday() >= 5:  # 토/일 건너뜀
        candidate += dt.timedelta(days=1)
    return candidate


def main() -> None:
    print(f"[개장스캔] 평일 {_START_HH:02d}:{_START_MM:02d} KST부터 {WINDOW_MINUTES}분간 "
          f"등락률순위(최대 {MAX_PAGES}페이지) 스냅샷 캡처 시작", flush=True)
    token = issue_token()
    token_at = time.monotonic()

    while True:
        now = _now()
        start, end = _today_window(now)

        if now.weekday() >= 5 or now >= end:
            target = _next_start_after(now)
            print(f"[개장스캔] 오늘 창 종료(또는 휴장) — 다음 시작 {target.isoformat()} 까지 대기", flush=True)
            _sleep_until(target)
            continue
        if now < start:
            _sleep_until(start)
            continue

        print(f"[개장스캔] 캡처 시작 {start.isoformat()} ~ {end.isoformat()}", flush=True)
        snapshot_count = 0
        row_count = 0
        error_count = 0
        while _now() < end:
            cycle_started = time.monotonic()
            if time.monotonic() - token_at > TOKEN_TTL_SECONDS:
                token = issue_token()
                token_at = time.monotonic()
            try:
                rows = fetch_fluctuation_ranking(token, max_pages=MAX_PAGES)
                append_batch(CATEGORY, [{
                    "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "row_count": len(rows),
                    "rows": rows,
                }])
                snapshot_count += 1
                row_count += len(rows)
            except Exception as exc:  # noqa: BLE001
                error_count += 1
                if error_count == 1 or error_count % 20 == 0:
                    print(f"[개장스캔] 스냅샷 실패(누적 {error_count}회): {exc}", flush=True)
            elapsed = time.monotonic() - cycle_started
            if elapsed < MIN_GAP_SECONDS:
                time.sleep(MIN_GAP_SECONDS - elapsed)
        print(f"[개장스캔] 캡처 종료 — 스냅샷 {snapshot_count}건 (row 합계 {row_count}), "
              f"실패 {error_count}건", flush=True)


if __name__ == "__main__":
    main()
