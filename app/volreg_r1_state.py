"""VOLREG-R1 포워드 가상매매 상태 저장소 — us_state.py와 동일 패턴.

고정 파라미터(entry=-2.5, exit=2.5, SPY/QQQ/SHY)는 PREREG_VOLREG_R1_TEST_FREEZE.md에서
동결됐다. 포워드 가상매매는 그 동결 파라미터를 그대로 실행만 하는 것이고 재튜닝이 아니다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.state_io import atomic_write_json

STATE_PATH = Path(os.environ.get("VOLREG_R1_STATE_PATH", "/app/data/volreg_r1_state.json"))

# 2026-11-19 종가까지 TRAIN_TRIALS.csv에 적힌 동결 백테스트와 동일한 입력(VIX cboe parquet,
# SPY/QQQ/SHY yahoo parquet)으로 다시 계산한 레짐 상태(診断용 재계산, 신규 trial 아님).
# 포워드 루프 최초 기동시 이 값을 시드로 쓰고, 첫 사이클에서 곧바로 최신 데이터로 재계산해 덮어쓴다.
SEED_STATE_AS_OF = "2026-11-19"
SEED_STATE = 1.0  # risk-on: SPY 0.5 / QQQ 0.5 / SHY 0.0

_DEFAULT_STATE = {
    "regime_state": None,          # 1.0(risk-on) 또는 0.0(risk-off); None이면 아직 시드 안 됨
    "regime_state_asof_date": None,  # 이 상태를 결정한 신호 계산 기준일(세션 종가일, "YYYY-MM-DD")
    "executed_weights": {"SPY": None, "QQQ": None, "SHY": None},  # 실제로 마지막에 체결한 목표비중
    "last_signal_date": None,      # 마지막으로 신호를 계산한 날(미국 동부시간 기준 거래일)
    "last_rebalance_date": None,   # 마지막으로 리밸런싱 주문을 낸 날
    "pending_target_state": None,  # 신호계산 완료, 아직 다음 장시작 체결 대기중인 목표 state
    "spread_history": [],          # [{date, vix_close, rv20, spread, state}] 최근 180개
    "trade_log": [],
    "equity_history": [],          # [{ts, nav, spy_nav}] 포워드 시작 이후 전략 대 SPY 비교용
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
    atomic_write_json(STATE_PATH, state)


def log_event(state: dict, message: str) -> None:
    entry = {"ts": now_iso(), "message": message}
    state.setdefault("trade_log", []).append(entry)
    state["trade_log"] = state["trade_log"][-2000:]
    print(f"[{entry['ts']}] {message}", flush=True)
