"""VOLREG-R1 포워드 신호 계산 — PREREG_VOLREG_R1_TEST_FREEZE.md에서 동결한 정의 그대로:

    spread = CBOE VIX 종가 - RV20(SPY, 20일 로그수익률 표준편차*sqrt(252)*100)
    spread <= entry(-2.5) → state 0.0 (risk-off: SHY 100%)
    spread >= exit(1.0)   아님, exit(2.5) → state 1.0 (risk-on: SPY 50% / QQQ 50%)
    그 사이면 직전 state 유지(히스테리시스).

TRAIN/TEST 백테스트는 SPY/QQQ Yahoo 수정종가(adj_close)를 썼지만, 포워드는 토스증권 공식
시세 API의 비조정 종가를 쓴다 — SPY/QQQ는 배당은 나오지만 최근 분할은 없어 RV20(수익률
표준편차)에는 영향이 거의 없고, 이 근사가 동결 정의와 다르다는 점을 여기 명시해 둔다.
(한투 KIS 모의투자 인증이 계속 막혀서 2026-11-27 사용자 승인으로 토스로 교체했다.)

VIX는 CBOE 공식 공개 CSV(cboe_index_history.parquet를 만들 때 쓴 바로 그 소스, 비공식
스크레이핑이 아니라 CBOE가 직접 공개하는 공식 엔드포인트)에서 받는다.
"""
from __future__ import annotations

import datetime as dt
import math

import requests

from app.toss_price import get_daily_closes

VIX_CSV_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
ENTRY = -2.5
EXIT = 2.5
RV_WINDOW = 20
LOOKBACK_CALENDAR_DAYS = 60  # 20거래일 수익률 확보용 여유(휴장일 포함)


def fetch_vix_closes(max_retries: int = 4) -> dict[str, float]:
    """날짜("YYYY-MM-DD") -> VIX 종가. CBOE 공개 CSV, 재시도 포함."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(VIX_CSV_URL, timeout=20)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                continue
            raise RuntimeError(f"CBOE VIX CSV 조회 실패: {exc}") from exc
    lines = resp.text.strip().splitlines()
    header = lines[0].split(",")
    close_idx = header.index("CLOSE")
    out: dict[str, float] = {}
    for line in lines[1:]:
        parts = line.split(",")
        month, day, year = parts[0].split("/")
        iso = f"{year}-{int(month):02d}-{int(day):02d}"
        out[iso] = float(parts[close_idx])
    return out


def fetch_spy_closes(since_iso: str) -> dict[str, float]:
    """날짜 -> SPY 비조정 종가. 토스증권 공식 시세 API 일봉."""
    closes = get_daily_closes("SPY", since_iso)
    if not closes:
        raise RuntimeError("SPY 종가 조회 결과가 비어 있음 — 토스 API 응답 확인 필요")
    return closes


def compute_rv20(closes_by_date: dict[str, float], ordered_dates: list[str]) -> dict[str, float]:
    """각 날짜의 RV20(연율화 %). 앞 20개 로그수익률이 다 있어야 계산된다."""
    values = [closes_by_date[d] for d in ordered_dates]
    logret = [math.nan] + [math.log(values[i] / values[i - 1]) for i in range(1, len(values))]
    rv: dict[str, float] = {}
    for i in range(RV_WINDOW, len(ordered_dates)):
        window = logret[i - RV_WINDOW + 1:i + 1]
        if any(math.isnan(v) for v in window):
            continue
        mean = sum(window) / len(window)
        var = sum((v - mean) ** 2 for v in window) / (len(window) - 1)
        rv[ordered_dates[i]] = math.sqrt(var) * math.sqrt(252.0) * 100.0
    return rv


def latest_spread() -> dict[str, object]:
    """가장 최근 종가가 확정된 거래일의 spread와 그 날짜를 반환한다."""
    since = (dt.date.today() - dt.timedelta(days=LOOKBACK_CALENDAR_DAYS)).isoformat()
    spy_closes = fetch_spy_closes(since)
    vix_closes = fetch_vix_closes()
    spy_dates = sorted(spy_closes)
    rv = compute_rv20(spy_closes, spy_dates)
    common_dates = [d for d in spy_dates if d in rv and d in vix_closes]
    if not common_dates:
        raise RuntimeError("SPY RV20과 VIX 종가가 겹치는 날짜가 없음 — 데이터 소스 점검 필요")
    latest_date = common_dates[-1]
    spread = vix_closes[latest_date] - rv[latest_date]
    return {"date": latest_date, "vix_close": vix_closes[latest_date],
            "rv20": rv[latest_date], "spread": spread}


def decide_state(spread: float, previous_state: float | None) -> float:
    """동결 규칙: entry/exit 돌파시에만 전환, 아니면 직전 state 유지."""
    if previous_state is None:
        previous_state = 1.0  # 최초 시드가 없을 때의 보수적 기본값(risk-on) — 실제로는 state 파일 시드 사용 권장
    if spread <= ENTRY:
        return 0.0
    if spread >= EXIT:
        return 1.0
    return previous_state
