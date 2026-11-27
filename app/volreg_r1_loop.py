"""VOLREG-R1 포워드 가상매매 메인 루프 — 동결 파라미터(entry=-2.5, exit=2.5, SPY50/QQQ50/SHY)
를 실행만 한다. 재튜닝 없음(PREREG_VOLREG_R1_TEST_FREEZE.md 참고).

실거래 아님: 토스증권 공식 시세 API(app/toss_price.py)로 받은 현재가 기준 가상 현금/보유
수량을 state.json에 기록하는 장부용 포워드 가상매매다(2026-11-27 사용자 승인 — 한투 KIS
모의투자 인증이 계속 막혀서 "실거래 아니고 백테스트용 정보 받아오기면 진행"으로 전환).

하루 2번:
  - 장마감후(SIGNAL_AFTER, America/New_York 16:10 이후, 하루 1회): 신호 계산해 pending state 저장.
  - 장시작후(REBALANCE_AFTER, 09:35 이후, 하루 1회): pending state와 실제 체결된 state가 다르면
    가상 리밸런싱을 기록한다("next_session_adjusted_open" 동결 정의와 동일하게 신호 다음날 시가 체결 근사).

us_swing_loop.py와 동일하게 watchdog으로 각 사이클에 타임아웃을 건다.
"""
from __future__ import annotations

import datetime as dt
import os
import time
from zoneinfo import ZoneInfo

from app.volreg_r1_order import TARGET_WEIGHTS, rebalance
from app.volreg_r1_signal import decide_state, latest_spread
from app.volreg_r1_state import SEED_STATE, SEED_STATE_AS_OF, load_state, log_event, save_state
from app.watchdog import run_with_timeout

ET = ZoneInfo("America/New_York")
SIGNAL_AFTER = dt.time(16, 10)
REBALANCE_AFTER = dt.time(9, 35)
LOOP_SLEEP_SECONDS = int(os.environ.get("VOLREG_R1_LOOP_SLEEP_SECONDS", "30"))
CYCLE_TIMEOUT_SECONDS = 60


def _run_signal_cycle(state: dict) -> None:
    today_et = dt.datetime.now(ET).date().isoformat()
    if state.get("last_signal_date") == today_et:
        return
    if state.get("regime_state") is None:
        state["regime_state"] = SEED_STATE
        state["regime_state_asof_date"] = SEED_STATE_AS_OF
        log_event(state, f"초기 상태 시드: {SEED_STATE}(as of {SEED_STATE_AS_OF})")
    result = latest_spread()
    new_state = decide_state(float(result["spread"]), state.get("regime_state"))
    state["spread_history"].append({**result, "state": new_state})
    state["spread_history"] = state["spread_history"][-180:]
    state["pending_target_state"] = new_state
    state["last_signal_date"] = today_et
    log_event(state, f"신호계산 {result['date']}: VIX={result['vix_close']:.2f} "
                     f"RV20={result['rv20']:.2f} spread={result['spread']:.2f} -> state={new_state}")


def _run_rebalance_cycle(state: dict) -> None:
    today_et = dt.datetime.now(ET).date().isoformat()
    if state.get("last_rebalance_date") == today_et:
        return
    pending = state.get("pending_target_state")
    if pending is None:
        return
    if state.get("regime_state") == pending and state.get("executed_weights", {}).get("SPY") is not None:
        state["last_rebalance_date"] = today_et
        return
    logs = rebalance(state, pending)
    state["regime_state"] = pending
    state["executed_weights"] = TARGET_WEIGHTS[pending]
    state["last_rebalance_date"] = today_et
    for entry in logs:
        log_event(state, f"가상매매 {entry['symbol']} {entry['side']} {entry['qty']}주 "
                         f"@{entry['price']:.2f}(비용 ${entry['cost_usd']})")
    if not logs:
        log_event(state, f"리밸런싱: 목표 state={pending}, 가상 거래 없음(이미 목표비중)")
    else:
        log_event(state, f"리밸런싱 완료: NAV=${state['nav_usd']:.2f}")


def main() -> None:
    state = load_state()
    log_event(state, "VOLREG-R1 포워드 가상매매 루프 시작(실거래 아님)")
    save_state(state)

    while True:
        try:
            now = dt.datetime.now(ET)
            is_weekday = now.weekday() < 5

            if is_weekday and now.time() >= SIGNAL_AFTER:
                state = load_state()
                run_with_timeout(
                    lambda: _run_signal_cycle(state), CYCLE_TIMEOUT_SECONDS,
                    on_timeout=lambda: print("[경고] 신호계산이 타임아웃", flush=True))
                save_state(state)
            if is_weekday and now.time() >= REBALANCE_AFTER:
                state = load_state()
                run_with_timeout(
                    lambda: _run_rebalance_cycle(state), CYCLE_TIMEOUT_SECONDS,
                    on_timeout=lambda: print("[경고] 리밸런싱이 타임아웃", flush=True))
                save_state(state)
        except Exception as exc:  # noqa: BLE001
            state = load_state()
            log_event(state, f"[오류] 루프 사이클 실패: {exc}")
            save_state(state)

        time.sleep(LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    main()
