"""국장/미장 top-N 모멘텀 로테이션 페이퍼봇 상태 저장소.

KIS 잔고조회가 실제 보유/현금의 진실 소스이고, 여기엔 전략 부가정보(리밸런스 타이밍,
목표 바스켓, 대기 주문 큐, 원가 원장, 대시보드용 히스토리)만 둔다. kr_state/us_state 와
같은 패턴, 경로만 ROTATION_STATE_PATH 로 분리한다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path(os.environ.get("ROTATION_STATE_PATH", "/app/data/stock_rotation_state.json"))
CURRENCY = os.environ.get("ROTATION_CURRENCY", "KRW")

_DEFAULT_STATE = {
    "entry_cost": {},            # {symbol: 매수원가}
    "symbol_names": {},          # {symbol: 표시명}
    "realized_pnl": 0.0,         # 누적 실현손익
    "target_basket": [],         # 최근 리밸런스가 정한 목표 보유 종목
    "pending_sells": [],         # 다음 장중에 처분할 종목
    "pending_buys": [],          # 다음 장중에 매수할 종목
    "last_plan_date": None,      # 리밸런스 계획을 세운 마지막 시장일 "YYYY-MM-DD"
    "last_rebalance_date": None, # 큐를 다 소비해 실제 리밸런스가 끝난 마지막 시장일
    "regime_cash": False,        # 최근 계획에서 레짐필터가 전액현금을 지시했는지
    "trade_log": [],
    "equity_history": [],        # [{ts, total_pnl, equity}]
    "position_history": {},      # {symbol: [{ts, price, unrealized_pnl}]}
    # --- 수동 제어 (즉시 매도 / 즉시 진입) ---
    "manual_flat": False,        # True면 전량 매도 상태로 정지, 자동 재진입 안 함
    "manual_flat_ts": None,
    "manual_flat_pending": False,  # 장 마감 중 청산 명령 — 다음 개장 때 실행 대기
    "consumed_control_nonce": None,
    # --- 봇 헬스 (KIS 모의투자 서버 연결 불안정 감지용) ---
    "consecutive_cycle_failures": 0,  # 연속으로 실패한 루프 사이클 수, 한 번이라도 성공하면 0으로 리셋
    "last_cycle_error": None,         # 마지막 실패 사유 문자열
    "last_cycle_error_ts": None,      # 마지막 실패 시각
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return json.loads(json.dumps(_DEFAULT_STATE))
    state = json.loads(STATE_PATH.read_text())
    for key, default in _DEFAULT_STATE.items():
        state.setdefault(key, json.loads(json.dumps(default)))
    return state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    os.replace(tmp_path, STATE_PATH)


def log_event(state: dict, message: str) -> None:
    entry = {"ts": now_iso(), "message": message}
    state.setdefault("trade_log", []).append(entry)
    state["trade_log"] = state["trade_log"][-2000:]
    print(f"[{entry['ts']}] {message}", flush=True)
