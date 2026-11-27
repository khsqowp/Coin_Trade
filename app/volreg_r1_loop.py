"""VOLREG-R1 포워드 가상매매 메인 루프 — 동결 파라미터(entry=-2.5, exit=2.5, SPY50/QQQ50/SHY)
를 한투 모의투자 계좌에서 실행만 한다. 재튜닝 없음(PREREG_VOLREG_R1_TEST_FREEZE.md 참고).

하루 2번:
  - 장마감후(SIGNAL_AFTER, America/New_York 16:10 이후, 하루 1회): 신호 계산해 pending state 저장.
  - 장시작후(REBALANCE_AFTER, 09:35 이후, 하루 1회): pending state와 실제 체결된 state가 다르면
    리밸런싱 주문을 낸다("next_session_adjusted_open" 동결 정의와 동일하게 신호 다음날 시가 체결).

us_swing_loop.py와 동일하게 watchdog으로 각 사이클에 타임아웃을 건다.
"""
from __future__ import annotations

import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

from app.kis_auth import issue_token
from app.volreg_r1_order import rebalance
from app.volreg_r1_signal import decide_state, latest_spread
from app.volreg_r1_state import SEED_STATE, SEED_STATE_AS_OF, load_state, log_event, save_state
from app.watchdog import run_with_timeout

# kr_watchlist.py/us_watchlist.py와 동일 계좌(모의투자 1천만원 예산을 국장/미장 반반 나눈 그
# 계좌) — 두 파일도 이 값을 import로 공유하지 않고 각자 하드코딩하는 기존 관례를 따른다.
CANO = "50203118"
ACNT_PRDT_CD = "01"

ET = ZoneInfo("America/New_York")
SIGNAL_AFTER = dt.time(16, 10)
REBALANCE_AFTER = dt.time(9, 35)
LOOP_SLEEP_SECONDS = int(os.environ.get("VOLREG_R1_LOOP_SLEEP_SECONDS", "30"))
TOKEN_TTL_SECONDS = 12 * 3600
CYCLE_TIMEOUT_SECONDS = 60

# 리밸런싱 주문 규모 계산에 쓸 USD 현금 조회 필드명을 KIS 응답에서 확정 못 했다(이번 세션
# 모의투자 인증 문제로 inquire_balance output2 실측 불가). 인증 복구 후 실제 응답을 찍어보고
# 맞는 필드로 교체할 것 — 그 전까지는 모르는 필드면 조용히 0으로 두지 않고 바로 예외를 던진다.
_CASH_FIELD_CANDIDATES = ("frcr_dncl_amt_2", "frcr_dncl_amt1", "frcr_evlu_amt2", "ustl_evlu_amt")


def _get_cash_usd(token: str) -> float:
    from app.kis_overseas_order import inquire_balance
    for excg in ("NASD", "NYSE", "AMEX"):
        body = inquire_balance(token, CANO, ACNT_PRDT_CD, excg)
        if body.get("rt_cd") != "0":
            continue
        output2 = body.get("output2", {})
        for field in _CASH_FIELD_CANDIDATES:
            if field in output2:
                return float(output2[field])
    raise RuntimeError(
        f"USD 현금 필드를 output2에서 못 찾음(시도: {_CASH_FIELD_CANDIDATES}) — "
        "실제 응답 구조를 확인해 _CASH_FIELD_CANDIDATES를 고쳐야 함")


def _run_signal_cycle(token: str, state: dict) -> None:
    today_et = dt.datetime.now(ET).date().isoformat()
    if state.get("last_signal_date") == today_et:
        return
    if state.get("regime_state") is None:
        state["regime_state"] = SEED_STATE
        state["regime_state_asof_date"] = SEED_STATE_AS_OF
        log_event(state, f"초기 상태 시드: {SEED_STATE}(as of {SEED_STATE_AS_OF})")
    result = latest_spread(token)
    new_state = decide_state(float(result["spread"]), state.get("regime_state"))
    state["spread_history"].append({**result, "state": new_state})
    state["spread_history"] = state["spread_history"][-180:]
    state["pending_target_state"] = new_state
    state["last_signal_date"] = today_et
    log_event(state, f"신호계산 {result['date']}: VIX={result['vix_close']:.2f} "
                     f"RV20={result['rv20']:.2f} spread={result['spread']:.2f} -> state={new_state}")


def _run_rebalance_cycle(token: str, state: dict) -> None:
    today_et = dt.datetime.now(ET).date().isoformat()
    if state.get("last_rebalance_date") == today_et:
        return
    pending = state.get("pending_target_state")
    if pending is None:
        return
    if state.get("regime_state") == pending and state.get("executed_weights", {}).get("SPY") is not None:
        state["last_rebalance_date"] = today_et
        return
    cash_usd = _get_cash_usd(token)
    logs = rebalance(token, CANO, ACNT_PRDT_CD, pending, cash_usd)
    state["regime_state"] = pending
    from app.volreg_r1_order import TARGET_WEIGHTS
    state["executed_weights"] = TARGET_WEIGHTS[pending]
    state["last_rebalance_date"] = today_et
    for entry in logs:
        log_event(state, f"주문 {entry['symbol']} {entry['side']} {entry['qty']}주 "
                         f"@{entry['limit_price']}: rt_cd={entry['rt_cd']} {entry['msg1']}")
    if not logs:
        log_event(state, f"리밸런싱: 목표 state={pending}, 실제 주문 없음(이미 목표비중)")


def main() -> None:
    state = load_state()
    log_event(state, "VOLREG-R1 포워드 가상매매 루프 시작")
    save_state(state)

    token = issue_token()
    token_issued_at = time.monotonic()

    while True:
        try:
            if time.monotonic() - token_issued_at > TOKEN_TTL_SECONDS:
                token = issue_token()
                token_issued_at = time.monotonic()

            now = dt.datetime.now(ET)
            is_weekday = now.weekday() < 5

            if is_weekday and now.time() >= SIGNAL_AFTER:
                state = load_state()
                run_with_timeout(
                    lambda: _run_signal_cycle(token, state), CYCLE_TIMEOUT_SECONDS,
                    on_timeout=lambda: print("[경고] 신호계산이 타임아웃", flush=True))
                save_state(state)
            if is_weekday and now.time() >= REBALANCE_AFTER:
                state = load_state()
                run_with_timeout(
                    lambda: _run_rebalance_cycle(token, state), CYCLE_TIMEOUT_SECONDS,
                    on_timeout=lambda: print("[경고] 리밸런싱이 타임아웃", flush=True))
                save_state(state)
        except Exception as exc:  # noqa: BLE001
            state = load_state()
            log_event(state, f"[오류] 루프 사이클 실패: {exc}")
            save_state(state)

        time.sleep(LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
